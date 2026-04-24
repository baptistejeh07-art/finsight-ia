# -*- coding: utf-8 -*-
"""
core/finsight_score.py — Score FinSight propriétaire (note 0-100 composite).

v1.1 — Ajout de 6 facteurs (révisions EPS, Beneish M-Score, short interest,
insider holdings, dilution shares, ETF flows si dispo) répartis dans les 4
dimensions existantes pour garder l'équilibre 25/25/25/25.

Quatre dimensions (25 pts max chacune, total 100) :
  - **Qualité** : ROIC + Marge + ND/EBITDA + Altman Z + Piotroski + Beneish M
  - **Valorisation** : P/E + EV/EBITDA + FCF Yield (vs médiane sectorielle)
  - **Momentum** : 52w + Rev Growth + Beta + Révisions EPS + Short interest
  - **Gouvernance** : Payout + Div Yield + Dilution + Insider + ETF flows

API simple :

    from core.finsight_score import compute_score

    score = compute_score(
        ratios={"pe_ratio": 18.5, "roe": 0.32, ...},
        market={"share_price": 150, "beta_levered": 1.1, ...},
        info={...},                          # yfinance info brut (optionnel)
        sector_analytics={"pe_median_ltm": 25, ...},   # optionnel
    )
    # → {"global": 72, "grade": "B", "verdict": "...", "quality": 21, ...}

Déterministe — pas de LLM. Documenté dans /methodologie pour transparence.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# Charge les quartiles calibrés par secteur (outputs/backtest/sector_bounds.json)
# Si fichier absent, _scale() utilise ses bornes hardcodées par défaut.
_SECTOR_BOUNDS_CACHE: Optional[dict] = None


def _get_sector_bounds() -> dict:
    """Lazy-load sector_bounds.json avec quartiles Q10/Q25/Q50/Q75/Q90 par ratio."""
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


def set_sector_bounds_override(bounds: Optional[dict]) -> None:
    """Remplace temporairement le cache des bornes sectorielles.

    Usage walk-forward backtest : a chaque date T, calculer les quartiles
    de la cross-section disponible a T, puis appeler cette fonction avant
    de scorer les tickers a T. Permet d'eliminer le data leakage du
    calibrage sur snapshots 2025 applique retroactivement.

    bounds=None restaure le chargement depuis sector_bounds.json.
    """
    global _SECTOR_BOUNDS_CACHE
    _SECTOR_BOUNDS_CACHE = bounds


def _resolve_bounds(ratio: str, sector: Optional[str],
                     default_low: float, default_high: float) -> tuple[float, float]:
    """Retourne (low, high) calibrés pour ce ratio dans ce secteur.
    Fallback : _default secteur, puis defaults hardcodés.
    """
    bounds = _get_sector_bounds()
    if not bounds:
        return default_low, default_high
    # Match secteur (fuzzy : "Technology" match "Information Technology")
    candidates = [sector] if sector else []
    candidates.append("_default")
    for s in candidates:
        if not s:
            continue
        # Match direct ou partial
        for key in bounds:
            if key == s or (s and key.lower() in s.lower()):
                r = bounds[key].get(ratio)
                if r and r.get("q10") is not None and r.get("q90") is not None:
                    return float(r["q10"]), float(r["q90"])
    return default_low, default_high


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


def _neutral(max_pts: float) -> float:
    """Score neutre (mid-point) quand donnée indisponible — évite de pénaliser
    artificiellement une société dont yfinance n'expose pas le champ."""
    return round(max_pts * 0.5, 2)


