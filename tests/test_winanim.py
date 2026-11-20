"""Window motion for the desktop app: eased, clock-driven, and done by revealing the window, not resizing it."""
import ctypes
import ctypes.wintypes as wt

import pytest

from desktop import winanim


def test_easing_starts_and_stops_gently():
    for ease in (winanim.ease_in_out, winanim.ease_out):
        assert ease(0) == 0 and abs(ease(1) - 1) < 1e-9
        values = [ease(i / 50) for i in range(51)]
        assert values == sorted(values)                        # never goes backwards
    assert winanim.ease_in_out(0.1) < 0.1 and winanim.ease_in_out(0.9) > 0.9    # slow at both ends
    assert abs(winanim.ease_in_out(0.5) - 0.5) < 1e-9


@pytest.fixture
def window():
    user32 = ctypes.windll.user32
    user32.CreateWindowExW.restype = ctypes.c_void_p
    user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                       ctypes.c_void_p]
    hwnd = user32.CreateWindowExW(0, "STATIC", "t", 0x80000000, 50, 60, 300, 200, None, None, None, None)  # WS_POPUP
    if not hwnd:
        pytest.skip("cannot create a test window here")
    yield hwnd
    user32.DestroyWindow(hwnd)


def _band(hwnd):
    box = wt.RECT()
    ctypes.windll.user32.GetWindowRgnBox(hwnd, ctypes.byref(box))
    return box.left, box.right


def test_visible_band_cuts_away_the_hidden_side(window):
    winanim.set_visible_band(window, 120, 300, 8)
    left, right = _band(window)
    assert left == 120 and right >= 300
    assert winanim.rect(window)[2:] == (300, 200)              # the window itself was not resized


def test_reveal_slides_the_edge_and_never_resizes(window):
    seen = []
    original = winanim.set_visible_band
    winanim.set_visible_band = lambda *a, **k: (seen.append(a[1]), original(*a, **k))[1]
    try:
        frames = winanim.reveal(window, 120, 0, from_left=True, radius_px=8, duration=0.12)
    finally:
        winanim.set_visible_band = original
    assert frames >= 5 and seen[0] > seen[-1] == 0              # the left edge moved from 120 to 0
    assert seen == sorted(seen, reverse=True)                   # smoothly, never backwards
    assert winanim.rect(window)[2:] == (300, 200)
    assert _band(window)[0] == 0


def test_reveal_from_the_right_side(window):
    winanim.reveal(window, 0, 100, from_left=False, radius_px=8, duration=0.08)
    left, right = _band(window)
    assert left == 0 and 195 <= right <= 205                    # 300 wide, 100 cut away on the right


def test_animate_moves_to_the_target_without_overshoot(window):
    winanim.animate(window, (10, 20, 300, 200), duration=0.1)
    assert winanim.rect(window) == (10, 20, 300, 200)
