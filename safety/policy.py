"""Policy gate. This Python code, not a prompt, decides what may run.

- Every tool has a fixed risk tier and belongs to exactly one domain (specialist).
- R0 runs automatically. R1 and R2 run only with an explicit user approval.
  R3 is never executed by the agent: such requests become a ticket for IT.
- Arguments are type-checked and checked against the allow-lists in config.yaml.
- Read-only mode (global kill switch) blocks every change.
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

R0, R1, R2, R3 = 0, 1, 2, 3
# Names kept for older code and tests.
READ_ONLY, NEEDS_APPROVAL, SENSITIVE = R0, R1, R3

_read_only_override: bool | None = None


class PolicyError(Exception):
    """Raised when the policy gate blocks an action."""


def set_read_only(value: bool | None) -> None:
    """Runtime kill switch (used by the interface). None = follow config.yaml."""
    global _read_only_override
    _read_only_override = value


def is_read_only() -> bool:
    if _read_only_override is not None:
        return _read_only_override
    return bool(cfg("safety", "read_only_mode", default=False))


# ---------------------------------------------------------------------------
# R3 detection. Checked on the raw request before any model call.
# These are actions the agent must never perform itself; it opens a ticket instead.
# Questions ("is the firewall on?", "when does my password expire?") are not matched.
# ---------------------------------------------------------------------------
_R3_PATTERNS = [
    (r"\b(reset|change|forgot|forgotten|recover|unlock|remove)\b.{0,30}\b(password|passcode|pin|account|mfa|2fa|authenticator)\b",
     "access_request", "Password, account unlock and MFA changes need identity verification by IT"),
    (r"\b(password|account)\b.{0,25}\b(reset|locked out|is locked|unlock)\b",
     "access_request", "Password, account unlock and MFA changes need identity verification by IT"),
    (r"\b(un|re)?install\b|\b(upgrade|downgrade)\b.{0,20}\b(windows|office|driver|bios|firmware)\b",
     "software_request", "Installing or removing software is done by IT"),
    (r"\b(disable|turn off|switch off|stop|remove|bypass|uninstall)\b.{0,25}\b(antivirus|firewall|defender|bitlocker|uac|encryption|security)\b",
     "security", "Security protection is never switched off by the agent"),
    (r"\b(give|grant|make|need|want|add)\b.{0,25}\b(admin|administrator)\b.{0,15}\b(rights?|access|privileges?|account)?",
     "access_request", "Administrator rights need approval from IT"),
    (r"\b(edit|change|modify|delete|add)\b.{0,25}\b(registry|regedit|group policy|gpedit|permissions?)\b",
     "service_request", "Registry, policy and permission changes are done by IT"),
    (r"\bdelete\b.{0,15}\b(my|all|the|user'?s?)\b.{0,15}\b(files|documents|folder|photos|data|profile)\b",
     "service_request", "Deleting user files is never done by the agent"),
    (r"\b(format|wipe|factory reset|reimage)\b.{0,20}\b(c:|drive|disk|laptop|computer|pc|device)\b",
     "service_request", "Wiping a device is done by IT"),
    (r"\b(create|add|delete|disable|remove)\b.{0,15}\b(user|account)s?\b.{0,20}\b(for|called|named)?",
     "access_request", "Creating or removing accounts is done by IT"),
    (r"\b(join|rejoin)\b.{0,15}\bdomain\b|\bdomain rejoin\b", "service_request", "Domain changes are done by IT"),
    (r"\b(read|open|show|spy|monitor)\b.{0,25}\b(someone|colleague|coworker|another user|other user|my boss|employee)'?s?\b.{0,20}\b(email|mail|files|messages|screen|chats?)\b",
     "security", "Looking at another person's data is not allowed"),
]
_R3 = [(re.compile(p, re.IGNORECASE), cat, why) for p, cat, why in _R3_PATTERNS]


def sensitive_reason(text: str) -> tuple[str, str] | None:
    """Return (ticket category, reason) when the request asks for an R3 action, else None."""
    for pattern, category, why in _R3:
        if pattern.search(text or ""):
            return category, why
    return None


R3_SOFTWARE = "Installing or removing software is done by IT"
R3_PASSWORD = "Password, account unlock and MFA changes need identity verification by IT"


def sensitive_reasons(text: str) -> set[str]:
    """Every R3 reason the request matches (sensitive_reason only reports the first)."""
    return {why for pattern, _, why in _R3 if pattern.search(text or "")}


def sensitive_categories(text: str) -> set[str]:
    """Every R3 category the request matches (sensitive_reason only reports the first)."""
    return {cat for pattern, cat, _ in _R3 if pattern.search(text or "")}


def is_sensitive_request(text: str) -> bool:
    return sensitive_reason(text) is not None


# ---------------------------------------------------------------------------
# Allow-list checks for tools that change something
# ---------------------------------------------------------------------------
def _window_allowed(window: str) -> bool:
    if not isinstance(window, str) or not window.strip():
        return False
    patterns = cfg("desktop", "allowed_windows", default=[]) or []
    return any(re.search(p, window, re.IGNORECASE) for p in patterns)


def _connector_guards() -> dict:
    from connectors.base import GUARDS  # local import avoids a cycle
    return GUARDS


def check_args(tool: str, args: dict) -> None:
    """Allow-list checks beyond the type checks in the registry. Raises PolicyError."""
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
    elif tool in _connector_guards():
        try:
            _connector_guards()[tool](args)
        except ValueError as e:
            raise PolicyError(str(e))
    elif tool == "open_website":
        from tools.desktop import clean_url  # local import avoids a cycle
        try:
            clean_url(args.get("url", ""))
        except ValueError as e:
            raise PolicyError(str(e))
    elif tool == "install_software":
        from tools.software import find_installable  # local import avoids a cycle
        if find_installable(args.get("package", "")) is None:
            raise PolicyError(f"'{args.get('package')}' is not on the installable software list")
    elif tool in ("click_control", "type_text", "press_keys", "list_controls"):
        if not _window_allowed(args.get("window", "")):
            raise PolicyError(f"Window '{args.get('window')}' is not on the allowed window list")
    elif tool == "run_browser_task":
        if args.get("task_id") not in (cfg("browser", "allowed_tasks", default={}) or {}):
            raise PolicyError(f"Browser task '{args.get('task_id')}' is not on the allowed task list")
    elif tool == "clear_app_cache":
        if args.get("app") not in (cfg("storage", "app_caches", default={}) or {}):
            raise PolicyError(f"'{args.get('app')}' is not on the allowed cache list")


def check_step(domain: str, tool: str, args: dict) -> dict:
    """Full pre-flight check of one planned step. Returns the cleaned arguments."""
    from tools.registry import TOOLS, validate_args  # local import avoids a cycle

    spec = TOOLS.get(tool)
    if spec is None:
        raise PolicyError(f"Unknown tool '{tool}'. Only catalogue tools can run.")
    if spec.domain != domain:
        raise PolicyError(f"Tool '{tool}' does not belong to the {domain} agent")
    if spec.risk >= R3:
        raise PolicyError("This is a high-risk (R3) action. It needs IT.")
    if spec.risk >= R1 and is_read_only():
        raise PolicyError("Read-only mode is on, so no changes can be made")
    try:
        clean = validate_args(spec, args)
    except ValueError as e:
        raise PolicyError(str(e))
    check_args(tool, clean)
    return clean


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
    agent: str                      # the domain this runner acts for
    calls_made: int = 0
    max_calls: int = field(default_factory=lambda: int(cfg("limits", "max_tool_calls_per_request", default=10)))

    def run(self, tool: str, args: dict | None = None, *, approved: bool = False) -> dict:
        from tools.registry import TOOLS  # local import avoids a cycle

        args = dict(args or {})
        spec = TOOLS.get(tool)
        try:
            args = check_step(self.agent, tool, args)
            if spec.risk >= R1 and not approved:
                raise PolicyError(f"'{tool}' changes the system and needs user approval first")
            if self.calls_made >= self.max_calls:
                raise PolicyError(f"Tool call limit of {self.max_calls} reached for this request")
        except PolicyError as e:
            audit.log_event(self.task_id, "blocked", agent=self.agent, tool=tool, args=args,
                            risk_level=getattr(spec, "risk", None), detail=str(e))
            raise

        self.calls_made += 1
        from tools.automation import TIMEOUTS      # a screen recording needs longer than the usual 30 s
        timeout = max(float(cfg("limits", "tool_timeout_seconds", default=30)), TIMEOUTS.get(tool, 0))
        try:
            future = _pool.submit(spec.func, **args)
            result = future.result(timeout=timeout)
            if not isinstance(result, dict):
                result = {"result": result}
        except FutureTimeout:
            result = {"ok": False, "error": f"'{tool}' timed out after {int(timeout)} seconds"}
        except Exception as e:  # tool failures are reported, never hidden
            result = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}
        result = _shorten(result, int(cfg("limits", "max_tool_output_chars", default=1500)))
        audit.log_event(self.task_id, "tool_call", agent=self.agent, tool=tool, args=args,
                        risk_level=spec.risk, detail=result)
        return result
