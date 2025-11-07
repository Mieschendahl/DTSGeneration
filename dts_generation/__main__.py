from pathlib import Path
import argparse

from dts_generation import generate, evaluate

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="dts_generation",
        description="Run DTS Generation or Evaluation pipeline."
    )
    parser.add_argument(
        "--mode",
        metavar="MODE",
        default="generation",
        help="Which mode to run: (default='generation', 'evaluation')."
    )
    parser.add_argument(
        "--package",
        type=str,
        default="abs",
        metavar="NAME",
        help="Package name for generation mode (default: 'abs')."
    )
    parser.add_argument(
        "--exclude-es5-check",
        action="store_true",
        help="Do not check if packages support es5 syntax."
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare declarations to the ground truth for generation mode."
    )
    parser.add_argument(
        "--exclude-llm",
        action="store_true",
        help="Do not use an LLM to generate use-case examples for a package."
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Start index for evaluation mode (default: 0)."
    )
    parser.add_argument(
        "--length",
        type=int,
        default=100,
        help="Number of evaluation samples (default: 100)."
    )
    args = parser.parse_args()
    match args.mode:
        case "evaluation":
            evaluate(
                evaluation_path=Path("output/evaluation"),
                build_path=Path("output/builds"),
                start=args.start,
                length=args.length,
                random_seed=50,
                verbose=True,
                verbose_setup=True,
                verbose_execution=False,
                verbose_files=False,
                verbose_exceptions=True,
                verbose_statistics=True,
                remove_cache=True,
                extract_from_readme=True,
                generate_with_llm=not args.exclude_llm,
                check_es5=args.exclude_es5_check,
                llm_model_name="gpt-4o-mini-2024-07-18",
                llm_temperature=0,
                llm_verbose=True,
                llm_interactive=False,
                overwrite=False
            )
        case "generation":
            generate(
                package_name=args.package,
                generation_path=Path(f"output/generation/{args.package}"),
                build_path=Path("output/builds"),
                remove_cache=False,
                verbose=True,
                verbose_setup=True,
                verbose_execution=False,
                verbose_files=False,
                generate_examples=True,
                generate_declarations=True,
                generate_comparisons=args.compare,
                extract_from_readme=True,
                generate_with_llm=not args.exclude_llm,
                check_es5=not args.exclude_es5_check,
                llm_model_name="gpt-4o-mini-2024-07-18",
                llm_temperature=0,
                llm_verbose=True,
                llm_interactive=False,
                overwrite=True,
                combine_examples=True,
                combined_only=True
            )
        case _:
            print(f"Unknown mode given {args.mode!r}")
            exit(1)