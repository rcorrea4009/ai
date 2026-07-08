import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd

from lib.config import DISCLOSURE, APP_TITLE, APP_ICON
from lib import kotak_client as kotak
from lib import ui

st.set_page_config(page_title=f"Kotak Neo — {APP_TITLE}", page_icon="🇮🇳",
                   layout="wide", initial_sidebar_state="expanded")
ui.inject()

with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_TITLE}")
    st.caption("Educational market research tool")
    st.divider()

ui.hero("🇮🇳 Kotak Neo",
        "Kotak Securities (Indian market — NSE/BSE). Interactive TOTP login each session. "
        "Recommend-only + manual confirm, same as Tiger. Educational only.",
        pills=["Indian market", "TOTP 2FA", "UNTESTED"])

st.warning("⚠️ This connector is **new and untested end-to-end** — it needs your real Kotak "
           "account + a live TOTP code. First login may surface field tweaks; tell me any error.")

if not kotak.is_configured():
    st.error("Kotak isn't configured. Add these to your `.env`, then restart:\n\n"
             "```\nKOTAK_CONSUMER_KEY=your_consumer_key\nKOTAK_MOBILE=+9198XXXXXXXX\n"
             "KOTAK_UCC=your_unique_client_code\nKOTAK_ENV=PROD\n```\n\n"
             "Get the consumer key from the Kotak Neo dev portal "
             "(https://tradeapi.kotaksecurities.com/devportal/applications).")
    st.stop()

# ── Login ────────────────────────────────────────────────────────────────────────
if not kotak.is_connected():
    st.subheader("🔐 Log in to Kotak Neo")
    st.caption(f"Mobile `{os.environ.get('KOTAK_MOBILE','')}` · UCC `{os.environ.get('KOTAK_UCC','')}` "
               "(from .env). Enter the 6-digit code from your authenticator app and your MPIN.")
    with st.form("kotak_login"):
        c1, c2 = st.columns(2)
        totp = c1.text_input("TOTP (authenticator code)", max_chars=6)
        mpin = c2.text_input("MPIN (6-digit)", type="password", max_chars=6)
        if st.form_submit_button("Log in", type="primary"):
            with st.spinner("Logging in to Kotak…"):
                r = kotak.login(totp, mpin)
            if r.get("ok"):
                st.success("✅ Logged in.")
                st.rerun()
            else:
                st.error(f"Login failed: {r.get('error')}")
    st.stop()

# ── Connected ────────────────────────────────────────────────────────────────────
top = st.columns([3, 1])
top[0].success("Connected to Kotak Neo")
if top[1].button("Log out"):
    kotak.logout()
    st.rerun()

summ = kotak.get_account_summary()
if summ and not summ.get("error"):
    m = st.columns(3)
    m[0].metric("Net", f"₹ {summ.get('net') or '—'}")
    m[1].metric("Cash / Collateral", f"₹ {summ.get('cash') or '—'}")
    m[2].metric("Currency", summ.get("currency", "INR"))
    with st.expander("Raw limits payload (for debugging field names)"):
        st.json(summ.get("raw", {}))
elif summ.get("error"):
    st.warning(f"Couldn't read limits: {summ['error']}")

st.subheader("Positions")
pos = kotak.get_positions()
if pos:
    st.dataframe(pd.DataFrame(pos), use_container_width=True, hide_index=True)
else:
    st.caption("No positions (or fields need mapping — check the raw payload above).")

st.divider()

# ── Order ticket ─────────────────────────────────────────────────────────────────
st.subheader("Order Ticket · manual confirm")
oc = st.columns([2, 1, 1, 1])
sym = oc[0].text_input("Trading symbol (e.g. TCS-EQ, RELIANCE-EQ)").upper().strip()
act = oc[1].selectbox("Action", ["BUY", "SELL"])
qty = oc[2].number_input("Qty", min_value=1, value=1, step=1)
prod = oc[3].selectbox("Product", ["CNC", "MIS"], help="CNC = delivery, MIS = intraday")

armed = st.checkbox("🔓 Arm — place a REAL order on Kotak")
if st.button("✅ Place order", type="primary", disabled=not (armed and sym)):
    r = kotak.place_order(sym, act, int(qty), product=prod)
    if r.get("ok"):
        st.success("Order sent to Kotak.")
        st.json(r.get("raw", {}))
    else:
        st.error(f"Order failed: {r.get('error')}")

st.divider()
st.caption(DISCLOSURE)
