"""Tests for the extended capability set: registry validation, settings, software, devices, logs,
security, account, knowledge base, tickets, secret redaction and the planning step."""
import json
import winreg

import pytest

from agent import specialists
from agent.llm import MalformedOutput
from safety.redact import redact
from tools import knowledge, security, settings, software, tickets
from tools.registry import R0, TOOLS, catalogue_text, tools_for, validate_args

SAMPLE_ARGS = {"host": "www.microsoft.com", "port": 443, "setting": "developer_mode", "device_class": "Monitor",
               "search": "microsoft", "days": 3, "hours": 6, "name": "zoom", "url": "https://www.microsoft.com",
               "query": "how do I connect to the vpn", "ticket": "ITB-0001",
               "symptoms": "vpn keeps disconnecting", "doc_id": "network_and_vpn", "section": "VPN",
               "code_or_message": "0x80070005", "app": "outlook", "os_filter": "any", "doc_type_filter": "any",
               "topic": "password policy", "role_filter": "any", "context": "test", "chunk_id": "nope",
               "helpful": "yes", "correction": "", "ticket_ref": "ITB-0001", "symptom": "vpn drops",
               "resolution": "Reinstalled the VPN client and rebooted.",
               "file": "", "path": "Downloads", "folder": "Downloads", "pattern": "*.nomatch", "offset": 0, "number": 1,
               "count": 3, "incident": "INC0010023", "unread_only": "no", "title": "Test", "summary": "Test", "priority": "P3",
               "package": "7-Zip", "browser": "default", "command": "Get-Date", "purpose": "test",
               "content": "x", "mode": "create", "to": "a@b.com", "subject": "s", "body": "b", "start": "2026-01-01T10:00",
               "end": "2026-01-01T11:00", "attendee": "", "short_description": "t", "description": "d",
               "urgency": "3", "text": "x", "window": "Calculator", "seconds": 1, "target": "ODC B printer"}


@pytest.mark.parametrize("name", sorted(n for n, t in TOOLS.items() if t.risk == R0))
def test_every_read_only_tool_runs_and_stays_short(name):
    spec = TOOLS[name]
    out = spec.func(**validate_args(spec, {p.name: SAMPLE_ARGS[p.name] for p in spec.params}))
    assert isinstance(out, dict) and "ok" in out
    assert len(json.dumps(out, default=str)) <= 1500, "tool output must stay short for the local model"


def test_argument_validation():
    port = TOOLS["check_port"]
    assert validate_args(port, {"host": " example.com ", "port": "443"}) == {"host": "example.com", "port": 443}
    for bad in ({"host": "example.com"}, {"host": "example.com", "port": "abc"},
                {"host": "example.com", "port": 443, "command": "dir"}):
        with pytest.raises(ValueError):
            validate_args(port, bad)
    with pytest.raises(ValueError):
        validate_args(TOOLS["read_setting"], {"setting": "bitlocker_recovery_key"})
    with pytest.raises(ValueError):
        validate_args(TOOLS["open_settings_page"], {"page": "cmd.exe"})
    assert validate_args(TOOLS["read_setting"], {"setting": "Developer_Mode"}) == {"setting": "developer_mode"}


def test_hostnames_cannot_carry_extra_arguments():
    from tools import network
    assert network._clean_host("https://www.Example.com/path?x=1") == "www.example.com"
    for bad in ("exa mple.com", "example.com; rm -rf /", "-n 5 example.com", "", "a" * 300):
        assert network._clean_host(bad) is None


def test_read_setting_matches_the_registry():
    expected = "Off"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock") as key:
            expected = "On" if winreg.QueryValueEx(key, "AllowDevelopmentWithoutDevLicense")[0] == 1 else "Off"
    except OSError:
        pass
    out = settings.read_setting("developer_mode")
    assert out["ok"] is True and out["value"] == expected


def test_only_listed_preferences_and_pages_can_be_touched():
    assert set(settings._PREFERENCES) == {"dark_mode", "file_extensions", "hidden_files", "clipboard_history"}
    assert all(link.startswith(("ms-settings:", "windowsdefender:")) for link in settings.PAGES.values())


def test_software_search_and_catalogue():
    everything = software.find_installed_software("")
    assert everything["total_installed"] > 0
    assert software.find_installed_software("zzz-no-such-program")["matches"] == 0
    assert software.search_approved_software("zoom")["approved"] is True
    assert software.search_approved_software("limewire")["approved"] is False


def test_suspicious_link_check():
    bad = security.check_suspicious_link("http://micros0ft-login.verify-account.xyz/login")
    assert "suspicious" in bad["verdict"] and len(bad["warning_signs"]) >= 2
    fake = security.check_suspicious_link("https://paypal.secure-billing.top/account")
    assert any("paypal" in s for s in fake["warning_signs"])
    good = security.check_suspicious_link("https://www.microsoft.com/en-us/windows")
    assert good["warning_signs"] == []


def test_knowledge_base_returns_sourced_text():
    out = knowledge.search_knowledge_base("how do I connect to the vpn")
    assert out["results"] and out["results"][0]["source"].startswith("network_and_vpn.md")
    assert knowledge.search_knowledge_base("quantum chromodynamics lagrangian")["results"] == []


def test_tickets_roundtrip():
    t = tickets.create_ticket("New keyboard", "Keys are stuck", category="hardware_request", priority="P3", task_id="x")
    assert t["ref"].startswith("ITB-")
    assert tickets.get_ticket(t["ref"])["status"] == "open"
    tickets.set_status(t["id"], "resolved")
    assert tickets.list_my_tickets()["tickets"][0]["status"] == "resolved"
    assert tickets.get_ticket("ITB-9999")["ok"] is False
    assert tickets.create_ticket("x", "y", category="nonsense", priority="P9")["priority"] == "P3"


