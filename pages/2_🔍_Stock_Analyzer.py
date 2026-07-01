import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import plotly.graph_objects as go
from lib.config import DISCLOSURE, APP_TITLE, APP_ICON
from lib.market_data import PERIOD_MAP, get_quote, get_history, get_stock_fundamentals
from lib.charts import render_price_chart, render_gauge
from lib.signals import compute_technical_score, compute_fundamental_score, at_a_glance
from lib.logos import logo_img_tag
from lib.news import ticker_news

st.set_page_config(page_title=f"Stock Analyzer — {APP_TITLE}", page_icon="🔍",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    section.main > div { font-size: 17px; }
    .chip { display:inline-block; padding:3px 12px; border-radius:14px; font-size:13px; margin:3px; }
    .stat-label { font-size:12px; color:#aaa; }
    .stat-value { font-size:15px; font-weight:600; }
    .headline-row { border-bottom:1px solid #333; padding:8px 0; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_TITLE}")
    st.caption("Educational market research tool")
    st.divider()

st.title("🔍 Stock Analyzer")
st.caption("Factual company research — not financial advice.")

col_input, col_period = st.columns([2, 3])
with col_input:
    ticker = st.text_input("Ticker", value="AAPL", max_chars=10,
                           placeholder="e.g. AAPL, MSFT, TSLA").upper().strip()
with col_period:
    period_options = list(PERIOD_MAP.keys())
    period = st.segmented_control("Period", period_options, default="1Y", key="sa_period")
    if not period:
        period = "1Y"

if not ticker:
    st.info("Enter a ticker symbol to begin.")
    st.stop()

yf_period, yf_interval = PERIOD_MAP[period]

with st.spinner(f"Loading {ticker}…"):
    quote = get_quote(ticker)
    info = get_stock_fundamentals(ticker)
    df = get_history(ticker, yf_period, yf_interval)

price = quote.get("price")
pct = quote.get("pct_change")
name = info.get("longName") or info.get("shortName") or ticker
sector = info.get("sector") or "—"
industry = info.get("industry") or "—"
market_cap = info.get("marketCap")
pe = info.get("trailingPE")
beta = info.get("beta")

# ── Header ────────────────────────────────────────────────────────────────────
h_logo, h_name, h_metrics = st.columns([1, 4, 6])
with h_logo:
    st.markdown(logo_img_tag(ticker, 64), unsafe_allow_html=True)
with h_name:
    st.markdown(f"### {name}")
    st.caption(f"**{ticker}** · {sector} · {industry}")
with h_metrics:
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Price", f"${price:,.2f}" if price else "—",
               f"{pct:+.2f}%" if pct is not None else None)
    mc2.metric("Market Cap", f"${market_cap/1e9:.1f}B" if market_cap else "—")
    mc3.metric("P/E (TTM)", f"{pe:.1f}" if pe else "—")
    mc4.metric("Beta", f"{beta:.2f}" if beta else "—")

st.divider()

# ── Price Chart ───────────────────────────────────────────────────────────────
view_options = ["Performance", "Price", "Candlestick", "Area"]
view = st.segmented_control("Chart view", view_options, default="Performance", key="sa_view")
baseline = quote.get("prev_close") if period == "1D" else None
fig_price = render_price_chart(df, ticker, view=view or "Performance",
                               show_volume=True, baseline_price=baseline)
st.plotly_chart(fig_price, use_container_width=True, config={"displayModeBar": False})

st.divider()

# ── Snapshot ──────────────────────────────────────────────────────────────────
st.subheader("Snapshot")
st.caption("Factual observations derived from price history and financial data. "
           "Not a recommendation.")

tech_score, tech_details = compute_technical_score(df)
fund_score, fund_details = compute_fundamental_score(info)
chips = at_a_glance(info, tech_details)

chip_col, gauge_t, gauge_f = st.columns([2, 1.5, 1.5])

CHIP_COLORS = {
    "green": ("#1b5e20", "#a5d6a7"),
    "red": ("#b71c1c", "#ef9a9a"),
    "orange": ("#e65100", "#ffcc80"),
    "blue": ("#0d47a1", "#90caf9"),
    "gray": ("#333", "#aaa"),
}

with chip_col:
    st.markdown("**At a Glance**")
    for chip in chips:
        bg, fg = CHIP_COLORS.get(chip["color"], CHIP_COLORS["gray"])
        st.markdown(
            f'<div style="margin:4px 0;">'
            f'<span style="color:#aaa;font-size:12px;">{chip["label"]}: </span>'
            f'<span class="chip" style="background:{bg};color:{fg};">{chip["value"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

with gauge_t:
    fig_tg = render_gauge(tech_score, "Technical Strength",
                          "Trend, momentum, position vs averages")
    st.plotly_chart(fig_tg, use_container_width=True, config={"displayModeBar": False})
    with st.expander("Technical factors"):
        for k, v in tech_details.items():
            if not k.startswith("ma") and k not in ("52w_high", "52w_low"):
                st.markdown(f"- {v}")

with gauge_f:
    fig_fg = render_gauge(fund_score, "Fundamental Quality",
                          "Margins, returns, leverage, growth")
    st.plotly_chart(fig_fg, use_container_width=True, config={"displayModeBar": False})
    with st.expander("Fundamental factors"):
        for k, v in fund_details.items():
            st.markdown(f"- {v}")

st.divider()

# ── Key Statistics ─────────────────────────────────────────────────────────────
st.subheader("Key Statistics")

def _fmt(val, fmt=".2f", suffix="", prefix="", scale=1.0, pct=False):
    if val is None:
        return "—"
    v = float(val) * scale
    if pct:
        return f"{v*100:{fmt}}{suffix}"
    return f"{prefix}{v:{fmt}}{suffix}"

def _fmt_large(val):
    if val is None:
        return "—"
    v = float(val)
    if v >= 1e12:
        return f"${v/1e12:.2f}T"
    if v >= 1e9:
        return f"${v/1e9:.2f}B"
    if v >= 1e6:
        return f"${v/1e6:.2f}M"
    return f"${v:,.0f}"

ks1, ks2, ks3 = st.columns(3)

with ks1:
    st.markdown("**Valuation**")
    st.markdown(f"<div class='stat-label'>Market Cap</div><div class='stat-value'>{_fmt_large(info.get('marketCap'))}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>P/E (TTM)</div><div class='stat-value'>{_fmt(info.get('trailingPE'))}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>Forward P/E</div><div class='stat-value'>{_fmt(info.get('forwardPE'))}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>Price/Book</div><div class='stat-value'>{_fmt(info.get('priceToBook'))}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>Price/Sales</div><div class='stat-value'>{_fmt(info.get('priceToSalesTrailing12Months'))}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>EV/EBITDA</div><div class='stat-value'>{_fmt(info.get('enterpriseToEbitda'))}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>PEG Ratio</div><div class='stat-value'>{_fmt(info.get('pegRatio'))}</div>", unsafe_allow_html=True)
    st.markdown("")
    st.markdown("**Profitability**")
    st.markdown(f"<div class='stat-label'>Gross Margin</div><div class='stat-value'>{_fmt(info.get('grossMargins'), pct=True, suffix='%')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>Operating Margin</div><div class='stat-value'>{_fmt(info.get('operatingMargins'), pct=True, suffix='%')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>Net Margin</div><div class='stat-value'>{_fmt(info.get('profitMargins'), pct=True, suffix='%')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>ROE</div><div class='stat-value'>{_fmt(info.get('returnOnEquity'), pct=True, suffix='%')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>ROA</div><div class='stat-value'>{_fmt(info.get('returnOnAssets'), pct=True, suffix='%')}</div>", unsafe_allow_html=True)

with ks2:
    st.markdown("**Balance Sheet**")
    st.markdown(f"<div class='stat-label'>Total Cash</div><div class='stat-value'>{_fmt_large(info.get('totalCash'))}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>Total Debt</div><div class='stat-value'>{_fmt_large(info.get('totalDebt'))}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>Debt/Equity</div><div class='stat-value'>{_fmt(info.get('debtToEquity'))}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>Current Ratio</div><div class='stat-value'>{_fmt(info.get('currentRatio'))}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>Quick Ratio</div><div class='stat-value'>{_fmt(info.get('quickRatio'))}</div>", unsafe_allow_html=True)
    st.markdown("")
    st.markdown("**Growth**")
    st.markdown(f"<div class='stat-label'>Revenue Growth (YoY)</div><div class='stat-value'>{_fmt(info.get('revenueGrowth'), pct=True, suffix='%')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>Earnings Growth (YoY)</div><div class='stat-value'>{_fmt(info.get('earningsGrowth'), pct=True, suffix='%')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>EPS Growth (QoQ)</div><div class='stat-value'>{_fmt(info.get('earningsQuarterlyGrowth'), pct=True, suffix='%')}</div>", unsafe_allow_html=True)
    st.markdown("")
    st.markdown("**Income**")
    st.markdown(f"<div class='stat-label'>Revenue (TTM)</div><div class='stat-value'>{_fmt_large(info.get('totalRevenue'))}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>EBITDA</div><div class='stat-value'>{_fmt_large(info.get('ebitda'))}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>Free Cash Flow</div><div class='stat-value'>{_fmt_large(info.get('freeCashflow'))}</div>", unsafe_allow_html=True)

with ks3:
    st.markdown("**Trading**")
    st.markdown(f"<div class='stat-label'>Beta</div><div class='stat-value'>{_fmt(info.get('beta'))}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>52W High</div><div class='stat-value'>{_fmt(info.get('fiftyTwoWeekHigh'), prefix='$')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>52W Low</div><div class='stat-value'>{_fmt(info.get('fiftyTwoWeekLow'), prefix='$')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>50D Avg</div><div class='stat-value'>{_fmt(info.get('fiftyDayAverage'), prefix='$')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>200D Avg</div><div class='stat-value'>{_fmt(info.get('twoHundredDayAverage'), prefix='$')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>Avg Volume</div><div class='stat-value'>{_fmt(info.get('averageVolume'), fmt=',.0f')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>Short % Float</div><div class='stat-value'>{_fmt(info.get('shortPercentOfFloat'), pct=True, suffix='%')}</div>", unsafe_allow_html=True)
    st.markdown("")
    st.markdown("**Dividends**")
    st.markdown(f"<div class='stat-label'>Dividend Rate</div><div class='stat-value'>{_fmt(info.get('dividendRate'), prefix='$')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>Dividend Yield</div><div class='stat-value'>{_fmt(info.get('dividendYield'), pct=True, suffix='%')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>Payout Ratio</div><div class='stat-value'>{_fmt(info.get('payoutRatio'), pct=True, suffix='%')}</div>", unsafe_allow_html=True)
    st.markdown("")
    st.markdown("**Analyst Estimates**")
    st.markdown(f"<div class='stat-label'>Mean Target</div><div class='stat-value'>{_fmt(info.get('targetMeanPrice'), prefix='$')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>High Target</div><div class='stat-value'>{_fmt(info.get('targetHighPrice'), prefix='$')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'>Low Target</div><div class='stat-value'>{_fmt(info.get('targetLowPrice'), prefix='$')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='stat-label'># Analysts</div><div class='stat-value'>{info.get('numberOfAnalystOpinions') or '—'}</div>", unsafe_allow_html=True)

st.divider()

# ── Business Summary ──────────────────────────────────────────────────────────
biz = info.get("longBusinessSummary")
if biz:
    with st.expander("Business Summary"):
        st.write(biz)

st.divider()

# ── AI Analysis ───────────────────────────────────────────────────────────────
st.subheader("AI Analysis")
st.caption("AI-generated educational content. Not financial advice.")

tab_bull_bear, tab_deep, tab_news = st.tabs(["Bull / Bear Case", "Deep Analysis", "Recent Headlines"])

with tab_bull_bear:
    if st.button("Generate Bull / Bear Case", key="sa_bb_btn"):
        from lib.claude_analyst import bull_bear_case
        with st.spinner("Asking Claude…"):
            bull, bear = bull_bear_case(ticker, info, tech_details)
        col_b, col_r = st.columns(2)
        with col_b:
            st.markdown("#### Potential Strengths")
            st.markdown(bull)
        with col_r:
            st.markdown("#### Potential Risks")
            st.markdown(bear)
    else:
        st.info("Click the button to generate an AI educational analysis.")

with tab_deep:
    if st.button("Generate Deep Analysis", key="sa_deep_btn"):
        from lib.claude_analyst import deep_analysis
        with st.spinner("Asking Claude…"):
            analysis = deep_analysis(ticker, info, tech_details)
        st.markdown(analysis)
    else:
        st.info("Click the button to generate an in-depth educational overview.")

with tab_news:
    with st.spinner("Loading headlines…"):
        news = ticker_news(ticker, limit=10)
    if not news:
        st.info(f"No recent headlines found for {ticker}.")
    else:
        for h in news:
            title = h.get("title", "")
            url = h.get("url", "")
            pub = h.get("publisher", "")
            ago = h.get("time_ago", "")
            summary = h.get("summary", "")
            link = f'<a href="{url}" target="_blank" style="color:#5c9eff;text-decoration:none;">{title}</a>' if url else title
            st.markdown(f"""
            <div class="headline-row">
                <div style="font-size:15px;font-weight:600;">{link}</div>
                <div style="font-size:12px;color:#888;">{pub} · {ago}</div>
                <div style="font-size:13px;color:#bbb;margin-top:4px;">{summary[:180]}</div>
            </div>
            """, unsafe_allow_html=True)

st.divider()
st.caption(DISCLOSURE)
