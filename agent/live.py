"""Live view: screenshots of what the agent just did, shown in the interface while it works.

After a step that changes something (a browser or folder opens, a file is written, a program starts ...) the
screen is captured and streamed to the interface together with the step text, so you can watch the automation.

Privacy: the screenshots are a small JPEG of your own screen, kept only in data/live (the newest 40 are kept),
shown only in your own interface, and never sent to the model or to any cloud service.
"""
from __future__ import annotations

import time
from pathlib import Path

from appconfig import ROOT, cfg

LIVE_DIR = ROOT / "data" / "live"
_KEEP = 40
_enabled_override: bool | None = None

# Seconds to wait before the capture so the new window has time to appear and paint.
_DELAYS = {"open_website": 3.0, "open_application": 2.2, "open_folder": 2.2, "open_in_notepad": 2.2, "install_software": 1.5,
           "start_password_reset": 3.0, "m365_sign_in": 3.0}


def set_enabled(value: bool | None) -> None:
    """Runtime switch from the interface. None = follow config.yaml (`live_view.enabled`)."""
    global _enabled_override
    _enabled_override = value


def is_enabled() -> bool:
    if _enabled_override is not None:
        return _enabled_override
    return bool(cfg("live_view", "enabled", default=True))


def capture(task_id: str, tool: str = "") -> str | None:
    """Save a screenshot of the whole desktop and return its path (None if live view is off or capture fails)."""
    if not is_enabled():
        return None
    try:
        from PIL import ImageGrab
        time.sleep(_DELAYS.get(tool, 0.8))
        image = ImageGrab.grab(all_screens=True).convert("RGB")
        image.thumbnail((1280, 800))
        LIVE_DIR.mkdir(parents=True, exist_ok=True)
        path = LIVE_DIR / f"{task_id}_{int(time.time() * 1000)}.jpg"
        image.save(path, "JPEG", quality=70)
        for old in sorted(LIVE_DIR.glob("*.jpg"), key=lambda p: p.stat().st_mtime)[:-_KEEP]:
            old.unlink(missing_ok=True)
        return str(path)
    except Exception:
        return None            # a missing screenshot must never break the task


def clear() -> None:
    """Delete all captured screenshots."""
    for f in Path(LIVE_DIR).glob("*.jpg"):
        f.unlink(missing_ok=True)
