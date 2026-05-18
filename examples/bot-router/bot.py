#!/usr/bin/env python
"""Per-room routing — one bot account, different behavior per room.

Only the rooms you register are handled; the bot stays silent in every other
room it gets added to (safe allowlist by default).

Set DAOU_* env vars (see README) and the room ids you want to handle, then::

    export ROOM_STANDUP="11000000001"
    uv run --with python-daouoffice-bot examples/bot-router/bot.py
"""

from __future__ import annotations

import asyncio
import logging
import os

from daouoffice import DaouBot, NewMessage, RoomRouter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)

router = RoomRouter()


@router.room(os.getenv("ROOM_STANDUP", "ROOM_STANDUP_ID"))
async def standup(msg: NewMessage) -> str | None:
    if msg.message_text.strip() == "!standup":
        return "오늘 스탠드업: 어제 한 일 / 오늘 할 일 / 블로커 를 적어주세요."
    return None


@router.room_type("SINGLE")
async def direct_message(msg: NewMessage) -> str:
    return f"안녕하세요 {msg.sender_name}님, 1:1 봇입니다. 무엇을 도와드릴까요?"


# No @router.default → unregistered group rooms are ignored.


async def main() -> None:
    bot = DaouBot(
        login_id=os.environ["DAOU_LOGIN_ID"],
        password=os.environ["DAOU_PASSWORD"],
        prompt_func=router,
    )
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
