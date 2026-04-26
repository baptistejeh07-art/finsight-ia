# =============================================================================
# FinSight IA — Agent Data
# agents/agent_data.py
#
# Collecte pure — zéro raisonnement LLM (brief §3 : "Ne fait aucun raisonnement")
# Orchestrateur multi-sources avec fallback automatique.
#
# Priorité des sources (brief §3) :
#   1. yfinance  — cotées, historique 5 ans, illimité
#   2. FMP       — fondamentaux européens, non-cotées, 250 req/jour
#   3. Finnhub   — métriques complémentaires, news
# =============================================================================

from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

from data.models import FinancialSnapshot, FinancialYear, MarketData
from data.sources import yfinance_source, fmp_source, finnhub_source
from logs.db_logger import log_request

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Merge helpers — priorité source 1, comble les gaps avec source 2
# ---------------------------------------------------------------------------

def _merge_year(primary: FinancialYear, secondary: FinancialYear) -> FinancialYear:
    """Fusionne deux FinancialYear : primary prioritaire, secondary remplit les None."""
    merged = FinancialYear(year=primary.year)
    for fname in merged.__dataclass_fields__:
        if fname == "year":
            continue
        p_val = getattr(primary, fname)
        s_val = getattr(secondary, fname)
        setattr(merged, fname, p_val if p_val is not None else s_val)
    return merged


def _merge_market(p: MarketData, s: MarketData) -> MarketData:
    merged = MarketData()
    for fname in merged.__dataclass_fields__:
        p_val = getattr(p, fname)
        s_val = getattr(s, fname)
        setattr(merged, fname, p_val if p_val is not None else s_val)
    return merged


def _merge_snapshots(
    primary: Optional[FinancialSnapshot],
    secondary: Optional[FinancialSnapshot],
) -> Optional[FinancialSnapshot]:
    """Fusionne deux snapshots : primary prioritaire, secondary comble les gaps."""
    if primary is None:
        return secondary
    if secondary is None:
        return primary

    # Années
    all_years = set(primary.years) | set(secondary.years)
    merged_years: dict[str, FinancialYear] = {}
    for year in all_years:
        p_fy = primary.years.get(year)
        s_fy = secondary.years.get(year)
        if p_fy and s_fy:
            merged_years[year] = _merge_year(p_fy, s_fy)
        else:
            merged_years[year] = p_fy or s_fy

    # Market data
    merged_market = _merge_market(primary.market, secondary.market)

    # Stock history : prendre le plus complet
    stock_hist = primary.stock_history if primary.stock_history else secondary.stock_history

    # Company info : primary prioritaire, fallback secondary CHAMP PAR CHAMP
    # Bug TSLA 2026-04-14 : yfinance peut renvoyer sector="" pour certains
    # tickers en rate-limit, et le fallback complet ne marche que si
    # company_name est vide aussi. Fix : fallback field-by-field.
    from dataclasses import fields as _dc_fields, replace as _dc_replace
    ci = primary.company_info
    s_ci = secondary.company_info
    _updates = {}
    for _f in _dc_fields(ci):
        _p_val = getattr(ci, _f.name, None)
        _s_val = getattr(s_ci, _f.name, None)
        # Si primary est vide (None ou "") ET secondary a une valeur, fallback
        if (not _p_val or _p_val in ("", "N/A")) and _s_val and _s_val not in ("", "N/A"):
            _updates[_f.name] = _s_val
    if _updates:
        ci = _dc_replace(ci, **_updates)

    # Traçabilité sources
    sources = []
    for snap in [primary, secondary]:
        src = snap.meta.get("source", "")
        if src and src not in sources:
            sources.append(src)

    return FinancialSnapshot(
        ticker        = primary.ticker,
        company_info  = ci,
        years         = merged_years,
        market        = merged_market,
        stock_history = stock_hist,
        meta          = {"source": "+".join(sources)},
    )


# ---------------------------------------------------------------------------
# Agent Data
# ---------------------------------------------------------------------------

class AgentData:
    """
    Agent Data — collecte pure, zéro LLM.

    Constitution §1 : chaque output contient
      - confidence_score  : couverture moyenne des champs (0.0–1.0)
      - invalidation_conditions : conditions dans lesquelles les données seraient fausses

    Usage :
        agent = AgentData()
        snapshot = agent.collect("MC.PA")
        print(snapshot.meta["confidence_score"])
    """

    def collect(self, ticker: str) -> Optional[FinancialSnapshot]:
        """
        Collecte toutes les données financières pour un ticker.

        Returns:
            FinancialSnapshot complet, ou None si aucune source ne répond.
        """
        request_id = str(uuid.uuid4())
        t_start    = time.time()

        log.info(f"[AgentData] Debut collecte '{ticker}' — {request_id[:8]}")

        # ------------------------------------------------------------------
        # Sources 1, 2 & 3 en parallèle : yfinance + FMP + Finnhub
        # Finnhub est independent (ne complète que beta_levered et share_price
        # post-merge), donc safe à paralléliser. Gain : ~1-2s/ticker (réseau
        # blocking time réduit). Audit perf 26/04/2026 — agent suggestion P1 #4.
        # ------------------------------------------------------------------
        with ThreadPoolExecutor(max_workers=3) as pool:
            f_yf  = pool.submit(yfinance_source.fetch, ticker)
            f_fmp = pool.submit(fmp_source.fetch, ticker)
            f_fh  = pool.submit(finnhub_source.fetch_market_metrics, ticker)

        snapshot = f_yf.result()
        fmp_snap = f_fmp.result()
        finnhub_metrics = f_fh.result() or {}
        sources_tried = ["yfinance", "fmp", "finnhub"]
        snapshot = _merge_snapshots(snapshot, fmp_snap)

        if snapshot is None:
            log.error(f"[AgentData] '{ticker}' : aucune donnée (yfinance + FMP)")
            return None

        mkt = snapshot.market
        if mkt.beta_levered is None and finnhub_metrics.get("beta"):
            mkt.beta_levered = finnhub_metrics["beta"]
        if mkt.share_price is None and finnhub_metrics.get("quote_price"):
            mkt.share_price = finnhub_metrics["quote_price"]

        # ------------------------------------------------------------------
        # Métadonnées (constitution §1 — confiance + invalidation obligatoires)
        # ------------------------------------------------------------------
        latency_ms = int((time.time() - t_start) * 1000)

        coverages = [fy.coverage() for fy in snapshot.years.values() if fy]
        confidence = round(sum(coverages) / len(coverages), 2) if coverages else 0.0

        snapshot.meta.update({
            "request_id":   request_id,
            "timestamp":    datetime.utcnow().isoformat(),
            "ticker":       ticker.upper(),
            "sources_tried": sources_tried,
            "source":       snapshot.meta.get("source", "unknown"),
            "latency_ms":   latency_ms,
            "confidence_score": confidence,
            "invalidation_conditions": (
                "Données invalides si : "
                "(1) ticker changé de place boursière ou restaté, "
                "(2) données yfinance > 24h sans refresh, "
                "(3) couverture champs < 0.5, "
                "(4) restatement comptable postérieur à la collecte"
            ),
            "tokens_used": 0,  # pas de LLM — Python pur
        })

        log.info(
            f"[AgentData] '{ticker}' OK — "
            f"{latency_ms}ms | confiance={confidence:.0%} | src={snapshot.meta['source']}"
        )

        # ------------------------------------------------------------------
        # Log structuré → Supabase (fallback JSON local)
        # ------------------------------------------------------------------
        log_request(snapshot.meta, snapshot.to_dict())

        return snapshot
