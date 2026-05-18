"""DaouOffice Messenger Bot - WebSocket handler for real-time messaging

SAZ 분석 결과:
  - EndPoint: GET /ws/pc
  - Protocol: STOMP v12 over WebSocket
  - Extensions: permessage-deflate

TODO: v2 에서 WebSocket/STOMP 실시간 기능 구현할 때 사용

NOTE: v0.1 에서는 REST API 폴링만 사용. WebSocket 관련 코드는 v2 에서 활성화.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

import websockets

logger = logging.getLogger(__name__)


# STOMP commands
CMD_CONNECT = "CONNECT"
CMD_CONNECTED = "CONNECTED"
CMD_SUBSCRIBE = "SUBSCRIBE"
CMD_SEND = "SEND"
CMD_BEGIN = "BEGIN"
CMD_COMMIT = "COMMIT"
CMD_ACK = "ACK"
CMD_DISCONNECT = "DISCONNECT"
CMD_STOMP = "STOMP"

CTL_DEL = "\x0c"


class StompFrame:
    """STOMP frame parser (v2 for WebSocket)"""

    @staticmethod
    def parse(text: str) -> dict:
        lines = text.split("\n")
        command = lines[0].strip()
        headers: dict[str, str] = {}
        i = 1
        while i < len(lines):
            line = lines[i].strip()
            if line == "":
                i += 1
                break
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()
            i += 1
        body = text[i:] if i < len(lines) else ""
        return {"command": command, "headers": headers, "body": body}

    @staticmethod
    def build(command: str, headers: dict | None = None, body: str = "") -> str:
        headers = headers or {}
        lines: list[str] = [command]
        for key, value in headers.items():
            lines.append(f"{key}:{value}")
        lines.append("")
        lines.append(body)
        lines.append(CTL_DEL)
        return "\n".join(lines)


class WebSocketClient:
    """STOMP over WebSocket client (v2 for real-time messaging)

    NOTE: v0.1 에서는 사용되지 않음. v2 에서 활성화予定.
    """

    WS_PATH = "/ws/pc"

    def __init__(
        self,
        ws_url: str,
        access_token: str,
        refresh_token: str,
        on_message=None,
        on_connected=None,
        on_error=None,
        heartbeat=(10000, 10000),
    ) -> None:
        # ws_url e.g. "wss://yourcompany.daouoffice.com/ws/pc"
        self._ws_url = ws_url
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._on_message = on_message
        self._on_connected = on_connected
        self._on_error = on_error
        self._heartbeat = heartbeat
        self._ws = None
        self._session_id = None
        self._running = False

    def _make_cookie(self) -> str:
        return f"AccessToken={self._access_token}; RefreshToken={self._refresh_token}"

    async def connect(self) -> None:
        cookie = self._make_cookie()
        subprotocols = ["v12.stomp", "v11.stomp", "v10.stomp"]
        self._ws = await websockets.connect(
            self._ws_url,
            subprotocols=subprotocols,
            additional_headers={"Cookie": cookie},
            close_timeout=5,
            extensions=[],
        )
        self._running = True
        logger.info("WebSocket connected")

        connect_frame = StompFrame.build(
            CMD_CONNECT,
            {
                "accept-version": "1.2",
                "heart-beat": f"{self._heartbeat[0]},{self._heartbeat[1]}",
                "cookie": cookie,
            },
        )
        await self._ws.send(connect_frame)
        logger.info("STOMP CONNECT sent")

    async def subscribe(self, destination: str, *, sub_id: str | None = None) -> str:
        if sub_id is None:
            sub_id = f"sub-{uuid.uuid4().hex[:8]}"
        frame = StompFrame.build(
            CMD_SUBSCRIBE,
            {"id": sub_id, "destination": destination, "ack": "client"},
        )
        await self._ws.send(frame)
        logger.info(f"Subscribed to {destination} (id={sub_id})")
        return sub_id

    async def disconnect(self) -> None:
        self._running = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
            logger.info("Disconnected")

    async def listen(self) -> None:
        if not self._ws:
            raise RuntimeError("Not connected")
        buffer = ""
        try:
            async for raw in self._ws:
                buffer += raw.decode("utf-8", errors="replace")
                while CTL_DEL in buffer:
                    frame_text, buffer = buffer.split(CTL_DEL, 1)
                    if not frame_text.strip():
                        continue
                    frame = StompFrame.parse(frame_text)
                    cmd = frame["command"]
                    headers = frame["headers"]
                    if cmd == CMD_CONNECTED:
                        self._session_id = headers.get("session")
                        if self._on_connected:
                            self._on_connected(self._session_id)
                    elif cmd == "MESSAGE":
                        await self._handle_message(headers, frame["body"].strip())
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket closed: {e}")
            if self._on_error:
                self._on_error(e)

    async def _handle_message(self, headers: dict, body: str) -> None:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON: {body[:200]}")
            return

        room_id = payload.get("roomId") or payload.get("chatRoomId") or ""
        message_data = payload.get("message") or payload.get("content") or {}
        sender = message_data.get("sender") or {}
        content = message_data.get("contents") or {}
        text_data = content.get("message") or content
        sender_id = sender.get("platformUserId", "")
        sender_name = sender.get("platformUserName", "")
        message_text = text_data.get("text", "") if isinstance(text_data, dict) else str(text_data)

        if not room_id or not message_text:
            return

        logger.info(f"[{room_id}] {sender_name}: {message_text[:100]}")
        if self._on_message:
            result = self._on_message(room_id, sender_id, sender_name, message_text, "")
            if asyncio.iscoroutine(result):
                await result
