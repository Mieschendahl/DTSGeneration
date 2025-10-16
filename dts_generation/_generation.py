from pathlib import Path
import shutil
import traceback

from dts_generation._utils import *
from dts_generation._examplification import generate_examples as generate_examples_helper
from dts_generation._declaration import generate_declarations as generate_declarations_helper
from dts_generation._comparison import generate_comparisons as generate_comparisons_helper

def generate(
    package_name: str,
    generation_path: Path,
    build_path: Path,
    verbose: bool = True,
    verbose_setup: bool = False,
    verbose_execution: bool = False,
    verbose_files: bool = False,
    remove_cache: bool = False,
    generate_examples: bool = True,
    generate_declarations: bool = True,
    generate_comparisons: bool = False,
    extract_from_readme: bool = False,
    generate_with_llm: bool = True,
    combine_examples: bool = True,
    combined_only: bool = True,
    reproduce: bool = False, # should generally be False, if not used by evaluation in reproduction mode
    overwrite: bool = True,
    llm_model_name: str = "gpt-4o-mini",
    llm_temperature: int = 0,
    llm_verbose: bool = False,
    llm_interactive: bool = False,
    llm_use_cache: bool = False
) -> None:
    data_path = generation_path / DATA_PATH
    create_dir(generation_path, overwrite=overwrite)
    if not dir_empty(data_path):
        printer(f"Skipping generation for \"{package_name}\" (already generated)")
        return None
    logs_path = generation_path / LOGS_PATH
    create_dir(generation_path / data_path)
    create_dir(generation_path / logs_path)
    create_dir(generation_path / EXAMPLES_PATH)
    create_dir(generation_path / DECLARATIONS_PATH)
    create_dir(generation_path / COMPARISONS_PATH)
    with open(logs_path / "shell.txt", "w") as log_file:
        with printer.with_file(log_file):
            with printer(f"Starting generation for \"{package_name}\":"):
                try:
                    with printer.with_verbose(verbose):
                        if generate_examples:
                            generate_examples_helper(
                                package_name=package_name,
                                generation_path=generation_path,
                                verbose_setup=verbose_setup,
                                verbose_execution=verbose_execution,
                                verbose_files=verbose_files,
                                extract_from_readme=extract_from_readme,
                                generate_with_llm=generate_with_llm,
                                combine_examples=combine_examples,
                                reproduce=reproduce,
                                llm_model_name=llm_model_name,
                                llm_temperature=llm_temperature,
                                llm_verbose=llm_verbose,
                                llm_interactive=llm_interactive,
                                llm_use_cache=llm_use_cache
                            )
                        if generate_declarations:
                            assert package_name == escape_package_name(package_name), "ts-declaration-file-generator does not support qualilfied package names"
                            generate_declarations_helper(
                                package_name=package_name,
                                generation_path=generation_path,
                                build_path=build_path,
                                verbose_setup=verbose_setup,
                                verbose_execution=verbose_execution,
                                verbose_files=verbose_files,
                                combined_only=combined_only,
                                reproduce=reproduce
                            )
                        if generate_comparisons:
                            generate_comparisons_helper(
                                package_name=package_name,
                                generation_path=generation_path,
                                build_path=build_path,
                                verbose_setup=verbose_setup,
                                verbose_execution=verbose_execution,
                                verbose_files=verbose_files,
                                combined_only=combined_only,
                                reproduce=reproduce
                            )
                            create_file(data_path / "usable")
                            printer(f"Generation succeeded for \"{package_name}\"")
                except CommonJSUnsupportedError:
                    create_file(data_path / "not_commonjs", content=traceback.format_exc())
                    printer(f"Generation failed for \"{package_name}\"")
                    raise
                except PackageDataMissingError:
                    create_file(data_path / "package_data_missing", content=traceback.format_exc())
                    printer(f"Generation failed for \"{package_name}\"")
                    raise
                except PackageInstallationError:
                    create_file(data_path / "package_installation_fail", content=traceback.format_exc())
                    printer(f"Generation failed for \"{package_name}\"")
                    raise
                except Exception:
                    create_file(data_path / "raised_error", content=traceback.format_exc())
                    printer(f"Generation failed for \"{package_name}\"")
                    raise
                finally:
                    if remove_cache:
                        shutil.rmtree(generation_path / "cache", ignore_errors=True)