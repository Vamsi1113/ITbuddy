"""Tobi look and feel: a light, airy theme built from one four-colour palette.

    NAVY  #131B2B   text and the smallest, sharpest accents (headings, primary buttons, active tab)
    SLATE #2F4A63   secondary text, borders, "ready" pills, hover emphasis
    TEAL  #5B91A3   accents, focus, accent bars, soft fills
    MINT  #CFEAE0   page and panel tints (the light base of the whole UI)

The page is a pale tint of MINT; cards are white-to-mint with SLATE-tinted borders. The dark colours appear
only as text and small details so the interface stays light. Type is a little smaller than Streamlit's default.
"""
from __future__ import annotations

import html

import streamlit as st

NAVY, SLATE, TEAL, MINT = "#131B2B", "#2F4A63", "#5B91A3", "#CFEAE0"

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500..800&family=Figtree:wght@400;500;600;700&display=swap');
:root {{
  --navy: {NAVY}; --slate: {SLATE}; --teal: {TEAL}; --mint: {MINT};
  --page: #EDF7F2;                          /* MINT lightened */
  --card-a: rgba(255, 255, 255, .78); --card-b: rgba(207, 234, 224, .62);
  --line: rgba(47, 74, 99, .16); --line-strong: rgba(91, 145, 163, .75);
  --soft: rgba(19, 27, 43, .8); --shadow: rgba(47, 74, 99, .16);
}}

/* ---- smaller type everywhere (the app is rem-based, so this scales every component) ---- */
html {{ font-size: 14px; }}
.stApp {{
  background: radial-gradient(900px 520px at 92% -8%, rgba(91, 145, 163, .22), transparent 62%),
              radial-gradient(700px 480px at -6% 105%, rgba(207, 234, 224, .95), transparent 60%), var(--page);
  color: var(--navy);
}}
h1 {{ font-size: 1.65rem !important; font-weight: 650 !important; letter-spacing: -.01em; color: var(--navy); }}
h2 {{ font-size: 1.25rem !important; }}
h3 {{ font-size: 1.02rem !important; }}
h4 {{ font-size: .95rem !important; }}
p, li, label, .stMarkdown {{ font-size: .88rem; }}
[data-testid="stCaptionContainer"], .stCaption {{ font-size: .74rem !important; color: var(--soft) !important; }}
.stButton > button, .stDownloadButton > button {{ font-size: .78rem !important; }}
[data-testid="stChatInput"] textarea {{ font-size: 1.1rem !important; line-height: 1.5 !important; min-height: 3.2rem; padding-top: .9rem !important; }}
[data-testid="stChatInput"] textarea::placeholder {{ font-size: 1.05rem; opacity: .7; }}
[data-testid="stSidebar"] * {{ font-size: 1rem; }}
[data-testid="stSidebar"] h2 {{ font-size: 1.4rem !important; }}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{ font-size: .86rem !important; line-height: 1.45; }}
[data-testid="stSidebar"] .stButton > button {{ font-size: .95rem !important; padding: .55rem .8rem; }}
[data-testid="stSidebar"] [role="radiogroup"] label {{ padding: .2rem 0; }}
[data-testid="stSidebar"] code {{ font-size: .85rem !important; }}
.block-container {{ padding-top: 2rem; max-width: 1280px; }}
code {{ background: rgba(91, 145, 163, .16) !important; color: var(--slate) !important; border-radius: 6px; }}
[data-testid="stHeader"] {{ background: transparent; }}

/* ---- sidebar: light mint panel ---- */
section[data-testid="stSidebar"] {{
  background: linear-gradient(185deg, #D9EEE6 0%, var(--mint) 55%, #BFDDD2 100%);
  border-right: 1px solid var(--line);
}}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{ color: var(--slate) !important; }}

/* chat avatars in the palette */
[data-testid="stChatMessageAvatarUser"] {{ background: var(--teal) !important; }}
[data-testid="stChatMessageAvatarAssistant"] {{ background: var(--slate) !important; }}

