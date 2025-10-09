from pathlib import Path

from dts_generation._generation import generate
from dts_generation._evaluation import evaluate

evaluate(
    Path("output/evaluation"),
    Path("output"),
    start=0,
    length=1,
    remove_cache=False,
    random_seed=84,
    verbose=True,
    verbose_setup=False,
    verbose_execution=False,
    verbose_files=True,
    evaluate_package=True,
    extract_from_readme=False,
    generate_with_llm=True,
    llm_interactive=True
)

# generate(
#     "abs",
#     Path("output/package"),
#     Path("output"),
#     generate_examples=True,
#     generate_declarations=False,
#     generate_comparisons=False,
#     evaluate_package=False,
#     extract_from_readme=False,
#     generate_with_llm=True,
#     verbose=True,
#     verbose_setup=False,
#     verbose_execution=False,
#     verbose_files=False,
#     llm_interactive=True
# )

