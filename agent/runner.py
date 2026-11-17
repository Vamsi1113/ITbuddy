"""Runs the graph until it finishes or pauses for approval. Shared by the CLI and Streamlit."""
from __future__ import annotations

import uuid
from typing import Callable

from langgraph.types import Command


def new_task_id() -> str:
    return uuid.uuid4().hex[:12]


def _drive(graph, payload, task_id: str, on_status: Callable[[dict], None] | None) -> dict:
    config = {"configurable": {"thread_id": task_id}}
    for mode, chunk in graph.stream(payload, config, stream_mode=["custom", "updates"]):
        if mode == "custom" and on_status:
            on_status(chunk)
    snapshot = graph.get_state(config)
    pending = [i for task in snapshot.tasks for i in task.interrupts]
    if pending:
        return {"status": "needs_approval", "task_id": task_id, "approval": pending[0].value}
    return {"status": "done", "task_id": task_id, "state": snapshot.values}


def start(graph, request: str, on_status=None, task_id: str | None = None) -> dict:
    task_id = task_id or new_task_id()
    return _drive(graph, {"task_id": task_id, "request": request}, task_id, on_status)


def resume(graph, task_id: str, approved: bool, on_status=None) -> dict:
    return _drive(graph, Command(resume={"approved": bool(approved)}), task_id, on_status)
