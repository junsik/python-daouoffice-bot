"""Connection settings resolution.

One place to answer "where do base_url / company_id / login_id / password
come from". Precedence (highest first):

1. **explicit argument** — e.g. ``DaouBot(base_url=...)``
2. ``DAOU_*`` **environment variable** — ``DAOU_BASE_URL`` / ``DAOU_COMPANY_ID`` /
   ``DAOU_LOGIN_ID`` / ``DAOU_PASSWORD``
3. **operator app config** — an external YAML the SDK is pointed at (via
   ``app_config=`` argument, ``DAOU_APP_CONFIG`` env, or CLI ``--app-config``),
   read-only. Lets a downstream app keep all of its operator-tunable config —
   including the SDK connection — in one declarative file (e.g. an
   ``agent.yaml``) without running ``daoubot login``. The SDK reads a
   top-level ``daouoffice:`` section (``base_url`` / ``company_id`` /
   ``login_id`` / ``password``); values are used literally — no ``${ENV}``
   substitution, since the env tier above already covers that need.
4. **saved profile** — ``~/.daoubot/profile.yaml`` written by ``daoubot login``
   (auto-managed; also holds rotating tokens + identity)

The password sits at every tier because a daemon needs to re-authenticate
unattended; persisting it in the profile (chmod 600, gitignored) makes the
common case zero-config after one ``daoubot login``.

Used by :class:`DaouBot` to resolve connection settings, so a bot is just
``DaouBot(on_message=...)`` after ``daoubot login`` — or
``DaouBot(on_message=..., app_config="agent.yaml")`` when the connection
lives in the operator's own config file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from daouoffice.client import DaouConfigError
from daouoffice.profile import load_profile


@dataclass(slots=True)
class Settings:
    base_url: str
    company_id: str
    login_id: str
    password: str


def load_app_config(path: str | os.PathLike[str]) -> dict[str, str]:
    """Read the operator app config's ``daouoffice:`` section.

    Returns a ``{base_url, company_id, login_id, password}``-shaped dict
    (only the keys present in the file; missing keys absent, not empty
    strings, so :func:`load_settings` can tell "not provided" from
    "explicitly blank").

    The file is a YAML document; values are used literally — operators
    who want env injection set the corresponding ``DAOU_*`` env (it
    overrides this tier anyway).

    Missing file → empty dict (silent — the app config is an optional
    tier). Unparseable file → :class:`DaouConfigError` (operator error,
    fail loud).
    """
    fp = Path(path)
    if not fp.exists():
        return {}
    try:
        doc = yaml.safe_load(fp.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise DaouConfigError(f"app config {fp}: invalid YAML ({e})") from e
    if not isinstance(doc, dict):
        return {}
    section = doc.get("daouoffice") or {}
    if not isinstance(section, dict):
        raise DaouConfigError(
            f"app config {fp}: 'daouoffice:' section must be a mapping, "
            f"got {type(section).__name__}"
        )
    known = {"base_url", "company_id", "login_id", "password"}
    return {k: str(v) for k, v in section.items() if k in known and v is not None}


def load_settings(
    *,
    base_url: str | None = None,
    company_id: str | None = None,
    login_id: str | None = None,
    password: str | None = None,
    use_profile: bool = True,
    config_path: str | None = None,
    app_config: str | os.PathLike[str] | None = None,
) -> Settings:
    """Resolve connection settings (arg > env > app config > profile).

    ``config_path`` points at an explicit profile file (the CLI
    ``--config``); otherwise the default ``~/.daoubot/profile.yaml`` is
    used. ``app_config`` points at an operator YAML whose ``daouoffice:``
    section provides connection values when the operator prefers a
    single declarative file over ``daoubot login``; resolved from the
    arg, then ``DAOU_APP_CONFIG`` env.

    Raises:
        DaouConfigError: if ``base_url`` cannot be resolved.
    """
    prof = load_profile(path=config_path) if use_profile else None
    app_path = app_config or os.getenv("DAOU_APP_CONFIG")
    app = load_app_config(app_path) if app_path else {}

    def pick(value: str | None, env: str, app_key: str, prof_value: str) -> str:
        return value or os.getenv(env) or app.get(app_key, "") or prof_value

    resolved = Settings(
        base_url=pick(base_url, "DAOU_BASE_URL", "base_url", prof.base_url if prof else ""),
        company_id=pick(
            company_id, "DAOU_COMPANY_ID", "company_id", prof.company_id if prof else ""
        ),
        login_id=pick(login_id, "DAOU_LOGIN_ID", "login_id", prof.login_id if prof else ""),
        password=pick(password, "DAOU_PASSWORD", "password", prof.password if prof else ""),
    )
    if not resolved.base_url:
        raise DaouConfigError(
            "base_url unknown — pass it, set DAOU_BASE_URL, point "
            "DAOU_APP_CONFIG at a YAML with a daouoffice: section, or "
            "run `daoubot login`"
        )
    return resolved
