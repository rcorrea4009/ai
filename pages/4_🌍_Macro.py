import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from lib.config import DISCLOSURE, APP_TITLE, APP_ICON
from lib.macro import get_all_macro, get_fred_series, compute_yoy, compute_mom, FRED_DISPLAY
from lib.rates import get_yield_curve, render_yield_curve

st.set_page_config(page_title=f"Macro — {APP_TITLE}", page_icon="🌍",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>section.main > div { font-size: 17px; }</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_TITLE}")
    st.caption("Educational market research tool")
    st.divider()

st.title("🌍 Macro Dashboard")
st.caption("US macroeconomic indicators from FRED. For educational research only.")

fred_key = os.environ.get("FRED_API_KEY", "")
if not fred_key:
    st.warning(
        "⚠️ FRED API key not configured. Add `FRED_API_KEY=your_key` to the `.env` file "
        "in the project root. Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html"
    )
    st.stop()

with st.spinner("Loading macro data from FRED…"):
    macro_data = get_all_macro()

if not macro_data:
    st.error("Could not load FRED data. Check your API key.")
    st.stop()

# ── KPI Row ───────────────────────────────────────────────────────────────────
kpi_map = {
    "GDP Growth (QoQ %)": ("A191RL1Q225SBEA", None, "%"),
    "Unemployment": ("UNRATE", None, "%"),
    "CPI (YoY %)": ("CPIAUCSL", "yoy", "%"),
    "Core CPI (YoY %)": ("CPILFESL", "yoy", "%"),
    "Fed Funds": ("FEDFUNDS", None, "%"),
    "10Y Yield": ("GS10", None, "%"),
    "2Y Yield": ("GS2", None, "%"),
    "10Y–2Y Spread": (None, "spread", "bps"),
}

kpi_values = {}
s10 = macro_data.get("GS10")
s2 = macro_data.get("GS2")
if s10 is not None and s2 is not None and not s10.empty and not s2.empty:
    spread = (s10.iloc[-1] - s2.iloc[-1]) * 100
    kpi_values["10Y–2Y Spread"] = (spread, None, "bps")

for label, (sid, transform, unit) in kpi_map.items():
    if label == "10Y–2Y Spread":
        continue
    s = macro_data.get(sid)
    if s is None or s.empty:
        continue
    if transform == "yoy":
        s = compute_yoy(s).dropna()
    val = float(s.iloc[-1])
    delta = float(s.iloc[-1] - s.iloc[-2]) if len(s) > 1 else None
    kpi_values[label] = (val, delta, unit)

kpi_keys = list(kpi_map.keys())
cols = st.columns(len(kpi_keys))
for i, label in enumerate(kpi_keys):
    if label in kpi_values:
        val, delta, unit = kpi_values[label]
        suffix = unit if unit else ""
        delta_str = f"{delta:+.2f}{suffix}" if delta is not None else None
        cols[i].metric(label, f"{val:.2f}{suffix}", delta_str)
    else:
        cols[i].metric(label, "—")

st.divider()

# ── Indicator Charts ──────────────────────────────────────────────────────────
CHART_CONFIGS = [
    ("GDP Growth (QoQ %)", "A191RL1Q225SBEA", None, "%", "#5c9eff"),
    ("Unemployment Rate", "UNRATE", None, "%", "#ef5350"),
    ("CPI YoY %", "CPIAUCSL", "yoy", "%", "#ffd700"),
    ("Core CPI YoY %", "CPILFESL", "yoy", "%", "#ff9800"),
    ("Fed Funds Rate", "FEDFUNDS", None, "%", "#26a69a"),
    ("10Y Treasury Yield", "GS10", None, "%", "#90caf9"),
    ("Retail Sales (Level)", "RSAFS", None, "$M", "#a5d6a7"),
    ("Industrial Production Index", "INDPRO", None, "", "#ce93d8"),
]

st.subheader("Indicator Charts")
for title, sid, transform, unit, color in CHART_CONFIGS:
    s = macro_data.get(sid)
    if s is None or s.empty:
        continue
    if transform == "yoy":
        s = compute_yoy(s).dropna()
    with st.expander(title, expanded=False):
        fig = go.Figure(go.Scatter(
            x=s.index, y=s.values,
            mode="lines", line=dict(color=color, width=2),
            hovertemplate=f"%{{x|%Y-%m}}: %{{y:.2f}}{unit}<extra></extra>",
        ))
        fig.update_layout(
            template="plotly_dark", height=280,
            margin=dict(l=10, r=10, t=10, b=10),
            yaxis_ticksuffix=unit if unit in ("%",) else "",
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

st.divider()

# ── Yield Curve ───────────────────────────────────────────────────────────────
st.subheader("Yield Curve")
with st.spinner("Loading yield curve…"):
    yc_df = get_yield_curve()
fig_yc = render_yield_curve(yc_df)
st.plotly_chart(fig_yc, use_container_width=True, config={"displayModeBar": False})

if s10 is not None and s2 is not None and not s10.empty and not s2.empty:
    spread_val = s10.iloc[-1] - s2.iloc[-1]
    spread_color = "#26a69a" if spread_val > 0 else "#ef5350"
    spread_label = "normal (positive)" if spread_val > 0 else "inverted (negative)"
    st.markdown(
        f'<span style="color:{spread_color}">10Y–2Y spread: <b>{spread_val:.2f}%</b> — {spread_label}</span>',
        unsafe_allow_html=True,
    )

st.divider()

# ── Claude Macro Pulse ────────────────────────────────────────────────────────
st.subheader("AI Macro Pulse Check")
st.caption("AI-generated educational summary. Not investment advice.")
if st.button("Generate Macro Pulse", key="macro_pulse_btn"):
    from lib.claude_analyst import macro_pulse
    with st.spinner("Asking Claude…"):
        pulse = macro_pulse(macro_data)
    st.markdown(pulse)
else:
    st.info("Click the button to generate an AI educational summary of current macro conditions.")

st.divider()
st.caption(DISCLOSURE)
