import pandas as pd
import numpy as np


def compute_etf_risk_score(df: pd.DataFrame, info: dict) -> tuple[float, dict]:
    """
    ETF risk score 0-100 (higher = more aggressive / risky).
    Based on: annualized volatility, max drawdown, concentration (top-10 weight).
    Returns (score, details).
    """
    details = {}
    components = []

    if df is not None and not df.empty and "Close" in df.columns:
        close = df["Close"].dropna()
        if len(close) >= 20:
            # Annualized volatility (252 trading days)
            daily_ret = close.pct_change().dropna()
            ann_vol = float(daily_ret.std() * np.sqrt(252)) * 100
            details["ann_volatility_pct"] = round(ann_vol, 1)
            # Map vol to 0-50 score contribution (30% vol = 50 pts)
            vol_score = min(ann_vol / 30 * 50, 50)
            components.append(vol_score)

            # Max drawdown over available history
            roll_max = close.cummax()
            drawdown = (close - roll_max) / roll_max * 100
            max_dd = float(drawdown.min())
            details["max_drawdown_pct"] = round(max_dd, 1)
            # Map drawdown to 0-30 score (50% drawdown = 30 pts)
            dd_score = min(abs(max_dd) / 50 * 30, 30)
            components.append(dd_score)

    # Concentration: sum of top-10 holdings weight
    holdings = info.get("holdings", [])
    if holdings:
        top_weights = sorted([h.get("weight", 0) for h in holdings], reverse=True)[:10]
        conc = sum(top_weights)
        details["top10_concentration_pct"] = round(conc * 100, 1)
        # Very concentrated (>80%) = 20 pts, diversified (<20%) = 0 pts
        conc_score = min(conc / 0.80 * 20, 20)
        components.append(conc_score)

    if not components:
        return 50.0, details

    raw = sum(components)
    score = round(min(max(raw, 0), 100), 1)
    details["score"] = score

    if score < 20:
        details["label"] = "Conservative"
    elif score < 40:
        details["label"] = "Moderate"
    elif score < 60:
        details["label"] = "Balanced"
    elif score < 80:
        details["label"] = "Aggressive"
    else:
        details["label"] = "Very Aggressive"

    return score, details
