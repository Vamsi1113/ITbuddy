"""Windows settings: read a setting, open a Settings page, change a small list of personal preferences.

Reading is R0. System-wide settings are never changed by the agent: it opens the right
Settings page for the user instead. Only the per-user preferences in _PREFERENCES can be changed.
"""
from __future__ import annotations

import ctypes
import os
import winreg

from tools import powershell
from tools.registry import R0, R1, Param, tool

HKLM, HKCU = winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER

powershell.SCRIPTS.update({
    "firewall_profiles": (
        "Get-NetFirewallProfile | Select-Object Name,@{n='enabled';e={[bool]$_.Enabled}} | ConvertTo-Json -Compress"
    ),
    "timezone": "Get-TimeZone | Select-Object Id,DisplayName | ConvertTo-Json -Compress",
    "languages": "(Get-WinUserLanguageList | ForEach-Object { $_.LanguageTag }) -join ', '",
    "defender_realtime": (
        "Get-MpComputerStatus | Select-Object RealTimeProtectionEnabled,AntivirusEnabled | ConvertTo-Json -Compress"
    ),
})


def _reg(hive, path: str, name: str, default=None):
    try:
        with winreg.OpenKey(hive, path) as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return default


def _on_off(value) -> str:
    return "On" if value else "Off"


_EXPLORER = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
_PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
_CONSENT = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"


def _developer_mode():
    v = _reg(HKLM, r"SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock", "AllowDevelopmentWithoutDevLicense", 0)
    return _on_off(v == 1)


def _dark_mode():
    apps = _reg(HKCU, _PERSONALIZE, "AppsUseLightTheme", 1)
    system = _reg(HKCU, _PERSONALIZE, "SystemUsesLightTheme", 1)
    return f"Apps: {'Light' if apps else 'Dark'}, Windows: {'Light' if system else 'Dark'}"


def _remote_desktop():
    return _on_off(_reg(HKLM, r"SYSTEM\CurrentControlSet\Control\Terminal Server", "fDenyTSConnections", 1) == 0)


def _uac():
    return _on_off(_reg(HKLM, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "EnableLUA", 1) == 1)


def _firewall():
    rows = powershell.run_powershell_list("firewall_profiles")
    return ", ".join(f"{r['Name']}: {_on_off(r['enabled'])}" for r in rows) or "unknown"


def _defender():
    d = powershell.run_powershell_json("defender_realtime") or {}
    if d.get("AntivirusEnabled") is None:
        return "unknown: Microsoft Defender did not report its state (another antivirus may manage this PC)"
    return f"Real-time protection: {_on_off(d.get('RealTimeProtectionEnabled'))}, antivirus: {_on_off(d.get('AntivirusEnabled'))}"


def _timezone():
    d = powershell.run_powershell_json("timezone") or {}
    return d.get("DisplayName") or d.get("Id") or "unknown"


def _power_plan():
    out = powershell.run_executable("active_power_plan").stdout or ""
    return out[out.find("(") + 1: out.rfind(")")] if "(" in out else out.strip() or "unknown"