# ═══ QUALITÉ (25 pts) ═════════════════════════════════════════════════════
# v1.1 : ajout Beneish M-Score (qualité des earnings, détection manipulation).
# v1.3 backtest_mode=True : skip Beneish (redistribue points sur les autres)
def _quality_score(ratios: dict, info: Optional[dict] = None,
                    backtest_mode: bool = False,
                    sector: Optional[str] = None) -> tuple[float, dict]:
    """ROIC + Marge + Solvabilité + Altman + Piotroski [+ Beneish si !backtest].

    Pondération v1.2 (full live) : ROIC 6 + Marg 4 + Debt 4 + Alt 3 + Pio 3 + Beneish 5 = 25
    Pondération v1.3 (backtest)  : ROIC 8 + Marg 5 + Debt 5 + Alt 4 + Pio 3            = 25
    (le Beneish n'a pas de data historique fiable yfinance, ses 5 pts neutre
    polluent le signal → on redistribue proportionnellement.)
    """
    info = info or {}
    roic = _safe(ratios.get("roic"))
    net_m = _safe(ratios.get("net_margin"))
    nd_ebitda = _safe(ratios.get("net_debt_ebitda"))
    altman = _safe(ratios.get("altman_z"))
    piotroski = _safe(ratios.get("piotroski_f"))
    beneish_m = _safe(ratios.get("beneish_m"))

    # Conversion % → décimal si nécessaire
    if roic is not None and abs(roic) > 1.5:
        roic = roic / 100.0
    if net_m is not None and abs(net_m) > 1.5:
        net_m = net_m / 100.0

    if backtest_mode:
        # v2 : bornes calibrées par secteur (quartiles Q10/Q90 réels) si dispo.
        roic_low, roic_high = _resolve_bounds("roic", sector, 0.05, 0.30)
        marg_low, marg_high = _resolve_bounds("net_margin", sector, 0.0, 0.25)
        debt_low, debt_high = _resolve_bounds("net_debt_ebitda", sector, 0.0, 4.0)
        s_roic = _scale(roic, roic_low, roic_high, 8)
        s_marg = _scale(net_m, marg_low, marg_high, 5)
        s_debt = _scale_inverse(nd_ebitda, debt_low, debt_high, 5)
        s_alt  = _scale(altman, 1.8, 3.5, 4)
        s_pio  = _scale(piotroski, 4.0, 8.0, 3)
        s_beneish = 0.0
    else:
        s_roic = _scale(roic, 0.05, 0.30, 6)         # 5%-30% → 0-6 pts
        s_marg = _scale(net_m, 0.0, 0.25, 4)         # 0-25% net margin → 0-4 pts
        s_debt = _scale_inverse(nd_ebitda, 0.0, 4.0, 4)   # 0-4x ND/EBITDA → 4-0 pts
        s_alt  = _scale(altman, 1.8, 3.5, 3)         # zone grise/sécurité → 0-3 pts
        s_pio  = _scale(piotroski, 4.0, 8.0, 3)      # 4/9 à 8/9 → 0-3 pts

        # Beneish M-Score : <-2.22 = sain
        if beneish_m is None:
            s_beneish = _neutral(5)
        elif beneish_m <= -2.5:
            s_beneish = 5.0
        elif beneish_m <= -2.22:
            s_beneish = 4.5
        elif beneish_m <= -1.78:
            s_beneish = 3.0
        elif beneish_m <= -1.0:
            s_beneish = 1.5
        else:
            s_beneish = 0.0

    total = s_roic + s_marg + s_debt + s_alt + s_pio + s_beneish
    return round(total, 1), {
        "roic_pts": s_roic, "roic_value": roic,
        "margin_pts": s_marg, "margin_value": net_m,
        "debt_pts": s_debt, "debt_value": nd_ebitda,
        "altman_pts": s_alt, "altman_value": altman,
        "piotroski_pts": s_pio, "piotroski_value": piotroski,
        "beneish_pts": s_beneish, "beneish_value": beneish_m,
    }


