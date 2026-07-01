import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_TEMPLATE = "plotly_dark"
_GREEN = "#26a69a"
_RED = "#ef5350"
_GOLD = "#ffd700"
_BLUE = "#5c9eff"


def _interpolate_zero_crossings(x_vals, y_vals):
    """Return (x, y) lists with linearly-interpolated zero crossings inserted."""
    xs, ys = list(x_vals), list(y_vals)
    out_x, out_y = [], []
    for i in range(len(xs)):
        if i > 0 and ys[i - 1] is not None and ys[i] is not None:
            if (ys[i - 1] < 0 < ys[i]) or (ys[i - 1] > 0 > ys[i]):
                frac = abs(ys[i - 1]) / (abs(ys[i - 1]) + abs(ys[i]))
                if isinstance(xs[i - 1], pd.Timestamp):
                    delta = xs[i] - xs[i - 1]
                    mid_x = xs[i - 1] + delta * frac
                else:
                    mid_x = xs[i - 1] + (xs[i] - xs[i - 1]) * frac
                out_x.append(mid_x)
                out_y.append(0.0)
        out_x.append(xs[i])
        out_y.append(ys[i])
    return out_x, out_y


def split_traces(x_vals, y_vals, color_above=_GREEN, color_below=_RED, name="", fill=False, baseline=0.0):
    """
    Split a series into green (above baseline) and red (below baseline) segments
    with zero-crossing interpolation. Returns a list of go.Scatter traces.
    """
    x_interp, y_interp = _interpolate_zero_crossings(x_vals, [v - baseline if v is not None else None for v in y_vals])
    y_shifted = [v + baseline if v is not None else None for v in y_interp]

    traces = []
    seg_x, seg_y, color = [], [], None

    def flush():
        if seg_x:
            fill_type = "tozeroy" if fill else "none"
            traces.append(go.Scatter(
                x=seg_x[:],
                y=seg_y[:],
                mode="lines",
                line=dict(color=color, width=2),
                fill=fill_type if fill else "none",
                fillcolor=color.replace(")", ", 0.15)").replace("rgb", "rgba") if fill else None,
                name=name,
                showlegend=len(traces) == 0,
                hovertemplate="%{y:.2f}<extra></extra>",
            ))

    for xi, yi, yr in zip(x_interp, y_shifted, y_interp):
        c = color_above if (yr is not None and yr >= 0) else color_below
        if c != color and seg_x:
            seg_x.append(xi)
            seg_y.append(yi)
            flush()
            seg_x, seg_y = [xi], [yi]
        else:
            seg_x.append(xi)
            seg_y.append(yi)
        color = c

    flush()
    return traces