/* ---- buttons ---- */
.stButton > button {{
  background: rgba(255, 255, 255, .7); color: var(--slate); border: 1px solid var(--line); border-radius: 10px;
  transition: background .18s ease, border-color .18s ease, transform .18s ease, box-shadow .18s ease, color .18s ease;
}}
.stButton > button:hover {{
  background: #fff; border-color: var(--teal); color: var(--navy); transform: translateY(-1px);
  box-shadow: 0 5px 14px var(--shadow);
}}
.stButton > button[kind="primary"] {{ background: var(--slate); color: var(--mint); border-color: var(--slate); font-weight: 600; }}
.stButton > button[kind="primary"]:hover {{ background: var(--navy); color: #fff; border-color: var(--navy); }}

/* ---- chat, status, expanders, tabs, alerts ---- */
[data-testid="stChatMessage"] {{
  background: linear-gradient(160deg, var(--card-a), var(--card-b)); border: 1px solid var(--line); border-radius: 14px;
  padding: .8rem 1rem; transition: border-color .2s ease, box-shadow .2s ease;
}}
[data-testid="stChatMessage"]:hover {{ border-color: var(--line-strong); box-shadow: 0 6px 18px var(--shadow); }}
[data-testid="stExpander"], [data-testid="stStatusWidget"], details {{
  border: 1px solid var(--line) !important; border-radius: 12px !important; background: rgba(255, 255, 255, .55);
}}
.stTabs [data-baseweb="tab-list"] {{ gap: .3rem; border-bottom: 1px solid var(--line); }}
.stTabs [data-baseweb="tab"] {{
  font-size: .82rem; border-radius: 8px 8px 0 0; padding: .45rem .9rem; opacity: .65; color: var(--slate);
  transition: opacity .18s, background .18s;
}}
.stTabs [data-baseweb="tab"]:hover {{ opacity: 1; background: rgba(91, 145, 163, .16); }}
.stTabs [aria-selected="true"] {{ opacity: 1; color: var(--navy); font-weight: 600; }}
.stTabs [data-baseweb="tab-highlight"] {{ background: var(--slate); }}
[data-testid="stAlert"] {{ border-radius: 12px; border: 1px solid var(--line); background: rgba(91, 145, 163, .14); font-size: .82rem; color: var(--navy); }}
[data-testid="stDataFrame"] {{ border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: #fff; }}
[data-testid="stChatInput"] {{ border-radius: 16px; min-height: 3.6rem; border: 1px solid var(--line); background: rgba(255, 255, 255, .85); }}
input, textarea {{ border-radius: 10px !important; }}
hr {{ border-color: var(--line) !important; }}

/* ---- cards: agents and connectors (containers whose key starts with "card_") ---- */
[class*="st-key-card_"] {{
  background: linear-gradient(160deg, var(--card-a) 0%, var(--card-b) 100%);
  border: 1px solid var(--line); border-radius: 16px; padding: 1rem 1.05rem !important;
  opacity: .95; position: relative; overflow: hidden; box-shadow: 0 2px 8px rgba(47, 74, 99, .08);
  transition: opacity .2s ease, transform .2s ease, box-shadow .2s ease, border-color .2s ease;
}}
[class*="st-key-card_"]::before {{      /* accent bar that grows on hover */
  content: ""; position: absolute; left: 0; top: 0; height: 3px; width: 28%;
  background: linear-gradient(90deg, var(--slate), var(--teal)); border-radius: 0 3px 3px 0;
  transition: width .3s ease; z-index: 1;
}}
[class*="st-key-card_"]:hover {{
  opacity: 1; transform: translateY(-4px); border-color: var(--line-strong);
  box-shadow: 0 16px 32px rgba(47, 74, 99, .22), 0 0 0 1px rgba(91, 145, 163, .5);
}}
[class*="st-key-card_"]:hover::before {{ width: 100%; }}
[class*="st-key-card_"] .stButton > button {{ text-align: left; justify-content: flex-start; color: var(--slate); font-weight: 500; }}

.ib-head {{ display: flex; gap: .7rem; align-items: center; margin-bottom: .55rem; }}
.ib-ico {{
  width: 2.3rem; height: 2.3rem; border-radius: 11px; display: flex; align-items: center; justify-content: center;
  font-size: 1.15rem; background: rgba(207, 234, 224, .95); border: 1px solid var(--line); flex: none;
}}
.ib-name {{ font-size: .98rem; font-weight: 650; line-height: 1.15; color: var(--navy); }}
.ib-purpose {{ font-size: .8rem; line-height: 1.45; color: var(--soft); margin: .1rem 0 .55rem; }}
.ib-meta {{ font-size: .7rem; letter-spacing: .02em; color: var(--slate); margin-bottom: .55rem; font-weight: 500; }}
.pill {{
  display: inline-block; font-size: .66rem; font-weight: 600; letter-spacing: .03em; padding: .12rem .55rem;
  border-radius: 999px; margin-top: .2rem; border: 1px solid transparent;
}}
.pill.ready {{ background: var(--slate); color: var(--mint); }}
.pill.setup {{ background: rgba(91, 145, 163, .18); color: var(--slate); border-color: var(--teal); }}
.pill.off   {{ background: rgba(47, 74, 99, .08); color: rgba(47, 74, 99, .6); border-color: var(--line); }}
.ib-section {{
  font-size: .7rem; letter-spacing: .14em; text-transform: uppercase; color: var(--slate); font-weight: 650;
  margin: 1.2rem 0 .1rem; padding-left: .6rem; border-left: 3px solid var(--teal);
}}

/* ---- Live view dock: pinned above the chat box while the page scrolls ---- */
.st-key-live_dock {{
  position: sticky; bottom: 5.4rem; z-index: 60; margin-top: 1.2rem; padding: .7rem 1rem .6rem;
  background: linear-gradient(160deg, rgba(255, 255, 255, .94), rgba(207, 234, 224, .94));
  border: 1px solid var(--line-strong); border-radius: 16px; backdrop-filter: blur(8px);
  box-shadow: 0 -6px 26px rgba(47, 74, 99, .20);
}}
.st-key-live_dock:empty, .st-key-live_dock:not(:has(.lv-head)) {{ display: none; }}
.st-key-live_dock img {{ max-height: 210px; width: 100%; object-fit: contain; border-radius: 10px; border: 1px solid var(--line); }}
.st-key-live_dock [data-testid="stImageCaption"] {{ font-size: .7rem; color: var(--soft); }}
.lv-head {{ display: flex; align-items: center; gap: .6rem; margin-bottom: .45rem; }}
.lv-title {{ font-size: .8rem; font-weight: 650; color: var(--navy); letter-spacing: .02em; }}
.lv-count {{ margin-left: auto; font-size: .68rem; color: var(--slate); }}
.lv-live, .lv-idle {{ font-size: .64rem; font-weight: 700; letter-spacing: .08em; padding: .1rem .5rem; border-radius: 999px; }}
.lv-live {{ background: var(--slate); color: var(--mint); animation: lvpulse 1.3s ease-in-out infinite; }}
.lv-idle {{ background: rgba(47, 74, 99, .1); color: var(--slate); }}
@keyframes lvpulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: .55; }} }}
.lv-feed {{ display: flex; flex-direction: column; gap: .18rem; max-height: 210px; overflow: hidden; }}
.lv-row {{ display: flex; gap: .5rem; align-items: baseline; font-size: .76rem; line-height: 1.35; color: var(--navy);
          padding: .12rem .3rem; border-radius: 6px; }}
