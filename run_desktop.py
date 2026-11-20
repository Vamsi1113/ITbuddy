"""Tobi as a desktop pet: a small avatar at the bottom-right of the screen; click it to open the chat window
(a quarter of the screen wide, up to three quarters tall, just above the avatar). Closing the chat sends it back to
the avatar; right-click the avatar to quit.

    python run_desktop.py                 # start the avatar (click it to chat)
    python run_desktop.py --open          # start with the chat already open
    python run_desktop.py --demo "text"   # open the chat and send a message (for demos and checks)
    python run_desktop.py --shot out.png  # save a picture of the chat + avatar after a few seconds, then quit
    python run_desktop.py --probe         # print what the pages rendered, then quit

No server is needed: the windows are HTML pages (desktop/web) in native Edge WebView2 windows through pywebview, and
the agent is the same Python code as the web console (app.py), reached through desktop/bridge.py.
Only one Tobi runs at a time: starting it again opens the chat of the running one (or replaces a frozen one).
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import webview  # noqa: E402

from desktop.bridge import LIVE_PANEL_WIDTH, Api  # noqa: E402

WEB = ROOT / "desktop" / "web" / "index.html"
PET_WEB = ROOT / "desktop" / "web" / "pet.html"
MARGIN = 14
PET = 112                                           # size of the avatar window
_SUFFIX = os.environ.get("ITBUDDY_INSTANCE", "")       # lets a test run beside the real app
CHAT_TITLE, PET_TITLE = "Tobi" + _SUFFIX, "Tobi Pet" + _SUFFIX
MUTEX_NAME, EVENT_NAME = "Local\\ITBuddyDesktop" + _SUFFIX, "Local\\ITBuddyShow" + _SUFFIX


def work_area() -> tuple[int, int, int, int]:
    """Usable desktop area (left, top, right, bottom): the screen without the taskbar."""
    r = wt.RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)      # SPI_GETWORKAREA
    return r.left, r.top, r.right, r.bottom


def chat_width() -> int:
    return round(webview.screens[0].width / 4)


def geometry() -> tuple[int, int, int, int]:
    """Chat window (x, y, width, height). The visible chat is 1/4 of the screen wide and up to 3/4 tall, just above the
    avatar. The window itself is wider by the live panel and stays that size: the live view slides out by revealing
    part of the window, never by resizing it (resizing a web page 60 times a second judders and shakes)."""
    screen = webview.screens[0]
    left, top, right, bottom = work_area()
    width = chat_width()
    height = min(round(screen.height * 3 / 4), bottom - top - 2 * MARGIN - PET - 8)
    chat_x = right - width - MARGIN
    x = chat_x - LIVE_PANEL_WIDTH if chat_x - LIVE_PANEL_WIDTH >= left else chat_x     # the panel opens on the roomy side
    return x, bottom - PET - 8 - MARGIN - height, width + LIVE_PANEL_WIDTH, height


def pet_geometry() -> tuple[int, int, int, int]:
    _, _, right, bottom = work_area()
    return right - PET - MARGIN, bottom - PET - MARGIN, PET, PET


# ---------------------------------------------------------------------------------------------- Windows plumbing
def _hwnd(title: str) -> int:
    return ctypes.windll.user32.FindWindowW(None, title)


PID_FILE = ROOT / "data" / f"desktop{_SUFFIX}.pid"
LOG_FILE = ROOT / "data" / "desktop.log"
_ready = threading.Event()                          # set when the avatar and chat pages are loaded


def log(message: str) -> None:
    """Startup problems go to data/desktop.log (the app runs without a console, so nothing else would show them)."""
    try:
        LOG_FILE.parent.mkdir(exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + message + "\n")
        if LOG_FILE.stat().st_size > 200_000:
            LOG_FILE.write_text(LOG_FILE.read_text(encoding="utf-8")[-50_000:], encoding="utf-8")
    except OSError:
        pass


def _kill_holder() -> None:
    """End the Tobi that holds the lock but shows nothing (frozen, half-closed, or left over)."""
    try:
        pid = int(PID_FILE.read_text().split()[0])
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        log(f"ended the stale Tobi process {pid}")
    except (OSError, ValueError, IndexError):
        pass
    time.sleep(1.2)


def single_instance() -> bool:
    """True when this process should run. Only one Tobi runs at a time: if a healthy one exists (or is still
    starting) this asks it to open its chat and returns False; if the other one is frozen, has no avatar, or never
    finished starting, it is ended and this one takes over."""
    k32, user32 = ctypes.windll.kernel32, ctypes.windll.user32
    for _ in range(3):
        handle = k32.CreateMutexW(None, False, MUTEX_NAME)
        if k32.GetLastError() != 183:                                 # not ERROR_ALREADY_EXISTS: we are first
            PID_FILE.parent.mkdir(exist_ok=True)
            PID_FILE.write_text(f"{os.getpid()} {int(time.time())}")
            return True
        k32.CloseHandle(handle)
        started = 0
        try:
            started = int(PID_FILE.read_text().split()[1])
        except (OSError, ValueError, IndexError):
            pass
        deadline = time.time() + (30 if time.time() - started < 30 else 0)      # the other one may still be starting
        hwnd = _hwnd(PET_TITLE)
        while not hwnd and time.time() < deadline:
            time.sleep(0.5)
            hwnd = _hwnd(PET_TITLE)
        if hwnd and not user32.IsHungAppWindow(hwnd) and user32.IsWindowVisible(hwnd):
            ev = k32.OpenEventW(0x0002, False, EVENT_NAME)            # EVENT_MODIFY_STATE
            if ev:
                k32.SetEvent(ev)
                k32.CloseHandle(ev)
                return False
        _kill_holder()                                                # no avatar, frozen, or no way to reach it
    return True


def listen_for_second_launch(api: Api) -> None:
    """Opening Tobi again (Start menu, desktop icon) just opens the chat of the running one."""
    k32 = ctypes.windll.kernel32
    ev = k32.CreateEventW(None, False, False, EVENT_NAME)

    def loop() -> None:
        while True:
            if k32.WaitForSingleObject(ev, 0xFFFFFFFF) == 0:
                _ready.wait(30)
                api.show_chat()
    threading.Thread(target=loop, daemon=True, name="itb-single-instance").start()


def watchdog(window, argv: list[str]) -> None:
    """If the window stops answering (it can freeze after the laptop wakes from sleep), restart Tobi by itself."""
    def probe() -> bool:
        done = threading.Event()

        def ask() -> None:
            try:
                window.evaluate_js("1")
            except Exception:
                return
            done.set()
        threading.Thread(target=ask, daemon=True).start()
        return done.wait(20)

    def loop() -> None:
        misses, last = 0, time.time()
        while True:
            time.sleep(10)
            now = time.time()
            woke = now - last > 40                                    # the computer slept: give the page time to recover
            last = now
            if woke:
                misses = 0
                time.sleep(15)
                last = time.time()
                continue
            misses = 0 if probe() else misses + 1
            if misses >= 3:
                subprocess.Popen([sys.executable, *argv], cwd=str(ROOT), close_fds=True,
                                 creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
                os._exit(0)
    threading.Thread(target=loop, daemon=True, name="itb-watchdog").start()


def main() -> int:
    parser = argparse.ArgumentParser(description="Tobi desktop pet and chat window")
    parser.add_argument("--open", action="store_true", help="open the chat window right away")
    parser.add_argument("--demo", help="send this message once the chat is open (implies --open)")
    parser.add_argument("--shot", help="save a picture of the chat and avatar to this file after a few seconds, then quit")
    parser.add_argument("--wait", type=float, default=6.0, help="seconds to wait before --shot or --probe")
    parser.add_argument("--probe", action="store_true", help="print what the pages rendered, then quit")
    args = parser.parse_args()
    testing = bool(args.demo or args.shot or args.probe)
    show_now = args.open or testing

    if not testing and not single_instance():
        return 0

    try:                                           # warm the knowledge index in the background (never blocks the window)
        from rag.startup import ensure_rag_index
        ensure_rag_index(background=True)
    except Exception:
        pass

    x, y, w, h = geometry()
    api = Api()
    window = webview.create_window(
        CHAT_TITLE, url=str(WEB), js_api=api, width=w, height=h, x=x, y=y, frameless=True, easy_drag=False,
        resizable=False, background_color="#E8F3EE", text_select=True, shadow=False, hidden=True)
    px, py, pw, ph = pet_geometry()
    pet = webview.create_window(
        PET_TITLE, url=str(PET_WEB), js_api=api, width=pw, height=ph, x=px, y=py, frameless=True, easy_drag=False,
        resizable=False, min_size=(PET, PET), on_top=True, transparent=True, background_color="#000000", shadow=False)
    left, _, _, _ = work_area()
    api.attach(window, w, fix_east=(x + w == work_area()[2] - MARGIN))      # panel on the left: the window's right edge is the chat's
    api.attach_pet(pet)
    def on_closing():                              # Alt+F4 on the chat sends it back to the avatar; only Quit ends the app
        if api.quitting or testing:
            return True
        api.hide_chat()
        return False
    window.events.closing += on_closing
    if not testing:
        listen_for_second_launch(api)

    def after_start() -> None:
        window.events.loaded.wait(30)              # the pages have loaded and the bridge is up
        pet.events.loaded.wait(30)
        window.resize(w, h)                        # creation scaling makes windows a little smaller than asked: set exactly
        window.move(x, y)
        pet.resize(pw, ph)
        pet.move(px, py)
        api.apply_region()                          # chat only: the live panel part of the window starts cut away
        if not show_now:
            for _ in range(3):                     # the chat must start hidden: only the avatar shows until it is clicked
                window.hide()
                time.sleep(0.4)
        _ready.set()
        if not testing:
            watchdog(window, sys.argv)
        time.sleep(0.5)
        if show_now:
            api.show_chat()
            time.sleep(0.5)
        if args.demo:
            api.send(args.demo)
        if args.probe:
            time.sleep(args.wait)
            print(window.evaluate_js("""JSON.stringify({
                title: document.title, inner: [innerWidth, innerHeight], dpr: devicePixelRatio,
                rows: document.querySelectorAll('.row').length, chips: document.querySelectorAll('#suggest .chip').length,
                bridge: !!(window.pywebview && window.pywebview.api), ib: typeof window.ib,
                logoLoaded: (() => { const i = document.querySelector('#logo'); return !!(i && i.complete && i.naturalWidth > 0); })(),
                status: document.querySelector('#status').innerText, headerH: document.querySelector('.head').offsetHeight})"""))
            print("pet bridge:", pet.evaluate_js("!!(window.pywebview && window.pywebview.api)"), "| pet canvas:",
                  pet.evaluate_js("!!document.getElementById('c') && typeof THREE !== 'undefined'"))
            print("chat:", window.x, window.y, window.width, window.height, "| pet:", pet.x, pet.y, pet.width, pet.height,
                  "| screen:", webview.screens[0].width, webview.screens[0].height)
            window.destroy()
            pet.destroy()
        if args.shot:
            time.sleep(args.wait)
            from PIL import ImageGrab
            for _ in range(4):                                    # the display can be briefly unavailable (lock, sleep)
                try:
                    full = ImageGrab.grab(all_screens=True)
                    break
                except OSError:
                    time.sleep(2)
            else:
                print("could not capture the screen")
                window.destroy()
                pet.destroy()
                return
            k = full.width / webview.screens[0].width             # physical pixels per logical pixel (display scaling)
            box = (round(window.x * k), round(window.y * k), round((window.x + window.width) * k),
                   round((window.y + window.height + 8 + PET) * k))       # the chat and the avatar below it
            full.crop(box).save(args.shot)                        # only our windows, never the rest of the screen
            window.destroy()
            pet.destroy()

    webview.start(after_start)                     # private mode: no profile folder to lock or clean up
    return 0


def run() -> None:
    try:
        code = main()
    except BaseException:
        import traceback
        log("crashed:\n" + traceback.format_exc())
        code = 1
    os._exit(code)                                 # leave nothing behind: a lingering thread must never keep the lock


if __name__ == "__main__":
    run()
