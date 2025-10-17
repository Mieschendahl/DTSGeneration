import json
from pathlib import Path
from typing import Optional

from dts_generation._utils._helpers import create_dir, create_file, dir_empty, get_children, file_exists
from dts_generation._utils._shell import ShellError, shell
from dts_generation._utils._printer import printer
from dts_generation._utils._shared import CACHE_PATH, DATA_PATH, DECLARATION_SCRIPTS_PATH, TEMPLATE_PATH, PackageDataMissingError, PackageInstallationError, ReproductionError, INSTALLATION_TIMEOUT

BUILD_SUB_PATH = Path("builds")
RUN_TIME_ANALYZER_PATH = BUILD_SUB_PATH / "run-time-information-analyzer"
DECLARATION_GENERATOR_PATH = BUILD_SUB_PATH / "ts-declaration-file-generator"
DEFINITELY_TYPED_PATH = BUILD_SUB_PATH / "DefinitelyTyped"
NPM_TOOLS_PATH = BUILD_SUB_PATH / "npm-tools"
TRANSPILE_PATH = BUILD_SUB_PATH / "npm-tools" / "transpile.js"
REPOSITORY_PATH = CACHE_PATH / "repository"
PACKAGE_JSON_PATH = DATA_PATH / "package.json"
README_PATH = DATA_PATH / "README.md"
MAIN_PATH = DATA_PATH / "index.js"
TESTS_PATH = DATA_PATH / "tests"

def build_definitely_typed(build_path: Path, verbose_setup: bool, reproduce: bool) -> None:
    with printer.with_verbose(verbose_setup):
        with printer(f"Cloning the DefinitelyTyped repository:"):
            output_path = build_path / DEFINITELY_TYPED_PATH
            if not dir_empty(output_path):
                printer(f"Success (already cloned)")
                return
            create_dir(output_path, overwrite=True)
            shell(
                f"git clone --depth 1 https://github.com/DefinitelyTyped/DefinitelyTyped.git {output_path}",
                timeout=INSTALLATION_TIMEOUT,
                verbose=verbose_setup
            )
            if reproduce:
                shell(
                    # DefinitelyTyped version that the last big evaluation was performed on
                    f"git checkout 3b48ce35f1236733d9c1940eb95e6647b8a30852",
                    cwd=output_path,
                    timeout=INSTALLATION_TIMEOUT,
                    verbose=verbose_setup
                )
            printer(f"Success")

# currently not in development, so does not need a reproduction mode
def build_run_time_information_gathering(build_path: Path, verbose_setup: bool) -> None:
    with printer.with_verbose(verbose_setup):
        with printer(f"Cloning run-time-information-gathering repository:"):
            output_path = build_path / RUN_TIME_ANALYZER_PATH
            if not dir_empty(output_path):
                printer(f"Success (already build)")
                return None
            create_dir(output_path, overwrite=True)
            shell(
                f"git clone --depth 1 https://github.com/Proglang-TypeScript/run-time-information-gathering.git {output_path}",
                timeout=INSTALLATION_TIMEOUT,
                verbose=verbose_setup
            )
            printer(f"Success")
        # We tie building the docker image to whether the repository needs to be cloned (simple build control)
        with printer(f"Building run-time-information-gathering docker image:"):
            shell(f"{output_path}/build/build.sh", check=False, timeout=INSTALLATION_TIMEOUT, verbose=verbose_setup)
            # printer(f"Success")
            printer(f"Success (ignoring test errors)")

