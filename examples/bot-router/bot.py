#!/usr/bin/env python
"""Per-room routing — one bot account, different behavior per room.

Only registered rooms are handled; the bot stays silent everywhere else
(allowlist). Convention: 1:1 (SINGLE) answers everything, busy GROUP rooms
only when the bot is @-mentioned.

Connection env vars: the same four shown in bot-echobot / README.
Optional app config:
    ROOM_STANDUP   a group room id that runs the !standup command

    uv run --with python-daouoffice-bot examples/bot-router/bot.py
"""

from __future__ import annotations

import asyncio
import logging
import os

from daouoffice import DaouBot, NewMessage, RoomRouter, only_when_mentioned

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)

router = RoomRouter()


@router.room_type("SINGLE")
async def direct_message(msg: NewMessage) -> str:
    return f"안녕하세요 {msg.sender_name}님, 1:1 봇입니다. 무엇을 도와드릴까요?"


async def standup(msg: NewMessage) -> str | None:
    if msg.message_text.strip() == "!standup":
        return "오늘 스탠드업: 어제 한 일 / 오늘 할 일 / 블로커 를 적어주세요."
    return None


room_standup = os.getenv("ROOM_STANDUP")
if room_standup:
    # Busy group room → only react when the bot is @-mentioned.
    router.add_room(room_standup, only_when_mentioned(standup))

# Unregistered rooms have no handler → silently ignored.


async def main() -> None:
    bot = DaouBot(
        base_url=os.environ["DAOU_BASE_URL"],
        company_id=os.environ["DAOU_COMPANY_ID"],
        login_id=os.environ["DAOU_LOGIN_ID"],
        password=os.environ["DAOU_PASSWORD"],
        on_message=router,
    )
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
