"""Printing troubleshooter: finds out WHERE a printing problem is, fixes what is on this computer, and tells the
user exactly what to do about the rest.

Four layers are checked in one read-only pass (`diagnose_printing`):
  computer  the print service (spooler), printers, default printer, stuck or failed jobs, driver, recent print errors
  file      the document itself: missing, empty, locked, corrupted, password-protected, a type that cannot be printed
  printer   what the printer itself reports: offline, out of paper or ink, jam, open door, needs service
  network   whether the printer can be reached at all (its address answers on the printing port) or is on USB

Everything that is wrong on the COMPUTER side gets a fix (clear queue, set default, bring online, restart the
spooler when the user is an administrator). Everything outside the computer gets plain-language steps for the
user. Problems that need administrator rights are handed to IT instead of being attempted.
"""
from __future__ import annotations

import ctypes
import os
import re
import socket
import zipfile
from pathlib import Path

from tools import powershell
from tools.registry import R0, R1, R2, Param, tool

# ---------------------------------------------------------------------------
# Fixed PowerShell scripts (the model never writes a command; the one argument comes from ITB_ARG)
# ---------------------------------------------------------------------------
powershell.SCRIPTS.update({
    "print_state": (
        "$sp=(Get-Service Spooler -ErrorAction SilentlyContinue).Status.ToString(); "
        "$pr=@(Get-CimInstance Win32_Printer | Select-Object Name,Default,WorkOffline,PrinterStatus,DetectedErrorState,"
        "PortName,Local,Network,DriverName); "
        "$ports=@(Get-PrinterPort -ErrorAction SilentlyContinue | Select-Object Name,PrinterHostAddress,PortNumber); "
        "$jobs=@(foreach($p in $pr){ Get-PrintJob -PrinterName $p.Name -ErrorAction SilentlyContinue | "
        "Select-Object PrinterName,DocumentName,@{n='status';e={\"$($_.JobStatus)\"}},"
        "@{n='age_min';e={[int]((Get-Date)-$_.SubmittedTime).TotalMinutes}},TotalPages }); "
        "$ev=@(try{ Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-PrintService/Admin';Level=2,3;"
        "StartTime=(Get-Date).AddHours(-24)} -MaxEvents 4 -ErrorAction Stop | "
        "Select-Object Id,@{n='msg';e={$_.Message.Substring(0,[Math]::Min(140,$_.Message.Length))}} }catch{}); "
        "[pscustomobject]@{spooler=$sp;printers=$pr;ports=$ports;jobs=$jobs;events=$ev} | ConvertTo-Json -Depth 4 -Compress"
    ),
    "restart_spooler": "Restart-Service -Name Spooler -Force -ErrorAction Stop; 'ok'",
    "set_default_printer": (
        "$n=$env:ITB_ARG.Replace(\"'\",\"''\"); $p=Get-CimInstance Win32_Printer -Filter \"Name='$n'\" -ErrorAction Stop; "
        "if(-not $p){throw 'printer not found'}; $r=Invoke-CimMethod -InputObject $p -MethodName SetDefaultPrinter; "
        "if($r.ReturnValue -ne 0){throw \"SetDefaultPrinter returned $($r.ReturnValue)\"}; 'ok'"
    ),
    "set_printer_online": (
        "$n=$env:ITB_ARG.Replace(\"'\",\"''\"); $p=Get-CimInstance Win32_Printer -Filter \"Name='$n'\" -ErrorAction Stop; "
        "Set-CimInstance -InputObject $p -Property @{WorkOffline=$false} -ErrorAction Stop; 'ok'"
    ),
    "print_test_page": (
        "$n=$env:ITB_ARG.Replace(\"'\",\"''\"); $p=Get-CimInstance Win32_Printer -Filter \"Name='$n'\" -ErrorAction Stop; "
        "$r=Invoke-CimMethod -InputObject $p -MethodName PrintTestPage; "
        "if($r.ReturnValue -ne 0){throw \"PrintTestPage returned $($r.ReturnValue)\"}; 'ok'"
    ),
})

