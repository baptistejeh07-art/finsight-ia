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


def _clamp_targets(price, base, bull, bear, ticker: str = "?"):
    """Borne les targets LLM si hallucinés (ex: ASML.AS bull 1450€ vs cours 650€).

    Règles réalistes :
      - base ∈ [price*0.85, price*1.25]
      - bull ∈ [price*1.05, price*1.40] ET bull >= base
      - bear ∈ [price*0.60, price*0.95] ET bear <= base

    Si le LLM sort de ces bornes, on replace la valeur par la borne la plus proche.
    """
    if not price or price <= 0:
        return base, bull, bear

    def _clamp(val, lo, hi):
        if val is None:
            return None
        try:
            return max(lo, min(val, hi))
        except (TypeError, ValueError):
            return None

    import logging
    log = logging.getLogger(__name__)

    orig_base, orig_bull, orig_bear = base, bull, bear
    base = _clamp(base, price * 0.85, price * 1.25)
    bull = _clamp(bull, price * 1.05, price * 1.40)
    bear = _clamp(bear, price * 0.60, price * 0.95)

    # Cohérence : bull >= base >= bear
    if base is not None and bull is not None and bull < base:
        bull = base * 1.08
    if base is not None and bear is not None and bear > base:
        bear = base * 0.90

    if (orig_base != base) or (orig_bull != bull) or (orig_bear != bear):
        log.warning(
            "[synthesis] %s targets clampés (LLM hallucination?) : "
            "base %s→%s, bull %s→%s, bear %s→%s (cours=%s)",
            ticker, orig_base, base, orig_bull, bull, orig_bear, bear, price,
        )

    return base, bull, bear


