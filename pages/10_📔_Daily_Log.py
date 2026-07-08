import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st

from lib.config import DISCLOSURE, APP_TITLE, APP_ICON
from lib import report_store
from lib import tiger_client as tiger
from lib import ui

st.set_page_config(
    page_title=f"Daily Log — {APP_TITLE}",
    page_icon="📔",
    layout="wide",
    initial_sidebar_state="expanded",
)

ui.inject()

with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_TITLE}")
    st.caption("Educational market research tool")
    st.divider()

st.title("📔 Daily Log")
st.caption("Your morning & evening briefings, kept for the last week. Auto-updated by the "
           "scheduled 9am / 9pm tasks — or generate one now. Educational only, not advice.")


def _generate(slot: str):
    from scripts.daily_report import build
    cash = (tiger.get_account_summary() or {}).get("cash") if tiger.is_configured() else None
    capital = float(cash) if cash and cash > 5 else 60.0
    content = build(capital, slot)
    report_store.save(slot, content)


gc = st.columns([1, 1, 2])
if gc[0].button("☀️ Generate morning log now", use_container_width=True):
    with st.spinner("Running full analysis (backtest + news)…"):
        _generate("morning")
    st.success("Morning log updated.")
    st.rerun()
if gc[1].button("🌙 Generate evening log now", use_container_width=True):
    with st.spinner("Running full analysis (backtest + news)…"):
        _generate("evening")
    st.success("Evening log updated.")
    st.rerun()

st.divider()

# ── Latest two slots ────────────────────────────────────────────────────────────
m = report_store.latest("morning")
e = report_store.latest("evening")
c1, c2 = st.columns(2)
with c1:
    st.subheader("☀️ Latest Morning")
    if m:
        st.caption(f"{m['date']} · {m['time']}")
        st.markdown(m["content"])
    else:
        st.info("No morning log yet — press ‘Generate morning log now’.")
with c2:
    st.subheader("🌙 Latest Evening")
    if e:
        st.caption(f"{e['date']} · {e['time']}")
        st.markdown(e["content"])
    else:
        st.info("No evening log yet — press ‘Generate evening log now’.")

st.divider()

# ── Past week ───────────────────────────────────────────────────────────────────
st.subheader("🗓️ Past week")
entries = report_store.load_all()
if not entries:
    st.caption("History will fill in as morning/evening logs are generated.")
else:
    for en in entries:
        icon = "☀️" if en["slot"] == "morning" else "🌙"
        with st.expander(f"{icon} {en['date']} · {en['slot'].title()} · {en['time']}"):
            st.markdown(en["content"])

st.divider()
st.caption(DISCLOSURE)
