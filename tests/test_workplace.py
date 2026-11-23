"""Workplace rules: kind of computer, ODC / floor / seat, printer and network options per ODC, approval-gated print."""
import ipaddress

import pytest

from agent.router import fast_route
from agent.specialists import route_workplace
from tools import org_context, org_rules

ODCS = {
    "ODC-A": {"name": "Office A", "subnets": ["10.1.0.0/16"], "floors": {"3": ["10.1.3.0/24"]}, "hostname_prefixes": ["AAA-"],
              "groups": ["A-Staff"], "printing_sop": "SOP-P-1",
              "printers": [
                  {"name": "A-Mono-1", "queue": "\\\\srv\\A-Mono-1", "floor": "3", "colour": False,
                   "accepts": ["pdf", "docx"], "max_pages": 10, "secure_release": True},
                  {"name": "A-Colour-2", "queue": "\\\\srv\\A-Colour-2", "floor": "4", "colour": True,
                   "accepts": ["pdf"], "allowed_groups": ["A-Colour"]},
                  {"name": "A-Mono-5", "queue": "\\\\srv\\A-Mono-5", "floor": "5", "accepts": ["pdf"]}],
              "wifi": {"corporate": ["A-Corp"], "guest": ["A-Guest"]},
              "vpn": {"client": "GP", "when_needed": "Only outside the office."}},
    "ODC-B": {"name": "Office B", "subnets": ["10.2.0.0/16"], "hostname_prefixes": ["BBB-"], "printers": []},
}


@pytest.fixture(autouse=True)
def _config(monkeypatch, tmp_path):
    monkeypatch.delenv("ITBUDDY_ODC", raising=False)
    monkeypatch.setattr(org_context, "odc_catalogue", lambda: ODCS)
    monkeypatch.setattr(org_rules, "odc_info", lambda odc: ODCS.get(odc) or {})
    monkeypatch.setattr(org_context, "PROFILE_FILE", tmp_path / "org_profile.json")
    monkeypatch.setattr(org_context, "seat_table", lambda: [
        {"computer": "AAA-LT-1", "odc": "ODC-A", "floor": "3", "seat": "3-B-17"},
        {"computer": "USER-PC-9", "odc": "ODC-B", "floor": "1", "seat": "1-A-2"}])
    monkeypatch.setattr(org_context, "cfg", lambda *a, default=None: default)
    monkeypatch.setattr(org_context, "user_groups", lambda: [])
    monkeypatch.setattr(org_context, "_local_ipv4", lambda: [])


def env(kind="physical", computer="X", client_name="", client_ip=""):
    return {"kind": kind, "computer": computer, "client_name": client_name, "client_ip": client_ip, "remote": kind != "physical"}


# --- where the user is ------------------------------------------------------------------------
def test_odc_and_floor_from_this_pcs_network(monkeypatch):
    monkeypatch.setattr(org_context, "_local_ipv4", lambda: [ipaddress.IPv4Address("10.1.3.44")])
    loc = org_context.detect_location(env())
    assert (loc["odc"], loc["floor"]) == ("ODC-A", "3")


def test_in_avd_the_remote_pcs_ip_is_used_not_the_cloud_hosts(monkeypatch):
    monkeypatch.setattr(org_context, "_local_ipv4", lambda: [ipaddress.IPv4Address("10.1.3.44")])    # the cloud host
    assert org_context.detect_location(env("avd"))["odc"] == ""
    assert org_context.detect_location(env("avd", client_ip="10.2.5.5"))["odc"] == "ODC-B"


def test_seat_table_matches_the_remote_pc_name():
    loc = org_context.detect_location(env("avd", computer="AVD-123", client_name="USER-PC-9"))
    assert (loc["odc"], loc["seat"], loc["floor"]) == ("ODC-B", "1-A-2", "1")


def test_computer_name_prefix_and_group(monkeypatch):
    assert org_context.detect_location(env(computer="AAA-LT-77"))["odc"] == "ODC-A"
    monkeypatch.setattr(org_context, "user_groups", lambda: ["B-Group", "Everyone"])
    ODCS["ODC-B"]["groups"] = ["B-Group"]
    try:
        assert org_context.detect_location(env(computer="HOME-PC"))["odc"] == "ODC-B"
    finally:
        ODCS["ODC-B"].pop("groups")


