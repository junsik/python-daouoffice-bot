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
import getpass
import json
import os
import sys
import unicodedata

import httpx

from daouoffice import BotClient, DaouBot
from daouoffice.client import DaouAuthError, DaouConfigError
from daouoffice.profile import Profile, load_profile, profile_path, save_profile


def _pick(flag: str | None, env: str, prof: str | None) -> str | None:
    """Resolve a setting: CLI flag > environment variable > profile."""
    return flag or os.getenv(env) or (prof or None)


def _fit(s: str, width: int) -> str:
    """Truncate/pad ``s`` to ``width`` *display* columns.

    CJK glyphs occupy two terminal columns, so plain ``str`` slicing and
    ``:width`` formatting misalign tables that mix Korean and ASCII. Measure
    by East Asian Width instead.
    """
    out: list[str] = []
    used = 0
    for ch in s:
        w = 2 if unicodedata.east_asian_width(ch) in "WF" else 1
        if used + w > width:
            break
        out.append(ch)
        used += w
    return "".join(out) + " " * (width - used)


def _die(msg: str, code: int = 2) -> None:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _resolve_password(args: argparse.Namespace, profile_pw: str | None = None) -> str | None:
    """Password: --password > DAOU_PASSWORD > saved profile > hidden prompt.

    The profile (chmod 600, gitignored) keeps the password so commands
    re-authenticate unattended when the token expires. Prompting (TTY) is the
    last resort — it keeps the secret out of argv (`ps` / shell history) and
    sidesteps shell quoting of special chars like ``!``.
    """
    pw = _pick(args.password, "DAOU_PASSWORD", profile_pw)
    if pw:
        return pw
    if sys.stdin.isatty():
        return getpass.getpass("DaouOffice password: ") or None
    return None


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
    """A logged-in client: reuse the saved token, else log in with creds.

    Any (re-)login persists the fresh token back to the profile via on_auth,
    so subsequent commands reuse it instead of re-authenticating.
    """
    prof, base_url, company_id = _settings(args)
    cfg = _cfg(args)

    def _persist(c: BotClient) -> None:
        _store(c, base_url, cfg)

    if prof and prof.access_token:
        client = BotClient.from_token(base_url, prof.access_token, on_auth=_persist)
        try:
            client.identity = client.whoami()
            return client
        except (httpx.HTTPError, DaouAuthError):
            print("saved session expired — re-authenticating...", file=sys.stderr)

    login_id = _pick(args.login_id, "DAOU_LOGIN_ID", prof.login_id if prof else None)
    password = _resolve_password(args, prof.password if prof else None)
    if not (login_id and company_id):
        _die("no profile found — run `daoubot login` first")
    if not password:
        _die(
            "session expired; password required to re-authenticate "
            "(set DAOU_PASSWORD or run interactively)"
        )
    client = BotClient(
        login_id, password, base_url=base_url, company_id=company_id, on_auth=_persist
    )
    client.login()
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
            password=client._password,
        ),
        path=config_path,
    )


# -- commands -----------------------------------------------------------


def cmd_login(args: argparse.Namespace) -> None:
    base_url = _pick(args.base_url, "DAOU_BASE_URL", None)
    if not base_url:
        _die("--base-url (or DAOU_BASE_URL) is required for login")
    login_id = _pick(args.login_id, "DAOU_LOGIN_ID", None)
    password = _resolve_password(args)
    if not (login_id and password):
        _die("--login-id and a password (flag/env/prompt) are required for login")

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
        print(f"\n{'#':>3}  {_fit('room name', 24)} {'type':6} {'mbr':>4} {'unread':>6}  room id")
        print("-" * 78)
        for i, r in enumerate(rooms, 1):
            rtype = {"SINGLE": "1:1", "GROUP": "group"}.get(r.roomType, r.roomType)
            print(
                f"{i:>3}  {_fit(r.roomName, 24)} {rtype:6} "
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
    cfg = _cfg(args)
    login_id = _pick(args.login_id, "DAOU_LOGIN_ID", prof.login_id if prof else None)
    password = _resolve_password(args, prof.password if prof else None)
    if not (login_id and password and company_id):
        _die("`start` needs login_id, a password (flag/env/profile) and company_id")
    client = BotClient(
        login_id,
        password,
        base_url=base_url,
        company_id=company_id,
        on_auth=lambda c: _store(c, base_url, cfg),  # persist refreshed token on 401 re-login
    )
    asyncio.run(DaouBot(client=client).run_forever())


def build_parser() -> argparse.ArgumentParser:
    # Connection options live on a shared parent applied to every
    # subcommand, so they work AFTER the subcommand
    # (`daoubot login --base-url ...`) — which is how all docs show it.
    # (argparse does not accept main-parser options after a subcommand.)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--config",
        help="profile file path (default: ./.daoubot/profile.json); "
        "use a per-bot/tenant path for multiple accounts on one host",
    )
    common.add_argument("--base-url", help="tenant URL (env DAOU_BASE_URL)")
    common.add_argument("--company-id", help="tenant company id (env DAOU_COMPANY_ID)")
    common.add_argument("--login-id", help="bot login id (env DAOU_LOGIN_ID)")
    common.add_argument(
        "--password",
        help="bot password (env DAOU_PASSWORD; omit to be prompted securely)",
    )

    parser = argparse.ArgumentParser(
        prog="daoubot",
        description="DaouOffice bot CLI — options go after the subcommand, "
        "e.g. `daoubot login --base-url ... --login-id ...`",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        return sub.add_parser(name, help=help_text, parents=[common])

    add("login", "authenticate and save the profile")
    add("discover", "look up company id / uuid / domain")
    add("whoami", "print the saved bot identity")
    add("rooms", "list chat rooms with their room ids")

    p_room = sub.add_parser("room", help="room operations").add_subparsers(
        dest="room_command", required=True
    )
    p_create = p_room.add_parser("create", help="create a chat room", parents=[common])
    p_create.add_argument("--users", required=True, help="comma-separated user ids")
    p_create.add_argument("--name", default=None)
    p_create.add_argument("--type", default="SINGLE", choices=("SINGLE", "GROUP"))
    p_open = p_room.add_parser("open", help="show room detail + members", parents=[common])
    p_open.add_argument("room_id")

    p_send = add("send", "send a message to a room")
    p_send.add_argument("room_id")
    p_send.add_argument("message")

    add("start", "run the polling bot (read-only without a handler)")
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
