"""Per-room processed-message cursors.

The engine needs to know *up to which message it has already handled* so that a
restart resumes correctly instead of either replaying the backlog or silently
dropping messages that arrived while the bot was down.

A cursor maps ``room_id -> highest handled chatMessageId``.

- :class:`MemoryCursorStore` — process-lifetime only (lost on restart).
- :class:`FileCursorStore` — persisted to ``.daoubot/cursors.json`` so a
  restart picks up where it left off.

Restart caveat: catch-up is bounded by the REST history window (the last ~20
messages per room). If the bot is down long enough that more than that arrive
in a room, messages older than the window cannot be recovered — this is
inherent to polling an API with no "since id" endpoint.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Protocol, runtime_checkable

from daouoffice.profile import PROFILE_DIR

logger = logging.getLogger(__name__)

CURSOR_FILE = "cursors.json"


@runtime_checkable
class CursorStore(Protocol):
    """Persistence interface for per-room processed cursors."""

    def get(self, room_id: str) -> int | None: ...

    def set(self, room_id: str, message_id: int) -> None: ...


class MemoryCursorStore:
    """In-memory cursor store (not durable across restarts)."""

    def __init__(self) -> None:
        self._cursors: dict[str, int] = {}

    def get(self, room_id: str) -> int | None:
        return self._cursors.get(room_id)

    def set(self, room_id: str, message_id: int) -> None:
        self._cursors[room_id] = message_id


class FileCursorStore:
    """Cursor store persisted to ``<base_dir>/.daoubot/cursors.json``."""

    def __init__(self, base_dir: str | os.PathLike[str] | None = None) -> None:
        root = Path(base_dir) if base_dir else Path.cwd()
        self._path = root / PROFILE_DIR / CURSOR_FILE
        self._cursors = self._load()

    def _load(self) -> dict[str, int]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return {str(k): int(v) for k, v in raw.items()}
        except (OSError, json.JSONDecodeError, ValueError, AttributeError):
            return {}

    def get(self, room_id: str) -> int | None:
        return self._cursors.get(room_id)

    def set(self, room_id: str, message_id: int) -> None:
        self._cursors[room_id] = message_id
        self._flush()

    def _flush(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._cursors, indent=2), encoding="utf-8")
            os.replace(tmp, self._path)  # atomic on the same filesystem
        except OSError:
            logger.exception("Failed to persist cursors to %s", self._path)
