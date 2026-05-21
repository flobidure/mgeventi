#!/usr/bin/env python3
"""Catégorise les transactions d'un relevé bancaire via des règles de mots-clés."""
import argparse
import json
import os
import unicodedata

from common import load_transactions

RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.json")


def _norm(s):
    s = "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")
    return s.lower()


def load_rules(path):
    with open(path, encoding="utf-8") as f:
        rules = json.load(f)
    return {cat: [_norm(k) for k in kws] for cat, kws in rules.items()}


def categorize_label(label, rules):
    text = _norm(label)
    for category, keywords in rules.items():
        if any(kw in text for kw in keywords):
            return category
    return "Non classé"


def main():
    p = argparse.ArgumentParser(description="Catégorise un relevé bancaire CSV.")
    p.add_argument("csv")
    p.add_argument("--rules", default=RULES_PATH, help="Fichier JSON de règles.")
    p.add_argument("--out", help="CSV de sortie (sinon résumé à l'écran).")
    args = p.parse_args()

    df = load_transactions(args.csv)
    rules = load_rules(args.rules)
    df["categorie"] = df["libelle"].apply(lambda x: categorize_label(x, rules))

    n_unclassified = (df["categorie"] == "Non classé").sum()
    print(f"{len(df)} transactions catégorisées, {n_unclassified} non classées.")

    if args.out:
        df.to_csv(args.out, index=False)
        print(f"Écrit dans {args.out}")
        if n_unclassified:
            print("\nLibellés non classés les plus fréquents (à ajouter à rules.json) :")
            top = df[df["categorie"] == "Non classé"]["libelle"].value_counts().head(10)
            for label, count in top.items():
                print(f"  {count:>3}x  {label[:60]}")
    else:
        summary = df.groupby("categorie")["montant"].agg(["count", "sum"]).round(2)
        print(summary.sort_values("sum"))


if __name__ == "__main__":
    main()
