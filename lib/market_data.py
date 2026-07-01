import yfinance as yf
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta


def _make_cf_session():
    # curl_cffi impersonates a real Chrome browser, bypassing Yahoo Finance's
    # datacenter-IP blocks (HTTP 401) that affect Streamlit Cloud deployments.
    try:
        from curl_cffi.requests import Session
        return Session(impersonate="chrome")
    except Exception:
        return None


_yf_session = _make_cf_session()

INDEX_TICKERS = {
    "S&P 500": "^GSPC",
    "Nasdaq 100": "^NDX",
    "Dow Jones": "^DJI",
    "Russell 2000": "^RUT",
    "VIX": "^VIX",
    "10Y Yield": "^TNX",
    "Gold": "GC=F",
    "Crude Oil": "CL=F",
    "Bitcoin": "BTC-USD",
    "DXY": "DX-Y.NYB",
}

SECTOR_ETFS = {
    "Technology": "XLK",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Cons. Discret.": "XLY",
    "Cons. Staples": "XLP",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Materials": "XLB",
    "Comm. Services": "XLC",
}

PERIOD_MAP = {
    "1D": ("1d", "5m"),
    "5D": ("5d", "15m"),
    "1M": ("1mo", "1h"),
    "3M": ("3mo", "1d"),
    "6M": ("6mo", "1d"),
    "YTD": ("ytd", "1d"),
    "1Y": ("1y", "1d"),
    "3Y": ("3y", "1wk"),
    "5Y": ("5y", "1wk"),
    "10Y": ("10y", "1mo"),
    "20Y": ("20y", "1mo"),
    "30Y": ("30y", "1mo"),
    "Max": ("max", "1mo"),
}


@st.cache_data(ttl=60)
def get_quote(ticker: str) -> dict:
    # NOTE: yfinance's `fast_info` segfaults on Python 3.13 (curl_cffi path),
    # so we read everything from `.info`, which is stable.
    try:
        full_info = yf.Ticker(ticker, session=_yf_session).info or {}
        prev_close = full_info.get("previousClose") or full_info.get("regularMarketPreviousClose")
        last_price = (
            full_info.get("currentPrice")
            or full_info.get("regularMarketPrice")
            or full_info.get("regularMarketPreviousClose")
        )
        # Fallback: quoteSummary (used by .info) needs a crumb cookie that can
        # fail on the very first request from a fresh session — the chart endpoint
        # (v8/finance/chart, same as yf.download) doesn't need one and is already
        # proven reliable.  Only triggered when .info returns no price.
        if not last_price:
            hist = yf.Ticker(ticker, session=_yf_session).history(
                period="5d", interval="1d", auto_adjust=True
            )
            if not hist.empty and "Close" in hist.columns:
                closes = hist["Close"].dropna()
                if len(closes) >= 1:
                    last_price = float(closes.iloc[-1])
                if not prev_close and len(closes) >= 2:
                    prev_close = float(closes.iloc[-2])
        change = (last_price - prev_close) if (last_price and prev_close) else None
        pct = (change / prev_close * 100) if (change is not None and prev_close) else None
        return {
            "ticker": ticker,
            "name": full_info.get("shortName") or full_info.get("longName") or ticker,
            "price": last_price,
            "prev_close": prev_close,
            "change": change,
            "pct_change": pct,
            "volume": full_info.get("volume") or full_info.get("regularMarketVolume"),
            "market_cap": full_info.get("marketCap"),
            "pe_ratio": full_info.get("trailingPE"),
            "beta": full_info.get("beta"),
            "sector": full_info.get("sector"),
            "industry": full_info.get("industry"),
            "fifty_two_week_high": full_info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": full_info.get("fiftyTwoWeekLow"),
        }
    except Exception:
        return {"ticker": ticker, "name": ticker, "price": None, "pct_change": None}


@st.cache_data(ttl=300)
def get_history(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    try:
        df = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False, session=_yf_session)
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_quotes_bulk(tickers: list) -> dict:
    results = {}
    for t in tickers:
        results[t] = get_quote(t)
    return results


@st.cache_data(ttl=300)
def get_history_bulk(tickers: list, period: str = "1y", interval: str = "1d") -> dict:
    results = {}
    for t in tickers:
        results[t] = get_history(t, period, interval)
    return results


