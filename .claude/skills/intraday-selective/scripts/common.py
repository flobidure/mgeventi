"""Chargement, indicateurs et helpers de séance pour l'intraday sélectif."""
import sys

import numpy as np
import pandas as pd

REQUIRED = ["open", "high", "low", "close"]


def load_ohlcv(path):
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    ts_col = next((c for c in ("timestamp", "datetime", "date", "time") if c in df.columns), None)
    if ts_col is None:
        sys.exit("Colonne temporelle introuvable (timestamp/datetime/date/time requise).")
    if pd.api.types.is_numeric_dtype(df[ts_col]):
        unit = "ms" if df[ts_col].iloc[0] > 1e11 else "s"
        df.index = pd.to_datetime(df[ts_col], unit=unit)
    else:
        df.index = pd.to_datetime(df[ts_col], errors="coerce")
    df.index.name = "dt"
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        sys.exit(f"Colonnes manquantes : {missing}. Attendu : open, high, low, close [, volume].")
    if "volume" not in df.columns:
        df["volume"] = 0.0
    df = df[REQUIRED + ["volume"]].apply(pd.to_numeric, errors="coerce").dropna(subset=REQUIRED)
    return df[~df.index.isna()].sort_index()


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def rsi(close, n=14):
    d = close.diff()
    ag = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    al = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = ag / al.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def atr(df, n=14):
    pc = df.close.shift(1)
    tr = pd.concat([df.high - df.low, (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def macd(close, fast=12, slow=26, signal=9):
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False).mean()
    return line, sig, line - sig


def vwap_daily(df):
    tp = (df.high + df.low + df.close) / 3
    day = df.index.normalize()
    return (tp * df.volume).groupby(day).cumsum() / df.volume.groupby(day).cumsum().replace(0, np.nan)


def session_info(df):
    """Renvoie (day_id, minutes écoulées depuis le 1er bar de la séance)."""
    day = df.index.normalize()
    session_start = df.groupby(day).apply(lambda g: g.index[0]).reindex(day).values
    minute_off = (df.index.values - session_start) / np.timedelta64(1, "m")
    return day, pd.Series(minute_off, index=df.index)


def add_indicators(df):
    df = df.copy()
    df["vwap"] = vwap_daily(df)
    for p in (8, 20, 50):
        df[f"ema_{p}"] = ema(df.close, p)
    df["rsi_14"] = rsi(df.close, 14)
    df["atr_14"] = atr(df, 14)
    _, _, df["macd_hist"] = macd(df.close)
    vmean = df.volume.rolling(20, min_periods=20).mean()
    vstd = df.volume.rolling(20, min_periods=20).std()
    df["vol_z"] = (df.volume - vmean) / vstd.replace(0, np.nan)
    df["day"], df["min_off"] = session_info(df)
    return df
