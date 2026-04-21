# -*- coding: utf-8 -*-
"""
core/finsight_score_v2.py — Score FinSight v2 : 4 scores distincts + reco contextuelle.

Philosophie :
Un score monolithique « BUY/HOLD/SELL » universel est utopique. Morningstar, S&P,
MSCI, AQR — tous utilisent 3-5 scores séparés car un titre peut être BUY pour un
profil Growth et SELL pour un profil Value.

Architecture :
1. **4 scores fondamentaux** (0-100 chacun) :
   - Quality   : ROIC, marges, Piotroski, Altman, solvabilité
   - Value     : P/E, EV/EBITDA, FCF yield vs médianes sectorielles
   - Momentum  : 52w, EPS revisions, croissance revenue
   - Risk      : volatilité, drawdown 52w, beta, dette nette
2. **Profils investisseurs** : 5 templates avec pondérations différentes des 4 scores
3. **Reco contextuelle** : BUY/HOLD/SELL calculé par profil, pas universel.

API :

    from core.finsight_score_v2 import compute_scores_v2, recommend_for_profile

    scores = compute_scores_v2(ratios, market, info, sector="Technology")
    # {'quality': 85, 'value': 30, 'momentum': 75, 'risk': 60}

    reco = recommend_for_profile(scores, profile="growth_aggressive")
    # {'composite': 72, 'recommendation': 'BUY', 'conviction': 0.74,
    #  'reasoning': 'Momentum élevé + Quality solide compensent Value tendue'}

Chaque profil = dict {quality_w, value_w, momentum_w, risk_w} totalisant 1.0.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


# ═══ Helpers ══════════════════════════════════════════════════════════════
def _safe(v) -> Optional[float]:
    try:
        f = float(v)
        if f != f or abs(f) == float("inf"):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _scale(v: Optional[float], low: float, high: float, max_pts: float = 100) -> float:
    if v is None:
        return 0.0
    if v <= low:
        return 0.0
    if v >= high:
        return max_pts
    return round(((v - low) / (high - low)) * max_pts, 1)


def _scale_inverse(v: Optional[float], low: float, high: float, max_pts: float = 100) -> float:
    if v is None:
        return 0.0
    if v <= low:
        return max_pts
    if v >= high:
        return 0.0
    return round(((high - v) / (high - low)) * max_pts, 1)


def _neutral(default: float = 50) -> float:
    """Valeur médiane utilisée quand la donnée manque (évite 0-bias)."""
    return default


# ═══ Sector bounds loading (même fichier que v1) ════════════════════════
_SECTOR_BOUNDS_CACHE: Optional[dict] = None


def _get_sector_bounds() -> dict:
    global _SECTOR_BOUNDS_CACHE
    if _SECTOR_BOUNDS_CACHE is not None:
        return _SECTOR_BOUNDS_CACHE
    try:
        path = Path(__file__).resolve().parent.parent / "outputs" / "backtest" / "sector_bounds.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                _SECTOR_BOUNDS_CACHE = json.load(f)
        else:
            _SECTOR_BOUNDS_CACHE = {}
    except Exception:
        _SECTOR_BOUNDS_CACHE = {}
    return _SECTOR_BOUNDS_CACHE


def _bounds_for(ratio: str, sector: Optional[str],
                 default_low: float, default_high: float) -> tuple[float, float]:
    bounds = _get_sector_bounds()
    if not bounds:
        return default_low, default_high
    for s in ([sector] if sector else []) + ["_default"]:
        if not s:
            continue
        for key in bounds:
            if key == s or (s and key.lower() in s.lower()):
                r = bounds[key].get(ratio)
                if r and r.get("q10") is not None and r.get("q90") is not None:
                    return float(r["q10"]), float(r["q90"])
    return default_low, default_high


# ═══ 4 SCORES ═════════════════════════════════════════════════════════════
def score_quality(ratios: dict, sector: Optional[str] = None) -> tuple[float, dict]:
    """Score Quality 0-100 : ROIC, marges, solvabilité, Altman, Piotroski.

    Mesure la SOLIDITÉ fondamentale. Indicateur long terme type Buffett-Graham.
    Haut = business robuste avec marges et rentabilité.
    """
    roic = _safe(ratios.get("roic"))
    net_m = _safe(ratios.get("net_margin"))
    nd_ebitda = _safe(ratios.get("net_debt_ebitda"))
    altman = _safe(ratios.get("altman_z"))
    piotroski = _safe(ratios.get("piotroski_f"))

    # Normalisation % → décimal
    if roic is not None and abs(roic) > 1.5:
        roic = roic / 100.0
    if net_m is not None and abs(net_m) > 1.5:
        net_m = net_m / 100.0

    # Bornes calibrées par secteur si dispo
    roic_lo, roic_hi = _bounds_for("roic", sector, 0.05, 0.30)
    marg_lo, marg_hi = _bounds_for("net_margin", sector, 0.0, 0.25)
    debt_lo, debt_hi = _bounds_for("net_debt_ebitda", sector, 0.0, 4.0)

    # Pondération interne (total 100)
    s_roic = _scale(roic, roic_lo, roic_hi, 30)              # 30 pts ROIC
    s_marg = _scale(net_m, marg_lo, marg_hi, 20)             # 20 pts marge nette
    s_debt = _scale_inverse(nd_ebitda, debt_lo, debt_hi, 20) # 20 pts solvabilité
    s_alt = _scale(altman, 1.8, 3.5, 15)                     # 15 pts Altman
    s_pio = _scale(piotroski, 4, 8, 15)                      # 15 pts Piotroski

    total = s_roic + s_marg + s_debt + s_alt + s_pio
    return round(total, 1), {
        "roic": {"pts": s_roic, "max": 30, "val": roic},
        "margin": {"pts": s_marg, "max": 20, "val": net_m},
        "solvency": {"pts": s_debt, "max": 20, "val": nd_ebitda},
        "altman": {"pts": s_alt, "max": 15, "val": altman},
        "piotroski": {"pts": s_pio, "max": 15, "val": piotroski},
    }


def score_value(ratios: dict, sector: Optional[str] = None,
                 sector_analytics: Optional[dict] = None) -> tuple[float, dict]:
    """Score Value 0-100 : P/E, EV/EBITDA, FCF yield (vs médiane sectorielle).

    Mesure la DÉCOTE. Haut = pas cher vs pairs sectoriels. Graham style.
    """
    pe = _safe(ratios.get("pe_ratio") or ratios.get("pe"))
    ev_ebitda = _safe(ratios.get("ev_ebitda"))
    fcf_yield = _safe(ratios.get("fcf_yield"))

    if fcf_yield is not None and abs(fcf_yield) > 1.5:
        fcf_yield = fcf_yield / 100.0

    # Bornes secteur
    pe_lo, pe_hi = _bounds_for("pe_ratio", sector, 8, 35)
    ev_lo, ev_hi = _bounds_for("ev_ebitda", sector, 6, 25)
    fcf_lo, fcf_hi = _bounds_for("fcf_yield", sector, 0.0, 0.10)

    # Ajustement sector_analytics médiane dispo (runtime)
    sa = sector_analytics or {}
    pe_med = _safe(sa.get("pe_median_ltm"))
    if pe_med and pe_lo == 8:
        pe_lo, pe_hi = pe_med * 0.6, pe_med * 1.5

    # Scores sur 100
    s_pe = _scale_inverse(pe, pe_lo, pe_hi, 40)          # 40 pts P/E
    s_ev = _scale_inverse(ev_ebitda, ev_lo, ev_hi, 35)   # 35 pts EV/EBITDA
    s_fcf = _scale(fcf_yield, fcf_lo, fcf_hi, 25)        # 25 pts FCF yield

    total = s_pe + s_ev + s_fcf
    return round(total, 1), {
        "pe": {"pts": s_pe, "max": 40, "val": pe, "bounds": [pe_lo, pe_hi]},
        "ev_ebitda": {"pts": s_ev, "max": 35, "val": ev_ebitda},
        "fcf_yield": {"pts": s_fcf, "max": 25, "val": fcf_yield},
    }


def score_momentum(ratios: dict, market: Optional[dict] = None,
                    sector: Optional[str] = None) -> tuple[float, dict]:
    """Score Momentum 0-100 : 52w price change, croissance revenue, EPS momentum.

    Mesure la DYNAMIQUE récente. Haut = tendance haussière solide.
    """
    mom52 = _safe(ratios.get("momentum_52w"))
    rev_g = _safe(ratios.get("revenue_growth"))
    # EPS momentum : growth trimestriel ou earningsGrowth
    eps_g = _safe(ratios.get("earnings_growth")
                   or ratios.get("earningsQuarterlyGrowth"))

    # Normalisation
    if mom52 is not None and abs(mom52) > 2.0:
        mom52 = mom52 / 100.0
    if rev_g is not None and abs(rev_g) > 2.0:
        rev_g = rev_g / 100.0
    if eps_g is not None and abs(eps_g) > 2.0:
        eps_g = eps_g / 100.0

    mom_lo, mom_hi = _bounds_for("momentum_52w", sector, -0.20, 0.50)
    rev_lo, rev_hi = _bounds_for("revenue_growth", sector, 0.0, 0.25)

    s_mom = _scale(mom52, mom_lo, mom_hi, 50)             # 50 pts 52w price
    s_rev = _scale(rev_g, rev_lo, rev_hi, 30)             # 30 pts rev growth
    s_eps = _scale(eps_g, -0.10, 0.30, 20) if eps_g is not None else _neutral(10)

    total = s_mom + s_rev + s_eps
    return round(total, 1), {
        "price_52w": {"pts": s_mom, "max": 50, "val": mom52},
        "revenue_growth": {"pts": s_rev, "max": 30, "val": rev_g},
        "eps_growth": {"pts": s_eps, "max": 20, "val": eps_g},
    }


def score_risk(ratios: dict, market: Optional[dict] = None,
                sector: Optional[str] = None) -> tuple[float, dict]:
    """Score Risk 0-100 : INVERSE (100 = faible risque, 0 = très risqué).

    Mesure la stabilité : volatilité implicite (beta), drawdown max,
    solvabilité (Altman Z), endettement.
    """
    beta = _safe((market or {}).get("beta_levered") or ratios.get("beta"))
    drawdown = _safe(ratios.get("drawdown_52w"))  # négatif
    altman = _safe(ratios.get("altman_z"))
    nd_ebitda = _safe(ratios.get("net_debt_ebitda"))

    if drawdown is not None and abs(drawdown) > 2.0:
        drawdown = drawdown / 100.0

    # Beta : 1.0 = neutre, >1.5 = risqué, <0.8 = défensif (bonus pour défensif)
    if beta is None:
        s_beta = _neutral(15)
    elif beta <= 0.8:
        s_beta = 30
    elif beta <= 1.0:
        s_beta = 25
    elif beta <= 1.2:
        s_beta = 18
    elif beta <= 1.5:
        s_beta = 10
    else:
        s_beta = 3

    # Drawdown 52w : -15% OK, -50% risqué
    if drawdown is None:
        s_dd = _neutral(12)
    else:
        s_dd = _scale_inverse(abs(drawdown), 0.10, 0.50, 25)

    # Altman Z : safe zone > 2.99
    s_altman = _scale(altman, 1.8, 3.5, 25)

    # Net debt / EBITDA : faible = meilleur risque
    s_debt = _scale_inverse(nd_ebitda, 0.0, 4.0, 20)

    total = s_beta + s_dd + s_altman + s_debt
    return round(total, 1), {
        "beta": {"pts": s_beta, "max": 30, "val": beta},
        "drawdown": {"pts": s_dd, "max": 25, "val": drawdown},
        "altman": {"pts": s_altman, "max": 25, "val": altman},
        "debt": {"pts": s_debt, "max": 20, "val": nd_ebitda},
    }


# ═══ API principale ═══════════════════════════════════════════════════════
def compute_scores_v2(
    ratios: dict,
    market: Optional[dict] = None,
    sector_analytics: Optional[dict] = None,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
) -> dict:
    """Calcule les 4 scores FinSight v2 (Quality/Value/Momentum/Risk).

    Retourne : {"quality": {"score": 85, "details": {...}}, "value": ..., ...}
    """
    q, q_det = score_quality(ratios or {}, sector)
    v, v_det = score_value(ratios or {}, sector, sector_analytics)
    m, m_det = score_momentum(ratios or {}, market, sector)
    r, r_det = score_risk(ratios or {}, market, sector)

    return {
        "version": "v2.0",
        "sector": sector,
        "industry": industry,
        "quality": {"score": q, "details": q_det},
        "value": {"score": v, "details": v_det},
        "momentum": {"score": m, "details": m_det},
        "risk": {"score": r, "details": r_det},
    }


# ═══ PROFILS INVESTISSEURS ════════════════════════════════════════════════
PROFILES: dict[str, dict] = {
    "conservative_lt": {
        "label": "Conservateur long terme",
        "description": "Préservation capital, dividendes, horizon 5+ ans. "
                        "Privilégie qualité et stabilité.",
        "weights": {"quality": 0.35, "value": 0.30, "momentum": 0.10, "risk": 0.25},
        "horizon": "long",
    },
    "value_contrarian": {
        "label": "Value contrarian",
        "description": "Style Buffett-Graham. Achète la décote, ignore le momentum.",
        "weights": {"quality": 0.30, "value": 0.40, "momentum": 0.10, "risk": 0.20},
        "horizon": "long",
    },
    "growth_aggressive": {
        "label": "Growth agressif",
        "description": "Croissance avant tout, tolère valorisations élevées et volatilité.",
        "weights": {"quality": 0.20, "value": 0.10, "momentum": 0.50, "risk": 0.20},
        "horizon": "medium",
    },
    "income_dividends": {
        "label": "Rente dividendes",
        "description": "Flux de cash régulier, portefeuille défensif, faible volatilité.",
        "weights": {"quality": 0.40, "value": 0.25, "momentum": 0.05, "risk": 0.30},
        "horizon": "long",
    },
    "balanced": {
        "label": "Équilibré (défaut)",
        "description": "Répartition neutre entre les 4 dimensions.",
        "weights": {"quality": 0.25, "value": 0.25, "momentum": 0.25, "risk": 0.25},
        "horizon": "medium",
    },
}


def recommend_for_profile(scores_v2: dict, profile: str = "balanced") -> dict:
    """Calcule composite + reco BUY/HOLD/SELL POUR UN PROFIL DONNÉ.

    Args:
        scores_v2 : output de compute_scores_v2
        profile : key dans PROFILES (ex: "growth_aggressive")

    Returns:
        {
          "profile_used": "Growth agressif",
          "composite": 72,
          "recommendation": "BUY",   # BUY >= 65, HOLD 40-64, SELL < 40
          "conviction": 0.74,        # float 0-1
          "reasoning": "Momentum élevé + Quality solide compensent Value tendue.",
          "weights": {...}
        }
    """
    prof = PROFILES.get(profile, PROFILES["balanced"])
    w = prof["weights"]

    q = scores_v2.get("quality", {}).get("score", 0) or 0
    v = scores_v2.get("value", {}).get("score", 0) or 0
    m = scores_v2.get("momentum", {}).get("score", 0) or 0
    r = scores_v2.get("risk", {}).get("score", 0) or 0

    composite = (
        q * w["quality"] + v * w["value"]
        + m * w["momentum"] + r * w["risk"]
    )
    composite = round(composite, 1)

    # Seuils BUY/HOLD/SELL
    if composite >= 65:
        reco = "BUY"
    elif composite >= 40:
        reco = "HOLD"
    else:
        reco = "SELL"

    # Conviction : proportionnelle à la distance du seuil
    if reco == "BUY":
        conv = 0.55 + min(0.40, (composite - 65) / 100)
    elif reco == "SELL":
        conv = 0.55 + min(0.40, (40 - composite) / 100)
    else:   # HOLD
        # HOLD = conviction modérée 0.40-0.55 selon proximité des bornes
        if composite >= 55:
            conv = 0.45 + (composite - 55) / 100
        else:
            conv = 0.45 + (composite - 45) / 100
    conv = round(max(0.30, min(0.90, conv)), 2)

    # Reasoning basique (le LLM pourra enrichir)
    drivers = []
    if q >= 70:
        drivers.append(f"Quality forte ({q}/100)")
    elif q < 40:
        drivers.append(f"Quality faible ({q}/100)")
    if v >= 70:
        drivers.append(f"Value attractive ({v}/100)")
    elif v < 40:
        drivers.append(f"Valorisation tendue ({v}/100)")
    if m >= 70:
        drivers.append(f"Momentum positif ({m}/100)")
    elif m < 40:
        drivers.append(f"Momentum faible ({m}/100)")
    if r >= 70:
        drivers.append(f"Risque maîtrisé ({r}/100)")
    elif r < 40:
        drivers.append(f"Risque élevé ({r}/100)")
    reasoning = (
        f"Pour profil {prof['label']} : "
        + ("; ".join(drivers) if drivers else "Profil mixte, signaux contrastés")
        + "."
    )

    return {
        "profile_key": profile,
        "profile_label": prof["label"],
        "composite": composite,
        "recommendation": reco,
        "conviction": conv,
        "reasoning": reasoning,
        "weights": w,
    }


def recommend_all_profiles(scores_v2: dict) -> dict[str, dict]:
    """Calcule la reco POUR CHAQUE profil → pour afficher « BUY pour Growth,
    HOLD pour Conservateur » dans l'UI."""
    return {
        key: recommend_for_profile(scores_v2, profile=key)
        for key in PROFILES.keys()
    }
