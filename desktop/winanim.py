"""Smooth window motion for the desktop app.

Why this exists: asking the toolkit to resize the window in a few coarse steps, while the rounded-corner clip was
rebuilt on every step, made the live-view slide judder and the chat content shake. Here the window is moved with ONE
atomic SetWindowPos per frame (position and size together, so the fixed edge never moves), the frames are driven by
the clock (not by a step count, so a slow frame never makes the motion lag), and the corner clip is updated cheaply
from the same loop.

All values are physical pixels (what Windows reports for a DPI-aware window).
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import time

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
try:
    winmm = ctypes.windll.winmm
except OSError:                      # pragma: no cover
    winmm = None

SWP_NOZORDER, SWP_NOACTIVATE, SWP_NOOWNERZORDER = 0x0004, 0x0010, 0x0200
FLAGS = SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOOWNERZORDER
GWL_EXSTYLE, WS_EX_LAYERED, LWA_ALPHA = -20, 0x00080000, 0x2


def rect(hwnd: int) -> tuple[int, int, int, int]:
    """(left, top, width, height) of the window."""
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def set_rect(hwnd: int, left: int, top: int, width: int, height: int) -> None:
    user32.SetWindowPos(hwnd, 0, int(left), int(top), int(width), int(height), FLAGS)


def scale(hwnd: int) -> float:
    try:
        return user32.GetDpiForWindow(hwnd) / 96
    except Exception:
        return 1.0


def ease_in_out(k: float) -> float:
    """Smooth start and stop (cubic)."""
    return 4 * k * k * k if k < 0.5 else 1 - pow(-2 * k + 2, 3) / 2


def ease_out(k: float) -> float:
    return 1 - pow(1 - k, 3)


def round_clip(hwnd: int, radius_px: int) -> None:
    """Clip the window to a rounded rectangle of its current size (top-level window only: cheap enough per frame)."""
    left, top, width, height = rect(hwnd)
    d = max(2, int(radius_px * 2))
    user32.SetWindowRgn(hwnd, gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, d, d), True)


def set_visible_band(hwnd: int, left: int, right: int, radius_px: int) -> None:
    """Show only the band [left, right) of the window (window coordinates), with rounded corners. Everything outside
    the band is cut away and mouse clicks pass through it. Cheap: no resize, no web page layout."""
    _, _, width, height = rect(hwnd)
    d = max(2, int(radius_px * 2))
    left, right = max(0, int(left)), min(width, int(right))
    region = gdi32.CreateRoundRectRgn(left, 0, right + 1, height + 1, d, d)
    user32.SetWindowRgn(hwnd, region, False)            # False: the picture underneath is already drawn, just reveal it


def reveal(hwnd: int, hidden_from: float, hidden_to: float, from_left: bool, radius_px: int,
           duration: float = 0.55, ease=None) -> int:
    """Slide the edge of the visible band: `hidden_*` = how many pixels of the window are cut away on the leading
    side (the left side when from_left, else the right). The window itself never moves or resizes, so the web page
    is not laid out again and nothing shakes. Returns the number of frames drawn."""
    ease = ease or ease_in_out
    _, _, width, _ = rect(hwnd)
    if winmm:
        winmm.timeBeginPeriod(1)
    frames = 0
    try:
        t0 = time.perf_counter()
        while True:
            k = min(1.0, (time.perf_counter() - t0) / max(duration, 0.001))
            hidden = hidden_from + (hidden_to - hidden_from) * ease(k)
            if from_left:
                set_visible_band(hwnd, hidden, width, radius_px)
            else:
                set_visible_band(hwnd, 0, width - hidden, radius_px)
            frames += 1
            if k >= 1.0:
                break
            time.sleep(0.004)
    finally:
        if winmm:
            winmm.timeEndPeriod(1)
    return frames


def set_alpha(hwnd: int, alpha: int) -> None:
    """Window opacity 0-255 (layered window)."""
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if not style & WS_EX_LAYERED:
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
    user32.SetLayeredWindowAttributes(hwnd, 0, max(0, min(255, int(alpha))), LWA_ALPHA)


def clear_alpha(hwnd: int) -> None:
    """Back to a normal opaque window (no layered style), so nothing is composited twice while idle."""
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if style & WS_EX_LAYERED:
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_LAYERED)


def animate(hwnd: int, to: tuple[int, int, int, int], duration: float = 0.5, ease=ease_in_out,
            start: tuple[int, int, int, int] | None = None, alpha: tuple[int, int] | None = None,
            corner_radius: int = 0, on_frame=None) -> int:
    """Move/resize `hwnd` from `start` (default: where it is) to `to` = (left, top, width, height) over `duration`
    seconds. `alpha` = (from, to) fades the window at the same time. Returns the number of frames drawn."""
    frm = start or rect(hwnd)
    if winmm:
        winmm.timeBeginPeriod(1)                       # 1 ms timer resolution so frames are evenly spaced
    frames = 0
    try:
        t0 = time.perf_counter()
        while True:
            k = min(1.0, (time.perf_counter() - t0) / max(duration, 0.001))
            e = ease(k)
            cur = [round(a + (b - a) * e) for a, b in zip(frm, to)]
            set_rect(hwnd, *cur)
            if corner_radius:
                round_clip(hwnd, corner_radius)
            if alpha:
                set_alpha(hwnd, alpha[0] + (alpha[1] - alpha[0]) * e)
            if on_frame:
                on_frame(k, cur)
            frames += 1
            if k >= 1.0:
                break
            time.sleep(0.004)
    finally:
        if winmm:
            winmm.timeEndPeriod(1)
    return frames
