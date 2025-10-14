from pathlib import Path
import shutil
import traceback

from dts_generation._utils import create_dir, create_file, escape_package_name, is_empty, printer
from dts_generation._example import CommonJSUnsupportedError, NodeJSUnsupportedError, PackageInstallationError, PackageDataMissingError, generate_examples as _generate_examples
from dts_generation._declaration import generate_declarations as _generate_declarations
from dts_generation._comparison import generate_comparisons as _generate_comparisons

def generate(
    package_name: str,
    output_path: Path,
    build_path: Path,
    execution_timeout: int = 60,
    installation_timeout: int = 600,
    verbose: bool = True,
    verbose_setup: bool = False,
    verbose_execution: bool = False,
    verbose_files: bool = False,
    remove_cache: bool = False,
    generate_examples: bool = True,
    generate_declarations: bool = True,
    generate_comparisons: bool = False,
    evaluate_with_llm: bool = True,
    extract_from_readme: bool = False,
    generate_with_llm: bool = True,
    llm_model_name: str = "gpt-4o-mini",
    llm_temperature: int = 0,
    llm_verbose: bool = False,
    llm_interactive: bool = False,
    llm_use_cache: bool = False,
    combine_examples: bool = True,
    combined_only: bool = True,
    reproduce: bool = False, # should generally be False, if not used by evaluation in reproduction mode
    overwrite: bool = True
) -> None:
    logs_path = output_path / "logs"
    create_dir(logs_path, overwrite=False)
    with open(logs_path / "shell.txt", "w") as log_file:
        with printer.with_file(log_file):
            with printer(f"Starting generation for \"{package_name}\":"):
                if not is_empty(output_path / "data") and not overwrite:
                    printer(f"Skipping generation (already generated)")
                    return
                create_dir(output_path, overwrite=True)
                data_path = output_path / "data"
                create_dir(data_path, overwrite=True)
                try:
                    with printer.with_verbose(verbose):
                        if generate_examples:
                            _generate_examples(
                                package_name=package_name,
                                output_path=output_path,
                                execution_timeout=execution_timeout,
                                installation_timeout=installation_timeout,
                                verbose_setup=verbose_setup,
                                verbose_execution=verbose_execution,
                                verbose_files=verbose_files,
                                evaluate_with_llm=evaluate_with_llm,
                                extract_from_readme=extract_from_readme,
                                generate_with_llm=generate_with_llm,
                                llm_model_name=llm_model_name,
                                llm_temperature=llm_temperature,
                                llm_verbose=llm_verbose,
                                llm_interactive=llm_interactive,
                                llm_use_cache=llm_use_cache,
                                combine_examples=combine_examples,
                                combined_only=combined_only,
                                reproduce=reproduce
                            )
                        if generate_declarations:
                            assert package_name == escape_package_name(package_name), "ts-declaration-file-generator does not support qualilfied package names"
                            # ts-declaration-file-generator also does not support ES6+, only ES5
                            _generate_declarations(
                                package_name=package_name,
                                output_path=output_path,
                                build_path=build_path,
                                execution_timeout=execution_timeout,
                                installation_timeout=installation_timeout,
                                verbose_setup=verbose_setup,
                                verbose_execution=verbose_execution,
                                verbose_files=verbose_files,
                                reproduce=reproduce
                            )
                        if generate_comparisons:
                            _generate_comparisons(
                                package_name=package_name,
                                output_path=output_path,
                                build_path=build_path,
                                execution_timeout=execution_timeout,
                                installation_timeout=installation_timeout,
                                verbose_setup=verbose_setup,
                                verbose_execution=verbose_execution,
                                verbose_files=verbose_files,
                                reproduce=reproduce
                            )
                            create_file(data_path / "is_usable")
                            printer(f"Generation succeeded for \"{package_name}\"")
                except CommonJSUnsupportedError:
                    create_file(data_path / "commonjs_unsupported", content=traceback.format_exc())
                    printer(f"Generation failed for \"{package_name}\"")
                    raise
                except NodeJSUnsupportedError:
                    create_file(data_path / "nodejs_unsupported", content=traceback.format_exc())
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
                        shutil.rmtree(output_path / "cache", ignore_errors=True)