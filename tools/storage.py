"""Storage tools: get_disk_usage, find_large_temp_folders, clean_approved_temp_files."""
from __future__ import annotations

import os
import stat
import time
from pathlib import Path

import psutil

from appconfig import cfg, expand
from tools import powershell
from tools.registry import R0, R1, R2, Param, tool

_GB = 1024 ** 3
_MB = 1024 ** 2
_SCAN_SECONDS = 20  # stay inside the 30 second tool timeout


def allowed_temp_folders() -> list[Path]:
    out = []
    for raw in cfg("storage", "allowed_temp_folders", default=[]) or []:
        p = expand(raw)
        try:
            p = p.resolve(strict=True)
        except OSError:
            continue
        if p.is_dir() and p not in out:
            out.append(p)
    return out


def _is_link(entry: os.DirEntry) -> bool:
    try:
        st = entry.stat(follow_symlinks=False)
    except OSError:
        return True
    if entry.is_symlink():
        return True
    # Windows junctions / reparse points: never follow them out of the folder.
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _walk_files(root: Path, deadline: float):
    stack = [root]
    while stack:
        if time.monotonic() > deadline:
            return
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    if _is_link(entry):
                        continue
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            yield entry
                    except OSError:
                        continue
        except OSError:
            continue


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root)
        return True
    except (ValueError, OSError):
        return False


@tool("storage", R0, "Total and free space per drive.")
def get_disk_usage() -> dict:
    drives = []
    for part in psutil.disk_partitions(all=False):
        if "cdrom" in part.opts or not part.fstype:
            continue
        try:
            u = psutil.disk_usage(part.mountpoint)
        except OSError:
            continue
        drives.append({
            "drive": part.mountpoint.rstrip("\\"),
            "total_gb": round(u.total / _GB, 1),
            "free_gb": round(u.free / _GB, 2),
            "used_percent": u.percent,
        })
    return {"ok": True, "drives": drives}


@tool("storage", R0, "Size of the allowed temp folders and how many MB can be cleaned.")
def find_large_temp_folders() -> dict:
    deadline = time.monotonic() + _SCAN_SECONDS
    min_age = float(cfg("storage", "min_file_age_minutes", default=60)) * 60
    now = time.time()
    folders = []
    for folder in allowed_temp_folders():
        total = files = cleanable = cleanable_files = 0
        for entry in _walk_files(folder, deadline):
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            total += st.st_size
            files += 1
            if now - st.st_mtime >= min_age:
                cleanable += st.st_size
                cleanable_files += 1
        folders.append({
            "folder": str(folder),
            "size_mb": round(total / _MB, 1),
            "files": files,
            "cleanable_mb": round(cleanable / _MB, 1),
            "cleanable_files": cleanable_files,
        })
    return {"ok": True, "folders": folders,
            "total_cleanable_mb": round(sum(f["cleanable_mb"] for f in folders), 1),
            "scan_complete": time.monotonic() <= deadline}


@tool("storage", R1, "Delete old files inside the allowed temp folders only.",
      change_note="Old temporary files will be deleted. Files in use are skipped. Your documents are not touched. "
                  "Deleted temp files cannot be restored.")
def clean_approved_temp_files() -> dict:
    """Delete files older than the minimum age inside the allowed temp folders only."""
    deadline = time.monotonic() + _SCAN_SECONDS
    min_age = float(cfg("storage", "min_file_age_minutes", default=60)) * 60
    now = time.time()
    deleted = skipped = freed = 0
    folders = allowed_temp_folders()
    for folder in folders:
        for entry in _walk_files(folder, deadline):
            path = Path(entry.path)
            try:
                st = entry.stat(follow_symlinks=False)
                if now - st.st_mtime < min_age or not _inside(path, folder):
                    skipped += 1
                    continue
                os.remove(path)
                deleted += 1
                freed += st.st_size
            except OSError:
                skipped += 1  # in use or access denied: leave it
    return {"ok": True, "folders": [str(f) for f in folders], "files_deleted": deleted,
            "files_skipped": skipped, "freed_mb": round(freed / _MB, 1),
            "finished": time.monotonic() <= deadline}


