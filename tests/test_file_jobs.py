"""Delete / open one of the user's files, printer status questions, and yes/no offers."""
import pytest
from langgraph.checkpoint.memory import MemorySaver

from agent import graph as graph_module
from agent import runner
from agent.router import fast_route
from agent.specialists import COMPUTER_USE
from tools import fileops, pdfprint, printing


@pytest.fixture
def files(tmp_path, monkeypatch):
    for name in ("RAGAS.txt", "RAGAS.pdf", "setup.exe", "notes.lnk", "Budget 2026.xlsx", "team photo.jpg"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    monkeypatch.setattr(pdfprint, "_folders", lambda: [tmp_path])
    monkeypatch.setattr(pdfprint, "_search_roots", lambda: [(tmp_path, 2)])
    return tmp_path


# --- understanding the request --------------------------------------------------------------------
@pytest.mark.parametrize("text, file", [("can u delete the RAGAS pdf in my desktop", "RAGAS pdf"), ("delete RAGAS.txt", "RAGAS.txt"),
                                        ("remove the team photo", "team photo"), ("bin my budget 2026 sheet", "budget 2026 sheet")])
def test_delete_requests_are_understood(text, file):
    assert COMPUTER_USE.quick_pick(text) == {"task": "delete_file", "file": file, "reason": ""}


@pytest.mark.parametrize("text", ["delete all my files", "uninstall zoom", "delete chrome", "delete my browser history",
                                  "remove the printer", "delete the folder Projects", "how do I delete a file?"])
def test_these_are_not_single_file_deletions(text):
    assert (COMPUTER_USE.quick_pick(text) or {}).get("task") != "delete_file"


def test_a_pdf_mentioned_is_not_a_pdf_to_make():
    assert COMPUTER_USE.quick_pick("can u delete the RAGAS pdf in my desktop")["task"] == "delete_file"
    assert (COMPUTER_USE.quick_pick("email the report pdf to my manager") or {}).get("task") != "save_as_pdf"
    assert COMPUTER_USE.quick_pick("convert the RAGAS document to pdf")["task"] == "save_as_pdf"


def test_open_a_file_only_when_it_exists(files):
    assert COMPUTER_USE.quick_pick("open the RAGAS pdf") == {"task": "open_file", "file": "the RAGAS pdf", "reason": ""}
    assert COMPUTER_USE.quick_pick("open youtube")["task"] == "open_website"


@pytest.mark.parametrize("text", ["can u tell me whether a printer is connected to my system or not", "do I have a printer",
                                  "is any printer installed on this pc"])
def test_printer_status_questions_check_this_computer(text):
    assert printing.is_print_status(text) and not printing.is_print_problem(text)
    assert fast_route(text)["agent"] == "devices"


# --- finding the right file -------------------------------------------------------------------------
def test_the_type_word_picks_the_right_file(files):
    assert pdfprint.resolve_document("the RAGAS pdf", kinds=None).name == "RAGAS.pdf"
    assert pdfprint.resolve_document("my RAGAS text file", kinds=None).name == "RAGAS.txt"


def test_programs_and_shortcuts_are_never_offered(files):
    assert pdfprint.find_documents("setup", kinds=None) == [] and pdfprint.find_documents("notes", kinds=None) == []


def test_two_files_with_the_same_name_are_asked_about(files):
    plan = COMPUTER_USE.plan_delete_file({"file": "RAGAS"})
    assert plan["fix"] is None and "RAGAS.txt" in plan["diagnosis"] and "RAGAS.pdf" in plan["diagnosis"]
    assert "Which one" in plan["diagnosis"]


def test_the_delete_plan_names_the_file_and_the_recycle_bin(files):
    plan = COMPUTER_USE.plan_delete_file({"file": "RAGAS pdf"})
    assert plan["summary"] == "Move RAGAS.pdf to the Recycle Bin" and plan["steps"][0]["args"]["file"].endswith("RAGAS.pdf")
    assert "Recycle Bin, so you can get it back" in plan["ask"]


def test_delete_moves_only_that_file_to_the_recycle_bin(files, monkeypatch):
    gone = []
    monkeypatch.setattr(fileops, "recycle", lambda p: (gone.append(p.name), p.unlink()))
    out = fileops.delete_file(str(files / "RAGAS.pdf"))
    assert out["ok"] and gone == ["RAGAS.pdf"] and (files / "RAGAS.txt").exists()


def test_delete_refuses_programs_and_unknown_files(files, monkeypatch):
    monkeypatch.setattr(fileops, "recycle", lambda p: pytest.fail("must not delete"))
    assert fileops.delete_file(str(files / "setup.exe"))["ok"] is False
    assert fileops.delete_file("nothing like this")["ok"] is False


# --- yes / no offers --------------------------------------------------------------------------------
def _offer_graph(monkeypatch):
    monkeypatch.setattr(graph_module.router, "route", lambda request: {"agent": "devices", "question": ""})
    monkeypatch.setattr(graph_module, "_diagnose_printing", lambda state: {"diagnostics": {}, "proposal": {
        "diagnosis": "No printer is connected to this computer right now.", "fix": "printing_fix", "reason": "", "risk": 1,
        "summary": "Open the printer settings", "offer": True, "ask": "Want me to open the printer settings so you can add one?",
        "what_changes": "x", "steps": [{"tool": "open_settings_page", "args": {"page": "printers"}, "domain": "settings",
                                        "label": "x"}]}})
    monkeypatch.setattr(graph_module, "_run", lambda *a, **k: {"ok": True})
    return graph_module.build_graph(MemorySaver())


def test_an_offer_is_a_yes_no_question_and_no_is_fine(monkeypatch):
    graph = _offer_graph(monkeypatch)
    first = runner.start(graph, "is a printer connected to my system")
    card = first["approval"]
    assert card["style"] == "offer" and card["say"] == "Want me to open the printer settings so you can add one?"
    state = runner.resume(graph, first["task_id"], False)["state"]
    assert state["outcome"] == "chat" and state["report"] == "No problem! Just ask if you need anything else."


def test_an_accepted_offer_is_done_without_a_recheck(monkeypatch):
    graph = _offer_graph(monkeypatch)
    monkeypatch.setattr("agent.specialists.verify", lambda *a, **k: pytest.fail("no re-check for an offer"))
    first = runner.start(graph, "is a printer connected to my system")
    state = runner.resume(graph, first["task_id"], True)["state"]
    assert state["outcome"] == "done" and "Opened the printer settings ✓" in state["report"]
    assert state["basis"] == []                     # no "Steps taken" for a small "opened X"
