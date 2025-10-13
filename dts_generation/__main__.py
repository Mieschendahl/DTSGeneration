from pathlib import Path

from dts_generation._generation import generate
from dts_generation._evaluation import evaluate

# TODO: issue with evaluate (maybe ignore that... and simply run it, maybe with an abortion mechanism for generation..., seems safer than to trust
# evaluate...?)

evaluate(
    output_path=Path("output/evaluation"),
    build_path=Path("output"),
    start=0,
    length=4,
    random_seed=100,
    execution_timeout=60,
    installation_timeout=600,
    verbose=True,
    verbose_setup=False,
    verbose_execution=False,
    verbose_files=False,
    verbose_exceptions=True,
    remove_cache=False, # set this to True later on
    evaluate_with_llm=True,
    extract_from_readme=True,
    generate_with_llm=True,
    llm_model_name="gpt-4o-mini",
    llm_temperature=0,
    llm_verbose=False,
    llm_interactive=False,
    reproduce=False
)

# TODO: check if llm prompts are all ok
# TODO: still need versioning/reproducability

# evaluate(
#     Path("output/evaluation"),
#     Path("output"),
#     start=0,
#     length=1,
#     random_seed=100,
#     remove_cache=False,
#     verbose=True,
#     verbose_setup=False,
#     verbose_execution=False,
#     verbose_files=True,
#     verbose_exceptions=True,
#     evaluate_package=True,
#     extract_from_readme=False,
#     generate_with_llm=True,
#     llm_interactive=True,
# )

# generate(
#     "abs",
#     Path("output/generation"),
#     Path("output"),
#     generate_examples=True,
#     generate_declarations=True,
#     generate_comparisons=True,
#     evaluate_package=True,
#     extract_from_readme=True,
#     generate_with_llm=True,
#     verbose=True,
#     verbose_setup=False,
#     verbose_execution=False,
#     verbose_files=False,
#     llm_interactive=False,
#     llm_use_cache=True,
#     combine_examples=True,
#     combined_only=True
# )