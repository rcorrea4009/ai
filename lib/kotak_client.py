"""
Kotak Neo (Kotak Securities) broker connector — INDIAN market (NSE/BSE).

Unlike Tiger (stored RSA keys), Kotak uses interactive TOTP 2FA, so you log in
each session: consumer key + mobile + UCC come from .env; the 6-digit TOTP (from
your authenticator app) and your MPIN are entered in the app at login time.

Static config in .env:
    KOTAK_CONSUMER_KEY   from the Kotak Neo dev portal app
    KOTAK_MOBILE         registered mobile, e.g. +9198XXXXXXXX
    KOTAK_UCC            Unique Client Code (profile section of the app)
    KOTAK_ENV            PROD (default) or UAT

NOTE: This connector is UNTESTED end-to-end (needs a real Kotak account + live
TOTP). Response-field parsing is best-effort and may need tweaks on first login.
"""
import os
import streamlit as st

_CLIENT = "_kotak_client"


def _cfg(k: str) -> str:
    return os.environ.get(k, "").strip()


def is_configured() -> bool:
    return bool(_cfg("KOTAK_CONSUMER_KEY") and _cfg("KOTAK_MOBILE") and _cfg("KOTAK_UCC"))


def is_connected() -> bool:
    return st.session_state.get(_CLIENT) is not None


def login(totp: str, mpin: str) -> dict:
    """Run the two-step TOTP login and cache the authenticated client for the session."""
    if not is_configured():
        return {"ok": False, "error": "Kotak not configured — set KOTAK_* in .env"}
    try:
        from neo_api_client import NeoAPI
        client = NeoAPI(consumer_key=_cfg("KOTAK_CONSUMER_KEY"),
                        environment=_cfg("KOTAK_ENV") or "PROD")
        client.totp_login(mobile_number=_cfg("KOTAK_MOBILE"), ucc=_cfg("KOTAK_UCC"), totp=str(totp).strip())
        client.totp_validate(mpin=str(mpin).strip())
        st.session_state[_CLIENT] = client
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def logout():
    c = st.session_state.get(_CLIENT)
    try:
        if c:
            c.logout()
    except Exception:
        pass
    st.session_state[_CLIENT] = None


def get_account_summary() -> dict:
    """Margin/limits. Field names are best-effort; raw payload kept for debugging."""
    c = st.session_state.get(_CLIENT)
    if not c:
        return {}
    try:
        lim = c.limits()
        data = lim.get("data", lim) if isinstance(lim, dict) else {}
        return {
            "net": data.get("Net") or data.get("net"),
            "cash": data.get("CollateralValue") or data.get("MarginUsed"),
            "currency": "INR",
            "raw": lim,
        }
    except Exception as e:
        return {"error": str(e)}


def get_positions() -> list[dict]:
    c = st.session_state.get(_CLIENT)
    if not c:
        return []
    try:
        pos = c.positions()
        rows = pos.get("data", []) if isinstance(pos, dict) else []
        out = []
        for p in rows:
            out.append({
                "symbol": p.get("trdSym") or p.get("sym") or p.get("tok"),
                "quantity": p.get("flBuyQty") or p.get("cfBuyQty") or p.get("netQty"),
                "avg_cost": p.get("buyAmt") or p.get("avgnetPrice"),
            })
        return out
    except Exception:
        return []


def place_order(trading_symbol: str, action: str, quantity: int,
                product: str = "CNC", exchange_segment: str = "nse_cm") -> dict:
    """
    Market order on Kotak (Indian market). trading_symbol e.g. 'TCS-EQ'.
    product: CNC (delivery) or MIS (intraday). ONLY from an explicit user click.
    """
    c = st.session_state.get(_CLIENT)
    if not c:
        return {"ok": False, "error": "Not logged in to Kotak"}
    try:
        res = c.place_order(
            exchange_segment=exchange_segment, product=product, price="0",
            order_type="MKT", quantity=str(int(quantity)), validity="DAY",
            trading_symbol=trading_symbol.upper().strip(),
            transaction_type="B" if action.upper() == "BUY" else "S",
        )
        return {"ok": True, "raw": res}
    except Exception as e:
        return {"ok": False, "error": str(e)}
