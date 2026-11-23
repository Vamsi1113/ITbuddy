"""Tobi - Streamlit interface: chat, live status, approval buttons, before/after, tickets, history.

Run:  streamlit run app.py
"""
from __future__ import annotations

import base64
import html
import os
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from agent import live, runner
from agent.catalog import SUBAGENTS, agent_status, tool_counts
from agent.graph import build_graph
from agent.llm import describe_model
from agent.specialists import DOMAINS
from appconfig import cfg
from connectors.base import CONNECTORS
from safety import audit, policy
from tools import tickets
from tools.registry import R0, TOOLS
from ui_theme import apply_theme, card_header, section

# RAG: initialise index in the background (silent if unavailable)
try:
    from rag.startup import ensure_rag_index
    ensure_rag_index(background=True)
except Exception:
    pass

ASSETS = Path(__file__).parent / "assets"
LOGO = ASSETS / "logo.png"           # blue robot mascot (Pixabay, OpenClipart-Vectors)
AVATAR = ASSETS / "favicon.png"

st.set_page_config(page_title="Tobi", page_icon=str(AVATAR) if AVATAR.exists() else "🛠️", layout="wide")
apply_theme()

OUTCOME_LABELS = {
    "fixed": "✅ Done and verified",
    "done": "✅ Done",
    "not_fixed": "⚠️ Problem remains - ticket opened",
    "rejected": "🚫 Change rejected - nothing changed",
    "refused": "⛔ Blocked by the safety policy",
    "no_action": "ℹ️ Answered - nothing changed",
    "escalated": "🎫 Ticket opened for IT",
    "unsupported": "❓ I need more detail",
    "chat": "💬 Tobi",
    "error": "❌ Stopped with an error",
    "running": "⏳ Waiting / not finished",
}
RISK_LABELS = {1: "Low-impact change (R1)", 2: "Medium change that cannot be undone (R2)"}

EXAMPLE_GROUPS = (
    ("Fix a problem", "I check the real system before I answer.",
     ("My computer is very slow.", "My C drive is almost full.", "Wi-Fi is connected but websites do not open.",
      "I forgot my password.")),
    ("Find something out", "Answers come from your own knowledge base, with the source.",
     ("How do I connect to the VPN?", "Is Zoom installed on this computer?", "Which apps crashed this week?",
      "Is developer mode on or off in my settings?")),
    ("Get something done", "Every change waits for your approval.",
     ("Open YouTube in Chrome.", "Search for HeyGen and open its website.", "Install 7-Zip.",
      "Open Notepad, write a summary of my system health and save it in Documents.")),
)


@st.cache_resource
def get_graph():
    return build_graph()


def init_state() -> None:
    st.session_state.setdefault("messages", [])   # {"role", "content", "comparison", "outcome", "steps", "task_id"}
    st.session_state.setdefault("pending", None)  # {"task_id", "approval", "steps"}
    st.session_state.setdefault("live_feed", [])   # events of the current task: {"t", "agent", "tool", "text", "image"}
    st.session_state.setdefault("live_running", False)


def status_line(event: dict) -> str:
    tool = f" (`{event['tool']}`)" if event.get("tool") else ""
    return f"**{event['agent']}**{tool}: {event['text']}"


FEED_ICONS = {"open_website": "🌐", "web_search": "🔎", "read_webpage": "🌐", "open_folder": "📁", "list_folder": "📁",
              "read_text_file": "📄", "write_text_file": "✍️", "search_files": "📁", "run_powershell": "⌨️",
              "install_software": "📦", "open_application": "🖱️", "start_password_reset": "🔑", "mail_send": "✉️",
              "mail_list_recent": "✉️", "calendar_upcoming": "📅", "raise_ticket": "🎫"}


def feed_icon(event: dict) -> str:
    text = event.get("text", "")
    if text.startswith("Done:"):
        return "✅"
    if "failed" in text.lower() or "blocked" in text.lower():
        return "⚠️"
    if "approval" in text.lower():
        return "⏸️"
    return FEED_ICONS.get(event.get("tool") or "", "⚙️")


