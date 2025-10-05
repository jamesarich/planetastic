# Agent Instructions for Planetastic

Welcome, agent! This file contains instructions to help you work with the `planetastic` codebase.

## Development Environment

This project uses a set of development tools to ensure code quality and consistency. Before making any changes, please set up the development environment.

1.  **Install all dependencies:**
    This project separates runtime dependencies from development dependencies.
    - `requirements.txt`: For running the application.
    - `requirements-dev.txt`: For development, linting, and formatting.

    Install both sets of dependencies using pip:
    ```bash
    pip install -r requirements.txt -r requirements-dev.txt
    ```

2.  **Set up pre-commit hooks:**
    This project uses `pre-commit` to automatically format and lint code before each commit. This is crucial for maintaining a clean and consistent codebase.

    Install the hooks:
    ```bash
    pre-commit install
    ```
    After this, the hooks will run automatically on every `git commit`.

## Making Changes

1.  **Code Formatting and Linting:**
    All Python code in this repository is formatted with `black` and linted with `ruff`. The pre-commit hooks handle this automatically.

2.  **Running Checks Manually:**
    If you want to run the checks on all files at any time, use this command:
    ```bash
    pre-commit run --all-files
    ```
    Please ensure all checks pass before submitting your work.

By following these instructions, you help keep the `planetastic` codebase healthy and maintainable. Thank you!