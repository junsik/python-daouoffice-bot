# 2. 채팅방 (Chat Room)

## 2.1 채팅방 목록 조회 - GET /api/chat/room

### Request
```
GET /api/chat/room?pageNumber=0&pageSize=20
Cookie: AccessToken=...
Accept: */*
```

### Response
```json
{
  "code": "SUCCESS-0000",
  "message": "성공",
  "data": {
    "elements": [
      {
        "roomId": "11000303036",
        "roomName": "김상준, 이경헌, ...",
        "roomType": "GROUP",
        "roomMemberCount": 10,
        "unreadMessageCount": 12,
        "latestMessage": {
          "metadata": {"messageType":"CHAT","subType":"TEXT","action":"REPLY"},
          "sender": {"platformUserId":"11000022611","platformUserName":"정예리","positionName":"팀원"},
          "chatMessageId": "1505833539940147200",
          "createdAt": "2026-05-18T16:24:52.000+09:00",
          "contents": {"message": {"text":"안녕하세요", "plainText":"안녕하세요"}}
        },
        "userIdList": ["11000022611","11000022612"],
        "roomPushFlag": true,
        "roomPinFlag": false,
        "backgroundColor": "#427FFC"
      }
    ],
    "hasElements": true
  }
}
```

### roomType
| 값 | 의미 |
|---|---|
| `SINGLE` | 1:1 개인 채팅 |
| `GROUP` | 그룹 채팅 |

---

## 2.2 채팅방 생성 - POST /api/chat/room

### Request
```json
{
  "userList": ["11000022611", "11000022612"],
  "roomName": "대화방 이름",
  "roomType": "GROUP",
  "backgroundColor": "#f0bd03"
}
```

### Response
```json
{
  "code": "SUCCESS-0000",
  "message": "성공",
  "data": {
    "roomId": "1505835441897709568"
  }
}
```

---

## 2.3 채팅방 상세 조회 - GET /api/chat/room/{roomId}/open

### Request
```
GET /api/chat/room/1505835754159448064/open
Cookie: AccessToken=...
```

### Response
```json
{
  "code": "SUCCESS-0000",
  "data": {
    "memberList": [
      {
        "roomMemberId": "xxx",
        "roomMemberName": "박준식",
        "connectionStatus": "OFFLINE",
        "platformUserId": "11000022612",
        "positionName": "부장",
        "profileUrl": "..."
      }
    ],
    "notice": null,
    "roomName": "대화방 이름",
    "roomPushFlag": true,
    "roomPinFlag": false,
    "inputLockFlag": false,
    "messageHistoryOpenFlag": false,
    "lastReadMessageId": "0",
    "lastSentMessage": null,
    "roomType": "GROUP",
    "backgroundColor": "#f0bd03"
  }
}
```

---

## 2.4 방 구성원 목록 - GET /api/chat/room/{roomId}/member

### Request
```
GET /api/chat/room/1505835754159448064/member
Cookie: AccessToken=...
```

### Response
```json
{
  "code": "SUCCESS-0000",
  "data": {
    "elements": [
      {
        "roomMemberId": "xxx",
        "roomMemberName": "박준식",
        "profileUrl": "...",
        "connectionStatus": "OFFLINE",
        "lastReadMessageId": "0",
        "platformUserId": "11000022612",
        "userStatus": "NORMAL",
        "positionName": "부장",
        "companyUuid": "<COMPANY_UUID>"
      }
    ],
    "hasElements": true
  }
}
```

### connectionStatus
| 값 | 의미 |
|---|---|
| `ONLINE` | 접속 중 |
| `OFFLINE` | 오프라인 |
| `ABSENCE` | 자리에 없음 |

---

## 2.5 채팅방 나가기 - PUT /api/chat/room/{roomId}/leave

### Request
```
PUT /api/chat/room/{roomId}/leave
Cookie: AccessToken=...
```

### Response
```json
{"code":"SUCCESS-0000","message":"성공"}
```

---

## 2.6 채팅방 잠금 - PUT /api/chat/room/{roomId}/lock

### Request
```json
{"roomInputLockFlag": true}
```

### Response
```json
{"code":"SUCCESS-0000","message":"성공"}
```

---

## 2.7 추방 - PUT /api/chat/room/{roomId}/kickout

### Request
```json
{"platformUserId": "11000054149"}
```

### Response
```json
{"code":"SUCCESS-0000","message":"성공"}
```
