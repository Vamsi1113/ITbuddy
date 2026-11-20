"""Performance and system tools."""
from __future__ import annotations

import os
import time
import winreg

import psutil

from appconfig import cfg
from tools import powershell
from tools.registry import R0, R1, Param, tool

_MB = 1024 * 1024
_GB = 1024 * _MB

powershell.SCRIPTS.update({
    "sys_info": (
        "$cs=Get-CimInstance Win32_ComputerSystem; $os=Get-CimInstance Win32_OperatingSystem; $b=Get-CimInstance Win32_BIOS; "
        "[pscustomobject]@{computer_name=$cs.Name; manufacturer=$cs.Manufacturer; model=$cs.Model; serial=$b.SerialNumber; "
        "os=$os.Caption; version=$os.Version; build=$os.BuildNumber; architecture=$os.OSArchitecture; "
        "last_boot=$os.LastBootUpTime.ToString('yyyy-MM-dd HH:mm'); domain=$cs.Domain; part_of_domain=$cs.PartOfDomain; "
        "ram_gb=[math]::Round($cs.TotalPhysicalMemory/1GB,1)} | ConvertTo-Json -Compress"
    ),
    "startup_items": (
        "Get-CimInstance Win32_StartupCommand | Select-Object -First 15 Name,Command,Location | ConvertTo-Json -Compress"
    ),
    "stopped_services": (
        "Get-Service | Where-Object { $_.StartType -eq 'Automatic' -and $_.Status -ne 'Running' } | "
        "Select-Object -First 12 Name,DisplayName,@{n='status';e={$_.Status.ToString()}} | ConvertTo-Json -Compress"
    ),
})


def _protected_names() -> set[str]:
    return {n.lower() for n in (cfg("performance", "protected_processes", default=[]) or [])}


def _own_process_tree() -> set[int]:
    """This app's own process and its parents are never closed."""
    pids = set()
    try:
        p = psutil.Process(os.getpid())
        while p is not None:
            pids.add(p.pid)
            p = p.parent()
    except psutil.Error:
        pass
    return pids


def protection_reason(pid: int) -> str | None:
    """Return why a process must not be closed, or None if it is a closable user process."""
    if pid in (0, 4):
        return "it is a core Windows process"
    if pid in _own_process_tree():
        return "it is part of Tobi itself"
    try:
        proc = psutil.Process(pid)
        name = proc.name()
    except psutil.NoSuchProcess:
        return "no process with that ID is running"
    except psutil.AccessDenied:
        return "it belongs to the system (access denied)"
    if name.lower() in _protected_names():
        return f"'{name}' is on the protected process list"
    try:
        owner = proc.username()
        me = psutil.Process(os.getpid()).username()
    except psutil.AccessDenied:
        return "it belongs to the system (access denied)"
    if not owner or owner.lower() != me.lower():
        return f"it runs as another user ({owner}), not as you"
    return None


@tool("performance", R0, "CPU %, RAM %, uptime right now. Use for a slow computer.")
def get_system_health() -> dict:
    vm = psutil.virtual_memory()
    uptime_s = time.time() - psutil.boot_time()
    return {
        "ok": True,
        "cpu_percent": psutil.cpu_percent(interval=1.0),
        "cpu_cores": psutil.cpu_count(logical=True),
        "ram_percent": vm.percent,
        "ram_used_gb": round(vm.used / _GB, 1),
        "ram_total_gb": round(vm.total / _GB, 1),
        "ram_available_gb": round(vm.available / _GB, 1),
        "uptime_hours": round(uptime_s / 3600, 1),
    }


