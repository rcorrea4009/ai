"""
Python backtest of the same strategy the generated PineScript encodes
(SMA200 trend filter + MACD + RSI). PineScript only runs on TradingView, so
this is the in-app equivalent: it replays the rules on historical data and
reports what would have happened — equity curve, trades, win rate, drawdown.

Backtests describe the past. They do NOT guarantee future results, and a
strategy that looks great historically can still lose money going forward.
"""
import numpy as np
import pandas as pd


def _rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    gain = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def backtest_signals(df: pd.DataFrame) -> dict:
    """Long/flat trend strategy. Returns stats, equity curves, trades, markers."""
    if df is None or df.empty or "Close" not in df.columns or len(df) < 210:
        return {}
    d = df.copy()
    close = d["Close"]

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    rsi = _rsi(close, 14)
    sma200 = close.rolling(200).mean()

    bull = (close > sma200) & (macd > signal) & (rsi > 50) & (rsi < 70)
    bear = (close < sma200) & (macd < signal) & (rsi < 50)

    # Build position: enter long on bull when flat, exit on bear. Act next bar.
    pos = np.zeros(len(d))
    state = 0
    for i in range(len(d)):
        if state == 0 and bool(bull.iloc[i]):
            state = 1
        elif state == 1 and bool(bear.iloc[i]):
            state = 0
        pos[i] = state
    d["pos"] = pos
    d["pos_eff"] = d["pos"].shift(1).fillna(0)  # trade on next bar's return

    ret = close.pct_change().fillna(0)
    strat_ret = ret * d["pos_eff"]
    d["equity"] = (1 + strat_ret).cumprod()
    d["bh_equity"] = (1 + ret).cumprod()

    # Extract trades + markers
    trades, markers = [], []
    entry_price, entry_date = None, None
    prev = 0
    for i in range(len(d)):
        cur = d["pos_eff"].iloc[i]
        dt, px = d.index[i], float(close.iloc[i])
        if prev == 0 and cur == 1:
            entry_price, entry_date = px, dt
            markers.append({"date": dt, "price": px, "type": "BUY"})
        elif prev == 1 and cur == 0 and entry_price:
            trades.append({"entry": entry_date, "exit": dt,
                           "return_pct": round((px - entry_price) / entry_price * 100, 2)})
            markers.append({"date": dt, "price": px, "type": "SELL"})
            entry_price = None
        prev = cur
    if entry_price:  # still open at end
        px = float(close.iloc[-1])
        trades.append({"entry": entry_date, "exit": d.index[-1], "open": True,
                       "return_pct": round((px - entry_price) / entry_price * 100, 2)})

    def _max_dd(eq: pd.Series) -> float:
        roll = eq.cummax()
        return round(float(((eq - roll) / roll).min()) * 100, 2)

    wins = [t for t in trades if t["return_pct"] > 0]
    total_ret = round((float(d["equity"].iloc[-1]) - 1) * 100, 2)
    bh_ret = round((float(d["bh_equity"].iloc[-1]) - 1) * 100, 2)

    return {
        "total_return_pct": total_ret,
        "bh_return_pct": bh_ret,
        "n_trades": len(trades),
        "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0.0,
        "avg_win": round(np.mean([t["return_pct"] for t in wins]), 2) if wins else 0.0,
        "avg_loss": round(np.mean([t["return_pct"] for t in trades if t["return_pct"] <= 0]), 2)
                    if (len(trades) - len(wins)) else 0.0,
        "max_drawdown_pct": _max_dd(d["equity"]),
        "bh_max_drawdown_pct": _max_dd(d["bh_equity"]),
        "time_in_market_pct": round(float(d["pos_eff"].mean()) * 100, 1),
        "beats_bh": total_ret > bh_ret,
        "currently_long": bool(d["pos"].iloc[-1] == 1),
        "equity": d["equity"], "bh_equity": d["bh_equity"],
        "price": close, "markers": markers, "trades": trades,
    }


