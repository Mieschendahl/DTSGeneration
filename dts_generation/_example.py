
from functools import partial
import json
from pathlib import Path
import re
import shutil
from typing import Optional

from easy_prompting.prebuilt import GPT, LogList, LogFile, LogFunc, LogReadable, Prompter, IList, IData, ICode, IChoice, IItem, delimit_code, list_text, create_interceptor, pad_text
from dts_generation._utils import ShellError, create_dir, get_children, is_empty, printer, create_file, shell

MAX_NUM_MESSAGE_LINES = 3
MAX_NUM_TESTS = 3
MAX_NUM_GENERATION_ATTEMPTS = 3
MAX_FILE_PROMPT_LENGTH = 10000

class ReproductionError(Exception):
    pass

class PackageDataMissingError(Exception):
    pass

class CommonJSUnsupportedError(Exception):
    pass

class NodeJSUnsupportedError(Exception):
    pass

class PackageInstallationError(Exception):
    pass

def clone_repository(package_name: str, output_path: Path, installation_timeout: int, verbose_setup: bool) -> None:
    with printer(f"Cloning the GitHub repository:"):
        if not is_empty(output_path):
            printer(f"Success (already cloned)")
            return
        try:
            shell_output = shell(f"npm view {package_name} repository --json", timeout=installation_timeout, verbose=verbose_setup)
        except ShellError as e:
            raise PackageDataMissingError(f"npm view failed") from e
        if not shell_output.value:
            raise PackageDataMissingError(f"No npm view value found")
        try:
            repo_data = json.loads(shell_output.value)
        except Exception as e:
            raise PackageDataMissingError(f"npm view value is invalid: {shell_output.value}") from e
        url = repo_data.get("url", "") if isinstance(repo_data, dict) else repo_data
        if "github.com" not in url:
            raise PackageDataMissingError(f"No GitHub URL found")
        github_url = "https://github.com" + url.split("github.com", 1)[-1].split(".git")[0]
        create_dir(output_path, overwrite=True)
        try:
            shell(f"git clone --depth 1 {github_url} {output_path}", timeout=installation_timeout, verbose=verbose_setup)
        except ShellError as e:
            raise PackageDataMissingError(f"Git clone failed") from e
        if is_empty(output_path):
            raise PackageDataMissingError(f"Repository clone is empty")
        printer(f"Success")

def get_package_json(output_path: Path, repository_path: Path) -> Optional[str]:
    try:
        package_json_path = repository_path / "package.json"
        if package_json_path.is_file():
            package_json = package_json_path.read_text()
            create_file(output_path, content=package_json)
            printer(f"Package file found")
            return package_json
        printer(f"No package file found")
    except Exception:
        pass
    return None

def get_readme(output_path: Path, repository_path: Path) -> Optional[str]:
    try:
        for readme_path in get_children(repository_path):
            if readme_path.is_file() and "readme" in readme_path.name.lower():
                readme = readme_path.read_text()
                create_file(output_path, content=readme)#
                printer(f"Readme file found")
                return readme_path.read_text()
        printer(f"No readme file found")
    except Exception:
        pass
    return None

def get_main(output_path: Path, repository_path: Path) -> Optional[str]:
    try:
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
    except Exception:
        pass
    return None

def get_tests(output_path: Path, repository_path: Path) -> list[tuple[str, str]]:
    tests_ls = []
    try:
        tests = {}
        # Check well-known test directories
        test_dirs = ["test", "tests", "__tests__"]
        for d in test_dirs:
            test_path = repository_path / d
            if test_path.is_dir():
                for f in test_path.rglob("*.js"):
                    try:
                        tests[f.relative_to(repository_path)] = f.read_text()
                    except UnicodeDecodeError:
                        pass
        # Check repo for suffixes
        test_suffixes = [".test.js", ".spec.js"]
        for suffix in test_suffixes:
            for f in repository_path.rglob(f"*{suffix}"):
                if f.suffix ==".js":
                    try:
                        tests[f.relative_to(repository_path)] = f.read_text()
                    except UnicodeDecodeError:
                        pass
        tests_ls = [(path, content) for path, content in sorted(tests.items()) if content]
        create_dir(output_path, overwrite=True)
        for i, (path, content) in enumerate(tests):
            (output_path / f"{i}.js").write_text(f"// File: {path}\n\n{content}")
        printer(f"{len(tests)} test file(s) found")
    except Exception:
        pass
    return tests_ls