# ═══ VALORISATION (25 pts) ════════════════════════════════════════════════
def _value_score(ratios: dict, sector_analytics: Optional[dict] = None,
                  sector: Optional[str] = None) -> tuple[float, dict]:
    """P/E 9 + EV/EBITDA 8 + FCF Yield 8 — bornes adaptables secteur."""
    pe = _safe(ratios.get("pe_ratio") or ratios.get("pe"))
    ev_ebitda = _safe(ratios.get("ev_ebitda"))
    fcf_yield = _safe(ratios.get("fcf_yield"))

    sa = sector_analytics or {}
    # Priorité 1 : bornes calibrées par secteur (si sector_bounds.json chargé)
    pe_low, pe_high = _resolve_bounds("pe_ratio", sector, 8, 35)
    ev_low, ev_high = _resolve_bounds("ev_ebitda", sector, 6, 25)
    fcf_low, fcf_high = _resolve_bounds("fcf_yield", sector, 0.0, 0.10)
    # Priorité 2 : median sector_analytics si fournie (runtime)
    pe_med = _safe(sa.get("pe_median_ltm"))
    if pe_med and pe_low == 8:  # overwrite uniquement si pas calibré
        pe_low, pe_high = pe_med * 0.6, pe_med * 1.5

    if fcf_yield is not None and abs(fcf_yield) > 1.5:
        fcf_yield = fcf_yield / 100.0

    s_pe   = _scale_inverse(pe, pe_low, pe_high, 9)
    s_ev   = _scale_inverse(ev_ebitda, ev_low, ev_high, 8)
    s_fcf  = _scale(fcf_yield, fcf_low, fcf_high, 8)

    total = s_pe + s_ev + s_fcf
    return round(total, 1), {
        "pe_pts": s_pe, "pe_value": pe, "pe_sector_med": pe_med,
        "ev_ebitda_pts": s_ev, "ev_ebitda_value": ev_ebitda,
        "fcf_yield_pts": s_fcf, "fcf_yield_value": fcf_yield,
    }


# ═══ MOMENTUM (25 pts) ════════════════════════════════════════════════════
# v1.1 : 52w 8 + Rev 7 + Beta 3 + Révisions EPS 4 + Short interest 3.
# v1.3 backtest : 52w 12 + Rev 9 + Beta 4 (retour v1.0, EPS/short pas historiques)
def _momentum_score(ratios: dict, market: Optional[dict] = None,
                    info: Optional[dict] = None,
                    backtest_mode: bool = False,
                    sector: Optional[str] = None) -> tuple[float, dict]:
    """Momentum élargi avec révisions analystes + short squeeze potential."""
    info = info or {}
    mom52 = _safe(ratios.get("momentum_52w"))
    rev_g = _safe(ratios.get("revenue_growth"))
    beta = _safe((market or {}).get("beta_levered") or ratios.get("beta"))

    if mom52 is not None and abs(mom52) > 2.0:
        mom52 = mom52 / 100.0
    if rev_g is not None and abs(rev_g) > 2.0:
        rev_g = rev_g / 100.0

    if backtest_mode:
        # v2 : bornes calibrées si dispo
        mom_low, mom_high = _resolve_bounds("momentum_52w", sector, -0.20, 0.50)
        rev_low, rev_high = _resolve_bounds("revenue_growth", sector, 0.0, 0.25)
        s_mom = _scale(mom52, mom_low, mom_high, 12)
        s_rev = _scale(rev_g, rev_low, rev_high, 9)
        if beta is None:
            s_beta = _neutral(4)
        elif 0.8 <= beta <= 1.2:
            s_beta = 4.0
        elif 0.6 <= beta <= 1.4:
            s_beta = 3.0
        elif 0.4 <= beta <= 1.6:
            s_beta = 2.0
        else:
            s_beta = 1.0
        return round(s_mom + s_rev + s_beta, 1), {
            "mom52_pts": s_mom, "mom52_value": mom52,
            "rev_growth_pts": s_rev, "rev_growth_value": rev_g,
            "beta_pts": s_beta, "beta_value": beta,
        }

    s_mom = _scale(mom52, -0.20, 0.50, 8)         # -20% à +50% → 0-8 pts
    s_rev = _scale(rev_g, 0.0, 0.25, 7)           # 0-25% croissance → 0-7 pts

    # Beta : 0.8-1.2 = sweet spot (3 pts)
    if beta is None:
        s_beta = _neutral(3)
    elif 0.8 <= beta <= 1.2:
        s_beta = 3.0
    elif 0.6 <= beta <= 1.4:
        s_beta = 2.25
    elif 0.4 <= beta <= 1.6:
        s_beta = 1.5
    else:
        s_beta = 0.75

    # Révisions EPS analystes : signal alpha le plus puissant connu (Womack 1996,
    # Stickel 1992). Proxy via earningsQuarterlyGrowth ou earningsGrowth yfinance.
    eps_growth = _safe(info.get("earningsQuarterlyGrowth")
                        or info.get("earningsGrowth")
                        or ratios.get("earnings_growth"))
    if eps_growth is None:
        s_eps_rev = _neutral(4)
    else:
        # Convertir en décimal si en % brut
        if abs(eps_growth) > 2.0:
            eps_growth = eps_growth / 100.0
        # -10% à +30% → 0-4 pts
        s_eps_rev = _scale(eps_growth, -0.10, 0.30, 4)

    # Short interest : un short interest faible (<5% float) = 3 pts (pas de squeeze
    # imminent ni de smart-money short). 5-15% = neutre. >20% = pénalité (smart
    # money pari contre l'entreprise).
    short_pct = _safe(info.get("shortPercentOfFloat"))
    if short_pct is not None and short_pct > 1.5:
        short_pct = short_pct / 100.0
    if short_pct is None:
        s_short = _neutral(3)
    elif short_pct <= 0.03:
        s_short = 3.0
    elif short_pct <= 0.10:
        s_short = 2.25
    elif short_pct <= 0.20:
        s_short = 1.0
    else:
        s_short = 0.0  # >20% short = bear thesis institutionnelle

    total = s_mom + s_rev + s_beta + s_eps_rev + s_short
    return round(total, 1), {
        "mom52_pts": s_mom, "mom52_value": mom52,
        "rev_growth_pts": s_rev, "rev_growth_value": rev_g,
        "beta_pts": s_beta, "beta_value": beta,
        "eps_rev_pts": s_eps_rev, "eps_growth_value": eps_growth,
        "short_pts": s_short, "short_pct_value": short_pct,
    }


