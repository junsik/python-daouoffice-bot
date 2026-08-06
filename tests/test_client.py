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
    OrganizationMember,
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


def _login_routes_with_refresh(mock: respx.MockRouter) -> respx.Route:
    """Login mock that also issues a RefreshToken (the real server does);
    returns the login route so the caller can count re-login attempts."""
    login = mock.post("/api/portal/public/auth/login").mock(
        return_value=httpx.Response(
            200,
            json={"code": "SUCCESS-0000"},
            headers=[
                ("set-cookie", "AccessToken=acc-1; Path=/"),
                ("set-cookie", "RefreshToken=rfr-1; Path=/"),
            ],
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
    return login


@respx.mock
def test_refresh_endpoint_mints_new_access_token_with_url_body() -> None:
    _login_routes_with_refresh(respx.mock)
    refresh = respx.post("/api/portal/public/auth/refresh/login").mock(
        return_value=httpx.Response(
            200,
            json={"data": "OK"},
            headers={"set-cookie": "AccessToken=acc-2; Path=/"},
        )
    )
    rooms = respx.get("/api/chat/room").mock(
        side_effect=[
            httpx.Response(401, json={"code": "ROUTE-0004"}),
            httpx.Response(200, json={"data": {"elements": [{"roomId": "r1"}]}}),
        ]
    )
    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    client.login()
    assert client.refresh_token == "rfr-1"  # captured at login

    assert client.get_rooms()[0].roomId == "r1"
    assert refresh.called  # cheap refresh used, not full re-login
    # Body is the absolute URL of the failed request (capture wire shape).
    body = refresh.calls.last.request.content
    assert body == f"{BASE}/api/chat/room".encode()
    assert refresh.calls.last.request.headers["content-type"] == "application/json"
    # Cookie carries both tokens so the refresh endpoint can authenticate.
    cookie = refresh.calls.last.request.headers["cookie"]
    assert "AccessToken=acc-1" in cookie and "RefreshToken=rfr-1" in cookie
    assert client.access_token == "acc-2"  # rotated
    assert rooms.call_count == 2  # original + retry


@respx.mock
def test_refresh_failure_falls_back_to_full_relogin() -> None:
    login = _login_routes_with_refresh(respx.mock)
    # Refresh endpoint rejects → SDK must re-login with the password.
    refresh = respx.post("/api/portal/public/auth/refresh/login").mock(
        return_value=httpx.Response(401, json={"code": "ROUTE-0004"})
    )
    respx.get("/api/chat/room").mock(
        side_effect=[
            httpx.Response(401, json={"code": "ROUTE-0004"}),
            httpx.Response(200, json={"data": {"elements": [{"roomId": "r1"}]}}),
        ]
    )
    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    client.login()
    assert client.get_rooms()[0].roomId == "r1"
    assert refresh.called  # tried refresh first
    assert login.call_count == 2  # then full re-login (initial + fallback)


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
def test_mark_read_sends_chat_room_id_body() -> None:
    # The {"chatRoomId": ...} body is mandatory: without it the server
    # answers 200 but never registers the read (no receipt).
    _login_routes(respx.mock)
    route = respx.post("/api/chat/message/555/read").mock(
        return_value=httpx.Response(
            200, json={"code": "SUCCESS-0000", "data": {"readMessageId": "555"}}
        )
    )
    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    client.login()

    client.mark_read(555, "room-9")
    assert route.called
    assert json.loads(route.calls.last.request.content) == {"chatRoomId": "room-9"}


@respx.mock
def test_send_message_reply_to_sets_parent_chat_message_id() -> None:
    _login_routes(respx.mock)
    route = respx.post("/api/chat/message").mock(
        return_value=httpx.Response(200, json={"data": {"cmid": "c2"}})
    )
    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    client.login()

    assert client.send_message("r1", "answer", reply_to="987654321") == "c2"
    body = json.loads(route.calls.last.request.content)
    assert body["content"]["message"] == "answer"
    assert body["content"]["parentChatMessageId"] == "987654321"

    # No reply_to → field absent (a plain message, not a threaded reply).
    client.send_message("r1", "plain")
    plain = json.loads(route.calls.last.request.content)
    assert "parentChatMessageId" not in plain["content"]


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
                "content-disposition": 'attachment; filename="x.md"; '
                "filename*=UTF-8''%EB%A9%94%EB%AA%A8.md",
            },
        )
    )
    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    client.login()

    # fileName from the attachment entry wins over the header.
    out = client.download_attachment({"attachmentId": 999, "fileName": "report.md"}, tmp_path)
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


