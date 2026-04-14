"""Système de profils sectoriels pour FinSight.

Détecte le profil d'une société à partir de son secteur + industrie yfinance
et fournit les métriques, modèles de valorisation et prompts LLM spécifiques.

Profils supportés :
- STANDARD   : tech, conso, healthcare classique, industrials, materials, etc.
- BANK       : banques commerciales (Financial Services + Banks)
- INSURANCE  : assurances (Financial Services + Insurance)
- REIT       : foncières cotées (Real Estate)
- UTILITY    : utilities régulées (Utilities)
- OIL_GAS    : E&P pétrole/gaz (Energy + Oil & Gas E&P ou Integrated)

Usage :
    from core.sector_profiles import detect_profile, get_profile_config

    profile = detect_profile(sector="Financial Services", industry="Banks - Diversified")
    # → "BANK"

    config = get_profile_config(profile)
    # → dict avec ratios_keys, valuation_model, prompt_hints, table_rows, etc.
"""
from __future__ import annotations


# =============================================================================
# DÉTECTION DU PROFIL
# =============================================================================

STANDARD = "STANDARD"
BANK     = "BANK"
INSURANCE = "INSURANCE"
REIT     = "REIT"
UTILITY  = "UTILITY"
OIL_GAS  = "OIL_GAS"


def detect_profile(sector: str | None, industry: str | None = None) -> str:
    """Détecte le profil sectoriel à partir du sector+industry yfinance.

    Args:
        sector   : sector yfinance (ex: "Financial Services", "Real Estate")
        industry : industry yfinance (ex: "Banks - Diversified", "REIT - Residential")

    Returns:
        Un des profils : STANDARD, BANK, INSURANCE, REIT, UTILITY, OIL_GAS
    """
    s = (sector or "").strip().lower()
    i = (industry or "").strip().lower()

    # REIT — Real Estate ou industry contient REIT
    if "real estate" in s or "reit" in i:
        return REIT

    # Utilities
    if "utilities" in s or "utility" in s or "utilit" in i:
        return UTILITY

    # Banks
    if "financial" in s:
        if any(kw in i for kw in ("bank", "banque", "lending", "saving")):
            return BANK
        if any(kw in i for kw in ("insurance", "assurance", "reinsurance")):
            return INSURANCE
        # Capital markets / investment banks (Goldman Sachs, Morgan Stanley) →
        # BANK : pas d'EBITDA significatif, valorisation P/B + ROE comme banques
        if "capital markets" in i:
            return BANK
        # Asset managers (BlackRock, Brookfield) : fee-based, marges nettes →
        # restent en STANDARD (comparables a societes de services)
        return STANDARD

    # Oil & Gas E&P (exploration & production) ou integrated
    if "energy" in s:
        # Exclure d'abord les sous-secteurs aval (downstream) qui sont plus proches du STANDARD
        if any(kw in i for kw in ("refining", "marketing", "storage", "transport",
                                   "equipment", "service", "drilling")):
            return STANDARD
        # Puis matcher les profils upstream
        if any(kw in i for kw in ("e&p", "exploration", "integrated", "oil & gas")):
            return OIL_GAS
        return STANDARD

    return STANDARD


# =============================================================================
# CONFIGURATION PAR PROFIL
# =============================================================================

# Schéma du dict config :
# - name                : nom lisible du profil
# - description         : une ligne résumant pourquoi ce profil existe
# - valuation_model     : "DCF" | "DDM" (Dividend Discount Model) | "NAV" | "RAB"
# - ratios_vs_peers     : liste de dicts {label, key, unit, benchmark_range}
# - llm_prompt_hints    : hints à injecter dans les prompts LLM
# - fin_table_rows      : rows additionnelles pour le tableau financier
# - hide_standard_rows  : rows du tableau standard à masquer (si non pertinentes)

