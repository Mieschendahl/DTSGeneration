import argparse
import shutil
from pathlib import Path
import sys
import traceback
from typing import Optional
from dts_generation._utils import create_dir, create_file, escape_package_name, shell, unescape_package_name
from dts_generation._utils import build_dts, build_definitely_typed
from dts_generation._generate_js import generate_examples
from dts_generation._generate_dts import generate_declarations
from dts_generation._compare_dts import compare_to_definitely_typed
import openai

def run_from_commandline(
    output_path: str, model_name: str, temperature: int, interactive_llm: Optional[str], execution_timeout: int, dt_path: str, reproduce: bool, versions_path: Path,
    dts_path: str, package_name: Optional[str], dt_start: int, dt_end: int, remove_cache: str, no_readme_extraction: bool, simple_llm_generation: bool,
    advanced_llm_generation: bool, no_example_generation: bool, no_declaration_generation: bool, no_comparison_generation: bool, no_llm_cache: bool, build: bool
) -> None:
    if build:
        build_definitely_typed(Path(dt_path))
        build_dts(Path(dts_path))
        print("Finished building")
        exit(0)
    if not Path(dt_path).is_dir():
        print("DefinitelyTyped repository was not found. Maybe you forgot to run --build first.")

    print("Checking required shell programs")
    versions = []
    versions.append(f"python: {sys.version}")
    versions.append(f"openai: {openai.__version__}")
    versions.append(f"openai model: {model_name}")
    versions.append(f"openai model temperature: {temperature}")
    versions.append(f"node: " + shell("node --version").value.strip())
    versions.append(f"npm: " + shell("npm --version").value.strip())
    versions.append(f"git: " + shell("git --version").value.strip())
    versions.append(f"docker: " + shell("docker --version").value.strip())
    create_file(Path(versions_path), content="\n".join(versions))

    if package_name:
        print(f"\nRunning for a specific packge")
        package_names = [package_name]
        dt_start = 0
        dt_end = 1
    else:
        types_path = Path(dt_path) / "types"
        package_names = [path.name for path in types_path.iterdir() if path.is_dir()]
        package_names = [unescape_package_name(name) for name in package_names]
        dt_end = len(package_names) if dt_end is None else dt_end
        print(f"\nRunning for all {len(package_names)} DefinitelyTyped packages, starting at index {dt_start}, ending before index {dt_end}")
    package_names = sorted(package_names)    

    for index, package_name in enumerate(package_names[dt_start:dt_end]):
        index += dt_start
        print(f"\nRunning for {package_name} ({index})")
        escaped_package_name = escape_package_name(package_name)
        if package_name != escaped_package_name:
            print(f"TSD does not support qualified packages: {package_name}. Skipping package")
            continue
        package_path = Path(output_path) / escaped_package_name
        create_dir(package_path)
            
        try:
            if not no_example_generation:
                print(f"\nGenerating examples:")    
                generate_examples(
                    model_name=model_name,
                    temperature=temperature,
                    interactive_llm=interactive_llm,
                    package_name=package_name,
                    package_path=package_path,
                    execution_timeout=execution_timeout,
                    no_readme_extraction=no_readme_extraction,
                    simple_llm_generation=simple_llm_generation,
                    advanced_llm_generation=advanced_llm_generation,
                    reproduce=reproduce,
                    no_llm_cache=no_llm_cache
                )

            if not no_declaration_generation:
                print(f"\nGenerating declarations:")
                generate_declarations(package_name, package_path, execution_timeout)
            
            if not no_comparison_generation:
                print(f"\nComparing declarations:")
                compare_to_definitely_typed(package_name, package_path, Path(dt_path))
                
            print(f"\nFinished with {package_name}")

        except Exception as e:
            print(f"Failed on {package_name}")
            # print(f"Error: {e}")
            traceback.print_exception(type(e), e, e.__traceback__)
            
        finally:
            if remove_cache:
                shutil.rmtree(package_path / "template", ignore_errors=True)
                shutil.rmtree(package_path / "playground", ignore_errors=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate examples and d.ts files for an npm package and compare them to DefinitlyTyped d.ts files."
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Clones DefinitelyTyped and build dts-generate."
    )
    parser.add_argument(
        "--dt-path",
        metavar="PATH",
        default="./output/DefinitelyTyped",
        help="Path to DefinitelyTyped(default: ./output/DefinitelyTyped)"
    )
    parser.add_argument(
        "--dts-path",
        metavar="PATH",
        default="./output/dts-generate",
        help="Path to dts-generate (default: ./output/dts-generate)"
    )
    parser.add_argument(
        "--output-path",
        metavar="PATH",
        default="./output/packages",
        help="Where to put the generated files (default: ./output/packages)"
    )
    parser.add_argument(
        "--versions-path",
        metavar="PATH",
        default="./output/versions.txt",
        help="Where to save the generated versions file for reproducability (default: ./output/versions.txt)"
    )
    parser.add_argument(
        "--remove-cache",
        action="store_true",
        help="Remove temporary files to save memory"
    )
    parser.add_argument(
        "--reproduce",
        action="store_true",
        help="Try to use package.json / package-lock.json from old runs to make example execution more reproducable."
    )
    
    parser.add_argument(
        "--package-name",
        metavar="NAME",
        default=None,
        help="Run dts_generation for a specific package. If not specified then all packges in DefinitelyTyped are used"
    )
    parser.add_argument(
        "--dt-start",
        metavar="INDEX",
        type=int,
        default=0,
        help="Inclusive start index for iterating over the DefinitelyTyped packages (default: 0)"
    )
    parser.add_argument(
        "--dt-end",
        metavar="INDEX",
        type=int,
        default=None,
        help="Exclusive end index for iterating over the DefinitelyTyped packages (default: inf)"
    )
    parser.add_argument(
        "--execution-timeout",
        metavar="SECONDS",
        type=int,
        default=120,
        help="Timeout for testing the generated examples (default: 120)"
    )
    parser.add_argument(
        "--no-example-generation",
        action="store_true",
        help="Skip generating examples"
    )
    parser.add_argument(
        "--no-declaration-generation",
        action="store_true",
        help="Skip generating declarations"
    )
    parser.add_argument(
        "--no-comparison-generation",
        action="store_true",
        help="Skip generating comparisons"
    )
    parser.add_argument(
        "--no-readme-extraction",
        action="store_true",
        help="Do not extract examples from the README file of an npm package"
    )
    parser.add_argument(
        "--simple-llm-generation",
        action="store_true",
        help="Generate examples from README/main/test files of an npm package using an LLM"
    )
    parser.add_argument(
        "--advanced-llm-generation",
        action="store_true",
        help="Same as --simple-llm-generation but using a more sophisticated approach"
    )
    parser.add_argument(
        "--model-name",
        default="gpt-4o-mini-2024-07-18",
        metavar="NAME",
        help=("OpenAI model to use (i.g. gpt-4o, gpt-4o-mini, gpt-4, gpt-4-turbo, gpt-3.5-turbo) (default: gpt-4o-mini-2024-07-18).")
    )
    parser.add_argument(
        "--temperature",
        type=int,
        default=0,
        metavar="VALUE",
        help=(
            "The temperature that the model should use for completion generation (default: 0)"
        )
    )
    parser.add_argument(
        "--interactive-llm",
        action="store_true",
        help="Make llm prompting interactive"
    )
    parser.add_argument(
        "--no-llm-cache",
        action="store_true",
        help="Do not use LLM response caching"
    )
    args = parser.parse_args()
    
    run_from_commandline(
        output_path=args.output_path,
        model_name=args.model_name,
        temperature=args.temperature,
        no_readme_extraction=args.no_readme_extraction,
        simple_llm_generation=args.simple_llm_generation,
        advanced_llm_generation=args.advanced_llm_generation,
        execution_timeout=args.execution_timeout,
        dt_path=args.dt_path,
        dts_path=args.dts_path,
        package_name=args.package_name,
        dt_start=args.dt_start,
        dt_end=args.dt_end,
        remove_cache=args.remove_cache,
        interactive_llm="user" if args.interactive_llm else None,
        reproduce=args.reproduce,
        no_example_generation=args.no_example_generation,
        no_declaration_generation=args.no_declaration_generation,
        no_comparison_generation=args.no_comparison_generation,
        versions_path=args.versions_path,
        no_llm_cache=args.no_llm_cache,
        build=args.build
    )