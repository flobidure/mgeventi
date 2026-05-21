#!/usr/bin/env python3
"""Évalue le signal de scalping actuel sur une ou plusieurs séries intraday."""
import argparse
import os

import numpy as np

from common_intraday import load_ohlcv, add_indicators
from scalp_backtest import target_ema_ribbon, target_breakout, target_vwap_reversion

LABEL = {1: "LONG", -1: "SHORT", 0: "—"}


def main():
    p = argparse.ArgumentParser(description="Screener de signaux de scalping.")
    p.add_argument("csvs", nargs="+", help="Fichiers CSV de bougies intraday.")
    p.add_argument("--strategy", default="ema_ribbon",
                   choices=["ema_ribbon", "vwap_reversion", "breakout"])
    p.add_argument("--lookback", type=int, default=20)
    args = p.parse_args()

    print(f"\nSignaux ({args.strategy})")
    print("=" * 70)
    print(f"  {'Instrument':<22}{'Signal':<8}{'Close':>12}{'VWAP':>12}{'RSI7':>8}")
    print("-" * 70)

    for path in args.csvs:
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            df = add_indicators(load_ohlcv(path))
        except SystemExit as e:
            print(f"  {name:<22} erreur: {e}")
            continue
        if args.strategy == "ema_ribbon":
            tgt = target_ema_ribbon(df)
        elif args.strategy == "breakout":
            tgt = target_breakout(df, args.lookback)
        else:
            tgt = target_vwap_reversion(df)

        last = df.iloc[-1]
        sig = int(tgt.iloc[-1]) if not np.isnan(tgt.iloc[-1]) else 0
        rsi = last.rsi_7
        print(f"  {name:<22}{LABEL[sig]:<8}{last.close:>12.4f}{last.vwap:>12.4f}"
              f"{(rsi if not np.isnan(rsi) else 0):>8.1f}")


if __name__ == "__main__":
    main()
