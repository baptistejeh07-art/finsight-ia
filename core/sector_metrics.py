# -*- coding: utf-8 -*-
"""
core/sector_metrics.py — Métriques financières spécifiques par profil sectoriel.

Chantier #204 Baptiste (2026-04-15) : les PDF/PPTX société actuels affichent
les mêmes ratios génériques quel que soit le secteur (P/E, EV/EBITDA, ND/EBITDA,
Current Ratio, etc.). Ces métriques sont pertinentes pour les corporates mais
INADAPTÉES pour les profils spécifiques :

- **OIL_GAS** : EV/EBITDAX, EV/DACF, break-even Brent, reserves life
- **BANK**    : NIM, Cost/Income, ROTE, CET1 (si dispo), NPL, P/TBV
- **INSURANCE** : Combined Ratio, Loss Ratio, Solvency II, Embedded Value
- **REIT**    : FFO, AFFO, NAV, Cap Rate, LTV, Occupancy
- **UTILITY** : RAB, Allowed ROE, Dividend Coverage

Ce module calcule les métriques DISPONIBLES à partir du FinancialSnapshot
yfinance (pas toutes — CET1, NPL, Combined Ratio, RAB ne sont pas dans
yfinance et nécessitent des sources spécialisées type SNL Financial,
Orbis Bank Focus, SFCR, etc.).

USAGE :

    from core.sector_metrics import compute_sector_specific_metrics

    profile = detect_profile(snapshot.company_info.sector, snapshot.company_info.industry)
    metrics = compute_sector_specific_metrics(snapshot, profile)
    # metrics = {
    #     "ev_dacf": 5.2, "ev_ebitdax": 4.8, "breakeven_brent": 45.0,
    #     "nim": 0.032, "cost_income": 0.58, "ptbv": 1.2, "rote": 0.14,
    #     "combined_ratio": 0.92, "ptb": 1.5,
    #     ...
    # }

Les fonctions retournent `None` pour les métriques non-calculables à partir
du snapshot fourni. L'appelant doit gérer ce cas (affichage "n.d." ou skip
de la métrique concernée).

NOTE : ces ratios sont des PROXIES calculés à partir des états financiers
disponibles dans yfinance. Ils ne remplacent pas les chiffres officiels
publiés par les régulateurs (BCE/EBA pour CET1, SFCR pour Solvency II).
Leur usage est indicatif et sert à alimenter la narrative PDF/PPTX.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _safe_ratio(num: Optional[float], den: Optional[float]) -> Optional[float]:
    """Division sûre : None si l'un des deux est None ou dénominateur ≤ 0."""
    if num is None or den is None:
        return None
    try:
        n = float(num)
        d = float(den)
        if d <= 0:
            return None
        return n / d
    except (TypeError, ValueError):
        return None


def _latest_year(snapshot) -> Optional[object]:
    """Retourne le FinancialYear le plus récent (LTM si dispo)."""
    years = snapshot.years if hasattr(snapshot, "years") else {}
    if not years:
        return None
    # Priorité à "LTM" dans le label
    ltm_keys = [k for k in years.keys() if "LTM" in str(k).upper()]
    if ltm_keys:
        return years[ltm_keys[0]]
    # Sinon la dernière année par ordre lexicographique (ex: "2024" > "2023")
    return years[max(years.keys())]


def _prev_year(snapshot):
    """Retourne le FinancialYear N-1 (utile pour les moyennes de bilan)."""
    years = snapshot.years if hasattr(snapshot, "years") else {}
    if not years:
        return None
    # Trie par nom décroissant, skip LTM, prend le deuxième
    sorted_keys = sorted(
        (k for k in years.keys() if "LTM" not in str(k).upper()),
        reverse=True,
    )
    if len(sorted_keys) >= 2:
        return years[sorted_keys[1]]
    return None


def _market_cap(snapshot) -> Optional[float]:
    mkt = getattr(snapshot, "market", None)
    if mkt is None:
        return None
    sp = getattr(mkt, "share_price", None)
    sh = getattr(mkt, "shares_diluted", None)
    if sp is None or sh is None:
        return None
    try:
        # share_price en devise unité, shares en millions → market_cap en millions
        return float(sp) * float(sh)
    except (TypeError, ValueError):
        return None


