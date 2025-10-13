from pathlib import Path

from dts_generation._generation import generate
from dts_generation._evaluation import evaluate

if True:
    evaluate(
        output_path=Path("output/evaluation"),
        build_path=Path("output"),
        start=0,
        length=100,
        random_seed=42,
        execution_timeout=60,
        installation_timeout=600,
        verbose=True,
        verbose_setup=True,
        verbose_execution=True,
        verbose_files=True,
        verbose_exceptions=True,
        verbose_statistics=True,
        remove_cache=True,
        evaluate_with_llm=True,
        extract_from_readme=True,
        generate_with_llm=True,
        llm_model_name="gpt-4o-mini",
        llm_temperature=0,
        llm_verbose=False,
        llm_interactive=False,
        reproduce=False
    )
else:
    package_name = "lodash.padend"
    generate(
        package_name=package_name,
        output_path=Path("output/generation"),
        build_path=Path("output"),
        execution_timeout=60,
        installation_timeout=600,
        verbose=True,
        verbose_setup=True,
        verbose_execution=True,
        verbose_files=True,
        remove_cache=False,
        evaluate_with_llm=True,
        extract_from_readme=True,
        generate_with_llm=True,
        llm_model_name="gpt-4o-mini",
        llm_temperature=0,
        llm_verbose=True,
        llm_interactive=False,
        reproduce=False
    )