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
_DEFAULT_MODEL = "mistral-small-latest"


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
    peers_commentary:    str = ""
    positive_themes:     list = field(default_factory=list)
    negative_themes:     list = field(default_factory=list)
    invalidation_list:   list = field(default_factory=list)
    comparable_peers:    list = field(default_factory=list)
    football_field:      list = field(default_factory=list)
    is_projections:      dict = field(default_factory=dict)
    confidence_score:    float = 0.5
    invalidation_conditions: str = ""
    # Champs visibles PDF — scenarios + catalyseurs + revision + conclusion
    bear_hypothesis:     str = ""
    base_hypothesis:     str = ""
    bull_hypothesis:     str = ""
    catalysts:           list = field(default_factory=list)
    buy_trigger:         str = ""
    sell_trigger:        str = ""
    conclusion:          str = ""
    next_review:         str = ""
    meta:                dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


_SYSTEM = """Tu es un analyste financier senior Investment Banking.
Tu produis des analyses objectives, concises, professionnelles en français.
LANGUE : français avec TOUS les accents (é, è, ê, à, ù, ô, î, û, ç, œ, etc.) — JAMAIS de caractères sans accent (ex: "Modérée" et non "Moderee", "résilience" et non "resilience").
REGLES ABSOLUES :
1. Output = JSON valide uniquement, zero markdown, zero texte avant/apres le JSON
2. Tous les champs sont obligatoires et ne peuvent PAS etre null
3. company_description = 3 phrases sur l'activite, le positionnement et les avantages concurrentiels (MINIMUM 50, MAXIMUM 70 mots)
4. thesis = exactement 3 phrases courtes separees par ' | ', chaque phrase 18-22 mots avec catalyseurs concrets chiffres
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

    # Serie historique des marges (pour ratio_commentary du graphique)
    hist_years_sorted = sorted(ratios.years.keys(), key=lambda y: str(y).replace("_LTM",""))
    margins_series = []
    for hy in hist_years_sorted:
        hyr = ratios.years.get(hy)
        if hyr:
            margins_series.append(
                f"{hy}: GM={_pct(hyr.gross_margin)} EBITDA={_pct(hyr.ebitda_margin)} Net={_pct(hyr.net_margin)}"
            )
    margins_series_str = " / ".join(margins_series) if margins_series else "N/A"

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
MargesHistoriques: {margins_series_str}
Sentiment: {sent_block}

JSON requis (tous les champs obligatoires) :
{{
  "recommendation":"BUY|HOLD|SELL",
  "conviction":<float 0-1 — calcule strictement: SELL=0.3-0.5, HOLD=0.45-0.60, BUY faible=0.60-0.70, BUY fort=0.70-0.85; NE PAS depasser 0.85 sauf catalyseur exceptionnel>,
  "target_price_base":<float|null>,
  "target_price_bull":<float|null>,
  "target_price_bear":<float|null>,
  "summary":"<2 phrases>",
  "company_description":"<MINIMUM 50, MAXIMUM 70 mots — 3 phrases: activite principale, positionnement marche, avantages competitifs de {ci.company_name}>",
  "segments":[
    {{"name":"<nom exact segment operationnel>","description":"<MINIMUM 35, MAXIMUM 50 mots — 3-4 phrases: modele de revenus du segment, produits ou services phares, clients cibles et principaux moteurs de croissance>","revenue_pct":<float 0-100>}},
    {{"name":"<nom segment 2>","description":"<MINIMUM 35, MAXIMUM 50 mots — 3-4 phrases: modele de revenus du segment, produits ou services phares, clients cibles et principaux moteurs de croissance>","revenue_pct":<float 0-100>}}
  ],
  "thesis":"<exactement 3 phrases separees par ' | ', chaque phrase 18-22 mots — catalyseurs d investissement concrets avec chiffres precis>",
  "strengths":["<MAXIMUM 8 mots — titre atout1>","<MAXIMUM 8 mots — titre atout2>","<MAXIMUM 8 mots — titre atout3>"],
  "risks":["<MAXIMUM 8 mots — titre risque1>","<MAXIMUM 8 mots — titre risque2>","<MAXIMUM 8 mots — titre risque3>"],
  "valuation_comment":"<2 phrases valorisation relative>",
  "financial_commentary":"<70 mots MAX — 2-3 phrases: (1) tendances chiffrees P&L (croissance CA, evolution marges), (2) POURQUOI ces tendances (levier operationnel, discipline cout, mix), (3) implication sur la generation de cash et la solidite bilancielle pour la these d'investissement>",
  "ratio_commentary":"<80 mots MAX — 2-3 phrases ANALYTIQUES sur le graphique MargesHistoriques: (1) decrire la tendance chiffree des marges brute/EBITDA/nette sur la periode, (2) expliquer POURQUOI ces niveaux (structure des couts, levier operationnel, mix produits, pricing power), (3) ce que ca implique pour l'investisseur (durabilite, re-rating potentiel, risque de compression)>",
  "dcf_commentary":"<60 mots MAX — 2 phrases: (1) rappeler WACC/TGR et le prix implicite DCF vs cours actuel, (2) expliquer ce que l'upside/downside implicite signifie pour la these: est-ce une sous-valorisation structurelle, une prime de croissance deja pricee, ou un risque d'execution? Quel catalyseur debloquerait la valeur?>",
  "peers_commentary":"<80 mots MAX — 2-3 phrases ANALYTIQUES: (1) position de la societe vs mediane peers sur EV/EBITDA et P/E (prime ou decote en %), (2) expliquer POURQUOI cette prime/decote est justifiee ou non (qualite des actifs, croissance superieure, risque specifique), (3) ce qu'une convergence vers la mediane implique comme upside/downside potentiel en %>",
  "positive_themes":["<20-30 mots: catalyseur + mecanisme d'impact financier + horizon temporel>","<20-30 mots: catalyseur + mecanisme d'impact financier + horizon temporel>","<20-30 mots: catalyseur + mecanisme d'impact financier + horizon temporel>"],
  "negative_themes":["<20-30 mots: risque specifique + mecanisme de deterioration + horizon temporel et ampleur potentielle>","<20-30 mots: risque specifique + mecanisme de deterioration + horizon temporel et ampleur potentielle>","<20-30 mots: risque specifique + mecanisme de deterioration + horizon temporel et ampleur potentielle>"],
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
    {{"label":"DCF - Bear","range_low":<prix_implicite_en_{ci.currency}>,"range_high":<prix_implicite_en_{ci.currency}>,"midpoint":<target_price_bear>}},
    {{"label":"DCF - Base","range_low":<prix_implicite_en_{ci.currency}>,"range_high":<prix_implicite_en_{ci.currency}>,"midpoint":<target_price_base>}},
    {{"label":"DCF - Bull","range_low":<prix_implicite_en_{ci.currency}>,"range_high":<prix_implicite_en_{ci.currency}>,"midpoint":<target_price_bull>}},
    {{"label":"EV/EBITDA - Mediane peers","range_low":<prix_implicite_en_{ci.currency}>,"range_high":<prix_implicite_en_{ci.currency}>,"midpoint":<prix_implicite_en_{ci.currency}>}},
    {{"label":"EV/EBITDA - Prime tech +50 %","range_low":<prix_implicite_en_{ci.currency}>,"range_high":<prix_implicite_en_{ci.currency}>,"midpoint":<prix_implicite_en_{ci.currency}>}},
    {{"label":"EV/Revenue - Mediane peers","range_low":<prix_implicite_en_{ci.currency}>,"range_high":<prix_implicite_en_{ci.currency}>,"midpoint":<prix_implicite_en_{ci.currency}>}}
  ],
  "IMPORTANT_football_field":"Tous les range_low/range_high/midpoint sont des PRIX PAR ACTION en {ci.currency} (ex: 280.5), JAMAIS des multiples bruts (ex: NE PAS mettre 15.2 pour EV/EBITDA). Calculer le prix implicite a partir du multiple et du EBITDA/Revenue par action.",
  "confidence_score":<0-1>,
  "invalidation_conditions":"<resume conditions>",
  "bear_hypothesis":"<15-20 mots — hypothese determinante scenario Bear : chiffre cle ou evenement declencheur>",
  "base_hypothesis":"<15-20 mots — hypothese determinante scenario Base : moteur principal croissance chiffre>",
  "bull_hypothesis":"<15-20 mots — hypothese determinante scenario Bull : catalyseur haussier concret chiffre>",
  "catalysts":[
    {{"title":"<titre 2-5 mots>","description":"<35-45 mots — analyse detaillee: impact financier, horizon, chiffres>"}},
    {{"title":"<titre 2-5 mots>","description":"<35-45 mots — analyse detaillee: impact financier, horizon, chiffres>"}},
    {{"title":"<titre 2-5 mots>","description":"<35-45 mots — analyse detaillee: impact financier, horizon, chiffres>"}}
  ],
  "buy_trigger":"<15-20 mots — condition precise declenchant revision BUY>",
  "sell_trigger":"<15-20 mots — condition precise declenchant revision SELL>",
  "conclusion":"<25-35 mots — synthese finale recommandation, risques residuels, horizon>",
  "next_review":"<prochaine revue ex: Q2 2026 resultats>"
}}"""


