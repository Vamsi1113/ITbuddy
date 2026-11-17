"""Router: one short model call that picks a specialist (FR-3, FR-4)."""
from __future__ import annotations

from agent import prompts
from agent.llm import ask_json

AGENTS = ("performance", "storage", "network", "computer_use")


def _validate(data: dict) -> dict:
    agent = str(data.get("agent", "")).strip().lower().replace(" ", "_").replace("-", "_")
    if agent not in AGENTS + ("none",):
        raise ValueError(f'"agent" must be one of {AGENTS + ("none",)}')
    return {"agent": agent, "question": str(data.get("question") or "").strip()}


def route(request: str) -> dict:
    """Return {"agent": ..., "question": ...}. Raises ModelError if the model fails."""
    return ask_json(prompts.ROUTER, f"Request: {request.strip()[:500]}", _validate)
