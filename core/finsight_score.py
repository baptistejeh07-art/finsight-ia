# -*- coding: utf-8 -*-
"""
core/finsight_score.py — Score FinSight propriétaire (note 0-100 composite).

Quatre dimensions (25 pts max chacune, total 100) :
  - **Qualité** : ROIC, marges nettes, ND/EBITDA, Altman Z, Piotroski F
  - **Valorisation** : P/E, EV/EBITDA, FCF Yield vs médiane sectorielle
  - **Momentum** : 52-week change, croissance revenue YoY, beta
  - **Gouvernance** : payout ratio, dividend track record, dilution

API simple :

    from core.finsight_score import compute_score

    score = compute_score(
        ratios={"pe_ratio": 18.5, "roe": 0.32, ...},
        market={"share_price": 150, "beta_levered": 1.1, ...},
        sector_analytics={"pe_median_ltm": 25, ...},   # optionnel
    )
    # score = {
    #   "global": 72,
    #   "quality": 21,
    #   "value": 16,
    #   "momentum": 19,
    #   "governance": 16,
    #   "verdict": "Bon investissement (BUY)",
    #   "details": {...}
    # }

Déterministe — pas de LLM. Documenté dans /methodologie pour transparence.
Reproduit Bloomberg-style (Score, Recommendation, Conviction) mais propre à
FinSight et adaptable par secteur.
"""
from __future__ import annotations

from typing import Optional


def _safe(v) -> Optional[float]:
    try:
        f = float(v)
        if f != f or abs(f) == float("inf"):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _scale(v: Optional[float], low: float, high: float, max_pts: float) -> float:
    """Score linéaire entre [low, high] → [0, max_pts]. Clamp aux bornes."""
    if v is None:
        return 0.0
    if v <= low:
        return 0.0
    if v >= high:
        return max_pts
    return round(((v - low) / (high - low)) * max_pts, 2)


def _scale_inverse(v: Optional[float], low: float, high: float, max_pts: float) -> float:
    """Score inverse : meilleur quand v plus bas (ex: P/E, ND/EBITDA)."""
    if v is None:
        return 0.0
    if v <= low:
        return max_pts
    if v >= high:
        return 0.0
    return round(((high - v) / (high - low)) * max_pts, 2)


# ═══ QUALITÉ (25 pts) ═════════════════════════════════════════════════════
def _quality_score(ratios: dict) -> tuple[float, dict]:
    """ROIC + Marges + Solvabilité + Altman + Piotroski."""
    roic = _safe(ratios.get("roic"))
    net_m = _safe(ratios.get("net_margin"))
    nd_ebitda = _safe(ratios.get("net_debt_ebitda"))
    altman = _safe(ratios.get("altman_z"))
    piotroski = _safe(ratios.get("piotroski_f"))

    # Conversion % → décimal si nécessaire
    if roic is not None and abs(roic) > 1.5:
        roic = roic / 100.0
    if net_m is not None and abs(net_m) > 1.5:
        net_m = net_m / 100.0

    s_roic = _scale(roic, 0.05, 0.30, 7)         # 5%-30% → 0-7 pts
    s_marg = _scale(net_m, 0.0, 0.25, 5)         # 0-25% net margin → 0-5 pts
    s_debt = _scale_inverse(nd_ebitda, 0.0, 4.0, 5)  # 0-4x ND/EBITDA → 5-0 pts
    s_alt  = _scale(altman, 1.8, 3.5, 4)         # zone grise/sécurité → 0-4 pts
    s_pio  = _scale(piotroski, 4.0, 8.0, 4)      # 4/9 à 8/9 → 0-4 pts

    total = s_roic + s_marg + s_debt + s_alt + s_pio
    return round(total, 1), {
        "roic_pts": s_roic, "roic_value": roic,
        "margin_pts": s_marg, "margin_value": net_m,
        "debt_pts": s_debt, "debt_value": nd_ebitda,
        "altman_pts": s_alt, "altman_value": altman,
        "piotroski_pts": s_pio, "piotroski_value": piotroski,
    }


# ═══ VALORISATION (25 pts) ════════════════════════════════════════════════
def _value_score(ratios: dict, sector_analytics: Optional[dict] = None) -> tuple[float, dict]:
    """P/E + EV/EBITDA + FCF Yield, ajusté secteur si dispo."""
    pe = _safe(ratios.get("pe_ratio") or ratios.get("pe"))
    ev_ebitda = _safe(ratios.get("ev_ebitda"))
    fcf_yield = _safe(ratios.get("fcf_yield"))

    # Bornes adaptées secteur si dispo
    sa = sector_analytics or {}
    pe_med = _safe(sa.get("pe_median_ltm"))
    if pe_med:
        pe_low, pe_high = pe_med * 0.6, pe_med * 1.5
    else:
        pe_low, pe_high = 8, 35

    # Conversion % → décimal pour FCF yield
    if fcf_yield is not None and abs(fcf_yield) > 1.5:
        fcf_yield = fcf_yield / 100.0

    s_pe   = _scale_inverse(pe, pe_low, pe_high, 9)        # 9 pts max P/E
    s_ev   = _scale_inverse(ev_ebitda, 6, 25, 8)           # 6-25x → 8-0 pts
    s_fcf  = _scale(fcf_yield, 0.0, 0.10, 8)               # 0-10% FCF yield → 8 pts

    total = s_pe + s_ev + s_fcf
    return round(total, 1), {
        "pe_pts": s_pe, "pe_value": pe, "pe_sector_med": pe_med,
        "ev_ebitda_pts": s_ev, "ev_ebitda_value": ev_ebitda,
        "fcf_yield_pts": s_fcf, "fcf_yield_value": fcf_yield,
    }


