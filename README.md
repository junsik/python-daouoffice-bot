# python-daouoffice-bot

다우오피스(DaouOffice) 메신저용 비공식 봇 SDK.

공식 봇 API가 없는 다우오피스 메신저를, **PC 메신저가 쓰는 REST API를 역분석**하여
파이썬에서 다룰 수 있게 합니다. 방 목록 조회·메시지 송수신·폴링 기반 응답을 지원하며,
선택적으로 LLM 백엔드를 붙여 챗봇을 만들 수 있습니다.

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
| `DAOU_LLM_BASE_URL` | (선택) OpenAI 호환 LLM 게이트웨이 |
| `DAOU_LLM_API_KEY` | (선택) LLM API 키 |

### 회사 id / 봇 사용자 id 조회

`companyId`나 봇 계정의 내부 user id를 모를 때:

```bash
# 회사 메타데이터 (인증 불필요)
daoubot discover --base-url https://yourcompany.daouoffice.com

# 위에서 얻은 company id로 로그인까지 해서 봇 계정 정보 확인
daoubot discover --base-url https://yourcompany.daouoffice.com \
  --company-id 11000000000 --login-id my-bot --password '...'
```

## 빠른 시작

```python
import asyncio
from daouoffice import DaouBot, NewMessage

async def on_message(msg: NewMessage) -> str | None:
    if "안녕" in msg.message_text:
        return f"안녕하세요, {msg.sender_name}님!"
    return None  # 응답 안 함

async def main():
    bot = DaouBot(
        login_id="my-bot",
        password="...",                          # 또는 env DAOU_PASSWORD
        base_url="https://acme.daouoffice.com",  # 또는 env DAOU_BASE_URL
        company_id="11000000000",                # 또는 env DAOU_COMPANY_ID
        llm="none",
        prompt_func=on_message,
    )
    await bot.run_forever()   # Ctrl-C로 종료

asyncio.run(main())
```

메시지 처리 우선순위: `prompt_func` → `!`로 시작하는 명령 → LLM 백엔드 → 무응답.

## CLI

```bash
daoubot discover                  # 회사 id / uuid / 도메인 조회
daoubot whoami                    # 이 봇 계정의 신원 출력
daoubot rooms                     # 채팅방 목록
daoubot send <room_id> "<text>"   # 메시지 전송
daoubot start                     # 폴링 봇 실행
```

(설치 없이: `uv run python -m daouoffice.cli rooms`)

## 예제

`examples/` 의 각 봇은 `DAOU_*` 환경 변수만 설정하면 그대로 실행됩니다:

| 예제 | 설명 |
|---|---|
| `bot-echobot` | 받은 메시지를 그대로 반복 |
| `bot-conversation` | 방별 상태 머신 대화 |
| `bot-assistant` | LLM 백엔드로 자동 응답 |
| `bot-error-handler` | 핸들러 예외를 잡아 개발자 방에 알림 |

```bash
uv run --with python-daouoffice-bot examples/bot-echobot/bot.py
```

## SDK 개요

| 심볼 | 설명 |
|---|---|
| `BotClient` | REST API 래퍼 (로그인·방·메시지·`whoami`·`discover_company`) |
| `BotEngine` | 폴링 엔진 (단일 구현, async) |
| `DaouBot` | 고수준 봇 (`prompt_func` / LLM / 명령) |
| `NewMessage` | 정규화된 수신 메시지 |
| `BotIdentity` | 로그인 시 해석된 봇 자신의 신원 |
| `ApiBackend` / `CliBackend` | LLM 백엔드 (OpenAI 호환 / CLI) |
| `DaouAuthError` / `DaouConfigError` | 예외 |

실시간 WebSocket/STOMP(`ws_handler.py`)는 실험적이며 폴링이 정식 경로입니다.

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
uv run pytest -q
```

기여 가이드는 [CONTRIBUTING.md](CONTRIBUTING.md)를 참고하세요.

## 라이선스

[MIT](LICENSE) © junsik