# currently not in development, so does not need a reproduction mode
def build_ts_declaration_file_generator(build_path: Path, verbose_setup: bool) -> None:
    with printer.with_verbose(verbose_setup):
        with printer(f"Cloning ts-declaration-file-generator repository:"):
            output_path = build_path / DECLARATION_GENERATOR_PATH
            if not dir_empty(output_path):
                printer(f"Success (already build)")
                return None
            create_dir(output_path, overwrite=True)
            shell(
                f"git clone --depth 1 https://github.com/Proglang-TypeScript/ts-declaration-file-generator.git {output_path}",
                timeout=INSTALLATION_TIMEOUT,
                verbose=verbose_setup
            )
            printer(f"Success")
        # We tie building the docker image to whether the repository needs to be cloned (simple build control)
        with printer(f"Building ts-declaration-file-generator docker image:"):
            shell(f"{output_path}/build/build.sh", timeout=INSTALLATION_TIMEOUT, verbose=verbose_setup)
            printer(f"Success")

def build_npm_tools(build_path: Path, verbose_setup: bool) -> None:
    with printer.with_verbose(verbose_setup):
        with printer(f"Building npm tools:"):
            output_path = build_path / NPM_TOOLS_PATH
            if not dir_empty(output_path) and (output_path / "transpile.js").is_file():
                printer(f"Success (already build)")
                return None
            create_dir(output_path, overwrite=True)
            create_file(output_path / "package.json", DECLARATION_SCRIPTS_PATH / "package.json")
            create_file(output_path / "package-lock.json", DECLARATION_SCRIPTS_PATH / "package-lock.json")
            create_file(output_path / "transpile.js", DECLARATION_SCRIPTS_PATH / "transpile.js")
            shell(
                # f"npm install @babel/core @babel/preset-env", # dont use this because of reproducability,
                f"npm ci",
                cwd=output_path,
                timeout=INSTALLATION_TIMEOUT,
                verbose=verbose_setup
            )
            printer(f"Success")

def build_template_project(package_name: str, generation_path: Path, verbose_setup: bool, reproduce: bool):
    with printer.with_verbose(verbose_setup):
        with printer(f"Building template npm project:"):
            output_path = generation_path / TEMPLATE_PATH
            if not dir_empty(output_path):
                printer("Success (already build)")
                return None
            create_dir(output_path, overwrite=True)
            with printer(f"Installing packages:"):
                data_path = generation_path / DATA_PATH
                try:
                    if reproduce:
                        if not file_exists(data_path / "package.json") or not file_exists(data_path / "package-lock.json"):
                            raise ReproductionError("Need package.json and package-lock.json from previous build, to build template project in reproduction mode")
                        create_file(output_path / "package.json", data_path / "package.json")
                        create_file(output_path / "package-lock.json", data_path / "package-lock.json")
                        shell(f"npm ci", cwd=output_path, timeout=INSTALLATION_TIMEOUT, verbose=verbose_setup)
                    else:
                        shell(f"npm install tsx typescript @types/node {package_name}", cwd=output_path, timeout=INSTALLATION_TIMEOUT, verbose=verbose_setup)
                        create_file(data_path / "package.json", output_path / "package.json")
                        create_file(data_path / "package-lock.json", output_path / "package-lock.json")
                    printer(f"Success")
                except ShellError as e:
                    raise PackageInstallationError(f"Running npm install {package_name} failed") from e

def clone_repository(package_name: str, generation_path: Path, verbose_setup: bool) -> None:#
    with printer.with_verbose(verbose_setup):
        with printer(f"Cloning the GitHub repository:"):
            output_path = generation_path / REPOSITORY_PATH
            if not dir_empty(output_path):
                printer(f"Success (already cloned)")
                return None
            create_dir(output_path)
            try:
                shell_output = shell(f"npm view {package_name} repository --json", timeout=INSTALLATION_TIMEOUT, verbose=verbose_setup)
            except ShellError as e:
                raise PackageDataMissingError(f"npm view failed") from e
            if not shell_output.value:
                raise PackageDataMissingError(f"No npm view value found")
            try:
                repo_data = json.loads(shell_output.value)
            except Exception as e:
                raise PackageDataMissingError(f"npm view value is invalid: {shell_output.value}") from e
            url = repo_data.get("url", "") if isinstance(repo_data, dict) else repo_data
            if "github.com" not in url:
                raise PackageDataMissingError(f"No GitHub URL found")
            github_url = "https://github.com" + url.split("github.com", 1)[-1].split(".git")[0]
            try:
                shell(f"git clone --depth 1 {github_url} {output_path}", timeout=INSTALLATION_TIMEOUT, verbose=verbose_setup)
            except ShellError as e:
                raise PackageDataMissingError(f"Git clone failed") from e
            if dir_empty(output_path):
                raise PackageDataMissingError(f"Repository clone is empty")
            printer(f"Success")

