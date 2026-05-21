#!/usr/bin/env python3
"""Télécharge l'historique de marché via yfinance et l'écrit en CSV."""
import argparse
import sys


def main():
    p = argparse.ArgumentParser(description="Télécharge des données de marché (yfinance).")
    p.add_argument("tickers", nargs="+", help="Un ou plusieurs symboles (ex: AAPL BTC-USD).")
    p.add_argument("--period", default="1y", help="1mo, 6mo, 1y, 2y, 5y, max...")
    p.add_argument("--interval", default="1d", help="1d, 1wk, 1mo, 1h...")
    p.add_argument("--start", help="Date de début YYYY-MM-DD (prioritaire sur --period).")
    p.add_argument("--end", help="Date de fin YYYY-MM-DD.")
    p.add_argument("--out", required=True, help="Chemin du CSV de sortie.")
    args = p.parse_args()

    try:
        import yfinance as yf
    except ImportError:
        sys.exit("yfinance non installé. Lancer : pip install -r requirements.txt")

    kwargs = {"interval": args.interval, "auto_adjust": True, "progress": False}
    if args.start:
        kwargs["start"] = args.start
        if args.end:
            kwargs["end"] = args.end
    else:
        kwargs["period"] = args.period

    data = yf.download(args.tickers, **kwargs)
    if data.empty:
        sys.exit("Aucune donnée récupérée (ticker invalide ou réseau indisponible ?).")

    if len(args.tickers) == 1:
        # OHLCV complet pour un seul ticker
        df = data.copy()
        df.columns = [c.lower() if isinstance(c, str) else str(c).lower() for c in df.columns]
        df.index.name = "date"
        df.to_csv(args.out)
    else:
        # Matrice de prix de clôture pour plusieurs tickers
        close = data["Close"] if "Close" in data.columns.get_level_values(0) else data
        close.index.name = "date"
        close.to_csv(args.out)

    print(f"Écrit dans {args.out} : {len(data)} lignes pour {', '.join(args.tickers)}.")


if __name__ == "__main__":
    main()
