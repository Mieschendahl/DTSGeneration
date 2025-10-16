from pathlib import Path

from dts_generation._generation import generate
from dts_generation._evaluation import evaluate

if False:
    evaluate(
        output_path=Path("output/evaluation"),
        build_path=Path("output"),
        start=0,
        length=100,
        random_seed=43,
        execution_timeout=60,
        installation_timeout=600,
        verbose=True,
        verbose_setup=True,
        verbose_execution=True,
        verbose_files=True,
        verbose_exceptions=True,
        verbose_statistics=True,
        remove_cache=True,
        evaluate_with_llm=False,
        extract_from_readme=True,
        generate_with_llm=True,
        llm_model_name="gpt-4o-mini",
        llm_temperature=0,
        llm_verbose=False,
        llm_interactive=False,
        reproduce=False,
        wait_after_error=True,
        overwrite=False
    )
else:
    package_name = "breeze"
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
        generate_with_llm=False,
        llm_model_name="gpt-4o-mini",
        llm_temperature=0,
        llm_verbose=True,
        llm_interactive=False,
        reproduce=False,
        overwrite=True,
        combine_examples=True,
        combined_only=True
    )