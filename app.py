import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from lib.config import DISCLOSURE, APP_TITLE, APP_ICON
from lib.market_data import INDEX_TICKERS, PERIOD_MAP, get_quotes_bulk, get_history
from lib.charts import render_sparkline
import plotly.graph_objects as go

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    section.main > div { font-size: 17px; }
    .metric-card {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 8px;
    }
    .chip {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 13px;
        margin: 2px;
    }
    .headline-row {
        border-bottom: 1px solid #333;
        padding: 8px 0;
    }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_TITLE}")
    st.caption("Educational market research tool")
    st.divider()

st.title(f"{APP_ICON} {APP_TITLE}")
st.caption("Real-time market data for educational and research purposes.")

period_options = list(PERIOD_MAP.keys())
default_period = "1D"
period = st.segmented_control("Period", period_options, default=default_period, key="home_period")
if not period:
    period = default_period

yf_period, yf_interval = PERIOD_MAP[period]

st.subheader("Market Snapshot")

tickers = list(INDEX_TICKERS.values())
names = list(INDEX_TICKERS.keys())

with st.spinner("Loading market data…"):
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
            <div style="font-size:13px;color:#aaa;">{name}</div>
            <div style="font-size:20px;font-weight:700;">{price_str}</div>
            <div style="color:{color};font-size:15px;font-weight:600;">{pct_str}</div>
        </div>
        """, unsafe_allow_html=True)

        # Sparkline
        df_spark = get_history(ticker, yf_period, yf_interval)
        if not df_spark.empty and "Close" in df_spark.columns:
            close_vals = df_spark["Close"].dropna()
            baseline = q.get("prev_close") if period == "1D" else None
            fig_spark = render_sparkline(
                list(close_vals.index),
                list(close_vals.values),
                baseline_price=baseline,
            )
            st.plotly_chart(fig_spark, use_container_width=True, config={"displayModeBar": False})

st.divider()

# Big S&P 500 chart
st.subheader("S&P 500 (^GSPC)")
from lib.charts import render_price_chart
view = st.segmented_control("Chart view", ["Performance", "Price", "Area", "Candlestick"],
                             default="Performance", key="home_spx_view")
df_spx = get_history("^GSPC", yf_period, yf_interval)
baseline_spx = None
if period == "1D":
    q_spx = quotes.get("^GSPC", {})
    baseline_spx = q_spx.get("prev_close")
fig_spx = render_price_chart(df_spx, "^GSPC", view=view or "Performance",
                              baseline_price=baseline_spx)
st.plotly_chart(fig_spx, use_container_width=True, config={"displayModeBar": False})

st.divider()

# Quick navigation cards
st.subheader("Navigate")
nav_cols = st.columns(3)
with nav_cols[0]:
    st.page_link("pages/1_💹_Market_Pulse.py", label="💹 Market Pulse", use_container_width=True)
    st.page_link("pages/4_🌍_Macro.py", label="🌍 Macro Dashboard", use_container_width=True)
with nav_cols[1]:
    st.page_link("pages/2_🔍_Stock_Analyzer.py", label="🔍 Stock Analyzer", use_container_width=True)
    st.page_link("pages/5_💼_Portfolio.py", label="💼 Portfolio Tracker", use_container_width=True)
with nav_cols[2]:
    st.page_link("pages/3_🧺_ETF_Analyzer.py", label="🧺 ETF Analyzer", use_container_width=True)
    st.page_link("pages/6_📰_News.py", label="📰 News Feed", use_container_width=True)
    st.page_link("pages/8_🧠_AI_Verdict.py", label="🧠 AI Verdict", use_container_width=True)
    st.page_link("pages/9_💵_Tiger_Trade.py", label="💵 Tiger Trade", use_container_width=True)

st.divider()
st.caption(DISCLOSURE)
