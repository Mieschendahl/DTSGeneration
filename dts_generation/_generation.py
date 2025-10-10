from pathlib import Path
import shutil

from dts_generation._utils import GenerationError, escape_package_name, printer
from dts_generation._example import generate_examples as _generate_examples
from dts_generation._declaration import generate_declarations as _generate_declarations
from dts_generation._comparison import combine_comparisons as _combine_comparisons, generate_comparisons as _generate_comparisons

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
    combine_comparisons: bool = True,
    evaluate_package: bool = True,
    extract_from_readme: bool = False,
    generate_with_llm: bool = True,
    llm_model_name: str = "gpt-4o-mini",
    llm_temperature: int = 0,
    llm_verbose: bool = False,
    llm_interactive: bool = False,
    llm_use_cache: bool = False
) -> None:
    with printer(f"Starting generation:"):
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
                        evaluate_package=evaluate_package,
                        extract_from_readme=extract_from_readme,
                        generate_with_llm=generate_with_llm,
                        llm_model_name=llm_model_name,
                        llm_temperature=llm_temperature,
                        llm_verbose=llm_verbose,
                        llm_interactive=llm_interactive,
                        llm_use_cache=llm_use_cache
                    )
                if generate_declarations:
                    assert build_path is not None, "Build path can not be None for declaration generation"
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
                    )
                if generate_comparisons:
                    assert build_path is not None, "Build path can not be None for comparison generation"
                    _generate_comparisons(
                        package_name=package_name,
                        output_path=output_path,
                        build_path=build_path,
                        execution_timeout=execution_timeout,
                        installation_timeout=installation_timeout,
                        verbose_setup=verbose_setup,
                        verbose_execution=verbose_execution,
                        verbose_files=verbose_files,
                    )
                if combine_comparisons:
                    comparisons_path = output_path / "comparisons"
                    extractions_path = comparisons_path / "extraction"
                    extraction_paths = []
                    if extractions_path.is_dir():
                        extraction_paths = [path for path in extractions_path.iterdir() if path.name.endswith(".json")]
                    if len(extraction_paths) > 1:
                        with printer("Combining multiple comparison results from readme extraction:"):
                            _combine_comparisons(extraction_paths, comparisons_path, comparisons_path / "combined_extraction.json", verbose_files)
                    generations_path = output_path / "comparisons" / "generation"
                    generation_paths = []
                    if generations_path.is_dir():
                        generation_paths = [path for path in generations_path.iterdir() if path.name.endswith(".json")]
                    if len(generation_paths) > 1:
                        with printer("Combining multiple comparison results from LLM generation:"):
                            _combine_comparisons(generation_paths, comparisons_path, comparisons_path / "combined_generation.json", verbose_files)
                    if len(extraction_paths) + len(generation_paths) > 1:
                        with printer("Combining multiple comparison results from extraction and LLM generation:"):
                            _combine_comparisons(extraction_paths + generation_paths, comparisons_path, comparisons_path / "combined_total.json", verbose_files)
            printer(f"Generation succeeded")
        except GenerationError:
            printer(f"Generation failed")
            raise
        finally:
            if remove_cache:
                shutil.rmtree(output_path / "cache", ignore_errors=True)