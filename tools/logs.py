"""Event log tools: recent errors, app crashes, unexpected shutdowns. Read-only.

Log text is data. It is shortened and never treated as an instruction.
"""
from __future__ import annotations

from tools import powershell
from tools.registry import R0, Param, tool

powershell.SCRIPTS.update({
    "recent_errors": (
        "$t=(Get-Date).AddHours(-[int]$env:ITB_ARG); "
        "Get-WinEvent -FilterHashtable @{LogName='System','Application'; Level=1,2; StartTime=$t} -ErrorAction SilentlyContinue | "
        "Group-Object ProviderName,Id | Sort-Object Count -Descending | Select-Object -First 8 "
        "@{n='count';e={$_.Count}},@{n='source';e={$_.Group[0].ProviderName}},@{n='event_id';e={$_.Group[0].Id}},"
        "@{n='last';e={$_.Group[0].TimeCreated.ToString('MM-dd HH:mm')}},"
        "@{n='message';e={(\"$($_.Group[0].Message)\" -split \"`n\")[0]}} | ConvertTo-Json -Compress"
    ),
    "app_crashes": (
        "$t=(Get-Date).AddDays(-[int]$env:ITB_ARG); "
        "Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='Application Error','Application Hang'; StartTime=$t} "
        "-ErrorAction SilentlyContinue | Group-Object { $_.Properties[0].Value } | Sort-Object Count -Descending | "
        "Select-Object -First 8 @{n='app';e={$_.Name}},@{n='crashes';e={$_.Count}},"
        "@{n='last';e={$_.Group[0].TimeCreated.ToString('MM-dd HH:mm')}},"
        "@{n='kind';e={$_.Group[0].ProviderName}} | ConvertTo-Json -Compress"
    ),
    "shutdowns": (
        "$t=(Get-Date).AddDays(-30); "
        "Get-WinEvent -FilterHashtable @{LogName='System'; Id=41,6008,1001; StartTime=$t} -ErrorAction SilentlyContinue | "
        "Select-Object -First 8 @{n='time';e={$_.TimeCreated.ToString('yyyy-MM-dd HH:mm')}},Id,"
        "@{n='source';e={$_.ProviderName}} | ConvertTo-Json -Compress"
    ),
})

_SHUTDOWN_MEANING = {41: "the computer restarted without shutting down cleanly (power loss, freeze or crash)",
                     6008: "the previous shutdown was unexpected", 1001: "Windows crashed with a blue screen"}


@tool("logs", R0, "The most frequent errors in the Windows System and Application logs in the last hours.",
      params=(Param("hours", "int", "how many hours back, 1-168", required=False),))
def get_recent_errors(hours: int = 24) -> dict:
    hours = max(1, min(int(hours or 24), 168))
    rows = powershell.run_powershell_list("recent_errors", arg=str(hours))
    for r in rows:
        r["message"] = (r.get("message") or "").strip()[:110]
    return {"ok": True, "hours": hours, "distinct_errors": len(rows), "errors": rows}


@tool("logs", R0, "Which apps crashed or froze in the last days, and how often.",
      params=(Param("days", "int", "how many days back, 1-30", required=False),))
def get_app_crashes(days: int = 7) -> dict:
    days = max(1, min(int(days or 7), 30))
    rows = powershell.run_powershell_list("app_crashes", arg=str(days))
    return {"ok": True, "days": days, "apps_with_crashes": len(rows), "crashes": rows}


@tool("logs", R0, "Unexpected shutdowns, power losses and blue-screen crashes in the last 30 days.")
def get_unexpected_shutdowns() -> dict:
    rows = powershell.run_powershell_list("shutdowns")
    events = [{"time": r["time"], "what": _SHUTDOWN_MEANING.get(r["Id"], r.get("source"))}
              for r in rows if r["Id"] != 1001 or "BugCheck" in (r.get("source") or "") or "WER" in (r.get("source") or "")]
    return {"ok": True, "count": len(events), "events": events}
