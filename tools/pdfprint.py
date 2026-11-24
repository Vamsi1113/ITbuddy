"""Save a document as a PDF with Windows' virtual printer ("Microsoft Print to PDF").

This is what a user does by hand: print the document, choose the PDF printer, type a file name, click Save. Tobi does
the same steps: it sends the file to the virtual printer, waits for the "Save Print Output As" window Windows shows,
types the new file's path and presses Save, then checks that the PDF really exists.

Safety:
  - only documents inside the allowed folders (Documents, Desktop, Downloads) are used, found from the words the user
    gave ("my itbuddy test note"), never from an arbitrary path
  - the PDF goes to Desktop, Documents or Downloads and never overwrites a file (a number is added to the name)
  - nothing is printed on paper, and the original file is not changed
"""
from __future__ import annotations

import difflib
import os
import re
import subprocess
import time
from pathlib import Path

from appconfig import cfg
from tools import powershell
from tools.automation import TIMEOUTS, free_path, safe_filename
from tools.knownfolders import known_folder
from tools.registry import R1, Param, tool

PDF_PRINTER = "Microsoft Print to PDF"
FOLDERS = ("Desktop", "Documents", "Downloads")
TIMEOUTS["save_as_pdf"] = 110                     # the Save window and the PDF writer can take a while

# What the virtual printer can be given. Others (zip, exe, media) cannot be printed at all.
CONVERTIBLE = {".txt", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".rtf", ".csv", ".jpg", ".jpeg", ".png",
               ".bmp", ".gif", ".tif", ".tiff", ".htm", ".html", ".odt", ".ods"}

# Fixed scripts (the model never writes a command; the file and printer come in through ITB_ARG as "file|printer").
# They run in the background: the virtual printer then waits for a file name in its "Save Print Output As" window.
_TEXT_SCRIPT = (r"$a=$env:ITB_ARG -split '\|',2; Get-Content -LiteralPath $a[0] -Raw | Out-Printer -Name $a[1]")
_IMAGE_SCRIPT = (
    r"$a=$env:ITB_ARG -split '\|',2; Add-Type -AssemblyName System.Drawing; "
    "$img=[System.Drawing.Image]::FromFile($a[0]); $d=New-Object System.Drawing.Printing.PrintDocument; "
    "$d.PrinterSettings.PrinterName=$a[1]; "
    "$d.add_PrintPage({param($s,$e) $b=$e.MarginBounds; $r=[Math]::Min($b.Width/$img.Width,$b.Height/$img.Height); "
    "$e.Graphics.DrawImage($img,$b.X,$b.Y,[int]($img.Width*$r),[int]($img.Height*$r)); $e.HasMorePages=$false}); "
    "$d.Print(); $img.Dispose()")


# ------------------------------------------------------------------------------------------------ finding the file
# Words that describe WHERE or WHAT, not the file's name ("the RAGAS document there in my destop" -> "ragas").
_FILLER = {"my", "the", "a", "an", "this", "that", "these", "those", "it", "its", "file", "files", "document", "documents",
           "documnet", "doc", "docs", "please", "pls", "called", "named", "of", "in", "on", "to", "into", "at", "from", "there",
           "here", "which", "is", "are", "was", "and", "or", "with", "using", "use", "via", "by", "for", "me", "u", "you",
           "can", "could", "would", "will", "print", "printer", "printers", "printing", "service", "save", "saved", "store",
           "convert", "export", "make", "pdf", "copy", "desktop", "destop", "deskop", "dekstop", "downloads", "download",
           "folder", "folders", "drive", "drives", "virtual", "avd", "system", "computer", "pc", "laptop", "find", "will",
           "should", "as", "into", "then", "also", "be", "need", "want", "wanna", "ok", "okay", "no", "yes"}
# Never searched: Windows itself, installed programs, app data, caches, source control and package folders.
_SKIP_DIRS = {"windows", "program files", "program files (x86)", "programdata", "appdata", "$recycle.bin",
              "system volume information", "recovery", "perflogs", "msocache", "node_modules", ".git", ".venv", "venv",
              "__pycache__", "site-packages", ".cache", "temp", "tmp", "onedrivetemp", "intel", "nvidia", "amd", "drivers"}
