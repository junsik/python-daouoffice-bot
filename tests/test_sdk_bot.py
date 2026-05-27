"""Tests for DaouBot wiring: base_dir relocates profile + cursor store."""

from __future__ import annotations

from daouoffice import sdk_bot
from daouoffice.sdk_bot import DaouBot, _build_client
from daouoffice.state import MemoryCursorStore


class _StubClient:
    """Bypass _build_client; DaouBot does not call the client at init."""

    user_id = "BOT"


def test_base_dir_relocates_default_cursor_store(tmp_path) -> None:
    bot = DaouBot(client=_StubClient(), base_dir=tmp_path)
    bot._engine._cursors.set("r1", 7)
    assert (tmp_path / ".daoubot" / "cursors.json").exists()
    assert bot._engine._cursors.get("r1") == 7


def test_explicit_cursor_store_overrides_base_dir(tmp_path) -> None:
    store = MemoryCursorStore()
    bot = DaouBot(client=_StubClient(), base_dir=tmp_path, cursor_store=store)
    assert bot._engine._cursors is store
    bot._engine._cursors.set("r1", 1)
    assert not (tmp_path / ".daoubot" / "cursors.json").exists()


def test_room_filter_is_threaded_into_engine() -> None:
    def room_filter(room) -> bool:
        return room.roomId == "allowed"

    bot = DaouBot(client=_StubClient(), room_filter=room_filter)

    assert bot._engine._room_filter is room_filter


def test_build_client_threads_base_dir_into_load_profile(tmp_path, monkeypatch) -> None:
    seen: list = []

    def _spy(base_dir=None, *, path=None):
        # no saved profile → falls through to password path
        seen.append(base_dir)

    monkeypatch.setattr(sdk_bot, "load_profile", _spy)
    client = _build_client(
        base_url="https://acme.daouoffice.com",
        company_id="11000",
        login_id="acme-bot",
        password="pw",
        base_dir=tmp_path,
    )
    assert seen == [tmp_path]
    assert client is not None


def test_build_client_discovers_company_id_for_password_login(tmp_path, monkeypatch) -> None:
    seen: list[str] = []
    monkeypatch.delenv("DAOU_COMPANY_ID", raising=False)

    def _discover(base_url: str):
        seen.append(base_url)
        return {"companyId": "22000"}

    monkeypatch.setattr(sdk_bot.BotClient, "discover_company", _discover)

    client = _build_client(
        base_url="https://acme.daouoffice.com",
        company_id=None,
        login_id="acme-bot",
        password="pw",
        base_dir=tmp_path,
    )

    assert seen == ["https://acme.daouoffice.com"]
    assert client._company_id == "22000"
