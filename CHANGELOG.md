# Changelog

All notable changes to this project are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [0.1.0] — Unreleased

First open-source release. Reverse-engineered from the DaouOffice PC messenger
REST API; no official bot API exists.

### Added
- `BotClient` — REST client: login, identity resolution via GraphQL `me`,
  rooms, messages, read receipts. Multi-tenant (`base_url` / `company_id` from
  args or `DAOU_*` env). No tenant value is hard-coded.
- `BotClient.discover_company()` — resolve `companyId` from a tenant URL.
- Automatic re-login on HTTP 401 (`ROUTE-0004`): the AccessToken lives ~30 min
  and the captured traffic shows no refresh endpoint, so long-running bots
  recover by re-authenticating.
- `BotEngine` — async polling engine with per-room last-seen tracking; the
  startup backlog is not replayed and messages are not handled twice.
- Persistent cursors (`FileCursorStore`, default for `DaouBot`):
  `.daoubot/cursors.json` records how far each room was processed so a restart
  resumes instead of replaying or skipping. `MemoryCursorStore` opts out.
  Catch-up is bounded by the ~20-message REST history window.
- Fixed **at-least-once** delivery (the industry standard; not a knob):
  ordered per-room retry until the handler succeeds, poison guard via
  `max_attempts`, read receipts only up to the last acked message. The
  engine owns the cursor/ack; handlers stay pure (make them idempotent;
  swallow errors for fire-and-forget).
- Architecture documented in `docs/ARCHITECTURE.md` (with diagrams).
- `DaouBot` — high-level bot driven solely by a `prompt_func` callback.
- `RoomRouter` — allowlist-by-default per-room dispatch
  (`room_id` > `room_type` > default > ignore).
- `Profile` + `daoubot` CLI: `login` (saves `.daoubot/profile.json`),
  `discover`, `whoami`, `rooms`, `room create/open`, `send`, `start`.
- Examples: echobot, conversation, assistant (self-contained LLM call),
  error-handler, router.
- Test suite (pytest + respx, network mocked), ruff lint + format, CI on
  Python 3.12 / 3.13, `py.typed` for downstream type checking.

### Notes
- Unofficial; depends on a private API and may break on server changes.
- The LLM integration is intentionally **not** part of the SDK — see
  `examples/bot-assistant`.
- Real-time WebSocket/STOMP (`ws_handler.py`) is experimental; polling is the
  supported path.
