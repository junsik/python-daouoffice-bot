# Suggested commands

- Bootstrap development dependencies: `uv sync --extra dev`.
- Run all tests: `uv run pytest -q`.
- Static lint: `uv run ruff check .`; format verification: `uv run ruff format --check .`.
- Run CLI from source without installation: `uv run python -m daouoffice.cli <subcommand>`.
- User-facing installed entry point is `daoubot`; use its `login`, `rooms`, `room`, `send`, and `config` subcommands rather than reimplementing REST calls.
- On Windows, use PowerShell paths and `Get-Content` for local inspection; do not put credentials in command arguments or repository files.