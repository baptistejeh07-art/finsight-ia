# =============================================================================
# FinSight IA — Agent Synthèse
# agents/agent_synthese.py
#
# Claude Haiku — synthèse financière structurée.
# Input  : FinancialSnapshot + RatiosResult + SentimentResult
# Output : SynthesisResult (JSON parsé depuis Haiku)
#
# Constitution §1 :
#   - confidence_score obligatoire dans chaque output
#   - invalidation_conditions obligatoires
# =============================================================================

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Optional

from core.llm_provider import LLMProvider

log = logging.getLogger(__name__)

# Modèle par défaut : Haiku (coût/qualité optimal pour synthèses courantes)
_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# ---------------------------------------------------------------------------
# Modèle de résultat
# ---------------------------------------------------------------------------

@dataclass
class SynthesisResult:
    """
    Résultat de l'Agent Synthèse.
    Constitution §1 : confidence_score + invalidation_conditions présents.
    """
    ticker:              str
    company_name:        str
    recommendation:      str         # "BUY" | "HOLD" | "SELL"
    conviction:          float        # [0, 1]
    target_base:         Optional[float] = None
    target_bull:         Optional[float] = None
    target_bear:         Optional[float] = None
    summary:             str = ""
    strengths:           list = field(default_factory=list)   # 3 bullets
    risks:               list = field(default_factory=list)   # 3 bullets
    valuation_comment:   str = ""
    confidence_score:    float = 0.5
    invalidation_conditions: str = ""
    meta:                dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Prompt engineering
# ---------------------------------------------------------------------------

_SYSTEM = """Tu es un analyste financier senior spécialisé Investment Banking.
Tu analyses des sociétés cotées et non-cotées pour des boutiques IB indépendantes.
Tu produis des analyses objectives, concises, professionnelles.

RÈGLE CONSTITUTIONNELLE (non violable) :
Chaque output DOIT contenir :
  - "confidence_score" : float entre 0 et 1
  - "invalidation_conditions" : string décrivant dans quelles conditions ton analyse serait fausse

Tu réponds UNIQUEMENT en JSON valide, sans markdown, sans commentaire, sans texte avant/après le JSON."""


def _build_prompt(
    snapshot,
    ratios,
    sentiment,
) -> str:
    ci  = snapshot.company_info
    mkt = snapshot.market

    # Ratios de l'année la plus récente
    latest = ratios.latest_year
    yr     = ratios.years.get(latest)

    def _f(v, suffix="", mult=1.0, dp=1):
        if v is None: return "N/A"
        return f"{v * mult:,.{dp}f}{suffix}"

    def _pct(v):
        if v is None: return "N/A"
        return f"{v*100:.1f}%"

    # Tableau ratios clés
    ratios_lines = []
    if yr:
        ratios_lines = [
            f"Revenue ({latest})    : {_f(None)} — cf données brutes",
            f"Gross Margin          : {_pct(yr.gross_margin)}",
            f"EBITDA Margin         : {_pct(yr.ebitda_margin)}",
            f"EBIT Margin           : {_pct(yr.ebit_margin)}",
            f"Net Margin            : {_pct(yr.net_margin)}",
            f"ROE                   : {_pct(yr.roe)}",
            f"ROA                   : {_pct(yr.roa)}",
            f"ROIC                  : {_pct(yr.roic)}",
            f"Current Ratio         : {_f(yr.current_ratio, dp=2)}",
            f"Net Debt / EBITDA     : {_f(yr.net_debt_ebitda, dp=2)}x",
            f"Interest Coverage     : {_f(yr.interest_coverage, dp=1)}x",
            f"EV / EBITDA           : {_f(yr.ev_ebitda, dp=1)}x",
            f"P/E Ratio             : {_f(yr.pe_ratio, dp=1)}x",
            f"FCF Yield             : {_pct(yr.fcf_yield)}",
            f"CapEx / Revenue       : {_pct(yr.capex_ratio)}",
            f"Altman Z-Score        : {_f(yr.altman_z, dp=2)} (>2.99=sain, <1.81=détresse)",
        ]
        if yr.beneish_m is not None:
            ratios_lines.append(
                f"Beneish M-Score       : {yr.beneish_m:.3f} (>-2.22 = risque manip.)"
            )
        # Croissance
        if yr.revenue_growth is not None:
            ratios_lines.append(f"Revenue Growth YoY    : {_pct(yr.revenue_growth)}")
        if yr.ebitda_growth is not None:
            ratios_lines.append(f"EBITDA Growth YoY     : {_pct(yr.ebitda_growth)}")

    ratios_block = "\n".join(ratios_lines) if ratios_lines else "Ratios non disponibles."

    # Sentiment
    sent_block = "Non disponible."
    if sentiment:
        sent_block = (
            f"Label : {sentiment.label} | Score : {sentiment.score:+.3f} | "
            f"Confiance : {sentiment.confidence:.0%} | "
            f"Articles : {sentiment.articles_analyzed}"
        )

    # Cours actuel
    price_str = f"{mkt.share_price} {ci.currency}" if mkt.share_price else "N/A"

    prompt = f"""MISSION : Analyse financière de {ci.company_name} ({ci.ticker}) — {date.today().isoformat()}

SECTEUR : {ci.sector or "Non renseigné"}
DEVISE   : {ci.currency} | UNITÉS : {ci.units}
COURS    : {price_str}

RATIOS CLÉS ({latest}) :
{ratios_block}

SENTIMENT MARCHÉ (7 derniers jours) :
{sent_block}

Produis un JSON avec exactement ces champs :
{{
  "recommendation": "BUY|HOLD|SELL",
  "conviction": <float 0-1>,
  "target_price_base": <float ou null>,
  "target_price_bull": <float ou null>,
  "target_price_bear": <float ou null>,
  "summary": "<2-3 phrases synthèse>",
  "strengths": ["<point fort 1>", "<point fort 2>", "<point fort 3>"],
  "risks": ["<risque 1>", "<risque 2>", "<risque 3>"],
  "valuation_comment": "<1-2 phrases sur la valorisation>",
  "confidence_score": <float 0-1>,
  "invalidation_conditions": "<conditions dans lesquelles cette analyse serait fausse>"
}}"""

    return prompt


