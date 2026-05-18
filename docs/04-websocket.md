# 4. WebSocket / 실시간 (Real-time)

> ⚠️ **미검증 · 미구현.** 아래는 SAZ 캡처에서 관측된 엔드포인트/프레임의
> 역분석 *메모*일 뿐입니다. STOMP 핸드셰이크·구독·메시지 흐름을 실제로
> 검증하지 못했고, SDK에는 WebSocket 코드가 **없습니다**(추정 코드는 싣지
> 않음). 정식 경로는 REST 폴링입니다. 이 문서는 향후 작업용 참고 자료입니다.

## 4.1 WebSocket 연결 - GET /ws/pc

### Client → Server
```
GET /ws/pc HTTP/1.1
Host: yourcompany.daouoffice.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Version: 13
Sec-WebSocket-Key: CE+yzm0rAt8t7BVqPCtxyw==
Sec-WebSocket-Extensions: permessage-deflate; client_max_window_bits
Sec-WebSocket-Protocol: v12.stomp, v11.stomp, v10.stomp
Cookie: AccessToken=...; RefreshToken=...
```

### Server → Client
```
HTTP/1.1 101 Switching Protocols
Connection: Upgrade
Upgrade: websocket
Sec-WebSocket-Protocol: v12.stomp
Sec-WebSocket-Extensions: permessage-deflate;client_max_window_bits=15
```

### 프로토콜
- **STOMP over WebSocket** (STOMP v12)
- `permessage-deflate` 압축 지원

### WebSocket 메시지 구조 (예상)

**CONNECT (클라이언트 → 서버)**
```
CONNECT
cookie: AccessToken=...; RefreshToken=...
accept-version: 1.2
heart-beat: 10000,10000

^@^@
```

**CONNECTED (서버 → 클라이언트)**
```
CONNECTED
version: 1.2
heart-beat: 10000,10000
session: <session-id>

^@^@
```

**SUBSCRIBE (클라이언트 → 서버)**
```
SUBSCRIBE
id: sub-0
destination: /user/queue/messages
```

**MESSAGE (서버 → 클라이언트)**
```
MESSAGE
message-id: msg-0
destination: /user/queue/messages
content-type: application/json

{"type":"CHAT","roomId":"1505835441897709568","message":{...}}
```

---

## 4.2 상태 업데이트 (Keepalive) - POST /api/chat/user/status/connection

실시간 WebSocket 연결 유지 + 사용자 상태 확인

### Request
```json
{
  "platformUserIdList": [
    "11000000002", "11000000003", "11000000005", ...
  ]
}
```

### Response
```json
{
  "code": "SUCCESS-0000",
  "message": "성공",
  "data": {
    "connectionStatusDtoList": [
      {"platformUserId":"11000000002","connectionStatus":"ONLINE"},
      {"platformUserId":"11000000003","connectionStatus":"OFFLINE"},
      {"platformUserId":"11000000001","connectionStatus":"ABSENCE"}
    ]
  }
}
```

---

## 4.3 상태 값

| 값 | 의미 |
|---|---|
| `ONLINE` | 접속 중 |
| `OFFLINE` | 오프라인 |
| `ABSENCE` | 자리에 없음 |
