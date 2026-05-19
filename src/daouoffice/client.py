"""DaouOffice Messenger Bot — REST API client layer.

DaouOffice is a multi-tenant SaaS: every company is served from its own
sub-domain (``https://<company>.daouoffice.com``) and identified by a numeric
``companyId``. Nothing in this module is hard-coded to a single tenant — the
base URL and company id are supplied by the caller (constructor argument or
environment variable). Use :meth:`BotClient.discover_company` /
:meth:`BotClient.whoami` (or the ``daoubot discover`` CLI) to look those values
up for your own account.

Unlike Telegram there is no BotFather: a "bot" is just a normal DaouOffice
account that an administrator issues for automation. You log in with that
account's id/password the same way the desktop messenger does.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

# DaouOffice PC messenger client User-Agent. The server gates the chat API on a
# messenger-looking UA, so we keep this shape by default; override if needed.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "dop-chat-front/4.3.3 Chrome/130.0.6723.137 "
    "Electron/33.2.1 Safari/537.36 DOP_PC_MESSENGER"
)


HTTP_OK = 200
HTTP_UNAUTHORIZED = 401


class DaouConfigError(ValueError):
    """Raised when required connection settings are missing."""


class DaouAuthError(RuntimeError):
    """Raised when login fails or the session is rejected."""


def _resolve(value: str | None, env: str) -> str | None:
    """Return ``value`` if set, otherwise fall back to environment ``env``."""
    if value:
        return value
    return os.getenv(env) or None


def _default_headers(base_url: str, user_agent: str) -> dict[str, str]:
    """Headers the DaouOffice server expects.

    ``X-Referer-Info`` is the tenant host; the unauthenticated public
    endpoints (e.g. ``/api/portal/public/auth/company``) use it to pick the
    tenant and return **400** without it (observed in the SAZ capture).
    """
    return {
        "User-Agent": user_agent,
        "X-Referer-Info": urlparse(base_url).hostname or "",
    }


# ============================================================
# Models
# ============================================================


class ChatRoomItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    roomId: str
    roomName: str = ""
    roomType: str = ""  # "SINGLE" | "GROUP"
    roomMemberCount: int = 0
    unreadMessageCount: int = 0
    roomPinFlag: bool = False
    backgroundColor: str | None = None
    latestMessage: dict | None = None

    @property
    def latest_message_id(self) -> int | None:
        """The room's newest message id, independent of the unread badge.

        The badge is cleared by ``mark_read`` (which the bot itself calls),
        so it cannot tell whether the cursor is caught up; this can.
        """
        try:
            return int((self.latestMessage or {}).get("chatMessageId"))
        except (TypeError, ValueError):
            return None


class ChatHistoryItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    chatRoomId: str = ""
    chatMessageId: int | str = ""
    createdAt: str = ""
    sender: dict = {}
    contents: dict = {}
    metadata: dict = {}
    messageStatus: dict | str = ""


class RoomOpenData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    memberList: list[dict] = []
    lastReadMessageId: str = ""
    roomName: str = ""
    roomType: str = ""
    lastSentMessage: dict | None = None
    roomPushFlag: bool = True
    roomPinFlag: bool = False
    inputLockFlag: bool = False
    messageHistoryOpenFlag: bool = False
    backgroundColor: str | None = None


# Inline mention token in content.message (see docs/api/03-messages.md §3.6):
#   {{<uuid>::USER::@<name>::<userId>}}   or   {{<uuid>::ALL::@ALL}}
_MENTION_RE = re.compile(
    r"\{\{[0-9a-fA-F-]+::(?P<type>USER|ALL)::@(?P<name>[^:}]+)(?:::(?P<uid>\d+))?\}\}"
)


def parse_mentions(text: str) -> tuple[str, list[str], bool]:
    """Parse mention tokens out of a raw message body.

    Returns ``(clean_text, mentioned_user_ids, mention_all)`` where
    ``clean_text`` has each token replaced by a human-readable ``@name``.
    """
    if not text or "{{" not in text:
        return text, [], False
    user_ids: list[str] = []
    mention_all = False

    def _sub(m: re.Match[str]) -> str:
        nonlocal mention_all
        if m.group("type") == "ALL":
            mention_all = True
        elif m.group("uid"):
            user_ids.append(m.group("uid"))
        return f"@{m.group('name')}"

    clean = _MENTION_RE.sub(_sub, text).strip()
    return clean, user_ids, mention_all


@dataclass(slots=True)
class NewMessage:
    """A single inbound chat message, normalized from the history payload.

    ``message_text`` is human-readable (mention tokens rendered as ``@name``);
    ``raw_text`` keeps the original wire text including ``{{...}}`` tokens.
    """

    room_id: str
    room_type: str
    sender_user_id: str
    sender_name: str
    message_text: str
    message_id: str
    created_at: str
    raw_text: str = ""
    mentions: list[str] = field(default_factory=list)
    mentions_me: bool = False
    mention_all: bool = False


@dataclass(slots=True)
class BotIdentity:
    """The logged-in account's own identity, resolved at login time."""

    user_id: str
    name: str
    login_id: str
    company_id: str
    company_uuid: str
    company_domain: str