def render_dock(ph) -> None:
    """The Live view panel docked at the bottom of the chat page: latest screenshot + a timeline of steps."""
    feed = st.session_state.get("live_feed") or []
    if not feed or not st.session_state.get("live_view", True):
        ph.empty()
        return
    running = st.session_state.get("live_running", False)
    shots = [e for e in feed if e.get("image") and os.path.exists(e["image"])]
    rows = "".join(
        f'<div class="lv-row"><span class="lv-t">{html.escape(e["t"])}</span><span class="lv-i">{feed_icon(e)}</span>'
        f'<span class="lv-x"><b>{html.escape(str(e["agent"]))}</b> {html.escape(str(e["text"]))[:150]}</span></div>'
        for e in reversed(feed[-14:]))      # newest first: the stylesheet shows it at the bottom of a scrollable list
    head = ('<div class="lv-head">' + ('<span class="lv-live">● Live</span>' if running else '<span class="lv-idle">● Last run</span>')
            + f'<span class="lv-title">Live view</span><span class="lv-count">{len(feed)} steps</span></div>')
    with ph.container():
        st.markdown(head, unsafe_allow_html=True)
        if shots:
            left, right = st.columns([1, 1.7], gap="medium")
            left.image(shots[-1]["image"], caption=str(shots[-1]["text"])[:70], width="stretch")
            right.markdown(f'<div class="lv-feed">{rows}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="lv-feed">{rows}</div>', unsafe_allow_html=True)


def run_with_status(label: str, fn, earlier_steps: list[str] | None = None, dock=None) -> tuple[dict, list[str]]:
    """Run one graph segment and show each step live (in the status box and, if given, in the Live view dock)."""
    steps = list(earlier_steps or [])
    st.session_state.live_running = True
    with st.status(label, expanded=True) as box:
        for line in steps:
            st.markdown(line)

        def on_status(event: dict) -> None:
            line = status_line(event)
            steps.append(line)
            st.markdown(line)
            box.update(label=f"{event['agent']}: {event['text']}")
            st.session_state.live_feed.append({"t": time.strftime("%H:%M:%S"), "agent": event["agent"],
                                               "tool": event.get("tool"), "text": event["text"],
                                               "image": event.get("image")})
            if dock is not None:
                render_dock(dock)

        try:
            result = fn(on_status)
        except Exception as e:  # never hide a failure
            st.session_state.live_running = False
            box.update(label="Stopped with an error", state="error")
            st.error(f"{type(e).__name__}: {e}")
            return {"status": "crashed", "error": f"{type(e).__name__}: {e}"}, steps
        st.session_state.live_running = bool(result["status"] == "needs_approval")
        if result["status"] == "needs_approval":
            box.update(label="Waiting for your approval", state="running", expanded=False)
        else:
            box.update(label="Finished", state="complete", expanded=False)
    return result, steps


def render_comparison(rows: list[dict]) -> None:
    df = pd.DataFrame(rows).rename(columns={"metric": "Measurement", "before": "Before", "after": "After"})
    st.dataframe(df.astype(str), hide_index=True, width="stretch")


def render_message(msg: dict, index: int) -> None:
    with st.chat_message(msg["role"], avatar=assistant_avatar() if msg["role"] == "assistant" else None):
        if msg.get("basis") or msg.get("steps"):
            with st.expander("Steps taken", expanded=False):
                for line in (msg.get("basis") or msg["steps"]):      # the rules and sources behind the answer
                    st.markdown(line)
        if msg.get("outcome"):
            st.markdown(f"**{OUTCOME_LABELS.get(msg['outcome'], msg['outcome'])}**")
        st.markdown(msg["content"])
        if msg.get("comparison"):
            st.markdown("**Before and after**")
            render_comparison(msg["comparison"])
        if msg["role"] == "assistant" and msg.get("task_id"):
            rating = st.feedback("thumbs", key=f"fb{index}")
            if rating is not None and msg.get("rated") != rating:
                msg["rated"] = rating
                audit.log_event(msg["task_id"], "feedback", detail="helpful" if rating == 1 else "not helpful")


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
            "comparison": state.get("comparison"), "steps": steps, "task_id": result["task_id"],
            "basis": state.get("basis") or [],
        })
        st.session_state.pending = None


