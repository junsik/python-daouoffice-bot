# Core

- Python SDK for DaouOffice Messenger's desktop-client REST surface; package root is `src/daouoffice`.
- Public facade: `DaouBot` wires settings, client authentication, polling and reply dispatch. Low-level API access belongs in `BotClient`.
- Runtime stays polling-only. Preserve at-least-once delivery and durable per-room cursors; business handlers must be idempotent.
- Do not add an official-bot/WebSocket abstraction without verified protocol evidence.
- Source map: client and message models in `client.py`; polling and dispatch in `engine.py`; high-level facade in `sdk_bot.py`; settings/profile in `config.py` and `profile.py`; router/mention gates in `router.py`; cursor stores in `state.py`; chat Markdown conversion in `markdown.py`.
- Consumer examples are `examples/`; reverse-engineering reference and API contracts are `docs/`; distributable agent guidance is `skills/daouoffice-bot`.

For toolchain and checks read `mem:tech_stack`, `mem:suggested_commands`, and `mem:task_completion`. For code-shape rules read `mem:conventions`.