def test_unknown_location_is_not_guessed():
    assert org_context.detect_location(env(computer="HOME-PC"))["odc"] == ""


def test_what_the_user_told_tobi_is_remembered(monkeypatch):
    out = org_context.set_my_location("odc-a", "3", "3-B-17")
    assert out["ok"] and out["saved"]["odc"] == "ODC-A"
    loc = org_context.detect_location(env("avd"))
    assert (loc["odc"], loc["seat"], loc["how"]) == ("ODC-A", "3-B-17", "you told Tobi")
    assert org_context.set_my_location("NOWHERE")["ok"] is False


def test_override_beats_everything(monkeypatch):
    org_context.set_my_location("ODC-A")
    monkeypatch.setenv("ITBUDDY_ODC", "ODC-B")
    assert org_context.detect_location(env())["odc"] == "ODC-B"


# --- printers ---------------------------------------------------------------------------------
INSTALLED = [{"Name": "A-Mono-1", "WorkOffline": False, "PrinterStatus": 3, "PortName": "IP_10.1.3.9"},
             {"Name": "\\\\srv\\A-Mono-5 (redirected 2)", "WorkOffline": True, "PortName": "TS001"},
             {"Name": "Microsoft Print to PDF", "PortName": "PORTPROMPT:"}]


@pytest.fixture
def at_a(monkeypatch):
    org_context.set_my_location("ODC-A", "3", "3-B-17")
    monkeypatch.setattr(org_rules, "installed_printers", lambda: INSTALLED)
    monkeypatch.setattr(org_context, "environment", lambda: env("physical"))
    monkeypatch.setattr(org_context, "network_state",
                        lambda: {"ips": [], "wifi": {"connected": True, "ssid": "A-Guest", "signal": "90%"},
                                 "vpn": {"connected": False, "adapters": []}})


def _by_name(out):
    return {r["printer"]: r for r in out["printers"]}


def test_printer_statuses_for_the_users_odc(at_a):
    rows = _by_name(org_rules.print_options())
    assert rows["A-Mono-1"]["status"] == "ready" and rows["A-Mono-1"]["on_your_floor"]
    assert rows["A-Mono-5"]["status"] == "offline"                       # installed as a redirected queue, but offline
    assert rows["A-Colour-2"]["status"] == "not_allowed" and "A-Colour" in rows["A-Colour-2"]["why_not"]


def test_missing_printer_comes_with_how_to_add(at_a, monkeypatch):
    monkeypatch.setattr(org_rules, "installed_printers", lambda: [])
    row = _by_name(org_rules.print_options())["A-Mono-1"]
    assert row["status"] == "add_first" and "\\\\srv\\A-Mono-1" in row["how_to_add"]


def test_best_printer_is_listed_first(at_a):
    assert org_rules.print_options()["printers"][0]["printer"] == "A-Mono-1"


def test_file_type_and_page_limit_are_checked(at_a, monkeypatch):
    monkeypatch.setattr(org_rules, "file_facts", lambda name: {"name": name, "found": True, "problems": [], "path": "x",
                                                                "ext": "xlsx", "pages": None})
    row = _by_name(org_rules.print_options("sheet.xlsx"))["A-Mono-1"]
    assert row["status"] == "not_allowed" and ".xlsx" in row["why_not"]
    monkeypatch.setattr(org_rules, "file_facts", lambda name: {"name": name, "found": True, "problems": [], "path": "x",
                                                                "ext": "pdf", "pages": 40})
    row = _by_name(org_rules.print_options("big.pdf"))["A-Mono-1"]
    assert row["status"] == "ready" and any("manager" in c for c in row["conditions"])
    assert any("secure release" in c for c in row["conditions"])


def test_group_members_may_use_restricted_printers(at_a, monkeypatch):
    monkeypatch.setattr(org_context, "user_groups", lambda: ["A-Colour"])
    assert _by_name(org_rules.print_options())["A-Colour-2"]["status"] == "add_first"


def test_virtual_printers_are_labelled_and_unknown_odc_lists_installed(monkeypatch):
    monkeypatch.setattr(org_rules, "installed_printers", lambda: INSTALLED)
    monkeypatch.setattr(org_context, "environment", lambda: env("avd", computer="AVD-1"))
    out = org_rules.print_options()
    assert out["odc"] == "unknown" and "avd_note" in out and out["virtual_printers"][0] == "Microsoft Print to PDF"
    assert "printers" not in out


