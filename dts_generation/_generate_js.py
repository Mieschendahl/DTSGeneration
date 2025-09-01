from pathlib import Path
import re
import shutil
import sys
import traceback
from typing import Optional
from easy_prompting.prebuilt import GPT, Prompter, Message, Option, delimit_code, extract_code, PrettyLogger
from dts_generation._utils import clone_package_repository, create_file, get_main, get_readme, create_dir, get_tests, shell

MAX_LINES = 20

def generate_examples(model_name: str, temperature: int, interactive_llm, package_name: str, package_path: Path, execution_timeout: int,
                      no_readme_extraction: bool, simple_llm_generation: bool, advanced_llm_generation: bool, reproduce: bool, no_cache: bool) -> None:        
    examples_path = package_path / "examples"
    create_dir(examples_path)
    
    template_path = package_path / "template"
    create_dir(template_path)

    package_json_path = package_path / "reproduction"
    create_dir(package_path)
    
    playground_path = package_path / "playground"
    create_dir(playground_path)
    
    log_path = package_path / "log"
    create_dir(log_path)

    repository_path = package_path / "repository"
    try:
        clone_package_repository(package_name, repository_path, overwrite=not reproduce)
    except Exception as e:
        print(f"Cloning the repository failed: {e}")
    
    try:
        readme = get_readme(repository_path)
        (package_path / "README.md").write_text(readme)
    except:
        readme = None
        
    try:
        main = get_main(repository_path, package_name)
        (package_path / "index.js").write_text(main)
    except:
        main = None
        
    try:
        tests = get_tests(repository_path)
        tests_path = package_path / "tests"
        create_dir(tests_path)
        for i, test in enumerate(tests):
            (tests_path / f"test_{i}").write_text(f"// {test['path']}\n\n{test['content']}")
    except:
        tests = []
    
    class Fail(Exception):
        pass

    ### README EXTRACTION ###
    
    if not no_readme_extraction:
        mode = "readme_extraction"
        try:
            examples_sub_path = examples_path / mode
            create_dir(examples_sub_path, overwrite=True)
            
            template_sub_path = template_path / mode
            create_dir(template_sub_path, overwrite=True)

            if not readme:
                raise Fail("No README file found in the repository")

            pattern = r"```.*?\n(.*?)```"
            code_blocks = re.findall(pattern, readme, flags=re.DOTALL)

            if len(code_blocks) == 0:
                raise Fail("No examples found in the README file")
            
            package_json_sub_path = package_json_path / mode
            print(f"\nInstalling example")
            if not reproduce:
                shell(f"npm init -y", cwd=template_sub_path)
                output = shell(f"npm install tsx typescript @types/node {package_name}", cwd=template_sub_path, check=False)
            else:
                if not package_json_sub_path.is_dir():
                    raise Fail("No package_json directory found for reproduction mode")
                create_file(template_sub_path / "package.json", package_json_sub_path / "package.json")
                create_file(template_sub_path / "package-lock.json", package_json_sub_path / "package-lock.json")
                output = shell(f"npm ci", cwd=template_sub_path, check=False)

            if output.code:
                raise Fail(f"Installation failed with code: {output.code}")
            
            create_dir(package_json_sub_path, overwrite=True)
            create_file(package_json_sub_path / "package.json", template_sub_path / "package.json")
            create_file(package_json_sub_path / "package-lock.json", template_sub_path / "package-lock.json")
            
            playground_sub_path = playground_path / mode
            example_index = 0
            for code_block in code_blocks:
                code_block = code_block.strip()
                create_dir(playground_sub_path, template_sub_path, overwrite=True)
                create_file(playground_sub_path / "index.js", content=code_block)
                print(f"\nRunnning example")
                output = shell(f"node index.js", cwd=playground_sub_path, check=False, timeout=execution_timeout)
                if output.code:
                    print(f"Node failed with return code: {output.code}")
                else:
                    create_file(examples_sub_path / f"example_{example_index}.js", content=code_block)
                    example_index += 1

        except Fail as e:
            print(f"Readme extraction failed: {e}")
            pass

    ### LLM GENERATION ###

    quoted_package_name = f'"{package_name}"'

    def add_package_info(agent: Prompter):
        if readme is not None:
            agent.add_message(
                    f"Here is the README file of {quoted_package_name}:"
                    f"\n{delimit_code(readme, "markdown")}"
                )
        if main is not None:
            agent.add_message(
                    f"Here is the main file of {quoted_package_name}:"
                    f"\n{delimit_code(main, "javascript")}"
                )
        if len(tests) > 0:
            agent.add_message(
                    f"Here is a list of test files of {quoted_package_name}:\n\n"
                    +
                    "\n\n".join(
                        f"{test['path']}:\n{delimit_code(test['content'], "javascript")}"
                        for test in tests
                    )
                )

    prompter = Prompter(
            GPT(
                model=model_name,
                temperature=temperature
            )
        )\
        .set_cache_path(None if no_cache else package_path / f"prompter/{model_name}")\
        .set_interaction(interactive_llm)
        
    ### SIMPLE LLM GENERATION ###

    if simple_llm_generation:
        mode = "simple_llm_generation"
        try:
            examples_sub_path = examples_path / mode
            create_dir(examples_sub_path, overwrite=True)
            
            template_sub_path = template_path / mode
            create_dir(template_sub_path, overwrite=True)

            if not (readme or main or tests):
                raise Fail("No README, nor main, nor test files found in the repository")

            log_sub_path = log_path / mode
            create_dir(log_sub_path, overwrite=True)
            with open(log_sub_path / "log.txt", "w") as file:
                with PrettyLogger(sys.stdout, file) as logger:
                    logger.set_max_lines(MAX_LINES)
                    generation_agent = prompter.get_copy()\
                        .set_logger(logger)\
                        .set_tag("GENERATION")\
                        .add_message(
                            f"You are an autonomous agent and javascript / npm / node expert."
                            f"\nThe user is a program that can only interact with you in predetermined ways."
                            f"\nThe user will give you a task and instructions on how to complete the task."
                            f"\nYou should try to achieve the task by following the instructions of the user.",
                            role="developer"
                        )\
                        .add_message(
                            f"I want to know how to correctly import and use the npm package {quoted_package_name}."
                            f"\nYour task is"
                            +
                            Message.create_list(
                                f"Create an index.js file which correctly imports and uses {quoted_package_name}",
                                f"Create a package.json file such that node index.js executes successfully",
                                f"Include examples for all relevant use cases, including edge cases",
                                f"Do not write tests or use any kind of test framework or test package, only create proper use case examples",
                                f"Do not write any examples that use the package incorrectly",
                                f"Mmake sure that no errors occur in your examples and imports",
                                scope=True
                            )
                        )

                    add_package_info(generation_agent)

                    sequence = generation_agent.add_message(
                            f"You should complete the task in the following way"
                            +
                            Message.describe_sequence(
                                f"think",
                                f"Explain what {quoted_package_name} does and how it should be used, then explain how you want to complete the task successfully.",
                                f"index.js",
                                f"Write the content of the index.js file.",
                                f"package.json",
                                f"Write the content of the package.json file.",
                                f"stop",
                                scope=True
                            )
                        )\
                        .get_completion("stop")

                    _, indexjs, packagejson = map(extract_code, Message.extract_sequence(sequence, ["think", "index.js", "package.json"]))

                    print(f"\nInstalling example")
                    package_json_sub_path = package_json_path / mode
                    if not reproduce:
                        create_file(package_json_sub_path / "package.json", content=packagejson)
                        output = shell(f"npm install tsx typescript @types/node {package_name}", cwd=template_sub_path, check=False)
                    else:
                        # In reproduction mode the generated package.json is replaced by the previously generated one, which might result in failure
                        if not package_json_sub_path.is_dir():
                            raise Fail("No package_json directory found for reproduction mode")
                        create_file(template_sub_path / "package.json", package_json_sub_path / "package.json")
                        create_file(template_sub_path / "package-lock.json", package_json_sub_path / "package-lock.json")
                        output = shell(f"npm ci", cwd=template_sub_path, check=False)

                    if output.code:
                        raise Fail(f"Installation failed with code: {output.code}")

                    create_dir(package_json_sub_path, overwrite=True)
                    create_file(package_json_sub_path / "package.json", template_sub_path / "package.json")
                    create_file(package_json_sub_path / "package-lock.json", template_sub_path / "package-lock.json")
                    
                    print(f"\nRunnning example")
                    playground_sub_path = playground_path / mode
                    create_dir(playground_sub_path, template_sub_path, overwrite=True)
                    create_file(playground_sub_path / "index.js", content=indexjs)
                    output = shell(f"node index.js", cwd=playground_sub_path, check=False, timeout=execution_timeout)
                    if output.code:
                        print(f"Node failed with return code: {output.code}")
                    else:
                        create_file(examples_sub_path / f"example_0.js", content=indexjs)
            
        except Fail as e:
            print(f"Readme extraction failed: {e}")
            pass

    ### ADVANCED LLM GENERATION ###

    # TODO:
    # - Finish high quality generation, i.e. coverage agent
    # - Coverage agent still needs a way to access files for line / branch coverage, either autonomous or like how Rojus did

    if advanced_llm_generation:
        mode = "simple_llm_generation"
        try:
            examples_sub_path = examples_path / mode
            create_dir(examples_sub_path, overwrite=True)
            
            template_sub_path = template_path / mode
            create_dir(template_sub_path, overwrite=True)

            if not (readme or main or tests):
                raise Fail("No README, nor main, nor test files found in the repository")

            log_sub_path = log_path / mode
            create_dir(log_sub_path, overwrite=True)
            with open(log_sub_path / "log.txt", "w") as file:
                with PrettyLogger(sys.stdout, file) as logger:

                    ### EVALUATION AGENT ###

                    logger.set_max_lines(MAX_LINES)
                    evaluation_agent = prompter.get_copy()\
                        .set_logger(logger)\
                        .set_tag("EVALUATION")\
                        .add_message(
                            f"You are an autonomous agent and javascript / npm / node expert."
                            f"\nThe user is a program that can only interact with you in predetermined ways."
                            f"\nThe user will give you a task and options that you can use to complete the task."
                            f"\nYou should try to achieve the task by choosing the right options.",
                            role="developer"
                        )\
                        .add_message(
                            f"Some npm packages can not be executed directly via Node because e.g. they are browser-exclusive or framework-dependent."
                            f"\nYour task is to determine if the npm package {quoted_package_name} can be executed via Node."
                        )
                        
                    add_package_info(evaluation_agent)

                    think_option = Option(
                        f"think",
                        f"If you want to think about the current situation and how to continue",
                        f"Write your thoughts"
                    )
                    executable_option = Option(
                        f"node executable",
                        f"If the package is executable via Node",
                        f"Explain how you determined that this is the case"
                    )
                    not_executable_option = Option(
                        f"not node executable",
                        f"If the package is not executable via Node",
                        f"Explain how you determined that this is the case"

                    )
                    while True:
                        match evaluation_agent.get_choice(
                                think_option,
                                executable_option,
                                not_executable_option
                            ):
                            case think_option.name, _:
                                continue
                            case executable_option.name, _:
                                break
                            case not_executable_option.name, _:
                                raise Fail("The evaluation agent determiend that the package is not executable via Node")
                    
                    ### GENERATION AGENT ###
                    
                    generation_agent = prompter.get_copy()\
                        .set_logger(logger)\
                        .set_tag("GENERATION")\
                        .add_message(
                            f"You are an autonomous agent and javascript / npm / node expert."
                            f"\nThe user is a program that can only interact with you in predetermined ways."
                            f"\nThe user will give you a task and instructions on how to complete the task."
                            f"\nYou should try to achieve the task by following the instructions of the user.",
                            role="developer"
                        )\
                        .add_message(
                            f"I want to know how to correctly import and use the npm package {quoted_package_name}."
                            f"\nYour task is"
                            +
                            Message.create_list(
                                f"Create an index.js file which correctly imports and uses {quoted_package_name}",
                                f"Create a package.json file such that node index.js executes successfully",
                                f"Include examples for all relevant use cases, including edge cases",
                                f"Do not write tests or use any kind of test framework or test package, only create proper use case examples",
                                f"Do not write any examples that use the package incorrectly",
                                scope=True
                            )
                        )

                    add_package_info(generation_agent)

                    sequence = generation_agent.add_message(
                            f"You should complete the task in the following way"
                            +
                            Message.describe_sequence(
                                f"think",
                                f"Explain what {quoted_package_name} does and how it should be used, then explain how you want to complete the task successfully.",
                                f"index.js",
                                f"Write the content of the index.js file.",
                                f"package.json",
                                f"Write the content of the package.json file.",
                                f"stop",
                                scope=True
                            )
                        )\
                        .get_completion("stop")

                    example_index = 0
                    while True:
                        _, indexjs, packagejson = map(extract_code, Message.extract_sequence(sequence, ["think", "index.js", "package.json"]))

                        print(f"\nInstalling example")
                        package_json_sub_path = package_json_path / mode
                        if not reproduce:
                            create_file(package_json_sub_path / "package.json", content=packagejson)
                            output = shell(f"npm install tsx typescript @types/node nyc {package_name}", cwd=template_sub_path, check=False)
                        else:
                            # In reproduction mode the generated package.json is replaced by the previously generated one, which might result in failure
                            if not package_json_sub_path.is_dir():
                                raise Fail("No package_json directory found for reproduction mode")
                            create_file(template_sub_path / "package.json", package_json_sub_path / "package.json")
                            create_file(template_sub_path / "package-lock.json", package_json_sub_path / "package-lock.json")
                            output = shell(f"npm ci", cwd=template_sub_path, check=False)

                        if output.code:
                            generation_agent.add_message(
                                    f"Running npm install with your package.json returned an error:"
                                    f"\n{delimit_code(output.value, "shell")}"
                                    f"\nError code: {output.code}"
                                )
                            sequence = generation_agent.add_message(
                                    f"Do the following"
                                    +
                                    Message.describe_sequence(
                                        f"think",
                                        f"Explain what went wrong, then explain how this problem can be fixed to complete the task successfully.",
                                        f"index.js",
                                        f"Write the updated content of the index.js file.",
                                        f"package.json",
                                        f"Write the updated content of the package.json file.",
                                        f"stop",
                                        scope=True
                                    )
                                )\
                                .get_completion("stop")
                            continue
                        
                        create_dir(package_json_sub_path, overwrite=True)
                        create_file(package_json_sub_path / "package.json", template_sub_path / "package.json")
                        create_file(package_json_sub_path / "package-lock.json", template_sub_path / "package-lock.json")

                        print("\nRunnning example")                        
                        playground_sub_path = playground_path / mode
                        create_dir(playground_sub_path, template_sub_path, overwrite=True)
                        create_file(playground_sub_path / "index.js", content=indexjs)
                        output = shell(f"node index.js", cwd=playground_sub_path, check=False, timeout=execution_timeout)
                        if output.code:
                            print(f"Node failed with return code: {output.code}")
                            generation_agent.add_message(
                                    f"Running index.js with Node produced an error:"
                                    f"\n{delimit_code(output.value, "shell")}"
                                    f"\nError code: {output.code}"
                                )
                            sequence = generation_agent.add_message(
                                    f"Do the following"
                                    +
                                    Message.describe_sequence(
                                        f"think",
                                        f"Explain what went wrong, then explain how this problem can be fixed to complete the task successfully.",
                                        f"index.js",
                                        f"Write the updated content of the index.js file.",
                                        f"package.json",
                                        f"Write the updated content of the package.json file.",
                                        f"stop",
                                        scope=True
                                    )
                                )\
                                .get_completion("stop")                            
                            continue
                        else:
                            create_file(examples_sub_path / f"example_{example_index}.js", content=indexjs)
                            example_index += 1
                        break

                    ### COVERAGE AGENT ###

                    # COVERAGE REPORT NEEDS TO BE AGGREGATED FOR EVERY NEW INDEX.js FILE

                    coverage_agent = prompter.get_copy()\
                        .set_logger(logger)\
                        .set_tag("COVERAGE")\
                        .add_message(
                            f"You are an autonomous agent and javascript / npm / node expert."
                            f"\nThe user is a program that can only interact with you in predetermined ways."
                            f"\nThe user will give you a task and options that you can use to complete the task."
                            f"\nYou should try to achieve the task by choosing the right options.",
                            role="developer"
                        )\
                        .add_message(
                            f"\nYour task is"
                            +
                            Message.create_list(
                                f"Create an index.js file which correctly imports and uses the npm package {quoted_package_name}",
                                f"The index.js file should increase the line and branch coverage of the package if possible"
                                f"Do not write tests or use any kind of test framework or test package, only create proper use case examples",
                                f"Do not write any examples that use the package incorrectly",
                                scope=True
                            )
                        )

                    add_package_info(generation_agent)
                    
                    logger.set_max_lines(MAX_LINES)
                    coverage_agent.add_message(
                            f"I already created an example that imports and uses the package."
                            f"\nHere is the index.js file of that example:"
                            f"\n{delimit_code(indexjs, "javascript")}"
                        )\
                        .add_message(
                            f"\nHere is the package.json file of that example:"
                            f"\n{delimit_code(packagejson, "json")}"
                            f"\nYour index.js file should work with this package.json"
                        )
                    logger.set_max_lines()
                    
                    example_option = Option(
                        f"indexjs",
                        f"If you want to provide an index.js file that increases the line or branch coverage of {quoted_package_name}",
                        f"Write the file",
                        f"The example will be executed and a new coverage report will be given to you"
                    )
                    inspect_option = Option(
                        f"inspect",
                        f"If you want to inspect files or directories inside of node_modules/{package_name} to determine how to cover the uncovered lines and branches",
                        f"For each file or directory that you want to inspect"
                        +
                        Message.describe_sequence(
                            f"path",
                            f"Write the path of the file or directory relative to node_modules/{package_name}/",
                            scope=True
                        ),
                        f"The contents of the files and or directories will be returned to you."
                    )
                    finish_option = Option(
                        f"finish",
                        f"If no further line or branch coverage can be achieved with additional examples"
                    )
                    output = shell(f"npx nyc --no-exclude-node-modules --include=node_modules/{package_name}/** node index.js", cwd=playground_sub_path, check=False, timeout=execution_timeout)
                    coverage_agent.add_message(
                            f"Here is the coverage that is currently achieved:"
                            f"\n{delimit_code(output.value, "shell")}"
                            f"\nAll files mentioned are from ./node_modules/{package_name}/"
                        )
                    while True:
                        match coverage_agent.get_choice(
                                think_option,
                                example_option,
                                inspect_option,
                                finish_option
                            ):
                            case think_option.name, _:
                                continue
                            
                            case example_option.name, indexjs:
                                print("\nRunnning example")
                                indexjs = extract_code(indexjs)
                                create_dir(playground_sub_path, template_sub_path, overwrite=True)
                                create_file(playground_sub_path / "index.js", content=indexjs)
                                output = shell(f"node index.js", cwd=playground_sub_path, check=False, timeout=execution_timeout)
                                if output.code:
                                    print(f"Node failed with return code: {output.code}")
                                    generation_agent.add_message(
                                            f"Running index.js with Node produced an error:"
                                            f"\n{delimit_code(output.value, "shell")}"
                                            f"\nError code: {output.code}"
                                        )
                                else:
                                    create_file(examples_sub_path / f"example_{example_index}.js", content=indexjs)
                                    example_index += 1
                                    output = shell(f"npx nyc --no-exclude-node-modules --include=node_modules/{package_name}/** node index.js", cwd=playground_sub_path, check=False, timeout=execution_timeout)
                                    coverage_agent.add_message(
                                            f"Here is the coverage that is currently achieved:"
                                            f"\n{delimit_code(output.value, "shell")}"
                                            f"\nAll files mentioned are from ./node_modules/{package_name}/"
                                        )
                                continue
                            
                            case inspect_option.name, sequence:
                                paths = Message.extract_repeating_sequence(sequence, ["path"])
                                message = []
                                for path in paths:
                                    path = extract_code(path[0])
                                    abs_path = playground_sub_path / "node_modules" / package_name / path
                                    if abs_path.is_file():
                                        obj_type = "file"
                                        content = abs_path.read_text()
                                        content = f"\n{delimit_code(content)}"
                                    elif abs_path.is_dir():
                                        obj_type = "dir"
                                        content = shell(f"ls", cwd=abs_path, check=False).value
                                        content = f"\n{delimit_code(content, "shell")}"
                                    else:
                                        obj_type = "undefined"
                                        content = f" Path does not exists relative to node_modules/{package_name}/"
                                    message.append(f"{path} ({obj_type}):{content}")
                                coverage_agent.add_message(
                                        f"Here are the contents of the files or directories that you requested for inspection:\n\n"
                                        +
                                        "\n\n".join(message)
                                    )
                                continue

                            case finish_option.name, _:
                                break
            
        except Fail as e:
            print(f"Readme extraction failed: {e}")
            pass

# nyc report generation commands:
# npx nyc --no-exclude-node-modules --include=node_modules/abs/** node index.js
# npx nyc --no-exclude-node-modules --include=node_modules/abs/** report --reporter=json