# ============================================================
# BotClient
# ============================================================


class BotClient:
    """DaouOffice Messenger REST API client.

    Args:
        login_id: Bot account login id.
        password: Bot account password.
        base_url: Tenant base URL, e.g. ``https://acme.daouoffice.com``.
            Falls back to the ``DAOU_BASE_URL`` environment variable.
        company_id: Numeric tenant company id. Falls back to the
            ``DAOU_COMPANY_ID`` environment variable. Not required for
            :meth:`discover_company`, but required for :meth:`login`.
        user_agent: Override the messenger User-Agent if necessary.
        timeout: Per-request timeout in seconds.

    Raises:
        DaouConfigError: If ``base_url`` is not provided via argument or env.
    """

    def __init__(
        self,
        login_id: str,
        password: str,
        *,
        base_url: str | None = None,
        company_id: str | None = None,
        access_token: str = "",
        on_auth: Callable[[BotClient], None] | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 30.0,
    ) -> None:
        resolved_base = _resolve(base_url, "DAOU_BASE_URL")
        if not resolved_base:
            raise DaouConfigError(
                "base_url is required. Pass base_url=... or set the "
                "DAOU_BASE_URL environment variable "
                "(e.g. https://yourcompany.daouoffice.com)."
            )

        self._login_id = login_id
        self._password = password
        self._base_url = resolved_base.rstrip("/")
        self._company_id = _resolve(company_id, "DAOU_COMPANY_ID")
        self._client = httpx.Client(
            base_url=self._base_url,
            follow_redirects=True,
            http2=True,
            timeout=timeout,
            headers=_default_headers(self._base_url, user_agent),
        )
        self.access_token: str = access_token
        self.identity: BotIdentity | None = None
        # Called after every successful login() (initial or 401-triggered),
        # so the owner can persist the refreshed token + identity.
        self._on_auth = on_auth

    @classmethod
    def from_token(
        cls,
        base_url: str,
        access_token: str,
        *,
        on_auth: Callable[[BotClient], None] | None = None,
        timeout: float = 30.0,
    ) -> BotClient:
        """Build a client from a previously obtained token (skips login).

        Validate it with :meth:`whoami`; an expired token raises on use.
        Provide creds elsewhere (env) for the 401 path to self-recover.
        """
        return cls(
            "",
            "",
            base_url=base_url,
            access_token=access_token,
            on_auth=on_auth,
            timeout=timeout,
        )

    @property
    def user_id(self) -> str:
        """The bot account's own platform user id (set after :meth:`login`)."""
        return self.identity.user_id if self.identity else ""

    # -- Authentication -------------------------------------------------

    def login(self) -> BotIdentity:
        """Log in, store the access token, and resolve the bot's identity.

        Returns:
            The resolved :class:`BotIdentity`.

        Raises:
            DaouConfigError: If ``company_id`` is unknown.
            DaouAuthError: If the credentials are rejected.
        """
        if not self._company_id:
            raise DaouConfigError(
                "company_id is required to log in. Pass company_id=..., set "
                "DAOU_COMPANY_ID, or run `daoubot discover` to look it up."
            )

        resp = self._client.post(
            "/api/portal/public/auth/login",
            json={
                "companyId": self._company_id,
                "loginId": self._login_id,
                "password": self._password,
                "captcha": "",
            },
        )
        if resp.status_code != HTTP_OK:
            raise DaouAuthError(f"Login HTTP {resp.status_code}: {resp.text[:300]}")
        body = resp.json()
        logger.debug("Login response: %s", body)

        code = body.get("code", "")
        if not code and body.get("data") in ("OK", True):
            code = "SUCCESS-0000"
        if code != "SUCCESS-0000":
            raise DaouAuthError(f"Login failed: {code or body}")

        self.access_token = self._client.cookies.get("AccessToken", "")
        if not self.access_token:
            raise DaouAuthError("AccessToken cookie not present in login response")

        self.identity = self.whoami()
        logger.info(
            "Logged in as %s (user_id=%s, company=%s)",
            self.identity.login_id,
            self.identity.user_id,
            self.identity.company_domain or self._company_id,
        )
        if self._on_auth is not None:
            self._on_auth(self)  # persist the fresh token + identity
        return self.identity

    def get_auth_headers(self) -> dict[str, str]:
        return {"Cookie": f"AccessToken={self.access_token}"}

    def _can_relogin(self) -> bool:
        return bool(self._login_id and self._password and self._company_id)

    def _api(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Authenticated request; re-login once on a 401 if creds are known.

        The AccessToken lives ~30 minutes and there is no observed refresh
        endpoint, so a long-running bot recovers by re-authenticating. A fresh
        login is a new server session and does not disturb other sessions.
        """
        headers = {**kwargs.pop("headers", {}), **self.get_auth_headers()}
        resp = self._client.request(method, path, headers=headers, **kwargs)
        if resp.status_code == HTTP_UNAUTHORIZED:
            if not self._can_relogin():
                raise DaouAuthError(
                    "Session expired (401) and no credentials to re-authenticate. "
                    "Set DAOU_PASSWORD for unattended re-login, or run "
                    "`daoubot login` again. (A profile token alone cannot be "
                    "refreshed after ~30 minutes.)"
                )
            logger.info("401 (%s) — session expired, re-authenticating", path)
            self.login()  # persists the new token via on_auth
            headers = {**headers, **self.get_auth_headers()}
            resp = self._client.request(method, path, headers=headers, **kwargs)
        return resp

    def whoami(self) -> BotIdentity:
        """Resolve the logged-in account's own identity via GraphQL ``me``."""
        resp = self._client.post(
            "/api/portal/graphql",
            json={
                "operationName": "userSessionQuery",
                "query": (
                    "query userSessionQuery { me { id name loginId "
                    "company { id uuid domain name } } }"
                ),
                "variables": {},
            },
            headers=self.get_auth_headers(),
        )
        resp.raise_for_status()
        me = (resp.json().get("data") or {}).get("me") or {}
        company = me.get("company") or {}
        return BotIdentity(
            user_id=str(me.get("id", "")),
            name=me.get("name", ""),
            login_id=me.get("loginId", self._login_id),
            company_id=str(company.get("id", self._company_id or "")),
            company_uuid=company.get("uuid", ""),
            company_domain=company.get("domain", ""),
        )

    @classmethod
    def discover_company(cls, base_url: str, *, timeout: float = 15.0) -> dict:
        """Fetch tenant metadata from the public (no-auth) company endpoint.

        Useful for finding ``companyId`` from a bare tenant URL.
        """
        url = (base_url or "").rstrip("/")
        if not url:
            raise DaouConfigError("base_url is required for discover_company")
        with httpx.Client(
            base_url=url,
            follow_redirects=True,
            timeout=timeout,
            headers=_default_headers(url, DEFAULT_USER_AGENT),
        ) as client:
            resp = client.get("/api/portal/public/auth/company")
            resp.raise_for_status()
            body = resp.json()
        data = body.get("data", body) if isinstance(body, dict) else body
        # Response shape: {"data": {"companyList": [{companyId, uuid, ...}]}}
        if isinstance(data, dict) and data.get("companyList"):
            return data["companyList"][0]
        return data

    def logout(self) -> None:
        try:
            self._client.post(
                "/api/portal/common/auth/logout",
                headers=self.get_auth_headers(),
            )
        except Exception:
            pass
        finally:
            self._client.close()

    # -- Chat rooms -----------------------------------------------------

    def get_rooms(self, *, page: int = 0, size: int = 20) -> list[ChatRoomItem]:
        resp = self._api(
            "GET",
            "/api/chat/room",
            params={"pageNumber": page, "pageSize": size},
        )
        if resp.status_code != HTTP_OK:
            logger.error("get_rooms: %s %s", resp.status_code, resp.text[:300])
            resp.raise_for_status()
        elements = resp.json().get("data", {}).get("elements", [])
        return [ChatRoomItem(**item) for item in elements]

    def create_room(
        self,
        user_list: list[str],
        *,
        room_name: str | None = None,
        room_type: str = "SINGLE",
        background_color: str = "#00FFFF",
    ) -> str:
        """Create a chat room and return its ``roomId``."""
        body: dict = {
            "userList": user_list,
            "roomType": room_type,
            "backgroundColor": background_color,
        }
        if room_name:
            body["roomName"] = room_name
        resp = self._api("POST", "/api/chat/room", json=body)
        resp.raise_for_status()
        return resp.json()["data"]["roomId"]

    def open_room(self, room_id: str) -> RoomOpenData:
        resp = self._api("GET", f"/api/chat/room/{room_id}/open")
        resp.raise_for_status()
        return RoomOpenData(**resp.json()["data"])

    # -- Messages -------------------------------------------------------

    def send_message(
        self,
        room_id: str,
        content: str = "",
        *,
        attachments: list[dict] | None = None,
    ) -> str:
        """Send a message (optionally with uploaded attachments).

        ``attachments`` is a list of dicts returned by
        :meth:`upload_attachment`. Returns the client message id (``cmid``).
        """
        cmid = str(uuid.uuid4())
        body: dict = {"message": content}
        if attachments:
            body["attachmentList"] = [self._attachment_entry(a) for a in attachments]
        resp = self._api(
            "POST",
            "/api/chat/message",
            json={"chatRoomId": room_id, "cmid": cmid, "content": body},
        )
        resp.raise_for_status()
        return resp.json()["data"]["cmid"]

    def upload_attachment(self, path: str | os.PathLike[str]) -> dict:
        """Upload a file for chat and return its attachment metadata.

        The returned dict (server ``data``: ``filePath``/``fileName``/
        ``fileSize``/...) is passed to :meth:`send_message` via
        ``attachments=[...]`` or used by :meth:`send_file`.
        """
        p = Path(path)
        data = p.read_bytes()
        resp = self._api(
            "POST",
            "/api/upload/attach/app",
            params={"app-code": "dop-default-chat", "thumb-category": "attach"},
            files={"file": (p.name, data, "application/octet-stream")},
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def send_file(self, room_id: str, path: str | os.PathLike[str], content: str = "") -> str:
        """Upload ``path`` and post it to ``room_id`` as an attachment."""
        meta = self.upload_attachment(path)
        return self.send_message(room_id, content, attachments=[meta])

    def _attachment_entry(self, meta: dict) -> dict:
        """Build a chat ``attachmentList`` entry from upload metadata."""
        ident = self.identity
        sender = {
            "companyUuid": ident.company_uuid if ident else "",
            "platformUserId": ident.user_id if ident else "",
            "platformUserName": ident.name if ident else "",
            "profilePath": "",
        }
        return {
            "attachmentId": -1,
            "filePath": meta["filePath"],
            "fileType": "",
            "fileName": meta["fileName"],
            "fileSize": meta.get("fileSize", 0),
            "fileStatus": "UPLOADED",
            "sender": sender,
            "createdAt": datetime.now(UTC).isoformat(timespec="milliseconds"),
        }

    def get_chat_history(
        self, room_id: str, *, offset: int = 20, message_id: int = 0
    ) -> list[ChatHistoryItem]:
        resp = self._api(
            "GET",
            f"/api/chat/room/{room_id}/chat/range",
            params={"offset": offset, "messageId": message_id},
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        if isinstance(data, list):
            items = data
        else:
            items = data.get("items") or data.get("elements") or []
        return [ChatHistoryItem(**item) for item in items]

    def mark_read(self, message_id: int | str) -> None:
        self._api("POST", f"/api/chat/message/{message_id}/read")
