"""DaouOffice bot command-line interface (``daoubot``).

Connection settings come from flags or environment variables:

    DAOU_BASE_URL    https://yourcompany.daouoffice.com
    DAOU_COMPANY_ID  numeric tenant id (use `daoubot discover` to find it)
    DAOU_LOGIN_ID    bot account login id
    DAOU_PASSWORD    bot account password

Commands:
    daoubot discover                 # look up company id / uuid / domain
    daoubot whoami                   # print this bot account's identity
    daoubot rooms                    # list chat rooms
    daoubot send <room_id> <text>    # send a message
    daoubot start                    # run the polling bot
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from daouoffice import BotClient, DaouBot
from daouoffice.client import DaouConfigError


def _env(name: str, value: str | None) -> str | None:
    return value or os.getenv(name) or None


def _need(name: str, value: str | None, flag: str) -> str:
    resolved = _env(name, value)
    if not resolved:
        print(f"error: missing {flag} (or env {name})", file=sys.stderr)
        sys.exit(2)
    return resolved


def _make_client(args: argparse.Namespace) -> BotClient:
    return BotClient(
        _need("DAOU_LOGIN_ID", args.login_id, "--login-id"),
        _need("DAOU_PASSWORD", args.password, "--password"),
        base_url=_need("DAOU_BASE_URL", args.base_url, "--base-url"),
        company_id=_env("DAOU_COMPANY_ID", args.company_id),
    )


def cmd_discover(args: argparse.Namespace) -> None:
    base_url = _need("DAOU_BASE_URL", args.base_url, "--base-url")
    print(f"Querying {base_url} (public, no auth) ...")
    try:
        info = BotClient.discover_company(base_url)
        print("\n[company]")
        print(json.dumps(info, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"  public company lookup failed: {e}")

    login_id = _env("DAOU_LOGIN_ID", args.login_id)
    password = _env("DAOU_PASSWORD", args.password)
    company_id = _env("DAOU_COMPANY_ID", args.company_id)
    if login_id and password and company_id:
        client = BotClient(
            login_id, password, base_url=base_url, company_id=company_id
        )
        identity = client.login()
        client.logout()
        print("\n[bot account]")
        print(json.dumps(identity.__dict__, indent=2, ensure_ascii=False))
    else:
        print(
            "\nProvide --login-id/--password and the company id above "
            "to also resolve this bot account's user id."
        )


def cmd_whoami(args: argparse.Namespace) -> None:
    client = _make_client(args)
    identity = client.login()
    client.logout()
    print(json.dumps(identity.__dict__, indent=2, ensure_ascii=False))


def cmd_rooms(args: argparse.Namespace) -> None:
    client = _make_client(args)
    client.login()
    try:
        rooms = client.get_rooms()
        print(f"\n{'#':>3}  {'room name':24} {'type':6} {'mbr':>4} {'unread':>6}  room id")
        print("-" * 78)
        for i, r in enumerate(rooms, 1):
            rtype = {"SINGLE": "1:1", "GROUP": "group"}.get(r.roomType, r.roomType)
            print(
                f"{i:>3}  {r.roomName[:24]:24} {rtype:6} "
                f"{r.roomMemberCount:>4} {r.unreadMessageCount:>6}  {r.roomId}"
            )
        print(f"\nTotal {len(rooms)} rooms\n")
    finally:
        client.logout()


def cmd_send(args: argparse.Namespace) -> None:
    client = _make_client(args)
    client.login()
    try:
        client.send_message(args.room_id, args.message)
        print(f"sent to {args.room_id}")
    finally:
        client.logout()


def cmd_start(args: argparse.Namespace) -> None:
    bot = DaouBot(
        _need("DAOU_LOGIN_ID", args.login_id, "--login-id"),
        _need("DAOU_PASSWORD", args.password, "--password"),
        base_url=_need("DAOU_BASE_URL", args.base_url, "--base-url"),
        company_id=_env("DAOU_COMPANY_ID", args.company_id),
        llm=args.llm,
    )
    asyncio.run(bot.run_forever())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="daoubot", description="DaouOffice bot CLI")
    parser.add_argument("--base-url", help="tenant URL (env DAOU_BASE_URL)")
    parser.add_argument("--company-id", help="tenant company id (env DAOU_COMPANY_ID)")
    parser.add_argument("--login-id", help="bot login id (env DAOU_LOGIN_ID)")
    parser.add_argument("--password", help="bot password (env DAOU_PASSWORD)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("discover", help="look up company id / uuid / domain")
    sub.add_parser("whoami", help="print this bot account's identity")
    sub.add_parser("rooms", help="list chat rooms")

    p_send = sub.add_parser("send", help="send a message to a room")
    p_send.add_argument("room_id")
    p_send.add_argument("message")

    p_start = sub.add_parser("start", help="run the polling bot")
    p_start.add_argument(
        "--llm",
        default="none",
        choices=("api", "claude-cli", "ollama", "hermes-cli", "none"),
        help="LLM backend (default: none)",
    )
    return parser


_COMMANDS = {
    "discover": cmd_discover,
    "whoami": cmd_whoami,
    "rooms": cmd_rooms,
    "send": cmd_send,
    "start": cmd_start,
}


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        _COMMANDS[args.command](args)
    except DaouConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
