#!/usr/bin/env python3
"""Télécharge des bougies intraday via ccxt (crypto). Nécessite un accès réseau."""
import argparse
import sys
import time

FALLBACK = ["binance", "kraken", "coinbase", "kucoin", "okx", "bybit", "kraken"]
TF_MS = {"1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000}


def fetch(exchange_name, symbol, timeframe, days):
    import ccxt

    ex = getattr(ccxt, exchange_name)({"enableRateLimit": True})
    if timeframe not in TF_MS:
        sys.exit(f"Timeframe non géré : {timeframe}. Choix : {list(TF_MS)}")
    now = ex.milliseconds()
    since = now - days * 86_400_000
    step = TF_MS[timeframe]
    all_rows, cursor = [], since
    while cursor < now:
        batch = ex.fetch_ohlcv(symbol, timeframe, since=cursor, limit=1000)
        if not batch:
            break
        all_rows += batch
        cursor = batch[-1][0] + step
        time.sleep(ex.rateLimit / 1000)
        if len(batch) < 1000:
            break
    return all_rows


def main():
    p = argparse.ArgumentParser(description="Récupère des bougies intraday (ccxt).")
    p.add_argument("symbol", help="Ex: BTC/USDT, ETH/USD")
    p.add_argument("--exchange", default="binance", help="Nom ccxt, ou 'auto' pour essayer plusieurs.")
    p.add_argument("--timeframe", default="1m", choices=list(TF_MS))
    p.add_argument("--days", type=float, default=3)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    try:
        import pandas as pd
    except ImportError:
        sys.exit("pandas requis : pip install -r requirements.txt")

    exchanges = FALLBACK if args.exchange == "auto" else [args.exchange]
    rows = None
    for name in exchanges:
        try:
            print(f"Tentative via {name}…", file=sys.stderr)
            rows = fetch(name, args.symbol, args.timeframe, args.days)
            if rows:
                print(f"OK via {name}.", file=sys.stderr)
                break
        except Exception as e:
            print(f"  {name} indisponible : {str(e)[:80]}", file=sys.stderr)
            rows = None

    if not rows:
        sys.exit("Aucune donnée récupérée (réseau bloqué ou symbole/exchange invalide).")

    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = df.drop_duplicates("timestamp").sort_values("timestamp")
    df.to_csv(args.out, index=False)
    print(f"Écrit dans {args.out} : {len(df)} bougies {args.timeframe}.")


if __name__ == "__main__":
    main()
