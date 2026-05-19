# DaouOffice API 엔드포인트 전체 목록

SAZ 분석 결과 기반 전체 API 엔드포인트 목록입니다.

## 도메인별 분류

| 도메인 | 설명 | 파일 |
|---|---|---|
| 포털(인증) | 로그인, 조직도, GraphQL | [01-auth.md](./01-auth.md), [05-other-api.md](./05-other-api.md) |
| 채팅방 | 생성, 목록, 상세, 구성원 | [02-chat-room.md](./02-chat-room.md) |
| 메시지 | 전송, 히스토리, 읽음, 검색 | [03-messages.md](./03-messages.md) |
| 실시간 (미구현) | WebSocket/STOMP — 미검증 RE 메모 | [04-websocket.md](./04-websocket.md) |

## 전체 엔드포인트 목록

| Method | Endpoint | 설명 | 주요 문서 |
|---|---|---|---|
| POST | `/api/portal/public/auth/login` | 로그인 | 01-auth |
| POST | `/api/portal/common/auth/logout` | 로그아웃 | 01-auth |
| POST | `/api/portal/common/auth/sso-token` | SSO 토큰 | 05-other |
| POST | `/api/portal/graphql` | GraphQL 쿼리 | 05-other |
| GET | `/api/portal/public/auth/company` | 회사 정보 | 05-other |
| GET | `/api/portal/common/company/color` | 회사 커스터마이징 | 05-other |
| GET | `/api/portal/common/organization/tree` | 조직도 트리 | 05-other |
| GET | `/api/portal/common/organization/tree/favorite/user` | 즐겨찾리 조직 | 05-other |
| GET | `/api/portal/common/notification/badge` | 알림 배지 | 05-other |
| GET | `/api/portal/emoticon/theme` | 이모티콘 테마 | 05-other |
| POST | `/api/portal/admin/organization/chart/config` | admin 조직도 설정 | 05-other |
| **GET** | **`/api/chat/room`** | **채팅방 목록** | **02-chat-room** |
| **POST** | **`/api/chat/room`** | **채팅방 생성** | **02-chat-room** |
| GET | `/api/chat/room/{id}/open` | 방 상세 | 02-chat-room |
| GET | `/api/chat/room/{id}/member` | 구성원 | 02-chat-room |
| PUT | `/api/chat/room/{id}/leave` | 방 나가기 | 02-chat-room |
| PUT | `/api/chat/room/{id}/lock` | 방 잠금 | 02-chat-room |
| PUT | `/api/chat/room/{id}/kickout` | 구성원 추방 | 02-chat-room |
| PUT | `/api/chat/room/{id}/history-open` | 히스토리 공개 | 02-chat-room |
| PUT | `/api/chat/room/{id}/history-open/option` | 히스토리 공개 옵션 | 02-chat-room |
| **POST** | **`/api/chat/message`** | **메시지 전송** | **03-messages** |
| POST | `/api/chat/message/{id}/read` | 읽음 처리 | 03-messages |
| POST | `/api/chat/message/emoticon` | 이모티콘 | 03-messages |
| GET | `/api/chat/room/{id}/chat/range` | 메시지 히스토리 | 03-messages |
| GET | `/api/chat/room/{id}/history-open` | 히스토리 공개 여부 | 03-messages |
| GET | `/api/chat/room/{id}/attachment` | 첨부파일 | 03-messages |
| GET | `/api/chat/room/{id}/link` | 링크 정보 | 03-messages |
| GET | `/api/chat/room/{id}/vote` | 투표 | 03-messages |
| GET | `/api/chat/search/message` | 메시지 검색 | 03-messages |
| GET | `/api/chat/room/pin` | 고정된 방 목록 | 02-chat-room |
| GET | `/api/chat/backup/list` | 대화백업 | 05-other |
| GET | `/api/chat/setting/data-management/data-retention` | 데이터 보관 | 05-other |
| GET | `/api/chat/user/setting` | 사용자 설정 | 05-other |
| GET | `/api/chat/user/setting/push` | 푸시 설정 | 05-other |
| GET | `/api/chat/user/app-manager` | 앱 매니저 | 05-other |
| POST | `/api/chat/user/status/connection` | 연결 상태 | 04-websocket |
| GET | `/ws/pc` | WebSocket 연결 | 04-websocket |
| POST | `/api/upload/attach/app` | 파일 업로드 | - |
| GET | `/api/agg/badge/apps` | 앱 배지 | 05-other |
