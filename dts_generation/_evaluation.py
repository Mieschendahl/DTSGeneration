import json
from pathlib import Path
import random
import shutil
import sys
import traceback
from typing import Optional

from dts_generation._utils import ShellError, create_dir, create_file, escape_package_name, get_children, is_empty, printer, shell, unescape_package_name
from dts_generation._example import CommonJSUnsupportedError, NodeJSUnsupportedError, PackageDataMissingError, PackageInstallationError, ReproductionError
from dts_generation._comparison import build_definitely_typed
from dts_generation._generation import generate

VERSION_INSENSITIVE_PROGRAMS = ["git", "docker"]

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
    verbose_files: bool = True,
    verbose_exceptions: bool = True,
    verbose_statistics: bool = False,
    remove_cache: bool = True,
    evaluate_with_llm: bool = True,
    extract_from_readme: bool = True,
    generate_with_llm: bool = True,
    llm_model_name: str = "gpt-4o-mini",
    llm_temperature: int = 0,
    llm_verbose: bool = False,
    llm_interactive: bool = False,
    reproduce: bool = False
) -> None:
    with printer("Starting evaluation:"):
        with printer.with_verbose(verbose):
            # Checking required programs and their versions
            try:
                reproduction_data: dict = dict(
                    python = ".".join(map(str, sys.version_info[:3])),
                    node = shell("node --version").value.strip(),
                    npm = shell("npm --version").value.strip(),
                    git = shell("git --version").value.strip(),
                    docker = shell("docker --version").value.strip(),
                    llm_model_name = llm_model_name,
                    llm_temperature = llm_temperature,
                    random_seed = random_seed
                )
            except ShellError as e:
                raise ReproductionError("Missing required shell program for evaluation") from e
            if reproduce:
                saved_reproduction_data = json.loads((output_path / "reproduction.json").read_text())
                for key, old_value in saved_reproduction_data.items():
                    new_value = reproduction_data[key]
                    if old_value != new_value:
                        if key not in VERSION_INSENSITIVE_PROGRAMS:
                            raise ReproductionError(f"Current {key} version is {new_value} which does not match old {key} version {old_value}")
                        printer(f"Reproduction mode warning: Current {key} version is {new_value} which does not match old {key} version {old_value}")
            else:
                reproduction_data_json = json.dumps(reproduction_data, indent=2, ensure_ascii=False)
                create_file(output_path / "reproduction.json", content=reproduction_data_json)
                if verbose_setup:
                    with printer(f"Reproduction data:"):
                        printer(reproduction_data_json)
            # Gathering packages to evaluate
            dt_path = build_path / "DefinitelyTyped"
            build_definitely_typed(dt_path, installation_timeout, verbose_setup, reproduce)
            package_names = [path.name for path in get_children(dt_path / "types") if path.is_dir()]
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
        printer(f"Evaluating {len(package_names_subset)} of {len(package_names)} packages ({start}-{start+length})")
        for i, package_name in enumerate(package_names_subset):
            with printer(f"Evaluating package \"{package_name}\" (seed: {random_seed}) (index: {i+start}):"):
                package_path = output_path / "packages" / escape_package_name(package_name)
                if not is_empty(package_path):
                    printer(f"Skipping evaluation (already evaluated)")
                    continue
                create_dir(package_path, overwrite=True)
                data_path = package_path / "data"
                create_dir(data_path, overwrite=True)
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
                        remove_cache=remove_cache,
                        generate_examples=True,
                        generate_declarations=True,
                        generate_comparisons=True,
                        evaluate_with_llm=evaluate_with_llm,
                        extract_from_readme=extract_from_readme,
                        generate_with_llm=generate_with_llm,
                        llm_model_name=llm_model_name,
                        llm_temperature=llm_temperature,
                        llm_verbose=llm_verbose,
                        llm_interactive=llm_interactive,
                        llm_use_cache=False,
                        combine_examples=True,
                        combined_only=True,
                        reproduce=reproduce
                    )
                    create_file(data_path / "is_usable")
                except CommonJSUnsupportedError as e:
                    create_file(data_path / "commonjs_unsupported")
                    if verbose_exceptions:
                        with printer(f"Package does not support CommonJS module system:"):
                            printer(str(e))
                    continue
                except NodeJSUnsupportedError as e:
                    create_file(data_path / "nodejs_unsupported")
                    if verbose_exceptions:
                        with printer(f"Package does not support Node:"):
                            printer(str(e))
                    continue
                except PackageDataMissingError as e:
                    create_file(data_path / "package_data_missing")
                    if verbose_exceptions:
                        with printer(f"Missing package data for example generation:"):
                            printer(str(e))
                    continue
                except PackageInstallationError as e:
                    create_file(data_path / "package_installation_fail")
                    if verbose_exceptions:
                        with printer(f"Package could not be installed:"):
                            printer(str(e))
                    continue
                except Exception as e:
                    create_file(data_path / "raised_error")
                    if verbose_exceptions:
                        with printer(f"Encountered an unexpected exception:"):
                            printer(traceback.format_exc())
                            printer("Waiting for input, before continuing...")
                            input()
        sub_metrics: dict = dict(
            num_sound = 0,
            num_complete = 0,
            num_equivalent = 0,
            num_examples_generated = 0,
            num_declarations_generated = 0,
            num_comparisons_generated = 0
        )
        metrics: dict = dict(
            num_total = len(package_names_subset),
            num_usable = 0,
            num_not_commonjs = 0,
            num_not_nodejs = 0,
            num_package_data_missing = 0,
            package_installation_fail = 0,
            num_errors = 0,
            num_found_repository = 0, # _found_ metrics are counted only for the usable packages
            num_found_package_json = 0,
            num_found_readme = 0,
            num_found_main = 0,
            num_found_tests = 0,
            combined_extraction = sub_metrics.copy(),
            combined_generation = sub_metrics.copy(),
            combined_all = sub_metrics.copy()
        )
        for package_path in get_children(output_path / "packages"):
            data_path = package_path / "data"
            exists = lambda name: (data_path / name).is_file()
            metrics["num_usable"] += exists("is_usable")
            metrics["num_not_commonjs"] += exists("commonjs_unsupported")
            metrics["num_not_nodejs"] += exists("nodejs_unsupported")
            metrics["num_package_data_missing"] += exists("package_data_missing")
            metrics["package_installation_fail"] += exists("package_installation_fail")
            metrics["num_errors"] += exists("raised_error")
            metrics["num_found_repository"] += not exists("has_repository")
            metrics["num_found_package_json"] += exists("package.json")
            metrics["num_found_readme"] += exists("README.md")
            metrics["num_found_main"] += exists("index.js")
            metrics["num_found_tests"] += exists("has_tests")
            for mode in ["combined_extraction", "combined_generation", "combined_all"]:
                sub_metrics = metrics[mode]
                examples_sub_path = package_path / "examples" / mode
                sub_metrics["num_examples_generated"] += not is_empty(examples_sub_path)
                declarations_sub_path = package_path / "declarations" / mode
                sub_metrics["num_declarations_generated"] += not is_empty(declarations_sub_path)
                comparisons_sub_path = package_path / "comparisons" / mode
                sub_metrics["num_comparisons_generated"] += not is_empty(comparisons_sub_path)
                if not is_empty(comparisons_sub_path):
                    assert len(get_children(comparisons_sub_path)) == 1, "Expected only one comparison file (combined_only mode)"
                    for comparison_path in get_children(comparisons_sub_path):
                        comparison_json = json.loads(comparison_path.read_text())
                        sub_metrics["num_sound"] += comparison_json["isSound"]
                        sub_metrics["num_complete"] += comparison_json["isComplete"]
                        sub_metrics["num_equivalent"] += comparison_json["isEquivalent"]
        metrics_path = output_path / "metrics"
        create_dir(metrics_path, overwrite=True)
        metrics_json = json.dumps(metrics, indent=2, ensure_ascii=False)
        create_file(metrics_path / "absolute_metrics.json", content=metrics_json)
        with printer(f"Absolute metrics:"):
            printer(metrics_json)
        # Compared to num_usable
        relative_metrics: dict = dict(
            combined_extraction = sub_metrics.copy(),
            combined_generation = sub_metrics.copy(),
            combined_all = sub_metrics.copy()
        )
        for mode in ["combined_extraction", "combined_generation", "combined_all"]:
            for metric, old_value in metrics[mode].items():
                old_value = old_value / metrics["num_usable"] if metrics["num_usable"] > 0 else 1
                relative_metrics[mode][metric] = f"{old_value:.2%}" # type:ignore
        relative_metrics_json = json.dumps(relative_metrics, indent=2, ensure_ascii=False)
        create_file(metrics_path / "realtive_metrics.json", content=relative_metrics_json)
        if verbose_statistics:
            with printer(f"Relative metrics:"):
                printer(relative_metrics_json)
        # Compared to combined_extraction
        base_line_metrics: dict = dict(
            combined_generation = sub_metrics.copy(),
            combined_all = sub_metrics.copy()
        )
        for mode in ["combined_generation", "combined_all"]:
            for metric, old_value in metrics["combined_extraction"].items():
                old_value = (metrics[mode][metric] - old_value) / old_value if old_value > 0 else float("inf")
                base_line_metrics[mode][metric] = f"{old_value:.2%}" # type:ignore
        base_line_metrics_json = json.dumps(base_line_metrics, indent=2, ensure_ascii=False)
        create_file(metrics_path/ "base_line_metrics.json", content=base_line_metrics_json)
        if verbose_statistics:
            with printer(f"Base line metrics:"):
                printer(base_line_metrics_json)
        printer(f"Evaluation succeeded ({metrics["num_errors"]} errors)")