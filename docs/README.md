# Docs

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — how the SDK is designed and *why* (decisions, diagrams). Start here to understand the project.
- **[api/](api/README.md)** — the reverse-engineered DaouOffice REST endpoint reference (auth, chat rooms, messages incl. mentions/attachments, the unimplemented WebSocket notes, portal/org). Anonymized samples from SAZ capture.

Operational note: there is no bundled systemd unit — running the bot is just `python your_bot.py` (or `daoubot start`); wrap it in whatever supervisor you use (systemd/Docker/etc.).
