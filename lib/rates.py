import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from lib.macro import get_fred_series

YIELD_CURVE_MATURITIES = {
    "1M": "DGS1MO",
    "3M": "DGS3MO",
    "6M": "DGS6MO",
    "1Y": "DGS1",
    "2Y": "DGS2",
    "3Y": "DGS3",
    "5Y": "DGS5",
    "7Y": "DGS7",
    "10Y": "DGS10",
    "20Y": "DGS20",
    "30Y": "DGS30",
}


@st.cache_data(ttl=3600)
def get_yield_curve() -> pd.DataFrame:
    rows = {}
    for label, sid in YIELD_CURVE_MATURITIES.items():
        s = get_fred_series(sid, periods=5)
        if not s.empty:
            rows[label] = float(s.iloc[-1])
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame({"Maturity": list(rows.keys()), "Yield": list(rows.values())})


def render_yield_curve(df: pd.DataFrame) -> go.Figure:
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(template="plotly_dark", title="Yield curve data unavailable")
        return fig
    fig = go.Figure(go.Scatter(
        x=df["Maturity"], y=df["Yield"],
        mode="lines+markers",
        line=dict(color="#5c9eff", width=2),
        marker=dict(size=8, color="#5c9eff"),
        hovertemplate="%{x}: %{y:.2f}%<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_dark",
        title="US Treasury Yield Curve (Current)",
        xaxis_title="Maturity",
        yaxis_title="Yield (%)",
        yaxis_ticksuffix="%",
        height=350,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig
