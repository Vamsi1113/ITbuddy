"""Hands-on computer tasks: record the screen, take a screenshot, look at an app's buttons, press keyboard shortcuts.

Together with open_application, click_control and type_text (tools/desktop.py) these let Tobi do what it would
otherwise only explain ("open Snipping Tool, then press Win+Shift+R ..."). Every tool that changes something is a
Level 1 action: the user approves it first, and read-only-mode blocks it.

Safety rules kept here:
  - Screen recordings and screenshots are saved as files in the user's Videos / Pictures folder with a safe name,
    never overwrite an existing file, and are never sent to the model or any cloud service.
  - press_keys only works on windows from the allow-list (desktop.allowed_windows), only sends a small set of keys,
    and refuses shortcuts that lock the PC, close windows, open Run or system menus, or end tasks.
  - list_controls only reads the names of buttons and menus in allowed windows (no text the user typed).
"""
from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

from appconfig import cfg
from tools.knownfolders import known_folder
from tools.registry import R0, R1, Param, tool

_MAX_RECORD = int(cfg("automation", "max_record_seconds", default=30))
_FPS = int(cfg("automation", "record_fps", default=15))
TIMEOUTS = {"record_screen": _MAX_RECORD + 45}       # the runner's default 30 s is too short for a recording


# ------------------------------------------------------------------------------------------------ files
def safe_filename(raw: str, fallback: str, ext: str) -> str:
    """A plain file name from user words: letters, digits, spaces, dots, dashes; never a path; right extension."""
    name = re.sub(r"[^\w .\-()]", "", (raw or "").strip()).strip(" .")
    name = re.sub(r"\s+", " ", name)[:80]
    if name.lower().endswith("." + ext):
        name = name[: -(len(ext) + 1)].strip(" .")
    return f"{name or fallback}.{ext}"


def free_path(folder: Path, filename: str) -> Path:
    """folder/filename, or 'name (2).ext' when it already exists: an existing file is never overwritten."""
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    stem, suffix, n = target.stem, target.suffix, 2
    while target.exists():
        target = folder / f"{stem} ({n}){suffix}"
        n += 1
    return target


def videos_folder() -> Path:
    return known_folder("Videos")


def pictures_folder() -> Path:
    return known_folder("Pictures")


# ------------------------------------------------------------------------------------------------ recording
def _ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


@tool("computer_use", R1, "Record the whole desktop screen as an MP4 video for a few seconds and save it in the "
      "Videos folder under the given name. Records everything visible on screen (no sound).",
      params=(Param("seconds", "int", f"length of the recording, 1 to {_MAX_RECORD}"),
              Param("name", "str", "file name without a folder, for example first video by tobi", required=False,
                    max_len=80)),
      change_note="Everything visible on your screens is recorded for that time, without sound. The video is saved "
                  "in your Videos folder; nothing is uploaded or sent anywhere.",
      summary="Record the screen for {seconds} seconds and save it as '{name}'")
