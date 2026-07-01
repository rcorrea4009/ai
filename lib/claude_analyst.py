import os
import streamlit as st

_DISCLAIMER = (
    "Note: This is an AI-generated educational analysis for informational purposes only. "
    "It is not financial advice and should not be used to make investment decisions."
)


def _get_client():
    try:
        import anthropic
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            return None
        return anthropic.Anthropic(api_key=key)
    except ImportError:
        return None


def _call(prompt: str, system: str = "", max_tokens: int = 1024,
          model: str = "claude-sonnet-4-6") -> str:
    client = _get_client()
    if client is None:
        return "⚠️ Anthropic API key not configured. Add ANTHROPIC_API_KEY to your .env file to enable AI analysis."
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system or (
                "You are a financial educator providing balanced, factual market analysis. "
                "You never give buy/sell/hold recommendations. You present both positive and negative factors objectively. "
                "Always remind users that this is educational content only, not financial advice."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text + f"\n\n---\n*{_DISCLAIMER}*"
    except Exception as e:
        return f"⚠️ Error calling Claude API: {e}"


def ai_verdict(
    ticker: str,
    fundamentals: dict,
    tech_details: dict,
    kronos_interp: dict | None,
    signal_scores: dict,
    combined: float,
) -> str:
    """
    Flagship 'AI Stock Verdict' — Claude synthesises the Kronos forecast and every
    cross-reference signal into one cohesive educational read on the stock.

    Returns a markdown string. Uses the most capable model (claude-opus-4-8).
    """
    name = fundamentals.get("longName", ticker)
    sector = fundamentals.get("sector", "—")
    pe = fundamentals.get("trailingPE")
    roe = fundamentals.get("returnOnEquity")
    margin = fundamentals.get("profitMargins")
    rev_growth = fundamentals.get("revenueGrowth")

    if kronos_interp:
        kronos_line = (
            f"Kronos AI forecast: {kronos_interp['direction']} "
            f"({kronos_interp['pct_change']:+.2f}% predicted over the horizon; "
            f"current ${kronos_interp['current_close']:,.2f} → "
            f"predicted ${kronos_interp['pred_close_end']:,.2f}; "
            f"direction score {kronos_interp['direction_score']:.0f}/100)"
        )
    else:
        kronos_line = "Kronos AI forecast: unavailable this run"

    signals_block = "\n".join(f"- {n}: {s:.0f}/100" for n, s in signal_scores.items())

    context = (
        f"Company: {name} ({ticker}) · Sector: {sector}\n"
        f"Fundamentals — P/E: {pe}, ROE: {roe}, Net Margin: {margin}, Revenue Growth: {rev_growth}\n"
        f"Technical — RSI {tech_details.get('rsi', '—')}, {tech_details.get('vs_200dma', '—')}\n"
        f"{kronos_line}\n"
        f"Combined weighted model score: {combined:.0f}/100\n"
        f"Individual cross-reference signals (0-100, higher = more favourable):\n{signals_block}"
    )

    system = (
        "You are a financial educator writing a concise 'AI market read' for a stock dashboard. "
        "You synthesise quantitative signals into a clear, balanced narrative. "
        "You NEVER give buy/sell/hold recommendations or price targets. "
        "You explain what the data shows and what a careful researcher would watch, objectively. "
        "Always present both supporting and opposing factors."
    )

    prompt = (
        f"Write an educational 'AI Stock Verdict' for {name} ({ticker}) based ONLY on the data below. "
        f"Structure it in markdown exactly as:\n\n"
        f"**Stance:** one short sentence describing the overall tilt of the combined signals "
        f"(e.g. 'Signals lean cautiously constructive') — NOT advice.\n\n"
        f"**What the data shows:** 3-4 bullets connecting the Kronos forecast, technicals, and fundamentals.\n\n"
        f"**Key risks / counterpoints:** 2-3 bullets on what argues against the prevailing signal.\n\n"
        f"**What to watch:** 2-3 concrete, observable things a researcher could monitor next.\n\n"
        f"Be specific to the numbers. Keep it tight.\n\nData:\n{context}"
    )

    return _call(prompt, system=system, max_tokens=1100, model="claude-opus-4-8")


def bull_bear_case(ticker: str, fundamentals: dict, tech_details: dict) -> tuple[str, str]:
    """Return (bull_case, bear_case) as markdown strings."""
    name = fundamentals.get("longName", ticker)
    pe = fundamentals.get("trailingPE")
    roe = fundamentals.get("returnOnEquity")
    margin = fundamentals.get("profitMargins")
    de = fundamentals.get("debtToEquity")
    rev_growth = fundamentals.get("revenueGrowth")
    sector = fundamentals.get("sector", "")
    summary = (fundamentals.get("longBusinessSummary") or "")[:500]
    rsi = tech_details.get("rsi")
    vs_200 = tech_details.get("vs_200dma")

    context = (
        f"Company: {name} ({ticker}), Sector: {sector}\n"
        f"P/E: {pe}, ROE: {roe}, Net Margin: {margin}, D/E: {de}, "
        f"Revenue Growth: {rev_growth}\n"
        f"Technical: {vs_200}, RSI {rsi}\n"
        f"Business: {summary}"
    )

    bull = _call(
        f"Based on the following data, identify 3-4 potential bull case factors for {name} ({ticker}). "
        f"Be factual and balanced. Do NOT recommend buying. Focus on business strengths, market position, "
        f"and growth opportunities visible in the data.\n\nData:\n{context}",
        max_tokens=512,
    )
    bear = _call(
        f"Based on the following data, identify 3-4 potential risk factors or bear case considerations for "
        f"{name} ({ticker}). Be factual and balanced. Do NOT recommend selling. Focus on risks, "
        f"competitive challenges, and financial concerns visible in the data.\n\nData:\n{context}",
        max_tokens=512,
    )
    return bull, bear


def deep_analysis(ticker: str, fundamentals: dict, tech_details: dict) -> str:
    name = fundamentals.get("longName", ticker)
    pe = fundamentals.get("trailingPE")
    roe = fundamentals.get("returnOnEquity")
    margin = fundamentals.get("profitMargins")
    de = fundamentals.get("debtToEquity")
    rev_growth = fundamentals.get("revenueGrowth")
    beta = fundamentals.get("beta")
    sector = fundamentals.get("sector", "")
    summary = (fundamentals.get("longBusinessSummary") or "")[:600]

    context = (
        f"Company: {name} ({ticker})\nSector: {sector}\n"
        f"P/E: {pe}, ROE: {roe}, Net Margin: {margin}, D/E: {de}, "
        f"Revenue Growth: {rev_growth}, Beta: {beta}\n"
        f"Business: {summary}"
    )

    return _call(
        f"Provide a comprehensive educational overview of {name} ({ticker}) covering: "
        f"1) Business model and competitive position, 2) Financial health observations, "
        f"3) Key risks and uncertainties, 4) Industry context. "
        f"Be educational and factual. Do not give investment recommendations.\n\nData:\n{context}",
        max_tokens=1200,
    )


def macro_pulse(macro_data: dict) -> str:
    lines = []
    for sid, series in macro_data.items():
        if hasattr(series, "iloc") and not series.empty:
            prev = f"{series.iloc[-2]:.2f}" if len(series) > 1 else "N/A"
            lines.append(f"{sid}: latest={series.iloc[-1]:.2f}, prev={prev}")
    context = "\n".join(lines[:10])

    return _call(
        f"Based on the following macroeconomic indicators from FRED, provide an educational "
        f"summary of the current economic environment. Describe what the data shows factually. "
        f"Do not give investment or policy recommendations.\n\nData:\n{context}",
        max_tokens=800,
    )


def portfolio_analysis(holdings_df, total_value: float) -> str:
    if holdings_df is None or holdings_df.empty:
        return "No portfolio data to analyze."
    rows = []
    for _, row in holdings_df.iterrows():
        rows.append(
            f"{row.get('Ticker','?')}: {row.get('Shares',0):.0f} shares, "
            f"cost basis ${row.get('Cost Basis',0):.2f}, "
            f"current ${row.get('Price',0):.2f}, "
            f"gain {row.get('Gain %',0):.1f}%"
        )
    context = "\n".join(rows)

    return _call(
        f"Based on the following portfolio data (total value ~${total_value:,.0f}), provide an "
        f"educational analysis covering: 1) Diversification observations, 2) Concentration risks, "
        f"3) Sector exposure, 4) Performance factors visible in the data. "
        f"Do not give buy/sell recommendations.\n\nPortfolio:\n{context}",
        max_tokens=900,
    )