# ---------------------------------------------------------------------------
# Reading the current state
# ---------------------------------------------------------------------------
_VIRTUAL_PORTS = ("portprompt", "file:", "nul:", "xpsport", "microsoft.", "ps:")
_VIRTUAL_NAMES = re.compile(r"pdf|xps|onenote|fax|snagit|document writer|print to file", re.IGNORECASE)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _as_list(value) -> list:
    if value is None or value == "":
        return []
    return value if isinstance(value, list) else [value]


def is_virtual(printer: dict) -> bool:
    port = str(printer.get("PortName") or "").lower()
    return port.startswith(_VIRTUAL_PORTS) or bool(_VIRTUAL_NAMES.search(str(printer.get("Name") or "")))


def collect_state() -> dict:
    """The raw state of the print system (one PowerShell call)."""
    raw = powershell.run_powershell_json("print_state", timeout=28) or {}
    return {
        "spooler": raw.get("spooler") or "Unknown",
        "admin": is_admin(),
        "printers": _as_list(raw.get("printers")),
        "ports": _as_list(raw.get("ports")),
        "jobs": _as_list(raw.get("jobs")),
        "events": _as_list(raw.get("events")),
    }


def probe_host(host: str, port: int = 9100, timeout: float = 2.0) -> bool:
    """Does the printer's address accept a connection on its printing port? (no ping needed)"""
    for p in dict.fromkeys([port or 9100, 9100, 631, 515]):
        try:
            with socket.create_connection((host, int(p)), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def _host_of_port(port: dict) -> tuple[str, int] | None:
    """Printer address and port number for a TCP/IP, IPP or LPR port, else None (USB, WSD, local)."""
    host = str(port.get("PrinterHostAddress") or "").strip()
    number = int(port.get("PortNumber") or 9100)
    if host:
        return host, number
    name = str(port.get("Name") or "")
    m = re.match(r"https?://([^/:]+)(?::(\d+))?", name, re.IGNORECASE)      # IPP: http://host:631/ipp/print
    if m:
        return m.group(1), int(m.group(2) or 631)
    m = re.match(r"IP_(\d{1,3}(?:\.\d{1,3}){3})$", name)                    # Standard TCP/IP port named IP_192.168.1.20
    if m:
        return m.group(1), number
    return None


# ---------------------------------------------------------------------------
# What the printer says (Win32_Printer.DetectedErrorState) -> plain language and steps for the user
# ---------------------------------------------------------------------------
_PRINTER_ERRORS = {
    3: ("is low on paper", ["Add paper to the tray before it runs out."]),
    4: ("is out of paper", ["Load paper into the tray, then press the printer's OK or Resume button."]),
    5: ("is low on toner or ink", ["Printing can continue, but replace the cartridge soon."]),
    6: ("is out of toner or ink", ["Replace the ink or toner cartridge, then press OK or Resume on the printer."]),
    7: ("has a door or cover open", ["Close every cover, the cartridge door and the paper tray fully, then press OK."]),
    8: ("has a paper jam", ["Switch the printer off.", "Open the covers and pull stuck paper out gently, in the direction the paper travels, without tearing it.",
                           "Check for small torn pieces, close everything, switch it on and press OK."]),
    9: ("says it is offline", ["Check it is switched on and not asleep (press a button on it).", "Look at its screen for an error and clear it."]),
    10: ("asks for service", ["Switch the printer off, wait 30 seconds and on again.", "If the message returns, note it down and ask IT or the printer supplier."]),
    11: ("has a full output tray", ["Empty the output tray, then press OK on the printer."]),
}

_NETWORK_STEPS = [
    "Check the printer is switched on and its screen shows no error.",
    "Check it is on the same network as your computer (same Wi-Fi or network cable). Working from home? Connect to the VPN or the office network first.",
    "Print the printer's own network or status page from its menu and compare its IP address with {host}. If they differ, the printer's address has changed and IT must update it.",
    "Restart the printer, wait two minutes, and try again.",
]
_USB_STEPS = [
    "Check the USB cable is firmly connected at both ends, and try another USB port or cable.",
    "Check the printer is switched on, then switch it off and on again.",
    "Avoid USB hubs and docks for a test: plug the printer straight into the computer.",
]
_FILE_STEPS = [
    "Open the file in its own program and check it opens and looks right.",
    "Save a copy (File > Save as) and print the copy, or print it to PDF first and print the PDF.",
    "Try printing a different document. If that works, the problem is this file, not the printer.",
]

_PRINTABLE = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf", ".csv", ".jpg", ".jpeg", ".png",
              ".gif", ".bmp", ".tif", ".tiff", ".odt", ".ods", ".htm", ".html", ".xps"}
