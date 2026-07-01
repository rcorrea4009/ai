import pandas as pd
import numpy as np


def _rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff().dropna()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not rsi.empty else 50.0


def _macd_signal(series: pd.Series) -> float:
    """Returns MACD histogram value as a score contribution."""
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = float((macd - signal).iloc[-1]) if not macd.empty else 0
    return hist


def compute_technical_score(df: pd.DataFrame) -> tuple[float, dict]:
    """
    Returns (score 0-100, details dict).
    Neutral language only — no buy/sell signals.
    """
    if df is None or df.empty or "Close" not in df.columns:
        return 50.0, {}

    close = df["Close"].dropna()
    if len(close) < 30:
        return 50.0, {}

    score = 0.0
    details = {}

    # 1. Price vs 200-day MA (25 pts)
    ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else close.rolling(len(close)).mean().iloc[-1]
    price = float(close.iloc[-1])
    above_200 = price > ma200
    details["vs_200dma"] = "Above 200DMA" if above_200 else "Below 200DMA"
    details["ma200"] = round(float(ma200), 2)
    score += 25 if above_200 else 0

    # 2. Price vs 50-day MA (15 pts)
    ma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else close.rolling(len(close)).mean().iloc[-1]
    above_50 = price > ma50
    details["vs_50dma"] = "Above 50DMA" if above_50 else "Below 50DMA"
    details["ma50"] = round(float(ma50), 2)
    score += 15 if above_50 else 0

    # 3. RSI (20 pts)
    rsi = _rsi(close)
    details["rsi"] = round(rsi, 1)
    if 40 <= rsi <= 70:
        details["rsi_bucket"] = "Healthy range (40–70)"
        score += 20
    elif rsi > 70:
        details["rsi_bucket"] = "Extended (>70)"
        score += 10
    elif rsi > 30:
        details["rsi_bucket"] = "Subdued (30–40)"
        score += 8
    else:
        details["rsi_bucket"] = "Oversold (<30)"
        score += 5

    # 4. 52-week range position (20 pts)
    high_52 = float(close.rolling(252).max().iloc[-1]) if len(close) >= 252 else float(close.max())
    low_52 = float(close.rolling(252).min().iloc[-1]) if len(close) >= 252 else float(close.min())
    rng = high_52 - low_52
    pos = (price - low_52) / rng if rng > 0 else 0.5
    details["52w_position"] = round(pos * 100, 1)
    details["52w_high"] = round(high_52, 2)
    details["52w_low"] = round(low_52, 2)
    score += pos * 20

    # 5. MACD histogram direction (20 pts)
    hist = _macd_signal(close)
    details["macd_hist"] = round(hist, 4)
    details["macd_direction"] = "Positive MACD histogram" if hist > 0 else "Negative MACD histogram"
    score += 20 if hist > 0 else 0

    return round(min(max(score, 0), 100), 1), details


def compute_fundamental_score(info: dict) -> tuple[float, dict]:
    """
    Returns (score 0-100, details dict).
    Neutral language only.
    """
    if not info:
        return 50.0, {}

    score = 0.0
    details = {}
    earned = 0
    possible = 0

    def _add(pts, condition, label_true, label_false):
        nonlocal score, earned, possible
        possible += pts
        if condition:
            score += pts
            earned += pts
            return label_true
        return label_false

    # Profitability — ROE (20 pts)
    roe = info.get("returnOnEquity")
    if roe is not None:
        label = _add(20, roe > 0.15,
                     f"ROE {roe*100:.1f}% — above 15%",
                     f"ROE {roe*100:.1f}% — below 15%")
        details["roe"] = label
    else:
        possible += 20
        details["roe"] = "ROE not available"

    # Profit margin (15 pts)
    margin = info.get("profitMargins")
    if margin is not None:
        label = _add(15, margin > 0.10,
                     f"Net margin {margin*100:.1f}% — above 10%",
                     f"Net margin {margin*100:.1f}% — below 10%")
        details["margin"] = label
    else:
        possible += 15
        details["margin"] = "Margin not available"

    # Debt/Equity (15 pts)
    de = info.get("debtToEquity")
    if de is not None:
        de_normalized = de / 100 if de > 5 else de
        label = _add(15, de_normalized < 1.0,
                     f"D/E {de_normalized:.2f} — moderate leverage",
                     f"D/E {de_normalized:.2f} — elevated leverage")
        details["leverage"] = label
    else:
        possible += 15
        details["leverage"] = "D/E not available"

    # Revenue growth (15 pts)
    rev_growth = info.get("revenueGrowth")
    if rev_growth is not None:
        label = _add(15, rev_growth > 0.05,
                     f"Revenue growth {rev_growth*100:.1f}%",
                     f"Revenue growth {rev_growth*100:.1f}% — below 5%")
        details["revenue_growth"] = label
    else:
        possible += 15
        details["revenue_growth"] = "Revenue growth not available"

    # P/E valuation (20 pts)
    pe = info.get("trailingPE")
    if pe is not None and pe > 0:
        if pe < 15:
            val = "Low multiple"
            score += 20
            possible += 20
        elif pe < 30:
            val = "Market-range multiple"
            score += 15
            possible += 20
        elif pe < 50:
            val = "Elevated multiple"
            score += 8
            possible += 20
        else:
            val = "High multiple"
            score += 0
            possible += 20
        details["valuation"] = f"P/E {pe:.1f} — {val}"
    else:
        possible += 20
        details["valuation"] = "P/E not available"

    # Current ratio (15 pts)
    cr = info.get("currentRatio")
    if cr is not None:
        label = _add(15, cr > 1.5,
                     f"Current ratio {cr:.2f} — adequate liquidity",
                     f"Current ratio {cr:.2f} — watch liquidity")
        details["liquidity"] = label
    else:
        possible += 15
        details["liquidity"] = "Liquidity data not available"

    normalized = (score / possible * 100) if possible > 0 else 50.0
    return round(min(max(normalized, 0), 100), 1), details