.lv-row:last-child {{ background: rgba(91, 145, 163, .18); }}
.lv-t {{ font-variant-numeric: tabular-nums; color: var(--slate); font-size: .68rem; flex: none; }}
.lv-i {{ flex: none; }}
.lv-x b {{ color: var(--slate); font-weight: 650; }}

/* ---- brand ---- */
.ib-brand {{ display: flex; align-items: center; gap: .85rem; margin: .2rem 0 .6rem; }}
.ib-brand img {{ flex: none; filter: drop-shadow(0 4px 8px rgba(47, 74, 99, .28)); transition: transform .25s ease; }}
.ib-brand:hover img {{ transform: rotate(-6deg) scale(1.06); }}
.ib-brand-name {{ font-size: 1.7rem; font-weight: 700; line-height: 1.05; color: var(--navy); letter-spacing: -.01em; }}
.ib-brand-sub {{ font-size: .8rem; color: var(--slate); margin-top: .2rem; }}
section[data-testid="stSidebar"] .ib-brand {{ flex-direction: column; align-items: flex-start; gap: .55rem; }}
section[data-testid="stSidebar"] .ib-brand-name {{ font-size: 1.55rem; }}
.ib-credit {{ font-size: .68rem; color: var(--slate); opacity: .8; margin-top: 1rem; line-height: 1.4; }}
.ib-credit a {{ color: var(--slate); text-decoration: underline; }}
[data-testid="stChatMessageAvatarCustom"] {{ background: rgba(207, 234, 224, .9) !important; border: 1px solid var(--line); }}