# ═══ GOUVERNANCE (25 pts) ═════════════════════════════════════════════════
# v1.1 : Payout 7 + Div Yield 5 + Dilution 5 + Insider 4 + ETF flows 4.
# v1.3 backtest : Payout 10 + Div 8 + Dilution 7 (retour v1.0, insider/inst non histo)
def _governance_score(ratios: dict, market: Optional[dict] = None,
                       info: Optional[dict] = None,
                       backtest_mode: bool = False) -> tuple[float, dict]:
    """Gouvernance enrichie avec insider holdings + signal flux passifs."""
    info = info or {}
    payout = _safe(ratios.get("payout_ratio"))
    div_yield = _safe(ratios.get("div_yield") or (market or {}).get("dividend_yield"))
    shares_change = _safe(ratios.get("shares_change_pct"))

    if backtest_mode:
        # v1.3 : payout 10 + div 8 + dilution 7 (retour v1.0)
        if payout is None:
            s_payout = _neutral(10)
        elif 0.30 <= payout <= 0.70:
            s_payout = 10.0
        elif 0.20 <= payout <= 0.80:
            s_payout = 7.0
        elif 0.10 <= payout <= 0.90:
            s_payout = 4.0
        else:
            s_payout = 2.0
        if div_yield is not None and abs(div_yield) > 1.5:
            div_yield = div_yield / 100.0
        s_div = _scale(div_yield, 0.0, 0.04, 8)
        if shares_change is None:
            s_dilution = _neutral(7)
        elif shares_change <= -0.02:
            s_dilution = 7.0
        elif shares_change <= 0.005:
            s_dilution = 5.0
        elif shares_change <= 0.02:
            s_dilution = 3.0
        else:
            s_dilution = 1.0
        return round(s_payout + s_div + s_dilution, 1), {
            "payout_pts": s_payout, "payout_value": payout,
            "div_yield_pts": s_div, "div_yield_value": div_yield,
            "dilution_pts": s_dilution, "shares_change_value": shares_change,
        }

    # Payout sain : 30-70%
    if payout is None:
        s_payout = _neutral(7)
    elif 0.30 <= payout <= 0.70:
        s_payout = 7.0
    elif 0.20 <= payout <= 0.80:
        s_payout = 5.0
    elif 0.10 <= payout <= 0.90:
        s_payout = 3.0
    else:
        s_payout = 1.0

    # Div yield 0-4% sweet spot
    if div_yield is not None and abs(div_yield) > 1.5:
        div_yield = div_yield / 100.0
    s_div = _scale(div_yield, 0.0, 0.04, 5)

    # Dilution
    if shares_change is None:
        s_dilution = _neutral(5)
    elif shares_change <= -0.02:
        s_dilution = 5.0    # rachat actions = top
    elif shares_change <= 0.005:
        s_dilution = 3.5    # stable
    elif shares_change <= 0.02:
        s_dilution = 2.0    # légère dilution
    else:
        s_dilution = 0.5    # dilution massive

    # Insider holdings : >5% détenu par dirigeants = skin in the game (4 pts)
    insider_pct = _safe(info.get("heldPercentInsiders"))
    if insider_pct is not None and insider_pct > 1.5:
        insider_pct = insider_pct / 100.0
    if insider_pct is None:
        s_insider = _neutral(4)
    elif insider_pct >= 0.10:
        s_insider = 4.0   # >10% détenu = très fort alignement
    elif insider_pct >= 0.05:
        s_insider = 3.0
    elif insider_pct >= 0.01:
        s_insider = 2.0
    else:
        s_insider = 1.0

    # Flux ETF passive : proxy via heldPercentInstitutions (% détenu par
    # institutions = signal qualité d'allocation pro). >70% = top.
    inst_pct = _safe(info.get("heldPercentInstitutions"))
    if inst_pct is not None and inst_pct > 1.5:
        inst_pct = inst_pct / 100.0
    if inst_pct is None:
        s_etf = _neutral(4)
    elif inst_pct >= 0.70:
        s_etf = 4.0
    elif inst_pct >= 0.50:
        s_etf = 3.0
    elif inst_pct >= 0.30:
        s_etf = 2.0
    else:
        s_etf = 1.0

    total = s_payout + s_div + s_dilution + s_insider + s_etf
    return round(total, 1), {
        "payout_pts": s_payout, "payout_value": payout,
        "div_yield_pts": s_div, "div_yield_value": div_yield,
        "dilution_pts": s_dilution, "shares_change_value": shares_change,
        "insider_pts": s_insider, "insider_pct_value": insider_pct,
        "etf_inst_pts": s_etf, "institutional_pct_value": inst_pct,
    }


