"""Tests for mention-token parsing and the mention gate."""

from __future__ import annotations

import pytest

from daouoffice import NewMessage, only_when_addressed, only_when_mentioned
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


def _msg(text: str = "hi", *, mentions_me=False, mention_all=False) -> NewMessage:
    return NewMessage(
        room_id="r1",
        room_type="GROUP",
        sender_user_id="u",
        sender_name="T",
        message_text=text,
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


# -- only_when_addressed ----------------------------------------------------


@pytest.mark.asyncio
async def test_only_when_addressed_token_mention_still_works() -> None:
    # With no aliases set it behaves exactly like only_when_mentioned.
    gated = only_when_addressed(lambda m: "pong")
    assert await gated(_msg(mentions_me=True)) == "pong"
    assert await gated(_msg(mention_all=True)) == "pong"
    assert await gated(_msg("plain talk")) is None


@pytest.mark.asyncio
async def test_only_when_addressed_alias_in_text() -> None:
    gated = only_when_addressed(lambda m: "pong", aliases=("디티", "DT"))
    # Each alias hits, both case variants of DT hit (case-insensitive).
    assert await gated(_msg("안녕 @디티 누구야")) == "pong"
    assert await gated(_msg("hey @DT, what's up")) == "pong"
    assert await gated(_msg("hey @dt, what's up")) == "pong"


@pytest.mark.asyncio
async def test_only_when_addressed_word_boundary_blocks_partial_matches() -> None:
    gated = only_when_addressed(lambda m: "pong", aliases=("디티",))
    # `@디티봇` / `@디티는` should NOT match `@디티` — Hangul boundary.
    assert await gated(_msg("@디티봇 이리와")) is None
    assert await gated(_msg("@디티는 어디?")) is None
    # `@디티스` similarly.
    assert await gated(_msg("ping @디티스 here")) is None
    # But trailing punctuation is fine.
    assert await gated(_msg("@디티, 안녕")) == "pong"
    assert await gated(_msg("@디티.")) == "pong"


@pytest.mark.asyncio
async def test_only_when_addressed_no_naked_alias_without_at() -> None:
    # "디티" alone is plain text, not addressing; must have the @ prefix.
    gated = only_when_addressed(lambda m: "pong", aliases=("디티",))
    assert await gated(_msg("디티 알려줘")) is None


@pytest.mark.asyncio
async def test_only_when_addressed_alias_with_special_chars() -> None:
    # Special regex chars in an alias are escaped, not treated as syntax.
    gated = only_when_addressed(lambda m: "pong", aliases=("dt.bot",))
    assert await gated(_msg("@dt.bot 안녕")) == "pong"
    assert await gated(_msg("@dtXbot 안녕")) is None  # the dot is literal, not "any char"


@pytest.mark.asyncio
async def test_only_when_addressed_exclude_all_still_works() -> None:
    gated = only_when_addressed(lambda m: "pong", aliases=("디티",), include_all=False)
    # include_all=False shuts the @ALL path; alias path still open.
    assert await gated(_msg(mention_all=True)) is None
    assert await gated(_msg("@디티 hi")) == "pong"


@pytest.mark.asyncio
async def test_only_when_addressed_alias_path_independent_of_mentions_me() -> None:
    # Alias hit alone, with no token mention, is enough.
    gated = only_when_addressed(lambda m: "pong", aliases=("디티",))
    assert await gated(_msg("@디티 누구야", mentions_me=False, mention_all=False)) == "pong"
