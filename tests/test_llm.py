"""Tests for LLM backend selection and the generate() entry point."""

from __future__ import annotations

import pytest

from daouoffice import __version__
from daouoffice.llm_handler import ApiBackend, BackendRegistry, CliBackend


def test_version_is_string() -> None:
    assert isinstance(__version__, str)
    assert __version__.startswith("0.")


def test_registry_resolves_api() -> None:
    assert isinstance(BackendRegistry.resolve("api"), ApiBackend)


def test_registry_resolves_custom_cli() -> None:
    backend = BackendRegistry.resolve("cli:mytool")
    assert isinstance(backend, CliBackend)
    assert backend._command == "mytool"


def test_registry_unknown_falls_back_to_api() -> None:
    assert isinstance(BackendRegistry.resolve("nonsense"), ApiBackend)


@pytest.mark.asyncio
async def test_generate_combines_build_and_execute() -> None:
    class Dummy(ApiBackend):
        async def execute(self, full_message: str) -> str:
            return f"<<{full_message}>>"

    backend = Dummy()
    out = await backend.generate("hi", context="sender=Bob")
    assert "hi" in out and out.startswith("<<")
