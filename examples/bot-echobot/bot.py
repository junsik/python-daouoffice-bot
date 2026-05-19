#!/usr/bin/env python
"""Echo bot — repeats every message back.

Onboard once: `daoubot login` writes ~/.daoubot/profile.json; this bot reads
it automatically from any directory. For unattended operation the saved
password lets it re-authenticate itself when the ~30-min token expires.
Any setting can be overridden via a DAOU_* env var (precedence: env > profile).

    daoubot login --base-url https://yourco.daouoffice.com --login-id my-bot
    uv run --with python-daouoffice-bot examples/bot-echobot/bot.py
"""

from __future__ import annotations

import asyncio
import logging

from daouoffice import DaouBot, NewMessage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)


async def on_message(msg: NewMessage) -> str:
    return msg.message_text


async def main() -> None:
    bot = DaouBot(on_message=on_message)
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
