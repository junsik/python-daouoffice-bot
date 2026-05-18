#!/usr/bin/env python
"""AI assistant bot — replies to every message using an LLM backend.

Configure the DaouOffice connection via DAOU_* env vars (see README), plus the
LLM backend. For the OpenAI-compatible API backend::

    export DAOU_LLM_BASE_URL="https://your-gateway/v1"
    export DAOU_LLM_API_KEY="sk-..."

    uv run --with python-daouoffice-bot bot.py --llm api --model claude-sonnet-4-5

Or use a local CLI backend::

    uv run --with python-daouoffice-bot bot.py --llm claude-cli
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os

from daouoffice import DaouBot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AI assistant bot")
    p.add_argument(
        "--llm",
        default="api",
        choices=("api", "claude-cli", "ollama", "hermes-cli", "none"),
    )
    p.add_argument("--model", default="claude-sonnet-4-5")
    return p.parse_args()


async def main() -> None:
    args = parse_args()
    bot = DaouBot(
        login_id=os.environ["DAOU_LOGIN_ID"],
        password=os.environ["DAOU_PASSWORD"],
        llm=args.llm,
        llm_model=args.model,
    )
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