_NEVER_PRINT = {".exe", ".dll", ".zip", ".rar", ".7z", ".iso", ".msi", ".mp3", ".mp4", ".mov", ".avi", ".bat", ".ps1", ".lnk"}
_EXT = r"(?:pdf|docx?|xlsx?|pptx?|txt|csv|rtf|jpe?g|png|gif|bmp|tiff?|odt|ods)"
_FILE_NAME = re.compile(r"[\"\u201c']([^\"\u201d'\n]{1,80}\." + _EXT + r")[\"\u201d']|"
                        r"(?<![\w'\u2019])([\w][\w\-()]*(?: [\w\-()]+){0,5}\." + _EXT + r")(?![\w])", re.IGNORECASE)
_PRINT_REQUEST = re.compile(
    r"(?<!\w)(printers?|printing|print\s+(?:job|jobs|queue|spooler|server)|spooler|toner|cartridge|paper\s+jam|"
    r"(?:won'?t|can'?t|cannot|not|unable\s+to|fails?\s+to|doesn'?t|does\s+not|will\s+not)\s+(?:[\w.\-()]+\s+){0,3}print\w*|"
    r"print\w*\s+(?:is\s+|are\s+)?(?:stuck|slow|blank|offline|failing))(?!\w)", re.IGNORECASE)


def is_print_request(text: str) -> bool:
    return bool(_PRINT_REQUEST.search(text or ""))


_PRINT_PROBLEM = re.compile(
    r"(?<!\w)(not|cannot|unable|fails?|failed|failing|error|errors|offline|stuck|jam|jams|jammed|toner|ink|cartridge|spooler|"
    r"blank|slow|queue|broken|issue|issues|problem|problems|wrong|stopped|missing|disappeared|garbled|faded|streaks?|smudged)(?!\w)"
    r"|n[\u2019']t(?!\w)", re.IGNORECASE)


def is_print_problem(text: str) -> bool:
    """Something is WRONG with printing (offline, stuck, will not print ...). Mentioning a printer is not a problem:
    "which printer should I use" or "I want to use another ODC's printer" is a question about rules and access, and
    "is a printer connected or not" is a status question."""
    cleaned = re.sub(r"(?<!\w)(?:or\s+not|whether)(?!\w)", " ", text or "", flags=re.IGNORECASE)
    return is_print_request(cleaned) and bool(_PRINT_PROBLEM.search(cleaned))


_PRINT_STATUS = re.compile(
    r"(?<!\w)(?:printers?\b.{0,40}\b(?:connected|installed|attached|set\s*up|available|plugged|working|there|added)|"
    r"(?:connected|installed|attached|available|any|have\s+(?:a|any))\s+(?:\w+\s+){0,3}printers?|"
    r"do\s+i\s+have\s+(?:a|any)\s+printers?)(?!\w)", re.IGNORECASE)


def is_print_status(text: str) -> bool:
    """"Is a printer connected to my system?", "do I have a printer", "which printers are installed here"."""
    return bool(_PRINT_STATUS.search(text or ""))


def extract_file_name(text: str) -> str:
    m = _FILE_NAME.search(text or "")
    return (m.group(1) or m.group(2)).strip() if m else ""


# ---------------------------------------------------------------------------
# The file layer
# ---------------------------------------------------------------------------
def locate_file(name: str) -> Path | None:
    """Find the document: an absolute path inside an allowed folder, or a file name in Documents, Desktop, Downloads.
    A name picked out of a sentence may carry extra leading words, so shorter endings are tried too."""
    from connectors.files import allowed_folders, resolve_inside
    try:
        p = resolve_inside(name) if os.path.isabs(os.path.expandvars(name)) else None
    except ValueError:
        return None
    if p and p.is_file():
        return p
    words = Path(name).name.split()
    candidates = [" ".join(words[i:]).lower() for i in range(len(words))]      # longest first
    for folder in allowed_folders():
        base_depth = len(folder.parts)
        index: dict[str, Path] = {}
        for root, dirs, files in os.walk(folder):
            if len(Path(root).parts) - base_depth >= 2:
                dirs[:] = []
            for f in files:
                index.setdefault(f.lower(), Path(root, f))
        for c in candidates:
            if c in index:
                return index[c]
    return None


