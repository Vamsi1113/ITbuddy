"""Desktop control with Pywinauto (UIA backend): open_application, click_control, type_text.

Controls are found by their accessible name. No screenshots and no vision model.
Text read from windows is only used to find controls; it is never treated as an instruction.
"""
from __future__ import annotations

import ipaddress
import os
import re
import shutil
import subprocess
import time
import winreg
from pathlib import Path
from urllib.parse import urlparse

from appconfig import cfg
from tools.registry import R1, Param, tool
from tools.urlsafe import clean_url  # noqa: F401  (re-exported: other modules import it from here)


# ---------------------------------------------------------------------------
# Finding and starting programs
# ---------------------------------------------------------------------------
def resolve_exe(command: str) -> str | None:
    """Full path of an executable: PATH first, then the Windows "App Paths" registry (where Chrome, Word, ...
    register themselves)."""
    found = shutil.which(command)
    if found:
        return found
    exe = command if command.lower().endswith(".exe") else command + ".exe"
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}") as key:
                path = os.path.expandvars(str(winreg.QueryValueEx(key, None)[0]).strip('"'))
                if Path(path).exists():
                    return path
        except OSError:
            continue
    return None


def _launch(target: str) -> bool | str:
    """Start an allow-listed app. Returns True or an error message. Never goes through a shell."""
    if target.endswith(":"):                       # Windows URI such as a Store app
        os.startfile(target)
        return True
    exe = resolve_exe(target)
    if exe is None:
        return f"{target} is not installed on this computer"
    subprocess.Popen([exe])
    return True


# ---------------------------------------------------------------------------
# Websites
# ---------------------------------------------------------------------------
def _browser_choices() -> list[str]:
    return ["default"] + sorted(cfg("desktop", "browsers", default={}) or {})


@tool("computer_use", R1, "Open a website in a browser.",
      params=(Param("url", "str", "website address or a name such as youtube", max_len=300),
              Param("browser", "str", "which browser", choices=_browser_choices, required=False)),
      change_note="A browser window will open that website. Nothing on your computer is changed.",
      summary="Open {url} in the browser")
def open_website(url: str, browser: str = "default") -> dict:
    address = clean_url(url)
    name = (browser or "default").lower()
    if name == "default":
        os.startfile(address)          # the Windows default browser
        return {"ok": True, "opened": address, "browser": "default"}
    exe_name = (cfg("desktop", "browsers", default={}) or {}).get(name)
    exe = resolve_exe(exe_name) if exe_name else None
    if exe is None:
        return {"ok": False, "error": f"{name} is not installed on this computer; try the default browser"}
    subprocess.Popen([exe, address])
    return {"ok": True, "opened": address, "browser": name}

_MAX_TEXT = 2000
_CLICKABLE = ("MenuItem", "Button", "SplitButton", "TabItem", "ListItem", "Hyperlink", "CheckBox", "RadioButton")

# Handle of the window most recently opened by open_application, per app name.
_opened: dict[str, int] = {}


def _desktop():
    from pywinauto import Desktop
    return Desktop(backend="uia")


def _allowed_window(title: str) -> bool:
    patterns = cfg("desktop", "allowed_windows", default=[]) or []
    return any(re.search(p, title, re.IGNORECASE) for p in patterns)


def _top_windows():
    out = []
    for w in _desktop().windows():
        try:
            if w.window_text():
                out.append(w)
        except Exception:
            continue
    return out


def _child_windows(parent) -> list:
    """Direct child windows (dialogs such as "Save as"). Far faster than walking the whole control tree, which
    takes many seconds when the app holds a lot of content (Notepad with many open tabs)."""
    try:
        return [c for c in parent.children() if c.element_info.control_type == "Window"]
    except Exception:
        return []


def _find_window(window: str, timeout: float = 10.0):
    """Find a window whose title contains `window`. Prefers the one Tobi opened.

    Dialogs such as "Save as" are child windows of the app, so those are searched too (children first, and the
    full control tree only as a slow last resort).
    """
    needle = window.strip().lower()
    start = time.monotonic()
    deadline = start + timeout
    while True:
        tops = _top_windows()
        matches = [w for w in tops if needle in w.window_text().lower()]
        opened = [w for w in matches if w.handle in _opened.values()]
        if opened or matches:
            return (opened or matches)[0]
        # Child dialogs of windows we opened first, then of any allowed window.
        parents = sorted((w for w in tops if _allowed_window(w.window_text())),
                         key=lambda w: w.handle not in _opened.values())
        for parent in parents:
            for child in _child_windows(parent):
                if needle in child.window_text().lower():
                    return child
                for grandchild in _child_windows(child):          # a dialog's own prompt, e.g. "Confirm Save As"
                    if needle in grandchild.window_text().lower():
                        return grandchild
        if time.monotonic() - start > 4:                           # not a direct child: walk the tree, once per loop
            for parent in parents:
                try:
                    for child in parent.descendants(control_type="Window"):
                        if needle in child.window_text().lower():
                            return child
                except Exception:
                    continue
        if time.monotonic() > deadline:
            return None
        time.sleep(0.3)


