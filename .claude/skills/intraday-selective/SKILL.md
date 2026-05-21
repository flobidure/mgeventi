---
name: intraday-selective
description: >-
  Trading intraday SÉLECTIF (peu de trades/jour, haute qualité) sur bougies
  5m/15m : setups à confluence, Opening Range Breakout, repli de tendance.
  Backtester avec garde-fous de day-trader (plafond de trades/jour, limite de
  pertes journalières, fenêtre horaire, clôture forcée en fin de séance, stops
  ATR) et coûts réalistes. À utiliser pour concevoir et tester une approche
  intraday disciplinée visant < 10 trades/jour, et scanner les setups du moment.
  Fonctionne sur crypto, forex et actions via CSV.
---

# Intraday sélectif

Approche opposée au scalping : **peu de trades, mais triés sur le volet**. Moins
de coûts cumulés, des setups de meilleure qualité, une discipline de séance.
Conçu pour viser **moins de ~10 trades par jour** (souvent 1 à 5).

> Outils de recherche/backtest et d'aide à la décision — **pas** d'exécution
> automatique d'ordres. Éducatif, pas un conseil en investissement.

## Installation

```bash
pip install -r .claude/skills/intraday-selective/requirements.txt
```

Données : un CSV de bougies intraday (`timestamp`/`date`, `open`, `high`, `low`,
`close`, `volume`). Récupérables via le skill `scalping` (`fetch_intraday.py`,
ex. timeframe `5m`/`15m`) ou ton propre export forex/actions.

## Stratégies

- **`orb`** — Opening Range Breakout : on cadre le range des premières minutes de
  la séance, puis on trade la cassure. Naturellement ~1-2 trades/jour.
- **`trend_pullback`** — dans une tendance (EMA20/50), on attend un repli sur la
  VWAP puis la reprise du momentum (RSI repasse 50).
- **`confluence`** — score multi-filtres (tendance, position vs VWAP, RSI, MACD,
  volume) ; on entre seulement quand le score franchit un seuil → peu de signaux.

## Backtester (avec garde-fous + coûts)

```bash
# Opening Range Breakout, max 2 trades/jour, stop après 2 pertes
python .claude/skills/intraday-selective/scripts/backtest.py data_5m.csv \
    --strategy orb --or-minutes 30 --max-trades 2 --max-losses 2 \
    --atr-stop 1.5 --atr-target 2.5 --fee-bps 4

# Confluence stricte (seuil élevé = encore moins de trades)
python .claude/skills/intraday-selective/scripts/backtest.py data_5m.csv \
    --strategy confluence --threshold 4 --max-trades 5 --max-hold 24

# Repli de tendance
python .claude/skills/intraday-selective/scripts/backtest.py data_5m.csv \
    --strategy trend_pullback --max-trades 3
```

Le rapport affiche `trades_par_jour_moyen` **et** `trades_par_jour_max` pour
vérifier la contrainte, plus profit factor, espérance, ratio gain/perte, pertes
consécutives max, drawdown, et la répartition des sorties (stop/objectif/temps/eod).

### Garde-fous disponibles

| Option | Rôle | Défaut |
|---|---|---|
| `--max-trades` | plafond de trades par jour | 5 |
| `--max-losses` | arrêt de la journée après N pertes | 2 |
| `--warmup` | minutes après ouverture avant d'entrer | 15 |
| `--last-entry` | dernière minute d'entrée de la séance | 360 |
| `--cooldown` | barres d'attente après un trade | 10 |
| `--max-hold` | stop temporel en barres (0 = off) | 0 |
| `--atr-stop` / `--atr-target` | stop / objectif en multiples d'ATR | 1.5 / 2.5 |
| `--spread-bps` / `--fee-bps` / `--slippage-bps` | coûts par côté | 1 / 4 / 1 |

Toute position est **clôturée d'office en fin de séance** (rien gardé la nuit).

## Scanner du moment

```bash
python .claude/skills/intraday-selective/scripts/scan.py btc_5m.csv eth_5m.csv \
    --strategy confluence --threshold 4
```

Affiche le signal, le stop et l'objectif (ATR) sur la dernière barre de chaque CSV.

## Workflow recommandé

1. Récupérer des bougies 5m/15m (skill `scalping` → `fetch_intraday.py --timeframe 5m`).
2. Backtester avec coûts ET garde-fous ; ajuster seuil/ATR pour rester < 10 trades/jour.
3. Comparer `--fee-bps 0` vs réel pour voir la robustesse aux coûts.
4. Dimensionner les positions avec `risk.py` du skill `trading-analysis`.
5. `scan.py` pour repérer les setups en cours.

## Pourquoi sélectif > scalping

- Bien moins de coûts cumulés (5 trades/jour vs 300).
- Marge d'erreur plus grande : on vise un ratio gain/perte > 1.5 et on n'a pas
  besoin d'un taux de réussite élevé.
- Discipline intégrée (plafonds, limite de pertes, horaires) = moins de
  sur-trading, le principal tueur de comptes.