def check_file(name: str) -> dict:
    """Read-only checks on the document. Returns {"name", "found", "problems": [str]}."""
    out = {"name": name, "found": False, "path": "", "problems": []}
    p = locate_file(name)
    if p is None:
        out["problems"].append("I could not find that file in Documents, Desktop or Downloads")
        return out
    out.update(found=True, path=str(p), name=p.name)
    size = p.stat().st_size
    ext = p.suffix.lower()
    if size == 0:
        out["problems"].append("the file is empty (0 bytes), so there is nothing to print")
        return out
    if ext in _NEVER_PRINT or (ext and ext not in _PRINTABLE):
        out["problems"].append(f"{ext or 'this'} files cannot be printed directly: open them in their own program first")
    if size > 150 * 1024 * 1024:
        out["problems"].append(f"the file is very large ({size // (1024 * 1024)} MB), which can make the print job fail or take very long")
    try:
        with open(p, "rb") as f:
            head = f.read(2048)
            if ext == ".pdf":
                if not head.startswith(b"%PDF"):
                    out["problems"].append("the PDF looks damaged (it does not start like a PDF)")
                f.seek(0)
                data = f.read(min(size, 4_000_000))
                if b"/Encrypt" in data:
                    out["problems"].append("the PDF is password-protected or has printing restrictions")
            elif ext in (".docx", ".xlsx", ".pptx") and not zipfile.is_zipfile(p):
                out["problems"].append("the Office file looks damaged (it is not a valid document)")
    except PermissionError:
        out["problems"].append("the file is locked or you have no permission to read it (it may be open in another program)")
    except OSError as e:
        out["problems"].append(f"the file cannot be read ({type(e).__name__})")
    return out


# ---------------------------------------------------------------------------
# The analysis: findings, each with its layer, a fix (if the computer can do it) and steps (if the user must)
# ---------------------------------------------------------------------------
def _finding(fid: str, layer: str, what: str, *, severity: str = "problem", fix: dict | None = None,
             steps: list[str] | None = None, needs_it: bool = False) -> dict:
    return {"id": fid, "layer": layer, "severity": severity, "what": what, "fix": fix, "steps": steps or [],
            "needs_it": needs_it}


