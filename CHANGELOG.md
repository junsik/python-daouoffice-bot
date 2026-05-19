# 변경 이력

이 프로젝트의 모든 주요 변경 사항을 여기에 기록합니다. 이 형식은 [Keep a Changelog](https://keepachangelog.com/)를 따르며, 이 프로젝트는 [Semantic Versioning](https://semver.org/)을 준수합니다.

## [0.1.0] — 미출시

첫 오픈소스 릴리스. DaouOffice PC 메신저 REST API를 역엔지니어링했으며, 공식 봇 API는 존재하지 않습니다.

### 추가됨
- `BotClient` — REST 클라이언트: 로그인, GraphQL `me`을 통한 ID 해결, 방, 메시지, 읽음 확인. 다중 테넌트 지원 (`base_url` / `company_id`를 인자 또는 `DAOU_*` 환경변수에서 받아오며, 테넌트 값은 하드코딩하지 않음).
- `BotClient.discover_company()` — 테넌트 URL에서 `companyId`를 해결.
- HTTP 401 발생 시 자동 재로그인 (`ROUTE-0004`): AccessToken 수명은 약 30분이며, 캡처된 트래픽에서는 refresh 엔드포인트가 보이지 않으므로 장기 실행 봇은 재인증으로 복구함.
- `BotEngine` — 방별 마지막 메시지 추적 기능이 있는 비동기 폴링 엔진; 시작 시 백로그는 재생되지 않으며 메시지가 중복 처리되지 않음.
- 영구 커서 저장 (`FileCursorStore`, `DaouBot`의 기본값): `.daoubot/cursors.json`이 각 방의 처리 진행 상황을 기록하여, 재시작 시 재생이나 스킵 대신 이어서 처리함. `MemoryCursorStore`는 이 기능을 비활성화. Catch-up은 약 20개 메시지 REST 히스토리 윈도우로 제한됨.
- 고정 **최소 한번 이상(at-least-once)** 배달 (업계 표준, 선택 사항 아님): 핸들러가 성공할 때까지 방별 정렬 재시도, `max_attempts`를 통한 poison guard, 읽음 확인은 마지막으로 확인된 메시지까지만. 엔진이 커서/ack를 관리하며, 핸들러는 순수한 상태를 유지 (식별자 중복 방지용 핸들러를 idempotent하게 만듦; fire-and-forget 용도는 에러 swallow).
- Mention 파싱: inline `{{uuid::USER::@name::id}}` / `{{uuid::ALL::@ALL}}` 토큰을 `NewMessage.mentions` / `mentions_me` / `mention_all`로 파싱하고, 인간이 읽을 수 있는 `message_text`와 원문 `raw_text`를 제공. 새로운 `only_when_mentioned(handler)` 필터가 소음이 많은 그룹 방을 제한 (글로벌 토큰 없음 — 정책은 선언적으로 유지). 인코딩은 `docs/api/03-messages.md` §3.6에 문서화됨.
- `DaouBot()` 가 연결 설정을 스스로 해석한다: 명시 인자 > `DAOU_*` 환경변수 > `daoubot login` 프로필(`load_settings()`). 비밀번호는 인자/env 만(프로필 불가). 그래서 봇 코드는 `DaouBot(on_message=...)` 한 줄이면 되고 예제·자격증명을 코드에 두지 않는다. 무인 운영 시 `DAOU_PASSWORD`(예: systemd EnvironmentFile)를 주면 토큰 만료마다 자동 재로그인하고 새 토큰을 프로필에 다시 저장한다. 비밀번호가 없으면 토큰 만료 시 명확한 에러로 멈춘다(사용자에게 재로그인을 강요하지 않음). (`from_env` 류 별도 API는 두지 않음 — env 오버라이드는 문서로만 안내.)
- 메시지 핸들러 인자가 이제 `on_message`임 (이전 `prompt_func`: LLM 프롬프트 결합을 오해하게 names를 변경). `set_handler()` (이전 `set_prompt_func`); 타입 `MessageHandler`.
- 오해의 소지가 있던 `.env.example` 제거 (SDK는 `.env`를 읽지 않음 — dotenv 없음). profile 파일이.tool이 읽고/쓰는 유일한 설정 파일; `profile.example.json`이 그 형태를 보여줌 (비밀번호 등 민감 정보 없음 — 비민감 필드만), `--config <path>` (서브커맨드 이후)로 다중 봇/테넌트 호스트에서 위치 변경. `load_profile`/`save_profile`/`load_settings`가 명시적 경로 인자를 받음.
- **고침**: 서브커맨드 이후 연결 옵션
  (`daoubot login --base-url ...`, 모든 문서에서 보여주는 것과 정확히 동일한 형태)이 "인식의 못하는 인자" 에러로 실패 — 이 인자들이 메인 파서에 있었는데, argparse가 서브커맨드 이후로는 파싱하지 않음. 모든 서브커맨드에 적용되는 공유 상위 파서로 이동하여 문서화된 형태가 작동하도록 함.
- **고침**: `discover_company` (및 `daoubot login` 자동 발견)이 `/api/portal/public/auth/company`에서 HTTP 400 반환 — 요청에 `X-Referer-Info` 테넌트-호스트 헤더가 누락됨. 비인증 엔드포인트는 이 헤더를 필요로 함 (SAZ 캡처에서 모든 비인증 요청에 존재). 클라이언트가 이제 모든 요청에 `X-Referer-Info: <base_url host>`를 전송함; `docs/api/05-other-api.md`에 문서화됨.
- CLI: `--password`/`DAOU_PASSWORD`를 생략하면 `login`/`start`가 TTY에서 안전하게 비밀번호를 프로ンプ트함 (`getpass` 사용, 숨김 처리) — 시크릿이 argv(`ps`/ 셸 히스토리)에 남지 않도록 하고, 셸 쿼터링(`!`/특수 문자) 문제도 회피.
- 우아한 종료: `run_forever()`이 SIGINT/SIGTERM 핸들러를 설치하고 정상적으로 로그아웃 (systemd 하에서 중요, systemd는 SIGTERM로 스톱); 시그널 사용 불가 환경에서는 일반 취소로 폴백.
- 지속적 폴링 실패 시 지수 백오프 (최대 5분) — 고정 간격 재시도가 아님.
- 새로운 `examples/bot-command` (일반적인 `!cmd args` 디스패처 패턴).
- 에이전트 스킬 (표준 `SKILL.md` 형식, 모든 스킬 호환 런타임으로 이식 가능 — Claude.ai/Claude Code/Agent SDK) `skills/daouoffice-bot/`(SKILL.md + reference.md + scaffold.py) — 배포 가능한 소비자 스킬 (런타임의 스킬 디렉토리, e.g. `~/.claude/skills/`, 또는 `npx skills add`로 설치), 로컬 개발 설정인 `.claude/`에 있지 않음. **디자인 가이드**, 템플릿 메뉴 아님 — 에이전트가 요구사항을 추출하고, 의사결정 매트릭스를 통해 기본값을 매핑하며, SDK의 불변식 하에 봇을 조립 (BotFather/webhooks/inline 없음; polling, allowlist, idempotency, env/profile 설정). `scaffold.py`는 정확한 초기 코드만 생성 (UTF-8는 cp949 Windows에서 안전); 디자인은 에이전트의 것, 사용자의 실제 필요에서.
- 첨부 파일 전송: `BotClient.upload_attachment(path)` + `send_message(..., attachments=[...])`, 단축키 `send_file()` / `DaouBot.send_file()` (예: LLM이 생성한 뉴스레터 .md/.html을 다운로드 가능한 파일로 게시). SAZ에서 디코딩한 2단계 흐름; `docs/api/03-messages.md` §3.7에 문서화됨; 계약은 **미검증**.
- 아키텍처를 `docs/ARCHITECTURE.md`(다이어그램 포함)에 문서화.
- `DaouBot` — `on_message` 콜백만으로 구동되는 고수준 봇.
- `RoomRouter` — 방별 allowlist 기본값 디스패치 (`room_id` > `room_type` > 기본값 > 무시).
- `Profile` + `daoubot` CLI: `login` (`.daoubot/profile.json` 저장), `discover`, `whoami`, `rooms`, `room create/open`, `send`, `start`.
- 예제: echobot, command, conversation, assistant (독립 LLM 호출), router, error-handler, room-saver (지정/전체 방 메시지를 JSONL로 수집).
- 테스트 스위트 (pytest + respx, 네트워크 mock), ruff lint + format, Python 3.12 / 3.13에서 CI, 다운스트림 타입 체킹용 `py.typed`.

### 참고
- 공식 아님; 사설 API에 의존하며 서버 변경으로 인해 중단될 수 있음.
- LLM 통합을 SDK의 일부로 의도하지 않음 — `examples/bot-assistant` 참조.
- 폴링이 유일한 배달 경로임. 캡처에서 WebSocket/STOMP 엔드포인트를 발견했으나 검증하지 않았으므로, WS 코드는 배포되지 않음 — 향후 작업을 위해 역엔지니어링 참고록으로 유지 (`docs/api/04-websocket.md`).
