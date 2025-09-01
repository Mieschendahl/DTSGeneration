from pathlib import Path
from dts_generation._utils import create_dir, create_file, shell, escape_package_name

typescript_comparison_path = Path(__file__).parent.parent / "assets" / "typescript_comparison"

def compare_to_definitely_typed(package_name: str, package_path: Path, dt_path: Path) -> None:
    declarations_path = package_path / "declarations"
    if not declarations_path.is_dir():
        raise Exception(f"Declarations not found: {declarations_path}")

    template_path = package_path / "template"
    if not template_path.is_dir():
        raise Exception(f"Templates not found: {template_path}")

    comparisons_path = package_path / "comparisons"
    create_dir(comparisons_path)
    
    playground_path = package_path / "playground"
    create_dir(playground_path)
    
    if not dt_path.is_dir():
        raise Exception(f"DefinitelyTyped not found: {dt_path}")
    dt_package_name = escape_package_name(package_name)

    for declarations_sub_path in declarations_path.iterdir():
        playground_sub_path = playground_path / declarations_sub_path.name
        template_sub_path = template_path / declarations_sub_path.name
        comparisons_sub_path = comparisons_path / declarations_sub_path.name
        create_dir(comparisons_sub_path, overwrite=True)

        for declaration_path in declarations_sub_path.iterdir():
            create_dir(playground_sub_path, template_sub_path, overwrite=True)
            create_file(playground_sub_path / "tsconfig.json", typescript_comparison_path / "tsconfig.json")
            create_file(playground_sub_path / "comparison.ts", typescript_comparison_path / "comparison.ts")
            create_file(playground_sub_path / "generated.d.ts", declaration_path)
            create_file(playground_sub_path / "manual.d.ts", dt_path / f"types/{dt_package_name}/index.d.ts")

            print(f"\nComparing declaration {declaration_path.name} to DefinitelyTyped ground truth")
            if shell(f"npx tsx comparison.ts", cwd=playground_sub_path, check=False).code:
                print(f"Comparison script failed on {declaration_path.name}")
                continue

            comparison_path = playground_sub_path /  "comparison.json"
            if comparison_path.is_file():
                comparison_name = declaration_path.name.replace("declaration", "comparison").replace("d.ts", "json")
                create_file(comparisons_sub_path / comparison_name, comparison_path)
                print(f"Comparison successful for {declaration_path.name}. Stored result in {comparison_name}")
            else:
                print(f"Comparison script failed on {declaration_path.name}")