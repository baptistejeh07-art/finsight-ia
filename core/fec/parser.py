"""Parser FEC (Fichier des Écritures Comptables) — arrêté 29 juillet 2013.

Format officiel imposé par l'administration fiscale FR. Fichier texte CSV
avec séparateur \\t ou | contenant 18 colonnes obligatoires :
  JournalCode, JournalLib, EcritureNum, EcritureDate, CompteNum,
  CompteLib, CompAuxNum, CompAuxLib, PieceRef, PieceDate, EcritureLib,
  Debit, Credit, EcritureLet, DateLet, ValidDate, Montantdevise, Idevise.

On extrait le compte de résultat + bilan depuis le Plan Comptable Général :
  - 6xxxxx : charges
  - 7xxxxx : produits
  - 1xxxxx-5xxxxx : bilan (immobilisations, circulant, trésorerie, dettes...)

Usage :
    from core.fec import parse_fec, summarize_fec
    entries = parse_fec("data.fec")
    summary = summarize_fec(entries)
    # summary = {revenue, cogs, opex, ebitda, net_income, total_assets, equity, debt}
"""
from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class FECEntry:
    journal_code: str
    journal_lib: str
    ecriture_num: str
    ecriture_date: str            # YYYYMMDD
    compte_num: str               # ex: "707100"
    compte_lib: str
    piece_ref: str
    ecriture_lib: str
    debit: float
    credit: float


def _detect_delimiter(text: str) -> str:
    """FEC utilise soit tab soit pipe selon l'éditeur."""
    first_line = text.split("\n", 1)[0]
    if "\t" in first_line:
        return "\t"
    if "|" in first_line:
        return "|"
    return ";"


