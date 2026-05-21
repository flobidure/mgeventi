#!/usr/bin/env python3
"""Backtest de scalping trade par trade, avec spread + frais + slippage et stops ATR.

Convention : long et short, une position à la fois, pas de levier (capital plein
par trade). Les signaux sont décidés à la clôture de la barre ; les stops/objectifs
sont vérifiés en intrabar (si stop et objectif touchés dans la même barre, on
suppose le stop d'abord — hypothèse conservatrice).
"""
import argparse

import numpy as np
import pandas as pd

from common_intraday import load_ohlcv, add_indicators


def target_ema_ribbon(df):
    up = (df.ema_5 > df.ema_8) & (df.ema_8 > df.ema_13) & (df.ema_13 > df.ema_21)
    down = (df.ema_5 < df.ema_8) & (df.ema_8 < df.ema_13) & (df.ema_13 < df.ema_21)
    t = np.where(up, 1, np.where(down, -1, 0))
    return pd.Series(t, index=df.index)


def target_breakout(df, lookback):
    hh = df.high.rolling(lookback, min_periods=lookback).max().shift(1)
    ll = df.low.rolling(lookback, min_periods=lookback).min().shift(1)
    raw = pd.Series(np.nan, index=df.index)
    raw[df.close > hh] = 1
    raw[df.close < ll] = -1
    return raw.ffill().fillna(0)


def target_vwap_reversion(df, lo=35, hi=65):
    close, vwap, rsi = df.close.values, df.vwap.values, df.rsi_7.values
    out = np.zeros(len(df))
    pos = 0
    for i in range(len(df)):
        if np.isnan(vwap[i]) or np.isnan(rsi[i]):
            out[i] = pos
            continue
        if pos == 0:
            if close[i] < vwap[i] and rsi[i] < lo:
                pos = 1
            elif close[i] > vwap[i] and rsi[i] > hi:
                pos = -1
        elif pos == 1 and close[i] >= vwap[i]:
            pos = 0
        elif pos == -1 and close[i] <= vwap[i]:
            pos = 0
        out[i] = pos
    return pd.Series(out, index=df.index)


def trade_return(pos, entry, exit_px, cost_side, fee):
    if pos > 0:
        eff_in = entry * (1 + cost_side)
        eff_out = exit_px * (1 - cost_side)
        return eff_out / eff_in - 1 - 2 * fee
    eff_in = entry * (1 - cost_side)
    eff_out = exit_px * (1 + cost_side)
    return eff_in / eff_out - 1 - 2 * fee


def run(df, target, spread_bps, fee_bps, slippage_bps, atr_stop, atr_target):
    close, high, low = df.close.values, df.high.values, df.low.values
    atr = df.atr_14.values
    tgt_arr = target.values
    cost_side = (spread_bps / 2 + slippage_bps) / 1e4
    fee = fee_bps / 1e4

    pos = 0
    entry = stop = target_px = 0.0
    entry_i = 0
    equity = 1.0
    eq_curve = np.empty(len(df))
    trades = []

    def close_trade(i, exit_px):
        nonlocal pos, equity
        ret = trade_return(pos, entry, exit_px, cost_side, fee)
        equity *= 1 + ret
        trades.append({"ret": ret, "bars": i - entry_i, "dir": pos})
        pos = 0

    def open_trade(i, direction):
        nonlocal pos, entry, stop, target_px, entry_i
        pos = direction
        entry = close[i]
        entry_i = i
        if direction > 0:
            stop = entry - atr_stop * atr[i]
            target_px = entry + atr_target * atr[i]
        else:
            stop = entry + atr_stop * atr[i]
            target_px = entry - atr_target * atr[i]

    for i in range(len(df)):
        # 1) gérer la position ouverte en intrabar (stop prioritaire sur objectif)
        if pos != 0:
            exit_px = None
            if pos > 0:
                if low[i] <= stop:
                    exit_px = stop
                elif high[i] >= target_px:
                    exit_px = target_px
            else:
                if high[i] >= stop:
                    exit_px = stop
                elif low[i] <= target_px:
                    exit_px = target_px
            if exit_px is not None:
                close_trade(i, exit_px)

        # 2) décision à la clôture
        desired = tgt_arr[i]
        if not np.isnan(atr[i]) and atr[i] > 0:
            if pos == 0 and desired != 0:
                open_trade(i, int(np.sign(desired)))
            elif pos != 0 and (desired == 0 or np.sign(desired) != np.sign(pos)):
                close_trade(i, close[i])
                if desired != 0:
                    open_trade(i, int(np.sign(desired)))

        eq_curve[i] = equity

    return trades, pd.Series(eq_curve, index=df.index)


