"""
Tiger Brokers Open API wrapper.

Degrades gracefully: every function returns a safe value (None / empty / a
status dict) when credentials are missing, so the app runs without Tiger
configured. Nothing here places an order on its own — `place_market_order`
is only ever called from an explicit user button-click in the UI.

Env vars (see .env):
    TIGER_ID                developer id from quant.itigerup.com
    TIGER_ACCOUNT           account number (paper account while testing)
    TIGER_PRIVATE_KEY_PATH  path to PKCS#1 RSA private key
    TIGER_TRADE_MODE        "paper" (default) or "live"
"""
import os
import streamlit as st


def trade_mode() -> str:
    return (os.environ.get("TIGER_TRADE_MODE") or "paper").strip().lower()


def is_live() -> bool:
    return trade_mode() == "live"


def is_configured() -> bool:
    # DEMO_ONLY (public cloud deploy) hard-disables any live broker connection.
    if os.environ.get("DEMO_ONLY", "").strip().lower() in ("1", "true", "yes"):
        return False
    return all(
        os.environ.get(k)
        for k in ("TIGER_ID", "TIGER_ACCOUNT", "TIGER_PRIVATE_KEY_PATH")
    ) and os.path.exists(os.environ.get("TIGER_PRIVATE_KEY_PATH", ""))


@st.cache_resource(show_spinner="Connecting to Tiger Brokers…")
def _get_clients():
    """Return (trade_client, quote_client, account) or None if unavailable."""
    if not is_configured():
        return None
    try:
        from tigeropen.tiger_open_config import TigerOpenClientConfig
        from tigeropen.common.util.signature_utils import read_private_key
        from tigeropen.trade.trade_client import TradeClient
        from tigeropen.quote.quote_client import QuoteClient

        config = TigerOpenClientConfig()
        config.private_key = read_private_key(os.environ["TIGER_PRIVATE_KEY_PATH"])
        config.tiger_id = os.environ["TIGER_ID"]
        config.account = os.environ["TIGER_ACCOUNT"]
        lic = os.environ.get("TIGER_LICENSE")
        if lic:
            config.license = lic

        trade_client = TradeClient(config)
        quote_client = QuoteClient(config)
        return trade_client, quote_client, config.account
    except Exception as e:
        st.session_state["_tiger_error"] = str(e)
        return None


def connection_status() -> dict:
    """Lightweight status for the UI header."""
    if not is_configured():
        return {"connected": False, "reason": "not_configured", "mode": trade_mode()}
    clients = _get_clients()
    if clients is None:
        return {
            "connected": False,
            "reason": st.session_state.get("_tiger_error", "connection_failed"),
            "mode": trade_mode(),
        }
    return {"connected": True, "account": clients[2], "mode": trade_mode()}


def get_account_summary() -> dict:
    """Cash, net liquidation, buying power. Empty dict if unavailable."""
    clients = _get_clients()
    if clients is None:
        return {}
    trade_client, _, account = clients
    try:
        assets = trade_client.get_prime_assets(account=account)
        seg = assets.segments.get("S") if hasattr(assets, "segments") else None
        if seg is not None:
            return {
                "net_liquidation": getattr(seg, "net_liquidation", None),
                "cash": getattr(seg, "cash_available_for_trade", None)
                or getattr(seg, "cash", None),
                "buying_power": getattr(seg, "buying_power", None),
                "currency": getattr(seg, "currency", "USD"),
            }
    except Exception:
        pass
    # Fallback to classic get_assets
    try:
        for acc in trade_client.get_assets(account=account):
            s = acc.summary
            return {
                "net_liquidation": getattr(s, "net_liquidation", None),
                "cash": getattr(s, "cash", None),
                "buying_power": getattr(s, "buying_power", None),
                "currency": getattr(s, "currency", "USD"),
            }
    except Exception:
        pass
    return {}


def get_positions() -> list[dict]:
    """Current stock positions. Empty list if unavailable."""
    clients = _get_clients()
    if clients is None:
        return []
    trade_client, _, account = clients
    try:
        from tigeropen.common.consts import SecurityType
        positions = trade_client.get_positions(account=account, sec_type=SecurityType.STK)
        out = []
        for p in positions or []:
            out.append({
                "symbol": getattr(p.contract, "symbol", "?"),
                "quantity": getattr(p, "quantity", 0),
                "avg_cost": getattr(p, "average_cost", None),
                "market_price": getattr(p, "market_price", None),
                "market_value": getattr(p, "market_value", None),
                "unrealized_pnl": getattr(p, "unrealized_pnl", None),
            })
        return out
    except Exception:
        return []


