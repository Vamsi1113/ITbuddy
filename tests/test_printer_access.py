"""Printer questions by intent: access to another ODC's printer (rules, request, email, own options), and no
approval card or troubleshooting for a question that only mentions the word "printer"."""
import pytest
from langgraph.checkpoint.memory import MemorySaver

from agent import graph as graph_module
from agent import runner, specialists
from agent.router import fast_route
from tools import org_context, org_rules, printing

ODCS = {
    "ODC-A": {"name": "Office A", "aliases": ["odc a", "block a"], "devices": ["A-Scan-1 (scanner)"],
              "printers": [{"name": "A-Mono-1", "queue": "\\\\srv\\A-Mono-1", "floor": "3", "location": "3rd floor",
                            "accepts": ["pdf"]}],
              "outside_printer_access": {"mode": "request", "email": "it-a@example.com"}},
    "ODC-B": {"name": "Office B", "aliases": ["odc b", "side block", "block b"],
              "printers": [{"name": "B-Secure-1", "queue": "\\\\srv\\B-Secure-1", "floor": "0"}],
              "outside_printer_access": {"mode": "not_possible", "note": "Client-dedicated: no outside access."}},
    "ODC-C": {"name": "Office C", "aliases": ["odc c"], "printers": [{"name": "C-1", "floor": "1"}]},
}
POLICY = {"default": "request", "request_portal": "ServiceNow > Printer access", "request_email": "it-printing@example.com",
          "approvers": "your manager and that ODC's IT", "turnaround": "2 working days", "sop": "SOP-P-6 v1.0"}


def fake_cfg(*keys, default=None):
    node = {"organisation": {"odcs": ODCS, "printer_access": POLICY}}
    for k in keys:
        if not isinstance(node, dict) or k not in node:
            return default
        node = node[k]
    return node


@pytest.fixture(autouse=True)
def rules(monkeypatch, tmp_path):
    monkeypatch.setattr(org_rules, "cfg", fake_cfg)
    monkeypatch.setattr(org_rules, "odc_info", lambda odc: ODCS.get(odc) or {})
    monkeypatch.setattr(org_context, "odc_catalogue", lambda: ODCS)
    monkeypatch.setattr(org_context, "PROFILE_FILE", tmp_path / "profile.json")
    monkeypatch.setattr(org_context, "seat_table", lambda: [])
    monkeypatch.setattr(org_context, "user_groups", lambda: [])
    monkeypatch.setattr(org_context, "environment", lambda: {"kind": "physical", "computer": "PC", "client_name": "",
                                                             "client_ip": "", "remote": False})
    monkeypatch.setattr(org_context, "_local_ipv4", lambda: [])
    monkeypatch.setattr(org_context, "network_state", lambda: {"ips": [], "wifi": {"connected": False, "ssid": "", "signal": ""},
                                                               "vpn": {"connected": False, "adapters": []}})
    monkeypatch.setattr(org_rules, "installed_printers", lambda: [])


def at(odc, floor="3", seat="3-B-1"):
    org_context.set_my_location(odc, floor, seat)


# --- routing by intent ------------------------------------------------------------------------
@pytest.mark.parametrize("text", [
    "I want to use side blocks ODC 'B''s printer, how to do it", "can I use the printer in the other building",
    "use ODC B printer", "which printer should I use", "can I print on the 5th floor printer",
    "ok raise it, the reason is project Falcon", "raise a printer access request for ODC B"])
def test_printer_questions_go_to_the_rules_agent(text):
    assert fast_route(text)["agent"] == "workplace"


@pytest.mark.parametrize("text", ["my printer is offline", "I cannot print anything", "printing is slow", "toner is low",
                                  "the printer shows an error", "documents are stuck in the print queue", "printer won't print"])
def test_real_printing_problems_still_get_troubleshooting(text):
    assert printing.is_print_problem(text) and fast_route(text)["agent"] == "devices"


@pytest.mark.parametrize("text", ["I want to use the printer", "which printer should I use", "use ODC B printer",
                                  "I want to print a document"])
def test_naming_a_printer_is_not_a_problem(text):
    assert not printing.is_print_problem(text)


def test_a_model_choice_of_devices_is_corrected_for_a_non_problem(monkeypatch):
    monkeypatch.setattr(graph_module.router, "route", lambda request: {"agent": "devices", "question": ""})
    seen = {}
    monkeypatch.setattr(graph_module, "_diagnose", lambda state, domain: seen.update(agent=domain.name) or {"outcome": "no_action"})
    runner.start(graph_module.build_graph(MemorySaver()), "I want to print this document on the printer")
    assert seen["agent"] == "workplace"


# --- the ODC a user means ---------------------------------------------------------------------
@pytest.mark.parametrize("text, odc", [("ODC 'B''s printer", "ODC-B"), ("the side block printer", "ODC-B"), ("use Office C", "ODC-C"),
                                       ("block A", "ODC-A"), ("a printer somewhere", "")])
def test_the_odc_is_found_from_the_users_words(text, odc):
    assert org_rules.resolve_odc(text) == odc


