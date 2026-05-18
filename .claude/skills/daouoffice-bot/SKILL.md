---
name: daouoffice-bot
description: >-
  Build a DaouOffice (다우오피스) messenger bot with the python-daouoffice-bot
  SDK. Use when the user wants to create, scaffold, or extend a DaouOffice
  chatbot / assistant / notifier / command bot, asks about DaouOffice
  messenger automation, `DaouBot`, `daoubot` CLI, or "다우오피스 봇". NOT for
  Telegram/Slack/Discord bots.
license: MIT
---

# DaouOffice Bot Builder

Scaffold and extend bots on `python-daouoffice-bot` — an unofficial,
reverse-engineered SDK for the DaouOffice messenger REST API.

## Mental model (read first — it differs from Telegram/Slack)

- **No BotFather, no tokens.** A "bot" is a normal DaouOffice **account** an
  admin issues for automation. You log in with its id/password.
- **Use a dedicated account.** Read state is account-global: the bot's
  `mark_read` clears a human's unread too. Never share the account.
- **Polling only.** No webhooks, no inline keyboards, no slash-command
  framework (commands are a `!`-prefix text convention). Don't invent these.
- **Multi-tenant.** Every install needs `base_url` + `company_id`; nothing is
  hard-coded. These come from env / `.daoubot/profile.json`.
- **The handler is a pure function** `prompt_func(NewMessage) -> str | None`.
  The SDK owns transport, cursor/ack, at-least-once delivery, 401 re-login,
  mention parsing. The user writes only the handler.

## Workflow

Follow these steps in order. Do not skip onboarding.

### 1. Install the SDK

```bash
uv add python-daouoffice-bot      # or: pip install -e <path-to-checkout>
```

### 2. Onboarding — discover IDs and log in (no BotFather equivalent)

The user must supply: tenant URL + the bot account's id/password.

```bash
# Find companyId from the bare tenant URL (no auth):
daoubot discover --base-url https://<company>.daouoffice.com

# Log in once → saves .daoubot/profile.json (company + identity + token;
# password is NOT stored). company_id auto-discovered if omitted.
daoubot login --base-url https://<company>.daouoffice.com \
  --login-id <bot-account> --password '<pw>'

daoubot rooms        # list rooms + room ids the bot can act in
```

Set connection config as env vars (preferred) so code stays clean:
`DAOU_BASE_URL`, `DAOU_COMPANY_ID`, `DAOU_LOGIN_ID`, `DAOU_PASSWORD`.

### 3. Scaffold the bot

Run the bundled generator, then edit the handler:

```bash
python .claude/skills/daouoffice-bot/scaffold.py <kind> > bot.py
# kind: echo | command | assistant | router
```

Or write it directly using the pattern below. Always build via
`DaouBot.from_env(...)` so connection settings resolve from env/profile.

```python
import asyncio
from daouoffice import DaouBot, NewMessage

async def handle(msg: NewMessage) -> str | None:
    if msg.message_text.startswith("!ping"):
        return "pong"
    return None  # None = no reply

async def main() -> None:
    bot = DaouBot.from_env(prompt_func=handle)
    await bot.run_forever()   # graceful SIGINT/SIGTERM shutdown

asyncio.run(main())
```

### 4. Pick the right pattern

| Need | Use |
|---|---|
| Reply to everything | bare `prompt_func` |
| `!cmd args` commands | dispatch on `msg.message_text` prefix (see `command` scaffold) |
| Different behavior per room | `RoomRouter` (allowlist — unregistered rooms ignored) |
| Only react when @-mentioned (busy groups) | wrap with `only_when_mentioned(handler)` |
| LLM answers | call any API **inside** the handler (SDK bundles no LLM) |
| Per-room state | dict keyed by `msg.room_id` |

### 5. Run and verify

```bash
python bot.py        # then send a message in a registered room
```

Smoke-test live access first with `daoubot send <room_id> "test"` before
trusting a long-running bot — the SDK's contracts are tested but live E2E
depends on the tenant.

## Rules the agent MUST follow

- **Never hard-code** `base_url`/`company_id`/credentials or a room id in
  example/bot code. Use `DaouBot.from_env()` and env vars; read room ids from
  env too. No real passwords/tokens in anything you write or commit.
- **Make handlers idempotent.** Delivery is at-least-once; a crash/restart can
  re-deliver a message → a non-idempotent side effect double-fires.
- For any group bot, default to `RoomRouter` and/or `only_when_mentioned` so
  the bot does not reply to every message in every room it is added to.
- The handler must return quickly or be `async`; blocking it stalls polling.
- Mentions arrive parsed: use `msg.mentions_me` / `msg.mention_all` /
  `msg.mentions`; `msg.message_text` is already human-readable, `msg.raw_text`
  has the original `{{...}}` tokens.
- If something needs webhooks / inline buttons / BotFather, tell the user
  DaouOffice does not support it — do not fabricate an API.

See `reference.md` (bundled) for the full API surface, gotchas, and the
mention/auth/delivery details. The SDK repo also has `docs/ARCHITECTURE.md`
and runnable `examples/`.
