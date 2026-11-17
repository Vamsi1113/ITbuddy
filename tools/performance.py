"""Performance tools: get_system_health, get_running_processes, close_process."""
from __future__ import annotations

import os
import time

import psutil

from appconfig import cfg

_MB = 1024 * 1024
_GB = 1024 * _MB


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
        return "it is part of IT Buddy itself"
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
