---
name: market-data
description: >-
  Récupération et analyse de données de marché (actions, ETF, crypto, indices)
  via yfinance, plus outils quant : rendements, volatilité, corrélations,
  ratio de Sharpe, drawdown, optimisation de portefeuille et graphiques. À
  utiliser pour télécharger l'historique d'un ticker, analyser un portefeuille,
  mesurer la corrélation entre actifs ou produire un graphique de cours.
---

# Market Data & Quant

Télécharge des données de marché et fournit des analyses quantitatives. Produit
des CSV compatibles avec le skill `trading-analysis`.

## Installation des dépendances

```bash
pip install -r .claude/skills/market-data/requirements.txt
```

`yfinance` nécessite un accès réseau. Si le réseau est restreint dans cet
environnement, les scripts d'analyse fonctionnent aussi sur un CSV fourni
manuellement.

## Télécharger des données

`scripts/fetch.py` récupère l'historique OHLCV d'un ou plusieurs tickers.

```bash
# Un ticker, 1 an de données journalières
python .claude/skills/market-data/scripts/fetch.py AAPL --period 1y --out aapl.csv

# Plusieurs tickers (matrice de prix de clôture)
python .claude/skills/market-data/scripts/fetch.py AAPL MSFT GOOGL BTC-USD \
    --period 2y --out portfolio.csv

# Plage de dates explicite
python .claude/skills/market-data/scripts/fetch.py SPY --start 2023-01-01 --end 2024-01-01 --out spy.csv
```

## Analyse quantitative

`scripts/analyze.py` calcule les statistiques de rendement/risque sur une
matrice de prix de clôture (une colonne par actif).

```bash
# Statistiques par actif + matrice de corrélation
python .claude/skills/market-data/scripts/analyze.py portfolio.csv

# Performance d'un portefeuille pondéré
python .claude/skills/market-data/scripts/analyze.py portfolio.csv \
    --weights "AAPL=0.4,MSFT=0.3,GOOGL=0.3"
```

Métriques : rendement annualisé, volatilité, Sharpe, Sortino, drawdown max,
corrélations entre actifs.

## Graphiques

`scripts/plot.py` génère un PNG (cours, moyennes mobiles, ou comparaison
normalisée base 100).

```bash
python .claude/skills/market-data/scripts/plot.py aapl.csv --type price --sma 20 50 --out aapl.png
python .claude/skills/market-data/scripts/plot.py portfolio.csv --type compare --out compare.png
```

## Workflow recommandé

1. `fetch.py` pour récupérer les données → CSV.
2. `analyze.py` pour les stats risque/rendement et corrélations.
3. `plot.py` pour visualiser.
4. Passer le CSV au skill `trading-analysis` pour indicateurs et backtests.

Outils éducatifs : ne constituent pas un conseil en investissement.
