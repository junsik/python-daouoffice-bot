# Contributing

Thanks for your interest in improving `python-daouoffice-bot`.

## Development setup

```bash
git clone https://github.com/junsik/python-daouoffice-bot
cd python-daouoffice-bot
uv sync --extra dev
```

## Before opening a PR

```bash
uv run ruff check .     # lint
uv run pytest -q        # tests
```

Both must pass; CI runs them on Python 3.12 and 3.13.

## Guidelines

- **Never commit secrets.** No real credentials, tokens, company ids,
  internal hostnames, or `.saz` captures. Use placeholders. The repo is
  multi-tenant by design — nothing should be hard-coded to one company.
- Keep the public API (`daouoffice.__all__`) stable; discuss breaking
  changes in an issue first.
- Add or update tests for behavior changes. Network is mocked with `respx`;
  tests must not hit a live server.
- This project reverse-engineers an undocumented API. If you map a new
  endpoint, document it under `docs/` with anonymized samples.

## Reporting security issues

Please open a private report rather than a public issue if a change could
expose credentials or tenant data.
