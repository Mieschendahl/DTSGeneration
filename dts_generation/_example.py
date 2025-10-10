
from functools import partial
import json
from pathlib import Path
import re
from typing import Optional

from easy_prompting.prebuilt import GPT, LogList, LogFile, LogFunc, LogReadable, Prompter, IList, IData, ICode, IChoice, IItem, delimit_code, list_text, create_interceptor
from dts_generation._utils import create_dir, printer, create_file, shell, GenerationError

MAX_NUM_MESSAGE_LINES = 3
MAX_NUM_TESTS = 3
MAX_NUM_GENERATION_ATTEMPTS = 3

class EvaluationError(GenerationError):
    pass

def clone_repository(package_name: str, output_path: Path, installation_timeout: int, verbose_setup: bool) -> None:
    with printer(f"Cloning the GitHub repository:"):
        if output_path.is_dir() and any(output_path.iterdir()):
            printer(f"Success (already cloned)")
            return
        shell_output = shell(f"npm view {package_name} repository --json", timeout=installation_timeout, verbose=verbose_setup)
        if not shell_output.value:
            raise GenerationError(f"No npm view value found")
        try:
            repo_data = json.loads(shell_output.value)
        except Exception as e:
            raise GenerationError(f"npm view value is invalid: {shell_output.value}") from e
        url = repo_data.get("url", "") if isinstance(repo_data, dict) else repo_data
        if "github.com" not in url:
            raise GenerationError(f"No GitHub URL found")
        github_url = "https://github.com" + url.split("github.com", 1)[-1].split(".git")[0]
        create_dir(output_path, overwrite=True)
        shell_output = shell(f"git clone --depth 1 {github_url} {output_path}", check=False, timeout=installation_timeout, verbose=verbose_setup)
        if shell_output.code:
            if shell_output.code == 128:
                raise GenerationError(f"GitHub URL is invalid: {github_url}")
            else:
                raise Exception(f"Unexpected git clone fail with exit code: {shell_output.code}")
        printer(f"Success")

def get_package_json(output_path: Path, repository_path: Path) -> Optional[str]:
    assert repository_path.is_dir(), "Repository not found"
    package_json_path = repository_path / "package.json"
    if package_json_path.is_file():
        package_json = package_json_path.read_text()
        create_file(output_path, content=package_json)
        printer(f"Package file found")
        return package_json
    printer(f"No package file found")
    return None

def get_readme(output_path: Path, repository_path: Path) -> Optional[str]:
    assert repository_path.is_dir(), "Repository not found"
    for readme_path in repository_path.iterdir():
        if readme_path.is_file() and "readme" in readme_path.name.lower():
            readme = readme_path.read_text()
            create_file(output_path, content=readme)#
            printer(f"Readme file found")
            return readme_path.read_text()
    printer(f"No readme file found")
    return None

def get_main(output_path: Path, repository_path: Path) -> Optional[str]:
    package_json_path = repository_path / "package.json"
    if package_json_path.is_file():
        # Check if package.json contains a main file reference
        try:
            package_json = json.loads(package_json_path.read_text())
            main_path = repository_path / package_json["main"]
            if main_path.is_file():
                main = main_path.read_text()
                create_file(output_path, content=main)
                printer(f"Main file found")
                return main
        except Exception:
            pass
        # Fallback: search for common main file names
        main_names = ["index.js", "index.json", "index.node"]
        for name in main_names:
            main_path = repository_path / name
            if main_path.is_file():
                main = main_path.read_text()
                create_file(output_path, content=main)
                printer(f"Main file found")
                return main
        printer(f"No main file found")
        return None

def get_tests(output_path: Path, repository_path: Path) -> list[tuple[str, str]]:
    tests = {}
    # Check well-known test directories
    test_dirs = ["test", "tests", "__tests__"]
    for d in test_dirs:
        test_path = repository_path / d
        if test_path.is_dir():
            for f in test_path.rglob("*.js"):
                tests[f.relative_to(repository_path)] = f.read_text()
            for f in test_path.rglob("*.ts"):
                tests[f.relative_to(repository_path)] = f.read_text()
    # Sntire repo for suffixes
    test_suffixes = [".test.js", ".spec.js", ".test.ts", ".spec.ts"]
    for suffix in test_suffixes:
        for f in repository_path.rglob(f"*{suffix}"):
            if f.suffix in (".js", ".ts"):
                tests[f.relative_to(repository_path)] = f.read_text()
    tests = [(path, content) for path, content in sorted(tests.items()) if content]
    create_dir(output_path, overwrite=True)
    for i, (path, content) in enumerate(tests):
        (output_path / f"{i}.js").write_text(f"// file-path: {path}\n\n{content}")
    printer(f"{len(tests)} test file(s) found")
    return tests

