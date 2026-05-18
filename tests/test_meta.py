"""Package metadata and public surface."""

from __future__ import annotations

import daouoffice


def test_version_is_string() -> None:
    assert isinstance(daouoffice.__version__, str)
    assert daouoffice.__version__.startswith("0.")


def test_public_api_exports() -> None:
    for name in ("DaouBot", "BotClient", "BotEngine", "NewMessage", "Profile"):
        assert hasattr(daouoffice, name), name
    # LLM backends were removed from the SDK (use a handler / the example).
    assert not hasattr(daouoffice, "ApiBackend")
