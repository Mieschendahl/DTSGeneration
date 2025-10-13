# Setup

To run dts_generation in a Linux shell environment you will need to
- Install python3, node, npm, docker, and git in the shell.
- Install dts_generation via `python3 -m pip install path/to/project`.
- Run dts_generation on an npm package via `python3 -m dts_generation --package-name package_name`.

(need sudo docker!)

If you want to run `--llm-evaluation`, `--llm-generation` or `--llm-coverage` you also need to
- Get a valid API key from OpenAI.
- Set the key to the `OPENAI_API_KEY` environment variable.