# ═══ MOMENTUM (25 pts) ════════════════════════════════════════════════════
def _momentum_score(ratios: dict, market: Optional[dict] = None) -> tuple[float, dict]:
    """52-week change, croissance revenue, beta."""
    mom52 = _safe(ratios.get("momentum_52w"))
    rev_g = _safe(ratios.get("revenue_growth"))
    beta = _safe((market or {}).get("beta_levered") or ratios.get("beta"))

    # Conversion % → décimal
    if mom52 is not None and abs(mom52) > 2.0:
        mom52 = mom52 / 100.0
    if rev_g is not None and abs(rev_g) > 2.0:
        rev_g = rev_g / 100.0

    s_mom = _scale(mom52, -0.20, 0.50, 12)        # -20% à +50% → 0-12 pts
    s_rev = _scale(rev_g, 0.0, 0.25, 9)           # 0-25% croissance → 0-9 pts
    # Beta : 0.8-1.2 = sweet spot (4 pts), trop bas ou trop haut = pénalité
    if beta is None:
        s_beta = 2.0
    elif 0.8 <= beta <= 1.2:
        s_beta = 4.0
    elif 0.6 <= beta <= 1.4:
        s_beta = 3.0
    elif 0.4 <= beta <= 1.6:
        s_beta = 2.0
    else:
        s_beta = 1.0

    total = s_mom + s_rev + s_beta
    return round(total, 1), {
        "mom52_pts": s_mom, "mom52_value": mom52,
        "rev_growth_pts": s_rev, "rev_growth_value": rev_g,
        "beta_pts": s_beta, "beta_value": beta,
    }


# ═══ GOUVERNANCE (25 pts) ═════════════════════════════════════════════════
def _governance_score(ratios: dict, market: Optional[dict] = None) -> tuple[float, dict]:
    """Payout ratio + Dividend yield + Dilution."""
    payout = _safe(ratios.get("payout_ratio"))
    div_yield = _safe(ratios.get("div_yield") or (market or {}).get("dividend_yield"))
    # Dilution proxy : croissance shares — pas toujours dispo
    shares_change = _safe(ratios.get("shares_change_pct"))

    # Payout sain : 30-70% (sustainable, retourne au shareholder sans s'endetter)
    if payout is None:
        s_payout = 4.0  # neutre si inconnu
    elif 0.30 <= payout <= 0.70:
        s_payout = 10.0
    elif 0.20 <= payout <= 0.80:
        s_payout = 7.0
    elif 0.10 <= payout <= 0.90:
        s_payout = 4.0
    else:
        s_payout = 2.0

    # Dividend yield : 0-6% sweet spot
    if div_yield is not None and abs(div_yield) > 1.5:
        div_yield = div_yield / 100.0
    s_div = _scale(div_yield, 0.0, 0.04, 8)

    # Dilution : pas de dilution = bonus (negative shares_change = buyback)
    if shares_change is None:
        s_dilution = 4.0  # neutre
    elif shares_change <= -0.02:
        s_dilution = 7.0  # rachat actions = top
    elif shares_change <= 0.005:
        s_dilution = 5.0  # stable
    elif shares_change <= 0.02:
        s_dilution = 3.0  # légère dilution
    else:
        s_dilution = 1.0  # dilution massive = mauvais

    total = s_payout + s_div + s_dilution
    return round(total, 1), {
        "payout_pts": s_payout, "payout_value": payout,
        "div_yield_pts": s_div, "div_yield_value": div_yield,
        "dilution_pts": s_dilution, "shares_change_value": shares_change,
    }


# ═══ AGRÉGATION + VERDICT ════════════════════════════════════════════════
def _verdict(score: float) -> str:
    """Verdict textuel court (badge)."""
    if score >= 80:
        return "Excellence (STRONG BUY)"
    if score >= 65:
        return "Bon investissement (BUY)"
    if score >= 50:
        return "Neutre — surveiller (HOLD)"
    if score >= 35:
        return "Précaution (HOLD/SELL)"
    return "À éviter (SELL)"


def _grade(score: float) -> str:
    """Lettre A/B/C/D/E pour affichage compact (badge couleur)."""
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    if score >= 35:
        return "D"
    return "E"


def compute_score(
    ratios: dict,
    market: Optional[dict] = None,
    sector_analytics: Optional[dict] = None,
) -> dict:
    """Calcule le Score FinSight composite à partir des inputs.

    Args:
        ratios: dict avec clés roic, net_margin, pe_ratio, ev_ebitda, fcf_yield,
                momentum_52w, revenue_growth, payout_ratio, div_yield,
                altman_z, piotroski_f, net_debt_ebitda, beta...
        market: dict optionnel avec share_price, beta_levered, dividend_yield
        sector_analytics: dict optionnel pour ajuster les bornes sectorielles
                          (pe_median_ltm, ev_ebitda_median, etc.)

    Returns:
        dict avec global (0-100), 4 sous-scores, verdict, grade A/E, details.
    """
    quality, q_det = _quality_score(ratios or {})
    value, v_det = _value_score(ratios or {}, sector_analytics)
    momentum, m_det = _momentum_score(ratios or {}, market)
    governance, g_det = _governance_score(ratios or {}, market)

    total = round(quality + value + momentum + governance)
    return {
        "global": total,
        "grade": _grade(total),
        "verdict": _verdict(total),
        "quality": round(quality, 1),
        "value": round(value, 1),
        "momentum": round(momentum, 1),
        "governance": round(governance, 1),
        "details": {
            "quality": q_det,
            "value": v_det,
            "momentum": m_det,
            "governance": g_det,
        },
    }