def at_a_glance(info: dict, tech_details: dict) -> list[dict]:
    """
    7 neutral-language chips for the At a glance panel.
    Each: {label, value, color}
    """
    chips = []

    # 1. Trend
    v200 = tech_details.get("vs_200dma", "—")
    chips.append({"label": "Trend", "value": v200,
                  "color": "green" if "Above" in v200 else "red"})

    # 2. Momentum (RSI bucket)
    rsi_b = tech_details.get("rsi_bucket", "—")
    rsi_v = tech_details.get("rsi", None)
    chips.append({"label": "Momentum",
                  "value": rsi_b if rsi_b != "—" else "—",
                  "color": "green" if rsi_v and 40 <= rsi_v <= 70 else "orange"})

    # 3. 52-week range position
    pos = tech_details.get("52w_position")
    if pos is not None:
        if pos >= 70:
            pos_label = f"Near 52w high ({pos:.0f}th %ile)"
        elif pos <= 30:
            pos_label = f"Near 52w low ({pos:.0f}th %ile)"
        else:
            pos_label = f"Mid-range ({pos:.0f}th %ile)"
    else:
        pos_label = "—"
    chips.append({"label": "52-Week Range", "value": pos_label, "color": "blue"})

    # 4. Profitability (ROE)
    roe = info.get("returnOnEquity")
    if roe is not None:
        if roe > 0.20:
            roe_label = f"High ROE ({roe*100:.0f}%)"
        elif roe > 0.10:
            roe_label = f"Moderate ROE ({roe*100:.0f}%)"
        else:
            roe_label = f"Low ROE ({roe*100:.0f}%)"
        roe_color = "green" if roe > 0.15 else ("orange" if roe > 0 else "red")
    else:
        roe_label, roe_color = "ROE N/A", "gray"
    chips.append({"label": "Profitability", "value": roe_label, "color": roe_color})

    # 5. Leverage
    de = info.get("debtToEquity")
    if de is not None:
        de_n = de / 100 if de > 5 else de
        if de_n < 0.5:
            lev_label, lev_color = f"Low leverage (D/E {de_n:.2f})", "green"
        elif de_n < 1.5:
            lev_label, lev_color = f"Moderate leverage (D/E {de_n:.2f})", "orange"
        else:
            lev_label, lev_color = f"High leverage (D/E {de_n:.2f})", "red"
    else:
        lev_label, lev_color = "Leverage N/A", "gray"
    chips.append({"label": "Leverage", "value": lev_label, "color": lev_color})

    # 6. Volatility (beta)
    beta = info.get("beta")
    if beta is not None:
        if beta < 0.8:
            beta_label, beta_color = f"Lower than market (β {beta:.2f})", "green"
        elif beta < 1.2:
            beta_label, beta_color = f"Similar to market (β {beta:.2f})", "blue"
        else:
            beta_label, beta_color = f"Higher than market (β {beta:.2f})", "orange"
    else:
        beta_label, beta_color = "Beta N/A", "gray"
    chips.append({"label": "Volatility", "value": beta_label, "color": beta_color})

    # 7. Valuation (P/E)
    pe = info.get("trailingPE")
    if pe and pe > 0:
        if pe < 15:
            pe_label, pe_color = f"Low multiple (P/E {pe:.1f})", "green"
        elif pe < 30:
            pe_label, pe_color = f"Market-range multiple (P/E {pe:.1f})", "blue"
        elif pe < 50:
            pe_label, pe_color = f"Elevated multiple (P/E {pe:.1f})", "orange"
        else:
            pe_label, pe_color = f"High multiple (P/E {pe:.1f})", "red"
    else:
        pe_label, pe_color = "P/E N/A", "gray"
    chips.append({"label": "Valuation", "value": pe_label, "color": pe_color})

    return chips
