import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import plotly.graph_objects as go

from lib.config import DISCLOSURE, APP_TITLE, APP_ICON
from lib.market_data import get_history, get_quote, get_stock_fundamentals
from lib.signals import compute_technical_score, compute_fundamental_score
from lib.macro import get_all_macro
from lib.free_apis import (
    get_fear_greed,
    score_vix,
    score_fear_greed,
    compute_macro_score,
)
from lib.kronos_runner import run_kronos_prediction, interpret_kronos
from lib.claude_analyst import ai_verdict

st.set_page_config(
    page_title=f"AI Verdict — {APP_TITLE}",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    section.main > div { font-size: 17px; }
    .verdict-hero {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 16px;
        padding: 26px 30px;
        margin: 8px 0 18px 0;
        border: 1px solid #2a2a40;
    }
    .verdict-tag {
        display:inline-block; padding:4px 12px; border-radius:14px;
        font-size:12px; font-weight:700; letter-spacing:.5px;
        text-transform:uppercase; margin-bottom:10px;
    }
    .verdict-score { font-size:60px; font-weight:900; line-height:1; }
    .verdict-sub   { font-size:14px; color:#9aa; margin-top:4px; }
    .chip-row span {
        display:inline-block; padding:3px 11px; border-radius:12px;
        font-size:12px; margin:3px 4px 3px 0; background:#252538; color:#cbd;
    }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_TITLE}")
    st.caption("Educational market research tool")
    st.divider()

st.title("🧠 AI Stock Verdict")
st.caption(
    "Point Claude at any stock — it runs the Kronos forecast, gathers six independent "
    "signals, and writes one synthesised AI read. Educational only, never financial advice."
)

c1, c2, c3 = st.columns([3, 2, 2])
with c1:
    ticker = st.text_input("Ticker Symbol", value="AAPL", max_chars=10).upper().strip()
with c2:
    pred_len = st.selectbox(
        "Forecast Horizon",
        [5, 10, 20, 30], index=1,
        format_func=lambda x: f"{x} trading days",
    )
with c3:
    sample_count = st.selectbox("Kronos Samples", [1, 3, 5], index=1)

run = st.button("🧠 Generate AI Verdict", type="primary", use_container_width=True)

if not ticker or not run:
    st.info("Enter a ticker and press **Generate AI Verdict**.")
    st.stop()

# ── Gather data ─────────────────────────────────────────────────────────────────
with st.spinner(f"Fetching market data for {ticker}…"):
    df_daily = get_history(ticker, "2y", "1d")
    quote    = get_quote(ticker)
    info     = get_stock_fundamentals(ticker)
    vix_q    = get_quote("^VIX")

if df_daily.empty:
    st.error(f"No price data for **{ticker}**. Verify the ticker and try again.")
    st.stop()

with st.spinner("Fetching sentiment & macro data…"):
    fg_data    = get_fear_greed()
    macro_data = get_all_macro()

with st.spinner("Running Kronos inference… (first run downloads model weights ~100 MB)"):
    pred_df = run_kronos_prediction(df_daily, pred_len=pred_len, sample_count=sample_count)
kronos_interp = interpret_kronos(df_daily, pred_df) if pred_df is not None else None

# ── Compute the six signals (mirrors Kronos Predictor) ──────────────────────────
tech_score, tech_details = compute_technical_score(df_daily)
fund_score, fund_details = compute_fundamental_score(info)
vix_val   = vix_q.get("price")
vix_score = score_vix(vix_val)
fg_val    = fg_data.get("value")
fg_score  = score_fear_greed(fg_val)
macro_score = compute_macro_score(macro_data)

SIGNALS = [
    ("Kronos AI Forecast", kronos_interp["direction_score"] if kronos_interp else 50.0, 0.30),
    ("Technical Strength",  tech_score,  0.20),
    ("Fundamental Quality", fund_score,  0.15),
    ("Crypto Fear & Greed", fg_score,    0.15),
    ("VIX Stability",       vix_score,   0.10),
    ("Macro Environment",   macro_score, 0.10),
]
signal_scores = {n: s for n, s, _ in SIGNALS}
combined = sum(w * s for _, s, w in SIGNALS)

if combined >= 68:
    tilt, tilt_color = "Constructive", "#26a69a"
elif combined >= 52:
    tilt, tilt_color = "Mixed / Neutral", "#ffb300"
else:
    tilt, tilt_color = "Cautious", "#ef5350"

name = info.get("longName", ticker)

# ── Hero card ───────────────────────────────────────────────────────────────────
price = quote.get("price")
pct_day = quote.get("pct_change")
price_str = f"${price:,.2f}" if price else "—"
day_str = f"{pct_day:+.2f}% today" if pct_day is not None else ""

st.markdown(f"""
<div class="verdict-hero">
  <div class="verdict-tag" style="background:{tilt_color}22;color:{tilt_color};">
    Signals lean: {tilt}
  </div>
  <div style="display:flex;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;gap:12px;">
    <div>
      <div style="font-size:24px;font-weight:800;">{name} <span style="color:#778;">({ticker})</span></div>
      <div class="verdict-sub">{price_str} &nbsp;·&nbsp; {day_str} &nbsp;·&nbsp; {info.get('sector','—')}</div>
    </div>
    <div style="text-align:right;">
      <div class="verdict-sub">Combined Model Score</div>
      <div class="verdict-score" style="color:{tilt_color};">{combined:.0f}<span style="font-size:18px;color:#556;">/100</span></div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# Signal chips
chips = "".join(
    f'<span>{n}: {s:.0f}</span>' for n, s in signal_scores.items()
)
st.markdown(f'<div class="chip-row">{chips}</div>', unsafe_allow_html=True)
st.divider()

# ── Claude's synthesised verdict ────────────────────────────────────────────────
left, right = st.columns([3, 2])

with left:
    st.subheader("Claude's AI Read")
    with st.spinner("Claude is analysing the forecast and signals…"):
        verdict_md = ai_verdict(
            ticker, info, tech_details, kronos_interp, signal_scores, combined
        )
    st.markdown(verdict_md)

with right:
    st.subheader("Signal Radar")
    labels = list(signal_scores.keys())
    values = list(signal_scores.values())
    fig_radar = go.Figure(go.Scatterpolar(
        r=values + [values[0]],
        theta=labels + [labels[0]],
        fill="toself",
        fillcolor="rgba(92,158,255,0.18)",
        line=dict(color="#5c9eff", width=2),
    ))
    fig_radar.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100],
                            tickfont=dict(size=10, color="#555"), gridcolor="#2a2a40"),
            angularaxis=dict(tickfont=dict(size=11, color="#ccc"), gridcolor="#2a2a40"),
            bgcolor="#0e1117",
        ),
        paper_bgcolor="#0e1117", font=dict(color="#ccc"),
        height=340, margin=dict(l=40, r=40, t=20, b=20), showlegend=False,
    )
    st.plotly_chart(fig_radar, use_container_width=True, config={"displayModeBar": False})

    if kronos_interp:
        st.metric(
            f"Kronos forecast ({pred_len}d)",
            f"${kronos_interp['pred_close_end']:,.2f}",
            f"{kronos_interp['pct_change']:+.2f}%",
        )
    else:
        st.caption("⚠️ Kronos model unavailable this run — verdict uses the other five signals.")

    st.page_link("pages/7_🔮_Kronos_Predictor.py",
                 label="See full Kronos Predictor breakdown →",
                 use_container_width=True)

st.divider()
st.caption(DISCLOSURE)
