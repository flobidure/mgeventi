#!/usr/bin/env python3
"""Validation walk-forward : la seule façon honnête de mesurer un edge.

Principe : on découpe l'historique en fenêtres glissantes. Sur chaque fenêtre
« in-sample » (IS) on cherche les meilleurs paramètres ; on les applique ensuite
sur la fenêtre « out-of-sample » (OOS) suivante — des données que l'optimisation
n'a JAMAIS vues. On agrège uniquement les trades OOS.

Si la stratégie est rentable en OOS, l'edge est probablement réel. Si elle brille
en IS mais s'effondre en OOS, c'est du surapprentissage : on l'abandonne. Les
chiffres OOS sont ceux à brancher dans le simulateur Monte Carlo.
"""
import argparse
import itertools
from types import SimpleNamespace

import numpy as np
import pandas as pd

from common import load_ohlcv, add_indicators
from strategies import get_signal
from backtest import run

PARAM_GRID = {
    "atr_stop": [1.0, 1.5, 2.0],
    "rr": [2.0, 3.0],  # objectif = rr × stop
}
STRAT_GRID = {
    "orb": {"or_minutes": [15, 30, 60]},
    "confluence": {"threshold": [3, 4, 5]},
    "pullback_breakout": {"lookback": [10, 20, 30]},
    "trend_pullback": {"_": [0]},
}


def base_args(a):
    return dict(
        spread_bps=a.spread_bps, fee_bps=a.fee_bps, slippage_bps=a.slippage_bps,
        max_trades=a.max_trades, max_losses=a.max_losses, warmup=a.warmup,
        last_entry=a.last_entry, cooldown=a.cooldown, max_hold=a.max_hold,
        or_minutes=30, threshold=4, lookback=20,
    )


def make_args(base, combo):
    d = dict(base)
    d["atr_stop"] = combo["atr_stop"]
    d["atr_target"] = combo["atr_stop"] * combo["rr"]
    for k, v in combo.items():
        if k in ("or_minutes", "threshold", "lookback"):
            d[k] = v
    return SimpleNamespace(**d)


def trade_metrics(trades):
    rets = np.array([t["ret"] for t in trades]) if trades else np.array([])
    if len(rets) == 0:
        return {"n": 0, "pf": 0.0, "exp": 0.0, "wr": 0.0, "rets": rets}
    wins, losses = rets[rets > 0], rets[rets < 0]
    pf = wins.sum() / abs(losses.sum()) if losses.sum() else float("inf")
    return {"n": len(rets), "pf": pf, "exp": float(rets.mean()),
            "wr": len(wins) / len(rets), "rets": rets}


def iter_combos(strategy):
    grids = {**PARAM_GRID, **{k: v for k, v in STRAT_GRID[strategy].items() if k != "_"}}
    keys = list(grids)
    for vals in itertools.product(*[grids[k] for k in keys]):
        yield dict(zip(keys, vals))


def evaluate(df, strategy, args_obj, params):
    sig = get_signal(df, strategy, or_minutes=getattr(args_obj, "or_minutes", 30),
                     threshold=getattr(args_obj, "threshold", 4),
                     lookback=getattr(args_obj, "lookback", 20))
    trades, eq = run(df, sig, args_obj)
    return trades, eq


