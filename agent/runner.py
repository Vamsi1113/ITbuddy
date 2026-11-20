"""Runs the graph until it finishes or pauses for approval. Shared by the CLI and Streamlit."""
from __future__ import annotations

import uuid
from typing import Callable

from langgraph.types import Command


def new_task_id() -> str:
    return uuid.uuid4().hex[:12]


def _drive(graph, payload, task_id: str, on_status: Callable[[dict], None] | None) -> dict:
    config = {"configurable": {"thread_id": task_id}, "recursion_limit": 120}
    for mode, chunk in graph.stream(payload, config, stream_mode=["custom", "updates"]):
        if mode == "custom" and on_status:
            on_status(chunk)
    snapshot = graph.get_state(config)
    pending = [i for task in snapshot.tasks for i in task.interrupts]
    if pending:
        return {"status": "needs_approval", "task_id": task_id, "approval": pending[0].value}
    return {"status": "done", "task_id": task_id, "state": snapshot.values}


def start(graph, request: str, on_status=None, task_id: str | None = None, mode: str | None = None,
          history: list | None = None) -> dict:
    """mode="autopilot" sends the request to the general agent instead of letting the router choose.
    history: the earlier turns of this chat ([{"role": "user"|"assistant", "text"}]), so follow-ups are understood."""
    task_id = task_id or new_task_id()
    payload = {"task_id": task_id, "request": request, **({"mode": mode} if mode else {}),
               **({"history": list(history)} if history else {})}
    return _drive(graph, payload, task_id, on_status)


def resume(graph, task_id: str, approved: bool, on_status=None) -> dict:
    return _drive(graph, Command(resume={"approved": bool(approved)}), task_id, on_status)
