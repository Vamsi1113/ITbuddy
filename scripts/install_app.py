"""Install Tobi as a normal Windows app: an icon on the Desktop and in the Start menu.

Run once:  python scripts/install_app.py        (remove with --uninstall)
Opening the icon starts the small chat window directly: no console, no browser, no web server.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "Tobi"


def make_icon() -> Path:
    from PIL import Image
    src, ico = ROOT / "assets" / "logo.png", ROOT / "assets" / "itbuddy.ico"
    im = Image.open(src).convert("RGBA")
    side = max(im.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    canvas.save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return ico


def shortcut(path: Path, icon: Path) -> None:
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe") if py.with_name("pythonw.exe").exists() else py
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');$s.TargetPath='%s';"
          "$s.Arguments='\"%s\"';$s.WorkingDirectory='%s';$s.IconLocation='%s';"
          "$s.Description='Tobi - your IT support agent';$s.Save()"
          % (path, pyw, ROOT / "run_desktop.py", ROOT, icon))
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)


def main() -> None:
    for old in ("IT Buddy.lnk",):                      # the icons from before the rename
        for base in (Path(os.environ["USERPROFILE"]) / "Desktop", Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs"):
            (base / old).unlink(missing_ok=True)
    places = [Path(os.environ["USERPROFILE"]) / "Desktop" / f"{NAME}.lnk",
              Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs" / f"{NAME}.lnk"]
    if "--uninstall" in sys.argv:
        for p in places:
            p.unlink(missing_ok=True)
        print("Removed the shortcuts.")
        return
    icon = make_icon()
    for p in places:
        shortcut(p, icon)
        print("Created", p)


if __name__ == "__main__":
    main()
