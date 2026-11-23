"""SOP knowledge base: the organisation's Standard Operating Procedures, indexed with who and where they apply to.

Put SOPs in kb_sop/ as Markdown, Word (.docx) or PDF. Each SOP needs its metadata, either as front matter at the top
of a Markdown file or in a side file with the same name and the extension .yaml (for Word and PDF):

    sop_id: SOP-IT-PRN-004          # required, unique
    title: Printing in Hyderabad ODC 2
    version: "3.1"
    effective_date: 2026-09-01
    owner: IT Service Desk
    odc: [HYD-ODC-2]                # or "all" (default): which ODCs it applies to
    department: all
    access_groups: []               # empty = everyone; otherwise only members of these groups see it
    status: approved                # draft SOPs are indexed but never used in answers

Each section (## heading) becomes a searchable chunk with doc_type "sop", the SOP id and version in its citation,
and the ODC list stored so searches return only the rules for the user's ODC.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from appconfig import ROOT
from rag import embed as _embedder
from rag.index import delete_chunk, delete_document, get_conn, get_document_chunks, rebuild_fts

log = logging.getLogger("rag.sop")
SOP_DIR = ROOT / "kb_sop"
_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_SUFFIXES = (".md", ".docx", ".pdf")


def _docx_text(path: Path) -> str:
    """Word -> Markdown: 'Heading 1/2/3' styles become #, ##, ###; tables become '|' rows."""
    import docx
    d = docx.Document(str(path))
    lines = []
    for block in d.element.body.iterchildren():
        tag = block.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = docx.text.paragraph.Paragraph(block, d)
            text = p.text.strip()
            if not text:
                continue
            style = (p.style.name or "").lower() if p.style is not None else ""
            m = re.match(r"heading (\d)", style)
            if style == "title" or (m and m.group(1) == "1"):
                lines.append(f"# {text}")
            elif m:
                lines.append("#" * min(int(m.group(1)), 3) + f" {text}")
            elif "list" in style:
                lines.append(f"- {text}")
            else:
                lines.append(text)
            lines.append("")
        elif tag == "tbl":
            t = docx.table.Table(block, d)
            for row in t.rows:
                lines.append("| " + " | ".join(c.text.strip() for c in row.cells) + " |")
            lines.append("")
    return "\n".join(lines)


def _pdf_text(path: Path) -> str:
    """PDF -> text. Lines that look like numbered headings ("3. Confidential documents") become ## sections."""
    from pypdf import PdfReader
    out = []
    for page in PdfReader(str(path)).pages:
        for line in (page.extract_text() or "").splitlines():
            s = line.strip()
            if re.fullmatch(r"\d{1,2}(\.\d{1,2})?\.?\s+[A-Z][^.]{2,70}", s):
                out += ["", f"## {s}", ""]
            else:
                out.append(s)
    return "\n".join(out)


def read_sop(path: Path) -> tuple[dict, str]:
    """(metadata, markdown text) for one SOP file. Raises ValueError when the metadata is missing or wrong."""
    meta: dict = {}
    if path.suffix.lower() == ".md":
        text = path.read_text(encoding="utf-8", errors="replace")
        m = _FRONT.match(text)
        if m:
            meta = yaml.safe_load(m.group(1)) or {}
            text = text[m.end():]
    else:
        side = path.with_suffix(".yaml")
        if side.exists():
            meta = yaml.safe_load(side.read_text(encoding="utf-8")) or {}
        text = _docx_text(path) if path.suffix.lower() == ".docx" else _pdf_text(path)
    if not isinstance(meta, dict) or not str(meta.get("sop_id") or "").strip():
        raise ValueError(f"{path.name}: missing 'sop_id' (front matter, or a {path.stem}.yaml side file)")
    if not re.search(r"^# ", text, re.MULTILINE):
        text = f"# {meta.get('title') or meta['sop_id']}\n\n{text}"
    return meta, text


