# 5. 기타 API (Portal / User)

## 5.1 GraphQL - POST /api/portal/graphql

### 현재 사용자 조회 (userSessionQuery)
```json
{
  "operationName": "userSessionQuery",
  "query": "query userSessionQuery { me { id name loginId company{id uuid domain name} email status ... } }",
  "variables": {}
}
```

### Company 정보 조회
```
GET /api/portal/public/auth/company
Cookie: AccessToken=...
```

---

## 5.2 조직도 - GET /api/portal/common/organization/tree

### Request
```
GET /api/portal/common/organization/tree?rootDepartmentId=&shouldApplyOrganizationChartExpansion=true
Cookie: AccessToken=...
```

---

## 5.3 읽지 않은 메개수 - GET /api/portal/common/notification/badge

### Request
```
GET /api/portal/common/notification/badge
Cookie: AccessToken=...
```

### Response
```json
{
  "code": "SUCCESS-0000",
  "data": {
    "chatUnreadCount": 5,
    "totalUnreadCount": 8,
    ...
  }
}
```

---

## 5.4 사용자 설정 - GET /api/chat/user/setting

```
GET /api/chat/user/setting
Cookie: AccessToken=...
```

## 5.5 푸시 설정 - GET /api/chat/user/setting/push

### Query
```
GET /api/chat/user/setting/push?pageNumber=0&pageSize=10
```

## 5.6 앱 관리 - GET /api/chat/user/app-manager

---

## 5.7 프로필 이미지

### 기본 경로
```
GET {BASE_URL}/api/thumb/user/small/common/{COMPANY_UUID}/{YYYYMMDD}/{IMAGE_HASH}
```

### 예시
```
GET {BASE_URL}/api/thumb/user/small/common/{COMPANY_UUID}/{YYYYMMDD}/{IMAGE_HASH}
```

---

## 5.8 데이터 관리 - GET /api/chat/setting/data-management/data-retention

---

## 5.9 백업 - GET /api/chat/backup/list

---

## 5.10 이모티콘 테마 - GET /api/portal/emoticon/theme

---

## 5.11 알림 배지 - GET /api/agg/badge/apps?appCodes=dop-default-chat
