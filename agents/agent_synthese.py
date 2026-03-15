# =============================================================================
# FinSight IA — Agent Synthese
# agents/agent_synthese.py
# =============================================================================

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Optional

from core.llm_provider import LLMProvider

log = logging.getLogger(__name__)
_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


@dataclass
class SynthesisResult:
    ticker:              str
    company_name:        str
    recommendation:      str
    conviction:          float
    target_base:         Optional[float] = None
    target_bull:         Optional[float] = None
    target_bear:         Optional[float] = None
    summary:             str = ""
    company_description: str = ""
    thesis:              str = ""
    segments:            list = field(default_factory=list)
    strengths:           list = field(default_factory=list)
    risks:               list = field(default_factory=list)
    valuation_comment:   str = ""
    financial_commentary: str = ""
    ratio_commentary:    str = ""
    dcf_commentary:      str = ""
    positive_themes:     list = field(default_factory=list)
    negative_themes:     list = field(default_factory=list)
    invalidation_list:   list = field(default_factory=list)
    comparable_peers:    list = field(default_factory=list)
    football_field:      list = field(default_factory=list)
    is_projections:      dict = field(default_factory=dict)
    confidence_score:    float = 0.5
    invalidation_conditions: str = ""
    meta:                dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


_SYSTEM = """Tu es un analyste financier senior Investment Banking.
Tu produis des analyses objectives, concises, professionnelles en francais.
REGLES ABSOLUES :
1. Output = JSON valide uniquement, zero markdown, zero texte avant/apres le JSON
2. Tous les champs sont obligatoires et ne peuvent PAS etre null
3. company_description = minimum 4 phrases detaillees sur l'activite, les segments, le positionnement
4. thesis = minimum 3 phrases sur les catalyseurs d'investissement concrets
5. comparable_peers = exactement 5 vrais concurrents avec leurs multiples LTM reels (utilise ta connaissance)
6. is_projections = estimations chiffrees reelles pour les 2 prochaines annees (pas null)
7. Toutes les valeurs numeriques doivent etre des nombres, jamais null ou string"""


