# -*- coding: utf-8 -*-
"""
tools/build_sector_templates.py — Génère les templates XLSX sectoriels
(INSURANCE / REIT / UTILITY) à partir du template OIL_GAS de référence.

Approche : clone + modifications ciblées sur les cellules spécifiques à chaque
secteur, sans toucher aux feuilles INPUT / SCENARIOS / DCF / DASHBOARD 2 /
STOCK_DATA qui ont la même structure pour tous.

Modifications par secteur :
1. Feuille DASHBOARD R54-R56 : label "OIL & GAS KPIs" → label sectoriel, et
   les 2 formules KPI en dessous (remplacer EV/DACF + Net Debt/EBITDAX par
   les ratios sectoriels pertinents).
2. Feuille SCENARIOS R9 : label "EBITDAX Margin (OIL_GAS)" → label secteur.
3. Feuille SECTOR_REF : ajoute une row sectorielle si elle n'existe pas
   (la row Energie/Utilities existe déjà, à réutiliser pour UTILITY).

Le writer excel_writer.py écrit les données financières via _is_rows_active etc.
qui viennent du cell_map du router. Tant que _INSURANCE_CELL_MAP etc. restent
vides (ou STANDARD), le writer utilise le layout STANDARD qui est identique à
celui de OIL_GAS sur la feuille INPUT.

USAGE :
    python tools/build_sector_templates.py

Génère les 3 fichiers dans assets/ et imprime un résumé.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

# Force stdout utf-8 pour Windows
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import openpyxl

_ASSETS = Path(__file__).resolve().parent.parent / "assets"
_BASE = _ASSETS / "FinSight_IA_Template_OIL_GAS_v1.xlsx"


# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURATION PAR SECTEUR
# ═════════════════════════════════════════════════════════════════════════════

SECTOR_CONFIG = {
    "INSURANCE": {
        "file": "FinSight_IA_Template_INSURANCE_v1.xlsx",
        # DASHBOARD R54 label
        "kpi_section_label": "MÉTRIQUES ASSURANCE (LTM)",
        # R55 KPI 1 : P/TBV (Market Cap / (Equity - Intangibles))
        "kpi1_label": "P/TBV",
        "kpi1_formula": "=IFERROR(INPUT!H97/(INPUT!H60-INPUT!H42),NA())",
        "kpi1_benchmark": "Bmk : 1,0-1,5x • Prime si >1,5x",
        # R56 KPI 2 : ROE
        "kpi2_label": "ROE",
        "kpi2_formula": "=IFERROR(INPUT!H26/INPUT!H60,NA())",
        "kpi2_benchmark": "Bmk : 10-15% stable • Reg Bâle-like",
        # SCENARIOS R9 label (remplace "EBITDAX Margin (OIL_GAS)")
        "scenario_r9_label": "Net Combined Ratio (ASSURANCE)",
        # SECTOR_REF new row to add (pour scenario lookup si D116 matche)
        "sector_ref_name": "Assurance / Insurance",
    },
    "REIT": {
        "file": "FinSight_IA_Template_REIT_v1.xlsx",
        "kpi_section_label": "MÉTRIQUES REIT (LTM)",
        # P/FFO = Market Cap / (Net Income + |D&A|)
        "kpi1_label": "P/FFO",
        "kpi1_formula": "=IFERROR(INPUT!H97/(INPUT!H26+ABS(INPUT!H16)),NA())",
        "kpi1_benchmark": "Bmk : 12-18x • Prime si qualité assets",
        # LTV = Total Debt / Total Assets
        "kpi2_label": "LTV",
        "kpi2_formula": "=IFERROR((INPUT!H48+INPUT!H54)/INPUT!H44,NA())",
        "kpi2_benchmark": "Bmk : <40% sain • Stress si >50%",
        "scenario_r9_label": "NOI Margin (REIT)",
        "sector_ref_name": "Immobilier / REIT",
    },
    "UTILITY": {
        "file": "FinSight_IA_Template_UTILITY_v1.xlsx",
        "kpi_section_label": "MÉTRIQUES UTILITY (LTM)",
        # EV/EBITDA = EV / EBITDA (standard pour utilities)
        "kpi1_label": "EV/EBITDA",
        "kpi1_formula": "=IFERROR(INPUT!H98/INPUT!H30,NA())",
        "kpi1_benchmark": "Bmk : 8-11x • Prime si croissance RAB",
        # Dividend Yield = |Dividends Paid| / Market Cap
        "kpi2_label": "Dividend Yield",
        "kpi2_formula": "=IFERROR(ABS(INPUT!H85)/INPUT!H97,NA())",
        "kpi2_benchmark": "Bmk : 3-5% • Clé utility",
        "scenario_r9_label": "EBITDA Margin (UTILITY)",
        "sector_ref_name": None,  # "Energie / Utilities" existe déjà
    },
}


# ═════════════════════════════════════════════════════════════════════════════
# MAIN BUILD
# ═════════════════════════════════════════════════════════════════════════════

def build_template(profile: str, config: dict) -> Path:
    """Clone OIL_GAS et applique les modifications sectorielles."""
    target = _ASSETS / config["file"]

    # Clone
    shutil.copy2(_BASE, target)
    print(f"\n[{profile}] Clone : {target.name}")

    # Ouvre + modifie
    wb = openpyxl.load_workbook(str(target), keep_links=False, data_only=False)

    # ── 1. DASHBOARD R54-R56 : KPI section sectorielle ──────────────────────
    ws_dash = wb["DASHBOARD"]
    # Préserve le style de la cellule en modifiant uniquement .value
    ws_dash.cell(row=54, column=2).value = config["kpi_section_label"]
    ws_dash.cell(row=55, column=2).value = config["kpi1_label"]
    ws_dash.cell(row=55, column=3).value = config["kpi1_formula"]
    ws_dash.cell(row=55, column=4).value = config["kpi1_benchmark"]
    ws_dash.cell(row=56, column=2).value = config["kpi2_label"]
    ws_dash.cell(row=56, column=3).value = config["kpi2_formula"]
    ws_dash.cell(row=56, column=4).value = config["kpi2_benchmark"]
    # Clean OIL_GAS leftovers : E55 FCF Yield auxiliary + E56 Net Debt check
    # (non pertinents pour les autres secteurs)
    ws_dash.cell(row=55, column=5).value = None
    ws_dash.cell(row=56, column=5).value = None
    print(f"  DASHBOARD : {config['kpi_section_label']}")
    print(f"    R55 {config['kpi1_label']:12} = {config['kpi1_formula'][:50]}")
    print(f"    R56 {config['kpi2_label']:12} = {config['kpi2_formula'][:50]}")

    # ── 2. SCENARIOS R9 : label driver ──────────────────────────────────────
    ws_sc = wb["SCENARIOS"]
    # Colonne B row 9 : "EBITDAX Margin (OIL_GAS)"
    # On modifie uniquement le label, pas les ArrayFormulas qui suivent
    ws_sc.cell(row=9, column=2).value = config["scenario_r9_label"]
    print(f"  SCENARIOS R9 label : {config['scenario_r9_label']}")

    # ── 3. SECTOR_REF : ajoute row sectorielle si demandé ──────────────────
    if config.get("sector_ref_name"):
        ws_ref = wb["SECTOR_REF"]
        # Trouve la première row vide après la dernière ligne data
        new_row = ws_ref.max_row + 2  # +2 pour laisser un espacement
        # Ajoute les 11 drivers standards avec des valeurs par défaut raisonnables
        # Structure : col A = sector name, col B = driver name, col C/D/E = Pess/Real/Opt
        default_drivers = {
            "INSURANCE": [
                ("Revenue Growth Rate (Y1-Y5)", 0.01, 0.04, 0.07),
                ("Gross Margin", 0.10, 0.18, 0.25),
                ("EBITDA Margin", 0.05, 0.12, 0.18),
                ("SG&A (% Revenue)", 0.08, 0.06, 0.04),
                ("R&D (% Revenue)", 0.00, 0.00, 0.00),
                ("CapEx (% Revenue)", 0.02, 0.015, 0.01),
                ("Change in NWC (% Rev Change)", 0.02, 0.01, 0.005),
                ("Terminal Growth Rate", 0.01, 0.02, 0.03),
                ("WACC", 0.09, 0.08, 0.07),
                ("EV/EBITDA Exit Multiple", 6, 8, 11),
            ],
            "REIT": [
                ("Revenue Growth Rate (Y1-Y5)", 0.00, 0.03, 0.06),
                ("Gross Margin", 0.60, 0.70, 0.80),  # REIT high gross margin
                ("EBITDA Margin", 0.55, 0.65, 0.75),
                ("SG&A (% Revenue)", 0.05, 0.03, 0.02),
                ("R&D (% Revenue)", 0.00, 0.00, 0.00),
                ("CapEx (% Revenue)", 0.10, 0.07, 0.04),
                ("Change in NWC (% Rev Change)", 0.02, 0.01, 0.005),
                ("Terminal Growth Rate", 0.01, 0.02, 0.025),
                ("WACC", 0.08, 0.07, 0.055),
                ("EV/EBITDA Exit Multiple", 15, 18, 22),
            ],
        }
        drivers = default_drivers.get(profile, [])
        for i, (drv_name, pes, real, opt) in enumerate(drivers):
            r = new_row + i
            ws_ref.cell(row=r, column=1).value = config["sector_ref_name"]
            ws_ref.cell(row=r, column=2).value = drv_name
            ws_ref.cell(row=r, column=3).value = pes
            ws_ref.cell(row=r, column=4).value = real
            ws_ref.cell(row=r, column=5).value = opt
        print(f"  SECTOR_REF : +{len(drivers)} rows pour '{config['sector_ref_name']}'")

    # ── 4. Save ──────────────────────────────────────────────────────────────
    wb.save(str(target))
    sz = target.stat().st_size // 1024
    print(f"  Saved : {target.name} ({sz} ko)")
    return target


def main():
    if not _BASE.exists():
        print(f"ERREUR : base template introuvable : {_BASE}")
        return 1

    print("=" * 70)
    print("  BUILD SECTOR TEMPLATES — base OIL_GAS (TTE)")
    print("=" * 70)

    for profile, config in SECTOR_CONFIG.items():
        build_template(profile, config)

    print("\n" + "=" * 70)
    print("  OK — 3 templates générés :")
    for profile, config in SECTOR_CONFIG.items():
        print(f"    assets/{config['file']}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
