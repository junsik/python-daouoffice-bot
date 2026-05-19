"""Local developer profile: persisted connection + identity info.

`daoubot login` writes a profile so later commands work without re-auth.
Stored in ``./.daoubot/profile.json`` (gitignore ``.daoubot/``). The session
token and password are saved so the bot can re-authenticate unattended; the
file is chmod 600 where supported and only ever printed via `public_dict()`
(``****``-masked). Lookup walks up parent directories, so an example run from
a subfolder still finds the repo-root profile (like git finding ``.git``).
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

PROFILE_DIR = ".daoubot"
PROFILE_FILE = "profile.json"


@dataclass(slots=True)
class Profile:
    base_url: str = ""
    company_id: str = ""
    company_uuid: str = ""
    company_domain: str = ""
    login_id: str = ""
    user_id: str = ""
    name: str = ""
    access_token: str = ""
    password: str = ""
    saved_at: str = ""

    def public_dict(self) -> dict:
        """Profile with secrets masked as ``****`` (safe to print/log).

        The real ``password``/``access_token`` are kept in the on-disk file
        (chmod 600, gitignored) so the bot can re-authenticate unattended;
        only this stdout view masks them.
        """
        d = asdict(self)
        for secret in ("access_token", "password"):
            if d.get(secret):
                d[secret] = "****"
        return d


def profile_path(
    base_dir: str | os.PathLike[str] | None = None,
    *,
    path: str | os.PathLike[str] | None = None,
) -> Path:
    """Resolve where the profile is *written*.

    ``path`` (the CLI ``--config`` value) is an explicit file location and
    wins. Otherwise ``<base_dir or cwd>/.daoubot/profile.json``.
    """
    if path:
        return Path(path)
    root = Path(base_dir) if base_dir else Path.cwd()
    return root / PROFILE_DIR / PROFILE_FILE


def find_profile(
    base_dir: str | os.PathLike[str] | None = None,
) -> Path | None:
    """Locate an existing profile, searching ``base_dir``/cwd then parents.

    A bot run from ``examples/foo/`` still finds the repo-root profile,
    matching how git resolves ``.git`` from any subdirectory.
    """
    start = Path(base_dir) if base_dir else Path.cwd()
    for d in (start, *start.parents):
        fp = d / PROFILE_DIR / PROFILE_FILE
        if fp.exists():
            return fp
    return None


def load_profile(
    base_dir: str | os.PathLike[str] | None = None,
    *,
    path: str | os.PathLike[str] | None = None,
) -> Profile | None:
    if path:
        fp = Path(path)
    else:
        fp = find_profile(base_dir)
    if not fp or not fp.exists():
        return None
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    known = set(Profile.__dataclass_fields__)
    return Profile(**{k: v for k, v in data.items() if k in known})


def save_profile(
    profile: Profile,
    base_dir: str | os.PathLike[str] | None = None,
    *,
    path: str | os.PathLike[str] | None = None,
) -> Path:
    profile.saved_at = datetime.now(UTC).isoformat(timespec="seconds")
    fp = profile_path(base_dir, path=path)
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(
        json.dumps(asdict(profile), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    try:  # best-effort: restrict to owner (no-op on Windows)
        fp.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return fp
