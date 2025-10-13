import platform
from pathlib import Path

from dts_generation._utils import get_children, is_empty, printer, create_file, shell, create_dir
from dts_generation._example import build_template_project

SCRIPTS_PATH = Path(__file__).parent.parent / "assets" / "declaration"

# currently not in development, so does not need a reproduction mode
def build_run_time_information_gathering(output_path: Path, installation_timeout: int, verbose_setup: bool) -> None:
    with printer(f"Cloning run-time-information-gathering repository:"):
        if not is_empty(output_path):
            printer(f"Success (already build)")
            return
        create_dir(output_path, overwrite=True)
        shell(
            f"git clone --depth 1 https://github.com/Proglang-TypeScript/run-time-information-gathering.git {output_path}",
            timeout=installation_timeout,
            verbose=verbose_setup
        )
        printer(f"Success")
    # We tie building the docker image to whether the repository needs to be cloned (simple build control)
    with printer(f"Building run-time-information-gathering docker image:"):
        shell(f"{output_path}/build/build.sh", check=False, timeout=installation_timeout, verbose=verbose_setup)
        # printer(f"Success")
        printer(f"Success (ignoring test errors)")

# currently not in development, so does not need a reproduction mode
def build_ts_declaration_file_generator(output_path: Path, installation_timeout: int, verbose_setup: bool) -> None:
    with printer(f"Cloning ts-declaration-file-generator repository:"):
        if not is_empty(output_path):
            printer(f"Success (already build)")
            return
        create_dir(output_path, overwrite=True)
        shell(
            f"git clone --depth 1 https://github.com/Proglang-TypeScript/ts-declaration-file-generator.git {output_path}",
            timeout=installation_timeout,
            verbose=verbose_setup
        )
        printer(f"Success")
    # We tie building the docker image to whether the repository needs to be cloned (simple build control)
    with printer(f"Building ts-declaration-file-generator docker image:"):
        shell(f"{output_path}/build/build.sh", timeout=installation_timeout, verbose=verbose_setup)
        printer(f"Success")

def build_npm_tools(output_path: Path, installation_timeout: int, verbose_setup: bool) -> None:
    with printer(f"Building npm tools:"):
        if not is_empty(output_path) and (output_path / "transpile.js").is_file():
            printer(f"Success (already build)")
            return
        create_dir(output_path, overwrite=True)
        create_file(output_path / "package.json", SCRIPTS_PATH / "package.json")
        create_file(output_path / "package-lock.json", SCRIPTS_PATH / "package-lock.json")
        create_file(output_path / "transpile.js", SCRIPTS_PATH / "transpile.js")
        shell(
            # f"npm install @babel/core @babel/preset-env", # dont use this because of reproducability,
            f"npm ci",
            cwd=output_path,
            timeout=installation_timeout,
            verbose=verbose_setup
        )
        printer(f"Success")

