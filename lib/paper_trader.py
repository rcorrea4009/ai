"""
Simulated PAPER trading account (a DEMO).

This is NOT connected to a real Tiger paper account — it's an in-session
simulation so you can see what the trading flow looks like without risking
money. State lives in st.session_state and resets when the app restarts.
Fills use the real live market price from yfinance, but no real order is sent.
"""
import streamlit as st
from datetime import datetime
from lib.market_data import get_quote

DEFAULT_CASH = 100_000.0
_K = "_paper_state"


def _state() -> dict:
    if _K not in st.session_state:
        st.session_state[_K] = {
            "cash": DEFAULT_CASH,
            "positions": {},   # symbol -> {"qty": int, "avg_cost": float}
            "history": [],     # list of fill dicts
        }
    return st.session_state[_K]


def reset(starting_cash: float = DEFAULT_CASH):
    st.session_state[_K] = {"cash": float(starting_cash), "positions": {}, "history": []}


def get_positions() -> list[dict]:
    s = _state()
    out = []
    for sym, p in s["positions"].items():
        if p["qty"] == 0:
            continue
        price = get_quote(sym).get("price") or p["avg_cost"]
        mv = price * p["qty"]
        cost = p["avg_cost"] * p["qty"]
        out.append({
            "symbol": sym,
            "quantity": p["qty"],
            "avg_cost": round(p["avg_cost"], 2),
            "market_price": round(price, 2),
            "market_value": round(mv, 2),
            "unrealized_pnl": round(mv - cost, 2),
        })
    return out


def get_summary() -> dict:
    s = _state()
    positions_value = sum(p["market_value"] for p in get_positions())
    net_liq = s["cash"] + positions_value
    return {
        "net_liquidation": round(net_liq, 2),
        "cash": round(s["cash"], 2),
        "buying_power": round(s["cash"], 2),  # cash account, no margin in the demo
        "currency": "USD",
    }


def place_order(symbol: str, action: str, quantity: int) -> dict:
    """Simulate a market order filled at the current live price."""
    s = _state()
    symbol = symbol.upper().strip()
    qty = int(quantity)
    price = get_quote(symbol).get("price")
    if not price:
        return {"ok": False, "error": f"No live price for {symbol}"}

    pos = s["positions"].get(symbol, {"qty": 0, "avg_cost": 0.0})

    if action.upper() == "BUY":
        cost = price * qty
        if cost > s["cash"]:
            return {"ok": False, "error": f"Insufficient demo cash (need ${cost:,.2f}, have ${s['cash']:,.2f})"}
        new_qty = pos["qty"] + qty
        # weighted average cost
        pos["avg_cost"] = (pos["avg_cost"] * pos["qty"] + cost) / new_qty if new_qty else 0.0
        pos["qty"] = new_qty
        s["cash"] -= cost
    else:  # SELL
        if qty > pos["qty"]:
            return {"ok": False, "error": f"Can't sell {qty} {symbol}; demo holds {pos['qty']}"}
        pos["qty"] -= qty
        s["cash"] += price * qty
        if pos["qty"] == 0:
            pos["avg_cost"] = 0.0

    s["positions"][symbol] = pos
    fill = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "symbol": symbol, "action": action.upper(),
        "qty": qty, "price": round(price, 2),
    }
    s["history"].append(fill)
    return {"ok": True, "fill": fill, "mode": "paper-demo"}


def history() -> list[dict]:
    return list(reversed(_state()["history"]))
