# Reference — python-daouoffice-bot

Condensed, self-contained API + gotchas for building bots. (Repo docs: `docs/ARCHITECTURE.md`, `docs/api/`, `examples/`.)

## Public API (`from daouoffice import ...`)

| Symbol | Purpose |
|---|---|
| `DaouBot` | High-level bot. `DaouBot(on_message=..., *, markdown=False, app_config=None)` resolves connection in this order: explicit arg > `DAOU_*` env > app config YAML's `daouoffice:` section (read-only, via `app_config=` or `DAOU_APP_CONFIG` env — for embedding the SDK in a downstream app's own config file) > saved profile. `markdown=True` renders each reply's Markdown into the chat-HTML subset before sending (see gotcha 9). `run_forever()` = login + poll + graceful SIGINT/SIGTERM. The daemon recovers itself on 401 — RefreshToken first, then full re-login (see gotcha 5). |
| `BotClient` | REST wrapper: `login()`, `whoami()`, `discover_company()`, `get_rooms()`, `create_room()`, `open_room()`, `send_message(room, content="", *, attachments=[...], reply_to=None)`, `upload_attachment(path)`, `send_file(room, path, content="")`, `get_chat_history()`, `mark_read(message_id, room_id)`. `from_token(..., refresh_token=...)`. |
| `to_chat_html(text)` | Markdown → chat-HTML subset converter (bold, italic, links, ordered/bullet lists, line breaks). Exposed for manual rendering; `DaouBot(markdown=True)` calls it automatically on each handler reply. |
| `BotEngine` | Polling engine (used internally by `DaouBot`). |
| `NewMessage` | Inbound message (see fields below). |
| `RoomRouter` | Per-room handler dispatch; **allowlist** — unregistered rooms ignored. `add_room(id, fn)`, `add_room_type("SINGLE"/"GROUP", fn)`, `set_default(fn)`, decorators `@router.room(id)` / `@router.room_type(t)` / `@router.default`. Pass the router as `on_message`. |
| `only_when_mentioned(fn, *, include_all=True)` | Wrap a handler so it runs only when `mentions_me` (or `@ALL`). Composable with `on_message` or a router handler. |
| `load_settings(...)` / `Settings` | Resolve base_url/company_id/login_id/password: arg > `DAOU_*` env > app config YAML's `daouoffice:` section > profile (password included, so a daemon re-auths unattended). |
| `load_app_config(path)` | Read the operator app config's top-level `daouoffice:` section as a dict. Missing file → empty; malformed/non-mapping → `DaouConfigError`. |
| `Profile` / `load_profile` / `save_profile` | `~/.daoubot/profile.yaml` model (home-anchored, cwd-independent). Legacy `profile.json` is read transparently on first load and rewritten as YAML on the next save. |
| `FileCursorStore` / `MemoryCursorStore` / `CursorStore` | Where "processed up to" is persisted. `DaouBot` defaults to `FileCursorStore` (restart-resume). |
| `BotIdentity` | Resolved bot identity (user_id, company_*). |
| `DaouAuthError` / `DaouConfigError` | Exceptions. |

`NewMessage` fields: `room_id`, `room_type` (`SINGLE`|`GROUP`), `sender_user_id`, `sender_name`, `message_text` (human-readable), `message_id`, `created_at`, `raw_text` (original incl. `{{...}}`), `mentions: list[str]`, `mentions_me: bool`, `mention_all: bool`.

`on_message`: `Callable[[NewMessage], str | None | Awaitable[...]]`. Return a string to reply, `None` for no reply. Sync or async.

## CLI (`daoubot`)

`login` (auto-discovers `company_id` when `--company-id` is omitted) · `whoami` · `config [show|set <key> <value>|path]` (view/edit the saved profile; `key` ∈ base_url/company_id/login_id/password) · `rooms` · `room create --users a,b [--name N] [--type GROUP]` · `room open <id>` · `send <room_id> "<text>"`. (No `start`: the CLI cannot carry a handler — run the bot as `python bot.py` with `DaouBot(on_message=...)`. No standalone `discover`: `login` resolves the company id itself.)