def _net_debt(fy) -> Optional[float]:
    """Dette nette = Short-term + Long-term - Cash."""
    if fy is None:
        return None
    st = getattr(fy, "short_term_debt", None) or 0
    lt = getattr(fy, "long_term_debt", None) or 0
    cash = getattr(fy, "cash", None) or 0
    try:
        return float(st) + float(lt) - float(cash)
    except (TypeError, ValueError):
        return None


def _ebitda(fy) -> Optional[float]:
    """EBITDA calculé depuis EBIT + D&A si dispo, sinon approximation."""
    if fy is None:
        return None
    ebit = getattr(fy, "ebit_yf", None)
    da = getattr(fy, "da", None)
    if ebit is not None and da is not None:
        try:
            return float(ebit) + abs(float(da))
        except (TypeError, ValueError):
            pass
    # Fallback : revenue - cogs - sga - rd (approximation naïve)
    return None


# ═════════════════════════════════════════════════════════════════════════════
# OIL_GAS — Métriques pétrolières
# ═════════════════════════════════════════════════════════════════════════════

def compute_oil_gas_metrics(snapshot) -> dict:
    """Calcule les ratios spécifiques au secteur pétrolier.

    Retourne un dict avec (chaque clé peut valoir None si non-calculable) :
    - ev_dacf : Enterprise Value / Debt-Adjusted Cash Flow
    - ev_ebitdax : EV / EBITDAX (EBITDA + exploration expense ≈ EBITDA en proxy)
    - dacf : DACF en millions de devise native
    - breakeven_brent : Prix du Brent implicite pour FCF neutre (approximation)
    - reserves_life : Années de réserves (N/A car yfinance ne fournit pas)
    - roace : Return on Average Capital Employed
    """
    fy = _latest_year(snapshot)
    if fy is None:
        return {}

    # EV = Market cap + Net Debt
    mcap = _market_cap(snapshot)
    net_debt = _net_debt(fy)
    ev = None
    if mcap is not None and net_debt is not None:
        ev = mcap + net_debt

    ebitda = _ebitda(fy)
    revenue = getattr(fy, "revenue", None)

    # DACF = Operating Cash Flow + Interest * (1 - tax_rate)
    # OCF approximation : NI + D&A + change_wc
    ni = getattr(fy, "net_income_yf", None)
    da = getattr(fy, "da", None) or 0
    d_ar = getattr(fy, "change_accounts_receivable", None) or 0
    d_inv = getattr(fy, "change_inventories", None) or 0
    d_ap = getattr(fy, "change_accounts_payable", None) or 0
    d_wc = getattr(fy, "other_wc_changes", None) or 0
    int_exp = getattr(fy, "interest_expense", None)
    tax_rate = None
    mkt = getattr(snapshot, "market", None)
    if mkt is not None:
        tax_rate = getattr(mkt, "tax_rate", None)
    if tax_rate is None:
        tax_rate = 0.25  # hypothèse conservatrice

    ocf = None
    if ni is not None:
        try:
            ocf = float(ni) + float(da or 0) + float(d_ar) + float(d_inv) + float(d_ap) + float(d_wc)
        except (TypeError, ValueError):
            ocf = None

    dacf = None
    if ocf is not None and int_exp is not None:
        try:
            dacf = ocf + abs(float(int_exp)) * (1 - float(tax_rate))
        except (TypeError, ValueError):
            dacf = None

    ev_dacf = _safe_ratio(ev, dacf)
    ev_ebitdax = _safe_ratio(ev, ebitda)  # EBITDAX ≈ EBITDA sans donnée exploration

    # Break-even Brent : approximation = revenue / (production_proxy * 1.0)
    # Sans donnée de production, on ne peut pas calculer. Laissé à None.
    breakeven_brent = None

    # Reserves Life : yfinance ne fournit pas les réserves 1P/2P/3P → N/A
    reserves_life = None

    # ROACE = EBIT * (1 - tax) / average capital employed
    # Capital employed = equity + long-term debt
    ebit = getattr(fy, "ebit_yf", None)
    equity = getattr(fy, "total_equity_yf", None) or 0
    ltd = getattr(fy, "long_term_debt", None) or 0
    cap_employed = None
    try:
        cap_employed = float(equity) + float(ltd)
    except (TypeError, ValueError):
        pass
    roace = None
    if ebit is not None and cap_employed and cap_employed > 0:
        try:
            roace = float(ebit) * (1 - float(tax_rate)) / cap_employed
        except (TypeError, ValueError):
            pass

    return {
        "ev_dacf": ev_dacf,
        "ev_ebitdax": ev_ebitdax,
        "dacf": dacf,
        "breakeven_brent": breakeven_brent,
        "reserves_life": reserves_life,
        "roace": roace,
        "ev": ev,
        "mcap": mcap,
        "net_debt": net_debt,
    }


