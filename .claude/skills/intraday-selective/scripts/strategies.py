"""Générateurs de signaux d'entrée sélectifs.

Chaque fonction renvoie une Series de déclencheurs d'entrée dans {-1, 0, 1} :
  +1 = déclenche un achat sur cette barre, -1 = vente, 0 = rien.
Les sorties (stop/objectif/temps/fin de séance) sont gérées par le backtester.
On émet un déclencheur uniquement sur la barre de transition, pas en continu :
c'est ce qui garde le nombre de trades bas et les setups « propres ».
"""
import numpy as np
import pandas as pd


def opening_range_breakout(df, or_minutes=30):
    """Cassure du range d'ouverture : long au-dessus du high d'ouverture, short en dessous du low."""
    sig = pd.Series(0, index=df.index)
    for _, g in df.groupby("day"):
        opening = g[g.min_off < or_minutes]
        if opening.empty:
            continue
        or_high, or_low = opening.high.max(), opening.low.min()
        after = g[g.min_off >= or_minutes]
        if after.empty:
            continue
        c = after.close
        prev = c.shift(1)
        long_brk = (c > or_high) & (prev <= or_high)
        short_brk = (c < or_low) & (prev >= or_low)
        sig.loc[after.index[long_brk]] = 1
        sig.loc[after.index[short_brk]] = -1
    return sig


def _cross_up(series, level):
    return (series > level) & (series.shift(1) <= level)


def trend_pullback(df):
    """Tendance (EMA20/50) + repli sur la VWAP + reprise du momentum (RSI repasse 50)."""
    up_trend = (df.ema_20 > df.ema_50) & (df.ema_50 > df.ema_50.shift(5))
    down_trend = (df.ema_20 < df.ema_50) & (df.ema_50 < df.ema_50.shift(5))
    pulled_below = df.close.shift(1) < df.vwap.shift(1)
    pulled_above = df.close.shift(1) > df.vwap.shift(1)

    long_sig = up_trend & pulled_below & _cross_up(df.rsi_14, 50) & (df.close > df.vwap)
    short_sig = down_trend & pulled_above & (df.rsi_14 < 50) & (df.rsi_14.shift(1) >= 50) & (df.close < df.vwap)

    sig = pd.Series(0, index=df.index)
    sig[long_sig] = 1
    sig[short_sig] = -1
    return sig


def confluence(df, threshold=4):
    """Score de confluence : on entre quand le score franchit un seuil (peu de signaux)."""
    long_score = (
        (df.ema_20 > df.ema_50).astype(int)
        + (df.close > df.vwap).astype(int)
        + (df.rsi_14 > 50).astype(int)
        + (df.macd_hist > 0).astype(int)
        + (df.vol_z > 0.5).astype(int)
    )
    short_score = (
        (df.ema_20 < df.ema_50).astype(int)
        + (df.close < df.vwap).astype(int)
        + (df.rsi_14 < 50).astype(int)
        + (df.macd_hist < 0).astype(int)
        + (df.vol_z > 0.5).astype(int)
    )
    long_trig = (long_score >= threshold) & (long_score.shift(1) < threshold)
    short_trig = (short_score >= threshold) & (short_score.shift(1) < threshold)

    sig = pd.Series(0, index=df.index)
    sig[long_trig] = 1
    sig[short_trig & ~long_trig] = -1
    return sig


def get_signal(df, name, **kw):
    if name == "orb":
        return opening_range_breakout(df, kw.get("or_minutes", 30))
    if name == "trend_pullback":
        return trend_pullback(df)
    if name == "confluence":
        return confluence(df, kw.get("threshold", 4))
    raise ValueError(f"Stratégie inconnue : {name}")
