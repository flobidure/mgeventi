---
name: scalping
description: >-
  Outils de scalping intraday (timeframes 1m/5m) : récupération de bougies via
  ccxt (crypto), indicateurs rapides (VWAP, ruban d'EMA, RSI/Stoch courts, ATR,
  pics de volume), backtester réaliste intégrant spread + frais + slippage, et
  screener de signaux sur une watchlist. À utiliser pour concevoir, tester de
  façon réaliste et générer des signaux de scalping — PAS pour exécuter des
  ordres automatiquement. Fonctionne sur crypto, forex et actions via CSV.
---

# Scalping intraday

Boîte à outils pour scalper en court terme. Les scripts d'analyse/backtest/screener
fonctionnent sur n'importe quel CSV de bougies intraday (`timestamp/date`, `open`,
`high`, `low`, `close`, `volume`) — donc crypto, forex ou actions.

> ⚠️ **À lire absolument.** Ces outils servent à la **recherche et au backtest**,
> pas à l'exécution automatique. Le scalping fait des centaines de trades : les
> **coûts (spread + frais + slippage)** décident de tout. Un backtest qui les
> ignore est mensonger. Toujours backtester avec des coûts réalistes. Outils
> éducatifs, pas un conseil en investissement.

## Installation

```bash
pip install -r .claude/skills/scalping/requirements.txt
```

## 1. Récupérer des bougies intraday (crypto, via ccxt)

`scripts/fetch_intraday.py` télécharge l'historique paginé d'un exchange.
Nécessite un accès réseau (à lancer sur ta machine, pas dans un environnement
web restreint).

```bash
# 3 jours de bougies 1m BTC/USDT
python .claude/skills/scalping/scripts/fetch_intraday.py BTC/USDT \
    --exchange binance --timeframe 1m --days 3 --out btc_1m.csv

# Essaie plusieurs exchanges jusqu'à en trouver un accessible
python .claude/skills/scalping/scripts/fetch_intraday.py ETH/USDT \
    --exchange auto --timeframe 5m --days 7 --out eth_5m.csv
```

Pour le **forex/actions**, fournis ton propre CSV intraday (mêmes colonnes) —
les scripts ci-dessous l'acceptent directement.

## 2. Indicateurs de scalping

`scripts/scalp_indicators.py` ajoute les indicateurs courts adaptés au scalping.

```bash
python .claude/skills/scalping/scripts/scalp_indicators.py btc_1m.csv --out btc_ind.csv
```

Ajoute : `vwap` (réinitialisé par jour), ruban `ema_5/8/13/21`, `rsi_7`,
`stoch_k/d`, `atr_14`, `vol_z` (z-score de volume sur 20 barres, détecte les pics).

## 3. Backtest réaliste (avec coûts)

`scripts/scalp_backtest.py` simule trade par trade avec spread, frais et slippage,
et sortie par stop/objectif basés sur l'ATR.

```bash
# Stratégie ruban d'EMA, coûts en points de base (bps)
python .claude/skills/scalping/scripts/scalp_backtest.py btc_1m.csv \
    --strategy ema_ribbon --spread-bps 1 --fee-bps 4 --slippage-bps 1 \
    --atr-stop 1.0 --atr-target 1.5

# Réversion à la VWAP
python .claude/skills/scalping/scripts/scalp_backtest.py btc_1m.csv \
    --strategy vwap_reversion --fee-bps 4

# Cassure (Donchian)
python .claude/skills/scalping/scripts/scalp_backtest.py btc_1m.csv \
    --strategy breakout --lookback 20 --fee-bps 4
```

Stratégies : `ema_ribbon`, `vwap_reversion`, `breakout`.
Métriques : rendement net, profit factor, espérance par trade, taux de réussite,
trades/jour, pertes consécutives max, drawdown — **net de coûts**.

> Astuce : lance toujours le même backtest avec `--fee-bps 0` puis avec tes vrais
> coûts. L'écart te montre combien les frais mangent ta stratégie.

## 4. Screener de signaux

`scripts/screener.py` évalue le signal actuel sur une liste de CSV.

```bash
python .claude/skills/scalping/scripts/screener.py btc_1m.csv eth_5m.csv \
    --strategy ema_ribbon
```

## Workflow recommandé

1. `fetch_intraday.py` (ou ton CSV) → bougies 1m/5m.
2. `scalp_indicators.py` pour visualiser/comprendre.
3. `scalp_backtest.py` **avec coûts réalistes** — itérer sur la stratégie.
4. `screener.py` pour repérer les setups en cours.
5. Dimensionner avec `risk.py` du skill `trading-analysis`.

## Réalité du scalping (à garder en tête)

- Les coûts dominent : 200 trades × 5 bps = 100 % de capital en frais cumulés sur le notional tradé. Vise un edge largement supérieur aux coûts.
- L'exécution live à basse latence n'est pas faisable avec un script lancé à la main : ces outils préparent la décision, ils ne tradent pas seuls.
- Backtester sur bougies sous-estime spread/slippage réels : sois conservateur sur les `bps`.