# ═════════════════════════════════════════════════════════════════════════════
# BANK — Métriques bancaires
# ═════════════════════════════════════════════════════════════════════════════

def compute_bank_metrics(snapshot) -> dict:
    """Calcule les ratios bancaires spécifiques.

    Retourne un dict :
    - nii : Net Interest Income (interest_income - |interest_expense|)
    - nim : Net Interest Margin (NII / Average Earning Assets proxy)
    - cost_income : Cost / Income Ratio (SG&A / (NII + fees proxy))
    - rote : Return on Tangible Equity (NI / (Equity - Intangibles))
    - ptbv : Price / Tangible Book Value
    - efficiency_ratio : SG&A / Total Revenue (similar Cost/Income)
    - cet1 : None (yfinance ne fournit pas)
    - npl_ratio : None (yfinance ne fournit pas)
    """
    fy = _latest_year(snapshot)
    if fy is None:
        return {}

    int_inc = getattr(fy, "interest_income", None)
    int_exp = getattr(fy, "interest_expense", None)

    nii = None
    if int_inc is not None and int_exp is not None:
        try:
            # interest_expense stocké négatif par convention _IS_COST_FIELDS
            nii = float(int_inc) - abs(float(int_exp))
        except (TypeError, ValueError):
            pass

    # NIM = NII / Average Earning Assets
    # Proxy : earning assets ≈ 65% du total des actifs (convention sectorielle)
    ta_curr = getattr(fy, "total_assets_yf", None)
    fy_prev = _prev_year(snapshot)
    ta_prev = getattr(fy_prev, "total_assets_yf", None) if fy_prev else None
    avg_ta = None
    if ta_curr is not None and ta_prev is not None:
        try:
            avg_ta = (float(ta_curr) + float(ta_prev)) / 2
        except (TypeError, ValueError):
            pass
    elif ta_curr is not None:
        try:
            avg_ta = float(ta_curr)
        except (TypeError, ValueError):
            pass
    nim = None
    if nii is not None and avg_ta:
        nim = _safe_ratio(nii, avg_ta * 0.65)

    # Cost / Income = SG&A / (NII + fees proxy)
    # Fees ≈ revenue (les banques ont revenue = NII + fees)
    sga = getattr(fy, "sga", None)
    revenue = getattr(fy, "revenue", None)
    cost_income = None
    if sga is not None and revenue is not None:
        try:
            cost_income = abs(float(sga)) / float(revenue) if float(revenue) > 0 else None
        except (TypeError, ValueError):
            pass

    # ROTE = NI / (Equity - Intangibles)
    ni = getattr(fy, "net_income_yf", None)
    equity = getattr(fy, "total_equity_yf", None)
    intangibles = getattr(fy, "intangibles", None) or 0
    rote = None
    if ni is not None and equity is not None:
        try:
            tangible_equity = float(equity) - float(intangibles)
            if tangible_equity > 0:
                rote = float(ni) / tangible_equity
        except (TypeError, ValueError):
            pass

    # P/TBV = Market Cap / Tangible Book Value
    mcap = _market_cap(snapshot)
    ptbv = None
    if mcap is not None and equity is not None:
        try:
            tbv = float(equity) - float(intangibles)
            if tbv > 0:
                ptbv = mcap / tbv
        except (TypeError, ValueError):
            pass

    return {
        "nii": nii,
        "nim": nim,
        "cost_income": cost_income,
        "rote": rote,
        "ptbv": ptbv,
        "avg_assets": avg_ta,
        "tangible_equity": (float(equity) - float(intangibles)) if equity is not None else None,
        "cet1": None,      # yfinance ne fournit pas
        "npl_ratio": None,  # yfinance ne fournit pas
    }


# ═════════════════════════════════════════════════════════════════════════════
# INSURANCE — Métriques assurance
# ═════════════════════════════════════════════════════════════════════════════

