"""Safe wrapper for a fixed set of commands. The model can never pass a command string.

Tool modules register their fixed scripts in SCRIPTS at import time. A script may read ONE
validated argument from the environment variable ITB_ARG, so no text is ever spliced into a command.
"""
from __future__ import annotations

import json
import os
import subprocess

SCRIPTS: dict[str, str] = {
    "network_config": (
        "Get-NetIPConfiguration | Where-Object { $_.NetAdapter.Status -eq 'Up' } | "
        "ForEach-Object { [pscustomobject]@{ "
        "adapter = $_.InterfaceAlias; "
        "ipv4 = @($_.IPv4Address | ForEach-Object { $_.IPAddress }); "
        "gateway = @($_.IPv4DefaultGateway | ForEach-Object { $_.NextHop }); "
        "dns_servers = @($_.DNSServer | Where-Object { $_.AddressFamily -eq 2 } | ForEach-Object { $_.ServerAddresses } | Select-Object -Unique) } } | "
        "ConvertTo-Json -Depth 3 -Compress"
    ),
    "clear_dns_cache": "Clear-DnsClientCache -ErrorAction Stop",
    "default_gateway": (
        "Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | "
        "Sort-Object RouteMetric | Select-Object -First 1 -ExpandProperty NextHop"
    ),
}

_EXECUTABLES = {
    "flush_dns": ["ipconfig", "/flushdns"],
    "wlan_interfaces": ["netsh", "wlan", "show", "interfaces"],
    "active_power_plan": ["powercfg", "/getactivescheme"],
    "whoami_groups": ["whoami", "/groups", "/fo", "csv", "/nh"],
    "gpupdate_user": ["gpupdate", "/target:user", "/wait:20"],
}

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class CommandError(Exception):
    pass


def run_powershell(key: str, timeout: int = 25, arg: str | None = None) -> str:
    if key not in SCRIPTS:
        raise CommandError(f"Unknown PowerShell command key '{key}'")
    env = os.environ.copy()
    env["ITB_ARG"] = "" if arg is None else str(arg)
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-Command", "$ProgressPreference='SilentlyContinue'; " + SCRIPTS[key]],
        capture_output=True, text=True, timeout=timeout, creationflags=_NO_WINDOW, env=env,
    )
    # A query that finds nothing (for example no matching events) exits with 1 and no error text.
    if proc.returncode != 0 and (proc.stderr or "").strip():
        raise CommandError(proc.stderr.strip()[:300])
    return proc.stdout.strip()


def run_powershell_json(key: str, timeout: int = 25, arg: str | None = None):
    out = run_powershell(key, timeout, arg)
    if not out:
        return None
    return json.loads(out)


def run_powershell_list(key: str, timeout: int = 25, arg: str | None = None) -> list:
    """Like run_powershell_json, but always a list (PowerShell returns a bare object for one item)."""
    data = run_powershell_json(key, timeout, arg)
    if data is None:
        return []
    return data if isinstance(data, list) else [data]


def run_executable(key: str, timeout: int = 25, extra: list[str] | None = None) -> subprocess.CompletedProcess:
    """Run a fixed executable. `extra` is for arguments the caller has already validated."""
    if key not in _EXECUTABLES:
        raise CommandError(f"Unknown command key '{key}'")
    return subprocess.run(_EXECUTABLES[key] + list(extra or []), capture_output=True, text=True,
                          timeout=timeout, creationflags=_NO_WINDOW)


def ping(host: str, count: int = 2, timeout: int = 15) -> dict:
    """Ping one host. host is validated by the caller (IP or hostname from config)."""
    proc = subprocess.run(["ping", "-n", str(count), "-w", "1000", host],
                          capture_output=True, text=True, timeout=timeout, creationflags=_NO_WINDOW)
    out = proc.stdout
    received = 0
    avg_ms = None
    for line in out.splitlines():
        line_l = line.lower()
        if "received =" in line_l:
            try:
                received = int(line_l.split("received =")[1].split(",")[0].strip())
            except ValueError:
                pass
        if "average =" in line_l:
            try:
                avg_ms = int(line_l.split("average =")[1].strip().rstrip("ms").strip())
            except ValueError:
                pass
    return {"host": host, "reachable": received > 0, "replies": f"{received}/{count}", "avg_ms": avg_ms}
