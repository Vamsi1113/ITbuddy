"""Network tools: check_network_connection, check_dns_resolution, get_network_config, flush_dns_cache."""
from __future__ import annotations

import ipaddress
import socket
import time
import urllib.error
import urllib.request

from appconfig import cfg
from tools import powershell
from tools.registry import R0, R1, Param, tool


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


@tool("network", R0, "Is the internet connection up? Pings the gateway and a public address and opens one website.")
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


@tool("network", R0, "Do DNS lookups work? Resolves a short list of test hostnames.")
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


@tool("network", R0, "Adapter name, IP address, gateway, DNS servers.")
def get_network_config() -> dict:
    data = powershell.run_powershell_json("network_config")
    if data is None:
        return {"ok": True, "adapters": [], "note": "no connected network adapter"}
    if isinstance(data, dict):
        data = [data]
    return {"ok": True, "adapters": data[:3]}


@tool("network", R1, "Flush the DNS cache.",
      change_note="The saved list of website addresses (DNS cache) on this computer will be cleared, so Windows "
                  "looks them up again. No files or settings are changed.")
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


import re as _re  # noqa: E402

powershell.SCRIPTS.update({
    "vpn_connections": (
        "Get-VpnConnection -ErrorAction SilentlyContinue | Select-Object Name,ServerAddress,"
        "@{n='status';e={\"$($_.ConnectionStatus)\"}} | ConvertTo-Json -Compress"
    ),
})

_HOST_RE = _re.compile(r"^(?=.{1,253}$)[A-Za-z0-9]([A-Za-z0-9-]{0,62})(\.[A-Za-z0-9]([A-Za-z0-9-]{0,62}))*$")


def _clean_host(host: str) -> str | None:
    host = (host or "").strip().lower()
    for prefix in ("https://", "http://"):
        if host.startswith(prefix):
            host = host[len(prefix):]
    host = host.split("/")[0].split(":")[0]
    return host if _HOST_RE.match(host) else None


def _active_connections() -> list[str]:
    """The network connections that are up right now, so "no Wi-Fi" can say what the computer uses instead."""
    try:
        import psutil
        out = []
        for name, st in psutil.net_if_stats().items():
            low = name.lower()
            if not st.isup or "loopback" in low or low.startswith(("vethernet", "bluetooth")):
                continue
            kind = "Wi-Fi" if ("wi-fi" in low or "wlan" in low or "wireless" in low) else \
                   "VPN" if ("vpn" in low or "tap" in low or "tun" in low) else "wired (Ethernet)"
            speed = f", {st.speed} Mbps" if 0 < st.speed < 4294 else ""     # 4294 = "unknown" on virtual adapters
            out.append(f"{name}: {kind}{speed}")
        return out or ["no active network connection found"]
    except Exception:
        return []


@tool("network", R0, "Wi-Fi details: is Wi-Fi connected, network name, signal strength, band, channel, speed; "
                     "when there is no Wi-Fi, which connection the computer uses instead (for example wired Ethernet).")
def get_wifi_info() -> dict:
    proc = powershell.run_executable("wlan_interfaces")
    info = {}
    for line in (proc.stdout or "").splitlines():
        if " : " in line:
            key, value = line.split(" : ", 1)
            info[key.strip().lower()] = value.strip()
    if "ssid" not in info and "state" not in info:
        return {"ok": True, "wifi_connected": False,
                "wifi": "no Wi-Fi: there is no wireless adapter, or the Wi-Fi service is not running",
                "connected_through": _active_connections()}
    wanted = ("name", "state", "ssid", "radio type", "band", "channel", "signal", "receive rate (mbps)",
              "transmit rate (mbps)", "authentication")
    return {"ok": True, **{k.replace(" ", "_"): info[k] for k in wanted if k in info}}


@tool("network", R0, "Can this computer reach a server on a TCP port (for example mail.company.com 443)?",
      params=(Param("host", "str", "hostname or IP, no path"), Param("port", "int", "1-65535")))
def check_port(host: str, port: int) -> dict:
    clean = _clean_host(host)
    if not clean or not (1 <= int(port) <= 65535):
        return {"ok": False, "error": "host must be a hostname or IP and port must be 1-65535"}
    start = time.monotonic()
    try:
        with socket.create_connection((clean, int(port)), timeout=6):
            return {"ok": True, "host": clean, "port": port, "reachable": True,
                    "ms": round((time.monotonic() - start) * 1000)}
    except socket.gaierror:
        return {"ok": True, "host": clean, "port": port, "reachable": False,
                "reason": "the name could not be resolved (DNS)"}
    except OSError as e:
        return {"ok": True, "host": clean, "port": port, "reachable": False, "reason": str(e)[:100]}


