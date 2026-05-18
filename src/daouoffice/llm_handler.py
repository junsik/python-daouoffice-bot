"""DaouOffice Bot — LLM Backend system

OpenClaw / hermes 패턴에 기반한 다중 백엔드 아키텍처.

Backends (implement BaseLlmBackend):
  ApiBackend   — OpenAI-compatible REST API
  CliBackend   — CLI subprocess (claude / hermes / ollama)

BackendRegistry
  - 환경 변수에서 LLM 설정 자동 감지
  - CLI binary 위치 자동 탐색
  - fallback 정책: env > fallback_chain

사용법 (DaouBot에서):
    # API backend
    bot = DaouBot(login_id="...", password="...", llm="api")

    # CLI backend (자동 감지)
    bot = DaouBot(login_id="...", password="...", llm="claude-cli")

    # CLI backend (직접 지정)
    bot = DaouBot(login_id="...", password="...", llm="custom-cli")
    bot._llm_backend = CliBackend(command="ollama", model="llama3.2")
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

import httpx

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# System prompt
# ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "너는 다우오피스 메신저에 연결된 도움이야.\n"
    "사용자의 질문에 간결하고 정확하게 답변해.\n"
    "과장한 설명은 피하고, 필요한 경우만 상세하게 답변해.\n"
    "사용자가 한국어로 말하면 한국어로 답변하고, 영어로 말하면 영어로 답변해."
)


# ──────────────────────────────────────────────────────────────
# Abstract Backend
# ──────────────────────────────────────────────────────────────

class BaseLlmBackend(ABC):
    """LLM 백엔드 추상 클래스.

    모든 백엔드는 이 인터페이스를 구현해야 한다.
    - build_messages(): 시스템/사용자 메시지를 chat format으로 구성
    - execute(): 실제 LLM 호출 (API or CLI), 응답 텍스트 반환
    - fallback_error(): 실패 시 한국어 에러 메시지
    """

    name: str = "base"

    def __init__(
        self,
        *,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self._system_prompt = system_prompt

    @abstractmethod
    def build_messages(self, user_message: str, *, context: str | None = None) -> str:
        """시스템 프롬프트 + 컨텍스트 + 사용자 메시지를 병합."""
        ...

    @abstractmethod
    async def execute(self, full_message: str) -> str:
        """실제 LLM 호출. 응답 텍스트 또는 에러 메시지."""
        ...

    async def generate(self, user_message: str, *, context: str | None = None) -> str:
        """build_messages + execute 를 묶은 공개 진입점."""
        return await self.execute(self.build_messages(user_message, context=context))

    def fallback_error(self) -> str:
        return "죄송합니다. 응답 생성에 실패했습니다."


# ──────────────────────────────────────────────────────────────
# API Backend (OpenAI-compatible)
# ──────────────────────────────────────────────────────────────

class ApiBackend(BaseLlmBackend):
    """OpenAI-compatible REST API 백엔드.

    설정 순서: constructor > env > default
      DAOU_LLM_BASE_URL  → base_url
      DAOU_LLM_API_KEY   → api_key
    """

    name = "api"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-5",
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        super().__init__(system_prompt=system_prompt)
        self._base_url = base_url or os.getenv("DAOU_LLM_BASE_URL", "")
        self._api_key = api_key or os.getenv("DAOU_LLM_API_KEY", "")
        self._model = model

    def build_messages(self, user_message: str, *, context: str | None = None) -> str:
        parts: list[str] = []
        if self._system_prompt:
            parts.append(self._system_prompt)
        if context:
            parts.append(f"[Context: {context}]\n{user_message}")
        else:
            parts.append(user_message)
        return "\n".join(parts)

    async def execute(self, full_message: str) -> str:
        messages: list[dict] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.append({"role": "user", "content": full_message})

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    json={
                        "model": self._model,
                        "messages": messages,
                        "max_tokens": 1024,
                        "temperature": 0.7,
                    },
                    headers=headers,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error("API backend failed: %s", e)
            return self.fallback_error()


# ──────────────────────────────────────────────────────────────
# CLI Backend (claude / hermes / ollama)
# ──────────────────────────────────────────────────────────────

class CliBackend(BaseLlmBackend):
    """CLI subprocess 백엔드.

    hermes/openclaw cli-runner 스타일:
      - command: 실행할 CLI binary
      - args: 고정 인자
      - system_prompt: 별도 파일로 전달하거나 stdin에 포함

    환경 변수:
      DAOU_LLM_COMMAND  — CLI 명령어 (default: "claude")
      DAOU_LLM_ARGS     — 추가 인자 (default: "")
    """

    name = "cli"

    def __init__(
        self,
        *,
        command: str | None = None,
        args: str = "",
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        super().__init__(system_prompt=system_prompt)
        self._command = command or os.getenv("DAOU_LLM_COMMAND", "claude")
        self._args_str = args or os.getenv("DAOU_LLM_ARGS", "")
        self._parsed_args: list[str] = self._args_str.split() if self._args_str else []
        self._tmpdir: Path | None = None

    def build_messages(self, user_message: str, *, context: str | None = None) -> str:
        parts: list[str] = []
        if self._system_prompt:
            parts.append(self._system_prompt)
        if context:
            parts.append(f"[Context: {context}]\n{user_message}")
        else:
            parts.append(user_message)
        return "\n\n".join(parts)

    async def execute(self, full_message: str) -> str:
        try:
            cmd = [self._command, *self._parsed_args]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate(input=full_message.encode())

            if proc.returncode != 0:
                logger.error(
                    "CLI backend %s failed (rc=%d): %s",
                    self._command, proc.returncode,
                    stderr.decode()[:200],
                )
                return self.fallback_error()

            return self._extract_text(stdout.decode().strip())

        except FileNotFoundError:
            logger.error("CLI not found: %s", self._command)
            return self.fallback_error()
        except Exception as e:
            logger.error("CLI backend failed: %s", e)
            return self.fallback_error()

    @staticmethod
    def _extract_text(output: str) -> str:
        """Pull the text out of common CLI JSON shapes; fall back to raw."""
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            return output
        if not isinstance(parsed, dict):
            return output
        for key in ("content", "response", "message", "text"):
            if key not in parsed:
                continue
            val = parsed[key]
            if isinstance(val, list):
                return val[0].get("text", str(val)) if val else output
            return str(val)
        return output


# ──────────────────────────────────────────────────────────────
# Backend Registry (OpenClaw plugin registry 스타일)
# ──────────────────────────────────────────────────────────────

class BackendRegistry:
    """LLM 백엔드 레지스트리.

    env 선택 > fallback chain > 기본값
    """

    # 백엔드별 fallback 체인 (명령어 순서대로 탐색)
    _FALLBACK_CHAINS: ClassVar[dict[str, list[str]]] = {
        # claude code CLI
        "claude-cli": ["claude", "opencode"],
        # ollama
        "ollama": ["ollama"],
        # hermes agent
        "hermes-cli": ["hermes"],
    }

    @classmethod
    def resolve(cls, backend_id: str) -> BaseLlmBackend:
        """backend_id 로 적절한 백엔드 인스턴스 반환.

        Args:
            backend_id: "api" | "claude-cli" | "ollama" | "hermes-cli"

        Returns:
            생성된 백엔드 인스턴스
        """
        if backend_id == "api":
            return ApiBackend()

        if backend_id in cls._FALLBACK_CHAINS:
            return cls._resolve_cli(backend_id)

        # 커스텀 명령어 ("custom-ollama" 같은 것)
        if backend_id.startswith("cli:"):
            command = backend_id[4:]
            return CliBackend(command=command)

        # 기본값
        return ApiBackend()

    @classmethod
    def _resolve_cli(cls, backend_id: str) -> BaseLlmBackend:
        """fallback 체인에서 첫 번째 binary 탐색."""
        chain = cls._FALLBACK_CHAINS[backend_id]
        for cmd in chain:
            if shutil.which(cmd):
                logger.info("Found CLI: %s = %s", backend_id, cmd)
                return CliBackend(command=cmd)
        logger.warning("CLI not found: %s (tried: %s)", backend_id, chain)
        return CliBackend(command=chain[0])  # 찾아도 없음 → 기본 명령어
