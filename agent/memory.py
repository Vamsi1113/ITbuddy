"""Conversation memory: Tobi remembers the earlier messages of the current chat.

Each chat (the desktop window, one Streamlit session) keeps a short list of turns. Before a new message is
routed, a follow-up such as "close the biggest one" or "what about Chrome?" is rewritten into a standalone request
("close chrome.exe (PID 16024)") using that history, so every specialist, tool and safety check works on a
complete request. The chat reply and Autopilot also see the recent turns.

Memory lives only in the running app (it is gone when the chat is cleared or the app restarts). User text is
redacted before it is stored, exactly like the request itself.
"""
from __future__ import annotations

import re
import threading

from appconfig import cfg
from safety.redact import redact

MAX_TURNS = int(cfg("memory", "max_turns", default=12))          # user + assistant messages kept
TURN_CHARS = int(cfg("memory", "turn_chars", default=700))       # each message is shortened to this


class Conversation:
    """The turns of one chat, newest last. Thread-safe: the desktop app adds turns from a worker thread."""

    def __init__(self, max_turns: int = MAX_TURNS) -> None:
        self._turns: list[dict] = []
        self._max = max_turns
        self._lock = threading.Lock()

    def add(self, role: str, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        if role == "user":
            text, _ = redact(text)
        with self._lock:
            self._turns.append({"role": role, "text": text[:TURN_CHARS]})
            del self._turns[:-self._max]

    def turns(self) -> list[dict]:
        with self._lock:
            return list(self._turns)

    def clear(self) -> None:
        with self._lock:
            self._turns.clear()


def as_text(history: list[dict] | None, limit: int = 3000) -> str:
    """The turns as a transcript for a prompt, newest kept when it is too long."""
    lines = [f"{'User' if t['role'] == 'user' else 'Tobi'}: {t['text']}" for t in (history or [])]
    text = "\n".join(lines)
    return text[-limit:]


# Words that point back at the earlier conversation. A long message without them is already standalone, so the
# rewrite call is skipped (saves a model call and keeps the user's own words).
_REFERS_BACK = re.compile(
    r"(?<!\w)(it|its|that|this|those|these|them|they|there|one|ones|same|again|also|too|another|other|others|instead|"
    r"more|else|first|second|third|last|biggest|largest|smallest|top|previous|above|earlier|before|what about|"
    r"how about|and|then|yes|yeah|yep|ok|okay|sure|no|nope|do it|go ahead|why|how come)(?!\w)", re.IGNORECASE)


# In a long message only these clearly point back (a long message with "this" or "and" is usually standalone).
_STRONG_REFERENCE = re.compile(
    r"(?<!\w)(it|them|those|that one|this one|the same|same one|again|instead|what about|how about|"
    r"the (?:biggest|largest|smallest|first|second|last|other|top) (?:one|app|process|file|item)s?|do it|go ahead)(?!\w)",
    re.IGNORECASE)


def needs_context(request: str, history: list[dict] | None) -> bool:
    if not history:
        return False
    words = len(request.split())
    if words <= 6:
        return True
    if words <= 12:
        return bool(_REFERS_BACK.search(request))
    return bool(_STRONG_REFERENCE.search(request))


def standalone(request: str, history: list[dict] | None) -> str:
    """Rewrite a follow-up into a request that makes sense on its own. Returns the request unchanged when it
    already does, when there is no history, or when the model fails (memory must never break a request)."""
    if not needs_context(request, history):
        return request
    from agent import prompts
    from agent.llm import ModelError, ask_json

    def validate(d: dict) -> dict:
        text = str(d.get("request") or "").strip()
        if not text:
            raise ValueError('"request" must be non-empty text')
        return {"request": text[:600]}

    user = f"EARLIER CONVERSATION:\n{as_text(history)}\n\nLATEST MESSAGE: {request.strip()[:500]}"
    try:
        return ask_json(prompts.CONTEXTUALIZE, user, validate)["request"]
    except ModelError:
        return request
