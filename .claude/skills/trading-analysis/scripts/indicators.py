#!/usr/bin/env python3
"""Calcule des indicateurs techniques et les ajoute à un CSV de prix OHLCV."""
import argparse
import sys

import numpy as np
import pandas as pd


def sma(close, period):
    return close.rolling(window=period, min_periods=period).mean()


def ema(close, period):
    return close.ewm(span=period, adjust=False).mean()


def rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(close, fast=12, slow=26, signal=9):
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line, macd_line - signal_line


def bollinger(close, period=20, num_std=2.0):
    mid = sma(close, period)
    std = close.rolling(window=period, min_periods=period).std()
    return mid + num_std * std, mid, mid - num_std * std


def atr(df, period=14):
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def stochastic(df, period=14):
    low_min = df["low"].rolling(window=period, min_periods=period).min()
    high_max = df["high"].rolling(window=period, min_periods=period).max()
    k = 100 * (df["close"] - low_min) / (high_max - low_min)
    return k, k.rolling(window=3, min_periods=3).mean()


def load_prices(path):
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    if "close" not in df.columns:
        sys.exit("Erreur : le CSV doit contenir une colonne 'close'.")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.set_index("date")
    return df


def main():
    p = argparse.ArgumentParser(description="Ajoute des indicateurs techniques à un CSV.")
    p.add_argument("csv", help="Chemin du CSV de prix OHLCV.")
    p.add_argument(
        "--indicators",
        nargs="+",
        required=True,
        help="Ex: sma:20 ema:50 rsi:14 macd bollinger:20:2 atr:14 stoch:14",
    )
    p.add_argument("--out", help="CSV de sortie (sinon affiche les dernières lignes).")
    args = p.parse_args()

    df = load_prices(args.csv)

    for spec in args.indicators:
        parts = spec.split(":")
        name = parts[0].lower()
        nums = [float(x) for x in parts[1:]]
        try:
            if name == "sma":
                df[f"sma_{int(nums[0])}"] = sma(df["close"], int(nums[0]))
            elif name == "ema":
                df[f"ema_{int(nums[0])}"] = ema(df["close"], int(nums[0]))
            elif name == "rsi":
                period = int(nums[0]) if nums else 14
                df[f"rsi_{period}"] = rsi(df["close"], period)
            elif name == "macd":
                f, s, sig = (int(nums[0]), int(nums[1]), int(nums[2])) if len(nums) == 3 else (12, 26, 9)
                m, signal, hist = macd(df["close"], f, s, sig)
                df["macd"], df["macd_signal"], df["macd_hist"] = m, signal, hist
            elif name == "bollinger":
                period = int(nums[0]) if nums else 20
                std = nums[1] if len(nums) > 1 else 2.0
                up, mid, low = bollinger(df["close"], period, std)
                df["bb_upper"], df["bb_mid"], df["bb_lower"] = up, mid, low
            elif name == "atr":
                df[f"atr_{int(nums[0]) if nums else 14}"] = atr(df, int(nums[0]) if nums else 14)
            elif name == "stoch":
                period = int(nums[0]) if nums else 14
                k, d = stochastic(df, period)
                df[f"stoch_k_{period}"], df[f"stoch_d_{period}"] = k, d
            else:
                print(f"Indicateur inconnu ignoré : {name}", file=sys.stderr)
        except KeyError as e:
            print(f"Colonne manquante pour {name} : {e}", file=sys.stderr)

    if args.out:
        df.to_csv(args.out)
        print(f"Écrit dans {args.out} ({len(df)} lignes, {len(df.columns)} colonnes).")
    else:
        with pd.option_context("display.max_columns", None, "display.width", 200):
            print(df.tail(10))


if __name__ == "__main__":
    main()
