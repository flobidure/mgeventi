#!/usr/bin/env python3
"""Résumé mensuel des dépenses, revenus et taux d'épargne."""
import argparse

import pandas as pd

from common import load_transactions


def main():
    p = argparse.ArgumentParser(description="Résumé d'un relevé bancaire.")
    p.add_argument("csv")
    p.add_argument("--month", help="Filtrer un mois (format YYYY-MM).")
    args = p.parse_args()

    df = load_transactions(args.csv)
    if "categorie" not in df.columns:
        df["categorie"] = "Non classé"
    # Conserve la catégorie si déjà présente dans le CSV source
    raw = pd.read_csv(args.csv, sep=None, engine="python")
    raw.columns = [c.strip().lower() for c in raw.columns]
    if "categorie" in raw.columns and len(raw) == len(df):
        df["categorie"] = raw["categorie"].values

    if args.month:
        df = df[df["mois"] == args.month]
        if df.empty:
            print(f"Aucune transaction pour {args.month}.")
            return

    revenus = df[df["montant"] > 0]["montant"].sum()
    depenses = df[df["montant"] < 0]["montant"].sum()
    net = revenus + depenses
    taux_epargne = (net / revenus * 100) if revenus else 0

    titre = f"Résumé {args.month}" if args.month else "Résumé global"
    print(f"\n{titre}")
    print("=" * 50)
    print(f"  Revenus           {revenus:>12,.2f}")
    print(f"  Dépenses          {depenses:>12,.2f}")
    print(f"  Solde net         {net:>12,.2f}")
    print(f"  Taux d'épargne    {taux_epargne:>11.1f} %")

    print("\nDépenses par catégorie :")
    print("-" * 50)
    cats = (
        df[df["montant"] < 0]
        .groupby("categorie")["montant"]
        .sum()
        .sort_values()
    )
    for cat, montant in cats.items():
        pct = montant / depenses * 100 if depenses else 0
        print(f"  {cat:<22} {montant:>12,.2f}  ({pct:4.1f}%)")

    if not args.month and df["mois"].nunique() > 1:
        print("\nÉvolution mensuelle (solde net) :")
        print("-" * 50)
        monthly = df.groupby("mois")["montant"].sum()
        for mois, montant in monthly.items():
            print(f"  {mois}   {montant:>12,.2f}")


if __name__ == "__main__":
    main()
