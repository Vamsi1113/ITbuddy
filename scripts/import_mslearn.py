"""Import Microsoft's Windows documentation (Microsoft Learn) into Tobi's knowledge base.

Sources (public GitHub repositories, text licensed CC BY 4.0, which allows reuse with attribution):
  troubleshoot    MicrosoftDocs/SupportArticles-docs, support/windows-client: the Windows troubleshooting library
                  (https://learn.microsoft.com/troubleshoot/windows-client/)
  windows-server  MicrosoftDocs/windowsserverdocs: the Disk Management how-to guides (shrink, extend, drive letters,
                  new disks ...) and the Windows command reference for everyday support commands (chkdsk, sfc,
                  diskpart, ipconfig, robocopy, manage-bde ...), https://learn.microsoft.com/windows-server/
Every imported file keeps a link to its original page, answers cite that page, and
kb_vendor/microsoft_learn/NOTICE.md records the licence.

    python scripts/import_mslearn.py                  # import or refresh every source, then index them
    python scripts/import_mslearn.py --sources windows-server
    python scripts/import_mslearn.py --areas networking printing
    python scripts/import_mslearn.py --list           # show the areas and article counts
    python scripts/import_mslearn.py --no-index       # download only

Re-running it is safe: unchanged articles are skipped when indexing, and articles Microsoft removed are deleted.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REPO = "MicrosoftDocs/SupportArticles-docs"
BRANCH = "main"
PREFIX = "support/windows-client/"
LEARN = "https://learn.microsoft.com/en-us/troubleshoot/windows-client/"
OUT = ROOT / "kb_vendor" / "microsoft_learn"
# Admin-only tooling, retired products and navigation pages that do not help an end-user support agent.
SKIP_AREAS = {"app-v", "ue-v", "admin-development", "high-availability", "windows-tss", "breadcrumb", "context",
              "windows-7-eos-faq"}

NOTICE = """# Microsoft Learn articles (imported)

