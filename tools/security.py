"""Security tools: antivirus and firewall state, a quick scan, and a suspicious-link check.

The agent never turns protection off, never isolates a host and never deletes mail: those are R3.
"""
from __future__ import annotations

import ipaddress
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from appconfig import cfg
from tools import powershell
from tools.registry import R0, R1, Param, tool

powershell.SCRIPTS.update({
    "defender_status": (
        "Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureAge,"
        "QuickScanAge,FullScanAge,@{n='last_quick_scan';e={ if($_.QuickScanEndTime){ $_.QuickScanEndTime.ToString('yyyy-MM-dd HH:mm') } }},"
        "@{n='definitions_updated';e={ if($_.AntivirusSignatureLastUpdated){ $_.AntivirusSignatureLastUpdated.ToString('yyyy-MM-dd') } }} | "
        "ConvertTo-Json -Compress"
    ),
    "threats": (
        "Get-MpThreatDetection -ErrorAction SilentlyContinue | Sort-Object InitialDetectionTime -Descending | "
        "Select-Object -First 5 @{n='time';e={$_.InitialDetectionTime.ToString('yyyy-MM-dd HH:mm')}},"
        "@{n='file';e={\"$($_.Resources | Select-Object -First 1)\"}},ThreatID | ConvertTo-Json -Compress"
    ),
})

_SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly", "rebrand.ly", "cutt.ly"}
_RISKY_TLDS = {"zip", "mov", "xyz", "top", "click", "country", "gq", "tk", "ml", "cf", "work", "rest"}
_BRANDS = ("microsoft", "office365", "outlook", "google", "apple", "paypal", "amazon", "netflix", "dhl", "fedex",
           "linkedin", "dropbox", "docusign", "okta", "adobe")


@tool("security", R0, "Antivirus state: is Microsoft Defender on, how old are the virus definitions, last scan.")
def get_antivirus_status() -> dict:
    d = powershell.run_powershell_json("defender_status") or {}
    age = d.get("AntivirusSignatureAge")
    if d.get("AntivirusEnabled") is None:
        return {"ok": True, "status": "unknown", "note": "Microsoft Defender did not report its state. Another "
                "antivirus product may manage this computer, or the information needs admin rights."}
    return {"ok": True, "antivirus_on": d.get("AntivirusEnabled"), "real_time_protection_on": d.get("RealTimeProtectionEnabled"),
            "definitions_age_days": age, "definitions_updated": d.get("definitions_updated"),
            "last_quick_scan": d.get("last_quick_scan") or "never",
            "healthy": bool(d.get("AntivirusEnabled") and d.get("RealTimeProtectionEnabled") and (age is None or age <= 7))}


@tool("security", R0, "Is the Windows Firewall on for each network type?")
def get_firewall_status() -> dict:
    rows = powershell.run_powershell_list("firewall_profiles")
    return {"ok": True, "profiles": {r["Name"]: ("on" if r["enabled"] else "off") for r in rows},
            "all_on": bool(rows) and all(r["enabled"] for r in rows)}


@tool("security", R0, "Threats the antivirus found recently on this computer.")
def get_recent_threats() -> dict:
    try:
        rows = powershell.run_powershell_list("threats")
    except powershell.CommandError as e:
        return {"ok": False, "error": f"The threat history could not be read without admin rights ({str(e)[:80]})"}
    return {"ok": True, "count": len(rows), "threats": [{"time": r.get("time"), "file": (r.get("file") or "")[:90]}
                                                        for r in rows]}


@tool("security", R0, "Check a link from an email or message for signs of phishing WITHOUT opening it.",
      params=(Param("url", "str", "the full link", max_len=500),))
def check_suspicious_link(url: str) -> dict:
    raw = url.strip()
    parts = urlsplit(raw if "://" in raw else "http://" + raw)
    host = (parts.hostname or "").lower()
    if not host:
        return {"ok": False, "error": "That does not look like a link"}
    signs = []
    if parts.scheme != "https":
        signs.append("it does not use https")
    try:
        ipaddress.ip_address(host)
        signs.append("it uses a raw IP address instead of a name")
    except ValueError:
        pass
    if host.startswith("xn--") or ".xn--" in host:
        signs.append("the name uses look-alike international characters")
    if "@" in parts.netloc:
        signs.append("it hides the real address behind an @ sign")
    if host in _SHORTENERS:
        signs.append("it is a link shortener, so the real destination is hidden")
    labels = host.split(".")
    if labels[-1] in _RISKY_TLDS:
        signs.append(f"the ending .{labels[-1]} is often used for scams")
    if len(labels) > 4:
        signs.append("it has an unusually long chain of sub-names")
    registered = ".".join(labels[-2:])
    trusted = [d.lower() for d in (cfg("security", "trusted_domains", default=[]) or [])]
    for brand in _BRANDS:
        if brand in host and not any(registered == t or registered.endswith("." + t) for t in trusted) \
                and not registered.startswith(brand + "."):
            signs.append(f"it mentions '{brand}' but the real site is {registered}")
            break
    if re.search(r"(login|verify|secure|account|update|password)", parts.path.lower() + host) and signs:
        signs.append("it asks you to sign in or verify an account")
    verdict = "looks suspicious: do not open it" if len(signs) >= 2 else \
              "be careful" if signs else "no warning signs found (this is not a guarantee)"
    return {"ok": True, "site": registered, "warning_signs": signs, "verdict": verdict,
            "advice": "Never enter your password after clicking a link in an email. Report suspicious emails to IT."}


@tool("security", R1, "Start a Microsoft Defender quick virus scan in the background.",
      change_note="A quick virus scan will start and run in the background for a few minutes. "
                  "The computer may feel slower while it runs. Nothing is deleted without Defender's own prompt.")
def start_quick_scan() -> dict:
    exe = Path(r"C:\Program Files\Windows Defender\MpCmdRun.exe")
    if not exe.is_file():
        return {"ok": False, "error": "Microsoft Defender is not installed on this computer"}
    subprocess.Popen([str(exe), "-Scan", "-ScanType", "1"],
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True, "started": "quick scan", "note": "Results appear in Windows Security > Protection history."}
