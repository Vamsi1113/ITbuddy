"""PowerShell connector: run ONE command the user has approved.

This is the most powerful tool, so it has three layers:
  1. It is R2: it never runs without the user approving the exact command text shown on the approval card.
  2. A hard deny-list (below) blocks commands that destroy data, change security or accounts, download and run
     code, hide their content, or tamper with logs. The list is checked by the policy gate, in Python.
  3. It runs as the signed-in user, never elevated, with no profile, a 25 second limit and truncated output.
The deny-list cannot make an arbitrary shell safe on its own; the approval step is the real control.
"""
from __future__ import annotations

import re
import subprocess

from connectors.base import ensure, guard
from tools.registry import R2, Param, tool

_DENY = [
    (r"format-volume|(?<!\w)format\s+[a-z]:|diskpart|clear-disk|remove-partition|initialize-disk", "disk formatting or partitioning"),
    (r"bcdedit|bootrec|(?<!\w)reagentc", "boot configuration"),
    (r"(?<!\w)reg(?:\.exe)?\s+(?:add|delete|import|load|save|restore)|new-itemproperty|set-itemproperty|remove-itemproperty"
     r"|(?:hklm|hkey_local_machine|hkcu|hkey_current_user)\s*:?[\\/]", "registry changes"),
    (r"net(?:1)?\s+(?:user|localgroup|accounts)|new-localuser|set-localuser|remove-localuser|add-localgroupmember|"
     r"enable-localuser|disable-localuser|add-adgroupmember|set-aduser|new-aduser", "user and group changes"),
    (r"set-mppreference|add-mppreference|disable-windowsoptionalfeature|netsh\s+(?:advfirewall|firewall)|"
     r"set-netfirewall|disable-netfirewall|new-netfirewallrule|stop-service.{0,40}(?:defender|windefend|sense|mpssvc|wscsvc)|"
     r"sc(?:\.exe)?\s+(?:stop|delete|config)|set-service.{0,60}disabled", "security and service settings"),
    (r"invoke-expression|(?<!\w)iex(?!\w)|downloadstring|downloadfile|invoke-webrequest|invoke-restmethod|"
     r"(?<!\w)(?:curl|wget|iwr|irm)(?:\.exe)?(?!\w)|start-bitstransfer|bitsadmin|certutil.{0,30}urlcache|new-object\s+net\.webclient|"
     r"system\.net\.", "downloading or running remote code"),
    (r"-enc(?:odedcommand)?(?!\w)|frombase64string|-windowstyle\s+hidden|-w\s+hidden", "hidden or encoded commands"),
    (r"start-process.{0,60}-verb\s+runas|-verb\s+runas|runas(?:\.exe)?(?!\w)", "elevation"),
    (r"set-executionpolicy|unblock-file", "script execution policy"),
    (r"vssadmin|wbadmin|cipher\s+/w|wevtutil\s+cl|clear-eventlog|remove-eventlog|fsutil\s+usn", "backups and logs"),
    (r"(?<!\w)(?:stop|restart)-computer|(?<!\w)shutdown(?:\.exe)?(?!\w)|(?<!\w)logoff(?!\w)", "shutdown and restart"),
    (r"(?:remove-item|(?<!\w)del(?:\.exe)?(?!\w)|(?<!\w)rd(?!\w)|rmdir|(?<!\w)rm(?!\w)|erase).{0,200}?"
     r"(?:[a-z]:\\\s*(?:$|[\"'\s*])|[a-z]:\\windows|program files|programdata|\\users\\?\s*(?:$|[\"'\s*])|system32|\\\\\*)",
     "deleting system or whole-drive locations"),
    (r"register-scheduledtask|schtasks\s+/create|new-scheduledtask|at\.exe", "scheduled tasks"),
    (r"(?<!\w)(?:wmic|mshta|rundll32|regsvr32|cscript|wscript|msiexec)(?:\.exe)?(?!\w)", "script hosts and installers"),
    (r"add-type|\[reflection\.assembly\]|\[system\.reflection|loadwithpartialname|\[convert\]::frombase64", "code loading"),
    (r"out-file|set-content|add-content|tee-object|export-csv|export-clixml|new-item|(?<![-=])>", "writing files (use the Files tools instead)"),
]
_DENY_RE = [(re.compile(p, re.IGNORECASE), why) for p, why in _DENY]


def check_command(command: str) -> str | None:
    """The reason a command is blocked, or None when the deny-list allows it."""
    text = str(command or "")
    if not text.strip():
        return "The command is empty"
    if len(text) > 1000 or text.count("\n") > 15:
        return "The command is too long; split it into smaller steps"
    for pattern, why in _DENY_RE:
        if pattern.search(text):
            return f"Blocked: this command involves {why}"
    return None


@guard("run_powershell")
def _guard(args: dict) -> None:
    why = check_command(args.get("command", ""))
    if why:
        raise ValueError(why)


@tool("shell", R2, "Run one PowerShell command as the signed-in user (not elevated) after the user approves the exact "
                   "text. Prefer the dedicated tools; use this only when none fits. No downloads, registry, accounts, "
                   "security or service changes.",
      params=(Param("command", "str", "the PowerShell command", max_len=1000),
              Param("purpose", "str", "one sentence: why this command is needed", max_len=200, required=False)),
      change_note="PowerShell will run exactly the command shown, with your Windows permissions. It can change things "
                  "on this computer, so read it before approving.",
      summary="Run a PowerShell command")
def run_powershell(command: str, purpose: str = "") -> dict:
    if (e := ensure("shell")):
        return e
    why = check_command(command)
    if why:
        return {"ok": False, "error": why}
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=25, stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "The command took longer than 25 seconds and was stopped"}
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    return {"ok": proc.returncode == 0, "exit_code": proc.returncode,
            "output": out[:900] + ("..." if len(out) > 900 else ""),
            **({"error": err[:400]} if err else {})}
