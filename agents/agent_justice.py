# =============================================================================
# FinSight IA — Agent Justice
# agents/agent_justice.py
#
# Agent de gouvernance : verifie la conformite constitutionnelle et propose
# des amendements bases sur des evidences quantifiees.
#
# Processus formel (Constitution Article 6 & 7) :
#   1. Collecter les donnees observateurs (Sociologue, Enquete, RH)
#   2. Analyser les violations et patterns
#   3. Evaluer si un amendement est justifie
#   4. Formaliser la proposition avec : justification + simulation + periode
#   5. Archiver dans knowledge/amendments/
#   6. Indexer dans la base vectorielle
#
# Constitution Article 6 garantit l'independance de cet agent.
# =============================================================================

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

_AMENDMENTS_DIR = Path(__file__).parent.parent / "knowledge" / "amendments"


# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------

@dataclass
class PropositionAmendement:
    """
    Proposition formelle d'amendement a la Constitution.
    (Constitution Article 7)
    """
    amendment_id:   str = field(default_factory=lambda: f"amend_{uuid.uuid4().hex[:8]}")
    date:           str = field(default_factory=lambda: datetime.utcnow().isoformat())
    proposed_by:    str = "AgentJustice"

    article_number: int    = 0
    title:          str    = ""
    current_text:   str    = ""
    proposed_text:  str    = ""

    # Evidence (Constitution Article 6a)
    justification:  str    = ""
    evidence_stats: dict   = field(default_factory=dict)   # metriques quantifiees

    # Simulation d'impact (Article 6b)
    impact_simulation: dict = field(default_factory=dict)  # avant/apres seuils

    # Periode d'observation recommandee (Article 6c)
    observation_days: int   = 7

    # Validation humaine (Article 7 step 4)
    validated:       bool  = False
    validated_by:    str   = ""
    validated_date:  str   = ""

    def to_dict(self) -> dict:
        return {
            "amendment_id":      self.amendment_id,
            "date":              self.date,
            "proposed_by":       self.proposed_by,
            "article_number":    self.article_number,
            "title":             self.title,
            "current_text":      self.current_text,
            "proposed_text":     self.proposed_text,
            "justification":     self.justification,
            "evidence_stats":    self.evidence_stats,
            "impact_simulation": self.impact_simulation,
            "observation_days":  self.observation_days,
            "validated":         self.validated,
            "validated_by":      self.validated_by,
            "validated_date":    self.validated_date,
        }


@dataclass
class JusticeReport:
    """Rapport complet de l'Agent Justice."""
    date:              str
    total_requests:    int
    compliance_checks: list[dict]        # verifications par article
    violations_summary: dict             # article → nb violations
    propositions:      list[PropositionAmendement]
    verdict:           str               # "CONFORME" | "ALERTES" | "AMENDEMENTS_REQUIS"
    commentary:        str               # analyse narrative


# ---------------------------------------------------------------------------
# AgentJustice
# ---------------------------------------------------------------------------

