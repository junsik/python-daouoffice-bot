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
Set-Cookie: AccessToken=<JWT>; Path=/; HttpOnly
Set-Cookie: RefreshToken=<JWT>; Path=/; HttpOnly
Set-Cookie: GOSSOcookie=<uuid>; Path=/; Secure

{"code":"SUCCESS-0000","message":"성공"}
```

### Auth 방식
- `AccessToken` (JWT RS256, **약 30분** — JWT `exp - iat = 1800s`) + `RefreshToken` (30일, `Max-Age=2592000`, JWT `exp - iat = 2592000s`) 쿠키 기반
- 모든 API 호출 시 `Cookie: AccessToken=...; RefreshToken=...` 송신
- 만료 시 응답: `HTTP 401 {"code":"ROUTE-0004","message":"Invalid token"}`
- SDK 의 401 복구 순서: **(1) `/refresh/login` 으로 AccessToken 재발급** → (2) 실패 시 비밀번호로 풀 재로그인. RefreshToken 이 없거나 거부되면 자동으로 (2) 로 폴백.

---

## 1.2 토큰 리프레시 - POST /api/portal/public/auth/refresh/login

장시간 실행 시 30분짜리 AccessToken 을 비밀번호 없이 갱신한다. RefreshToken 은 회전하지 않고(요청·응답 JWT 의 `iat` 동일) AccessToken 만 새로 발급된다. 라이브 캡처(200 SUCCESS) 로 확인된 계약.

### Request
```
POST /api/portal/public/auth/refresh/login
Content-Type: application/json
Cookie: RefreshToken=<JWT>; AccessToken=<JWT>

https://yourcompany.daouoffice.com/api/chat/room/<roomId>/open
```

본문은 PC 메신저가 그 시점에 요청 중이던 절대 URL 한 줄(JSON 형식이 아니지만 `Content-Type: application/json` 으로 보낸다 — 서버는 본문 내용을 인증에 쓰지 않고 쿠키의 RefreshToken 으로 판단). SDK 는 401 을 유발한 요청의 절대 URL 을 본문으로 송신한다.

### Response
```
HTTP 200
Set-Cookie: AccessToken=<new JWT>; Max-Age=2592000; Path=/; HttpOnly
Set-Cookie: RefreshToken=<same JWT>; Max-Age=2592000; Path=/; HttpOnly

{"data":"OK"}
```

`AccessToken` 만 새 값. `RefreshToken` 은 같은 JWT 가 다시 set-cookie 되어 쿠키 수명만 갱신되고 값은 동일(회전 없음).

---

## 1.3 로그아웃 - POST /api/portal/common/auth/logout

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
