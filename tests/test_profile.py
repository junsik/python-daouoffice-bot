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


@pytest.fixture(autouse=True)
def _home_in_tmp(monkeypatch, tmp_path):
    # Profile/cursors default to ~/.daoubot/; anchor HOME at tmp_path so a
    # test never reads or clobbers the developer's real profile.
    monkeypatch.setattr("daouoffice.profile.Path.home", lambda: tmp_path)


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


def test_public_dict_masks_secrets() -> None:
    p = Profile(base_url=BASE, access_token="tok-secret", password="pw-secret")
    d = p.public_dict()
    assert d["base_url"] == BASE
    assert d["access_token"] == "****" and d["password"] == "****"
    assert "tok-secret" not in d.values() and "pw-secret" not in d.values()


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
    # password is persisted so the bot can re-authenticate unattended
    assert prof.password == "pw"
    # but neither secret is echoed to stdout (masked as ****)
    out = capsys.readouterr().out
    assert "tok123" not in out and "pw" not in out and "****" in out


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
    # written to the --config path, NOT the default ~/.daoubot/profile.json
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


@respx.mock
def test_cli_whoami_prints_identity(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    save_profile(
        Profile(base_url=BASE, company_id="11000", access_token="tok"),
        base_dir=tmp_path,
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
    # Regression: BotIdentity is a slots dataclass (no __dict__); whoami
    # must serialize it without AttributeError.
    cli_main(["whoami"])
    out = json.loads(capsys.readouterr().out)
    assert out["user_id"] == "42" and out["login_id"] == "acme-bot"


def test_cli_config_show_masks_and_set_persists(tmp_path, capsys) -> None:
    save_profile(
        Profile(base_url=BASE, login_id="bot", access_token="tok", password="pw"),
        base_dir=tmp_path,
    )

    # `config` (no action) → show, secrets masked, no plaintext leak
    cli_main(["config"])
    shown = json.loads(capsys.readouterr().out)
    assert shown["base_url"] == BASE
    assert shown["access_token"] == "****" and shown["password"] == "****"
    assert "pw" not in shown.values() and "tok" not in shown.values()

    # `config path` → the profile file location (YAML form)
    cli_main(["config", "path"])
    assert "profile.yaml" in capsys.readouterr().out

    # `config set` persists an editable field
    cli_main(["config", "set", "company_id", "99999"])
    capsys.readouterr()
    assert load_profile(base_dir=tmp_path).company_id == "99999"


def test_cli_config_set_password_prompts_when_value_omitted(tmp_path, monkeypatch) -> None:
    save_profile(Profile(base_url=BASE, login_id="bot"), base_dir=tmp_path)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli.getpass, "getpass", lambda _p="": "typed-pw")
    cli_main(["config", "set", "password"])  # no value → hidden prompt
    assert load_profile(base_dir=tmp_path).password == "typed-pw"


def test_cli_config_without_profile_errors(tmp_path) -> None:
    with pytest.raises(SystemExit):
        cli_main(["config"])


@respx.mock
def test_cli_auto_relogins_from_saved_password(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    save_profile(
        Profile(
            base_url=BASE,
            company_id="11000",
            login_id="acme-bot",
            access_token="expired",
            password="pw",
        ),
        base_dir=tmp_path,
    )
    # The saved token is dead → whoami 401.
    respx.post("/api/portal/graphql").mock(
        side_effect=[
            httpx.Response(401, json={"code": "ROUTE-0004"}),
            httpx.Response(200, json={"data": {"me": {"id": 1, "loginId": "acme-bot"}}}),
        ]
    )
    login = respx.post("/api/portal/public/auth/login").mock(
        return_value=httpx.Response(
            200,
            json={"code": "SUCCESS-0000"},
            headers={"set-cookie": "AccessToken=fresh; Path=/"},
        )
    )
    rooms = respx.get("/api/chat/room").mock(
        return_value=httpx.Response(200, json={"data": {"elements": []}})
    )

    def _no_prompt(*_a, **_k):  # must NOT prompt — password is saved
        raise AssertionError("getpass called; should auto-relogin from profile")

    monkeypatch.setattr(cli.getpass, "getpass", _no_prompt)

    cli_main(["rooms"])

    assert login.called and rooms.called
    # the refreshed token is written back, keeping the password
    prof = load_profile(base_dir=tmp_path)
    assert prof.access_token == "fresh" and prof.password == "pw"


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


def test_resolve_login_id_flag_env_prompt(monkeypatch) -> None:
    monkeypatch.delenv("DAOU_LOGIN_ID", raising=False)
    assert cli._resolve_login_id(argparse.Namespace(login_id="bot")) == "bot"

    monkeypatch.setenv("DAOU_LOGIN_ID", "envbot")
    assert cli._resolve_login_id(argparse.Namespace(login_id=None)) == "envbot"

    monkeypatch.delenv("DAOU_LOGIN_ID", raising=False)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "  typed-bot  ")
    assert cli._resolve_login_id(argparse.Namespace(login_id=None)) == "typed-bot"

    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    assert cli._resolve_login_id(argparse.Namespace(login_id=None)) is None


def test_login_missing_login_id_errors_before_password_prompt(monkeypatch) -> None:
    # `daoubot login --base-url X` (no login id): must fail clearly on the
    # missing login id, NOT prompt for a password first.
    for k in ("DAOU_LOGIN_ID", "DAOU_PASSWORD", "DAOU_COMPANY_ID"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)

    def _no_password(*_a, **_k):
        raise AssertionError("password prompted before login id was resolved")

    monkeypatch.setattr(cli.getpass, "getpass", _no_password)
    with pytest.raises(SystemExit):
        cli_main(["login", "--base-url", BASE])
