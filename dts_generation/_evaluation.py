import json
from pathlib import Path
import random
import sys
import traceback
from typing import Optional

from dts_generation._utils import *
from dts_generation._comparison import build_definitely_typed
from dts_generation._generation import generate

def evaluate(
    evaluation_path: Path,
    build_path: Path,
    start: int = 0,
    length: Optional[int] = None,
    random_seed: Optional[int] = 42,
    verbose: bool = True,
    verbose_setup: bool = False,
    verbose_execution: bool = False,
    verbose_files: bool = False,
    interactive_exceptions: bool = True,
    verbose_statistics: bool = False,
    remove_cache: bool = True,
    extract_from_readme: bool = True,
    generate_with_llm: bool = True,
    reproduce: bool = False,
    overwrite: bool = False,
    llm_model_name: str = "gpt-4o-mini",
    llm_temperature: int = 0,
    llm_verbose: bool = False,
    llm_interactive: bool = False
) -> None:
    logs_path = evaluation_path / "logs"
    create_dir(logs_path)
    with open(make_path_name_unique(logs_path / "shell.txt"), "w") as log_file:
        with printer.with_file(log_file):
            with printer("Starting evaluation:"):
                with printer.with_verbose(verbose):
                    try:
                        versions: dict = dict(
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
                    versions_path = evaluation_path / "reproduction" / "versions.json"
                    create_dir(versions_path.parent)
                    if reproduce:
                        if not versions_path.is_file():
                            raise ReproductionError(f"Missing old versions file for version comparison")
                        saved_versions = json.loads(versions_path.read_text())
                        for key, old_value in saved_versions.items():
                            new_value = versions[key]
                            if old_value != new_value:
                                if key not in ["git", "docker"]:
                                    raise ReproductionError(f"Current {key} version is {new_value} which does not match old {key} version {old_value}")
                                printer(f"Reproduction mode warning: Current {key} version is {new_value} which does not match old {key} version {old_value}")
                    else:
                        versions_json = json.dumps(versions, indent=2, ensure_ascii=False)
                        create_file(versions_path, content=versions_json)
                        if verbose_setup:
                            with printer(f"Version data:"):
                                printer(versions_json)
                    # Gathering packages to evaluate
                    build_definitely_typed(build_path, verbose_setup, reproduce)
                    package_names = [path.name for path in get_children(build_path / DEFINITELY_TYPED_PATH / "types") if not dir_empty(path)]
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
                    with printer(f"Evaluating package \"{package_name}\" (index: {i+start}):"):
                        generation_path = evaluation_path / PACKAGES_PATH / escape_package_name(package_name)
                        try:
                            generate(
                                package_name=package_name,
                                generation_path=generation_path,
                                build_path=build_path,
                                verbose=verbose,
                                verbose_setup=verbose_setup,
                                verbose_execution=verbose_execution,
                                verbose_files=verbose_files,
                                remove_cache=remove_cache,
                                generate_examples=True,
                                generate_declarations=True,
                                generate_comparisons=True,
                                extract_from_readme=extract_from_readme,
                                generate_with_llm=generate_with_llm,
                                llm_model_name=llm_model_name,
                                llm_temperature=llm_temperature,
                                llm_verbose=llm_verbose,
                                llm_interactive=llm_interactive,
                                llm_use_cache=False,
                                combine_examples=True,
                                combined_only=True,
                                reproduce=reproduce,
                                overwrite=overwrite
                            )
                        except (CommonJSUnsupportedError, PackageDataMissingError, PackageInstallationError):
                            pass
                        except Exception as e:
                            if interactive_exceptions:
                                with printer(f"Encountered an unexpected exception:"):
                                    printer(traceback.format_exc(), end="")
                                try:
                                    printer("Waiting for user input: ", end="")
                                    input()
                                except (KeyboardInterrupt, EOFError):
                                    printer(" User aborted")
                                    exit(0)
                with printer("Computing metrics:"):
                    sub_metrics: dict = dict(
                        sound = 0,
                        complete = 0,
                        equivalent = 0,
                        examples_generated = 0,
                        declarations_generated = 0,
                        comparisons_generated = 0
                    )
                    metrics: dict = dict(
                        total = len(package_names_subset),
                        usable = 0,
                        package_data_missing = 0,
                        package_installation_failed = 0,
                        commonjs_unsupported = 0,
                        unexpected_exception = 0,
                        llm_rejected = 0,
                        has_repository = 0,
                        has_package_json = 0,
                        has_readme = 0,
                        has_main = 0,
                        has_tests = 0,
                        combined_extraction = sub_metrics.copy(),
                        combined_generation = sub_metrics.copy(),
                        combined_all = sub_metrics.copy()
                    )
                    for package_name in package_names_subset:
                        generation_path = evaluation_path / PACKAGES_PATH / escape_package_name(package_name)
                        data_json_path = generation_path / DATA_JSON_PATH
                        metrics["usable"] += load_data(data_json_path, "usable")
                        metrics["package_data_missing"] += load_data(data_json_path, "package_data_missing")
                        metrics["package_installation_failed"] +=  load_data(data_json_path, "package_installation_failed")
                        metrics["commonjs_unsupported"] += load_data(data_json_path, "commonjs_unsupported")
                        metrics["unexpected_exception"] += load_data(data_json_path, "unexpected_exception")
                        metrics["llm_rejected"] += load_data(data_json_path, "llm_rejected")
                        metrics["has_repository"] += load_data(data_json_path, "has_repository")
                        metrics["has_package_json"] += load_data(data_json_path, "has_package_json")
                        metrics["has_readme"] += load_data(data_json_path, "has_readme")
                        metrics["has_main"] += load_data(data_json_path, "has_main")
                        metrics["has_tests"] += load_data(data_json_path, "has_tests")
                        for mode in COMBINED_MODE_PATHS:
                            sub_metrics = metrics[mode.name]
                            sub_metrics["examples_generated"] += not dir_empty(generation_path / EXAMPLES_PATH / mode)
                            sub_metrics["declarations_generated"] += not dir_empty(generation_path / DECLARATIONS_PATH / mode)
                            sub_metrics["comparisons_generated"] += not dir_empty(generation_path / COMPARISONS_PATH / mode)
                            children = get_children(generation_path / COMPARISONS_PATH / mode)
                            assert len(children) <= 1, "Expected not more than one comparison file for combined examples"
                            for comparison_path in children:
                                comparison_json = json.loads(comparison_path.read_text())
                                sub_metrics["sound"] += comparison_json["isSound"]
                                sub_metrics["complete"] += comparison_json["isComplete"]
                                sub_metrics["equivalent"] += comparison_json["isEquivalent"]
                    metrics_path = evaluation_path / "metrics"
                    create_dir(metrics_path)
                    metrics_json = json.dumps(metrics, indent=2, ensure_ascii=False)
                    create_file(metrics_path / "absolute_metrics.json", content=metrics_json)
                    if verbose_statistics:
                        with printer(f"Absolute metrics:"):
                            printer(metrics_json)
                    # # Compared to usable
                    # relative_metrics: dict = dict(
                    #     combined_extraction = sub_metrics.copy(),
                    #     combined_generation = sub_metrics.copy(),
                    #     combined_all = sub_metrics.copy()
                    # )
                    # for mode in COMBINED_MODE_PATHS:
                    #     for metric, old_value in metrics[mode.name].items():
                    #         old_value = old_value / metrics["usable"] if metrics["usable"] > 0 else 1
                    #         relative_metrics[mode.name][metric] = f"{old_value:.2%}" # type:ignore
                    # relative_metrics_json = json.dumps(relative_metrics, indent=2, ensure_ascii=False)
                    # create_file(metrics_path / "realtive_metrics.json", content=relative_metrics_json)
                    # if verbose_statistics:
                    #     with printer(f"Relative metrics:"):
                    #         printer(relative_metrics_json)
                    # Compared to combined_extraction
                    base_line_metrics: dict = dict(
                        combined_generation = sub_metrics.copy(),
                        combined_all = sub_metrics.copy()
                    )
                    for mode in COMBINED_MODE_PATHS[1:]:
                        for metric, old_value in metrics["combined_extraction"].items():
                            old_value = (metrics[mode.name][metric] - old_value) / old_value if old_value > 0 else float("inf")
                            base_line_metrics[mode.name][metric] = f"{old_value:.2%}" # type:ignore
                    base_line_metrics_json = json.dumps(base_line_metrics, indent=2, ensure_ascii=False)
                    create_file(metrics_path/ "base_line_metrics.json", content=base_line_metrics_json)
                    if verbose_statistics:
                        with printer(f"Base line metrics:"):
                            printer(base_line_metrics_json)