powershell.SCRIPTS.update({
    "recycle_bin": (
        "$i=(New-Object -ComObject Shell.Application).Namespace(10).Items(); $s=0; foreach($x in $i){$s+=$x.Size}; "
        "[pscustomobject]@{items=$i.Count; size_mb=[math]::Round($s/1MB,1)} | ConvertTo-Json -Compress"
    ),
    "empty_recycle_bin": "Clear-RecycleBin -Force -ErrorAction Stop",
    "disk_health": (
        "Get-PhysicalDisk | Select-Object FriendlyName,@{n='media';e={\"$($_.MediaType)\"}},"
        "@{n='health';e={\"$($_.HealthStatus)\"}},@{n='status';e={\"$($_.OperationalStatus)\"}},"
        "@{n='size_gb';e={[math]::Round($_.Size/1GB)}} | ConvertTo-Json -Compress"
    ),
})

_USER_FOLDERS = ("Downloads", "Documents", "Desktop", "Pictures", "Videos", "Music")


@tool("storage", R0, "Size of the user's main folders (Downloads, Documents, Desktop, Pictures, Videos, Music).")
def get_user_folder_sizes() -> dict:
    home = Path(os.path.expandvars("%USERPROFILE%"))
    rows = []
    for name in _USER_FOLDERS:
        folder = home / name
        if not folder.is_dir():
            continue
        deadline = time.monotonic() + 4
        total = files = 0
        for entry in _walk_files(folder, deadline):
            try:
                total += entry.stat(follow_symlinks=False).st_size
                files += 1
            except OSError:
                continue
        rows.append({"folder": name, "size_mb": round(total / _MB, 1), "files": files,
                     "complete": time.monotonic() <= deadline})
    rows.sort(key=lambda r: r["size_mb"], reverse=True)
    return {"ok": True, "folders": rows}


@tool("storage", R0, "How many items are in the Recycle Bin and how much space they use.")
def get_recycle_bin_size() -> dict:
    return {"ok": True, **(powershell.run_powershell_json("recycle_bin") or {})}


@tool("storage", R0, "Physical disk health status (Healthy / Warning / Unhealthy).")
def get_disk_health() -> dict:
    return {"ok": True, "disks": powershell.run_powershell_list("disk_health")}


@tool("storage", R2, "Empty the Recycle Bin.",
      change_note="Everything in the Recycle Bin will be deleted permanently. This cannot be undone.")
def empty_recycle_bin() -> dict:
    before = powershell.run_powershell_json("recycle_bin") or {}
    powershell.run_powershell("empty_recycle_bin")
    return {"ok": True, "items_removed": before.get("items"), "freed_mb": before.get("size_mb")}


def app_cache_names() -> list[str]:
    return sorted(cfg("storage", "app_caches", default={}) or {})


@tool("storage", R1, "Clear the cache of one app (browser or Teams). Sign-ins and bookmarks are kept.",
      params=(Param("app", "str", "which app", choices=app_cache_names),),
      change_note="Cached files of the app will be deleted. The app rebuilds them; the first start may be slower. "
                  "Close the app first, files in use are skipped.",
      summary="Clear the {app} cache")
def clear_app_cache(app: str) -> dict:
    caches = cfg("storage", "app_caches", default={}) or {}
    if app not in caches:
        return {"ok": False, "error": f"'{app}' is not on the allowed cache list"}
    folder = expand(caches[app])
    if not folder.is_dir():
        return {"ok": False, "error": f"No cache folder found for {app} on this computer"}
    folder = folder.resolve()
    deadline = time.monotonic() + _SCAN_SECONDS
    deleted = skipped = freed = 0
    for entry in _walk_files(folder, deadline):
        try:
            size = entry.stat(follow_symlinks=False).st_size
            if not _inside(Path(entry.path), folder):
                continue
            os.remove(entry.path)
            deleted += 1
            freed += size
        except OSError:
            skipped += 1
    return {"ok": True, "app": app, "files_deleted": deleted, "files_skipped": skipped,
            "freed_mb": round(freed / _MB, 1)}
