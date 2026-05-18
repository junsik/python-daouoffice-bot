#!/usr/bin/env python
"""Echo bot — repeats every message back to its room.

All connection settings come from env / .daoubot/profile.json (see README):
DAOU_BASE_URL, DAOU_COMPANY_ID, DAOU_LOGIN_ID, DAOU_PASSWORD.

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


async def echo(msg: NewMessage) -> str:
    return msg.message_text


async def main() -> None:
    bot = DaouBot.from_env(prompt_func=echo)
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
