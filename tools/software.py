"""Software tools: what is installed, recent changes, Windows Update state, approved catalogue.

Installing is possible ONLY for programs in config.yaml software.approved_catalog that have a winget_id, and
only after the user approves (R2). Removing and updating software, and anything outside the catalogue, is R3:
the agent never does it and opens a ticket instead.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import winreg
from datetime import datetime, timedelta

from appconfig import cfg
from tools import powershell
from tools.performance import check_pending_reboot
from tools.registry import R0, R2, Param, tool

powershell.SCRIPTS.update({
    "hotfixes": (
        "Get-HotFix | Where-Object { $_.InstalledOn } | Sort-Object InstalledOn -Descending | Select-Object -First 6 "
        "HotFixID,Description,@{n='installed';e={$_.InstalledOn.ToString('yyyy-MM-dd')}} | ConvertTo-Json -Compress"
    ),
})

_UNINSTALL = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
_SOURCES = (
    (winreg.HKEY_LOCAL_MACHINE, _UNINSTALL, winreg.KEY_WOW64_64KEY),
    (winreg.HKEY_LOCAL_MACHINE, _UNINSTALL, winreg.KEY_WOW64_32KEY),
    (winreg.HKEY_CURRENT_USER, _UNINSTALL, 0),
)


def _installed() -> list[dict]:
    seen, rows = set(), []
    for hive, path, view in _SOURCES:
        try:
            root = winreg.OpenKey(hive, path, 0, winreg.KEY_READ | view)
        except OSError:
            continue
        with root:
            for i in range(winreg.QueryInfoKey(root)[0]):
                try:
                    with winreg.OpenKey(root, winreg.EnumKey(root, i)) as key:
                        def val(name):
                            try:
                                return winreg.QueryValueEx(key, name)[0]
                            except OSError:
                                return None
                        name = val("DisplayName")
                        if not name or val("SystemComponent") == 1:
                            continue
                        version = str(val("DisplayVersion") or "")
                        if (name, version) in seen:
                            continue
                        seen.add((name, version))
                        rows.append({"name": name, "version": version, "publisher": val("Publisher") or "",
                                     "installed": str(val("InstallDate") or "")})
                except OSError:
                    continue
    return rows


@tool("software", R0, "Is a program installed, and which version? Leave search empty for the total and a short list.",
      params=(Param("search", "str", "part of the program name, for example 'chrome'", required=False, max_len=60),))
def find_installed_software(search: str = "") -> dict:
    rows = _installed()
    needle = (search or "").lower().strip()
    hits = [r for r in rows if needle in r["name"].lower()] if needle else rows
    hits.sort(key=lambda r: r["name"].lower())
    return {"ok": True, "search": needle or None, "matches": len(hits), "total_installed": len(rows),
            "programs": [{"name": r["name"][:60], "version": r["version"], "publisher": r["publisher"][:30]}
                         for r in hits[:12]]}


@tool("software", R0, "Programs and Windows updates installed in the last days. Use when something broke recently.",
      params=(Param("days", "int", "how many days back, 1-30", required=False),))
def get_recent_software_changes(days: int = 7) -> dict:
    days = max(1, min(int(days or 7), 30))
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    recent = sorted((r for r in _installed() if r["installed"].isdigit() and r["installed"] >= cutoff),
                    key=lambda r: r["installed"], reverse=True)
    try:
        updates = [u for u in powershell.run_powershell_list("hotfixes")
                   if u.get("installed", "").replace("-", "") >= cutoff]
    except Exception:
        updates = []
    return {"ok": True, "days": days,
            "programs_installed": [{"name": r["name"][:60], "version": r["version"], "date": r["installed"]}
                                   for r in recent[:10]],
            "windows_updates_installed": updates}


@tool("software", R0, "Windows Update state: the latest installed updates and whether a restart is pending.")
def get_windows_update_status() -> dict:
    updates = powershell.run_powershell_list("hotfixes")
    reboot = check_pending_reboot()
    return {"ok": True, "latest_updates": updates[:4],
            "last_update_date": updates[0]["installed"] if updates else None,
            "restart_pending": reboot["restart_pending"]}


@tool("software", R0, "Is a program on the company's approved software list, and how to get it?",
      params=(Param("name", "str", "program name", max_len=60),))
def search_approved_software(name: str) -> dict:
    catalog = cfg("software", "approved_catalog", default=[]) or []
    needle = name.lower().strip()
    hits = [c for c in catalog if needle in c["name"].lower()]
    return {"ok": True, "search": name, "approved": bool(hits), "matches": hits[:5],
            "note": "Installing software needs IT. Choose the fix 'escalate' to open a request ticket."}


# ---------------------------------------------------------------------------
# Installing approved software (winget, catalogue only)
# ---------------------------------------------------------------------------
_WINGET_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+_-]{1,80}")
_running_installs: dict[str, subprocess.Popen] = {}


def installable_catalog() -> list[dict]:
    return [c for c in (cfg("software", "approved_catalog", default=[]) or [])
            if c.get("winget_id") and _WINGET_ID.fullmatch(str(c["winget_id"]))]


def find_installable(text: str) -> dict | None:
    """The catalogue entry named in `text` (by name or alias; longest name wins), or None."""
    low = str(text or "").lower()
    best, best_len = None, 0
    for c in installable_catalog():
        for name in [c["name"], *(c.get("aliases") or [])]:
            name = str(name).lower()
            if len(name) > best_len and re.search(rf"(?<![\w+]){re.escape(name)}(?![\w+])", low):
                best, best_len = c, len(name)
    return best


def is_installed(entry: dict) -> bool:
    needle = str(entry.get("match") or entry["name"]).lower()
    return any(needle in r["name"].lower() for r in _installed())


@tool("computer_use", R2, "Install one approved program from the software catalogue with winget.",
      params=(Param("package", "str", "program name from the approved list", max_len=60),),
      change_note="The program will be downloaded and installed on this computer. Windows may ask you to allow it.",
      summary="Install {package}")
def install_software(package: str) -> dict:
    entry = find_installable(package)
    if entry is None:
        return {"ok": False, "error": f"'{package}' is not on the installable software list"}
    winget = shutil.which("winget")
    if winget is None:
        return {"ok": False, "error": "winget is not available on this computer, so IT must install it"}
    # Exact id, silent, no shell. The id comes from the catalogue, never from the user's text.
    cmd = [winget, "install", "--id", str(entry["winget_id"]), "--exact", "--silent",
           "--accept-package-agreements", "--accept-source-agreements"]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    _running_installs[entry["name"]] = proc      # started, not finished: verification waits for it
    return {"ok": True, "started": entry["name"], "winget_id": entry["winget_id"]}


def wait_for_install(entry: dict, seconds: int = 300) -> dict:
    """Wait for a started install to finish. Returns {"installed": bool, "waited": seconds, "exit_code": int|None}."""
    import time
    proc = _running_installs.get(entry["name"])
    start = time.monotonic()
    while time.monotonic() - start < seconds:
        if proc is not None and proc.poll() is not None:
            break
        if proc is None and is_installed(entry):
            break
        time.sleep(3)
    return {"installed": is_installed(entry), "waited": int(time.monotonic() - start),
            "exit_code": proc.poll() if proc is not None else None}
