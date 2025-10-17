
from functools import partial
from pathlib import Path
import re
from typing import Optional

from easy_prompting.prebuilt import GPT, LogList, LogFile, LogFunc, LogReadable, Prompter, IList, IData, ICode, IChoice, IItem, delimit_code, list_text, create_interceptor, pad_text
from dts_generation._utils import *

MAX_LENGTH_FILE_PRINTS = 1
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
        data_json_path = generation_path / DATA_JSON_PATH
        save_data(data_json_path, "has_repository", False)
        save_data(data_json_path, "has_package_json", False)
        save_data(data_json_path, "has_readme", False)
        save_data(data_json_path, "has_main", False)      
        save_data(data_json_path, "has_tests", False)
        save_data(data_json_path, "llm_rejected", False)
        logs_path = generation_path / LOGS_PATH
        examples_path = generation_path / EXAMPLES_PATH
        template_path = generation_path / TEMPLATE_PATH
        playground_path = generation_path / PLAYGROUND_PATH
        clone_repository(package_name, generation_path, verbose_setup)
        package_json = get_package_json(generation_path, verbose_setup)
        readme = get_readme(generation_path, verbose_setup)
        main = get_main(generation_path, verbose_setup)
        tests = get_tests(generation_path, verbose_setup)
        save_data(data_json_path, "has_repository", not dir_empty(generation_path / REPOSITORY_PATH), raise_missing=True)
        save_data(data_json_path, "has_package_json", file_exists(generation_path / PACKAGE_JSON_PATH), raise_missing=True)
        save_data(data_json_path, "has_readme", file_exists(generation_path / README_PATH), raise_missing=True)
        save_data(data_json_path, "has_main", file_exists(generation_path / MAIN_PATH), raise_missing=True)
        save_data(data_json_path, "has_tests", not dir_empty(generation_path / TESTS_PATH), raise_missing=True)
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
                printer(f"Found {len(examples)} example(s)")
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
                model = GPT(llm_model_name, llm_temperature)
                agent = Prompter(model)
                if llm_interactive:
                    agent.set_interceptor(create_interceptor(partial(printer, end="")))
                if llm_use_cache:
                    agent.set_cache_path(CACHE_PATH / "prompter" / llm_model_name)
                readable_logger = LogReadable(LogFunc(partial(printer, end="\n\n")))
                readable_logger.set_verbose(llm_verbose)
                # Evaluate usability of package
                with LogList(readable_logger, LogFile(logs_path / f"evaluation.txt")) as logger:
                    evaluation_agent = agent.get_copy()
                    evaluation_agent.set_logger(logger)
                    evaluation_agent.set_tag("evaluation")
                    evaluation_agent.add_message(
                        list_text(
                            f"You are an autonomous agent and JavaScript/Node/NPM expert",
                            f"The user is a program that can only interact with you in predetermined ways",
                            f"The user will give you a task and instructions on how to complete the task",
                            f"You should try to achieve the task by following the instructions of the user"
                        ),
                        role="developer"
                    )
                    evaluation_agent.add_message(
                        f"Check if the npm package \"{package_name}\" satisfied at least one of the following conditions" + list_text(
                            f"It can only be used in the browser",
                            f"It can only be used with a framework",
                            f"It can not directly be used in Node",
                            f"Running \"npm install {package_name}\" is not enough to properly use",
                            add_scope=True
                        )
                    )
                    # Crop long messages for print readability
                    readable_logger.set_crop(MAX_LENGTH_FILE_PRINTS)
                    if readme:
                        evaluation_agent.add_message(
                            f"Here is the readme file of the package's GitHub repository:"
                            f"\n{delimit_code(readme[:MAX_LENGTH_FILE_PROMPTS], "markdown")}"
                        )
                    if package_json:
                        evaluation_agent.add_message(
                            f"Here is the package.json file of the package's GitHub repository:"
                            f"\n{delimit_code(package_json[:MAX_LENGTH_FILE_PROMPTS], "json")}"
                        )
                    if main:
                        evaluation_agent.add_message(
                            f"Here is the main file of the package's GitHub repository:"
                            f"\n{delimit_code(main[:MAX_LENGTH_FILE_PROMPTS], "javascript")}"
                        )
                    if tests:
                        evaluation_agent.add_message(
                            f"Here are some test files of the package's GitHub repository:"
                            f"\n{
                                "\n".join(f"{path}:\n{delimit_code(content[:MAX_LENGTH_FILE_PROMPTS], "javascript")}"
                                for path, content in tests[:MAX_NUM_TEST_FILES])
                            }"
                        )
                    readable_logger.set_crop()
                    (choice, data) = evaluation_agent.get_data(
                        IList(
                            "Do the following",
                            IItem(
                                "think",
                                IData(f"Go through each condition step by step and check if it satisfied")
                            ),
                            IItem(
                                "choose",
                                IChoice(
                                    f"Choose one of the following options",
                                    IList(
                                        f"If at least one of the conditions is satisfied",
                                        IItem(
                                            "satisfied",
                                            IData(f"Explain which conditions are satisfied")
                                        )
                                    ),
                                    IList(
                                        f"Otherwise",
                                        IItem("unsatisfied")
                                    )
                                )
                            )
                        )
                    )[1]
                    match choice:
                        case "satisfied":
                            raise LLMRejectedError(f"LLM rejected the package because of:\n{pad_text(data[0], "  ")}")
                # Generate package examples
                with LogList(readable_logger, LogFile(logs_path / f"generation.txt")) as logger:
                    generation_agent = agent.get_copy()
                    generation_agent.set_logger(logger)
                    generation_agent.set_tag("generation")
                    generation_agent.add_message(
                        list_text(
                            f"You are an autonomous agent and JavaScript/Node/NPM expert",
                            f"The user is a program that can only interact with you in predetermined ways",
                            f"The user will give you a task and instructions on how to complete the task",
                            f"You should try to achieve the task by following the instructions of the user"
                        ),
                        role="developer"
                    )
                    generation_agent.add_message(
                        list_text(
                            f"Your task is to create an example for the npm package \"{package_name}\" with the following requirements " + list_text(
                                f"It should import the package using CommonJS style imports",
                                f"It should use as much functionality of the package as is possible",
                                f"It should not require user inputs",
                                f"It should execute in Node without errors",
                                f"It should execute with only \"{package_name}\" installed",
                                add_scope=True
                            )
                        )
                    )
                    # Crop long messages for print readability
                    readable_logger.set_crop(MAX_LENGTH_FILE_PRINTS)
                    if readme:
                        generation_agent.add_message(
                            f"Here is the readme file of the package's GitHub repository:"
                            f"\n{delimit_code(readme[:MAX_LENGTH_FILE_PROMPTS], "markdown")}"
                        )
                    if package_json:
                        generation_agent.add_message(
                            f"Here is the package.json file of the package's GitHub repository:"
                            f"\n{delimit_code(package_json[:MAX_LENGTH_FILE_PROMPTS], "json")}"
                        )
                    if main:
                        generation_agent.add_message(
                            f"Here is the main file of the package's GitHub repository:"
                            f"\n{delimit_code(main[:MAX_LENGTH_FILE_PROMPTS], "javascript")}"
                        )
                    if tests:
                        generation_agent.add_message(
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
                            example = generation_agent.get_data(
                                    IList(
                                        "Do the following",
                                        IItem(
                                            "think",
                                            IData(f"Go through each requirement step by step and think about how you are going to satisfy it")
                                        ),
                                        IItem(
                                            "example",
                                            ICode(f"Provide the content of the example", "javascript")
                                        ),
                                        effect=f"I will check if the example satisfies the requirements"
                                    )
                                )[1]
                            printer(f"Success")
                        with printer(f"Checking example {example_index}:"):
                            output = run_example(example, examples_sub_path / f"{example_index}.js")
                            example_index += 1
                            if output.get("require_missing", False):
                                generation_agent.add_message(
                                    f"Your example does not contain an import statement for the package e.g. \"require('{package_name}')\"."
                                    f"\nAdd an import statement for the package with the exact package name i.e. \"{package_name}\"."
                                )
                                continue
                            if output.get("shell_code", 0):
                                if output.get("shell_timeout", False):
                                    generation_agent.add_message(
                                        f"Running your example with Node did not finish after {EXECUTION_TIMEOUT} seconds:"
                                        f"\n{delimit_code(output["shell_output"], "shell")}"
                                        f"\nMake the example complete in under {EXECUTION_TIMEOUT} seconds and wait for user inputs."
                                    )
                                    continue
                                generation_agent.add_message(
                                    f"Running your example with Node failed with code {output["shell_code"]}:"
                                    f"\n{delimit_code(output["shell_output"], "shell")}"
                                    f"\nFix the error."
                                )
                                continue
                            break
            if combine_examples:
                with printer("Combining generated examples:"):
                    combined_examples_sub_path = examples_path / COMBINED_GENERATION_PATH
                    create_dir(combined_examples_sub_path)
                    combined_example = combine_files_helper(get_children(examples_sub_path))
                    run_example(combined_example, combined_examples_sub_path / "0.js")

        # doing generation first, can be faster because of llm rejection
        if generate_with_llm:
            generate_with_llm_helper()
        if extract_from_readme:
            extract_from_readme_helper()
        if combine_examples:
            with printer("Combining all examples:"):
                combined_examples_sub_path = examples_path / COMBINED_ALL_PATH
                create_dir(combined_examples_sub_path)
                paths = get_children(examples_path / EXTRACTION_PATH) + get_children(examples_path / GENERATION_PATH)
                combined_example = combine_files_helper(paths)
                run_example(combined_example, combined_examples_sub_path / "0.js")