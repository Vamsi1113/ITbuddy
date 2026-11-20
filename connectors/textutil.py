"""Small text helpers shared by connectors (kept separate so connector modules never import each other)."""
from __future__ import annotations

import html
import re


def html_to_text(raw: str) -> str:
    """Reduce an HTML page to readable text: no scripts, styles, comments or tags."""
    raw = re.sub(r"(?is)<(script|style|noscript|svg|head)\b.*?</\1>", " ", raw)
    raw = re.sub(r"(?is)<!--.*?-->", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr)>", "\n", raw)
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()
