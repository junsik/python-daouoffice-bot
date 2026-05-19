"""Connection settings resolution.

One place to answer "where do base_url / company_id / login_id / password
come from": explicit argument > ``DAOU_*`` environment variable > saved
``.daoubot/profile.json``. The password is **never** read from the profile
(it is never stored there) — only from the argument or ``DAOU_PASSWORD``.

Used by :class:`DaouBot` to resolve connection settings, so a bot is just
``DaouBot(on_message=...)`` after ``daoubot login``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from daouoffice.client import DaouConfigError
from daouoffice.profile import load_profile


@dataclass(slots=True)
class Settings:
    base_url: str
    company_id: str
    login_id: str
    password: str


def load_settings(
    *,
    base_url: str | None = None,
    company_id: str | None = None,
    login_id: str | None = None,
    password: str | None = None,
    use_profile: bool = True,
    config_path: str | None = None,
) -> Settings:
    """Resolve connection settings (arg > env > profile; password: arg > env).

    ``config_path`` points at an explicit profile file (the CLI ``--config``);
    otherwise the default ``.daoubot/profile.json`` is used.

    Raises:
        DaouConfigError: if ``base_url`` cannot be resolved.
    """
    prof = load_profile(path=config_path) if use_profile else None

    def pick(value: str | None, env: str, prof_value: str) -> str:
        return value or os.getenv(env) or prof_value

    resolved = Settings(
        base_url=pick(base_url, "DAOU_BASE_URL", prof.base_url if prof else ""),
        company_id=pick(company_id, "DAOU_COMPANY_ID", prof.company_id if prof else ""),
        login_id=pick(login_id, "DAOU_LOGIN_ID", prof.login_id if prof else ""),
        password=password or os.getenv("DAOU_PASSWORD", ""),
    )
    if not resolved.base_url:
        raise DaouConfigError(
            "base_url unknown — pass it, set DAOU_BASE_URL, or run `daoubot login`"
        )
    return resolved
