import re
import platform
from pathlib import Path
from dts_generation._utils import create_file, shell, create_dir

scripts_path = Path(__file__).parent.parent / "assets" / "ts_declaration_file_generation"

def generate_declarations(package_name: str, package_path: Path, execution_timeout: int) -> None:    
    examples_path = package_path / "examples"
    if not examples_path.is_dir():
        raise Exception(f"Examples not found: {examples_path}")
    
    template_path = package_path / "template"
    if not template_path.is_dir():
        raise Exception(f"Templates not found: {template_path}")
    
    playground_path = package_path / "playground"
    create_dir(playground_path)

    declarations_path = package_path / "declarations"
    create_dir(declarations_path)
    
    for examples_sub_path in examples_path.iterdir():
        playground_sub_path = playground_path / examples_sub_path.name
        template_sub_path = template_path / examples_sub_path.name
        declarations_sub_path = declarations_path / examples_sub_path.name
        create_dir(declarations_sub_path, overwrite=True)

        for example_path in examples_sub_path.iterdir():
            create_dir(playground_sub_path, template_sub_path, overwrite=True)
            example = example_path.read_text()
            example = re.sub(r'\bconst\b', 'var', example)
            example = re.sub(r'\blet\b', 'var', example)
            main_path = playground_sub_path / "index.js"
            create_file(main_path, content=example)

            print(f"\nExecuting example {example_path.name} via getRunTimeInformation")
            script_path = scripts_path / ("getRunTimeInformation.linux.sh" if platform.system() == "Linux" else "getRunTimeInformation.sh")
            run_time_path = Path("run_time_info_output") / "run_time_info.json"
            create_dir(playground_sub_path / run_time_path.parent, overwrite=True)           
            code = shell(f"{script_path} {main_path.name} {run_time_path} {execution_timeout}", cwd=playground_sub_path, check=False).code
            if code or not (playground_sub_path / run_time_path).is_file() or not (playground_sub_path / run_time_path).read_text():
                print(f"getRunTimeInformation failed {example_path.name}")
                continue

            print(f"Executing example {example_path.name} via generateDeclarationFile")
            script_path = scripts_path / "generateDeclarationFile.sh"
            tsd_path = Path("tsd_output")
            create_dir(playground_sub_path / tsd_path, overwrite=True)
            tsd_file_path = playground_sub_path / tsd_path / package_name / "index.d.ts"
            code = shell(f"{script_path} {run_time_path} {package_name} {tsd_path}", cwd=playground_sub_path, check=False).code
            if code or not tsd_file_path.is_file() or not tsd_file_path.read_text():
                print(f"generateDeclarationFile failed on {example_path.name}")
                continue

            declaration_name = example_path.name.replace("example", "declaration").replace(".js", ".d.ts")
            create_file(declarations_sub_path / declaration_name, tsd_file_path)
            print(f"Declaration generation successful for {example_path.name}. Stored result in {declaration_name}")