def build_template_project(package_name: str, data_path: Path, output_path: Path, installation_timeout: int, verbose_setup: bool, reproduce: bool):
    with printer(f"Building template npm project:"):
        if not is_empty(output_path):
            printer("Success (already build)")
            return
        create_dir(output_path, overwrite=True)
        with printer(f"Installing packages:"):
            try:
                if reproduce:
                    if not (data_path / "package.json").is_file() or not (data_path / "package-lock.json").is_file():
                        raise ReproductionError("Need package.json and package-lock.json from previous build, to build template project in reproduction mode")
                    create_file(output_path / "package.json", data_path / "package.json")
                    create_file(output_path / "package-lock.json", data_path / "package-lock.json")
                    shell(f"npm ci", cwd=output_path, timeout=installation_timeout, verbose=verbose_setup)
                else:
                    shell(f"npm install tsx typescript @types/node {package_name}", cwd=output_path, timeout=installation_timeout, verbose=verbose_setup)
                    create_file(data_path / "package.json", output_path / "package.json")
                    create_file(data_path / "package-lock.json", output_path / "package-lock.json")
                printer(f"Success")
            except ShellError as e:
                raise PackageInstallationError(f"Running npm install {package_name} failed") from e

def combine_example_files(file_paths: list[Path], relative_path: Path) -> Optional[str]:
    with printer(f"Combining examples:"):
        if len(file_paths) == 0:
            printer(f"No examples found")
            return
        combined_parts = []
        for file_path in file_paths:
            content = file_path.read_text()
            wrapped = (
                f"// File: {file_path.relative_to(relative_path)}\n\n"
                f"(function() {"{\n" + pad_text(content, "  ") + "\n}"})();"
            )
            combined_parts.append(wrapped)
        printer(f"Success")
        return "\n\n".join(combined_parts)