class AgentSynthese:
    def __init__(self, model: str = _DEFAULT_MODEL):
        self.llm = LLMProvider(provider="mistral", model="mistral-small-latest")

    def synthesize(self, snapshot, ratios, sentiment=None) -> Optional[SynthesisResult]:
        request_id = str(uuid.uuid4())
        t_start    = time.time()
        ci         = snapshot.company_info

        log.info(f"[AgentSynthese] Synthese '{snapshot.ticker}' — {request_id[:8]}")

        prompt = _build_prompt(snapshot, ratios, sentiment)
        raw = None
        try:
            raw = self.llm.generate(prompt=prompt, system=_SYSTEM, max_tokens=4000)
        except Exception as e:
            log.warning(f"[AgentSynthese] {self.llm.provider} echec ({type(e).__name__}: {e})")

        # Cascade fallback : Groq (primaire) → Mistral → Cerebras → Anthropic
        _fallbacks = [
            ("mistral",  "mistral-small-latest"),
            ("cerebras", "qwen-3-235b-a22b-instruct-2507"),
            ("anthropic", "claude-haiku-4-5-20251001"),
        ]
        for _prov, _model in _fallbacks:
            if raw:
                break
            log.warning(f"[AgentSynthese] fallback → {_prov}")
            try:
                _fb = LLMProvider(provider=_prov, model=_model)
                raw = _fb.generate(prompt=prompt, system=_SYSTEM, max_tokens=4000)
            except Exception as _e:
                log.error(f"[AgentSynthese] {_prov} echec ({type(_e).__name__}: {_e})")

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
            peers_commentary     = parsed.get("peers_commentary", ""),
            positive_themes      = parsed.get("positive_themes", []),
            negative_themes      = parsed.get("negative_themes", []),
            invalidation_list    = parsed.get("invalidation_list", []),
            comparable_peers     = parsed.get("comparable_peers", []),
            football_field       = parsed.get("football_field", []),
            is_projections       = parsed.get("is_projections", {}),
            confidence_score     = float(parsed.get("confidence_score", 0.5)),
            invalidation_conditions = parsed.get("invalidation_conditions", ""),
            bear_hypothesis      = parsed.get("bear_hypothesis", ""),
            base_hypothesis      = parsed.get("base_hypothesis", ""),
            bull_hypothesis      = parsed.get("bull_hypothesis", ""),
            catalysts            = parsed.get("catalysts", []),
            buy_trigger          = parsed.get("buy_trigger", ""),
            sell_trigger         = parsed.get("sell_trigger", ""),
            conclusion           = parsed.get("conclusion", ""),
            next_review          = parsed.get("next_review", ""),
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