def chat_history() -> list[dict]:
    """The earlier messages of this chat (without the one just typed), so follow-ups are understood."""
    from agent.memory import MAX_TURNS, Conversation
    conv = Conversation(MAX_TURNS)
    for msg in st.session_state.messages[:-1]:
        conv.add(msg.get("role", "user"), str(msg.get("content") or ""))
    return conv.turns()


def greeting() -> str:
    hour = time.localtime().tm_hour
    return "Good morning." if hour < 12 else "Good afternoon." if hour < 18 else "Good evening."


def hero_html() -> str:
    uri = _logo_data_uri()
    art = f'<div class="ib-hero-art"><div class="ib-blob"></div><img src="{uri}" alt=""></div>' if uri else ""
    return ('<div class="ib-hero"><div>'
            f'<h1 class="ib-hero-title">{greeting()}<span>What can I fix for you?</span></h1>'
            "<p class=\"ib-hero-sub\">Tell me what is not working. I check your computer, ask before I change anything, "
            "and show you what I did.</p></div>" + art + "</div>")


def chat_page() -> None:
    fresh = not st.session_state.messages and not st.session_state.pending
    if fresh:
        st.markdown(hero_html(), unsafe_allow_html=True)
    else:
        st.markdown(brand_header(56, "Your IT support agent"), unsafe_allow_html=True)
    if st.session_state.get("autopilot"):
        st.info("🧭 **Autopilot mode is on.** Every request goes to the general agent, which plans and uses tools "
                "from all ready connectors step by step. Changes still wait for your approval.")

    for i, msg in enumerate(st.session_state.messages):
        render_message(msg, i)

    with st.container(key="live_dock"):          # pinned to the bottom of the page by the stylesheet
        dock = st.empty()
    render_dock(dock)

    pending = st.session_state.pending
    if pending:
        a = pending["approval"]
        with st.chat_message("assistant", avatar=assistant_avatar()):
            with st.expander("Steps taken", expanded=False):
                for line in pending["steps"]:
                    st.markdown(line)
            st.markdown(f"**Finding ({a['agent']} agent)**\n\n{a['diagnosis']}")
            with st.container(border=True, key="approval_card"):
                st.markdown(f"#### Approval needed: {a['summary']}")
                st.caption(RISK_LABELS.get(a.get("risk", 1), ""))
                st.markdown(f"**What will change**\n\n{a['what_changes']}")
                st.markdown("**Planned steps**\n\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(a["steps"], 1)))
                col1, col2 = st.columns(2)
                approve = col1.button("✅ Approve", type="primary", width="stretch")
                reject = col2.button("❌ Reject", width="stretch")
            if approve or reject:
                label = "Running the approved change" if approve else "Recording your decision"
                result, steps = run_with_status(
                    label, lambda cb: runner.resume(get_graph(), pending["task_id"], approve, cb), pending["steps"], dock)
                finish(result, steps)
                st.rerun()
        return  # no new request while an approval is waiting

    prompt = st.chat_input("Describe your problem, for example: My computer is very slow")
    prompt = st.session_state.pop("queued_prompt", None) or prompt
    if not st.session_state.messages:
        cols = st.columns(3, gap="medium")
        for g, (title, blurb, examples) in enumerate(EXAMPLE_GROUPS):
            with cols[g].container(key=f"tile_{g}", height=304):
                st.markdown(f'<div class="ib-tile-title">{html.escape(title)}</div>'
                            f'<div class="ib-tile-sub">{html.escape(blurb)}</div>', unsafe_allow_html=True)
                for i, example in enumerate(examples):
                    if st.button(example, key=f"chip_{g}_{i}", width="stretch"):
                        prompt = example
    if prompt:
        st.session_state.live_feed = []           # a new task starts a new live view
        st.session_state.messages.append({"role": "user", "content": prompt})
        render_message(st.session_state.messages[-1], len(st.session_state.messages) - 1)
        with st.chat_message("assistant", avatar=assistant_avatar()):
            result, steps = run_with_status(
                "Starting", lambda cb: runner.start(
                    get_graph(), prompt, cb, mode="autopilot" if st.session_state.get("autopilot") else None,
                    history=chat_history()), None, dock)
        finish(result, steps)
        st.rerun()


def tickets_page() -> None:
    st.title("Tickets")
    st.caption("Built-in ticket desk. Tobi opens a ticket, with its findings attached, whenever a request "
               "needs IT staff or a fix did not work. An ITSM connector (ServiceNow, Jira) can replace it later.")
    rows = tickets.all_tickets()
    if not rows:
        st.info("No tickets yet. Try: \"I need a new keyboard\" or \"Please reset my password\".")
        return
    st.dataframe(pd.DataFrame([{
        "Ticket": tickets.ticket_ref(r["id"]), "Title": r["title"], "Category": r["category"].replace("_", " "),
        "Priority": r["priority"], "Status": r["status"], "Opened": r["created"][:16].replace("T", " "),
    } for r in rows]), hide_index=True, width="stretch")
    choice = st.selectbox("Open a ticket", [r["id"] for r in rows],
                          format_func=lambda i: next(f"{tickets.ticket_ref(r['id'])} - {r['title'][:60]}"
                                                     for r in rows if r["id"] == i))
    row = next(r for r in rows if r["id"] == choice)
    st.markdown(f"**{tickets.ticket_ref(row['id'])}: {row['title']}**  \nRequester `{row['requester']}`, "
                f"{row['category'].replace('_', ' ')}, priority {row['priority']}, {row['status']}")
    st.markdown(f"**Summary**\n\n{row['summary']}")
    if row.get("work_notes"):
        with st.expander("Work notes from Tobi (diagnostics and steps tried)", expanded=False):
            st.code(row["work_notes"], language=None)
    statuses = ["open", "in_progress", "resolved", "closed"]
    new = st.selectbox("Status (IT staff)", statuses, index=statuses.index(row["status"]), key=f"st{choice}")
    if new != row["status"]:
        tickets.set_status(choice, new)
        tickets.add_work_note(choice, f"Status changed to {new} in the Tobi console")
        st.rerun()


def history_page() -> None:
    st.title("History")
    st.caption("Every request, tool call, approval decision and result is saved in the audit log.")
    tasks = audit.list_tasks(200)
    if not tasks:
        st.info("No tasks yet.")
        return
    df = pd.DataFrame([{
        "Started": t["started"].replace("T", " ")[:19],
        "Request": t["request"],
        "Agent": DOMAINS[t["agent"]].label if t["agent"] in DOMAINS else (t["agent"] or ""),
        "Outcome": OUTCOME_LABELS.get(t["outcome"], t["outcome"]),
        "Task ID": t["task_id"],
    } for t in tasks])
    st.dataframe(df, hide_index=True, width="stretch")

    choice = st.selectbox("Show the audit trail of a task", [t["task_id"] for t in tasks],
                          format_func=lambda tid: next(f"{t['started'][:19].replace('T', ' ')} - {t['request'][:60]}"
                                                       for t in tasks if t["task_id"] == tid))
    task = next(t for t in tasks if t["task_id"] == choice)
    if task.get("summary"):
        st.markdown(f"**Final report**\n\n{task['summary']}")
    events = audit.task_events(choice)
    st.dataframe(pd.DataFrame([{
        "Time": e["ts"][11:19], "Event": e["event"], "Agent": e["agent"] or "", "Tool": e["tool"] or "",
        "Tier": "" if e["risk_level"] is None else f"R{e['risk_level']}",
        "Arguments": e["args"] or "", "Detail": e["detail"] or "",
    } for e in events]), hide_index=True, width="stretch")


@st.cache_resource
def _logo_data_uri() -> str:
    try:
        return "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode()
    except OSError:
        return ""


def brand_header(size_px: int, subtitle: str = "") -> str:
    """The robot logo next to the product name."""
    uri = _logo_data_uri()
    img = f'<img src="{uri}" alt="Tobi" style="width:{size_px}px;height:{size_px}px">' if uri else "🛠️"
    sub_html = f'<div class="ib-brand-sub">{html.escape(subtitle)}</div>' if subtitle else ""
    return f'<div class="ib-brand">{img}<div><div class="ib-brand-name">Tobi</div>{sub_html}</div></div>'


def assistant_avatar():
    return str(AVATAR) if AVATAR.exists() else None


CARD_HEIGHT = 262      # every agent card is exactly this tall
STATUS_BADGE = {"ready": "🟢 Ready", "needs setup": "🟠 Needs setup", "disabled": "⚪ Switched off"}


def _ask(prompt: str) -> None:
    """Send an example to the chat page."""
    st.session_state.queued_prompt = prompt
    st.session_state.page = "Chat"


def agents_page() -> None:
    st.title("Agents and connectors")
    ready = sum(1 for c in CONNECTORS.values() if c.status() == "ready")
    st.caption(f"{len(SUBAGENTS)} agents, {ready} of {len(CONNECTORS)} connectors ready, {len(TOOLS)} tools. "
               "Read-only tools (R0) run automatically. Changes (R1, R2) always wait for your approval. "
               "High-risk actions (R3) are never run: they become a ticket for IT.")
    tab_agents, tab_connectors, tab_tools = st.tabs(["Agents", "Connectors", "All tools"])

    with tab_agents:
        for group, blurb in (("Special agents", "Agents that act on systems. Most work through a connector."),
                             ("Specialists", "Diagnose, answer from real data, propose a fix, verify it.")):
            st.markdown(section(group), unsafe_allow_html=True)
            st.caption(blurb)
            members = [a for a in SUBAGENTS if a.group == group]
            for row_start in range(0, len(members), 3):
                cols = st.columns(3)
                for col, agent in zip(cols, members[row_start:row_start + 3]):
                    counts = tool_counts(agent)
                    meta = (f"{counts['total']} tool{'s' if counts['total'] != 1 else ''}: {counts['read_only']} read-only, {counts['approval']} need approval"
                            if counts["total"] else "Uses every ready connector")
                    # Every card has the same fixed height, so the grid is always even.
                    with col.container(key=f"card_agent_{agent.id}", height=CARD_HEIGHT):
                        st.markdown(card_header(agent.icon, agent.name, agent_status(agent))
                                    + f'<div class="ib-purpose">{html.escape(agent.purpose)}</div>'
                                    + f'<div class="ib-meta">{html.escape(meta)}</div>', unsafe_allow_html=True)
                        for j, example in enumerate(agent.examples[:2]):
                            st.button(f"💬 {example}", key=f"try_{agent.id}_{j}", width="stretch",
                                      on_click=_ask, args=(example,))

    with tab_connectors:
        st.caption("A connector is a system Tobi can reach. Switch one on with `enabled: true` under "
                   "`connectors:` in config.yaml; credentials go in the `.env` file, never in config.yaml.")
        for c in CONNECTORS.values():
            status = c.status()
            with st.container(key=f"card_conn_{c.id}"):
                st.markdown(card_header("🔌", c.name, status)
                            + f'<div class="ib-purpose">{html.escape(c.description)}</div>'
                            + f'<div class="ib-meta">{html.escape(c.kind)} connector</div>', unsafe_allow_html=True)
                names = c.tool_names()
                if status == "needs setup":
                    st.warning(f"Missing in .env: {', '.join(c.missing())}. {c.setup}")
                elif status == "disabled" and c.setup:
                    st.caption(f"Switched off. {c.setup}")
                if names:
                    with st.expander(f"{len(names)} tools"):
                        rows = [{"Tool": n, "Tier": f"R{TOOLS[n].risk}",
                                 "Runs": "automatically" if TOOLS[n].risk == R0 else "after approval",
                                 "What it does": TOOLS[n].description} for n in names]
                        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.markdown(section("Model"), unsafe_allow_html=True)
        st.markdown(f"Active model: **{describe_model()}**. Change `model.provider` in config.yaml "
                    "(`nvidia` or `ollama`). Cloud prompts have passwords, tokens and keys removed first.")

    with tab_tools:
        query = st.text_input("Filter tools", placeholder="type part of a name or description")
        tier = st.multiselect("Tier", ["R0", "R1", "R2"], default=["R0", "R1", "R2"])
        rows = []
        for t in TOOLS.values():
            owner = next((c for c in CONNECTORS.values() if t.domain in c.domains), None)
            text = f"{t.name} {t.description} {t.domain}".lower()
            if f"R{t.risk}" in tier and (not query or query.lower() in text):
                rows.append({"Tool": t.name, "Connector": owner.name if owner else t.domain, "Tier": f"R{t.risk}",
                             "Status": STATUS_BADGE[owner.status()] if owner else "🟢 Ready",
                             "What it does": t.description})
        st.dataframe(pd.DataFrame(sorted(rows, key=lambda r: (r["Connector"], r["Tier"], r["Tool"]))),
                     hide_index=True, width="stretch")


PAGES = ["Chat", "Agents and connectors", "Tickets", "History"]


def main() -> None:
    init_state()
    with st.sidebar:
        st.markdown(brand_header(88, "Your IT support agent"), unsafe_allow_html=True)
        page = st.radio("Page", PAGES, key="page", label_visibility="collapsed")
        st.divider()
        st.toggle("🧭 Autopilot mode", key="autopilot",
                  help="Send every request to the general agent, which plans and chains tools across all ready "
                       "connectors (files, PowerShell, web, mail, tickets ...). Changes still need your approval.")
        st.toggle("📺 Live view", key="live_view", value=True,
                  help="Shows a panel at the bottom of the chat with screenshots and a timeline of what the agent "
                       "does (browser, folders, files). Screenshots stay on this computer and are never sent to the model.")
        live.set_enabled(bool(st.session_state.get("live_view", True)))
        st.session_state.setdefault("read_only", policy.is_read_only())
        read_only = st.toggle("Read-only mode", key="read_only",
                              help="Kill switch: the agent can only look, never change anything.")
        policy.set_read_only(read_only)
        ready = [c.name for c in CONNECTORS.values() if c.status() == "ready"]
        st.caption(f"Model: `{describe_model()}`")
        st.caption(f"Connectors ready: {len(ready)} of {len(CONNECTORS)}")
        st.caption("R0 read-only runs automatically. R1/R2 changes wait for your approval. "
                   "R3 actions become a ticket for IT.")
        if st.button("New conversation", width="stretch", disabled=bool(st.session_state.pending)):
            st.session_state.messages = []
            st.rerun()
        st.markdown('<div class="ib-credit">Logo: <a href="https://pixabay.com/users/openclipart-vectors-30363/" '
                    'target="_blank">OpenClipart-Vectors</a> from <a href="https://pixabay.com/" target="_blank">Pixabay</a></div>',
                    unsafe_allow_html=True)
    {"Chat": chat_page, "Agents and connectors": agents_page, "Tickets": tickets_page,
     "History": history_page}[page]()


main()
