import json
from pathlib import Path
from typing import Optional

from dts_generation._utils import create_dir, create_file, shell, printer, escape_package_name
from dts_generation._example import build_template_project

SCRIPTS_PATH = Path(__file__).parent.parent / "assets" / "comparison"

def build_definitely_typed(output_path: Path, installation_timeout: int, verbose_setup: bool) -> None:
    with printer(f"Cloning the DefinitelyTyped repository:"):
        if output_path.is_dir() and any(output_path.iterdir()):
            printer(f"Success (already cloned)")
            return
        create_dir(output_path, overwrite=True)
        shell(
            f"git clone --depth 1 https://github.com/DefinitelyTyped/DefinitelyTyped.git {output_path}",
            timeout=installation_timeout,
            verbose=verbose_setup
        )
        printer(f"Success")

def generate_comparisons(
    package_name: str,
    output_path: Path,
    build_path: Path,
    execution_timeout: int,
    installation_timeout: int,
    verbose_setup: bool,
    verbose_execution: bool,
    verbose_files: bool
) -> None:
    with printer(f"Generating comparisons:"):
        build_definitely_typed(build_path / "DefinitelyTyped", installation_timeout, verbose_setup)
        # Setting up directory interface
        cache_path = output_path / "cache"
        declarations_path = output_path / "declarations"
        assert declarations_path.is_dir(), "Declaration directory missing"
        playground_path = cache_path / "playground"
        create_dir(playground_path, overwrite=True)
        comparisons_path = output_path / "comparisons"
        create_dir(comparisons_path, overwrite=False)
        template_path = cache_path / "template"
        build_template_project(package_name, template_path, installation_timeout, verbose_setup)
        dt_declaration_path = build_path / "DefinitelyTyped" / "types" / escape_package_name(package_name) / "index.d.ts"
        if verbose_files:
            with printer(f"DefinitelyTyped declaration content:"):
                printer(dt_declaration_path.read_text().strip())
        # Iterate over sub directories in the declaration directory (corresponding to the different example generation modes)
        for declarations_sub_path in declarations_path.iterdir():
            if not declarations_sub_path.is_dir():
                continue
            with printer(f"Generating comparisons for \"{declarations_sub_path.name}\" mode:"):
                iterdir = [path for path in declarations_sub_path.iterdir() if path.name.endswith(".d.ts")]
                printer(f"Found {len(iterdir)} declaration(s)")
                comparisons_sub_path = comparisons_path / declarations_sub_path.name
                create_dir(comparisons_sub_path, overwrite=True)
                for declaration_path in iterdir:
                    with printer(f"Generating comparison for {declaration_path.name}:"):
                        if verbose_files:
                            with printer(f"Declaration content:"):
                                printer(declaration_path.read_text())
                        create_dir(playground_path, template_path, overwrite=True)
                        create_file(playground_path / "index.d.ts", declaration_path)
                        create_file(playground_path / "compare.ts", SCRIPTS_PATH / "compare.ts")
                        create_file(playground_path / "tsconfig.json", SCRIPTS_PATH / "tsconfig.json")
                        create_file(playground_path / "predicted.d.ts", declaration_path)
                        create_file(playground_path / "expected.d.ts", dt_declaration_path)
                        with printer(f"Comparing generated declaration to DefinitelyTyped declaration:"):
                            shell_output = shell(
                                f"npx tsx compare.ts",
                                cwd=playground_path,
                                check=False,
                                timeout=execution_timeout,
                                verbose=verbose_execution
                            )
                            comparison_path = playground_path / "comparison.json"
                            if shell_output.code or not comparison_path.is_file() or not comparison_path.read_text():
                                printer(f"Fail")
                                continue
                            comparison = comparison_path.read_text()
                            if verbose_files:
                                with printer(f"Comparison content:"):
                                    printer(comparison)
                            create_file(comparisons_sub_path / declaration_path.name.replace(".d.ts", ".json"), content=comparison)
                            stats = json.loads(comparison)
                            printer(f"Soundness: {stats["soundness"]:.0%}")
                            printer(f"Completeness: {stats["completeness"]:.0%}")
                            printer(f"Equivalence: {stats["equivalence"]:.0%}")
                            printer(f"Success")

def combine_comparisons(paths: list[Path], relative_path: Optional[Path], output_path: Path, verbose_files: bool) -> None:
    with printer(f"Combining results:"):
        assert all(path.is_file() and path.name.endswith(".json") for path in paths), "Can only handle json files"
        # maps a predicted exported type to an expected exported sub type, if it exists (determines soundness)
        predicted_to_expected_sub: dict[str, Optional[str]] = {}
        # maps an expected exported type to a predicted exported sub type, if it exists (determines completeness)
        expected_to_predicted_sub: dict[str, Optional[str]] = {}
        for path in paths:
            stats = json.loads(path.read_text())
            if relative_path is not None:
                path = path.relative_to(relative_path)
            for key, value in stats["predicted_to_expected_sub"].items():
                key = f"{path}:{key}"
                predicted_to_expected_sub[key] = value
            for key, value in stats["expected_to_predicted_sub"].items():
                value = None if value is None else f"{path}:{value}"
                if key not in expected_to_predicted_sub:  
                    expected_to_predicted_sub[key] = value
                elif expected_to_predicted_sub[key] is None:
                    expected_to_predicted_sub[key] = value
        predicted_length = len(predicted_to_expected_sub.keys())
        num_sound = sum(1 for value in predicted_to_expected_sub.values() if value is not None)
        expected_length = len(expected_to_predicted_sub.keys())
        num_complete = sum(1 for value in expected_to_predicted_sub.values() if value is not None)
        isSound = num_sound == predicted_length
        soundness = num_sound / predicted_length if predicted_length > 0 else 1
        isComplete = num_complete == expected_length
        completeness = num_complete / expected_length if expected_length > 0 else 1
        isEquivalent = isSound and isComplete
        equivalence = soundness * completeness
        result = dict(
            isSound=isSound,
            soundness=soundness,
            isComplete=isComplete,
            completeness=completeness,
            isEquivalent=isEquivalent,
            equivalence=equivalence,
            predicted_to_expected_sub=predicted_to_expected_sub,
            expected_to_predicted_sub=expected_to_predicted_sub,
        )
        comparison = json.dumps(result, indent=2, ensure_ascii=False)
        if verbose_files:
            with printer(f"Comparison content:"):
                printer(comparison)
        create_file(output_path, content=comparison)
        printer(f"Soundness: {soundness:.0%}")
        printer(f"Completeness: {completeness:.0%}")
        printer(f"Equivalence: {equivalence:.0%}")
        printer(f"Success")