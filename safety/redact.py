"""Removes secrets a user pasted into the chat before the text reaches the model or the audit log."""
from __future__ import annotations

import re


def _secret_after_keyword(m: re.Match) -> str:
    # "my password is expired" is not a secret; "my password is Tr0ub4dor&3" is.
    value = m.group(3)
    if "is" in m.group(2) and value.strip(".,!?").isalpha():
        return m.group(0)
    return f"{m.group(1)}{m.group(2)}[REDACTED]"


_PATTERNS = [
    # "password is hunter2", "pwd: abc", "passcode = 1234"
    (re.compile(r"(?i)\b(pass(?:word|code|phrase)?|pwd|pin|otp|secret|api[ _-]?key|token)\b(\s*(?:is|=|:)\s*)(\S+)"),
     lambda m: _secret_after_keyword(m)),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), lambda m: "[REDACTED AWS KEY]"),
    (re.compile(r"\b(?:sk|pk|ghp|gho|xox[baprs])[-_][A-Za-z0-9_\-]{16,}\b"), lambda m: "[REDACTED TOKEN]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
     lambda m: "[REDACTED PRIVATE KEY]"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}\b"), lambda m: "[REDACTED TOKEN]"),
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"), lambda m: "[REDACTED CARD NUMBER]"),
]


def redact(text: str) -> tuple[str, bool]:
    """Return (safe text, whether anything was removed)."""
    found = False
    for pattern, replace in _PATTERNS:
        new = pattern.sub(replace, text or "")
        found = found or new != text
        text = new
    return text, found
