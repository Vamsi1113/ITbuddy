"""The bridge between the desktop chat window (HTML in a native pywebview window) and Tobi's agent.

JavaScript calls the methods of `Api` (window.pywebview.api.<method>). Long-running work (a request to the
agent) runs in a background thread and reports back by calling `ib.onEvent(...)` in the page, so the window
never freezes. Everything the agent does still goes through the same graph, policy gate and audit log as the
web console: this file only moves messages.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from appconfig import ROOT

LIVE_PANEL_WIDTH = 340            # extra width the window gains when the live view is pulled out
ASSETS = ROOT / "assets"


def data_uri(path: str | Path) -> str:
    """A file as a data: URI, so the page can show it without a file server (logo, screenshots)."""
    p = Path(path)
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


class Api:
    """Exposed to the page. Public methods are callable from JavaScript; EVERYTHING ELSE MUST START WITH AN UNDERSCORE:
    pywebview walks every public attribute of this object and recurses into it (a public window reference made it
    recurse into the native window and hang)."""

    def __init__(self) -> None:
        self._window = None
        self._graph = None
        self._busy = False
        self._lock = threading.Lock()
        self._autopilot = False
        self._live_open = False
        self._base_width = 0
        self._pet = None
        self.animating = False              # True while the window slides (the corner clip is then driven by the animation)
        self._anim_lock = threading.Lock()
        from agent.memory import Conversation
        self._memory = Conversation()          # earlier messages of this chat ("New chat" clears it)
        self.quitting = False               # True once Quit was chosen (the chat may then really close)
        self._on_shown = None
        self._visible = False
        self._unread = False
        self._fix_east = True              # the widget sits at the right edge, so the live panel grows to the left

    # ------------------------------------------------------------------ plumbing
    def attach(self, window, base_width: int, fix_east: bool = True) -> None:
        self._window, self._base_width, self._fix_east = window, base_width, fix_east

    def attach_pet(self, pet, on_shown=None) -> None:
        self._pet, self._on_shown = pet, on_shown

    def _pet_state(self) -> None:
        """Tell the pet (the small avatar) whether the chat is open and whether there is something unread."""
        if self._pet is not None:
            try:
                self._pet.evaluate_js("window.setPet && setPet(%s, %s, %s)" % (json.dumps(self._visible), json.dumps(self._unread), json.dumps(self._busy)))
            except Exception:
                pass

    def _push(self, **event) -> None:
        """Send one event to the page. Safe to call from any thread."""
        if self._window is None:
            return
        try:
            self._window.evaluate_js("window.ib && ib.onEvent(%s)" % json.dumps(event, ensure_ascii=True))
        except Exception:
            pass                          # the window may be closing

    def _get_graph(self):
        if self._graph is None:
            from agent.graph import build_graph
            self._graph = build_graph()
        return self._graph

    # ------------------------------------------------------------------ startup info
    def info(self) -> dict:
        from agent.llm import describe_model
        from connectors.base import CONNECTORS
        from safety import policy
        return {
            "name": "Tobi",
            "model": describe_model(),
            "logo": data_uri(ASSETS / "logo.png") if (ASSETS / "logo.png").exists() else "",
            "autopilot": self._autopilot, "live": True, "readOnly": policy.is_read_only(),
            "side": "left" if self._fix_east else "right",
            "connectorsReady": sum(1 for c in CONNECTORS.values() if c.status() == "ready"),
            "connectorsTotal": len(CONNECTORS),
        }

    # ------------------------------------------------------------------ chat
    def send(self, text: str) -> dict:
        """Start a request. Returns at once; the answer arrives as events."""
        text = (text or "").strip()
        if not text:
            return {"ok": False, "error": "empty"}
        with self._lock:
            if self._busy:
                return {"ok": False, "error": "busy"}
            self._busy = True
        from agent import live, runner
        live.clear()
        self._pet_state()
        mode = "autopilot" if self._autopilot else None
        history = self._memory.turns()
        self._memory.add("user", text)
        self._spawn(lambda cb: runner.start(self._get_graph(), text, cb, mode=mode, history=history))
        return {"ok": True}

    def new_chat(self) -> bool:
        """Forget the earlier messages (the "New chat" option)."""
        self._memory.clear()
        return True

    def resume(self, task_id: str, approved: bool) -> dict:
        self._memory.add("user", "Approved." if approved else "Rejected, do not make that change.")
        with self._lock:
            if self._busy:
                return {"ok": False, "error": "busy"}
            self._busy = True
        self._pet_state()
        from agent import runner
        self._spawn(lambda cb: runner.resume(self._get_graph(), task_id, bool(approved), cb))
        return {"ok": True}

    def _spawn(self, work) -> None:
        def run() -> None:
            try:
                def on_status(event: dict) -> None:
                    image = event.get("image")
                    self._push(type="status", agent=event.get("agent", "Tobi"), tool=event.get("tool"),
                               text=event.get("text", ""), t=time.strftime("%H:%M:%S"),
                               image=data_uri(image) if image and os.path.exists(image) else None)

                result = work(on_status)
                if result["status"] == "needs_approval":
                    self._push(type="approval", task_id=result["task_id"], approval=result["approval"])
                    a = result["approval"] or {}
                    self._memory.add("assistant", f"{a.get('diagnosis', '')}\nI proposed: {a.get('summary', '')} "
                                                  "(waiting for the user's approval)")
                    self._note_unread()
                else:
                    state = result["state"]
                    self._memory.add("assistant", state.get("report", ""))
                    self._push(type="done", task_id=result["task_id"], outcome=state.get("outcome"),
                               report=state.get("report", ""), comparison=state.get("comparison") or [],
                               basis=state.get("basis") or [])
                    self._note_unread()
            except Exception as e:           # never leave the page waiting
                self._push(type="error", message=f"{type(e).__name__}: {str(e)[:300]}")
            finally:
                with self._lock:
                    self._busy = False
                self._pet_state()

        threading.Thread(target=run, daemon=True, name="itb-request").start()

    # ------------------------------------------------------------------ options
    def set_options(self, autopilot: bool | None = None, live_view: bool | None = None,
                    read_only: bool | None = None) -> dict:
        from agent import live
        from safety import policy
        if autopilot is not None:
            self._autopilot = bool(autopilot)
        if live_view is not None:
            live.set_enabled(bool(live_view))
        if read_only is not None:
            policy.set_read_only(bool(read_only))
        return {"autopilot": self._autopilot, "liveView": live.is_enabled(), "readOnly": policy.is_read_only()}

    # ------------------------------------------------------------------ catalogue for the three sheets
    def catalog(self) -> dict:
        from agent.catalog import SUBAGENTS, agent_status, tool_counts
        from connectors.base import CONNECTORS
        from tools.registry import R0, TOOLS
        agents = [{"id": a.id, "name": a.name, "icon": a.icon, "group": a.group, "purpose": a.purpose,
                   "status": agent_status(a), "examples": list(a.examples[:2]), "tools": tool_counts(a)["total"]}
                  for a in SUBAGENTS]
        connectors = [{"id": c.id, "name": c.name, "kind": c.kind, "description": c.description, "status": c.status(),
                       "missing": c.missing(), "setup": c.setup, "tools": len(c.tool_names())}
                      for c in CONNECTORS.values()]
        owner = {d: c for c in CONNECTORS.values() for d in c.domains}
        tools = [{"name": t.name, "risk": t.risk, "description": t.description,
                  "connector": owner[t.domain].name if t.domain in owner else t.domain,
                  "status": owner[t.domain].status() if t.domain in owner else "ready"}
                 for t in sorted(TOOLS.values(), key=lambda t: (t.risk, t.name))]
        return {"agents": agents, "connectors": connectors, "tools": tools}

    # ------------------------------------------------------------------ window
    def set_live(self, open_: bool) -> dict:
        """Pull the live view out (the window grows sideways) or push it back."""
        from desktop import winanim
        side = "left" if self._fix_east else "right"
        if self._window is None or bool(open_) == self._live_open:
            return {"open": self._live_open, "side": side}
        with self._anim_lock:
            hwnd = self._window.native.Handle.ToInt64()
            k = winanim.scale(hwnd)
            hidden = round(LIVE_PANEL_WIDTH * k)
            self.animating = True
            try:
                # The window is always wide enough for the chat AND the live panel; only the visible band moves.
                # Nothing is resized, so the page is not laid out again: no juddering and the chat cannot shake.
                winanim.reveal(hwnd, 0 if not open_ else hidden, hidden if not open_ else 0, self._fix_east,
                               radius_px=round(8 * k), duration=0.55)
            finally:
                self.animating = False
        self._live_open = bool(open_)
        return {"open": self._live_open, "side": "left" if self._fix_east else "right"}

    def apply_region(self) -> None:
        """Clip the chat window to what should be visible now: the chat, plus the live panel when it is pulled out."""
        if self._window is None:
            return
        from desktop import winanim
        try:
            hwnd = self._window.native.Handle.ToInt64()
            k = winanim.scale(hwnd)
            hidden = 0 if self._live_open else round(LIVE_PANEL_WIDTH * k)
            _, _, width, _ = winanim.rect(hwnd)
            if self._fix_east:
                winanim.set_visible_band(hwnd, hidden, width, round(8 * k))
            else:
                winanim.set_visible_band(hwnd, 0, width - hidden, round(8 * k))
        except Exception:
            pass

    def _note_unread(self) -> None:
        if not self._visible:
            self._unread = True
            self._pet_state()

    def show_chat(self) -> bool:
        if self._pet is not None:
            try:
                self._pet.show()               # the avatar is always there when the chat is
            except Exception:
                pass
        if self._window is not None:
            self._animate_chat(show=True)
            self._visible, self._unread = True, False
            self._pet_state()
            try:
                self._window.evaluate_js("document.querySelector('#input') && document.querySelector('#input').focus()")
            except Exception:
                pass
        return True

    def _animate_chat(self, show: bool) -> None:
        """The chat fades and glides in from the avatar (and back out): hidden -> shown or shown -> hidden."""
        from desktop import winanim
        with self._anim_lock:
            self.animating = True
            hwnd = self._window.native.Handle.ToInt64()
            try:
                k = winanim.scale(hwnd)
                lift = round(26 * k)                                   # how far it glides
                radius = round(8 * k)
                left, top, width, height = winanim.rect(hwnd)
                self.apply_region()
                if show:
                    winanim.set_alpha(hwnd, 0)
                    winanim.set_rect(hwnd, left, top + lift, width, height)
                    self._window.show()
                    self._window.restore()
                    winanim.animate(hwnd, (left, top, width, height), duration=0.24, ease=winanim.ease_out,
                                    start=(left, top + lift, width, height), alpha=(0, 255))
                    winanim.clear_alpha(hwnd)
                else:
                    winanim.animate(hwnd, (left, top + lift // 2, width, height), duration=0.16, alpha=(255, 0))
                    self._window.hide()
                    winanim.set_rect(hwnd, left, top, width, height)   # back to its place for the next time
                    winanim.clear_alpha(hwnd)
            finally:
                self.animating = False

    def hide_chat(self) -> bool:
        if self._window is not None:
            if self._visible:
                self._animate_chat(show=False)
            else:
                self._window.hide()
            self._visible = False
            self._pet_state()
        return False

    def toggle_chat(self) -> bool:
        return self.hide_chat() if self._visible else self.show_chat()

    def quit(self) -> None:
        self.quitting = True
        for w in (self._window, self._pet):
            try:
                w and w.destroy()
            except Exception:
                pass

    def set_shape(self, runs: list, grid: int) -> bool:
        """The avatar's silhouette from the page: rows of covered cells [y, x0, x1, ...] on a grid x grid picture.
        The avatar window is clipped to it, so only the character shows (no frame, no background)."""
        if self._pet is None or not runs:
            return False
        import ctypes
        import ctypes.wintypes as wt
        user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
        hwnd = self._pet.native.Handle.ToInt64()
        r = wt.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        kx, ky = (r.right - r.left) / grid, (r.bottom - r.top) / grid
        region = gdi32.CreateRectRgn(0, 0, 0, 0)
        for i in range(0, len(runs) - 2, 3):
            y, x0, x1 = runs[i], runs[i + 1], runs[i + 2]
            piece = gdi32.CreateRectRgn(int(x0 * kx), int(y * ky), int(x1 * kx + 1), int((y + 1) * ky + 1))
            gdi32.CombineRgn(region, region, piece, 2)                      # RGN_OR
            gdi32.DeleteObject(piece)
        user32.SetWindowRgn(hwnd, region, True)                             # Windows owns the region from here
        return True

    def pin(self, on: bool) -> bool:
        if self._window is not None:
            self._window.on_top = bool(on)
        return bool(on)

    def minimize(self) -> None:
        self.hide_chat()                   # back to the pet

    def close(self) -> None:
        self.hide_chat()                   # the pet stays; right-click it to quit

    # ------------------------------------------------------------------ links and the full console
    def open_url(self, url: str) -> bool:
        """Open a link from a message in the default browser (public http/https only)."""
        from tools.urlsafe import clean_url
        try:
            os.startfile(clean_url(url))
            return True
        except (ValueError, OSError):
            return False

    def open_console(self) -> bool:
        """The full Streamlit console: start it if it is not running, then open it in the browser."""
        port = 8501
        with socket.socket() as s:
            running = s.connect_ex(("127.0.0.1", port)) == 0
        if not running:
            exe = sys.executable.replace("pythonw.exe", "python.exe")
            subprocess.Popen([exe, "-m", "streamlit", "run", str(ROOT / "app.py"), "--server.headless", "true"],
                             cwd=str(ROOT), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            for _ in range(30):
                time.sleep(0.5)
                with socket.socket() as s:
                    if s.connect_ex(("127.0.0.1", port)) == 0:
                        break
        os.startfile(f"http://localhost:{port}")
        return True
