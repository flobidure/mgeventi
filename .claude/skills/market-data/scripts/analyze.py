#!/usr/bin/env python3
"""Statistiques quant sur une matrice de prix de clôture (une colonne par actif)."""
import argparse
import sys

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def load_prices(path):
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    date_col = next((c for c in df.columns if c.lower() == "date"), None)
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.set_index(date_col)
    # Si un seul actif avec OHLCV, ne garder que 'close'
    lower = [c.lower() for c in df.columns]
    if "close" in lower and len(df.columns) > 1:
        col = df.columns[lower.index("close")]
        df = df[[col]]
    return df.apply(pd.to_numeric, errors="coerce").dropna(how="all")


def asset_stats(returns):
    ann_ret = (1 + returns.mean()) ** TRADING_DAYS - 1
    ann_vol = returns.std() * np.sqrt(TRADING_DAYS)
    sharpe = ann_ret / ann_vol
    downside = returns[returns < 0].std() * np.sqrt(TRADING_DAYS)
    sortino = ann_ret / downside
    equity = (1 + returns).cumprod()
    max_dd = (equity / equity.cummax() - 1).min()
    return pd.DataFrame(
        {
            "rendement_annualisé_%": (ann_ret * 100).round(2),
            "volatilité_%": (ann_vol * 100).round(2),
            "sharpe": sharpe.round(2),
            "sortino": sortino.round(2),
            "drawdown_max_%": (max_dd * 100).round(2),
        }
    )


def main():
    p = argparse.ArgumentParser(description="Analyse quant d'une matrice de prix.")
    p.add_argument("csv")
    p.add_argument("--weights", help='Pondérations: "AAPL=0.4,MSFT=0.3,GOOGL=0.3"')
    args = p.parse_args()

    prices = load_prices(args.csv)
    returns = prices.pct_change().dropna(how="all")
    if returns.empty:
        sys.exit("Pas assez de données pour calculer des rendements.")

    print("\nStatistiques par actif")
    print("=" * 70)
    with pd.option_context("display.width", 200):
        print(asset_stats(returns).to_string())

    if returns.shape[1] > 1:
        print("\nMatrice de corrélation des rendements")
        print("=" * 70)
        print(returns.corr().round(2).to_string())

    if args.weights:
        weights = {}
        for part in args.weights.split(","):
            k, v = part.split("=")
            weights[k.strip()] = float(v)
        missing = set(weights) - set(returns.columns)
        if missing:
            sys.exit(f"Actifs introuvables dans le CSV : {missing}")
        w = pd.Series(weights).reindex(returns.columns).fillna(0)
        if abs(w.sum() - 1) > 1e-6:
            print(f"\n(Note : somme des pondérations = {w.sum():.3f}, normalisation appliquée.)")
            w = w / w.sum()
        port_ret = (returns[w.index] * w).sum(axis=1)
        print("\nPortefeuille pondéré")
        print("=" * 70)
        print(asset_stats(port_ret.to_frame("portefeuille")).to_string())


if __name__ == "__main__":
    main()
