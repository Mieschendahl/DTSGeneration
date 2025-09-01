from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import threading
from typing import Optional

@dataclass
class ShellOutput:
    value: str
    code: int
    timeout: bool

class ShellError(Exception):
    pass

def shell(
    command: str,
    show_output: bool = True,
    timeout: Optional[float] = None,
    check: bool = True,
    cwd: Optional[str | Path] = None,
    env: Optional[dict[str, str]] = None
) -> ShellOutput:
    if show_output:
        print(command)

    # Start in a new session so we can kill the whole group on timeout
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,                # line-buffered text mode
        universal_newlines=True,  # ensures iteration yields lines
        cwd=cwd,
        env=env,
        shell=True,
        start_new_session=True,   # <<< key
    )

    captured: list[str] = []

    def _reader():
        assert proc.stdout is not None
        for line in proc.stdout:
            if show_output:
                print(line, end="")
            captured.append(line)

    t = threading.Thread(target=_reader, daemon=True)
    t.start()

    timeout_error = False
    try:
        rc = proc.wait(timeout=timeout)  # timeout=None means wait forever (same as before)
    except subprocess.TimeoutExpired:
        timeout_error = True
        # Announce + capture (was stderr in wrapper, but you merged stderr->stdout,
        # so including it in captured output preserves user-facing behavior)
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()

        rc = 124  # like GNU timeout

    # Ensure we've drained stdout and the thread exited
    t.join()

    if show_output:
        print()

    output = ShellOutput("".join(captured), rc, timeout_error)
    if check and output.code != 0:
        raise ShellError(f"Non-zero exit: {output.code}\nCommand: {command}\nOutput: {output.value}")
    return output

def create_dir(dst_path: Path, src_path: Optional[Path] = None, overwrite: bool = False) -> None:
    if overwrite:
        shutil.rmtree(dst_path, ignore_errors=True)
    if src_path is None:
        dst_path.mkdir(parents=True, exist_ok=True)
    else:
        shutil.copytree(src_path, dst_path, dirs_exist_ok=True, symlinks=True)

def create_file(dst_path: Path, src_path: Optional[Path] = None, content: Optional[str] = None) -> None:
    create_dir(dst_path.parent)
    if src_path is None:
        dst_path.write_text("" if content is None else content)
    else:
        dst_path.write_text(src_path.read_text())

def escape_package_name(package_name: str) -> str:
    if package_name.startswith("@"):
        scope, package_name = package_name[1:].split("/", 1)
        return f"{scope}__{package_name}"
    return package_name

def unescape_package_name(name: str) -> str:
    if "__" in name:
        scope, pkg = name.split("__", 1)
        return f"@{scope}/{pkg}"
    return name

def clone_package_repository(package_name: str, clone_path: Path, overwrite: bool = False) -> None:
    if clone_path.exists() and not overwrite:
        print(f"{clone_path} already exists. Skipping clone.")
        return

    result = shell(f"npm view {package_name} repository --json").value
    if result == "":
        raise Exception("No value returned by npm view")

    repo_data = json.loads(result)
    url = None
    if isinstance(repo_data, dict):
        url = repo_data.get("url")
    elif isinstance(repo_data, str):
        url = repo_data
    if not isinstance(url, str):
        raise Exception(f"Unexpected value returned by npm view: {result}")
    if "github.com" not in url:
        raise Exception(f"Invalid URL returned by npm view: {url}")
    github_url = "https://github.com" + url.split("github.com", 1)[-1].split(".git")[0]

    create_dir(clone_path, overwrite=True)
    shell(f"git clone --depth 1 {github_url} {clone_path}")

def get_readme(repository_path: Path) -> str:
    readme_names = [
        'README.md', 'README.rst', 'README.txt', 'README',
        'readme.md', 'readme.rst', 'readme.txt', 'readme',
        'Readme.md', 'Readme.rst', 'Readme.txt', 'Readme',
        "README.markdown", "readme.markdown"
    ]
    for name in readme_names:
        try:
            readme_path = repository_path / name
            if readme_path.is_file():
                return readme_path.read_text()
        except:
            pass
    raise Exception("No README file found")

def get_main(repository_path: Path, package_name: str) -> str:
    package_json_path = repository_path / "package.json"
    if package_json_path.is_file():
        try:
            package_json = json.loads(package_json_path.read_text())
            main_path = repository_path / package_json["main"]
            if main_path.is_file():
                return main_path.read_text()
        except Exception:
            pass

    candidates = [
        "index.js",
        "main.js",
        "app.js",
        f"{package_name.split("/")[-1]}.js"
    ]
    for prefix in ["", "src", "source", "dist", "lib"]:
        for main_path in candidates:
            main_path = repository_path / prefix / main_path
            if main_path.is_file():
                return main_path.read_text()
    raise Exception("No main file found")

def get_tests(repository_path: Path) -> list[dict[str, str]]:
    test_dirs = ["test", "tests", "__tests__"]
    test_suffixes = [".test.js", ".spec.js", ".test.ts", ".spec.ts"]
    tests = []

    # 1. Check well-known test directories
    for d in test_dirs:
        test_path = repository_path / d
        if test_path.is_dir():
            for f in test_path.rglob("*.js"):
                tests.append(dict(path=f.relative_to(repository_path), content=f.read_text()))
            for f in test_path.rglob("*.ts"):
                tests.append(dict(path=f.relative_to(repository_path), content=f.read_text()))

    # 2. Also scan entire repo for suffixes
    for suffix in test_suffixes:
        for f in repository_path.rglob(f"*{suffix}"):
            if f.suffix in (".js", ".ts"):
                tests.append(dict(path=f.relative_to(repository_path), content=f.read_text()))
    if len(tests) == 0:
        raise Exception("No tests found")
    return [test for test in tests if test["content"]]

def build_definitely_typed(clone_path: Path) -> None:
    if clone_path.exists():
        print(f"{clone_path} already exists. Skipping installation.")
    else:
        create_dir(clone_path)
        shell(f"git clone --depth 1 https://github.com/DefinitelyTyped/DefinitelyTyped.git {clone_path.resolve()}")

def build_tsd(tsd_path: Path) -> None:
    project_name = "master-mind-wp3"
    clone_path = tsd_path / project_name
    repo_url = "https://github.com/Proglang-TypeScript/run-time-information-gathering.git"
    if clone_path.exists():
        print(f"{clone_path} already exists. Skipping installation.")
    else:
        create_dir(clone_path)
        shell(f"git clone --depth 1 {repo_url} {clone_path}")
        shell(f"{clone_path}/build/build.sh", check=False)
        print("...ingnoring test errors\n")

    project_name = "tsd-generator"
    clone_path = tsd_path / project_name
    repo_url = "https://github.com/Proglang-TypeScript/ts-declaration-file-generator.git"
    if clone_path.exists():
        print(f"{clone_path} already exists. Skipping installation.")
    else:
        create_dir(clone_path)
        shell(f"git clone --depth 1 {repo_url} {clone_path}")
        shell(f"{clone_path}/build/build.sh")