"""IT Buddy - Streamlit interface: chat, live status, approval buttons, before/after, history.

Run:  streamlit run app.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from agent import runner
from agent.graph import build_graph
from appconfig import cfg
from safety import audit

st.set_page_config(page_title="IT Buddy", page_icon="🛠️", layout="centered")

OUTCOME_LABELS = {
    "fixed": "✅ Fixed and verified",
    "not_fixed": "⚠️ Problem remains - contact IT",
    "rejected": "🚫 Fix rejected - nothing changed",
    "refused": "⛔ Refused - contact IT",
    "no_action": "ℹ️ No change needed",
    "unsupported": "❓ Not supported",
    "error": "❌ Stopped with an error",
    "running": "⏳ Waiting / not finished",
}

EXAMPLES = [
    "My computer is very slow.",
    "My C drive is almost full.",
    "Wi-Fi is connected but websites do not open.",
    "Open Notepad, write a summary of my system health and save it in Documents.",
    "Open the test portal and download the latest report.",
]


@st.cache_resource
def get_graph():
    return build_graph()


def init_state() -> None:
    st.session_state.setdefault("messages", [])   # {"role", "content", "comparison", "outcome", "steps"}
    st.session_state.setdefault("pending", None)  # {"task_id", "approval", "steps"}


def status_line(event: dict) -> str:
    tool = f" · `{event['tool']}`" if event.get("tool") else ""
    return f"**{event['agent']}**{tool}: {event['text']}"


def run_with_status(label: str, fn, earlier_steps: list[str] | None = None) -> tuple[dict, list[str]]:
    """Run one graph segment and show each step live (FR-2)."""
    steps = list(earlier_steps or [])
    with st.status(label, expanded=True) as box:
        for line in steps:
            st.markdown(line)

        def on_status(event: dict) -> None:
            line = status_line(event)
            steps.append(line)
            st.markdown(line)
            box.update(label=f"{event['agent']}: {event['text']}")

        try:
            result = fn(on_status)
        except Exception as e:  # never hide a failure (FR-18)
            box.update(label="Stopped with an error", state="error")
            st.error(f"{type(e).__name__}: {e}")
            return {"status": "crashed", "error": f"{type(e).__name__}: {e}"}, steps
        if result["status"] == "needs_approval":
            box.update(label="Waiting for your approval", state="running", expanded=False)
        else:
            box.update(label="Finished", state="complete", expanded=False)
    return result, steps


def render_comparison(rows: list[dict]) -> None:
    df = pd.DataFrame(rows).rename(columns={"metric": "Measurement", "before": "Before", "after": "After"})
    st.dataframe(df.astype(str), hide_index=True, use_container_width=True)


def render_message(msg: dict) -> None:
    with st.chat_message(msg["role"]):
        if msg.get("steps"):
            with st.expander("Steps taken", expanded=False):
                for line in msg["steps"]:
                    st.markdown(line)
        if msg.get("outcome"):
            st.markdown(f"**{OUTCOME_LABELS.get(msg['outcome'], msg['outcome'])}**")
        st.markdown(msg["content"])
        if msg.get("comparison"):
            st.markdown("**Before and after**")
            render_comparison(msg["comparison"])


def finish(result: dict, steps: list[str]) -> None:
    if result["status"] == "crashed":
        st.session_state.messages.append({"role": "assistant", "outcome": "error", "steps": steps,
                                          "content": f"I had to stop: {result['error']}"})
        st.session_state.pending = None
    elif result["status"] == "needs_approval":
        st.session_state.pending = {"task_id": result["task_id"], "approval": result["approval"], "steps": steps}
    else:
        state = result["state"]
        st.session_state.messages.append({
            "role": "assistant", "content": state.get("report", ""), "outcome": state.get("outcome"),
            "comparison": state.get("comparison"), "steps": steps,
        })
        st.session_state.pending = None


def chat_page() -> None:
    st.title("🛠️ IT Buddy")
    st.caption("Describe your computer problem. I check the real system, ask before I change anything, "
               "and re-check afterwards.")

    for msg in st.session_state.messages:
        render_message(msg)

    pending = st.session_state.pending
    if pending:
        a = pending["approval"]
        with st.chat_message("assistant"):
            with st.expander("Steps taken", expanded=False):
                for line in pending["steps"]:
                    st.markdown(line)
            st.markdown(f"**Diagnosis ({a['agent']} agent)**\n\n{a['diagnosis']}")
            with st.container(border=True):
                st.markdown(f"#### Approval needed: {a['summary']}")
                st.markdown(f"**What will change**\n\n{a['what_changes']}")
                st.markdown("**Planned steps**\n\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(a["steps"], 1)))
                col1, col2 = st.columns(2)
                approve = col1.button("✅ Approve", type="primary", use_container_width=True)
                reject = col2.button("❌ Reject", use_container_width=True)
            if approve or reject:
                label = "Running the approved fix" if approve else "Recording your decision"
                result, steps = run_with_status(
                    label, lambda cb: runner.resume(get_graph(), pending["task_id"], approve, cb), pending["steps"])
                finish(result, steps)
                st.rerun()
        return  # no new request while an approval is waiting

    prompt = st.chat_input("Describe your problem, for example: My computer is very slow")
    if not st.session_state.messages:
        st.markdown("**Try one of these:**")
        for i, example in enumerate(EXAMPLES):
            if st.button(example, key=f"ex{i}", use_container_width=True):
                prompt = example
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        render_message(st.session_state.messages[-1])
        with st.chat_message("assistant"):
            result, steps = run_with_status(
                "Starting", lambda cb: runner.start(get_graph(), prompt, cb))
        finish(result, steps)
        st.rerun()


def history_page() -> None:
    st.title("📜 History")
    st.caption("Every request, tool call, approval decision and result is saved in the audit log.")
    tasks = audit.list_tasks(200)
    if not tasks:
        st.info("No tasks yet.")
        return
    df = pd.DataFrame([{
        "Started": t["started"].replace("T", " ")[:19],
        "Request": t["request"],
        "Agent": (t["agent"] or "").replace("_", " ").title(),
        "Outcome": OUTCOME_LABELS.get(t["outcome"], t["outcome"]),
        "Task ID": t["task_id"],
    } for t in tasks])
    st.dataframe(df, hide_index=True, use_container_width=True)

    choice = st.selectbox("Show the audit trail of a task", [t["task_id"] for t in tasks],
                          format_func=lambda tid: next(f"{t['started'][:19].replace('T', ' ')} - {t['request'][:60]}"
                                                       for t in tasks if t["task_id"] == tid))
    task = next(t for t in tasks if t["task_id"] == choice)
    if task.get("summary"):
        st.markdown(f"**Final report**\n\n{task['summary']}")
    events = audit.task_events(choice)
    st.dataframe(pd.DataFrame([{
        "Time": e["ts"][11:19], "Event": e["event"], "Agent": e["agent"] or "", "Tool": e["tool"] or "",
        "Level": "" if e["risk_level"] is None else str(e["risk_level"]),
        "Arguments": e["args"] or "", "Detail": e["detail"] or "",
    } for e in events]), hide_index=True, use_container_width=True)


def main() -> None:
    init_state()
    with st.sidebar:
        page = st.radio("Page", ["Chat", "History"], label_visibility="collapsed")
        st.divider()
        st.caption(f"Model: `{cfg('model', 'name')}`\n\nOllama: `{cfg('model', 'base_url')}`")
        st.caption("Level 1 (read-only) runs automatically. Level 2 changes always wait for your approval. "
                   "Level 3 (sensitive) is refused.")
        if st.button("New conversation", use_container_width=True, disabled=bool(st.session_state.pending)):
            st.session_state.messages = []
            st.rerun()
    if page == "Chat":
        chat_page()
    else:
        history_page()


main()
