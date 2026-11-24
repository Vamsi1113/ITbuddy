"""How Tobi talks: like an assistant who gets on with the job, not like a form.

  offer   the line on an approval card: "Sure, I'll save RAGAS.txt as a PDF on your Desktop. Just say OK and I'll do it."
  done    after a change worked:          "Done! Saved RAGAS.txt as a PDF ... ✓" + what was checked
  failed  after a change did not work:    "I tried to ..., but it didn't work: ..."
  declined when the user said no:         "Okay, I'll leave it. Nothing was changed."

The texts are built in Python from the plan (what will happen is never invented); only the wording is friendly.
"""
from __future__ import annotations

import re

_KEEP_CASE = re.compile(r"^([A-Z]{2,}|[A-Z][a-z]*[A-Z]|[A-Z]\w*\.\w+)")      # "VPN", "OneDrive", "RAGAS.txt": keep as is

# imperative first word -> past tense, for "Done! Saved ..." lines
_PAST = {"save": "Saved", "open": "Opened", "close": "Closed", "clear": "Cleared", "delete": "Deleted", "install": "Installed",
         "print": "Printed", "make": "Made", "set": "Set", "switch": "Switched", "restart": "Restarted", "raise": "Raised",
         "remember": "Remembered", "record": "Recorded", "take": "Took", "flush": "Flushed", "empty": "Emptied",
         "fix": "Fixed", "send": "Sent", "write": "Wrote", "create": "Created", "turn": "Turned", "run": "Ran",
         "start": "Started", "add": "Added", "remove": "Removed", "clean": "Cleaned", "search": "Searched",
         "download": "Downloaded", "press": "Pressed", "click": "Clicked", "type": "Typed", "move": "Moved",
         "copy": "Copied", "rename": "Renamed", "update": "Updated", "enable": "Enabled", "disable": "Disabled",
         "bring": "Brought", "reset": "Reset", "free": "Freed", "stop": "Stopped"}


def _lower_first(text: str) -> str:
    text = (text or "").strip().rstrip(".")
    if not text or _KEEP_CASE.match(text):
        return text
    return text[0].lower() + text[1:]


def _nicer(text: str) -> str:
    """Small wording fixes: 'in Desktop' -> 'on your Desktop', 'in Documents' -> 'in your Documents'."""
    text = re.sub(r"\bin Desktop\b", "on your Desktop", text)
    text = re.sub(r"\bin (Documents|Downloads)\b", r"in your \1", text)
    return text


def past(summary: str) -> str:
    """'Save X as a PDF' -> 'Saved X as a PDF' (falls back to the summary itself)."""
    s = _nicer((summary or "").strip().rstrip("."))
    first, _, rest = s.partition(" ")
    word = _PAST.get(first.lower())
    return f"{word} {rest}".strip() if word else s


def offer(summary: str) -> str:
    """The friendly line at the top of an approval card."""
    s = _nicer(_lower_first(summary)) or "do that"
    return f"Sure, I'll {s}. Just say OK and I'll get it done."


def done(summary: str, note: str = "") -> str:
    line = f"Done! {past(summary)} ✓"
    note = (note or "").strip()
    if note and not note.lower().startswith(("it was opened", "the action completed")):
        line += f"\n\n{note}"
    return line


def failed(summary: str, note: str = "") -> str:
    return f"I tried to {_lower_first(_nicer(summary)) or 'do that'}, but it didn't work out. {note}".strip()


def declined() -> str:
    return "Okay, I'll leave it as it is, nothing was changed."
