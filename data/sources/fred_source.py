# -*- coding: utf-8 -*-
"""
data/sources/fred_source.py — Données macroéconomiques FRED (Federal Reserve).

Fournit des indicateurs macro sectoriels pour enrichir les rapports PDF sectoriels :
- Production industrielle par secteur
- Taux directeur Fed, spread crédit, inflation
- Emploi sectoriel, PIB

Usage :
    from data.sources.fred_source import fetch_macro_context

    macro = fetch_macro_context()
    # macro = {
    #     "fed_funds_rate": 5.25,
    #     "cpi_yoy": 3.2,
    #     "gdp_growth": 2.1,
    #     "credit_spread_baa": 1.8,
    #     "industrial_prod_yoy": 1.5,
    #     "unemployment": 4.1,
    #     ...
    # }
"""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Optional

log = logging.getLogger(__name__)

_FRED_KEY = os.getenv("FRED_API_KEY", "")
_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


# Séries FRED utiles pour l'analyse sectorielle
SERIES = {
    "fed_funds_rate":      "FEDFUNDS",        # Taux directeur Fed (%)
    "treasury_10y":        "GS10",            # Taux 10 ans US (%)
    "treasury_2y":         "GS2",             # Taux 2 ans US (%)
    "cpi_yoy":             "CPIAUCSL",        # CPI (index, calcul YoY)
    "gdp_real":            "GDPC1",           # PIB réel US (Mds$, trimestriel)
    "unemployment":        "UNRATE",          # Taux de chômage US (%)
    "credit_spread_baa":   "BAA10Y",          # Spread BAA - 10Y Treasury (%)
    "industrial_prod":     "INDPRO",          # Production industrielle (index)
    "tech_employment":     "CES6054130001",   # Emploi secteur informatique (milliers)
    "vix":                 "VIXCLS",          # VIX (volatilité implicite)
}


def _fetch_series(series_id: str, limit: int = 24) -> list[dict]:
    """Fetch les dernières observations d'une série FRED."""
    if not _FRED_KEY:
        log.warning("[fred] FRED_API_KEY non configurée — skip")
        return []
    try:
        import requests
        params = {
            "series_id": series_id,
            "api_key": _FRED_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }
        resp = requests.get(_BASE_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("observations", [])
    except Exception as e:
        log.warning(f"[fred] Erreur fetch {series_id}: {e}")
        return []


def _latest_value(series_id: str) -> Optional[float]:
    """Retourne la dernière valeur non-nulle d'une série."""
    obs = _fetch_series(series_id, limit=5)
    for o in obs:
        val = o.get("value", ".")
        if val != "." and val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                continue
    return None


def _yoy_change(series_id: str) -> Optional[float]:
    """Calcule le changement YoY (%) d'une série mensuelle."""
    obs = _fetch_series(series_id, limit=15)
    if len(obs) < 13:
        return None
    try:
        current = float(obs[0]["value"])
        year_ago = float(obs[12]["value"])
        if year_ago == 0:
            return None
        return round((current - year_ago) / year_ago * 100, 2)
    except (ValueError, TypeError, KeyError):
        return None


def fetch_macro_context() -> dict:
    """Récupère le contexte macroéconomique depuis FRED.

    Returns:
        dict avec les indicateurs macro. Les clés absentes = données indisponibles.
    """
    if not _FRED_KEY:
        log.info("[fred] Pas de clé FRED — contexte macro vide")
        return {}

    log.info("[fred] Fetch contexte macro FRED...")
    result = {}

    # Taux et spreads
    result["fed_funds_rate"] = _latest_value("FEDFUNDS")
    result["treasury_10y"] = _latest_value("GS10")
    result["treasury_2y"] = _latest_value("GS2")
    result["credit_spread_baa"] = _latest_value("BAA10Y")
    result["vix"] = _latest_value("VIXCLS")
    result["unemployment"] = _latest_value("UNRATE")

    # YoY changes
    result["cpi_yoy"] = _yoy_change("CPIAUCSL")
    result["industrial_prod_yoy"] = _yoy_change("INDPRO")
    result["tech_employment_yoy"] = _yoy_change("CES6054130001")

    # Yield curve (2Y-10Y spread)
    if result.get("treasury_10y") and result.get("treasury_2y"):
        result["yield_curve_spread"] = round(
            result["treasury_10y"] - result["treasury_2y"], 2
        )

    # Filtrer les None
    result = {k: v for k, v in result.items() if v is not None}

    log.info(f"[fred] Contexte macro: {len(result)} indicateurs récupérés")
    return result