@tool("performance", R0, "Top 5 processes by memory and by CPU, and the largest process that may be closed.")
def get_running_processes() -> dict:
    procs = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            p.cpu_percent(None)  # prime the CPU counter
            procs.append(p)
        except psutil.Error:
            pass
    time.sleep(1.0)
    cores = psutil.cpu_count(logical=True) or 1
    rows = []
    for p in procs:
        try:
            with p.oneshot():
                rows.append({
                    "pid": p.pid,
                    "name": p.info["name"],
                    "memory_mb": round(p.memory_info().rss / _MB),
                    "cpu_percent": round(p.cpu_percent(None) / cores, 1),
                })
        except psutil.Error:
            pass
    rows = [r for r in rows if r["pid"] not in (0, 4)]
    by_mem = sorted(rows, key=lambda r: r["memory_mb"], reverse=True)[:5]
    by_cpu = sorted(rows, key=lambda r: r["cpu_percent"], reverse=True)[:5]
    for r in by_mem + by_cpu:
        r["closable"] = protection_reason(r["pid"]) is None
    largest_closable = None
    for r in sorted(rows, key=lambda r: r["memory_mb"], reverse=True)[:40]:
        if protection_reason(r["pid"]) is None:
            largest_closable = {k: r[k] for k in ("pid", "name", "memory_mb", "cpu_percent")}
            break
    return {
        "ok": True,
        "top_by_memory": by_mem,
        "top_by_cpu": by_cpu,
        "largest_closable_process": largest_closable,
    }


@tool("performance", R1, "Close ONE user process by pid. Protected system processes are refused.",
      params=(Param("pid", "int", "pid of largest_closable_process from get_running_processes"),),
      change_note="The process will be closed. Unsaved work in that app will be lost.")
def close_process(pid: int) -> dict:
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return {"ok": False, "error": f"pid must be a positive integer, got {pid!r}"}
    reason = protection_reason(pid)
    if reason:
        return {"ok": False, "error": f"Refused to close process {pid}: {reason}"}
    proc = psutil.Process(pid)
    name = proc.name()
    mem_mb = round(proc.memory_info().rss / _MB)
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except psutil.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    return {"ok": True, "closed_pid": pid, "name": name, "memory_released_mb": mem_mb,
            "still_running": psutil.pid_exists(pid)}


@tool("performance", R0, "Computer name, model, serial number, Windows version and build, last boot time, domain.")
def get_system_info() -> dict:
    return {"ok": True, **(powershell.run_powershell_json("sys_info") or {})}


def _key_exists(path: str) -> bool:
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path))
        return True
    except OSError:
        return False


@tool("performance", R0, "Is a restart pending (after updates or installs)? Also how long since the last restart.")
def check_pending_reboot() -> dict:
    cbs = _key_exists(r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending")
    wu = _key_exists(r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired")
    uptime_days = round((time.time() - psutil.boot_time()) / 86400, 1)
    return {"ok": True, "restart_pending": cbs or wu, "pending_for_windows_update": wu,
            "pending_for_component_servicing": cbs, "days_since_last_restart": uptime_days,
            "advice": "A restart is recommended." if (cbs or wu or uptime_days > 7) else "No restart is needed."}


@tool("performance", R0, "Programs that start automatically when Windows starts (slow startup).")
def list_startup_items() -> dict:
    items = powershell.run_powershell_list("startup_items")
    return {"ok": True, "count": len(items),
            "items": [{"name": i.get("Name"), "command": (i.get("Command") or "")[:70]} for i in items]}


@tool("performance", R0, "Windows services that should be running automatically but are stopped.")
def list_stopped_services() -> dict:
    rows = powershell.run_powershell_list("stopped_services")
    return {"ok": True, "count": len(rows),
            "services": [{"name": r.get("Name"), "display_name": r.get("DisplayName"), "status": r.get("status")}
                         for r in rows]}


@tool("performance", R0, "Battery charge, whether it is plugged in, time left. Laptops only.")
def get_battery_status() -> dict:
    b = psutil.sensors_battery()
    if b is None:
        return {"ok": True, "battery": "none (desktop or virtual machine)"}
    left = None if b.secsleft in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN) else round(b.secsleft / 60)
    return {"ok": True, "percent": b.percent, "plugged_in": b.power_plugged, "minutes_left": left}
