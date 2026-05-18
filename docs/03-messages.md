# 3. 메시지 (Chat Messages)

## 3.1 메시지 전송 - POST /api/chat/message

### Request
```json
{
  "chatRoomId": "1505835441897709568",
  "cmid": "a6ee32d1-93f6-412c-8e1d-6515dee26171",
  "content": {"message": "메시지 내용"}
}
```

### Response
```json
{
  "code": "SUCCESS-0000",
  "message": "성공",
  "data": {
    "cmid": "a6ee32d1-93f6-412c-8e1d-6515dee26171"
  }
}
```

---

## 3.2 메시지 히스토리 조회 - GET /api/chat/room/{roomId}/chat/range

### Request
```
GET /api/chat/room/1505835441897709568/chat/range?offset=20&messageId=0
```

| 파라미터 | 설명 |
|---|---|
| `offset` | 가져올 메시지 수 (기본 20) |
| `messageId` | 기준 메시지 ID (0이면 최신부터 조회) |

### Response
```json
{
  "data": {
    "items": [
      {
        "metadata": {
          "messageType": "CHAT",
          "subType": "TEXT",
          "action": "REPLY",
          "templateType": "NORMAL"
        },
        "chatRoomId": "1505835441897709568",
        "sender": {
          "platformUserId": "11000000003",
          "platformUserName": "임꺽정",
          "profilePath": "...",
          "positionName": "부장"
        },
        "chatMessageId": 1505833539940147200,
        "createdAt": "2026-05-18T16:24:52.000+09:00",
        "contents": {
          "message": {
            "text": "메시지 내용",
            "plainText": "메시지 내용"
          }
        },
        "messageStatus": {
          "read": false
        }
      }
    ]
  }
}
```

### messageType / subType
| messageType | subType | 의미 |
|---|---|---|
| `CHAT` | `TEXT` | 텍스트 메시지 |
| `CHAT` | `IMAGE` | 이미지 |
| `CHAT` | `FILE` | 파일 |
| `CHAT` | `EMOTICON` | 이모티콘 |
| `SYSTEM` | - | 시스템 메시지 |

---

## 3.3 읽음 처리 - POST /api/chat/message/{messageId}/read

### Request
```
POST /api/chat/message/1505835490224381952/read
Cookie: AccessToken=...
```

### Response
```json
{"code":"SUCCESS-0000","message":"성공"}
```

---

## 3.4 이모티콘 반응 - POST /api/chat/message/emoticon

### Request
```json
{
  "chatRoomId": "1505835441897709568",
  "cmid": "a6ee32d1-93f6-412c-8e1d-6515dee26171",
  "content": {"message": "(아하_다다)"}
}
```

---

## 3.5 메시지 검색 - GET /api/chat/search/message

### Request
```
GET /api/chat/search/message?previousLastId=0&sliceSize=80
  &periodType=ENTIRE
  &startDate=2026-01-01
  &endDate=2026-05-18&keyword=검색어
Cookie: AccessToken=...
```

---

## 3.6 멘션(Mention) 인코딩

SAZ 캡처 분석으로 확정. 멘션은 **별도 구조 필드가 아니라 `content.message`
본문 안의 인라인 토큰**이다. 방 전체가 같은 메시지를 받고, 멘션된 사용자만
하이라이트/알림된다 — 특정 사용자에게만 보이는 비공개 전달이 아니다.

### 토큰 형식

특정 사용자:
```
{{<UUID>::USER::@<표시이름>::<platformUserId>}} 본문
```
전체 멘션(@전체):
```
{{<UUID>::ALL::@ALL}} 본문
```

- `{{ }}` 델리미터, 필드 구분자 `::`
- 타입: `USER` | `ALL` (검색 API의 `mentionTypeList=USER,ALL` 와 대응)
- `USER` 일 때만 4번째 필드에 숫자 `platformUserId`
- 토큰은 보통 메시지 맨 앞이지만 위치는 보장되지 않음 — 정규식으로 파싱하고
  접두어로 가정하지 말 것
- 별도의 `mentionedUsers` / `mentionList` JSON 필드는 없음

### 송신 예 (POST /api/chat/message)
```json
{
  "chatRoomId": "<ROOM_ID>",
  "cmid": "<UUID>",
  "content": {"message": "{{<UUID>::USER::@<표시이름>::<platformUserId>}} 멘션!"}
}
```

수신 시 `chat/range`·실시간 페이로드의 `contents.message.text` 에 동일 토큰이
그대로 들어온다.

### 관련 검색 API

`GET /api/chat/search/message?...&mentionTypeList=ALL&mentionTypeList=USER`
— "나를 멘션한 메시지" 서버측 검색. 효율적 멘션 전용 폴링에 활용 가능(현재 SDK는
본문 토큰 파싱으로 처리).

> SDK는 이 토큰을 파싱해 `NewMessage.mentions` / `mentions_me` / `mention_all`
> 로 노출하고, 사람이 읽는 `message_text`(토큰 → `@이름`)와 원본 `raw_text` 를
> 함께 제공한다. 멘션 게이팅 정책(전원 vs 멘션만)은 노브가 아니라 핸들러/라우터
> 선언으로 표현한다. 설계 근거는 [ARCHITECTURE.md](ARCHITECTURE.md) 참고.
