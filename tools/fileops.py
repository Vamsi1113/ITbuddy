"""Everyday file jobs on the user's own files. First: delete a file.

A deleted file goes to the Recycle Bin (it can be restored), never straight to permanent deletion. Only one file at a
time, found from the user's words with the same search as Save-as-PDF (usual folders, then the profile, then the other
drives; Windows, program folders and app data are never searched). Programs, scripts, shortcuts and system files are
never touched, and deleting many files at once ("delete all my files") stays a job for IT.
"""
from __future__ import annotations

from pathlib import Path

from tools.registry import R1, Param, tool


def recycle(path: Path) -> None:
    """Move one file to the Recycle Bin (the Windows shell does it, exactly like pressing Delete in Explorer)."""
    from win32com.shell import shell, shellcon
    flags = shellcon.FOF_ALLOWUNDO | shellcon.FOF_NOCONFIRMATION | shellcon.FOF_SILENT | shellcon.FOF_NOERRORUI
    result, aborted = shell.SHFileOperation((0, shellcon.FO_DELETE, str(path), None, flags, None, None))
    if result != 0 or aborted:
        raise OSError(f"Windows could not move it to the Recycle Bin (code {result})")


@tool("computer_use", R1, "Delete ONE file of the user's by moving it to the Recycle Bin (it can be restored).",
      params=(Param("file", "str", "the file: its full path, its name, or the user's words for it", max_len=400),),
      change_note="The file is moved to the Recycle Bin. You can restore it from there.",
      summary="Move {file} to the Recycle Bin")
def delete_file(file: str) -> dict:
    from tools import pdfprint
    target = pdfprint.resolve_document(file, kinds=None)
    if target is None:
        near = [p.name for p in pdfprint.find_documents(file, 3, kinds=None)]
        return {"ok": False, "error": f"I could not find exactly one file called '{file}'", **({"did_you_mean": near} if near else {})}
    if not target.is_file():
        return {"ok": False, "error": f"{target} is not a file"}
    try:
        recycle(target)
    except Exception as e:
        return {"ok": False, "error": f"{target.name} could not be deleted: {str(e)[:150]}"}
    if target.exists():
        return {"ok": False, "error": f"{target.name} is still there (it may be open in another program)"}
    return {"ok": True, "deleted": target.name, "from": str(target.parent), "recycle_bin": True}


@tool("computer_use", R1, "Open ONE of the user's files (a document, PDF, picture ...) in the program Windows uses for it.",
      params=(Param("file", "str", "the file: its full path, its name, or the user's words for it", max_len=400),),
      change_note="The file opens in its usual program. Nothing is changed.",
      summary="Open {file}")
def open_file(file: str) -> dict:
    import os
    from tools import pdfprint
    target = pdfprint.resolve_document(file, kinds=None)
    if target is None:
        return {"ok": False, "error": f"I could not find exactly one file called '{file}'"}
    try:
        os.startfile(str(target))
    except OSError as e:
        return {"ok": False, "error": f"{target.name} could not be opened: {str(e)[:150]}"}
    return {"ok": True, "opened": target.name, "from": str(target.parent)}