/* ================= v3: type, greeting, tiles, navigation ================= */
.stApp, .stApp p, .stApp li, .stApp label, .stApp button, .stApp input, .stApp textarea,
[data-testid="stSidebar"], [data-testid="stMarkdownContainer"] {{
  font-family: 'Figtree', 'Segoe UI', system-ui, sans-serif;
}}
h1, h2, h3, h4, .ib-brand-name, .ib-name, .ib-hero-title, .ib-tile-title, .ib-section {{
  font-family: 'Bricolage Grotesque', 'Figtree', 'Segoe UI', system-ui, sans-serif !important;
  letter-spacing: -.02em;
}}
.stApp :focus-visible {{ outline: 2px solid var(--teal) !important; outline-offset: 2px; border-radius: 8px; }}

/* section titles: plain sentence case, no tracking, no all caps */
.ib-section {{
  font-size: 1.15rem !important; font-weight: 650 !important; letter-spacing: -.015em !important; text-transform: none !important;
  color: var(--navy) !important; margin: 1.6rem 0 .1rem !important; padding-left: 0 !important; border-left: 0 !important;
}}
.lv-live, .lv-idle {{ letter-spacing: .01em !important; text-transform: none !important; font-size: .7rem !important; }}

/* ---- greeting (the one memorable moment) ---- */
.ib-hero {{ display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 2.4rem; padding: 1.4rem 0 1.8rem; }}
.ib-hero-title {{
  font-size: clamp(2.3rem, 4.4vw, 3.6rem); line-height: 1.03; font-weight: 700; color: var(--navy); margin: 0;
  letter-spacing: -.035em !important;
}}
.ib-hero-title span {{ display: block; color: var(--slate); font-weight: 600; }}
.ib-hero-sub {{ max-width: 34rem; font-size: 1.04rem; line-height: 1.55; color: var(--soft); margin: 1.1rem 0 0; }}
.ib-hero-art {{ position: relative; width: 190px; height: 190px; flex: none; }}
.ib-blob {{
  position: absolute; inset: 10% 0 0 10%; border-radius: 58% 42% 55% 45% / 48% 55% 45% 52%;
  background: radial-gradient(circle at 30% 28%, rgba(91, 145, 163, .6), rgba(207, 234, 224, .25) 72%);
}}
.ib-hero-art img {{ position: relative; width: 100%; transform: rotate(-5deg); filter: drop-shadow(0 12px 18px rgba(47, 74, 99, .3)); }}

