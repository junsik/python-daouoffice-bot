#!/usr/bin/env python
"""Echo bot — repeats every message back to its room.

The four connection settings are read from the environment explicitly so you
can see exactly what a bot needs (no hard-coded secrets, no hidden magic):

    export DAOU_BASE_URL="https://yourcompany.daouoffice.com"
    export DAOU_COMPANY_ID="11000000000"   # daoubot discover
    export DAOU_LOGIN_ID="my-bot"
    export DAOU_PASSWORD="..."

    uv run --with python-daouoffice-bot examples/bot-echobot/bot.py
"""

from __future__ import annotations

import asyncio
import logging
import os

from daouoffice import DaouBot, NewMessage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)


async def on_message(msg: NewMessage) -> str:
    return msg.message_text


async def main() -> None:
    bot = DaouBot(
        base_url=os.environ["DAOU_BASE_URL"],
        company_id=os.environ["DAOU_COMPANY_ID"],
        login_id=os.environ["DAOU_LOGIN_ID"],
        password=os.environ["DAOU_PASSWORD"],
        on_message=on_message,
    )
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
