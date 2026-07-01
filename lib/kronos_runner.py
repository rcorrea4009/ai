import os
import sys
import pandas as pd
import streamlit as st


def _add_repo_root():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)


@st.cache_resource(show_spinner="Loading Kronos model weights…")
def get_kronos_predictor():
    """
    Load Kronos-small from HuggingFace and cache for the session.
    Returns None if PyTorch / model weights are unavailable.
    """
    # Skip the heavy torch model on the public cloud demo (limited RAM).
    if os.environ.get("DEMO_ONLY", "").strip().lower() in ("1", "true", "yes") \
       or os.environ.get("DISABLE_KRONOS", "").strip().lower() in ("1", "true", "yes"):
        return None
    _add_repo_root()
    try:
        from model import Kronos, KronosTokenizer, KronosPredictor
        tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
        model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
        return KronosPredictor(model, tokenizer, max_context=512)
    except Exception:
        return None


def _yf_to_kronos(df: pd.DataFrame) -> pd.DataFrame:
    """Convert yfinance DataFrame (title-case columns) to Kronos format (lowercase)."""
    col_map = {
        "Open": "open", "High": "high",
        "Low": "low", "Close": "close", "Volume": "volume",
    }
    out = df.rename(columns=col_map)
    needed = ["open", "high", "low", "close", "volume"]
    out = out[[c for c in needed if c in out.columns]].copy()
    if "volume" not in out.columns:
        out["volume"] = 0.0
    out = out.dropna(subset=["open", "high", "low", "close"])
    return out.astype(float)


def run_kronos_prediction(
    df_yf: pd.DataFrame,
    pred_len: int = 10,
    sample_count: int = 5,
) -> pd.DataFrame | None:
    """
    Run KronosPredictor on a yfinance OHLCV DataFrame.

    Returns a DataFrame of predicted OHLCV indexed by future business dates,
    or None when the model is unavailable or inference fails.
    """
    predictor = get_kronos_predictor()
    if predictor is None:
        return None

    try:
        kdf = _yf_to_kronos(df_yf)
        if len(kdf) < 30:
            return None

        lookback = min(400, len(kdf))
        x_df = kdf.iloc[:lookback].reset_index(drop=True)
        x_ts = pd.Series(kdf.index[:lookback])

        last_date = kdf.index[-1]
        future_dates = pd.bdate_range(
            start=last_date + pd.Timedelta(days=1), periods=pred_len
        )
        y_ts = pd.Series(future_dates)

        pred_df = predictor.predict(
            df=x_df,
            x_timestamp=x_ts,
            y_timestamp=y_ts,
            pred_len=pred_len,
            T=1.0,
            top_p=0.9,
            sample_count=sample_count,
        )
        pred_df.index = future_dates
        return pred_df
    except Exception:
        return None


def interpret_kronos(df_yf: pd.DataFrame, pred_df: pd.DataFrame) -> dict:
    """
    Summarise a Kronos prediction into a directional signal + stats.

    Returns a dict with keys:
        current_close, pred_close_end, pred_close_avg,
        pct_change, direction_score (0–100), direction (str)
    """
    current = float(df_yf["Close"].iloc[-1])
    end_pred = float(pred_df["close"].iloc[-1])
    avg_pred = float(pred_df["close"].mean())
    pct = (end_pred - current) / current * 100

    # Map percentage change to a 0-100 directional score
    if pct > 8:
        dscore = 93.0
    elif pct > 5:
        dscore = 82.0
    elif pct > 2:
        dscore = 70.0
    elif pct > 0.5:
        dscore = 60.0
    elif pct > -0.5:
        dscore = 50.0
    elif pct > -2:
        dscore = 38.0
    elif pct > -5:
        dscore = 25.0
    else:
        dscore = 12.0

    direction = (
        "Bullish" if pct > 0.5
        else ("Bearish" if pct < -0.5 else "Neutral")
    )

    return {
        "current_close": current,
        "pred_close_end": end_pred,
        "pred_close_avg": avg_pred,
        "pct_change": pct,
        "direction_score": dscore,
        "direction": direction,
    }
