"""Network tools: check_network_connection, check_dns_resolution, get_network_config, flush_dns_cache."""
from __future__ import annotations

import ipaddress
import socket
import time
import urllib.error
import urllib.request

from appconfig import cfg
from tools import powershell


def _valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _website_check(url: str) -> dict:
    start = time.monotonic()
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "IT-Buddy/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            status = resp.status
        return {"url": url, "opens": True, "status": status,
                "ms": round((time.monotonic() - start) * 1000)}
    except urllib.error.HTTPError as e:  # the server answered, so the site is reachable
        return {"url": url, "opens": e.code < 500, "status": e.code,
                "ms": round((time.monotonic() - start) * 1000)}
    except Exception as e:
        return {"url": url, "opens": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}


def check_network_connection() -> dict:
    try:
        gateway = powershell.run_powershell("default_gateway").splitlines()
        gateway = gateway[0].strip() if gateway else ""
    except Exception:
        gateway = ""
    results = {"ok": True}
    if gateway and _valid_ip(gateway):
        results["gateway"] = powershell.ping(gateway)
    else:
        results["gateway"] = {"host": None, "reachable": False, "note": "no default gateway found"}
    public = cfg("network", "public_ping_host", default="1.1.1.1")
    results["internet_ip"] = powershell.ping(public) if _valid_ip(public) else {"error": "invalid host in config"}
    results["website"] = _website_check(cfg("network", "test_website", default="https://www.microsoft.com"))
    pings_ok = results["gateway"].get("reachable") or results["internet_ip"].get("reachable")
    web_ok = results["website"].get("opens")
    results["internet_connected"] = bool(pings_ok or web_ok)
    if web_ok and not pings_ok:
        # Many networks block ping. A working website proves the connection is up,
        # so do not report the gateway as down.
        results.pop("gateway")
        results.pop("internet_ip")
        results["ping"] = "not available: this network blocks ping, which is normal and not a fault"
    return results


def check_dns_resolution() -> dict:
    hosts = cfg("network", "test_hostnames", default=[]) or []
    rows = []
    for host in hosts[:5]:
        start = time.monotonic()
        try:
            infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
            ips = sorted({i[4][0] for i in infos})[:2]
            rows.append({"host": host, "resolves": True, "ips": ips,
                         "ms": round((time.monotonic() - start) * 1000)})
        except socket.gaierror as e:
            rows.append({"host": host, "resolves": False, "error": str(e)[:80]})
    ok_count = sum(r["resolves"] for r in rows)
    return {"ok": True, "resolved": f"{ok_count}/{len(rows)}", "all_resolve": ok_count == len(rows),
            "results": rows}


def get_network_config() -> dict:
    data = powershell.run_powershell_json("network_config")
    if data is None:
        return {"ok": True, "adapters": [], "note": "no connected network adapter"}
    if isinstance(data, dict):
        data = [data]
    return {"ok": True, "adapters": data[:3]}


def flush_dns_cache() -> dict:
    proc = powershell.run_executable("flush_dns")
    out = (proc.stdout or "").strip()
    if proc.returncode == 0 and "success" in out.lower():
        return {"ok": True, "method": "ipconfig /flushdns", "output": out[-200:]}
    # ipconfig /flushdns needs an elevated prompt on some Windows builds.
    # Clear-DnsClientCache does the same job and works for a standard user.
    try:
        powershell.run_powershell("clear_dns_cache")
        return {"ok": True, "method": "Clear-DnsClientCache", "output": "DNS client cache cleared"}
    except Exception as e:
        return {"ok": False, "error": f"ipconfig: {out[-120:]} | Clear-DnsClientCache: {str(e)[:120]}"}
