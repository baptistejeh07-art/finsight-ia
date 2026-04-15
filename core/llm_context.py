# -*- coding: utf-8 -*-
"""
core/llm_context.py — Helpers partagés pour enrichir le contexte LLM.

Ce module centralise la construction du contexte riche injecté dans les
prompts des agents LLM (agent_synthese, cmp_societe._generate_synthesis,
etc.) pour permettre un choix éclairé :

1. **Macro live** : VIX, 10Y, 3M, DXY, régime de marché, proba récession
   (cache 15 min parce que ces chiffres bougent en minute pendant les
   heures de marché).

2. **News fresh** : 5 headlines récents par ticker avec sentiment pré-calculé
   via FinBERT + LLM (on utilise les samples déjà produits par AgentSentiment
   dans le pipeline, donc pas de re-fetch Finnhub — cache 5h).

3. **Score FinSight expliqué** : le score 0-100 n'est plus une vérité mais
   une indication. On fournit au LLM le détail (Value/Growth/Quality/Momentum)
   + la méthodologie pour qu'il puisse pondérer intelligemment.

4. **Formatage prompt** : helpers format_*_for_prompt() qui retournent des
   blocs de texte prêts à insérer dans le système de messages LLM.

Design :
- Zéro I/O direct côté appelant — tout passe par ces helpers.
- Cache TTL en dict module-level (pas de st.cache_data pour compatibilité
  CLI / tests unitaires).
- Thread-safe simple (pas de parallélisation massive attendue).
"""
from __future__ import annotations

import logging
import time
from typing import Optional

log = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# CACHE MODULE-LEVEL (TTL simple)
# ═════════════════════════════════════════════════════════════════════════════

_MACRO_CACHE: dict = {"ts": 0.0, "data": None}
_NEWS_CACHE: dict = {}  # ticker → {"ts": float, "data": dict}

_MACRO_TTL_SEC = 15 * 60       # 15 min — macro bouge en minute pendant RTH
_NEWS_TTL_SEC  = 5 * 60 * 60   # 5h — news cycles relativement lents


# ═════════════════════════════════════════════════════════════════════════════
# MACRO LIVE
# ═════════════════════════════════════════════════════════════════════════════

def fetch_macro_live() -> dict:
    """Retourne un snapshot macro live avec cache 15 min.

    Wrapping de AgentMacro.analyze() + enrichissement avec les valeurs
    live depuis yfinance (VIX, 10Y, 3M, DXY déjà dans AgentMacro) et
    fallback gracieux si AgentMacro échoue.

    Returns:
        dict avec les clés : regime, vix, tnx_10y, irx_3m, spread_10y_3m,
        recession_prob_6m, recession_prob_12m, recession_level,
        recession_drivers, sp_vs_ma200, sp_mom_6m, timestamp_ms.
    """
    now = time.time()
    if _MACRO_CACHE["data"] is not None and (now - _MACRO_CACHE["ts"]) < _MACRO_TTL_SEC:
        return _MACRO_CACHE["data"]

    data = {
        "regime":             None,
        "vix":                None,
        "tnx_10y":            None,
        "irx_3m":             None,
        "spread_10y_3m":      None,
        "recession_prob_6m":  None,
        "recession_prob_12m": None,
        "recession_level":    None,
        "recession_drivers":  [],
        "sp_vs_ma200":        None,
        "sp_mom_6m":          None,
        "timestamp_ms":       int(now * 1000),
    }

    try:
        from agents.agent_macro import AgentMacro
        macro_res = AgentMacro().analyze()
        if isinstance(macro_res, dict):
            for k in data.keys():
                if k in macro_res and macro_res[k] is not None:
                    data[k] = macro_res[k]
    except Exception as e:
        log.warning(f"[llm_context] AgentMacro fail: {e}")

    _MACRO_CACHE["data"] = data
    _MACRO_CACHE["ts"]   = now
    return data


