import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import plotly.graph_objects as go
from lib.config import DISCLOSURE, APP_TITLE, APP_ICON
from lib.market_data import (INDEX_TICKERS, SECTOR_ETFS, PERIOD_MAP,
                              get_quotes_bulk, get_history, get_history_bulk)
from lib.charts import render_price_chart, render_sparkline
from lib.logos import logo_img_tag
from lib.news import market_news

st.set_page_config(page_title=f"Market Pulse — {APP_TITLE}", page_icon="💹",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    section.main > div { font-size: 17px; }
    .metric-card { background:#1e1e2e; border-radius:10px; padding:12px 16px; margin-bottom:8px; }
    .headline-row { border-bottom:1px solid #333; padding:8px 0; }
    .mover-row { display:flex; align-items:center; gap:10px; padding:6px 0; border-bottom:1px solid #222; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_TITLE}")
    st.caption("Educational market research tool")
    st.divider()

st.title("💹 Market Pulse")
st.caption("Live indices, sector performance, and market movers.")

period_options = list(PERIOD_MAP.keys())
period = st.segmented_control("Period", period_options, default="1D", key="mp_period")
if not period:
    period = "1D"
yf_period, yf_interval = PERIOD_MAP[period]

# ── Index Cards ───────────────────────────────────────────────────────────────
st.subheader("Indices & Assets")
tickers = list(INDEX_TICKERS.values())
with st.spinner("Fetching quotes…"):
    quotes = get_quotes_bulk(tickers)

cols = st.columns(5)
for i, (name, ticker) in enumerate(INDEX_TICKERS.items()):
    q = quotes.get(ticker, {})
    price = q.get("price")
    pct = q.get("pct_change")
    col = cols[i % 5]
    with col:
        color = "#26a69a" if (pct or 0) >= 0 else "#ef5350"
        sign = "+" if (pct or 0) >= 0 else ""
        pct_str = f"{sign}{pct:.2f}%" if pct is not None else "—"
        price_str = f"{price:,.2f}" if price else "—"
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size:12px;color:#aaa;">{name}</div>
            <div style="font-size:18px;font-weight:700;">{price_str}</div>
            <div style="color:{color};font-size:14px;font-weight:600;">{pct_str}</div>
        </div>
        """, unsafe_allow_html=True)
        df_spark = get_history(ticker, yf_period, yf_interval)
        if not df_spark.empty and "Close" in df_spark.columns:
            close_vals = df_spark["Close"].dropna()
            baseline = q.get("prev_close") if period == "1D" else None
            fig_s = render_sparkline(list(close_vals.index), list(close_vals.values),
                                     baseline_price=baseline)
            st.plotly_chart(fig_s, use_container_width=True, config={"displayModeBar": False})

st.divider()

# ── S&P 500 Big Chart ─────────────────────────────────────────────────────────
st.subheader("S&P 500 (^GSPC)")
view_options = ["Performance", "Price", "Candlestick", "Area"]
view = st.segmented_control("View", view_options, default="Performance", key="mp_spx_view")
df_spx = get_history("^GSPC", yf_period, yf_interval)
baseline_spx = quotes.get("^GSPC", {}).get("prev_close") if period == "1D" else None
fig_spx = render_price_chart(df_spx, "^GSPC", view=view or "Performance",
                              baseline_price=baseline_spx)
st.plotly_chart(fig_spx, use_container_width=True, config={"displayModeBar": False})

st.divider()

# ── Sector Heatmap ────────────────────────────────────────────────────────────
st.subheader("Sector Performance")
sector_tickers = list(SECTOR_ETFS.values())
with st.spinner("Loading sector data…"):
    sector_quotes = get_quotes_bulk(sector_tickers)

sector_names = list(SECTOR_ETFS.keys())
sector_pcts = []
for etf in sector_tickers:
    q = sector_quotes.get(etf, {})
    sector_pcts.append(q.get("pct_change") or 0.0)

colors = ["#26a69a" if p >= 0 else "#ef5350" for p in sector_pcts]
fig_sector = go.Figure(go.Bar(
    x=sector_names,
    y=sector_pcts,
    marker_color=colors,
    text=[f"{p:+.2f}%" for p in sector_pcts],
    textposition="outside",
    hovertemplate="%{x}: %{y:+.2f}%<extra></extra>",
))
fig_sector.update_layout(
    template="plotly_dark",
    height=320,
    margin=dict(l=10, r=10, t=10, b=10),
    yaxis_ticksuffix="%",
    showlegend=False,
)
st.plotly_chart(fig_sector, use_container_width=True, config={"displayModeBar": False})

st.divider()

# ── Movers ────────────────────────────────────────────────────────────────────
TOP_MOVERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "JPM", "V", "UNH",
    "XOM", "BAC", "JNJ", "WMT", "PG", "HD", "AVGO", "LLY", "MA", "COST",
    "CVX", "MRK", "ABBV", "CRM", "AMD", "NFLX", "ADBE", "ORCL", "ACN", "TMO",
    "INTC", "QCOM", "TXN", "GS", "MS", "IBM", "AMGN", "GILD", "REGN", "PFE",
    "KO", "PEP", "MCD", "NKE", "DIS", "CSCO", "MU", "UBER", "PYPL", "SQ",
]

with st.spinner("Loading movers…"):
    mover_quotes = get_quotes_bulk(TOP_MOVERS)

valid = [(t, mover_quotes[t]) for t in TOP_MOVERS
         if mover_quotes.get(t, {}).get("pct_change") is not None]
sorted_pct = sorted(valid, key=lambda x: x[1]["pct_change"], reverse=True)
gainers = sorted_pct[:5]
losers = sorted_pct[-5:][::-1]
by_vol = sorted(valid, key=lambda x: x[1].get("volume") or 0, reverse=True)[:5]

def _mover_row(ticker, q):
    pct = q.get("pct_change", 0) or 0
    price = q.get("price") or 0
    name = (q.get("name") or ticker)[:22]
    color = "#26a69a" if pct >= 0 else "#ef5350"
    sign = "+" if pct >= 0 else ""
    logo = logo_img_tag(ticker, 28)
    return (
        f'<div class="mover-row">'
        f'{logo}'
        f'<span style="font-weight:600;min-width:52px">{ticker}</span>'
        f'<span style="color:#aaa;font-size:13px;flex:1">{name}</span>'
        f'<span style="margin-right:12px">${price:,.2f}</span>'
        f'<span style="color:{color};font-weight:700">{sign}{pct:.2f}%</span>'
        f'</div>'
    )

col_g, col_l, col_a = st.columns(3)
with col_g:
    st.markdown("**Top Gainers**")
    for t, q in gainers:
        st.markdown(_mover_row(t, q), unsafe_allow_html=True)
with col_l:
    st.markdown("**Top Losers**")
    for t, q in losers:
        st.markdown(_mover_row(t, q), unsafe_allow_html=True)
with col_a:
    st.markdown("**Most Active**")
    for t, q in by_vol:
        st.markdown(_mover_row(t, q), unsafe_allow_html=True)

st.divider()

# ── Top Headlines ─────────────────────────────────────────────────────────────
st.subheader("Market Headlines")
with st.spinner("Loading news…"):
    headlines = market_news(limit=6)

if not headlines:
    st.info("No headlines available right now.")
else:
    for h in headlines[:6]:
        title = h.get("title", "")
        pub = h.get("publisher", "")
        ago = h.get("time_ago", "")
        summary = h.get("summary", "")
        url = h.get("url", "")
        link = f'<a href="{url}" target="_blank" style="color:#5c9eff;text-decoration:none;">{title}</a>' if url else title
        st.markdown(f"""
        <div class="headline-row">
            <div style="font-size:15px;font-weight:600;">{link}</div>
            <div style="font-size:12px;color:#888;">{pub} · {ago}</div>
            <div style="font-size:13px;color:#bbb;margin-top:4px;">{summary[:160]}</div>
        </div>
        """, unsafe_allow_html=True)

st.divider()
st.caption(DISCLOSURE)
