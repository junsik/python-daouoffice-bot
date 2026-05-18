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
          "platformUserId": "11000022612",
          "platformUserName": "박준식",
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