# ═══ RECALIBRATION — SPREAD + SECTOR PERCENTILE ═══════════════════════════
# Diagnostic 2026-04-24 : sur un snapshot SP100 (n=50) le score v1.2 clusterise
# à mean=47.6 std=10.9 — trois sociétés type MC.PA/OR.PA/SU.PA ressortent toutes
# à 48-50 alors qu'elles ont des profils de qualité très différents. Deux
# corrections sont appliquées en post-processing (sans toucher aux sous-scores
# pour ne pas invalider le backtest `backtest_mode=True`) :
#   1. `displayed` : recalibration linéaire qui étire la distribution (on passe
#      de std≈11 à std≈20) tout en préservant l'ordre des sociétés.
#   2. `sector_percentile` : rang percentile de chaque ratio vs les quartiles
#      Q10/Q25/Q50/Q75/Q90 du secteur (sector_bounds.json), moyenné sur 5-6
#      ratios. Donne un "rang sectoriel" complémentaire au score absolu.
_SPREAD_CENTER = 48.0   # mean observé sur snapshot backtest 2026-03-01
_SPREAD_FACTOR = 1.4    # étirement modéré (std 11 -> ~15). On laisse le
                         # sector_percentile porter le différentiel fin entre
                         # pairs qui ont un raw score voisin (MC.PA vs OR.PA).


def _spread_calibration(raw: float) -> int:
    """Elargit l'échelle autour du centre observé. Préserve l'ordre."""
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return int(round(raw)) if raw is not None else 0
    widened = _SPREAD_CENTER + (v - _SPREAD_CENTER) * _SPREAD_FACTOR
    return int(round(max(0.0, min(100.0, widened))))


