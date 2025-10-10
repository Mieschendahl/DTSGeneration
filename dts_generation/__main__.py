from pathlib import Path

from dts_generation._generation import generate
from dts_generation._evaluation import evaluate

# evaluate(
#     Path("output/evaluation"),
#     Path("output"),
#     start=0,
#     length=1,
#     remove_cache=False,
#     random_seed=84,
#     verbose=True,
#     verbose_setup=False,
#     verbose_execution=False,
#     verbose_files=True,
#     evaluate_package=True,
#     extract_from_readme=False,
#     generate_with_llm=True,
#     llm_interactive=True
# )

generate(
    "abs",
    Path("output/generation"),
    Path("output"),
    generate_examples=True,
    generate_declarations=True,
    generate_comparisons=True,
    evaluate_package=True,
    extract_from_readme=True,
    generate_with_llm=True,
    verbose=True,
    verbose_setup=False,
    verbose_execution=False,
    verbose_files=False,
    llm_interactive=False,
    llm_use_cache=True,
    combine_examples=True,
    combined_only=True
)

