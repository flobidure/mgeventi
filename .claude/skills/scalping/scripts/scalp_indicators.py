#!/usr/bin/env python3
"""Ajoute les indicateurs de scalping à un CSV de bougies intraday."""
import argparse

import pandas as pd

from common_intraday import load_ohlcv, add_indicators


def main():
    p = argparse.ArgumentParser(description="Indicateurs de scalping.")
    p.add_argument("csv")
    p.add_argument("--out", help="CSV de sortie (sinon affiche les dernières barres).")
    args = p.parse_args()

    df = add_indicators(load_ohlcv(args.csv))

    if args.out:
        df.to_csv(args.out)
        print(f"Écrit dans {args.out} ({len(df)} barres, {len(df.columns)} colonnes).")
    else:
        with pd.option_context("display.max_columns", None, "display.width", 220):
            print(df.tail(10))


if __name__ == "__main__":
    main()