def _ratio_percentile(value: Optional[float], quartiles: dict,
                       inverse: bool = False) -> Optional[float]:
    """Retourne un rang 0-100 dans la distribution sectorielle.

    quartiles : dict avec clés q10, q25, q50, q75, q90 (doivent être remplies).
    inverse=True pour les ratios où "plus bas = mieux" (PE, EV/EBITDA, ND/EBITDA).
    Interpole linéairement entre les quartiles pour une échelle continue.
    """
    if value is None:
        return None
    q10 = quartiles.get("q10"); q25 = quartiles.get("q25")
    q50 = quartiles.get("q50"); q75 = quartiles.get("q75")
    q90 = quartiles.get("q90")
    if any(x is None for x in (q10, q25, q50, q75, q90)):
        return None
    # Anchors (pos, rank) en mode "plus haut = mieux"
    if value <= q10:
        p = 5.0
    elif value <= q25:
        p = 5.0 + (value - q10) / max(q25 - q10, 1e-9) * (25 - 5)
    elif value <= q50:
        p = 25.0 + (value - q25) / max(q50 - q25, 1e-9) * (50 - 25)
    elif value <= q75:
        p = 50.0 + (value - q50) / max(q75 - q50, 1e-9) * (75 - 50)
    elif value <= q90:
        p = 75.0 + (value - q75) / max(q90 - q75, 1e-9) * (95 - 75)
    else:
        p = 95.0
    if inverse:
        p = 100.0 - p
    return max(0.0, min(100.0, p))


# Ratios utilisés pour le percentile sectoriel : mix qualité + valo + momentum.
# Dans chaque tuple : (clé ratios, inverse=True si plus bas = mieux).
_PERCENTILE_RATIOS = [
    ("roic",            False),
    ("net_margin",      False),
    ("ebitda_margin",   False),
    ("revenue_growth",  False),
    ("fcf_yield",       False),
    ("pe_ratio",        True),
    ("ev_ebitda",       True),
    ("net_debt_ebitda", True),
    ("momentum_52w",    False),
]


def compute_sector_percentile(ratios: dict, sector: Optional[str]) -> Optional[dict]:
    """Calcule un rang percentile 0-100 de la société dans son secteur.

    Agrège les percentiles ratio-par-ratio (moyenne simple sur les ratios
    disponibles). Retourne None si secteur absent ou aucun quartile trouvé.
    """
    if not ratios or not sector:
        return None
    bounds = _get_sector_bounds()
    if not bounds:
        return None
    # Match secteur fuzzy
    sec_block = None
    for key in bounds:
        if key == "_default":
            continue
        if key == sector or (sector and key.lower() in sector.lower()) or (sector and sector.lower() in key.lower()):
            sec_block = bounds[key]
            break
    if sec_block is None:
        sec_block = bounds.get("_default")
    if not sec_block:
        return None

    per_ratio: dict[str, float] = {}
    for key, inv in _PERCENTILE_RATIOS:
        v = _safe(ratios.get(key))
        if v is None:
            continue
        # Conversion % → décimal si on détecte un % brut
        if key in ("roic", "net_margin", "ebitda_margin", "revenue_growth",
                   "fcf_yield", "momentum_52w") and v is not None and abs(v) > 1.5:
            v = v / 100.0
        q = sec_block.get(key)
        if not q:
            continue
        p = _ratio_percentile(v, q, inverse=inv)
        if p is not None:
            per_ratio[key] = round(p, 1)
    if not per_ratio:
        return None
    avg = sum(per_ratio.values()) / len(per_ratio)
    return {
        "percentile": int(round(avg)),
        "n_ratios": len(per_ratio),
        "per_ratio": per_ratio,
    }


# ═══ AGRÉGATION + VERDICT ════════════════════════════════════════════════
def _verdict(score: float) -> str:
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
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    if score >= 35:
        return "D"
    return "E"


