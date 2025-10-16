
from functools import partial
from pathlib import Path
import re
from typing import Optional

from easy_prompting.prebuilt import GPT, LogList, LogFile, LogFunc, LogReadable, Prompter, IList, IData, ICode, IChoice, IItem, delimit_code, list_text, create_interceptor, pad_text
from dts_generation._utils import *

MAX_LENGTH_FILE_PRINTS = 3
MAX_LENGTH_FILE_PROMPTS = 10000
MAX_NUM_TEST_FILES = 3
MAX_NUM_GENERATION_ATTEMPTS = 3

def generate_examples(
    package_name: str,
    generation_path: Path,
    verbose_setup: bool,
    verbose_execution: bool,
    verbose_files: bool,
    extract_from_readme: bool,
    generate_with_llm: bool,
    combine_examples: bool,
    reproduce: bool,
    llm_model_name: str,
    llm_temperature: int,
    llm_verbose: bool,
    llm_interactive: bool,
    llm_use_cache: bool, # Makes llm_temperature > 0 obsolete
) -> None:
    llm_verbose = llm_verbose or llm_interactive
    with printer(f"Generating examples:"):
        data_path = generation_path / DATA_PATH
        data_json_path = generation_path / DATA_JSON_PATH
        logs_path = generation_path / LOGS_PATH
        examples_path = generation_path / EXAMPLES_PATH
        template_path = generation_path / TEMPLATE_PATH
        playground_path = generation_path / PLAYGROUND_PATH
        clone_repository(package_name, generation_path, verbose_setup)
        package_json = get_package_json(generation_path, verbose_setup)
        readme = get_readme(generation_path, verbose_setup)
        main = get_main(generation_path, verbose_setup)
        tests = get_tests(generation_path, verbose_setup)
        save_data(data_json_path, "has_repository", not dir_empty(generation_path / REPOSITORY_PATH))
        save_data(data_json_path, "has_package_json", file_exists(generation_path / PACKAGE_JSON_PATH))
        save_data(data_json_path, "has_readme", file_exists(generation_path / README_PATH))
        save_data(data_json_path, "has_main", file_exists(generation_path / MAIN_PATH))      
        save_data(data_json_path, "has_tests", not dir_empty(generation_path / TESTS_PATH))
        save_data(data_json_path, "llm_rejected", False)
        if not readme and not package_json and not main and not tests:
            raise PackageDataMissingError("Not enough package information found")
        build_template_project(package_name, generation_path, verbose_setup, reproduce)

        # Reusable helper function for example testing
        def run_example(example: Optional[str], example_path: Path) -> dict:
            if example is None:
                return dict(no_example=True)
            with printer(f"Testing example {example_path.name}"):
                if verbose_files:
                    with printer(f"Example content:"):
                        printer(example)
                with printer(f"Checking import statements:"):
                    require_pattern = r'\brequire\s*\(\s*["\'`]' + package_name + r'["\'`]\s*\)'
                    if not re.search(require_pattern, example):
                        printer(f"Fail")
                        return dict(no_require=True)
                    printer(f"Success")
                create_dir(playground_path, template_path, overwrite=True)
                create_file(playground_path / "index.js", content=example)
                with printer(f"Running example with Node:"):
                    shell_output = shell(f"node index.js", cwd=playground_path, check=False, timeout=EXECUTION_TIMEOUT, verbose=verbose_execution)
                    if shell_output.code:
                        printer(f"Fail")
                    else:
                        printer(f"Success")
                        create_file(example_path, content=example)
                    return dict(shell_code=shell_output.code, shell_output=shell_output.value, shell_timeout=shell_output.timeout)

        # Reusable helper function for combining examples
        def combine_files_helper(file_paths: list[Path],) -> Optional[str]:
            with printer(f"Combining examples:"):
                if len(file_paths) == 0:
                    printer(f"No examples found")
                    return None
                combined_parts = []
                for file_path in file_paths:
                    content = file_path.read_text()
                    wrapped = (
                        f"// File: {file_path.relative_to(generation_path)}\n\n"
                        f"(function() {"{\n" + pad_text(content, "  ") + "\n}"})();"
                    )
                    combined_parts.append(wrapped)
                printer(f"Success")
                return "\n\n".join(combined_parts)

        # Checking if package is usable
        with printer(f"Checking CommonJS support:"):
            output = run_example(f"const package = require(\"{package_name}\");", playground_path / "test.js")
            if output.get("shell_code", 0):
                raise CommonJSUnsupportedError(f"Require statement fails on package with error:\n{pad_text(output["shell_output"])}")

        def extract_from_readme_helper() -> None:
            with printer(f"Extracting examples from the readme file:"):
                if not readme:
                    printer(f"No readme file available for extraction")
                    return None
                examples_sub_path = examples_path / EXTRACTION_PATH
                create_dir(examples_sub_path)
                examples = re.findall( r"```.*?\n(.*?)```", readme, flags=re.DOTALL)
                examples = [example.strip() for example in examples]
                with printer(f"Found {len(examples)} example(s):"):
                    for example_index, example in enumerate(examples):
                        run_example(example, examples_sub_path / f"{example_index}.js")
            if combine_examples:
                with printer("Combining extracted examples:"):
                    combined_examples_sub_path = examples_path / COMBINED_EXTRACTION_PATH
                    create_dir(combined_examples_sub_path)
                    combined_example = combine_files_helper(get_children(examples_sub_path))
                    run_example(combined_example, combined_examples_sub_path / "0.js")

        def generate_with_llm_helper() -> None:
            with printer(f"Generating examples with LLM:"):
                examples_sub_path = examples_path / GENERATION_PATH
                create_dir(examples_sub_path)
                readable_logger = LogReadable(LogFunc(partial(printer, end="\n\n")))
                readable_logger.set_verbose(llm_verbose)
                file_logger = LogFile(logs_path / f"{GENERATION_PATH.name}.txt")
                with LogList(readable_logger, file_logger) as logger:
                    model = GPT(llm_model_name, llm_temperature)
                    agent = Prompter(model)
                    agent.set_logger(logger)
                    if llm_interactive:
                        agent.set_interceptor(create_interceptor(partial(printer, end="")))
                    if llm_use_cache:
                        agent.set_cache_path(PROMPTER_PATH / llm_model_name)
                    agent.set_tag(GENERATION_PATH.name)
                    agent.add_message(
                        list_text(
                            f"You are an autonomous agent and Node expert.",
                            f"The user is a program that can only interact with you in predetermined ways.",
                            f"The user will give you a task and instructions on how to complete the task.",
                            f"You should try to achieve the task by following the instructions of the user."
                        ),
                        role="developer"
                    )
                    agent.add_message(
                        list_text(
                            f"I want to know how to use the npm package \"{package_name}\".",
                            f"Your task is to create an example that correctly imports and uses the package to its full extent.",
                            f"Make sure that the example covers as much functionality of the package as possible.",
                            f"Make sure that the example uses CommonJS style imports and exports and includes require('{package_name}').",
                            f"Make sure that the example does not import any other npm packages that would first need to be installed.",
                            f"Make sure that the example does not run indefinitly, e.g. in case a server gets started.",
                            f"Make sure that the example does not require user input.",
                        )
                    )
                    # Crop long messages for print readability
                    readable_logger.set_crop(MAX_LENGTH_FILE_PRINTS)
                    if readme:
                        agent.add_message(
                            f"Here is the readme file of the package's GitHub repository:"
                            f"\n{delimit_code(readme[:MAX_LENGTH_FILE_PROMPTS], "markdown")}"
                        )
                    if package_json:
                        agent.add_message(
                            f"Here is the package.json file of the package's GitHub repository:"
                            f"\n{delimit_code(package_json[:MAX_LENGTH_FILE_PROMPTS], "json")}"
                        )
                    if main:
                        agent.add_message(
                            f"Here is the main file of the package's GitHub repository:"
                            f"\n{delimit_code(main[:MAX_LENGTH_FILE_PROMPTS], "javascript")}"
                        )
                    if tests:
                        agent.add_message(
                            f"Here are some test files of the package's GitHub repository:"
                            f"\n{
                                "\n".join(f"{path}:\n{delimit_code(content[:MAX_LENGTH_FILE_PROMPTS], "javascript")}"
                                for path, content in tests[:MAX_NUM_TEST_FILES])
                            }"
                        )
                    readable_logger.set_crop()
                    # Reprompt LLM for an example until the example is valid
                    example_index = 0
                    while True:
                        with printer(f"Generating example {example_index}:"):
                            if example_index >= MAX_NUM_GENERATION_ATTEMPTS:
                                printer(f"Failed (too many attempts)")
                                return None
                            (choice, data) = agent.get_data(
                                    IList(
                                        "Do the following",
                                        IItem(
                                            "think",
                                            IData(f"Think about how to complete the current task.")
                                        ),
                                        IItem(
                                            "choose",
                                            IChoice(
                                                f"Choose one of the following options",
                                                IList(
                                                    f"If the package is not ment to be used as a stand alone package in Node e.g."
                                                    f" because it is browser-exclusive, framework-dependent, or requires additional packages to be installed.",
                                                    IItem(
                                                        "unusable",
                                                        IData(f"Explain why this is the case")
                                                    )
                                                ),
                                                IList(
                                                    f"Otherwise",
                                                    IItem(
                                                        "example",
                                                        ICode(f"Provide the content of an example.", "javascript")
                                                    )
                                                )
                                            )
                                        )
                                    )
                                )[1]
                            if choice == "unsusable":
                                save_data(data_json_path, "llm_rejected", True, raise_missing=True)
                                explanation = data[0]
                                create_file(logs_path / f"llm_rejected.txt", content=explanation)
                                printer(f"Fail (package is unusable)")
                                return None
                            example = data[0]
                            printer(f"Success")
                        with printer(f"Checking example {example_index}:"):
                            output = run_example(example, examples_sub_path / f"{example_index}.js")
                            example_index += 1
                            if output.get("require_missing", False):
                                agent.add_message(
                                    f"Your example does not include an import statement such as require('{package_name}')."
                                    f"\nPlease do not use any other name than exactly \"{package_name}\" in the require statement, else we can not proceed."
                                )
                                continue
                            if output.get("shell_code", 0):
                                if output.get("shell_timeout", False):
                                    agent.add_message(
                                        f"Running your example with Node did not finish after {EXECUTION_TIMEOUT} seconds:"
                                        f"\n{delimit_code(output["shell_output"], "shell")}"
                                    )
                                    continue
                                agent.add_message(
                                    f"Running your example with Node failed with code {output["shell_code"]}:"
                                    f"\n{delimit_code(output["shell_output"], "shell")}"
                                )
                                continue
                            break
            if combine_examples:
                with printer("Combining generated examples:"):
                    combined_examples_sub_path = examples_path / COMBINED_GENERATION_PATH
                    create_dir(combined_examples_sub_path)
                    combined_example = combine_files_helper(get_children(examples_sub_path))
                    run_example(combined_example, combined_examples_sub_path / "0.js")

        if extract_from_readme:
            extract_from_readme_helper()
        if generate_with_llm:
            generate_with_llm_helper()
        if combine_examples:
            with printer("Combining all examples:"):
                combined_examples_sub_path = examples_path / COMBINED_ALL_PATH
                create_dir(combined_examples_sub_path)
                paths = get_children(examples_path / EXTRACTION_PATH) + get_children(examples_path / GENERATION_PATH)
                combined_example = combine_files_helper(paths)
                run_example(combined_example, combined_examples_sub_path / "0.js")