SEARCH_SECONDS = 8.0


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^\w]+", text.lower()) if t]


def _word_match(a: str, b: str) -> bool:
    a, b = a.replace("ph", "f"), b.replace("ph", "f")            # "foto" ~ "photo"
    return a == b or (len(a) > 3 and len(b) > 3 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8)


def _folders() -> list[Path]:
    from connectors.files import allowed_folders
    return allowed_folders()


def folder_path(name: str) -> Path:
    return known_folder(name if name in FOLDERS else "Desktop")


def _search_roots() -> list[tuple[Path, int]]:
    """Where to look, nearest first, with how deep: the usual folders, then the whole user profile, then the other
    local drives (D:, E: ...). System and program folders are never searched."""
    roots: list[tuple[Path, int]] = [(f, 2) for f in _folders()]
    home = Path(os.path.expanduser("~"))
    roots.append((home, 5))
    try:
        import psutil
        for part in psutil.disk_partitions(all=False):
            mount = Path(part.mountpoint)
            if "fixed" in (part.opts or "").lower() or part.fstype:
                if mount.drive.upper() != home.drive.upper():
                    roots.append((mount, 4))
    except Exception:
        pass
    seen, out = set(), []
    for r, d in roots:
        key = str(r).lower()
        if key not in seen and r.exists():
            seen.add(key)
            out.append((r, d))
    return out


def _explicit_names(phrase: str) -> list[str]:
    """Possible file names in the words, longest first: "print my Q3 report.docx" -> ["my Q3 report.docx",
    "Q3 report.docx", "report.docx"] (the search tries each; a sentence often carries extra leading words)."""
    m = re.search(r"[\"']([^\"']{1,120}\.[A-Za-z0-9]{2,5})[\"']|([\w\-. ()]{1,120}\.[A-Za-z0-9]{2,5})(?![\w.])", phrase or "")
    name = (m.group(1) or m.group(2)).strip() if m else ""
    if not name:
        return []
    words = Path(name).name.split()
    return [" ".join(words[i:]) for i in range(len(words))]


def _explicit_name(phrase: str) -> str:
    """A real file name in the words ("RAGAS.txt", "\"Q3 report.docx\""), lowercase, or ""."""
    m = re.search(r"[\"']([^\"']{1,120}\.[A-Za-z0-9]{2,5})[\"']|([\w\-. ()]{1,120}\.[A-Za-z0-9]{2,5})(?![\w.])", phrase or "")
    if not m:
        return ""
    name = (m.group(1) or m.group(2)).strip()
    return name.split()[-1] if not m.group(1) and " " in name and name.split()[-1].count(".") else name


def _score(path: Path, words: list[str]) -> float:
    stem = _tokens(path.stem)
    if not stem or not words:
        return 0.0
    stem_cover = sum(1 for s in stem if any(_word_match(s, w) for w in words)) / len(stem)
    word_cover = sum(1 for w in words if any(_word_match(s, w) for s in stem)) / len(words)
    whole_stem = stem_cover >= 0.99 and any(len(s) >= 3 for s in stem)      # every word of the name was said
    if whole_stem or (word_cover >= 0.99 and stem_cover >= 0.34):
        return stem_cover + word_cover - 0.001 * len(stem) - (0.01 if path.suffix.lower() == ".pdf" else 0)
    return 0.0


