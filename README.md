# python-daouoffice-bot

다우오피스(DaouOffice) 메신저용 비공식 봇 SDK.

공식 봇 API가 없는 다우오피스 메신저를, **PC 메신저가 쓰는 REST API를 역분석**하여
파이썬에서 다룰 수 있게 합니다. 방 목록 조회·메시지 송수신·폴링 기반 응답을 지원하며,
메시지 핸들러(`on_message`) 안에서 원하는 로직(LLM 포함)을 자유롭게 붙입니다 —
SDK 자체는 LLM을 번들하지 않습니다.

[![CI](https://github.com/junsik/python-daouoffice-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/junsik/python-daouoffice-bot/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

> ⚠️ **비공식·역분석 프로젝트입니다.** 다우오피스/다우기술과 무관하며, 비공개 API에
> 의존하므로 서버 변경 시 동작이 깨질 수 있습니다. 사용 전 소속 조직의 정책과
> 서비스 약관을 확인하세요. 자동화 계정 발급 권한이 있는 환경에서만 사용하십시오.

## 봇 모델 — BotFather가 없습니다

텔레그램처럼 봇을 등록해 토큰을 받는 구조가 **아닙니다**. 다우오피스에서 "봇"은
관리자가 자동화용으로 발급한 **일반 사용자 계정**입니다. 그 계정의
`loginId`/`password`로 PC 메신저와 동일하게 로그인해서 사용합니다.

준비물:

1. 다우오피스 테넌트 URL — `https://<회사>.daouoffice.com`
2. 자동화 전용 계정 (관리자 발급)
3. 테넌트의 숫자 `companyId` — 아래 `daoubot discover`로 조회

## 설치

아직 PyPI에 게시되지 않았습니다. 소스에서 설치하세요:

```bash
git clone https://github.com/junsik/python-daouoffice-bot
cd python-daouoffice-bot
uv sync                 # 또는: pip install -e .
```

## 설정

연결 정보는 코드에 하드코딩하지 않고 **환경 변수** 또는 생성자 인자로 전달합니다.
`.env.example`를 복사해 채우세요:

| 환경 변수 | 설명 |
|---|---|
| `DAOU_BASE_URL` | 테넌트 URL (`https://회사.daouoffice.com`) |
| `DAOU_COMPANY_ID` | 숫자 회사 id (`daoubot discover`로 조회) |
| `DAOU_LOGIN_ID` | 봇 계정 로그인 id |
| `DAOU_PASSWORD` | 봇 계정 비밀번호 |

> LLM은 SDK에 포함돼 있지 않습니다. `bot-assistant` 예제가 핸들러 안에서
> OpenAI 호환 API를 호출하는 법을 보여줍니다 (`LLM_BASE_URL`/`LLM_API_KEY`).

### 온보딩: `login` → 프로필 저장

처음 한 번 `login` 하면 회사·사용자 정보와 세션 토큰이
`./.daoubot/profile.json` 에 저장되고(비밀번호는 저장 안 함, `.daoubot/` 는
gitignore), 이후 명령은 자격증명 없이 그 프로필로 동작합니다. `company_id` 를
주지 않으면 공개 엔드포인트로 자동 탐색합니다.

```bash
daoubot login --base-url https://yourcompany.daouoffice.com \
  --login-id my-bot --password '...'
# → .daoubot/profile.json 저장 + 회사/사용자 정보 출력 (토큰은 미출력)
```

설정 우선순위: **명시 인자/CLI 플래그 > 환경 변수 > 프로필 파일**. 토큰이
만료되면 자격증명이 있을 때 자동 재로그인하고, 없으면 `daoubot login` 을
다시 안내합니다.

예제·아래 코드는 네 개의 `DAOU_*` 를 **명시적으로 환경에서 읽어** 무엇이
필요한지 코드에 드러냅니다(시크릿 하드코딩 없음, 마법 없음). 실배포/CLI 용
단축이 필요하면 `DaouBot.from_env(...)` / `BotClient.from_env()` 가 env·프로필을
읽어 한 줄로 생성합니다(`load_settings()` 직접 조회 가능, 비밀번호는 프로필에서
절대 안 읽음).

## 빠른 시작

```python
import asyncio
import os

from daouoffice import DaouBot, NewMessage

async def on_message(msg: NewMessage) -> str | None:
    if "안녕" in msg.message_text:
        return f"안녕하세요, {msg.sender_name}님!"
    return None  # 응답 안 함

async def main():
    bot = DaouBot(
        base_url=os.environ["DAOU_BASE_URL"],
        company_id=os.environ["DAOU_COMPANY_ID"],
        login_id=os.environ["DAOU_LOGIN_ID"],
        password=os.environ["DAOU_PASSWORD"],
        on_message=on_message,
    )
    await bot.run_forever()   # Ctrl-C / SIGTERM 시 graceful 종료

asyncio.run(main())
```

`on_message` 가 문자열을 반환하면 답장, `None` 이면 무응답입니다. 핸들러를
주지 않으면 봇은 메시지를 읽기만 합니다(답장 안 함). 30분 만료 시 자격증명이
있으면 자동 재로그인합니다.

> 봇 계정은 누구나 아무 방에나 초대할 수 있습니다. 특정 방에서만 동작시키려면
> `RoomRouter` 를 쓰세요 — 등록한 방만 처리하고 나머지는 무시합니다(allowlist).
> `bot = DaouBot(..., on_message=router)`. 예제: `examples/bot-router`.

**멘션:** 다우오피스 멘션은 본문 인라인 토큰입니다(전체 공개, 비공개 아님 —
[docs/03-messages.md](docs/03-messages.md) §3.6). SDK가 파싱해 `msg.mentions` /
`msg.mentions_me` / `msg.mention_all` 와 사람이 읽는 `message_text`(토큰 →
`@이름`), 원본 `raw_text` 를 제공합니다. 바쁜 그룹에서 멘션 시에만 응답하려면
`only_when_mentioned(handler)` 로 감싸세요(글로벌 노브 아님 — 정책은 선언으로).

```python
bot = DaouBot(..., on_message=only_when_mentioned(handle))
```

**재시작 복구:** "어디까지 처리했는지"(방별 마지막 메시지 id)는 기본적으로
`.daoubot/cursors.json` 에 저장됩니다 — 봇이 재시작해도 백로그를 다시 처리하거나
다운타임 메시지를 건너뛰지 않고 이어받습니다. 비영속을 원하면
`DaouBot(..., cursor_store=MemoryCursorStore())`. 단, 폴링 특성상 따라잡기는
방당 최근 ~20개 히스토리 창 안으로 제한됩니다(그보다 오래 다운되면 창 밖
메시지는 복구 불가 — "since id" 엔드포인트가 없음).

**전달 보장:** 엔진은 **at-least-once** 를 보장합니다 — 메시지 전달의 업계
표준(Kafka/SQS/Slack/Telegram)이라 노브로 노출하지 않고 SDK가 책임집니다.
핸들러가 예외 없이 끝날 때까지 방 내 순서대로 재전달하며, 같은 메시지가
`max_attempts`(기본 5)회 실패하면 poison으로 건너뜁니다.

- 중복이 의미를 가지면 **핸들러를 멱등하게** 작성하세요 (Kafka/SQS 교리).
  트랜스포트 dedup은 엔진, 비즈니스 멱등성은 핸들러 책임.
- fire-and-forget(재시도 원치 않음)은 별도 모드가 아니라 **핸들러가 자기
  예외를 삼키면**(실패로 안 침) 자연히 표현됩니다.

## CLI

```bash
daoubot login ...                      # 인증 + 프로필 저장 (위 참고)
daoubot discover --base-url <url>      # 회사 id / uuid / 도메인 (인증 불필요)
daoubot whoami                         # 저장된 봇 신원 출력
daoubot rooms                          # 채팅방 목록 (room id 포함)
daoubot room create --users a,b --name "Bot Test" [--type GROUP]
daoubot room open <room_id>            # 방 상세 + 구성원
daoubot send <room_id> "<text>"        # 메시지 전송
daoubot start                          # 폴링 봇 실행
```

개발자는 `login` → `rooms`/`room create` 로 필요한 `company_id`·`user_id`·
`room_id` 를 손에 넣은 뒤, 그 값들로 SDK 봇을 작성하면 됩니다.
(설치 없이: `uv run python -m daouoffice.cli rooms`)

## 예제

`examples/` 의 각 봇은 `DAOU_*` 환경 변수만 설정하면 그대로 실행됩니다:

| 예제 | 설명 |
|---|---|
| `bot-echobot` | 받은 메시지를 그대로 반복 |
| `bot-command` | `!cmd args` 명령 디스패처 (help/echo/whoami) |
| `bot-conversation` | 방별 상태 머신 대화 |
| `bot-assistant` | 핸들러에서 OpenAI 호환 LLM 호출 (LLM_* env 필요) |
| `bot-router` | 방별 핸들러 분기 (등록한 방만 처리하는 allowlist) |
| `bot-error-handler` | 핸들러 예외를 잡아 개발자 방에 알림 |

```bash
uv run --with python-daouoffice-bot examples/bot-echobot/bot.py
```

## AI로 봇 만들기 (Claude Code 스킬)

저장소에 Claude Code **스킬**이 포함돼 있어, 클론한 폴더를 Claude Code로 열면
바로 AI에게 "다우오피스 봇 만들어줘"라고 시켜 스캐폴딩·확장할 수 있습니다.

```
.claude/skills/daouoffice-bot/   # SKILL.md + reference.md + scaffold.py
```

- 자동 인식(저장소를 Claude Code로 열면) 또는 `~/.claude/skills/` 로 복사해
  전역 사용.
- 스킬은 템플릿 메뉴가 아니라 **설계 가이드**입니다 — AI가 요구사항을
  인터뷰하고(테넌트·대상 방·트리거·상태·부작용), 결정 매트릭스로 프리미티브
  (`on_message`/`RoomRouter`/`only_when_mentioned`/상태/LLM)를 조합해
  사용자가 원하는 봇을 만들도록, SDK 불변규칙(계정 전역 read·allowlist·
  멱등성·없는 API 날조 금지)과 함께 가르칩니다.
- `scaffold.py` 는 유스케이스를 추측하지 않고 **올바른 보일러플레이트만**
  출력합니다(env/프로필 연결 + graceful run + 빈 핸들러). 설계는 AI가
  요구사항에서 결정: `python .claude/skills/daouoffice-bot/scaffold.py > bot.py`

## SDK 개요

| 심볼 | 설명 |
|---|---|
| `BotClient` | REST API 래퍼 (로그인·방·메시지·`whoami`·`discover_company`) |
| `BotEngine` | 폴링 엔진 (단일 구현, async) |
| `DaouBot` | 고수준 봇 (`on_message` + 폴링 + 401 자동 재로그인) |
| `RoomRouter` | 방별 핸들러 분기 (등록한 방만 처리, 나머지 무시) |
| `only_when_mentioned` | 봇 멘션(`@봇`/`@전체`) 시에만 핸들러 실행 |
| `load_settings` / `.from_env()` | env·프로필에서 연결설정 단일 조회 |
| `FileCursorStore` / `MemoryCursorStore` | 처리 위치 영속/비영속 저장 |
| `NewMessage` | 정규화된 수신 메시지 |
| `BotIdentity` | 로그인 시 해석된 봇 자신의 신원 |
| `Profile` | `daoubot login` 이 저장하는 프로필 (`load_profile`) |
| `DaouAuthError` / `DaouConfigError` | 예외 |

전달은 **폴링만** 사용합니다. WebSocket(`GET /ws/pc`, STOMP)은 캡처에서
엔드포인트만 관측됐을 뿐 흐름을 검증하지 못해 **구현하지 않았습니다**
(미검증 RE 메모: [docs/04-websocket.md](docs/04-websocket.md)).

## 프로젝트 구조

```
src/daouoffice/   SDK 패키지 (import daouoffice)
examples/         실행 가능한 예제 봇
docs/             역분석된 API 엔드포인트 문서
tools/            SAZ 캡처 분석 스크립트 (개발용)
tests/            pytest (네트워크는 respx로 목)
```

## 개발

```bash
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

설계 배경과 다이어그램은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
향후 계획은 [ROADMAP.md](ROADMAP.md), 기여 가이드는
[CONTRIBUTING.md](CONTRIBUTING.md), 변경 이력은
[CHANGELOG.md](CHANGELOG.md)를 참고하세요.

## 라이선스

[MIT](LICENSE) © junsik
