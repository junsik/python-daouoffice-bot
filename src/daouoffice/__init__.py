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
from daouoffice.engine import BotEngine
from daouoffice.profile import Profile, load_profile, save_profile
from daouoffice.sdk_bot import DaouBot

__all__ = (
    "BotClient",
    "BotEngine",
    "BotIdentity",
    "ChatHistoryItem",
    "ChatRoomItem",
    "DaouAuthError",
    "DaouBot",
    "DaouConfigError",
    "NewMessage",
    "Profile",
    "RoomOpenData",
    "__version__",
    "__version_info__",
    "load_profile",
    "save_profile",
)
