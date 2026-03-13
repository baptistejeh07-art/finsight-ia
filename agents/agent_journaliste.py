# =============================================================================
# FinSight IA — Agent Journaliste
# agents/agent_journaliste.py
#
# Redacteur de rapports de gouvernance.
# Synthetise les observations des agents Sociologue et Enquete
# en un rapport lisible destine a l'equipe de gouvernance.
#
# Produit :
#   - Rapport hebdomadaire (mode "weekly")
#   - Bulletin d'incident (mode "incident")
#   - Note de gouvernance (mode "governance")
#
# Droit de lecture seule (Constitution Article 5).
# Sauvegarde les rapports dans outputs/generated/governance/
# =============================================================================

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_OUTPUT_DIR = Path(__file__).parent.parent / "outputs" / "generated" / "governance"


# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------

@dataclass
class GouvernanceReport:
    """Rapport de gouvernance produit par l'Agent Journaliste."""
    mode:         str           # "weekly" | "incident" | "governance"
    title:        str
    date:         str
    executive_summary: str
    sections:     list[dict]    # [{title, content}]
    alerts:       list[str]
    recommendations: list[str]
    file_path:    Optional[str] = None


# ---------------------------------------------------------------------------
# AgentJournaliste
# ---------------------------------------------------------------------------

