"""The four specialists: Performance, Storage, Network, Computer Use.

Each specialist has three parts:
  diagnose(runner, emit)   -> runs its read-only tools (fixed plan, no model involved)
  propose(request, diag)   -> one model call: plain-English diagnosis + one fix from its own list
  verify(runner, state)    -> re-runs the diagnostic and compares before and after

A proposal is: {"diagnosis", "fix", "summary", "what_changes", "steps": [{"tool", "args", "label"}]}
"fix" is None when no change is proposed.
"""
from __future__ import annotations

import ctypes
import json
import os
from datetime import datetime
from pathlib import Path

from agent import prompts
from agent.llm import ask_json
from appconfig import cfg
from safety.policy import ToolRunner
from tools import browser as browser_tools

LABELS = {"performance": "Performance", "storage": "Storage", "network": "Network",
          "computer_use": "Computer Use"}


def _text(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'"{key}" must be a non-empty string')
    return value.strip()


def _ask(agent: str, request: str, diagnostics: dict, validate) -> dict:
    user = f"User request: {request.strip()[:500]}\n\nTOOL OUTPUT:\n{json.dumps(diagnostics, default=str)}"
    return ask_json(prompts.BY_AGENT[agent], user, validate)


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------
class Performance:
    name = "performance"
    diagnostic_tools = ["get_system_health", "get_running_processes"]

    def propose(self, request: str, diag: dict) -> dict:
        closable = (diag.get("get_running_processes") or {}).get("largest_closable_process")

        def validate(d: dict) -> dict:
            fix = str(d.get("fix", "")).strip()
            if fix not in ("close_process", "none"):
                raise ValueError('"fix" must be "close_process" or "none"')
            out = {"diagnosis": _text(d, "diagnosis"), "fix": fix, "reason": str(d.get("reason") or "")}
            if fix == "close_process":
                if not closable:
                    raise ValueError('there is no closable process, so "fix" must be "none"')
                try:
                    pid = int(d.get("pid"))
                except (TypeError, ValueError):
                    raise ValueError('"pid" must be a number')
                if pid != closable["pid"]:
                    raise ValueError(f'"pid" must be {closable["pid"]}, the pid of largest_closable_process')
                out["pid"] = pid
            return out

        d = _ask(self.name, request, diag, validate)
        if d["fix"] == "none":
            return {"diagnosis": d["diagnosis"], "fix": None, "reason": d["reason"]}
        return {
            "diagnosis": d["diagnosis"], "fix": "close_process", "reason": d["reason"],
            "summary": f"Close {closable['name']} (process {closable['pid']})",
            "what_changes": (f"{closable['name']} will be closed. It is using {closable['memory_mb']} MB of memory. "
                             "Unsaved work in that app will be lost."),
            "steps": [{"tool": "close_process", "args": {"pid": closable["pid"]},
                       "label": f"Close {closable['name']} (PID {closable['pid']})"}],
        }

    def verify(self, runner: ToolRunner, state: dict) -> dict:
        before = state["diagnostics"].get("get_system_health", {})
        after = runner.run("get_system_health")
        result = (state.get("fix_results") or [{}])[-1]
        closed = result.get("ok") and not result.get("still_running")
        rows = [
            {"metric": "Memory in use (%)", "before": before.get("ram_percent"), "after": after.get("ram_percent")},
            {"metric": "Memory in use (GB)", "before": before.get("ram_used_gb"), "after": after.get("ram_used_gb")},
            {"metric": "CPU in use (%)", "before": before.get("cpu_percent"), "after": after.get("cpu_percent")},
        ]
        improved = (after.get("ram_used_gb") is not None and before.get("ram_used_gb") is not None
                    and after["ram_used_gb"] < before["ram_used_gb"])
        fixed = bool(closed and improved)
        note = ("The process was closed and memory use went down." if fixed else
                "The process was closed, but memory use did not go down." if closed else
                "The process could not be closed.")
        return {"comparison": rows, "fixed": fixed, "note": note}


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
class Storage:
    name = "storage"
    diagnostic_tools = ["get_disk_usage", "find_large_temp_folders"]

    def propose(self, request: str, diag: dict) -> dict:
        temp = diag.get("find_large_temp_folders") or {}
        cleanable = temp.get("total_cleanable_mb") or 0

        def validate(d: dict) -> dict:
            fix = str(d.get("fix", "")).strip()
            if fix not in ("clean_approved_temp_files", "none"):
                raise ValueError('"fix" must be "clean_approved_temp_files" or "none"')
            if fix != "none" and cleanable <= 0:
                raise ValueError('total_cleanable_mb is 0, so "fix" must be "none"')
            return {"diagnosis": _text(d, "diagnosis"), "fix": fix, "reason": str(d.get("reason") or "")}

        d = _ask(self.name, request, diag, validate)
        if d["fix"] == "none":
            return {"diagnosis": d["diagnosis"], "fix": None, "reason": d["reason"]}
        folders = [f["folder"] for f in temp.get("folders", [])]
        age = cfg("storage", "min_file_age_minutes", default=60)
        return {
            "diagnosis": d["diagnosis"], "fix": "clean_approved_temp_files", "reason": d["reason"],
            "summary": f"Delete temporary files (about {cleanable} MB)",
            "what_changes": (f"Temporary files older than {age} minutes will be deleted from: "
                             f"{', '.join(folders)}. About {cleanable} MB. Files in use are skipped. "
                             "Your documents are not touched. Deleted temp files cannot be restored."),
            "steps": [{"tool": "clean_approved_temp_files", "args": {},
                       "label": "Delete old files in the allowed temp folders"}],
        }

    def verify(self, runner: ToolRunner, state: dict) -> dict:
        before = {d["drive"]: d for d in state["diagnostics"].get("get_disk_usage", {}).get("drives", [])}
        after_out = runner.run("get_disk_usage")
        result = (state.get("fix_results") or [{}])[-1]
        rows = []
        for d in after_out.get("drives", []):
            b = before.get(d["drive"], {})
            rows.append({"metric": f"Free space on {d['drive']} (GB)", "before": b.get("free_gb"), "after": d["free_gb"]})
            rows.append({"metric": f"Used on {d['drive']} (%)", "before": b.get("used_percent"), "after": d["used_percent"]})
        freed = result.get("freed_mb") or 0
        rows.append({"metric": "Temp files deleted", "before": 0, "after": result.get("files_deleted", 0)})
        rows.append({"metric": "Space freed (MB)", "before": 0, "after": freed})
        fixed = bool(result.get("ok") and freed > 0)
        note = (f"{freed} MB was freed." if fixed else "No space could be freed from the temp folders.")
        return {"comparison": rows, "fixed": fixed, "note": note}


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
class Network:
    name = "network"
    diagnostic_tools = ["check_network_connection", "check_dns_resolution", "get_network_config"]

    def propose(self, request: str, diag: dict) -> dict:
        def validate(d: dict) -> dict:
            fix = str(d.get("fix", "")).strip()
            if fix not in ("flush_dns_cache", "none"):
                raise ValueError('"fix" must be "flush_dns_cache" or "none"')
            return {"diagnosis": _text(d, "diagnosis"), "fix": fix, "reason": str(d.get("reason") or "")}

        d = _ask(self.name, request, diag, validate)
        if d["fix"] == "none":
            return {"diagnosis": d["diagnosis"], "fix": None, "reason": d["reason"]}
        return {
            "diagnosis": d["diagnosis"], "fix": "flush_dns_cache", "reason": d["reason"],
            "summary": "Flush the DNS cache",
            "what_changes": ("The saved list of website addresses (DNS cache) on this computer will be cleared, "
                             "so Windows looks them up again. No files or settings are changed."),
            "steps": [{"tool": "flush_dns_cache", "args": {}, "label": "Run ipconfig /flushdns"}],
        }

    def verify(self, runner: ToolRunner, state: dict) -> dict:
        b_dns = state["diagnostics"].get("check_dns_resolution", {})
        b_net = state["diagnostics"].get("check_network_connection", {})
        a_dns = runner.run("check_dns_resolution")
        a_net = runner.run("check_network_connection")

        def site(net):
            w = net.get("website") or {}
            return "opens" if w.get("opens") else "does not open"

        rows = [
            {"metric": "DNS lookups that work", "before": b_dns.get("resolved"), "after": a_dns.get("resolved")},
            {"metric": f"Test website ({cfg('network', 'test_website')})", "before": site(b_net), "after": site(a_net)},
        ]
        fixed = bool(a_dns.get("all_resolve") and (a_net.get("website") or {}).get("opens"))
        note = ("DNS lookups work and the test website opens." if fixed else
                "DNS lookups or the test website still fail after the flush.")
        return {"comparison": rows, "fixed": fixed, "note": note}


