#!/usr/bin/env python
"""Scaffold a python-daouoffice-bot bot.

Usage:
    python scaffold.py <kind>     # kind: echo | command | assistant | router

Prints a complete bot.py to stdout. Connection settings are read from env /
.daoubot/profile.json via DaouBot.from_env() — nothing is hard-coded.
"""

from __future__ import annotations

import sys

_HEADER = '''#!/usr/bin/env python
"""DaouOffice bot — connection from env/profile (DaouBot.from_env).

Requires: DAOU_BASE_URL, DAOU_COMPANY_ID, DAOU_LOGIN_ID, DAOU_PASSWORD
(or a prior `daoubot login`). Run:  python bot.py
"""

from __future__ import annotations

import asyncio
import logging
'''

_LOGGING = '''
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
'''

ECHO = (
    _HEADER
    + "\nfrom daouoffice import DaouBot, NewMessage\n"
    + _LOGGING
    + '''

async def handle(msg: NewMessage) -> str:
    return msg.message_text


async def main() -> None:
    bot = DaouBot.from_env(prompt_func=handle)
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
'''
)

COMMAND = (
    _HEADER
    + "\nfrom daouoffice import DaouBot, NewMessage\n"
    + _LOGGING
    + '''
PREFIX = "!"


async def handle(msg: NewMessage) -> str | None:
    text = msg.message_text.strip()
    if not text.startswith(PREFIX):
        return None
    name, _, args = text[len(PREFIX):].partition(" ")
    if name == "help":
        return "명령: !help, !ping, !echo <text>"
    if name == "ping":
        return "pong"
    if name == "echo":
        return args or "(빈 메시지)"
    return f"알 수 없는 명령: {PREFIX}{name} (!help)"


async def main() -> None:
    bot = DaouBot.from_env(prompt_func=handle)
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
'''
)

ASSISTANT = (
    _HEADER
    + "import os\n\nimport httpx\n\nfrom daouoffice import DaouBot, NewMessage\n"
    + _LOGGING
    + '''
# This example's own config (the SDK bundles no LLM):
LLM_BASE_URL = os.environ["LLM_BASE_URL"].rstrip("/")
LLM_API_KEY = os.environ["LLM_API_KEY"]
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")


async def handle(msg: NewMessage) -> str:
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            r = await http.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={
                    "model": LLM_MODEL,
                    "messages": [{"role": "user", "content": msg.message_text}],
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        logging.exception("LLM call failed")
        return "죄송합니다. 지금은 응답할 수 없어요."


async def main() -> None:
    bot = DaouBot.from_env(prompt_func=handle)
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
'''
)

ROUTER = (
    _HEADER
    + "import os\n\n"
    + "from daouoffice import DaouBot, NewMessage, RoomRouter, only_when_mentioned\n"
    + _LOGGING
    + '''
router = RoomRouter()


@router.room_type("SINGLE")
async def dm(msg: NewMessage) -> str:
    return f"안녕하세요 {msg.sender_name}님, 무엇을 도와드릴까요?"


async def group_cmd(msg: NewMessage) -> str | None:
    if msg.message_text.strip() == "!status":
        return "정상 동작 중입니다."
    return None


# Busy group room id from env → only react when the bot is @-mentioned.
_room = os.getenv("ROOM_ID")
if _room:
    router.add_room(_room, only_when_mentioned(group_cmd))
# Unregistered rooms are silently ignored (allowlist).


async def main() -> None:
    bot = DaouBot.from_env(prompt_func=router)
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
'''
)

_KINDS = {"echo": ECHO, "command": COMMAND, "assistant": ASSISTANT, "router": ROUTER}


def main() -> None:
    kind = sys.argv[1] if len(sys.argv) > 1 else ""
    template = _KINDS.get(kind)
    if template is None:
        sys.exit(f"usage: python scaffold.py <{'|'.join(_KINDS)}>")
    # Force UTF-8: generated code contains Korean text and the default
    # Windows console codec (cp949) would raise UnicodeEncodeError.
    sys.stdout.buffer.write(template.encode("utf-8"))


if __name__ == "__main__":
    main()
