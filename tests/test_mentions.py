"""Tests for mention-token parsing and the mention gate."""

from __future__ import annotations

import pytest

from daouoffice import NewMessage, only_when_mentioned
from daouoffice.client import ChatHistoryItem, parse_mentions
from daouoffice.engine import BotEngine

USER_TOKEN = "{{00000000-0000-0000-0000-000000000000::USER::@홍길동::11000000001}}"
ALL_TOKEN = "{{00000000-0000-0000-0000-000000000000::ALL::@ALL}}"


def test_parse_user_mention() -> None:
    clean, ids, all_ = parse_mentions(f"{USER_TOKEN} 안녕")
    assert clean == "@홍길동 안녕"
    assert ids == ["11000000001"]
    assert all_ is False


def test_parse_mention_all() -> None:
    clean, ids, all_ = parse_mentions(f"{ALL_TOKEN} 공지")
    assert clean == "@ALL 공지"
    assert ids == []
    assert all_ is True


def test_parse_multiple_and_plain() -> None:
    other = "{{abc::USER::@임꺽정::11000000002}}"
    clean, ids, _ = parse_mentions(f"{USER_TOKEN}{other} hi")
    assert ids == ["11000000001", "11000000002"]
    assert clean == "@홍길동@임꺽정 hi"
    assert parse_mentions("no mention here") == ("no mention here", [], False)


class _Client:
    user_id = "11000000001"


def _item(text: str) -> ChatHistoryItem:
    return ChatHistoryItem(
        chatRoomId="r1",
        chatMessageId=10,
        sender={"platformUserId": "999", "platformUserName": "보낸이"},
        contents={"message": {"text": text}},
    )


def test_engine_populates_mention_fields() -> None:
    engine = BotEngine(_Client(), lambda m: None)
    msg = engine._to_message(_item(f"{USER_TOKEN} 질문"), "GROUP")
    assert msg is not None
    assert msg.message_text == "@홍길동 질문"
    assert msg.raw_text.startswith("{{")
    assert msg.mentions == ["11000000001"]
    assert msg.mentions_me is True  # client.user_id is in mentions
    assert msg.mention_all is False


def _msg(*, mentions_me=False, mention_all=False) -> NewMessage:
    return NewMessage(
        room_id="r1",
        room_type="GROUP",
        sender_user_id="u",
        sender_name="T",
        message_text="hi",
        message_id="1",
        created_at="",
        mentions_me=mentions_me,
        mention_all=mention_all,
    )


@pytest.mark.asyncio
async def test_only_when_mentioned_gate() -> None:
    gated = only_when_mentioned(lambda m: "pong")

    assert await gated(_msg(mentions_me=True)) == "pong"
    assert await gated(_msg(mention_all=True)) == "pong"  # include_all default
    assert await gated(_msg()) is None  # not addressed → silent


@pytest.mark.asyncio
async def test_only_when_mentioned_exclude_all() -> None:
    gated = only_when_mentioned(lambda m: "pong", include_all=False)
    assert await gated(_msg(mention_all=True)) is None
    assert await gated(_msg(mentions_me=True)) == "pong"