def _build_deterministic_fallback(snapshot, ratios) -> "SynthesisResult":
    """Genere un SynthesisResult de fallback quand TOUS les LLM ont echoue.

    Au lieu de retourner None (qui produit un PDF avec '—' partout), on
    populate les champs critiques depuis snapshot/ratios en utilisant des
    heuristiques deterministes. Le PDF est alors utilisable meme en cas
    de panne complete des providers LLM.

    Marqueurs : meta['fallback_mode'] = True pour que les writers puissent
    afficher un disclaimer si necessaire.
    """
    ci = snapshot.company_info
    mkt = snapshot.market
    price = mkt.share_price if mkt else None

    # Latest year ratios pour calcul cible
    latest_yr = None
    if ratios and getattr(ratios, "years", None):
        try:
            latest_yr = list(ratios.years.values())[-1]
        except Exception:
            pass

    # ── Cible 12M : a partir d'une simple regle multiple sectoriel ──
    # Si pas de Monte Carlo dispo, cible = price avec +/-15% bear/bull
    target_base = price
    target_bear = price * 0.85 if price else None
    target_bull = price * 1.20 if price else None

    # Recommendation deterministe : neutre par defaut
    recommendation = "HOLD"
    conviction = 0.50

    # ── Generations textuelles minimales ──
    _co = ci.company_name or ci.ticker
    _sec = ci.sector or "non specifie"
    _ev_ebitda = getattr(latest_yr, "ev_ebitda", None) if latest_yr else None
    _gross = getattr(latest_yr, "gross_margin", None) if latest_yr else None
    _ebitda_m = getattr(latest_yr, "ebitda_margin", None) if latest_yr else None
    _roe = getattr(latest_yr, "roe", None) if latest_yr else None

    _ratios_summary = []
    if _ev_ebitda is not None:
        _ratios_summary.append(f"EV/EBITDA {_ev_ebitda:.1f}x")
    if _ebitda_m is not None:
        _ratios_summary.append(f"marge EBITDA {_ebitda_m*100:.1f}%")
    if _roe is not None:
        _ratios_summary.append(f"ROE {_roe*100:.1f}%")
    _ratios_str = ", ".join(_ratios_summary) if _ratios_summary else "ratios LTM"

    thesis = (
        f"{_co} presente un profil financier {_ratios_str} dans le secteur {_sec}. "
        f"| L'analyse fondamentale indique un equilibre risque/rendement neutre a court terme. "
        f"| Une revision de la these necessite la confirmation des prochains catalyseurs operationnels."
    )

    summary = (
        f"Analyse fondamentale {_co} ({ci.ticker}) — secteur {_sec}. "
        f"Ratios cles : {_ratios_str}. Recommandation neutre par defaut, "
        f"a reviser selon evolution des fondamentaux et catalyseurs sectoriels."
    )

    company_description = (
        f"{_co} opere dans le secteur {_sec}. "
        f"Profil financier caractérisé par {_ratios_str}. "
        f"Description detaillee non disponible (mode fallback deterministe)."
    )

    catalysts = [
        {"title": "Publication trimestrielle",
         "description": f"Resultats du prochain trimestre — surveiller marges et guidance "
                        f"vs consensus. Impact direct sur la perception de la trajectoire."},
        {"title": "Evolution macro sectorielle",
         "description": f"Cycle {_sec} : taux directeurs, demande finale, et indicateurs "
                        f"avances PMI/credit. Toute inflexion macro impacte le re-rating."},
        {"title": "Annonces strategiques",
         "description": f"Operations M&A, lancement produits, ou changement de guidance "
                        f"peuvent declencher une revision rapide de la these."},
    ]

    risks = [
        {"title": "Compression des marges",
         "description": f"Pression concurrentielle ou hausse des couts intrants peuvent "
                        f"degrader la rentabilite operationnelle (marge EBITDA actuelle "
                        f"{_ebitda_m*100:.1f}% si dispo)." if _ebitda_m else
                        "Pression concurrentielle ou hausse des couts intrants."},
        {"title": "Choc macroeconomique",
         "description": "Recession, hausse des taux directeurs, ou degradation du credit "
                        "sectoriel peuvent declencher un de-rating significatif."},
        {"title": "Risque de revision baissiere",
         "description": "Les revisions du consensus sur les 1-2 prochains trimestres "
                        "constituent un signal d'alerte avance."},
    ]

    base_hypothesis = (
        f"Maintien des marges actuelles, croissance organique en ligne avec le secteur."
    )
    bear_hypothesis = (
        f"Compression marges -200 bps + ralentissement revenu -10% vs consensus."
    )
    bull_hypothesis = (
        f"Expansion marges +100 bps + acceleration revenu +15% vs consensus."
    )

    return SynthesisResult(
        ticker=snapshot.ticker,
        company_name=_co,
        recommendation=recommendation,
        conviction=conviction,
        target_base=target_base,
        target_bull=target_bull,
        target_bear=target_bear,
        summary=summary,
        company_description=company_description,
        thesis=thesis,
        risks=risks,
        catalysts=catalysts,
        bear_hypothesis=bear_hypothesis,
        base_hypothesis=base_hypothesis,
        bull_hypothesis=bull_hypothesis,
        confidence_score=0.30,  # signaler la basse confiance
        meta={
            "fallback_mode": True,
            "fallback_reason": "Tous les providers LLM ont echoue",
        },
    )


