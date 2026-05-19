"""Markdown → chat-HTML subset renderer."""

from __future__ import annotations

from daouoffice.markdown import to_chat_html


def test_bold_and_italic_both_marker_styles() -> None:
    assert to_chat_html("**a** __b__ *c* _d_") == "<b>a</b> <b>b</b> <i>c</i> <i>d</i>"


def test_bold_not_split_into_two_italics() -> None:
    assert to_chat_html("**strong**") == "<b>strong</b>"


def test_underscore_inside_word_is_not_italic() -> None:
    # snake_case must survive (word-boundary guard on _ italics).
    assert to_chat_html("call do_a_thing now") == "call do_a_thing now"


def test_ordered_list() -> None:
    assert to_chat_html("1. one\n2. two") == "<ol><li>one</li><li>two</li></ol>"


def test_unordered_list_any_marker() -> None:
    assert to_chat_html("- a\n* b\n+ c") == "<ul><li>a</li><li>b</li><li>c</li></ul>"


def test_inline_style_inside_list_item() -> None:
    assert to_chat_html("- **bold** item") == "<ul><li><b>bold</b> item</li></ul>"


def test_text_then_list_with_blank_line() -> None:
    assert to_chat_html("intro\n\n1. x") == "intro<br><ol><li>x</li></ol>"


def test_plain_lines_join_with_br() -> None:
    assert to_chat_html("line1\nline2") == "line1<br>line2"


def test_html_is_escaped_no_injection() -> None:
    assert to_chat_html("a < b & <script>") == "a &lt; b &amp; &lt;script&gt;"


def test_unsupported_markdown_degrades_to_literal_text() -> None:
    # No chat equivalent for headings/links → keep the literal characters
    # rather than emit a tag the client would show raw.
    assert to_chat_html("# Title") == "# Title"
    assert to_chat_html("[x](http://e.com)") == "[x](http://e.com)"


def test_leading_and_trailing_blank_lines_trimmed() -> None:
    assert to_chat_html("\n\nhi\n\n") == "hi"
