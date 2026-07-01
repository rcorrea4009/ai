import json
import os
from pathlib import Path
import pandas as pd

PORTFOLIO_FILE = Path(__file__).parent.parent / "data" / "portfolio.json"


def load_portfolio() -> list[dict]:
    """Load holdings from data/portfolio.json. Returns list of dicts."""
    if not PORTFOLIO_FILE.exists():
        return []
    try:
        with open(PORTFOLIO_FILE, "r") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_portfolio(holdings: list[dict]) -> None:
    PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(holdings, f, indent=2)


def holdings_to_df(holdings: list[dict]) -> pd.DataFrame:
    if not holdings:
        return pd.DataFrame(columns=["ticker", "shares", "cost_basis"])
    return pd.DataFrame(holdings)


def enrich_portfolio(holdings: list[dict], quotes: dict) -> pd.DataFrame:
    """Add current price, market value, return columns to holdings."""
    rows = []
    for h in holdings:
        ticker = h.get("ticker", "").upper()
        shares = float(h.get("shares", 0))
        cost_basis = float(h.get("cost_basis", 0))
        q = quotes.get(ticker, {})
        price = q.get("price") or 0
        mkt_val = price * shares
        cost_total = cost_basis * shares
        gain = mkt_val - cost_total
        gain_pct = (gain / cost_total * 100) if cost_total > 0 else 0
        rows.append({
            "Ticker": ticker,
            "Name": q.get("name", ticker),
            "Shares": shares,
            "Cost Basis": cost_basis,
            "Price": price,
            "Mkt Value": mkt_val,
            "Cost Total": cost_total,
            "Gain $": gain,
            "Gain %": gain_pct,
            "Sector": q.get("sector", "—"),
        })
    return pd.DataFrame(rows)
