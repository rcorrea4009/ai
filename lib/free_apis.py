import requests
import streamlit as st
from datetime import datetime
import pandas as pd


@st.cache_data(ttl=3600)
def get_fear_greed() -> dict:
    """
    Alternative.me Fear & Greed Index — free, no API key.
    Primarily crypto sentiment but correlates with broad risk appetite.
    https://alternative.me/crypto/fear-and-greed-index/
    """
    try:
        resp = requests.get(
            "https://api.alternative.me/fng/?limit=7",
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if resp.ok:
            data = resp.json().get("data", [])
            if data:
                latest = data[0]
                return {
                    "value": int(latest["value"]),
                    "classification": latest["value_classification"],
                    "history": [
                        {
                            "date": datetime.fromtimestamp(int(d["timestamp"])).strftime("%Y-%m-%d"),
                            "value": int(d["value"]),
                            "label": d["value_classification"],
                        }
                        for d in data
                    ],
                }
    except Exception:
        pass
    return {}


@st.cache_data(ttl=86400)
def _get_sec_cik(ticker: str) -> str | None:
    """Resolve ticker → SEC CIK (10-digit, zero-padded). Free, no key."""
    try:
        resp = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            timeout=10,
            headers={"User-Agent": "KronosApp research@example.com"},
        )
        if resp.ok:
            for _, v in resp.json().items():
                if v.get("ticker", "").upper() == ticker.upper():
                    return str(v["cik_str"]).zfill(10)
    except Exception:
        pass
    return None


@st.cache_data(ttl=3600)
def get_sec_insider_filings(ticker: str) -> list[dict]:
    """
    SEC EDGAR Form 4 insider transaction filings. Free, no API key.
    https://www.sec.gov/cgi-bin/browse-edgar
    """
    cik = _get_sec_cik(ticker)
    if not cik:
        return []
    try:
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        resp = requests.get(
            url, timeout=10,
            headers={"User-Agent": "KronosApp research@example.com"},
        )
        if not resp.ok:
            return []
        recent = resp.json().get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        docs = recent.get("primaryDocument", [])

        results = []
        for i, form in enumerate(forms):
            if form == "4":
                results.append({
                    "date": dates[i] if i < len(dates) else "",
                    "doc": docs[i] if i < len(docs) else "",
                })
                if len(results) >= 10:
                    break
        return results
    except Exception:
        return []


def score_vix(vix_value: float | None) -> float:
    """VIX → market stability score (0–100, higher = calmer environment)."""
    if vix_value is None:
        return 50.0
    if vix_value < 12:
        return 88.0
    if vix_value < 15:
        return 78.0
    if vix_value < 20:
        return 62.0
    if vix_value < 25:
        return 46.0
    if vix_value < 30:
        return 32.0
    if vix_value < 40:
        return 18.0
    return 8.0


def score_fear_greed(fg_value: int | None) -> float:
    """Alternative.me index (0–100) → sentiment score (higher = more greed/bullish env)."""
    return float(fg_value) if fg_value is not None else 50.0


def compute_macro_score(fred_data: dict) -> float:
    """
    Macro environment score (0–100) from FRED data.
    Returns 50 when no FRED data is available (no key configured).
    """
    if not fred_data:
        return 50.0

    score = 50.0

    unrate = fred_data.get("UNRATE")
    if unrate is not None and hasattr(unrate, "iloc") and not unrate.empty:
        u = float(unrate.iloc[-1])
        if u < 4.0:
            score += 12
        elif u < 5.0:
            score += 5
        elif u > 6.5:
            score -= 12

    fedfunds = fred_data.get("FEDFUNDS")
    if fedfunds is not None and hasattr(fedfunds, "iloc") and not fedfunds.empty:
        r = float(fedfunds.iloc[-1])
        if r < 2.0:
            score += 10
        elif r < 3.5:
            score += 3
        elif r > 5.5:
            score -= 10

    gdp = fred_data.get("A191RL1Q225SBEA")
    if gdp is not None and hasattr(gdp, "iloc") and not gdp.empty:
        g = float(gdp.iloc[-1])
        if g > 3.0:
            score += 12
        elif g > 1.0:
            score += 5
        elif g < 0:
            score -= 15

    return round(min(max(score, 0), 100), 1)
