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
- `AccessToken` (JWT RS256, **약 30분** — SAZ 캡처상 `exp - iat = 1800s`) + `RefreshToken` (30일, `Max-Age=2592000`) 쿠키 기반
- 모든 API 호출 시 `Cookie: AccessToken=...` 필요
- 만료 시 응답: `HTTP 401 {"code":"ROUTE-0004","message":"Invalid token"}`
- 캡처된 트래픽 326세션 전체에 **AccessToken 재발급(refresh) 엔드포인트가 관측되지 않음**. 따라서 이 SDK는 장시간 실행 시 401을 받으면 RefreshToken 교환 대신 **재로그인**으로 세션을 복구한다 (다중 세션 허용 특성상 안전).

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
