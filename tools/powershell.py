"""Safe wrapper for a fixed set of commands. The model can never pass a command string."""
from __future__ import annotations

import json
import subprocess

# Each key maps to one fixed command. Nothing is built from user or model input.
_POWERSHELL = {
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
}

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class CommandError(Exception):
    pass


def run_powershell(key: str, timeout: int = 25) -> str:
    if key not in _POWERSHELL:
        raise CommandError(f"Unknown PowerShell command key '{key}'")
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-Command", _POWERSHELL[key]],
        capture_output=True, text=True, timeout=timeout, creationflags=_NO_WINDOW,
    )
    if proc.returncode != 0:
        raise CommandError((proc.stderr or proc.stdout).strip()[:300])
    return proc.stdout.strip()


def run_powershell_json(key: str, timeout: int = 25):
    out = run_powershell(key, timeout)
    if not out:
        return None
    return json.loads(out)


def run_executable(key: str, timeout: int = 25) -> subprocess.CompletedProcess:
    if key not in _EXECUTABLES:
        raise CommandError(f"Unknown command key '{key}'")
    return subprocess.run(_EXECUTABLES[key], capture_output=True, text=True,
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
