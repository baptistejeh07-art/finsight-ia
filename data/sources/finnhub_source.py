# =============================================================================
# FinSight IA — Source 3 : Finnhub
# data/sources/finnhub_source.py
#
# News, métriques marché, sentiment, earnings. Plan gratuit généreux.
# Complémentaire pour : beta, P/E, EV/EBITDA, news (Agent Veille Phase 1).
# =============================================================================

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Optional

log = logging.getLogger(__name__)


def _client():
    import finnhub
    from core.secrets import get_secret
    return finnhub.Client(api_key=get_secret("FINNHUB_API_KEY") or "")


def _base_ticker(ticker: str) -> str:
    """Finnhub ne supporte pas les extensions .PA, .L etc. pour les métriques."""
    return ticker.split(".")[0]


def fetch_market_metrics(ticker: str) -> dict:
    """
    Collecte métriques marché via Finnhub :
    - beta, P/E TTM, EV/EBITDA, ROE, gross margin
    - cours temps réel
    Retourne un dict (peut être partiellement vide si ticker EU non supporté).
    """
    result: dict = {}
    try:
        client = _client()
        base = _base_ticker(ticker)

        # Quote temps réel
        quote = {}
        try:
            quote = client.quote(ticker) or client.quote(base) or {}
        except Exception:
            pass

        # Métriques fondamentales
        metrics_raw: dict = {}
        try:
            data = client.company_basic_financials(ticker, "all") or {}
            metrics_raw = data.get("metric", {})
            if not metrics_raw:
                data = client.company_basic_financials(base, "all") or {}
                metrics_raw = data.get("metric", {})
        except Exception:
            pass

        result = {
            "quote_price":    quote.get("c"),
            "beta":           metrics_raw.get("beta"),
            "pe_ttm":         metrics_raw.get("peBasicExclExtraTTM"),
            "ev_ebitda":      metrics_raw.get("evToEbitda"),
            "roe":            metrics_raw.get("roeTTM"),
            "gross_margin":   metrics_raw.get("grossMarginTTM"),
            "debt_to_equity": metrics_raw.get("totalDebt/totalEquityAnnual"),
            "revenue_ttm":    metrics_raw.get("revenuePerShareTTM"),
        }

    except Exception as e:
        log.warning(f"[Finnhub] Erreur metriques '{ticker}': {e}")

    return {k: v for k, v in result.items() if v is not None}


def fetch_news(ticker: str, days: int = 7) -> list[dict]:
    """
    News récentes pour un ticker (Agent Veille).
    Retourne une liste de dicts avec headline, summary, source, datetime, url.
    """
    try:
        client = _client()
        base  = _base_ticker(ticker)
        end   = date.today().isoformat()
        start = (date.today() - timedelta(days=days)).isoformat()

        news = client.company_news(base, _from=start, to=end) or []
        return [
            {
                "headline": n.get("headline", ""),
                "summary":  n.get("summary", ""),
                "source":   n.get("source", ""),
                "datetime": n.get("datetime"),
                "url":      n.get("url", ""),
            }
            for n in news[:10]
        ]
    except Exception as e:
        log.warning(f"[Finnhub] Erreur news '{ticker}': {e}")
        return []
