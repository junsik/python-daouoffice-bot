"""Tests for RoomRouter: precedence and allowlist-by-default."""

from __future__ import annotations

import pytest

from daouoffice import NewMessage, RoomRouter


def _msg(room_id: str, room_type: str = "GROUP") -> NewMessage:
    return NewMessage(
        room_id=room_id,
        room_type=room_type,
        sender_user_id="u",
        sender_name="Tester",
        message_text="hi",
        message_id="1",
        created_at="",
    )


@pytest.mark.asyncio
async def test_unregistered_room_is_ignored() -> None:
    router = RoomRouter()

    @router.room("known")
    async def _known(m):
        return "hello"

    assert await router(_msg("known")) == "hello"
    assert await router(_msg("random-room")) is None  # allowlist default


@pytest.mark.asyncio
async def test_precedence_room_over_type_over_default() -> None:
    router = RoomRouter(default=lambda m: "default")
    router.add_room_type("GROUP", lambda m: "by-type")
    router.add_room("vip", lambda m: "by-room")

    assert await router(_msg("vip", "GROUP")) == "by-room"
    assert await router(_msg("other", "GROUP")) == "by-type"
    assert await router(_msg("other", "SINGLE")) == "default"


@pytest.mark.asyncio
async def test_sync_and_async_handlers() -> None:
    router = RoomRouter()
    router.add_room("s", lambda m: "sync")

    @router.room("a")
    async def _a(m):
        return "async"

    assert await router(_msg("s")) == "sync"
    assert await router(_msg("a")) == "async"
