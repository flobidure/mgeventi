"""Chargement et normalisation des relevés bancaires CSV."""
import re
import sys
import unicodedata

import pandas as pd

DATE_NAMES = ["date", "date operation", "date de l'operation", "date valeur", "transaction date"]
LABEL_NAMES = ["libelle", "label", "description", "nature", "details", "narrative", "memo", "intitule"]
AMOUNT_NAMES = ["montant", "amount", "valeur"]
DEBIT_NAMES = ["debit", "depense", "withdrawal"]
CREDIT_NAMES = ["credit", "recette", "deposit"]


def _strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _norm(s):
    return _strip_accents(str(s).strip().lower())


def _find(cols_norm, candidates):
    for cand in candidates:
        for orig, n in cols_norm.items():
            if n == cand:
                return orig
    # match partiel
    for cand in candidates:
        for orig, n in cols_norm.items():
            if cand in n:
                return orig
    return None


def _parse_one_amount(raw):
    s = re.sub(r"[^\d,.\-]", "", str(raw))
    if not s or s in ("-", ".", ","):
        return None
    has_comma, has_dot = "," in s, "." in s
    if has_comma and has_dot:
        # Le dernier séparateur rencontré est le séparateur décimal.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")  # FR : 1.234,56
        else:
            s = s.replace(",", "")  # US : 1,234.56
    elif has_comma:
        # Virgule seule : décimale si elle isole 1-2 chiffres, sinon milliers.
        if re.search(r",\d{1,2}$", s):
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_dot:
        # Point seul : milliers si groupe de 3 chiffres exactement (ex: 1.234).
        if re.search(r"\.\d{3}$", s) and not re.search(r"\.\d{1,2}$", s):
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_amount(series):
    return pd.to_numeric(series.map(_parse_one_amount), errors="coerce")


def load_transactions(path):
    try:
        df = pd.read_csv(path, sep=None, engine="python")
    except Exception:
        df = pd.read_csv(path, sep=";")

    cols_norm = {c: _norm(c) for c in df.columns}

    date_col = _find(cols_norm, DATE_NAMES)
    label_col = _find(cols_norm, LABEL_NAMES)
    amount_col = _find(cols_norm, AMOUNT_NAMES)
    debit_col = _find(cols_norm, DEBIT_NAMES)
    credit_col = _find(cols_norm, CREDIT_NAMES)

    if label_col is None:
        sys.exit("Erreur : impossible de trouver une colonne de libellé/description.")

    out = pd.DataFrame()
    out["libelle"] = df[label_col].astype(str)

    if date_col is not None:
        out["date"] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
    else:
        out["date"] = pd.NaT

    if amount_col is not None:
        out["montant"] = _parse_amount(df[amount_col])
    elif debit_col is not None or credit_col is not None:
        debit = _parse_amount(df[debit_col]).fillna(0) if debit_col else 0
        credit = _parse_amount(df[credit_col]).fillna(0) if credit_col else 0
        out["montant"] = credit - debit
    else:
        sys.exit("Erreur : impossible de trouver une colonne de montant (ou débit/crédit).")

    out = out.dropna(subset=["montant"])
    out["mois"] = out["date"].dt.to_period("M").astype(str)
    return out
