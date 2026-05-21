---
name: trading-analysis
description: >-
  Analyse technique des marchés, calcul d'indicateurs (SMA, EMA, RSI, MACD,
  Bollinger, ATR), backtesting de stratégies et gestion du risque (taille de
  position, stop-loss, ratio risque/récompense). À utiliser pour analyser des
  séries de prix (actions, crypto, forex), tester une stratégie de trading sur
  données historiques, ou dimensionner une position selon le risque.
---

# Trading Analysis

Boîte à outils d'analyse technique et de backtesting. Les scripts attendent un
CSV de cours OHLCV avec au minimum une colonne `close` (et `date` en index ou
première colonne). Les colonnes `open`, `high`, `low`, `volume` sont utilisées
quand elles sont disponibles.

## Installation des dépendances

```bash
pip install -r .claude/skills/trading-analysis/requirements.txt
```

## Indicateurs techniques

`scripts/indicators.py` ajoute les indicateurs à un CSV de prix.

```bash
python .claude/skills/trading-analysis/scripts/indicators.py prices.csv \
    --indicators sma:20 ema:50 rsi:14 macd bollinger:20:2 atr:14 \
    --out prices_with_indicators.csv
```

Indicateurs disponibles : `sma:<période>`, `ema:<période>`, `rsi:<période>`,
`macd[:rapide:lent:signal]`, `bollinger:<période>:<écarts-types>`,
`atr:<période>`, `stoch:<période>`.

## Backtesting

`scripts/backtest.py` teste une stratégie simple sur données historiques et
renvoie les métriques de performance (rendement total, Sharpe, drawdown max,
taux de réussite).

```bash
# Croisement de moyennes mobiles
python .claude/skills/trading-analysis/scripts/backtest.py prices.csv \
    --strategy sma_cross --fast 20 --slow 50

# Stratégie RSI (achat survente / vente surachat)
python .claude/skills/trading-analysis/scripts/backtest.py prices.csv \
    --strategy rsi --rsi-period 14 --oversold 30 --overbought 70
```

Stratégies : `sma_cross`, `ema_cross`, `rsi`, `bollinger`, `buy_hold`.

## Gestion du risque

`scripts/risk.py` calcule la taille de position et les niveaux de stop.

```bash
# Taille de position selon le risque par trade
python .claude/skills/trading-analysis/scripts/risk.py position \
    --capital 10000 --risk-pct 1 --entry 100 --stop 95

# Métriques d'un trade (R:R, gain/perte, breakeven win rate)
python .claude/skills/trading-analysis/scripts/risk.py trade \
    --entry 100 --stop 95 --target 115
```

## Workflow recommandé

1. Récupérer les données avec le skill `market-data` (ou un CSV fourni).
2. Calculer les indicateurs avec `indicators.py`.
3. Tester l'idée de stratégie avec `backtest.py`.
4. Dimensionner les positions avec `risk.py` avant d'exécuter.

Toujours rappeler que les performances passées ne préjugent pas des résultats
futurs et que ces outils sont éducatifs, pas des conseils en investissement.