def get_package_json(generation_path: Path, verbose_setup: bool) -> Optional[str]:
    with printer.with_verbose(verbose_setup):
        package_json_path = generation_path / REPOSITORY_PATH / "package.json"
        output_path = generation_path / PACKAGE_JSON_PATH
        if package_json_path.is_file():
            try:
                package_json = package_json_path.read_text()
                create_file(output_path, content=package_json)
                printer(f"Package file found")
                return package_json
            except UnicodeDecodeError:
                pass
        printer(f"No package file found")

def get_readme(generation_path: Path, verbose_setup: bool) -> Optional[str]:
    with printer.with_verbose(verbose_setup):
        repository_path = generation_path / REPOSITORY_PATH
        output_path = generation_path / README_PATH
        for readme_path in get_children(repository_path):
            if readme_path.is_file() and "readme" in readme_path.name.lower():
                try:
                    readme = readme_path.read_text()
                    create_file(output_path, content=readme)
                    printer(f"Readme file found")
                    return readme_path.read_text()
                except UnicodeDecodeError:
                    pass
        printer(f"No readme file found")

def get_main(generation_path: Path, verbose_setup: bool) -> Optional[str]:
    with printer.with_verbose(verbose_setup):
        repository_path = generation_path / REPOSITORY_PATH
        package_json_path = repository_path / "package.json"
        output_path = generation_path / MAIN_PATH
        if package_json_path.is_file():
            # Check if package.json contains a main file reference
            try:
                package_json = json.loads(package_json_path.read_text())
                main_path = repository_path / package_json["main"]
                if main_path.is_file():
                    try:
                        main = main_path.read_text()
                        create_file(output_path, content=main)
                        printer(f"Main file found")
                        return main
                    except UnicodeDecodeError:
                        pass
            except (json.JSONDecodeError, KeyError):
                pass
            # Fallback: search for common main file names
            main_names = ["index.js", "index.json", "index.node"]
            for name in main_names:
                main_path = repository_path / name
                if main_path.is_file():
                    try:
                        main = main_path.read_text()
                        create_file(output_path, content=main)
                        printer(f"Main file found")
                        return main
                    except UnicodeDecodeError:
                        pass
            printer(f"No main file found")

def get_tests(generation_path: Path, verbose_setup: bool) -> list[tuple[str, str]]:
    with printer.with_verbose(verbose_setup):
        tests = {}
        repository_path = generation_path / REPOSITORY_PATH
        output_path = generation_path / TESTS_PATH
        create_dir(output_path)
        # Check well-known test directories
        test_dirs = ["test", "tests", "__tests__"]
        for d in test_dirs:
            test_path = repository_path / d
            if test_path.is_dir():
                for f in test_path.rglob("*.js"):
                    if f.is_file():
                        try:
                            tests[f.relative_to(repository_path)] = f.read_text()
                        except UnicodeDecodeError:
                            pass
        # Check repo for suffixes
        test_suffixes = [".test.js", ".spec.js"]
        for suffix in test_suffixes:
            for f in repository_path.rglob(f"*{suffix}"):
                if f.suffix ==".js":
                    if f.is_file():
                        try:
                            tests[f.relative_to(repository_path)] = f.read_text()
                        except UnicodeDecodeError:
                            pass
        tests = [(path, content) for path, content in sorted(tests.items()) if content]
        for i, (path, content) in enumerate(tests):
            (output_path / f"{i}.js").write_text(f"// File: {path}\n\n{content}")
        printer(f"{len(tests)} test file(s) found")
        return tests