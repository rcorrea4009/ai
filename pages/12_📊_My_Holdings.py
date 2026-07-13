import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import plotly.graph_objects as go

from lib.config import DISCLOSURE, APP_TITLE, APP_ICON
from lib import tiger_client as tiger
from lib.market_data import get_history
from lib.news import ticker_news
from lib import ui

st.set_page_config(page_title=f"My Holdings — {APP_TITLE}", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")
ui.inject()

with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_TITLE}")
    st.caption("Educational market research tool")
    st.divider()

ui.hero("📊 My Holdings",
        "What you bought and what happened to it — cost vs now, profit/loss, your safety "
        "orders, and the latest news. Read-only view of your live account.",
        pills=["Live positions", "P&L", "News"])

if not tiger.is_configured():
    st.info("Connect your Tiger account (add TIGER_* to `.env`) to see your holdings here.")
    st.stop()

summ = tiger.get_account_summary()
positions = tiger.get_positions()
open_orders = tiger.get_open_orders()

if summ:
    m = st.columns(4)
    m[0].metric("Net Liquidation", f"${summ.get('net_liquidation') or 0:,.2f}")
    m[1].metric("Cash", f"${summ.get('cash') or 0:,.2f}")
    total_pnl = sum((p.get("unrealized_pnl") or 0) for p in positions)
    m[2].metric("Open P&L", f"${total_pnl:,.2f}", f"{'▲ up' if total_pnl >= 0 else '▼ down'}",
                delta_color="normal" if total_pnl >= 0 else "inverse")
    m[3].metric("Holdings", f"{len(positions)}")

st.divider()

if not positions:
    st.success("You don't hold any stocks right now — nothing bought, nothing at risk.")
    if open_orders:
        st.caption("You do have pending orders waiting to fill:")
        st.dataframe(open_orders, use_container_width=True, hide_index=True)
    st.stop()

# ── One rich card per holding ────────────────────────────────────────────────────
for p in positions:
    sym = p["symbol"]
    qty = p.get("quantity") or 0
    cost = p.get("avg_cost") or 0
    price = p.get("market_price") or 0
    pnl = p.get("unrealized_pnl") or 0
    pnl_pct = ((price - cost) / cost * 100) if cost else 0
    up = pnl >= 0
    color = "#26d0a5" if up else "#ff5c72"

    st.markdown(f"### {sym}  ·  {qty} share{'s' if qty != 1 else ''}")
    cc = st.columns(4)
    cc[0].metric("You paid (avg)", f"${cost:,.2f}")
    cc[1].metric("Now", f"${price:,.2f}", f"{pnl_pct:+.1f}%",
                 delta_color="normal" if up else "inverse")
    cc[2].metric("Value", f"${(price*qty):,.2f}")
    cc[3].metric("Profit / Loss", f"${pnl:,.2f}", delta_color="off")

    # plain-language "what happened"
    verb = "gained" if up else "dropped"
    st.markdown(
        f"<div style='font-size:15px;color:{color};font-weight:600;'>"
        f"Since you bought it, {sym} has {verb} {abs(pnl_pct):.1f}% "
        f"— that's {'a gain' if up else 'a loss'} of ${abs(pnl):,.2f} so far (unrealised).</div>",
        unsafe_allow_html=True)

    # chart with entry line
    df = get_history(sym, "3mo", "1d")
    if not df.empty and "Close" in df.columns:
        fig = go.Figure(go.Scatter(x=df.index, y=df["Close"],
                                   line=dict(color="#5c9eff", width=1.8), name=sym))
        fig.add_hline(y=cost, line=dict(color="#aaa", dash="dot"),
                      annotation_text=f"your buy ${cost:,.2f}", annotation_position="right")
        fig.update_layout(paper_bgcolor="#0a0d13", plot_bgcolor="#0a0d13", font=dict(color="#ccc"),
                          height=240, margin=dict(l=0, r=0, t=8, b=0),
                          xaxis=dict(gridcolor="#1e1e2e"), yaxis=dict(gridcolor="#1e1e2e"),
                          title=dict(text=f"{sym} — last 3 months", font=dict(size=13)))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # pending safety orders on this symbol
    sym_orders = [o for o in open_orders if o["symbol"] == sym]
    if sym_orders:
        st.caption("🛡️ Your pending exit orders (auto-sell) on this stock:")
        rows = []
        for o in sym_orders:
            tgt = o.get("limit_price") or o.get("stop_price")
            kind = "Take-profit" if (o.get("limit_price") and not o.get("stop_price")) else \
                   ("Stop-loss" if o.get("stop_price") else "Sell")
            rows.append({"Type": kind, "Action": o["action"], "Qty": o["quantity"],
                         "Price": tgt, "Status": o["status"]})
        st.dataframe(rows, use_container_width=True, hide_index=True)

    # news
    news = ticker_news(sym, limit=3)
    if news:
        st.caption(f"📰 Why it might be moving — latest {sym} news:")
        for n in news:
            meta = " · ".join(x for x in [n.get("publisher", ""), n.get("time_ago", "")] if x)
            st.markdown(f"- [{n['title']}]({n['url']}) — {meta}" if n.get("url") else f"- {n['title']}")

    st.divider()

st.caption(DISCLOSURE)
