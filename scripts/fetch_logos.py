"""
Download logos for top US tickers into assets/logos/<TICKER>.<ext>.
Sources tried in order:
  1. simple-icons via jsdelivr CDN (SVG, dark-mode patched)
  2. vectorlogo.zone
  3. Apple touch icon from company domain
  4. Google faviconV2 (256px)
  5. DuckDuckGo icon
"""
import os
import re
import sys
import time
import requests
from pathlib import Path

LOGO_DIR = Path(__file__).parent.parent / "assets" / "logos"
LOGO_DIR.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (logo-fetcher/1.0)"})

TICKERS = [
    # Mega cap tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO",
    # Finance
    "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "AXP", "BLK", "SCHW",
    # Healthcare
    "UNH", "JNJ", "LLY", "ABBV", "MRK", "PFE", "ABT", "TMO", "DHR", "AMGN",
    "GILD", "REGN", "VRTX", "BIIB", "MRNA", "BMY", "CVS", "CI", "HUM",
    # Consumer
    "WMT", "HD", "MCD", "NKE", "COST", "TGT", "SBUX", "CMG", "DIS", "NFLX",
    "KO", "PEP", "PG", "PM", "MO", "CL", "EL",
    # Energy
    "XOM", "CVX", "COP", "SLB", "EOG", "PXD", "MPC", "VLO",
    # Industrials
    "GE", "HON", "CAT", "DE", "BA", "RTX", "LMT", "NOC", "GD", "UPS", "FDX",
    # Tech
    "CRM", "ADBE", "ORCL", "IBM", "INTC", "AMD", "QCOM", "TXN", "AMAT",
    "LRCX", "KLAC", "MU", "NXPI", "MRVL", "ON", "SMCI",
    "NOW", "PANW", "CRWD", "SNOW", "NET", "DDOG", "PLTR", "OKTA", "ZS",
    "FTNT", "S", "UBER", "LYFT", "ABNB", "DASH", "SHOP", "PYPL", "SQ",
    "COIN", "RBLX", "SPOT", "ZM", "DOCU", "TWLO", "PATH", "MDB",
    # Telecom/Media
    "VZ", "T", "TMUS", "CMCSA", "DIS", "CHTR",
    # Auto
    "F", "GM", "TSLA",
    # REITs / Utilities
    "AMT", "CCI", "EQIX", "NEE", "DUK", "SO",
    # ETFs
    "SPY", "QQQ", "IWM", "VOO", "VTI", "GLD", "IAU", "TLT", "AGG", "BND",
    "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLRE", "XLB", "XLC",
    "VEA", "VWO", "HYG", "QQQM",
]