def format_macro_for_prompt(macro: dict) -> str:
    """Formate le dict macro en bloc texte pour injection dans le prompt LLM."""
    if not macro:
        return "CONTEXTE MACRO : indisponible"

    lines = ["CONTEXTE MACRO ACTUEL (live, cache 15min)"]
    lines.append("━" * 60)

    regime = macro.get("regime") or "—"
    lines.append(f"Régime de marché       : {regime}")

    vix = macro.get("vix")
    if vix is not None:
        _vix_read = ("calme" if vix < 15 else "normal" if vix < 20 else "stressé" if vix < 30 else "panique")
        lines.append(f"VIX                     : {vix:.1f}  ({_vix_read})")

    tnx = macro.get("tnx_10y")
    irx = macro.get("irx_3m")
    spread = macro.get("spread_10y_3m")
    if tnx is not None:
        lines.append(f"Taux US 10Y             : {tnx:.2f}%")
    if irx is not None:
        lines.append(f"Taux US 3M              : {irx:.2f}%")
    if spread is not None:
        _sp_read = "inversée (alerte récession)" if spread < 0 else "normale" if spread > 0.5 else "plate"
        lines.append(f"Spread 10Y-3M           : {spread:+.2f}%  ({_sp_read})")

    rec6 = macro.get("recession_prob_6m")
    rec12 = macro.get("recession_prob_12m")
    rec_lvl = macro.get("recession_level")
    if rec6 is not None:
        lines.append(f"Proba récession 6M/12M  : {rec6}% / {rec12}%  ({rec_lvl or '—'})")

    drivers = macro.get("recession_drivers") or []
    if drivers:
        lines.append(f"Drivers récession       : {', '.join(drivers[:3])}")

    sp_ma200 = macro.get("sp_vs_ma200")
    sp_mom = macro.get("sp_mom_6m")
    if sp_ma200 is not None:
        _ma_read = "au-dessus" if sp_ma200 > 0 else "sous"
        lines.append(f"S&P 500 vs MA200        : {sp_ma200:+.1f}% ({_ma_read} la moyenne)")
    if sp_mom is not None:
        lines.append(f"S&P 500 momentum 6M     : {sp_mom:+.1f}%")

    return "\n".join(lines)


# ═════════════════════════════════════════════════════════════════════════════
# NEWS FRESH (via AgentSentiment)
# ═════════════════════════════════════════════════════════════════════════════

def format_news_for_prompt(sentiment_result, ticker: str = "") -> str:
    """Formate un SentimentResult en bloc news + sentiment pour le prompt LLM.

    Utilise les `samples` déjà calculés par AgentSentiment (Finnhub + RSS,
    sentiment via FinBERT + LLM). Pas de re-fetch ici.

    Args:
        sentiment_result : SentimentResult instance (ou None)
        ticker : pour l'en-tête du bloc

    Returns:
        Bloc texte multi-ligne prêt pour le prompt.
    """
    if sentiment_result is None:
        return f"NEWS RÉCENTES {ticker} : aucune news disponible"

    _label = getattr(sentiment_result, "label", "NEUTRAL")
    _score = getattr(sentiment_result, "score", 0.0)
    _n_articles = getattr(sentiment_result, "articles_analyzed", 0)
    _samples = getattr(sentiment_result, "samples", None) or []
    _commentary = getattr(sentiment_result, "llm_commentary", "") or ""

    lines = [f"NEWS RÉCENTES {ticker} (7 derniers jours, sentiment FinBERT+LLM)"]
    lines.append("━" * 60)
    lines.append(f"Sentiment global        : {_label}  (score {_score:+.2f}, {_n_articles} articles)")

    if _commentary:
        # Commentaire LLM pré-écrit par AgentSentiment (si dispo)
        lines.append(f"Lecture analytique      : {_commentary[:400]}")

    if _samples:
        lines.append("")
        lines.append("Headlines représentatifs :")
        for i, s in enumerate(_samples[:5], 1):
            _h = (s.get("headline") or "")[:120]
            _lbl = s.get("label", "?")
            _src = s.get("source", "")
            lines.append(f"  {i}. [{_lbl:8s}] {_h}  ({_src})")

    return "\n".join(lines)


# ═════════════════════════════════════════════════════════════════════════════
# FINSIGHT SCORE EXPLICATION
# ═════════════════════════════════════════════════════════════════════════════

_FINSIGHT_METHODOLOGY_SHORT = (
    "Le score FinSight (0-100) est une INDICATION QUANTITATIVE RÉTROSPECTIVE "
    "calibrée sur 4 dimensions équipondérées (25% chacune) : "
    "Value (multiples bas = mieux : EV/EBITDA, P/E, EV/Rev), "
    "Growth (croissance revenue LTM + NTM), "
    "Quality (marges, Altman Z, Current Ratio pour STANDARD ; ROE+ROA pour BANK), "
    "Momentum (performance 52 semaines). "
    "Chaque dimension est un percentile rank contre le pool analysé "
    "(0 = pire, 100 = meilleur). "
    "LIMITE : le score est 100% rétrospectif (données LTM), il ne tient PAS compte "
    "des catalyseurs forward-looking, du sentiment des news récentes, ni du contexte "
    "macro actuel — ces éléments sont à intégrer par la décision finale."
)

_FINSIGHT_METHODOLOGY_DETAIL = {
    "Value":    "EV/EBITDA, P/E, EV/Revenue — plus bas = mieux (BANK : P/E + P/B, REIT : P/E + P/B, UTILITY : P/E + EV/EBITDA)",
    "Growth":   "revenue_growth LTM + ebitda_ntm_growth — plus haut = mieux",
    "Quality":  "gross_margin, net_margin, current_ratio, Altman Z (STANDARD) | ROE + net_margin (BANK/INSURANCE/REIT) | net_margin + ROE + ebitda_margin (UTILITY)",
    "Momentum": "perf_52w (performance cours 52 semaines) — plus haut = mieux",
}


