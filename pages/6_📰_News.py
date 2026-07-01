import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from lib.config import DISCLOSURE, APP_TITLE, APP_ICON
from lib.news import market_news, ticker_news

st.set_page_config(page_title=f"News — {APP_TITLE}", page_icon="📰",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    section.main > div { font-size: 17px; }
    .headline-row { border-bottom:1px solid #333; padding:10px 0; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_TITLE}")
    st.caption("Educational market research tool")
    st.divider()

st.title("📰 News Feed")
st.caption("Recent market and company news. For informational purposes only.")

tab_market, tab_ticker = st.tabs(["Market Headlines", "By Ticker"])

def _render_articles(articles: list):
    if not articles:
        st.info("No articles found.")
        return
    for h in articles:
        title = h.get("title", "")
        url = h.get("url", "")
        pub = h.get("publisher", "")
        ago = h.get("time_ago", "")
        summary = h.get("summary", "")
        link = (f'<a href="{url}" target="_blank" style="color:#5c9eff;text-decoration:none;">{title}</a>'
                if url else title)
        st.markdown(f"""
        <div class="headline-row">
            <div style="font-size:16px;font-weight:600;line-height:1.4">{link}</div>
            <div style="font-size:12px;color:#888;margin:3px 0">{pub} · {ago}</div>
            <div style="font-size:13px;color:#bbb">{summary[:240]}</div>
        </div>
        """, unsafe_allow_html=True)

with tab_market:
    st.subheader("Market Headlines")
    limit = st.slider("Articles to show", 5, 30, 15, key="mkt_news_limit")
    with st.spinner("Loading market news…"):
        articles = market_news(limit=limit)
    _render_articles(articles)

with tab_ticker:
    st.subheader("Company / ETF News")
    col_t, col_n = st.columns([2, 1])
    with col_t:
        search_ticker = st.text_input("Ticker", placeholder="e.g. AAPL, NVDA, QQQ",
                                      max_chars=10, key="news_ticker_input").upper().strip()
    with col_n:
        n_articles = st.number_input("Articles", min_value=1, max_value=30, value=10, key="news_n")

    if search_ticker:
        with st.spinner(f"Loading news for {search_ticker}…"):
            articles = ticker_news(search_ticker, limit=int(n_articles))
        _render_articles(articles)
    else:
        st.info("Enter a ticker to search for company-specific headlines.")

st.divider()
st.caption(DISCLOSURE)
