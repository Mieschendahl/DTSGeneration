# Setup

To run dts_generation in a Linux shell environment you will need to
- Install python3, node, npm, docker, and git in the shell.
- Install the project via `python3 -m pip install path/to/project`.
- Run the project via `python3 -m dts_generation ...`
- You can access the manual via `python3 -m dts_generation -h`.

If you want to run `--simple-llm-generation` or `--advancec-llm-generation` you also need to
- Get a valid API key from OpenAI.
- Set the key to the `OPENAI_API_KEY` environment variable.