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
