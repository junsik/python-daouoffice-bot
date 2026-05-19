"""DaouOffice bot command-line interface (``daoubot``).

Onboarding flow for SDK developers::

    daoubot login --base-url https://acme.daouoffice.com \\
        --login-id my-bot --password '...'        # → saves .daoubot/profile.json

    daoubot whoami                                # company + bot identity
    daoubot rooms                                 # list rooms (with room ids)
    daoubot room create --users 110...,110... --name "Bot Test"
    daoubot room open <room_id>                   # members + detail
    daoubot send <room_id> "hello"
    daoubot start                                 # run the polling bot

After ``login`` the saved session token is reused, so later commands need no
credentials. Settings precedence: CLI flag > environment variable > profile.
Connection env vars: DAOU_BASE_URL, DAOU_COMPANY_ID, DAOU_LOGIN_ID, DAOU_PASSWORD.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import httpx

from daouoffice import BotClient, DaouBot
from daouoffice.client import DaouAuthError, DaouConfigError
from daouoffice.profile import Profile, load_profile, profile_path, save_profile


def _pick(flag: str | None, env: str, prof: str | None) -> str | None:
    """Resolve a setting: CLI flag > environment variable > profile."""
    return flag or os.getenv(env) or (prof or None)


def _die(msg: str, code: int = 2) -> None:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _cfg(args: argparse.Namespace) -> str | None:
    """The --config profile path, if given."""
    return getattr(args, "config", None)


def _settings(args: argparse.Namespace) -> tuple[Profile | None, str, str | None]:
    """Return (profile, base_url, company_id), erroring if base_url is unknown."""
    prof = load_profile(path=_cfg(args))
    base_url = _pick(args.base_url, "DAOU_BASE_URL", prof.base_url if prof else None)
    if not base_url:
        _die("base_url unknown — pass --base-url, set DAOU_BASE_URL, or run `daoubot login`")
    company_id = _pick(args.company_id, "DAOU_COMPANY_ID", prof.company_id if prof else None)
    return prof, base_url, company_id


def _authed_client(args: argparse.Namespace) -> BotClient:
    """A logged-in client: reuse the saved token, else log in with creds."""
    prof, base_url, company_id = _settings(args)

    if prof and prof.access_token:
        client = BotClient.from_token(base_url, prof.access_token)
        try:
            client.identity = client.whoami()
            return client
        except (httpx.HTTPError, DaouAuthError):
            print("saved session expired — re-authenticating...", file=sys.stderr)

    login_id = _pick(args.login_id, "DAOU_LOGIN_ID", prof.login_id if prof else None)
    password = _pick(args.password, "DAOU_PASSWORD", None)
    if not (login_id and password and company_id):
        _die("session expired and no credentials — run `daoubot login` again")
    client = BotClient(login_id, password, base_url=base_url, company_id=company_id)
    client.login()
    _store(client, base_url, _cfg(args))
    return client


def _store(client: BotClient, base_url: str, config_path: str | None = None) -> None:
    ident = client.identity
    if ident is None:
        return
    save_profile(
        Profile(
            base_url=base_url,
            company_id=ident.company_id,
            company_uuid=ident.company_uuid,
            company_domain=ident.company_domain,
            login_id=ident.login_id,
            user_id=ident.user_id,
            name=ident.name,
            access_token=client.access_token,
        ),
        path=config_path,
    )


# -- commands -----------------------------------------------------------


def cmd_login(args: argparse.Namespace) -> None:
    base_url = _pick(args.base_url, "DAOU_BASE_URL", None)
    if not base_url:
        _die("--base-url (or DAOU_BASE_URL) is required for login")
    login_id = _pick(args.login_id, "DAOU_LOGIN_ID", None)
    password = _pick(args.password, "DAOU_PASSWORD", None)
    if not (login_id and password):
        _die("--login-id and --password (or env) are required for login")

    company_id = _pick(args.company_id, "DAOU_COMPANY_ID", None)
    if not company_id:
        print("company_id not given — discovering from public endpoint...")
        try:
            info = BotClient.discover_company(base_url)
            company_id = str(info.get("id") or info.get("companyId") or "")
            if company_id:
                print(f"  resolved company_id={company_id}")
        except Exception as e:
            _die(f"could not auto-discover company_id ({e}); pass --company-id")

    client = BotClient(login_id, password, base_url=base_url, company_id=company_id)
    client.login()
    cfg = _cfg(args)
    _store(client, base_url, cfg)
    print(f"\nsaved → {profile_path(path=cfg)}\n")
    print(json.dumps(load_profile(path=cfg).public_dict(), indent=2, ensure_ascii=False))


def cmd_discover(args: argparse.Namespace) -> None:
    base_url = _pick(args.base_url, "DAOU_BASE_URL", None)
    if not base_url:
        _die("--base-url (or DAOU_BASE_URL) is required")
    print(f"Querying {base_url} (public, no auth) ...")
    try:
        print(json.dumps(BotClient.discover_company(base_url), indent=2, ensure_ascii=False))
    except Exception as e:
        _die(f"public company lookup failed: {e}")


def cmd_whoami(args: argparse.Namespace) -> None:
    client = _authed_client(args)
    try:
        print(json.dumps(client.identity.__dict__, indent=2, ensure_ascii=False))
    finally:
        client._client.close()


def cmd_rooms(args: argparse.Namespace) -> None:
    client = _authed_client(args)
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
        client._client.close()


def cmd_room_create(args: argparse.Namespace) -> None:
    client = _authed_client(args)
    try:
        users = [u.strip() for u in args.users.split(",") if u.strip()]
        room_id = client.create_room(users, room_name=args.name, room_type=args.type)
        print(f"created room: {room_id}")
    finally:
        client._client.close()


def cmd_room_open(args: argparse.Namespace) -> None:
    client = _authed_client(args)
    try:
        data = client.open_room(args.room_id)
        print(json.dumps(data.model_dump(), indent=2, ensure_ascii=False))
    finally:
        client._client.close()


def cmd_send(args: argparse.Namespace) -> None:
    client = _authed_client(args)
    try:
        client.send_message(args.room_id, args.message)
        print(f"sent to {args.room_id}")
    finally:
        client._client.close()


def cmd_start(args: argparse.Namespace) -> None:
    prof, base_url, company_id = _settings(args)
    login_id = _pick(args.login_id, "DAOU_LOGIN_ID", prof.login_id if prof else None)
    password = _pick(args.password, "DAOU_PASSWORD", None)
    if not (login_id and password and company_id):
        _die("`start` needs login_id, password and company_id (flags/env)")
    bot = DaouBot(login_id, password, base_url=base_url, company_id=company_id)
    asyncio.run(bot.run_forever())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="daoubot", description="DaouOffice bot CLI")
    parser.add_argument(
        "--config",
        help="profile file path (default: ./.daoubot/profile.json); "
        "use a per-bot/tenant path for multiple accounts on one host",
    )
    parser.add_argument("--base-url", help="tenant URL (env DAOU_BASE_URL)")
    parser.add_argument("--company-id", help="tenant company id (env DAOU_COMPANY_ID)")
    parser.add_argument("--login-id", help="bot login id (env DAOU_LOGIN_ID)")
    parser.add_argument("--password", help="bot password (env DAOU_PASSWORD)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="authenticate and save .daoubot/profile.json")
    sub.add_parser("discover", help="look up company id / uuid / domain")
    sub.add_parser("whoami", help="print the saved bot identity")
    sub.add_parser("rooms", help="list chat rooms with their room ids")

    p_room = sub.add_parser("room", help="room operations").add_subparsers(
        dest="room_command", required=True
    )
    p_create = p_room.add_parser("create", help="create a chat room")
    p_create.add_argument("--users", required=True, help="comma-separated user ids")
    p_create.add_argument("--name", default=None)
    p_create.add_argument("--type", default="SINGLE", choices=("SINGLE", "GROUP"))
    p_open = p_room.add_parser("open", help="show room detail + members")
    p_open.add_argument("room_id")

    p_send = sub.add_parser("send", help="send a message to a room")
    p_send.add_argument("room_id")
    p_send.add_argument("message")

    sub.add_parser("start", help="run the polling bot (read-only without a handler)")
    return parser


def _dispatch(args: argparse.Namespace) -> None:
    if args.command == "room":
        {"create": cmd_room_create, "open": cmd_room_open}[args.room_command](args)
        return
    {
        "login": cmd_login,
        "discover": cmd_discover,
        "whoami": cmd_whoami,
        "rooms": cmd_rooms,
        "send": cmd_send,
        "start": cmd_start,
    }[args.command](args)


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        _dispatch(args)
    except (DaouConfigError, DaouAuthError) as e:
        _die(str(e))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
