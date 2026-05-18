"""Tests for settings resolution (arg > env > profile)."""

from __future__ import annotations

import pytest

from daouoffice import DaouBot, load_settings
from daouoffice.client import DaouConfigError
from daouoffice.profile import Profile, save_profile

ENV_KEYS = ("DAOU_BASE_URL", "DAOU_COMPANY_ID", "DAOU_LOGIN_ID", "DAOU_PASSWORD")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.chdir(tmp_path)  # isolate .daoubot/


def test_env_resolution(monkeypatch) -> None:
    monkeypatch.setenv("DAOU_BASE_URL", "https://acme.daouoffice.com")
    monkeypatch.setenv("DAOU_COMPANY_ID", "11000000000")
    monkeypatch.setenv("DAOU_LOGIN_ID", "bot")
    monkeypatch.setenv("DAOU_PASSWORD", "pw")
    s = load_settings()
    assert s.base_url == "https://acme.daouoffice.com"
    assert s.company_id == "11000000000"
    assert s.login_id == "bot" and s.password == "pw"


def test_profile_fallback_but_never_password(tmp_path, monkeypatch) -> None:
    save_profile(
        Profile(
            base_url="https://acme.daouoffice.com",
            company_id="11000000000",
            login_id="bot",
            access_token="tok",
        ),
        base_dir=tmp_path,
    )
    s = load_settings()
    assert s.base_url == "https://acme.daouoffice.com"
    assert s.login_id == "bot"
    assert s.password == ""  # never sourced from the profile
    monkeypatch.setenv("DAOU_PASSWORD", "pw")
    assert load_settings().password == "pw"


def test_explicit_arg_overrides_env(monkeypatch) -> None:
    monkeypatch.setenv("DAOU_BASE_URL", "https://env.daouoffice.com")
    s = load_settings(base_url="https://explicit.daouoffice.com")
    assert s.base_url == "https://explicit.daouoffice.com"


def test_missing_base_url_raises() -> None:
    with pytest.raises(DaouConfigError, match="base_url"):
        load_settings()


def test_daoubot_from_env(monkeypatch) -> None:
    monkeypatch.setenv("DAOU_BASE_URL", "https://acme.daouoffice.com")
    monkeypatch.setenv("DAOU_COMPANY_ID", "11000000000")
    monkeypatch.setenv("DAOU_LOGIN_ID", "bot")
    monkeypatch.setenv("DAOU_PASSWORD", "pw")
    bot = DaouBot.from_env()
    assert bot.client._base_url == "https://acme.daouoffice.com"
