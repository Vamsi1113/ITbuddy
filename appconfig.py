"""Loads config.yaml once. Every module reads settings from here."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def load_config() -> dict:
    path = Path(os.environ.get("IT_BUDDY_CONFIG", ROOT / "config.yaml"))
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def cfg(*keys, default=None):
    """cfg("limits", "tool_timeout_seconds") -> value."""
    node = load_config()
    for k in keys:
        if not isinstance(node, dict) or k not in node:
            return default
        node = node[k]
    return node


def expand(path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path)))


def data_path(key: str) -> Path:
    p = ROOT / cfg("paths", key)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