@st.cache_data(ttl=300)
def get_stock_fundamentals(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker, session=_yf_session)
        info = t.info or {}
        return {
            "longName": info.get("longName") or info.get("shortName", ticker),
            "shortName": info.get("shortName", ticker),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "longBusinessSummary": info.get("longBusinessSummary"),
            "website": info.get("website"),
            "country": info.get("country"),
            "employees": info.get("fullTimeEmployees"),
            # Valuation
            "marketCap": info.get("marketCap"),
            "trailingPE": info.get("trailingPE"),
            "forwardPE": info.get("forwardPE"),
            "priceToBook": info.get("priceToBook"),
            "priceToSalesTrailing12Months": info.get("priceToSalesTrailing12Months"),
            "enterpriseToEbitda": info.get("enterpriseToEbitda"),
            "enterpriseToRevenue": info.get("enterpriseToRevenue"),
            "pegRatio": info.get("pegRatio"),
            # Profitability
            "profitMargins": info.get("profitMargins"),
            "grossMargins": info.get("grossMargins"),
            "operatingMargins": info.get("operatingMargins"),
            "returnOnEquity": info.get("returnOnEquity"),
            "returnOnAssets": info.get("returnOnAssets"),
            # Balance sheet
            "debtToEquity": info.get("debtToEquity"),
            "currentRatio": info.get("currentRatio"),
            "quickRatio": info.get("quickRatio"),
            "totalCash": info.get("totalCash"),
            "totalDebt": info.get("totalDebt"),
            # Growth
            "revenueGrowth": info.get("revenueGrowth"),
            "earningsGrowth": info.get("earningsGrowth"),
            "earningsQuarterlyGrowth": info.get("earningsQuarterlyGrowth"),
            # Income
            "totalRevenue": info.get("totalRevenue"),
            "ebitda": info.get("ebitda"),
            "freeCashflow": info.get("freeCashflow"),
            # Trading
            "beta": info.get("beta"),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
            "fiftyDayAverage": info.get("fiftyDayAverage"),
            "twoHundredDayAverage": info.get("twoHundredDayAverage"),
            "averageVolume": info.get("averageVolume"),
            "averageVolume10days": info.get("averageVolume10days"),
            "sharesOutstanding": info.get("sharesOutstanding"),
            "floatShares": info.get("floatShares"),
            "shortRatio": info.get("shortRatio"),
            "shortPercentOfFloat": info.get("shortPercentOfFloat"),
            # Dividends
            "dividendRate": info.get("dividendRate"),
            "dividendYield": info.get("dividendYield"),
            "payoutRatio": info.get("payoutRatio"),
            # Analyst
            "targetMeanPrice": info.get("targetMeanPrice"),
            "targetHighPrice": info.get("targetHighPrice"),
            "targetLowPrice": info.get("targetLowPrice"),
            "numberOfAnalystOpinions": info.get("numberOfAnalystOpinions"),
            "recommendationMean": info.get("recommendationMean"),
        }
    except Exception:
        return {}


@st.cache_data(ttl=300)
def get_etf_details(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker, session=_yf_session)
        info = t.info or {}
        holdings = []
        try:
            h = t.funds_data
            if h and hasattr(h, 'top_holdings') and h.top_holdings is not None:
                hdf = h.top_holdings
                if not hdf.empty:
                    for sym, row in hdf.iterrows():
                        holdings.append({
                            "symbol": sym,
                            "name": row.get("holdingName", sym),
                            "weight": row.get("holdingPercent", 0),
                        })
        except Exception:
            pass
        sector_weights = {}
        try:
            h = t.funds_data
            if h and hasattr(h, 'sector_weightings') and h.sector_weightings is not None:
                sw = h.sector_weightings
                if isinstance(sw, pd.DataFrame) and not sw.empty:
                    for _, row in sw.iterrows():
                        sector_weights[row.get("sector", "Other")] = row.get("weightPercentage", 0)
                elif isinstance(sw, dict):
                    sector_weights = sw
        except Exception:
            pass
        return {
            "longName": info.get("longName") or info.get("shortName", ticker),
            "shortName": info.get("shortName", ticker),
            "category": info.get("category"),
            "fundFamily": info.get("fundFamily"),
            "totalAssets": info.get("totalAssets"),
            "expenseRatio": info.get("annualReportExpenseRatio") or info.get("expenseRatio"),
            "beta3Year": info.get("beta3Year"),
            "ytdReturn": info.get("ytdReturn"),
            "threeYearAverageReturn": info.get("threeYearAverageReturn"),
            "fiveYearAverageReturn": info.get("fiveYearAverageReturn"),
            "holdings": holdings,
            "sector_weights": sector_weights,
        }
    except Exception:
        return {}


@st.cache_data(ttl=300)
def is_etf(ticker: str) -> bool:
    try:
        t = yf.Ticker(ticker, session=_yf_session)
        info = t.info or {}
        qt = info.get("quoteType", "")
        return qt in ("ETF", "MUTUALFUND")
    except Exception:
        return False


def get_prev_close(ticker: str) -> float | None:
    q = get_quote(ticker)
    return q.get("prev_close")
