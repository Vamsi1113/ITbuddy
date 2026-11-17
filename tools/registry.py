"""The tool catalogue: the only 14 actions an agent can take. There is no shell tool."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from tools import browser, desktop, network, performance, storage


@dataclass(frozen=True)
class ToolSpec:
    name: str
    func: Callable[..., dict]
    agent: str
    risk_level: int
    description: str


def _spec(func, agent, level, description):
    return ToolSpec(func.__name__, func, agent, level, description)


_ALL = [
    _spec(performance.get_system_health, "performance", 1, "CPU %, RAM %, uptime"),
    _spec(performance.get_running_processes, "performance", 1, "Top 5 processes by memory and by CPU"),
    _spec(performance.close_process, "performance", 2, "Closes one user process"),
    _spec(storage.get_disk_usage, "storage", 1, "Total and free space per drive"),
    _spec(storage.find_large_temp_folders, "storage", 1, "Size of each allowed temp folder"),
    _spec(storage.clean_approved_temp_files, "storage", 2, "Deletes files inside the allowed temp folders"),
    _spec(network.check_network_connection, "network", 1, "Pings the gateway and a public address, opens one website"),
    _spec(network.check_dns_resolution, "network", 1, "Resolves a short list of test hostnames"),
    _spec(network.get_network_config, "network", 1, "Adapter name, IP address, DNS servers"),
    _spec(network.flush_dns_cache, "network", 2, "Runs ipconfig /flushdns"),
    _spec(desktop.open_application, "computer_use", 2, "Opens an app from the allowed app list"),
    _spec(desktop.click_control, "computer_use", 2, "Clicks a named button or menu item"),
    _spec(desktop.type_text, "computer_use", 2, "Types text into the active control"),
    _spec(browser.run_browser_task, "computer_use", 2, "Runs one predefined Playwright script"),
]

TOOLS: dict[str, ToolSpec] = {t.name: t for t in _ALL}


def tools_for(agent: str) -> list[ToolSpec]:
    return [t for t in _ALL if t.agent == agent]
