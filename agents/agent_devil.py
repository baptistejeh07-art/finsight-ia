# =============================================================================
# FinSight IA — Agent Devil's Advocate
# agents/agent_devil.py
#
# Produit la these inverse pour detecter les biais de confirmation.
# Input  : SynthesisResult + RatiosResult
# Output : DevilResult (counter_thesis, counter_risks, conviction_delta)
#
# Principe : si AgentSynthese dit BUY, Devil argumente SELL (et vice versa).
# L'objectif est de challenger la these, pas de remplacer la reco finale.
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

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# ---------------------------------------------------------------------------
# Modele de resultat
# ---------------------------------------------------------------------------

@dataclass
class DevilResult:
    """
    Resultat Agent Devil's Advocate.
    Constitution S1 : confidence_score + invalidation_conditions presents.
    """
    ticker:              str
    original_reco:       str           # recommandation originale
    counter_reco:        str           # these inverse
    counter_thesis:      str           # argument principal contre
    counter_risks:       List[str]     = field(default_factory=list)  # 3 risques ignores
    conviction_delta:    float         = 0.0   # -1=these forte, 0=neutre, +1=these faible
    key_assumptions:     List[str]     = field(default_factory=list)  # hypotheses fragiles
    confidence_score:    float         = 0.6
    invalidation_conditions: str       = "Si les donnees fondamentales contredisent la these inverse."
    meta:                dict          = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "original_reco": self.original_reco,
            "counter_reco": self.counter_reco,
            "counter_thesis": self.counter_thesis,
            "counter_risks": self.counter_risks,
            "conviction_delta": self.conviction_delta,
            "key_assumptions": self.key_assumptions,
            "confidence_score": self.confidence_score,
            "invalidation_conditions": self.invalidation_conditions,
            "meta": self.meta,
        }


# ---------------------------------------------------------------------------
# Prompt engineering
# ---------------------------------------------------------------------------

_SYSTEM = """Tu es un avocat du diable specialise en analyse financiere contradictoire.
Ton role : produire systematiquement la these inverse de celle presentee.
Si l'analyse dit BUY, tu argues SELL. Si SELL, tu argues BUY. Si HOLD, tu challenges des deux cotes.
Tu identifies les hypotheses fragiles, les risques ignores, les biais potentiels.
Tu n'es pas defaitiste — tu es intellectuellement rigoureux.

REGLE CONSTITUTIONNELLE (non violable) :
Chaque output DOIT contenir :
  - "confidence_score" : float entre 0 et 1
  - "invalidation_conditions" : string

Tu reponds UNIQUEMENT en JSON valide, sans markdown, sans commentaire."""


def _counter_reco(reco: str) -> str:
    mapping = {"BUY": "SELL", "SELL": "BUY", "HOLD": "BUY/SELL"}
    return mapping.get(reco.upper(), "HOLD")


def _build_prompt(synthesis, ratios) -> str:
    latest = ratios.latest_year
    yr     = ratios.years.get(latest)

    def _p(v): return f"{v*100:.1f}%" if v is not None else "N/A"
    def _x(v): return f"{v:.2f}x" if v is not None else "N/A"

    ratios_brief = ""
    if yr:
        ratios_brief = (
            f"Gross Margin={_p(yr.gross_margin)} | "
            f"Net Margin={_p(yr.net_margin)} | "
            f"ROE={_p(yr.roe)} | "
            f"Net Debt/EBITDA={_x(yr.net_debt_ebitda)} | "
            f"EV/EBITDA={_x(yr.ev_ebitda)} | "
            f"P/E={_x(yr.pe_ratio)}"
        )
        if yr.altman_z is not None:
            ratios_brief += f" | Altman Z={yr.altman_z:.2f}"
        if yr.revenue_growth is not None:
            ratios_brief += f" | Revenue Growth={_p(yr.revenue_growth)}"

    counter = _counter_reco(synthesis.recommendation)

    return f"""THESE ORIGINALE : {synthesis.ticker} / {synthesis.company_name}
Recommandation : {synthesis.recommendation} (conviction {synthesis.conviction:.0%})
Summary : {synthesis.summary}
Points forts : {'; '.join(synthesis.strengths)}
Risques identifies : {'; '.join(synthesis.risks)}
Ratios ({latest}) : {ratios_brief}

TA MISSION : Produis une these {counter} convaincante qui :
1. Challenge les hypotheses les plus fragiles de la these {synthesis.recommendation}
2. Identifie 3 risques que l'analyse originale sous-estime ou ignore
3. Quantifie dans quelle mesure la these originale est solide (conviction_delta)
   - conviction_delta < 0 : these originale fragile (Devil a de bons arguments)
   - conviction_delta = 0 : these originale solide mais challengeable
   - conviction_delta > 0 : these originale tres solide (Devil peine a argumenter)

Produis un JSON avec exactement ces champs :
{{
  "counter_reco": "{counter}",
  "counter_thesis": "<argument principal contre la these en 2-3 phrases>",
  "counter_risks": ["<risque ignore 1>", "<risque ignore 2>", "<risque ignore 3>"],
  "conviction_delta": <float -1 a +1>,
  "key_assumptions": ["<hypothese fragile 1>", "<hypothese fragile 2>"],
  "confidence_score": <float 0-1>,
  "invalidation_conditions": "<conditions dans lesquelles la these inverse serait fausse>"
}}"""