def compute_insurance_metrics(snapshot) -> dict:
    """Calcule les ratios assurance spécifiques.

    Note : Combined Ratio, Loss Ratio, Solvency II ne sont PAS dans yfinance —
    ils viennent du SFCR publié annuellement par l'assureur (EIOPA).
    Ce helper calcule les proxies disponibles et marque les autres None.

    Retourne :
    - ptb : Price / Book Value
    - roe : Return on Equity
    - dividend_yield_payout : Dividend / Net Income
    - interest_coverage : EBIT / Interest Expense
    - leverage : Debt / Equity
    - asset_turnover : Revenue / Assets
    - combined_ratio : None (source : SFCR)
    - loss_ratio : None
    - solvency_ratio : None
    - embedded_value : None
    """
    fy = _latest_year(snapshot)
    if fy is None:
        return {}

    mcap = _market_cap(snapshot)
    equity = getattr(fy, "total_equity_yf", None)
    ni = getattr(fy, "net_income_yf", None)
    ebit = getattr(fy, "ebit_yf", None)
    int_exp = getattr(fy, "interest_expense", None)
    revenue = getattr(fy, "revenue", None)
    total_assets = getattr(fy, "total_assets_yf", None)
    total_debt = None
    st = getattr(fy, "short_term_debt", None) or 0
    lt = getattr(fy, "long_term_debt", None) or 0
    try:
        total_debt = float(st) + float(lt)
    except (TypeError, ValueError):
        pass
    dividends = getattr(fy, "dividends_paid", None) or getattr(fy, "dividends", None)

    ptb = _safe_ratio(mcap, equity)
    roe = _safe_ratio(ni, equity)
    dividend_payout = None
    if dividends is not None and ni is not None and ni != 0:
        try:
            dividend_payout = abs(float(dividends)) / float(ni)
        except (TypeError, ValueError):
            pass
    interest_coverage = None
    if ebit is not None and int_exp is not None:
        try:
            ie = abs(float(int_exp))
            if ie > 0:
                interest_coverage = float(ebit) / ie
        except (TypeError, ValueError):
            pass
    leverage = _safe_ratio(total_debt, equity)
    asset_turnover = _safe_ratio(revenue, total_assets)

    return {
        "ptb": ptb,
        "roe": roe,
        "dividend_payout": dividend_payout,
        "interest_coverage": interest_coverage,
        "leverage": leverage,
        "asset_turnover": asset_turnover,
        "combined_ratio": None,
        "loss_ratio": None,
        "solvency_ratio": None,
        "embedded_value": None,
    }


# ═════════════════════════════════════════════════════════════════════════════
# REIT — Métriques foncières
# ═════════════════════════════════════════════════════════════════════════════

def compute_reit_metrics(snapshot) -> dict:
    """Calcule les ratios REIT spécifiques (FFO, AFFO, NAV, LTV).

    Note : NAV et Cap Rate viennent d'évaluations d'experts indépendants
    (ex: Green Street) non disponibles via yfinance.
    """
    fy = _latest_year(snapshot)
    if fy is None:
        return {}

    ni = getattr(fy, "net_income_yf", None)
    da = getattr(fy, "da", None)
    equity = getattr(fy, "total_equity_yf", None)
    total_assets = getattr(fy, "total_assets_yf", None)
    mcap = _market_cap(snapshot)
    st = getattr(fy, "short_term_debt", None) or 0
    lt = getattr(fy, "long_term_debt", None) or 0

    # FFO ≈ NI + D&A (gains on sales not tracked)
    ffo = None
    if ni is not None and da is not None:
        try:
            ffo = float(ni) + abs(float(da))
        except (TypeError, ValueError):
            pass

    # AFFO ≈ FFO - CapEx (capital expenditures)
    capex = getattr(fy, "capex", None)
    affo = None
    if ffo is not None and capex is not None:
        try:
            affo = ffo - abs(float(capex))
        except (TypeError, ValueError):
            pass

    # P/FFO
    p_ffo = _safe_ratio(mcap, ffo)

    # LTV = Total Debt / Total Assets
    total_debt = None
    try:
        total_debt = float(st) + float(lt)
    except (TypeError, ValueError):
        pass
    ltv = _safe_ratio(total_debt, total_assets)

    # Debt / Equity
    debt_equity = _safe_ratio(total_debt, equity)

    return {
        "ffo": ffo,
        "affo": affo,
        "p_ffo": p_ffo,
        "ltv": ltv,
        "debt_equity": debt_equity,
        "p_nav": None,     # nécessite NAV expert
        "cap_rate": None,  # nécessite NAV expert
        "occupancy": None, # non tracké
    }


# ═════════════════════════════════════════════════════════════════════════════
# UTILITY — Métriques services aux collectivités
# ═════════════════════════════════════════════════════════════════════════════

