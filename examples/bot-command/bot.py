#!/usr/bin/env python
"""Command bot — the common `!cmd args` pattern.

DaouOffice has no slash-command framework, so commands are a text
convention. Connection resolves from the `daoubot login` profile / DAOU_*
env (see bot-echobot / README).

    uv run --with python-daouoffice-bot examples/bot-command/bot.py

In a room: !help / !echo hello / !whoami
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from daouoffice import DaouBot, NewMessage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)

PREFIX = "!"
Command = Callable[[NewMessage, str], Awaitable[str] | str]
_commands: dict[str, tuple[str, Command]] = {}


def command(name: str, help_text: str) -> Callable[[Command], Command]:
    def deco(fn: Command) -> Command:
        _commands[name] = (help_text, fn)
        return fn

    return deco


@command("help", "show this help")
def cmd_help(msg: NewMessage, args: str) -> str:
    lines = [f"{PREFIX}{n} — {h}" for n, (h, _) in sorted(_commands.items())]
    return "사용 가능한 명령:\n" + "\n".join(lines)


@command("echo", "echo the rest of the message")
def cmd_echo(msg: NewMessage, args: str) -> str:
    return args or "(빈 메시지)"


@command("whoami", "show the sender info")
def cmd_whoami(msg: NewMessage, args: str) -> str:
    return f"{msg.sender_name} (user_id={msg.sender_user_id}, room={msg.room_id})"


async def on_message(msg: NewMessage) -> str | None:
    text = msg.message_text.strip()
    if not text.startswith(PREFIX):
        return None  # not a command → ignore
    name, _, args = text[len(PREFIX) :].partition(" ")
    entry = _commands.get(name.lower())
    if entry is None:
        return f"알 수 없는 명령: {PREFIX}{name}. {PREFIX}help 를 입력하세요."
    result = entry[1](msg, args.strip())
    return await result if asyncio.iscoroutine(result) else result


async def main() -> None:
    bot = DaouBot(on_message=on_message)
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
