"""run_browser_task and the predefined Playwright scripts.

There is no free-form browsing: the model can only pick a task ID from the allow-list.
Text on the page is never treated as an instruction; the scripts use fixed selectors.
"""
from __future__ import annotations

import functools
import http.server
import socketserver
import threading
from pathlib import Path

from appconfig import ROOT, cfg, expand

_PORTAL_DIR = ROOT / "test_portal"
_server_lock = threading.Lock()
_server: socketserver.TCPServer | None = None


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def ensure_test_portal() -> str:
    """Serve ./test_portal on localhost (started once, in a background thread)."""
    global _server
    port = int(cfg("browser", "test_portal_port", default=8765))
    with _server_lock:
        if _server is None:
            handler = functools.partial(_QuietHandler, directory=str(_PORTAL_DIR))
            socketserver.TCPServer.allow_reuse_address = True
            try:
                _server = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
                threading.Thread(target=_server.serve_forever, daemon=True).start()
            except OSError:
                # Port already served (e.g. by an earlier run in this process tree).
                _server = None
    return f"http://127.0.0.1:{port}/"


def download_folder() -> Path:
    p = expand(cfg("browser", "download_folder", default="%USERPROFILE%\\Downloads"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _download_latest_report(page) -> dict:
    url = ensure_test_portal()
    page.goto(url, timeout=10_000)
    with page.expect_download(timeout=10_000) as dl_info:
        page.click("#latest-report", timeout=5_000)
    download = dl_info.value
    target = download_folder() / download.suggested_filename
    download.save_as(str(target))
    return {"ok": True, "task_id": "download_latest_report", "saved_to": str(target),
            "size_bytes": target.stat().st_size}


_TASKS = {
    "download_latest_report": _download_latest_report,
}


def run_browser_task(task_id: str) -> dict:
    if task_id not in _TASKS or task_id not in (cfg("browser", "allowed_tasks", default={}) or {}):
        return {"ok": False, "error": f"Unknown or not allowed browser task '{task_id}'"}
    from playwright.sync_api import sync_playwright

    channel = cfg("browser", "channel", default=None)
    headless = bool(cfg("browser", "headless", default=False))
    with sync_playwright() as p:
        launch = {"headless": headless}
        if channel:
            launch["channel"] = channel
        browser = p.chromium.launch(**launch)
        try:
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            result = _TASKS[task_id](page)
            page.wait_for_timeout(800)  # let the viewer see the page before it closes
            return result
        finally:
            browser.close()


def file_exists(path: str) -> dict:
    """Read-only verification helper (not a model tool)."""
    import time

    p = Path(path)
    if not p.is_file():
        return {"path": str(p), "exists": False, "size_bytes": 0, "fresh": False}
    st = p.stat()
    # "fresh" guards against an old file with the same name passing the check.
    return {"path": str(p), "exists": True, "size_bytes": st.st_size, "fresh": time.time() - st.st_mtime < 300}
