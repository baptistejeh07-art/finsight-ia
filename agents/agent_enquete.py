# =============================================================================
# FinSight IA — Agent Enquete
# agents/agent_enquete.py
#
# Investigateur specialise : creuse les anomalies specifiques signalees
# par l'Agent Sociologue ou detectees en temps reel.
#
# Capacites :
#   - Analyse d'un request_id specifique (trace complete)
#   - Recherche semantique dans la base vectorielle
#   - Detection de patterns recurrents d'echec
#   - Comparaison avant/apres un changement de configuration
#
# Droit de lecture seule (Constitution Article 5).
# =============================================================================

from __future__ import annotations

import json
import logging
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

_LOGS_DIR = Path(__file__).parent.parent / "logs" / "local"


# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------

@dataclass
class EnqueteTrace:
    """Trace complete d'une requete (analyse forensique)."""
    request_id:   str
    ticker:       str
    timestamp:    str
    agents_sequence:  list[str]
    agent_details:    list[dict]
    anomalies:        list[str]     # problemes detectes
    constitution_violations: list[str]


@dataclass
class PatternReport:
    """Rapport de pattern recurrent."""
    pattern_type:  str              # ex: "synthesis_fail", "low_confidence_sector"
    occurrences:   int
    affected_ids:  list[str]
    description:   str
    recommendation: str


@dataclass
class EnqueteReport:
    """Rapport complet d'enquete."""
    subject:         str             # sujet de l'enquete
    traces:          list[EnqueteTrace]
    patterns:        list[PatternReport]
    root_causes:     list[str]
    recommendations: list[str]
    severity:        str             # "INFO" | "WARNING" | "CRITICAL"


# ---------------------------------------------------------------------------
# AgentEnquete
# ---------------------------------------------------------------------------