def generate_declarations(
    package_name: str,
    output_path: Path,
    build_path: Path,
    execution_timeout: int,
    installation_timeout: int,
    verbose_setup: bool,
    verbose_execution: bool,
    verbose_files: bool,
    reproduce: bool
) -> None:
    with printer(f"Generating declarations:"):
        build_run_time_information_gathering(build_path / "run-time-information-gathering", installation_timeout, verbose_setup)
        build_ts_declaration_file_generator(build_path / "ts-declaration-file-generator", installation_timeout, verbose_setup)
        build_npm_tools(build_path / "npm-tools", installation_timeout, verbose_setup)
        transpile_path = build_path / "npm-tools" / "transpile.js"
        # Setting up directory interface
        cache_path = output_path / "cache"
        create_dir(cache_path, overwrite=False)
        data_path = output_path / "data"
        create_dir(data_path, overwrite=False)
        examples_path = output_path / "examples"
        assert examples_path.is_dir(), "Example directory missing"
        transpiled_path = cache_path / "transpiled_examples"
        create_dir(transpiled_path, overwrite=True)
        playground_path = cache_path / "playground"
        create_dir(playground_path, overwrite=True)
        declarations_path = output_path / "declarations"
        create_dir(declarations_path, overwrite=True)
        template_path = cache_path / "template"
        build_template_project(package_name, data_path, template_path, installation_timeout, verbose_setup, reproduce)
        # Iterate over sub directories in the example directory (corresponding to the different example generation modes)
        for examples_sub_path in get_children(examples_path):
            if is_empty(examples_sub_path):
                continue
            with printer(f"Generating declarations for \"{examples_sub_path.name}\" mode:"):
                children = get_children(examples_sub_path)
                printer(f"Found {len(children)} example(s)")
                declarations_sub_path = declarations_path / examples_sub_path.name
                transpiled_sub_path = transpiled_path / examples_sub_path.name
                create_dir(declarations_sub_path, overwrite=True)
                for example_path in children:
                    with printer(f"Generating declaration for {example_path.name}:"):
                        if verbose_files:
                            with printer(f"Example content:"):
                                printer(example_path.read_text())
                        create_dir(playground_path, template_path, overwrite=True)
                        main_path = playground_path / "index.js"
                        create_file(main_path, example_path)
                        # Transpile the example into JavaScript 5
                        with printer(f"Transpiling into ES5:"):
                            shell_output = shell(
                                f"node {transpile_path.resolve()} {main_path.relative_to(playground_path)}",
                                cwd=playground_path,
                                check=False,
                                timeout=execution_timeout,
                                verbose=verbose_execution
                            )
                            if shell_output.code:
                                printer(f"Fail")
                                continue
                            printer(f"Success")
                        create_file(transpiled_sub_path / example_path.name, main_path)
                        if verbose_files:
                            with printer(f"Transpiled example content:"):
                                printer(main_path.read_text())
                        # Apply run time information analysis using Jalangi 2
                        with printer(f"Running run-time-information-gathering:"):
                            if platform.system() == "Linux":
                                script_path = SCRIPTS_PATH / "getRunTimeInformation.linux.sh"
                            else:
                                script_path = SCRIPTS_PATH / "getRunTimeInformation.sh"
                            run_time_path = playground_path / "run-time-information-gathering" / "run_time_info.json"
                            create_dir(run_time_path.parent, overwrite=True)           
                            shell_output = shell(
                                f"{script_path} {main_path.relative_to(playground_path)} {run_time_path.relative_to(playground_path)} {execution_timeout * 2}",
                                cwd=playground_path,
                                check=False,
                                timeout=execution_timeout,
                                verbose=verbose_execution
                            )
                            if shell_output.code or not run_time_path.is_file() or not run_time_path.read_text():
                                printer(f"Fail")
                                continue
                            printer(f"Success")
                        # Generate .d.ts file using dts-generate
                        with printer(f"Running ts-declaration-file-generator:"):
                            script_path = SCRIPTS_PATH / "generateDeclarationFile.sh"
                            declaration_path = playground_path / "ts-declaration-file-generator"
                            create_dir(declaration_path, overwrite=True)
                            shell_output = shell(
                                f"{script_path} {run_time_path.relative_to(playground_path)} {package_name} {declaration_path.relative_to(playground_path)}",
                                cwd=playground_path,
                                check=False,
                                timeout=execution_timeout,
                                verbose=verbose_execution
                            )
                            declaration_path = declaration_path / package_name / "index.d.ts"
                            if shell_output.code or not declaration_path.is_file() or not declaration_path.read_text():
                                printer(f"Fail")
                                continue
                            declaration = declaration_path.read_text().strip()
                            if verbose_files:
                                with printer(f"Declaration content:"):
                                    printer(declaration)
                            create_file(declarations_sub_path / example_path.name.replace(".js", ".d.ts"), content=declaration)
                            printer(f"Success")