These files are imported from Microsoft's Windows troubleshooting documentation
(https://learn.microsoft.com/troubleshoot/windows-client/, GitHub repository MicrosoftDocs/SupportArticles-docs) and,
in the windows-server folder, from the Windows Server documentation: the Disk Management guides and part of the
Windows command reference (https://learn.microsoft.com/windows-server/, GitHub repository
MicrosoftDocs/windowsserverdocs). Both are published under the Creative Commons Attribution 4.0 International licence
(https://creativecommons.org/licenses/by/4.0/). © Microsoft Corporation.

Changes: front matter, images, includes and link targets were removed and the text was lightly reformatted for
search. Each file starts with a `<!-- source: ... -->` line pointing to the original article, and Tobi cites that
page when it uses the text. Refresh with `python scripts/import_mslearn.py`.
"""


def list_articles() -> list[dict]:
    r = requests.get(f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1", timeout=120)
    r.raise_for_status()
    out = []
    for t in r.json().get("tree", []):
        p = t["path"]
        if t["type"] == "blob" and p.startswith(PREFIX) and p.endswith(".md"):
            rel = p[len(PREFIX):]
            area = rel.split("/")[0]
            if "/" in rel and area not in SKIP_AREAS and not rel.endswith(("index.md", "toc.md")):
                out.append({"path": p, "rel": rel, "area": area, **SOURCES["troubleshoot"]})
    return out


# Windows Server docs: only what helps a user's own PC. Disk Management guides (all), and the commands a support
# agent explains to users. The diskpart sub-commands cover "split my C drive" style questions step by step.
WS_COMMANDS = {
    "chkdsk", "chkntfs", "sfc", "diskpart", "shrink", "extend", "create-partition-primary", "create-volume-simple",
    "delete-partition", "delete-volume", "assign", "remove", "format", "list-disk", "list-volume", "list-partition",
    "select-disk", "select-volume", "select-partition", "detail-disk", "detail-volume", "label", "vol", "convert",
    "clean", "active", "defrag", "cleanmgr", "fsutil", "mountvol", "subst", "compact", "cipher", "attrib", "icacls",
    "takeown", "robocopy", "xcopy", "copy", "move", "del", "rmdir", "mkdir", "dir", "manage-bde", "manage-bde-status",
    "manage-bde-on", "manage-bde-off", "manage-bde-protectors", "manage-bde-unlock", "manage-bde-resume",
    "manage-bde-pause", "ipconfig", "ping", "tracert", "pathping", "nslookup", "netstat", "arp", "getmac", "hostname",
    "route_ws2008", "netsh", "net-use", "net-print", "nbtstat", "gpupdate", "gpresult", "whoami", "systeminfo",
    "tasklist", "taskkill", "shutdown", "driverquery", "pnputil", "msinfo32", "mstsc", "sc-query", "sc-config",
    "schtasks", "wevtutil", "w32tm", "wbadmin", "wbadmin-start-backup", "wbadmin-get-versions", "recover", "expand",
    "where", "query-user", "logoff", "bcdedit", "reagentc", "winrs", "powershell", "cmd",
}

SOURCES = {
    "troubleshoot": {"source": "troubleshoot", "repo": "MicrosoftDocs/SupportArticles-docs", "prefix": "support/windows-client/",
                     "learn": LEARN, "out": OUT},
    "windows-server": {"source": "windows-server", "repo": "MicrosoftDocs/windowsserverdocs", "prefix": "WindowsServerDocs/",
                       "learn": "https://learn.microsoft.com/en-us/windows-server/", "out": OUT / "windows-server"},
}


def list_windows_server() -> list[dict]:
    src = SOURCES["windows-server"]
    r = requests.get(f"https://api.github.com/repos/{src['repo']}/git/trees/{BRANCH}?recursive=1", timeout=120)
    r.raise_for_status()
    out = []
    for t in r.json().get("tree", []):
        p = t["path"]
        if t["type"] != "blob" or not p.startswith(src["prefix"]) or not p.endswith(".md"):
            continue
        rel = p[len(src["prefix"]):]
        if rel.startswith("storage/disk-management/"):
            out.append({"path": p, "rel": rel, "area": "disk-management", **src})
        elif rel.startswith("administration/windows-commands/") and rel.rsplit("/", 1)[-1][:-3] in WS_COMMANDS:
            out.append({"path": p, "rel": rel, "area": "windows-commands", **src})
    return out


_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def clean(raw: str) -> tuple[str, str, str]:
    """(title, description, markdown body) from a Learn article."""
    meta = {}
    m = _FRONT.match(raw)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip("'\"")
        raw = raw[m.end():]
    text = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(("[!INCLUDE", ":::", "<a name", "![", "> [!div", "[!div")) or s.lower().startswith("<img"):
            continue
        line = re.sub(r">\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]", lambda g: "> " + g.group(1).title() + ":", line)
        line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)                    # images
        line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)                # links -> their text
        line = re.sub(r"</?(br|kbd|b|i|em|strong|sup|sub)\s*/?>", "", line, flags=re.IGNORECASE)
        line = line.replace("&nbsp;", " ").replace("_Applies to:_", "Applies to:")
        lines.append(line.rstrip())
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    title = meta.get("title", "")
    h1 = re.search(r"^# (.+)$", body, re.MULTILINE)
    if h1:
        title = title or h1.group(1).strip()
        body = body[:h1.start()] + body[h1.end():]
    return title, meta.get("description", ""), body.strip()


def fetch(article: dict) -> tuple[dict, str | None]:
    url = f"https://raw.githubusercontent.com/{article.get('repo', REPO)}/{BRANCH}/{article['path']}"
    for _ in range(3):
        try:
            r = requests.get(url, timeout=60)
            if r.ok:
                return article, r.text
        except requests.RequestException:
            pass
    return article, None


def write(article: dict, raw: str) -> Path | None:
    title, description, body = clean(raw)
    if len(body.split()) < 40:
        return None
    rel = article["rel"][:-3]
    target = article.get("out", OUT) / f"{rel}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    text = (f"<!-- source: {article.get('learn', LEARN)}{rel} -->\n# {title or rel.split('/')[-1].replace('-', ' ')}\n\n"
            + (f"{description}\n\n" if description else "") + body
            + "\n\n_Source: Microsoft Learn, licensed CC BY 4.0._\n")
    if not target.exists() or target.read_text(encoding="utf-8") != text:
        target.write_text(text, encoding="utf-8")
    return target


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--areas", nargs="*", help="only these areas (default: all useful areas)")
    ap.add_argument("--list", action="store_true", help="list the areas and article counts, then stop")
    ap.add_argument("--no-index", action="store_true", help="download only, do not index")
    ap.add_argument("--sources", nargs="*", choices=sorted(SOURCES), help="only these sources (default: all)")
    args = ap.parse_args()

    wanted = set(args.sources or SOURCES)
    articles = (list_articles() if "troubleshoot" in wanted else []) + \
               (list_windows_server() if "windows-server" in wanted else [])
    if args.list:
        for area, n in Counter(a["area"] for a in articles).most_common():
            print(f"{area:45} {n}")
        return 0
    if args.areas:
        articles = [a for a in articles if a["area"] in set(args.areas)]
    print(f"Downloading {len(articles)} articles from {', '.join(sorted({a['repo'] for a in articles}))} ...")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "NOTICE.md").write_text(NOTICE, encoding="utf-8")
    kept: set[Path] = set()
    failed = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for i, (article, raw) in enumerate(pool.map(fetch, articles), 1):
            if raw is None:
                failed += 1
                continue
            path = write(article, raw)
            if path:
                kept.add(path.resolve())
            if i % 50 == 0:
                print(f"  {i}/{len(articles)}")
    if not args.areas and not failed:              # a full, clean run: drop articles Microsoft removed
        server_dir = SOURCES["windows-server"]["out"].resolve()
        for name in wanted:                         # only inside the folders of the sources just imported
            for old in SOURCES[name]["out"].rglob("*.md"):
                inside_server = server_dir in old.resolve().parents
                if name == "troubleshoot" and inside_server:
                    continue
                if old.name != "NOTICE.md" and old.resolve() not in kept:
                    old.unlink()
    print(f"Saved {len(kept)} articles to {OUT.relative_to(ROOT)} ({failed} downloads failed).")

    if not args.no_index:
        from rag.embed import dense_enabled, model_name
        from rag.ingest import ingest_vendor_files
        print("Indexing" + (f" with vector embeddings ({model_name()}); this can take several minutes ..."
                            if dense_enabled() else " (keyword search only: no embedding model available) ..."))
        stats = ingest_vendor_files()
        print(f"Indexed: {stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
