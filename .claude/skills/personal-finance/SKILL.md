---
name: personal-finance
description: >-
  Gestion de finances personnelles : analyse de relevés bancaires CSV,
  catégorisation automatique des transactions, suivi de budget, calcul du taux
  d'épargne et résumés mensuels de dépenses. À utiliser pour comprendre où part
  l'argent, comparer dépenses réelles vs budget, ou nettoyer/analyser un export
  de compte bancaire.
---

# Personal Finance

Outils d'analyse de relevés bancaires et de budget. Le format d'entrée est un
CSV de transactions avec au minimum une colonne de date, une de libellé/description
et une de montant. Les noms de colonnes sont détectés automatiquement (date,
libellé, montant, label, description, amount, débit, crédit...).

## Installation des dépendances

```bash
pip install -r .claude/skills/personal-finance/requirements.txt
```

## Catégorisation des transactions

`scripts/categorize.py` classe chaque transaction par catégorie via des règles
de mots-clés (modifiables dans `rules.json`).

```bash
python .claude/skills/personal-finance/scripts/categorize.py releve.csv \
    --out releve_categorise.csv
```

Les catégories par défaut couvrent : alimentation, transport, logement, santé,
loisirs, abonnements, revenus, etc. Adapter `scripts/rules.json` aux commerçants
spécifiques de l'utilisateur améliore beaucoup la précision.

## Résumé mensuel et taux d'épargne

`scripts/summary.py` agrège les transactions par mois et par catégorie.

```bash
python .claude/skills/personal-finance/scripts/summary.py releve_categorise.csv

# Filtrer sur un mois précis
python .claude/skills/personal-finance/scripts/summary.py releve_categorise.csv --month 2026-04
```

Affiche revenus, dépenses, solde net, taux d'épargne et top des catégories.

## Suivi de budget

`scripts/budget.py` compare les dépenses réelles aux limites définies dans un
fichier budget JSON (`budget.example.json` fourni comme modèle).

```bash
python .claude/skills/personal-finance/scripts/budget.py releve_categorise.csv \
    --budget mon_budget.json --month 2026-04
```

## Workflow recommandé

1. Exporter le relevé bancaire en CSV depuis la banque.
2. Catégoriser avec `categorize.py` (ajuster `rules.json` si besoin).
3. Analyser avec `summary.py` pour la vue d'ensemble.
4. Vérifier le respect du budget avec `budget.py`.

Convention de signe : montants négatifs = dépenses, positifs = revenus. Le script
de catégorisation gère aussi les colonnes séparées débit/crédit.