def build_template_project(package_name: str, output_path: Path, installation_timeout: int, verbose_setup: bool):
    with printer(f"Building template npm project:"):
        if output_path.is_dir() and any(output_path.iterdir()):
            printer("Success (already build)")
            return
        create_dir(output_path, overwrite=True)
        with printer(f"Installing packages:"):
            shell(f"npm install tsx typescript @types/node {package_name}", cwd=output_path, timeout=installation_timeout, verbose=verbose_setup)
            printer(f"Success")

def generate_examples(
    package_name: str,
    output_path: Path,
    execution_timeout: int,
    installation_timeout: int,
    verbose_setup: bool,
    verbose_execution: bool,
    verbose_files: bool,
    evaluate_package: bool,
    extract_from_readme: bool,
    generate_with_llm: bool,
    llm_model_name: str,
    llm_temperature: int,
    llm_verbose: bool,
    llm_interactive: bool,
    llm_use_cache: bool # Makes llm_temperature > 0 obsolete
) -> None:
    with printer(f"Generating examples:"):
        llm_verbose = llm_verbose or llm_interactive
        cache_path = output_path / "cache"
        # Gather ressources for example generation
        repository_path = cache_path / "repository"
        clone_repository(package_name, repository_path, installation_timeout, verbose_setup)
        data_path = output_path / "data"
        package_json = get_package_json(data_path / "package.json", repository_path)
        readme = get_readme(data_path / "README.md", repository_path)
        main = get_main(data_path / "main.js", repository_path)
        tests = get_tests(data_path / "tests", repository_path)
        if not (readme or package_json or main or tests):
            raise GenerationError("Not enough package information found")
        # Evaluate if the package satisfies the necessary requirements
        if evaluate_package:
            with printer(f"Evaluating package:"):
                readable_logger = LogReadable(LogFunc(partial(printer, end="\n\n")))
                readable_logger.set_verbose(llm_verbose)
                tag = "evaluation"
                file_logger = LogFile(output_path / "logs" / f"{tag}.txt")
                with LogList(readable_logger, file_logger) as logger:
                    model = GPT(model=llm_model_name, temperature=llm_temperature)
                    agent = Prompter(model)
                    agent.set_logger(logger)
                    if llm_interactive:
                        agent.set_interceptor(create_interceptor(partial(printer, end="")))
                    if llm_use_cache:
                        agent.set_cache_path(cache_path / "prompter" / llm_model_name)
                    agent.set_tag(tag)
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
                            f"I want to know if the npm package \"{package_name}\" supports being executed with Node.",
                            f"Some npm packages are e.g. browser-exclusive or framework-dependent such that they can not be executed via Node.",
                            f"Your task is to determine whether the npm package can possibly be executed via Node."
                        )
                    )
                    readable_logger.set_crop(MAX_NUM_MESSAGE_LINES)
                    if readme:
                        agent.add_message(
                            f"Here is the readme file of the package's GitHub repository:"
                            f"\n{delimit_code(readme, "markdown")}"
                        )
                    if package_json:
                        agent.add_message(
                            f"Here is the package.json file of the package's GitHub repository:"
                            f"\n{delimit_code(package_json, "json")}"
                        )
                    if main:
                        agent.add_message(
                            f"Here is the main file of the package's GitHub repository:"
                            f"\n{delimit_code(main, "javascript")}"
                        )
                    if tests:
                        agent.add_message(
                            f"Here are some test files of the package's GitHub repository:"
                            f"\n{
                                "\n".join(f"{path}:\n{delimit_code(content, "javascript")}"
                                for path, content in tests[:MAX_NUM_TESTS])
                            }"
                        )
                    readable_logger.set_crop()
                    choice, explanation = agent.get_data(
                            IList(
                                "Do the following",
                                IItem(
                                    "think",
                                    IData(f"Think about how to complete the current task.")
                                ),
                                IItem(
                                    "choose",
                                    IChoice(
                                        f"Then choose exactly one of the following answers",
                                        IList(
                                            f"If the package can possibly be executed via Node",
                                            IItem("possible", IData("Explain why it is possible"))
                                        ),
                                        IList(
                                            f"Otherwise",
                                            IItem("impossible", IData("Explain why it is not possible")),
                                        )
                                    )
                                )
                            )
                        )[1]
                match choice:
                    case "possible":
                        printer(f"Package is usable")
                    case "impossible":
                        printer(f"Package is not usable")
                        raise EvaluationError(explanation)
        # Quit if we only want to evaluate the package
        if not (extract_from_readme or generate_with_llm):
            return
        # Setting up directory interface
        playground_path = cache_path / "playground"
        create_dir(playground_path, overwrite=True)
        examples_path = output_path / "examples"
        create_dir(examples_path, overwrite=False)
        candidates_path = cache_path / "example_candidates"
        create_dir(candidates_path, overwrite=False)
        template_path = cache_path / "template"
        build_template_project(package_name, template_path, installation_timeout, verbose_setup)
        # Manually extract examples from the readme file of the package
        if extract_from_readme:
            with printer(f"Extracting examples from the readme file:"):
                if not readme:
                    raise GenerationError("Readme file missing for extraction mode")
                examples_sub_path = examples_path / "extraction"
                candidates_sub_path = candidates_path / "extraction"
                examples = re.findall( r"```.*?\n(.*?)```", readme, flags=re.DOTALL)
                examples = [example.strip() for example in examples]
                printer(f"Found {len(examples)} example(s)")
                for example_index, example in enumerate(examples):
                    with printer(f"Testing example {example_index}:"):
                        if verbose_files:
                            with printer(f"Example content:"):
                                printer(example)
                        with printer(f"Running example with Node:"):
                            create_file(candidates_sub_path / f"{example_index}.js", content=example)
                            create_dir(playground_path, template_path, overwrite=True)
                            create_file(playground_path / "index.js", content=example)
                            shell_output = shell(f"node index.js", cwd=playground_path, check=False, timeout=execution_timeout, verbose=verbose_execution)
                            if shell_output.code:
                                printer(f"Fail")
                            else:
                                printer(f"Success")
                                create_file(examples_sub_path / f"{example_index}.js", content=example)
        # Generate examples with an LLM
        if generate_with_llm:
            with printer(f"Generating examples with LLM:"):
                examples_sub_path = examples_path / "generation"
                candidates_sub_path = candidates_path / "generation"
                readable_logger = LogReadable(LogFunc(partial(printer, end="\n\n")))
                readable_logger.set_verbose(llm_verbose)
                tag = "generation"
                file_logger = LogFile(output_path / "logs" / f"{tag}.txt")
                with LogList(readable_logger, file_logger) as logger:
                    model = GPT(model=llm_model_name, temperature=llm_temperature)
                    agent = Prompter(model)
                    agent.set_logger(logger)
                    if llm_interactive:
                        agent.set_interceptor(create_interceptor(partial(printer, end="")))
                    if llm_use_cache:
                        agent.set_cache_path(cache_path / "prompter" / llm_model_name)
                    agent.set_tag(tag)
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
                            f"Make sure that the example does not import packages that are not installed by default, except \"{package_name}\".",
                            f"Make sure that the example does not run indefinitly, e.g. in case a server gets started.",
                            f"Make sure that the example does not require user input.",
                            # f"Make sure that the example is written in ES5."
                        )
                    )
                    readable_logger.set_crop(MAX_NUM_MESSAGE_LINES)
                    if readme:
                        agent.add_message(
                            f"Here is the readme file of the package's GitHub repository:"
                            f"\n{delimit_code(readme, "markdown")}"
                        )
                    if package_json:
                        agent.add_message(
                            f"Here is the package.json file of the package's GitHub repository:"
                            f"\n{delimit_code(package_json, "json")}"
                        )
                    if main:
                        agent.add_message(
                            f"Here is the main file of the package's GitHub repository:"
                            f"\n{delimit_code(main, "javascript")}"
                        )
                    if tests:
                        agent.add_message(
                            f"Here are some test files of the package's GitHub repository:"
                            f"\n{
                                "\n".join(f"{path}:\n{delimit_code(content, "javascript")}"
                                for path, content in tests[:MAX_NUM_TESTS])
                            }"
                        )
                    readable_logger.set_crop()
                    # Reprompt LLM for an example until the example is valid
                    example_index = 0
                    while True:
                        with printer(f"Generating example {example_index}:"):
                            if example_index > MAX_NUM_GENERATION_ATTEMPTS:
                                raise GenerationError(f"LLM failed generating a valid example in {MAX_NUM_GENERATION_ATTEMPTS} attempt(s)")
                            example = agent.get_data(
                                    IList(
                                        "Do the following",
                                        IItem(
                                            "think",
                                            IData(f"Think about how to complete the current task.")
                                        ),
                                        IItem(
                                            "example",
                                            ICode(f"Provide the content of an example.", "javascript")
                                        )
                                    )
                                )[1]
                            printer(f"Success")
                        with printer(f"Testing example {example_index}:"):
                            if verbose_files:
                                with printer(f"Content:"):
                                    printer(example)
                            with printer(f"Running example with Node:"):
                                create_file(candidates_sub_path / f"{example_index}.js", content=example)
                                create_dir(playground_path, template_path, overwrite=True)
                                create_file(playground_path / "index.js", content=example)
                                shell_output = shell(f"node index.js", cwd=playground_path, check=False, timeout=execution_timeout, verbose=verbose_execution)
                                if shell_output.code:
                                    printer(f"Fail (retrying example generation)")
                                    if shell_output.timeout:
                                        agent.add_message(
                                            f"Running your example with Node did not finish after {execution_timeout} seconds:"
                                            f"\n{delimit_code(shell_output.value, "shell")}"
                                        )
                                    else:
                                        agent.add_message(
                                            f"Running your example with Node failed with code {shell_output.code}:"
                                            f"\n{delimit_code(shell_output.value, "shell")}"
                                        )
                                    example_index += 1
                                    continue
                                printer(f"Success")
                        create_file(examples_sub_path / f"{example_index}.js", content=example)
                        example_index += 1
                        break