Global flags (on every subcommand):
- `--config <path>` — alternate **profile file** (where the SDK persists its own state — tokens, identity); default `~/.daoubot/profile.yaml`. Use a per-bot/tenant path for multiple accounts on one host.
- `--app-config <path>` (or `DAOU_APP_CONFIG` env) — operator app config YAML whose top-level `daouoffice:` section provides connection values **read-only**. Lets a downstream app keep its SDK connection alongside its own settings in one declarative file (e.g. an `agent.yaml`) without `daoubot login`.

Precedence: flag > env > app config (`daouoffice:` section) > profile. The password is persisted in the profile (chmod 600, gitignored, `****`-masked on stdout) so a daemon re-authenticates unattended; `DAOU_PASSWORD`/an arg still override it.

## Gotchas (encode these in any bot you build)

1. **Dedicated account.** Read state is account-global; the bot's `mark_read` clears a human's unread. Never share the account with a person.
2. **At-least-once + idempotency.** A message is re-delivered until the handler returns without raising; restart/crash can re-deliver. Make side effects idempotent. Repeated failures past `max_attempts` (default 5) are skipped as "poison". Fire-and-forget = swallow errors in the handler.
3. **Allowlist for groups.** Without `RoomRouter`/`only_when_mentioned` the bot replies to every message in every room it is invited to (spam/footgun).
4. **Mentions are inline text tokens** (`{{uuid::USER::@name::id}}` / `{{uuid::ALL::@ALL}}`), broadcast to the whole room (not private). Already parsed into `mentions*`; don't regex `message_text` yourself.
5. **Token recovery on 401.** AccessToken ~30 min, RefreshToken 30 days. On 401 the SDK tries `/refresh/login` first (cheap, no password) and falls back to full password re-login only if refresh fails or no RefreshToken is on hand. So a profile with only a token still recovers — until the 30-day refresh expires; persist the password (it already is) for indefinite unattended runs.
6. **Restart-resume is bounded by the per-room fetch window (~100 newest).** Long downtime (more than ~100 messages piled up in one room) loses the out-of-window tail — there is no "since id" API. This is a structural polling limit, not a knob.
7. **Replies are auto-threaded.** Whatever string a handler returns is posted as a quote-reply to the message that triggered it (`message_id` → `parentChatMessageId`). The engine owns this — handlers do not pass `reply_to`. For free-form (non-threaded) sends, call `bot.client.send_message(...)` directly without `reply_to`.
8. **Not supported by DaouOffice:** webhooks, inline keyboards/buttons, inline queries, slash-command framework, BotFather, WebSocket (endpoint observed but unimplemented). Do not fabricate these.
9. **Markdown subset only.** The chat renders **just** these tags: `<b>`, `<i>`, `<a href>`, `<ol><li>`, `<ul><li>`, `<br>`. With `markdown=True` the SDK converts `**bold**` / `*italic*` / `[t](url)` / `1.` / `-`; everything else (headings, code fences, blockquotes) degrades to escaped literal text rather than emit a tag the client would show raw. For longer documents (full Markdown/HTML), upload as an attachment via `send_file` instead.
10. **Don't run two bot processes on one account** — duplicate handling + `mark_read` races. Scale with `RoomRouter` in one process.
11. **Files are attachments, not inline.** Use `send_file(room, path)` (uploads then posts as a downloadable). Good for an LLM-generated newsletter: write `news.md`/`.html`, then `send_file`. Attachment contracts are SAZ-derived and **live-unverified**.

## Minimal working bot

```python
import asyncio
from daouoffice import DaouBot, NewMessage

async def on_message(msg: NewMessage) -> str | None:
    return f"echo: {msg.message_text}"

async def main() -> None:
    bot = DaouBot(on_message=on_message)   # resolves from `daoubot login` profile
    await bot.run_forever()

asyncio.run(main())
```

`DaouBot()` resolves connection from the `daoubot login` profile (or `DAOU_*`
env / explicit args; arg > env > profile). No credentials belong in the bot
code. `daoubot login` persists the password into the profile, so the daemon
re-authenticates itself indefinitely (refresh covers the first 30 days from
each login; the saved password covers everything beyond).
