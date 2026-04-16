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


# ═══════════════════════════════════════════════════════════════════════════════
# SÉRIES FRED — macro transversales + spécifiques par secteur
# ═══════════════════════════════════════════════════════════════════════════════

# Macro transversal (tous secteurs)
SERIES_MACRO = {
    "fed_funds_rate":      "FEDFUNDS",        # Taux directeur Fed (%)
    "treasury_10y":        "GS10",            # Taux 10 ans US (%)
    "treasury_2y":         "GS2",             # Taux 2 ans US (%)
    "cpi_yoy":             "CPIAUCSL",        # CPI (index, calcul YoY)
    "unemployment":        "UNRATE",          # Taux de chômage US (%)
    "credit_spread_baa":   "BAA10Y",          # Spread BAA - 10Y Treasury (%)
    "industrial_prod":     "INDPRO",          # Production industrielle (index)
    "vix":                 "VIXCLS",          # VIX (volatilité implicite)
}

# Séries spécifiques par secteur GICS
SERIES_BY_SECTOR = {
    "Technology": {
        "tech_employment":     "CES6054130001",   # Emploi informatique (milliers)
        "tech_prod":           "IPG3361T3S",      # Production industrielle : ordinateurs & électronique
    },
    "Financial Services": {
        "bank_lending":        "TOTCI",           # Prêts commerciaux & industriels (Mds$)
        "bank_charge_offs":    "CORCCACBS",       # Charge-off rate (%)
        "consumer_credit":     "TOTALSL",         # Crédit consommateur total (Mds$)
    },
    "Energy": {
        "wti_price":           "DCOILWTICO",      # Prix WTI ($/baril)
        "brent_price":         "DCOILBRENTEU",    # Prix Brent ($/baril)
        "natural_gas":         "DHHNGSP",         # Prix gaz naturel Henry Hub ($/MMBtu)
        "energy_prod":         "IPG2111A2S",      # Production industrielle : pétrole & gaz
    },
    "Real Estate": {
        "mortgage_30y":        "MORTGAGE30US",    # Taux hypothécaire 30 ans (%)
        "case_shiller":        "CSUSHPINSA",      # Indice Case-Shiller prix immobilier US
        "housing_starts":      "HOUST",           # Mises en chantier (milliers, annualisé)
        "existing_home_sales": "EXHOSLUSM495S",   # Ventes maisons existantes
    },
    "Utilities": {
        "natural_gas":         "DHHNGSP",         # Prix gaz naturel ($/MMBtu)
        "electricity_price":   "APU000072610",    # Prix électricité résidentiel ($/kWh)
        "energy_consumption":  "TOTALETCBUS",     # Consommation énergie totale US
    },
    "Healthcare": {
        "health_spending":     "HLTHSCPCHCSA",    # Dépenses santé (index)
        "health_employment":   "CES6562000001",   # Emploi santé (milliers)
        "pharma_prod":         "IPG3254N",        # Production pharmaceutique (index)
    },
    "Consumer Discretionary": {
        "consumer_confidence": "UMCSENT",         # Confiance consommateur Michigan
        "retail_sales":        "RSAFS",           # Ventes retail (Mds$, mensuel)
        "auto_sales":          "TOTALSA",         # Ventes automobiles (millions, annualisé)
        "personal_income":     "PI",              # Revenu personnel (Mds$)
    },
    "Consumer Staples": {
        "consumer_confidence": "UMCSENT",         # Confiance consommateur Michigan
        "food_cpi":            "CPIUFDSL",        # CPI alimentaire (index)
        "retail_sales":        "RSAFS",           # Ventes retail
    },
    "Industrials": {
        "mfg_employment":      "MANEMP",          # Emploi manufacturier (milliers)
        "durable_goods":       "DGORDER",         # Commandes biens durables (Mds$)
        "capacity_util":       "TCU",             # Taux utilisation capacité (%)
        "industrial_prod":     "INDPRO",          # Production industrielle (index)
    },
    "Materials": {
        "copper_price":        "PCOPPUSDM",       # Prix cuivre ($/lb)
        "ppi_metals":          "WPU101",          # PPI métaux ferreux (index)
        "industrial_prod":     "INDPRO",          # Production industrielle
    },
    "Communication Services": {
        "tech_employment":     "CES6054130001",   # Emploi tech (milliers)
        "ad_spending":         "AABORDI",         # Dépenses publicité (proxy via revenus)
    },
}