def _build_prompt(snapshot, ratios, sentiment) -> str:
    ci  = snapshot.company_info
    mkt = snapshot.market
    latest = ratios.latest_year
    yr     = ratios.years.get(latest)

    def _f(v, dp=1):
        return "N/A" if v is None else f"{float(v):,.{dp}f}"
    def _pct(v):
        return "N/A" if v is None else f"{float(v)*100:.1f}%"

    lines = []
    if yr:
        raw_yr = snapshot.years.get(latest)
        lines = [
            f"Revenue({latest}): {_f(raw_yr.revenue if raw_yr else None)}M",
            f"GrossMargin: {_pct(yr.gross_margin)} | EBITDAMargin: {_pct(yr.ebitda_margin)} | NetMargin: {_pct(yr.net_margin)}",
            f"ROE: {_pct(yr.roe)} | ROIC: {_pct(yr.roic)}",
            f"EV/EBITDA: {_f(yr.ev_ebitda)}x | P/E: {_f(yr.pe_ratio)}x | EV/Rev: {_f(yr.ev_revenue)}x",
            f"NetDebt/EBITDA: {_f(yr.net_debt_ebitda)}x | AltmanZ: {_f(yr.altman_z, dp=2)}",
        ]
        if yr.revenue_growth is not None:
            lines.append(f"RevGrowthYoY: {_pct(yr.revenue_growth)}")

    sent_block = "N/A"
    if sentiment:
        sent_block = f"{sentiment.label} score={sentiment.score:+.3f} conf={sentiment.confidence:.0%} n={sentiment.articles_analyzed}"

    price_s  = f"{mkt.share_price}" if mkt.share_price else "N/A"
    wacc_s   = f"{(mkt.wacc or 0.10)*100:.1f}%"
    tgr_s    = f"{(mkt.terminal_growth or 0.03)*100:.1f}%"
    # Calcul des années de projection
    hist_keys = sorted(snapshot.years.keys(), key=lambda y: str(y).replace("_LTM",""))
    last_yr   = str(hist_keys[-1]).replace("_LTM","") if hist_keys else str(date.today().year - 1)
    try:
        ny1 = str(int(last_yr) + 1) + "F"
        ny2 = str(int(last_yr) + 2) + "F"
    except Exception:
        ny1, ny2 = "2025F", "2026F"

    return f"""Analyse {ci.company_name} ({ci.ticker}) — secteur:{ci.sector} — {date.today().isoformat()}
Cours:{price_s} {ci.currency} | WACC:{wacc_s} | TGR:{tgr_s}
{chr(10).join(lines)}
Sentiment: {sent_block}

JSON requis (tous les champs obligatoires) :
{{
  "recommendation":"BUY|HOLD|SELL",
  "conviction":<0-1>,
  "target_price_base":<float|null>,
  "target_price_bull":<float|null>,
  "target_price_bear":<float|null>,
  "summary":"<2 phrases>",
  "company_description":"<MAXIMUM 60 mots — 2 phrases activite positionnement {ci.company_name}>",
  "segments":[
    {{"name":"<nom exact segment operationnel>","description":"<MAXIMUM 12 mots — 1 ligne courte ex: Logiciels cloud B2B, SaaS entreprise>","revenue_pct":<float 0-100>}},
    {{"name":"<nom segment 2>","description":"<MAXIMUM 12 mots — 1 ligne courte>","revenue_pct":<float 0-100>}}
  ],
  "thesis":"<3-4 phrases these investissement catalyseurs>",
  "strengths":["<MAXIMUM 8 mots — titre atout1>","<MAXIMUM 8 mots — titre atout2>","<MAXIMUM 8 mots — titre atout3>"],
  "risks":["<MAXIMUM 8 mots — titre risque1>","<MAXIMUM 8 mots — titre risque2>","<MAXIMUM 8 mots — titre risque3>"],
  "valuation_comment":"<2 phrases valorisation relative>",
  "financial_commentary":"<2-3 phrases tendances P&L croissance marges cash>",
  "ratio_commentary":"<1-2 phrases ratios vs secteur>",
  "dcf_commentary":"<1-2 phrases hypotheses DCF sensibilite>",
  "positive_themes":["<catalyseur positif 1>","<catalyseur positif 2>","<catalyseur positif 3>"],
  "negative_themes":["<risque negatif 1>","<risque negatif 2>","<risque negatif 3>"],
  "is_projections":{{
    "{ny1}":{{"revenue":<float en memes unites que historique>,"revenue_growth":<float 0-1>,"gross_margin":<float 0-1>,"ebitda":<float>,"ebitda_margin":<float 0-1>,"net_income":<float>,"net_margin":<float 0-1>}},
    "{ny2}":{{"revenue":<float>,"revenue_growth":<float 0-1>,"gross_margin":<float 0-1>,"ebitda":<float>,"ebitda_margin":<float 0-1>,"net_income":<float>,"net_margin":<float 0-1>}}
  }},
  "invalidation_list":[
    {{"axis":"Macro","condition":"<evenement macro>","horizon":"6-12 mois"}},
    {{"axis":"Sectoriel","condition":"<evenement sectoriel>","horizon":"12-18 mois"}},
    {{"axis":"Societe","condition":"<evenement specifique {ci.ticker}>","horizon":"2-3 trim."}}
  ],
  "comparable_peers":[
    {{"name":"<pair1>","ticker":"<T1>","market_cap_mds":<float en Mds devise>,"ev_ebitda":<f>,"ev_revenue":<f>,"pe":<f>,"gross_margin":<0-1>,"ebitda_margin":<0-1>}},
    {{"name":"<pair2>","ticker":"<T2>","market_cap_mds":<float en Mds devise>,"ev_ebitda":<f>,"ev_revenue":<f>,"pe":<f>,"gross_margin":<0-1>,"ebitda_margin":<0-1>}},
    {{"name":"<pair3>","ticker":"<T3>","market_cap_mds":<float en Mds devise>,"ev_ebitda":<f>,"ev_revenue":<f>,"pe":<f>,"gross_margin":<0-1>,"ebitda_margin":<0-1>}},
    {{"name":"<pair4>","ticker":"<T4>","market_cap_mds":<float en Mds devise>,"ev_ebitda":<f>,"ev_revenue":<f>,"pe":<f>,"gross_margin":<0-1>,"ebitda_margin":<0-1>}},
    {{"name":"<pair5>","ticker":"<T5>","market_cap_mds":<float en Mds devise>,"ev_ebitda":<f>,"ev_revenue":<f>,"pe":<f>,"gross_margin":<0-1>,"ebitda_margin":<0-1>}}
  ],
  "football_field":[
    {{"label":"DCF - Bear","range_low":<f>,"range_high":<f>,"midpoint":<target_price_bear>}},
    {{"label":"DCF - Base","range_low":<f>,"range_high":<f>,"midpoint":<target_price_base>}},
    {{"label":"DCF - Bull","range_low":<f>,"range_high":<f>,"midpoint":<target_price_bull>}},
    {{"label":"EV/EBITDA - Mediane peers","range_low":<f>,"range_high":<f>,"midpoint":<f>}},
    {{"label":"EV/EBITDA - Prime tech +50 %","range_low":<f>,"range_high":<f>,"midpoint":<f>}},
    {{"label":"EV/Revenue - Mediane peers","range_low":<f>,"range_high":<f>,"midpoint":<f>}}
  ],
  "confidence_score":<0-1>,
  "invalidation_conditions":"<resume conditions>"
}}"""