def generate_examples(
    package_name: str,
    output_path: Path,
    execution_timeout: int,
    installation_timeout: int,
    verbose_setup: bool,
    verbose_execution: bool,
    verbose_files: bool,
    evaluate_with_llm: bool,
    extract_from_readme: bool,
    generate_with_llm: bool,
    llm_model_name: str,
    llm_temperature: int,
    llm_verbose: bool,
    llm_interactive: bool,
    llm_use_cache: bool, # Makes llm_temperature > 0 obsolete,
    combine_examples: bool,
    combined_only: bool,
    reproduce: bool
) -> None:
    with printer(f"Generating examples:"):
        llm_verbose = llm_verbose or llm_interactive
        # Setting up directory interface
        cache_path = output_path / "cache"
        create_dir(cache_path, overwrite=False)
        logs_path = output_path / "logs"
        create_dir(logs_path, overwrite=False)
        data_path = output_path / "data"
        create_dir(data_path, overwrite=False)
        playground_path = cache_path / "playground"
        create_dir(playground_path, overwrite=True)
        examples_path = output_path / "examples"
        create_dir(examples_path, overwrite=True)
        candidates_path = cache_path / "candidates"
        create_dir(candidates_path, overwrite=True)
        # Gather ressources for example generation
        repository_path = cache_path / "repository"
        clone_repository(package_name, repository_path, installation_timeout, verbose_setup)
        create_file(data_path / "has_repository")
        package_json = get_package_json(data_path / "package.json", repository_path)
        readme = get_readme(data_path / "README.md", repository_path)
        main = get_main(data_path / "index.js", repository_path)
        tests = get_tests(data_path / "tests", repository_path)
        if len(tests) > 0:
            create_file(data_path / "has_tests")
        if not (readme or package_json or main or tests):
            raise PackageDataMissingError("Not enough package information found")
        # Create tempalte project in which to run examples
        template_path = cache_path / "template"
        build_template_project(package_name, data_path, template_path, installation_timeout, verbose_setup, reproduce)
        # Regex for checking if a basic requrie statement is used for the package
        require_pattern = r'\brequire\s*\(\s*["\'`]' + package_name + r'["\'`]\s*\)'
        # Defining reusable helper function for example testing
        def test_example(example_name: int | str, example: str, candidates_path: Optional[Path] = None, examples_path: Optional[Path] = None) -> dict:
            with printer(f"Testing example \"{example_name}.js\""):
                if verbose_files:
                    with printer(f"Example content:"):
                        printer(example)
                main_path = playground_path / "index.js"
                if candidates_path is not None:
                    create_file(candidates_path / f"{example_name}.js", content=example)
                with printer(f"Checking import statements:"):
                    if not re.search(require_pattern, example):
                        printer(f"Fail")
                        return dict(require=True, code=0, shell="", timeout=False)
                    printer(f"Success")
                create_dir(playground_path, template_path, overwrite=True)
                create_file(main_path, content=example)
                with printer(f"Running example with Node:"):
                    shell_output = shell(f"node {main_path.name}", cwd=playground_path, check=False, timeout=execution_timeout, verbose=verbose_execution)
                    if shell_output.code:
                        printer(f"Fail")
                    else:
                        printer(f"Success")
                        if examples_path is not None:
                            create_file(examples_path / f"{example_name}.js", content=example)
                    return dict(require=False, code=shell_output.code, shell=shell_output.value, timeout=shell_output.timeout)
        # Checking if package is usable
        with printer(f"Checking CommonJS support:"):
            output = test_example("test_require", f"const package = require(\"{package_name}\");", cache_path / "test")
            if output["code"]:
                raise CommonJSUnsupportedError(f"Require statement fails on package with error:\n{pad_text(output["shell"])}")
        # Evaluate if the package satisfies the necessary requirements, such as Node, CommonJS, (potentially even ES5 compatibility)
        if evaluate_with_llm:
            with printer(f"Evaluating package with LLM:"):
                if not (readme or package_json or main):
                    printer(f"Not enough package information")
                else:
                    readable_logger = LogReadable(LogFunc(partial(printer, end="\n\n")))
                    readable_logger.set_verbose(llm_verbose)
                    tag = "evaluation"
                    file_logger = LogFile(logs_path / f"{tag}.txt")
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
                                f"The npm package \"{package_name}\" can be imported via the CommonJS module system and executed via Node.",
                                f"Your task is to decide if the package can be used directly in Node or not because e.g. it is browser-exclusive or framework-dependent."
                            )
                        )
                        readable_logger.set_crop(MAX_NUM_MESSAGE_LINES)
                        if readme:
                            agent.add_message(
                                f"Here is the readme file of the package's GitHub repository:"
                                f"\n{delimit_code(readme[:MAX_FILE_PROMPT_LENGTH], "markdown")}"
                            )
                        if package_json:
                            agent.add_message(
                                f"Here is the package.json file of the package's GitHub repository:"
                                f"\n{delimit_code(package_json[:MAX_FILE_PROMPT_LENGTH], "json")}"
                            )
                        if main:
                            agent.add_message(
                                f"Here is the main file of the package's GitHub repository:"
                                f"\n{delimit_code(main[:MAX_FILE_PROMPT_LENGTH], "javascript")}"
                            )
                        readable_logger.set_crop()
                        choice, (explanation,) = agent.get_data(
                                IList(
                                    "Do the following",
                                    IItem(
                                        "think",
                                        IData(f"Think about how to complete the current task.")
                                    ),
                                    IItem(
                                        "choose",
                                        IChoice(
                                            f"Then choose exactly one of the following options",
                                            IList(
                                                f"If the package can be used directly in Node",
                                                IItem("yes", IData("Explain why this is the case"))
                                            ),
                                            IList(
                                                f"Otherwise",
                                                IItem("no", IData("Explain why this is the case")),
                                            )
                                        )
                                    )
                                )
                            )[1]
                        create_file(logs_path / "evaluation_decision.txt", content=explanation)
                    match choice:
                        case "yes":
                            printer(f"Package is usable")
                        case "no":
                            printer(f"Package is not usable")
                            raise NodeJSUnsupportedError(explanation)
        # Manually extract examples from the readme file of the package
        if extract_from_readme:
            with printer(f"Extracting examples from the readme file:"):
                # if not readme:
                #     raise PackageDataMissingError("Readme file missing for extraction mode")
                if readme:
                    examples_sub_path = examples_path / "extraction"
                    create_dir(examples_sub_path, overwrite=True)
                    candidates_sub_path = candidates_path / "extraction"
                    create_dir(candidates_sub_path, overwrite=True)
                    examples = re.findall( r"```.*?\n(.*?)```", readme, flags=re.DOTALL)
                    examples = [example.strip() for example in examples]
                    printer(f"Found {len(examples)} example(s)")
                    for example_index, example in enumerate(examples):
                        with printer(f"Checking example {example_index}:"):
                            test_example(example_index, example, candidates_sub_path, examples_sub_path)
                    if combine_examples:
                        with printer("Combining extracted examples:"):
                            example = combine_example_files(get_children(examples_sub_path), output_path)
                            combined_examples_sub_path = examples_path / "combined_extraction"
                            combined_candidates_sub_path = candidates_sub_path / "combined_extraction"
                            if example is not None:
                                test_example("combined_extraction", example, combined_candidates_sub_path, combined_examples_sub_path)
                        if combined_only:
                            create_dir(cache_path / "examples" / examples_sub_path.name, examples_sub_path, overwrite=True) # for debug / combining all
                            shutil.rmtree(examples_sub_path, ignore_errors=True)
                else:
                    printer(f"No readme file available for extraction")
        # Generate examples with an LLM
        if generate_with_llm:
            with printer(f"Generating examples with LLM:"):
                examples_sub_path = examples_path / "generation"
                create_dir(examples_sub_path, overwrite=True)
                candidates_sub_path = candidates_path / "generation"
                create_dir(candidates_sub_path, overwrite=True)
                readable_logger = LogReadable(LogFunc(partial(printer, end="\n\n")))
                readable_logger.set_verbose(llm_verbose)
                tag = "generation"
                file_logger = LogFile(logs_path / f"{tag}.txt")
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
                            f"Make sure that the example uses CommonJS style imports and exports and includes require('{package_name}').",
                            f"Make sure that the example does not import any other npm packages that would first need to be installed.",
                            f"Make sure that the example does not run indefinitly, e.g. in case a server gets started.",
                            f"Make sure that the example does not require user input.",
                            # f"Make sure that the example is written in ES5."
                        )
                    )
                    readable_logger.set_crop(MAX_NUM_MESSAGE_LINES)
                    if readme:
                        agent.add_message(
                            f"Here is the readme file of the package's GitHub repository:"
                            f"\n{delimit_code(readme[:MAX_FILE_PROMPT_LENGTH], "markdown")}"
                        )
                    if package_json:
                        agent.add_message(
                            f"Here is the package.json file of the package's GitHub repository:"
                            f"\n{delimit_code(package_json[:MAX_FILE_PROMPT_LENGTH], "json")}"
                        )
                    if main:
                        agent.add_message(
                            f"Here is the main file of the package's GitHub repository:"
                            f"\n{delimit_code(main[:MAX_FILE_PROMPT_LENGTH], "javascript")}"
                        )
                    if tests:
                        agent.add_message(
                            f"Here are some test files of the package's GitHub repository:"
                            f"\n{
                                "\n".join(f"{path}:\n{delimit_code(content[:MAX_FILE_PROMPT_LENGTH], "javascript")}"
                                for path, content in tests[:MAX_NUM_TESTS])
                            }"
                        )
                    readable_logger.set_crop()
                    # Reprompt LLM for an example until the example is valid
                    example_index = 0
                    while True:
                        with printer(f"Generating example {example_index}:"):
                            if example_index >= MAX_NUM_GENERATION_ATTEMPTS:
                                printer(f"Aborting: LLM failed generating a valid example in {MAX_NUM_GENERATION_ATTEMPTS} attempt(s)")
                                break
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
                        with printer(f"Checking example {example_index}:"):
                            example_index += 1
                            output = test_example(example_index, example, candidates_sub_path, examples_sub_path)
                            if output["require"]:
                                agent.add_message(
                                    f"Your example does not include an import statement such as require('{package_name}')."
                                    f"\nPlease do not use any other name than exactly \"{package_name}\" in the require statement, else we can not proceed."
                                )
                                continue
                            if output["code"]:
                                if output["timeout"]:
                                    agent.add_message(
                                        f"Running your example with Node did not finish after {execution_timeout} seconds:"
                                        f"\n{delimit_code(output["shell"], "shell")}"
                                    )
                                    continue
                                agent.add_message(
                                    f"Running your example with Node failed with code {output["code"]}:"
                                    f"\n{delimit_code(output["shell"], "shell")}"
                                )
                                continue
                            break
                # Currently only one example is produced, so this is unecessary but more uniform.
                # Even if multiple examples are produced, we still have to ask if we want an LLM to combine them.
                if combine_examples:
                    with printer("Combining generated examples:"):
                        example = combine_example_files(get_children(examples_sub_path), output_path)
                        combined_examples_sub_path = examples_path / "combined_generation"
                        combined_candidates_sub_path = candidates_sub_path / "combined_generation"
                        if example is not None:
                            test_example("combined_generation", example, combined_candidates_sub_path, combined_examples_sub_path)
                    if combined_only:
                        create_dir(cache_path / "examples" / examples_sub_path.name, examples_sub_path, overwrite=True) # for debug / combining all
                        shutil.rmtree(examples_sub_path, ignore_errors=True)
        if combine_examples and extract_from_readme and generate_with_llm:
            with printer("Combining all examples:"):
                example = combine_example_files(
                    get_children(cache_path / "examples" / "extraction") + get_children(cache_path / "examples" / "generation"),
                    output_path
                )
                combined_examples_sub_path = examples_path / "combined_all"
                combined_candidates_sub_path = candidates_path / "combined_all"
                if example is not None:
                    test_example("combined_all", example, combined_candidates_sub_path, combined_examples_sub_path)