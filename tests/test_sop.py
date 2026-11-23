"""SOP knowledge base: ingestion with ODC / version / access tags, ODC-aware search, citations, routing."""
import ipaddress

import pytest

from agent.router import fast_route
from rag import sop_ingest
from rag.retrieval import RetrievalFilters, hybrid_search
from tools import org_context

HYD = """---
sop_id: SOP-T-001
title: Printing in Test ODC A
version: "2.3"
effective_date: 2026-09-01
odc: [ODC-A]
---
# Printing in Test ODC A

## Approved printers

| Printer | Colour |
| --- | --- |
| A-Mono-01 | Black and white |
| A-Colour-02 | Colour |

Colour printing needs the A-Colour group.
"""

PUNE = """---
sop_id: SOP-T-002
title: Printing in Test ODC B
version: "1.0"
odc: ODC-B
---
# Printing in Test ODC B

## Approved printers

Only B-Secure-01 may be used. There is no colour printing in ODC B. PDF files only.
"""

ALL = """---
sop_id: SOP-T-003
title: Temporary files
odc: all
---
# Temporary files

## Cleaning

Temporary files over 1 GB are cleaned only with the user's consent. Downloads are never cleaned.
"""

DRAFT = """---
sop_id: SOP-T-004
title: Draft printing rule
odc: all
status: draft
---
# Draft printing rule

## Printers

Everyone may print in colour on any printer anywhere, this draft rule is not approved yet.
"""

SECRET = """---
sop_id: SOP-T-005
title: Finance printing
odc: all
access_groups: [Finance-Team]
---
# Finance printing

## Cheque printers

Cheque printers are used only by the finance team with dual control.
"""


@pytest.fixture
def sops(tmp_path):
    for name, text in {"a.md": HYD, "b.md": PUNE, "all.md": ALL, "draft.md": DRAFT, "secret.md": SECRET}.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    (tmp_path / "README.md").write_text("# not an SOP", encoding="utf-8")
    stats = sop_ingest.ingest_sop_files(tmp_path)
    assert not stats["errors"] and stats["files_scanned"] == 5
    return tmp_path


def _docs(query, **filters):
    return {r.chunk_id: r for r in hybrid_search(query, RetrievalFilters(doc_types=["sop"], **filters), 10, record=False)}


def test_each_odc_only_sees_its_own_sops(sops):
    a = [r.citation for r in _docs("which printers can I use", odc="ODC-A").values()]
    b = [r.citation for r in _docs("which printers can I use", odc="ODC-B").values()]
    assert any("SOP-T-001" in c for c in a) and not any("SOP-T-002" in c for c in a)
    assert any("SOP-T-002" in c for c in b) and not any("SOP-T-001" in c for c in b)


def test_company_wide_sops_apply_in_every_odc(sops):
    for odc in ("ODC-A", "ODC-B", "SOMEWHERE-ELSE"):
        assert any("SOP-T-003" in r.citation for r in _docs("temporary files cleaning downloads", odc=odc).values())


def test_drafts_are_never_used(sops):
    assert not any("SOP-T-004" in r.citation for r in _docs("print in colour on any printer").values())


def test_restricted_sops_only_reach_their_group(sops):
    assert not any("SOP-T-005" in r.citation for r in _docs("cheque printers finance").values())
    assert any("SOP-T-005" in r.citation for r in _docs("cheque printers finance", acl_groups=["Finance-Team"]).values())


def test_citation_has_sop_id_version_and_section(sops):
    r = next(r for r in _docs("approved printers", odc="ODC-A").values() if "SOP-T-001" in r.citation)
    assert r.citation == "[SOP-T-001 Printing in Test ODC A v2.3 § Approved printers]"
    assert r.region == "|ODC-A|" and r.effective_date == "2026-09-01"


def test_removed_sops_are_deleted_from_the_index(sops):
    (sops / "b.md").unlink()
    assert sop_ingest.ingest_sop_files(sops)["chunks_deleted"] >= 1
    assert not any("SOP-T-002" in r.citation for r in _docs("which printers", odc="ODC-B").values())


def test_sop_without_an_id_is_reported_not_indexed(tmp_path):
    (tmp_path / "bad.md").write_text("---\ntitle: no id\n---\n# x\n\n## y\n\nsome rule text here for the test", encoding="utf-8")
    stats = sop_ingest.ingest_sop_files(tmp_path)
    assert stats["errors"] and stats["chunks_added"] == 0