@keyframes ib-rise {{ from {{ opacity: 0; transform: translateY(16px); }} to {{ opacity: 1; transform: none; }} }}
.ib-hero-title, .ib-hero-sub, .ib-hero-art {{ animation: ib-rise .85s cubic-bezier(.2, .7, .2, 1) both; }}
.ib-hero-art {{ animation-delay: .05s; }}
.ib-hero-sub {{ animation-delay: .14s; }}
[class*="st-key-tile_"] {{ animation: ib-rise .8s cubic-bezier(.2, .7, .2, 1) both; }}
.st-key-tile_0 {{ animation-delay: .28s; }} .st-key-tile_1 {{ animation-delay: .38s; }} .st-key-tile_2 {{ animation-delay: .48s; }}

/* ---- tiles with starter questions ---- */
[class*="st-key-tile_"] {{
  background: rgba(255, 255, 255, .58); backdrop-filter: blur(12px); border: 1px solid var(--line); border-radius: 22px;
  padding: 1.15rem 1.1rem 1rem !important; box-shadow: 0 2px 10px rgba(47, 74, 99, .07);
}}
.ib-tile-title {{ font-size: 1.15rem; font-weight: 650; color: var(--navy); line-height: 1.2; }}
.ib-tile-sub {{ font-size: .8rem; color: var(--soft); margin: .2rem 0 .85rem; line-height: 1.4; }}
[class*="st-key-chip_"] button {{
  justify-content: flex-start; text-align: left; height: auto; min-height: 2.7rem; padding: .6rem .9rem; white-space: normal;
  background: rgba(207, 234, 224, .6); border: 1px solid transparent; border-radius: 14px; color: var(--navy);
  font-size: .85rem !important; font-weight: 500; line-height: 1.35;
}}
[class*="st-key-chip_"] button:hover {{
  background: var(--slate); color: var(--mint); border-color: var(--slate); transform: translateX(4px); box-shadow: none;
}}

/* ---- sidebar navigation as pills ---- */
section[data-testid="stSidebar"] [role="radiogroup"] {{ gap: .2rem; }}
section[data-testid="stSidebar"] [role="radiogroup"] label {{
  padding: .55rem .85rem; border-radius: 13px; width: 100%; transition: background .18s ease, box-shadow .18s ease, transform .18s ease;
}}
section[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child {{ display: none; }}
section[data-testid="stSidebar"] [role="radiogroup"] label:hover {{ background: rgba(255, 255, 255, .5); transform: translateX(2px); }}
section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{
  background: rgba(255, 255, 255, .92); box-shadow: 0 3px 12px rgba(47, 74, 99, .16); font-weight: 650;
}}
section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {{ color: var(--navy); font-weight: 650; }}

/* ---- conversation: the user's words are the dark bubble, the agent's answer is the light glass ---- */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
  background: var(--slate); border-color: var(--slate);
}}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p {{ color: var(--mint) !important; }}

/* ---- the approval sheet ---- */
[class*="st-key-approval_card"] {{
  border: 1px solid var(--line-strong); border-left: 5px solid var(--teal); border-radius: 18px; padding: 1rem 1.2rem !important;
  background: linear-gradient(160deg, rgba(255, 255, 255, .95), rgba(207, 234, 224, .75));
  box-shadow: 0 12px 30px rgba(47, 74, 99, .16);
}}

@media (max-width: 760px) {{
  .ib-hero {{ grid-template-columns: 1fr; }}
  .ib-hero-art {{ display: none; }}
}}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ animation: none !important; transition: none !important; }}
}}

/* ---- v3 fixes after the first look ---- */
h1.ib-hero-title {{ font-size: clamp(2.4rem, 4.6vw, 3.7rem) !important; line-height: 1.02 !important; font-weight: 700 !important;
  letter-spacing: -.04em !important; padding: 0 !important; }}
h1.ib-hero-title span {{ font-weight: 600; }}
.ib-hero {{ padding-top: .4rem; }}

/* chips read left to right */
[class*="st-key-chip_"] button > div, [class*="st-key-chip_"] button span,
[class*="st-key-chip_"] button [data-testid="stMarkdownContainer"] {{ justify-content: flex-start !important; width: 100%; }}
[class*="st-key-chip_"] button p {{ text-align: left !important; font-size: .85rem; }}

