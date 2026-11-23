"""Who and where the user is: the kind of computer Tobi runs on, the ODC (office / delivery centre), floor and seat,
the network the PC is on, and the user's security groups. SOP and printer/network guidance use this so the user only
sees what applies to THEM.

Kind of computer
  physical          a normal PC or laptop
  virtual_machine   a virtual machine (Hyper-V, VMware ...)
  avd               an Azure Virtual Desktop / Windows 365 / remote-desktop session: Tobi runs in the cloud, so the
                    PC's own network says nothing about where the user sits. Printers only appear when they are
                    redirected from the user's real PC or mapped by IT.

Where the user is (ODC, floor, seat), first match wins:
  1. a test override: ITBUDDY_ODC / organisation.odc_override
  2. what the user told Tobi ("I am in ODC B, seat 3-B-17"): saved in data/org_profile.json
  3. the network: the remote client's IP in a remote session when Windows exposes it, else this PC's IP, against
     the subnets of each ODC (and each floor) in config.yaml
  4. the seat table organisation/seats.csv (computer name or remote client name -> ODC, floor, seat)
  5. the computer name prefix, then the user's security groups (organisation.odcs.<id>.groups)
If nothing matches the ODC stays unknown and Tobi says so; it never guesses.
"""
from __future__ import annotations

import csv
import ctypes
import ipaddress
import json
import os
import re
import socket
import subprocess
import threading
import time
from ctypes import wintypes as wt
from pathlib import Path

from appconfig import ROOT, cfg, data_path
from tools.registry import R0, R1, Param, tool

_GROUP_CACHE: dict = {"at": 0.0, "groups": []}
_lock = threading.Lock()
PROFILE_FILE = ROOT / "data" / "org_profile.json"


# ------------------------------------------------------------------------------------------------ catalogue
def odc_catalogue() -> dict:
    return cfg("organisation", "odcs", default={}) or {}


def _profile_path() -> Path:
    return PROFILE_FILE


def load_profile() -> dict:
    try:
        return json.loads(_profile_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_profile(profile: dict) -> None:
    path = _profile_path()
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(profile, indent=1), encoding="utf-8")


# ------------------------------------------------------------------------------------------------ the computer
def _wts_query(info_class: int) -> bytes | None:
    try:
        sid = wt.DWORD()
        ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(sid))
        buf, size = ctypes.c_void_p(), wt.DWORD()
        if not ctypes.windll.wtsapi32.WTSQuerySessionInformationW(None, sid.value, info_class, ctypes.byref(buf),
                                                                  ctypes.byref(size)):
            return None
        data = ctypes.string_at(buf, size.value)
        ctypes.windll.wtsapi32.WTSFreeMemory(buf)
        return data
    except Exception:
        return None


def remote_session() -> dict:
    """{"remote": bool, "client_name": str, "client_ip": str}: is this a remote-desktop session, and who is the client?"""
    proto = _wts_query(16)                                        # WTSClientProtocolType: 0 console, 2 RDP
    remote = bool(proto and int.from_bytes(proto[:2], "little") == 2)
    name = os.environ.get("CLIENTNAME", "")
    raw = _wts_query(10)                                          # WTSClientName
    if raw:
        name = raw.decode("utf-16-le", "ignore").rstrip("\x00") or name
    ip = ""
    addr = _wts_query(14)                                         # WTSClientAddress: family + 20 address bytes
    if addr and len(addr) >= 8 and int.from_bytes(addr[:4], "little") == 2:
        ip = ".".join(str(b) for b in addr[6:10])
        if ip in ("0.0.0.0", ""):
            ip = ""
    session = os.environ.get("SESSIONNAME", "")
    return {"remote": remote or session.upper().startswith("RDP"), "client_name": name, "client_ip": ip}


