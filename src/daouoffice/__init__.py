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
from daouoffice.engine import AT_LEAST_ONCE, AT_MOST_ONCE, BotEngine
from daouoffice.profile import Profile, load_profile, save_profile
from daouoffice.router import RoomRouter
from daouoffice.sdk_bot import DaouBot
from daouoffice.state import CursorStore, FileCursorStore, MemoryCursorStore

__all__ = (
    "AT_LEAST_ONCE",
    "AT_MOST_ONCE",
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
    "__version__",
    "__version_info__",
    "load_profile",
    "save_profile",
)