# Capture-shaped fixture mirroring the real
# /api/portal/common/organization/tree?targetUserId=... response: the tree
# has nested COMPANY -> DEPARTMENT -> MEMBER nodes, and MEMBER nodes can
# also appear at sibling depths.
_ORG_TREE_RESPONSE = {
    "data": {
        "elements": [
            {
                "id": "C1",
                "name": "Acme Corp",
                "nodeType": "COMPANY",
                "childrenList": [
                    {
                        "id": "D1",
                        "name": "Engineering",
                        "nodeType": "DEPARTMENT",
                        "childrenList": [
                            {
                                "id": "M1",
                                "name": "Junsik Park",
                                "nodeType": "MEMBER",
                                "userId": "11000022612",
                                "loginId": "junsik.park",
                                "email": "junsik.park@acme.co.kr",
                                "userStatus": "NORMAL",
                                "employeeNumber": "2315",
                                "positionName": "부장",
                                "dutyName": "팀장",
                                "departmentId": "D1",
                                "departmentName": "Engineering",
                                "departmentNamePath": "Acme Corp > Engineering",
                                "profileImagePath": "OPERATION/abc.png",
                            },
                            {
                                "id": "M2",
                                "name": "Kyunghern Lee",
                                "nodeType": "MEMBER",
                                "userId": "11000022611",
                                "loginId": "kyunghern.lee",
                                "email": "kyunghern.lee@acme.co.kr",
                                "userStatus": "NORMAL",
                                "employeeNumber": None,
                                "positionName": "마스터",
                                "dutyName": None,
                                "departmentId": "D1",
                                "departmentName": "Engineering",
                                "departmentNamePath": "Acme Corp > Engineering",
                                "profileImagePath": None,
                            },
                        ],
                    },
                ],
            },
        ],
    },
}


@respx.mock
def test_get_user_walks_org_tree_and_returns_member() -> None:
    _login_routes(respx.mock)
    route = respx.get("/api/portal/common/organization/tree").mock(
        return_value=httpx.Response(200, json=_ORG_TREE_RESPONSE)
    )
    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    client.login()

    member = client.get_user("11000022612")

    assert member is not None
    assert member.userId == "11000022612"
    assert member.loginId == "junsik.park"
    assert member.email == "junsik.park@acme.co.kr"
    assert member.name == "Junsik Park"
    assert member.departmentNamePath == "Acme Corp > Engineering"
    # targetUserId pins the response to the requested user
    request = route.calls.last.request
    assert request.url.params["targetUserId"] == "11000022612"
    assert request.url.params["shouldApplyOrganizationChartExpansion"] == "true"


@respx.mock
def test_get_user_returns_none_when_user_absent() -> None:
    _login_routes(respx.mock)
    respx.get("/api/portal/common/organization/tree").mock(
        return_value=httpx.Response(200, json=_ORG_TREE_RESPONSE)
    )
    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    client.login()

    assert client.get_user("99999999999") is None


def test_get_user_rejects_empty_id() -> None:
    client = BotClient("u", "p", base_url=BASE)
    assert client.get_user("") is None


@respx.mock
def test_get_user_peers_returns_all_member_nodes() -> None:
    _login_routes(respx.mock)
    respx.get("/api/portal/common/organization/tree").mock(
        return_value=httpx.Response(200, json=_ORG_TREE_RESPONSE)
    )
    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    client.login()

    peers = client.get_user_peers("11000022612")

    assert {p.userId for p in peers} == {"11000022612", "11000022611"}


