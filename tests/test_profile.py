"""Tests for profile persistence and the CLI login flow."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

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
            "--base-url",
            BASE,
            "--company-id",
            "11000",
            "--login-id",
            "acme-bot",
            "--password",
            "pw",
            "login",
        ]
    )
    prof = load_profile(base_dir=tmp_path)
    assert prof is not None
    assert prof.user_id == "42" and prof.access_token == "tok123"
    # token must not be echoed to stdout
    assert "tok123" not in capsys.readouterr().out


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
