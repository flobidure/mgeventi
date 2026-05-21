#!/usr/bin/env python3
"""Compare les dépenses réelles aux limites d'un budget par catégorie."""
import argparse
import json

import pandas as pd

from common import load_transactions


def main():
    p = argparse.ArgumentParser(description="Suivi de budget par catégorie.")
    p.add_argument("csv", help="Relevé catégorisé (colonne 'categorie' requise).")
    p.add_argument("--budget", required=True, help="Fichier JSON {categorie: limite}.")
    p.add_argument("--month", help="Mois à analyser (YYYY-MM).")
    args = p.parse_args()

    with open(args.budget, encoding="utf-8") as f:
        budget = json.load(f)

    df = load_transactions(args.csv)
    raw = pd.read_csv(args.csv, sep=None, engine="python")
    raw.columns = [c.strip().lower() for c in raw.columns]
    if "categorie" not in raw.columns:
        raise SystemExit("Le CSV doit contenir une colonne 'categorie' (lancer categorize.py d'abord).")
    df["categorie"] = raw["categorie"].values

    if args.month:
        df = df[df["mois"] == args.month]

    depenses = df[df["montant"] < 0].groupby("categorie")["montant"].sum().abs()

    titre = f"Budget {args.month}" if args.month else "Budget (toute la période)"
    print(f"\n{titre}")
    print("=" * 60)
    print(f"  {'Catégorie':<20}{'Dépensé':>12}{'Limite':>12}{'Reste':>12}")
    print("-" * 60)

    total_spent = total_budget = 0
    for cat, limit in budget.items():
        spent = depenses.get(cat, 0.0)
        remaining = limit - spent
        total_spent += spent
        total_budget += limit
        flag = "  DÉPASSÉ" if remaining < 0 else ""
        print(f"  {cat:<20}{spent:>12,.2f}{limit:>12,.2f}{remaining:>12,.2f}{flag}")

    print("-" * 60)
    print(f"  {'TOTAL':<20}{total_spent:>12,.2f}{total_budget:>12,.2f}{total_budget - total_spent:>12,.2f}")

    hors_budget = depenses[~depenses.index.isin(budget.keys())]
    if not hors_budget.empty:
        print("\nCatégories dépensées hors budget :")
        for cat, montant in hors_budget.sort_values(ascending=False).items():
            print(f"  {cat:<20}{montant:>12,.2f}")


if __name__ == "__main__":
    main()
