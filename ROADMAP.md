# 로드맵

버전별 제안 방향. 날짜 없음 — 항목은 준비되고 품질 기준을 달성하면 출시. 1.0 이전이므로 `0.x`에 충돌 변경이 포함될 수 있음 ([CHANGELOG.md](CHANGELOG.md) 참조).

## 원칙 (추가 전에 읽으시오)

이미 내린 결정들이며, 로드맵이 이를 후퇴시켜서는 안 됩니다.

- **표준 따르기; 함정 knobs 만들지 않기.** (전달이 at-least-once로 고정된 이유, 구성 가능한 이유는 아님 — ARCHITECTURE.md 참조.)
- **범위 집중하기.** SDK는 DaouOffice 메시징을 한다. LLM, 웹 프레임워크, 작업 오케스트레이션은 핵심에서 제외 (핸들러/예제 관심사).
- **미검증 항목에 정직하기**. 리버스 엔지니어링됨 — 추측성 항목이 기능으로 출시되지 않음. 라이브 동작은 "지원됨"으로 호출되기 전에 검증되어야 함.
- **멀티-테넌트, 하드코딩 값 없음, 비밀 없음**. 항상.
- **전송은 엔진에, 정책은 핸들러에**. 새 원소는 조립 가능하고 직교적으로 유지 (`RoomRouter` × `only_when_mentioned`과 같음).

## 0.1.0 — 첫 release (현재 브랜치, 미출시)

완료: 멀티-테넌트 client, GraphQL 신원, 401 재로그인, 폴링 엔진 (커서 persist, at-least-once, poison 가드), `RoomRouter`, `only_when_mentioned`, 멘션 파싱, `from_env`/구성 해결사, `daoubot` CLI, 프로필 저장소, 6개 예제, Claude 스킬, 문서, 42개 테스트 + CI.

0.1.0 실제 컷을 위한 관문:

- [ ] **라이브 smoke test** 실제 테넌트 하나에서 (`daoubot login` → `rooms` → `send` → 실행 중인 echo 봇) — 테스트가 여기서 커버할 수 없는 유일한 것. 결과를 CHANGELOG에 기록.
- [ ] `v0.1.0` 태그, CHANGELOG에서 GitHub Release 생성.
- [ ] (선택사항) PyPI에 publish.

## 0.2.x — 견고화 (프로토콜 리스크 없음)

- CI에 `mypy` (또는 `ty`) 도입 — 배송되는 `py.typed` 지원.
- CLI 명령 테스트 (`room create/open`, `send`, `whoami`, `discover`).
- `SECURITY.md` + 문서화된 의존성/버전 정책.
- Rate-limit / 범프 인식: HTTP 429 / 스로틀링 응답 감지하고 per-room 백오프 적용 (지금: 전체 루프 백오프만).
- 더 큰 restart catch-up: 저장된 커서에서 재개할 때 `get_chat_history(message_id=...)`로 ~20 메시지 창을 넘어 페이지네이션.
- `SqliteCursorStore` (`CursorStore` 인터페이스가 이미 지원) — JSON 파일을 넘어서는 멀티-룸 봇용.
- **동치 모델**: 지금 느린/awaiting 중인 핸들러가 전체 폴링 주기(모든 방)를 차단. 디스패치는 **per-room 순서지만 cross-room 동치성**(bounded)이어야, 하나 이상의 방이 나머지 방을 스톨링할 수 없음.

## 0.3.x — 기능 확장 (이미 관측된 엔드포인트 기반)

리버스엔지니어링 문서에 기반 — 각각 지원된다고 호출되기 전에 실제 트래픽 확인 필요.

