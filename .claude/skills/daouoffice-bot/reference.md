# Reference — python-daouoffice-bot

Condensed, self-contained API + gotchas for building bots. (Repo docs:
`docs/ARCHITECTURE.md`, `docs/0*.md`, `examples/`.)

## Public API (`from daouoffice import ...`)

| Symbol | Purpose |
|---|---|
| `DaouBot` | High-level bot. `DaouBot.from_env(prompt_func=...)` resolves connection from env/profile. `run_forever()` = login + poll + graceful SIGINT/SIGTERM. |
| `BotClient` | REST wrapper: `login()`, `whoami()`, `discover_company()`, `get_rooms()`, `create_room()`, `open_room()`, `send_message()`, `get_chat_history()`, `mark_read()`. `from_env()` / `from_token()`. |
| `BotEngine` | Polling engine (used internally by `DaouBot`). |
| `NewMessage` | Inbound message (see fields below). |
| `RoomRouter` | Per-room handler dispatch; **allowlist** — unregistered rooms ignored. `add_room(id, fn)`, `add_room_type("SINGLE"/"GROUP", fn)`, `set_default(fn)`, decorators `@router.room(id)` / `@router.room_type(t)` / `@router.default`. Pass the router as `prompt_func`. |
| `only_when_mentioned(fn, *, include_all=True)` | Wrap a handler so it runs only when `mentions_me` (or `@ALL`). Composable with `prompt_func` or a router handler. |
| `load_settings(...)` / `Settings` | Resolve base_url/company_id/login_id/password: arg > `DAOU_*` env > profile. Password never from profile. |
| `Profile` / `load_profile` / `save_profile` | `.daoubot/profile.json` model. |
| `FileCursorStore` / `MemoryCursorStore` / `CursorStore` | Where "processed up to" is persisted. `DaouBot` defaults to `FileCursorStore` (restart-resume). |
| `BotIdentity` | Resolved bot identity (user_id, company_*). |
| `DaouAuthError` / `DaouConfigError` | Exceptions. |

`NewMessage` fields: `room_id`, `room_type` (`SINGLE`|`GROUP`),
`sender_user_id`, `sender_name`, `message_text` (human-readable),
`message_id`, `created_at`, `raw_text` (original incl. `{{...}}`),
`mentions: list[str]`, `mentions_me: bool`, `mention_all: bool`.

`prompt_func`: `Callable[[NewMessage], str | None | Awaitable[...]]`. Return a
string to reply, `None` for no reply. Sync or async.

## CLI (`daoubot`)

`discover --base-url URL` · `login` · `whoami` · `rooms` ·
`room create --users a,b [--name N] [--type GROUP]` · `room open <id>` ·
`send <room_id> "<text>"` · `start`. Precedence: flag > env > profile.

## Gotchas (encode these in any bot you build)

1. **Dedicated account.** Read state is account-global; the bot's `mark_read`
   clears a human's unread. Never share the account with a person.
2. **At-least-once + idempotency.** A message is re-delivered until the handler
   returns without raising; restart/crash can re-deliver. Make side effects
   idempotent. Repeated failures past `max_attempts` (default 5) are skipped
   as "poison". Fire-and-forget = swallow errors in the handler.
3. **Allowlist for groups.** Without `RoomRouter`/`only_when_mentioned` the bot
   replies to every message in every room it is invited to (spam/footgun).
4. **Mentions are inline text tokens** (`{{uuid::USER::@name::id}}` /
   `{{uuid::ALL::@ALL}}`), broadcast to the whole room (not private). Already
   parsed into `mentions*`; don't regex `message_text` yourself.
5. **Token ~30 min, auto re-login.** No refresh endpoint exists; the client
   re-logs in on 401 using the credentials (so `DaouBot` needs them, not just
   a token).
6. **Restart-resume is bounded** by the ~20-message history window — long
   downtime loses out-of-window messages (no "since id" API).
7. **Not supported by DaouOffice:** webhooks, inline keyboards/buttons, inline
   queries, slash-command framework, BotFather, WebSocket (endpoint observed
   but unimplemented). Do not fabricate these.
8. **Don't run two bot processes on one account** — duplicate handling +
   `mark_read` races. Scale with `RoomRouter` in one process.

## Minimal working bot

```python
import asyncio
from daouoffice import DaouBot, NewMessage

async def handle(msg: NewMessage) -> str | None:
    return f"echo: {msg.message_text}"

asyncio.run(DaouBot.from_env(prompt_func=handle).run_forever())
```

Requires env: `DAOU_BASE_URL`, `DAOU_COMPANY_ID`, `DAOU_LOGIN_ID`,
`DAOU_PASSWORD` (or a prior `daoubot login`).
