# Roadmap

Proposed direction by version. Not dated — items ship when ready and the
quality bar is met. Pre-1.0, so `0.x` may contain breaking changes
(documented in [CHANGELOG.md](CHANGELOG.md)).

## Principles (read before adding anything)

These are decisions already made; the roadmap must not regress them.

- **Follow standards; don't add footgun knobs.** (Why delivery is fixed
  at-least-once, not configurable — see ARCHITECTURE.md.)
- **Tight scope.** The SDK does DaouOffice messaging. LLM, web framework,
  job orchestration stay out of core (handler/example concerns).
- **Honest about the unverified.** Reverse-engineered; nothing speculative
  ships as a feature. Live behavior must be validated before it's "supported".
- **Multi-tenant, no hard-coded values, no secrets.** Always.
- **Transport in the engine, policy in the handler.** New primitives stay
  composable and orthogonal (like `RoomRouter` × `only_when_mentioned`).

## 0.1.0 — First release (current branch, unreleased)

Done: multi-tenant client, GraphQL identity, 401 re-login, polling engine
(cursor persistence, at-least-once, poison guard), `RoomRouter`,
`only_when_mentioned`, mention parsing, `from_env`/config resolver, `daoubot`
CLI, profile store, 6 examples, Claude skill, docs, 42 tests + CI.

Gate to actually cut 0.1.0:

- [ ] **Live smoke test** against one real tenant (`daoubot login` → `rooms`
      → `send` → a running echo bot) — the one thing tests can't cover here.
      Record the result in CHANGELOG.
- [ ] Tag `v0.1.0`, GitHub Release from CHANGELOG.
- [ ] (Optional) publish to PyPI.

## 0.2.x — Hardening (no protocol risk)

- `mypy` (or `ty`) in CI — back the shipped `py.typed`.
- CLI command tests (`room create/open`, `send`, `whoami`, `discover`).
- `SECURITY.md` + a documented dependency/version policy.
- Rate-limit / flood awareness: detect HTTP 429 / throttling responses and
  back off per-room (today: only whole-loop backoff).
- Larger restart catch-up: use `get_chat_history(message_id=...)` to page
  past the ~20-message window when resuming from a saved cursor.
- `SqliteCursorStore` (the `CursorStore` interface already supports it) for
  multi-room bots that outgrow a JSON file.
- **Concurrency model**: today a slow/awaiting handler blocks the whole poll
  cycle (all rooms). Dispatch should be **per-room ordered but cross-room
  concurrent** (bounded), so one busy room can't stall the rest.

## 0.3.x — Capability expansion (only already-observed endpoints)

Grounded in the reverse-engineered docs; each needs a real-traffic check
before being called supported.

- **Inbound message taxonomy & events** (the biggest functional gap): the
  engine currently drops everything that is not `contents.message.text`. A
  messenger SDK must surface message *kind* from `metadata`
  (`messageType`/`subType`/`action`) — files/images/emoticons, **system
  events (member join/leave** → welcome-bot, the canonical pattern),
  reply/quote, and edit/delete (`messageStatus`). `NewMessage` grows a
  `kind` + typed payload; handlers can opt in. Receiving/downloading inbound
  attachments (`tempFileDownloadLink`) builds on this.
- **Outbound interactions**: emoticon/reaction (`/api/chat/message/emoticon`)
  and reply-to-a-message (`action:"REPLY"`) — basic messenger verbs we can
  send but currently can't.
- **Room members & presence**: a `get_members()` model and
  presence/connection status (`/api/chat/user/status/connection`, seen in
  the capture) — needed for welcome/roster bots. Verification needed.
- **Org directory lookup**: resolve users by name/department (GraphQL /
  organization tree) so `create_room`/mentions don't require raw numeric ids.
- **Outbound mentions**: helper to build the `{{uuid::USER::@name::id}}`
  token so a reply can @-mention someone (inbound parsing already exists).
- **Message search wrapper**: `/api/chat/search/message` (incl.
  `mentionTypeList`) — could power an efficient "mentions-only" mode.
- **Room admin ops**: leave / lock / kick / history-open (documented in
  `docs/02-chat-room.md`), behind explicit methods.
- **Attachments**: *send* is done in 0.1 (`upload_attachment`/`send_file`,
  SAZ-derived, live-unverified). Remaining: receiving/downloading inbound
  attachments, and emoticon reactions (`/api/chat/message/emoticon`).

## 0.4.x — Ergonomics (gated on real demand, not speculation)

- Proactive/scheduled send: a small documented pattern or thin helper for
  running a sender task alongside polling (no heavy JobQueue framework).
- Optional conversation-state helper — only if examples prove the userland
  dict pattern is genuinely insufficient. Default stays "do it in the
  handler"; resist framework creep.

## Research track (version-independent, parallel)

- **WebSocket / STOMP real-time** (`GET /ws/pc`). Endpoint observed in
  capture but the flow was never validated, so it is **not implemented** and
  **not scheduled**. Promotion requires: a clean validated capture against a
  live tenant, a tested client, and parity with polling's delivery
  guarantees. Even then, **polling remains the supported default**; WS would
  be opt-in. No speculative code lands before validation.

## 1.0.0 — API stability (a gate, not a date)

Cut only when all hold:

- Live-verified against ≥1 real tenant over a sustained period.
- Public API (`daouoffice.__all__`) frozen; deprecation policy written.
- Docs complete; CHANGELOG reflects every breaking 0.x change.
- No "unverified/experimental" surface remaining in the package.

## Explicitly out of scope (do not re-propose)

- Bundling an LLM in the SDK (handler/example concern).
- A BotFather-style registration (DaouOffice has none — it's a normal
  account).
- Webhooks / inline keyboards / slash-command framework (server doesn't
  support them — don't fabricate).
- A configurable delivery-mode knob (rejected: silent-loss footgun — see
  ARCHITECTURE.md "Decision history").
- Running multiple bot processes on one account (duplicate handling / read
  races) — scale with `RoomRouter` in one process.