def render_price_chart(
    df: pd.DataFrame,
    ticker: str = "",
    view: str = "Performance",
    show_volume: bool = True,
    baseline_price: float = None,
    height: int = 500,
) -> go.Figure:
    """
    Render a price chart with 4 views: Performance, Price, Candlestick, Area.

    baseline_price: for 1D intraday, pass yesterday's close so the performance
                    baseline is correct (not today's first bar).
    """
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(template=_TEMPLATE, title="No data available")
        return fig

    close_col = "Close" if "Close" in df.columns else df.columns[0]
    close = df[close_col].dropna()
    if close.empty:
        fig = go.Figure()
        fig.update_layout(template=_TEMPLATE, title="No data")
        return fig

    x = close.index
    y = close.values

    start_price = baseline_price if baseline_price is not None else float(y[0])
    end_price = float(y[-1])
    total_return = (end_price - start_price) / start_price * 100
    badge_color = _GREEN if total_return >= 0 else _RED
    badge_text = f"{total_return:+.2f}%"

    rows = 2 if (show_volume and "Volume" in df.columns) else 1
    row_heights = [0.75, 0.25] if rows == 2 else [1.0]
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=row_heights)

    if view == "Performance":
        pct_vals = [(float(v) - start_price) / start_price * 100 for v in y]
        for trace in split_traces(list(x), pct_vals, name=ticker):
            fig.add_trace(trace, row=1, col=1)
        fig.update_yaxes(title_text="Return %", ticksuffix="%", row=1, col=1)

    elif view == "Price":
        color = _GREEN if total_return >= 0 else _RED
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines", line=dict(color=color, width=2),
            name=ticker, hovertemplate="%{y:.2f}<extra></extra>"
        ), row=1, col=1)
        if baseline_price is not None:
            fig.add_hline(y=baseline_price, line_dash="dot", line_color="rgba(255,255,255,0.3)", row=1, col=1)
        fig.update_yaxes(title_text="Price", row=1, col=1)

    elif view == "Candlestick":
        needed = ["Open", "High", "Low", "Close"]
        if all(c in df.columns for c in needed):
            fig.add_trace(go.Candlestick(
                x=df.index,
                open=df["Open"], high=df["High"],
                low=df["Low"], close=df["Close"],
                name=ticker,
                increasing_line_color=_GREEN,
                decreasing_line_color=_RED,
            ), row=1, col=1)
        else:
            for trace in split_traces(list(x), list(y), name=ticker):
                fig.add_trace(trace, row=1, col=1)
        fig.update_yaxes(title_text="Price", row=1, col=1)

    elif view == "Area":
        for trace in split_traces(list(x), list(y), fill=True, baseline=start_price, name=ticker):
            fig.add_trace(trace, row=1, col=1)
        fig.add_hline(y=start_price, line_dash="dot", line_color="rgba(255,255,255,0.3)", row=1, col=1)
        fig.update_yaxes(title_text="Price", row=1, col=1)

    # Return badge annotation
    fig.add_annotation(
        x=x[-1], y=y[-1] if view in ("Price", "Candlestick", "Area") else (end_price - start_price) / start_price * 100,
        text=f"  {badge_text}",
        showarrow=False,
        font=dict(color=badge_color, size=14, family="monospace"),
        xanchor="left",
        row=1, col=1,
    )

    # Volume
    if rows == 2 and "Volume" in df.columns:
        vol = df["Volume"].fillna(0)
        vol_colors = []
        closes = df[close_col].values
        for i in range(len(closes)):
            if i == 0:
                vol_colors.append(_GREEN)
            else:
                vol_colors.append(_GREEN if closes[i] >= closes[i - 1] else _RED)
        fig.add_trace(go.Bar(
            x=df.index, y=vol,
            marker_color=vol_colors,
            name="Volume", showlegend=False,
            hovertemplate="%{y:,.0f}<extra></extra>",
        ), row=2, col=1)
        fig.update_yaxes(title_text="Vol", row=2, col=1)

    fig.update_layout(
        template=_TEMPLATE,
        height=height,
        margin=dict(l=10, r=60, t=10, b=10),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.02),
        hovermode="x unified",
    )
    return fig


def render_sparkline(x_vals, y_vals, baseline_price=None, height=60, width=120) -> go.Figure:
    """Tiny sparkline for index cards."""
    start = baseline_price if baseline_price is not None else (float(y_vals[0]) if y_vals else 0)
    pct = [(float(v) - start) / start * 100 if v is not None else None for v in y_vals]
    fig = go.Figure()
    for trace in split_traces(list(x_vals), pct):
        trace.update(showlegend=False, hoverinfo="skip")
        fig.add_trace(trace)
    fig.update_layout(
        template=_TEMPLATE,
        height=height,
        width=width,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def render_gauge(score: float, title: str, subtitle: str = "") -> go.Figure:
    """0-100 gauge with red→yellow→green band, needle, score number."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": f"<b>{title}</b><br><span style='font-size:0.7em;color:gray'>{subtitle}</span>",
               "font": {"size": 14}},
        number={"font": {"size": 28}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "white"},
            "bar": {"color": "white", "thickness": 0.05},
            "bgcolor": "rgba(0,0,0,0)",
            "steps": [
                {"range": [0, 33], "color": "#c62828"},
                {"range": [33, 66], "color": "#f9a825"},
                {"range": [66, 100], "color": "#2e7d32"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 3},
                "thickness": 0.85,
                "value": score,
            },
        },
    ))
    fig.update_layout(
        template=_TEMPLATE,
        height=220,
        margin=dict(l=20, r=20, t=50, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig
