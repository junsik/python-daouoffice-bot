# Conventions

- Keep the public API explicit through package exports and typed Pydantic models; use async methods for network I/O.
- `BotClient` owns protocol/API calls, `BotEngine` owns polling/ordering/retry, and `DaouBot` owns composition. Do not mix handler policy into transport.
- A message handler returns a reply string or `None`; room scope and mention policy are opt-in wrappers via `RoomRouter`, `only_when_mentioned`, or `only_when_addressed`.
- Preserve configuration precedence: explicit arguments, environment, application config, then stored profile. SDK code reads application config but does not write it.
- Preserve secret safety: credentials/tokens/profile data are user-local, masked in output, and never committed or logged at normal levels.
- Keep tests deterministic: mock HTTP with respx and avoid live tenant access in unit tests.
- Follow Ruff rules; SDK constructors may use many keyword-only options and assertions may retain literal expected values as configured in `pyproject.toml`.