# ---------------------------------------------------------------------------
# Agent Devil's Advocate
# ---------------------------------------------------------------------------

class AgentDevil:
    """
    Agent Devil's Advocate — these inverse via Claude Haiku.

    Usage :
        agent = AgentDevil()
        result = agent.challenge(synthesis, ratios)
    """

    def __init__(self, model: str = _DEFAULT_MODEL):
        self.llm = LLMProvider(provider="anthropic", model=model)

    def challenge(
        self,
        synthesis,
        ratios,
    ) -> Optional[DevilResult]:
        """
        Produit la these inverse de la synthese.
        Returns DevilResult, ou None si LLM inaccessible.
        """
        request_id = str(uuid.uuid4())
        t_start    = time.time()
        ticker     = synthesis.ticker

        log.info(f"[AgentDevil] Challenge '{ticker}' ({synthesis.recommendation}) — {request_id[:8]}")

        prompt = _build_prompt(synthesis, ratios)

        # --- Appel LLM avec fallback Groq ---
        raw = None
        _groq = LLMProvider(provider="groq")

        for llm in [self.llm, _groq]:
            try:
                raw = llm.generate(prompt=prompt, system=_SYSTEM, max_tokens=768)
                if raw:
                    if llm is not self.llm:
                        log.info("[AgentDevil] Fallback Groq utilise")
                    break
            except Exception as e:
                err = str(e).lower()
                if any(k in err for k in ["credit", "billing", "balance", "quota"]):
                    log.warning(f"[AgentDevil] {llm.provider} credits insuffisants — fallback")
                else:
                    log.error(f"[AgentDevil] Erreur {llm.provider} : {e}")
                    break

        if not raw:
            log.error("[AgentDevil] Tous les providers ont echoue")
            return None

        latency_ms = int((time.time() - t_start) * 1000)

        parsed = _parse_json(raw)
        if not parsed:
            log.error(f"[AgentDevil] JSON non parseable :\n{raw[:300]}")
            return None

        result = DevilResult(
            ticker           = ticker,
            original_reco    = synthesis.recommendation,
            counter_reco     = parsed.get("counter_reco", _counter_reco(synthesis.recommendation)),
            counter_thesis   = parsed.get("counter_thesis", ""),
            counter_risks    = parsed.get("counter_risks", []),
            conviction_delta = float(parsed.get("conviction_delta", 0.0)),
            key_assumptions  = parsed.get("key_assumptions", []),
            confidence_score = float(parsed.get("confidence_score", 0.6)),
            invalidation_conditions = parsed.get("invalidation_conditions", ""),
            meta = {
                "request_id": request_id,
                "latency_ms": latency_ms,
                "model": self.llm.model,
            },
        )

        log.info(
            f"[AgentDevil] '{ticker}' — {result.original_reco} vs {result.counter_reco} "
            f"conviction_delta={result.conviction_delta:+.2f} ({latency_ms}ms)"
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
