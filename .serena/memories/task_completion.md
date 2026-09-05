# Task completion

- Run `uv sync --extra dev` when the environment is not prepared, then `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest -q`.
- For public API, CLI, profile/configuration, or protocol changes, add or update focused respx-backed tests and validate the relevant example or CLI parsing path without real credentials.
- Never include real tenant URLs, account identifiers, tokens, passwords, raw captures, or customer message content in commits or test fixtures.
- For Serena knowledge maintenance, run `serena memories check` from the project root after changing tracked memories.