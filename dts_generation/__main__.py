from pathlib import Path

from dts_generation._generation import generate
from dts_generation._evaluation import evaluate

if True:
    evaluate(
        evaluation_path=Path("output/evaluation"),
        build_path=Path("output"),
        start=0,
        length=100,
        random_seed=50,
        verbose=True,
        verbose_setup=True,
        verbose_execution=False,
        verbose_files=False,
        interactive_exceptions=True,
        verbose_statistics=True,
        remove_cache=True,
        extract_from_readme=True,
        generate_with_llm=True,
        llm_model_name="gpt-4o-mini",
        llm_temperature=0,
        llm_verbose=True,
        llm_interactive=False,
        reproduce=False,
        overwrite=False
    )
else:
    package_name = "abs"
    generate(
        package_name=package_name,
        generation_path=Path(f"output/generation/{package_name}"),
        build_path=Path("output"),
        remove_cache=False,
        verbose=True,
        verbose_setup=True,
        verbose_execution=True,
        verbose_files=False,
        generate_examples=True,
        generate_declarations=True,
        generate_comparisons=True,
        extract_from_readme=True,
        generate_with_llm=True,
        llm_model_name="gpt-4o-mini",
        llm_temperature=0,
        llm_verbose=True,
        llm_interactive=False,
        reproduce=False,
        overwrite=True,
        combine_examples=True,
        combined_only=True
    )