def get_open_orders() -> list[dict]:
    """Pending/active orders (e.g. the take-profit and stop-loss legs of a bracket)."""
    clients = _get_clients()
    if clients is None:
        return []
    trade_client, _, account = clients
    try:
        orders = trade_client.get_open_orders(account=account)
        out = []
        for o in orders or []:
            out.append({
                "symbol": getattr(o.contract, "symbol", "?"),
                "action": getattr(o, "action", "?"),
                "quantity": getattr(o, "quantity", 0),
                "type": str(getattr(o, "order_type", "") or ""),
                "limit_price": getattr(o, "limit_price", None),
                "stop_price": getattr(o, "aux_price", None),
                "status": str(getattr(o, "status", "") or ""),
            })
        return out
    except Exception:
        return []


def preview_market_order(symbol: str, action: str, quantity: int, currency: str = "USD") -> dict:
    """
    Dry-run an order via Tiger's preview endpoint (commission, margin impact).
    Does NOT place anything. Returns {} if unavailable.
    """
    clients = _get_clients()
    if clients is None:
        return {}
    trade_client, _, account = clients
    try:
        from tigeropen.common.util.contract_utils import stock_contract
        from tigeropen.common.util.order_utils import market_order
        contract = stock_contract(symbol=symbol, currency=currency)
        order = market_order(account=account, contract=contract,
                             action=action.upper(), quantity=int(quantity))
        return trade_client.preview_order(order) or {}
    except Exception as e:
        return {"error": str(e)}


def place_bracket_order(symbol: str, action: str, quantity: int,
                        entry_limit: float, take_profit: float, stop_loss: float,
                        currency: str = "USD") -> dict:
    """
    Place a LIMIT entry with attached take-profit + stop-loss legs (a bracket).
    The broker then auto-exits at TP or SL. ONLY called from explicit user click.
    Note: Tiger supports attached legs on Global accounts; on others this errors
    and the caller should fall back to a manual OCO. Returns {"ok", ...}.
    """
    clients = _get_clients()
    if clients is None:
        return {"ok": False, "error": "Tiger not connected"}
    trade_client, _, account = clients
    try:
        from tigeropen.common.util.contract_utils import stock_contract
        from tigeropen.common.util.order_utils import limit_order_with_legs, order_leg
        contract = stock_contract(symbol=symbol, currency=currency)
        legs = [
            order_leg("PROFIT", price=round(float(take_profit), 2), time_in_force="GTC"),
            order_leg("LOSS", price=round(float(stop_loss), 2), time_in_force="GTC"),
        ]
        order = limit_order_with_legs(
            account=account, contract=contract, action=action.upper(),
            quantity=int(quantity), limit_price=round(float(entry_limit), 2),
            order_legs=legs, time_in_force="GTC",
        )
        order_id = trade_client.place_order(order)
        return {"ok": True, "order_id": order_id, "mode": trade_mode()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def place_fractional_order(symbol: str, action: str, amount: float, currency: str = "USD") -> dict:
    """
    Buy/sell a DOLLAR AMOUNT of a stock (fractional shares) via a market order.
    Fractional orders are market-only, regular US hours, and cannot carry an
    attached bracket (TP/SL). ONLY called from an explicit user click.
    """
    clients = _get_clients()
    if clients is None:
        return {"ok": False, "error": "Tiger not connected"}
    trade_client, _, account = clients
    try:
        from tigeropen.common.util.contract_utils import stock_contract
        from tigeropen.common.util.order_utils import market_order_by_amount
        contract = stock_contract(symbol=symbol, currency=currency)
        order = market_order_by_amount(account=account, contract=contract,
                                       action=action.upper(), amount=round(float(amount), 2))
        order_id = trade_client.place_order(order)
        return {"ok": True, "order_id": order_id, "mode": trade_mode()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def place_market_order(symbol: str, action: str, quantity: int, currency: str = "USD") -> dict:
    """
    Place a market order. ONLY call this from an explicit user confirmation.
    Returns {"ok": bool, "order_id"/"error": ...}.
    """
    clients = _get_clients()
    if clients is None:
        return {"ok": False, "error": "Tiger not connected"}
    trade_client, _, account = clients
    try:
        from tigeropen.common.util.contract_utils import stock_contract
        from tigeropen.common.util.order_utils import market_order
        contract = stock_contract(symbol=symbol, currency=currency)
        order = market_order(account=account, contract=contract,
                             action=action.upper(), quantity=int(quantity))
        order_id = trade_client.place_order(order)
        return {"ok": True, "order_id": order_id, "mode": trade_mode()}
    except Exception as e:
        return {"ok": False, "error": str(e)}
