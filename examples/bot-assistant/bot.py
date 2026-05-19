#!/usr/bin/env python
"""AI assistant bot — how to plug an LLM into a handler.

The SDK bundles no LLM; this calls an OpenAI-compatible chat API inside the
handler (swap for Anthropic/Ollama/your own logic).

Connection resolves from the `daoubot login` profile / DAOU_* env (see
bot-echobot / README). This example's own config:
    LLM_BASE_URL  OpenAI-compatible base, e.g. https://gateway/v1
    LLM_API_KEY   bearer key
    LLM_MODEL     model name (optional, default gpt-4o-mini)

    uv run --with python-daouoffice-bot --with httpx examples/bot-assistant/bot.py
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx

from daouoffice import DaouBot, NewMessage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

LLM_BASE_URL = os.environ["LLM_BASE_URL"].rstrip("/")
LLM_API_KEY = os.environ["LLM_API_KEY"]
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
SYSTEM_PROMPT = "너는 다우오피스 메신저에 연결된 비서야. 간결하고 정확하게 답해."


async def on_message(msg: NewMessage) -> str:
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": msg.message_text},
                    ],
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        logger.exception("LLM call failed")
        return "죄송합니다. 지금은 응답을 생성할 수 없어요."


async def main() -> None:
    bot = DaouBot(on_message=on_message)
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