# ---------------------------------------------------------------------------
# Computer Use
# ---------------------------------------------------------------------------
def documents_folder() -> Path:
    """The user's real Documents folder (it may be redirected, for example to OneDrive)."""
    try:
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]

        # FOLDERID_Documents {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
        guid = GUID(0xFDD39AD0, 0x238F, 0x46AF, (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
        out = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(out)) == 0:
            path = Path(out.value)
            ctypes.windll.ole32.CoTaskMemFree(out)
            return path
    except Exception:
        pass
    return Path(os.path.expandvars(r"%USERPROFILE%\Documents"))


def health_note_text(health: dict, disks: dict) -> str:
    lines = [
        f"System health summary, {datetime.now():%d %b %Y %H:%M}",
        f"CPU in use: {health.get('cpu_percent')} percent of {health.get('cpu_cores')} cores",
        f"Memory in use: {health.get('ram_percent')} percent, "
        f"{health.get('ram_used_gb')} GB of {health.get('ram_total_gb')} GB",
        f"Time since last restart: {health.get('uptime_hours')} hours",
    ]
    for d in disks.get("drives", []):
        lines.append(f"Drive {d['drive']} {d['free_gb']} GB free of {d['total_gb']} GB, {d['used_percent']} percent used")
    lines.append("Written by IT Buddy from live measurements.")
    return "\n".join(lines)


class ComputerUse:
    name = "computer_use"
    diagnostic_tools: list[str] = []  # decided after the task is known

    def pick_task(self, request: str) -> dict:
        tasks = cfg("browser", "allowed_tasks", default={}) or {}
        listing = "\n".join(f'  "{k}": {v}' for k, v in tasks.items())
        system = prompts.COMPUTER_USE.replace("{browser_tasks}", listing)

        def validate(d: dict) -> dict:
            task = str(d.get("task", "")).strip()
            if task not in ("write_health_note", "browser_task", "none"):
                raise ValueError('"task" must be write_health_note, browser_task or none')
            task_id = str(d.get("task_id") or "").strip()
            if task == "browser_task" and task_id not in tasks:
                raise ValueError(f'"task_id" must be one of {list(tasks)}')
            return {"task": task, "task_id": task_id, "reason": str(d.get("reason") or "")}

        return ask_json(system, f"User request: {request.strip()[:500]}", validate)

    def plan_health_note(self, health: dict, disks: dict) -> dict:
        target = documents_folder() / f"system_health_{datetime.now():%Y%m%d_%H%M%S}.txt"
        text = health_note_text(health, disks)
        steps = [
            {"tool": "open_application", "args": {"name": "notepad"}, "label": "Open Notepad"},
            {"tool": "type_text", "args": {"window": "Notepad", "text": text}, "label": "Type the health summary"},
            {"tool": "click_control", "args": {"window": "Notepad", "control_name": "File"}, "label": "Click the File menu"},
            {"tool": "click_control", "args": {"window": "Notepad", "control_name": "Save as"}, "label": "Click Save as"},
            {"tool": "type_text", "args": {"window": "Save as", "text": str(target)}, "label": f"Type the file name {target.name}"},
            {"tool": "click_control", "args": {"window": "Save as", "control_name": "Save"}, "label": "Click Save"},
        ]
        return {
            "diagnosis": ("I measured the system health: CPU "
                          f"{health.get('cpu_percent')}%, memory {health.get('ram_percent')}% "
                          f"({health.get('ram_used_gb')} of {health.get('ram_total_gb')} GB)."),
            "fix": "computer_use_task", "reason": "",
            "summary": "Write the system health summary in Notepad and save it in Documents",
            "what_changes": (f"Notepad will open, the summary below will be typed, and a new file will be saved as "
                             f"{target}. Please do not use the mouse or keyboard while it runs.\n\n{text}"),
            "steps": steps, "expected_file": str(target),
        }

    def plan_browser_task(self, task_id: str) -> dict:
        description = (cfg("browser", "allowed_tasks", default={}) or {}).get(task_id, task_id)
        folder = browser_tools.download_folder()
        return {
            "diagnosis": "No diagnosis is needed for this task.",
            "fix": "computer_use_task", "reason": "",
            "summary": description,
            "what_changes": (f"A browser window will open the local test portal, click 'Download latest report' "
                             f"and save the file in {folder}."),
            "steps": [{"tool": "run_browser_task", "args": {"task_id": task_id},
                       "label": f"Run browser task '{task_id}': open the portal and download the report"}],
            "expected_file": None,
        }

    def verify(self, runner: ToolRunner, state: dict) -> dict:
        proposal = state["proposal"]
        results = state.get("fix_results") or [{}]
        path = proposal.get("expected_file") or results[-1].get("saved_to")
        all_ok = all(r.get("ok") for r in results) and len(results) == len(proposal["steps"])
        check = (browser_tools.file_exists(path) if path
                 else {"exists": False, "fresh": False, "path": None, "size_bytes": 0})
        rows = [{"metric": f"New file saved: {check['path']}", "before": "no",
                 "after": f"yes ({check['size_bytes']} bytes)" if check["exists"] and check["fresh"] else "no"}]
        fixed = bool(all_ok and check["exists"] and check["fresh"])
        note = (f"The file was saved: {check['path']}" if fixed else "The file was not found after the task.")
        return {"comparison": rows, "fixed": fixed, "note": note}


SPECIALISTS = {s.name: s for s in (Performance(), Storage(), Network(), ComputerUse())}
