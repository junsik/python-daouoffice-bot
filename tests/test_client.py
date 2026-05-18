"""Tests for the REST client: config, login, identity, room/message ops."""

from __future__ import annotations

import httpx
import pytest
import respx

from daouoffice.client import BotClient, DaouAuthError, DaouConfigError

BASE = "https://acme.daouoffice.com"


def _login_routes(mock: respx.MockRouter) -> None:
    mock.post("/api/portal/public/auth/login").mock(
        return_value=httpx.Response(
            200,
            json={"code": "SUCCESS-0000"},
            headers={"set-cookie": "AccessToken=tok123; Path=/"},
        )
    )
    mock.post("/api/portal/graphql").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "me": {
                        "id": 42,
                        "name": "Acme Bot",
                        "loginId": "acme-bot",
                        "company": {
                            "id": 11000,
                            "uuid": "ACME-UUID",
                            "domain": "acme",
                            "name": "Acme",
                        },
                    }
                }
            },
        )
    )


def test_base_url_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DAOU_BASE_URL", raising=False)
    with pytest.raises(DaouConfigError, match="base_url"):
        BotClient("u", "p")


def test_base_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAOU_BASE_URL", BASE)
    client = BotClient("u", "p")
    assert client._base_url == BASE


def test_login_requires_company_id() -> None:
    client = BotClient("u", "p", base_url=BASE)
    with pytest.raises(DaouConfigError, match="company_id"):
        client.login()


@respx.mock
def test_login_resolves_identity() -> None:
    _login_routes(respx.mock)
    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    identity = client.login()
    assert identity.user_id == "42"
    assert identity.company_uuid == "ACME-UUID"
    assert client.user_id == "42"


@respx.mock
def test_login_failure_raises() -> None:
    respx.post("/api/portal/public/auth/login").mock(
        return_value=httpx.Response(200, json={"code": "FAIL-0001"})
    )
    client = BotClient("u", "p", base_url=BASE, company_id="1")
    with pytest.raises(DaouAuthError):
        client.login()


@respx.mock
def test_discover_company() -> None:
    respx.get("/api/portal/public/auth/company").mock(
        return_value=httpx.Response(200, json={"data": {"id": 11000, "uuid": "X"}})
    )
    info = BotClient.discover_company(BASE)
    assert info == {"id": 11000, "uuid": "X"}


@respx.mock
def test_get_rooms_and_send() -> None:
    _login_routes(respx.mock)
    respx.get("/api/chat/room").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"elements": [{"roomId": "r1", "roomName": "General"}]}},
        )
    )
    respx.post("/api/chat/message").mock(
        return_value=httpx.Response(200, json={"data": {"cmid": "c1"}})
    )
    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    client.login()
    rooms = client.get_rooms()
    assert rooms[0].roomId == "r1"
    assert client.send_message("r1", "hi") == "c1"