_SYSTEM = """Tu es un analyste financier senior Investment Banking.
Tu produis des analyses objectives, concises, professionnelles en français.
LANGUE : français avec TOUS les accents (é, è, ê, à, ù, ô, î, û, ç, œ, etc.) — JAMAIS de caractères sans accent (ex: "Modérée" et non "Moderee", "résilience" et non "resilience").
GRAMMAIRE : français IMPECCABLE — participes passés corrects (ex: "caractérisé par" et non "caractérise par", "marqué par" et non "marque par"), accords en genre/nombre, conjugaisons exactes, apostrophes droites.

CADRE DÉCISIONNEL — IMPORTANT :
Tu es le DÉCIDEUR pour la recommandation BUY/HOLD/SELL. Tu disposes dans le prompt de 4 sources :
  1. Les métriques fondamentales (P&L, bilan, cash-flow, multiples LTM)
  2. Le contexte macro ACTUEL (taux, VIX, régime de marché, probabilité récession)
  3. Les news RÉCENTES du ticker avec sentiment pré-calculé
  4. Ta connaissance sectorielle et des catalyseurs forward-looking

Tu dois pondérer intelligemment TOUTES ces sources. Le contexte macro et les news
récentes sont souvent décisifs — un bon ratio LTM dans un régime macro défavorable
ne vaut pas un BUY automatique. Tu peux contredire ce que les chiffres seuls
suggèrent si la macro ou les news justifient la divergence.

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

    # ── Contexte enrichi : macro live + news fresh ───────────────────────
    # Refonte #173-177 Baptiste : le LLM est le décideur, on lui donne TOUT
    # le contexte actuel (pas juste les chiffres LTM).
    _macro_news_block = ""
    try:
        from core.llm_context import (
            fetch_macro_live, format_macro_for_prompt,
            format_news_for_prompt,
        )
        _macro = fetch_macro_live()
        _parts = [
            "",  # saut de ligne avant
            "=" * 70,
            "CONTEXTE DÉCISIONNEL ENRICHI (pour décision éclairée)",
            "=" * 70,
            format_macro_for_prompt(_macro),
            "",
            format_news_for_prompt(sentiment, ticker=ci.ticker),
            "=" * 70,
            "",
        ]
        _macro_news_block = "\n".join(_parts)
    except Exception as _e_ctx:
        log.warning(f"[agent_synthese] contexte enrichi fail: {_e_ctx}")

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

    # Multi-year revenue trend for context
    rev_series = []
    for hy in hist_years_sorted:
        hyr_raw = snapshot.years.get(hy)
        hyr_rat = ratios.years.get(hy)
        if hyr_raw and hyr_rat:
            rev_val = getattr(hyr_raw, 'revenue', None)
            gr_val  = getattr(hyr_rat, 'revenue_growth', None)
            if rev_val:
                gr_s = f" (+{gr_val*100:.1f}%)" if gr_val and gr_val > 0 else (f" ({gr_val*100:.1f}%)" if gr_val else "")
                rev_series.append(f"{hy}:{_f(rev_val)}M{gr_s}")
    rev_series_str = " | ".join(rev_series) if rev_series else "N/A"

    # FCF and capital allocation
    fcf_s = "N/A"
    capex_s = "N/A"
    div_s = "N/A"
    if yr:
        raw_yr = snapshot.years.get(latest)
        if raw_yr:
            fcf_val = getattr(raw_yr, 'free_cash_flow', None)
            capex_val = getattr(raw_yr, 'capex', None)
            div_val = getattr(raw_yr, 'dividends', None)
            if fcf_val: fcf_s = f"{_f(fcf_val)}M"
            if capex_val: capex_s = f"{_f(abs(capex_val))}M"
            if div_val: div_s = f"{_f(abs(div_val))}M"

    # Sector median multiples for context (approximate)
    _SECTOR_PE = {"Technology":30,"Healthcare":22,"Financials":13,"Consumer Discretionary":20,
                  "Consumer Staples":18,"Industrials":21,"Energy":12,"Materials":15,"Utilities":20}
    sector_pe_med = _SECTOR_PE.get(ci.sector or "", None)
    sector_ctx = f"Mediane sectorielle P/E: {sector_pe_med}x" if sector_pe_med else ""

    # Balance sheet quality
    bs_ctx = ""
    if yr:
        nd = yr.net_debt_ebitda
        az = yr.altman_z
        ic = getattr(yr, 'interest_coverage', None)
        bs_parts = []
        if nd is not None: bs_parts.append(f"ND/EBITDA:{_f(nd)}x")
        if az is not None: bs_parts.append(f"AltmanZ:{_f(az,2)}")
        if ic is not None: bs_parts.append(f"IntCov:{_f(ic,1)}x")
        bs_ctx = " | ".join(bs_parts)

    # ─── Profil sectoriel (banque, REIT, utility, etc.) → adapte les hints LLM ───
    try:
        from core.sector_profiles import detect_profile, get_prompt_hints, is_non_standard
        _industry = getattr(ci, 'industry', '') or ''
        _profile = detect_profile(ci.sector, _industry)
        _profile_hints = get_prompt_hints(_profile) if is_non_standard(_profile) else ""
    except Exception:
        _profile = "STANDARD"
        _profile_hints = ""
    _profile_section = f"\nPROFIL SECTORIEL SPÉCIFIQUE : {_profile_hints}" if _profile_hints else ""

    # ─── Instructions is_projections adaptées au profil ───────────────────────
    # Pour BANK/INSURANCE, EBITDA n'a pas de sens : on autorise revenue=NII+fees
    # et ebitda=Pre-Provision Profit. Sinon le LLM retourne du texte invalide.
    if _profile == "BANK":
        _proj_hint = (
            "\nPOUR LES BANQUES : dans is_projections, 'revenue' = Total Revenue "
            "(NII + commissions + trading), 'ebitda' = Pre-Provision Profit (PPOP), "
            "'gross_margin' et 'ebitda_margin' = NIM (Net Interest Margin, 1-4%), "
            "'net_margin' = profit margin net. Ne renvoie PAS null — donne des "
            "estimations chiffrées plausibles même approximatives."
        )
    elif _profile == "INSURANCE":
        _proj_hint = (
            "\nPOUR LES ASSUREURS : 'revenue' = Gross Written Premiums, "
            "'ebitda' = Operating Result avant taxes, 'gross_margin' = (1 - Loss Ratio), "
            "'ebitda_margin' = (1 - Combined Ratio), 'net_margin' = ROE/2 approximation."
        )
    elif _profile == "REIT":
        _proj_hint = (
            "\nPOUR LES REITs : 'revenue' = Rental Income total, 'ebitda' = NOI "
            "(Net Operating Income), 'gross_margin' = NOI margin (70-90%), "
            "'ebitda_margin' = idem. 'net_margin' souvent <10% (dépréciations)."
        )
    else:
        _proj_hint = ""

    return f"""Analyse {ci.company_name} ({ci.ticker}) — secteur:{ci.sector} — {date.today().isoformat()}
