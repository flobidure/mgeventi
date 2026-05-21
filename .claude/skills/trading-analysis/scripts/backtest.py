#!/usr/bin/env python3
"""Backtest de stratégies simples sur un CSV de prix (long-only, sans frais par défaut)."""
import argparse
import sys

import numpy as np
import pandas as pd

from indicators import sma, ema, rsi, bollinger


def load_prices(path):
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    if "close" not in df.columns:
        sys.exit("Erreur : le CSV doit contenir une colonne 'close'.")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.set_index("date")
    return df.dropna(subset=["close"])


def signals_sma_cross(df, fast, slow):
    f, s = sma(df["close"], fast), sma(df["close"], slow)
    return (f > s).astype(int)


def signals_ema_cross(df, fast, slow):
    f, s = ema(df["close"], fast), ema(df["close"], slow)
    return (f > s).astype(int)


def signals_rsi(df, period, oversold, overbought):
    r = rsi(df["close"], period)
    pos = pd.Series(np.nan, index=df.index)
    pos[r < oversold] = 1
    pos[r > overbought] = 0
    return pos.ffill().fillna(0).astype(int)


def signals_bollinger(df, period, num_std):
    up, mid, low = bollinger(df["close"], period, num_std)
    pos = pd.Series(np.nan, index=df.index)
    pos[df["close"] < low] = 1
    pos[df["close"] > mid] = 0
    return pos.ffill().fillna(0).astype(int)


def metrics(returns, position, fee):
    # Position décalée d'un jour : on entre au prix de clôture suivant le signal.
    pos = position.shift(1).fillna(0)
    trades = pos.diff().abs().fillna(0)
    strat_ret = pos * returns - trades * fee
    equity = (1 + strat_ret).cumprod()

    total = equity.iloc[-1] - 1 if len(equity) else 0.0
    ann = (1 + strat_ret).prod() ** (252 / len(strat_ret)) - 1 if len(strat_ret) else 0.0
    vol = strat_ret.std() * np.sqrt(252)
    sharpe = (strat_ret.mean() * 252) / vol if vol else 0.0
    drawdown = (equity / equity.cummax() - 1).min()

    entries = trades[(pos > 0) & (trades > 0)]
    n_trades = int((pos.diff() > 0).sum())
    wins = (strat_ret[pos > 0] > 0).sum()
    active = (pos > 0).sum()
    win_rate = wins / active if active else 0.0

    return {
        "rendement_total_%": round(total * 100, 2),
        "rendement_annualisé_%": round(ann * 100, 2),
        "volatilité_annualisée_%": round(vol * 100, 2),
        "sharpe": round(sharpe, 2),
        "drawdown_max_%": round(drawdown * 100, 2),
        "nombre_de_trades": n_trades,
        "taux_de_réussite_%": round(win_rate * 100, 2),
        "equity_finale": round(equity.iloc[-1], 4) if len(equity) else 1.0,
    }


def main():
    p = argparse.ArgumentParser(description="Backtest d'une stratégie de trading.")
    p.add_argument("csv")
    p.add_argument(
        "--strategy",
        required=True,
        choices=["sma_cross", "ema_cross", "rsi", "bollinger", "buy_hold"],
    )
    p.add_argument("--fast", type=int, default=20)
    p.add_argument("--slow", type=int, default=50)
    p.add_argument("--rsi-period", type=int, default=14)
    p.add_argument("--oversold", type=float, default=30)
    p.add_argument("--overbought", type=float, default=70)
    p.add_argument("--bb-period", type=int, default=20)
    p.add_argument("--bb-std", type=float, default=2.0)
    p.add_argument("--fee", type=float, default=0.0, help="Frais par transaction (ex: 0.001 = 0.1%).")
    args = p.parse_args()

    df = load_prices(args.csv)
    returns = df["close"].pct_change().fillna(0)

    if args.strategy == "sma_cross":
        pos = signals_sma_cross(df, args.fast, args.slow)
    elif args.strategy == "ema_cross":
        pos = signals_ema_cross(df, args.fast, args.slow)
    elif args.strategy == "rsi":
        pos = signals_rsi(df, args.rsi_period, args.oversold, args.overbought)
    elif args.strategy == "bollinger":
        pos = signals_bollinger(df, args.bb_period, args.bb_std)
    else:  # buy_hold
        pos = pd.Series(1, index=df.index)

    result = metrics(returns, pos, args.fee)
    bh = metrics(returns, pd.Series(1, index=df.index), 0.0)

    print(f"\nStratégie : {args.strategy}")
    print(f"Période   : {df.index[0]} → {df.index[-1]}  ({len(df)} barres)")
    print("-" * 50)
    for k, v in result.items():
        print(f"  {k:<26} {v}")
    print("-" * 50)
    print(f"  Référence buy & hold       {bh['rendement_total_%']}%  "
          f"(sharpe {bh['sharpe']}, DD {bh['drawdown_max_%']}%)")


if __name__ == "__main__":
    main()