def analyse(state: dict, file_info: dict | None = None, probe=probe_host) -> list[dict]:
    """Turn the raw state into findings. Pure: `probe` is injectable so tests need no network."""
    f: list[dict] = []
    admin = bool(state.get("admin"))
    printers = state.get("printers", [])
    real = [p for p in printers if not is_virtual(p)]

    # --- computer: the print service
    if state.get("spooler") not in ("Running", "Unknown"):
        f.append(_finding("spooler", "computer", f"The Print Spooler service is {state.get('spooler', 'not running')}, so nothing can print",
                          fix={"tool": "restart_print_spooler", "args": {}, "domain": "devices"} if admin else None,
                          steps=[] if admin else ["Ask IT to start the Print Spooler service: changing Windows services needs administrator rights."],
                          needs_it=not admin))

    # --- computer: no printer / wrong default
    if not real:
        f.append(_finding("no-printer", "computer", "No physical printer is installed on this computer (only virtual ones such as Print to PDF)",
                          fix={"tool": "open_settings_page", "args": {"page": "printers"}, "domain": "settings", "assist": True},
                          steps=["Settings > Bluetooth & devices > Printers & scanners > Add device, then pick your printer.",
                                 "An office printer may need to be added by IT or from the company print server."]))
    else:
        default = next((p for p in printers if p.get("Default")), None)
        if default is not None and is_virtual(default) and len(real) == 1:
            f.append(_finding("default-virtual", "computer",
                              f"Your default printer is '{default.get('Name')}' (a virtual printer), so documents never reach {real[0].get('Name')}",
                              fix={"tool": "set_default_printer", "args": {"printer_name": real[0]["Name"]}, "domain": "devices"}))
        elif default is None and len(real) == 1:
            f.append(_finding("default-none", "computer", "No default printer is set",
                              fix={"tool": "set_default_printer", "args": {"printer_name": real[0]["Name"]}, "domain": "devices"}))

    ports = {str(p.get("Name")): p for p in state.get("ports", [])}
    for p in real[:3]:
        name = str(p.get("Name"))
        port = ports.get(str(p.get("PortName")), {"Name": p.get("PortName")})
        err = int(p.get("DetectedErrorState") or 0)
        status = int(p.get("PrinterStatus") or 0)

        # --- printer: what it reports
        if err in _PRINTER_ERRORS:
            text, steps = _PRINTER_ERRORS[err]
            f.append(_finding(f"printer-{err}-{name}", "printer", f"{name} {text}",
                              severity="info" if err in (3, 5) else "problem", steps=steps))
        # --- computer: Windows marked it offline
        if p.get("WorkOffline"):
            f.append(_finding(f"offline-flag-{name}", "computer", f"{name} is set to 'Use Printer Offline' in Windows",
                              fix={"tool": "set_printer_online", "args": {"printer_name": name}, "domain": "devices"},
                              steps=["Settings > Printers & scanners > your printer > Printer properties > Advanced, or open the print queue and untick Printer > Use Printer Offline."]))
        elif status == 7 and err not in _PRINTER_ERRORS:
            f.append(_finding(f"printer-offline-{name}", "printer", f"{name} is reported offline", steps=_PRINTER_ERRORS[9][1]))

        # --- network / USB: can the printer be reached?
        target = _host_of_port(port)
        pname = str(p.get("PortName") or "")
        if target:
            host, number = target
            if not probe(host, number):
                f.append(_finding(f"unreachable-{name}", "network", f"{name} does not answer at {host}: it is off, asleep, or not on your network",
                                  steps=[s.format(host=host) for s in _NETWORK_STEPS]))
        elif pname.upper().startswith(("USB", "DOT4")) and (p.get("WorkOffline") or status == 7):
            f.append(_finding(f"usb-{name}", "network", f"{name} is on USB but Windows cannot talk to it", steps=_USB_STEPS))

        # --- computer: driver
        driver = str(p.get("DriverName") or "")
        if not driver or driver.lower() == "unknown":
            f.append(_finding(f"driver-{name}", "computer", f"{name} has no working driver installed",
                              steps=["Install the driver from the printer maker's website, or ask IT to add the printer from the company print server."],
                              needs_it=True))

    # --- computer: stuck or failed jobs
    bad = re.compile(r"error|offline|paperout|userintervention|blocked|paused|deleting|retained", re.IGNORECASE)
    stuck: dict[str, int] = {}
    for j in state.get("jobs", []):
        st = str(j.get("status") or "")
        if bad.search(st) or (int(j.get("age_min") or 0) >= 10 and re.search(r"spool|print", st, re.IGNORECASE)):
            stuck[str(j.get("PrinterName"))] = stuck.get(str(j.get("PrinterName")), 0) + 1
    for printer, n in stuck.items():
        f.append(_finding(f"stuck-{printer}", "computer", f"{n} document{'s' if n != 1 else ''} stuck or failed in the queue of {printer}",
                          fix={"tool": "clear_print_queue", "args": {"printer_name": printer}, "domain": "devices"}))

    # --- computer: recent print errors (evidence)
    if state.get("events"):
        first = str(state["events"][0].get("msg") or "").replace("\n", " ")[:110]
        f.append(_finding("events", "computer", f"Windows logged {len(state['events'])} print error(s) in the last 24 hours, for example: {first}",
                          severity="info"))

    # --- file
    if file_info:
        for problem in file_info["problems"]:
            steps = (["Tell me the exact file name, or put the file in Documents, Desktop or Downloads, and I will check the file itself."]
                     if problem.startswith("I could not find") else _FILE_STEPS)
            f.append(_finding("file-" + re.sub(r"\W+", "-", problem)[:30], "file", f"{file_info['name']}: {problem}", steps=steps))
    return f


