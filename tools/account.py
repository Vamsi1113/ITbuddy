"""Account tools (read-only): who is signed in, admin rights, password expiry.

Password resets, unlocks, MFA and group changes need identity verification and a directory
connector (AD / Entra / Okta). They are R3 here: the agent opens a ticket for IT.
"""
from __future__ import annotations

import ctypes
import getpass
import os
import subprocess

from tools import powershell
from tools.registry import R0, tool

_WANTED = ("Full Name", "Account active", "Account expires", "Password last set", "Password expires",
           "Password changeable", "Last logon")


@tool("account", R0, "Who is signed in: user name, domain or local account, admin rights, main groups.")
def get_current_user() -> dict:
    user = getpass.getuser()
    domain = os.environ.get("USERDOMAIN", "")
    groups = []
    try:
        for line in (powershell.run_executable("whoami_groups").stdout or "").splitlines():
            name = line.split('","')[0].strip('"')
            if name and not name.startswith(("Mandatory Label", "NT AUTHORITY", "Everyone", "CONSOLE", "LOCAL")):
                groups.append(name)
    except Exception:
        pass
    try:
        elevated = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        elevated = None
    return {"ok": True, "user": user, "domain": domain,
            "account_type": "local account" if domain == os.environ.get("COMPUTERNAME") else "domain account",
            "running_with_admin_rights": elevated,
            "member_of_administrators": any(g.endswith("\\Administrators") for g in groups),
            "groups": groups[:8]}


@tool("account", R0, "Password facts for the signed-in user: when it was last set, when it expires, last sign-in.")
def get_password_info() -> dict:
    user = getpass.getuser()  # never taken from the model
    proc = subprocess.run(["net", "user", user], capture_output=True, text=True, timeout=20,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if proc.returncode != 0:
        return {"ok": False, "error": "Windows could not read this account locally. For a company (domain) account, "
                                      "password details come from the directory, which is not connected."}
    info = {}
    for line in proc.stdout.splitlines():
        for key in _WANTED:
            if line.startswith(key):
                info[key.lower().replace(" ", "_")] = line[len(key):].strip()
    return {"ok": True, "user": user, **info}