def _is_avd_host() -> bool:
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\RDInfraAgent"))
        return True
    except OSError:
        pass
    try:
        out = subprocess.run(["sc", "query", "RDAgentBootLoader"], capture_output=True, text=True, timeout=8,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return "RUNNING" in out.upper() or "STOPPED" in out.upper()
    except Exception:
        return False


def _is_virtual_machine() -> bool:
    try:
        import psutil
        return any("hyper-v" in n.lower() or "vmware" in n.lower() or "virtualbox" in n.lower()
                   for n in psutil.net_if_addrs())
    except Exception:
        return False


def environment() -> dict:
    """The kind of computer: avd | remote_desktop | virtual_machine | physical, with the remote client when known."""
    session = remote_session()
    if _is_avd_host():
        kind = "avd"
    elif session["remote"]:
        kind = "remote_desktop"
    elif _is_virtual_machine():
        kind = "virtual_machine"
    else:
        kind = "physical"
    return {"kind": kind, "computer": os.environ.get("COMPUTERNAME") or socket.gethostname(),
            "client_name": session["client_name"], "client_ip": session["client_ip"], "remote": session["remote"]}


# ------------------------------------------------------------------------------------------------ the network
def _local_ipv4() -> list[ipaddress.IPv4Address]:
    out = []
    try:
        import psutil
        stats = psutil.net_if_stats()
        for name, addrs in psutil.net_if_addrs().items():
            if name in stats and not stats[name].isup:
                continue
            for a in addrs:
                if a.family == socket.AF_INET and not a.address.startswith(("127.", "169.254.")):
                    out.append(ipaddress.IPv4Address(a.address))
    except Exception:
        pass
    return out


def _run(cmd: list[str], timeout: int = 10) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout or ""
    except Exception:
        return ""


def wifi_state() -> dict:
    """{"connected": bool, "ssid": str, "signal": str}. Not connected when there is no Wi-Fi adapter or service."""
    out = _run(["netsh", "wlan", "show", "interfaces"])
    info = {}
    for line in out.splitlines():
        if " : " in line:
            k, v = line.split(" : ", 1)
            info[k.strip().lower()] = v.strip()
    ssid = info.get("ssid", "")
    return {"connected": info.get("state", "").lower() == "connected" and bool(ssid), "ssid": ssid,
            "signal": info.get("signal", "")}


_VPN_WORDS = re.compile(r"vpn|globalprotect|anyconnect|forti|pulse|openvpn|wireguard|ppp|tap-windows|nord|zscaler|cisco",
                        re.IGNORECASE)


def vpn_state() -> dict:
    """{"connected": bool, "adapters": [...]}: a VPN-looking network adapter that is up (works for any VPN client)."""
    names = []
    try:
        import psutil
        stats = psutil.net_if_stats()
        for name, st in stats.items():
            if st.isup and _VPN_WORDS.search(name):
                names.append(name)
    except Exception:
        pass
    return {"connected": bool(names), "adapters": names}


def network_state() -> dict:
    ips = [str(i) for i in _local_ipv4()]
    wifi = wifi_state()
    return {"ips": ips[:4], "wifi": wifi, "vpn": vpn_state()}


# ------------------------------------------------------------------------------------------------ seats
def seat_table() -> list[dict]:
    path = Path(cfg("organisation", "seats_file", default="organisation/seats.csv"))
    path = path if path.is_absolute() else ROOT / path
    try:
        with path.open(encoding="utf-8", newline="") as f:
            return [{k.strip().lower(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]
    except OSError:
        return []


def seat_for(*names: str) -> dict:
    wanted = {n.upper() for n in names if n}
    for row in seat_table():
        if row.get("computer", "").upper() in wanted:
            return row
    return {}


# ------------------------------------------------------------------------------------------------ user groups
def user_groups(max_age: float = 600) -> list[str]:
    """Security group names of the signed-in user (cached 10 minutes). Empty when they cannot be read."""
    if time.time() - _GROUP_CACHE["at"] < max_age and _GROUP_CACHE["groups"]:
        return list(_GROUP_CACHE["groups"])
    groups: list[str] = []
    for line in _run(["whoami", "/groups", "/fo", "csv", "/nh"]).splitlines():
        name = line.split('","')[0].strip('"').strip()
        if name:
            groups.append(name.split("\\")[-1])               # "CONTOSO\HYD2-All-Staff" -> "HYD2-All-Staff"
    _GROUP_CACHE.update(at=time.time(), groups=groups)
    return list(groups)


# ------------------------------------------------------------------------------------------------ where the user is
def _floor_from_ips(odc: str, ips: list) -> str:
    for floor, nets in ((odc_catalogue().get(odc) or {}).get("floors") or {}).items():
        for net in nets or []:
            try:
                network = ipaddress.ip_network(str(net), strict=False)
            except ValueError:
                continue
            if any(ip in network for ip in ips):
                return str(floor)
    return ""


def detect_location(env: dict | None = None) -> dict:
    """{"odc", "name", "floor", "seat", "how"}: where the user is. ODC "" = unknown. Never raises."""
    odcs = odc_catalogue()
    env = env or environment()

    def found(odc, how, floor="", seat=""):
        return {"odc": odc, "name": (odcs.get(odc) or {}).get("name", odc), "floor": floor, "seat": seat, "how": how}

    override = os.environ.get("ITBUDDY_ODC") or cfg("organisation", "odc_override", default="") or ""
    if override:
        return found(override, "set in configuration")
    told = load_profile()
    if told.get("odc"):
        return found(told["odc"], "you told Tobi", str(told.get("floor") or ""), str(told.get("seat") or ""))
    ips = []
    if env.get("client_ip"):
        try:
            ips.append(ipaddress.IPv4Address(env["client_ip"]))
        except ValueError:
            pass
    ips += _local_ipv4() if env["kind"] != "avd" else []      # an AVD session host's own IP says nothing about the user
    source = "the remote PC's network" if env.get("client_ip") else "this PC's network"
    for odc, info in odcs.items():
        for net in (info or {}).get("subnets", []) or []:
            try:
                network = ipaddress.ip_network(str(net), strict=False)
            except ValueError:
                continue
            if any(ip in network for ip in ips):
                return found(odc, f"{source} ({network})", _floor_from_ips(odc, ips), seat_for(env["computer"], env["client_name"]).get("seat", ""))
    row = seat_for(env["computer"], env["client_name"])
    if row.get("odc") in odcs:
        return found(row["odc"], f"seat table ({row.get('computer')})", row.get("floor", ""), row.get("seat", ""))
    host = (env["client_name"] or env["computer"]).upper()
    for odc, info in odcs.items():
        for prefix in (info or {}).get("hostname_prefixes", []) or []:
            if prefix and host.startswith(str(prefix).upper()):
                return found(odc, f"computer name starts with {prefix}")
    groups = {g.lower() for g in user_groups()}
    for odc, info in odcs.items():
        if any(str(g).lower() in groups for g in (info or {}).get("groups", []) or []):
            return found(odc, "your security group")
    return found("", "no ODC matched this PC's network, name or groups")


def detect_odc() -> dict:
    """Back-compat: {"odc", "name", "how"}."""
    loc = detect_location()
    return {"odc": loc["odc"], "name": loc["name"], "how": loc["how"]}


def full_context() -> dict:
    env = environment()
    loc = detect_location(env)
    return {"environment": env, "location": loc, "network": network_state(), "groups": user_groups()}


# ------------------------------------------------------------------------------------------------ tools
@tool("workplace", R0, "Where the user is and what kind of computer this is: ODC, floor, seat, whether this is a "
      "virtual desktop (AVD) or a physical PC, the Wi-Fi network and VPN state. Used to apply the right SOPs.")
def get_my_org_context() -> dict:
    ctx = full_context()
    env, loc, net = ctx["environment"], ctx["location"], ctx["network"]
    out = {"ok": True, "computer_type": env["kind"], "computer_name": env["computer"],
           "odc": loc["odc"] or "unknown", "odc_name": loc["name"], "floor": loc["floor"] or "unknown",
           "seat": loc["seat"] or "unknown", "located_by": loc["how"], "known_odcs": sorted(odc_catalogue()),
           "wifi": net["wifi"]["ssid"] if net["wifi"]["connected"] else "not connected to Wi-Fi",
           "vpn": "connected" if net["vpn"]["connected"] else "not connected", "group_count": len(ctx["groups"])}
    if env["client_name"]:
        out["remote_pc_name"] = env["client_name"]
    if env["kind"] == "avd":
        out["note"] = ("This is a virtual desktop (AVD): its own network is in the cloud, so it cannot show which "
                       "office the user sits in. Ask the user, or use set_my_location.")
    return out


@tool("workplace", R1, "Remember where the user sits (ODC, and optionally floor and seat), so the right SOPs, printers "
      "and network rules are used. Saved only on this PC.",
      params=(Param("odc", "str", "ODC id, for example HYD-ODC-2", max_len=40),
              Param("floor", "str", "floor number, optional", required=False, max_len=10),
              Param("seat", "str", "seat id, optional", required=False, max_len=20)),
      change_note="Tobi will remember this location on this PC (a small file in its data folder) and use it to pick "
                  "the SOPs, printers and network rules for you. You can change it any time.",
      summary="Remember that you sit in {odc}")
def set_my_location(odc: str, floor: str = "", seat: str = "") -> dict:
    catalogue = odc_catalogue()
    key = next((k for k in catalogue if k.lower() == str(odc).strip().lower()), None)
    if key is None:
        return {"ok": False, "error": f"'{odc}' is not a known ODC", "known_odcs": sorted(catalogue)}
    profile = {"odc": key, "floor": re.sub(r"[^\w\-]", "", str(floor or ""))[:10],
               "seat": re.sub(r"[^\w\-]", "", str(seat or ""))[:20]}
    save_profile(profile)
    return {"ok": True, "saved": profile, "odc_name": catalogue[key].get("name", key)}
