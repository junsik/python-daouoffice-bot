#!/usr/bin/env python
"""Conversation bot — a tiny per-room state machine.

Drive it by sending: "시작" → "네" → "네".
Connection settings come from env / profile (see README).

    uv run --with python-daouoffice-bot examples/bot-conversation/bot.py
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from daouoffice import DaouBot, NewMessage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)

# (state, keyword) -> (next_state, reply)
TRANSITIONS: dict[tuple[str | None, str], tuple[str, str]] = {
    (None, "시작"): ("greeting", "안녕하세요! 계속하려면 '네' 라고 보내주세요."),
    ("greeting", "네"): ("ask_name", "이름을 입력해 주세요."),
    ("ask_name", "네"): ("done", "감사합니다! 대화를 종료합니다."),
}

_state: dict[str, str | None] = defaultdict(lambda: None)


async def handle(msg: NewMessage) -> str:
    current = _state[msg.room_id]
    nxt = TRANSITIONS.get((current, msg.message_text.strip()))
    if nxt is None:
        _state[msg.room_id] = None
        return "처음으로 돌아갑니다. '시작' 을 보내주세요."
    next_state, reply = nxt
    _state[msg.room_id] = None if next_state == "done" else next_state
    return reply


async def main() -> None:
    bot = DaouBot.from_env(prompt_func=handle)
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
