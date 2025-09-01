# DTS Generation

This project lets you automatically generate typescript delcaration files (d.ts files) for a given npm package, from nothing more than the name of the package.

## Methodology

dts_generation can be divided into three stages:
- first it looks at the official GitHub repository of the given npm package and extracts ues case examples from its README file and or generates examples using an LLM
- The generated examples are then passed to [dts-generate](https://arxiv.org/abs/2108.08027) to automatically generate d.ts files.
- Finally, the generated d.ts files are compared to [DefinitelyTyped's](https://github.com/DefinitelyTyped/DefinitelyTyped) d.ts files via TypeScript's type assignability API.

There are two types of LLM generation modes:
- A simple mode, which runs via a single completion request:
    - The LLM generates use case examples for the npm package based on the README, main, and test files of the package.
- An advanced mode, which is divided into multiple stages:
    - An evaluation stage, where the LLM determines if the npm package supports node execution.
    - A generation stage, where a simple example is generated based on the README, main, and test files of the package, to ensure that the LLM knows how to correctly import and use the npm package.
    - And finally, a coverage stage, where the LLM tries to increase the line and branch coverage of the npm packages source code via new examples, such that dts-generate can generate more accurate d.ts files.

## Additional Ressources

- `SETUP.md` describes how to setup and run dts_generation.
- `REPRODUCE.md` describes how to run dts_generation in a reproducable way