- **발신 메시지 분류 & 이벤트** (가장 큰 기능적 격차): 엔진은 현재 `contents.message.text`가 아닌 것은 모두 스크랩. 메신저 SDK는 `metadata`(`messageType`/`subType`/`action`)에서 메시지 *종류*를 노출해야 — 파일/이미지/이모티콘, **이벤트 (멤버 join/leave** — 웰컴봇, 정형 패턴), 답장/인용, 편집/삭제 (`messageStatus`). `NewMessage`에 `kind` + 타입별 페이로드 추가; 핸들러가 opt-in. 발신/다운로드 발신 첨부파일 (`tempFileDownloadLink`)이 여기에 빌드.
- **발신 상호작용**: 이모티콘/리액션 (`/api/chat/message/emoticon`)과 답장-메시지 (`action:"REPLY"`) — 기본 메신저 동사들, 보낼 수 있지만 현재 못 함.
- **방 구성원 & 상태**: `get_members()` 모델과 상태/연결 상태 (`/api/chat/user/status/connection`, 캡처에서 확인) — 웰컴/명단 봇에 필요. 검증 필요.
- **조직 디렉토리 검색**: 이름/부서별로 사용자 해석 (`create_room`/mentions이 숫자 id를 요구하지 않도록).
- **발신 mentions**: 답장에서 @-mention할 수 있는 `{{uuid::USER::@name::id}}` 토큰을 만드는 헬퍼 (수신 파싱은 이미 존재).
- **메시지 검색 래퍼**: `/api/chat/search/message` (`mentionTypeList` 포함) — 효율적인 "mentions-only" 모드 지원 가능.
- **방 관리자 작업**: leave / lock / kick / history-open (`docs/api/02-chat-room.md`에 문서화), 명시적 메소드 behind.
- **첨부파일**: *보내기*는 0.1에 완료 (`upload_attachment`/`send_file`, SAZ 기반, 라이브 미검증). 남은 것: 발신 첨부파일 수신/다운로드, 이모티콘 리액션 (`/api/chat/message/emoticon`).

## 0.4.x — 사용성 (실제 수요에 gate, 추측성 아님)

- 프로액티브/예약된 보내기: 폴링 alongside 실행되는 보내기 작업용 경량 패턴 또는 thin 헬퍼 (무거운 JobQueue 프레임워크 아님).
- 선택형 대화상태 헬퍼 — 예제가 userland dict 패턴을 진정으로 불충분하게 보여주지만 도입. 기본값은 "핸들러에서 처리"로 두고, 프레임워크 크리프에 저항.

## 연구 트랙 (버전 독립적, 병렬)

- **WebSocket / STOMP 실시간** (`GET /ws/pc`). 캡처에서 엔드포인트 확인했지만 흐름은 검증되지 않음, 따라서 **구현되지 않음** 및 **일정 없음**. 프로모션 필요: 라이브 테넌트에서 clean 검증된 캡처, 테스트된 클라이언트, 폴링의 전달 보장과 동등성. 그래도, **폴링이 지원된 기본값으로 유지**; WS는 opt-in. 검증 전까지 추측성 코드는 들어오지 않음.

## 1.0.0 — API 안정성 (날짜가 아닌 관문)

모든 조건 충족 시에만 컷:

- ≥1 실제 테넌트에서 장기간 라이브 검증.
- 공개 API (`daouoffice.__all__`) 고정; deprecation 정책 작성.
- 문서 완성; CHANGELOG가 모든 충돌 0.x 변경을 반영.
- 패키지에 "미검증/실험적" 표면 잔여물 없음.

## 명시적으로 범위에서 제외 (다시 제안하지 마시오)

- SDK에 LLM 번들링 (핸들러/예제 관심사).
- BotFather-style 등록 (DaouOffice에는 없음 — 일반 계정임).
- 웹훅 / 인라인 키보드 / 슬래시커맨드 프레임워크 (서버가 지원하지 않음 — 발명하지 마시오).
- 구성 가능한 전달 모드 knob (거부됨: 조용한 손실 함정 — ARCHITECTURE.md "의사 결정 기록" 참조).
- 하나의 계정에서 여러 bot 프로세스 실행 (중복 처리 / 읽음 경합) — 하나의 프로세스에서 `RoomRouter`로 확장.
