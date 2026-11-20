"""Devices and peripherals: printers, audio, cameras, Bluetooth, monitors, devices with problems."""
from __future__ import annotations

from tools import powershell
from tools.registry import R0, R1, Param, tool

_CLASSES = ("AudioEndpoint", "Camera", "Bluetooth", "Monitor", "Keyboard", "Mouse", "USB", "Net", "Display",
            "Printer", "Biometric")

powershell.SCRIPTS.update({
    "printers": (
        "$d=(Get-CimInstance Win32_Printer -Filter 'Default=True').Name; Get-Printer | Select-Object Name,DriverName,"
        "PortName,@{n='status';e={\"$($_.PrinterStatus)\"}},@{n='default';e={$_.Name -eq $d}} | ConvertTo-Json -Compress"
    ),
    "printer_names": "Get-Printer | Select-Object -ExpandProperty Name | ConvertTo-Json -Compress",
    "print_jobs": (
        "Get-Printer | ForEach-Object { Get-PrintJob -PrinterName $_.Name -ErrorAction SilentlyContinue } | "
        "Select-Object -First 10 PrinterName,DocumentName,UserName,@{n='status';e={\"$($_.JobStatus)\"}} | "
        "ConvertTo-Json -Compress"
    ),
    "clear_print_jobs": (
        "$jobs=@(Get-PrintJob -PrinterName $env:ITB_ARG -ErrorAction Stop); $jobs | Remove-PrintJob -ErrorAction Stop; "
        "[pscustomobject]@{removed=$jobs.Count} | ConvertTo-Json -Compress"
    ),
    "problem_devices": (
        "Get-PnpDevice -PresentOnly | Where-Object { $_.Status -ne 'OK' -and $_.Status -ne 'Unknown' } | "
        "Select-Object -First 10 FriendlyName,Class,Status,@{n='problem';e={\"$($_.Problem)\"}} | ConvertTo-Json -Compress"
    ),
    "devices_by_class": (
        "Get-PnpDevice -PresentOnly -Class $env:ITB_ARG -ErrorAction SilentlyContinue | Select-Object -First 12 "
        "FriendlyName,Status | ConvertTo-Json -Compress"
    ),
})


def _printer_names() -> list[str]:
    try:
        data = powershell.run_powershell_json("printer_names")
    except Exception:
        return []
    if data is None:
        return []
    return data if isinstance(data, list) else [data]


@tool("devices", R0, "Printers installed on this computer, which one is the default, and their status.")
def list_printers() -> dict:
    rows = powershell.run_powershell_list("printers")
    return {"ok": True, "count": len(rows), "printers": rows[:8]}


@tool("devices", R0, "Print jobs waiting in the print queues (stuck documents).")
def get_print_queue() -> dict:
    rows = powershell.run_powershell_list("print_jobs")
    return {"ok": True, "waiting_jobs": len(rows), "jobs": rows}


@tool("devices", R0, "Devices that Windows reports a problem with (driver error, disabled, not started).")
def list_problem_devices() -> dict:
    rows = [r for r in powershell.run_powershell_list("problem_devices") if r.get("FriendlyName")]
    return {"ok": True, "count": len(rows), "devices": rows,
            "note": "No device problems found." if not rows else "Driver fixes need IT: choose the fix 'escalate'."}


@tool("devices", R0, "List connected devices of one kind and whether each is working. "
                     "AudioEndpoint = speakers, headsets and microphones.",
      params=(Param("device_class", "str", "kind of device", choices=_CLASSES),))
def list_devices(device_class: str) -> dict:
    rows = powershell.run_powershell_list("devices_by_class", arg=device_class)
    return {"ok": True, "device_class": device_class, "count": len(rows),
            "devices": [{"name": r.get("FriendlyName"), "status": r.get("Status")} for r in rows]}


@tool("devices", R1, "Delete all waiting print jobs of one printer (clears a stuck print queue).",
      params=(Param("printer_name", "str", "exact printer name from list_printers", choices=_printer_names),),
      change_note="All documents waiting in that printer's queue will be cancelled. They must be printed again.",
      summary="Clear the print queue of {printer_name}")
def clear_print_queue(printer_name: str) -> dict:
    if printer_name not in _printer_names():
        return {"ok": False, "error": f"No printer named '{printer_name}'"}
    out = powershell.run_powershell_json("clear_print_jobs", arg=printer_name) or {}
    return {"ok": True, "printer": printer_name, "jobs_removed": out.get("removed", 0)}