DOMAIN_MAP = {
    "AAPL": "apple.com", "MSFT": "microsoft.com", "GOOGL": "google.com",
    "GOOG": "google.com", "AMZN": "amazon.com", "NVDA": "nvidia.com",
    "META": "meta.com", "TSLA": "tesla.com", "AVGO": "broadcom.com",
    "LLY": "lilly.com", "JPM": "jpmorganchase.com", "V": "visa.com",
    "UNH": "unitedhealthgroup.com", "XOM": "exxonmobil.com", "WMT": "walmart.com",
    "MA": "mastercard.com", "PG": "pg.com", "COST": "costco.com",
    "HD": "homedepot.com", "JNJ": "jnj.com", "MRK": "merck.com",
    "ABBV": "abbvie.com", "CVX": "chevron.com", "BAC": "bankofamerica.com",
    "CRM": "salesforce.com", "AMD": "amd.com", "NFLX": "netflix.com",
    "ADBE": "adobe.com", "ORCL": "oracle.com", "KO": "coca-cola.com",
    "PEP": "pepsico.com", "CSCO": "cisco.com", "TMO": "thermofisher.com",
    "MCD": "mcdonalds.com", "ACN": "accenture.com", "ABT": "abbott.com",
    "DHR": "danaher.com", "INTC": "intel.com", "TXN": "ti.com",
    "QCOM": "qualcomm.com", "VZ": "verizon.com", "WFC": "wellsfargo.com",
    "MS": "morganstanley.com", "GS": "goldmansachs.com", "IBM": "ibm.com",
    "NOW": "servicenow.com", "AMAT": "appliedmaterials.com",
    "LRCX": "lamresearch.com", "KLAC": "kla.com", "MRVL": "marvell.com",
    "PANW": "paloaltonetworks.com", "CRWD": "crowdstrike.com",
    "SNOW": "snowflake.com", "UBER": "uber.com", "LYFT": "lyft.com",
    "ABNB": "airbnb.com", "DASH": "doordash.com", "SHOP": "shopify.com",
    "SQ": "block.xyz", "PYPL": "paypal.com", "COIN": "coinbase.com",
    "RBLX": "roblox.com", "SPOT": "spotify.com", "TWLO": "twilio.com",
    "ZM": "zoom.us", "DOCU": "docusign.com", "OKTA": "okta.com",
    "DDOG": "datadoghq.com", "NET": "cloudflare.com", "MDB": "mongodb.com",
    "PATH": "uipath.com", "PLTR": "palantir.com", "S": "sentinelone.com",
    "ZS": "zscaler.com", "FTNT": "fortinet.com", "DIS": "disney.com",
    "CMCSA": "comcast.com", "T": "att.com", "TMUS": "t-mobile.com",
    "MU": "micron.com", "SMCI": "supermicro.com", "GE": "ge.com",
    "HON": "honeywell.com", "CAT": "caterpillar.com", "DE": "deere.com",
    "BA": "boeing.com", "RTX": "rtx.com", "LMT": "lockheedmartin.com",
    "NOC": "northropgrumman.com", "GD": "gd.com", "UPS": "ups.com",
    "FDX": "fedex.com", "F": "ford.com", "GM": "gm.com",
    "CVS": "cvshealth.com", "CI": "cigna.com", "HUM": "humana.com",
    "AMGN": "amgen.com", "GILD": "gilead.com", "REGN": "regeneron.com",
    "VRTX": "vrtx.com", "BIIB": "biogen.com", "MRNA": "modernatx.com",
    "PFE": "pfizer.com", "BMY": "bms.com", "NKE": "nike.com",
    "SBUX": "starbucks.com", "MO": "altria.com", "PM": "pmi.com",
    "CL": "colgate.com", "TGT": "target.com", "CMG": "chipotle.com",
    "NEE": "nexteraenergy.com", "AMT": "americantower.com",
    "EQIX": "equinix.com", "COP": "conocophillips.com", "SLB": "slb.com",
    "EOG": "eogresources.com", "MPC": "marathonpetroleum.com",
    "VLO": "valero.com", "AXP": "americanexpress.com", "BLK": "blackrock.com",
    "SCHW": "schwab.com", "WBA": "walgreens.com",
}

# simple-icons slug overrides (when ticker ≠ brand slug)
SIMPLE_ICONS_SLUGS = {
    "AAPL": "apple", "MSFT": "microsoft", "GOOGL": "google", "AMZN": "amazon",
    "NVDA": "nvidia", "META": "meta", "TSLA": "tesla", "JPM": "jpmorgan",
    "V": "visa", "MA": "mastercard", "KO": "cocacola", "PEP": "pepsi",
    "MCD": "mcdonalds", "NFLX": "netflix", "ADBE": "adobe", "ORCL": "oracle",
    "IBM": "ibm", "INTC": "intel", "AMD": "amd", "QCOM": "qualcomm",
    "VZ": "verizon", "T": "att", "TMUS": "tmobile", "DIS": "disney",
    "SBUX": "starbucks", "NKE": "nike", "PYPL": "paypal", "SQ": "square",
    "COIN": "coinbase", "SHOP": "shopify", "RBLX": "roblox", "SPOT": "spotify",
    "TWLO": "twilio", "ZM": "zoom", "DOCU": "docusign", "OKTA": "okta",
    "SNOW": "snowflake", "UBER": "uber", "LYFT": "lyft", "ABNB": "airbnb",
    "PANW": "paloaltonetworks", "CRWD": "crowdstrike", "NET": "cloudflare",
    "DDOG": "datadog", "PLTR": "palantir", "MDB": "mongodb",
    "GE": "generalelectric", "HON": "honeywell", "BA": "boeing",
    "F": "ford", "GM": "generalmotors", "FDX": "fedex", "UPS": "ups",
    "AMGN": "amgen", "GILD": "gilead", "PFE": "pfizer",
    "BLK": "blackrock", "GS": "goldmansachs", "MS": "morganstanley",
    "BAC": "bankofamerica", "WFC": "wellsfargo",
}


