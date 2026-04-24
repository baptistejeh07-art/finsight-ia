# -*- coding: utf-8 -*-
"""
core/llm_guardrails.py — Post-processing des sorties LLM pour détecter les
hallucinations les plus courantes.

Deux catégories de garde-fous :
1. Plages temporelles : repère les années citées hors de la fenêtre de
   contexte (ex: texte qui parle de « 2019-2023 » alors que les données
   couvrent 2022-2025).
2. Tickers/noms de sociétés étrangers à l'univers analysé (ex: rapport
   CAC 40 qui cite Vonovia, un constituant DAX).

Usage :

    from core.llm_guardrails import check_years, check_tickers

    warn = check_years(text, min_year=2022, max_year=2025)
    if warn:
        log.warning(f"[llm-guard] années hors range : {warn}")

    off = check_tickers(text, allowed=["BNP.PA", "AXA.PA", ...],
                         allowed_names=["BNP Paribas", "AXA", ...])
    if off:
        log.warning(f"[llm-guard] tickers étrangers : {off}")

Aucune régénération automatique : le module ne fait que signaler. Les callers
peuvent décider de demander un re-prompt ou de masquer les passages suspects.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

log = logging.getLogger(__name__)


_YEAR_RE = re.compile(r"\b(19[89]\d|20\d{2})\b")


def check_years(text: str,
                min_year: Optional[int] = None,
                max_year: Optional[int] = None) -> list[int]:
    """Retourne la liste triée des années hors de la fenêtre [min_year, max_year].

    Tolère des années futures jusqu'à max_year+2 (projections analystes).
    Si min_year/max_year est None, pas de contrôle côté correspondant.
    """
    if not text:
        return []
    if min_year is None and max_year is None:
        return []
    seen: set[int] = set()
    for m in _YEAR_RE.finditer(text):
        try:
            y = int(m.group(1))
        except ValueError:
            continue
        if min_year is not None and y < min_year:
            seen.add(y)
        if max_year is not None and y > max_year + 2:  # tolérance F+1/F+2
            seen.add(y)
    return sorted(seen)


# Petite liste de tickers/noms connus pour des principaux constituants
# d'indices voisins. Sert de watchlist de détection rapide (ex: si un texte
# CAC 40 cite Vonovia, SAP, Adidas — tous DAX — c'est suspect).
_CROSS_INDEX_FLAGS: dict[str, list[str]] = {
    "DAX":   ["Vonovia", "SAP", "Siemens", "Adidas", "BMW", "Daimler",
              "Allianz", "Deutsche", "Linde", "BASF", "Bayer", "Infineon"],
    "FTSE":  ["AstraZeneca", "HSBC", "Unilever", "BP", "Shell", "GlaxoSmith",
              "Rio Tinto", "Barclays", "Diageo", "Lloyds"],
    "IBEX":  ["Santander", "Iberdrola", "Telef\u00f3nica", "BBVA", "Inditex",
              "Repsol", "Ferrovial"],
    "FTSEMIB": ["ENI", "Enel", "Stellantis Italy", "Ferrari", "UniCredit",
                "Intesa", "Poste Italiane"],
    "SMI":   ["Nestl\u00e9", "Roche", "Novartis", "UBS", "Zurich Insurance",
              "Richemont", "Swisscom"],
    "SP500": ["Apple", "Microsoft", "Amazon", "Google", "Tesla", "Meta",
              "NVIDIA", "JPMorgan", "Exxon"],
    "NIKKEI": ["Toyota", "Sony", "Nintendo", "Mitsubishi", "Honda", "SoftBank"],
}


def check_foreign_index_mentions(text: str,
                                  current_index: Optional[str]) -> list[str]:
    """Retourne la liste des sociétés citées qui appartiennent à un indice
    étranger à `current_index`.

    Heuristique volontairement simple : on parcourt les watchlists des autres
    indices et on ne flagge que celles qui sont citées par nom complet.
    Pas parfait mais attrape les cas les plus grossiers (Vonovia dans un
    rapport CAC 40, AstraZeneca dans un DAX...).
    """
    if not text or not current_index:
        return []
    current = _normalize_index_key(current_index)
    flagged: list[str] = []
    for idx_key, names in _CROSS_INDEX_FLAGS.items():
        if idx_key == current:
            continue
        for name in names:
            # Match entier de mot pour éviter les collisions parasites.
            if re.search(rf"\b{re.escape(name)}\b", text, flags=re.IGNORECASE):
                flagged.append(name)
    # De-dup ordered
    seen = set()
    dedup = []
    for x in flagged:
        if x.lower() in seen:
            continue
        seen.add(x.lower())
        dedup.append(x)
    return dedup


def _normalize_index_key(index: str) -> str:
    s = (index or "").lower().replace(" ", "").replace("&", "").replace("-", "")
    if "cac" in s:
        return "CAC"
    if "dax" in s:
        return "DAX"
    if "ftsemib" in s or "italian" in s or "mib" in s:
        return "FTSEMIB"
    if "ftse" in s:
        return "FTSE"
    if "ibex" in s:
        return "IBEX"
    if "smi" in s or "swiss" in s:
        return "SMI"
    if "sp500" in s or "spx" in s:
        return "SP500"
    if "nikkei" in s or "topix" in s:
        return "NIKKEI"
    return s.upper()


def audit_llm_output(text: str,
                     ticker: Optional[str] = None,
                     index_name: Optional[str] = None,
                     min_year: Optional[int] = None,
                     max_year: Optional[int] = None,
                     context_label: str = "") -> dict:
    """Lance les contrôles et retourne un résumé. Log des warnings au passage.

    Args:
        text : sortie LLM à auditer.
        ticker : ticker de la société analysée (ou None si c'est un indice).
        index_name : nom de l'indice de référence (CAC 40, DAX...).
        min_year/max_year : fenêtre temporelle contextuelle.
        context_label : libellé court pour le logging.

    Returns:
        dict {years_out: [...], foreign_names: [...], flagged: bool}
    """
    years_out = check_years(text, min_year=min_year, max_year=max_year)
    foreign_names: list[str] = []
    if index_name:
        foreign_names = check_foreign_index_mentions(text, index_name)
    flagged = bool(years_out or foreign_names)
    if flagged:
        log.warning(
            "[llm-guard] %s ticker=%s index=%s annees_hors_range=%s "
            "noms_etrangers=%s",
            context_label or "LLM output", ticker, index_name,
            years_out, foreign_names,
        )
    return {
        "years_out": years_out,
        "foreign_names": foreign_names,
        "flagged": flagged,
    }
