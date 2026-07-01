import streamlit as st
import yfinance as yf
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


def _time_ago(ts) -> str:
    """Human-readable relative time."""
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        elif isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            dt = ts
        now = datetime.now(tz=timezone.utc)
        delta = now - dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else now - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return "just now"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except Exception:
        return ""


def _parse_yf_news(raw: list) -> list[dict]:
    items = []
    for article in (raw or []):
        try:
            content = article.get("content", {})
            title = content.get("title") or article.get("title", "")
            url = (content.get("canonicalUrl", {}) or {}).get("url") or article.get("link", "")
            publisher = (content.get("provider", {}) or {}).get("displayName") or article.get("publisher", "")
            pub_date = content.get("pubDate") or article.get("providerPublishTime")
            summary = content.get("summary") or ""
            if title:
                items.append({
                    "title": title,
                    "url": url,
                    "publisher": publisher,
                    "time_ago": _time_ago(pub_date),
                    "summary": summary,
                })
        except Exception:
            continue
    return items


@st.cache_data(ttl=300)
def ticker_news(ticker: str, limit: int = 10) -> list[dict]:
    try:
        t = yf.Ticker(ticker)
        raw = t.news or []
        return _parse_yf_news(raw)[:limit]
    except Exception:
        return []


@st.cache_data(ttl=300)
def market_news(limit: int = 20) -> list[dict]:
    """Aggregate market news from yfinance index tickers + Yahoo RSS fallback."""
    items = []
    seen = set()

    # Try yfinance on SPY for broad market news
    for symbol in ["SPY", "^GSPC", "QQQ"]:
        try:
            raw = yf.Ticker(symbol).news or []
            for item in _parse_yf_news(raw):
                key = item["title"][:60]
                if key not in seen:
                    seen.add(key)
                    items.append(item)
            if len(items) >= limit:
                break
        except Exception:
            continue

    # RSS fallback
    if len(items) < limit:
        rss_urls = [
            "https://finance.yahoo.com/news/rssindex",
            "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
        ]
        for url in rss_urls:
            try:
                resp = requests.get(url, timeout=5,
                                    headers={"User-Agent": "Mozilla/5.0"})
                if resp.ok:
                    root = ET.fromstring(resp.text)
                    for item in root.iter("item"):
                        title = (item.findtext("title") or "").strip()
                        link = (item.findtext("link") or "").strip()
                        pub = item.findtext("pubDate") or ""
                        desc = (item.findtext("description") or "").strip()
                        key = title[:60]
                        if title and key not in seen:
                            seen.add(key)
                            items.append({
                                "title": title,
                                "url": link,
                                "publisher": "Yahoo Finance",
                                "time_ago": _time_ago(pub) if pub else "",
                                "summary": desc[:200],
                            })
            except Exception:
                continue

    return items[:limit]
