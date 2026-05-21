#!/usr/bin/env python3
"""Simulateur Monte Carlo de croissance de compte — chiffres réalistes.

Rejoue un compte des milliers de fois pour montrer la DISTRIBUTION des résultats
(et pas un seul scénario optimiste). Modélise ce qui compte vraiment :
  - frais prélevés sur le NOTIONAL (capital × levier), pas sur la marge ;
  - compounding (la taille de position suit l'équité) ;
  - le levier effectif = risque% / stop%, plafonné par le broker ;
  - la ruine (compte sous un seuil) est absorbante.

Le levier n'est donc pas un bouton magique : plus il est élevé, plus les frais
rongent chaque trade. On voit noir sur blanc le compromis.
"""
import argparse

import numpy as np


def simulate(capital, risk_pct, stop_pct, rr, win_rate, fee_bps,
             trades, sims, max_leverage, ruin_pct, seed=None):
    rng = np.random.default_rng(seed)
    risk_frac = risk_pct / 100
    stop_frac = stop_pct / 100
    p_win = win_rate / 100

    # Levier effectif : pour risquer risk% avec un stop à stop%, il faut un
    # notional = risk/stop fois l'équité. Plafonné par le broker.
    desired_lev = risk_frac / stop_frac
    eff_lev = min(desired_lev, max_leverage)
    # Si plafonné, le risque réel par trade est réduit en conséquence.
    real_risk_frac = min(risk_frac, eff_lev * stop_frac)

    fee_frac = eff_lev * (fee_bps / 1e4) * 2          # frais (aller-retour) en % de l'équité
    win_frac = eff_lev * stop_frac * rr                # gain brut en % de l'équité
    loss_frac = eff_lev * stop_frac                    # perte brute en % de l'équité

    # espérance nette par trade (en fraction de l'équité)
    exp_net = p_win * (win_frac - fee_frac) + (1 - p_win) * (-loss_frac - fee_frac)
    single_loss_wipeout = (loss_frac + fee_frac) >= 1.0

    ruin_abs = capital * ruin_pct / 100
    eq = np.full(sims, float(capital))
    blown = np.zeros(sims, dtype=bool)

    wins = rng.random((trades, sims)) < p_win
    up = 1 + win_frac - fee_frac
    down = 1 - loss_frac - fee_frac
    for t in range(trades):
        factor = np.where(wins[t], up, down)
        eq = np.where(blown, 0.0, eq * factor)
        newly = (~blown) & (eq < ruin_abs)
        eq[newly] = 0.0
        blown |= newly

    return {
        "eq": eq,
        "blown": blown,
        "eff_lev": eff_lev,
        "real_risk_frac": real_risk_frac,
        "fee_frac": fee_frac,
        "exp_net": exp_net,
        "single_loss_wipeout": single_loss_wipeout,
        "capped": desired_lev > max_leverage,
    }


def pct(eq, q):
    return float(np.percentile(eq, q))


def main():
    p = argparse.ArgumentParser(description="Simulateur Monte Carlo de croissance de compte.")
    p.add_argument("--capital", type=float, default=500)
    p.add_argument("--risk-pct", type=float, default=1, help="Risque par trade en % de l'équité.")
    p.add_argument("--stop-pct", type=float, default=1, help="Distance du stop en %.")
    p.add_argument("--rr", type=float, default=1.5, help="Ratio gain/perte (objectif = rr × stop).")
    p.add_argument("--win-rate", type=float, default=50, help="Taux de réussite en %.")
    p.add_argument("--fee-bps", type=float, default=4, help="Frais par côté (bps du notional).")
    p.add_argument("--trades-per-day", type=float, default=3)
    p.add_argument("--days", type=int, default=252, help="Jours de trading (252 ≈ 1 an).")
    p.add_argument("--max-leverage", type=float, default=5)
    p.add_argument("--ruin-pct", type=float, default=10, help="Seuil de ruine en % du capital initial.")
    p.add_argument("--sims", type=int, default=20000)
    p.add_argument("--seed", type=int, default=None)
    args = p.parse_args()

    trades = int(args.trades_per_day * args.days)
    r = simulate(args.capital, args.risk_pct, args.stop_pct, args.rr, args.win_rate,
                 args.fee_bps, trades, args.sims, args.max_leverage, args.ruin_pct, args.seed)
    eq, blown = r["eq"], r["blown"]

    print("\n" + "=" * 60)
    print("  SIMULATEUR DE COMPTE — Monte Carlo")
    print("=" * 60)
    print(f"  Capital de départ          {args.capital:>12,.2f} €")
    print(f"  Risque/trade demandé       {args.risk_pct:>11.2f} %   stop {args.stop_pct:.2f} %   R:R {args.rr}")
    print(f"  Taux de réussite           {args.win_rate:>11.1f} %")
    print(f"  Frais                      {args.fee_bps:>11.1f} bps/côté")
    print(f"  Trades simulés             {trades:>12,}  ({args.trades_per_day}/j × {args.days} j)")
    print(f"  Simulations                {args.sims:>12,}")
    print("-" * 60)
    print(f"  Levier effectif (=risk/stop) {r['eff_lev']:>9.1f}x"
          + ("  [plafonné par le broker]" if r["capped"] else ""))
    print(f"  Frais par trade            {r['fee_frac'] * 100:>11.3f} % de l'équité")
    print(f"  Espérance nette/trade      {r['exp_net'] * 100:>11.4f} % de l'équité"
          + ("   ⚠️ NÉGATIVE" if r["exp_net"] <= 0 else "   ✓ positive"))
    if r["single_loss_wipeout"]:
        print("  ⚠️  Une SEULE perte peut ruiner le compte (perte+frais ≥ 100%).")

    print("\n  --- Distribution du capital final ---")
    for q, lab in [(5, "très défavorable (P5)"), (25, "défavorable (P25)"),
                   (50, "MÉDIANE (P50)"), (75, "favorable (P75)"), (95, "très favorable (P95)")]:
        v = pct(eq, q)
        print(f"  {lab:<26} {v:>12,.2f} €   ({(v / args.capital - 1) * 100:+.0f} %)")
    print(f"  moyenne                    {eq.mean():>12,.2f} €")
    print(f"  meilleur cas               {eq.max():>12,.2f} €")

    print("\n  --- Probabilités ---")
    print(f"  Compte ruiné (< {args.ruin_pct:.0f}% capital) {blown.mean() * 100:>10.1f} %")
    print(f"  En perte                   {(eq < args.capital).mean() * 100:>11.1f} %")
    print(f"  En profit                  {(eq > args.capital).mean() * 100:>11.1f} %")
    print(f"  Compte doublé (×2)         {(eq >= 2 * args.capital).mean() * 100:>11.1f} %")
    print(f"  Compte ×10                 {(eq >= 10 * args.capital).mean() * 100:>11.1f} %")
    print("=" * 60)
    if r["exp_net"] <= 0:
        print("  Espérance négative : à long terme, ce réglage DÉTRUIT le capital,")
        print("  même si quelques simulations chanceuses finissent en profit.")
    print()


if __name__ == "__main__":
    main()
