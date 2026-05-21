"""Chargement et indicateurs partagés pour les bougies intraday."""
import sys

import numpy as np
import pandas as pd

REQUIRED = ["open", "high", "low", "close"]


def load_ohlcv(path):
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    ts_col = next((c for c in ("timestamp", "date", "datetime", "time") if c in df.columns), None)
    if ts_col:
        # timestamp epoch (ms) ou date lisible
        if pd.api.types.is_numeric_dtype(df[ts_col]):
            unit = "ms" if df[ts_col].iloc[0] > 1e11 else "s"
            df["dt"] = pd.to_datetime(df[ts_col], unit=unit)
        else:
            df["dt"] = pd.to_datetime(df[ts_col], errors="coerce")
        df = df.set_index("dt")
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        sys.exit(f"Colonnes manquantes : {missing}. Attendu : open, high, low, close [, volume].")
    if "volume" not in df.columns:
        df["volume"] = 0.0
    return df[REQUIRED + ["volume"]].apply(pd.to_numeric, errors="coerce").dropna(subset=REQUIRED)


def ema(s, period):
    return s.ewm(span=period, adjust=False).mean()


def rsi(close, period=7):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    ag = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    al = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = ag / al.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def atr(df, period=14):
    pc = df["close"].shift(1)
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def vwap(df):
    """VWAP réinitialisée chaque jour (séance)."""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    pv = tp * df["volume"]
    if isinstance(df.index, pd.DatetimeIndex):
        day = df.index.normalize()
        cum_pv = pv.groupby(day).cumsum()
        cum_v = df["volume"].groupby(day).cumsum()
    else:
        cum_pv, cum_v = pv.cumsum(), df["volume"].cumsum()
    return cum_pv / cum_v.replace(0, np.nan)


def stochastic(df, period=14, smooth=3):
    low_min = df["low"].rolling(period, min_periods=period).min()
    high_max = df["high"].rolling(period, min_periods=period).max()
    k = 100 * (df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)
    return k, k.rolling(smooth, min_periods=smooth).mean()


def volume_zscore(volume, window=20):
    mean = volume.rolling(window, min_periods=window).mean()
    std = volume.rolling(window, min_periods=window).std()
    return (volume - mean) / std.replace(0, np.nan)


def add_indicators(df):
    df = df.copy()
    df["vwap"] = vwap(df)
    for p in (5, 8, 13, 21):
        df[f"ema_{p}"] = ema(df["close"], p)
    df["rsi_7"] = rsi(df["close"], 7)
    df["stoch_k"], df["stoch_d"] = stochastic(df)
    df["atr_14"] = atr(df, 14)
    df["vol_z"] = volume_zscore(df["volume"], 20)
    return df
