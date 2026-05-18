"""DaouOffice Messenger bot SDK.

Usage::

    from daouoffice import DaouBot

    bot = DaouBot(login_id="...", password="...", base_url="https://...")
    await bot.run_forever()
"""

from daouoffice._version import __version__, __version_info__
from daouoffice.client import (
    BotClient,
    BotIdentity,
    ChatHistoryItem,
    ChatRoomItem,
    DaouAuthError,
    DaouConfigError,
    NewMessage,
    RoomOpenData,
)
from daouoffice.config import Settings, load_settings
from daouoffice.engine import BotEngine
from daouoffice.profile import Profile, load_profile, save_profile
from daouoffice.router import RoomRouter, only_when_mentioned
from daouoffice.sdk_bot import DaouBot
from daouoffice.state import CursorStore, FileCursorStore, MemoryCursorStore

__all__ = (
    "BotClient",
    "BotEngine",
    "BotIdentity",
    "ChatHistoryItem",
    "ChatRoomItem",
    "CursorStore",
    "DaouAuthError",
    "DaouBot",
    "DaouConfigError",
    "FileCursorStore",
    "MemoryCursorStore",
    "NewMessage",
    "Profile",
    "RoomOpenData",
    "RoomRouter",
    "Settings",
    "__version__",
    "__version_info__",
    "load_profile",
    "load_settings",
    "only_when_mentioned",
    "save_profile",
)
