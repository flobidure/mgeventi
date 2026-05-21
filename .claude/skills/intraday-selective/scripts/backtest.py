#!/usr/bin/env python3
"""Backtest intraday sélectif : déclencheurs d'entrée + gestion de séance réaliste.

Garde-fous (façon day-trader discipliné) :
  - une position à la fois, capital plein, pas de levier ;
  - plafond de trades par jour (--max-trades) ;
  - arrêt de la journée après N pertes (--max-losses) ;
  - fenêtre d'entrée : pas avant --warmup min, pas après --last-entry min de séance ;
  - clôture forcée en fin de séance (aucune position gardée la nuit) ;
  - cooldown en barres après chaque trade ;
  - sortie par stop ATR / objectif ATR / stop temporel (--max-hold).
Tous les rendements sont nets de spread + frais + slippage.
"""
import argparse

import numpy as np
import pandas as pd

from common import load_ohlcv, add_indicators
from strategies import get_signal


def trade_return(direction, entry, exit_px, cost_side, fee):
    if direction > 0:
        return (exit_px * (1 - cost_side)) / (entry * (1 + cost_side)) - 1 - 2 * fee
    return (entry * (1 - cost_side)) / (exit_px * (1 + cost_side)) - 1 - 2 * fee


def run(df, signal, args):
    close, high, low = df.close.values, df.high.values, df.low.values
    atr = df.atr_14.values
    day = df.day.values
    min_off = df.min_off.values
    sig = signal.values
    is_last_of_day = np.r_[day[1:] != day[:-1], True]

    cost_side = (args.spread_bps / 2 + args.slippage_bps) / 1e4
    fee = args.fee_bps / 1e4

    equity = 1.0
    eq_curve = np.empty(len(df))
    trades = []

    pos = 0
    entry = stop = target = 0.0
    entry_i = 0
    cur_day = None
    day_trades = day_losses = 0
    cooldown_until = -1

    def open_pos(i, direction):
        nonlocal pos, entry, stop, target, entry_i
        pos, entry, entry_i = direction, close[i], i
        if direction > 0:
            stop = entry - args.atr_stop * atr[i]
            target = entry + args.atr_target * atr[i]
        else:
            stop = entry + args.atr_stop * atr[i]
            target = entry - args.atr_target * atr[i]

    def close_pos(i, exit_px, reason):
        nonlocal pos, equity, day_trades, day_losses, cooldown_until
        ret = trade_return(pos, entry, exit_px, cost_side, fee)
        equity *= 1 + ret
        trades.append({"day": cur_day, "ret": ret, "bars": i - entry_i,
                       "dir": pos, "reason": reason})
        day_trades += 1
        if ret < 0:
            day_losses += 1
        cooldown_until = i + args.cooldown
        pos = 0

    for i in range(len(df)):
        if day[i] != cur_day:
            cur_day, day_trades, day_losses = day[i], 0, 0

        # 1) gérer la position : stop/objectif intrabar (stop d'abord), puis stop temporel
        if pos != 0:
            exit_px = None
            if pos > 0:
                if low[i] <= stop:
                    exit_px, reason = stop, "stop"
                elif high[i] >= target:
                    exit_px, reason = target, "target"
            else:
                if high[i] >= stop:
                    exit_px, reason = stop, "stop"
                elif low[i] <= target:
                    exit_px, reason = target, "target"
            if exit_px is None and args.max_hold and (i - entry_i) >= args.max_hold:
                exit_px, reason = close[i], "time"
            # clôture forcée en fin de séance
            if exit_px is None and is_last_of_day[i]:
                exit_px, reason = close[i], "eod"
            if exit_px is not None:
                close_pos(i, exit_px, reason)

        # 2) entrée si flat et toutes les conditions de séance OK
        if (
            pos == 0
            and sig[i] != 0
            and not np.isnan(atr[i]) and atr[i] > 0
            and i > cooldown_until
            and day_trades < args.max_trades
            and day_losses < args.max_losses
            and min_off[i] >= args.warmup
            and min_off[i] <= args.last_entry
            and not is_last_of_day[i]
        ):
            open_pos(i, int(np.sign(sig[i])))

        eq_curve[i] = equity

    return trades, pd.Series(eq_curve, index=df.index)


