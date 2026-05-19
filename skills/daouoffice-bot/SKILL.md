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

You are designing a bot **to the user's actual requirements** on `python-daouoffice-bot` (an unofficial, reverse-engineered SDK). This skill is the SDK author's distilled knowledge: do not guess from a template menu — elicit what the user needs, then assemble the right bot from primitives while obeying the invariants below. `reference.md` has the full API + gotchas.

## Step 1 — Elicit requirements (ask, don't assume)

Before writing code, get answers (ask only what's unknown):

1. **Tenant + account**: their `https://<co>.daouoffice.com`, and a **dedicated** automation account (not a human's — read state is account-global). `company_id` need not be known up front — `daoubot login` auto-resolves it when `--company-id` is omitted.
2. **Scope**: which rooms? a specific room/list, only 1:1 DMs, or any room it is added to? (drives RoomRouter vs not)
3. **Trigger**: respond to every message, only `!commands`, only when @-mentioned, on a keyword, or on a schedule/external event (proactive)?
4. **Logic**: stateless reply, per-room conversation state, or calls an external service / LLM?
5. **Side effects**: does handling cause non-idempotent actions (creating tickets, sending mail)? → must be made idempotent (at-least-once).

If the user is vague ("make an AI bot"), pick the smallest design that meets the stated goal and state the assumptions; don't invent scope.

## Step 2 — Map requirements → design

| Requirement | Use |
|---|---|
| One behavior, any/one room | bare `on_message(msg)->str|None` |
| Different behavior per room / DM vs group | `RoomRouter` (allowlist: unregistered rooms ignored) |
| Quiet in busy groups, act only when addressed | wrap handler in `only_when_mentioned(...)` |
| `/cmd args` commands | parse a `msg.message_text` prefix yourself (no command framework; `/` is just convention, pick any) |
| Conversation state | dict keyed by `msg.room_id` (or external store) |
| AI answers | call any LLM/API **inside** the handler — SDK bundles none |
| Proactive/scheduled send | run a separate task using `bot.send_message(room_id, text)`; polling stays for inbound |
| Survive restarts | default `FileCursorStore` already does; nothing to do |

Compose these — they are orthogonal (e.g. `RoomRouter` whose group handler is `only_when_mentioned(llm_handler)` with per-room history).

## Step 3 — Assemble (start from the skeleton, then build)

`scaffold.py` prints **only** the correct boilerplate (env/profile config, graceful run loop, empty handler). It does not choose the design — you do, in the handler, from Step 2.

```bash
python skills/daouoffice-bot/scaffold.py > bot.py   # path: where the skill is installed
```

Then implement the handler. Build the bot as `DaouBot(on_message=...)` — it resolves connection from the operator's `daoubot login` profile (or `DAOU_*` env / explicit args; precedence arg > env > profile). Never put credentials or a tenant URL in the bot code. The user runs `daoubot login` once first — that persists the password in `~/.daoubot/profile.json` (chmod 600, gitignored, home-anchored so it works from any directory), so the daemon re-authenticates unattended with no extra config. `DAOU_PASSWORD` is only an optional override. Read room ids from env/args too.

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

State plainly that contracts are tested but live behavior depends on the tenant. See `reference.md` for the API surface, the mention/auth/delivery mechanics, and all gotchas; the SDK repo has `docs/ARCHITECTURE.md` (design rationale) and runnable `examples/` to copy patterns from.
