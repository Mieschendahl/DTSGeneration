from pathlib import Path
import random
import shutil
from typing import Optional

from dts_generation._utils import GenerationError, create_dir, escape_package_name, printer, unescape_package_name
from dts_generation._example import EvaluationError
from dts_generation._comparison import build_definitely_typed
from dts_generation._generation import generate

def evaluate(
    output_path: Path,
    build_path: Path,
    start: int = 0,
    length: Optional[int] = None,
    random_seed: Optional[int] = 42,
    execution_timeout: int = 60,
    installation_timeout: int = 600,
    verbose: bool = True,
    verbose_setup: bool = False,
    verbose_execution: bool = False,
    verbose_files: bool = False,
    remove_cache: bool = True,
    evaluate_package: bool = True,
    extract_from_readme: bool = True,
    generate_with_llm: bool = True,
    llm_model_name: str = "gpt-4o-mini",
    llm_temperature: int = 0,
    llm_verbose: bool = False,
    llm_interactive: bool = False
) -> None:
    with printer("Starting evaluation:"):
        with printer.with_verbose(verbose):
            dt_path = build_path / "DefinitelyTyped"
            build_definitely_typed(dt_path, installation_timeout, verbose_setup)
            package_names = [path.name for path in (dt_path / "types").iterdir() if path.is_dir()]
            package_names.sort()
            # ts-declaration-file-generator currently does not qualified package names (e.g. @babel/core)
            printer(f"Removing packages with qualified names (not supported)")
            package_names = [package_name for package_name in package_names if package_name == unescape_package_name(package_name)]
            if random_seed:
                printer(f"Packages are shuffled with seed {random_seed}")
                random.seed(random_seed)
                random.shuffle(package_names)
            else:
                printer(f"Packages are sorted by name")
            start = 0 if start is None else start
            length = len(package_names) if length is None else length
            package_names_subset = package_names[start:start+length]
        printer(f"Evaluating {len(package_names_subset)} of {len(package_names)} packages starting from {start}")
        for i, package_name in enumerate(package_names_subset):
            with printer(f"Evaluating package \"{package_name}\" (seed: {random_seed}) (index: {i+start}):"):
                package_path = output_path / "packages" / escape_package_name(package_name)
                create_dir(package_path, overwrite=True)
                try:
                    try:
                        generate(
                            package_name=package_name,
                            output_path=package_path,
                            build_path=build_path,
                            execution_timeout=execution_timeout,
                            installation_timeout=installation_timeout,
                            verbose=verbose,
                            verbose_setup=verbose_setup,
                            verbose_execution=verbose_execution,
                            verbose_files=verbose_files,
                            remove_cache=False,
                            generate_examples=True,
                            generate_declarations=True,
                            generate_comparisons=True,
                            evaluate_package=evaluate_package,
                            extract_from_readme=extract_from_readme,
                            generate_with_llm=generate_with_llm,
                            llm_model_name=llm_model_name,
                            llm_temperature=llm_temperature,
                            llm_verbose=llm_verbose,
                            llm_interactive=llm_interactive,
                            llm_use_cache=False,
                        )
                    except EvaluationError as e:
                        with printer(f"Generation failed (unsupported package):"): # Unsupported in terms of Node 11
                            printer(str(e))
                        continue
                    except GenerationError as e:
                        with printer(f"Generation failed:"):
                            printer(str(e))
                        continue
                finally:
                    if remove_cache:
                        shutil.rmtree(output_path / "cache", ignore_errors=True)