# --- network ----------------------------------------------------------------------------------
def test_guest_wifi_is_flagged_and_vpn_rule_is_given(at_a):
    out = org_rules.network_options()
    assert out["allowed_wifi"]["corporate"] == ["A-Corp"]
    assert any("guest Wi-Fi" in g and "A-Corp" in g for g in out["guidance"])
    assert any("VPN" in g for g in out["guidance"])


def test_wrong_wifi_and_unknown_odc(at_a, monkeypatch):
    monkeypatch.setattr(org_context, "network_state", lambda: {"ips": [], "wifi": {"connected": True, "ssid": "Cafe", "signal": ""},
                                                               "vpn": {"connected": True, "adapters": ["GP"]}})
    assert any("not a ODC-A network" in g for g in org_rules.network_options()["guidance"])
    org_context.PROFILE_FILE.unlink()
    assert "unknown" in org_rules.network_options()["odc"]


# --- printing a file --------------------------------------------------------------------------
@pytest.fixture
def a_pdf(monkeypatch, at_a):
    monkeypatch.setattr(org_rules, "file_facts", lambda name: {"name": "plan.pdf", "found": True, "problems": [],
                                                                "path": "C:/Users/u/Documents/plan.pdf", "ext": "pdf", "pages": 3})
    sent = []
    monkeypatch.setattr(org_rules.powershell, "run_powershell", lambda key, timeout=25, arg=None: sent.append((key, arg)) or "ok")
    return sent


def test_print_goes_only_to_a_ready_printer(a_pdf):
    out = org_rules.print_file("plan.pdf", "A-Mono-1")
    assert out["ok"] and out["printer"] == "A-Mono-1"
    assert a_pdf == [("print_file_to", "C:/Users/u/Documents/plan.pdf|A-Mono-1")]


@pytest.mark.parametrize("printer, text", [("A-Colour-2", "not ready"), ("A-Mono-5", "not ready"), ("HP-Home", "not one of your")])
def test_print_refuses_other_printers(a_pdf, printer, text):
    out = org_rules.print_file("plan.pdf", printer)
    assert out["ok"] is False and text in out["error"] and a_pdf == []


def test_print_refuses_bad_files(monkeypatch, at_a):
    monkeypatch.setattr(org_rules, "file_facts", lambda name: {"name": name, "found": False, "problems": ["not found"]})
    assert org_rules.print_file("nope.pdf", "A-Mono-1")["ok"] is False
    monkeypatch.setattr(org_rules, "file_facts", lambda name: {"name": "a.pdf", "found": True, "problems": ["the PDF looks damaged"]})
    assert "damaged" in org_rules.print_file("a.pdf", "A-Mono-1")["error"]


def test_print_reports_a_failed_send_with_a_manual_fallback(a_pdf, monkeypatch):
    def boom(*a, **k):
        raise org_rules.powershell.CommandError("no application is associated")
    monkeypatch.setattr(org_rules.powershell, "run_powershell", boom)
    out = org_rules.print_file("plan.pdf", "A-Mono-1")
    assert out["ok"] is False and "Ctrl+P" in out["error"]


# --- routing and planning -----------------------------------------------------------------------
@pytest.mark.parametrize("text", ["which printer should I use?", "which printers can I use here", "which wifi can I connect to",
                                  "what vpn do I need", "where can I print on my floor", "which ODC am I in",
                                  "am I on a virtual desktop", "print Q3 report.pdf", "printers available near me"])
def test_workplace_questions_go_to_the_workplace_agent(text):
    assert fast_route(text) == {"agent": "workplace", "question": ""}


@pytest.mark.parametrize("text, agent", [("my printer is offline", "devices"), ("I cannot print anything", "devices"),
                                          ("how do I connect to the VPN?", "howto"), ("how to add a printer", "howto")])
def test_problems_and_how_tos_keep_their_agents(text, agent):
    assert fast_route(text)["agent"] == agent


def test_planner_picks_the_right_checks():
    assert [s["tool"] for s in route_workplace("which printer should I use for plan.pdf")] == ["get_my_print_options", "get_workplace_sop"]
    assert route_workplace("which printer should I use for plan.pdf")[0]["args"] == {"file": "plan.pdf"}
    assert route_workplace("which wifi can I use")[0]["tool"] == "get_my_network_options"
    assert route_workplace("which odc am I in")[0]["tool"] == "get_my_org_context"
