import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from lib.config import DISCLOSURE, APP_TITLE, APP_ICON
from lib.portfolio import load_portfolio, save_portfolio, enrich_portfolio
from lib.market_data import get_quotes_bulk, get_history_bulk, PERIOD_MAP
from lib.risk import compute_etf_risk_score
from lib.charts import render_price_chart

st.set_page_config(page_title=f"Portfolio — {APP_TITLE}", page_icon="💼",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>section.main > div { font-size: 17px; }</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_TITLE}")
    st.caption("Educational market research tool")
    st.divider()

st.title("💼 Portfolio Tracker")
st.caption("Track your holdings for educational and research purposes. Saved locally.")

# ── Holdings Editor ───────────────────────────────────────────────────────────
st.subheader("My Holdings")
holdings = load_portfolio()

with st.expander("Add / Edit Holdings", expanded=not bool(holdings)):
    st.caption("Enter each position. Data is saved locally in `data/portfolio.json`.")

    n_rows = st.number_input("Number of positions", min_value=1, max_value=50,
                              value=max(len(holdings), 1), step=1)

    rows = []
    for i in range(int(n_rows)):
        c1, c2, c3 = st.columns([2, 2, 2])
        existing = holdings[i] if i < len(holdings) else {}
        ticker = c1.text_input("Ticker", value=existing.get("ticker", ""),
                                key=f"pticker_{i}", max_chars=10).upper().strip()
        shares = c2.number_input("Shares", min_value=0.0, step=0.01,
                                  value=float(existing.get("shares", 0)),
                                  key=f"pshares_{i}", format="%.4f")
        cost_basis = c3.number_input("Cost Basis (per share $)", min_value=0.0, step=0.01,
                                      value=float(existing.get("cost_basis", 0)),
                                      key=f"pcost_{i}", format="%.2f")
        if ticker:
            rows.append({"ticker": ticker, "shares": shares, "cost_basis": cost_basis})

    if st.button("💾 Save Portfolio", key="save_portfolio"):
        valid_rows = [r for r in rows if r["ticker"] and r["shares"] > 0]
        save_portfolio(valid_rows)
        st.success(f"Saved {len(valid_rows)} position(s).")
        st.rerun()

holdings = load_portfolio()
if not holdings:
    st.info("Add holdings above to get started.")
    st.divider()
    st.caption(DISCLOSURE)
    st.stop()

tickers = [h["ticker"] for h in holdings]

with st.spinner("Fetching current prices…"):
    quotes = get_quotes_bulk(tickers)

df_port = enrich_portfolio(holdings, quotes)

# ── Summary Metrics ───────────────────────────────────────────────────────────
total_cost = df_port["Cost Total"].sum()
total_value = df_port["Mkt Value"].sum()
total_gain = total_value - total_cost
total_gain_pct = (total_gain / total_cost * 100) if total_cost > 0 else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Value", f"${total_value:,.2f}")
m2.metric("Total Cost", f"${total_cost:,.2f}")
m3.metric("Total Gain $", f"${total_gain:+,.2f}",
          delta_color="normal" if total_gain >= 0 else "inverse")
m4.metric("Total Return", f"{total_gain_pct:+.2f}%",
          delta_color="normal" if total_gain_pct >= 0 else "inverse")

st.divider()

# ── Holdings Table ────────────────────────────────────────────────────────────
st.subheader("Positions")

def _color_gain(val):
    color = "#26a69a" if val >= 0 else "#ef5350"
    return f"color: {color}"

display_df = df_port[["Ticker", "Name", "Shares", "Cost Basis", "Price",
                        "Mkt Value", "Cost Total", "Gain $", "Gain %"]].copy()
display_df["Gain %"] = display_df["Gain %"].map(lambda x: f"{x:+.2f}%")
display_df["Gain $"] = display_df["Gain $"].map(lambda x: f"${x:+,.2f}")
display_df["Mkt Value"] = display_df["Mkt Value"].map(lambda x: f"${x:,.2f}")
display_df["Cost Total"] = display_df["Cost Total"].map(lambda x: f"${x:,.2f}")
display_df["Cost Basis"] = display_df["Cost Basis"].map(lambda x: f"${x:.2f}")
display_df["Price"] = display_df["Price"].map(lambda x: f"${x:.2f}" if x else "—")

