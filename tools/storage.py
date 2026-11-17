"""Storage tools: get_disk_usage, find_large_temp_folders, clean_approved_temp_files."""
from __future__ import annotations

import os
import stat
import time
from pathlib import Path

import psutil

from appconfig import cfg, expand

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
