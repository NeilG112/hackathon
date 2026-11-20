"""Strip the HTML wrapper out of GAEB item text.

X83 stores item text as HTML (`<span style=...>`, `<p>`, `<li>`, `<br>`) inside
`<Text>`. GAEB 90 stores it as plain type-26 continuation lines. Both sides run
through here so text comparisons mean something.

Stdlib only — this is imported by the parsers, which must stay dependency-free.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

_WS = re.compile(r"\s+")
_BLOCK_BREAK = {"p", "br", "li", "div", "tr"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in _BLOCK_BREAK:
            self._parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCK_BREAK:
            self._parts.append(" ")

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def strip_html(raw: str) -> str:
    """Return the visible text of an HTML fragment, tags removed."""
    if not raw:
        return ""
    if "<" not in raw:
        return html.unescape(raw)
    parser = _TextExtractor()
    parser.feed(raw)
    parser.close()
    return parser.text()


def collapse_whitespace(raw: str) -> str:
    """Collapse all whitespace runs (incl. newlines, nbsp) to single spaces."""
    return _WS.sub(" ", raw.replace("\xa0", " ")).strip()


def clean_item_text(raw: str) -> str:
    """The function the parsers call. HTML out, whitespace normalized."""
    return collapse_whitespace(strip_html(raw))


def short_text(raw: str, limit: int = 120) -> str:
    """First sentence-ish of an item's text, for table display."""
    cleaned = clean_item_text(raw)
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def compare_key(raw: str) -> str:
    """Lowercased, punctuation-light form for *informational* text comparison.

    The twin-pair gate reports text differences but must not fail on them.
    """
    cleaned = clean_item_text(raw).lower()
    return _WS.sub(" ", re.sub(r"[^\wäöüß ]+", " ", cleaned)).strip()
