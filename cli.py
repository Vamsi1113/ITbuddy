"""Terminal runner (Phase 3 check). Usage: python cli.py "My computer is very slow."

Add --yes or --no to answer the approval prompt without typing.
"""
from __future__ import annotations

import sys

from agent import runner
from agent.graph import build_graph


def _status(event: dict) -> None:
    tool = f" [{event['tool']}]" if event.get("tool") else ""
    print(f"  ... {event['agent']}{tool}: {event['text']}", flush=True)


def main() -> int:
    args = [a for a in sys.argv[1:] if a not in ("--yes", "--no")]
    auto = True if "--yes" in sys.argv else False if "--no" in sys.argv else None
    request = " ".join(args).strip() or input("Describe your problem: ").strip()
    graph = build_graph()
    result = runner.start(graph, request, _status)
    if result["status"] == "needs_approval":
        a = result["approval"]
        print(f"\nDiagnosis ({a['agent']}): {a['diagnosis']}")
        print(f"\nProposed fix: {a['summary']}\nWhat will change: {a['what_changes']}\nSteps:")
        for i, step in enumerate(a["steps"], 1):
            print(f"  {i}. {step}")
        if auto is None:
            auto = input("\nApprove? [y/N] ").strip().lower() in ("y", "yes")
        print("-> Approved" if auto else "-> Rejected")
        result = runner.resume(graph, result["task_id"], auto, _status)
    state = result["state"]
    print(f"\nOutcome: {state.get('outcome')}\n\n{state.get('report')}")
    if state.get("comparison"):
        print("\nBefore and after:")
        for row in state["comparison"]:
            print(f"  {row['metric']}: {row['before']} -> {row['after']}")
    print(f"\nTask ID {result['task_id']} (see the audit log in data/audit.db)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
