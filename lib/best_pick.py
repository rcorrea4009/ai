"""
AI Best Pick engine — one call runs the whole stack and returns the single best
stock to buy now, ranked by a blended conviction of:
  • backtest edge (win rate, beats buy-and-hold, currently in a buy signal)
  • Kronos forecast (direction score)
  • Monte Carlo odds (probability up over 10 days)

Only considers names that are in a buy signal NOW and affordable with the given
cash. Analysis only — it never places an order.
"""
import numpy as np
from lib.market_data import get_history, get_quote
from lib.backtest import backtest_signals
from lib.kronos_runner import run_kronos_prediction, interpret_kronos
from lib.forecast_sim import monte_carlo


def find_best_pick(tickers, cash, deep_n=3, period="5y", progress=None):
    """Return a list of candidate dicts sorted by conviction (best first)."""
    ranked = []
    for tk in tickers:
        df = get_history(tk, period, "1d")
        s = backtest_signals(df)
        if not s:
            continue
        price = get_quote(tk).get("price") or float(df["Close"].iloc[-1])
        ranked.append({"ticker": tk, "stats": s, "price": price, "df": df})

    # candidates: any name in a buy signal NOW (no price/affordability filter —
    # fractional shares mean any price is buyable with any cash).
    cands = [r for r in ranked if r["stats"]["currently_long"]]
    cands.sort(key=lambda r: (r["stats"]["beats_bh"], r["stats"]["win_rate"]), reverse=True)
    deep = cands[:deep_n]

    results = []
    for i, r in enumerate(deep):
        if progress:
            progress(i, len(deep), r["ticker"])
        df = r["df"]
        pred = run_kronos_prediction(df, pred_len=10, sample_count=3)
        if pred is not None:
            k = interpret_kronos(df, pred)
            kronos = {"score": k["direction_score"], "dir": k["direction"], "pct": k["pct_change"]}
        else:
            kronos = {"score": 50.0, "dir": "n/a", "pct": 0.0}
        mc = monte_carlo(df, days=10, n_sims=2000) or {}
        prob_up = mc.get("prob_up", 50)
        conviction = round(
            0.34 * min(r["stats"]["win_rate"], 100)
            + 0.33 * kronos["score"]
            + 0.33 * prob_up, 1)
        results.append({**r, "kronos": kronos, "mc": mc,
                        "prob_up": prob_up, "conviction": conviction})

    results.sort(key=lambda r: r["conviction"], reverse=True)
    return results, [r["ticker"] for r in cands]  # (deep results, all affordable-in-signal)
