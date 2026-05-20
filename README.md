# python-daouoffice-bot

다우오피스(DaouOffice) 메신저용 비공식 봇 SDK.

공식 봇 API가 없는 다우오피스 메신저를, **PC 메신저가 쓰는 REST API를 역분석**하여 파이썬에서 다룰 수 있게 합니다. 방 목록 조회·메시지 송수신·폴링 기반 응답을 지원하며, 메시지 핸들러(`on_message`) 안에서 원하는 로직(LLM 포함)을 자유롭게 붙입니다 — SDK 자체는 LLM을 번들하지 않습니다.

[![CI](https://github.com/junsik/python-daouoffice-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/junsik/python-daouoffice-bot/actions/workflows/ci.yml) ![Python](https://img.shields.io/badge/python-3.12%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

> ⚠️ **비공식·역분석 프로젝트입니다.** 다우오피스/다우기술과 무관하며, 비공개 API에 의존하므로 서버 변경 시 동작이 깨질 수 있습니다. 사용 전 소속 조직의 정책과 서비스 약관을 확인하세요. 자동화 계정 발급 권한이 있는 환경에서만 사용하십시오. **공개 시점 스냅샷("as-is")으로 제공되며 적극적인 유지보수를 약속하지 않습니다.** 일부 계약(첨부 전송 등)은 SAZ 캡처 기반으로 도출돼 라이브 미검증입니다 — 포크 시 실제 트래픽으로 확인하세요.

## 일반 메신저 봇과 무엇이 다른가 (이 프로젝트가 존재하는 이유)

텔레그램·슬랙·디스코드는 **공식 봇 플랫폼**이 있습니다 — 봇을 등록하고, 토큰/OAuth를 받고, 웹훅이나 이벤트 푸시로 메시지를 받습니다. 다우오피스에는 **그게 없습니다.** 공식 봇 API가 존재하지 않습니다. 그런데 다우오피스를 쓰는 조직에도 ChatOps·알림·어시스턴트 봇 수요는 똑같이 있습니다. 유일한 경로는 **PC 메신저가 쓰는 비공개 REST API를 역분석**하는 것이고, 그 과정과 비자명한 운영 함정(아래)을 매 팀이 다시 파헤치지 않도록 한곳에 캡슐화한 것이 이 프로젝트입니다.

핵심은 **봇을 만드는 절차 자체가 다르다**는 점입니다:

| | 텔레그램/슬랙/디스코드 | 다우오피스 (이 SDK) |
|---|---|---|
| 봇 등록 | BotFather / 앱 등록 + OAuth / 개발자 포털 | **없음.** 관리자가 **일반 사용자 계정**을 발급 |
| 인증 | 봇 토큰 / OAuth 스코프 | 계정 `loginId`/`password` 로그인 (세션 ~30분, 자동 재로그인) |
| 방에 "연결" | 봇 초대 + 권한/스코프, 채널별 설치 | 그 계정을 방 멤버로 **추가하면 끝** — 멤버십이 곧 연결 |
| 메시지 수신 | 웹훅 / Events / Gateway 푸시 | **푸시 없음** — PC 클라이언트와 같은 REST를 폴링 |
| 권한 모델 | 스코프된 봇 토큰 | 그 계정이 가진 권한 그대로 (그래서 *전용* 계정 필수) |
| 공식성/안정성 | 문서화된 안정 API | 비공개·역분석 — 서버 변경 시 깨질 수 있음 |
| 테넌시 | 단일 플랫폼 | 회사별 SaaS 서브도메인 — 어떤 값도 하드코딩 안 함 |

절차 비교:

- **텔레그램** — BotFather로 봇 생성 → 토큰 발급 → 방에 초대 → 웹훅/`getUpdates`
- **다우오피스** — 관리자에게 자동화 전용 계정 요청 → 데스크톱 메신저처럼 로그인 → 방에 멤버로 추가 → 폴링

즉 "토큰 발급"도 "앱 등록"도 "웹훅 설정"도 없습니다.

이 모델에서 흘러나오는, 일반 봇 SDK엔 없는 운영 제약을 SDK가 흡수합니다: 계정 단위 읽음 상태(전용 계정 필수), 폴링 기반 at-least-once + 재시작 커서, 그룹 도배 방지 allowlist, 인라인 멘션 토큰 파싱, 30분 토큰 자동 재로그인. 설계 근거는 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 참고.

준비물:

1. 다우오피스 테넌트 URL — `https://<회사>.daouoffice.com`
2. 자동화 전용 계정 (관리자 발급)

(테넌트의 숫자 `companyId` 는 `daoubot login` 이 공개 엔드포인트에서 자동으로 알아내므로 미리 준비할 필요 없습니다 — 필요하면 `--company-id` 로 직접 지정.)

## 설치

아직 PyPI에 게시 전입니다. 봇 프로젝트의 의존성으로 Git에서 직접 추가하세요:

```bash
uv add "git+https://github.com/junsik/python-daouoffice-bot"
# 또는: pip install "git+https://github.com/junsik/python-daouoffice-bot"
```

특정 릴리스에 고정하려면 태그를 붙입니다:

```bash
uv add "git+https://github.com/junsik/python-daouoffice-bot@v0.1.0"
```

이 저장소 자체를 개발하려면 소스에서:

```bash
git clone https://github.com/junsik/python-daouoffice-bot
cd python-daouoffice-bot
uv sync                 # dev 의존성 포함
```

## 온보딩: `daoubot login` → 프로필

봇은 백그라운드 데몬입니다. 처음 한 번 로그인하면 회사·사용자 정보, 세션 토큰, **비밀번호**가 `~/.daoubot/profile.yaml`(홈 디렉터리, 실행 위치 무관 — `~/.aws`/`~/.docker` 와 같은 방식)에 저장되고, 이후 코드/명령은 어느 디렉터리에서 실행하든 그 프로필을 자동으로 씁니다. 데몬이 무인 자동 재로그인하려면 비밀번호가 필요하므로 저장하는 것이며 — 파일은 `chmod 600`·`.daoubot/` gitignore, 화면 출력 시에는 항상 `****` 로 마스킹합니다. `company_id` 를 안 주면 공개 엔드포인트로 자동 탐색합니다.

```bash
# --login-id 를 생략하면 로그인 id 를, --password 를 생략하면 비밀번호를
# (이 순서로) 프롬프트로 입력받습니다 — 비밀번호는 숨김 입력이라 argv·셸
# 히스토리에 안 남고, ! 같은 특수문자 인용 문제도 없습니다:
daoubot login --base-url https://yourcompany.daouoffice.com
# → ~/.daoubot/profile.yaml 저장 (토큰·비밀번호는 화면엔 **** 로만 표시)
```

한 호스트에서 여러 봇/테넌트를 쓰려면 `--config <경로>` 로 프로필 파일을 분리합니다 — 옵션은 **서브커맨드 뒤**에 옵니다(`daoubot login --config X ...`, `daoubot rooms --config X`).

### 무인(백그라운드) 운영

AccessToken 은 약 30분 뒤 만료됩니다. `daoubot login` 한 번이면 30일짜리 RefreshToken 과 비밀번호가 프로필에 함께 저장돼, 봇/CLI 는 401 을 받으면 **(1) RefreshToken 으로 새 AccessToken 만 빠르게 발급**받고, 그게 실패할 때만 **(2) 비밀번호로 풀 재로그인**합니다 — 새 토큰은 프로필에 다시 씁니다. 추가 설정 없이 무인 운영됩니다. (`DAOU_PASSWORD` 환경 변수로 오버라이드 가능, 예: systemd `EnvironmentFile`.) RefreshToken 도 비밀번호도 전혀 없을 때만 만료 시 명확한 에러로 멈춥니다(사용자에게 재로그인을 강요하지 않음).

모든 연결값(비밀번호 포함)은 **명시 인자 > `DAOU_*` 환경 변수 > 앱 설정(`DAOU_APP_CONFIG`) > 프로필** 순으로 해석됩니다. SDK는 `.env` 파일을 자동으로 읽지 않으니, 환경 변수로 오버라이드하려면 셸에 직접 export 하거나 systemd EnvironmentFile 을 쓰세요. 다운스트림 앱(예: dt-agent)이 자기 `agent.yaml` 의 `daouoffice:` 섹션에 연결값을 선언하면 SDK 가 그걸 **읽기 전용**으로 사용합니다 — 토큰·identity 는 여전히 프로필이 관리(파일 분리).

| 환경 변수 | 설명 |
|---|---|
| `DAOU_BASE_URL` | 테넌트 URL (`https://회사.daouoffice.com`) — 로그인 필수 |
| `DAOU_COMPANY_ID` | 숫자 회사 id — 생략 시 `daoubot login` 이 공개 엔드포인트로 자동 탐색 |
| `DAOU_LOGIN_ID` | 봇 계정 로그인 id — 로그인 필수 |
| `DAOU_PASSWORD` | 봇 계정 비밀번호 — 무인 자동 재로그인용. 프로필에 저장되므로 한 번 `daoubot login` 했으면 다시 설정할 필요 없음 |
| `DAOU_APP_CONFIG` | 다운스트림 앱의 YAML 경로(예: `agent.yaml`). 그 파일의 top-level `daouoffice:` 섹션에서 `base_url`/`company_id`/`login_id`/`password` 를 **읽기만** 함. SDK 가 그 파일에 절대 쓰지 않음 — 토큰·identity 는 프로필이 따로 관리. 정밀도 위 4개 사이 (env 보다 아래, 프로필 보다 위). CLI 는 `--app-config <path>` 로도 가능 |
| `DAOU_LOG_LEVEL` | `daouoffice` 패키지 로거 레벨(`DEBUG`/`INFO`/`WARNING`/…). 연결값 아님. 미설정 시 앱 로깅 설정을 따름(라이브러리는 root/basicConfig 를 건드리지 않음). 메시지 본문·발신자 로그는 기본적으로 `DEBUG` 라 기본 `INFO` 에서는 **대화 내용이 로깅되지 않음** — 진단 시 `DEBUG` 로 켜고, 더 조용히 하려면 `WARNING` |

위 6개(`DAOU_` 접두사)가 **SDK가 읽는 환경 변수의 전부**입니다. 개별 예제가 자체적으로 쓰는 변수(LLM 키, 대상 방 id 등)는 각 예제의 docstring 에 적혀 있습니다 — SDK 코어와 무관하므로 여기서 다루지 않습니다.

**다운스트림 앱과의 통합 (예: dt-agent의 `agent.yaml`)**: 앱이 이미 자기 설정 YAML 을 들고 있으면, 거기에 `daouoffice:` 섹션 하나 더 붙이고 SDK 에 그 파일을 가리키면 됩니다. SDK 는 읽기만 하므로 앱이 자기 파일 포맷·주석을 그대로 유지합니다. 토큰/identity 는 여전히 `~/.daoubot/profile.yaml` (또는 `--config` 지정 경로) 에 SDK 가 자동 관리.

```yaml
# agent.yaml (앱이 들고 있는 기존 파일)
daouoffice:
  base_url: https://yourcompany.daouoffice.com
  login_id: yourbot
  password: <비밀번호>      # 또는 DAOU_PASSWORD env 로(env 가 더 우선)
  # company_id 는 생략 가능 (자동 탐색)
```

```python
bot = DaouBot(on_message=on_message, app_config="agent.yaml")
# 또는 환경변수: DAOU_APP_CONFIG=/etc/myapp/agent.yaml python bot.py
```

## 빠른 시작

`daoubot login` 후, 봇 코드는 연결 설정이 필요 없습니다 — 프로필에서 자동 해석됩니다:

```python
import asyncio

from daouoffice import DaouBot, NewMessage

async def on_message(msg: NewMessage) -> str | None:
    if "안녕" in msg.message_text:
        return f"안녕하세요, {msg.sender_name}님!"
    return None  # 응답 안 함

async def main():
    bot = DaouBot(on_message=on_message)   # 프로필/환경에서 자동 해석
    await bot.run_forever()                # Ctrl-C / SIGTERM 시 graceful 종료

asyncio.run(main())
```

`on_message` 가 문자열을 반환하면 답장, `None` 이면 무응답입니다. 답장은 그 핸들러를 유발한 메시지에 대한 **인용 회신(threaded reply)** 으로 자동 연결되므로(다우오피스 답장 UI 와 동일), 바쁜 방에서도 무엇에 대한 답인지 분명합니다. 핸들러를 주지 않으면 봇은 메시지를 읽기만 합니다(답장 안 함). 30분 만료 시 RefreshToken/자격증명이 있으면 자동 갱신·재로그인합니다.

> 봇 계정은 누구나 아무 방에나 초대할 수 있습니다. 특정 방에서만 동작시키려면 `RoomRouter` 를 쓰세요 — 등록한 방만 처리하고 나머지는 무시합니다(allowlist). `bot = DaouBot(..., on_message=router)`. 예제: `examples/bot-router`.

**멘션:** 다우오피스 멘션은 본문 인라인 토큰입니다(전체 공개, 비공개 아님 — [docs/api/03-messages.md](docs/api/03-messages.md) §3.6). SDK가 파싱해 `msg.mentions` / `msg.mentions_me` / `msg.mention_all` 와 사람이 읽는 `message_text`(토큰 → `@이름`), 원본 `raw_text` 를 제공합니다. 바쁜 그룹에서 멘션 시에만 응답하려면 `only_when_mentioned(handler)` 로 감싸세요(글로벌 노브 아님 — 정책은 선언으로).

```python
bot = DaouBot(..., on_message=only_when_mentioned(handle))
```

**마크다운 스타일 (`markdown=True`):** 채팅은 작은 HTML 부분집합만 렌더합니다 — 볼드·이탤릭·링크·번호목록·블릿목록(라이브 캡처로 확인). `DaouBot(..., markdown=True)` 면 핸들러가 반환한 마크다운을 엔진이 전송 전 자동 변환합니다(`**굵게**`/`*기울임*`/`[텍스트](url)`/`1.`/`-`). 기본은 비활성(그대로 전송). 부분집합 밖 문법(헤딩·코드)은 태그 대신 원문 그대로 degrade 하고, 텍스트는 HTML escape, 링크 href 는 `"` 까지 escape 되어 깨짐/주입이 없습니다. 직접 변환은 `to_chat_html(text)`. 계약·태그표는 [docs/api/03-messages.md](docs/api/03-messages.md) §3.1.

**파일 첨부 (예: LLM 뉴스레터):** 긴 MD/HTML *문서*는 인라인 렌더되지 않습니다(위 부분집합 밖). `bot.send_file(room_id, "news.md", "이번 주 뉴스레터")` 로 업로드 → 첨부로 전송(수신자 다운로드). `BotClient.upload_attachment()` + `send_message(..., attachments=[...])` 분해도 가능. 첨부 계약은 SAZ 기반이며 **라이브 미검증**입니다([docs/api/03-messages.md](docs/api/03-messages.md) §3.7).

**재시작 복구:** "어디까지 처리했는지"(방별 마지막 메시지 id)는 기본적으로 `~/.daoubot/cursors.json` 에 저장됩니다 — 봇이 재시작해도(어느 디렉터리에서 실행하든) 백로그를 다시 처리하거나 다운타임 메시지를 건너뛰지 않고 이어받습니다. 비영속을 원하면 `DaouBot(..., cursor_store=MemoryCursorStore())`. 단, 폴링 특성상 따라잡기는 방당 최근 ~100개 히스토리 창 안으로 제한됩니다(그보다 오래 다운되면 창 밖 메시지는 복구 불가 — "since id" 엔드포인트가 없음).

**전달 보장:** 엔진은 **at-least-once** 를 보장합니다 — 메시지 전달의 업계 표준(Kafka/SQS/Slack/Telegram)이라 노브로 노출하지 않고 SDK가 책임집니다. 핸들러가 예외 없이 끝날 때까지 방 내 순서대로 재전달하며, 같은 메시지가 `max_attempts`(기본 5)회 실패하면 poison으로 건너뜁니다.

- 중복이 의미를 가지면 **핸들러를 멱등하게** 작성하세요 (Kafka/SQS 교리). 트랜스포트 dedup은 엔진, 비즈니스 멱등성은 핸들러 책임.
- fire-and-forget(재시도 원치 않음)은 별도 모드가 아니라 **핸들러가 자기 예외를 삼키면**(실패로 안 침) 자연히 표현됩니다.

## CLI

```bash
daoubot login ...                      # 인증 + 프로필 저장 (위 참고)
daoubot whoami                         # 저장된 봇 신원 출력
daoubot config                         # 저장된 프로필 보기(시크릿 마스킹)
daoubot config set base_url <url>      # 연결 항목 수정 (password 는 값 생략 시 숨김 입력)
daoubot config path                    # 프로필 파일 경로 출력
daoubot rooms                          # 채팅방 목록 (room id 포함)
daoubot room create --users a,b --name "Bot Test" [--type GROUP]
daoubot room open <room_id>            # 방 상세 + 구성원
daoubot send <room_id> "<text>"        # 메시지 전송

daoubot login --config bots/a.json ... # 프로필 파일 위치 분리(멀티 봇/테넌트)
```

CLI는 온보딩·조회·단발 전송용입니다. **봇 실행은 CLI가 아니라** `DaouBot(on_message=...)` 를 담은 파이썬 스크립트(`python my_bot.py`)입니다 — CLI는 핸들러를 실을 수 없어 별도 `start` 명령을 두지 않습니다(아래 [빠른 시작](#빠른-시작)·`examples/`).

`--login-id`/`--password` 를 생략하면 (이 순서로) 프롬프트로 입력받습니다(비밀번호는 숨김 — argv·히스토리 노출 방지).

개발자는 `login` → `rooms`/`room create` 로 필요한 `company_id`·`user_id`·`room_id` 를 손에 넣은 뒤, 그 값들로 SDK 봇을 작성하면 됩니다. (설치 없이: `uv run python -m daouoffice.cli rooms`)

## 예제

`examples/` 의 각 봇은 `DAOU_*` 환경 변수만 설정하면 그대로 실행됩니다:

| 예제 | 설명 |
|---|---|
| `bot-echobot` | 받은 메시지를 그대로 반복 |
| `bot-command` | `/cmd args` 명령 디스패처 (help/echo/whoami; 접두사는 `BOT_CMD_PREFIX` 로 변경) |
| `bot-attachment` | `!report` → 그 자리에서 .md 생성해 파일 첨부로 답장 (`send_file`) |
| `bot-conversation` | 방별 상태 머신 대화 |
| `bot-assistant` | 핸들러에서 OpenAI 호환 LLM 호출 (LLM_* env 필요) |
| `bot-router` | 방별 핸들러 분기 (등록한 방만 처리하는 allowlist) |
| `bot-error-handler` | 핸들러 예외를 잡아 개발자 방에 알림 |
| `bot-room-saver` | `RoomRouter` 로 지정한 방만 JSONL로 저장(응답 안 함; 방 id는 `daoubot rooms`) |

```bash
uv run --with python-daouoffice-bot examples/bot-echobot/bot.py
```

## AI로 봇 만들기 (에이전트 스킬)

표준 **에이전트 스킬**(`SKILL.md` + frontmatter + 번들 파일)이 저장소에 포함돼 있어, AI에게 "다우오피스 봇 만들어줘"라고 시켜 스캐폴딩·확장할 수 있습니다. 특정 도구 전용이 아니라 이 스킬 포맷을 지원하는 어떤 에이전트 런타임(Claude.ai·Claude Code·Claude API/Agent SDK 등)에도 그대로 이식됩니다.

```
skills/daouoffice-bot/   # SKILL.md + reference.md + scaffold.py
```

설치 — 에이전트의 스킬 디렉터리에 폴더를 놓으면 됩니다. Claude 계열 런타임은 `~/.claude/skills/`(전역), 다른 런타임은 각자의 스킬 로더 규약을 따르세요:

```bash
cp -r skills/daouoffice-bot ~/.claude/skills/        # 수동 복사
# 또는
npx skills add junsik/python-daouoffice-bot --skill daouoffice-bot
```

> 이 폴더는 **소비자용 배포물**입니다. 저장소의 `.claude/` (있다면)는 *이 SDK 자체를 개발*하기 위한 로컬 설정이라 gitignore되며, 이 스킬과 무관합니다 — 봇을 만들려면 위처럼 본인 환경에 설치하세요.

### 적용법 (설치 후)

스킬은 별도 명령이 아니라 **요청 내용으로 자동 발동**합니다. 봇을 만들 작업 폴더에서 스킬 포맷을 지원하는 에이전트(Claude Code·Claude.ai·Claude Desktop·Agent SDK 등)를 열고, 그냥 평소처럼 말하면 됩니다:

```text
다우오피스 봇 만들어줘. 우리 회사는 acme.daouoffice.com 이고,
#개발-알림 방에서 !배포 명령에만 응답하면 돼.
```

그러면 스킬이 잡혀서 — (1) 부족한 정보(테넌트·전용 계정·대상 방·트리거·상태·부작용)를 **되묻고**, (2) 결정 매트릭스로 설계를 정한 뒤, (3) `scaffold.py` 로 보일러플레이트를 깔고 핸들러를 구현하고, (4) SDK 불변규칙을 지키며, (5) `daoubot login`/`send` 로 라이브 스모크까지 안내합니다. ("스킬 써"라고 명시할 필요 없음 — `다우오피스 봇`/`DaouBot`/`daoubot` 같은 표현이면 발동합니다.)

설치 위치별 적용 범위:

- `~/.claude/skills/daouoffice-bot/` → **모든 프로젝트**에서 발동(권장).
- 특정 봇 프로젝트의 `<그_프로젝트>/.claude/skills/daouoffice-bot/` → 그 프로젝트에서만. *이 SDK 저장소 자체의 `.claude/` 에는 넣지 마세요* — 거긴 SDK 개발용입니다.

- 스킬은 템플릿 메뉴가 아니라 **설계 가이드**입니다 — AI가 요구사항을 인터뷰하고(테넌트·대상 방·트리거·상태·부작용), 결정 매트릭스로 프리미티브(`on_message`/`RoomRouter`/`only_when_mentioned`/상태/LLM)를 조합해 사용자가 원하는 봇을 만들도록, SDK 불변규칙(계정 전역 read·allowlist·멱등성·없는 API 날조 금지)과 함께 가르칩니다.
- `scaffold.py` 는 유스케이스를 추측하지 않고 **올바른 보일러플레이트만** 출력합니다(env/프로필 연결 + graceful run + 빈 핸들러). 설계는 AI가 요구사항에서 결정: `python skills/daouoffice-bot/scaffold.py > bot.py`

## SDK 개요

| 심볼 | 설명 |
|---|---|
| `BotClient` | REST API 래퍼 (로그인·방·메시지·첨부·`whoami`·`discover_company`) |
| `BotEngine` | 폴링 엔진 (단일 구현, async) |
| `DaouBot` | 고수준 봇 (`on_message` + 폴링 + 401 자동 재로그인) |
| `RoomRouter` | 방별 핸들러 분기 (등록한 방만 처리, 나머지 무시) |
| `only_when_mentioned` | 봇 멘션(`@봇`/`@전체`) 시에만 핸들러 실행 |
| `load_settings` / `Settings` | 연결설정 해석(인자>env>프로필); `DaouBot()` 이 내부 사용 |
| `FileCursorStore` / `MemoryCursorStore` | 처리 위치 영속/비영속 저장 |
| `NewMessage` | 정규화된 수신 메시지 |
| `BotIdentity` | 로그인 시 해석된 봇 자신의 신원 |
| `Profile` | `daoubot login` 이 저장하는 프로필 (`load_profile`) |
| `DaouAuthError` / `DaouConfigError` | 예외 |

전달은 **폴링만** 사용합니다. WebSocket(`GET /ws/pc`, STOMP)은 캡처에서 엔드포인트만 관측됐을 뿐 흐름을 검증하지 못해 **구현하지 않았습니다** (미검증 RE 메모: [docs/api/04-websocket.md](docs/api/04-websocket.md)).

## 프로젝트 구조

```
src/daouoffice/         SDK 패키지 (import daouoffice)
examples/               실행 가능한 예제 봇 (echobot/command/attachment/
                        conversation/assistant/router/error-handler/room-saver)
skills/daouoffice-bot/  배포용 에이전트 스킬 (SKILL.md + reference.md + scaffold.py)
docs/                   ARCHITECTURE.md (설계 근거) + api/ (역분석 엔드포인트 레퍼런스)
tools/                  SAZ 캡처 분석 스크립트 (개발용)
tests/                  pytest (네트워크는 respx로 목)

```

## 개발

```bash
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

설계 배경과 다이어그램은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), 기여 가이드는 [CONTRIBUTING.md](CONTRIBUTING.md), 변경 이력은 [CHANGELOG.md](CHANGELOG.md)를 참고하세요.

## 라이선스

[MIT](LICENSE) © junsik