@pytest.mark.parametrize("text,secret", [
    ("my password is Tr0ub4dor&3 and it fails", "Tr0ub4dor&3"),
    ("api key: sk-abcdefghijklmnopqrstuv", "sk-abcdefghijklmnopqrstuv"),
    ("use AKIAIOSFODNN7EXAMPLE to log in", "AKIAIOSFODNN7EXAMPLE"),
    ("card 4111 1111 1111 1111 was declined", "4111 1111 1111 1111"),
])
def test_secrets_are_redacted(text, secret):
    clean, found = redact(text)
    assert found and secret not in clean


@pytest.mark.parametrize("text", ["my password is expired", "when does my password expire?", "the token is missing"])
def test_ordinary_sentences_are_not_redacted(text):
    assert redact(text) == (text, False)


def test_plan_accepts_only_read_only_tools_of_the_domain(monkeypatch):
    domain = specialists.DOMAINS["storage"]

    def model_says(reply):
        monkeypatch.setattr(specialists, "ask_json", lambda system, user, validate: validate(reply))

    model_says({"tools": [{"tool": "get_disk_usage", "args": {}}, {"tool": "get_disk_usage", "args": {}}]})
    assert specialists.plan(domain, "disk full") == [{"tool": "get_disk_usage", "args": {}}]
    for bad in ({"tools": [{"tool": "clean_approved_temp_files", "args": {}}]},   # a change, not a check
                {"tools": [{"tool": "flush_dns_cache", "args": {}}]},             # another domain
                {"tools": [{"tool": "run_shell", "args": {"cmd": "dir"}}]},       # not a tool
                {"tools": []}):
        model_says(bad)
        with pytest.raises(ValueError):
            specialists.plan(domain, "disk full")


def test_plan_falls_back_to_the_default_when_the_model_output_stays_malformed(monkeypatch):
    def broken(system, user, validate):
        raise MalformedOutput("bad json three times")

    monkeypatch.setattr(specialists, "ask_json", broken)
    steps = specialists.plan(specialists.DOMAINS["network"], "no internet")
    assert [s["tool"] for s in steps] == ["check_network_connection", "check_dns_resolution", "get_network_config"]


def test_answer_rejects_fixes_with_bad_arguments(monkeypatch):
    domain = specialists.DOMAINS["settings"]

    def model_says(reply):
        monkeypatch.setattr(specialists, "ask_json", lambda system, user, validate: validate(reply))

    model_says({"answer": "Developer Mode is On.", "fix": "none"})
    assert specialists.answer(domain, "is dev mode on", {})["fix"] is None
    model_says({"answer": "Opening it.", "fix": "open_settings_page", "args": {"page": "developers"}})
    p = specialists.answer(domain, "open developer settings", {})
    assert p["fix"] == "open_settings_page" and p["steps"][0]["args"] == {"page": "developers"}
    for bad in ({"answer": "x", "fix": "open_settings_page", "args": {"page": "regedit"}},
                {"answer": "x", "fix": "set_user_preference", "args": {"setting": "firewall", "value": "off"}},
                {"answer": "x", "fix": "close_process", "args": {"pid": 4}},
                {"answer": "", "fix": "none"}):
        model_says(bad)
        with pytest.raises(ValueError):
            specialists.answer(domain, "x", {})


def test_fix_names_from_a_small_model_are_understood():
    names = {"close_process"}
    assert specialists._match_fix("close_process(pid=4321)", names) == "close_process"
    assert specialists._match_fix("Close Process", names) == "close_process"
    assert specialists._match_fix(None, names) == "none"
    assert specialists._match_fix("escalate", names) == "escalate"
    assert specialists._match_fix("format_disk", names) is None


def test_close_process_can_only_target_the_measured_closable_process():
    diag = {"get_running_processes": {"largest_closable_process": {"pid": 4242, "name": "x.exe"}}}
    assert specialists._collect_args("close_process", {"args": {"pid": 4}}, diag) == {"pid": 4242}
    assert specialists._collect_args("close_process", {"pid": 999}, diag) == {"pid": 4242}
    assert specialists._collect_args("open_settings_page", {"page": "display", "cmd": "x"}, {}) == {"page": "display"}


def test_every_domain_prompt_fits_the_context_window():
    for d in specialists.DOMAINS.values():
        text = catalogue_text(tools_for(d.name))
        assert len(text) < 5000, f"{d.name} tool list is too long for a small model"


@pytest.mark.parametrize("request_text,tool", [
    ("How do I connect to the VPN?", "search_knowledge_base"),
    ("Outlook shows error 0x800CCC0E", "lookup_error_code"),
    ("blue screen DRIVER_IRQL_NOT_LESS_OR_EQUAL", "lookup_error_code"),
    ("What is the BYOD policy?", "lookup_sop"),
    ("Am I allowed to plug in a USB stick?", "lookup_sop"),
    ("Has this happened before? similar tickets for vpn drops", "find_similar_tickets"),
])
def test_howto_planner_routes_to_the_right_knowledge_tool(request_text, tool):
    steps = specialists.plan(specialists.DOMAINS["howto"], request_text)
    assert [s["tool"] for s in steps] == [tool]
    name = next(iter(steps[0]["args"]))
    assert validate_args(TOOLS[tool], steps[0]["args"])[name].startswith(request_text[:20])
