# -*- coding: utf-8 -*-
"""
core/etf_holdings.py — Fetcher des holdings & metriques d'un ETF sectoriel.

Utilise en priorite yfinance `Ticker.funds_data` qui expose :
- top_holdings (top 10 avec weights)
- fund_overview (TER, AUM)
- description

Pour les ETF SPDR US, les top 10 couvrent 50-70% de l'ETF, suffisant pour
un rapport analytique. Pour les iShares STOXX 600, le top 10 couvre 30-50%
(plus disperse). Dans les deux cas, c'est exploitable.

Un cache local 7 jours (logs/cache/etf_holdings/*.json) evite les appels
repetes a yfinance (rate-limiting + latence).

Usage typique :

    from core.etf_holdings import fetch_etf_holdings

    data = fetch_etf_holdings("XLK")
    # -> {
    #     "ticker": "XLK",
    #     "name": "Technology Select Sector SPDR Fund",
    #     "aum_usd": 72_500_000_000,
    #     "ter_bps": 9,
    #     "description": "...",
    #     "holdings": [
    #         {"ticker": "AAPL", "name": "Apple Inc.",         "weight": 0.2142},
    #         {"ticker": "MSFT", "name": "Microsoft Corp.",    "weight": 0.1898},
    #         ...
    #     ],
    #     "fetched_at": "2026-04-14T17:30:00"
    # }
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# CACHE — chemin local + duree de vie
# ═════════════════════════════════════════════════════════════════════════════

_CACHE_DIR = Path(__file__).resolve().parent.parent / "logs" / "cache" / "etf_holdings"
_CACHE_TTL_DAYS = 7


def _cache_path(ticker: str) -> Path:
    """Retourne le chemin du fichier cache pour un ETF."""
    safe = ticker.replace(".", "_").replace("/", "_")
    return _CACHE_DIR / f"{safe}.json"


def _read_cache(ticker: str) -> dict | None:
    """Lit le cache si present et non-expire. None sinon."""
    path = _cache_path(ticker)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        fetched = datetime.fromisoformat(data.get("fetched_at", "1970-01-01"))
        if datetime.now() - fetched > timedelta(days=_CACHE_TTL_DAYS):
            return None
        return data
    except Exception as e:
        log.warning("etf_holdings cache read %s: %s", ticker, e)
        return None


def _write_cache(ticker: str, data: dict) -> None:
    """Ecrit le cache (creation du dir si besoin)."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _cache_path(ticker)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        log.warning("etf_holdings cache write %s: %s", ticker, e)


# ═════════════════════════════════════════════════════════════════════════════
# FETCHER — yfinance funds_data
# ═════════════════════════════════════════════════════════════════════════════