def _patch_svg_for_dark(svg: bytes) -> bytes:
    text = svg.decode("utf-8", errors="replace")
    text = re.sub(r'fill\s*=\s*"#?[0-9a-fA-F]{3,6}"', 'fill="#ffffff"', text)
    text = re.sub(r"fill\s*:\s*#?[0-9a-fA-F]{3,6}", "fill:#ffffff", text)
    if "fill" not in text:
        text = text.replace("<svg", '<svg fill="#ffffff"', 1)
    return text.encode("utf-8")


def _get(url: str, timeout: int = 6) -> requests.Response | None:
    try:
        r = SESSION.get(url, timeout=timeout, allow_redirects=True)
        if r.ok and len(r.content) > 200:
            return r
    except Exception:
        pass
    return None


def _try_simple_icons(ticker: str) -> bytes | None:
    slug = SIMPLE_ICONS_SLUGS.get(ticker, ticker.lower())
    url = f"https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/{slug}.svg"
    r = _get(url)
    if r:
        return _patch_svg_for_dark(r.content)
    return None


def _try_vectorlogo(ticker: str) -> bytes | None:
    slug = ticker.lower()
    url = f"https://www.vectorlogo.zone/logos/{slug}/{slug}-icon.svg"
    r = _get(url)
    return r.content if r else None


def _try_apple_touch(domain: str) -> bytes | None:
    for path in ("/apple-touch-icon.png", "/apple-touch-icon-precomposed.png"):
        r = _get(f"https://{domain}{path}")
        if r and "image" in r.headers.get("content-type", ""):
            return r.content
    return None


def _try_google_favicon(domain: str) -> bytes | None:
    url = f"https://www.google.com/s2/favicons?domain={domain}&sz=256"
    r = _get(url)
    if r and "image" in r.headers.get("content-type", ""):
        return r.content
    return None


def _try_duckduckgo(domain: str) -> bytes | None:
    url = f"https://icons.duckduckgo.com/ip3/{domain}.ico"
    r = _get(url)
    if r:
        return r.content
    return None


def fetch_logo(ticker: str) -> bool:
    safe_ticker = ticker.replace(".", "_")
    # Skip if already downloaded
    for ext in ("svg", "png", "jpg", "ico"):
        if (LOGO_DIR / f"{safe_ticker}.{ext}").exists():
            return True

    domain = DOMAIN_MAP.get(ticker)
    data, ext = None, "svg"

    # 1. simple-icons
    data = _try_simple_icons(ticker)
    if data:
        ext = "svg"

    # 2. vectorlogo.zone
    if not data and domain:
        data = _try_vectorlogo(ticker)
        if data:
            ext = "svg"

    # 3. apple-touch-icon
    if not data and domain:
        data = _try_apple_touch(domain)
        if data:
            ext = "png"

    # 4. Google faviconV2
    if not data and domain:
        data = _try_google_favicon(domain)
        if data:
            ext = "png"

    # 5. DuckDuckGo
    if not data and domain:
        data = _try_duckduckgo(domain)
        if data:
            ext = "ico"

    if data:
        out = LOGO_DIR / f"{safe_ticker}.{ext}"
        out.write_bytes(data)
        return True
    return False


if __name__ == "__main__":
    tickers = list(dict.fromkeys(TICKERS))
    print(f"Fetching logos for {len(tickers)} tickers into {LOGO_DIR}")
    ok = fail = 0
    for i, t in enumerate(tickers):
        result = fetch_logo(t)
        status = "✓" if result else "✗"
        print(f"  [{i+1:3d}/{len(tickers)}] {status} {t}")
        if result:
            ok += 1
        else:
            fail += 1
        time.sleep(0.15)
    print(f"\nDone: {ok} fetched, {fail} not found.")
