# 1. 인증 (Authentication)

## 1.1 로그인 - POST /api/portal/public/auth/login

### Request
```
Content-Type: application/json
Accept: */*
User-Agent: Mozilla/5.0 ... dop-chat-front/4.3.3 ... DOP_PC_MESSENGER

{"companyId":"<COMPANY_ID>","loginId":"<BOT_LOGIN_ID>","password":"<PASSWORD>","captcha":""}
```

### Response
```
HTTP 200
Set-Cookie: AccessToken=eyJhbGciOiJSUzI1NiJ9...; Path=/; HttpOnly
Set-Cookie: RefreshToken=eyJhbGciOiRSUzI1NiJ9...; Path=/; HttpOnly
Set-Cookie: GOSSOcookie=uuid-xxx; Path=/; Secure

{"code":"SUCCESS-0000","message":"성공"}
```

### Auth 방식
- `AccessToken` (JWT RS256, 1시간) + `RefreshToken` (30일) 쿠키 기반
- 모든 API 호출 시 `Cookie: AccessToken=...; RefreshToken=...` 필요

---

## 1.2 로그아웃 - POST /api/portal/common/auth/logout

### Request
```
Content-Type: application/json
Content-Length: 0
Cookie: AccessToken=...; RefreshToken=...
```

### Response
```
HTTP 200
{"code":"SUCCESS-0000","message":"성공"}
```