def odc_list(value) -> list[str]:
    if value in (None, "", "all", "ALL", ["all"]):
        return []
    items = value if isinstance(value, list) else re.split(r"[,;]\s*", str(value))
    return [str(v).strip() for v in items if str(v).strip() and str(v).strip().lower() != "all"]


def region_tag(odcs: list[str]) -> str:
    """Stored form of the ODC list: '|HYD-ODC-2|PUNE-ODC-1|' (exact-match friendly), '' = every ODC."""
    return "|" + "|".join(odcs) + "|" if odcs else ""


def parse_sop(path: Path):
    from rag.ingest import parse_markdown_file
    meta, text = read_sop(path)
    sop_id = str(meta["sop_id"]).strip()
    version = str(meta.get("version") or "1")
    effective = str(meta.get("effective_date") or "")
    odcs = odc_list(meta.get("odc"))
    title = str(meta.get("title") or sop_id)
    chunks = parse_markdown_file(path, doc_id=f"sop/{sop_id}", base_url=f"sop/{sop_id}", source_system="sop",
                                 trust=1.0, doc_type="sop", text=text)
    for c in chunks:
        c.title = f"{sop_id} {title}"
        c.version = version
        c.effective_date = effective
        c.last_reviewed = effective or c.last_reviewed
        c.owner = str(meta.get("owner") or "")
        c.department = str(meta.get("department") or "all")
        c.region = region_tag(odcs)
        c.acl_groups = [str(g) for g in (meta.get("access_groups") or [])]
        c.status = "approved" if str(meta.get("status") or "approved").lower() == "approved" else "draft"
        c.audience = "end_user"
        applies = ", ".join(odcs) if odcs else "all ODCs"
        # the scope goes into the searchable text, so "printing in HYD-ODC-2" matches the right SOP
        c.text = f"[SOP {sop_id} v{version} | applies to: {applies}]\n" + c.text
    return sop_id, chunks


def ingest_sop_files(sop_dir: Path | None = None, force: bool = False) -> dict:
    """Index every SOP in kb_sop/. Unchanged sections are skipped; sections and SOPs that were removed are deleted."""
    from rag.ingest import _upsert_with_embedding
    sop_dir = sop_dir or SOP_DIR
    stats = {"files_scanned": 0, "chunks_added": 0, "chunks_skipped": 0, "chunks_deleted": 0, "errors": []}
    if not sop_dir.exists():
        return stats
    dense = _embedder.dense_enabled()
    present: set[str] = set()
    for path in sorted(p for p in sop_dir.rglob("*") if p.suffix.lower() in _SUFFIXES):
        if path.name.upper().startswith("README"):
            continue
        stats["files_scanned"] += 1
        try:
            sop_id, chunks = parse_sop(path)
        except Exception as e:                       # one broken SOP must not stop the others
            stats["errors"].append(str(e)[:200])
            log.warning("SOP skipped: %s", e)
            continue
        doc_id = f"sop/{sop_id}"
        present.add(doc_id)
        existing = {c.chunk_id: c for c in get_document_chunks(doc_id)}
        todo = []
        for chunk in chunks:
            old = existing.get(chunk.chunk_id)
            if (not force and old is not None and old.text == chunk.text and old.version == chunk.version
                    and old.region == chunk.region and old.status == chunk.status
                    and list(old.acl_groups or []) == list(chunk.acl_groups or [])
                    and (old.embedding is not None or not dense)):
                stats["chunks_skipped"] += 1
                continue
            todo.append(chunk)
        _upsert_with_embedding(todo)
        stats["chunks_added"] += len(todo)
        new_ids = {c.chunk_id for c in chunks}
        for old_id in existing:
            if old_id not in new_ids:
                delete_chunk(old_id)
                stats["chunks_deleted"] += 1
    for row in get_conn().execute("SELECT DISTINCT doc_id FROM chunks WHERE doc_id LIKE 'sop/%'").fetchall():
        if row[0] not in present:
            stats["chunks_deleted"] += delete_document(row[0])
    if stats["chunks_added"] or stats["chunks_deleted"]:
        rebuild_fts()
    return stats