def record_screen(seconds: int, name: str = "") -> dict:
    seconds = int(seconds)
    if not 1 <= seconds <= _MAX_RECORD:
        return {"ok": False, "error": f"seconds must be between 1 and {_MAX_RECORD}"}
    exe = _ffmpeg()
    if exe is None:
        return {"ok": False, "error": "The screen recorder is not installed (run: pip install imageio-ffmpeg)"}
    target = free_path(videos_folder(), safe_filename(name, time.strftime("Tobi recording %Y-%m-%d %H-%M-%S"), "mp4"))
    cmd = [exe, "-y", "-loglevel", "error", "-f", "gdigrab", "-framerate", str(_FPS), "-draw_mouse", "1",
           "-t", str(seconds), "-i", "desktop", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
           "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(target)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=seconds + 30,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "The recording did not finish in time"}
    if proc.returncode != 0 or not target.exists() or target.stat().st_size == 0:
        return {"ok": False, "error": f"The recording failed: {(proc.stderr or '').strip()[-200:] or 'no file was written'}"}
    return {"ok": True, "saved_as": str(target), "file_name": target.name, "folder": str(target.parent),
            "seconds": seconds, "size_kb": round(target.stat().st_size / 1024), "recorded_with": "Tobi's own screen recorder"}


@tool("computer_use", R1, "Take a screenshot of the whole desktop and save it as a PNG in the Pictures folder.",
      params=(Param("name", "str", "file name without a folder", required=False, max_len=80),),
      change_note="A picture of everything visible on your screens is saved in your Pictures folder; "
                  "nothing is uploaded or sent anywhere.",
      summary="Take a screenshot and save it as '{name}'")
def take_screenshot(name: str = "") -> dict:
    try:
        from PIL import ImageGrab
        image = ImageGrab.grab(all_screens=True).convert("RGB")
    except Exception as e:
        return {"ok": False, "error": f"Could not capture the screen: {e}"}
    target = free_path(pictures_folder(), safe_filename(name, time.strftime("Tobi screenshot %Y-%m-%d %H-%M-%S"), "png"))
    image.save(target, "PNG")
    return {"ok": True, "saved_as": str(target), "file_name": target.name, "folder": str(target.parent),
            "size_kb": round(target.stat().st_size / 1024)}


# ------------------------------------------------------------------------------------------------ waiting
@tool("computer_use", R0, "Wait a few seconds (for example while a window opens or something finishes).",
      params=(Param("seconds", "int", "1 to 15"),))
def wait_seconds(seconds: int) -> dict:
    seconds = max(1, min(int(seconds), 15))
    time.sleep(seconds)
    return {"ok": True, "waited_seconds": seconds}


# ------------------------------------------------------------------------------------------------ looking at a window
_LIST_TYPES = ("Button", "SplitButton", "MenuItem", "TabItem", "CheckBox", "RadioButton", "Hyperlink", "ListItem", "ComboBox")


@tool("computer_use", R0, "List the buttons, menu items and tabs of an open app window, so you use their real names "
      "with click_control. Only windows on the allowed list.",
      params=(Param("window", "str", "part of the window title, for example Snipping Tool", max_len=80),))
def list_controls(window: str) -> dict:
    from tools import desktop
    if not desktop._allowed_window(window):
        return {"ok": False, "error": f"Window '{window}' is not on the allowed window list",
                "allowed_windows": cfg("desktop", "allowed_windows", default=[])}
    win = desktop._find_window(window, timeout=6)
    if win is None:
        return {"ok": False, "error": f"No open window with '{window}' in its title"}
    names, seen = [], set()
    try:
        for c in win.descendants():
            kind = c.element_info.control_type
            label = (c.window_text() or "").strip()
            if kind in _LIST_TYPES and label and len(label) <= 60 and (kind, label) not in seen:
                seen.add((kind, label))
                names.append(f"{kind}: {label}")
            if len(names) >= 60:
                break
    except Exception as e:
        return {"ok": False, "error": f"Could not read the window: {e}"}
    return {"ok": True, "window": win.window_text(), "controls": names,
            "note": "use these names exactly with click_control" if names else "no named buttons were found"}


# ------------------------------------------------------------------------------------------------ keyboard shortcuts
_MODS = {"ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B, "windows": 0x5B}
_KEYS = {"enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B, "tab": 0x09, "space": 0x20, "backspace": 0x08,
         "delete": 0x2E, "del": 0x2E, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, "home": 0x24,
         "end": 0x23, "pageup": 0x21, "pagedown": 0x22, "printscreen": 0x2C, "prtsc": 0x2C}
_KEYS.update({f"f{i}": 0x6F + i for i in range(1, 13)})
# Shortcuts that lock the PC, close or switch windows, open Run or system menus, or end tasks.
_BLOCKED = {"win+l", "win+r", "win+x", "win+d", "win+m", "win+tab", "win+e", "win+i", "win+s", "win+p", "win+k",
            "alt+f4", "alt+tab", "alt+esc", "ctrl+alt+delete", "ctrl+alt+del", "ctrl+shift+esc", "ctrl+esc",
            "ctrl+w", "ctrl+shift+delete", "win+ctrl+d", "win+ctrl+f4"}


def parse_keys(spec: str) -> tuple[list[int], str]:
    """'win+shift+r' -> ([0x5B, 0x10], 'r' code ...). Returns (virtual-key codes in press order, normalised text).
    Raises ValueError with a message for the model when the shortcut is not allowed."""
    parts = [p.strip().lower() for p in re.split(r"\s*\+\s*", (spec or "").strip()) if p.strip()]
    if not 1 <= len(parts) <= 4:
        raise ValueError("keys must look like ctrl+s or win+shift+r (1 to 4 keys joined with +)")
    codes = []
    for p in parts[:-1]:
        if p not in _MODS:
            raise ValueError(f"'{p}' is not a modifier key (use ctrl, alt, shift or win)")
        codes.append(_MODS[p])
    last = parts[-1]
    if last in _KEYS:
        codes.append(_KEYS[last])
    elif re.fullmatch(r"[a-z0-9]", last):
        codes.append(ord(last.upper()))
    elif last in _MODS and len(parts) == 1:
        raise ValueError("a modifier key alone does nothing")
    else:
        raise ValueError(f"'{last}' is not a supported key (letters, digits, F1-F12, enter, esc, tab, space, arrows)")
    normal = "+".join("ctrl" if p == "control" else "win" if p == "windows" else p for p in parts)
    if normal in _BLOCKED:
        raise ValueError(f"'{normal}' is blocked for safety (it can lock the PC, close windows or open system menus)")
    return codes, normal


def _send(codes: list[int]) -> None:
    import win32api
    import win32con
    for c in codes:
        win32api.keybd_event(c, 0, 0, 0)
        time.sleep(0.03)
    for c in reversed(codes):
        win32api.keybd_event(c, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.03)


@tool("computer_use", R1, "Press a keyboard shortcut or key in an open app window (for example ctrl+s, enter, esc, "
      "win+shift+r). The window comes to the front first. Only allowed windows.",
      params=(Param("window", "str", "part of the window title, for example Snipping Tool", max_len=80),
              Param("keys", "str", "keys joined with +, for example win+shift+r", max_len=40)),
      change_note="The shortcut is sent to that window as if you had pressed it.",
      summary="Press {keys} in the {window} window")
def press_keys(window: str, keys: str) -> dict:
    from tools import desktop
    try:
        codes, normal = parse_keys(keys)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    if not desktop._allowed_window(window):
        return {"ok": False, "error": f"Window '{window}' is not on the allowed window list"}
    win = desktop._find_window(window, timeout=8)
    if win is None:
        return {"ok": False, "error": f"No open window with '{window}' in its title"}
    try:
        win.set_focus()
    except Exception:
        pass
    time.sleep(0.4)
    _send(codes)
    time.sleep(0.6)
    return {"ok": True, "window": win.window_text(), "pressed": normal}
