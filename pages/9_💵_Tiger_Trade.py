import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from lib.config import DISCLOSURE, APP_TITLE, APP_ICON
from lib.market_data import get_history, get_quote, get_stock_fundamentals
from lib.signals import compute_technical_score, compute_fundamental_score
from lib.macro import get_all_macro
from lib.free_apis import (
    get_fear_greed, score_vix, score_fear_greed, compute_macro_score,
)
from lib.kronos_runner import run_kronos_prediction, interpret_kronos
from lib.forecast_sim import monte_carlo, generate_pinescript
from lib.backtest import backtest_signals, interpret_backtest, position_size, bracket_order
from lib.news import ticker_news
from lib.best_pick import find_best_pick
from lib import tiger_client as tiger
from lib import paper_trader as paper
from lib import auth

st.set_page_config(
    page_title=f"Tiger Trade — {APP_TITLE}",
    page_icon="💵",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    section.main > div { font-size: 17px; }
    .tg-card { background:#1a1a2e; border-radius:12px; padding:16px 20px;
               margin-bottom:10px; border:1px solid #2a2a40; }
    .badge { display:inline-block; padding:3px 12px; border-radius:12px;
             font-size:12px; font-weight:700; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_TITLE}")
    st.caption("Educational market research tool")
    st.divider()

st.title("💵 Tiger Trade")

# Watchlist (defined early so the AI Best Pick section above the scan can use it)
default_watchlist = (
    "SOFI, F, INTC, T, PFE, BAC, HOOD, PLTR, NIO, AAL, CCL, SNAP, WBD, RIVN, NU, "
    "NVDA, AMD"
)  # liquid, mostly lower-priced US names so a ~$60 account can buy whole shares + trade quickly

# ── Mode toggle: Live vs Paper (Demo) — LIVE is password-locked ─────────────────
# Default is always Demo so a shared link is safe for anyone. Live (real money)
# requires the owner's password.
choice = st.segmented_control(
    "Trading mode",
    ["🟢 Paper (Demo)", "🔴 Live"],
    default="🟢 Paper (Demo)",
    key="trade_mode_toggle",
)
requested_live = (choice == "🔴 Live")
active_mode = "paper"

if requested_live:
    if not auth.is_configured():
        st.error("🔒 Live trading is disabled — no password is set. The owner must run "
                 "`python scripts/set_password.py` to enable real-money mode. Staying in Demo.")
    elif auth.live_unlocked():
        active_mode = "live"
        if st.button("🔒 Lock live again"):
            auth.lock()
            st.rerun()
    else:
        with st.form("live_unlock_form"):
            st.warning("🔒 **Live (real-money) mode is locked.** Enter the owner password to unlock. "
                       "Demo and all analysis stay available without it.")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Unlock live trading"):
                if auth.try_unlock(pw):
                    st.success("✅ Live unlocked for this session.")
                    st.rerun()
                else:
                    st.error("❌ Wrong password — staying in Demo.")
        if auth.live_unlocked():
            active_mode = "live"
        else:
            st.info("Showing **Demo** until the correct password is entered.")

# ── Account panel (branches on mode) ─────────────────────────────────────────────
held_symbols = set()
positions = []
acct_buying_power = 0.0
acct_cash = 0.0  # YOUR money (sizing uses this, never margin buying power)

if active_mode == "paper":
    st.info(
        "🧪 **PAPER — DEMO / SIMULATION.** This is **not** a real Tiger paper account "
        "(you don't have one yet). It's an in-app simulation with fake starting cash; "
        "orders 'fill' at the real live market price but **no real order is sent**. "
        "State resets when the app restarts. Use it to see how the flow works."
    )
    summ = paper.get_summary()
    positions = paper.get_positions()
    held_symbols = {p["symbol"] for p in positions}
    acct_buying_power = summ.get("buying_power", 0.0)
    acct_cash = summ.get("cash", 0.0)

    m = st.columns(4)
    m[0].metric("Net Liquidation", f"${summ['net_liquidation']:,.2f}")
    m[1].metric("Cash", f"${summ['cash']:,.2f}")
    m[2].metric("Buying Power", f"${summ['buying_power']:,.2f}")
    with m[3]:
        rc = st.number_input("Reset cash to", value=100000, step=10000, label_visibility="visible")
        if st.button("↺ Reset demo"):
            paper.reset(float(rc))
            st.rerun()

    st.subheader("Demo Positions")
    if positions:
        st.dataframe(pd.DataFrame(positions), use_container_width=True, hide_index=True)
    else:
        st.caption("No demo positions yet — place a simulated order below.")
    if paper.history():
        with st.expander("Demo fill history"):
            st.dataframe(pd.DataFrame(paper.history()), use_container_width=True, hide_index=True)
    connected = True  # demo is always "available"

else:  # live
    status = tiger.connection_status()
    if status["connected"]:
        st.success(f"Connected to Tiger Brokers · account `{status['account']}`")
        st.error("⚠️ LIVE MODE — orders here use **real money** on account "
                 f"`{status['account']}`. Switch to Paper (Demo) to practice safely.")
        summ = tiger.get_account_summary()
        positions = tiger.get_positions()
        held_symbols = {p["symbol"] for p in positions}
        acct_buying_power = (summ.get("buying_power") or 0.0) if summ else 0.0
        acct_cash = (summ.get("cash") or 0.0) if summ else 0.0
        if summ:
            m = st.columns(3)
            cur = summ.get("currency", "USD")
            m[0].metric("Net Liquidation", f"{cur} {summ.get('net_liquidation') or 0:,.2f}")
            m[1].metric("Your Cash", f"{cur} {acct_cash:,.2f}")
            m[2].metric("Buying Power", f"{cur} {acct_buying_power:,.2f}")
            if acct_buying_power > acct_cash + 1:
                st.warning(f"⚠️ Buying power (${acct_buying_power:,.2f}) is bigger than your cash "
                           f"(${acct_cash:,.2f}) because this account has **margin** (leverage). "
                           f"Anything above ${acct_cash:,.2f} is **borrowed money**. As a beginner, "
                           f"only trade with your own cash — this app sizes to your cash, not margin.")
        st.subheader("Your Positions")
        if positions:
            st.dataframe(pd.DataFrame(positions), use_container_width=True, hide_index=True)
        else:
            st.info("No open stock positions found.")
        connected = True
    else:
        connected = False
        if status["reason"] == "not_configured":
            st.warning("Tiger Brokers not configured for live trading. Add credentials to `.env`, "
                       "or use Paper (Demo) mode above.")
        else:
            st.error(f"Tiger live connection failed: {status['reason']}")

st.divider()

# ── AI Best Pick (one button → full analysis → best stock → one-click place) ─────
st.subheader("🤖 AI Best Pick — one button does everything")
st.caption("Runs backtest + Kronos forecast + Monte Carlo across your watchlist, keeps only names "
           "in a buy signal you can afford, checks the news, and ranks by blended conviction. "
           "Then place the winner's overnight bracket in one click. Analysis only — not advice or a profit guarantee.")

if st.button("🤖 Find the best stock to buy now", type="primary", key="bp_run"):
    tickers = [t.strip().upper() for t in default_watchlist.split(",") if t.strip()]
    cash_for_pick = acct_cash if acct_cash and acct_cash > 0 else 1e9
    prog = st.progress(0.0, text="Analyzing watchlist…")
    def _p(i, n, tk):
        prog.progress(min((i + 1) / max(n, 1), 1.0), text=f"Deep-analyzing {tk} (Kronos + Monte Carlo)…")
    try:
        results, affordable = find_best_pick(tickers, cash_for_pick, deep_n=3, progress=_p)
    except Exception as e:
        results, affordable = [], []
        st.error(f"Analysis error: {e}")
    prog.empty()
    st.session_state["best_pick_results"] = results
    st.session_state["best_pick_affordable"] = affordable

bp_results = st.session_state.get("best_pick_results")
if bp_results is not None:
    if not bp_results:
        st.warning("🚫 **No stock in your watchlist is both in a buy signal AND affordable with your cash "
                   "right now.** The strategy says WAIT — don't force a trade today.")
    else:
        best = bp_results[0]
        conv = best["conviction"]
        if conv >= 60:
            verdict, vcolor = "Decent setup", "#26a69a"
        elif conv >= 50:
            verdict, vcolor = "Weak / marginal — small size only", "#ffb300"
        else:
            verdict, vcolor = "No strong buy today — WAIT or tiny learning trade only", "#ef5350"

        price = best["price"]
        sigb = float(np.log(best["df"]["Close"] / best["df"]["Close"].shift(1)).dropna().std())
        bo = bracket_order(acct_cash if acct_cash else price, price, sigb, rr=2.0)
        k = best["kronos"]
        st.markdown(f"""
        <div class="tg-card" style="border:1px solid {vcolor}55;">
          <div style="font-size:13px;color:#888;">🤖 AI BEST PICK · conviction {conv}/100</div>
          <div style="font-size:30px;font-weight:900;color:{vcolor};">{best['ticker']} @ ${price:,.2f}</div>
          <div style="font-size:16px;font-weight:700;color:{vcolor};margin:4px 0;">{verdict}</div>
          <div style="font-size:13px;color:#bbb;">
            Backtest win {best['stats']['win_rate']:.0f}% · in a LONG signal now ·
            Kronos {k['dir']} ({k['pct']:+.1f}%, {k['score']:.0f}/100) ·
            Monte Carlo prob. up {best['prob_up']:.0f}% over 10d
          </div>
        </div>
        """, unsafe_allow_html=True)

        # candidate table
        st.dataframe(pd.DataFrame([{
            "Ticker": r["ticker"], "Conviction": r["conviction"], "Price": round(r["price"], 2),
            "Win %": r["stats"]["win_rate"], "Kronos": f"{r['kronos']['dir']} {r['kronos']['pct']:+.1f}%",
            "Prob up %": r["prob_up"],
        } for r in bp_results]), use_container_width=True, hide_index=True)

        # news on the winner
        news = ticker_news(best["ticker"], limit=3)
        if news:
            st.markdown(f"**📰 News on {best['ticker']}:**")
            for n in news:
                meta = " · ".join(x for x in [n.get("publisher", ""), n.get("time_ago", "")] if x)
                st.markdown(f"- [{n['title']}]({n['url']}) — {meta}" if n.get("url") else f"- {n['title']}")

        # ── Place the winner ────────────────────────────────────────────────────
        is_paper_bp = active_mode == "paper"
        deploy = st.number_input("Amount to deploy (USD)", min_value=5,
                                 value=int(min(acct_cash, 50)) if acct_cash else 50,
                                 step=5, key="bp_deploy")
        frac_shares = (deploy / price) if price else 0
        st.markdown(f"**Fractional buy:** \\${deploy:,.0f} of {best['ticker']} ≈ "
                    f"**{frac_shares:.4f} shares** (market order, US regular hours, **no auto TP/SL**).")

        # Fractional buy (works at ANY price — no whole-share blocker)
        if is_paper_bp:
            if st.button(f"🟢 Buy \\${deploy:,.0f} of {best['ticker']} in DEMO", key="bp_frac_demo"):
                # demo trades whole shares; approximate with floor
                qd = max(1, int(deploy // price))
                r = paper.place_order(best["ticker"], "BUY", qd)
                (st.success if r.get("ok") else st.error)(
                    f"Demo bought {qd} {best['ticker']} @ ${r['fill']['price']:,.2f}"
                    if r.get("ok") else f"Demo rejected: {r.get('error')}")
                if r.get("ok"):
                    st.rerun()
        else:
            armed_f = st.checkbox("🔓 Arm — place REAL fractional market buy", key="bp_frac_arm")
            if st.button(f"🚀 Buy \\${deploy:,.0f} of {best['ticker']} LIVE (fractional)",
                         type="primary", disabled=not armed_f, key="bp_frac_live"):
                r = tiger.place_fractional_order(best["ticker"], "BUY", float(deploy))
                if r.get("ok"):
                    st.success(f"✅ Fractional buy submitted! Order ID: {r.get('order_id')}")
                    st.balloons()
                else:
                    st.error(f"Failed: {r.get('error')}")

        # Whole-share overnight bracket (only when you can afford ≥1 share — gives auto TP/SL)
        if bo and bo["shares"] >= 1 and not is_paper_bp:
            with st.expander(f"Alternative: whole-share overnight BRACKET ({bo['shares']}× with auto TP/SL)"):
                st.markdown(f"BUY {bo['shares']} {best['ticker']} @ \\${bo['entry']:,.2f} · "
                            f"TP \\${bo['take_profit']:,.2f} · SL \\${bo['stop_price']:,.2f} (auto-sells; works overnight)")
                armed_bp = st.checkbox("🔓 Arm — place REAL bracket", key="bp_arm")
                if st.button("🚀 Place bracket LIVE", disabled=not armed_bp, key="bp_place_live"):
                    r = tiger.place_bracket_order(best["ticker"], "BUY", bo["shares"],
                                                  entry_limit=bo["entry"], take_profit=bo["take_profit"],
                                                  stop_loss=bo["stop_price"])
                    (st.success if r.get("ok") else st.error)(
                        f"✅ Bracket submitted! Order ID: {r.get('order_id')}" if r.get("ok")
                        else f"Failed: {r.get('error')}")

        st.caption("ℹ️ Fractional = market order, US regular hours, **no attached stop/take-profit** (broker "
                   "limitation). For a hands-off overnight auto-sell, use the whole-share bracket above. "
                   + ("⚠️ Conviction is low today — consider waiting or trading small to learn."
                      if conv < 50 else ""))

st.divider()

# ── Quick Trade (fast in/out) ────────────────────────────────────────────────────
st.subheader("⚡ Quick Trade — fast in / out")
st.caption("For quick scalps: live price, one-tap buy/sell, and a flatten button. "
           "Still manual (your click = the order). The $25k day-trade rule was scrapped "
           "June 2026, but small cash accounts settle T+1 — see the note below.")

if not connected:
    st.info("Switch to Paper (Demo) or connect Tiger to use Quick Trade.")
else:
    qcols = st.columns([2, 1, 1, 1])
    q_symbol = qcols[0].text_input("Symbol", value="SOFI", key="q_sym").upper().strip()
    q_quote = get_quote(q_symbol) if q_symbol else {}
    q_price = q_quote.get("price")
    qcols[1].metric("Live price", f"${q_price:,.2f}" if q_price else "—",
                    f"{q_quote.get('pct_change'):+.2f}%" if q_quote.get("pct_change") is not None else "")
    q_qty = qcols[2].number_input("Qty", min_value=1, value=1, step=1, key="q_qty")
    max_aff = int(acct_cash // q_price) if (q_price and acct_cash) else 0
    qcols[3].metric("Max (your cash)", f"{max_aff}")

    if q_price:
        st.caption(f"Est. cost of {int(q_qty)} {q_symbol}: **${q_price*int(q_qty):,.2f}**  ·  "
                   f"your cash: ${acct_cash:,.2f}"
                   + (f"  ·  (buying power ${acct_buying_power:,.2f} includes margin — avoid)"
                      if acct_buying_power > acct_cash + 1 else ""))

    # Price chart so there's a visual of what you're trading
    if q_symbol:
        dfq = get_history(q_symbol, "3mo", "1d")
        if not dfq.empty and "Close" in dfq.columns:
            figq = go.Figure(go.Scatter(x=dfq.index, y=dfq["Close"],
                                        line=dict(color="#5c9eff", width=1.7), name=q_symbol))
            if q_price:
                figq.add_hline(y=q_price, line=dict(color="#aaa", dash="dot"),
                               annotation_text=f"now ${q_price:,.2f}", annotation_position="right")
            figq.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                               font=dict(color="#ccc"), height=220,
                               margin=dict(l=0, r=0, t=10, b=0),
                               title=dict(text=f"{q_symbol} — last 3 months", font=dict(size=13)),
                               xaxis=dict(gridcolor="#1e1e2e"), yaxis=dict(gridcolor="#1e1e2e"))
            st.plotly_chart(figq, use_container_width=True, config={"displayModeBar": False})
        else:
            st.warning(f"Couldn't load a price chart for **{q_symbol}** — check the symbol is a valid US ticker.")

    # current position in this symbol
    cur_pos = next((p for p in positions if p["symbol"] == q_symbol), None)
    if cur_pos:
        st.caption(f"You hold **{cur_pos['quantity']} {q_symbol}** "
                   f"(avg ${cur_pos.get('avg_cost','?')}, P&L ${cur_pos.get('unrealized_pnl','?')}).")

    is_paper = active_mode == "paper"
    armed = True
    if not is_paper:
        armed = st.checkbox("🔓 Arm LIVE trading (real money)", value=False, key="q_arm")

    qb = st.columns(3)
    do_buy = qb[0].button(f"🟢 BUY {int(q_qty)}", use_container_width=True, disabled=not armed)
    do_sell = qb[1].button(f"🔴 SELL {int(q_qty)}", use_container_width=True, disabled=not armed)
    do_flat = qb[2].button("⏹ Flatten (sell all)", use_container_width=True,
                           disabled=not armed or not cur_pos)

    def _exec(action, qty):
        if is_paper:
            return paper.place_order(q_symbol, action, qty)
        return tiger.place_market_order(q_symbol, action, qty)

    if do_buy:
        r = _exec("BUY", int(q_qty))
        (st.success if r.get("ok") else st.error)(
            f"{'Demo ' if is_paper else 'LIVE '}BUY {int(q_qty)} {q_symbol}: "
            + (f"filled @ ${r['fill']['price']:,.2f}" if (is_paper and r.get('ok'))
               else (f"order {r.get('order_id')}" if r.get('ok') else r.get('error'))))
        if r.get("ok") and is_paper:
            st.rerun()
    if do_sell:
        r = _exec("SELL", int(q_qty))
        (st.success if r.get("ok") else st.error)(
            f"{'Demo ' if is_paper else 'LIVE '}SELL {int(q_qty)} {q_symbol}: "
            + (f"filled @ ${r['fill']['price']:,.2f}" if (is_paper and r.get('ok'))
               else (f"order {r.get('order_id')}" if r.get('ok') else r.get('error'))))
        if r.get("ok") and is_paper:
            st.rerun()
    if do_flat and cur_pos:
        r = _exec("SELL", int(cur_pos["quantity"]))
        (st.success if r.get("ok") else st.error)(
            f"Flatten {q_symbol}: " + ("done" if r.get("ok") else r.get("error")))
        if r.get("ok") and is_paper:
            st.rerun()

    with st.expander("⚠️ Can I really day-trade $100? Read this"):
        st.markdown(
            "- **PDT $25k rule: gone** (scrapped June 4, 2026) — you're no longer blocked from "
            "frequent day trades for being under $25k.\n"
            "- **But cash settles T+1.** In a cash account, after you sell, the proceeds take ~1 day "
            "to settle before you can reuse them. So you can't spin the same $100 through unlimited "
            "round-trips in one day without risking a *good-faith violation*.\n"
            "- **A margin account** now needs >$2,000 for intraday buying power — you're under that, so "
            "no leverage; you trade your own cash either way.\n"
            "- **Fees & spread eat small accounts.** On $100, a few cents of spread + any commission is a "
            "big % — quick scalping rarely nets profit at this size. Bigger edge comes from fewer, "
            "higher-conviction trades (the overnight plan) than from rapid in/out."
        )

st.divider()

# ── Recommendation scan ─────────────────────────────────────────────────────────
st.subheader("Buy / Sell Scan")
st.caption("Ranks each ticker by a combined score (technical + fundamental + market-wide "
           "sentiment/macro). Educational only — not financial advice.")

wl_raw = st.text_area("Watchlist (comma-separated)", value=default_watchlist, height=70)
dc = st.columns([3, 2])
with dc[0]:
    scan = st.button("🔎 Scan & Rank", type="primary", use_container_width=True)
with dc[1]:
    deep_rank = st.checkbox(
        "Deep rank top candidates with Kronos", value=False,
        help="After the fast scan, runs the Kronos forecast on the top candidates and "
             "blends its direction into the score. Slower (downloads weights on first run).",
    )
deep_n = st.slider("How many top candidates to deep-rank", 1, 5, 3, disabled=not deep_rank)


@st.cache_data(ttl=300)
def _market_signals():
    fg = get_fear_greed()
    vix_q = get_quote("^VIX")
    macro = get_all_macro()
    return (score_fear_greed(fg.get("value")), score_vix(vix_q.get("price")),
            compute_macro_score(macro))


if scan:
    tickers = [t.strip().upper() for t in wl_raw.split(",") if t.strip()]
    fg_score, vix_score, macro_score = _market_signals()
    rows = []
    prog = st.progress(0.0, text="Scanning…")
    for i, tk in enumerate(tickers):
        prog.progress((i + 1) / len(tickers), text=f"Scoring {tk}…")
        df = get_history(tk, "1y", "1d")
        if df.empty:
            continue
        info = get_stock_fundamentals(tk)
        tech_score, _ = compute_technical_score(df)
        fund_score, _ = compute_fundamental_score(info)
        combined = (0.40 * tech_score + 0.25 * fund_score +
                    0.15 * fg_score + 0.10 * vix_score + 0.10 * macro_score)
        if combined >= 62:
            signal = "BUY"
        elif combined <= 42:
            signal = "SELL" if tk in held_symbols else "AVOID"
        else:
            signal = "HOLD"
        rows.append({
            "Ticker": tk, "Score": round(combined, 1), "Signal": signal,
            "Technical": round(tech_score, 0), "Fundamental": round(fund_score, 0),
            "Held": "✓" if tk in held_symbols else "",
        })
    prog.empty()

    if rows:
        df_rank = pd.DataFrame(rows).sort_values("Score", ascending=False).reset_index(drop=True)
        df_rank["Kronos"] = "—"
        if deep_rank:
            top_tickers = df_rank["Ticker"].head(deep_n).tolist()
            kprog = st.progress(0.0, text="Running Kronos on top candidates…")
            for j, tk in enumerate(top_tickers):
                kprog.progress((j + 1) / len(top_tickers), text=f"Kronos forecasting {tk}…")
                dfk = get_history(tk, "2y", "1d")
                pred = run_kronos_prediction(dfk, pred_len=10, sample_count=3) if not dfk.empty else None
                if pred is None:
                    continue
                interp = interpret_kronos(dfk, pred)
                kscore = interp["direction_score"]
                mask = df_rank["Ticker"] == tk
                fast = float(df_rank.loc[mask, "Score"].iloc[0])
                blended = 0.35 * kscore + 0.65 * fast
                df_rank.loc[mask, "Score"] = round(blended, 1)
                df_rank.loc[mask, "Kronos"] = f"{kscore:.0f} ({interp['pct_change']:+.1f}%)"
                df_rank.loc[mask, "Signal"] = (
                    "BUY" if blended >= 62 else
                    ("SELL" if (blended <= 42 and tk in held_symbols)
                     else ("AVOID" if blended <= 42 else "HOLD")))
            kprog.empty()
            df_rank = df_rank.sort_values("Score", ascending=False).reset_index(drop=True)

        df_rank = df_rank[["Ticker", "Score", "Signal", "Kronos",
                           "Technical", "Fundamental", "Held"]]
        st.session_state["tiger_rank"] = df_rank

        def _hl(val):
            return {"BUY": "color:#26a69a;font-weight:700;", "SELL": "color:#ef5350;font-weight:700;",
                    "AVOID": "color:#ef5350;", "HOLD": "color:#ffb300;"}.get(val, "")
        st.dataframe(df_rank.style.map(_hl, subset=["Signal"]),
                     use_container_width=True, hide_index=True)
        top_buys = df_rank[df_rank["Signal"] == "BUY"]["Ticker"].tolist()
        if top_buys:
            st.markdown(f"**Top buy candidates:** {', '.join(top_buys)}")
    else:
        st.warning("No valid tickers scored. Check the symbols.")

st.divider()

# ── Outcome simulation + Top Pick ────────────────────────────────────────────────
st.subheader("Outcome Simulation & Top Pick")
st.caption("Monte Carlo projects the *range* of possible prices from historical volatility — "
           "a 'what could happen' spread, not a prediction. Combined with the scan + Kronos to "
           "suggest a pick. Educational only.")

df_rank_state = st.session_state.get("tiger_rank")
default_pick = "AAPL"
if df_rank_state is not None and not df_rank_state.empty:
    buys = df_rank_state[df_rank_state["Signal"] == "BUY"]
    default_pick = (buys.iloc[0]["Ticker"] if not buys.empty
                    else df_rank_state.iloc[0]["Ticker"])

sc = st.columns([2, 1, 1])
sim_ticker = sc[0].text_input("Ticker to simulate", value=default_pick).upper().strip()
sim_days = sc[1].selectbox("Horizon (days)", [5, 10, 20, 30], index=1)
sim_n = sc[2].selectbox("Simulations", [1000, 2000, 5000], index=1)
run_sim = st.button("🎲 Run outcome simulation & recommend", type="primary")

if run_sim and sim_ticker:
    dfh = get_history(sim_ticker, "1y", "1d")
    if dfh.empty:
        st.error(f"No price data for {sim_ticker}.")
    else:
        mc = monte_carlo(dfh, days=sim_days, n_sims=int(sim_n))
        if not mc:
            st.warning("Not enough data to simulate.")
        else:
            mcol = st.columns(5)
            mcol[0].metric("Current", f"${mc['current']:,.2f}")
            mcol[1].metric(f"Median in {sim_days}d", f"${mc['median_end']:,.2f}",
                           f"{mc['exp_return_pct']:+.2f}%")
            mcol[2].metric("Prob. up", f"{mc['prob_up']:.0f}%")
            mcol[3].metric("Downside (P10)", f"${mc['p10']:,.2f}")
            mcol[4].metric("Upside (P90)", f"${mc['p90']:,.2f}")

            # Fan chart
            b = mc["bands"]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=b["day"], y=b["p90"], line=dict(width=0),
                                     showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=b["day"], y=b["p10"], fill="tonexty",
                                     fillcolor="rgba(92,158,255,0.15)", line=dict(width=0),
                                     name="P10–P90 range"))
            fig.add_trace(go.Scatter(x=b["day"], y=b["p50"], line=dict(color="#5c9eff", width=2),
                                     name="Median path"))
            fig.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                              font=dict(color="#ccc"), height=300,
                              margin=dict(l=0, r=0, t=10, b=0),
                              xaxis=dict(title="Trading days ahead", gridcolor="#1e1e2e"),
                              yaxis=dict(title="Price", gridcolor="#1e1e2e"),
                              legend=dict(orientation="h", y=1.05, x=1, xanchor="right"))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            # ── Recommendation card (combines scan + Kronos + simulation) ───────────
            scan_score, scan_sig, kronos_str = None, None, "—"
            if df_rank_state is not None:
                hit = df_rank_state[df_rank_state["Ticker"] == sim_ticker]
                if not hit.empty:
                    scan_score = float(hit.iloc[0]["Score"])
                    scan_sig = hit.iloc[0]["Signal"]
                    kronos_str = hit.iloc[0]["Kronos"]

            prob_up = mc["prob_up"]
            if scan_score is not None:
                conviction = 0.6 * scan_score + 0.4 * prob_up
            else:
                conviction = prob_up

            if conviction >= 62 and prob_up >= 55:
                stance, scolor, action = "Lean BUY", "#26a69a", f"Consider buying {sim_ticker}"
            elif conviction <= 45 or prob_up <= 40:
                stance, scolor, action = "Avoid / Lean SELL", "#ef5350", f"Avoid or trim {sim_ticker}"
            else:
                stance, scolor, action = "Neutral / Watch", "#ffb300", f"Watch {sim_ticker} for a clearer setup"

            # rough position-size hint from buying power
            size_hint = ""
            if acct_buying_power and mc["current"]:
                shares = int(acct_buying_power // mc["current"])
                size_hint = f"At current buying power you could afford ~{shares} share(s)."

            st.markdown(f"""
            <div class="tg-card">
              <div style="font-size:13px;color:#888;">RECOMMENDATION · {sim_ticker}</div>
              <div style="font-size:30px;font-weight:900;color:{scolor};">{stance}</div>
              <div style="font-size:16px;color:#ddd;margin:6px 0;">{action}</div>
              <div style="font-size:13px;color:#aaa;">
                Scan score: {f'{scan_score:.0f}/100 ({scan_sig})' if scan_score is not None else 'run a scan to include'}
                &nbsp;·&nbsp; Kronos: {kronos_str}
                &nbsp;·&nbsp; Sim prob. up: {prob_up:.0f}%
                &nbsp;·&nbsp; Median move: {mc['exp_return_pct']:+.2f}% over {sim_days}d
              </div>
              <div style="font-size:12px;color:#666;margin-top:6px;">{size_hint}</div>
            </div>
            """, unsafe_allow_html=True)
            st.caption("⚠️ This is a model output, not advice. Simulations assume volatility repeats, "
                       "which it often doesn't. Verify independently before risking money.")

st.divider()

# ── Strategy backtest (PineScript logic, run in-app) + live pick ─────────────────
st.subheader("Run Strategy Backtest → Live Pick")
st.caption("PineScript only runs on TradingView, so this replays the **same strategy logic** "
           "(SMA200 trend + MACD + RSI) on historical data here, shows what would have happened, "
           "then turns it into a live buy suggestion + position size. Past results ≠ future profit.")

bc = st.columns([2, 1, 1])
bt_ticker = bc[0].text_input("Ticker to backtest", value=default_pick, key="bt_tk").upper().strip()
bt_period = bc[1].selectbox("History", ["2y", "5y", "10y"], index=1)
bt_risk = bc[2].selectbox("Risk per trade", ["1%", "2%", "3%"], index=1)
run_bt = st.button("📊 Run backtest & recommend live buy", type="primary")

if run_bt and bt_ticker:
    dfb = get_history(bt_ticker, bt_period, "1d")
    s = backtest_signals(dfb)
    if not s:
        st.error(f"Not enough history to backtest {bt_ticker} (need ~1yr+).")
    else:
        iv = interpret_backtest(s)
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Strategy return", f"{s['total_return_pct']:+.1f}%",
                  f"{s['total_return_pct'] - s['bh_return_pct']:+.1f}% vs hold")
        b2.metric("Win rate", f"{s['win_rate']:.0f}%", f"{s['n_trades']} trades")
        b3.metric("Max drawdown", f"{s['max_drawdown_pct']:.0f}%",
                  f"hold: {s['bh_max_drawdown_pct']:.0f}%", delta_color="off")
        b4.metric("Time in market", f"{s['time_in_market_pct']:.0f}%")

        # Equity curve: strategy vs buy & hold
        eq = go.Figure()
        eq.add_trace(go.Scatter(x=s["equity"].index, y=s["equity"].values,
                                name="Strategy", line=dict(color="#26a69a", width=2)))
        eq.add_trace(go.Scatter(x=s["bh_equity"].index, y=s["bh_equity"].values,
                                name="Buy & Hold", line=dict(color="#888", width=1.5, dash="dot")))
        eq.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font=dict(color="#ccc"),
                         height=260, margin=dict(l=0, r=0, t=10, b=0),
                         yaxis=dict(title="Growth of $1", gridcolor="#1e1e2e"),
                         xaxis=dict(gridcolor="#1e1e2e"),
                         legend=dict(orientation="h", y=1.05, x=1, xanchor="right"))
        st.plotly_chart(eq, use_container_width=True, config={"displayModeBar": False})

        # Price with buy/sell markers
        pr = go.Figure()
        pr.add_trace(go.Scatter(x=s["price"].index, y=s["price"].values,
                                name="Price", line=dict(color="#5c9eff", width=1.3)))
        buys = [m for m in s["markers"] if m["type"] == "BUY"]
        sells = [m for m in s["markers"] if m["type"] == "SELL"]
        if buys:
            pr.add_trace(go.Scatter(x=[m["date"] for m in buys], y=[m["price"] for m in buys],
                                    mode="markers", name="Buy",
                                    marker=dict(color="#26a69a", size=9, symbol="triangle-up")))
        if sells:
            pr.add_trace(go.Scatter(x=[m["date"] for m in sells], y=[m["price"] for m in sells],
                                    mode="markers", name="Sell",
                                    marker=dict(color="#ef5350", size=9, symbol="triangle-down")))
        pr.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font=dict(color="#ccc"),
                         height=260, margin=dict(l=0, r=0, t=10, b=0),
                         yaxis=dict(title="Price", gridcolor="#1e1e2e"),
                         xaxis=dict(gridcolor="#1e1e2e"),
                         legend=dict(orientation="h", y=1.05, x=1, xanchor="right"))
        st.plotly_chart(pr, use_container_width=True, config={"displayModeBar": False})

        gc, bd = st.columns(2)
        with gc:
            st.markdown("**✅ What's good**")
            for g in iv["good"]:
                st.markdown(f"- {g}")
        with bd:
            st.markdown("**⚠️ What's bad**")
            for b in iv["bad"]:
                st.markdown(f"- {b}")
        st.markdown(f"**Backtest verdict:** {iv['verdict']}")

        # ── Live buy recommendation + size ──────────────────────────────────────
        st.markdown("### 💸 Live buy recommendation")
        price_now = float(s["price"].iloc[-1])
        sig = float(np.log(dfb["Close"] / dfb["Close"].shift(1)).dropna().std())
        risk_pct = float(bt_risk.strip("%")) / 100

        # size to YOUR CASH (real account), never margin buying power
        live_cash = 0.0
        if tiger.is_configured():
            ls = tiger.get_account_summary()
            live_cash = (ls.get("cash") or 0.0) if ls else 0.0

        size_live = position_size(live_cash, price_now, sig, risk_pct=risk_pct)
        size_hypo = position_size(10000, price_now, sig, risk_pct=risk_pct)  # at a funded $10k

        # decide stance from backtest edge + currently-long + scan
        buyable = s["currently_long"] and iv["score"] >= 0
        stance = "BUY candidate" if buyable else "WAIT — no clean entry now"
        scolor = "#26a69a" if buyable else "#ffb300"

        st.markdown(f"""
        <div class="tg-card">
          <div style="font-size:13px;color:#888;">LIVE PICK · {bt_ticker} @ ${price_now:,.2f}</div>
          <div style="font-size:28px;font-weight:900;color:{scolor};">{stance}</div>
          <div style="font-size:14px;color:#ccc;margin:6px 0;">
            Strategy is {'LONG' if s['currently_long'] else 'FLAT'} now ·
            historical edge: {iv['verdict'].lower()} ·
            suggested stop ≈ ${size_hypo.get('stop_price','—')} ({size_hypo.get('stop_pct','—')}% below)
          </div>
          <div style="font-size:14px;color:#ddd;">
            <b>Size on your cash (${live_cash:,.2f})</b>:
            <b>{size_live.get('shares',0)} share(s)</b>
            {'' if live_cash >= price_now else '— ⚠️ not enough cash for 1 share.'}
          </div>
          <div style="font-size:13px;color:#999;margin-top:4px;">
            For reference, at a funded $10,000 this {risk_pct*100:.0f}%-risk rule would buy
            ~<b>{size_hypo.get('shares',0)} share(s)</b> (≈${size_hypo.get('notional',0):,.0f}),
            risking ≈${size_hypo.get('risk_dollars',0):,.0f} to the stop.
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.caption("⚠️ Not advice and not a profit guarantee. A backtested edge can vanish; position "
                   "sizing limits losses, it does not ensure gains. Only risk money you can afford to lose.")

st.divider()

# ── Auto-rank: backtest the whole watchlist → best buy now ───────────────────────
st.subheader("🏆 Auto-Rank Watchlist → Best Buy Now")
st.caption("Backtests the strategy on EVERY ticker in the watchlist above, ranks them by "
           "historical edge + whether they're in a buy signal right now, checks the news on the "
           "winner, and sizes a live order. Educational only — no profit guarantee.")

ar_period = st.selectbox("Backtest history for all", ["2y", "5y", "10y"], index=1, key="ar_period")
auto = st.button("🏁 Auto-run backtest across watchlist", type="primary")

if auto:
    tickers = [t.strip().upper() for t in wl_raw.split(",") if t.strip()]
    rows, store = [], {}
    prog = st.progress(0.0, text="Backtesting watchlist…")
    for i, tk in enumerate(tickers):
        prog.progress((i + 1) / len(tickers), text=f"Backtesting {tk}…")
        dfb = get_history(tk, ar_period, "1d")
        s = backtest_signals(dfb)
        if not s:
            continue
        excess = s["total_return_pct"] - s["bh_return_pct"]
        rank = (s["win_rate"]
                + (15 if s["beats_bh"] else -10)
                + (25 if s["currently_long"] else -15)
                + max(-20, min(20, excess))
                + max(-10, min(10, s["max_drawdown_pct"] - s["bh_max_drawdown_pct"])))
        store[tk] = (s, dfb)
        rows.append({
            "Ticker": tk, "Now": "LONG" if s["currently_long"] else "FLAT",
            "Rank": round(rank, 1), "Strategy %": s["total_return_pct"],
            "vs Hold": round(excess, 1), "Win %": s["win_rate"],
            "MaxDD %": s["max_drawdown_pct"], "Trades": s["n_trades"],
        })
    prog.empty()

    if not rows:
        st.warning("No tickers could be backtested. Check the watchlist symbols.")
    else:
        dfa = pd.DataFrame(rows).sort_values("Rank", ascending=False).reset_index(drop=True)
        st.session_state["auto_rank"] = dfa

        def _now_hl(v):
            return "color:#26a69a;font-weight:700;" if v == "LONG" else "color:#888;"
        st.dataframe(dfa.style.map(_now_hl, subset=["Now"]),
                     use_container_width=True, hide_index=True)

        longs = dfa[dfa["Now"] == "LONG"]
        if longs.empty:
            st.warning(f"⏸️ **No ticker is in a buy signal right now** — the strategy says WAIT. "
                       f"Highest historical rank is **{dfa.iloc[0]['Ticker']}**, but it's currently FLAT "
                       f"(no entry trigger today).")
        else:
            best = longs.iloc[0]["Ticker"]
            s_best, df_best = store[best]
            price = float(s_best["price"].iloc[-1])
            sig = float(np.log(df_best["Close"] / df_best["Close"].shift(1)).dropna().std())
            mc = monte_carlo(df_best, days=10, n_sims=2000)
            prob_up = mc.get("prob_up", 50) if mc else 50

            live_cash = 0.0
            if tiger.is_configured():
                ls = tiger.get_account_summary()
                live_cash = (ls.get("cash") or 0.0) if ls else 0.0
            size_live = position_size(live_cash, price, sig, risk_pct=0.02)
            size_hypo = position_size(10000, price, sig, risk_pct=0.02)

            st.markdown(f"""
            <div class="tg-card" style="border:1px solid #26a69a55;">
              <div style="font-size:13px;color:#888;">🏆 BEST BUY-NOW CANDIDATE</div>
              <div style="font-size:32px;font-weight:900;color:#26a69a;">{best} @ ${price:,.2f}</div>
              <div style="font-size:14px;color:#ddd;margin:6px 0;">
                In a LONG signal now · backtest {s_best['total_return_pct']:+.0f}%
                ({'beats' if s_best['beats_bh'] else 'trails'} hold {s_best['bh_return_pct']:+.0f}%) ·
                win rate {s_best['win_rate']:.0f}% · max DD {s_best['max_drawdown_pct']:.0f}% ·
                sim prob. up {prob_up:.0f}% over 10d
              </div>
              <div style="font-size:14px;color:#ddd;">
                <b>Live size (your cash ${live_cash:,.2f})</b>: <b>{size_live.get('shares',0)} share(s)</b>
                {'' if live_cash >= price else '— ⚠️ not enough cash for 1 share'}
                · suggested stop ≈ ${size_hypo.get('stop_price','—')} ({size_hypo.get('stop_pct','—')}% below)
              </div>
              <div style="font-size:13px;color:#999;margin-top:4px;">
                At a funded $10,000 (2% risk): ~<b>{size_hypo.get('shares',0)} share(s)</b>
                (≈${size_hypo.get('notional',0):,.0f}), risking ≈${size_hypo.get('risk_dollars',0):,.0f} to the stop.
              </div>
            </div>
            """, unsafe_allow_html=True)

            # News check on the winner
            st.markdown(f"**📰 Latest news on {best}** (check for anything that breaks the thesis):")
            news = ticker_news(best, limit=4)
            if news:
                for n in news:
                    meta = " · ".join(x for x in [n.get("publisher", ""), n.get("time_ago", "")] if x)
                    if n.get("url"):
                        st.markdown(f"- [{n['title']}]({n['url']})  \n  <span style='color:#777;font-size:12px;'>{meta}</span>",
                                    unsafe_allow_html=True)
                    else:
                        st.markdown(f"- {n['title']}  ({meta})")
            else:
                st.caption("No recent headlines pulled for this ticker.")
            st.caption("⚠️ Ranking is historical + statistical, not advice or a profit guarantee. "
                       "Read the news above — an earnings miss, downgrade, or lawsuit can override any backtest. "
                       "Verify before risking money.")

st.divider()

# ── Overnight Order Plan (bracket order for NZ timezone) ─────────────────────────
st.subheader("🌙 Overnight Order Plan (bracket order)")
st.caption("Because you're in NZ and the US market runs while you sleep (~1:30–8am NZT), "
           "enter this **bracket order** in Tiger before bed: Tiger auto-buys at open and "
           "auto-sells at your take-profit or stop — no need to be awake. You place it; the broker runs it.")

ar_state = st.session_state.get("auto_rank")
op_default = default_pick
if ar_state is not None and not ar_state.empty:
    op_longs = ar_state[ar_state["Now"] == "LONG"]
    op_default = op_longs.iloc[0]["Ticker"] if not op_longs.empty else ar_state.iloc[0]["Ticker"]

opc = st.columns([2, 1, 1])
op_ticker = opc[0].text_input("Ticker", value=op_default, key="op_tk").upper().strip()
op_capital = opc[1].number_input("Capital to deploy (USD)", min_value=10, value=60, step=10,
                                 help="~100 NZD ≈ 60 USD. Plan is sized to this.")
op_rr = opc[2].selectbox("Reward : Risk", ["1.5", "2.0", "3.0"], index=1)
build_op = st.button("🌙 Build overnight order plan", type="primary")

if build_op and op_ticker:
    dfo = get_history(op_ticker, "1y", "1d")
    if dfo.empty:
        st.error(f"No data for {op_ticker}.")
    else:
        price = get_quote(op_ticker).get("price") or float(dfo["Close"].iloc[-1])
        sig = float(np.log(dfo["Close"] / dfo["Close"].shift(1)).dropna().std())
        bo = bracket_order(float(op_capital), price, sig, rr=float(op_rr))
        if not bo or bo["shares"] < 1:
            st.warning(f"At \\${op_capital:,.0f}, one share of {op_ticker} (\\${price:,.2f}) is "
                       f"unaffordable. Put at least \\${price:,.0f} here (1 share), or pick a "
                       f"lower-priced ticker like SOFI/F/NU.")
        else:
            plan = (
                f"OVERNIGHT BRACKET ORDER — {op_ticker}\n"
                f"  Side:         BUY (long)\n"
                f"  Quantity:     {bo['shares']} share(s)   (~${bo['notional']:,.2f})\n"
                f"  Entry:        LIMIT ${bo['entry']:,.2f}  (or Market on open)\n"
                f"  Take-profit:  ${bo['take_profit']:,.2f}  (+{bo['tp_pct']}%)\n"
                f"  Stop-loss:    ${bo['stop_price']:,.2f}  (-{bo['stop_pct']}%)\n"
                f"  Time-in-force: GTC (good-till-cancelled)\n"
                f"  Risk:R/R:     risking ~${bo['risk_dollars']:,.2f} to make ~${bo['reward_dollars']:,.2f}  ({op_rr}:1)\n"
            )
            o1, o2, o3 = st.columns(3)
            o1.metric("Buy", f"{bo['shares']} @ ${bo['entry']:,.2f}")
            o2.metric("Take-profit", f"${bo['take_profit']:,.2f}", f"+{bo['tp_pct']}%")
            o3.metric("Stop-loss", f"${bo['stop_price']:,.2f}", f"-{bo['stop_pct']}%",
                      delta_color="inverse")
            st.code(plan, language="text")
            st.download_button("⬇️ Download plan", data=plan,
                               file_name=f"overnight_plan_{op_ticker}.txt", mime="text/plain")
            with st.expander("How to enter this in Tiger Trade before bed"):
                st.markdown(
                    f"1. Open **{op_ticker}** in Tiger Trade → tap **Trade / Buy**.\n"
                    f"2. Order type: **Limit**, price **${bo['entry']:,.2f}**, qty **{bo['shares']}**.\n"
                    f"3. Enable **Attached / Bracket order** (TP+SL), set "
                    f"**Take-profit ${bo['take_profit']:,.2f}** and **Stop-loss ${bo['stop_price']:,.2f}**.\n"
                    f"4. Time-in-force **GTC**. Review and submit.\n"
                    f"5. Sleep. Tiger fills at the US open and exits at TP or SL automatically.\n\n"
                    f"*If Tiger doesn't offer attached TP/SL on this account type, place the BUY limit, "
                    f"then add a separate **OCO** (one-cancels-other) sell with the TP and SL prices.*"
                )
            st.caption("⚠️ Sized to the capital you typed, not advice. The stop caps the loss; nothing "
                       "guarantees the take-profit fills. Past volatility set these levels — markets can gap past a stop.")
            st.session_state["op_plan"] = {
                "symbol": op_ticker, "shares": int(bo["shares"]), "entry": bo["entry"],
                "take_profit": bo["take_profit"], "stop_price": bo["stop_price"],
            }

# ── One-click place (persists across reruns) ─────────────────────────────────────
op_plan = st.session_state.get("op_plan")
if op_plan:
    st.markdown(f"#### 🚀 Place this bracket in one click — {op_plan['shares']}× {op_plan['symbol']}")
    st.caption(f"Buy {op_plan['shares']} @ limit ${op_plan['entry']:,.2f} · "
               f"take-profit ${op_plan['take_profit']:,.2f} · stop ${op_plan['stop_price']:,.2f} · GTC. "
               "You click; the broker buys and auto-sells at TP/SL.")
    is_paper_op = active_mode == "paper"
    if is_paper_op:
        if st.button("🟢 Place in DEMO (simulated buy)", key="op_place_demo"):
            r = paper.place_order(op_plan["symbol"], "BUY", op_plan["shares"])
            if r.get("ok"):
                st.success(f"Demo bought {op_plan['shares']} {op_plan['symbol']} @ "
                           f"${r['fill']['price']:,.2f}. (Demo can't auto-manage TP/SL — that's a live-broker feature.)")
                st.rerun()
            else:
                st.error(f"Demo rejected: {r.get('error')}")
    else:
        armed_op = st.checkbox("🔓 Arm — place this as a REAL live bracket order", key="op_arm")
        if st.button("🚀 Place LIVE bracket order", type="primary", disabled=not armed_op, key="op_place_live"):
            r = tiger.place_bracket_order(
                op_plan["symbol"], "BUY", op_plan["shares"],
                entry_limit=op_plan["entry"], take_profit=op_plan["take_profit"],
                stop_loss=op_plan["stop_price"],
            )
            if r.get("ok"):
                st.success(f"✅ LIVE bracket order submitted! Order ID: {r.get('order_id')}. "
                           "Tiger will buy at the limit and auto-sell at TP or SL.")
                st.balloons()
            else:
                st.error(f"Bracket order failed: {r.get('error')}")
                st.info("If it says attached legs aren't supported on this account, place the BUY via the "
                        "Quick Trade panel, then add a separate OCO sell in Tiger with the TP/SL prices above.")

st.divider()

# ── PineScript export ────────────────────────────────────────────────────────────
st.subheader("PineScript (TradingView backtest)")
st.caption("Paste this into TradingView's Pine Editor → add to chart → Strategy Tester to "
           "backtest the range of outcomes on real historical data. Mirrors the app's technical signals.")
pine_ticker = st.text_input("Symbol label for the script", value=default_pick).upper().strip() or "TICKER"
pine_code = generate_pinescript(pine_ticker)
st.code(pine_code, language="javascript")
st.download_button("⬇️ Download .pine", data=pine_code,
                   file_name=f"kronos_signals_{pine_ticker}.pine", mime="text/plain")

st.divider()

# ── Manual-confirm order ticket ─────────────────────────────────────────────────
st.subheader("Order Ticket  ·  manual confirm")
if not connected:
    st.info("Connect Tiger Brokers (or switch to Paper Demo) to place orders.")
else:
    is_paper = active_mode == "paper"
    oc = st.columns([2, 1, 1])
    o_symbol = oc[0].text_input("Symbol", value=default_pick, key="ot_sym").upper().strip()
    o_action = oc[1].selectbox("Action", ["BUY", "SELL"], key="ot_act")
    o_qty = oc[2].number_input("Quantity", min_value=1, value=1, step=1, key="ot_qty")

    if not is_paper:
        if st.button("👁️ Preview order (no placement)"):
            preview = tiger.preview_market_order(o_symbol, o_action, int(o_qty))
            if preview.get("error"):
                st.error(f"Preview failed: {preview['error']}")
            elif preview:
                st.json(preview)
            else:
                st.warning("No preview returned.")

    st.markdown("---")
    mode_word = "SIMULATED (demo)" if is_paper else "REAL-MONEY LIVE"
    confirm = st.checkbox(
        f"I understand this places a **{mode_word}** {o_action} market order for "
        f"**{int(o_qty)} {o_symbol}**."
    )
    place = st.button("✅ Place order", type="primary", disabled=not confirm)
    if place and confirm:
        if is_paper:
            res = paper.place_order(o_symbol, o_action, int(o_qty))
            if res.get("ok"):
                f = res["fill"]
                st.success(f"Demo {f['action']} filled: {f['qty']} {f['symbol']} @ ${f['price']:,.2f}")
                st.rerun()
            else:
                st.error(f"Demo order rejected: {res.get('error')}")
        else:
            res = tiger.place_market_order(o_symbol, o_action, int(o_qty))
            if res.get("ok"):
                st.success(f"LIVE order submitted. Order ID: {res.get('order_id')}")
            else:
                st.error(f"Order failed: {res.get('error')}")

st.divider()
st.caption(DISCLOSURE)