def _parse_number(s: str) -> float:
    """FEC : virgule comme séparateur décimal, espaces comme milliers."""
    if not s or s.strip() == "":
        return 0.0
    s = s.strip().replace(" ", "").replace("\u00a0", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def parse_fec(content: str | bytes) -> list[FECEntry]:
    """Parse un FEC (texte ou bytes). Retourne la liste d'écritures."""
    if isinstance(content, bytes):
        # Essaie UTF-8 puis CP1252 (cas fréquent export Sage)
        try:
            content = content.decode("utf-8")
        except UnicodeDecodeError:
            content = content.decode("cp1252", errors="replace")

    delimiter = _detect_delimiter(content)
    reader = csv.reader(io.StringIO(content), delimiter=delimiter, quoting=csv.QUOTE_NONE)
    entries: list[FECEntry] = []
    header = None

    for i, row in enumerate(reader):
        if i == 0:
            # Skip header (names can vary in case/spaces)
            if any("Journal" in str(c) for c in row):
                header = row
                continue
        if len(row) < 13:
            continue
        try:
            entries.append(FECEntry(
                journal_code=row[0].strip(),
                journal_lib=row[1].strip()[:100],
                ecriture_num=row[2].strip(),
                ecriture_date=row[3].strip(),
                compte_num=row[4].strip(),
                compte_lib=row[5].strip()[:200],
                piece_ref=row[8].strip() if len(row) > 8 else "",
                ecriture_lib=row[10].strip()[:200] if len(row) > 10 else "",
                debit=_parse_number(row[11]) if len(row) > 11 else 0.0,
                credit=_parse_number(row[12]) if len(row) > 12 else 0.0,
            ))
        except Exception as e:
            log.debug(f"[fec] skip ligne {i}: {e}")
            continue

    log.info(f"[fec] parsé {len(entries)} écritures (delimiter={delimiter!r})")
    return entries


def summarize_fec(entries: list[FECEntry]) -> dict:
    """Agrège les écritures en compte de résultat + bilan.

    Règles PCG :
      - Comptes 60-65 : charges d'exploitation
      - Compte 66 : charges financières
      - Comptes 70-75 : produits d'exploitation (revenue principal = 70)
      - Compte 76 : produits financiers
      - Comptes 10-15 : capitaux propres
      - Comptes 16-19 : dettes financières + provisions
      - Comptes 20-28 : immobilisations
      - Comptes 30-38 : stocks
      - Comptes 40-47 : créances + dettes court terme
      - Comptes 50-58 : trésorerie + banques
    """
    acc: dict[str, float] = {}  # compte_num_2chars -> solde net

    for e in entries:
        if not e.compte_num:
            continue
        # Classe (1er chiffre) + sous-classe (2 premiers chiffres)
        cls2 = e.compte_num[:2]
        # Produits (classe 7) : crédit - débit (sens normal)
        # Charges (classe 6) : débit - crédit
        # Bilan : à ajuster selon actif/passif
        acc.setdefault(cls2, 0.0)
        acc[cls2] += (e.credit - e.debit)

    # Compte de résultat
    revenue = 0.0
    for p in ("70", "71", "72"):           # ventes + production stockée + immobilisée
        revenue += max(0.0, acc.get(p, 0.0))
    other_operating_income = max(0.0, acc.get("74", 0.0)) + max(0.0, acc.get("75", 0.0))
    financial_income = max(0.0, acc.get("76", 0.0))
    exceptional_income = max(0.0, acc.get("77", 0.0))

    # Charges (on inverse le signe car comptes 6 sont en débit)
    cogs = 0.0                              # achats consommés
    for p in ("60",):
        cogs += max(0.0, -acc.get(p, 0.0))
    opex = 0.0                              # autres services externes + salaires
    for p in ("61", "62", "63", "64"):
        opex += max(0.0, -acc.get(p, 0.0))
    da = max(0.0, -acc.get("68", 0.0))      # dotations amortissements + provisions
    financial_expense = max(0.0, -acc.get("66", 0.0))
    exceptional_expense = max(0.0, -acc.get("67", 0.0))
    tax_expense = max(0.0, -acc.get("69", 0.0))

    ebitda = revenue + other_operating_income - cogs - opex
    ebit = ebitda - da
    net_income = ebit + financial_income - financial_expense + exceptional_income - exceptional_expense - tax_expense

    # Bilan
    immobilisations = sum(max(0.0, -acc.get(p, 0.0)) for p in ("20", "21", "22", "23", "24", "25", "26", "27"))
    stocks = max(0.0, -acc.get("30", 0.0)) + max(0.0, -acc.get("31", 0.0)) + max(0.0, -acc.get("37", 0.0))
    receivables = max(0.0, -acc.get("41", 0.0)) + max(0.0, -acc.get("42", 0.0)) + max(0.0, -acc.get("43", 0.0)) + max(0.0, -acc.get("44", 0.0))
    cash = max(0.0, -acc.get("51", 0.0)) + max(0.0, -acc.get("53", 0.0))

    equity = max(0.0, acc.get("10", 0.0)) + max(0.0, acc.get("11", 0.0)) + max(0.0, acc.get("12", 0.0))
    debt_lt = max(0.0, acc.get("16", 0.0)) + max(0.0, acc.get("17", 0.0))
    debt_st = max(0.0, acc.get("40", 0.0)) + max(0.0, acc.get("42", 0.0)) + max(0.0, acc.get("43", 0.0)) + max(0.0, acc.get("44", 0.0))

    total_assets = immobilisations + stocks + receivables + cash

    return {
        # P&L
        "revenue": round(revenue, 2),
        "cogs": round(cogs, 2),
        "opex": round(opex, 2),
        "ebitda": round(ebitda, 2),
        "da": round(da, 2),
        "ebit": round(ebit, 2),
        "financial_expense": round(financial_expense, 2),
        "tax_expense": round(tax_expense, 2),
        "net_income": round(net_income, 2),
        # Bilan
        "total_assets": round(total_assets, 2),
        "immobilisations": round(immobilisations, 2),
        "stocks": round(stocks, 2),
        "receivables": round(receivables, 2),
        "cash": round(cash, 2),
        "equity": round(equity, 2),
        "debt_lt": round(debt_lt, 2),
        "debt_st": round(debt_st, 2),
        "total_debt": round(debt_lt + debt_st, 2),
        # Ratios
        "ebitda_margin": round(ebitda / revenue * 100, 2) if revenue > 0 else None,
        "net_margin": round(net_income / revenue * 100, 2) if revenue > 0 else None,
        "debt_to_equity": round((debt_lt + debt_st) / equity, 2) if equity > 0 else None,
        # Meta
        "num_entries": len(entries),
        "detected_year": _detect_year(entries),
    }


def _detect_year(entries: list[FECEntry]) -> Optional[str]:
    """Détecte l'exercice en regardant les dates d'écritures."""
    years = set()
    for e in entries[:5000]:
        d = e.ecriture_date
        if d and len(d) >= 4 and d[:4].isdigit():
            years.add(d[:4])
    if not years:
        return None
    if len(years) == 1:
        return list(years)[0]
    return f"{min(years)}-{max(years)}"
