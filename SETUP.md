# Setup

To set up this library, run the usual pip command:
```bash
python3 -m pip install <path to this project>
```

If you do not want to clone this project you can also run:
```bash
python3 -m pip install "dts_generation @ git+https://github.com/Mieschendahl/DTSGeneration.git"
```

After that you can import `easy_prompting` and use it in your code.

If you want to execute the demo code run:
```bash
python3 -m easy_prompting -h
```

## OpenAI

To use ChatGPT as the LLM implementation, you will have to get a valid [OpenAI API Key](https://platform.openai.com/api-keys) and set it to the environment variable `OPENAI_API_KEY`.

For example, like this in Linux:
```bash
export OPENAI_API_KEY="<your key>"
```
Vsit OpenAI's [Best Practices](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety) for more information.