# ---------------------------------------------------------------------------
# Agent Synthèse
# ---------------------------------------------------------------------------

class AgentSynthese:
    """
    Agent Synthèse — premier appel Claude Haiku (brief Phase 3).

    Usage :
        agent = AgentSynthese()
        result = agent.synthesize(snapshot, ratios, sentiment)
    """

    def __init__(self, model: str = _DEFAULT_MODEL):
        self.llm = LLMProvider(provider="anthropic", model=model)

    def synthesize(
        self,
        snapshot,
        ratios,
        sentiment=None,
    ) -> Optional[SynthesisResult]:
        """
        Produit la synthèse financière via Claude Haiku.

        Returns:
            SynthesisResult, ou None si Haiku inaccessible.
        """
        request_id = str(uuid.uuid4())
        t_start    = time.time()
        ci         = snapshot.company_info

        log.info(f"[AgentSynthese] Synthese '{snapshot.ticker}' — {request_id[:8]}")

        prompt = _build_prompt(snapshot, ratios, sentiment)

        # --- Appel LLM (Haiku → fallback Groq si credits insuffisants) ---
        raw = None
        providers_tried = [self.llm]
        _groq_fallback  = LLMProvider(provider="groq")

        for llm_attempt in [self.llm, _groq_fallback]:
            try:
                raw = llm_attempt.generate(
                    prompt=prompt,
                    system=_SYSTEM,
                    max_tokens=1024,
                )
                if raw:
                    if llm_attempt is not self.llm:
                        log.info(f"[AgentSynthese] Fallback Groq utilise")
                    break
            except Exception as e:
                log.warning(f"[AgentSynthese] {llm_attempt.provider} echec ({type(e).__name__}: {e}) — provider suivant")

        if not raw:
            log.error("[AgentSynthese] Tous les providers ont echoue")
            return None

        latency_ms = int((time.time() - t_start) * 1000)

        # --- Parse JSON ---
        parsed = _parse_json(raw)
        if not parsed:
            log.error(f"[AgentSynthese] JSON non parseable :\n{raw[:300]}")
            return None

        result = SynthesisResult(
            ticker             = snapshot.ticker,
            company_name       = ci.company_name,
            recommendation     = parsed.get("recommendation", "HOLD").upper(),
            conviction         = float(parsed.get("conviction", 0.5)),
            target_base        = parsed.get("target_price_base"),
            target_bull        = parsed.get("target_price_bull"),
            target_bear        = parsed.get("target_price_bear"),
            summary            = parsed.get("summary", ""),
            strengths          = parsed.get("strengths", []),
            risks              = parsed.get("risks", []),
            valuation_comment  = parsed.get("valuation_comment", ""),
            confidence_score   = float(parsed.get("confidence_score", 0.5)),
            invalidation_conditions = parsed.get("invalidation_conditions", ""),
            meta = {
                "request_id":   request_id,
                "model":        self.llm.model,
                "latency_ms":   latency_ms,
                "tokens_used":  None,  # anthropic SDK v0.84 ne retourne pas usage ici
                "confidence_score": float(parsed.get("confidence_score", 0.5)),
                "invalidation_conditions": parsed.get("invalidation_conditions", ""),
            },
        )

        log.info(
            f"[AgentSynthese] '{snapshot.ticker}' — "
            f"{result.recommendation} conviction={result.conviction:.0%} "
            f"({latency_ms}ms)"
        )

        return result


# ---------------------------------------------------------------------------
# Helper JSON parsing robuste
# ---------------------------------------------------------------------------

def _parse_json(text: str) -> Optional[dict]:
    """Tente de parser le JSON, avec nettoyage si nécessaire."""
    if not text:
        return None
    # Cas 1 : JSON direct
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # Cas 2 : JSON dans un bloc markdown ```json ... ```
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Cas 3 : extraire le premier {...} du texte
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None