def _default_browser():
    prog = _reg(HKCU, r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice", "ProgId", "")
    names = {"MSEdgeHTM": "Microsoft Edge", "ChromeHTML": "Google Chrome", "FirefoxURL": "Mozilla Firefox",
             "BraveHTML": "Brave", "OperaStable": "Opera"}
    for key, label in names.items():
        if prog.startswith(key):
            return label
    return prog or "not set"


def _display():
    user32 = ctypes.windll.user32
    try:
        scale = round(user32.GetDpiForSystem() / 96 * 100)
    except Exception:
        scale = None
    return (f"{user32.GetSystemMetrics(0)} x {user32.GetSystemMetrics(1)} on the main screen, "
            f"{user32.GetSystemMetrics(80)} screen(s), scaling {scale}%")


def _languages():
    return powershell.run_powershell("languages") or "unknown"


def _privacy(capability: str):
    def read():
        v = _reg(HKCU, rf"{_CONSENT}\{capability}", "Value", None)
        system = _reg(HKLM, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\{capability}", "Value", None)
        return f"For your apps: {v or 'not set'}, for the whole device: {system or 'not set'}"
    return read


def _proxy():
    path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    return f"{_on_off(_reg(HKCU, path, 'ProxyEnable', 0))} {_reg(HKCU, path, 'ProxyServer', '') or ''}".strip()


def _storage_sense():
    v = _reg(HKCU, r"Software\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy", "01", 0)
    return _on_off(v == 1)


def _domain():
    name = os.environ.get("USERDOMAIN", "")
    computer = os.environ.get("COMPUTERNAME", "")
    return f"Computer name {computer}; " + ("local account (not joined to a domain)" if name == computer
                                            else f"signed in to domain {name}")


# id -> (label, reader). The model can only ask for these ids.
SETTINGS = {
    "developer_mode": ("Developer Mode", _developer_mode),
    "dark_mode": ("Dark or light theme", _dark_mode),
    "remote_desktop": ("Remote Desktop", _remote_desktop),
    "user_account_control": ("User Account Control (UAC)", _uac),
    "firewall": ("Windows Firewall", _firewall),
    "antivirus": ("Microsoft Defender antivirus", _defender),
    "timezone": ("Time zone", _timezone),
    "power_plan": ("Power plan", _power_plan),
    "default_browser": ("Default web browser", _default_browser),
    "display": ("Screen resolution and scaling", _display),
    "language": ("Display language and keyboards", _languages),
    "proxy": ("Proxy", _proxy),
    "camera_access": ("Camera privacy access", _privacy("webcam")),
    "microphone_access": ("Microphone privacy access", _privacy("microphone")),
    "location_access": ("Location privacy access", _privacy("location")),
    "notifications": ("Notifications", lambda: _on_off(_reg(
        HKCU, r"Software\Microsoft\Windows\CurrentVersion\PushNotifications", "ToastEnabled", 1) == 1)),
    "clipboard_history": ("Clipboard history", lambda: _on_off(_reg(
        HKCU, r"Software\Microsoft\Clipboard", "EnableClipboardHistory", 0) == 1)),
    "storage_sense": ("Storage Sense (automatic cleanup)", _storage_sense),
    "file_extensions": ("Show file extensions in File Explorer", lambda: _on_off(_reg(HKCU, _EXPLORER, "HideFileExt", 1) == 0)),
    "hidden_files": ("Show hidden files in File Explorer", lambda: _on_off(_reg(HKCU, _EXPLORER, "Hidden", 2) == 1)),
    "fast_startup": ("Fast startup", lambda: _on_off(_reg(
        HKLM, r"SYSTEM\CurrentControlSet\Control\Session Manager\Power", "HiberbootEnabled", 0) == 1)),
    "taskbar_alignment": ("Taskbar alignment", lambda: "Left" if _reg(HKCU, _EXPLORER, "TaskbarAl", 1) == 0 else "Center"),
    "domain_join": ("Computer name and domain", _domain),
}

# Settings pages the agent may open for the user (ms-settings: links only).
PAGES = {
    "developers": "ms-settings:developers", "display": "ms-settings:display", "sound": "ms-settings:sound",
    "network": "ms-settings:network", "wifi": "ms-settings:network-wifi", "vpn": "ms-settings:network-vpn",
    "proxy": "ms-settings:network-proxy", "bluetooth": "ms-settings:bluetooth", "printers": "ms-settings:printers",
    "windows_update": "ms-settings:windowsupdate", "apps": "ms-settings:appsfeatures",
    "default_apps": "ms-settings:defaultapps", "startup_apps": "ms-settings:startupapps",
    "storage": "ms-settings:storagesense", "disks_and_volumes": "ms-settings:disksandvolumes", "power": "ms-settings:powersleep", "date_time": "ms-settings:dateandtime",
    "language": "ms-settings:regionlanguage", "personalization": "ms-settings:personalization",
    "colors": "ms-settings:colors", "notifications": "ms-settings:notifications", "privacy": "ms-settings:privacy",
    "camera": "ms-settings:privacy-webcam", "microphone": "ms-settings:privacy-microphone",
    "accounts": "ms-settings:yourinfo", "sign_in_options": "ms-settings:signinoptions",
    "about": "ms-settings:about", "remote_desktop": "ms-settings:remotedesktop",
    "windows_security": "windowsdefender:", "accessibility": "ms-settings:easeofaccess",
    "mouse": "ms-settings:mousetouchpad", "keyboard": "ms-settings:keyboard",
}

# Per-user preferences the agent may change after approval: id -> (hive path, value name, on value, off value)
_PREFERENCES = {
    "dark_mode": (_PERSONALIZE, ("AppsUseLightTheme", "SystemUsesLightTheme"), 0, 1),
    "file_extensions": (_EXPLORER, ("HideFileExt",), 0, 1),
    "hidden_files": (_EXPLORER, ("Hidden",), 1, 2),
    "clipboard_history": (r"Software\Microsoft\Clipboard", ("EnableClipboardHistory",), 1, 0),
}


@tool("settings", R0, "Read ONE Windows setting and say whether it is on or off, or what its value is.",
      params=(Param("setting", "str", "setting id", choices=tuple(SETTINGS)),))
def read_setting(setting: str) -> dict:
    label, reader = SETTINGS[setting]
    return {"ok": True, "setting": setting, "name": label, "value": reader()}


@tool("settings", R0, "Read the most common settings in one go (theme, firewall, antivirus, time zone, power plan, "
                      "default browser, display, developer mode, remote desktop).")
def read_common_settings() -> dict:
    ids = ("developer_mode", "dark_mode", "firewall", "antivirus", "timezone", "power_plan", "default_browser",
           "display", "remote_desktop")
    out = {}
    for sid in ids:
        try:
            out[sid] = SETTINGS[sid][1]()
        except Exception as e:
            out[sid] = f"could not read ({type(e).__name__})"
    return {"ok": True, "settings": out}


@tool("settings", R1, "Open a Windows Settings page so the user can change something there themselves.",
      params=(Param("page", "str", "page id", choices=tuple(PAGES)),),
      change_note="The Windows Settings app will open on that page. Nothing is changed; you make the change yourself.",
      summary="Open the Windows Settings page '{page}'")
def open_settings_page(page: str) -> dict:
    os.startfile(PAGES[page])  # fixed ms-settings: link from the allow-list above
    return {"ok": True, "opened": page}


@tool("settings", R1, "Turn one personal preference on or off (dark_mode, file_extensions, hidden_files, clipboard_history).",
      params=(Param("setting", "str", "preference id", choices=tuple(_PREFERENCES)),
              Param("value", "str", "on or off", choices=("on", "off"))),
      change_note="This changes a personal preference for your Windows account only. It can be switched back the same way.",
      summary="Turn {value}: {setting}")
def set_user_preference(setting: str, value: str) -> dict:
    path, names, on_value, off_value = _PREFERENCES[setting]
    new = on_value if value == "on" else off_value
    previous = {}
    with winreg.CreateKeyEx(HKCU, path, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
        for name in names:
            try:
                previous[name] = winreg.QueryValueEx(key, name)[0]
            except OSError:
                previous[name] = None
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, new)
    # Tell running apps that a setting changed, so the new theme applies without signing out.
    try:
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "ImmersiveColorSet", 0x0002, 2000, None)
    except Exception:
        pass
    return {"ok": True, "setting": setting, "now": value, "previous_values": previous,
            "current": SETTINGS[setting][1](),
            "note": "File Explorer may need to be reopened to show the change."}
