import streamlit as st
import os
import pandas as pd

FRED_SERIES = {
    "GDP (Real, QoQ %)": "A191RL1Q225SBEA",
    "Unemployment Rate": "UNRATE",
    "CPI YoY %": "CPIAUCSL",
    "Core CPI YoY %": "CPILFESL",
    "Fed Funds Rate": "FEDFUNDS",
    "10Y-2Y Spread": None,  # computed
    "10Y Treasury": "GS10",
    "2Y Treasury": "GS2",
    "Retail Sales MoM %": "RSAFS",
    "Industrial Production": "INDPRO",
}

FRED_DISPLAY = {
    "A191RL1Q225SBEA": ("GDP Growth (QoQ %)", "%"),
    "UNRATE": ("Unemployment Rate", "%"),
    "CPIAUCSL": ("CPI (YoY %)", "%"),
    "CPILFESL": ("Core CPI (YoY %)", "%"),
    "FEDFUNDS": ("Fed Funds Rate", "%"),
    "GS10": ("10Y Treasury Yield", "%"),
    "GS2": ("2Y Treasury Yield", "%"),
    "RSAFS": ("Retail Sales (MoM %)", "%"),
    "INDPRO": ("Industrial Production Index", ""),
}


def _get_fred():
    try:
        from fredapi import Fred
        key = os.environ.get("FRED_API_KEY", "")
        if not key:
            return None
        return Fred(api_key=key)
    except ImportError:
        return None


@st.cache_data(ttl=3600)
def get_fred_series(series_id: str, periods: int = 60) -> pd.Series:
    fred = _get_fred()
    if fred is None:
        return pd.Series(dtype=float)
    try:
        s = fred.get_series(series_id)
        return s.dropna().tail(periods)
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=3600)
def get_all_macro() -> dict:
    fred = _get_fred()
    if fred is None:
        return {}
    results = {}
    ids = ["A191RL1Q225SBEA", "UNRATE", "CPIAUCSL", "CPILFESL",
           "FEDFUNDS", "GS10", "GS2", "RSAFS", "INDPRO"]
    for sid in ids:
        try:
            s = fred.get_series(sid).dropna()
            if not s.empty:
                results[sid] = s
        except Exception:
            pass
    return results


def compute_yoy(series: pd.Series) -> pd.Series:
    """Convert level series to YoY % change."""
    return series.pct_change(periods=12) * 100


def compute_mom(series: pd.Series) -> pd.Series:
    return series.pct_change(periods=1) * 100
