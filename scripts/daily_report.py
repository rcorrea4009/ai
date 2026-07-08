"""
Daily trading briefing — runs headlessly (no Streamlit UI) and writes a markdown
report to reports/. Designed to be run by Windows Task Scheduler each morning/evening.

It does ANALYSIS ONLY. It does NOT place any orders. The report hands you a
ready-to-enter bracket order; you place it in Tiger yourself.

Usage:
    python scripts/daily_report.py [--capital 60] [--label morning]
"""
import os
import sys
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import numpy as np
from lib.market_data import get_history, get_quote
from lib.backtest import backtest_signals, interpret_backtest, bracket_order
from lib.news import ticker_news
from lib import tiger_client as tiger

WATCHLIST = ["SOFI", "F", "INTC", "T", "PFE", "BAC", "HOOD", "PLTR", "NIO", "AAL",
             "CCL", "SNAP", "WBD", "RIVN", "NU", "NVDA", "AMD"]


def rank_watchlist(period="5y"):
    out = {}
    for tk in WATCHLIST:
        df = get_history(tk, period, "1d")
        s = backtest_signals(df)
        if not s:
            continue
        excess = s["total_return_pct"] - s["bh_return_pct"]
        rank = (s["win_rate"]
                + (15 if s["beats_bh"] else -10)
                + (25 if s["currently_long"] else -15)
                + max(-20, min(20, excess))
                + max(-10, min(10, s["max_drawdown_pct"] - s["bh_max_drawdown_pct"])))
        price = get_quote(tk).get("price") or float(df["Close"].iloc[-1])
        out[tk] = {"stats": s, "rank": round(rank, 1), "price": price, "df": df}
    return out


def build(capital: float, label: str) -> str:
    ranked = rank_watchlist()
    if not ranked:
        return "# Daily Briefing\n\nNo data could be fetched. Check the connection."

    rows = sorted(ranked.items(), key=lambda kv: kv[1]["rank"], reverse=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [f"# {label.title()} Trading Briefing — {now}",
             "",
             "_Analysis only. No orders were placed. You enter any trade yourself in Tiger._",
             "",
             "## Watchlist ranking (backtested strategy)",
             "",
             "| Rank | Ticker | Now | Price | Strategy % | vs Hold | Win % | MaxDD % |",
             "|---|---|---|---|---|---|---|---|"]
    for tk, d in rows:
        s = d["stats"]
        lines.append(f"| {d['rank']:.0f} | {tk} | {'🟢 LONG' if s['currently_long'] else '⚪ FLAT'} "
                     f"| ${d['price']:,.2f} | {s['total_return_pct']:+.0f}% "
                     f"| {s['total_return_pct'] - s['bh_return_pct']:+.0f}% | {s['win_rate']:.0f}% "
                     f"| {s['max_drawdown_pct']:.0f}% |")

    longs = [(tk, d) for tk, d in rows if d["stats"]["currently_long"]]
    lines += ["", "## Best buy-now candidate", ""]
    if not longs:
        lines.append("⏸️ **No ticker is in a buy signal right now — the strategy says WAIT today.** "
                     "No overnight order recommended.")
    else:
        best, d = longs[0]
        s = d["stats"]
        price = d["price"]
        sig = float(np.log(d["df"]["Close"] / d["df"]["Close"].shift(1)).dropna().std())
        bo = bracket_order(capital, price, sig, rr=2.0)

        lines.append(f"### 🏆 {best} @ ${price:,.2f}")
        lines.append(f"- In a LONG signal now · backtest {s['total_return_pct']:+.0f}% "
                     f"({'beats' if s['beats_bh'] else 'trails'} hold {s['bh_return_pct']:+.0f}%) "
                     f"· win rate {s['win_rate']:.0f}% · max DD {s['max_drawdown_pct']:.0f}%")

        lines += ["", "### Overnight bracket order (enter in Tiger before bed)", "```"]
        if bo and bo["shares"] >= 1:
            lines += [
                f"BUY {bo['shares']} {best}  @ LIMIT ${bo['entry']:,.2f}   (~${bo['notional']:,.2f})",
                f"  Take-profit: ${bo['take_profit']:,.2f}  (+{bo['tp_pct']}%)",
                f"  Stop-loss:   ${bo['stop_price']:,.2f}  (-{bo['stop_pct']}%)",
                f"  TIF: GTC   ·   risk ~${bo['risk_dollars']:,.2f} to make ~${bo['reward_dollars']:,.2f}",
            ]
        else:
            lines.append(f"At ${capital:,.0f}, one whole share of {best} (${price:,.2f}) is unaffordable.")
            affordable = [(tk, dd) for tk, dd in longs if dd["price"] <= capital]
            if affordable:
                atk, ad = affordable[0]
                aprice = ad["price"]
                asig = float(np.log(ad["df"]["Close"] / ad["df"]["Close"].shift(1)).dropna().std())
                abo = bracket_order(capital, aprice, asig, rr=2.0)
                lines += [f"Affordable alternative in a signal: {atk} @ ${aprice:,.2f}",
                          f"BUY {abo['shares']} {atk} @ LIMIT ${abo['entry']:,.2f}",
                          f"  Take-profit: ${abo['take_profit']:,.2f}  ·  Stop-loss: ${abo['stop_price']:,.2f}"]
            else:
                lines.append("No watchlist name in a signal is affordable at this capital. "
                             "Tiger supports FRACTIONAL shares for US stocks — you can buy a "
                             f"${capital:,.0f} slice of {best} instead (set TP/SL at the prices above).")
        lines.append("```")

        # News check
        lines += ["", f"### 📰 News on {best} (does anything break the thesis?)", ""]
        news = ticker_news(best, limit=4)
        if news:
            for n in news:
                meta = " · ".join(x for x in [n.get("publisher", ""), n.get("time_ago", "")] if x)
                lines.append(f"- [{n['title']}]({n['url']}) — {meta}" if n.get("url")
                             else f"- {n['title']} — {meta}")
        else:
            lines.append("- (no headlines fetched)")

    # Account snapshot
    lines += ["", "## Your live Tiger account", ""]
    if tiger.is_configured():
        summ = tiger.get_account_summary()
        if summ:
            lines.append(f"- Net liquidation: ${summ.get('net_liquidation', 0):,.2f} · "
                         f"Cash: ${summ.get('cash', 0):,.2f} · "
                         f"Buying power: ${summ.get('buying_power', 0):,.2f}")
            if (summ.get("buying_power") or 0) < 5:
                lines.append("- ⚠️ Account effectively unfunded — fund it before any order can fill.")
        positions = tiger.get_positions()
        if positions:
            lines.append("- Positions: " + ", ".join(f"{p['symbol']} x{p['quantity']}" for p in positions))
    else:
        lines.append("- Tiger not configured.")

    lines += ["", "---",
              "_Educational only. Not financial advice and not a profit guarantee. A backtested "
              "edge can fail; stops can be gapped through. Only risk money you can afford to lose._"]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capital", type=float, default=60.0, help="USD to size the plan to (~100 NZD)")
    ap.add_argument("--label", default="daily")
    ap.add_argument("--open", action="store_true", help="open the report when done")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    report = build(args.capital, args.label)
    # Save into the in-app log store (morning/evening slot, keeps ~a week).
    slot = "morning" if "morning" in args.label.lower() else (
        "evening" if "evening" in args.label.lower() else args.label.lower())
    from lib.report_store import save as save_report
    save_report(slot, report)
    print(report)
    print(f"\n[saved to in-app log store · slot={slot}]")


if __name__ == "__main__":
    main()
