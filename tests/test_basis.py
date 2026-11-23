"""The short "Steps taken" summary: rules and sources first, never the list of tools that ran."""
from agent import basis

PRINT = {"odc": "PUNE-ODC-1", "floor": "0", "seat": "G-12", "located_by": "you told Tobi", "computer_type": "avd",
         "sop": "SOP-IT-PRN-005 v1.4", "file": {"name": "plan.pdf", "ext": "pdf", "pages": 3},
         "printers": [{"printer": "PUN1-G-SecurePrint-01", "status": "add_first", "accepts": ["pdf"], "max_pages": 25,
                       "conditions": ["secure release: tap your badge at the printer to collect it"]}]}
SOP = {"results": [{"source": "[SOP-IT-PRN-005 Printing in Pune ODC 1 v1.4 § Approved printers]"}]}


def state(**kw):
    return {"outcome": "no_action", "request": "which printer", "diagnostics": {}, **kw}


def test_printer_answer_leads_with_where_you_are_and_the_rules():
    lines = basis.build(state(diagnostics={"get_my_print_options": PRINT, "get_workplace_sop": SOP}))
    text = "\n".join(lines)
    assert lines[0].startswith("**You:** ") and "floor 0" in lines[0] and "seat G-12" in lines[0] and "you told me" in lines[0]
    assert "**Rule:** allowed printers: PUN1-G-SecurePrint-01 (SOP-IT-PRN-005 v1.4)" in text
    assert "PDF, max 25 pages" in text and "secure release" in text
    assert "**File:** plan.pdf · 3 pages" in text
    assert "**Source:** SOP-IT-PRN-005 v1.4 · Approved printers" in text
    assert "not added here yet" in text
    assert "get_my_print_options" not in text and "tool" not in text.lower()          # no tool names


def test_it_stays_short():
    lines = basis.build(state(diagnostics={"get_my_print_options": PRINT, "get_workplace_sop": SOP}))
    assert len(lines) <= basis.MAX_LINES and all(len(l) <= basis.MAX_CHARS + 20 for l in lines)


def test_refused_printer_shows_why():
    ctx = {**PRINT, "printers": [{"printer": "A-Colour", "status": "not_allowed", "why_not": "only members of A-Colour may use it",
                                   "accepts": ["pdf"]}]}
    assert any("A-Colour not allowed: only members of A-Colour" in l for l in basis.build(state(diagnostics={"get_my_print_options": ctx})))


def test_unknown_odc_is_said_plainly():
    lines = basis.build(state(diagnostics={"get_my_org_context": {"odc": "unknown"}}))
    assert "ODC not known" in lines[0]


def test_network_rules():
    net = {"odc": "PUNE-ODC-1", "located_by": "you told Tobi", "computer_type": "avd", "sop": "SOP-IT-NET-003 v1.0",
           "allowed_wifi": {"corporate": ["PUN1-Secure"], "guest": []}, "vpn_rules": {"when_needed": "Not needed in the ODC."}}
    text = "\n".join(basis.build(state(diagnostics={"get_my_network_options": net})))
    assert "company Wi-Fi: PUN1-Secure; no guest Wi-Fi (SOP-IT-NET-003 v1.0)" in text and "VPN: Not needed" in text
    assert "virtual desktop (AVD): Wi-Fi and VPN are your own PC" in text


def test_knowledge_answers_show_their_source():
    kb = {"results": [{"source": "[network_and_vpn.md § Connect to the VPN]"}]}
    lines = basis.build(state(diagnostics={"search_knowledge_base": kb}))
    assert "**Source:** network_and_vpn.md · Connect to the VPN" in lines


def test_microsoft_learn_and_general_knowledge_sources():
    ms = {"results": [{"source": "[Microsoft Learn: Can't turn on Network Discovery – https://learn.microsoft.com/x/y]"}]}
    assert "**Source:** Microsoft Learn · Can't turn on Network Discovery" in basis.build(state(diagnostics={"search_knowledge_base": ms}))
    assert any("general Windows guidance" in l for l in basis.build(state(proposal={"general": True}, diagnostics={})))


def test_measurements_are_shown_when_no_rule_or_source_explains_the_answer():
    lines = basis.build(state(diagnostics={"get_system_health": {"ok": True}, "get_running_processes": {"ok": True}}))
    assert "**Checked:** CPU and memory, running programs" in lines


def test_results_say_what_changed_and_that_the_user_approved():
    fixed = basis.build(state(outcome="fixed", proposal={"summary": "Clear the print queue"}))
    assert fixed[-1] == "**Result:** Clear the print queue (you approved it first)"
    assert basis.build(state(outcome="rejected"))[-1].endswith("you declined, so nothing was changed")
    assert "nothing was changed" in basis.build(state())[-1]
    assert "blocked by the safety policy" in basis.build(state(outcome="refused", error="Read-only mode"))[-1]
    assert "ticket ITB-0007 opened" in basis.build(state(outcome="escalated", ticket={"ref": "ITB-0007"}))[-1]


def test_follow_ups_show_how_they_were_understood():
    lines = basis.build(state(original_request="close it", request="close claude.exe (PID 9708)"))
    assert lines[0] == "**You said:** “close it” → close claude.exe (PID 9708)"


def test_plain_chat_has_no_steps():
    assert basis.build(state(outcome="chat")) == []


def test_autopilot_history_is_used():
    lines = basis.build({"outcome": "done", "auto_history": [{"tool": "get_disk_usage", "args": {}, "result": {"ok": True}}]})
    assert "**Checked:** disk space" in lines


def test_one_odd_state_never_raises():
    assert isinstance(basis.build({"outcome": "error", "diagnostics": {"x": "not a dict"}}), list)
