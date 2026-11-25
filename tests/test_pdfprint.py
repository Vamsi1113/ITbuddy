"""Save a document as a PDF with the virtual printer: finding the file from loose words, the request, the safety."""
import subprocess

import pytest

from agent import basis
from agent.router import fast_route
from agent.specialists import COMPUTER_USE
from tools import pdfprint


@pytest.fixture
def docs(tmp_path, monkeypatch):
    for name in ("itbuddy test note.txt", "Quarterly Plan.docx", "Quarterly Report.docx", "holiday photo.png", "setup.exe",
                 "already.pdf", "Api keys.txt"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    monkeypatch.setattr(pdfprint, "_folders", lambda: [tmp_path])
    monkeypatch.setattr(pdfprint, "_search_roots", lambda: [(tmp_path, 2)])      # never the real profile or drives
    return tmp_path


@pytest.mark.parametrize("words, expected", [
    ("my itbuddy test note", "itbuddy test note.txt"), ("itbuddy test note documnet", "itbuddy test note.txt"),
    ("the itbuddy note", "itbuddy test note.txt"), ("ITBUDDY TEST NOTE.TXT", "itbuddy test note.txt"),
    ("quarterly plan", "Quarterly Plan.docx"), ("holiday foto", "holiday photo.png")])
def test_the_document_is_found_from_loose_words(docs, words, expected):
    assert pdfprint.resolve_document(words).name == expected


def test_nothing_or_too_many_matches_are_not_guessed(docs):
    assert pdfprint.resolve_document("budget forecast") is None
    assert pdfprint.resolve_document("quarterly") is None                  # plan or report: the user must say which
    assert {p.name for p in pdfprint.find_documents("quarterly")} == {"Quarterly Plan.docx", "Quarterly Report.docx"}
    assert pdfprint.resolve_document("setup") is None                      # programs are never converted


@pytest.mark.parametrize("text, file, folder", [
    ("can u convert my itbuddy test note to a pdf by using my printer option", "itbuddy test note", ""),
    ("use my virtual printer to save my itbuddy test note documnet in desktop as a pdf", "itbuddy test note", "Desktop"),
    ("save my report as pdf", "report", ""), ("export the quarterly plan.docx to pdf in documents", "quarterly plan.docx", "Documents"),
    ("make a pdf of my itbuddy test note", "itbuddy test note", ""), ("print holiday photo.png to pdf", "holiday photo.png", "")])
def test_pdf_requests_are_recognised(text, file, folder):
    pick = COMPUTER_USE.quick_pick(text)
    assert pick == {"task": "save_as_pdf", "file": file, "folder": folder, "reason": ""}
    assert fast_route(text)["agent"] == "computer_use"                       # not the printer troubleshooter


@pytest.mark.parametrize("text", ["how do I save as pdf?", "what is a pdf", "my printer is offline", "print my itbuddy test note",
                                  "I cannot print anything"])
def test_questions_and_printer_problems_are_not_pdf_requests(text):
    assert not (COMPUTER_USE.quick_pick(text) or {}).get("task") == "save_as_pdf"


def test_the_plan_names_the_file_the_printer_and_the_result(docs, monkeypatch):
    monkeypatch.setattr(pdfprint, "pdf_printer_installed", lambda: True)
    monkeypatch.setattr(pdfprint, "folder_path", lambda name: docs)
    plan = COMPUTER_USE.plan_save_as_pdf({"file": "my itbuddy test note", "folder": ""})
    assert plan["fix"] == "computer_use_task" and plan["risk"] == 1
    assert "itbuddy test note.txt" in plan["summary"] and "Microsoft Print to PDF" in plan["what_changes"]
    assert "nothing is printed" in plan["what_changes"].lower() or "nothing is printed on paper" in plan["what_changes"]
    assert plan["expected_file"].endswith("itbuddy test note.pdf")
    step = plan["steps"][0]
    assert step["tool"] == "save_as_pdf" and step["args"]["name"] == "itbuddy test note"


@pytest.mark.parametrize("choice, text", [({"file": "budget forecast"}, "couldn't find"), ({"file": "quarterly"}, "a few files"),
                                          ({"file": "already"}, "already a PDF"), ({"file": "setup"}, "couldn't find")])
def test_the_plan_explains_instead_of_guessing(docs, monkeypatch, choice, text):
    monkeypatch.setattr(pdfprint, "pdf_printer_installed", lambda: True)
    plan = COMPUTER_USE.plan_save_as_pdf({"folder": "", **choice})
    assert plan["fix"] is None and text in plan["diagnosis"]


def test_missing_pdf_printer_is_reported(docs, monkeypatch):
    monkeypatch.setattr(pdfprint, "pdf_printer_installed", lambda: False)
    assert "not installed" in COMPUTER_USE.plan_save_as_pdf({"file": "itbuddy test note", "folder": ""})["diagnosis"]


def test_the_tool_types_the_path_and_saves_without_overwriting(docs, monkeypatch):
    monkeypatch.setattr(pdfprint, "pdf_printer_installed", lambda: True)
    monkeypatch.setattr(pdfprint, "folder_path", lambda name: docs)
    (docs / "itbuddy test note.pdf").write_bytes(b"%PDF old")                  # an earlier PDF must stay untouched
    sent = {}

    class P:
        def poll(self):
            return None

        def kill(self):
            pass

    monkeypatch.setattr(pdfprint, "_launch", lambda source: P())
    monkeypatch.setattr(pdfprint, "_save_window", lambda timeout: 1234)

    def fill(dlg, target):
        sent["target"] = target
        target.write_bytes(b"%PDF-1.7 new content")                          # what the PDF writer would do

    monkeypatch.setattr(pdfprint, "_fill_save_window", fill)
    monkeypatch.setattr(pdfprint.time, "sleep", lambda s: None)
    out = pdfprint.save_as_pdf("my itbuddy test note", "", "Desktop")
    assert out["ok"] and out["file_name"] == "itbuddy test note (2).pdf" and sent["target"].name == "itbuddy test note (2).pdf"
    assert (docs / "itbuddy test note.pdf").read_bytes() == b"%PDF old"


def test_the_tool_reports_a_missing_save_window(docs, monkeypatch):
    monkeypatch.setattr(pdfprint, "pdf_printer_installed", lambda: True)
    monkeypatch.setattr(pdfprint, "_launch", lambda source: None)
    monkeypatch.setattr(pdfprint, "_save_window", lambda timeout: 0)
    out = pdfprint.save_as_pdf("itbuddy test note")
    assert out["ok"] is False and "Ctrl+P" in out["error"]


def test_the_tool_refuses_what_it_should_not_convert(docs, monkeypatch):
    monkeypatch.setattr(pdfprint, "pdf_printer_installed", lambda: True)
    assert "already a PDF" in pdfprint.save_as_pdf("already")["error"]
    assert pdfprint.save_as_pdf("setup")["ok"] is False
    assert pdfprint.save_as_pdf("nothing like it")["ok"] is False


def test_the_steps_taken_summary_says_what_became_what():
    state = {"outcome": "fixed", "proposal": {"summary": "Save a.txt as a PDF in Desktop"},
             "fix_results": [{"ok": True, "saved_as": "C:/u/Desktop/a.pdf", "from": "a.txt", "file_name": "a.pdf", "folder": "C:/u/Desktop"}]}
    lines = basis.build(state)
    assert "**File:** a.txt → a.pdf (Desktop)" in lines
    assert any("nothing printed on paper" in l for l in lines) and lines[-1].startswith("**Result:**")


def test_the_save_window_wording_is_allowed_by_the_policy():
    from safety.policy import _window_allowed
    assert _window_allowed("Save Print Output As")


# --- wider search, loose wording, friendly replies -------------------------------------------------
def test_files_beyond_the_usual_folders_are_found_but_nearer_ones_win(tmp_path, monkeypatch):
    usual, home = tmp_path / "Desktop", tmp_path / "home"
    deep = home / "Projects" / "2026" / "notes"
    usual.mkdir(); deep.mkdir(parents=True)
    (deep / "quarterly probe notes.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(pdfprint, "_folders", lambda: [usual])
    monkeypatch.setattr(pdfprint, "_search_roots", lambda: [(usual, 2), (home, 5)])
    assert pdfprint.resolve_document("my quarterly probe notes").parent == deep
    (usual / "quarterly probe notes.txt").write_text("x", encoding="utf-8")
    assert pdfprint.resolve_document("my quarterly probe notes").parent == usual        # the nearer copy is used


def test_system_and_program_folders_are_never_searched(tmp_path, monkeypatch):
    for d in ("Windows", "AppData", "node_modules", ".git"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "secret plan.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(pdfprint, "_folders", lambda: [])
    monkeypatch.setattr(pdfprint, "_search_roots", lambda: [(tmp_path, 4)])
    assert pdfprint.find_documents("secret plan") == []


def test_a_full_path_is_used_as_it_is(docs):
    assert pdfprint.resolve_document(str(docs / "holiday photo.png")).name == "holiday photo.png"


@pytest.mark.parametrize("text, file, folder", [
    ("can u print the RAGAS document there in my destop using my printer service and save it in desktop", "RAGAS", "Desktop"),
    ("can u print the RAGAS.txt file which is there in my destop using my printer service and save it in desktop", "RAGAS.txt", "Desktop"),
    ("print my budget sheet and save it in documnets", "budget sheet", "Documents")])
def test_printing_into_a_folder_means_a_pdf_even_without_the_word_pdf(text, file, folder):
    pick = COMPUTER_USE.quick_pick(text)
    assert pick["task"] == "save_as_pdf" and pick["file"].lower() == file.lower() and pick["folder"] == folder


@pytest.mark.parametrize("text", ["print Q3 report.pdf", "print my report on the HYD printer", "save the budget sheet in documents"])
def test_a_real_print_or_a_plain_save_is_not_a_pdf_request(text):
    assert (COMPUTER_USE.quick_pick(text) or {}).get("task") != "save_as_pdf"


def test_a_failed_fill_cancels_the_print_and_its_window(docs, monkeypatch):
    monkeypatch.setattr(pdfprint, "pdf_printer_installed", lambda: True)
    stopped = []

    class P:
        def poll(self):
            return None

    monkeypatch.setattr(pdfprint, "_launch", lambda source: P())
    monkeypatch.setattr(pdfprint, "_save_window", lambda timeout: 77)
    monkeypatch.setattr(pdfprint, "_fill_save_window", lambda dlg, target: (_ for _ in ()).throw(RuntimeError("no box")))
    monkeypatch.setattr(pdfprint, "_stop", lambda proc, dlg=0: stopped.append(dlg))
    out = pdfprint.save_as_pdf("itbuddy test note")
    assert out["ok"] is False and stopped == [77]


def test_friendly_wording():
    from agent import voice
    assert "save RAGAS.txt as a PDF on your Desktop" in voice.offer("Save RAGAS.txt as a PDF in Desktop")
    assert "Saved RAGAS.txt as a PDF on your Desktop ✓" in voice.done("Save RAGAS.txt as a PDF in Desktop", "The file was saved: C:/x.pdf")
    assert "close chrome.exe" in voice.offer("Close chrome.exe (PID 1)")
    lines = [voice.offer("Open Notepad") for _ in range(4)]
    assert len(set(lines)) == 4 and all(a != b for a, b in zip(lines, lines[1:]))     # never the same line twice in a row
    assert "nothing was changed" in voice.declined()
    assert voice.failed("Open the VPN app", "it is not installed").startswith("I tried to open the VPN app, but it didn't work out.")


def test_a_failed_computer_task_does_not_open_an_it_ticket(monkeypatch):
    from langgraph.checkpoint.memory import MemorySaver

    from agent import graph as graph_module
    from agent import runner
    monkeypatch.setattr(graph_module.router, "route", lambda request: {"agent": "computer_use", "question": ""})
    monkeypatch.setattr(graph_module, "_diagnose_computer_use", lambda state: {"diagnostics": {}, "proposal": {
        "diagnosis": "Found it.", "fix": "computer_use_task", "reason": "", "risk": 1, "summary": "Save a.txt as a PDF in Desktop",
        "what_changes": "x", "steps": [{"tool": "save_as_pdf", "args": {"file": "a"}, "domain": "computer_use", "label": "x"}],
        "expected_file": "C:/nowhere/a.pdf"}})
    monkeypatch.setattr(graph_module, "_run", lambda *a, **k: {"ok": False, "error": "The Save window did not appear"})
    opened = []
    monkeypatch.setattr(graph_module, "_open_ticket", lambda *a, **k: opened.append(1) or {"ref": "X"})
    graph = graph_module.build_graph(MemorySaver())
    first = runner.start(graph, "convert a.txt to pdf")
    card = first["approval"]
    assert "save a.txt as a PDF on your Desktop" in card["say"]
    state = runner.resume(graph, first["task_id"], True)["state"]
    assert state["outcome"] == "not_fixed" and opened == []
    assert state["report"].startswith("I tried to save a.txt as a PDF on your Desktop, but it didn't work out.")
