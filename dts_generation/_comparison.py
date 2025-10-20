import json
from pathlib import Path

from dts_generation._utils import *

def generate_comparisons(
    package_name: str,
    generation_path: Path,
    build_path: Path,
    verbose_setup: bool,
    verbose_execution: bool,
    verbose_files: bool,
    combined_only: bool
) -> None:
    with printer(f"Generating comparisons:"):
        declarations_path = generation_path / DECLARATIONS_PATH
        comparisons_path = generation_path / COMPARISONS_PATH
        template_path = generation_path / TEMPLATE_PATH
        playground_path = generation_path / PLAYGROUND_PATH
        build_definitely_typed(build_path, verbose_setup)
        build_template_project(package_name, generation_path, verbose_setup)
        dt_declaration_path = build_path / DEFINITELY_TYPED_PATH / "types" / escape_package_name(package_name) / "index.d.ts"
        if verbose_files:
            with printer(f"DefinitelyTyped declaration content:"):
                printer(dt_declaration_path.read_text().strip())
        for sub_path in (COMBINED_MODE_PATHS if combined_only else ALL_MODE_PATHS):
            declarations_sub_path = declarations_path / sub_path
            children = get_children(declarations_sub_path)
            printer(f"Found {len(children)} declarations(s) for {sub_path}")
            if len(children) == 0:
                continue
            comparisons_sub_path = comparisons_path / sub_path
            create_dir(comparisons_sub_path)
            for declaration_path in children:
                with printer(f"Generating comparisons for {declaration_path.name}:"):
                    if verbose_files:
                        with printer(f"Declaration content:"):
                            printer(declaration_path.read_text())
                    create_dir(playground_path, template_path, overwrite=True)
                    create_file(playground_path / "index.d.ts", declaration_path)
                    create_file(playground_path / "compare.ts", COMPARISON_SCRIPTS_PATH / "compare.ts")
                    create_file(playground_path / "tsconfig.json", COMPARISON_SCRIPTS_PATH / "tsconfig.json")
                    create_file(playground_path / "predicted.d.ts", declaration_path)
                    create_file(playground_path / "expected.d.ts", dt_declaration_path)
                    with printer(f"Comparing generated declaration to DefinitelyTyped declaration:"):
                        shell_output = shell(
                            f"npx tsx compare.ts",
                            cwd=playground_path,
                            check=False,
                            timeout=EXECUTION_TIMEOUT,
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
                        comparison_json = json.loads(comparison)
                        # Even though the values are fractions, they are not really meaningful, because they depend on the export type of the package.
                        # What really matters is if the fraction is 100% or not.
                        printer(f"Soundness: {comparison_json["soundness"]:.2%}")
                        printer(f"Completeness: {comparison_json["completeness"]:.2%}")
                        printer(f"Equivalence: {comparison_json["equivalence"]:.2%}")