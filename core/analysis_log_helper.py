"""Helpers pour écrire dans analysis_log depuis le graph pipeline.

Dérive country (depuis suffix ticker), market_cap_bucket, universe, etc.
Utilisé dans core/graph.py::output_node.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


# Mapping suffixe ticker → pays (ISO 2 lettres)
_TICKER_COUNTRY = {
    ".PA": "FR",   # Euronext Paris
    ".AS": "NL",   # Amsterdam
    ".BR": "BE",   # Brussels
    ".LS": "PT",   # Lisbon
    ".MC": "ES",   # Madrid
    ".MI": "IT",   # Milan
    ".DE": "DE",   # XETRA
    ".F":  "DE",   # Frankfurt
    ".L":  "UK",   # London
    ".SW": "CH",   # Swiss (SIX)
    ".HE": "FI",   # Helsinki
    ".OL": "NO",   # Oslo
    ".ST": "SE",   # Stockholm
    ".CO": "DK",   # Copenhagen
    ".T":  "JP",   # Tokyo
    ".HK": "HK",   # Hong Kong
    ".SS": "CN",   # Shanghai
    ".SZ": "CN",   # Shenzhen
    ".TO": "CA",   # Toronto
    ".V":  "CA",   # TSX Venture
    ".AX": "AU",   # ASX
    ".NS": "IN",   # NSE India
    ".BO": "IN",   # BSE India
    ".SA": "BR",   # São Paulo
    ".MX": "MX",   # Mexico
}


def derive_country(ticker: Optional[str]) -> Optional[str]:
    """Dérive le pays depuis le suffixe ticker. 'US' si pas de suffixe."""
    if not ticker:
        return None
    for suffix, country in _TICKER_COUNTRY.items():
        if ticker.upper().endswith(suffix):
            return country
    return "US"  # par défaut NYSE/NASDAQ


def market_cap_bucket(mcap_usd: Optional[float]) -> Optional[str]:
    """Classe une market cap en bucket GICS-inspired (en dollars).

    - nano   : < 50M
    - micro  : 50M-300M
    - small  : 300M-2B
    - mid    : 2B-10B
    - large  : 10B-200B
    - mega   : > 200B
    """
    if mcap_usd is None or mcap_usd <= 0:
        return None
    if mcap_usd < 50e6:
        return "nano"
    if mcap_usd < 300e6:
        return "micro"
    if mcap_usd < 2e9:
        return "small"
    if mcap_usd < 10e9:
        return "mid"
    if mcap_usd < 200e9:
        return "large"
    return "mega"


def log_societe_analysis(state: dict, duration_ms: int) -> bool:
    """Extrait les infos de state + écrit dans analysis_log.

    Appelé depuis output_node. Silencieux si Supabase non configuré.
    """
    try:
        from backend.db import insert_analysis_log
        snap = state.get("raw_data")
        ratios = state.get("ratios")
        synthesis = state.get("synthesis")

        ci = snap.company_info if snap else None
        mkt = snap.market if snap else None

        # Market cap : depuis ratios latest_year (plus fiable) sinon market
        mcap_bn = None
        if ratios and getattr(ratios, "years", None):
            try:
                latest = list(ratios.years.values())[-1]
                mc_m = getattr(latest, "market_cap", None)  # en millions USD
                if mc_m:
                    mcap_bn = float(mc_m) / 1000.0  # → Mds USD
            except Exception:
                pass

        # Target upside
        upside_pct = None
        if synthesis and mkt:
            try:
                tb = getattr(synthesis, "target_base", None)
                sp = getattr(mkt, "share_price", None)
                if tb and sp and sp > 0:
                    upside_pct = round((float(tb) - float(sp)) / float(sp) * 100, 2)
            except Exception:
                pass

        # LLM fallback utilisé ?
        _llm_fb = False
        if synthesis and getattr(synthesis, "meta", None):
            _llm_fb = bool(synthesis.meta.get("fallback_mode") or synthesis.meta.get("fallback_reason"))

        # Market cap USD en milliards (pour bucket)
        mcap_usd = mcap_bn * 1e9 if mcap_bn else None

        return insert_analysis_log(
            kind="societe",
            ticker=state.get("ticker") or (ci.ticker if ci else None),
            company_name=(ci.company_name if ci else None),
            sector=(ci.sector if ci else None),
            industry=(getattr(ci, "industry", None) if ci else None),
            country=derive_country(ci.ticker if ci else state.get("ticker")),
            market_cap_bucket=market_cap_bucket(mcap_usd),
            market_cap_usd_bn=round(mcap_bn, 2) if mcap_bn else None,
            score_finsight=None,  # pas de score FinSight single-ticker pour société (recommandation suffit)
            recommendation=(getattr(synthesis, "recommendation", None) if synthesis else None),
            conviction=(getattr(synthesis, "conviction", None) if synthesis else None),
            target_price_base=(getattr(synthesis, "target_base", None) if synthesis else None),
            target_upside_pct=upside_pct,
            language=state.get("language") or "fr",
            currency=state.get("currency") or "EUR",
            duration_ms=duration_ms,
            llm_fallback_used=_llm_fb,
            data_quality="full",
        )
    except Exception as e:
        log.debug(f"[analysis_log] société skip : {e}")
        return False


def log_indice_analysis(data: dict, duration_ms: int, language: str = "fr", currency: str = "EUR") -> bool:
    """Log analyse indice."""
    try:
        from backend.db import insert_analysis_log
        universe = data.get("universe") or data.get("indice")
        return insert_analysis_log(
            kind="indice",
            ticker=data.get("code"),
            company_name=universe,
            universe=universe,
            country=derive_country(data.get("code")) if data.get("code") else None,
            score_finsight=data.get("score_median"),
            recommendation=data.get("signal_global"),
            conviction=(data.get("conviction_pct", 0) / 100) if data.get("conviction_pct") else None,
            language=language,
            currency=currency,
            duration_ms=duration_ms,
            data_quality="full",
        )
    except Exception as e:
        log.debug(f"[analysis_log] indice skip : {e}")
        return False


def log_secteur_analysis(sector: str, universe: str, tickers: list, duration_ms: int,
                          language: str = "fr", currency: str = "EUR") -> bool:
    """Log analyse sectorielle."""
    try:
        from backend.db import insert_analysis_log
        return insert_analysis_log(
            kind="secteur",
            sector=sector,
            universe=universe,
            company_name=f"{sector} — {universe}",
            language=language,
            currency=currency,
            duration_ms=duration_ms,
            data_quality="full" if tickers else "partial",
        )
    except Exception as e:
        log.debug(f"[analysis_log] secteur skip : {e}")
        return False


def log_pme_analysis(siren: str, denomination: str, analysis, duration_ms: int,
                      language: str = "fr") -> bool:
    """Log analyse PME (Pappers)."""
    try:
        from backend.db import insert_analysis_log
        score = getattr(analysis, "health_score", None) if analysis else None
        verdict = getattr(analysis, "altman_verdict", None) if analysis else None
        # Map verdict Altman → recommendation-like
        reco = None
        if verdict == "safe":
            reco = "BUY"  # zone saine
        elif verdict == "grey":
            reco = "HOLD"
        elif verdict == "distress":
            reco = "SELL"
        return insert_analysis_log(
            kind="pme",
            ticker=siren,  # on stocke le SIREN dans ticker pour retrouver facilement
            company_name=denomination,
            country="FR",  # Pappers = France only
            score_finsight=score,
            recommendation=reco,
            language=language,
            currency="EUR",  # PME FR toujours en EUR
            duration_ms=duration_ms,
            data_quality="full",
        )
    except Exception as e:
        log.debug(f"[analysis_log] PME skip : {e}")
        return False