_CONFIGS = {
    STANDARD: {
        "name":            "Standard (corporate)",
        "description":     "Profil générique pour sociétés industrielles et services",
        "valuation_model": "DCF",
        "ratios_vs_peers": [
            {"label": "EV/EBITDA (x)",    "key": "ev_ebitda",    "unit": "x",  "benchmark_range": (8, 18)},
            {"label": "P/E (x)",          "key": "pe_ratio",     "unit": "x",  "benchmark_range": (15, 25)},
            {"label": "EV/Revenue (x)",   "key": "ev_revenue",   "unit": "x",  "benchmark_range": (1, 5)},
            {"label": "Marge brute",      "key": "gross_margin", "unit": "%",  "benchmark_range": (30, 60)},
            {"label": "Marge EBITDA",     "key": "ebitda_margin","unit": "%",  "benchmark_range": (15, 30)},
            {"label": "Return on Equity", "key": "roe",          "unit": "%",  "benchmark_range": (10, 20)},
        ],
        "llm_prompt_hints": (
            "Utilise les ratios standards EV/EBITDA, P/E, EV/Revenue, marges brute/EBITDA/nette, ROE, ROIC. "
            "Mentionne la génération de cash flow libre (FCF) et la qualité du bilan (Altman Z)."
        ),
        "fin_table_rows": [],
        "hide_standard_rows": [],
    },

    BANK: {
        "name":            "Banque commerciale",
        "description":     "Banques : pas d'EBITDA, valorisation sur P/TBV + DDM",
        "valuation_model": "DDM",  # Dividend Discount Model (Gordon)
        "ratios_vs_peers": [
            {"label": "P/TBV (x)",              "key": "pb_ratio",        "unit": "x",  "benchmark_range": (0.8, 1.5)},
            {"label": "P/E (x)",                "key": "pe_ratio",        "unit": "x",  "benchmark_range": (8, 14)},
            {"label": "NIM (Net Interest Mg)",  "key": "bank_nim",        "unit": "%",  "benchmark_range": (1.5, 3.5)},
            {"label": "Cost/Income",            "key": "bank_cost_income","unit": "%",  "benchmark_range": (45, 65)},
            {"label": "CET1 Ratio",             "key": "bank_cet1",       "unit": "%",  "benchmark_range": (12, 16)},
            {"label": "Return on Equity (ROE)", "key": "roe",             "unit": "%",  "benchmark_range": (8, 15)},
            {"label": "NPL Ratio",              "key": "bank_npl",        "unit": "%",  "benchmark_range": (0.5, 3.0)},
            {"label": "Dividend Yield",         "key": "div_yield",       "unit": "%",  "benchmark_range": (3, 7)},
        ],
        "llm_prompt_hints": (
            "ATTENTION : cette société est une banque commerciale. "
            "N'utilise PAS EV/EBITDA ni EV/Revenue — inapplicables au secteur bancaire. "
            "Les métriques clés sont : P/TBV (price to tangible book value), P/E, "
            "NIM (net interest margin), Cost/Income ratio, CET1 ratio, NPL ratio, ROE et ROA. "
            "La valorisation se fait via Dividend Discount Model (DDM Gordon-Shapiro) "
            "ou P/TBV × TBV cible. Un ROE supérieur au coût du capital justifie un P/TBV > 1.0. "
            "Mentionne la qualité du bilan (NPL coverage, LCR, NSFR), les revenus récurrents "
            "(commissions vs Net Interest Income), et la sensibilité aux taux directeurs."
        ),
        "fin_table_rows": [
            # Custom rows à ajouter au tableau financier : (label, key)
            ("Net Interest Income",     "bank_nii"),
            ("Fees & Commissions",      "bank_fees"),
            ("Cost/Income",             "bank_cost_income"),
            ("Provisions / loans",      "bank_provisions"),
        ],
        "hide_standard_rows": ["EBITDA", "Marge EBITDA"],  # pas pertinent pour banque
    },

    INSURANCE: {
        "name":            "Assurance",
        "description":     "Assureurs : Combined Ratio + Solvency II + P/EV",
        "valuation_model": "EV",  # Embedded Value
        "ratios_vs_peers": [
            {"label": "P/EV (x)",             "key": "ins_pev",          "unit": "x",  "benchmark_range": (0.7, 1.2)},
            {"label": "P/BV (x)",             "key": "pb_ratio",         "unit": "x",  "benchmark_range": (0.8, 1.5)},
            {"label": "Combined Ratio",       "key": "ins_combined",     "unit": "%",  "benchmark_range": (92, 98)},
            {"label": "Loss Ratio",           "key": "ins_loss",         "unit": "%",  "benchmark_range": (60, 70)},
            {"label": "Expense Ratio",        "key": "ins_expense",      "unit": "%",  "benchmark_range": (25, 32)},
            {"label": "Solvency II Ratio",    "key": "ins_solvency",     "unit": "%",  "benchmark_range": (180, 250)},
            {"label": "ROE",                  "key": "roe",              "unit": "%",  "benchmark_range": (8, 14)},
            {"label": "Dividend Yield",       "key": "div_yield",        "unit": "%",  "benchmark_range": (4, 7)},
        ],
        "llm_prompt_hints": (
            "ATTENTION : cette société est une compagnie d'assurance. "
            "N'utilise PAS EV/EBITDA — inapplicable. Les métriques clés sont : "
            "Combined Ratio (cible < 100% = profit technique), Loss Ratio, Expense Ratio, "
            "Solvency II Ratio (> 200% = sain), P/EV (price-to-embedded-value), ROE. "
            "La valorisation repose sur l'Embedded Value (EV = Net Asset Value + Value of In-Force business). "
            "Un Combined Ratio sous 95% traduit une excellente discipline de souscription. "
            "Mentionne l'allocation d'actifs du portefeuille d'investissement et la sensibilité "
            "aux taux longs (duration gap)."
        ),
        "fin_table_rows": [
            ("Primes brutes émises",    "ins_gross_premiums"),
            ("Combined Ratio",          "ins_combined"),
            ("Solvency II",             "ins_solvency"),
        ],
        "hide_standard_rows": ["EBITDA", "Marge EBITDA"],
    },

    REIT: {
        "name":            "REIT / Foncière cotée",
        "description":     "Foncières : FFO/AFFO + NAV + Cap Rate",
        "valuation_model": "NAV",  # Net Asset Value
        "ratios_vs_peers": [
            {"label": "P/NAV (x)",          "key": "reit_p_nav",       "unit": "x",  "benchmark_range": (0.8, 1.2)},
            {"label": "P/FFO (x)",          "key": "reit_p_ffo",       "unit": "x",  "benchmark_range": (12, 20)},
            {"label": "P/AFFO (x)",         "key": "reit_p_affo",      "unit": "x",  "benchmark_range": (15, 25)},
            {"label": "Cap Rate",           "key": "reit_cap_rate",    "unit": "%",  "benchmark_range": (4.0, 7.0)},
            {"label": "Occupancy Rate",     "key": "reit_occupancy",   "unit": "%",  "benchmark_range": (92, 98)},
            {"label": "Dividend Yield",     "key": "div_yield",        "unit": "%",  "benchmark_range": (3.5, 6.5)},
            {"label": "LTV",                "key": "reit_ltv",         "unit": "%",  "benchmark_range": (30, 50)},
            {"label": "Debt/EBITDA",        "key": "net_debt_ebitda",  "unit": "x",  "benchmark_range": (5, 9)},
        ],
        "llm_prompt_hints": (
            "ATTENTION : cette société est un REIT (Real Estate Investment Trust / foncière cotée). "
            "Les métriques clés sont : P/NAV (discount/premium à la valeur nette d'inventaire), "
            "FFO (Funds From Operations = net income + amortissements + charges non-cash), "
            "AFFO (Adjusted FFO = FFO - capex récurrents), Cap Rate (yield immobilier = NOI/property value), "
            "Occupancy Rate, LTV (Loan-to-Value), Debt/EBITDA. "
            "La valorisation se fait via NAV (GAV - dette nette) et multiples P/FFO et P/AFFO. "
            "Le P/E classique est moins pertinent car dilué par les amortissements comptables. "
            "Mentionne la qualité du portefeuille (géographie, class A vs B, WALT = weighted average lease term), "
            "la sensibilité aux taux longs (duration) et le cycle immobilier actuel."
        ),
        "fin_table_rows": [
            ("FFO",                     "reit_ffo"),
            ("AFFO",                    "reit_affo"),
            ("NOI",                     "reit_noi"),
            ("Occupancy",               "reit_occupancy"),
        ],
        "hide_standard_rows": ["EBITDA", "Marge EBITDA"],
    },

    UTILITY: {
        "name":            "Utility régulée",
        "description":     "Utilities : RAB + Regulated Return + Payout",
        "valuation_model": "RAB",  # Regulated Asset Base
        "ratios_vs_peers": [
            {"label": "EV/EBITDA (x)",       "key": "ev_ebitda",       "unit": "x",  "benchmark_range": (8, 12)},
            {"label": "P/E (x)",             "key": "pe_ratio",        "unit": "x",  "benchmark_range": (12, 18)},
            {"label": "EV/RAB (x)",          "key": "util_ev_rab",     "unit": "x",  "benchmark_range": (1.0, 1.4)},
            {"label": "Debt/EBITDA",         "key": "net_debt_ebitda", "unit": "x",  "benchmark_range": (3.5, 5.5)},
            {"label": "Dividend Yield",      "key": "div_yield",       "unit": "%",  "benchmark_range": (3.5, 6.0)},
            {"label": "Payout Ratio",        "key": "payout_ratio",    "unit": "%",  "benchmark_range": (60, 85)},
            {"label": "Allowed Return (CMPC)","key": "util_allowed",   "unit": "%",  "benchmark_range": (5.5, 7.5)},
            {"label": "ROE",                 "key": "roe",             "unit": "%",  "benchmark_range": (7, 11)},
        ],
        "llm_prompt_hints": (
            "ATTENTION : cette société est une utility régulée (électricité, gaz, eau). "
            "Son cash-flow est fortement contraint par le cadre régulatoire. "
            "Les métriques clés sont : EV/RAB (Regulated Asset Base = actif rémunéré), "
            "Debt/EBITDA (levier élevé acceptable car cash-flow stable), Dividend Yield, "
            "Payout Ratio, Allowed Return on RAB (taux de rémunération autorisé par le régulateur), "
            "ROE. "
            "La valorisation repose sur le RAB × EV/RAB multiple + valeur des activités non régulées. "
            "Un EV/RAB > 1.2 indique que le marché paye une prime au régulé (croissance RAB attendue). "
            "Mentionne la sensibilité aux taux d'intérêt (actif à duration longue), "
            "les cycles régulatoires (price control periods), et la transition énergétique."
        ),
        "fin_table_rows": [
            ("Regulated Asset Base",    "util_rab"),
            ("Allowed Return",          "util_allowed"),
            ("Opex/RAB",                "util_opex_rab"),
        ],
        "hide_standard_rows": [],
    },

    OIL_GAS: {
        "name":            "Oil & Gas E&P",
        "description":     "Exploration & Production : EV/DACF + réserves + breakeven",
        "valuation_model": "NAV",  # ou DACF
        "ratios_vs_peers": [
            {"label": "EV/DACF (x)",         "key": "og_ev_dacf",       "unit": "x",  "benchmark_range": (3, 6)},
            {"label": "EV/EBITDA (x)",       "key": "ev_ebitda",        "unit": "x",  "benchmark_range": (3, 5)},
            {"label": "P/E (x)",             "key": "pe_ratio",         "unit": "x",  "benchmark_range": (8, 12)},
            {"label": "Reserves/Production", "key": "og_rp_ratio",      "unit": "ans", "benchmark_range": (10, 20)},
            {"label": "F&D Cost ($/boe)",    "key": "og_fd_cost",       "unit": "$",  "benchmark_range": (8, 20)},
            {"label": "Breakeven WTI ($)",   "key": "og_breakeven",     "unit": "$",  "benchmark_range": (30, 55)},
            {"label": "Reserve Replacement", "key": "og_rrr",           "unit": "%",  "benchmark_range": (90, 130)},
            {"label": "Dividend Yield",      "key": "div_yield",        "unit": "%",  "benchmark_range": (3, 8)},
        ],
        "llm_prompt_hints": (
            "ATTENTION : cette société est un acteur Oil & Gas (exploration & production ou integrated). "
            "Les métriques spécifiques sont : EV/DACF (Debt-Adjusted Cash Flow), "
            "Reserves/Production (R/P ratio = years of production remaining), "
            "F&D Cost (Finding & Development cost per barrel), "
            "Breakeven WTI/Brent (prix du baril requis pour couvrir les coûts + dividende), "
            "Reserve Replacement Ratio (100%+ = croissance des réserves). "
            "La valorisation repose sur NAV (somme des valeurs actualisées des réserves) "
            "ou EV/DACF pour la comparabilité peer. "
            "Mentionne le cycle du prix du pétrole, le hedging, la transition énergétique "
            "(stranded assets risk), et la discipline capital (dividend coverage)."
        ),
        "fin_table_rows": [
            ("Production (kboe/d)",     "og_production"),
            ("Reserves 1P",             "og_reserves_1p"),
            ("F&D Cost",                "og_fd_cost"),
        ],
        "hide_standard_rows": [],
    },
}


def get_profile_config(profile: str) -> dict:
    """Retourne la configuration d'un profil sectoriel.

    Args:
        profile : STANDARD, BANK, INSURANCE, REIT, UTILITY, OIL_GAS

    Returns:
        Dict de configuration. Fallback sur STANDARD si profil inconnu.
    """
    return _CONFIGS.get(profile) or _CONFIGS[STANDARD]


def get_valuation_model(profile: str) -> str:
    """Retourne le modèle de valorisation du profil."""
    return get_profile_config(profile).get("valuation_model", "DCF")


def get_prompt_hints(profile: str) -> str:
    """Retourne les hints à injecter dans les prompts LLM."""
    return get_profile_config(profile).get("llm_prompt_hints", "")


def is_non_standard(profile: str) -> bool:
    """True si le profil nécessite un traitement spécifique (vs corporate standard)."""
    return profile != STANDARD
