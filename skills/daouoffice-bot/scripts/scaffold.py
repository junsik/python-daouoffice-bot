#!/usr/bin/env python
"""Print the minimal correct bot skeleton — boilerplate only.

This deliberately does NOT pick a bot "type". The design (router? mention
gate? commands? markdown? state? LLM?) is decided from the user's
requirements per SKILL.md; this only removes the connection/run-loop
ceremony so the agent fills in the handler.

    python scaffold.py > bot.py
"""

from __future__ import annotations

import sys

SKELETON = '''#!/usr/bin/env python
"""DaouOffice bot.

Connection (tenant URL, account, password) is resolved by the SDK in this
order — explicit argument > DAOU_* env > app config YAML's daouoffice:
section (DAOU_APP_CONFIG/app_config=) > ~/.daoubot/profile.yaml. Run
`daoubot login` once first so the profile is populated; after that this
script needs no env or args. To override on a host (e.g. systemd
EnvironmentFile), set DAOU_BASE_URL / DAOU_COMPANY_ID / DAOU_LOGIN_ID /
DAOU_PASSWORD. Never hard-code credentials here.

Run:  python bot.py
"""

from __future__ import annotations

import asyncio
import logging

from daouoffice import DaouBot, NewMessage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)


async def on_message(msg: NewMessage) -> str | None:
    # TODO: implement the behavior the user asked for.
    #   msg.room_id / room_type / sender_name / message_text
    #   msg.mentions_me / mention_all / mentions / raw_text
    # Return a string to reply, or None for no reply. Compose
    # RoomRouter / only_when_mentioned per SKILL.md Step 2 as needed.
    # Keep it idempotent (delivery is at-least-once).
    return None


async def main() -> None:
    # `markdown=True` would render bold/italic/links/lists in replies
    # (chat HTML subset). Leave off unless the design calls for styled
    # output. The engine already auto-threads each reply to the message
    # that triggered it; no flag needed.
    bot = DaouBot(on_message=on_message)
    await bot.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
'''


def main() -> None:
    # UTF-8: skeleton has non-ASCII and the default Windows console codec
    # (cp949 on Korean Windows) would raise UnicodeEncodeError on a pipe.
    sys.stdout.buffer.write(SKELETON.encode("utf-8"))


if __name__ == "__main__":
    main()