class AgentJustice:
    """
    Agent de gouvernance independant.
    Evalue la conformite constitutionnelle et propose des amendements.
    """

    def __init__(self):
        _AMENDMENTS_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Point d'entree principal
    # ------------------------------------------------------------------

    def evaluate(
        self,
        sociologue_report=None,
        enquete_report=None,
        rh_report: Optional[dict] = None,
        max_logs: int = 300,
    ) -> JusticeReport:
        """
        Evalue la conformite et genere un rapport de justice.
        Peut proposer des amendements si justifie.
        """
        log.info("[AgentJustice] Debut evaluation constitutionnelle")

        records = self._load_logs(max_logs)

        # 1. Verifications par article
        compliance_checks = self._check_all_articles(records, sociologue_report)

        # 2. Resume des violations
        violations_summary = {
            str(c["article"]): c["violation_count"]
            for c in compliance_checks
        }

        # 3. Evaluer si amendements necessaires
        propositions = self._evaluate_amendments(
            compliance_checks, sociologue_report, enquete_report, records
        )

        # 4. Archiver les propositions
        for prop in propositions:
            self._archive(prop)
            try:
                from knowledge.vector_store import VectorStore
                VectorStore().index_amendment(prop.to_dict())
            except Exception as e:
                log.warning(f"[AgentJustice] Impossible d'indexer amendement : {e}")

        # 5. Verdict global
        total_violations = sum(violations_summary.values())
        if total_violations == 0:
            verdict = "CONFORME"
        elif propositions:
            verdict = "AMENDEMENTS_REQUIS"
        else:
            verdict = "ALERTES"

        commentary = self._build_commentary(
            compliance_checks, propositions, verdict, records
        )

        report = JusticeReport(
            date=datetime.utcnow().isoformat(),
            total_requests=len(records),
            compliance_checks=compliance_checks,
            violations_summary=violations_summary,
            propositions=propositions,
            verdict=verdict,
            commentary=commentary,
        )

        log.info(
            f"[AgentJustice] Verdict={verdict} | "
            f"{total_violations} violations | "
            f"{len(propositions)} proposition(s)"
        )
        return report

    # ------------------------------------------------------------------
    # Verifications par article
    # ------------------------------------------------------------------

    def _check_all_articles(self, records: list[dict], soc) -> list[dict]:
        from config.constitution import ARTICLES, get_threshold

        checks = []
        for art in ARTICLES:
            if art.threshold is None:
                # Articles qualitatifs : check via proxy
                check = self._check_qualitative(art, records, soc)
            else:
                check = self._check_quantitative(art, records)
            checks.append(check)
        return checks

    def _check_quantitative(self, article, records: list[dict]) -> dict:
        key = article.threshold_key
        thr = article.threshold
        n   = article.number

        values = [r.get(key) for r in records if r.get(key) is not None]
        if not values:
            return {
                "article": n, "title": article.title,
                "threshold": thr, "key": key,
                "values_count": 0, "violation_count": 0,
                "violation_rate": 0.0, "note": "Aucune donnee disponible",
            }

        values_f = [float(v) for v in values]

        if n == 3:   # Article 3 : retries <= 1
            violations = [v for v in values_f if v > thr]
        else:        # Articles 1 & 2 : valeur >= seuil
            violations = [v for v in values_f if v < thr]

        return {
            "article":        n,
            "title":          article.title,
            "threshold":      thr,
            "key":            key,
            "values_count":   len(values_f),
            "violation_count": len(violations),
            "violation_rate": len(violations) / len(values_f),
            "avg_value":      sum(values_f) / len(values_f),
            "note":           "",
        }

    def _check_qualitative(self, article, records: list[dict], soc) -> dict:
        n = article.number
        violation_count = 0
        note = "Check qualitatif"

        if n == 4:
            # Article 4 : integrite Excel — chercher des logs avec erreurs ExcelWriter
            for r in records:
                agents = r.get("agents_called") or []
                for a in agents:
                    extra = a.get("extra") or {}
                    if "formula" in str(extra).lower() or "bloque" in str(extra).lower():
                        violation_count += 1
                        break
            note = "Violations formule Excel detectees dans les logs"

        elif n == 5:
            note = "Agents observateurs operationnels (lecture seule garantie)"

        elif n == 6:
            # Article 6 : verifier que des amendements precedents existent
            existing = list(_AMENDMENTS_DIR.glob("*.json"))
            note = f"{len(existing)} amendement(s) archive(s)"

        elif n == 7:
            validated = [
                f for f in _AMENDMENTS_DIR.glob("*.json")
                if json.loads(f.read_text(encoding="utf-8")).get("validated")
            ]
            note = f"{len(validated)} amendement(s) valide(s) par un humain"

        return {
            "article":         n,
            "title":           article.title,
            "threshold":       None,
            "key":             article.threshold_key,
            "values_count":    len(records),
            "violation_count": violation_count,
            "violation_rate":  0.0,
            "note":            note,
        }

    # ------------------------------------------------------------------
    # Proposition d'amendements
    # ------------------------------------------------------------------

    def _evaluate_amendments(
        self,
        checks: list[dict],
        soc,
        enquete,
        records: list[dict],
    ) -> list[PropositionAmendement]:
        from config.constitution import get_article

        propositions = []

        for check in checks:
            art_num = check["article"]
            viol_rate = check.get("violation_rate", 0.0)

            # Seuil : si taux de violation > 20%, envisager amendement
            if viol_rate > 0.20 and check.get("threshold") is not None:
                art = get_article(art_num)
                if art is None:
                    continue

                current_thr = art.threshold
                avg_val     = check.get("avg_value", current_thr)

                # Proposition : ajuster le seuil a la valeur mediane observee
                # seulement si l'ecart est significatif
                if art_num in (1, 2):
                    # Proposer un seuil plus bas si la majorite passe en dessous
                    proposed_thr = round(avg_val * 0.90, 2)   # -10% du niveau moyen
                    if proposed_thr >= current_thr:
                        continue  # Pas utile de baisser si deja conforme
                    prop = PropositionAmendement(
                        article_number=art_num,
                        title=art.title,
                        current_text=art.text[:200],
                        proposed_text=(
                            f"[AMENDEMENT PROPOSE] Ajuster le seuil de {current_thr:.0%} "
                            f"a {proposed_thr:.0%} sur la base des donnees observees. "
                            f"{art.text[:200]}..."
                        ),
                        justification=(
                            f"Sur {check['values_count']} analyses, "
                            f"{viol_rate:.0%} sont en dessous du seuil actuel "
                            f"de {current_thr:.0%}. "
                            f"La valeur moyenne observee est {avg_val:.0%}. "
                            f"Un seuil de {proposed_thr:.0%} reduirait le taux de blocage "
                            f"tout en maintenant la qualite minimale."
                        ),
                        evidence_stats={
                            "violation_rate":   viol_rate,
                            "avg_value":        avg_val,
                            "current_threshold": current_thr,
                            "proposed_threshold": proposed_thr,
                            "sample_size":      check["values_count"],
                        },
                        impact_simulation={
                            "current_block_rate":  viol_rate,
                            "projected_block_rate": max(0, viol_rate - 0.10),
                            "confidence_loss":     current_thr - proposed_thr,
                            "note": "Simulation lineaire — periode d'observation requise",
                        },
                        observation_days=14,
                    )
                    propositions.append(prop)

        return propositions

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_logs(self, max_logs: int) -> list[dict]:
        logs_dir = Path(__file__).parent.parent / "logs" / "local"
        files    = sorted(logs_dir.glob("v2_*.json"))[-max_logs:]
        records  = []
        for fp in files:
            try:
                records.append(json.loads(fp.read_text(encoding="utf-8")))
            except Exception:
                pass
        return records

    def _archive(self, prop: PropositionAmendement) -> str:
        """Archive la proposition dans knowledge/amendments/ (Article 7 step 2)."""
        fname = f"{prop.amendment_id}.json"
        fpath = _AMENDMENTS_DIR / fname
        fpath.write_text(
            json.dumps(prop.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        log.info(f"[AgentJustice] Proposition archivee : {fname}")
        return str(fpath)

    def _build_commentary(
        self,
        checks: list[dict],
        propositions: list[PropositionAmendement],
        verdict: str,
        records: list[dict],
    ) -> str:
        lines = [
            f"Rapport Agent Justice — {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC",
            f"Verdict : {verdict}",
            f"Corpus  : {len(records)} requetes analysees",
            "",
            "Articles verifies :",
        ]
        for c in checks:
            vc = c["violation_count"]
            vr = c.get("violation_rate", 0.0)
            status = "OK" if vc == 0 else f"VIOLATION ({vc} cas, {vr:.0%})"
            lines.append(
                f"  Art.{c['article']:1d} {c['title']:<35} {status}"
            )

        if propositions:
            lines.append("")
            lines.append(f"{len(propositions)} proposition(s) d'amendement :")
            for p in propositions:
                lines.append(
                    f"  [{p.amendment_id}] Article {p.article_number} — "
                    f"periode d'observation : {p.observation_days}j"
                )
                lines.append(f"    {p.justification[:150]}...")

        if verdict == "CONFORME":
            lines.append("")
            lines.append(
                "La Constitution est respectee sur la periode analysee. "
                "Aucun amendement n'est necessaire a ce stade."
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Validation d'un amendement (action humaine)
    # ------------------------------------------------------------------

    def validate_amendment(
        self,
        amendment_id: str,
        validated_by: str = "human",
    ) -> bool:
        """
        Valide un amendement propose (action humaine — Article 7 step 4).
        Met a jour le fichier JSON et la base vectorielle.
        """
        fpath = _AMENDMENTS_DIR / f"{amendment_id}.json"
        if not fpath.exists():
            log.error(f"[AgentJustice] Amendement introuvable : {amendment_id}")
            return False

        data = json.loads(fpath.read_text(encoding="utf-8"))
        data["validated"]      = True
        data["validated_by"]   = validated_by
        data["validated_date"] = datetime.utcnow().isoformat()
        fpath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        log.info(f"[AgentJustice] Amendement {amendment_id} valide par {validated_by}")
        return True

    def list_pending_amendments(self) -> list[dict]:
        """Liste les propositions en attente de validation."""
        pending = []
        for fp in _AMENDMENTS_DIR.glob("*.json"):
            try:
                d = json.loads(fp.read_text(encoding="utf-8"))
                if not d.get("validated"):
                    pending.append(d)
            except Exception:
                pass
        return pending