/* navigation pills: hide the radio circle, keep the label */
section[data-testid="stSidebar"] [role="radiogroup"] label > div > div:not([data-testid="stMarkdownContainer"]) {{ display: none; }}
section[data-testid="stSidebar"] [role="radiogroup"] label p {{ font-size: .98rem; }}

/* ---- v3 polish ---- */
h1.ib-hero-title {{ color: var(--navy) !important; letter-spacing: -.028em !important; margin: 0 !important; }}
h1.ib-hero-title span {{ color: var(--slate) !important; }}
.ib-hero-sub {{ margin-top: .7rem !important; }}
[class*="st-key-card_"] button > div, [class*="st-key-card_"] button span,
[class*="st-key-card_"] button [data-testid="stMarkdownContainer"] {{ justify-content: flex-start !important; width: 100%; }}
[class*="st-key-card_"] button p {{ text-align: left !important; }}

/* ---- sidebar: very light sky blue, gradient, thick blended edge ---- */
section[data-testid="stSidebar"] {{
  background:
    radial-gradient(420px 260px at 20% 0%, rgba(255, 255, 255, .75), transparent 70%),
    linear-gradient(185deg, #F1F9FF 0%, #DDF0FC 38%, #C9E8F8 70%, #D3EEF0 100%) !important;
  border-right: 7px solid transparent !important;
  border-image: linear-gradient(180deg, #5B91A3 0%, #9AD3F0 28%, #CFEAE0 55%, #9AD3F0 78%, #5B91A3 100%) 1 !important;
  box-shadow: 8px 0 26px rgba(91, 145, 163, .22), inset -1px 0 0 rgba(255, 255, 255, .7);
}}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{ color: #2F4A63 !important; }}
section[data-testid="stSidebar"] hr {{ border-color: rgba(91, 145, 163, .35) !important; }}
section[data-testid="stSidebar"] .stButton > button {{ background: rgba(255, 255, 255, .78); border-color: rgba(91, 145, 163, .4); }}

/* ---- live view: nothing sticks out, long lines wrap, the timeline scrolls and shows the newest step ---- */
.st-key-live_dock {{
  display: flow-root; max-height: 46vh; overflow-y: auto; overflow-x: hidden; padding-bottom: 1.15rem !important;
  scrollbar-width: thin; scrollbar-color: rgba(91, 145, 163, .6) transparent;
}}
.lv-feed {{
  display: flex; flex-direction: column-reverse;      /* newest row is the first child, shown at the bottom */
  max-height: 210px; overflow-y: auto; overflow-x: hidden; padding-right: .35rem;
  scrollbar-width: thin; scrollbar-color: rgba(91, 145, 163, .6) transparent;
}}
.lv-row {{ min-width: 0; max-width: 100%; background: transparent; }}
.lv-row:last-child {{ background: transparent; }}
.lv-row:first-child {{ background: rgba(91, 145, 163, .18); }}
.lv-x {{ min-width: 0; flex: 1 1 auto; overflow-wrap: anywhere; word-break: break-word; }}
.lv-t, .lv-i {{ flex: none; }}
.st-key-live_dock [data-testid="stImageCaption"] {{ overflow-wrap: anywhere; word-break: break-word; }}
.st-key-live_dock [data-testid="stColumn"] {{ min-width: 0; }}
</style>
"""

_PILLS = {"ready": ("ready", "● Ready"), "needs setup": ("setup", "◐ Needs setup"), "disabled": ("off", "○ Switched off")}


def apply_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def pill(status: str) -> str:
    css, label = _PILLS.get(status, ("off", status))
    return f'<span class="pill {css}">{label}</span>'


def card_header(icon: str, name: str, status: str) -> str:
    return (f'<div class="ib-head"><div class="ib-ico">{html.escape(icon)}</div>'
            f'<div><div class="ib-name">{html.escape(name)}</div>{pill(status)}</div></div>')


def section(title: str) -> str:
    return f'<div class="ib-section">{html.escape(title)}</div>'