def test_word_sops_are_read_with_their_side_file(tmp_path):
    docx = pytest.importorskip("docx")
    d = docx.Document()
    d.add_heading("USB devices", level=1)
    d.add_heading("Allowed devices", level=2)
    d.add_paragraph("Only encrypted company USB drives may be used in ODC-A.")
    d.save(tmp_path / "usb.docx")
    (tmp_path / "usb.yaml").write_text("sop_id: SOP-T-010\ntitle: USB devices\nversion: '1.1'\nodc: [ODC-A]\n", encoding="utf-8")
    sop_ingest.ingest_sop_files(tmp_path)
    hits = _docs("encrypted usb drives", odc="ODC-A")
    assert any(r.citation == "[SOP-T-010 USB devices v1.1 § Allowed devices]" for r in hits.values())


def test_odc_list_and_region_tag():
    assert sop_ingest.odc_list("all") == [] and sop_ingest.odc_list(None) == []
    assert sop_ingest.odc_list("A, B") == ["A", "B"] and sop_ingest.odc_list(["A"]) == ["A"]
    assert sop_ingest.region_tag(["A", "B"]) == "|A|B|" and sop_ingest.region_tag([]) == ""


# --- ODC detection ------------------------------------------------------------------------
ODCS = {"ODC-A": {"name": "A", "subnets": ["10.42.16.0/20"], "hostname_prefixes": ["HYDA-"]},
        "ODC-B": {"name": "B", "subnets": ["10.51.0.0/20"], "hostname_prefixes": ["PUNB-"]}}


@pytest.fixture
def odcs(monkeypatch):
    monkeypatch.delenv("ITBUDDY_ODC", raising=False)
    monkeypatch.setattr(org_context, "odc_catalogue", lambda: ODCS)
    monkeypatch.setattr(org_context, "cfg", lambda *a, default=None: default)
    return monkeypatch


def test_odc_from_subnet(odcs):
    odcs.setattr(org_context, "_local_ipv4", lambda: [ipaddress.IPv4Address("10.51.3.7")])
    assert org_context.detect_odc()["odc"] == "ODC-B"


def test_odc_from_computer_name(odcs):
    odcs.setattr(org_context, "_local_ipv4", lambda: [ipaddress.IPv4Address("192.168.1.5")])
    odcs.setenv("COMPUTERNAME", "HYDA-LT-0042")
    assert org_context.detect_odc()["odc"] == "ODC-A"


def test_unknown_odc_is_not_guessed(odcs):
    odcs.setattr(org_context, "_local_ipv4", lambda: [ipaddress.IPv4Address("192.168.1.5")])
    odcs.setenv("COMPUTERNAME", "HOME-PC")
    assert org_context.detect_odc()["odc"] == ""


def test_override_wins(odcs):
    odcs.setenv("ITBUDDY_ODC", "ODC-A")
    assert org_context.detect_odc()["odc"] == "ODC-A"


# --- the tool and routing -----------------------------------------------------------------
def test_lookup_sop_says_when_the_odc_is_unknown(sops, monkeypatch):
    from rag import tools_rag
    monkeypatch.setattr("tools.org_context.detect_odc", lambda: {"odc": "", "name": "", "how": "none"})
    monkeypatch.setattr("tools.org_context.user_groups", lambda: [])
    out = tools_rag.lookup_sop("which printers can I use")
    assert out["your_odc"] == "unknown" and "could not be detected" in out["note"]
    assert {r["applies_to"] for r in out["results"]} >= {"ODC-A", "ODC-B"}


def test_tables_are_compacted_for_the_model():
    from rag.tools_rag import _compact_tables
    out = _compact_tables("Printers:\n\n| Printer | Colour |\n| --- | --- |\n| P1 | Black and white |\n\nNo colour.")
    assert "- Printer: P1; Colour: Black and white" in out and "---" not in out and "No colour." in out


@pytest.mark.parametrize("text", ["what is the SOP for printing?", "which printers can I use in my ODC?",
                                  "can I print a word document in colour?", "is colour printing allowed here?",
                                  "am I allowed to use a USB drive?"])
def test_sop_questions_go_to_the_knowledge_agent(text):
    assert fast_route(text) == {"agent": "howto", "question": ""}


@pytest.mark.parametrize("text", ["I cannot print anything", "my printer is offline", "printing is stuck"])
def test_printing_problems_still_go_to_troubleshooting(text):
    assert fast_route(text)["agent"] == "devices"
