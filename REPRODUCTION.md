# Reproduction

Several things affect the reproducability of evaluation runs:
1. The versions of the required shell programs
2. The random seed which determines the package evaluation sample
3. The LLM configuration
4. The DefinitelyTyped version
5. The npm package versions
6. The LLM prompts

The relevant info for points 1 to 4 is saved under `<eval path>/reproduction/info.json`.

The npm package version info can be found under `<eval path>/packages/<package name>/data/package-lock.json`.

The LLM prompts that where used can be found under `<eval path>/packages/<package name>/logs/`.

Note, that the LLM prompts can depend on the file system state, for example Node execution erros can reference file paths. Furthermore, some LLM versions are not stable and can produce different outputs for the same inputs, even with the temperature set to 0.

## Comparison

Evaluation results from previous runs can be found in the repository [DTSGeneration-Evaluation-Results](https://github.com/Mieschendahl/DTSGeneration-Evaluation-Results).