def max_consecutive_losses(rets):
    best = cur = 0
    for r in rets:
        cur = cur + 1 if r < 0 else 0
        best = max(best, cur)
    return best


def report(name, trades, eq, df, fee_bps):
    rets = np.array([t["ret"] for t in trades])
    n = len(rets)
    print(f"\nStratégie : {name}")
    print(f"Période   : {df.index[0]} → {df.index[-1]}  ({len(df)} barres)")
    print("-" * 56)
    if n == 0:
        print("  Aucun trade généré.")
        return
    wins = rets[rets > 0]
    losses = rets[rets < 0]
    pf = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else float("inf")
    max_dd = (eq / np.maximum.accumulate(eq) - 1).min()
    span_days = max((df.index[-1] - df.index[0]).total_seconds() / 86400, 1e-9) \
        if isinstance(df.index, pd.DatetimeIndex) else 1
    avg_bars = np.mean([t["bars"] for t in trades])

    rows = {
        "rendement_net_%": round((eq.iloc[-1] - 1) * 100, 2),
        "nombre_de_trades": n,
        "trades_par_jour": round(n / span_days, 1),
        "taux_de_réussite_%": round(len(wins) / n * 100, 1),
        "profit_factor": round(pf, 2),
        "espérance_par_trade_bps": round(rets.mean() * 1e4, 2),
        "gain_moyen_bps": round(wins.mean() * 1e4, 2) if len(wins) else 0,
        "perte_moyenne_bps": round(losses.mean() * 1e4, 2) if len(losses) else 0,
        "pertes_consécutives_max": max_consecutive_losses(rets),
        "durée_moyenne_barres": round(avg_bars, 1),
        "drawdown_max_%": round(max_dd * 100, 2),
    }
    for k, v in rows.items():
        print(f"  {k:<28} {v}")
    if fee_bps > 0:
        print(f"\n  (Coûts inclus. Relancer avec --fee-bps 0 pour mesurer leur impact.)")


def main():
    p = argparse.ArgumentParser(description="Backtest de scalping avec coûts.")
    p.add_argument("csv")
    p.add_argument("--strategy", required=True, choices=["ema_ribbon", "vwap_reversion", "breakout"])
    p.add_argument("--lookback", type=int, default=20, help="Fenêtre Donchian (breakout).")
    p.add_argument("--spread-bps", type=float, default=1.0)
    p.add_argument("--fee-bps", type=float, default=4.0, help="Frais par côté (bps du notional).")
    p.add_argument("--slippage-bps", type=float, default=1.0)
    p.add_argument("--atr-stop", type=float, default=1.0, help="Stop = ATR × ce multiple.")
    p.add_argument("--atr-target", type=float, default=1.5, help="Objectif = ATR × ce multiple.")
    args = p.parse_args()

    df = add_indicators(load_ohlcv(args.csv))

    if args.strategy == "ema_ribbon":
        tgt = target_ema_ribbon(df)
    elif args.strategy == "breakout":
        tgt = target_breakout(df, args.lookback)
    else:
        tgt = target_vwap_reversion(df)

    trades, eq = run(df, tgt, args.spread_bps, args.fee_bps, args.slippage_bps,
                     args.atr_stop, args.atr_target)
    report(args.strategy, trades, eq, df, args.fee_bps)


if __name__ == "__main__":
    main()
