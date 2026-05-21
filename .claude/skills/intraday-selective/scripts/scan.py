#!/usr/bin/env python3
"""Scanne le setup intraday du moment sur une watchlist (dernière barre de chaque CSV)."""
import argparse
import os

import numpy as np

from common import load_ohlcv, add_indicators
from strategies import get_signal

LABEL = {1: "ACHAT", -1: "VENTE", 0: "—"}


def main():
    p = argparse.ArgumentParser(description="Scanner de setups intraday sélectifs.")
    p.add_argument("csvs", nargs="+")
    p.add_argument("--strategy", default="confluence", choices=["orb", "trend_pullback", "confluence"])
    p.add_argument("--or-minutes", type=int, default=30)
    p.add_argument("--threshold", type=int, default=4)
    p.add_argument("--atr-stop", type=float, default=1.5)
    p.add_argument("--atr-target", type=float, default=2.5)
    args = p.parse_args()

    print(f"\nSetups ({args.strategy})")
    print("=" * 78)
    print(f"  {'Instrument':<18}{'Signal':<8}{'Close':>12}{'VWAP':>12}{'Stop':>11}{'Objectif':>11}")
    print("-" * 78)

    for path in args.csvs:
        name = os.path.splitext(os.path.basename(path))[0]
        df = add_indicators(load_ohlcv(path))
        sig = get_signal(df, args.strategy, or_minutes=args.or_minutes, threshold=args.threshold)
        last = df.iloc[-1]
        s = int(sig.iloc[-1])
        atr = last.atr_14
        if s == 1:
            stop, tgt = last.close - args.atr_stop * atr, last.close + args.atr_target * atr
        elif s == -1:
            stop, tgt = last.close + args.atr_stop * atr, last.close - args.atr_target * atr
        else:
            stop = tgt = np.nan
        sd = f"{stop:>11.4f}" if not np.isnan(stop) else f"{'—':>11}"
        td = f"{tgt:>11.4f}" if not np.isnan(tgt) else f"{'—':>11}"
        print(f"  {name:<18}{LABEL[s]:<8}{last.close:>12.4f}{last.vwap:>12.4f}{sd}{td}")

    print("\nNote : signal sur la dernière barre du CSV. Rafraîchir les données pour le temps réel.")


if __name__ == "__main__":
    main()
