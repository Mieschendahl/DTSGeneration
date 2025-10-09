import json
from pathlib import Path

from dts_generation._utils import create_dir, create_file, shell, printer, escape_package_name
from dts_generation._example import GENERATION_MODES, build_template_project

SCRIPTS_PATH = Path(__file__).parent.parent / "assets" / "comparison"

def build_definitely_typed(output_path: Path, installation_timeout: int, verbose: bool) -> None:
    with printer(f"Cloning the DefinitelyTyped repository:"):
        if output_path.is_dir() and any(output_path.iterdir()):
            printer(f"Success (already cloned)")
            return
        create_dir(output_path, overwrite=True)
        shell(
            f"git clone --depth 1 https://github.com/DefinitelyTyped/DefinitelyTyped.git {output_path}",
            timeout=installation_timeout,
            verbose=verbose
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
        for mode in GENERATION_MODES:
            declarations_sub_path = declarations_path / mode
            if not declarations_sub_path.is_dir():
                continue
            with printer(f"Generating comparisons for \"{declarations_sub_path.name}\" mode:"):
                printer(f"Found {len(list(declarations_sub_path.iterdir()))} declaration(s)")
                comparisons_sub_path = comparisons_path / declarations_sub_path.name
                create_dir(comparisons_sub_path, overwrite=True)
                for declaration_path in declarations_sub_path.iterdir():
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
                            printer(f"Success")
                        stats = json.loads(comparison)
                        with printer(f"Reading comparison results:"):
                                printer(f"Soundness: {stats["soundness"]:.0%}")
                                printer(f"Completeness: {stats["completeness"]:.0%}")
                                printer(f"Equivalence: {stats["equivalence"]:.0%}")
                        # Saving generated comparison file
                        create_file(comparisons_sub_path / declaration_path.name.replace("d.ts", "json"), content=comparison)