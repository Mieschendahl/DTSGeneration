import json
from pathlib import Path
from typing import Optional

from dts_generation._utils import create_dir, create_file, get_children, shell, printer, escape_package_name, is_empty
from dts_generation._example import build_template_project

SCRIPTS_PATH = Path(__file__).parent.parent / "assets" / "comparison"

def build_definitely_typed(output_path: Path, installation_timeout: int, verbose_setup: bool, reproduce: bool) -> None:
    with printer(f"Cloning the DefinitelyTyped repository:"):
        if not is_empty(output_path):
            printer(f"Success (already cloned)")
            return
        create_dir(output_path, overwrite=True)
        shell(
            f"git clone --depth 1 https://github.com/DefinitelyTyped/DefinitelyTyped.git {output_path}",
            timeout=installation_timeout,
            verbose=verbose_setup
        )
        if reproduce:
            shell(
                f"git checkout 3b48ce35f1236733d9c1940eb95e6647b8a30852", # DefinitelyTyped version that the last big evaluation was performed on
                cwd=output_path,
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
    verbose_files: bool,
    reproduce: bool
) -> None:
    with printer(f"Generating comparisons:"):
        build_definitely_typed(build_path / "DefinitelyTyped", installation_timeout, verbose_setup, reproduce)
        # Setting up directory interface
        cache_path = output_path / "cache"
        create_dir(cache_path, overwrite=False)
        data_path = output_path / "data"
        create_dir(data_path, overwrite=False)
        declarations_path = output_path / "declarations"
        assert declarations_path.is_dir(), "Declaration directory missing"
        playground_path = cache_path / "playground"
        create_dir(playground_path, overwrite=True)
        comparisons_path = output_path / "comparisons"
        create_dir(comparisons_path, overwrite=True)
        template_path = cache_path / "template"
        build_template_project(package_name, data_path, template_path, installation_timeout, verbose_setup, reproduce)
        dt_declaration_path = build_path / "DefinitelyTyped" / "types" / escape_package_name(package_name) / "index.d.ts"
        if verbose_files:
            with printer(f"DefinitelyTyped declaration content:"):
                printer(dt_declaration_path.read_text().strip())
        # Iterate over sub directories in the declaration directory (corresponding to the different example generation modes)
        for declarations_sub_path in get_children(declarations_path):
            if is_empty(declarations_sub_path):
                continue
            with printer(f"Generating comparisons for \"{declarations_sub_path.name}\" mode:"):
                children = get_children(declarations_sub_path)
                printer(f"Found {len(children)} declaration(s)")
                comparisons_sub_path = comparisons_path / declarations_sub_path.name
                create_dir(comparisons_sub_path, overwrite=True)
                for declaration_path in children:
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
                            comparison_json = json.loads(comparison)
                            # Even though the values are fractions, they are not really meaningful, because they depend on the export type of the package.
                            # What really matters is if the fraction is 100% or not.
                            printer(f"Soundness: {comparison_json["soundness"]:.2%}")
                            printer(f"Completeness: {comparison_json["completeness"]:.2%}")
                            printer(f"Equivalence: {comparison_json["equivalence"]:.2%}")
                            printer(f"Success")