def _ranked(phrase: str) -> list[tuple[float, Path]]:
    """(score, path) for documents the words describe, best first. Looks in the usual folders first and only goes on
    to the whole profile and the other drives when nothing matched there. Extra words, small typos and missing
    extensions are fine: "the RAGAS document in my destop" finds RAGAS.txt; an exact file name always wins."""
    words = [t for t in _tokens(phrase) if t not in _FILLER] or [t for t in _tokens(phrase) if len(t) > 2]
    names = [n.lower() for n in _explicit_names(phrase)]
    exact = names[0] if names else ""
    if exact:
        words = [t for t in _tokens(Path(exact).stem) if t not in _FILLER] or words
    if not words and not exact:
        return []
    deadline = time.monotonic() + SEARCH_SECONDS
    scored: dict[Path, float] = {}
    for tier, (base, max_depth) in enumerate(_search_roots()):
        if scored and tier >= len(_folders()):
            break                                        # found in a nearer place: do not search further
        depth = len(base.parts)
        for root, dirs, files in os.walk(base):
            if time.monotonic() > deadline:
                break
            if len(Path(root).parts) - depth >= max_depth:
                dirs[:] = []
            dirs[:] = [d for d in dirs if d.lower() not in _SKIP_DIRS and not d.startswith((".", "$", "~"))]
            for f in files:
                low = f.lower()
                p = Path(root, f)
                if p.suffix.lower() not in CONVERTIBLE | {".pdf"}:
                    continue
                if names and low in names:
                    scored[p] = 10.0 - names.index(low) * 0.1          # the longest matching name wins
                    continue
                sc = _score(p, words)
                if sc:
                    scored[p] = max(scored.get(p, 0), sc)
    return sorted(((v, k) for k, v in scored.items()), key=lambda x: -x[0])


def find_documents(phrase: str, limit: int = 5) -> list[Path]:
    return [p for _, p in _ranked(phrase)[:limit]]


def _usable_path(text: str) -> Path | None:
    """A full path to an existing document outside the system folders (Tobi's own plan passes these)."""
    try:
        p = Path(os.path.expandvars((text or "").strip().strip("\"'")))
        if p.is_absolute() and p.is_file() and p.suffix.lower() in CONVERTIBLE | {".pdf"}:
            if not any(part.lower() in _SKIP_DIRS for part in p.parts[1:-1]):
                return p
    except (OSError, ValueError):
        pass
    return None


def resolve_document(phrase: str) -> Path | None:
    """The one document the words mean, or None when nothing matches or two documents match about equally well."""
    direct = _usable_path(phrase)
    if direct:
        return direct
    ranked = _ranked(phrase)
    if not ranked:
        return None
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 0.05 and ranked[0][1].stem.lower() != ranked[1][1].stem.lower():
        return None
    return ranked[0][1]


# ------------------------------------------------------------------------------------------------ the virtual printer
def pdf_printer_installed() -> bool:
    from tools import printing
    try:
        return any(PDF_PRINTER.lower() in str(p.get("Name", "")).lower() for p in printing.collect_state()["printers"])
    except Exception:
        return False


def _stop(proc, dlg: int = 0) -> None:
    """Cancel the print to the PDF printer: close its Save window and end the helper process Tobi started."""
    try:
        if dlg:
            import win32con
            import win32gui
            win32gui.PostMessage(dlg, win32con.WM_COMMAND, 2, 0)          # 2 = IDCANCEL
    except Exception:
        pass
    try:
        if proc is not None and proc.poll() is None:
            proc.kill()
    except Exception:
        pass


def _launch(source: Path) -> subprocess.Popen | None:
    """Send the document to the PDF printer without waiting (the printer's Save window must be answered first)."""
    ext = source.suffix.lower()
    arg = f"{source}|{PDF_PRINTER}"
    if ext in (".txt", ".csv", ".log"):
        script = _TEXT_SCRIPT
    elif ext in (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff"):
        script = _IMAGE_SCRIPT
    else:                                                  # Word, Excel, PowerPoint ...: their own "PrintTo" command
        powershell.run_powershell("print_file_to", timeout=40, arg=arg)
        return None
    env = dict(os.environ, ITB_ARG=arg)
    return subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], env=env,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _save_window(timeout: float) -> int:
    """Handle of the 'Save Print Output As' window Windows shows when printing to the PDF printer (0 if none).
    The window can exist without being visible, so every top-level window is searched, shown or not."""
    import win32gui
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        found = []

        def look(hwnd, _):
            if "save print output" in win32gui.GetWindowText(hwnd).lower():
                found.append(hwnd)
            return True

        win32gui.EnumWindows(look, None)
        if found:
            return found[0]
        time.sleep(0.3)
    return 0


