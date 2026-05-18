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
from daouoffice.llm_handler import (
    SYSTEM_PROMPT,
    ApiBackend,
    BackendRegistry,
    BaseLlmBackend,
    CliBackend,
)
from daouoffice.sdk_bot import DaouBot

__all__ = (
    "SYSTEM_PROMPT",
    "ApiBackend",
    "BackendRegistry",
    "BaseLlmBackend",
    "BotClient",
    "BotEngine",
    "BotIdentity",
    "ChatHistoryItem",
    "ChatRoomItem",
    "CliBackend",
    "DaouAuthError",
    "DaouBot",
    "DaouConfigError",
    "NewMessage",
    "RoomOpenData",
    "__version__",
    "__version_info__",
)
