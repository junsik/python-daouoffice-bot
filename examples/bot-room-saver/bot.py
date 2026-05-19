#!/usr/bin/env python
"""Room chat saver — append messages from selected rooms to a JSONL file.

This bot never replies; it only records messages. Connection resolves from
the `daoubot login` profile / DAOU_* env (see bot-echobot / README).

    uv run --with python-daouoffice-bot examples/bot-room-saver/bot.py

Optional config:
    SAVED_ROOM_IDS   comma-separated room ids to save (unset → all rooms)
    OUTPUT           JSONL output path (default: room-chat.jsonl, appended)
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

OUTPUT = Path(os.getenv("OUTPUT", "room-chat.jsonl"))


def _room_filter() -> set[str] | None:
    """Allowed room ids, or None for "all rooms"."""
    ids = {r.strip() for r in os.getenv("SAVED_ROOM_IDS", "").split(",") if r.strip()}
    return ids or None


ROOM_FILTER = _room_filter()


def make_handler(bot: DaouBot):
    """Skip the bot's own messages (its user id is known after start())."""

    async def on_message(msg: NewMessage) -> None:
        if ROOM_FILTER is not None and msg.room_id not in ROOM_FILTER:
            return
        if msg.sender_user_id == bot.client.user_id:
            return  # don't record our own messages
        record = {
            "room_id": msg.room_id,
            "room_type": msg.room_type,
            "sender_user_id": msg.sender_user_id,
            "sender_name": msg.sender_name,
            "message_id": msg.message_id,
            "created_at": msg.created_at,
            "message_text": msg.message_text,
            "mentions": msg.mentions,
            "mentions_me": msg.mentions_me,
            "mention_all": msg.mention_all,
        }
        with OUTPUT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return on_message


async def main() -> None:
    bot = DaouBot()
    bot.set_handler(make_handler(bot))
    if ROOM_FILTER:
        logging.info("Saving %d room(s): %s", len(ROOM_FILTER), ", ".join(sorted(ROOM_FILTER)))
    else:
        logging.info("Saving ALL rooms.")
    logging.info("Chat saver ready → %s", OUTPUT)
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
