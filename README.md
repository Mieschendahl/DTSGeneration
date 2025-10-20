# DTSGeneration

DTSGeneration is a Python library that can automatically generate TypeScript type declaration (TSD) files for a given JavaScript npm package.

It uses examples from the package's GitHub repository to analyze the runtime behavior of the package and infer Types for its interface.

Using a large language model (LLM), we can generate further examples for more complete interface coverage.

This project depends on [EasyPrompting](https://github.com/Mieschendahl/EasyPrompting) for generating additional examples using an LLM and [run-time-information-gathering](https://github.com/Proglang-TypeScript/run-time-information-gathering) and [ts-declaration-file-generator](https://github.com/Proglang-TypeScript/ts-declaration-file-generator) for generating the TypeScript declarations.

## Demo

To generate TSD files for an npm package, all you have to do is call the generate function on the package:
```python
from pathlib import Path
from dts_generation import generate

generate(package_name, Path("output/generation"), Path("output/builds"))  # generates declarations in output/generation/declarations
```

`dts_generation/__main__.py` shows how to properly use this package.

## Setup

`SETUP.md` contains all the setup instructions.

## Reproduction

`REPRODUCTION.md` contains all the information to make evaluations as reproducible as possible.

## Manual

The main function that `dts_generation` exposes is the `generate` function. As the name implies, it is responsible for coordinating the generation of example, declaration, and comparison files. To do this, it uses corresponding helper functions `generate_examples`, `generate_declarations`, and `generate_comparisons`.

### Generate Examples

`generate_examples` clones the GitHub repository of the npm package and produces examples in two ways:
- Either by extracting code blocks from the README file
- Or by generating examples via an LLM that analyzes the repository data

In both cases we check if the examples run with Node.js and the CommonJS module system, before saving them. Additionally, for the LLM approach, we also let the LLM determine if the package is actually designed to be used in Node as a stand-alone package, to avoid cases where no valid examples can be generated.

Furthermore, we combine the generated examples into a single file, such that we can later get a single TSD with hopefully higher interface coverage.

### Generate Declarations

`generate_declarations` takes the generated examples and runs [run-time-information-gathering](https://github.com/Proglang-TypeScript/run-time-information-gathering) and [ts-declaration-file-generator](https://github.com/Proglang-TypeScript/ts-declaration-file-generator) on them to produce a TSD for each example.

[run-time-information-gathering](https://github.com/Proglang-TypeScript/run-time-information-gathering) is designed for JavaScript ES5 and expects ES5 syntax from the examples, which means that we first have to down transpile them from ES6+ to ES5 via the babel npm package.

Some ES6+ features are semantically not compatible with ES5, and thus can not be handled via a simple transpilation of the example/package. This is currently a bottleneck that makes many npm packages unsuitable for TSD generation.

### Genreate Comparisons

`generate_comparisons` takes the generated TSDs and compares them with ground truth TSD pulled from the [DefinitelyTyped](https://github.com/DefinitelyTyped/DefinitelyTyped) repository.

We use TypeScript's own typechecker (specifically its isTypeAssignableTo API) to compare the TSDs. We are mainly interested in two conditions:
- Whether the generated TSD is sound, i.e. if every exported type in the generated TSD module is supertype of an exported type in the ground truth TSD module. Which implies that we can safely replace the generated TSD with the ground truth TSD.
- And whether the generated TSD is complete, i.e. if every exported type in the ground truth TSD module is supertype of an exported type in the generated TSD module. Which implies that we can safely replace the ground truth TSD with the generated TSD.

When both conditions hold, we have equivalence of the TSDs, which is the optimal outcome. Although usually, we have higher soundness than completeness, because the examples tend to not fully cover all use/edge cases of the package.

### Evaluation

`evaluate` runs `generate` on a random subsample of npm packages that can be found in the [DefinitelyTyped](https://github.com/DefinitelyTyped/DefinitelyTyped) repository, and keeps track of the comparison results of the generated declarations and other useful metrics to put the results into perspective.

We also compute the comparison metrics relative to:
- The number of packages for which example generation is currently supported (i.e. meant for Node.js + CommonJS, and only requires `npm install <package name>`).
- And the baseline of generating examples purely via code block extraction from the README file.