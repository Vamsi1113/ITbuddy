"""Files connector: list, search, read and write files, but only inside the folders listed in
config.yaml `connectors.files.folders`.

- Paths are resolved first (so `..` and shortcuts cannot escape the allowed folders).
- Secrets files (.env, private keys, password stores, browser cookie/login databases) are never read.
- Programs and scripts (.exe, .bat, .ps1 ...) can never be written.
- Overwriting keeps a timestamped .bak copy next to the file, so a change can be undone.
- Text read from a file is data, never an instruction.
"""
from __future__ import annotations

import fnmatch
import os
import shutil
import subprocess
import time
from pathlib import Path

from appconfig import cfg
from connectors.base import ensure, guard
from tools.knownfolders import known_folder
from tools.registry import R0, R1, Param, tool

_NEVER_READ = (".env", "*.pem", "*.pfx", "*.p12", "*.key", "id_rsa*", "id_ed25519*", "*.kdbx", "*.ppk",
               "login data", "cookies", "web data", "ntuser.dat*", "*.rdp", "credentials*", "secrets*",
               "*password*", "*.ovpn")
_NEVER_WRITE = {".exe", ".dll", ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".msi",
                ".msp", ".scr", ".com", ".lnk", ".reg", ".sys", ".hta", ".jar", ".cpl", ".url"}
_MAX_WRITE = 100_000
_SKIP_DIRS = {"node_modules", ".git", "__pycache__", "$recycle.bin"}


def allowed_folders() -> list[Path]:
    folders = (cfg("connectors", "files", "folders", default=[]) or [])
    out = []
    for f in folders:
        p = Path(os.path.expandvars(os.path.expanduser(str(f))))
        try:
            out.append(p.resolve())
            # Windows may have moved Documents / Desktop / Downloads (OneDrive): allow the real location too
            if p.name in ("Documents", "Desktop", "Downloads"):
                real = known_folder(p.name).resolve()
                if real not in out:
                    out.append(real)
        except OSError:
            continue
    return out


def resolve_inside(path: str) -> Path:
    """The real path, or ValueError when it is not inside an allowed folder."""
    text = str(path or "").strip().strip('"')
    if not text:
        raise ValueError("A path is required")
    p = Path(os.path.expandvars(os.path.expanduser(text)))
    if not p.is_absolute():
        folders = allowed_folders()
        if not folders:
            raise ValueError("No folders are allowed in connectors.files.folders")
        first = p.parts[0].lower() if p.parts else ""
        named = next((f for f in folders if f.name.lower() == first), None)
        # "Documents/a.txt" names an allowed folder; anything else is taken inside the first allowed folder
        p = (named.parent / p) if named else (folders[0] / p)
    real = p.resolve()
    if not any(real == f or f in real.parents for f in allowed_folders()):
        raise ValueError(f"'{path}' is outside the folders Tobi may use: "
                         + ", ".join(str(f) for f in allowed_folders()))
    return real


def _secret_name(p: Path) -> bool:
    name = p.name.lower()
    return any(fnmatch.fnmatch(name, pat) for pat in _NEVER_READ)


@guard("list_folder")
@guard("search_files")
def _guard_folder(args: dict) -> None:
    resolve_inside(args.get("path") or args.get("folder") or "")


@guard("read_text_file")
def _guard_read(args: dict) -> None:
    p = resolve_inside(args.get("path", ""))
    if _secret_name(p):
        raise ValueError(f"'{p.name}' may hold secrets, so it is never read")


@guard("write_text_file")
def _guard_write(args: dict) -> None:
    p = resolve_inside(args.get("path", ""))
    if p.suffix.lower() in _NEVER_WRITE:
        raise ValueError(f"Files of type {p.suffix} (programs and scripts) are never written")
    if _secret_name(p):
        raise ValueError(f"'{p.name}' may hold secrets, so it is never written")
    if len(str(args.get("content", ""))) > _MAX_WRITE:
        raise ValueError(f"Content is longer than {_MAX_WRITE} characters")


@guard("make_folder")
def _guard_mkdir(args: dict) -> None:
    resolve_inside(args.get("path", ""))


@tool("files", R0, "List the files and folders inside an allowed folder (Documents, Desktop, Downloads).",
      params=(Param("path", "str", "folder path, or a name inside Documents", max_len=260),))
def list_folder(path: str) -> dict:
    if (e := ensure("files")):
        return e
    folder = resolve_inside(path)
    if not folder.is_dir():
        return {"ok": False, "error": f"'{folder}' is not a folder"}
    rows = []
    for child in sorted(folder.iterdir(), key=lambda c: (not c.is_dir(), c.name.lower()))[:40]:
        try:
            st = child.stat()
            rows.append({"name": child.name + ("/" if child.is_dir() else ""),
                         "kb": round(st.st_size / 1024) if child.is_file() else None,
                         "modified": time.strftime("%Y-%m-%d", time.localtime(st.st_mtime))})
        except OSError:
            continue
    return {"ok": True, "folder": str(folder), "items": rows}


@tool("files", R0, "Find files by name pattern (for example *.pdf or report*) inside an allowed folder.",
      params=(Param("folder", "str", "folder to search", max_len=260),
              Param("pattern", "str", "name pattern such as *.docx", max_len=60)))