def test_organization_member_tolerates_null_strings() -> None:
    # The capture has dutyName/employeeNumber/profileImagePath as JSON null;
    # the model must accept those and coerce strings to "" where appropriate.
    member = OrganizationMember.model_validate(
        {
            "userId": "U1",
            "loginId": None,
            "name": None,
            "email": None,
            "userStatus": None,
            "employeeNumber": None,
            "positionName": None,
            "dutyName": None,
            "departmentId": None,
            "departmentName": None,
            "departmentNamePath": None,
            "profileImagePath": None,
        }
    )
    assert member.userId == "U1"
    assert member.loginId == ""
    assert member.email == ""
    assert member.employeeNumber is None
    assert member.profileImagePath is None


# --- get_organization_members -------------------------------------------

_ROOT_TREE = {
    "data": {
        "elements": [
            {
                "nodeType": "COMPANY",
                "childrenList": [
                    {"nodeType": "DEPARTMENT", "departmentId": "D1", "name": "Data"},
                    {"nodeType": "DEPARTMENT", "departmentId": "D2", "name": "Sales"},
                ],
                "unspecifiedMemberList": [
                    {"nodeType": "MEMBER", "userId": "U0", "name": "Unfiled"}
                ],
            }
        ]
    }
}
_DEPARTMENT_TREES = {
    "D1": {
        "data": {
            "elements": [
                {
                    "nodeType": "DEPARTMENT",
                    "departmentId": "D1",
                    "childrenList": [
                        {"nodeType": "MEMBER", "userId": "U1", "name": "Ada"},
                        {"nodeType": "DEPARTMENT", "departmentId": "D3"},
                    ],
                }
            ]
        }
    },
    "D2": {
        "data": {
            "elements": [
                {
                    "nodeType": "DEPARTMENT",
                    "departmentId": "D2",
                    # Ada is seconded here too; she must be counted once.
                    "childrenList": [{"nodeType": "MEMBER", "userId": "U1", "name": "Ada"}],
                }
            ]
        }
    },
    "D3": {
        "data": {
            "elements": [
                {
                    "nodeType": "DEPARTMENT",
                    "departmentId": "D3",
                    "childrenList": [{"nodeType": "MEMBER", "userId": "U2", "name": "Grace"}],
                }
            ]
        }
    },
}


def _organization_routes() -> list[str]:
    """Serve the root tree and each department tree; record what was asked."""
    asked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        department = request.url.params.get("rootDepartmentId", "")
        asked.append(department)
        return httpx.Response(200, json=_DEPARTMENT_TREES.get(department, _ROOT_TREE))

    respx.get("/api/portal/common/organization/tree").mock(side_effect=handler)
    return asked


@respx.mock
def test_get_organization_members_walks_every_department() -> None:
    _login_routes(respx.mock)
    _organization_routes()
    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    client.login()

    members = client.get_organization_members()

    assert {member.userId for member in members} == {"U0", "U1", "U2"}


@respx.mock
def test_get_organization_members_counts_a_seconded_person_once() -> None:
    _login_routes(respx.mock)
    _organization_routes()
    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    client.login()

    members = client.get_organization_members()

    assert [member.userId for member in members].count("U1") == 1


@respx.mock
def test_get_organization_members_visits_each_department_once() -> None:
    _login_routes(respx.mock)
    asked = _organization_routes()
    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    client.login()

    client.get_organization_members()

    assert asked.count("D1") == 1
    assert asked.count("D2") == 1


@respx.mock
def test_get_organization_members_includes_people_without_a_department() -> None:
    _login_routes(respx.mock)
    _organization_routes()
    client = BotClient("acme-bot", "p", base_url=BASE, company_id="11000")
    client.login()

    members = client.get_organization_members()

    assert "U0" in {member.userId for member in members}