st.dataframe(display_df, use_container_width=True, hide_index=True)

st.divider()

# ── Allocation Charts ─────────────────────────────────────────────────────────
st.subheader("Allocation")
pie_col, sector_col = st.columns(2)

with pie_col:
    fig_pie = go.Figure(go.Pie(
        labels=df_port["Ticker"],
        values=df_port["Mkt Value"],
        hole=0.4,
        hovertemplate="%{label}: %{percent}<extra></extra>",
    ))
    fig_pie.update_layout(
        template="plotly_dark", title="By Position",
        height=320, margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})

with sector_col:
    sector_map = df_port.groupby("Sector")["Mkt Value"].sum()
    fig_sec = go.Figure(go.Pie(
        labels=sector_map.index,
        values=sector_map.values,
        hole=0.4,
        hovertemplate="%{label}: %{percent}<extra></extra>",
    ))
    fig_sec.update_layout(
        template="plotly_dark", title="By Sector",
        height=320, margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig_sec, use_container_width=True, config={"displayModeBar": False})

st.divider()

# ── Performance Chart (YTD) ───────────────────────────────────────────────────
st.subheader("Portfolio vs S&P 500 (YTD)")
with st.spinner("Loading price history…"):
    hist_data = get_history_bulk(tickers + ["^GSPC"], period="ytd", interval="1d")

# Weighted portfolio return
port_returns = None
for h in holdings:
    t = h["ticker"]
    df_h = hist_data.get(t)
    if df_h is None or df_h.empty or "Close" not in df_h.columns:
        continue
    close = df_h["Close"].dropna()
    if close.empty:
        continue
    weight = (quotes.get(t, {}).get("price", 0) or 0) * h["shares"] / total_value if total_value > 0 else 0
    ret = (close / close.iloc[0] - 1) * weight
    port_returns = ret if port_returns is None else port_returns.add(ret, fill_value=0)

fig_perf = go.Figure()
if port_returns is not None and not port_returns.empty:
    fig_perf.add_trace(go.Scatter(
        x=port_returns.index, y=port_returns.values * 100,
        mode="lines", name="My Portfolio",
        line=dict(color="#ffd700", width=2),
        hovertemplate="Portfolio: %{y:.2f}%<extra></extra>",
    ))

df_spx = hist_data.get("^GSPC")
if df_spx is not None and not df_spx.empty and "Close" in df_spx.columns:
    spx_close = df_spx["Close"].dropna()
    spx_ret = (spx_close / spx_close.iloc[0] - 1) * 100
    fig_perf.add_trace(go.Scatter(
        x=spx_ret.index, y=spx_ret.values,
        mode="lines", name="S&P 500",
        line=dict(color="#5c9eff", width=2, dash="dot"),
        hovertemplate="S&P 500: %{y:.2f}%<extra></extra>",
    ))

fig_perf.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.2)")
fig_perf.update_layout(
    template="plotly_dark", height=350,
    margin=dict(l=10, r=10, t=10, b=10),
    yaxis_ticksuffix="%",
    hovermode="x unified",
)
st.plotly_chart(fig_perf, use_container_width=True, config={"displayModeBar": False})

st.divider()

# ── Claude Analysis ───────────────────────────────────────────────────────────
st.subheader("AI Portfolio Overview")
st.caption("AI-generated educational content. Not financial advice.")
if st.button("Generate Portfolio Analysis", key="portfolio_claude_btn"):
    from lib.claude_analyst import portfolio_analysis
    with st.spinner("Asking Claude…"):
        analysis = portfolio_analysis(df_port, total_value)
    st.markdown(analysis)
else:
    st.info("Click the button to generate an AI educational overview of your portfolio.")

st.divider()
st.caption(DISCLOSURE)
