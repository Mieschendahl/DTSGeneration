import platform
from pathlib import Path

from dts_generation._utils import *

def generate_declarations(
    package_name: str,
    generation_path: Path,
    build_path: Path,
    verbose_setup: bool,
    verbose_execution: bool,
    verbose_files: bool,
    combined_only: bool,
    reproduce: bool
) -> None:
    with printer(f"Generating declarations:"):
        examples_path = generation_path / EXAMPLES_PATH
        declarations_path = generation_path / DECLARATIONS_PATH
        template_path = generation_path / TEMPLATE_PATH
        playground_path = generation_path / PLAYGROUND_PATH
        transpile_path = build_path / TRANSPILE_PATH
        build_run_time_information_gathering(build_path, verbose_setup)
        build_ts_declaration_file_generator(build_path, verbose_setup)
        build_npm_tools(build_path, verbose_setup)
        build_template_project(package_name, generation_path, verbose_setup, reproduce)
        for sub_path in COMBINED_MODE_PATHS if combined_only else ALL_MODE_PATHS:
            examples_sub_path = examples_path / sub_path
            if dir_empty(examples_sub_path):
                break
            children = get_children(examples_sub_path)
            with printer(f"Found {len(children)} example(s) for {sub_path}:"):
                declarations_sub_path = declarations_path / sub_path
                create_dir(declarations_sub_path)
                for example_path in children:
                    with printer(f"Generating declaration for {example_path.name}:"):
                        if verbose_files:
                            with printer(f"Example content:"):
                                printer(example_path.read_text())
                        create_dir(playground_path, template_path, overwrite=True)
                        main_path = playground_path / "index.js"
                        create_file(main_path, example_path)
                        # Transpile the example into JavaScript 5 (does not polyfill missing API such as e.g. promises)
                        with printer(f"Transpiling example into ES5:"):
                            shell_output = shell(
                                f"node {transpile_path.resolve()} {main_path.relative_to(playground_path)}",
                                cwd=playground_path,
                                check=False,
                                timeout=EXECUTION_TIMEOUT,
                                verbose=verbose_execution
                            )
                            if shell_output.code:
                                printer(f"Fail")
                                continue
                            printer(f"Success")
                        if verbose_files:
                            with printer(f"Transpiled example content:"):
                                printer(main_path.read_text())
                        # Apply run time information analysis using Jalangi 2
                        with printer(f"Running {RUN_TIME_ANALYZER_PATH.name}:"):
                            if platform.system() == "Linux":
                                script_path = DECLARATION_SCRIPTS_PATH / "getRunTimeInformation.linux.sh"
                            else:
                                script_path = DECLARATION_SCRIPTS_PATH / "getRunTimeInformation.sh"
                            run_time_path = playground_path / RUN_TIME_ANALYZER_PATH.name / "run_time_info.json"
                            create_dir(run_time_path.parent, overwrite=True)           
                            shell_output = shell(
                                f"{script_path} {main_path.relative_to(playground_path)} {run_time_path.relative_to(playground_path)} {EXECUTION_TIMEOUT * 2}",
                                cwd=playground_path,
                                check=False,
                                timeout=EXECUTION_TIMEOUT,
                                verbose=verbose_execution
                            )
                            if shell_output.code or not run_time_path.is_file() or not run_time_path.read_text():
                                printer(f"Fail")
                                continue
                            printer(f"Success")
                        # Generate .d.ts file using dts-generate
                        with printer(f"Running {DECLARATION_GENERATOR_PATH.name}:"):
                            script_path = DECLARATION_SCRIPTS_PATH / "generateDeclarationFile.sh"
                            declaration_path = playground_path / DECLARATION_GENERATOR_PATH.name
                            create_dir(declaration_path, overwrite=True)
                            shell_output = shell(
                                f"{script_path} {run_time_path.relative_to(playground_path)} {package_name} {declaration_path.relative_to(playground_path)}",
                                cwd=playground_path,
                                check=False,
                                timeout=EXECUTION_TIMEOUT,
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