# Mapping secteur FR → clé SERIES_BY_SECTOR
_SECTOR_FR_MAP = {
    "technologie": "Technology",
    "technology": "Technology",
    "services financiers": "Financial Services",
    "financial services": "Financial Services",
    "banque": "Financial Services",
    "assurance": "Financial Services",
    "energie": "Energy",
    "energy": "Energy",
    "immobilier": "Real Estate",
    "real estate": "Real Estate",
    "sante": "Healthcare",
    "healthcare": "Healthcare",
    "health care": "Healthcare",
    "consommation discretionnaire": "Consumer Discretionary",
    "consumer discretionary": "Consumer Discretionary",
    "consumer cyclical": "Consumer Discretionary",
    "consommation de base": "Consumer Staples",
    "consumer staples": "Consumer Staples",
    "consumer defensive": "Consumer Staples",
    "industrie": "Industrials",
    "industrials": "Industrials",
    "materiaux": "Materials",
    "materials": "Materials",
    "basic materials": "Materials",
    "services aux collectivites": "Utilities",
    "utilities": "Utilities",
    "communication": "Communication Services",
    "communication services": "Communication Services",
}


def _resolve_sector(sector_name: str) -> str:
    """Résout un nom de secteur (FR ou EN) vers la clé SERIES_BY_SECTOR."""
    s = sector_name.strip().lower()
    return _SECTOR_FR_MAP.get(s, sector_name)


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


def fetch_macro_context(sector_name: str = "") -> dict:
    """Récupère le contexte macroéconomique depuis FRED.

    Args:
        sector_name: nom du secteur (FR ou EN) pour les séries spécifiques.
                     Si vide, ne retourne que les séries transversales.

    Returns:
        dict avec les indicateurs macro. Les clés absentes = données indisponibles.
        Sous-dict "sector" contient les indicateurs spécifiques au secteur.
    """
    if not _FRED_KEY:
        log.info("[fred] Pas de cle FRED -- contexte macro vide")
        return {}

    log.info(f"[fred] Fetch contexte macro FRED (secteur={sector_name or 'global'})...")
    result = {}

    # ── Macro transversal ────────────────────────────────────────────────
    for key, series_id in SERIES_MACRO.items():
        if key == "cpi_yoy":
            result[key] = _yoy_change(series_id)
        elif key == "industrial_prod":
            result["industrial_prod_yoy"] = _yoy_change(series_id)
            result["industrial_prod"] = _latest_value(series_id)
        else:
            result[key] = _latest_value(series_id)

    # Yield curve (2Y-10Y spread)
    if result.get("treasury_10y") and result.get("treasury_2y"):
        result["yield_curve_spread"] = round(
            result["treasury_10y"] - result["treasury_2y"], 2
        )

    # ── Séries spécifiques au secteur ────────────────────────────────────
    sector_data = {}
    if sector_name:
        _sector_key = _resolve_sector(sector_name)
        _sector_series = SERIES_BY_SECTOR.get(_sector_key, {})
        if _sector_series:
            log.info(f"[fred] Fetch {len(_sector_series)} series sectorielles ({_sector_key})")
            for key, series_id in _sector_series.items():
                # Pour les séries de volume/emploi, calculer le YoY aussi
                if any(kw in key for kw in ("employment", "prod", "sales", "starts",
                                             "spending", "credit", "lending", "goods")):
                    sector_data[f"{key}_yoy"] = _yoy_change(series_id)
                    sector_data[key] = _latest_value(series_id)
                else:
                    sector_data[key] = _latest_value(series_id)

    # Filtrer les None
    result = {k: v for k, v in result.items() if v is not None}
    sector_data = {k: v for k, v in sector_data.items() if v is not None}
    if sector_data:
        result["sector"] = sector_data

    log.info(f"[fred] Contexte macro: {len(result)} transversal + {len(sector_data)} sectoriel")
    return result