@tool("computer_use", R1, "Open an app from the allowed app list.", params=(Param("name"),))
def open_application(name: str) -> dict:
    apps = cfg("desktop", "allowed_apps", default={}) or {}
    key = str(name).lower().strip()
    if key not in apps:
        return {"ok": False, "error": f"'{name}' is not on the allowed app list", "allowed": sorted(apps)}
    before = {w.handle for w in _top_windows()}
    launched = _launch(apps[key])
    if launched is not True:
        return {"ok": False, "error": launched}
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        time.sleep(0.5)
        new = [w for w in _top_windows() if w.handle not in before]
        if new:
            win = new[0]
            _opened[key] = win.handle
            return {"ok": True, "app": key, "window": win.window_text()}
    # Some apps reuse an existing window (for example a new tab). Report what is there.
    existing = [w.window_text() for w in _top_windows() if key in w.window_text().lower()]
    if existing:
        return {"ok": True, "app": key, "window": existing[0], "note": "reused an existing window"}
    return {"ok": False, "error": f"{key} was started but no window appeared within 10 seconds"}


@tool("computer_use", R1, "Click a named button or menu item.",
      params=(Param("window"), Param("control_name", max_len=80)))
def click_control(window: str, control_name: str) -> dict:
    if not isinstance(window, str) or not _allowed_window(window):
        return {"ok": False, "error": f"Window '{window}' is not on the allowed window list"}
    if not isinstance(control_name, str) or not control_name.strip() or len(control_name) > 80:
        return {"ok": False, "error": "control_name must be a short, non-empty name"}
    win = _find_window(window)
    if win is None:
        return {"ok": False, "error": f"No open window with '{window}' in its title"}
    wanted = control_name.strip().lower()
    deadline = time.monotonic() + 6
    while True:
        found = []
        try:
            for c in win.descendants():
                if c.element_info.control_type in _CLICKABLE and c.window_text().strip().lower() == wanted:
                    found.append(c)
        except Exception:
            found = []
        if found:
            found.sort(key=lambda c: _CLICKABLE.index(c.element_info.control_type))
            try:
                win.set_focus()
            except Exception:
                pass
            # Read these first: clicking can close the window (for example Save in a dialog).
            title, kind = win.window_text(), found[0].element_info.control_type
            found[0].click_input()
            time.sleep(0.8)
            return {"ok": True, "window": title, "clicked": control_name, "control_type": kind}
        if time.monotonic() > deadline:
            return {"ok": False, "error": f"Could not find a control named '{control_name}' in '{win.window_text()}'"}
        time.sleep(0.4)


def _escape_keys(text: str) -> str:
    out = []
    for ch in text:
        if ch in "+^%~(){}":
            out.append("{" + ch + "}")
        elif ch == "\n":
            out.append("{ENTER}")
        elif ch == "\t":
            out.append("{TAB}")
        elif ch == "\r":
            continue
        else:
            out.append(ch)
    return "".join(out)


@tool("computer_use", R1, "Type text into the active control.",
      params=(Param("window"), Param("text", max_len=2000)))
def type_text(window: str, text: str) -> dict:
    if not isinstance(window, str) or not _allowed_window(window):
        return {"ok": False, "error": f"Window '{window}' is not on the allowed window list"}
    if not isinstance(text, str) or not text:
        return {"ok": False, "error": "text must be a non-empty string"}
    if len(text) > _MAX_TEXT:
        return {"ok": False, "error": f"text is longer than {_MAX_TEXT} characters"}
    win = _find_window(window)
    if win is None:
        return {"ok": False, "error": f"No open window with '{window}' in its title"}
    from pywinauto.keyboard import send_keys

    win.set_focus()
    time.sleep(0.4)
    # The text is inserted with one paste. Key-by-key typing drops characters in some apps
    # (seen in Windows 11 Notepad). The text itself is never sent as keystrokes, so it
    # cannot trigger shortcuts. The user's previous clipboard text is put back afterwards.
    method = "paste"
    previous = _get_clipboard()
    try:
        _set_clipboard(text.replace("\r\n", "\n").replace("\n", "\r\n"))
        send_keys("^v")
        time.sleep(0.6)
    except Exception:
        method = "keystrokes"
        send_keys(_escape_keys(text), with_spaces=True, with_tabs=True, with_newlines=True,
                  pause=float(cfg("desktop", "type_delay_seconds", default=0.03)))
    finally:
        if previous is not None:
            try:
                _set_clipboard(previous)
            except Exception:
                pass
    return {"ok": True, "window": win.window_text(), "characters_typed": len(text), "method": method}


def _get_clipboard() -> str | None:
    import win32clipboard as cb
    try:
        cb.OpenClipboard()
        try:
            if cb.IsClipboardFormatAvailable(cb.CF_UNICODETEXT):
                return cb.GetClipboardData(cb.CF_UNICODETEXT)
        finally:
            cb.CloseClipboard()
    except Exception:
        pass
    return None


def _set_clipboard(text: str) -> None:
    import win32clipboard as cb
    cb.OpenClipboard()
    try:
        cb.EmptyClipboard()
        cb.SetClipboardData(cb.CF_UNICODETEXT, text)
    finally:
        cb.CloseClipboard()