@tool("network", R0, "Does one website open? Use for 'site X does not load'.",
      params=(Param("host", "str", "hostname such as www.example.com"),))
def check_website(host: str) -> dict:
    clean = _clean_host(host)
    if not clean:
        return {"ok": False, "error": "host must be a hostname such as www.example.com"}
    return {"ok": True, **_website_check(f"https://{clean}")}


@tool("network", R0, "Security certificate of a website: valid or not, issuer, days until it expires.",
      params=(Param("host", "str", "hostname such as www.example.com"),))
def check_ssl_certificate(host: str) -> dict:
    import ssl
    from datetime import datetime, timezone

    clean = _clean_host(host)
    if not clean:
        return {"ok": False, "error": "host must be a hostname such as www.example.com"}
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((clean, 443), timeout=6) as sock:
            with ctx.wrap_socket(sock, server_hostname=clean) as tls:
                cert = tls.getpeercert()
    except ssl.SSLCertVerificationError as e:
        return {"ok": True, "host": clean, "valid": False, "problem": (e.verify_message or str(e))[:150]}
    except OSError as e:
        return {"ok": False, "error": f"Could not connect to {clean}:443 ({str(e)[:100]})"}
    expires = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    issuer = dict(x[0] for x in cert.get("issuer", ())).get("organizationName")
    return {"ok": True, "host": clean, "valid": True, "issuer": issuer,
            "expires": expires.strftime("%Y-%m-%d"), "days_left": (expires - datetime.now(timezone.utc)).days}


@tool("network", R0, "Proxy settings of this user: proxy on or off, proxy server, automatic configuration script.")
def get_proxy_settings() -> dict:
    import winreg
    out = {"ok": True, "proxy_enabled": False, "proxy_server": None, "auto_config_url": None}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as key:
            for name, field in (("ProxyEnable", "proxy_enabled"), ("ProxyServer", "proxy_server"),
                                ("AutoConfigURL", "auto_config_url")):
                try:
                    value = winreg.QueryValueEx(key, name)[0]
                    out[field] = bool(value) if field == "proxy_enabled" else value
                except OSError:
                    pass
    except OSError:
        pass
    return out


@tool("network", R0, "VPN connections set up in Windows and whether each is connected.")
def get_vpn_status() -> dict:
    rows = powershell.run_powershell_list("vpn_connections")
    if not rows:
        return {"ok": True, "vpn_connections": [], "note": "No Windows VPN connection is set up. "
                "A third-party VPN app (for example GlobalProtect or AnyConnect) is not visible here."}
    return {"ok": True, "vpn_connections": rows}


@tool("network", R0, "Is the computer clock correct? Compares it with an internet time source. "
                     "A wrong clock breaks sign-in, MFA and secure websites.")
def check_clock() -> dict:
    from datetime import datetime, timezone
    from email.utils import parsedate_to_datetime

    url = cfg("network", "test_website", default="https://www.microsoft.com")
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "IT-Buddy/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            server = parsedate_to_datetime(resp.headers["Date"])
    except Exception as e:
        return {"ok": False, "error": f"Could not read the internet time ({type(e).__name__})"}
    skew = (datetime.now(timezone.utc) - server).total_seconds()
    return {"ok": True, "local_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timezone": time.tzname[time.localtime().tm_isdst > 0],
            "difference_seconds": round(skew), "clock_ok": abs(skew) < 120}


@tool("network", R0, "Connection quality for calls (Teams/Zoom): average delay and jitter to three servers.")
def check_connection_quality() -> dict:
    hosts = (cfg("network", "test_hostnames", default=[]) or [])[:3]
    rows = []
    for host in hosts:
        times = []
        for _ in range(4):
            start = time.monotonic()
            try:
                with socket.create_connection((host, 443), timeout=3):
                    times.append((time.monotonic() - start) * 1000)
            except OSError:
                pass
        if times:
            avg = sum(times) / len(times)
            jitter = sum(abs(t - avg) for t in times) / len(times)
            rows.append({"host": host, "avg_ms": round(avg), "jitter_ms": round(jitter), "failed": 4 - len(times)})
        else:
            rows.append({"host": host, "reachable": False})
    good = [r for r in rows if "avg_ms" in r]
    verdict = ("no connection" if not good else
               "good for calls" if all(r["avg_ms"] < 150 and r["jitter_ms"] < 30 and not r["failed"] for r in good)
               else "poor: calls may break up")
    return {"ok": True, "results": rows, "verdict": verdict}
