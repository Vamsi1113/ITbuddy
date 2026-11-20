"""Import Microsoft's Windows troubleshooting library (Microsoft Learn) into Tobi's knowledge base.

Source: the public GitHub repository MicrosoftDocs/SupportArticles-docs, folder support/windows-client
(the articles behind https://learn.microsoft.com/troubleshoot/windows-client/). The text is licensed
CC BY 4.0, which allows reuse with attribution: every imported file keeps a link to its original page, answers cite
that page, and kb_vendor/microsoft_learn/NOTICE.md records the licence.

    python scripts/import_mslearn.py                  # import or refresh the default areas, then index them
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
(https://learn.microsoft.com/troubleshoot/windows-client/), published in the GitHub repository
MicrosoftDocs/SupportArticles-docs under the Creative Commons Attribution 4.0 International licence
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
                out.append({"path": p, "rel": rel, "area": area})
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
    url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{article['path']}"
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
    target = OUT / f"{rel}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    text = (f"<!-- source: {LEARN}{rel} -->\n# {title or rel.split('/')[-1].replace('-', ' ')}\n\n"
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
    args = ap.parse_args()

    articles = list_articles()
    if args.list:
        for area, n in Counter(a["area"] for a in articles).most_common():
            print(f"{area:45} {n}")
        return 0
    if args.areas:
        articles = [a for a in articles if a["area"] in set(args.areas)]
    print(f"Downloading {len(articles)} articles from {REPO} ...")
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
        for old in OUT.rglob("*.md"):
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
