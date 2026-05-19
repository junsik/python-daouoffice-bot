#!/usr/bin/env python
"""Error-handling bot — guard the handler and report failures.

Connection resolves from the `daoubot login` profile / DAOU_* env (see
bot-echobot / README). Optional config:
    DAOU_DEV_ROOM   room id to send tracebacks to (unset → log only)

    uv run --with python-daouoffice-bot examples/bot-error-handler/bot.py
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
    if msg.message_text.strip() == "!boom":
        raise RuntimeError("intentional failure for demo")
    return f"echo: {msg.message_text}"


def make_handler(bot: DaouBot):
    async def on_message(msg: NewMessage) -> str:
        try:
            return await risky_logic(msg)
        except Exception:
            logger.exception("handler failed")
            if DEV_ROOM:
                tb = traceback.format_exc()
                await bot.send_message(DEV_ROOM, f"⚠️ Bot error:\n```\n{tb}\n```")
            return "처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."

    return on_message


async def main() -> None:
    bot = DaouBot()
    bot.set_handler(make_handler(bot))
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