def compute_utility_metrics(snapshot) -> dict:
    """Calcule les ratios utility spécifiques.

    Note : RAB (Regulated Asset Base) et Allowed ROE viennent des régulateurs
    (ARENH, Ofgem, etc.) non disponibles via yfinance.
    """
    fy = _latest_year(snapshot)
    if fy is None:
        return {}

    ni = getattr(fy, "net_income_yf", None)
    equity = getattr(fy, "total_equity_yf", None)
    revenue = getattr(fy, "revenue", None)
    dividends = getattr(fy, "dividends_paid", None) or getattr(fy, "dividends", None)
    capex = getattr(fy, "capex", None)
    ebitda = _ebitda(fy)
    mcap = _market_cap(snapshot)

    roe = _safe_ratio(ni, equity)
    dividend_coverage = None
    if dividends is not None and ni is not None and dividends != 0:
        try:
            dividend_coverage = float(ni) / abs(float(dividends))
        except (TypeError, ValueError):
            pass
    capex_intensity = None
    if capex is not None and revenue is not None:
        try:
            capex_intensity = abs(float(capex)) / float(revenue) if float(revenue) > 0 else None
        except (TypeError, ValueError):
            pass

    return {
        "roe": roe,
        "dividend_coverage": dividend_coverage,
        "capex_intensity": capex_intensity,
        "ebitda": ebitda,
        "rab": None,            # nécessite données régulateur
        "allowed_roe": None,     # nécessite données régulateur
        "regulatory_ratio": None,
    }


# ═════════════════════════════════════════════════════════════════════════════
# API PRINCIPALE
# ═════════════════════════════════════════════════════════════════════════════

def compute_sector_specific_metrics(snapshot, profile: str) -> dict:
    """Dispatcher : calcule les métriques spécifiques au profil sectoriel.

    Args:
        snapshot : FinancialSnapshot
        profile  : STANDARD | OIL_GAS | BANK | INSURANCE | REIT | UTILITY

    Returns:
        dict de métriques profil-spécifiques. Les valeurs peuvent être None
        si non-calculables à partir de yfinance. STANDARD retourne un dict
        vide (les ratios standards sont déjà calculés par AgentQuant).
    """
    if snapshot is None:
        return {}
    _p = (profile or "STANDARD").upper()
    if _p == "OIL_GAS":
        return compute_oil_gas_metrics(snapshot)
    if _p == "BANK":
        return compute_bank_metrics(snapshot)
    if _p == "INSURANCE":
        return compute_insurance_metrics(snapshot)
    if _p == "REIT":
        return compute_reit_metrics(snapshot)
    if _p == "UTILITY":
        return compute_utility_metrics(snapshot)
    # STANDARD : pas de métriques sectorielles spéciales
    return {}


def get_sector_prompt_hint(profile: str) -> str:
    """Retourne un hint textuel injectable dans un prompt LLM pour orienter
    l'analyse en fonction du profil sectoriel.

    Utilisé par pdf_writer.py et pptx_writer.py pour que tous les prompts
    (business model, valorisation, risques, margin analysis, conclusion)
    héritent d'une grille sectorielle cohérente.

    Retourne '' pour STANDARD (pas d'orientation spéciale).
    """
    _p = (profile or "STANDARD").upper()
    if _p == "OIL_GAS":
        return (
            "IMPORTANT : société pétrolière/gazière. Les multiples EV/EBITDA "
            "standards sont peu pertinents — privilégie EV/DACF, EV/EBITDAX, "
            "break-even Brent, réserves 1P/2P, sensibilité prix du pétrole. "
            "N'UTILISE PAS P/E comme ratio principal (sensible aux cycles baril). "
            "Parle de transition énergétique, pression stranded assets, "
            "capex upstream vs renouvelables."
        )
    if _p == "BANK":
        return (
            "IMPORTANT : institution bancaire. Les multiples EV/EBITDA et "
            "ND/EBITDA n'ont aucun sens — un bilan bancaire est dominé par "
            "les loans/deposits, pas une dette corporate. Privilégie NIM, "
            "Cost/Income, CET1 (si dispo), ROTE, P/TBV, qualité du portefeuille "
            "(NPL/LLR). Parle cycle de crédit, pression taux, régulation Bâle III/IV, "
            "sensibilité spread taux longs/courts."
        )
    if _p == "INSURANCE":
        return (
            "IMPORTANT : compagnie d'assurance. Les métriques classiques "
            "(EV/EBITDA, Current Ratio) sont non pertinentes. Privilégie P/B, "
            "ROE, Combined Ratio (si dispo), Solvency II (si dispo), qualité "
            "des réserves techniques. Parle duration des passifs, risque taux, "
            "cycle tarifaire, Embedded Value, réassurance."
        )
    if _p == "REIT":
        return (
            "IMPORTANT : REIT (Real Estate Investment Trust). Les métriques "
            "FFO, AFFO, NAV, LTV, Cap Rate priment sur P/E et EV/EBITDA. "
            "Parle diversification géographique et sectorielle, taux d'occupation, "
            "WAULT, coût du capital vs cap rate, sensibilité taux longs."
        )
    if _p == "UTILITY":
        return (
            "IMPORTANT : utility (services aux collectivités). RAB, Allowed ROE "
            "et dividendes couvrent l'analyse (revenus régulés, transition "
            "énergétique, tarifs autorisés). P/E et Dividend Yield priment, "
            "EV/EBITDA reste pertinent mais secondaire. Parle du cadre "
            "réglementaire (ARENH, CRE, Ofgem) et de sa stabilité."
        )
    return ""