# ═══ PONDÉRATIONS PAR PROFIL SECTORIEL (v1.2) ═════════════════════════════
# Normalize sum to 1.0 — chaque facteur d'origine 25 pts est multiplié par
# 4 × poids ; le total reste 100.
#
# Sources : académique (Mauboussin "Untangling Skill and Luck" 2013,
# Damodaran "Country and Industry Risk" 2024) + intuition métier.
_SECTOR_WEIGHTS: dict[str, dict[str, float]] = {
    # STANDARD : équilibre par défaut
    "STANDARD":  {"quality": 0.25, "value": 0.25, "momentum": 0.25, "governance": 0.25},
    # TECH : momentum + qualité (croissance + ROIC drive returns), valo souvent
    # déconnectée court terme. Gouvernance OK mais moins critique.
    "TECH":      {"quality": 0.30, "value": 0.20, "momentum": 0.35, "governance": 0.15},
    # BANK : qualité + gouvernance dominent (NPL, CET1, capital allocation),
    # momentum peu pertinent (cycle long), valo via P/B et ROE.
    "BANK":      {"quality": 0.35, "value": 0.20, "momentum": 0.10, "governance": 0.35},
    # INSURANCE : similaire banque mais moins de momentum stochastique,
    # gouvernance encore plus importante (combined ratio discipline).
    "INSURANCE": {"quality": 0.30, "value": 0.20, "momentum": 0.10, "governance": 0.40},
    # UTILITY : ultra-stable, cash-cow → gouvernance et qualité dominent,
    # momentum quasi-zero (regulated returns), valo via P/E et div yield.
    "UTILITY":   {"quality": 0.30, "value": 0.25, "momentum": 0.10, "governance": 0.35},
    # REIT : valo (cap rate vs treasury) + gouvernance (FFO discipline) clés.
    "REIT":      {"quality": 0.25, "value": 0.30, "momentum": 0.15, "governance": 0.30},
    # ENERGY / OIL_GAS : momentum (cycle commodities) + gouvernance (capex
    # discipline), qualité pénalisée par volatilité naturelle.
    "OIL_GAS":   {"quality": 0.20, "value": 0.30, "momentum": 0.30, "governance": 0.20},
    "ENERGY":    {"quality": 0.20, "value": 0.30, "momentum": 0.30, "governance": 0.20},
    # CONSUMER : quality (brand moat) + valo, momentum modéré.
    "CONSUMER":  {"quality": 0.30, "value": 0.30, "momentum": 0.20, "governance": 0.20},
    # HEALTHCARE : qualité (R&D pipeline, marges) + momentum (catalyseurs
    # cliniques) + gouvernance (compliance FDA).
    "HEALTHCARE": {"quality": 0.30, "value": 0.20, "momentum": 0.25, "governance": 0.25},
    # INDUSTRIALS : équilibre, légèrement plus value (cycle).
    "INDUSTRIALS": {"quality": 0.25, "value": 0.30, "momentum": 0.25, "governance": 0.20},
    # MATERIALS : commodities → momentum + valo dominent.
    "MATERIALS": {"quality": 0.20, "value": 0.30, "momentum": 0.30, "governance": 0.20},
}


def _resolve_weights(sector: Optional[str], industry: Optional[str]) -> dict:
    """Map (sector, industry) → profil → pondérations."""
    if not sector and not industry:
        return _SECTOR_WEIGHTS["STANDARD"]

    s = (sector or "").lower().strip()
    # Mapping rapide secteur GICS yfinance → profil
    if any(k in s for k in ("technology", "tech", "software", "communication", "informat")):
        prof = "TECH"
    elif any(k in s for k in ("bank", "banque")):
        prof = "BANK"
    elif "insur" in s or "assur" in s:
        prof = "INSURANCE"
    elif any(k in s for k in ("real estate", "immob", "reit")):
        prof = "REIT"
    elif any(k in s for k in ("utilit", "util")):
        prof = "UTILITY"
    elif any(k in s for k in ("energy", "energi", "oil", "gas")):
        prof = "ENERGY"
    elif any(k in s for k in ("consumer", "conso", "retail", "luxury")):
        prof = "CONSUMER"
    elif any(k in s for k in ("health", "santé", "sante", "pharma", "biotech")):
        prof = "HEALTHCARE"
    elif any(k in s for k in ("industri", "manufactur", "aerospace", "defense")):
        prof = "INDUSTRIALS"
    elif any(k in s for k in ("material", "metal", "mining", "chimi")):
        prof = "MATERIALS"
    elif any(k in s for k in ("financ", "finan")):
        prof = "BANK"   # fallback générique financials
    else:
        prof = "STANDARD"

    return _SECTOR_WEIGHTS.get(prof, _SECTOR_WEIGHTS["STANDARD"])


