"""Who and where the user is in the organisation: the ODC (office / delivery centre) this PC is in, and the user's
security groups. SOP search uses these so it only returns the rules that apply to this user.

How the ODC is found, in order (the first that matches wins):
  1. `organisation.odc_override` in config.yaml, or the ITBUDDY_ODC environment variable (testing, kiosks)
  2. an IPv4 address of this PC inside one of the ODC's subnets
  3. the computer name starting with one of the ODC's prefixes
If nothing matches, the ODC is unknown and Tobi says so instead of guessing. (Phase 2 adds the Active Directory site
and asking the user once.)

The groups come from the Windows sign-in token (`whoami /groups`): no admin rights and no network call needed.
"""
from __future__ import annotations

import ipaddress
import os
import socket
import subprocess
import time

from appconfig import cfg
from tools.registry import R0, tool

_GROUP_CACHE: dict = {"at": 0.0, "groups": []}


def odc_catalogue() -> dict:
    return cfg("organisation", "odcs", default={}) or {}


def _local_ipv4() -> list[ipaddress.IPv4Address]:
    out = []
    try:
        import psutil
        for name, addrs in psutil.net_if_addrs().items():
            stats = psutil.net_if_stats().get(name)
            if stats is not None and not stats.isup:
                continue
            for a in addrs:
                if a.family == socket.AF_INET and not a.address.startswith(("127.", "169.254.")):
                    out.append(ipaddress.IPv4Address(a.address))
    except Exception:
        pass
    return out


def detect_odc() -> dict:
    """{"odc": id or "", "name", "how"}. Never raises."""
    odcs = odc_catalogue()
    override = os.environ.get("ITBUDDY_ODC") or cfg("organisation", "odc_override", default="") or ""
    if override:
        return {"odc": override, "name": (odcs.get(override) or {}).get("name", override), "how": "set in configuration"}
    ips = _local_ipv4()
    for odc, info in odcs.items():
        for net in (info or {}).get("subnets", []) or []:
            try:
                network = ipaddress.ip_network(str(net), strict=False)
            except ValueError:
                continue
            if any(ip in network for ip in ips):
                return {"odc": odc, "name": info.get("name", odc), "how": f"network {network}"}
    host = (os.environ.get("COMPUTERNAME") or socket.gethostname() or "").upper()
    for odc, info in odcs.items():
        for prefix in (info or {}).get("hostname_prefixes", []) or []:
            if prefix and host.startswith(str(prefix).upper()):
                return {"odc": odc, "name": info.get("name", odc), "how": f"computer name starts with {prefix}"}
    return {"odc": "", "name": "", "how": "no ODC matched this PC's network or name"}


def user_groups(max_age: float = 600) -> list[str]:
    """Security group names of the signed-in user (cached for 10 minutes). Empty list if they cannot be read."""
    if time.time() - _GROUP_CACHE["at"] < max_age and _GROUP_CACHE["groups"]:
        return list(_GROUP_CACHE["groups"])
    groups: list[str] = []
    try:
        proc = subprocess.run(["whoami", "/groups", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=10,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for line in (proc.stdout or "").splitlines():
            name = line.split('","')[0].strip('"').strip()
            if name:
                groups.append(name.split("\\")[-1])           # "CONTOSO\HYD2-All-Staff" -> "HYD2-All-Staff"
    except Exception:
        pass
    _GROUP_CACHE.update(at=time.time(), groups=groups)
    return list(groups)


@tool("account", R0, "Which ODC (office) this computer is in, and how many security groups the user is in. "
      "Used to apply the right SOPs.")
def get_my_org_context() -> dict:
    odc = detect_odc()
    groups = user_groups()
    return {"ok": True, "odc": odc["odc"] or "unknown", "odc_name": odc["name"], "detected_by": odc["how"],
            "known_odcs": sorted(odc_catalogue()), "group_count": len(groups)}
