from dataclasses import dataclass
from io import TextIOWrapper
import os
from pathlib import Path
import shutil
import signal
import subprocess
import threading
from typing import Any, Optional, Self

class WithVerbose:
    def __init__(self, printer: "Printer", verbose: bool):
        self._printer = printer
        self._verbose = verbose
    
    def __enter__(self) -> Self:
        self._old_verbose = self._printer.get_verbose()
        self._printer.set_verbose(self._verbose)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._printer.set_verbose(self._old_verbose)

class WithFile:
    def __init__(self, printer: "Printer", file: TextIOWrapper):
        self._printer = printer
        self._file = file
    
    def __enter__(self) -> Self:
        self._printer.add_file(self._file)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._printer.remove_file(self._file)

class Printer:
    def __init__(self):
        self._level = 0
        self._new_line = True
        self.set_padding()
        self.set_verbose()
        self.set_files([])
    
    def set_verbose(self, verbose: bool = True) -> None:
        self._verbose = verbose

    def get_verbose(self) -> bool:
        return self._verbose

    def set_padding(self, padding: str = "  ") -> Self:
        self._padding = padding
        return self
    
    def get_padding(self) -> str:
        return self._padding

    def set_files(self, file: list[TextIOWrapper]) -> None:
        self._files = file

    def get_file(self) -> list[TextIOWrapper]:
        return self._files

    def add_file(self, file: TextIOWrapper) -> None:
        if file not in self._files:
            self._files.append(file)
    
    def remove_file(self, file: TextIOWrapper) -> None:
        self._files.remove(file)

    def __enter__(self) -> Self:
        self._level += 1
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._level -= 1

    def with_verbose(self, verbose: bool) -> "WithVerbose":
        return WithVerbose(self, verbose)
    
    def with_file(self, file: TextIOWrapper) -> "WithFile":
        return WithFile(self, file)

    def __call__(self, text: str = "", end: str = "\n", flush: bool = True) -> Self:
        if not self._verbose:
            return self
        text += end
        if self._new_line:
            self._new_line = False
            text = self._padding * self._level + text
        if text.endswith("\n"):
            self._new_line = True
            text = text[:-1].replace("\n", "\n" + self._padding * self._level) + "\n"
        else:
            text = text.replace("\n", "\n" + self._padding * self._level)
        print(text, end="", flush=flush)
        for file in self._files:
            print(text, end="", flush=flush, file=file)
        return self

printer = Printer()

@dataclass
class ShellOutput:
    value: str
    code: int
    timeout: bool

class ShellError(Exception):
    pass

class ShellTimeoutError(ShellError):
    pass

def shell(
    command: str,
    verbose: bool = False,
    timeout: Optional[float] = None,
    check: bool = True,
    cwd: Optional[str | Path] = None,
    env: Optional[dict[str, str]] = None
) -> ShellOutput:
    with printer.with_verbose(verbose):
        message = f"Shell"
        if timeout is not None:
            message += f" (timeout: {timeout}s)"
        if cwd is not None:
            message += f" (cwd: {cwd})"
        if env is not None:
            message += f" (env: {env})"
        printer(message + ":")
        with printer:
            printer(command)
            proc = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1, # line-buffered text mode
                universal_newlines=True,
                cwd=cwd,
                env=env,
                shell=True,
                start_new_session=True,
            )
            captured: list[str] = []
            def _reader():
                assert proc.stdout is not None
                for line in proc.stdout:
                    printer(line, end="")
                    captured.append(line)
            t = threading.Thread(target=_reader, daemon=True)
            t.start()
            timeout_error = False
            try:
                rc = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timeout_error = True
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
            output = ShellOutput("".join(captured), rc, timeout_error)
            if check and output.timeout:
                raise ShellTimeoutError(f"Timeout after {timeout}s")
            if check and output.code != 0:
                raise ShellError(f"Non-Zero exit: {output.code}")
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

def get_children(dir_path: Path) -> list[Path]:
    assert dir_path.is_dir(), "dir_path must be a path to a directory"
    return sorted(dir_path.iterdir(), key=lambda path: path.name)

def is_empty(dir_path: Path) -> bool:
    return not (dir_path.is_dir() and any(dir_path.iterdir()))

def uniquify_path(path: Path) -> Path:
    stem = path.stem
    suffix = path.suffix
    index = 0
    while path.exists():
        path = path.parent / f"{stem}.{index}{suffix}"
        index += 1
    return path