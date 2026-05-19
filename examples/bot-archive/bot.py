#!/usr/bin/env python
"""Archive a room's chat to a JSONL file — one JSON object per line.

A read-only collector: it never replies, only appends messages it sees.
Connection resolves from the `daoubot login` profile / DAOU_* env
(see bot-echobot / README); set DAOU_PASSWORD for unattended runs.

Run:
    ARCHIVE_ROOM=11000000001 \\
        uv run --with python-daouoffice-bot examples/bot-archive/bot.py

Config (env):
    ARCHIVE_ROOM   room id to archive; comma-separate for several rooms.
                   Unset → archive every room the bot is in.
    ARCHIVE_FILE   output path (default: archive.jsonl), appended (UTF-8).
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

ARCHIVE_FILE = Path(os.getenv("ARCHIVE_FILE", "archive.jsonl"))
ROOMS = {r.strip() for r in os.getenv("ARCHIVE_ROOM", "").split(",") if r.strip()}


def archiver(bot: DaouBot):
    """A handler that records messages from the selected room(s)."""

    async def on_message(msg: NewMessage) -> None:
        if ROOMS and msg.room_id not in ROOMS:
            return
        if msg.sender_user_id == bot.client.user_id:
            return  # ignore the bot's own messages
        entry = {
            "room_id": msg.room_id,
            "room_type": msg.room_type,
            "message_id": msg.message_id,
            "created_at": msg.created_at,
            "sender_user_id": msg.sender_user_id,
            "sender_name": msg.sender_name,
            "text": msg.message_text,
            "mentions": msg.mentions,
            "mention_all": msg.mention_all,
        }
        with ARCHIVE_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logging.info("[%s] %s: %.60s", msg.room_id, msg.sender_name, msg.message_text)

    return on_message


async def main() -> None:
    bot = DaouBot()
    bot.set_handler(archiver(bot))
    target = ", ".join(sorted(ROOMS)) if ROOMS else "ALL rooms"
    logging.info("Archiving %s → %s", target, ARCHIVE_FILE)
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
