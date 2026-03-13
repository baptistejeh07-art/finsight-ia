# =============================================================================
# FinSight IA — Référentiel Sectoriel
# config/sector_ref.py
#
# Drivers sectoriels pour les projections (scénario Réaliste).
# Sources : Bloomberg consensus, MSCI sector medians, Damodaran 2024.
# Secteurs : nomenclature yfinance exacte.
# =============================================================================

from __future__ import annotations

# ---------------------------------------------------------------------------
# Drivers par secteur yfinance
# ---------------------------------------------------------------------------
# Champs :
#   rev_growth          : croissance CA annuelle réaliste (CAGR 2 ans)
#   gross_margin_target : marge brute cible (convergence)
#   ebitda_margin_target: marge EBITDA cible
#   net_margin_target   : marge nette cible
#   capex_pct_rev       : CapEx / Revenue (valeur absolue, sera négativée)
#   da_pct_rev          : D&A / Revenue
#   sga_pct_rev         : SG&A / Revenue (si non disponible dans données)
#   terminal_growth     : taux de croissance terminal DCF
#   tax_rate_default    : taux effectif IS de référence
#   erp                 : prime de risque marché (standard par secteur)

SECTOR_DRIVERS: dict[str, dict] = {
    "Technology": {
        "rev_growth":           0.09,
        "gross_margin_target":  0.55,
        "ebitda_margin_target": 0.26,
        "net_margin_target":    0.19,
        "capex_pct_rev":        0.04,
        "da_pct_rev":           0.04,
        "sga_pct_rev":          0.18,
        "terminal_growth":      0.030,
        "tax_rate_default":     0.18,
        "erp":                  0.055,
    },
    "Consumer Cyclical": {
        "rev_growth":           0.06,
        "gross_margin_target":  0.35,
        "ebitda_margin_target": 0.14,
        "net_margin_target":    0.07,
        "capex_pct_rev":        0.04,
        "da_pct_rev":           0.03,
        "sga_pct_rev":          0.16,
        "terminal_growth":      0.025,
        "tax_rate_default":     0.21,
        "erp":                  0.055,
    },
    "Consumer Defensive": {
        "rev_growth":           0.04,
        "gross_margin_target":  0.40,
        "ebitda_margin_target": 0.17,
        "net_margin_target":    0.09,
        "capex_pct_rev":        0.04,
        "da_pct_rev":           0.03,
        "sga_pct_rev":          0.15,
        "terminal_growth":      0.020,
        "tax_rate_default":     0.21,
        "erp":                  0.050,
    },
    "Healthcare": {
        "rev_growth":           0.07,
        "gross_margin_target":  0.55,
        "ebitda_margin_target": 0.23,
        "net_margin_target":    0.14,
        "capex_pct_rev":        0.04,
        "da_pct_rev":           0.05,
        "sga_pct_rev":          0.20,
        "terminal_growth":      0.025,
        "tax_rate_default":     0.19,
        "erp":                  0.055,
    },
    "Industrials": {
        "rev_growth":           0.05,
        "gross_margin_target":  0.30,
        "ebitda_margin_target": 0.14,
        "net_margin_target":    0.07,
        "capex_pct_rev":        0.05,
        "da_pct_rev":           0.03,
        "sga_pct_rev":          0.12,
        "terminal_growth":      0.020,
        "tax_rate_default":     0.21,
        "erp":                  0.055,
    },
    "Financial Services": {
        "rev_growth":           0.05,
        "gross_margin_target":  0.65,
        "ebitda_margin_target": 0.30,
        "net_margin_target":    0.20,
        "capex_pct_rev":        0.02,
        "da_pct_rev":           0.01,
        "sga_pct_rev":          0.25,
        "terminal_growth":      0.025,
        "tax_rate_default":     0.21,
        "erp":                  0.055,
    },
    "Energy": {
        "rev_growth":           0.03,
        "gross_margin_target":  0.25,
        "ebitda_margin_target": 0.20,
        "net_margin_target":    0.08,
        "capex_pct_rev":        0.12,
        "da_pct_rev":           0.06,
        "sga_pct_rev":          0.05,
        "terminal_growth":      0.015,
        "tax_rate_default":     0.22,
        "erp":                  0.060,
    },
    "Communication Services": {
        "rev_growth":           0.07,
        "gross_margin_target":  0.55,
        "ebitda_margin_target": 0.28,
        "net_margin_target":    0.16,
        "capex_pct_rev":        0.08,
        "da_pct_rev":           0.05,
        "sga_pct_rev":          0.15,
        "terminal_growth":      0.030,
        "tax_rate_default":     0.18,
        "erp":                  0.055,
    },
    "Basic Materials": {
        "rev_growth":           0.04,
        "gross_margin_target":  0.28,
        "ebitda_margin_target": 0.17,
        "net_margin_target":    0.08,
        "capex_pct_rev":        0.08,
        "da_pct_rev":           0.05,
        "sga_pct_rev":          0.08,
        "terminal_growth":      0.020,
        "tax_rate_default":     0.21,
        "erp":                  0.060,
    },
    "Real Estate": {
        "rev_growth":           0.04,
        "gross_margin_target":  0.55,
        "ebitda_margin_target": 0.42,
        "net_margin_target":    0.20,
        "capex_pct_rev":        0.10,
        "da_pct_rev":           0.08,
        "sga_pct_rev":          0.10,
        "terminal_growth":      0.025,
        "tax_rate_default":     0.15,
        "erp":                  0.050,
    },
    "Utilities": {
        "rev_growth":           0.03,
        "gross_margin_target":  0.38,
        "ebitda_margin_target": 0.30,
        "net_margin_target":    0.12,
        "capex_pct_rev":        0.15,
        "da_pct_rev":           0.06,
        "sga_pct_rev":          0.06,
        "terminal_growth":      0.020,
        "tax_rate_default":     0.21,
        "erp":                  0.048,
    },
    # Défaut générique
    "_default": {
        "rev_growth":           0.05,
        "gross_margin_target":  0.35,
        "ebitda_margin_target": 0.17,
        "net_margin_target":    0.09,
        "capex_pct_rev":        0.05,
        "da_pct_rev":           0.04,
        "sga_pct_rev":          0.14,
        "terminal_growth":      0.025,
        "tax_rate_default":     0.21,
        "erp":                  0.055,
    },
}


def get_sector_drivers(sector: str) -> dict:
    """Retourne les drivers sectoriels pour un secteur yfinance.
    Fallback sur '_default' si le secteur est inconnu."""
    return SECTOR_DRIVERS.get(sector or "_default", SECTOR_DRIVERS["_default"])
