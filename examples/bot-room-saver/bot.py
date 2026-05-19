#!/usr/bin/env python
"""Save a room's messages to a JSONL file (one JSON object per line).

The bot never replies — it only records. Connection resolves from the
`daoubot login` profile / DAOU_* env (see bot-echobot / README).

    SAVE_ROOM=11000000001 uv run --with python-daouoffice-bot \\
        examples/bot-room-saver/bot.py

Config:
    SAVE_ROOM   room id to collect. Comma-separate for several rooms.
                Leave unset to save every room the bot sees.
    OUTPUT      output file (default: messages.jsonl), appended.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from daouoffice import DaouBot, NewMessage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)

OUTPUT = Path(os.getenv("OUTPUT", "messages.jsonl"))
SAVE_ROOMS = {r.strip() for r in os.getenv("SAVE_ROOM", "").split(",") if r.strip()}


def make_handler(bot: DaouBot):
    async def on_message(msg: NewMessage) -> None:
        if SAVE_ROOMS and msg.room_id not in SAVE_ROOMS:
            return  # not a room we collect
        if msg.sender_user_id == bot.client.user_id:
            return  # skip the bot's own messages
        line = json.dumps(
            {
                "room_id": msg.room_id,
                "room_type": msg.room_type,
                "message_id": msg.message_id,
                "created_at": msg.created_at,
                "sender_user_id": msg.sender_user_id,
                "sender_name": msg.sender_name,
                "text": msg.message_text,
                "mentions": msg.mentions,
            },
            ensure_ascii=False,
        )
        with OUTPUT.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    return on_message


async def main() -> None:
    bot = DaouBot()
    bot.set_handler(make_handler(bot))
    where = ", ".join(sorted(SAVE_ROOMS)) if SAVE_ROOMS else "ALL rooms"
    logging.info("Saving %s → %s", where, OUTPUT)
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