class AgentJournaliste:
    """
    Redige les rapports de gouvernance de FinSight IA.
    Peut utiliser un LLM pour la mise en forme editoriale (optionnel).
    """

    def __init__(self, use_llm: bool = False):
        self._use_llm = use_llm

    # ------------------------------------------------------------------
    # Rapport hebdomadaire
    # ------------------------------------------------------------------

    def weekly_report(
        self,
        sociologue_report=None,
        enquete_report=None,
        rh_report=None,
    ) -> GouvernanceReport:
        """
        Rapport hebdomadaire de gouvernance.
        Combine les observations Sociologue + Enquete + RH.
        """
        now = datetime.utcnow()
        title = f"Rapport Hebdomadaire FinSight IA — {now.strftime('%d %b %Y')}"
        log.info(f"[AgentJournaliste] Redaction {title}")

        sections = []

        # Section 1 : Vue d'ensemble
        overview = self._build_overview(sociologue_report)
        sections.append({"title": "Vue d'ensemble", "content": overview})

        # Section 2 : Performance des agents
        perf = self._build_agent_performance(sociologue_report, rh_report)
        sections.append({"title": "Performance des agents", "content": perf})

        # Section 3 : Incidents et anomalies
        incidents = self._build_incidents(enquete_report)
        sections.append({"title": "Incidents et anomalies", "content": incidents})

        # Section 4 : Conformite constitutionnelle
        compliance = self._build_compliance(sociologue_report, enquete_report)
        sections.append({"title": "Conformite constitutionnelle", "content": compliance})

        # Aggreger alertes
        all_alerts = []
        if sociologue_report:
            all_alerts += sociologue_report.systemic_alerts
        if enquete_report and enquete_report.severity in ("WARNING", "CRITICAL"):
            all_alerts.append(
                f"[{enquete_report.severity}] Enquete '{enquete_report.subject}' : "
                f"{len(enquete_report.patterns)} patterns, "
                f"{len(enquete_report.root_causes)} causes racines"
            )

        # Recommandations
        recs = []
        if enquete_report:
            recs += enquete_report.recommendations
        if sociologue_report and sociologue_report.blocked_rate > 0.15:
            recs.append(
                "Revoir le seuil de confiance Article 1 ou enrichir les prompts "
                f"(taux blocage actuel : {sociologue_report.blocked_rate:.0%})"
            )

        # Executive summary
        exec_summ = self._build_exec_summary(sociologue_report, all_alerts, recs)

        report = GouvernanceReport(
            mode="weekly",
            title=title,
            date=now.isoformat(),
            executive_summary=exec_summ,
            sections=sections,
            alerts=all_alerts,
            recommendations=recs,
        )
        report.file_path = self._save(report)
        return report

    # ------------------------------------------------------------------
    # Bulletin d'incident
    # ------------------------------------------------------------------

    def incident_bulletin(self, enquete_report) -> GouvernanceReport:
        """Bulletin d'incident urgent base sur un rapport d'enquete."""
        now   = datetime.utcnow()
        title = (
            f"Bulletin Incident [{enquete_report.severity}] — "
            f"{now.strftime('%d %b %Y %H:%M')} UTC"
        )

        sections = [
            {
                "title": "Contexte de l'enquete",
                "content": (
                    f"Sujet : {enquete_report.subject}\n"
                    f"Traces analysees : {len(enquete_report.traces)}\n"
                    f"Patterns detectes : {len(enquete_report.patterns)}"
                ),
            },
            {
                "title": "Causes racines identifiees",
                "content": "\n".join(f"- {c}" for c in enquete_report.root_causes)
                           or "Aucune cause racine determinee",
            },
            {
                "title": "Details des patterns",
                "content": self._format_patterns(enquete_report.patterns),
            },
        ]

        exec_summ = (
            f"Incident de severite {enquete_report.severity} detecte. "
            f"{len(enquete_report.root_causes)} cause(s) racine(s) identifiee(s). "
            f"Action immediate requise : {enquete_report.recommendations[0] if enquete_report.recommendations else 'investigation manuelle'}."
        )

        report = GouvernanceReport(
            mode="incident",
            title=title,
            date=now.isoformat(),
            executive_summary=exec_summ,
            sections=sections,
            alerts=[f"[{enquete_report.severity}] {enquete_report.subject}"],
            recommendations=enquete_report.recommendations,
        )
        report.file_path = self._save(report)
        return report

    # ------------------------------------------------------------------
    # Note de gouvernance (avant amendement)
    # ------------------------------------------------------------------

    def governance_note(
        self,
        subject: str,
        context: str,
        observations: list[str],
        recommendations: list[str],
    ) -> GouvernanceReport:
        """Note de gouvernance structuree, typiquement produite avant une proposition d'amendement."""
        now = datetime.utcnow()
        title = f"Note de Gouvernance — {subject} — {now.strftime('%d %b %Y')}"

        sections = [
            {
                "title": "Contexte",
                "content": context,
            },
            {
                "title": "Observations factuelles",
                "content": "\n".join(f"{i+1}. {o}" for i, o in enumerate(observations)),
            },
            {
                "title": "Recommandations",
                "content": "\n".join(f"- {r}" for r in recommendations),
            },
        ]

        report = GouvernanceReport(
            mode="governance",
            title=title,
            date=now.isoformat(),
            executive_summary=f"Note de gouvernance sur : {subject}. "
                              f"{len(observations)} observations, "
                              f"{len(recommendations)} recommandations.",
            sections=sections,
            alerts=[],
            recommendations=recommendations,
        )
        report.file_path = self._save(report)
        return report

    # ------------------------------------------------------------------
    # Formatage des sections
    # ------------------------------------------------------------------

    def _build_overview(self, soc) -> str:
        if not soc:
            return "Donnees AgentSociologue non disponibles."
        lines = [
            f"Periode analysee   : {soc.period_days} jour(s)",
            f"Total requetes     : {soc.total_requests}",
            f"Tickers analyses   : {', '.join(soc.tickers_analyzed[:10])}",
            f"Taux blocage       : {soc.blocked_rate:.0%}",
            "",
            "Distribution sectorielle :",
        ]
        for sec, count in list(soc.sectors_breakdown.items())[:6]:
            lines.append(f"  {sec:<30} {count:>4} requetes")
        return "\n".join(lines)

    def _build_agent_performance(self, soc, rh) -> str:
        lines = []
        if soc and soc.agent_profiles:
            lines.append("Profils agents (logs V2) :")
            lines.append(f"  {'Agent':<25} {'Appels':>7} {'Erreurs':>8} {'P95 (ms)':>10}")
            lines.append("  " + "-" * 55)
            for p in soc.agent_profiles:
                lines.append(
                    f"  {p.agent_name:<25} {p.call_count:>7} "
                    f"{p.error_rate:>7.0%} {p.p95_latency_ms:>10.0f}"
                )

        if rh:
            lines.append("")
            lines.append("Distribution etats Markov (Agent RH) :")
            for name, result in rh.items():
                dist = getattr(result, "stationary_distribution", None)
                if dist:
                    repos, normal, surcharge = dist[0], dist[1], dist[2]
                    lines.append(
                        f"  {name:<25} Repos={repos:.0%} Normal={normal:.0%} "
                        f"Surcharge={surcharge:.0%}"
                    )
        return "\n".join(lines) if lines else "Aucune donnee de performance disponible."

    def _build_incidents(self, enquete) -> str:
        if not enquete:
            return "Aucune enquete disponible."
        lines = [
            f"Sujet     : {enquete.subject}",
            f"Severite  : {enquete.severity}",
            f"Traces    : {len(enquete.traces)}",
            "",
        ]
        if enquete.patterns:
            lines.append("Patterns detectes :")
            lines.append(self._format_patterns(enquete.patterns))
        if enquete.root_causes:
            lines.append("")
            lines.append("Causes racines :")
            for c in enquete.root_causes:
                lines.append(f"  - {c}")
        return "\n".join(lines)

    def _build_compliance(self, soc, enquete) -> str:
        lines = ["Conformite Constitution v1.0 :"]
        all_violations = []
        if enquete:
            all_violations = [
                v for t in enquete.traces
                for v in t.constitution_violations
            ]

        if not all_violations:
            lines.append("  Aucune violation detectee sur la periode.")
        else:
            from collections import Counter
            top = Counter(all_violations).most_common(5)
            for v, count in top:
                lines.append(f"  ({count}x) {v}")

        if soc:
            for note in soc.correlation_notes:
                lines.append(f"  Note : {note}")

        return "\n".join(lines)

    def _build_exec_summary(self, soc, alerts, recs) -> str:
        if not soc:
            return "Rapport de gouvernance genere automatiquement par AgentJournaliste."
        return (
            f"Systeme FinSight IA — {soc.total_requests} analyses sur {soc.period_days} jour(s). "
            f"Taux de blocage : {soc.blocked_rate:.0%}. "
            f"{len(alerts)} alerte(s) systemique(s). "
            f"{len(recs)} recommandation(s) en suspens."
        )

    def _format_patterns(self, patterns: list) -> str:
        if not patterns:
            return "  Aucun pattern identifie."
        lines = []
        for p in patterns:
            lines.append(
                f"  [{p.pattern_type}] {p.occurrences} occurrence(s)\n"
                f"    {p.description}\n"
                f"    => {p.recommendation}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Sauvegarde
    # ------------------------------------------------------------------

    def _save(self, report: GouvernanceReport) -> str:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts   = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        name = f"report_{report.mode}_{ts}.txt"
        fp   = _OUTPUT_DIR / name

        lines = [
            report.title,
            "=" * len(report.title),
            f"Date : {report.date}",
            "",
            "RESUME EXECUTIF",
            "-" * 40,
            report.executive_summary,
            "",
        ]

        for section in report.sections:
            lines.append(section["title"].upper())
            lines.append("-" * 40)
            lines.append(section["content"])
            lines.append("")

        if report.alerts:
            lines.append("ALERTES")
            lines.append("-" * 40)
            for a in report.alerts:
                lines.append(f"  ! {a}")
            lines.append("")

        if report.recommendations:
            lines.append("RECOMMANDATIONS")
            lines.append("-" * 40)
            for r in report.recommendations:
                lines.append(f"  - {r}")

        fp.write_text("\n".join(lines), encoding="utf-8")
        log.info(f"[AgentJournaliste] Rapport sauvegarde : {fp.name}")
        return str(fp)
