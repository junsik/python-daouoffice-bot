#!/usr/bin/env python
"""Save one specific room's chat to JSONL, using RoomRouter.

`RoomRouter` is allowlist-by-default: only the registered room is handled,
every other room is ignored — so this records exactly the one room you
choose and nothing else. The bot never replies (the handler returns
``None``); it appends one JSON object per line. The engine already filters
out the bot's own messages.

Find the room id first:

    daoubot login --base-url https://yourco.daouoffice.com --login-id my-bot
    daoubot rooms          # prints each room with its room id

Then run (connection resolves from the profile / DAOU_* env):

    ROOM_ID=11000000001 \\
        uv run --with python-daouoffice-bot examples/bot-room-saver/bot.py

Config (env):
    ROOM_ID   the room id to save (required).
    OUTPUT    output path (default: room-chat.jsonl), appended (UTF-8).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from daouoffice import DaouBot, NewMessage, RoomRouter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)

ROOM_ID = os.getenv("ROOM_ID", "").strip()
OUTPUT = Path(os.getenv("OUTPUT", "room-chat.jsonl"))


async def save(msg: NewMessage) -> None:
    entry = {
        "room_id": msg.room_id,
        "message_id": msg.message_id,
        "created_at": msg.created_at,
        "sender_user_id": msg.sender_user_id,
        "sender_name": msg.sender_name,
        "text": msg.message_text,
        "mentions": msg.mentions,
        "mention_all": msg.mention_all,
    }
    with OUTPUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logging.info("%s: %.60s", msg.sender_name, msg.message_text)


async def main() -> None:
    if not ROOM_ID:
        sys.exit("Set ROOM_ID (find it with `daoubot rooms`).")
    router = RoomRouter()
    router.add_room(ROOM_ID, save)  # only this room; all others ignored
    bot = DaouBot(on_message=router)
    logging.info("Saving room %s → %s", ROOM_ID, OUTPUT)
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