class AgentSynthese:
    def __init__(self, model: str = _DEFAULT_MODEL):
        self.llm = LLMProvider(provider="anthropic", model=model)

    def synthesize(self, snapshot, ratios, sentiment=None) -> Optional[SynthesisResult]:
        request_id = str(uuid.uuid4())
        t_start    = time.time()
        ci         = snapshot.company_info

        log.info(f"[AgentSynthese] Synthese '{snapshot.ticker}' — {request_id[:8]}")

        prompt = _build_prompt(snapshot, ratios, sentiment)
        raw = None
        for llm_attempt in [self.llm, LLMProvider(provider="groq")]:
            try:
                raw = llm_attempt.generate(prompt=prompt, system=_SYSTEM, max_tokens=4000)
                if raw:
                    if llm_attempt is not self.llm:
                        log.info("[AgentSynthese] Fallback Groq utilise")
                    break
            except Exception as e:
                log.warning(f"[AgentSynthese] {llm_attempt.provider} echec ({type(e).__name__}: {e})")

        if not raw:
            log.error("[AgentSynthese] Tous les providers ont echoue")
            return None

        latency_ms = int((time.time() - t_start) * 1000)
        parsed = _parse_json(raw)
        if not parsed:
            log.error(f"[AgentSynthese] JSON non parseable :\n{raw[:300]}")
            return None

        result = SynthesisResult(
            ticker               = snapshot.ticker,
            company_name         = ci.company_name,
            recommendation       = parsed.get("recommendation", "HOLD").upper(),
            conviction           = float(parsed.get("conviction", 0.5)),
            target_base          = parsed.get("target_price_base"),
            target_bull          = parsed.get("target_price_bull"),
            target_bear          = parsed.get("target_price_bear"),
            summary              = parsed.get("summary", ""),
            company_description  = parsed.get("company_description", ""),
            segments             = parsed.get("segments", []),
            thesis               = parsed.get("thesis", ""),
            strengths            = parsed.get("strengths", []),
            risks                = parsed.get("risks", []),
            valuation_comment    = parsed.get("valuation_comment", ""),
            financial_commentary = parsed.get("financial_commentary", ""),
            ratio_commentary     = parsed.get("ratio_commentary", ""),
            dcf_commentary       = parsed.get("dcf_commentary", ""),
            positive_themes      = parsed.get("positive_themes", []),
            negative_themes      = parsed.get("negative_themes", []),
            invalidation_list    = parsed.get("invalidation_list", []),
            comparable_peers     = parsed.get("comparable_peers", []),
            football_field       = parsed.get("football_field", []),
            is_projections       = parsed.get("is_projections", {}),
            confidence_score     = float(parsed.get("confidence_score", 0.5)),
            invalidation_conditions = parsed.get("invalidation_conditions", ""),
            meta = {
                "request_id":  request_id,
                "model":       self.llm.model,
                "latency_ms":  latency_ms,
                "tokens_used": None,
                "confidence_score": float(parsed.get("confidence_score", 0.5)),
                "invalidation_conditions": parsed.get("invalidation_conditions", ""),
            },
        )

        log.info(
            f"[AgentSynthese] '{snapshot.ticker}' — "
            f"{result.recommendation} conviction={result.conviction:.0%} ({latency_ms}ms)"
        )
        return result


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
