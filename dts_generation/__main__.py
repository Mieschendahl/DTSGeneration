from pathlib import Path

from dts_generation._utils import printer
from dts_generation._generation import generate

# printer.set_padding("| ")
generate(
    "abs",
    Path("output/package"),
    Path("output"),
    generate_examples=True,
    generate_declarations=True,
    generate_comparisons=True,
    evaluate_package=True,
    extract_from_readme=True,
    generate_with_llm=True,
    verbose=True,
    verbose_setup=False,
    verbose_execution=True,
    verbose_files=False
)
