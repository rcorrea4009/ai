import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from lib.config import DISCLOSURE, APP_TITLE, APP_ICON
from lib.market_data import get_history, get_quote, get_stock_fundamentals
from lib.signals import compute_technical_score, compute_fundamental_score
from lib.macro import get_all_macro
from lib.free_apis import (
    get_fear_greed,
    get_sec_insider_filings,
    score_vix,
    score_fear_greed,
    compute_macro_score,
)
from lib.kronos_runner import run_kronos_prediction, interpret_kronos

st.set_page_config(
    page_title=f"Kronos Predictor — {APP_TITLE}",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    section.main > div { font-size: 17px; }
    .sig-card {
        background: #1a1a2e;
        border-radius: 12px;
        padding: 14px 18px;
        margin-bottom: 10px;
        border: 1px solid #2a2a40;
    }
    .sig-label  { font-size: 12px; color: #777; margin-bottom: 4px; }
    .sig-value  { font-size: 26px; font-weight: 800; line-height: 1.1; }
    .sig-detail { font-size: 13px; color: #aaa; margin-top: 5px; }
    .sig-source { font-size: 11px; color: #444; margin-top: 3px; }
    .bar-bg  { background:#252538; border-radius:6px; height:10px; margin:6px 0; }
    .bar-fill{ height:10px; border-radius:6px; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_TITLE}")
    st.caption("Educational market research tool")
    st.divider()

st.title("🔮 Kronos Predictor")
st.caption(
    "Kronos foundation model forecast + cross-referenced signals from 5 independent free data sources. "
    "Educational only — not financial advice."
)

# ── Inputs ─────────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns([2, 2, 2])
with c1:
    ticker = st.text_input("Ticker Symbol", value="AAPL", max_chars=10).upper().strip()
with c2:
    pred_len = st.selectbox(
        "Forecast Horizon",
        [5, 10, 20, 30],
        index=1,
        format_func=lambda x: f"{x} trading days (~{x//5} week{'s' if x>=10 else ''})",
    )
with c3:
    sample_count = st.selectbox(
        "Kronos Samples",
        [1, 3, 5],
        index=1,
        help="Kronos averages N sampled paths. More = smoother forecast, slower inference.",
    )

if not ticker:
    st.stop()

# ── Fetch all data in parallel spinners ────────────────────────────────────────
with st.spinner(f"Fetching market data for {ticker}…"):
    df_daily = get_history(ticker, "2y", "1d")
    quote    = get_quote(ticker)
    info     = get_stock_fundamentals(ticker)
    vix_q    = get_quote("^VIX")

with st.spinner("Fetching sentiment & macro data…"):
    fg_data     = get_fear_greed()
    macro_data  = get_all_macro()
    sec_filings = get_sec_insider_filings(ticker)

if df_daily.empty:
    st.error(f"No price data for **{ticker}**. Verify the ticker and try again.")
    st.stop()

# ── Kronos Forecast ────────────────────────────────────────────────────────────
st.subheader("Kronos AI Forecast")
st.caption(
    f"Kronos-small (102M params) — foundation model trained on candlestick data from 45+ global exchanges. "
    f"Forecasting next **{pred_len} trading days** of OHLCV."
)

with st.spinner("Running Kronos inference… (first run downloads model weights ~100 MB)"):
    pred_df = run_kronos_prediction(df_daily, pred_len=pred_len, sample_count=sample_count)

kronos_interp = None
if pred_df is not None:
    kronos_interp = interpret_kronos(df_daily, pred_df)

    # Combined historical + forecast candlestick chart
    hist = df_daily.tail(120)
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=hist.index,
        open=hist["Open"], high=hist["High"],
        low=hist["Low"],  close=hist["Close"],
        name="Historical",
        increasing_line_color="#26a69a",
        decreasing_line_color="#ef5350",
    ))

    fig.add_trace(go.Candlestick(
        x=pred_df.index,
        open=pred_df["open"], high=pred_df["high"],
        low=pred_df["low"],  close=pred_df["close"],
        name="Kronos Forecast",
        increasing_line_color="#7c4dff",
        decreasing_line_color="#e040fb",
        opacity=0.88,
    ))

    fig.add_vrect(
        x0=str(pred_df.index[0]), x1=str(pred_df.index[-1]),
        fillcolor="rgba(124,77,255,0.08)",
        layer="below", line_width=0,
        annotation_text="Forecast Zone",
        annotation_position="top left",
        annotation_font_color="#888",
    )

    fig.update_layout(
        xaxis_rangeslider_visible=False,
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        font=dict(color="#ccc"),
        height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis=dict(gridcolor="#1e1e2e"),
        yaxis=dict(gridcolor="#1e1e2e"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Kronos headline metrics
    pct = kronos_interp["pct_change"]
    km1, km2, km3, km4 = st.columns(4)
    km1.metric("Current Close",  f"${kronos_interp['current_close']:,.2f}")
    km2.metric(f"Predicted Close ({pred_len}d)", f"${kronos_interp['pred_close_end']:,.2f}",
               f"{pct:+.2f}%")
    km3.metric("Kronos Direction", kronos_interp["direction"])
    km4.metric("Direction Score",  f"{kronos_interp['direction_score']:.0f}/100")
else:
    st.warning(
        "⚠️ Kronos model could not be loaded. "
        "Make sure `torch`, `einops`, and the HuggingFace weights are available. "
        "All cross-reference signals below are still shown."
    )

st.divider()

# ── Cross-Reference Signals ────────────────────────────────────────────────────
st.subheader("Cross-Reference Signals")
st.caption(
    "Five independent data sources validate the forecast direction. "
    "All sources are free — no paid API required."
)

tech_score, tech_details = compute_technical_score(df_daily)
fund_score, fund_details = compute_fundamental_score(info)
vix_val   = vix_q.get("price")
vix_score = score_vix(vix_val)
fg_val    = fg_data.get("value")
fg_label  = fg_data.get("classification", "N/A")
fg_score  = score_fear_greed(fg_val)
macro_score = compute_macro_score(macro_data)

SIGNALS = [
    {
        "icon": "🤖",
        "name": "Kronos AI Forecast",
        "score": kronos_interp["direction_score"] if kronos_interp else 50.0,
        "detail": (
            f"{kronos_interp['direction']}  ·  {kronos_interp['pct_change']:+.2f}% predicted change"
            if kronos_interp else "Model unavailable"
        ),
        "source": "Kronos-small · HuggingFace (free download)",
        "weight": 0.30,
    },
    {
        "icon": "📈",
        "name": "Technical Strength",
        "score": tech_score,
        "detail": (
            f"RSI {tech_details.get('rsi', '—')}  ·  {tech_details.get('vs_200dma', '—')}  ·  "
            f"MACD {'▲' if (tech_details.get('macd_hist') or 0) > 0 else '▼'}"
        ),
        "source": "yfinance price history (free)",
        "weight": 0.20,
    },
    {
        "icon": "🏦",
        "name": "Fundamental Quality",
        "score": fund_score,
        "detail": fund_details.get("roe", "N/A"),
        "source": "yfinance company fundamentals (free)",
        "weight": 0.15,
    },
    {
        "icon": "😱",
        "name": "Crypto Fear & Greed",
        "score": fg_score,
        "detail": (
            f"{fg_val}/100  ·  {fg_label}  (risk-appetite proxy)"
            if fg_val is not None else "Unavailable"
        ),
        "source": "alternative.me/fng — free, no API key",
        "weight": 0.15,
    },
    {
        "icon": "🌡️",
        "name": "VIX Stability",
        "score": vix_score,
        "detail": (
            f"VIX at {vix_val:.2f}  ·  {'Low vol' if vix_val < 15 else 'Elevated' if vix_val > 25 else 'Normal'}"
            if vix_val else "Unavailable"
        ),
        "source": "yfinance ^VIX (free)",
        "weight": 0.10,
    },
    {
        "icon": "🌍",
        "name": "Macro Environment",
        "score": macro_score,
        "detail": (
            "GDP, unemployment, Fed Funds rate from FRED"
            if macro_data else "Add FRED_API_KEY to .env for macro data (free key)"
        ),
        "source": "FRED API — free key at fred.stlouisfed.org",
        "weight": 0.10,
    },
]

score_map = {s["name"]: s["score"] for s in SIGNALS}


def _bar(score: float, color: str) -> str:
    pct = max(0.0, min(100.0, score))
    return (
        f'<div class="bar-bg">'
        f'<div class="bar-fill" style="width:{pct}%;background:{color};"></div>'
        f'</div>'
    )


def _color(score: float) -> str:
    if score >= 65:
        return "#26a69a"
    if score >= 45:
        return "#ffb300"
    return "#ef5350"


cols = st.columns(2)
for i, sig in enumerate(SIGNALS):
    sc = sig["score"]
    c  = _color(sc)
    with cols[i % 2]:
        st.markdown(f"""
        <div class="sig-card">
          <div class="sig-label">{sig['icon']} {sig['name']}
            <span style="float:right;font-size:11px;color:#555;">weight {sig['weight']*100:.0f}%</span>
          </div>
          <div class="sig-value" style="color:{c};">{sc:.0f}<span style="font-size:14px;font-weight:400;color:#555;"> /100</span></div>
          {_bar(sc, c)}
          <div class="sig-detail">{sig['detail']}</div>
          <div class="sig-source">Source: {sig['source']}</div>
        </div>
        """, unsafe_allow_html=True)

st.divider()

# ── Combined Score ─────────────────────────────────────────────────────────────
st.subheader("Combined Model Score")
st.caption("Weighted average of all six independent signals.")

combined = sum(s["weight"] * s["score"] for s in SIGNALS)

if combined >= 68:
    comb_label = "Favorable"
    comb_color = "#26a69a"
    comb_desc  = "Most cross-referenced signals point in the same positive direction."
elif combined >= 52:
    comb_label = "Mixed / Neutral"
    comb_color = "#ffb300"
    comb_desc  = "Signals are mixed — no strong directional consensus exists."
else:
    comb_label = "Unfavorable"
    comb_color = "#ef5350"
    comb_desc  = "Most cross-referenced signals lean negative."

left, right = st.columns([1, 2])

with left:
    st.markdown(f"""
    <div class="sig-card" style="text-align:center;padding:24px;">
      <div class="sig-label">Combined Weighted Score</div>
      <div style="font-size:64px;font-weight:900;color:{comb_color};line-height:1;">{combined:.0f}</div>
      <div style="font-size:18px;font-weight:700;color:{comb_color};margin:6px 0;">{comb_label}</div>
      <div style="font-size:13px;color:#aaa;">{comb_desc}</div>
    </div>
    """, unsafe_allow_html=True)

with right:
    # Radar / spider chart
    labels_short = ["Kronos AI", "Technical", "Fundamental",
                    "Fear & Greed", "VIX", "Macro"]
    values = [s["score"] for s in SIGNALS]
    values_closed = values + [values[0]]
    labels_closed = labels_short + [labels_short[0]]

    fig_radar = go.Figure(go.Scatterpolar(
        r=values_closed,
        theta=labels_closed,
        fill="toself",
        fillcolor="rgba(92,158,255,0.18)",
        line=dict(color="#5c9eff", width=2),
        name="Score",
    ))
    fig_radar.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100],
                            tickfont=dict(size=10, color="#555"),
                            gridcolor="#2a2a40"),
            angularaxis=dict(tickfont=dict(size=12, color="#ccc"),
                             gridcolor="#2a2a40"),
            bgcolor="#0e1117",
        ),
        paper_bgcolor="#0e1117",
        font=dict(color="#ccc"),
        height=300,
        margin=dict(l=50, r=50, t=20, b=20),
        showlegend=False,
    )
    st.plotly_chart(fig_radar, use_container_width=True, config={"displayModeBar": False})

st.divider()

# ── SEC Insider Activity ────────────────────────────────────────────────────────
st.subheader("SEC Insider Activity (Form 4)")
st.caption("Recent insider transaction filings via SEC EDGAR — free, no API key.")

if sec_filings:
    for f in sec_filings[:8]:
        st.markdown(f"- **{f['date']}** — Form 4 filed")
else:
    st.info(f"No recent Form 4 filings found for **{ticker}** via SEC EDGAR.")

with st.expander("What is Form 4?"):
    st.markdown(
        "Form 4 is filed by corporate insiders (officers, directors, >10% shareholders) "
        "whenever they buy or sell shares. A cluster of recent filings can indicate insider activity, "
        "though the direction (buy vs. sell) requires reviewing each individual filing on sec.gov."
    )

st.divider()

# ── Fear & Greed History ────────────────────────────────────────────────────────
if fg_data.get("history"):
    with st.expander("Fear & Greed Index — 7-Day History"):
        for h in fg_data["history"]:
            v   = h["value"]
            lbl = h["label"]
            dt  = h["date"]
            bar_w = int(v)
            c = "#26a69a" if v >= 50 else "#ef5350"
            st.markdown(
                f'**{dt}** — '
                f'<span style="color:{c};font-weight:700;">{v}/100</span> '
                f'({lbl})',
                unsafe_allow_html=True,
            )

st.divider()

# ── Data Sources Reference ──────────────────────────────────────────────────────
with st.expander("All Data Sources & APIs Used"):
    st.markdown("""
| # | Source | Data Provided | Cost |
|---|--------|---------------|------|
| 1 | **Kronos** `NeoQuasar/Kronos-small` | OHLCV candlestick forecast | Free — HuggingFace |
| 2 | **yfinance** | Price history, OHLCV, fundamentals, VIX | Free — Yahoo Finance |
| 3 | **FRED API** (`fredapi`) | GDP, unemployment, Fed Funds, yield curve | Free — key at fred.stlouisfed.org |
| 4 | **Alternative.me** | Fear & Greed Index (risk sentiment proxy) | Free — no key required |
| 5 | **SEC EDGAR** | Form 4 insider transaction filings | Free — no key required |
| 6 | **yfinance RSS / Yahoo** | News headlines | Free — Yahoo Finance |

> All APIs above are zero-cost. FRED and Kronos model weights are free to access
> but require a one-time setup (API key or model download respectively).
""")

st.divider()
st.caption(DISCLOSURE)
