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
    # Profile defaults to ~/.daoubot/; redirect HOME to a temp dir so a
    # developer's real profile never leaks into the test.
    monkeypatch.setattr("daouoffice.profile.Path.home", lambda: tmp_path)


def test_env_resolution(monkeypatch) -> None:
    monkeypatch.setenv("DAOU_BASE_URL", "https://acme.daouoffice.com")
    monkeypatch.setenv("DAOU_COMPANY_ID", "11000000000")
    monkeypatch.setenv("DAOU_LOGIN_ID", "bot")
    monkeypatch.setenv("DAOU_PASSWORD", "pw")
    s = load_settings()
    assert s.base_url == "https://acme.daouoffice.com"
    assert s.company_id == "11000000000"
    assert s.login_id == "bot" and s.password == "pw"


def test_profile_fallback_includes_password(tmp_path, monkeypatch) -> None:
    save_profile(
        Profile(
            base_url="https://acme.daouoffice.com",
            company_id="11000000000",
            login_id="bot",
            access_token="tok",
            password="stored-pw",
        ),
        base_dir=tmp_path,
    )
    s = load_settings()
    assert s.base_url == "https://acme.daouoffice.com"
    assert s.login_id == "bot"
    # Persisted so the daemon re-authenticates unattended.
    assert s.password == "stored-pw"
    # Env still overrides the stored password.
    monkeypatch.setenv("DAOU_PASSWORD", "pw")
    assert load_settings().password == "pw"


def test_profile_base_dir_is_used_for_profile_fallback(tmp_path) -> None:
    save_profile(
        Profile(
            base_url="https://isolated.daouoffice.com",
            company_id="22000",
            login_id="isolated-bot",
            access_token="tok",
            password="stored-pw",
        ),
        base_dir=tmp_path,
    )

    s = load_settings(profile_base_dir=tmp_path)

    assert s.base_url == "https://isolated.daouoffice.com"
    assert s.company_id == "22000"
    assert s.login_id == "isolated-bot"


def test_explicit_arg_overrides_env(monkeypatch) -> None:
    monkeypatch.setenv("DAOU_BASE_URL", "https://env.daouoffice.com")
    s = load_settings(base_url="https://explicit.daouoffice.com")
    assert s.base_url == "https://explicit.daouoffice.com"


def test_missing_base_url_raises() -> None:
    with pytest.raises(DaouConfigError, match="base_url"):
        load_settings()


def test_daoubot_resolves_from_env(monkeypatch) -> None:
    monkeypatch.setenv("DAOU_BASE_URL", "https://acme.daouoffice.com")
    monkeypatch.setenv("DAOU_COMPANY_ID", "11000000000")
    monkeypatch.setenv("DAOU_LOGIN_ID", "bot")
    monkeypatch.setenv("DAOU_PASSWORD", "pw")
    bot = DaouBot(on_message=lambda m: None)
    assert bot.client._base_url == "https://acme.daouoffice.com"


# -- app config tier --------------------------------------------------------


def _write_app_config(path, **daouoffice_fields):
    """Write a minimal operator YAML with a ``daouoffice:`` section."""
    lines = ["daouoffice:"]
    for k, v in daouoffice_fields.items():
        lines.append(f"  {k}: {v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_app_config_provides_connection_values(tmp_path) -> None:
    cfg = tmp_path / "agent.yaml"
    _write_app_config(cfg, base_url="https://acme.daouoffice.com", login_id="bot", password="pw")
    s = load_settings(app_config=cfg)
    assert s.base_url == "https://acme.daouoffice.com"
    assert s.login_id == "bot"
    assert s.password == "pw"


def test_app_config_path_from_env(tmp_path, monkeypatch) -> None:
    cfg = tmp_path / "agent.yaml"
    _write_app_config(cfg, base_url="https://acme.daouoffice.com", login_id="bot")
    monkeypatch.setenv("DAOU_APP_CONFIG", str(cfg))
    assert load_settings().base_url == "https://acme.daouoffice.com"


def test_app_config_loses_to_env_but_beats_profile(tmp_path, monkeypatch) -> None:
    save_profile(
        Profile(base_url="https://from-profile.daouoffice.com", login_id="prof-bot"),
        base_dir=tmp_path,
    )
    cfg = tmp_path / "agent.yaml"
    _write_app_config(cfg, base_url="https://from-app.daouoffice.com", login_id="app-bot")
    # Profile says "from-profile", app config says "from-app" → app wins.
    s = load_settings(app_config=cfg)
    assert s.base_url == "https://from-app.daouoffice.com"
    assert s.login_id == "app-bot"
    # But env overrides app config.
    monkeypatch.setenv("DAOU_BASE_URL", "https://from-env.daouoffice.com")
    assert load_settings(app_config=cfg).base_url == "https://from-env.daouoffice.com"


def test_app_config_missing_file_is_silent(tmp_path) -> None:
    # Operator pointed at a non-existent file: don't fail loud here — the
    # other tiers may still satisfy the resolution. Just behave as no app
    # config given. (Malformed YAML *is* loud — operator error.)
    save_profile(Profile(base_url="https://acme.daouoffice.com"), base_dir=tmp_path)
    s = load_settings(app_config=tmp_path / "missing.yaml")
    assert s.base_url == "https://acme.daouoffice.com"


def test_app_config_malformed_yaml_raises(tmp_path) -> None:
    cfg = tmp_path / "agent.yaml"
    cfg.write_text("daouoffice: [unterminated", encoding="utf-8")
    with pytest.raises(DaouConfigError, match="invalid YAML"):
        load_settings(app_config=cfg)


def test_app_config_no_daouoffice_section_is_empty(tmp_path) -> None:
    # A YAML that exists but has no daouoffice: section should not satisfy
    # the resolution; missing base_url propagates as the usual error.
    cfg = tmp_path / "agent.yaml"
    cfg.write_text("other:\n  key: value\n", encoding="utf-8")
    with pytest.raises(DaouConfigError, match="base_url"):
        load_settings(app_config=cfg)


def test_app_config_bad_section_type_raises(tmp_path) -> None:
    cfg = tmp_path / "agent.yaml"
    cfg.write_text("daouoffice: not-a-mapping\n", encoding="utf-8")
    with pytest.raises(DaouConfigError, match="must be a mapping"):
        load_settings(app_config=cfg)