class AgentEnquete:
    """
    Investigateur forensique du systeme FinSight.
    """

    def __init__(self, logs_dir: Optional[Path] = None):
        self._logs_dir = logs_dir or _LOGS_DIR

    # ------------------------------------------------------------------
    # Enquete sur un request_id specifique
    # ------------------------------------------------------------------

    def investigate_request(self, request_id: str) -> Optional[EnqueteTrace]:
        """Analyse complete d'une requete par son ID."""
        record = self._find_log(request_id)
        if not record:
            log.warning(f"[AgentEnquete] Log introuvable : {request_id}")
            return None
        return self._build_trace(record)

    # ------------------------------------------------------------------
    # Enquete sur un sujet (recherche semantique + analyse)
    # ------------------------------------------------------------------

    def investigate(
        self,
        subject: str,
        use_vector_store: bool = True,
        max_logs: int = 200,
    ) -> EnqueteReport:
        """
        Enquete thematique sur un sujet.
        Combine recherche semantique et analyse statistique.
        """
        log.info(f"[AgentEnquete] Debut enquete : '{subject}'")

        # Chargement logs pour analyse directe
        records = self._load_logs(max_logs)

        # Recherche semantique dans la base vectorielle
        vs_results: list[dict] = []
        if use_vector_store:
            try:
                from knowledge.vector_store import VectorStore
                vs = VectorStore()
                vs_results = vs.query(subject, n_results=10)
                vs_results += vs.query_incidents(subject, n_results=5)
            except Exception as e:
                log.warning(f"[AgentEnquete] VectorStore non disponible : {e}")

        # Filtrer les records pertinents (par subject keyword)
        relevant = self._filter_relevant(records, subject, vs_results)

        # Traces forensiques
        traces = [self._build_trace(r) for r in relevant[:10]]

        # Detection de patterns
        patterns = self._detect_patterns(records)

        # Root causes et recommandations
        root_causes, recommendations, severity = self._synthesize(
            subject, traces, patterns, records
        )

        report = EnqueteReport(
            subject=subject,
            traces=traces,
            patterns=patterns,
            root_causes=root_causes,
            recommendations=recommendations,
            severity=severity,
        )
        log.info(
            f"[AgentEnquete] Rapport : {len(traces)} traces, "
            f"{len(patterns)} patterns, severity={severity}"
        )
        return report

    # ------------------------------------------------------------------
    # Enquete sur les incidents recents
    # ------------------------------------------------------------------

    def investigate_recent_incidents(self, n_days: int = 7) -> EnqueteReport:
        """Analyse les incidents des N derniers jours."""
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=n_days)
        records = self._load_logs(500)

        recent = []
        for r in records:
            ts = r.get("timestamp", "")
            try:
                if datetime.fromisoformat(ts[:19]) >= cutoff:
                    recent.append(r)
            except Exception:
                pass

        incidents = [r for r in recent if self._is_incident(r)]
        return self.investigate(
            subject=f"incidents derniers {n_days} jours",
            use_vector_store=False,
            max_logs=500,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_log(self, request_id: str) -> Optional[dict]:
        # Cherche par request_id dans le nom du fichier ou dans le contenu
        for fp in self._logs_dir.glob("v2_*.json"):
            if request_id[:8] in fp.name:
                try:
                    r = json.loads(fp.read_text(encoding="utf-8"))
                    if r.get("request_id", "").startswith(request_id[:8]):
                        return r
                except Exception:
                    pass
        return None

    def _load_logs(self, max_logs: int) -> list[dict]:
        files   = sorted(self._logs_dir.glob("v2_*.json"))[-max_logs:]
        records = []
        for fp in files:
            try:
                records.append(json.loads(fp.read_text(encoding="utf-8")))
            except Exception:
                pass
        return records

    def _is_incident(self, record: dict) -> bool:
        agents = record.get("agents_called") or []
        has_error = any(a.get("status") == "error" for a in agents)
        conf = record.get("confidence_score")
        low_conf = conf is not None and float(conf) < 0.65
        return has_error or low_conf

    def _filter_relevant(
        self,
        records: list[dict],
        subject: str,
        vs_results: list[dict],
    ) -> list[dict]:
        """Filtre les records pertinents pour le sujet."""
        # IDs trouves par le vector store
        vs_ids = {r["metadata"].get("file", "").replace(".json", "") for r in vs_results}

        relevant = []
        subj_lower = subject.lower()

        for r in records:
            rid = r.get("request_id", "")
            text_fields = [
                r.get("ticker", ""),
                r.get("recommendation", ""),
                str(r.get("output", "") or ""),
                str(r.get("input_data", "") or ""),
            ]
            full_text = " ".join(text_fields).lower()

            # Match par ID vectoriel ou par keyword
            if any(rid.startswith(vs_id[:8]) for vs_id in vs_ids if vs_id):
                relevant.append(r)
            elif any(w in full_text for w in subj_lower.split() if len(w) > 3):
                relevant.append(r)
            elif self._is_incident(r) and "incident" in subj_lower:
                relevant.append(r)

        return relevant[:20]

    def _build_trace(self, record: dict) -> EnqueteTrace:
        agents = record.get("agents_called") or []
        sequence = [a.get("agent", "?") for a in agents]
        anomalies = []

        # Detecter anomalies
        for a in agents:
            if a.get("status") == "error":
                anomalies.append(
                    f"Agent {a.get('agent')} en erreur "
                    f"(latency={a.get('latency_ms')}ms)"
                )
            lat = a.get("latency_ms", 0)
            if lat > 20_000:
                anomalies.append(
                    f"Agent {a.get('agent')} latence excessive : {lat}ms"
                )

        conf = record.get("confidence_score")
        if conf is not None and float(conf) < 0.65:
            anomalies.append(f"Confidence trop faible : {float(conf):.0%} < 65%")

        # Violations Constitution
        from config.constitution import check_compliance
        violations_raw = check_compliance(record)
        violations = [
            f"Article {v['article']} ({v['title']}) : "
            f"{v['actual']:.2f} vs seuil {v['threshold']}"
            for v in violations_raw if not v["compliant"]
        ]

        return EnqueteTrace(
            request_id=record.get("request_id", ""),
            ticker=record.get("ticker", ""),
            timestamp=record.get("timestamp", ""),
            agents_sequence=sequence,
            agent_details=agents,
            anomalies=anomalies,
            constitution_violations=violations,
        )

    def _detect_patterns(self, records: list[dict]) -> list[PatternReport]:
        patterns = []

        # Pattern 1 : Synthese en echec recurrent
        synth_errors = [
            r.get("request_id", "")
            for r in records
            if any(
                a.get("agent") == "AgentSynthese" and a.get("status") == "error"
                for a in (r.get("agents_called") or [])
            )
        ]
        if len(synth_errors) >= 3:
            patterns.append(PatternReport(
                pattern_type="synthesis_recurrent_failure",
                occurrences=len(synth_errors),
                affected_ids=synth_errors[:5],
                description=(
                    f"AgentSynthese a echoue {len(synth_errors)} fois. "
                    "Verifier : cles API, prompt, tokens."
                ),
                recommendation="Verifier ANTHROPIC_API_KEY + logs erreur LLM",
            ))

        # Pattern 2 : Confiance systematiquement basse pour un secteur
        sect_conf: dict[str, list] = defaultdict(list)
        for r in records:
            sec = (r.get("input_data") or {}).get("sector") or "Unknown"
            c   = r.get("confidence_score")
            if c is not None:
                sect_conf[sec].append((float(c), r.get("request_id", "")))
        for sec, items in sect_conf.items():
            if len(items) >= 5:
                avg = statistics.mean(v for v, _ in items)
                if avg < 0.65:
                    patterns.append(PatternReport(
                        pattern_type=f"low_confidence_sector_{sec.lower().replace(' ', '_')}",
                        occurrences=len(items),
                        affected_ids=[rid for _, rid in items[:5]],
                        description=(
                            f"Secteur '{sec}' : confiance moyenne {avg:.0%} < 65%. "
                            "Les analyses sur ce secteur sont frequemment bloquees."
                        ),
                        recommendation=(
                            f"Enrichir les donnees secteur '{sec}' "
                            "ou ajuster le prompt de synthese pour ce secteur."
                        ),
                    ))

        # Pattern 3 : Latence excessive recurrente
        slow_runs = [
            r.get("request_id", "")
            for r in records
            if (r.get("latency_ms") or 0) > 45_000
        ]
        if len(slow_runs) >= 5:
            patterns.append(PatternReport(
                pattern_type="excessive_latency",
                occurrences=len(slow_runs),
                affected_ids=slow_runs[:5],
                description=(
                    f"{len(slow_runs)} requetes > 45s detectees. "
                    "Goulot possible : AgentData (yfinance) ou AgentSentiment (FinBERT)."
                ),
                recommendation="Activer TRANSFORMERS_OFFLINE=1 et monitorer yfinance rate limits",
            ))

        return patterns

    def _synthesize(
        self,
        subject: str,
        traces: list[EnqueteTrace],
        patterns: list[PatternReport],
        records: list[dict],
    ) -> tuple[list[str], list[str], str]:
        root_causes = []
        recommendations = []

        for p in patterns:
            root_causes.append(f"[{p.pattern_type}] {p.description}")
            recommendations.append(p.recommendation)

        all_anomalies = [a for t in traces for a in t.anomalies]
        if all_anomalies:
            top = Counter(all_anomalies).most_common(3)
            for anomaly, count in top:
                root_causes.append(f"Anomalie recurrente ({count}x) : {anomaly}")

        all_violations = [v for t in traces for v in t.constitution_violations]
        if all_violations:
            root_causes.append(
                f"{len(all_violations)} violations Constitution detectees"
            )
            recommendations.append(
                "Revoir les seuils Constitution ou corriger les agents en cause"
            )

        # Severity
        critical_patterns = [p for p in patterns
                             if "failure" in p.pattern_type or "low_confidence" in p.pattern_type]
        if len(critical_patterns) >= 2 or len(all_violations) >= 5:
            severity = "CRITICAL"
        elif patterns or all_violations:
            severity = "WARNING"
        else:
            severity = "INFO"

        return root_causes, recommendations, severity
