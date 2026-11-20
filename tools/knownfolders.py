"""The user's real Documents / Desktop / Downloads folders (Windows may have moved them, for example to OneDrive)."""
from __future__ import annotations

import ctypes
import os
import uuid
from ctypes import wintypes
from pathlib import Path

_IDS = {"Documents": "FDD39AD0-238F-46AF-ADB4-6C85480369C7", "Desktop": "B4BFCC3A-DB2C-424C-B029-7FE99A87C641",
        "Downloads": "374DE290-123F-4565-9164-39C4925E467B"}


class _GUID(ctypes.Structure):
    _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]


def known_folder(name: str) -> Path:
    try:
        u = uuid.UUID(_IDS[name])
        guid = _GUID(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:]))
        out = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(out)) == 0:
            path = Path(out.value)
            ctypes.windll.ole32.CoTaskMemFree(out)
            return path
    except Exception:
        pass
    return Path(os.path.expandvars(rf"%USERPROFILE%\{name}"))
