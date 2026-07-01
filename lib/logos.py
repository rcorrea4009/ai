import base64
import os
from pathlib import Path

LOGO_DIR = Path(__file__).parent.parent / "assets" / "logos"

# Ticker → company domain for logo fetching
TICKER_DOMAINS = {
    "AAPL": "apple.com", "MSFT": "microsoft.com", "GOOGL": "google.com",
    "GOOG": "google.com", "AMZN": "amazon.com", "NVDA": "nvidia.com",
    "META": "meta.com", "TSLA": "tesla.com", "BRK.B": "berkshirehathaway.com",
    "BRK.A": "berkshirehathaway.com", "AVGO": "broadcom.com", "LLY": "lilly.com",
    "JPM": "jpmorganchase.com", "V": "visa.com", "UNH": "unitedhealthgroup.com",
    "XOM": "exxonmobil.com", "WMT": "walmart.com", "MA": "mastercard.com",
    "PG": "pg.com", "COST": "costco.com", "HD": "homedepot.com",
    "JNJ": "jnj.com", "MRK": "merck.com", "ABBV": "abbvie.com",
    "CVX": "chevron.com", "BAC": "bankofamerica.com", "CRM": "salesforce.com",
    "AMD": "amd.com", "NFLX": "netflix.com", "ADBE": "adobe.com",
    "ORCL": "oracle.com", "KO": "coca-cola.com", "PEP": "pepsico.com",
    "CSCO": "cisco.com", "TMO": "thermofisher.com", "MCD": "mcdonalds.com",
    "ACN": "accenture.com", "ABT": "abbott.com", "DHR": "danaher.com",
    "INTC": "intel.com", "TXN": "ti.com", "QCOM": "qualcomm.com",
    "VZ": "verizon.com", "WFC": "wellsfargo.com", "MS": "morganstanley.com",
    "GS": "goldmansachs.com", "IBM": "ibm.com", "NOW": "servicenow.com",
    "AMAT": "appliedmaterials.com", "LRCX": "lamresearch.com",
    "KLAC": "kla.com", "MRVL": "marvell.com", "PANW": "paloaltonetworks.com",
    "CRWD": "crowdstrike.com", "SNOW": "snowflake.com", "UBER": "uber.com",
    "LYFT": "lyft.com", "ABNB": "airbnb.com", "DASH": "doordash.com",
    "SHOP": "shopify.com", "SQ": "block.xyz", "PYPL": "paypal.com",
    "COIN": "coinbase.com", "RBLX": "roblox.com", "SPOT": "spotify.com",
    "TWLO": "twilio.com", "ZM": "zoom.us", "DOCU": "docusign.com",
    "OKTA": "okta.com", "DDOG": "datadoghq.com", "NET": "cloudflare.com",
    "GTLB": "gitlab.com", "HCP": "hashicorp.com", "MDB": "mongodb.com",
    "ESTC": "elastic.co", "CFLT": "confluent.io", "PATH": "uipath.com",
    "AI": "c3.ai", "PLTR": "palantir.com", "S": "sentinelone.com",
    "ZS": "zscaler.com", "FTNT": "fortinet.com", "CHKP": "checkpoint.com",
    "DIS": "disney.com", "CMCSA": "comcast.com", "T": "att.com",
    "TMUS": "t-mobile.com", "CHTR": "charter.com", "NXPI": "nxp.com",
    "ON": "onsemi.com", "STM": "st.com", "MU": "micron.com",
    "WDC": "westerndigital.com", "SMCI": "supermicro.com",
    "GE": "ge.com", "HON": "honeywell.com", "CAT": "caterpillar.com",
    "DE": "deere.com", "BA": "boeing.com", "RTX": "rtx.com",
    "LMT": "lockheedmartin.com", "NOC": "northropgrumman.com",
    "GD": "gd.com", "UPS": "ups.com", "FDX": "fedex.com",
    "DAL": "delta.com", "UAL": "united.com", "AAL": "aa.com",
    "F": "ford.com", "GM": "gm.com", "STLA": "stellantis.com",
    "CVS": "cvshealth.com", "CI": "cigna.com", "HUM": "humana.com",
    "AMGN": "amgen.com", "GILD": "gilead.com", "REGN": "regeneron.com",
    "VRTX": "vrtx.com", "BIIB": "biogen.com", "MRNA": "modernatx.com",
    "PFE": "pfizer.com", "BMY": "bms.com",
    "GLD": "spdrgoldshares.com", "IAU": "ishares.com",
    "SPY": "ssga.com", "QQQ": "invesco.com", "IWM": "ishares.com",
    "DIA": "ssga.com", "VOO": "vanguard.com", "VTI": "vanguard.com",
    "VEA": "vanguard.com", "VWO": "vanguard.com", "AGG": "ishares.com",
    "BND": "vanguard.com", "TLT": "ishares.com", "HYG": "ishares.com",
    "XLK": "ssga.com", "XLF": "ssga.com", "XLV": "ssga.com",
    "XLE": "ssga.com", "XLI": "ssga.com", "XLY": "ssga.com",
    "XLP": "ssga.com", "XLU": "ssga.com", "XLRE": "ssga.com",
    "XLB": "ssga.com", "XLC": "ssga.com",
}


def get_logo_path(ticker: str) -> Path | None:
    """Return the local logo path for a ticker, or None if not found."""
    ticker = ticker.upper().replace(".", "_")
    for ext in ("svg", "png", "jpg", "ico"):
        p = LOGO_DIR / f"{ticker}.{ext}"
        if p.exists():
            return p
    return None


def logo_data_url(ticker: str, fallback: str = "") -> str:
    """
    Return a base64 data URL for the ticker logo.
    Falls back to fallback string (e.g. empty or a placeholder).
    """
    path = get_logo_path(ticker)
    if path is None:
        return fallback
    try:
        data = path.read_bytes()
        ext = path.suffix.lstrip(".")
        mime = "image/svg+xml" if ext == "svg" else f"image/{ext}"
        b64 = base64.b64encode(data).decode()
        return f"data:{mime};base64,{b64}"
    except Exception:
        return fallback


def logo_img_tag(ticker: str, size: int = 32) -> str:
    """Return an <img> HTML tag for the ticker logo, or a text fallback."""
    url = logo_data_url(ticker)
    if url:
        return (
            f'<img src="{url}" width="{size}" height="{size}" '
            f'style="object-fit:contain;border-radius:4px;background:#1e1e1e;" '
            f'alt="{ticker}">'
        )
    return (
        f'<span style="display:inline-flex;align-items:center;justify-content:center;'
        f'width:{size}px;height:{size}px;background:#333;border-radius:4px;'
        f'font-size:{size//3}px;color:#fff;">{ticker[:3]}</span>'
    )
