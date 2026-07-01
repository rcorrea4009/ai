import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import plotly.graph_objects as go
from lib.config import DISCLOSURE, APP_TITLE, APP_ICON
from lib.market_data import PERIOD_MAP, get_quote, get_history, get_etf_details, get_quotes_bulk
from lib.charts import render_price_chart, render_gauge
from lib.risk import compute_etf_risk_score
from lib.etf_peers import get_peers
from lib.logos import logo_img_tag

st.set_page_config(page_title=f"ETF Analyzer — {APP_TITLE}", page_icon="🧺",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    section.main > div { font-size: 17px; }
    .holding-row { display:flex; align-items:center; gap:10px; padding:5px 0; border-bottom:1px solid #222; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_TITLE}")
    st.caption("Educational market research tool")
    st.divider()

st.title("🧺 ETF Analyzer")
st.caption("ETF research for educational purposes.")

col_input, col_period = st.columns([2, 3])
with col_input:
    ticker = st.text_input("ETF Ticker", value="QQQ", max_chars=10,
                           placeholder="e.g. QQQ, SPY, XLK").upper().strip()
with col_period:
    period_options = list(PERIOD_MAP.keys())
    period = st.segmented_control("Period", period_options, default="1Y", key="etf_period")
    if not period:
        period = "1Y"

if not ticker:
    st.info("Enter an ETF ticker to begin.")
    st.stop()

yf_period, yf_interval = PERIOD_MAP[period]

with st.spinner(f"Loading {ticker}…"):
    quote = get_quote(ticker)
    info = get_etf_details(ticker)
    df = get_history(ticker, yf_period, yf_interval)

name = info.get("longName") or info.get("shortName") or ticker
price = quote.get("price")
pct = quote.get("pct_change")
aum = info.get("totalAssets")
expense = info.get("expenseRatio")

# ── Header ────────────────────────────────────────────────────────────────────
h_logo, h_name, h_metrics = st.columns([1, 4, 6])
with h_logo:
    st.markdown(logo_img_tag(ticker, 64), unsafe_allow_html=True)
with h_name:
    st.markdown(f"### {name}")
    st.caption(f"**{ticker}** · {info.get('category') or '—'} · {info.get('fundFamily') or '—'}")
with h_metrics:
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Price", f"${price:,.2f}" if price else "—",
               f"{pct:+.2f}%" if pct is not None else None)
    mc2.metric("AUM", f"${aum/1e9:.1f}B" if aum else "—")
    mc3.metric("Expense Ratio", f"{expense*100:.2f}%" if expense else "—")
    mc4.metric("3Y Beta", f"{info.get('beta3Year'):.2f}" if info.get('beta3Year') else "—")

st.divider()

# ── Chart ─────────────────────────────────────────────────────────────────────
view_options = ["Performance", "Price", "Candlestick", "Area"]
view = st.segmented_control("Chart view", view_options, default="Performance", key="etf_view")
baseline = quote.get("prev_close") if period == "1D" else None
fig_price = render_price_chart(df, ticker, view=view or "Performance",
                               show_volume=True, baseline_price=baseline)
st.plotly_chart(fig_price, use_container_width=True, config={"displayModeBar": False})

st.divider()

# ── Returns Table ─────────────────────────────────────────────────────────────
st.subheader("Returns")
r_ytd = info.get("ytdReturn")
r_3y = info.get("threeYearAverageReturn")
r_5y = info.get("fiveYearAverageReturn")
beta3 = info.get("beta3Year")
ret_cols = st.columns(4)
ret_cols[0].metric("YTD Return", f"{r_ytd*100:.2f}%" if r_ytd is not None else "—")
ret_cols[1].metric("3Y Avg Annual", f"{r_3y*100:.2f}%" if r_3y is not None else "—")
ret_cols[2].metric("5Y Avg Annual", f"{r_5y*100:.2f}%" if r_5y is not None else "—")
ret_cols[3].metric("3Y Beta", f"{beta3:.2f}" if beta3 is not None else "—")

st.divider()

# ── Risk Gauge ────────────────────────────────────────────────────────────────
risk_score, risk_details = compute_etf_risk_score(df, info)
st.subheader("Risk Profile")

rg_col, rg_detail = st.columns([1.5, 2])
with rg_col:
    fig_risk = render_gauge(risk_score, "Risk Score", "Volatility · Drawdown · Concentration")
    st.plotly_chart(fig_risk, use_container_width=True, config={"displayModeBar": False})
with rg_detail:
    st.markdown(f"**{risk_details.get('label', '')}**")
    if "ann_volatility_pct" in risk_details:
        st.markdown(f"- Annualized volatility: **{risk_details['ann_volatility_pct']}%**")
    if "max_drawdown_pct" in risk_details:
        st.markdown(f"- Max drawdown (period): **{risk_details['max_drawdown_pct']}%**")
    if "top10_concentration_pct" in risk_details:
        st.markdown(f"- Top-10 holdings concentration: **{risk_details['top10_concentration_pct']}%**")
    st.caption("Risk score is based on historical volatility, drawdown, and portfolio concentration. "
               "Higher = historically more volatile.")

st.divider()

# ── Sector Breakdown ──────────────────────────────────────────────────────────
sector_weights = info.get("sector_weights", {})
if sector_weights:
    st.subheader("Sector Breakdown")
    sw_items = sorted(sector_weights.items(), key=lambda x: x[1], reverse=True)
    sw_labels = [s for s, _ in sw_items]
    sw_vals = [v * 100 if v <= 1 else v for _, v in sw_items]
    fig_sw = go.Figure(go.Bar(
        x=sw_vals, y=sw_labels, orientation="h",
        marker_color="#5c9eff",
        text=[f"{v:.1f}%" for v in sw_vals],
        textposition="outside",
        hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
    ))
    fig_sw.update_layout(
        template="plotly_dark", height=max(250, len(sw_labels) * 28),
        margin=dict(l=10, r=60, t=10, b=10),
        xaxis_ticksuffix="%",
    )
    st.plotly_chart(fig_sw, use_container_width=True, config={"displayModeBar": False})
    st.divider()

# ── Top Holdings ──────────────────────────────────────────────────────────────
holdings = info.get("holdings", [])
if holdings:
    st.subheader("Top Holdings")
    n = len(holdings)
    mid = (n + 1) // 2
    left_h, right_h = holdings[:mid], holdings[mid:]
    h_left, h_right = st.columns(2)
    for col, group in [(h_left, left_h), (h_right, right_h)]:
        with col:
            for h in group:
                sym = h.get("symbol", "?")
                hname = (h.get("name") or sym)[:28]
                weight = h.get("weight", 0)
                w_pct = weight * 100 if weight <= 1 else weight
                logo = logo_img_tag(sym, 24)
                st.markdown(
                    f'<div class="holding-row">{logo}'
                    f'<span style="font-weight:600;min-width:52px">{sym}</span>'
                    f'<span style="color:#bbb;flex:1;font-size:13px">{hname}</span>'
                    f'<span style="color:#5c9eff;font-weight:700">{w_pct:.2f}%</span></div>',
                    unsafe_allow_html=True,
                )
    st.divider()

# ── Peer Comparison ───────────────────────────────────────────────────────────
peers = get_peers(ticker)
if peers:
    st.subheader("Peer Comparison")
    all_tickers = [ticker] + peers
    with st.spinner("Loading peer data…"):
        peer_quotes = get_quotes_bulk(all_tickers)

    peer_rows = []
    for t in all_tickers:
        pq = peer_quotes.get(t, {})
        pd_info = get_etf_details(t)
        er = pd_info.get("expenseRatio")
        ytd = pd_info.get("ytdReturn")
        aum_p = pd_info.get("totalAssets")
        peer_rows.append({
            "Ticker": t,
            "Name": (pd_info.get("shortName") or pq.get("name") or t)[:30],
            "Expense Ratio": f"{er*100:.2f}%" if er else "—",
            "_er": er or 999,
            "YTD Return": f"{ytd*100:.2f}%" if ytd is not None else "—",
            "AUM": f"${aum_p/1e9:.1f}B" if aum_p else "—",
            "Price": f"${pq.get('price'):,.2f}" if pq.get("price") else "—",
            "1D Change": f"{pq.get('pct_change'):+.2f}%" if pq.get("pct_change") is not None else "—",
        })
    peer_rows.sort(key=lambda r: r["_er"])
    import pandas as pd
    peer_df = pd.DataFrame(peer_rows).drop(columns=["_er"])
    st.dataframe(peer_df, use_container_width=True, hide_index=True)

    # Cheaper alternatives callout
    this_er = get_etf_details(ticker).get("expenseRatio") or 0
    cheaper = [r for r in peer_rows if r["_er"] < this_er and r["Ticker"] != ticker and r["_er"] < 999]
    if cheaper:
        best = min(cheaper, key=lambda r: r["_er"])
        best_er = best["_er"]
        savings_bps = (this_er - best_er) * 10000
        savings_dollars = (this_er - best_er) * 100_000
        st.info(
            f"💡 **{best['Ticker']}** has a lower expense ratio ({best_er*100:.2f}% vs {this_er*100:.2f}%), "
            f"saving **{savings_bps:.1f} bps** or **${savings_dollars:,.0f}/year** on a $100K position."
        )

st.divider()
st.caption(DISCLOSURE)
