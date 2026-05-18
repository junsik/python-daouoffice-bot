# Changelog

All notable changes to this project are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] — Unreleased

First open-source release. Reverse-engineered from the DaouOffice PC messenger REST API; no official bot API exists.

### Added
- `BotClient` — REST client: login, identity resolution via GraphQL `me`, rooms, messages, read receipts. Multi-tenant (`base_url` / `company_id` from args or `DAOU_*` env). No tenant value is hard-coded.
- `BotClient.discover_company()` — resolve `companyId` from a tenant URL.
- Automatic re-login on HTTP 401 (`ROUTE-0004`): the AccessToken lives ~30 min and the captured traffic shows no refresh endpoint, so long-running bots recover by re-authenticating.
- `BotEngine` — async polling engine with per-room last-seen tracking; the startup backlog is not replayed and messages are not handled twice.
- Persistent cursors (`FileCursorStore`, default for `DaouBot`): `.daoubot/cursors.json` records how far each room was processed so a restart resumes instead of replaying or skipping. `MemoryCursorStore` opts out. Catch-up is bounded by the ~20-message REST history window.
- Fixed **at-least-once** delivery (the industry standard; not a knob): ordered per-room retry until the handler succeeds, poison guard via `max_attempts`, read receipts only up to the last acked message. The engine owns the cursor/ack; handlers stay pure (make them idempotent; swallow errors for fire-and-forget).
- Mention parsing: inline `{{uuid::USER::@name::id}}` / `{{uuid::ALL::@ALL}}` tokens are parsed into `NewMessage.mentions` / `mentions_me` / `mention_all`, with a human-readable `message_text` and original `raw_text`. New `only_when_mentioned(handler)` filter gates noisy group rooms (no global knob — policy stays declarative). Encoding documented in `docs/03-messages.md` §3.6.
- `load_settings()` + `DaouBot.from_env()` / `BotClient.from_env()`: single resolver (arg > `DAOU_*` env > profile; password never from profile) — a terse shortcut for production/CLI. Examples instead construct `DaouBot` explicitly reading the four `DAOU_*` vars, so required inputs stay visible (no hard-coded secrets, no hidden config).
- The message-handler argument is `on_message` (was `prompt_func`, which wrongly implied an LLM-prompt coupling); `set_handler()` (was `set_prompt_func`); type `MessageHandler`.
- Graceful shutdown: `run_forever()` installs SIGINT/SIGTERM handlers and logs out cleanly (matters under systemd, which stops with SIGTERM); falls back to plain cancellation where signals are unavailable.
- Exponential backoff on sustained poll failure (cap 5 min) instead of a flat retry every interval.
- New `examples/bot-command` (the common `!cmd args` dispatcher pattern).
- Claude Code skill `skills/daouoffice-bot/` (SKILL.md + reference.md + scaffold.py) — a distributable consumer skill (install to `~/.claude/skills/` or via `npx skills add`), **not** in `.claude/` which is local dev config for this repo. A **design guide**, not a template menu — the agent elicits requirements, maps them to primitives via a decision matrix, and assembles the bot under the SDK's invariants (no BotFather/webhooks/inline; polling, allowlist, idempotency, env/profile config). `scaffold.py` emits only correct boilerplate (UTF-8 safe on cp949 Windows); the design is the agent's, from the user's actual needs.
- Attachment sending: `BotClient.upload_attachment(path)` + `send_message(..., attachments=[...])`, shortcut `send_file()` / `DaouBot.send_file()` (e.g. post an LLM-generated newsletter .md/.html as a downloadable file). Two-step flow decoded from the SAZ and documented in `docs/03-messages.md` §3.7; contracts are **live-unverified**.
- Architecture documented in `docs/ARCHITECTURE.md` (with diagrams).
- `DaouBot` — high-level bot driven solely by an `on_message` callback.
- `RoomRouter` — allowlist-by-default per-room dispatch (`room_id` > `room_type` > default > ignore).
- `Profile` + `daoubot` CLI: `login` (saves `.daoubot/profile.json`), `discover`, `whoami`, `rooms`, `room create/open`, `send`, `start`.
- Examples: echobot, conversation, assistant (self-contained LLM call), error-handler, router.
- Test suite (pytest + respx, network mocked), ruff lint + format, CI on Python 3.12 / 3.13, `py.typed` for downstream type checking.

### Notes
- Unofficial; depends on a private API and may break on server changes.
- The LLM integration is intentionally **not** part of the SDK — see `examples/bot-assistant`.
- Polling is the only delivery path. A WebSocket/STOMP endpoint was seen in the capture but never validated, so no WS code is shipped — kept as reverse-engineering notes (`docs/04-websocket.md`) for future work.