def main():
    p = argparse.ArgumentParser(description="Validation walk-forward d'une stratégie intraday.")
    p.add_argument("csv")
    p.add_argument("--strategy", required=True,
                   choices=["orb", "trend_pullback", "confluence", "pullback_breakout"])
    p.add_argument("--train-bars", type=int, default=2000, help="Taille fenêtre IS (barres).")
    p.add_argument("--test-bars", type=int, default=500, help="Taille fenêtre OOS (barres).")
    p.add_argument("--min-trades", type=int, default=8, help="Trades IS min pour retenir un réglage.")
    p.add_argument("--select-by", choices=["exp", "pf"], default="exp", help="Critère de sélection IS.")
    # garde-fous / coûts (transmis au moteur)
    p.add_argument("--max-trades", type=int, default=5)
    p.add_argument("--max-losses", type=int, default=2)
    p.add_argument("--warmup", type=float, default=15)
    p.add_argument("--last-entry", type=float, default=360)
    p.add_argument("--cooldown", type=int, default=10)
    p.add_argument("--max-hold", type=int, default=0)
    p.add_argument("--spread-bps", type=float, default=1.0)
    p.add_argument("--fee-bps", type=float, default=4.0)
    p.add_argument("--slippage-bps", type=float, default=1.0)
    args = p.parse_args()

    df = add_indicators(load_ohlcv(args.csv))
    base = base_args(args)
    combos = list(iter_combos(args.strategy))
    T = len(df)

    starts = list(range(0, T - args.train_bars - args.test_bars + 1, args.test_bars))
    if not starts:
        raise SystemExit(f"Pas assez de données : {T} barres pour train {args.train_bars} + test {args.test_bars}.")

    print(f"\nWalk-forward — {args.strategy}  ({len(combos)} réglages × {len(starts)} folds)")
    print(f"Données : {T} barres   IS {args.train_bars} / OOS {args.test_bars}")
    print("=" * 76)
    print(f"  {'Fold':<6}{'Période OOS':<26}{'Réglage retenu':<22}{'OOS n':>6}{'OOS exp(bps)':>13}")
    print("-" * 76)

    oos_rets = []
    oos_eq = 1.0
    fold_rows = []

    for i, s in enumerate(starts, 1):
        is_df = df.iloc[s:s + args.train_bars]
        oos_df = df.iloc[s + args.train_bars:s + args.train_bars + args.test_bars]

        best, best_score = None, -np.inf
        for combo in combos:
            a = make_args(base, combo)
            tr, _ = evaluate(is_df, args.strategy, a, combo)
            m = trade_metrics(tr)
            if m["n"] < args.min_trades:
                continue
            score = m["exp"] if args.select_by == "exp" else m["pf"]
            if score > best_score:
                best_score, best = score, combo

        if best is None:
            fold_rows.append((i, oos_df, "aucun (trop peu de trades IS)", 0, 0.0))
            continue

        a = make_args(base, best)
        tr, _ = evaluate(oos_df, args.strategy, a, best)
        m = trade_metrics(tr)
        oos_rets.extend(m["rets"].tolist())
        for r in m["rets"]:
            oos_eq *= (1 + r)

        label = ", ".join(f"{k}={best[k]}" for k in best)
        period = f"{oos_df.index[0].date()}→{oos_df.index[-1].date()}" if len(oos_df) else "-"
        print(f"  {i:<6}{period:<26}{label:<22}{m['n']:>6}{m['exp'] * 1e4:>13.1f}")

    print("-" * 76)
    agg = trade_metrics([{"ret": r} for r in oos_rets])
    print("\n=== Résultat OUT-OF-SAMPLE agrégé (le seul qui compte) ===")
    if agg["n"] == 0:
        print("  Aucun trade OOS. Stratégie inexploitable telle quelle.")
        return
    rets = np.array(oos_rets)
    print(f"  Trades OOS                 {agg['n']:>10}")
    print(f"  Taux de réussite           {agg['wr'] * 100:>9.1f} %")
    print(f"  Profit factor              {agg['pf']:>10.2f}")
    print(f"  Espérance par trade        {agg['exp'] * 1e4:>9.1f} bps")
    print(f"  Rendement cumulé OOS       {(oos_eq - 1) * 100:>9.1f} %")
    print(f"  Gain moyen / perte moyenne {rets[rets > 0].mean() * 1e4 if (rets > 0).any() else 0:>9.1f}"
          f" / {rets[rets < 0].mean() * 1e4 if (rets < 0).any() else 0:.1f} bps")
    print("\n  → Branche ce taux de réussite et ce R:R réel dans simulate.py")
    print("    (skill trading-analysis) pour la distribution réaliste sur ton capital.")
    if agg["exp"] <= 0:
        print("\n  ⚠️  Espérance OOS négative : PAS d'edge exploitable. Ne pas trader ce réglage.")
    else:
        print("\n  ✓ Espérance OOS positive après coûts : edge plausible. Valider ensuite en démo.")


if __name__ == "__main__":
    main()