def _fetch_from_yfinance(ticker: str) -> dict | None:
    """Fetch ETF data via yfinance.

    Returns a dict with keys: ticker, name, aum_usd, ter_bps, description,
    holdings (list of {ticker, name, weight}). None si echec.
    """
    try:
        import yfinance as yf
    except ImportError:
        log.warning("etf_holdings : yfinance non installe")
        return None

    try:
        yft = yf.Ticker(ticker)
        info = yft.info or {}
        funds_data = getattr(yft, "funds_data", None)

        # Nom
        name = info.get("longName") or info.get("shortName") or ticker

        # AUM + TER
        aum = info.get("totalAssets") or info.get("netAssets")
        ter = info.get("annualReportExpenseRatio") or info.get("expenseRatio") or 0.0
        try:
            ter_bps = int(round(float(ter) * 10000))
        except (ValueError, TypeError):
            ter_bps = None

        # Description
        description = info.get("longBusinessSummary") or info.get("description") or ""

        # Holdings via funds_data.top_holdings (DataFrame)
        # Le DataFrame a l'index = ticker, colonnes "Name" et "Holding Percent"
        holdings = []
        try:
            if funds_data is not None:
                th = funds_data.top_holdings
                if th is not None and len(th) > 0:
                    for _idx, _row in th.iterrows():
                        h_ticker = str(_idx)
                        # Colonnes DataFrame : "Name" (capital) + "Holding Percent"
                        h_name = _row.get("Name") or _row.get("name") or \
                                 _row.get("holdingName") or h_ticker
                        h_weight = _row.get("Holding Percent")
                        if h_weight is None:
                            h_weight = _row.get("holdingPercent") or _row.get("weight")
                        try:
                            h_weight = float(h_weight) if h_weight is not None else None
                        except (ValueError, TypeError):
                            h_weight = None
                        if h_weight is not None:
                            holdings.append({
                                "ticker": h_ticker,
                                "name":   str(h_name),
                                "weight": h_weight,
                            })
        except Exception as e:
            log.debug("etf_holdings top_holdings %s: %s", ticker, e)

        # Sector weightings (repartition sectorielle pour les ETF diversifies)
        sector_weightings = {}
        try:
            if funds_data is not None:
                sw = funds_data.sector_weightings
                if sw and isinstance(sw, dict):
                    sector_weightings = {k: float(v) for k, v in sw.items()
                                         if v is not None and float(v) > 0}
        except Exception as e:
            log.debug("etf_holdings sector_weightings %s: %s", ticker, e)

        # Fallback holdings : si top_holdings vide, utiliser info['fundHoldings']
        if not holdings:
            _fh = info.get("fundHoldings") or []
            for h in _fh:
                try:
                    holdings.append({
                        "ticker": h.get("symbol", "?"),
                        "name":   h.get("name") or h.get("symbol", "?"),
                        "weight": float(h.get("holdingPercent", 0)),
                    })
                except Exception:
                    pass

        if not holdings:
            log.warning("etf_holdings %s : aucun holding disponible via yfinance", ticker)

        return {
            "ticker":             ticker,
            "name":               name,
            "aum_usd":            aum,
            "ter_bps":            ter_bps,
            "description":        description[:500] if description else "",
            "holdings":           holdings,
            "sector_weightings":  sector_weightings,
            "fetched_at":         datetime.now().isoformat(),
            "source":             "yfinance",
        }
    except Exception as e:
        log.warning("etf_holdings yfinance %s: %s", ticker, e)
        return None


# ═════════════════════════════════════════════════════════════════════════════
# API PUBLIQUE
# ═════════════════════════════════════════════════════════════════════════════

def fetch_etf_holdings(ticker: str, force_refresh: bool = False) -> dict | None:
    """Fetch ETF holdings + metadata. Cache 7j.

    Args:
        ticker : ticker ETF (XLK, EXV1.DE, etc.)
        force_refresh : ignore le cache et re-fetch

    Returns:
        Dict avec holdings + metadata, ou None si indisponible.
    """
    if not ticker:
        return None
    if not force_refresh:
        cached = _read_cache(ticker)
        if cached is not None:
            return cached
    data = _fetch_from_yfinance(ticker)
    if data is not None:
        _write_cache(ticker, data)
    return data


def get_top_holdings(ticker: str, n: int = 10) -> list[dict]:
    """Retourne les N premiers holdings de l'ETF (tries par poids decroissant).

    Args:
        ticker : ticker ETF
        n : nombre max de holdings (defaut 10)

    Returns:
        Liste de dicts {ticker, name, weight} (vide si echec).
    """
    data = fetch_etf_holdings(ticker)
    if not data or not data.get("holdings"):
        return []
    h = sorted(data["holdings"], key=lambda x: x.get("weight", 0) or 0, reverse=True)
    return h[:n]


def get_constituent_tickers(ticker: str) -> list[str]:
    """Retourne uniquement les tickers des holdings (pour fetch yfinance batch).

    Returns:
        Liste de tickers (string), vide si echec.
    """
    holdings = get_top_holdings(ticker, n=100)
    return [h["ticker"] for h in holdings if h.get("ticker")]


def format_aum(aum: float | None) -> str:
    """Format lisible de l'AUM (Mds$ / Mds€).

    Ex: 72500000000 -> '72,5 Mds$'
    """
    if aum is None:
        return "n/d"
    try:
        val = float(aum)
        if val >= 1e9:
            return f"{val / 1e9:.1f} Mds$".replace(".", ",")
        if val >= 1e6:
            return f"{val / 1e6:.0f} M$".replace(".", ",")
        return f"{val:.0f} $"
    except (ValueError, TypeError):
        return "n/d"


def format_ter(ter_bps: int | None) -> str:
    """Format lisible du TER (ex: 9 -> '0,09 %').

    Args:
        ter_bps : TER exprimé en basis points (100 bps = 1 %)
    """
    if ter_bps is None:
        return "n/d"
    try:
        return f"{ter_bps / 100:.2f} %".replace(".", ",")
    except (ValueError, TypeError):
        return "n/d"
