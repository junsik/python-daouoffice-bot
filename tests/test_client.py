"""Tests for the REST client: config, login, identity, room/message ops."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from daouoffice.client import (
    BotClient,
    ChatHistoryItem,
    DaouAuthError,
    DaouConfigError,
)

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
def test_discover_company_companylist() -> None:
    # Real shape: data.companyList[0].{companyId,uuid,...}
    route = respx.get("/api/portal/public/auth/company").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "companyList": [{"companyId": "11000000000", "uuid": "U", "name": "Acme"}]
                }
            },
        )
    )
    info = BotClient.discover_company(BASE)
    assert info["companyId"] == "11000000000"
    # Regression: the public endpoint 400s without the tenant host header.
    assert route.calls.last.request.headers["X-Referer-Info"] == "acme.daouoffice.com"


@respx.mock
def test_auto_relogin_on_401() -> None:
    _login_routes(respx.mock)
    # First rooms call 401s, then succeeds after re-login.
    route = respx.get("/api/chat/room").mock(
        side_effect=[
            httpx.Response(401, json={"code": "ROUTE-0004", "message": "Invalid token"}),
            httpx.Response(200, json={"data": {"elements": [{"roomId": "r1"}]}}),
        ]
    )
    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    client.login()
    rooms = client.get_rooms()
    assert rooms[0].roomId == "r1"
    assert route.call_count > 1  # retried after re-auth


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


@respx.mock
def test_send_file_uploads_then_attaches(tmp_path) -> None:
    _login_routes(respx.mock)
    upload = respx.post("/api/upload/attach/app").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "filePath": "U/20260518/abc",
                    "fileName": "news.md",
                    "fileSize": 12,
                    "fileExtension": "md",
                }
            },
        )
    )
    msg = respx.post("/api/chat/message").mock(
        return_value=httpx.Response(200, json={"data": {"cmid": "c9"}})
    )
    f = tmp_path / "news.md"
    f.write_text("# hi", encoding="utf-8")

    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    client.login()
    assert client.send_file("r1", f, "뉴스레터") == "c9"

    assert upload.called and msg.called
    body = json.loads(msg.calls.last.request.content)
    att = body["content"]["attachmentList"][0]
    assert att["filePath"] == "U/20260518/abc"
    assert att["fileName"] == "news.md"
    assert att["fileStatus"] == "UPLOADED"
    # sender is the resolved bot identity, not hard-coded
    assert att["sender"]["platformUserId"] == "42"
    assert att["sender"]["companyUuid"] == "ACME-UUID"


def test_attachment_url_built_from_attachment_id() -> None:
    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    url = client.attachment_url({"attachmentId": 1506173980288004096})
    assert url == f"{BASE}/api/chat/attachment/1506173980288004096/download"


def test_attachment_url_rejects_unsendable_placeholder_id() -> None:
    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    # -1 is the outbound placeholder, never a real inbound attachment.
    with pytest.raises(ValueError):
        client.attachment_url({"attachmentId": -1})


@respx.mock
def test_download_attachment_writes_file(tmp_path) -> None:
    _login_routes(respx.mock)
    respx.get("/api/chat/attachment/999/download").mock(
        return_value=httpx.Response(
            200,
            content=b"# hello",
            headers={
                "content-disposition": "attachment; filename=\"x.md\"; "
                "filename*=UTF-8''%EB%A9%94%EB%AA%A8.md",
            },
        )
    )
    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    client.login()

    # fileName from the attachment entry wins over the header.
    out = client.download_attachment(
        {"attachmentId": 999, "fileName": "report.md"}, tmp_path
    )
    assert out == tmp_path / "report.md"
    assert out.read_bytes() == b"# hello"

    # No fileName → fall back to the RFC 5987 header (percent-decoded).
    out2 = client.download_attachment({"attachmentId": 999}, tmp_path)
    assert out2.name == "메모.md"


def test_chat_history_item_tolerates_null_fields() -> None:
    # System/empty messages (e.g. member-left notices) arrive with
    # contents/sender/metadata == null; the model must not reject them.
    item = ChatHistoryItem(
        chatRoomId="r1",
        chatMessageId=42,
        sender=None,
        contents=None,
        metadata=None,
        messageStatus=None,
    )
    assert item.sender == {}
    assert item.contents == {}
    assert item.metadata == {}
    assert item.messageStatus == ""