Cours:{price_s} {ci.currency} | WACC:{wacc_s} | TGR:{tgr_s}
{chr(10).join(lines)}
RevenuHistorique: {rev_series_str}
MargesHistoriques: {margins_series_str}
FCF:{fcf_s} | Capex:{capex_s} | Dividendes:{div_s}
BilanQualite: {bs_ctx}
{sector_ctx}{_profile_section}
Sentiment: {sent_block}{_proj_hint}
{_macro_news_block}
JSON requis (tous les champs obligatoires) :
{{
  "recommendation":"BUY|HOLD|SELL",
  "conviction":<float 0-1 — calcule strictement: SELL=0.3-0.5, HOLD=0.45-0.60, BUY faible=0.60-0.70, BUY fort=0.70-0.85; NE PAS depasser 0.85 sauf catalyseur exceptionnel>,
  "target_price_base":<float — ANCRÉ AU COURS ACTUEL {price_s} {ci.currency} ; plage RÉALISTE entre cours*0.85 et cours*1.20 ; JAMAIS >cours*1.30>,
  "target_price_bull":<float — SCÉNARIO OPTIMISTE mais RÉALISTE ; plage cours*1.10 à cours*1.35 ; upside MAX +40% vs cours actuel>,
  "target_price_bear":<float — SCÉNARIO BAISSIER ; plage cours*0.65 à cours*0.90 ; TOUJOURS <cours actuel (sinon pas un bear) ; downside ~-15% à -30%>,
  "summary":"<2 phrases>",
  "company_description":"<MINIMUM 50, MAXIMUM 70 mots — 3 phrases: activite principale, positionnement marche, avantages competitifs de {ci.company_name}>",
  "segments":[
    {{"name":"<nom exact segment operationnel>","description":"<EXACTEMENT 22-30 mots — 2 phrases denses: modele de revenus + driver principal. Box d affichage limitee, depassement = texte coupe>","revenue_pct":<float 0-100>}},
    {{"name":"<nom segment 2>","description":"<EXACTEMENT 22-30 mots — 2 phrases denses: modele de revenus + driver principal>","revenue_pct":<float 0-100>}}
  ],
  "thesis":"<exactement 3 phrases separees par ' | ', chaque phrase 12-18 mots STRICT — catalyseurs d investissement concrets avec chiffres precis. Depassement = texte coupe sur slide>",
  "strengths":["<MAXIMUM 8 mots — titre atout1>","<MAXIMUM 8 mots — titre atout2>","<MAXIMUM 8 mots — titre atout3>"],
  "risks":["<MAXIMUM 8 mots — titre risque1>","<MAXIMUM 8 mots — titre risque2>","<MAXIMUM 8 mots — titre risque3>"],
  "valuation_comment":"<EXACTEMENT 30-40 mots STRICT — 2 phrases courtes valorisation relative + lecture investisseur>",
  "financial_commentary":"<EXACTEMENT 55-65 mots STRICT. OBLIGATOIRE: (1) chiffre precis CA + croissance YoY, (2) mecanisme variation de marge (ex: levier operationnel +Xpts mix logiciel OU pression prix matieres +X%), (3) implication FCF/bilan (ND/EBITDA, capacite rachat). Citer chiffres.>",
  "ratio_commentary":"<EXACTEMENT 55-65 mots STRICT. OBLIGATOIRE: (1) evolution marges EBITDA/brute sur la periode (de X% en 20xx a Y% en 20xx), (2) mecanisme PRECIS de la trajectoire (volume/prix, mix produits, economie d echelle OU inflation), (3) durabilite pricing power et risque mean-reversion.>",
  "dcf_commentary":"<EXACTEMENT 30-35 mots STRICT — 2 phrases courtes: (1) WACC/TGR + prix implicite DCF vs cours, (2) lecture upside/downside (sous-valorisation, prime pricee, risque execution). Box etroite.>",
  "peers_commentary":"<EXACTEMENT 100-130 mots STRICT — 3 phrases ANALYTIQUES: (1) position vs mediane peers sur EV/EBITDA et P/E (prime ou decote en %), (2) POURQUOI cette prime/decote est justifiee ou non (qualite actifs, croissance superieure, risque specifique), (3) implication d'une convergence vers la mediane (upside/downside %).>",
  "positive_themes":["<EXACTEMENT 15-20 mots STRICT: catalyseur + mecanisme + horizon. Box affichage limitee>","<EXACTEMENT 15-20 mots STRICT>","<EXACTEMENT 15-20 mots STRICT>"],
  "negative_themes":["<EXACTEMENT 15-20 mots STRICT: risque specifique + mecanisme + horizon. Box affichage limitee>","<EXACTEMENT 15-20 mots STRICT>","<EXACTEMENT 15-20 mots STRICT>"],
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
    {{"title":"<titre 2-5 mots>","description":"<EXACTEMENT 18-25 mots STRICT — impact financier, horizon, chiffres. Box etroite slide>"}},
    {{"title":"<titre 2-5 mots>","description":"<EXACTEMENT 18-25 mots STRICT>"}},
    {{"title":"<titre 2-5 mots>","description":"<EXACTEMENT 18-25 mots STRICT>"}}
  ],
  "buy_trigger":"<15-20 mots — condition precise declenchant revision BUY>",
  "sell_trigger":"<15-20 mots — condition precise declenchant revision SELL>",
  "conclusion":"<25-35 mots — synthese finale recommandation, risques residuels, horizon>",
  "next_review":"<prochaine revue ex: Q2 2026 resultats>"
}}"""


class AgentSynthese:
    def __init__(self, model: str = _DEFAULT_MODEL, language: str = "fr"):
        self.llm = LLMProvider(provider="groq", model="llama-3.3-70b-versatile")
        self.language = language

    def _system_prompt(self) -> str:
        """System prompt avec directive de langue dynamique (i18n)."""
        try:
            from core.i18n import system_language_directive
            directive = system_language_directive(self.language)
        except Exception:
            directive = ""
        return f"{_SYSTEM}\n\n{directive}"

    def synthesize(self, snapshot, ratios, sentiment=None) -> Optional[SynthesisResult]:
        request_id = str(uuid.uuid4())
        t_start    = time.time()
        ci         = snapshot.company_info

        log.info(f"[AgentSynthese] Synthese '{snapshot.ticker}' — {request_id[:8]} (lang={self.language})")

        prompt = _build_prompt(snapshot, ratios, sentiment)
        system_prompt = self._system_prompt()
        raw = None
        # Collecte des erreurs par provider pour diagnostic
        _provider_errors: dict[str, str] = {}
        _provider_used: Optional[str] = None
        _provider_ms: dict[str, int] = {}
        _t_prov = time.time()
        try:
            raw = self.llm.generate(prompt=prompt, system=system_prompt, max_tokens=4000)
            _provider_ms[self.llm.provider] = int((time.time() - _t_prov) * 1000)
            if raw:
                _provider_used = self.llm.provider
        except Exception as e:
            _provider_ms[self.llm.provider] = int((time.time() - _t_prov) * 1000)
            _err_msg = f"{type(e).__name__}: {str(e)[:120]}"
            _provider_errors[self.llm.provider] = _err_msg
            log.warning(f"[AgentSynthese] {self.llm.provider} echec ({_err_msg}) en {_provider_ms[self.llm.provider]}ms")

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
            _t_prov = time.time()
            try:
                _fb_llm = LLMProvider(provider=_prov, model=_model)
                raw = _fb_llm.generate(prompt=prompt, system=system_prompt, max_tokens=4000)
                _provider_ms[_prov] = int((time.time() - _t_prov) * 1000)
                if raw:
                    _provider_used = _prov
            except Exception as _e:
                _provider_ms[_prov] = int((time.time() - _t_prov) * 1000)
                _err_msg = f"{type(_e).__name__}: {str(_e)[:120]}"
                _provider_errors[_prov] = _err_msg
                log.error(f"[AgentSynthese] {_prov} echec ({_err_msg}) en {_provider_ms[_prov]}ms")

        if not raw:
            log.error("[AgentSynthese] Tous les providers ont echoue — fallback deterministe")
            _fb = _build_deterministic_fallback(snapshot, ratios)
            _fb.meta["latency_ms"] = int((time.time() - t_start) * 1000)
            # Detail des erreurs par provider pour diagnostic UI
            _fb.meta["provider_errors"] = _provider_errors
            # Resume lisible : "groq: rate_limit | mistral: API key missing | ..."
            _fb.meta["fallback_reason"] = " | ".join(
                f"{p}: {e[:60]}" for p, e in _provider_errors.items()
            ) or "Tous les providers LLM ont echoue"
            return _fb

        latency_ms = int((time.time() - t_start) * 1000)
        parsed = _parse_json(raw)
        if not parsed:
            log.error(f"[AgentSynthese] JSON non parseable — fallback deterministe :\n{raw[:300]}")
            _fb = _build_deterministic_fallback(snapshot, ratios)
            _fb.meta["latency_ms"] = latency_ms
            _fb.meta["fallback_reason"] = "JSON LLM non parseable"
            return _fb

        # Helper : cast safe en float (LLM peut retourner string, null, dict)
        def _fnum(v):
            if v is None: return None
            try: return float(v)
            except (TypeError, ValueError): return None

        # ─── Safeguard valorisations : clamp si LLM hallucine ─────────────
        # Ex: ASML.AS cours ~650€ mais LLM target_bull 1450€ (+123%). Borner.
        _raw_base = _fnum(parsed.get("target_price_base"))
        _raw_bull = _fnum(parsed.get("target_price_bull"))
        _raw_bear = _fnum(parsed.get("target_price_bear"))
        _clamped_base, _clamped_bull, _clamped_bear = _clamp_targets(
            price, _raw_base, _raw_bull, _raw_bear, ticker=snapshot.ticker
        )
        # Fallback prix cibles si LLM a omis (bug prod détecté 2026-04-19 AAPL)
        # Empêche les "—" dans PDF/PPTX quand parsing JSON partiel.
        if _clamped_base is None and price:
            _clamped_base = price
            log.warning(f"[AgentSynthese] target_price_base absent du JSON LLM — fallback à price={price}")
        if _clamped_bull is None and price:
            _clamped_bull = price * 1.20
        if _clamped_bear is None and price:
            _clamped_bear = price * 0.85

        # Merge avec fallback déterministe si champs critiques manquants.
        # Bug prod 2026-04-19 : LLM peut renvoyer JSON valide mais avec
        # risks/catalysts/thesis vides → PDF/PPTX affichent "—" partout.
        _fb_template = None
        def _need_fb():
            nonlocal _fb_template
            if _fb_template is None:
                _fb_template = _build_deterministic_fallback(snapshot, ratios)
            return _fb_template

        _parsed_risks = parsed.get("risks") or []
        _parsed_catalysts = parsed.get("catalysts") or []
        _parsed_thesis = parsed.get("thesis") or ""
        if not _parsed_risks:
            _parsed_risks = _need_fb().risks
            log.warning("[AgentSynthese] risks absent du JSON LLM — fallback déterministe")
        if not _parsed_catalysts:
            _parsed_catalysts = _need_fb().catalysts
            log.warning("[AgentSynthese] catalysts absent du JSON LLM — fallback déterministe")
        if not _parsed_thesis:
            _parsed_thesis = _need_fb().thesis
        _parsed_desc = parsed.get("company_description") or ""
        if not _parsed_desc:
            _parsed_desc = _need_fb().company_description
        _parsed_bull_h = parsed.get("bull_hypothesis") or ""
        if not _parsed_bull_h:
            _parsed_bull_h = _need_fb().bull_hypothesis
        _parsed_base_h = parsed.get("base_hypothesis") or ""
        if not _parsed_base_h:
            _parsed_base_h = _need_fb().base_hypothesis
        _parsed_bear_h = parsed.get("bear_hypothesis") or ""
        if not _parsed_bear_h:
            _parsed_bear_h = _need_fb().bear_hypothesis

        result = SynthesisResult(
            ticker               = snapshot.ticker,
            company_name         = ci.company_name,
            recommendation       = parsed.get("recommendation", "HOLD").upper(),
            conviction           = _fnum(parsed.get("conviction")) or 0.5,
            target_base          = _clamped_base,
            target_bull          = _clamped_bull,
            target_bear          = _clamped_bear,
            summary              = parsed.get("summary", ""),
            company_description  = _parsed_desc,
            segments             = parsed.get("segments", []),
            thesis               = _parsed_thesis,
            strengths            = parsed.get("strengths", []),
            risks                = _parsed_risks,
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
            confidence_score     = _fnum(parsed.get("confidence_score")) or 0.5,
            invalidation_conditions = parsed.get("invalidation_conditions", ""),
            bear_hypothesis      = _parsed_bear_h,
            base_hypothesis      = _parsed_base_h,
            bull_hypothesis      = _parsed_bull_h,
            catalysts            = _parsed_catalysts,
            buy_trigger          = parsed.get("buy_trigger", ""),
            sell_trigger         = parsed.get("sell_trigger", ""),
            conclusion           = parsed.get("conclusion", ""),
            next_review          = parsed.get("next_review", ""),
            meta = {
                "request_id":  request_id,
                "model":       self.llm.model,
                "latency_ms":  latency_ms,
                "tokens_used": None,
                "confidence_score": _fnum(parsed.get("confidence_score")) or 0.5,
                "invalidation_conditions": parsed.get("invalidation_conditions", ""),
                "provider": _provider_used,
                "provider_ms": _provider_ms,
                "provider_errors": _provider_errors,
            },
        )

        log.info(
            f"[AgentSynthese] '{snapshot.ticker}' — provider={_provider_used} "
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