_LAST: dict = {}


def last() -> dict:
    """Full result of the most recent diagnosis (the tool's reply to the model is shortened to fit its size limit)."""
    return _LAST


def diagnose(file_name: str = "") -> dict:
    state = collect_state()
    file_info = check_file(file_name) if file_name else None
    findings = analyse(state, file_info)
    result = {"state": state, "findings": findings, "file": file_info, "file_name": file_name}
    _LAST.clear()
    _LAST.update(result)
    return result


def problem_ids(findings: list[dict]) -> set[str]:
    return {f["id"] for f in findings if f["severity"] == "problem"}


@tool("devices", R0,
      "Troubleshoot printing end to end in one read-only pass: the print service, printers, default printer, stuck "
      "jobs, driver, whether the printer can be reached, recent print errors, and (if a file name is given) the "
      "document itself. Findings are grouped by layer: computer, file, printer, network.",
      params=(Param("file", "str", "name or path of the document that will not print, if known", required=False, max_len=200),))
def diagnose_printing(file: str = "") -> dict:
    result = diagnose(file or "")
    findings = result["findings"]
    problems = [x for x in findings if x["severity"] == "problem"]
    return {"ok": True, "printers": [p.get("Name") for p in result["state"]["printers"]][:5],
            "spooler": result["state"]["spooler"], "problems": len(problems),
            "findings": [{"layer": x["layer"], "what": x["what"][:110]} for x in findings[:7]],
            "note": "No problem found on this computer." if not problems else ""}


# ---------------------------------------------------------------------------
# Fixes (the computer side)
# ---------------------------------------------------------------------------
def _printer_names() -> list[str]:
    try:
        return [p["Name"] for p in collect_state()["printers"]]
    except Exception:
        return []


def _run_fix(key: str, arg: str | None = None) -> dict:
    try:
        powershell.run_powershell(key, timeout=25, arg=arg)
        return {"ok": True}
    except powershell.CommandError as e:
        msg = str(e)
        if re.search(r"access is denied|cannot open|requires elevation|administrator|permission", msg, re.IGNORECASE):
            return {"ok": False, "needs_admin": True,
                    "error": "Windows needs administrator rights for this. Ask IT to do it."}
        return {"ok": False, "error": msg[:200]}


@tool("devices", R2, "Restart the Windows Print Spooler service (needs administrator rights). Clears most 'print service' hangs.",
      change_note="The print service restarts. Every waiting print job on this computer is cancelled and must be printed again.",
      summary="Restart the Print Spooler service")
def restart_print_spooler() -> dict:
    if not is_admin():
        return {"ok": False, "needs_admin": True, "error": "Restarting the print service needs administrator rights. Ask IT."}
    return _run_fix("restart_spooler") | {"restarted": True}


@tool("devices", R1, "Make one printer the default printer.",
      params=(Param("printer_name", "str", "exact printer name from list_printers", choices=_printer_names),),
      change_note="Documents will go to this printer by default. You can change it back in Settings.",
      summary="Make {printer_name} the default printer")
def set_default_printer(printer_name: str) -> dict:
    return _run_fix("set_default_printer", printer_name) | {"printer": printer_name}


@tool("devices", R1, "Switch a printer back online (clears the 'Use Printer Offline' setting).",
      params=(Param("printer_name", "str", "exact printer name from list_printers", choices=_printer_names),),
      change_note="Windows will send documents to this printer again instead of holding them.",
      summary="Bring {printer_name} back online")
def set_printer_online(printer_name: str) -> dict:
    return _run_fix("set_printer_online", printer_name) | {"printer": printer_name}


@tool("devices", R1, "Send the Windows test page to one printer to confirm it prints. Uses one sheet of paper.",
      params=(Param("printer_name", "str", "exact printer name from list_printers", choices=_printer_names),),
      change_note="One test page is sent to the printer (one sheet of paper).",
      summary="Print a test page on {printer_name}")
def print_test_page(printer_name: str) -> dict:
    return _run_fix("print_test_page", printer_name) | {"printer": printer_name}
