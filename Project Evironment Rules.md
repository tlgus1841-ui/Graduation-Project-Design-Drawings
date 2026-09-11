# Project Environment Rules
- Python package manager: Use `uv` strictly.
- Never use `pip install` or `python -m venv`.
- To add packages, run: `uv add <package>`
- To run scripts, tests, or servers, run: `uv run <command>`
- Virtual environment is located at `./.venv`.