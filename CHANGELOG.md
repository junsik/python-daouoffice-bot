# 변경 이력

이 프로젝트의 모든 주요 변경 사항을 여기에 기록합니다. 이 형식은 [Keep a Changelog](https://keepachangelog.com/)를 따르며, 이 프로젝트는 [Semantic Versioning](https://semver.org/)을 준수합니다.

## [0.1.0] — 2026-05-19

첫 오픈소스 릴리스. DaouOffice PC 메신저 REST API를 역엔지니어링했으며, 공식 봇 API는 존재하지 않습니다.

### 추가됨

- `BotClient` — REST 클라이언트: 로그인, GraphQL `me`을 통한 ID 해결, 방, 메시지, 읽음 확인. 다중 테넌트 지원 (`base_url` / `company_id`를 인자 또는 `DAOU_*` 환경변수에서 받아오며, 테넌트 값은 하드코딩하지 않음). `discover_company()`로 테넌트 URL에서 `companyId`를 해결.
- 모든 요청에 `X-Referer-Info: <base_url host>` 헤더 전송. 비인증 엔드포인트(`/api/portal/public/auth/company` 등)는 이 헤더를 요구함 (SAZ 캡처상 모든 비인증 요청에 존재); `docs/api/05-other-api.md`에 문서화.
- HTTP 401 발생 시 자동 재로그인 (`ROUTE-0004`): AccessToken 수명은 약 30분이며, 캡처된 트래픽에서 refresh 엔드포인트가 보이지 않으므로 장기 실행 봇은 재인증으로 복구함.
- `BotEngine` — 방별 마지막 메시지 추적 기능이 있는 비동기 폴링 엔진; 시작 시 백로그는 재생되지 않으며 메시지가 중복 처리되지 않음. 지속적 폴링 실패 시 지수 백오프 (최대 5분). 방을 들여다볼지는 **커서 대 방의 최신 메시지 id**(`latestMessage.chatMessageId`)로 판단함 — 봇이 `mark_read`로 스스로 0으로 만드는 unread 배지에 의존하지 않음(폴링과 ack 사이에 도착한 연속 메시지가 배지만 지워진 채 누락되던 문제 수정). unread는 첫 접촉 baseline 판정에만 보조로 사용.
- 영구 커서 저장 (`FileCursorStore`, `DaouBot`의 기본값): `~/.daoubot/cursors.json`(홈 기준, 실행 cwd 무관)이 각 방의 처리 진행 상황을 기록하여, 재시작 시 재생이나 스킵 대신 이어서 처리함. `MemoryCursorStore`는 이 기능을 비활성화. Catch-up은 약 100개 메시지 REST 히스토리 윈도우로 제한됨 (한 폴링 간격의 버스트가 윈도우 밖으로 밀려나지 않도록 폭을 넓힘).
- 고정 **최소 한번 이상(at-least-once)** 배달 (업계 표준, 선택 사항 아님): 핸들러가 성공할 때까지 방별 정렬 재시도, `max_attempts`를 통한 poison guard, 읽음 확인은 마지막으로 확인된 메시지까지만. 엔진이 커서/ack를 관리하며, 핸들러는 순수한 상태를 유지 (식별자 중복 방지용 핸들러를 idempotent하게 만듦; fire-and-forget 용도는 에러 swallow).
- Mention 파싱: inline `{{uuid::USER::@name::id}}` / `{{uuid::ALL::@ALL}}` 토큰을 `NewMessage.mentions` / `mentions_me` / `mention_all`로 파싱하고, 인간이 읽을 수 있는 `message_text`와 원문 `raw_text`를 제공. `only_when_mentioned(handler)` 필터가 소음이 많은 그룹 방을 제한 (글로벌 토큰 없음 — 정책은 선언적으로 유지). 인코딩은 `docs/api/03-messages.md` §3.6에 문서화됨.
- `DaouBot` — `on_message` 콜백만으로 구동되는 고수준 봇 (`set_handler()`, 타입 `MessageHandler`). `DaouBot()`는 연결 설정을 스스로 해석함: 모든 값(비밀번호 포함) 명시 인자 > `DAOU_*` 환경변수 > `daoubot login` 프로필(`load_settings()`). 그래서 봇 코드는 `DaouBot(on_message=...)` 한 줄이면 되고 자격증명을 코드에 두지 않음. 비밀번호는 무인 자동 재로그인을 위해 `~/.daoubot/profile.json`(홈 기준, 실행 cwd 무관)에 저장됨 — 파일은 `chmod 600`·gitignore, 화면 출력 시 `Profile.public_dict()`가 `****` 마스킹. 토큰 만료마다 저장된 비밀번호로 자동 재로그인하고 새 토큰을 프로필에 다시 저장하므로 추가 설정 없이 무인 운영됨(`DAOU_PASSWORD`로 오버라이드 가능). 비밀번호가 전혀 없을 때만 토큰 만료 시 명확한 에러로 멈춤. (env 오버라이드는 문서로만 안내 — `from_env` 류 별도 API 없음.)
- `RoomRouter` — 방별 allowlist 기본값 디스패치 (`room_id` > `room_type` > 기본값 > 무시).
- `Profile` + `daoubot` CLI: `login` (`~/.daoubot/profile.json` 저장; `--company-id` 생략 시 공개 엔드포인트로 자동 탐색), `whoami`, `config` (저장된 프로필 보기/`set`으로 연결 항목 수정/`path`), `rooms`, `room create/open`, `send`. (봇 실행 명령은 없음 — CLI는 핸들러를 실을 수 없으므로 봇은 `DaouBot(on_message=...)` 를 담은 `python bot.py` 로 실행.) 연결 옵션(`--base-url` 등)은 모든 서브커맨드에 적용되는 공유 상위 파서에 있어 `daoubot login --base-url ...`처럼 서브커맨드 뒤에 둘 수 있음 (문서가 보여주는 형태와 동일). `--password`/`DAOU_PASSWORD`를 생략하면 TTY에서 `getpass`로 안전하게 프롬프트 (숨김 처리) — 시크릿이 argv(`ps`/셸 히스토리)에 남지 않고, 셸 쿼팅(`!`/특수 문자) 문제도 회피.
- 설정 파일은 `~/.daoubot/profile.json` 단일 파일 — 홈 디렉터리 기준이라 실행 cwd 와 무관(`~/.aws`/`~/.docker` 류 관례); 어느 디렉터리·예제에서 실행하든 한 번의 `daoubot login` 으로 동작 (SDK는 `.env`/dotenv를 읽지 않음); `--config <path>` (서브커맨드 이후)로 다중 봇/테넌트 호스트에서 위치 변경. `load_profile`/`save_profile`/`load_settings`가 명시적 경로 인자를 받음.
- 우아한 종료: `run_forever()`이 SIGINT/SIGTERM 핸들러를 설치하고 정상적으로 로그아웃 (systemd 하에서 중요, systemd는 SIGTERM으로 스톱); 시그널 사용 불가 환경에서는 일반 취소로 폴백.
- 첨부 파일 전송: `BotClient.upload_attachment(path)` + `send_message(..., attachments=[...])`, 단축키 `send_file()` / `DaouBot.send_file()` (예: LLM이 생성한 뉴스레터 .md/.html을 다운로드 가능한 파일로 게시). SAZ에서 디코딩한 2단계 흐름; `docs/api/03-messages.md` §3.7에 문서화됨; 계약은 **미검증**.
- 에이전트 스킬 (표준 `SKILL.md` 형식, 모든 스킬 호환 런타임으로 이식 가능 — Claude.ai/Claude Code/Agent SDK) `skills/daouoffice-bot/`(SKILL.md + reference.md + scaffold.py) — 배포 가능한 소비자 스킬 (런타임의 스킬 디렉토리, e.g. `~/.claude/skills/`, 또는 `npx skills add`로 설치), 로컬 개발 설정인 `.claude/`에 있지 않음. **디자인 가이드**, 템플릿 메뉴 아님 — 에이전트가 요구사항을 추출하고, 의사결정 매트릭스를 통해 기본값을 매핑하며, SDK의 불변식 하에 봇을 조립 (BotFather/webhooks/inline 없음; polling, allowlist, idempotency, env/profile 설정). `scaffold.py`는 정확한 초기 코드만 생성 (UTF-8는 cp949 Windows에서 안전); 디자인은 에이전트의 것, 사용자의 실제 필요에서.
- 예제: echobot, command (`/cmd args` 디스패처, 접두사 `BOT_CMD_PREFIX` 로 변경 가능), attachment (`!report` → 생성한 .md 를 `send_file` 로 첨부 답장), conversation, assistant (독립 LLM 호출), router, error-handler, room-saver (`RoomRouter`로 지정한 방만 JSONL 저장).
- 아키텍처를 `docs/ARCHITECTURE.md`(다이어그램 포함)에 문서화.
- 테스트 스위트 (pytest + respx, 네트워크 mock), ruff lint + format, Python 3.12 / 3.13에서 CI, 다운스트림 타입 체킹용 `py.typed`.

### 참고

- 공식 아님; 사설 API에 의존하며 서버 변경으로 인해 중단될 수 있음.
- LLM 통합을 SDK의 일부로 의도하지 않음 — `examples/bot-assistant` 참조.
- 폴링이 유일한 배달 경로임. 캡처에서 WebSocket/STOMP 엔드포인트를 발견했으나 검증하지 않았으므로, WS 코드는 배포되지 않음 — 향후 작업을 위해 역엔지니어링 참고록으로 유지 (`docs/api/04-websocket.md`).