# --- the rules ---------------------------------------------------------------------------------
def test_other_odc_needs_a_request_and_comes_with_an_email_and_own_options():
    at("ODC-C")                                                 # the rule belongs to the ODC whose printer is wanted (A)
    out = org_rules.printer_access_rules("I want to use ODC A's printer")
    assert out["access"] == "request_required" and out["target_odc"] == "ODC-A" and out["sop"] == "SOP-P-6 v1.0"
    assert out["how_to_request"][0].startswith("Raise a request: ServiceNow")
    assert out["email"]["to"] == "it-a@example.com" and "Office C" in out["email"]["body"] and "A-Mono-1" in out["email"]["body"]
    assert "use_instead" in out


def test_an_odc_can_refuse_outside_use_completely():
    at("ODC-A")
    out = org_rules.printer_access_rules("ODC B printer")
    assert out["access"] == "not_possible" and "Client-dedicated" in out["why"] and "email" not in out
    assert out["other_devices"] == ["A-Scan-1 (scanner)"]


def test_the_users_own_odc_is_not_an_access_question():
    at("ODC-A")
    assert org_rules.printer_access_rules("odc a printer")["access"] == "same_odc"


def test_unknown_odcs_are_asked_not_guessed():
    out = org_rules.printer_access_rules("ODC B printer")
    assert out["odc"] == "unknown" and out["target_odc"] == "ODC-B" and "own ODC is not known" in out["note"]
    at("ODC-A")
    assert org_rules.printer_access_rules("a printer in another place")["target_odc"] == "unknown"


def test_a_request_creates_a_ticket_with_everything_in_it(monkeypatch):
    at("ODC-C", "2", "2-A-9")
    made = {}
    monkeypatch.setattr("tools.tickets.create_ticket",
                        lambda title, summary, **kw: made.update(title=title, summary=summary, **kw) or {"ref": "ITB-0042"})
    out = org_rules.request_printer_access("ODC A", "project Falcon")
    assert out["ok"] and out["ticket"] == "ITB-0042"
    assert made["category"] == "access_request" and "project Falcon" in made["summary"] and "seat 2-A-9" in made["summary"]


def test_a_request_is_refused_when_it_cannot_be_granted(monkeypatch):
    monkeypatch.setattr("tools.tickets.create_ticket", lambda *a, **k: pytest.fail("no ticket for this"))
    at("ODC-A")
    assert "no outside access" in org_rules.request_printer_access("ODC B", "x")["error"].lower()
    assert "own ODC" in org_rules.request_printer_access("ODC A", "x")["error"]
    assert org_rules.request_printer_access("nowhere", "x")["ok"] is False
    org_context.PROFILE_FILE.unlink()
    assert "do not know which ODC" in org_rules.request_printer_access("ODC A", "x")["error"]


# --- the answer ---------------------------------------------------------------------------------
def test_the_answer_has_the_rule_the_steps_the_email_and_what_to_use_meanwhile():
    at("ODC-C")
    text = specialists.access_proposal(org_rules.printer_access_rules("ODC A printer"))["diagnosis"]
    assert "Office A printers" in text and "SOP-P-6 v1.0" in text and "**How to get access**" in text
    assert "> **Subject:** Printer access request: Office A" in text and "it-a@example.com" in text
    assert "**Use these meanwhile (your own ODC)**" in text and "C-1" in text
    assert "raise it" in text


def test_the_answer_for_a_refusing_odc_offers_no_request():
    at("ODC-A")
    text = specialists.access_proposal(org_rules.printer_access_rules("ODC B printer"))["diagnosis"]
    assert "Client-dedicated" in text and "How to get access" not in text and "raise it" not in text
    assert "A-Mono-1" in text and "A-Scan-1" in text


def test_the_answer_asks_for_the_users_odc():
    text = specialists.access_proposal(org_rules.printer_access_rules("ODC B printer"))["diagnosis"]
    assert "could not tell which ODC you sit in" in text


def test_whole_graph_answers_from_the_rules_without_asking_for_approval(monkeypatch):
    at("ODC-C")
    monkeypatch.setattr(graph_module.router, "route", lambda request: {"agent": "workplace", "question": ""})
    monkeypatch.setattr("agent.specialists.ask_json", lambda *a, **k: pytest.fail("the model must not write this answer"))
    result = runner.start(graph_module.build_graph(MemorySaver()), "I want to use ODC A's printer, how do I do it")
    assert result["status"] == "done"
    state = result["state"]
    assert state["outcome"] == "no_action" and "Office A printers" in state["report"]
    assert any(l.startswith("**Rule:** Office A printers are for that ODC") for l in state["basis"])


# --- no printer: a short answer and a yes / no offer, not a big approval card ---------------------
def test_no_printer_installed_gives_a_short_answer_and_a_yes_no_offer():
    state = {"printers": [{"Name": "Microsoft Print to PDF", "PortName": "PORTPROMPT:"}], "spooler": "Running", "jobs": [], "ports": [],
             "events": [], "admin": False}
    proposal = specialists.print_proposal({"findings": printing.analyse(state), "state": state, "file_name": ""})
    assert proposal["offer"] is True and proposal["ask"] == "Want me to open the printer settings so you can add one?"
    assert proposal["diagnosis"].startswith("No printer is connected to this computer right now")
    assert len(proposal["diagnosis"]) < 300 and "What you need to do" not in proposal["diagnosis"]