def interpret_backtest(s: dict) -> dict:
    """Turn stats into plain-language good/bad bullets + a verdict."""
    good, bad = [], []
    if s["beats_bh"]:
        good.append(f"Beat buy-and-hold ({s['total_return_pct']:+.1f}% vs {s['bh_return_pct']:+.1f}%).")
    else:
        bad.append(f"Underperformed buy-and-hold ({s['total_return_pct']:+.1f}% vs {s['bh_return_pct']:+.1f}%) "
                   "— a simple hold would have done better.")
    if s["win_rate"] >= 50:
        good.append(f"Win rate {s['win_rate']:.0f}% across {s['n_trades']} trades.")
    else:
        bad.append(f"Low win rate {s['win_rate']:.0f}% ({s['n_trades']} trades) — many losing trades.")
    if abs(s["max_drawdown_pct"]) < abs(s["bh_max_drawdown_pct"]):
        good.append(f"Smaller worst drawdown than holding ({s['max_drawdown_pct']:.0f}% vs "
                    f"{s['bh_max_drawdown_pct']:.0f}%) — less stomach-churn.")
    else:
        bad.append(f"Drawdown as deep as holding ({s['max_drawdown_pct']:.0f}%).")
    if s["n_trades"] < 4:
        bad.append(f"Only {s['n_trades']} trades — too few to trust the stats.")
    if s["currently_long"]:
        good.append("Strategy is currently in a LONG signal (trend filter is positive now).")
    else:
        bad.append("Strategy is currently FLAT (no entry signal right now).")

    score = len(good) - len(bad)
    verdict = ("Edge looks decent (historically)" if score >= 2
               else "Mixed / weak edge" if score >= 0
               else "Poor historical edge")
    return {"good": good, "bad": bad, "verdict": verdict, "score": score}


def bracket_order(capital: float, price: float, daily_sigma: float,
                  rr: float = 2.0, risk_pct: float = 0.02, horizon: int = 10) -> dict:
    """
    Build a full overnight bracket order: entry + take-profit + stop-loss + size.
    `rr` = reward:risk ratio (take-profit distance = rr × stop distance).
    The user enters this in Tiger before bed; the broker executes it overnight.
    """
    ps = position_size(capital, price, daily_sigma, risk_pct=risk_pct, horizon=horizon)
    if not ps:
        return {}
    stop_price = ps["stop_price"]
    stop_dist = price - stop_price
    take_profit = round(price + rr * stop_dist, 2)
    shares = ps["shares"]
    return {
        "entry": round(price, 2),
        "shares": shares,
        "stop_price": stop_price,
        "stop_pct": ps["stop_pct"],
        "take_profit": take_profit,
        "tp_pct": round((take_profit - price) / price * 100, 1),
        "rr": rr,
        "notional": round(shares * price, 2),
        "risk_dollars": round(shares * stop_dist, 2),
        "reward_dollars": round(shares * (take_profit - price), 2),
        "limited_by": ps["limited_by"],
    }


def position_size(equity: float, price: float, daily_sigma: float,
                  risk_pct: float = 0.02, stop_mult: float = 2.0,
                  horizon: int = 10) -> dict:
    """Risk-based sizing: risk `risk_pct` of equity to a volatility stop, capped by cash."""
    if not price or price <= 0:
        return {}
    stop_pct = max(stop_mult * daily_sigma * np.sqrt(horizon), 0.02)
    stop_dist = price * stop_pct
    risk_dollars = equity * risk_pct
    by_risk = int(risk_dollars // stop_dist) if stop_dist else 0
    by_cash = int(equity // price)
    shares = max(0, min(by_risk, by_cash))
    limited_by = "cash" if by_cash < by_risk else "risk budget"
    # Micro-account override: the 2%-risk rule yields 0 shares on tiny accounts even
    # when 1+ share is affordable. There, cash is the real constraint — size by cash.
    if shares == 0 and by_cash >= 1:
        shares = by_cash
        limited_by = "cash (account too small for the % risk rule — risk is a larger % here)"
    return {
        "shares": shares,
        "stop_price": round(price * (1 - stop_pct), 2),
        "stop_pct": round(stop_pct * 100, 1),
        "notional": round(shares * price, 2),
        "risk_dollars": round(shares * stop_dist, 2),
        "limited_by": limited_by,
    }
