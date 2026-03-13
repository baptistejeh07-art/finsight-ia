# =============================================================================
# FinSight IA — Agent Sociologue
# agents/agent_sociologue.py
#
# Observe les patterns d'interaction entre agents via les logs V2.
# Detecte les tendances systemiques : agents surcharges, cycles d'erreurs,
# derives de confiance, correlations secteur/performance.
#
# Droit de lecture seule — ne modifie jamais l'etat du pipeline.
# (Constitution Article 5)
# =============================================================================

from __future__ import annotations

import json
import logging
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_LOGS_DIR = Path(__file__).parent.parent / "logs" / "local"


# ---------------------------------------------------------------------------
# Structures de sortie
# ---------------------------------------------------------------------------

@dataclass
class AgentProfile:
    """Profil statistique d'un agent sur la periode d'observation."""
    agent_name:    str
    call_count:    int
    error_rate:    float   # 0.0–1.0
    avg_latency_ms: float
    p95_latency_ms: float
    skip_rate:     float


@dataclass
class SociologueReport:
    """Rapport de l'Agent Sociologue."""
    period_days:        int
    total_requests:     int
    tickers_analyzed:   list[str]
    sectors_breakdown:  dict[str, int]        # secteur → nb requetes
    agent_profiles:     list[AgentProfile]
    confidence_trend:   list[float]           # serie temporelle (moyenne par jour)
    blocked_rate:       float                 # taux de pipelines bloques (conf < 0.65)
    top_error_agents:   list[str]             # agents les plus souvent en erreur
    correlation_notes:  list[str]             # observations textuelles
    systemic_alerts:    list[str]             # alertes necessitant enquete


# ---------------------------------------------------------------------------
# AgentSociologue
# ---------------------------------------------------------------------------

