#!/usr/bin/env python
"""Print the minimal correct bot skeleton — boilerplate only.

This deliberately does NOT pick a bot "type". The design (router? mention
gate? commands? state? LLM?) is decided from the user's requirements per
SKILL.md; this only removes the env/profile + run-loop ceremony so the agent
fills in the handler.

    python scaffold.py > bot.py
"""

from __future__ import annotations

import sys

SKELETON = '''#!/usr/bin/env python
"""DaouOffice bot.

The four connection settings are read from the environment explicitly so the
required inputs are visible (no hard-coded secrets):
DAOU_BASE_URL, DAOU_COMPANY_ID, DAOU_LOGIN_ID, DAOU_PASSWORD
Run:  python bot.py
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


async def on_message(msg: NewMessage) -> str | None:
    # TODO: implement the behavior the user asked for.
    #   msg.room_id / room_type / sender_name / message_text
    #   msg.mentions_me / mention_all / mentions / raw_text
    # Return a string to reply, or None for no reply.
    # Compose RoomRouter / only_when_mentioned per SKILL.md Step 2 if needed.
    # Keep it idempotent (delivery is at-least-once).
    return None


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
'''


def main() -> None:
    # UTF-8: skeleton has non-ASCII and the default Windows console codec
    # (cp949 on Korean Windows) would raise UnicodeEncodeError on a pipe.
    sys.stdout.buffer.write(SKELETON.encode("utf-8"))


if __name__ == "__main__":
    main()