def format_sector_metrics_for_prompt(metrics: dict, profile: str) -> str:
    """Formate les métriques sectorielles en bloc texte pour inclusion dans
    un prompt LLM. Skip les valeurs None.

    Exemple de sortie pour OIL_GAS :
        "Métriques pétrolières : EV/DACF 5.2x · EV/EBITDAX 4.8x · ROACE 12.3%"
    """
    if not metrics:
        return ""
    _p = (profile or "STANDARD").upper()

    def _x(v, suf="x"):
        return f"{v:.1f}{suf}" if isinstance(v, (int, float)) else "n.d."

    def _pct(v):
        return f"{v*100:.1f}%" if isinstance(v, (int, float)) else "n.d."

    if _p == "OIL_GAS":
        parts = []
        if metrics.get("ev_dacf") is not None:
            parts.append(f"EV/DACF {_x(metrics['ev_dacf'])}")
        if metrics.get("ev_ebitdax") is not None:
            parts.append(f"EV/EBITDAX {_x(metrics['ev_ebitdax'])}")
        if metrics.get("roace") is not None:
            parts.append(f"ROACE {_pct(metrics['roace'])}")
        return "Métriques pétrolières : " + " · ".join(parts) if parts else ""

    if _p == "BANK":
        parts = []
        if metrics.get("nim") is not None:
            parts.append(f"NIM {_pct(metrics['nim'])}")
        if metrics.get("cost_income") is not None:
            parts.append(f"Cost/Income {_pct(metrics['cost_income'])}")
        if metrics.get("rote") is not None:
            parts.append(f"ROTE {_pct(metrics['rote'])}")
        if metrics.get("ptbv") is not None:
            parts.append(f"P/TBV {_x(metrics['ptbv'])}")
        return "Métriques bancaires : " + " · ".join(parts) if parts else ""

    if _p == "INSURANCE":
        parts = []
        if metrics.get("ptb") is not None:
            parts.append(f"P/B {_x(metrics['ptb'])}")
        if metrics.get("roe") is not None:
            parts.append(f"ROE {_pct(metrics['roe'])}")
        if metrics.get("interest_coverage") is not None:
            parts.append(f"Couv. intérêts {_x(metrics['interest_coverage'])}")
        if metrics.get("leverage") is not None:
            parts.append(f"Levier {_x(metrics['leverage'])}")
        return "Métriques assurance (proxies) : " + " · ".join(parts) if parts else ""

    if _p == "REIT":
        parts = []
        if metrics.get("ffo") is not None:
            parts.append(f"FFO {metrics['ffo']:,.0f}M")
        if metrics.get("p_ffo") is not None:
            parts.append(f"P/FFO {_x(metrics['p_ffo'])}")
        if metrics.get("ltv") is not None:
            parts.append(f"LTV {_pct(metrics['ltv'])}")
        return "Métriques REIT : " + " · ".join(parts) if parts else ""

    if _p == "UTILITY":
        parts = []
        if metrics.get("roe") is not None:
            parts.append(f"ROE {_pct(metrics['roe'])}")
        if metrics.get("dividend_coverage") is not None:
            parts.append(f"Couv. div. {_x(metrics['dividend_coverage'])}")
        if metrics.get("capex_intensity") is not None:
            parts.append(f"Capex/Rev {_pct(metrics['capex_intensity'])}")
        return "Métriques utility : " + " · ".join(parts) if parts else ""

    return ""