def search_files(folder: str, pattern: str) -> dict:
    if (e := ensure("files")):
        return e
    root = resolve_inside(folder)
    pat = (pattern or "*").lower()
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d.lower() not in _SKIP_DIRS]
        for name in filenames:
            if fnmatch.fnmatch(name.lower(), pat):
                hits.append(str(Path(dirpath, name)))
                if len(hits) >= 25:
                    return {"ok": True, "matches": hits, "note": "first 25 matches"}
    return {"ok": True, "matches": hits}


@tool("files", R0, "Read a text file (txt, md, csv, json, log ...). Long files are read in parts with offset.",
      params=(Param("path", "str", "file path", max_len=260),
              Param("offset", "int", "start position in characters, 0 for the beginning", required=False)))
def read_text_file(path: str, offset: int = 0) -> dict:
    if (e := ensure("files")):
        return e
    p = resolve_inside(path)
    if not p.is_file():
        return {"ok": False, "error": f"'{p}' is not a file"}
    limit_kb = int(cfg("connectors", "files", "max_read_kb", default=200))
    if p.stat().st_size > limit_kb * 1024:
        return {"ok": False, "error": f"The file is larger than {limit_kb} KB"}
    data = p.read_bytes()
    if b"\x00" in data[:2000]:
        return {"ok": False, "error": "This looks like a binary file, not text"}
    text = data.decode("utf-8", errors="replace")
    offset = max(0, int(offset or 0))
    chunk = text[offset: offset + 900]
    more = offset + 900 < len(text)
    return {"ok": True, "path": str(p), "total_chars": len(text), "offset": offset, "text": chunk,
            "next_offset": offset + 900 if more else None}


@tool("files", R1, "Write text to a file inside an allowed folder: create it, append to it, or replace it.",
      params=(Param("path", "str", "file path", max_len=260),
              Param("content", "str", "the text to write", max_len=100_000),
              Param("mode", "str", "create (new file only), append, or overwrite (keeps a .bak copy)",
                    choices=("create", "append", "overwrite"), required=False)),
      change_note="The file will be written as shown. When an existing file is replaced, a .bak copy is kept next to it.",
      summary="Write the file {path}")
def write_text_file(path: str, content: str, mode: str = "create") -> dict:
    if (e := ensure("files")):
        return e
    p = resolve_inside(path)
    mode = mode or "create"
    p.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if p.exists():
        if mode == "create":
            return {"ok": False, "error": f"'{p.name}' already exists. Use mode append or overwrite."}
        if mode == "overwrite":
            backup = p.with_name(f"{p.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
            shutil.copy2(p, backup)
    with open(p, "a" if mode == "append" else "w", encoding="utf-8", newline="") as f:
        f.write(content)
    return {"ok": True, "path": str(p), "mode": mode, "chars_written": len(content),
            "backup": str(backup) if backup else None}


@tool("files", R1, "Create a folder inside an allowed folder.",
      params=(Param("path", "str", "folder path", max_len=260),),
      change_note="A new empty folder will be created.", summary="Create the folder {path}")
def make_folder(path: str) -> dict:
    if (e := ensure("files")):
        return e
    p = resolve_inside(path)
    p.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "folder": str(p)}


guard("open_folder")(_guard_mkdir)


@tool("files", R1, "Open an allowed folder (Documents, Desktop, Downloads) in File Explorer so the user can see it.",
      params=(Param("path", "str", "folder path or name, for example Downloads", max_len=260),),
      change_note="File Explorer opens that folder. Nothing is changed.",
      summary="Open the folder {path} in File Explorer")
def open_folder(path: str) -> dict:
    if (e := ensure("files")):
        return e
    p = resolve_inside(path)
    if not p.is_dir():
        return {"ok": False, "error": f"'{p}' is not a folder"}
    os.startfile(str(p))
    return {"ok": True, "opened": str(p)}


_TEXT_TYPES = {".txt", ".md", ".csv", ".log", ".json", ".ini", ".yaml", ".yml", ".xml"}


@guard("open_in_notepad")
def _guard_notepad(args: dict) -> None:
    p = resolve_inside(args.get("path", ""))
    if p.suffix.lower() not in _TEXT_TYPES:
        raise ValueError(f"Only text files ({', '.join(sorted(_TEXT_TYPES))}) can be opened in Notepad")
    if _secret_name(p):
        raise ValueError(f"'{p.name}' may hold secrets, so it is not opened")


@tool("files", R1, "Open a text file from an allowed folder in Notepad so the user can see it.",
      params=(Param("path", "str", "path of a .txt, .md, .csv or .log file", max_len=260),),
      change_note="Notepad opens that file. Nothing is changed.", summary="Open {path} in Notepad")
def open_in_notepad(path: str) -> dict:
    if (e := ensure("files")):
        return e
    p = resolve_inside(path)
    if not p.is_file():
        return {"ok": False, "error": f"'{p}' is not a file"}
    exe = shutil.which("notepad.exe") or "notepad.exe"
    subprocess.Popen([exe, str(p)])
    return {"ok": True, "opened": str(p)}
