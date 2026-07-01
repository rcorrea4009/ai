# Curated peer groups for ETF cost comparison
ETF_PEERS = {
    # US Broad Market
    "SPY": ["IVV", "VOO", "SPLG", "SCHB"],
    "IVV": ["SPY", "VOO", "SPLG"],
    "VOO": ["SPY", "IVV", "SPLG"],
    "QQQ": ["QQQM", "ONEQ", "IWY"],
    "QQQM": ["QQQ", "ONEQ"],
    "IWM": ["VB", "SCHA", "IJR"],
    "VTI": ["ITOT", "SCHB", "FSKAX"],
    # International
    "VEA": ["IEFA", "SCHF", "EFA"],
    "VWO": ["IEMG", "EEM", "SCHE"],
    # Fixed income
    "AGG": ["BND", "IUSB", "SCHZ"],
    "BND": ["AGG", "IUSB", "SCHZ"],
    "TLT": ["SPTL", "VGLT", "IEF"],
    "HYG": ["JNK", "USHY", "FALN"],
    # Sector ETFs
    "XLK": ["VGT", "FTEC", "IYW"],
    "XLF": ["VFH", "FNCL", "IYF"],
    "XLV": ["VHT", "FHLC", "IYH"],
    "XLE": ["VDE", "FENY", "IYE"],
    "XLI": ["VIS", "FIDU", "IYJ"],
    "XLY": ["VCR", "FDIS", "IYC"],
    "XLP": ["VDC", "FSTA", "IYK"],
    "XLU": ["VPU", "FUTY", "IDU"],
    "XLRE": ["VNQ", "FREL", "IYR"],
    "XLB": ["VAW", "FMAT", "IYM"],
    "XLC": ["VOX", "FCOM", "IYZ"],
    # Commodities / alternatives
    "GLD": ["IAU", "GLDM", "SGOL"],
    "IAU": ["GLD", "GLDM", "SGOL"],
    "USO": ["UCO", "BNO", "OIL"],
    # Leveraged / inverse (shown as context only)
    "TQQQ": ["QLD", "QQQ"],
    "SQQQ": ["PSQ", "QQQ"],
}


def get_peers(ticker: str) -> list[str]:
    return ETF_PEERS.get(ticker.upper(), [])
