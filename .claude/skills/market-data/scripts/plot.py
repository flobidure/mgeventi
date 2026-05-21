#!/usr/bin/env python3
"""Génère un graphique PNG à partir d'un CSV de prix."""
import argparse
import sys

import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_prices(path):
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    date_col = next((c for c in df.columns if c.lower() == "date"), None)
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.set_index(date_col)
    return df.apply(pd.to_numeric, errors="coerce")


def main():
    p = argparse.ArgumentParser(description="Graphique de prix.")
    p.add_argument("csv")
    p.add_argument("--type", choices=["price", "compare"], default="price")
    p.add_argument("--sma", type=int, nargs="*", default=[], help="Moyennes mobiles (type=price).")
    p.add_argument("--out", required=True, help="Fichier PNG de sortie.")
    args = p.parse_args()

    df = load_prices(args.csv)
    fig, ax = plt.subplots(figsize=(12, 6))

    if args.type == "price":
        lower = [c.lower() for c in df.columns]
        col = df.columns[lower.index("close")] if "close" in lower else df.columns[0]
        ax.plot(df.index, df[col], label=col, linewidth=1.2)
        for n in args.sma:
            ax.plot(df.index, df[col].rolling(n).mean(), label=f"SMA {n}", linewidth=1)
        ax.set_title(f"Cours — {col}")
        ax.set_ylabel("Prix")
    else:  # compare : base 100
        norm = df / df.iloc[0] * 100
        for c in norm.columns:
            ax.plot(norm.index, norm[c], label=c, linewidth=1.2)
        ax.set_title("Performance comparée (base 100)")
        ax.set_ylabel("Indice (base 100)")
        ax.axhline(100, color="grey", linestyle="--", linewidth=0.8)

    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(args.out, dpi=120)
    print(f"Graphique écrit dans {args.out}")


if __name__ == "__main__":
    main()