def compute_score(
    ratios: dict,
    market: Optional[dict] = None,
    sector_analytics: Optional[dict] = None,
    info: Optional[dict] = None,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    backtest_mode: bool = False,
) -> dict:
    """Calcule le Score FinSight composite (v1.1).

    Args:
        ratios: dict avec ratios calculés (pe_ratio, roe, roic, net_margin,
                ev_ebitda, fcf_yield, momentum_52w, revenue_growth, payout_ratio,
                div_yield, altman_z, piotroski_f, beneish_m, net_debt_ebitda,
                shares_change_pct, beta, earnings_growth)
        market: dict optionnel (share_price, beta_levered, dividend_yield)
        sector_analytics: dict optionnel pour bornes sectorielles
                          (pe_median_ltm, ev_ebitda_median, etc.)
        info: dict optionnel (yfinance .info brut) — utilisé pour
              shortPercentOfFloat, heldPercentInsiders, heldPercentInstitutions,
              earningsQuarterlyGrowth, etc.

    Returns:
        dict {global 0-100, grade A/B/C/D/E, verdict, quality, value,
              momentum, governance, details}
    """
    quality, q_det = _quality_score(ratios or {}, info,
                                      backtest_mode=backtest_mode, sector=sector)
    value, v_det = _value_score(ratios or {}, sector_analytics, sector=sector)
    momentum, m_det = _momentum_score(ratios or {}, market, info,
                                        backtest_mode=backtest_mode, sector=sector)
    governance, g_det = _governance_score(ratios or {}, market, info,
                                            backtest_mode=backtest_mode)

    # v1.2 : pondération sectorielle. Chaque sous-score sur 25 → multiplié
    # par 4 × poids sectoriel (qui somme à 1). Garde l'échelle 0-100.
    weights = _resolve_weights(sector, industry)
    weighted = (
        quality * 4 * weights["quality"]
        + value * 4 * weights["value"]
        + momentum * 4 * weights["momentum"]
        + governance * 4 * weights["governance"]
    )
    total = round(weighted)
    # v1.3 : post-calibration — `global` reste le score brut (backtest), mais
    # on expose `displayed` (étiré, mean=50/std≈20) et `sector_percentile`
    # (rang intra-sectoriel) pour rendre le signal discriminant côté UI.
    displayed = _spread_calibration(total)
    sec_pct = compute_sector_percentile(ratios or {}, sector)

    return {
        "global": total,            # compat backtest (non recalibré)
        "displayed": displayed,      # score recalibré affiché côté produit
        "grade": _grade(displayed),
        "verdict": _verdict(displayed),
        # Sous-scores affichés sur leur échelle native /25 pour lisibilité
        "quality": round(quality, 1),
        "value": round(value, 1),
        "momentum": round(momentum, 1),
        "governance": round(governance, 1),
        # Rang sectoriel 0-100 (0=fond du secteur, 100=top du secteur)
        "sector_percentile": sec_pct,
        # Pondérations appliquées (transparence pour l'utilisateur)
        "weights": weights,
        "sector_profile_used": _profile_label_for(sector),
        "details": {
            "quality": q_det,
            "value": v_det,
            "momentum": m_det,
            "governance": g_det,
        },
        "version": "v1.3",  # bump version (spread + sector_percentile)
    }


def _profile_label_for(sector: Optional[str]) -> str:
    """Label lisible du profil utilisé."""
    if not sector:
        return "STANDARD"
    s = sector.lower()
    for prof in ("TECH", "BANK", "INSURANCE", "REIT", "UTILITY", "ENERGY",
                 "CONSUMER", "HEALTHCARE", "INDUSTRIALS", "MATERIALS"):
        # Heuristique simple basée sur _resolve_weights
        if prof.lower() in s.replace("technology", "tech"):
            return prof
    # Reuse the same logic
    if any(k in s for k in ("technology", "software")):
        return "TECH"
    if any(k in s for k in ("bank", "financ")):
        return "BANK"
    if "real estate" in s or "reit" in s:
        return "REIT"
    if "utilit" in s:
        return "UTILITY"
    if "energ" in s or "oil" in s:
        return "ENERGY"
    if any(k in s for k in ("consumer", "retail")):
        return "CONSUMER"
    if any(k in s for k in ("health", "pharma")):
        return "HEALTHCARE"
    if "industri" in s:
        return "INDUSTRIALS"
    if "material" in s:
        return "MATERIALS"
    return "STANDARD"
