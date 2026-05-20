---
name: daouoffice-bot
description: >-
  Design and build a DaouOffice (다우오피스) messenger bot with the
  python-daouoffice-bot SDK. Use when the user wants a DaouOffice chatbot /
  assistant / notifier / command or workflow bot, or asks about DaouOffice
  messenger automation, `DaouBot`, the `daoubot` CLI, or "다우오피스 봇".
  NOT for Telegram/Slack/Discord.
license: MIT
---

# DaouOffice Bot Builder

You are designing a bot **to the user's actual requirements** on `python-daouoffice-bot` (an unofficial, reverse-engineered SDK). This skill is the SDK author's distilled knowledge: do not guess from a template menu — elicit what the user needs, then assemble the right bot from primitives while obeying the invariants below. `references/reference.md` has the full API + gotchas.

## Step 1 — Elicit requirements (ask, don't assume)

Before writing code, get answers (ask only what's unknown):

1. **Tenant + account**: their `https://<co>.daouoffice.com`, and a **dedicated** automation account (not a human's — read state is account-global). `company_id` need not be known up front — `daoubot login` auto-resolves it when `--company-id` is omitted.
2. **Scope**: which rooms? a specific room/list, only 1:1 DMs, or any room it is added to? (drives RoomRouter vs not)
3. **Trigger**: respond to every message, only `!commands`, only when @-mentioned, on a keyword, or on a schedule/external event (proactive)?
4. **Logic**: stateless reply, per-room conversation state, or calls an external service / LLM?
5. **Side effects**: does handling cause non-idempotent actions (creating tickets, sending mail)? → must be made idempotent (at-least-once).

If the user is vague ("make an AI bot"), pick the smallest design that meets the stated goal and state the assumptions; don't invent scope.

## Step 2 — Map requirements → design

The runnable examples in the SDK repo (`examples/bot-*`) are the canonical reference for each pattern — short(~50 lines), self-contained. Open the one closest to the user's case, adapt, don't re-derive.

| Requirement | Use | Example |
|---|---|---|
| One behavior, any/one room | bare `on_message(msg)->str|None` | `examples/bot-echobot` |
| Different behavior per room / DM vs group | `RoomRouter` (allowlist: unregistered rooms ignored) | `examples/bot-router` |
| Quiet in busy groups, act only when addressed | wrap handler in `only_when_mentioned(...)` | `examples/bot-router` (group-room handler) |
| `/cmd args` commands | parse a `msg.message_text` prefix yourself (no command framework; `/` is just convention, pick any) | `examples/bot-command` |
| Per-room conversation state | dict keyed by `msg.room_id` (or external store) | `examples/bot-conversation` |
| AI / LLM answers | call any LLM/API **inside** the handler (SDK bundles none) | `examples/bot-assistant` |
| Bold/italic/links/lists in replies | `DaouBot(..., markdown=True)` — engine renders Markdown to the chat's HTML subset; other syntax degrades to literal text | — |
| Reply visibly tied to the prompt | nothing — the engine already threads every handler reply to the message that triggered it (delivery property, not a flag) | — |
| File attachments out (long docs, CSVs) | `bot.send_file(room, path, content="")` (chat doesn't render long MD/HTML inline) | `examples/bot-attachment` |
| Proactive / scheduled send | a separate `asyncio.Task` calling `bot.client.send_message(room_id, text)` alongside `bot.run_forever()` — polling stays for inbound only | — |
| Blocking work inside a handler | wrap with `await asyncio.to_thread(blocking_fn, ...)` — synchronous code in a handler stalls polling for every room | `examples/bot-assistant` (uses async httpx; the same shape with `to_thread` for sync libs) |
| Recover from handler errors gracefully | catch in handler (fire-and-forget) vs let it raise (at-least-once retry, see invariants) | `examples/bot-error-handler` |
| Survive restarts | default `FileCursorStore` already does; nothing to do | — |

Compose these — they are orthogonal (e.g. `RoomRouter` whose group handler is `only_when_mentioned(llm_handler)` with per-room history).

## Step 2.5 — Configuration: what reads what

Two layers, kept separate:

- **SDK connection** (`base_url`, `company_id`, `login_id`, `password`) — resolved in this order: **explicit argument > `DAOU_*` env > app config YAML's `daouoffice:` section > `~/.daoubot/profile.yaml`** (written by `daoubot login`). Your bot code never re-implements this. The `DAOU_*` family is for connection only — don't repurpose those names for bot config.
- **Bot behavior** (which rooms are allowed, command prefix, LLM keys, feature flags) — yours to name and layer. Pick env names that fit the bot (`ROOM_ALLOW`, `BOT_CMD_PREFIX`, `LLM_API_KEY`, …); `examples/bot-router` shows the env-conditional registration pattern. A sensible layering is **arg > env > YAML/JSON file > default**; never commit secrets or tenant identifiers.

**Embedding the SDK in a downstream app's config (e.g. an `agent.yaml`).** If the app already maintains its own declarative YAML (a single edited file deployed as an artifact), point the SDK at it instead of running `daoubot login`:

```yaml
# agent.yaml — the app's own config; add one section for the SDK
daouoffice:
  base_url: https://yourcompany.daouoffice.com
  login_id: yourbot
  password: <literal or set DAOU_PASSWORD env to override>
  # company_id omitted → SDK auto-discovers it on first call
# ... the app's other sections stay untouched (the SDK only reads, never writes)
```

```python
bot = DaouBot(on_message=on_message, app_config="agent.yaml")
# or via env:   DAOU_APP_CONFIG=/path/to/agent.yaml python bot.py
# or per-CLI:   daoubot --app-config /path/to/agent.yaml rooms
```

The SDK reads only the `daouoffice:` section, only on each call — it never writes back. Tokens and identity stay in `~/.daoubot/profile.yaml` (or wherever `--config` points), so the operator's commented YAML stays intact and rotating secrets stay out of the deploy artifact. Values are literal — `${ENV}` substitution is the operator's app concern, not the SDK's; if env injection is wanted, just set `DAOU_PASSWORD` etc., which override the file anyway.

## Step 3 — Assemble (start from the skeleton, then build)

`scaffold.py` prints **only** the correct boilerplate (env/profile config, graceful run loop, empty handler). It does not choose the design — you do, in the handler, from Step 2.

```bash
python skills/daouoffice-bot/scripts/scaffold.py > bot.py   # path: where the skill is installed
```

Then implement the handler. Build the bot as `DaouBot(on_message=...)` — it resolves connection from the operator's `daoubot login` profile (or `DAOU_*` env / app config / explicit args; precedence arg > env > app config > profile, see Step 2.5). Never put credentials or a tenant URL in the bot code. The simplest setup is `daoubot login` once: that persists the password in `~/.daoubot/profile.yaml` (chmod 600, gitignored, home-anchored so it works from any directory), so the daemon re-authenticates unattended with no extra config. `DAOU_PASSWORD` is only an optional override. Read room ids from env/args too.

## Step 4 — Invariants you MUST keep (the SDK's hard rules)

- **No hard-coded** base_url/company_id/credentials/room ids in any code you write — read them from env (visibly). No real secrets in code or commits.
- **Idempotent handlers.** Delivery is at-least-once (not configurable); restart/crash can re-deliver. Guard non-idempotent side effects.
- **Don't spam.** Any bot reachable from group rooms uses `RoomRouter` and/or `only_when_mentioned` so it doesn't reply to everything everywhere.
- **Dedicated account only** — the bot's `mark_read` clears a human's unread.
- Handler returns fast or is `async`; blocking it stalls all polling.
- One bot process per account (duplicate handling + `mark_read` races).
- DaouOffice has **no** webhooks, inline keyboards, slash-command framework, BotFather, or working WebSocket. If the user asks for these, say so — never fabricate an API. Mentions are pre-parsed (`msg.mentions_me`/`.mention_all`/`.mentions`, `.raw_text`); don't regex `message_text`.

## Step 5 — Onboard & verify

```bash
daoubot login --base-url https://<co>.daouoffice.com --login-id <acct> --password '...'
                                    # company_id auto-resolved if --company-id omitted
daoubot config                      # verify the saved profile (secrets masked)
daoubot rooms                       # get the room ids the design needs
daoubot send <room_id> "smoke test" # confirm live access BEFORE long-run
python bot.py
```

State plainly that contracts are tested but live behavior depends on the tenant. See `references/reference.md` for the API surface, the mention/auth/delivery mechanics, and all gotchas; the SDK repo has `docs/ARCHITECTURE.md` (design rationale) and runnable `examples/` to copy patterns from.
