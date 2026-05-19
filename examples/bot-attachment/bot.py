#!/usr/bin/env python
"""Attachment bot — reply to `!report` with a generated file.

Chat does not inline-render Markdown/HTML, so the SDK posts generated
documents as downloadable attachments instead. On `!report` this bot
builds a small Markdown report on the fly, writes it to a temp file, and
sends it with `bot.send_file(room_id, path, caption)` (which is
`upload_attachment()` + `send_message(..., attachments=[...])` underneath).
The same path fits an LLM-generated newsletter.

Connection resolves from the `daoubot login` profile / DAOU_* env (see
bot-echobot / README).

    uv run --with python-daouoffice-bot examples/bot-attachment/bot.py

In a room: !report

NOTE: the attachment upload/send contract is reverse-engineered from SAZ
captures and is NOT live-verified — confirm against real traffic.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from datetime import datetime
from pathlib import Path

from daouoffice import DaouBot, NewMessage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)

PREFIX = "!"


def build_report(msg: NewMessage) -> str:
    """Return the Markdown document body (real bots plug an LLM here)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"# 데일리 리포트\n\n"
        f"- 생성 시각: {now}\n"
        f"- 요청자: {msg.sender_name}\n"
        f"- 방: {msg.room_id}\n\n"
        f"## 요약\n\n"
        f"여기에 집계/LLM 생성 내용이 들어갑니다.\n"
    )


def make_handler(bot: DaouBot):
    async def on_message(msg: NewMessage) -> str | None:
        if msg.message_text.strip() != f"{PREFIX}report":
            return None  # not the command → ignore (no text reply)
        report = build_report(msg)
        # Write to a temp file; the attachment is the file, not the text.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.md"
            path.write_text(report, encoding="utf-8")
            await bot.send_file(msg.room_id, str(path), "데일리 리포트입니다.")
        return None  # send_file already posted the message; no extra reply

    return on_message


async def main() -> None:
    bot = DaouBot()
    bot.set_handler(make_handler(bot))
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