def _fill_save_window(dlg: int, target: Path) -> None:
    """Put the new file's path in the 'File name' box and press Save, by sending the window its own messages."""
    import win32con
    import win32gui
    edit = None
    end = time.monotonic() + 8                      # the window is shown before its boxes are built: wait for them
    while edit is None and time.monotonic() < end:
        kids = []
        try:
            win32gui.EnumChildWindows(dlg, lambda h, _: kids.append((h, win32gui.GetClassName(h), win32gui.GetDlgCtrlID(h))) or True,
                                      None)
        except Exception:
            pass
        edit = next((h for h, cls, cid in kids if cls == "Edit" and cid == 1001), None)
        if edit is None:
            time.sleep(0.3)
    if edit is None:
        raise RuntimeError("could not find the 'File name' box in the Save window")
    win32gui.SendMessage(edit, win32con.WM_SETTEXT, 0, str(target))
    time.sleep(0.4)
    win32gui.PostMessage(dlg, win32con.WM_COMMAND, 1, 0)                     # 1 = IDOK: the Save button


@tool("computer_use", R1, "Save a document (text, Word, Excel, PowerPoint, picture) as a PDF with Windows' virtual PDF "
      "printer, in Desktop, Documents or Downloads. Nothing is printed on paper and the original is not changed.",
      params=(Param("file", "str", "the document: its name, its full path, or the words the user used for it", max_len=400),
              Param("name", "str", "name of the new PDF without a folder, optional", required=False, max_len=80),
              Param("folder", "str", "where to save the PDF", choices=FOLDERS, required=False)),
      change_note="Windows' virtual printer \"Microsoft Print to PDF\" makes a new PDF of the document. Nothing is printed on "
                  "paper and the original file is not changed.",
      summary="Save {file} as a PDF in {folder}")
def save_as_pdf(file: str, name: str = "", folder: str = "") -> dict:
    source = resolve_document(file)
    if source is None:
        near = [p.name for p in find_documents(file, 3)]
        return {"ok": False, "error": f"I could not find a single document called '{file}' in Desktop, Documents or Downloads",
                **({"did_you_mean": near} if near else {})}
    ext = source.suffix.lower()
    if ext == ".pdf":
        return {"ok": False, "error": f"{source.name} is already a PDF"}
    if ext not in CONVERTIBLE:
        return {"ok": False, "error": f"{ext} files cannot be saved as a PDF this way"}
    if not pdf_printer_installed():
        return {"ok": False, "error": "The Microsoft Print to PDF printer is not installed on this computer"}
    dest_dir = folder_path(folder) if folder else (source.parent if source.parent in _folders() else known_folder("Desktop"))
    target = free_path(dest_dir, safe_filename(name or source.stem, source.stem, "pdf"))
    try:
        proc = _launch(source)
    except (powershell.CommandError, OSError) as e:
        return {"ok": False, "error": f"Windows could not send {source.name} to the PDF printer: {str(e)[:150]}"}
    dlg = _save_window(25)
    if not dlg:
        if proc is not None and proc.poll() is None:
            proc.kill()
        return {"ok": False, "error": "The PDF printer's Save window did not appear. Open the file, press Ctrl+P, choose "
                                      f"{PDF_PRINTER}, and save it yourself."}
    try:
        _fill_save_window(dlg, target)
    except Exception as e:
        _stop(proc, dlg)
        return {"ok": False, "error": f"The Save window could not be filled in: {str(e)[:150]}"}
    end = time.monotonic() + 40
    last = -1
    while time.monotonic() < end:
        if target.exists() and target.stat().st_size > 0:
            size = target.stat().st_size
            if size == last:                                   # finished writing
                return {"ok": True, "saved_as": str(target), "file_name": target.name, "folder": str(target.parent),
                        "size_kb": max(1, round(size / 1024)), "from": source.name, "printer": PDF_PRINTER}
            last = size
        time.sleep(0.8)
    return {"ok": False, "error": f"The PDF was not written within 40 seconds (expected {target})"}
