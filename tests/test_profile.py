"""Tests for profile persistence and the CLI login flow."""

from __future__ import annotations

import argparse
import json

import httpx
import pytest
import respx

from daouoffice import cli
from daouoffice.cli import main as cli_main
from daouoffice.profile import Profile, load_profile, save_profile

BASE = "https://acme.daouoffice.com"


def test_save_load_roundtrip(tmp_path) -> None:
    p = Profile(base_url=BASE, company_id="11000", user_id="42", access_token="tok")
    path = save_profile(p, base_dir=tmp_path)
    assert path.exists()
    loaded = load_profile(base_dir=tmp_path)
    assert loaded is not None
    assert loaded.user_id == "42"
    assert loaded.access_token == "tok"
    assert loaded.saved_at  # stamped on save


def test_missing_profile_returns_none(tmp_path) -> None:
    assert load_profile(base_dir=tmp_path) is None


def test_explicit_path_overrides_default(tmp_path) -> None:
    fp = tmp_path / "bot-a.json"
    saved = save_profile(Profile(base_url=BASE, login_id="a"), path=fp)
    assert saved == fp and fp.exists()
    assert load_profile(path=fp).login_id == "a"
    # the default location is untouched
    assert load_profile(base_dir=tmp_path) is None


def test_public_dict_hides_token() -> None:
    p = Profile(base_url=BASE, access_token="secret")
    assert "access_token" not in p.public_dict()
    assert p.public_dict()["base_url"] == BASE


def test_load_ignores_unknown_keys(tmp_path) -> None:
    (tmp_path / ".daoubot").mkdir()
    (tmp_path / ".daoubot" / "profile.json").write_text(
        json.dumps({"base_url": BASE, "bogus": 1}), encoding="utf-8"
    )
    prof = load_profile(base_dir=tmp_path)
    assert prof is not None and prof.base_url == BASE


@respx.mock
def test_cli_login_writes_profile(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    respx.post("/api/portal/public/auth/login").mock(
        return_value=httpx.Response(
            200,
            json={"code": "SUCCESS-0000"},
            headers={"set-cookie": "AccessToken=tok123; Path=/"},
        )
    )
    respx.post("/api/portal/graphql").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "me": {
                        "id": 42,
                        "name": "Bot",
                        "loginId": "acme-bot",
                        "company": {"id": 11000, "uuid": "U", "domain": "acme"},
                    }
                }
            },
        )
    )
    cli_main(
        [
            "login",
            "--base-url",
            BASE,
            "--company-id",
            "11000",
            "--login-id",
            "acme-bot",
            "--password",
            "pw",
        ]
    )
    prof = load_profile(base_dir=tmp_path)
    assert prof is not None
    assert prof.user_id == "42" and prof.access_token == "tok123"
    # token must not be echoed to stdout
    assert "tok123" not in capsys.readouterr().out


@respx.mock
def test_cli_config_path_isolates_profiles(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    respx.post("/api/portal/public/auth/login").mock(
        return_value=httpx.Response(
            200,
            json={"code": "SUCCESS-0000"},
            headers={"set-cookie": "AccessToken=tokA; Path=/"},
        )
    )
    respx.post("/api/portal/graphql").mock(
        return_value=httpx.Response(
            200, json={"data": {"me": {"id": 7, "loginId": "a", "company": {"id": 11000}}}}
        )
    )
    cfg = tmp_path / "bot-a.json"
    cli_main(
        [
            "login",
            "--config",
            str(cfg),
            "--base-url",
            BASE,
            "--company-id",
            "11000",
            "--login-id",
            "a",
            "--password",
            "pw",
        ]
    )
    # written to the --config path, NOT the default ./.daoubot/profile.json
    assert cfg.exists()
    assert load_profile(base_dir=tmp_path) is None
    assert load_profile(path=cfg).user_id == "7"


@respx.mock
def test_cli_rooms_reuses_saved_token(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    save_profile(
        Profile(base_url=BASE, company_id="11000", access_token="tok"),
        base_dir=tmp_path,
    )
    respx.post("/api/portal/graphql").mock(
        return_value=httpx.Response(200, json={"data": {"me": {"id": 1}}})
    )
    rooms = respx.get("/api/chat/room").mock(
        return_value=httpx.Response(200, json={"data": {"elements": []}})
    )
    cli_main(["rooms"])
    assert rooms.called  # used the saved token, no re-login


def test_cli_rooms_without_profile_errors(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DAOU_BASE_URL", raising=False)
    with pytest.raises(SystemExit):
        cli_main(["rooms"])


def test_options_parse_after_subcommand() -> None:
    # Regression: connection options must be accepted AFTER the subcommand,
    # exactly as every doc shows (`daoubot login --base-url ...`).
    p = cli.build_parser()
    ns = p.parse_args(
        [
            "login",
            "--base-url",
            "https://x.daouoffice.com",
            "--login-id",
            "b",
            "--password",
            "p!@#",
        ]
    )
    assert ns.command == "login" and ns.base_url == "https://x.daouoffice.com"
    assert ns.password == "p!@#"
    ns2 = p.parse_args(["rooms", "--config", "bots/a.json"])
    assert ns2.command == "rooms" and ns2.config == "bots/a.json"
    ns3 = p.parse_args(["room", "create", "--users", "1,2", "--base-url", "https://x"])
    assert ns3.command == "room" and ns3.room_command == "create"
    assert ns3.base_url == "https://x"


def test_resolve_password_flag_env_prompt(monkeypatch) -> None:
    monkeypatch.delenv("DAOU_PASSWORD", raising=False)
    ns = argparse.Namespace(password="p!@#")
    assert cli._resolve_password(ns) == "p!@#"  # flag wins, special chars fine

    ns = argparse.Namespace(password=None)
    monkeypatch.setenv("DAOU_PASSWORD", "envpw")
    assert cli._resolve_password(ns) == "envpw"

    monkeypatch.delenv("DAOU_PASSWORD", raising=False)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt="": "typed-secret")
    assert cli._resolve_password(argparse.Namespace(password=None)) == "typed-secret"

    # non-TTY, nothing provided → None (caller errors clearly)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    assert cli._resolve_password(argparse.Namespace(password=None)) is None
