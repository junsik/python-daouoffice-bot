#!/usr/bin/env python
"""Error-handling bot — guards the handler and reports failures.

Any exception raised while handling a message is caught, the user gets a
friendly message, and (if DAOU_DEV_ROOM is set) the developer room receives
the traceback.

Configure via DAOU_* env vars (see README), then::

    export DAOU_DEV_ROOM="11000000000"   # optional: room id for alerts
    uv run --with python-daouoffice-bot bot.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import traceback

from daouoffice import DaouBot, NewMessage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

DEV_ROOM = os.getenv("DAOU_DEV_ROOM", "")


async def risky_logic(msg: NewMessage) -> str:
    # Demo: "!boom" raises so you can see the error path.
    if msg.message_text.strip() == "!boom":
        raise RuntimeError("intentional failure for demo")
    return f"echo: {msg.message_text}"


def make_handler(bot: DaouBot):
    """Build a guarded handler that reports failures to the dev room."""

    async def handle(msg: NewMessage) -> str:
        try:
            return await risky_logic(msg)
        except Exception:
            logger.exception("handler failed")
            if DEV_ROOM:
                tb = traceback.format_exc()
                await bot.send_message(DEV_ROOM, f"⚠️ Bot error:\n```\n{tb}\n```")
            return "처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."

    return handle


async def main() -> None:
    bot = DaouBot(
        login_id=os.environ["DAOU_LOGIN_ID"],
        password=os.environ["DAOU_PASSWORD"],
        llm="none",
    )
    bot.set_prompt_func(make_handler(bot))
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
