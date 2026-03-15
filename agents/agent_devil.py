# =============================================================================
# FinSight IA — Agent Devil's Advocate
# agents/agent_devil.py
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


@dataclass
class DevilResult:
    ticker:              str
    original_reco:       str
    counter_reco:        str
    counter_thesis:      str
    counter_risks:       List[str] = field(default_factory=list)
    conviction_delta:    float     = 0.0
    key_assumptions:     List[str] = field(default_factory=list)
    confidence_score:    float     = 0.6
    invalidation_conditions: str  = "Si les donnees fondamentales contredisent la these inverse."
    meta:                dict     = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker, "original_reco": self.original_reco,
            "counter_reco": self.counter_reco, "counter_thesis": self.counter_thesis,
            "counter_risks": self.counter_risks, "conviction_delta": self.conviction_delta,
            "key_assumptions": self.key_assumptions, "confidence_score": self.confidence_score,
            "invalidation_conditions": self.invalidation_conditions, "meta": self.meta,
        }


# Bug 3 fix — system prompt strictement négatif, zéro argument positif
_SYSTEM = """Tu es l'avocat du diable en analyse financiere contradictoire.
TON UNIQUE MISSION : produire des arguments NEGATIFS et BAISSIERS contre la these d'investissement presentee.

REGLES ABSOLUES (violation = output invalide) :
1. Il est INTERDIT d'inclure des arguments positifs, des nuances favorables, des expressions
   suggerant une opportunite d'achat, une resilience, un potentiel positif, ou une perspective haussiere.
2. Chaque phrase DOIT affaiblir la these, pas la defendre.
3. Si la these est BUY, tu produis uniquement des arguments pour SELL.
4. Si la these est SELL, tu produis uniquement des arguments pour BUY (sur-vendu, rebond).
5. Si la these est HOLD, tu identifies les deux risques les plus graves (baissier dominant).
6. Mots INTERDITS dans l'output : "opportunite", "solide", "resilient", "potentiel positif",
   "croissance acceleree", "catalyseur positif", "favorable", "robuste".

Tu reponds UNIQUEMENT en JSON valide, sans markdown, sans texte avant/apres."""


def _counter_reco(reco: str) -> str:
    return {"BUY": "SELL", "SELL": "BUY", "HOLD": "SELL"}.get(reco.upper(), "SELL")


def _build_prompt(synthesis, ratios) -> str:
    latest = ratios.latest_year
    yr     = ratios.years.get(latest)

    def _p(v): return f"{v*100:.1f}%" if v is not None else "N/A"
    def _x(v): return f"{v:.2f}x"    if v is not None else "N/A"

    ratios_brief = ""
    if yr:
        ratios_brief = (
            f"GrossMargin={_p(yr.gross_margin)} | NetMargin={_p(yr.net_margin)} | "
            f"ROE={_p(yr.roe)} | NetDebt/EBITDA={_x(yr.net_debt_ebitda)} | "
            f"EV/EBITDA={_x(yr.ev_ebitda)} | P/E={_x(yr.pe_ratio)}"
        )
        if yr.altman_z is not None:
            ratios_brief += f" | AltmanZ={yr.altman_z:.2f}"
        if yr.revenue_growth is not None:
            ratios_brief += f" | RevGrowth={_p(yr.revenue_growth)}"

    counter = _counter_reco(synthesis.recommendation)

    return f"""THESE A DETRUIRE : {synthesis.ticker} / {synthesis.company_name}
Recommandation originale : {synthesis.recommendation} (conviction {synthesis.conviction:.0%})
Arguments haussiers donnes : {'; '.join(synthesis.strengths)}
Ratios ({latest}) : {ratios_brief}

MISSION : Produis 3 paragraphes EXCLUSIVEMENT NEGATIFS qui demontent la these {synthesis.recommendation}.
Chaque paragraphe = 1 titre court (10 mots max) + 2-3 phrases d'argumentation negative concrete.
Identifie les hypotheses les plus fragiles et quantifie les risques de baisse.

JSON requis :
{{
  "counter_reco": "{counter}",
  "counter_thesis": "<3 paragraphes negatifs separes par ' | ', MAXIMUM 25 mots par paragraphe>",
  "counter_risks": ["<titre risque 1>", "<titre risque 2>", "<titre risque 3>"],
  "conviction_delta": <float -1 (these fragile) a 0 (these solide)>,
  "key_assumptions": ["<hypothese fragile 1>", "<hypothese fragile 2>"],
  "confidence_score": <float 0-1>,
  "invalidation_conditions": "<quand la these inverse serait fausse>"
}}"""


class AgentDevil:
    def __init__(self, model: str = _DEFAULT_MODEL):
        self.llm = LLMProvider(provider="anthropic", model=model)

    def challenge(self, synthesis, ratios) -> Optional[DevilResult]:
        if synthesis is None:
            log.warning("[AgentDevil] synthesis=None — skip")
            return None

        request_id = str(uuid.uuid4())
        t_start    = time.time()
        ticker     = synthesis.ticker

        log.info(f"[AgentDevil] Challenge '{ticker}' ({synthesis.recommendation}) — {request_id[:8]}")

        prompt = _build_prompt(synthesis, ratios)
        raw = None
        for llm in [self.llm, LLMProvider(provider="groq")]:
            try:
                raw = llm.generate(prompt=prompt, system=_SYSTEM, max_tokens=1024)
                if raw:
                    if llm is not self.llm:
                        log.info("[AgentDevil] Fallback Groq utilise")
                    break
            except Exception as e:
                log.warning(f"[AgentDevil] {llm.provider} echec ({type(e).__name__}: {e})")

        if not raw:
            log.error("[AgentDevil] Tous les providers ont echoue")
            return None

        latency_ms = int((time.time() - t_start) * 1000)
        parsed = _parse_json(raw)
        if not parsed:
            log.error(f"[AgentDevil] JSON non parseable :\n{raw[:300]}")
            return None

        # Validation post-génération : log warning si contenu positif détecté
        ct = parsed.get("counter_thesis", "")
        _POSITIVE_WORDS = ["opportunite", "resilient", "solide", "potentiel positif",
                           "favorable", "robuste", "croissance acceleree", "catalyseur positif"]
        found_positive = [w for w in _POSITIVE_WORDS if w in ct.lower()]
        if found_positive:
            log.warning(f"[AgentDevil] '{ticker}' : mots positifs detectes dans these inverse : {found_positive}")

        result = DevilResult(
            ticker           = ticker,
            original_reco    = synthesis.recommendation,
            counter_reco     = parsed.get("counter_reco", counter_reco := _counter_reco(synthesis.recommendation)),
            counter_thesis   = ct,
            counter_risks    = parsed.get("counter_risks", []),
            conviction_delta = float(parsed.get("conviction_delta", 0.0)),
            key_assumptions  = parsed.get("key_assumptions", []),
            confidence_score = float(parsed.get("confidence_score", 0.6)),
            invalidation_conditions = parsed.get("invalidation_conditions", ""),
            meta = {"request_id": request_id, "latency_ms": latency_ms, "model": self.llm.model},
        )

        log.info(
            f"[AgentDevil] '{ticker}' — {result.original_reco} vs {result.counter_reco} "
            f"conviction_delta={result.conviction_delta:+.2f} ({latency_ms}ms)"
        )
        return result


def _parse_json(text: str) -> Optional[dict]:
    if not text: return None
    try: return json.loads(text.strip())
    except json.JSONDecodeError: pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1))
        except json.JSONDecodeError: pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try: return json.loads(m.group(0))
        except json.JSONDecodeError: pass
    return None
