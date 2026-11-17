"""Policy gate. This Python code, not a prompt, decides what may run.

- Every tool has a fixed risk level and belongs to exactly one agent.
- Level 1 runs automatically, Level 2 only with an explicit user approval,
  Level 3 is never built: such requests are refused.
- Allow-lists come from config.yaml.
- One request may make at most `max_tool_calls_per_request` tool calls.
- Every call is time-limited, its output is truncated, and it is audited.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field

from appconfig import cfg
from safety import audit

READ_ONLY = 1
NEEDS_APPROVAL = 2
SENSITIVE = 3


class PolicyError(Exception):
    """Raised when the policy gate blocks an action."""


# ---------------------------------------------------------------------------
# Level 3 detection (FR-10). Checked on the raw request before routing.
# ---------------------------------------------------------------------------
_SENSITIVE_PATTERNS = [
    r"\binstall(ing|ed)?\b", r"\buninstall", r"\bpassword", r"\bpasscode",
    r"\bpermission", r"\badmin(istrator)?\s*(rights|access|privilege)", r"\bregistry\b", r"\bregedit",
    r"\bfirewall", r"\bantivirus", r"\bdefender\b", r"\bbitlocker", r"\buac\b",
    r"\bsecurity setting", r"\bgroup policy", r"\bgpedit",
    r"\bdelete (my|all|the user'?s?) (files|documents|folder|photos|data)",
    r"\bformat (the |my )?(c:|drive|disk)", r"\bdisable (the )?(antivirus|firewall|defender|security)",
    r"\bcreate (a )?(new )?(user|account)", r"\bdomain (join|account)",
]
_SENSITIVE_RE = re.compile("|".join(_SENSITIVE_PATTERNS), re.IGNORECASE)


def is_sensitive_request(text: str) -> bool:
    return bool(_SENSITIVE_RE.search(text or ""))


# ---------------------------------------------------------------------------
# Argument / allow-list checks for Level 2 tools
# ---------------------------------------------------------------------------
def _window_allowed(window: str) -> bool:
    if not isinstance(window, str) or not window.strip():
        return False
    patterns = cfg("desktop", "allowed_windows", default=[]) or []
    return any(re.search(p, window, re.IGNORECASE) for p in patterns)


def check_args(tool: str, args: dict) -> None:
    """Allow-list checks. Raises PolicyError when an argument is not allowed."""
    if tool == "close_process":
        from tools.performance import protection_reason  # local import avoids a cycle
        pid = args.get("pid")
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            raise PolicyError(f"pid must be a positive integer, got {pid!r}")
        reason = protection_reason(pid)
        if reason:
            raise PolicyError(f"Process {pid} cannot be closed: {reason}")
    elif tool == "open_application":
        name = str(args.get("name", "")).lower().strip()
        if name not in (cfg("desktop", "allowed_apps", default={}) or {}):
            raise PolicyError(f"Application '{name}' is not on the allowed app list")
    elif tool in ("click_control", "type_text"):
        if not _window_allowed(args.get("window", "")):
            raise PolicyError(f"Window '{args.get('window')}' is not on the allowed window list")
    elif tool == "run_browser_task":
        if args.get("task_id") not in (cfg("browser", "allowed_tasks", default={}) or {}):
            raise PolicyError(f"Browser task '{args.get('task_id')}' is not on the allowed task list")


# ---------------------------------------------------------------------------
# Tool runner: the only path from an agent to a tool
# ---------------------------------------------------------------------------
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tool")


def _shorten(result: dict, limit: int) -> dict:
    text = json.dumps(result, default=str)
    if len(text) <= limit:
        return result
    return {"truncated": True, "data": text[: limit - 40]}


@dataclass
class ToolRunner:
    task_id: str
    agent: str
    calls_made: int = 0
    max_calls: int = field(default_factory=lambda: int(cfg("limits", "max_tool_calls_per_request", default=10)))

    def run(self, tool: str, args: dict | None = None, *, approved: bool = False) -> dict:
        from tools.registry import TOOLS  # local import avoids a cycle

        args = dict(args or {})
        spec = TOOLS.get(tool)
        try:
            if spec is None:
                raise PolicyError(f"Unknown tool '{tool}'. Only catalogue tools can run.")
            if spec.agent != self.agent:
                raise PolicyError(f"Tool '{tool}' does not belong to the {self.agent} agent")
            if spec.risk_level >= SENSITIVE:
                raise PolicyError("Level 3 actions are not available. Please contact IT.")
            if spec.risk_level == NEEDS_APPROVAL and not approved:
                raise PolicyError(f"'{tool}' changes the system and needs user approval first")
            if self.calls_made >= self.max_calls:
                raise PolicyError(f"Tool call limit of {self.max_calls} reached for this request")
            check_args(tool, args)
        except PolicyError as e:
            audit.log_event(self.task_id, "blocked", agent=self.agent, tool=tool, args=args,
                            risk_level=getattr(spec, "risk_level", None), detail=str(e))
            raise

        self.calls_made += 1
        timeout = float(cfg("limits", "tool_timeout_seconds", default=30))
        try:
            future = _pool.submit(spec.func, **args)
            result = future.result(timeout=timeout)
            if not isinstance(result, dict):
                result = {"result": result}
        except FutureTimeout:
            result = {"ok": False, "error": f"'{tool}' timed out after {int(timeout)} seconds"}
        except Exception as e:  # tool failures are reported, never hidden (FR-18)
            result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        result = _shorten(result, int(cfg("limits", "max_tool_output_chars", default=1500)))
        audit.log_event(self.task_id, "tool_call", agent=self.agent, tool=tool, args=args,
                        risk_level=spec.risk_level, detail=result)
        return result
