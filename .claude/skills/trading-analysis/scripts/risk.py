#!/usr/bin/env python3
"""Gestion du risque : taille de position et métriques de trade."""
import argparse


def position_size(capital, risk_pct, entry, stop):
    risk_amount = capital * (risk_pct / 100)
    per_unit_risk = abs(entry - stop)
    if per_unit_risk == 0:
        raise SystemExit("Erreur : entrée et stop ne peuvent pas être égaux.")
    units = risk_amount / per_unit_risk
    notional = units * entry
    return {
        "capital": capital,
        "risque_par_trade": round(risk_amount, 2),
        "risque_par_unité": round(per_unit_risk, 4),
        "quantité": round(units, 4),
        "valeur_position": round(notional, 2),
        "exposition_%_du_capital": round(notional / capital * 100, 2),
    }


def trade_metrics(entry, stop, target):
    risk = abs(entry - stop)
    reward = abs(target - entry)
    if risk == 0:
        raise SystemExit("Erreur : entrée et stop ne peuvent pas être égaux.")
    rr = reward / risk
    breakeven_wr = 1 / (1 + rr)
    return {
        "entrée": entry,
        "stop": stop,
        "objectif": target,
        "risque_par_unité": round(risk, 4),
        "gain_par_unité": round(reward, 4),
        "ratio_risque_récompense": round(rr, 2),
        "taux_réussite_breakeven_%": round(breakeven_wr * 100, 2),
    }


def main():
    p = argparse.ArgumentParser(description="Outils de gestion du risque.")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("position", help="Calcule la taille de position.")
    ps.add_argument("--capital", type=float, required=True)
    ps.add_argument("--risk-pct", type=float, required=True, help="% du capital risqué.")
    ps.add_argument("--entry", type=float, required=True)
    ps.add_argument("--stop", type=float, required=True)

    pt = sub.add_parser("trade", help="Métriques d'un trade (R:R, breakeven).")
    pt.add_argument("--entry", type=float, required=True)
    pt.add_argument("--stop", type=float, required=True)
    pt.add_argument("--target", type=float, required=True)

    args = p.parse_args()
    if args.cmd == "position":
        result = position_size(args.capital, args.risk_pct, args.entry, args.stop)
    else:
        result = trade_metrics(args.entry, args.stop, args.target)

    for k, v in result.items():
        print(f"  {k:<28} {v}")


if __name__ == "__main__":
    main()
