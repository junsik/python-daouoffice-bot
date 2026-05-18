#!/usr/bin/env python
"""Echo bot — repeats every message back to its room.

Configure via environment variables, then run::

    export DAOU_BASE_URL="https://yourcompany.daouoffice.com"
    export DAOU_COMPANY_ID="11000000000"
    export DAOU_LOGIN_ID="my-bot"
    export DAOU_PASSWORD="..."

    uv run --with python-daouoffice-bot bot.py
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


async def echo(msg: NewMessage) -> str:
    return msg.message_text


async def main() -> None:
    bot = DaouBot(
        login_id=os.environ["DAOU_LOGIN_ID"],
        password=os.environ["DAOU_PASSWORD"],
        # base_url / company_id come from DAOU_BASE_URL / DAOU_COMPANY_ID
        llm="none",
        prompt_func=echo,
    )
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