def max_consec_losses(rets):
    best = cur = 0
    for r in rets:
        cur = cur + 1 if r < 0 else 0
        best = max(best, cur)
    return best


def report(name, trades, eq, df, args):
    print(f"\nStratégie : {name}")
    print(f"Période   : {df.index[0]} → {df.index[-1]}  ({len(df)} barres)")
    print("-" * 58)
    if not trades:
        print("  Aucun trade généré (filtres trop stricts ou données insuffisantes).")
        return
    rets = np.array([t["ret"] for t in trades])
    wins, losses = rets[rets > 0], rets[rets < 0]
    pf = wins.sum() / abs(losses.sum()) if losses.sum() else float("inf")
    max_dd = (eq / np.maximum.accumulate(eq) - 1).min()
    per_day = pd.Series([t["day"] for t in trades]).value_counts()
    n_days = pd.Series(df.day.unique()).shape[0]

    rows = {
        "rendement_net_%": round((eq.iloc[-1] - 1) * 100, 2),
        "nombre_de_trades": len(rets),
        "trades_par_jour_moyen": round(len(rets) / max(n_days, 1), 2),
        "trades_par_jour_max": int(per_day.max()),
        "taux_de_réussite_%": round(len(wins) / len(rets) * 100, 1),
        "profit_factor": round(pf, 2),
        "espérance_par_trade_bps": round(rets.mean() * 1e4, 1),
        "gain_moyen_bps": round(wins.mean() * 1e4, 1) if len(wins) else 0,
        "perte_moyenne_bps": round(losses.mean() * 1e4, 1) if len(losses) else 0,
        "ratio_gain_perte": round(abs(wins.mean() / losses.mean()), 2) if len(wins) and len(losses) else 0,
        "pertes_consécutives_max": max_consec_losses(rets),
        "durée_moyenne_barres": round(np.mean([t["bars"] for t in trades]), 1),
        "drawdown_max_%": round(max_dd * 100, 2),
    }
    for k, v in rows.items():
        print(f"  {k:<28} {v}")

    reasons = pd.Series([t["reason"] for t in trades]).value_counts()
    print("  sorties par motif           " + ", ".join(f"{k}:{v}" for k, v in reasons.items()))
    if args.fee_bps > 0:
        print("\n  (Net de coûts. --fee-bps 0 pour mesurer leur impact.)")


def main():
    p = argparse.ArgumentParser(description="Backtest intraday sélectif.")
    p.add_argument("csv")
    p.add_argument("--strategy", required=True,
                   choices=["orb", "trend_pullback", "confluence", "pullback_breakout"])
    p.add_argument("--or-minutes", type=int, default=30, help="Durée du range d'ouverture (orb).")
    p.add_argument("--threshold", type=int, default=4, help="Seuil de score (confluence).")
    p.add_argument("--lookback", type=int, default=20, help="Fenêtre de cassure (pullback_breakout).")
    # garde-fous
    p.add_argument("--max-trades", type=int, default=5, help="Plafond de trades par jour.")
    p.add_argument("--max-losses", type=int, default=2, help="Arrêt de la journée après N pertes.")
    p.add_argument("--warmup", type=float, default=15, help="Min après ouverture avant d'entrer.")
    p.add_argument("--last-entry", type=float, default=360, help="Dernière minute d'entrée de la séance.")
    p.add_argument("--cooldown", type=int, default=10, help="Barres d'attente après un trade.")
    p.add_argument("--max-hold", type=int, default=0, help="Stop temporel en barres (0 = désactivé).")
    # risque / coûts
    p.add_argument("--atr-stop", type=float, default=1.5)
    p.add_argument("--atr-target", type=float, default=2.5)
    p.add_argument("--spread-bps", type=float, default=1.0)
    p.add_argument("--fee-bps", type=float, default=4.0)
    p.add_argument("--slippage-bps", type=float, default=1.0)
    args = p.parse_args()

    df = add_indicators(load_ohlcv(args.csv))
    sig = get_signal(df, args.strategy, or_minutes=args.or_minutes,
                     threshold=args.threshold, lookback=args.lookback)
    trades, eq = run(df, sig, args)
    report(args.strategy, trades, eq, df, args)


if __name__ == "__main__":
    main()