class AgentSociologue:
    """
    Lit tous les logs V2 disponibles et produit un rapport sociologique
    sur le comportement du systeme multi-agents.
    """

    def __init__(self, logs_dir: Optional[Path] = None):
        self._logs_dir = logs_dir or _LOGS_DIR

    # ------------------------------------------------------------------
    # Point d'entree
    # ------------------------------------------------------------------

    def observe(self, max_logs: int = 500) -> SociologueReport:
        """
        Charge les logs V2 et produit le rapport.
        max_logs : limite de securite pour les gros corpus.
        """
        records = self._load_logs(max_logs)
        if not records:
            log.warning("[AgentSociologue] Aucun log V2 trouve")
            return SociologueReport(
                period_days=0, total_requests=0, tickers_analyzed=[],
                sectors_breakdown={}, agent_profiles=[], confidence_trend=[],
                blocked_rate=0.0, top_error_agents=[], correlation_notes=[],
                systemic_alerts=["Aucun log V2 disponible — bootstrap requis"],
            )

        report = self._analyze(records)
        log.info(
            f"[AgentSociologue] {report.total_requests} requetes analysees "
            f"| blocked_rate={report.blocked_rate:.0%} "
            f"| alertes={len(report.systemic_alerts)}"
        )
        return report

    # ------------------------------------------------------------------
    # Chargement des logs
    # ------------------------------------------------------------------

    def _load_logs(self, max_logs: int) -> list[dict]:
        files  = sorted(self._logs_dir.glob("v2_*.json"))[-max_logs:]
        records = []
        for fp in files:
            try:
                records.append(json.loads(fp.read_text(encoding="utf-8")))
            except Exception:
                pass
        return records

    # ------------------------------------------------------------------
    # Analyse
    # ------------------------------------------------------------------

    def _analyze(self, records: list[dict]) -> SociologueReport:
        # Tickers & secteurs
        tickers   = list({r.get("ticker", "") for r in records if r.get("ticker")})
        sectors   = Counter()
        for r in records:
            inp = r.get("input_data") or {}
            sec = inp.get("sector") or "Unknown"
            sectors[sec] += 1

        # Agents stats
        agent_calls: dict[str, list[dict]] = defaultdict(list)
        for r in records:
            for a in (r.get("agents_called") or []):
                agent_calls[a.get("agent", "?")].append(a)

        profiles = []
        for name, calls in sorted(agent_calls.items()):
            latencies = [c.get("latency_ms", 0) for c in calls]
            errors    = [c for c in calls if c.get("status") == "error"]
            skips     = [c for c in calls if c.get("status") == "skip"]
            sorted_lat = sorted(latencies)
            p95 = sorted_lat[int(len(sorted_lat) * 0.95)] if sorted_lat else 0
            profiles.append(AgentProfile(
                agent_name=name,
                call_count=len(calls),
                error_rate=len(errors) / len(calls) if calls else 0.0,
                avg_latency_ms=statistics.mean(latencies) if latencies else 0.0,
                p95_latency_ms=float(p95),
                skip_rate=len(skips) / len(calls) if calls else 0.0,
            ))

        # Confidence trend (par bloc de 10 requetes)
        confidences = [float(r.get("confidence_score") or 0) for r in records]
        trend = []
        chunk = 10
        for i in range(0, len(confidences), chunk):
            block = confidences[i:i + chunk]
            if block:
                trend.append(round(statistics.mean(block), 3))

        # Taux bloque (confidence < 0.65)
        blocked = sum(1 for c in confidences if c < 0.65)
        blocked_rate = blocked / len(records) if records else 0.0

        # Top agents en erreur
        top_errors = sorted(
            [p for p in profiles if p.error_rate > 0],
            key=lambda p: p.error_rate,
            reverse=True,
        )[:3]
        top_error_names = [p.agent_name for p in top_errors]

        # Notes de correlation
        notes = self._build_notes(records, profiles, sectors)

        # Alertes systemiques
        alerts = self._build_alerts(records, profiles, blocked_rate)

        # Periode estimee (delta entre premier et dernier timestamp)
        timestamps = [r.get("timestamp", "") for r in records if r.get("timestamp")]
        period_days = 0
        if len(timestamps) >= 2:
            try:
                from datetime import datetime
                t0 = datetime.fromisoformat(timestamps[0][:19])
                t1 = datetime.fromisoformat(timestamps[-1][:19])
                period_days = max(1, abs((t1 - t0).days))
            except Exception:
                period_days = 1

        return SociologueReport(
            period_days=period_days,
            total_requests=len(records),
            tickers_analyzed=sorted(tickers),
            sectors_breakdown=dict(sectors.most_common()),
            agent_profiles=profiles,
            confidence_trend=trend,
            blocked_rate=blocked_rate,
            top_error_agents=top_error_names,
            correlation_notes=notes,
            systemic_alerts=alerts,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_notes(
        self,
        records: list[dict],
        profiles: list[AgentProfile],
        sectors: Counter,
    ) -> list[str]:
        notes = []

        # Correlation secteur → confiance moyenne
        sect_conf: dict[str, list[float]] = defaultdict(list)
        for r in records:
            inp = r.get("input_data") or {}
            sec = inp.get("sector") or "Unknown"
            conf = r.get("confidence_score")
            if conf is not None:
                sect_conf[sec].append(float(conf))
        for sec, vals in sect_conf.items():
            if len(vals) >= 3:
                avg = statistics.mean(vals)
                notes.append(
                    f"Secteur '{sec}' : confiance moyenne {avg:.0%} "
                    f"({len(vals)} analyses)"
                )

        # Agents avec latence elevee
        for p in profiles:
            if p.p95_latency_ms > 15_000:
                notes.append(
                    f"{p.agent_name} : P95 latence = {p.p95_latency_ms/1000:.1f}s "
                    f"(potentiel goulot)"
                )

        # Recommendation distribution
        recs = Counter(r.get("recommendation", "N/A") for r in records)
        total = len(records)
        rec_note = ", ".join(
            f"{k}={v/total:.0%}" for k, v in recs.most_common()
        )
        notes.append(f"Distribution recommandations : {rec_note}")

        return notes

    def _build_alerts(
        self,
        records: list[dict],
        profiles: list[AgentProfile],
        blocked_rate: float,
    ) -> list[str]:
        alerts = []

        if blocked_rate > 0.20:
            alerts.append(
                f"ALERTE : {blocked_rate:.0%} des pipelines sont bloques "
                f"(confidence < 65%) — revoir calibrage AgentSynthese"
            )

        for p in profiles:
            if p.error_rate > 0.10:
                alerts.append(
                    f"ALERTE : {p.agent_name} taux d'erreur = {p.error_rate:.0%} "
                    f"(seuil 10%) — investigation requise"
                )

        # Derive de confiance : dernier quart < premier quart
        confidences = [float(r.get("confidence_score") or 0) for r in records]
        if len(confidences) >= 8:
            first_q = statistics.mean(confidences[:len(confidences)//4])
            last_q  = statistics.mean(confidences[-len(confidences)//4:])
            if last_q < first_q - 0.10:
                alerts.append(
                    f"DERIVE : confiance moyenne recente {last_q:.0%} vs debut "
                    f"{first_q:.0%} — tendance baissiere detectee"
                )

        return alerts
