# =============================================================================
# FinSight IA — Agent QA Haiku
# agents/agent_qa_haiku.py
#
# Claude Haiku verifie la qualite redactionnelle et professionnelle
# de la synthese produite par AgentSynthese.
# Input  : SynthesisResult + QAResult (Python)
# Output : QAHaikuResult (readability_score, issues, improved_summary)
#
# Constitution S1 :
#   - confidence_score obligatoire
#   - invalidation_conditions obligatoires
# =============================================================================

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from core.llm_provider import LLMProvider

log = logging.getLogger(__name__)

_DEFAULT_MODEL = "llama-3.3-70b-versatile"

# ---------------------------------------------------------------------------
# Modele de resultat
# ---------------------------------------------------------------------------

@dataclass
class QAHaikuResult:
    """
    Resultat Agent QA Haiku.
    Constitution S1 : confidence_score + invalidation_conditions presents.
    """
    ticker:              str
    readability_score:   float          # [0,1] qualite redactionnelle
    ib_standard:         bool           # True = standard IB respecte
    issues:              List[str]      = field(default_factory=list)
    improved_summary:    str            = ""
    tone_assessment:     str            = ""
    confidence_score:    float          = 0.7
    invalidation_conditions: str        = "Si le modele LLM produit une evaluation biaisee."
    meta:                dict           = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "readability_score": self.readability_score,
            "ib_standard": self.ib_standard,
            "issues": self.issues,
            "improved_summary": self.improved_summary,
            "tone_assessment": self.tone_assessment,
            "confidence_score": self.confidence_score,
            "invalidation_conditions": self.invalidation_conditions,
            "meta": self.meta,
        }


# ---------------------------------------------------------------------------
# Prompt engineering
# ---------------------------------------------------------------------------

_SYSTEM = """Tu es un directeur editorial specialise en recherche actions Investment Banking.
Tu evalues la qualite professionnelle des analyses financieres.
Criteres IB : objectivite, concision, absence d'hyperbole, donnees chiffrees, ton institutionnel.

REGLE CONSTITUTIONNELLE (non violable) :
Chaque output DOIT contenir :
  - "confidence_score" : float entre 0 et 1
  - "invalidation_conditions" : string

Tu reponds UNIQUEMENT en JSON valide, sans markdown, sans commentaire."""


def _build_prompt(synthesis, qa_python) -> str:
    flags_summary = ""
    if qa_python:
        errors   = [f.message for f in qa_python.flags if f.level == "ERROR"]
        warnings = [f.message for f in qa_python.flags if f.level == "WARNING"]
        if errors:
            flags_summary += f"\nERREURS QA Python : {'; '.join(errors)}"
        if warnings:
            flags_summary += f"\nWARNINGS QA Python : {'; '.join(warnings)}"

    return f"""MISSION : Evaluation qualite redactionnelle — {synthesis.ticker} / {synthesis.company_name}

RECOMMANDATION : {synthesis.recommendation} (conviction {synthesis.conviction:.0%})

SUMMARY :
{synthesis.summary}

POINTS FORTS :
{chr(10).join(f'- {s}' for s in synthesis.strengths)}

RISQUES :
{chr(10).join(f'- {r}' for r in synthesis.risks)}

COMMENTAIRE VALORISATION :
{synthesis.valuation_comment}

CONDITIONS D'INVALIDATION :
{synthesis.invalidation_conditions}
{flags_summary}

Evalue cette analyse selon les criteres suivants :
1. Professionnalisme IB (ton institutionnel, pas d'hyperbole)
2. Coherence interne (risques/forces alignes avec recommandation)
3. Precision et concision (chiffres cited, phrases directes)
4. Completude (summary, forces, risques, invalidation tous presents)

Produis un JSON avec exactement ces champs :
{{
  "readability_score": <float 0-1>,
  "ib_standard": <true|false>,
  "issues": ["<probleme 1>", ...],
  "improved_summary": "<summary ameliore ou vide si deja bon>",
  "tone_assessment": "<evaluation du ton en 1 phrase>",
  "confidence_score": <float 0-1>,
  "invalidation_conditions": "<conditions dans lesquelles cette evaluation serait fausse>"
}}"""


# ---------------------------------------------------------------------------
# Agent QA Haiku
# ---------------------------------------------------------------------------

class AgentQAHaiku:
    """
    Agent QA Haiku — validation editoriale et professionnelle via Claude Haiku.

    Usage :
        agent = AgentQAHaiku()
        result = agent.validate(synthesis, qa_python)
    """

    def __init__(self, model: str = _DEFAULT_MODEL):
        self.llm = LLMProvider(provider="groq", model=model)

    def validate(
        self,
        synthesis,
        qa_python=None,
    ) -> Optional[QAHaikuResult]:
        """
        Valide la qualite de la synthese via Groq.
        Returns QAHaikuResult, ou None si LLM inaccessible.
        """
        if synthesis is None:
            log.warning("[AgentQAHaiku] synthesis=None — validation impossible, skip")
            return None

        request_id = str(uuid.uuid4())
        t_start    = time.time()
        ticker     = synthesis.ticker

        log.info(f"[AgentQAHaiku] Validation '{ticker}' — {request_id[:8]}")

        prompt = _build_prompt(synthesis, qa_python)

        raw = None
        try:
            raw = self.llm.generate(prompt=prompt, system=_SYSTEM, max_tokens=768)
        except Exception as e:
            log.warning(f"[AgentQAHaiku] {self.llm.provider} echec ({type(e).__name__}: {e})")

        if not raw:
            log.error("[AgentQAHaiku] Groq a echoue")
            return None

        latency_ms = int((time.time() - t_start) * 1000)

        parsed = _parse_json(raw)
        if not parsed:
            log.error(f"[AgentQAHaiku] JSON non parseable :\n{raw[:300]}")
            return None

        result = QAHaikuResult(
            ticker             = ticker,
            readability_score  = float(parsed.get("readability_score", 0.5)),
            ib_standard        = bool(parsed.get("ib_standard", False)),
            issues             = parsed.get("issues", []),
            improved_summary   = parsed.get("improved_summary", ""),
            tone_assessment    = parsed.get("tone_assessment", ""),
            confidence_score   = float(parsed.get("confidence_score", 0.7)),
            invalidation_conditions = parsed.get("invalidation_conditions", ""),
            meta = {
                "request_id": request_id,
                "latency_ms": latency_ms,
                "model": self.llm.model,
            },
        )

        log.info(
            f"[AgentQAHaiku] '{ticker}' — "
            f"readability={result.readability_score:.0%} ib={result.ib_standard} "
            f"issues={len(result.issues)} ({latency_ms}ms)"
        )

        return result


# ---------------------------------------------------------------------------
# Helper JSON parsing robuste
# ---------------------------------------------------------------------------

def _parse_json(text: str) -> Optional[dict]:
    if not text:
        return None
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None
