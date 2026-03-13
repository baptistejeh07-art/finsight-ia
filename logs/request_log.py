# =============================================================================
# FinSight IA — RequestLog v2
# logs/request_log.py
#
# Context object construit progressivement pendant le pipeline.
# Ecrit une seule fois a la fin via db_logger.log_pipeline_v2().
#
# Schema final :
#   request_id, timestamp, ticker, version="v2"
#   agents : liste d'AgentEntry (nom, statut, latency_ms, tokens_used, extra)
#   confidence_score, invalidation_conditions, recommendation, conviction
#   total_latency_ms, tokens_used (somme agents)
# =============================================================================

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# ---------------------------------------------------------------------------
# AgentEntry — une entree par agent appele
# ---------------------------------------------------------------------------

@dataclass
class AgentEntry:
    agent:       str          # ex: "AgentData", "AgentSentiment", "AgentQuant"...
    status:      str          # "ok" | "error" | "skip"
    latency_ms:  int          # duree d'execution en ms
    tokens_used: int = 0      # tokens LLM consommes (0 pour agents non-LLM)
    extra:       dict = field(default_factory=dict)  # metadata specifique a chaque agent

    def to_dict(self) -> dict:
        d = {
            "agent":       self.agent,
            "status":      self.status,
            "latency_ms":  self.latency_ms,
            "tokens_used": self.tokens_used,
        }
        if self.extra:
            d.update(self.extra)
        return d


# ---------------------------------------------------------------------------
# RequestLog — context complet d'une requete pipeline
# ---------------------------------------------------------------------------

@dataclass
class RequestLog:
    ticker:     str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp:  str = field(default_factory=lambda: datetime.utcnow().isoformat())
    version:    str = "v2"

    agents: list[AgentEntry] = field(default_factory=list)

    # Rempli par finalize()
    confidence_score:        Optional[float] = None
    invalidation_conditions: Optional[str]   = None
    recommendation:          Optional[str]   = None
    conviction:              Optional[float] = None
    total_latency_ms:        int             = 0

    # Champs brief §4
    market_context: Optional[dict] = None  # conditions marché au moment de l'analyse
    input_data:     Optional[dict] = None  # résumé données brutes (snapshot condensé)
    output:         Optional[dict] = None  # analyse produite complète (synthesis)
    # retrospective_roi : V2 uniquement — non implémenté Phase 7

    # ---------------------------------------------------------------------------
    # API publique
    # ---------------------------------------------------------------------------

    def add(self, entry: AgentEntry) -> None:
        """Ajoute une entree agent au log."""
        self.agents.append(entry)

    def finalize(
        self,
        synthesis=None,
        snapshot=None,
        total_ms: Optional[int] = None,
    ) -> None:
        """
        Calcule les totaux et extrait les champs cles depuis synthesis + snapshot.
        Appeler a la fin du pipeline avant log_pipeline_v2().
        """
        self.total_latency_ms = total_ms if total_ms is not None else sum(
            a.latency_ms for a in self.agents
        )
        if synthesis:
            self.confidence_score        = getattr(synthesis, "confidence_score", None)
            self.invalidation_conditions = getattr(synthesis, "invalidation_conditions", None)
            self.recommendation          = getattr(synthesis, "recommendation", None)
            self.conviction              = getattr(synthesis, "conviction", None)
            self.output = {
                "recommendation":          self.recommendation,
                "conviction":              self.conviction,
                "confidence_score":        self.confidence_score,
                "target_base":             getattr(synthesis, "target_base", None),
                "target_bull":             getattr(synthesis, "target_bull", None),
                "target_bear":             getattr(synthesis, "target_bear", None),
                "summary":                 getattr(synthesis, "summary", None),
                "invalidation_conditions": self.invalidation_conditions,
            }
        if snapshot:
            mkt = getattr(snapshot, "market", None)
            self.market_context = {
                "share_price":    getattr(mkt, "share_price", None),
                "beta_levered":   getattr(mkt, "beta_levered", None),
                "risk_free_rate": getattr(mkt, "risk_free_rate", None),
                "wacc":           getattr(mkt, "wacc", None),
            } if mkt else None
            ci = getattr(snapshot, "company_info", None)
            self.input_data = {
                "sector":         getattr(ci, "sector", None),
                "currency":       getattr(ci, "currency", None),
                "years_available": list(snapshot.years.keys()) if snapshot.years else [],
                "base_year":      getattr(ci, "base_year", None),
            }

    @property
    def tokens_used(self) -> int:
        return sum(a.tokens_used for a in self.agents)

    def to_dict(self) -> dict:
        return {
            "request_id":              self.request_id,
            "timestamp":               self.timestamp,
            "ticker":                  self.ticker,
            "version":                 self.version,
            "market_context":          self.market_context,
            "agents_called":           [a.to_dict() for a in self.agents],
            "input_data":              self.input_data,
            "output":                  self.output,
            "confidence_score":        self.confidence_score,
            "invalidation_conditions": self.invalidation_conditions,
            "recommendation":          self.recommendation,
            "conviction":              self.conviction,
            "tokens_used":             self.tokens_used,
            "latency_ms":              self.total_latency_ms,
        }


# ---------------------------------------------------------------------------
# Helper : timer contextuel
# ---------------------------------------------------------------------------

class AgentTimer:
    """
    Usage :
        with AgentTimer("AgentQuant") as t:
            ratios = AgentQuant().compute(snapshot)
        req_log.add(t.entry(status="ok", extra={"ratios_count": 33}))
    """
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self._t0:    float = 0.0
        self.elapsed_ms: int = 0

    def __enter__(self) -> "AgentTimer":
        self._t0 = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.elapsed_ms = int((time.time() - self._t0) * 1000)
        return False  # ne supprime pas les exceptions

    def entry(
        self,
        status: str = "ok",
        tokens_used: int = 0,
        extra: Optional[dict] = None,
    ) -> AgentEntry:
        return AgentEntry(
            agent=self.agent_name,
            status=status,
            latency_ms=self.elapsed_ms,
            tokens_used=tokens_used,
            extra=extra or {},
        )
