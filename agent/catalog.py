"""The sub-agent catalogue shown in the interface: who Tobi can work with, what each one covers,
which connector it depends on, and how to try it. Status and tool counts are computed live from the
connector registry and the tool registry, so the page never drifts from what is really installed.
"""
from __future__ import annotations

from dataclasses import dataclass

from connectors.base import CONNECTORS
from tools.registry import R0, TOOLS


@dataclass(frozen=True)
class SubAgent:
    id: str
    name: str
    icon: str
    group: str                  # "Specialists" | "Special agents"
    purpose: str
    domains: tuple              # tool domains this agent uses
    connector: str              # connector id that gates it ("" = always available)
    examples: tuple


SUBAGENTS: tuple[SubAgent, ...] = (
    # ---- specialists: diagnose, answer, fix, verify -------------------------------------------------
    SubAgent("performance", "Performance", "⚡", "Specialists", "Slow computer, memory and CPU hogs, restart advice.",
             ("performance",), "system", ("My computer is very slow.",)),
    SubAgent("storage", "Storage", "💾", "Specialists", "Disk space, temp files, recycle bin and app caches.",
             ("storage",), "system", ("My C drive is almost full.",)),
    SubAgent("network", "Network", "🌐", "Specialists", "Internet, Wi-Fi, DNS, VPN, proxy, certificates, clock.",
             ("network",), "system", ("Wi-Fi is connected but websites do not open.",)),
    SubAgent("settings", "Settings", "⚙️", "Specialists", "Read Windows settings, open Settings pages, change personal preferences.",
             ("settings",), "system", ("Is developer mode on or off in my settings?",)),
    SubAgent("software", "Software", "📦", "Specialists", "Installed programs, recent changes, Windows Update, approved catalogue.",
             ("software",), "system", ("Is Zoom installed on this computer?",)),
    SubAgent("logs", "Logs", "📜", "Specialists", "App crashes and recent errors from the event logs.",
             ("logs",), "system", ("Which apps crashed this week?",)),
    SubAgent("security", "Security", "🛡️", "Specialists", "Antivirus and firewall status, suspicious link checks.",
             ("security",), "system", ("Is this link safe? http://paypa1-secure.xyz/login",)),
    SubAgent("account", "Account", "👤", "Specialists", "Who am I, admin rights, password expiry.",
             ("account",), "system", ("Do I have admin rights on this laptop?",)),
    SubAgent("devices", "Devices and printing", "🖨️", "Specialists",
             "Troubleshoots printing end to end (print service, queue, file, printer, network), fixes what is on your "
             "computer and tells you what to do about the rest. Also headsets, monitors and USB devices.",
             ("devices",), "system", ("My printer is not printing.", "Why won't report.pdf print?")),
    SubAgent("knowledge", "Knowledge", "📚", "Specialists", "How-to steps, policies and error codes from the company knowledge base, with sources.",
             ("howto",), "knowledge", ("How do I connect to the VPN?", "What is the BYOD policy?")),
    # ---- special agents: act on systems, usually through a connector ------------------------------------
    SubAgent("autopilot", "Autopilot", "🧭", "Special agents",
             "The general agent: plans, acts and checks in a loop across every ready connector. Use it for tasks "
             "that need several steps or systems. Turn on Autopilot mode in the settings to send everything here.",
             (), "", ("Read the budget file in my Documents.", "Summarise my unread email.")),
    SubAgent("service_desk", "Service desk (tickets)", "🎫", "Special agents",
             "Raises, lists and tracks IT tickets with the findings attached. Can also create ServiceNow incidents.",
             ("it_request", "servicenow"), "tickets", ("I need a new keyboard.", "Status of ITB-0003")),
    SubAgent("computer_use", "Computer use", "🖱️", "Special agents",
             "Opens websites and apps, installs approved software, writes notes in Notepad, runs the test-portal download.",
             ("computer_use",), "desktop", ("Open YouTube in Chrome.", "Install 7-Zip.")),
    SubAgent("web", "Web agent", "🕸️", "Special agents",
             "Reads public web pages as text and searches the web. Everything it reads is treated as untrusted data.",
             ("web",), "web", ("Search the web: clear Teams cache.",)),
    SubAgent("files", "Files agent", "🗂️", "Special agents",
             "Lists, finds, reads and writes files, only inside the folders you allow. Overwrites keep a backup.",
             ("files",), "files", ("List the files in my Downloads folder.",)),
    SubAgent("shell", "PowerShell agent", "⌨️", "Special agents",
             "Runs one PowerShell command after you approve its exact text. Dangerous commands are blocked.",
             ("shell",), "shell", ("Use PowerShell to show Windows uptime.",)),
    SubAgent("mail", "Mail and calendar agent", "✉️", "Special agents",
             "Reads and searches mail, shows the calendar, drafts or sends mail and creates events (Microsoft 365).",
             ("m365",), "microsoft365", ("Show my unread emails.", "What is on my calendar this week?")),
    SubAgent("directory", "Account self-service", "🔑", "Special agents",
             "Password reset and unlock: opens your organisation's official verified page. It never resets a password itself.",
             ("directory",), "directory", ("I forgot my password.",)),
    SubAgent("intune", "Device management (Intune)", "🖥️", "Special agents",
             "Shows your managed devices and compliance, and asks Intune to sync a device.",
             ("intune",), "intune", ("Is my laptop compliant?",)),
    SubAgent("defender", "Security alerts (Defender)", "🚨", "Special agents",
             "Reads recent Microsoft Defender alerts for the account.",
             ("defender",), "defender", ("Any security alerts for me?",)),
)


def agent_status(agent: SubAgent) -> str:
    """ready | needs setup | disabled. Autopilot is ready when the model is configured."""
    if not agent.connector:
        return "ready"
    return CONNECTORS[agent.connector].status()


def tool_counts(agent: SubAgent) -> dict:
    specs = [t for t in TOOLS.values() if t.domain in agent.domains]
    return {"total": len(specs), "read_only": sum(1 for t in specs if t.risk == R0),
            "approval": sum(1 for t in specs if t.risk != R0)}
