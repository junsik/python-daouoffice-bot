"""Minimal Markdown → DaouOffice chat-HTML renderer.

DaouOffice chat does not render Markdown; its message body is an HTML
*subset*. Captured live traffic shows exactly these tags are honored —
``<b>`` (bold), ``<i>`` (italic), ``<ol><li>`` (numbered list),
``<ul><li>`` (bullet list), ``<br>`` (line break). Nothing else.

So this converts only the Markdown that maps onto that subset:

* ``**bold**`` / ``__bold__``        → ``<b>…</b>``
* ``*italic*`` / ``_italic_``        → ``<i>…</i>``
* ``1.`` / ``2)`` lines              → ``<ol><li>…</li>…</ol>``
* ``-`` / ``*`` / ``+`` lines        → ``<ul><li>…</li>…</ul>``
* newline → ``<br>``; blank line → paragraph gap

Anything else (headings, code, links, blockquotes) has no chat
equivalent, so it degrades to its literal text rather than emitting a
tag the client would show raw. All text is HTML-escaped first, so user
content containing ``<``/``&`` can neither break the markup nor inject.

Opt in per bot with ``DaouBot(markdown=True)``; the engine then renders
every handler reply through :func:`to_chat_html` before sending.
"""

from __future__ import annotations

import html
import re

_OL = re.compile(r"\s*\d+[.)]\s+(.*)")
_UL = re.compile(r"\s*[-*+]\s+(.*)")
_BOLD_STAR = re.compile(r"\*\*(.+?)\*\*")
_BOLD_USCORE = re.compile(r"__(.+?)__")
_ITALIC_STAR = re.compile(r"\*(.+?)\*")
# Underscore italics only at word boundaries, so snake_case is left alone.
_ITALIC_USCORE = re.compile(r"(?<![A-Za-z0-9])_(.+?)_(?![A-Za-z0-9])")


def _inline(text: str) -> str:
    """Escape, then apply bold/italic. Bold first so ``**`` can't be read
    as two italics; afterwards no ``**`` remains for the italic pass."""
    text = html.escape(text, quote=False)
    text = _BOLD_STAR.sub(r"<b>\1</b>", text)
    text = _BOLD_USCORE.sub(r"<b>\1</b>", text)
    text = _ITALIC_STAR.sub(r"<i>\1</i>", text)
    text = _ITALIC_USCORE.sub(r"<i>\1</i>", text)
    return text


def to_chat_html(text: str) -> str:
    """Render Markdown ``text`` to the DaouOffice chat-HTML subset.

    Only bold, italic, ordered/unordered lists and line breaks are
    produced (the only tags the chat client honors); everything else
    becomes its escaped literal text.
    """
    lines = text.split("\n")
    # Each piece is (kind, html): kind "list" is a standalone block,
    # "text" lines are joined by <br> (a blank line → empty text → gap).
    pieces: list[tuple[str, str]] = []
    i = 0
    while i < len(lines):
        if _OL.fullmatch(lines[i]):
            items = []
            while i < len(lines) and (m := _OL.fullmatch(lines[i])):
                items.append(f"<li>{_inline(m.group(1))}</li>")
                i += 1
            pieces.append(("list", "<ol>" + "".join(items) + "</ol>"))
            continue
        if _UL.fullmatch(lines[i]):
            items = []
            while i < len(lines) and (m := _UL.fullmatch(lines[i])):
                items.append(f"<li>{_inline(m.group(1))}</li>")
                i += 1
            pieces.append(("list", "<ul>" + "".join(items) + "</ul>"))
            continue
        pieces.append(("text", _inline(lines[i])))
        i += 1

    # Drop blank lines at the very start/end so they don't yield an
    # orphan leading/trailing <br>.
    while pieces and pieces[0] == ("text", ""):
        pieces.pop(0)
    while pieces and pieces[-1] == ("text", ""):
        pieces.pop()

    out: list[str] = []
    for idx, (kind, frag) in enumerate(pieces):
        if kind == "text" and idx > 0 and pieces[idx - 1][0] == "text":
            out.append("<br>")
        out.append(frag)
    return "".join(out)