def format_finsight_explanation(
    score_global: Optional[float],
    score_value: Optional[float] = None,
    score_growth: Optional[float] = None,
    score_quality: Optional[float] = None,
    score_momentum: Optional[float] = None,
    profile: str = "STANDARD",
    ticker: str = "",
) -> str:
    """Formate le score FinSight + son explication pour le prompt LLM.

    Args:
        score_global : score composite 0-100 (ou None)
        score_value/growth/quality/momentum : sous-scores 0-100
        profile : profil sectoriel détecté (STANDARD/BANK/INSURANCE/REIT/UTILITY/OIL_GAS)
        ticker : pour l'en-tête

    Returns:
        Bloc texte multi-ligne.
    """
    if score_global is None:
        return f"SCORE FINSIGHT {ticker} : indisponible"

    def _fmt(v):
        return f"{int(v)}/100" if v is not None else "N/A"

    def _read(v):
        if v is None: return "—"
        if v >= 75:   return "fort"
        if v >= 50:   return "moyen"
        if v >= 25:   return "faible"
        return "très faible"

    lines = [f"SCORE FINSIGHT {ticker} (indication quantitative rétrospective — non décisionnelle)"]
    lines.append("━" * 60)
    lines.append(f"Score composite global  : {_fmt(score_global)}  ({_read(score_global)})")
    lines.append(f"  • Value     (25%)     : {_fmt(score_value)}      ({_read(score_value)})")
    lines.append(f"  • Growth    (25%)     : {_fmt(score_growth)}     ({_read(score_growth)})")
    lines.append(f"  • Quality   (25%)     : {_fmt(score_quality)}    ({_read(score_quality)})")
    lines.append(f"  • Momentum  (25%)     : {_fmt(score_momentum)}   ({_read(score_momentum)})")
    lines.append(f"Profil sectoriel détecté : {profile}")
    lines.append("")
    lines.append("MÉTHODOLOGIE :")
    lines.append(_FINSIGHT_METHODOLOGY_SHORT)
    return "\n".join(lines)


# ═════════════════════════════════════════════════════════════════════════════
# BLOC INSTRUCTION LLM (à insérer dans les system messages)
# ═════════════════════════════════════════════════════════════════════════════

LLM_DECISION_FRAMING = (
    "CADRE DÉCISIONNEL FINSIGHT IA — IMPORTANT :\n"
    "Le score FinSight fourni dans le contexte ci-dessous est une INDICATION "
    "quantitative, PAS une recommandation. Il est 100% rétrospectif et ne tient "
    "pas compte du sentiment des news, ni du contexte macro, ni des catalyseurs "
    "forward-looking.\n\n"
    "TA MISSION : prendre une décision ÉCLAIRÉE en pondérant intelligemment :\n"
    "  1. Les métriques fondamentales (P&L, bilan, cash-flow, multiples)\n"
    "  2. Le contexte macro actuel (taux, VIX, récession)\n"
    "  3. Le sentiment des news récentes\n"
    "  4. Le score FinSight comme REPÈRE chiffré (pas comme vérité)\n"
    "  5. Ta connaissance du secteur et des catalyseurs structurels\n\n"
    "Tu peux CHOISIR de contredire le score FinSight si le contexte macro, les "
    "news ou les catalyseurs forward-looking le justifient — dans ce cas, "
    "explique explicitement POURQUOI tu diverges du score.\n"
    "Tu peux aussi hésiter (verdict NEUTRE / 'Pas de préférence forte') si les "
    "arguments pour et contre sont équilibrés. C'est une décision honnête, "
    "préférable à un choix arbitraire."
)


def build_full_context_block(
    ticker: str,
    sentiment_result=None,
    score_global: Optional[float] = None,
    score_value: Optional[float] = None,
    score_growth: Optional[float] = None,
    score_quality: Optional[float] = None,
    score_momentum: Optional[float] = None,
    profile: str = "STANDARD",
) -> str:
    """Retourne un bloc complet macro + news + finsight pour injecter dans
    le prompt d'un LLM de décision (agent_synthese, verdict cmp, etc.).
    """
    parts = []

    # 1. Macro live (global, partagé entre tous les tickers)
    macro = fetch_macro_live()
    parts.append(format_macro_for_prompt(macro))

    # 2. News fresh (par ticker)
    parts.append(format_news_for_prompt(sentiment_result, ticker=ticker))

    # 3. Score FinSight expliqué
    parts.append(format_finsight_explanation(
        score_global=score_global,
        score_value=score_value,
        score_growth=score_growth,
        score_quality=score_quality,
        score_momentum=score_momentum,
        profile=profile,
        ticker=ticker,
    ))

    return "\n\n".join(parts)
