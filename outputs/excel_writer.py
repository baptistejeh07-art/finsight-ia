# =============================================================================
# FinSight IA — Excel Writer v2
# outputs/excel_writer.py
#
# Injecte FinancialSnapshot dans TEMPLATE.xlsx (openpyxl).
# Respecte le contrat config/excel_mapping.py v2 :
#   - NE PAS écraser les cellules formule (is_formula_cell strict)
#   - Colonnes : D=le plus ancien, alignement gauche (H peut être vide si <5 ans)
#   - Aucune projection injectée (formules Excel dans feuille dédiée)
#   - Market data : colonne H uniquement (données point-in-time)
#   - Sheet principale : "INPUT"
#   - Sheet historique : "STOCK_DATA"
#
# Usage :
#   writer = ExcelWriter()
#   path   = writer.write(snapshot, synthesis, ratios)
# =============================================================================

from __future__ import annotations

import logging
import math
import os
import shutil
from datetime import date
from pathlib import Path
from typing import Optional

from config.excel_mapping import is_formula_cell, COMPANY_INFO as _CI_CELLS

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------

_DEFAULT_TEMPLATE = Path(__file__).parent.parent / "assets" / "TEMPLATE.xlsx"
_TEMPLATE_ENV = os.getenv("TEMPLATE_PATH", "")
# Toujours résoudre en absolu : si relatif, ancrer sur la racine du projet
_TEMPLATE = (
    Path(_TEMPLATE_ENV).resolve()
    if _TEMPLATE_ENV
    else _DEFAULT_TEMPLATE
)
_OUTPUT_DIR = Path(__file__).parent / "generated"

# Mois anglais locale-indépendants pour STOCK_DATA
_MONTH_EN = ["Jan","Feb","Mar","Apr","May","Jun",
             "Jul","Aug","Sep","Oct","Nov","Dec"]

# ---------------------------------------------------------------------------
# Mapping année → colonne Excel (5 exercices, du plus ancien au plus récent)
# D=N-4, E=N-3, F=N-2, G=N-1, H=N
# ---------------------------------------------------------------------------

def _build_year_col(snapshot) -> dict:
    """
    Construit le mapping année_label → colonne Excel.
    Alignement à gauche : D = premier exercice avec revenue, H = plus récent.
    Exclut les années sans revenue pour eviter un decalage avec les formules
    F128/G128 du template (qui comptent les colonnes completes a partir de D).
    """
    cols = ["D", "E", "F", "G", "H"]
    labels = sorted(snapshot.years.keys(), key=lambda y: int(y.split("_")[0]))
    labels = labels[-5:]  # max 5, les plus récents
    # Exclure les annees sans revenue : la formule F128 du template
    # compte depuis la colonne D — un trou en D decale tous les headers
    labels_with_rev = [
        l for l in labels
        if getattr(snapshot.years.get(l), "revenue", None) is not None
    ]
    if labels_with_rev:
        labels = labels_with_rev[-5:]
    return {label: cols[i] for i, label in enumerate(labels)}

# ---------------------------------------------------------------------------
# Champs IS à injecter en négatif (coûts attendus <0 par les formules Excel)
# ---------------------------------------------------------------------------

_IS_COST_FIELDS = {"cogs", "sga", "rd", "da", "interest_expense",
                   "tax_expense_real", "dividends"}

# FinancialYear field → ligne Excel
_IS_ROWS = {
    "revenue":          9,
    "cogs":             10,
    "sga":              14,
    "rd":               15,
    "da":               16,
    "interest_expense": 20,
    "interest_income":  21,
    "tax_expense_real": 25,
    "dividends":        29,
}

_BS_ASSET_ROWS = {
    "cash":                 34,
    "accounts_receivable":  35,
    "inventories":          36,
    "other_current_assets": 37,
    "ppe_net":              41,
    "intangibles":          42,
    "other_lt_assets":      43,
}

_BS_LIAB_ROWS = {
    "accounts_payable":      47,
    "short_term_debt":       48,
    "income_tax_payable":    49,
    "other_current_liab":    50,
    "long_term_debt":        54,
    # D58 : Paid-In Capital = Capital Stock + APIC (calculé dans yfinance_source)
    "common_equity_paid_in": 58,
}

_CF_ROWS = {
    "change_accounts_receivable": 71,
    "change_inventories":         72,
    "change_accounts_payable":    73,
    "other_wc_changes":           74,
    "capex":                      78,
    "other_investing":            79,
    "change_lt_debt":             83,
    "change_common_equity":       84,
    "dividends_paid":             85,
    "beginning_cash":             90,
}

# Market data — colonne H uniquement (données point-in-time, D-G = tirets dans le template)
# H108 WACC = FORMULE Excel — absent de la liste
_MKT_FIELDS = {
    "share_price":          "H95",
    "shares_diluted":       "H96",
    "beta_levered":         "H99",
    "risk_free_rate":       "H100",
    "erp":                  "H101",
    "cost_of_debt_pretax":  "H103",
    "tax_rate":             "H104",
    "weight_equity":        "H106",
    "weight_debt":          "H107",
    # H108 WACC = FORMULE — absent de la liste
    "terminal_growth":      "H109",
    "days_in_period":       "H110",
}


# ---------------------------------------------------------------------------
# ExcelWriter
# ---------------------------------------------------------------------------

class ExcelWriter:
    """
    Injecte un FinancialSnapshot dans TEMPLATE.xlsx.
    Conserve toutes les formules Excel intactes (vérification stricte).
    """

    def write(
        self,
        snapshot,
        synthesis=None,
        ratios=None,
        output_path: Optional[Path] = None,
        comparables=None,   # list[PeerData] ou None
    ) -> Path:
        try:
            import openpyxl
        except ImportError:
            raise RuntimeError("openpyxl requis : pip install openpyxl")

        if not _TEMPLATE.exists():
            raise FileNotFoundError(f"Template introuvable : {_TEMPLATE}")

        ticker = snapshot.ticker.replace(".", "_")
        today  = date.today().isoformat()

        if output_path is None:
            _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            output_path = _OUTPUT_DIR / f"{ticker}_{today}.xlsx"

        shutil.copy2(_TEMPLATE, output_path)
        wb = openpyxl.load_workbook(
            str(output_path),
            keep_links=False,
            keep_vba=False,
            data_only=False,
        )
        ws = wb["INPUT"]

        # ------------------------------------------------------------------
        # 1. Company info (cellules fixes colonne D)
        # ------------------------------------------------------------------
        # ------------------------------------------------------------------
        # 2. Données financières — 5 exercices historiques (H=LTM → D)
        #    Alignement droite : H = LTM, G = LTM-1, ...
        #    Colonnes inactives (ex: D,E si 3 ans) : rien écrit — None implicite
        # ------------------------------------------------------------------
        year_col_map = _build_year_col(snapshot)
        written = 0

        ci = snapshot.company_info

        # D117 Base Year = toujours l'annee LTM (label mappe sur H)
        # ci doit etre defini avant d'acceder a ci.base_year (bug ordre corrige)
        ltm_label = next((lbl for lbl, col in year_col_map.items() if col == "H"), None)
        if ltm_label:
            ltm_year = int(ltm_label.split("_")[0])
        else:
            # <5 ans : base_year = annee du label le plus recent dans year_col_map
            most_recent_lbl = max(year_col_map.keys(), key=lambda y: int(y.split("_")[0])) if year_col_map else None
            ltm_year = int(most_recent_lbl.split("_")[0]) if most_recent_lbl else ci.base_year
        _write_cells(ws, {
            _CI_CELLS["company_name"]:  ci.company_name,
            _CI_CELLS["ticker"]:        ci.ticker,
            _CI_CELLS["sector"]:        ci.sector or "",
            _CI_CELLS["base_year"]:     ltm_year,       # toujours l'année H
            _CI_CELLS["currency"]:      ci.currency,
            _CI_CELLS["units"]:         ci.units,
            _CI_CELLS["analysis_date"]: ci.analysis_date or today,
        })

        for year_str, fy in snapshot.years.items():
            col = year_col_map.get(year_str)
            if col is None:
                log.warning(f"[ExcelWriter] Annee '{year_str}' sans colonne — ignore")
                continue

            for field, row in _IS_ROWS.items():
                val = getattr(fy, field, None)
                if val is not None and field in _IS_COST_FIELDS:
                    val = -abs(val)
                # Fallback 0 pour interest_expense/income : certaines societes
                # (ex: Apple FY2024+) ne les declarent plus separement.
                # Le template F128 requiert ces cellules non-vides pour
                # afficher les headers d'annees — 0 = "non declare separement".
                if val is None and field in ("interest_expense", "interest_income"):
                    if getattr(fy, "revenue", None) is not None:
                        val = 0
                written += _safe_write(ws, col, row, val)

            for field, row in _BS_ASSET_ROWS.items():
                written += _safe_write(ws, col, row, getattr(fy, field, None))

            for field, row in _BS_LIAB_ROWS.items():
                written += _safe_write(ws, col, row, getattr(fy, field, None))

            for field, row in _CF_ROWS.items():
                written += _safe_write(ws, col, row, getattr(fy, field, None))

        # ------------------------------------------------------------------
        # 3. Market data — colonne H uniquement (données point-in-time)
        # ------------------------------------------------------------------
        mkt = snapshot.market
        for field, cell_ref in _MKT_FIELDS.items():
            val = getattr(mkt, field, None)
            if val is None:
                continue
            # Filtre NaN/inf
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                log.warning(f"[ExcelWriter] SKIP {cell_ref} ({field}) — valeur NaN/inf ignoree")
                continue
            # Garde 1 statique
            if is_formula_cell(cell_ref):
                log.error(f"[ExcelWriter] BLOQUE (statique) {cell_ref} — cellule formule market")
                continue
            # Garde 2 dynamique
            current = ws[cell_ref].value
            if isinstance(current, str) and current.startswith("="):
                log.error(f"[ExcelWriter] BLOQUE (dynamique) {cell_ref} — formule non declaree : {current[:60]}")
                continue
            log.debug(f"[ExcelWriter] WRITE {cell_ref} = {val!r}")
            ws[cell_ref] = val
            written += 1

        # ------------------------------------------------------------------
        # 4. Historique cours — onglet STOCK_DATA
        #    Toujours ecrire B3:C15 (13 lignes) pour effacer residus template
        # ------------------------------------------------------------------
        if "STOCK_DATA" in wb.sheetnames:
            ws_stock = wb["STOCK_DATA"]
            history = snapshot.stock_history or []
            for i in range(13):
                row = 3 + i
                if i < len(history):
                    pt = history[i]
                    # Format MMM-YY locale-independant (ex: "Mar-26")
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(pt.month, "%b-%y")
                        month_str = f"{_MONTH_EN[dt.month - 1]}-{dt.strftime('%y')}"
                    except Exception:
                        month_str = pt.month  # fallback : valeur brute
                    ws_stock[f"B{row}"] = month_str
                    ws_stock[f"C{row}"] = pt.price
                else:
                    ws_stock[f"B{row}"] = None
                    ws_stock[f"C{row}"] = None

        # ------------------------------------------------------------------
        # 5. Synthese IA — zone libre (lignes 123–131, colonne D)
        # ------------------------------------------------------------------
        if synthesis:
            _write_synthesis_zone(ws, synthesis)

        # ------------------------------------------------------------------
        # 6. Comparables — onglet COMPARABLES (peers lignes 9-13)
        # ------------------------------------------------------------------
        if comparables and "COMPARABLES" in wb.sheetnames:
            written += _write_comparables(wb["COMPARABLES"], comparables)

        wb.calculation.fullCalcOnLoad = True
        wb.save(str(output_path))
        log.info(f"[ExcelWriter] '{ticker}' — {written} cellules ecrites → {output_path.name}")
        return output_path


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _safe_write(ws, col: str, row: int, value) -> int:
    """
    Ecrit une valeur avec double-garde anti-formule :
      1. Garde statique  : FORMULA_CELLS du mapping (O(1))
      2. Garde dynamique : inspecte la valeur courante de la cellule dans le template
    Filtre NaN/inf pour eviter la corruption XML Excel.
    Log audit systematique avant chaque ecriture effective.
    """
    if value is None:
        return 0
    # Filtre NaN et inf : openpyxl ecrit "nan" ou "inf" comme string
    # ce qui genere des erreurs de formule dans sheet1.xml
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        log.warning(f"[ExcelWriter] SKIP {col}{row} — valeur NaN/inf ignoree")
        return 0
    cell_ref = f"{col}{row}"

    # Garde 1 — liste statique
    if is_formula_cell(cell_ref):
        log.error(f"[ExcelWriter] BLOQUE (statique) {cell_ref} — cellule formule")
        return 0

    # Garde 2 — valeur dynamique dans le classeur chargé
    current = ws[cell_ref].value
    if isinstance(current, str) and current.startswith("="):
        log.error(f"[ExcelWriter] BLOQUE (dynamique) {cell_ref} — formule non declaree : {current[:60]}")
        return 0

    # Log audit
    log.debug(f"[ExcelWriter] WRITE {cell_ref} = {value!r}")
    ws[cell_ref] = value
    return 1


def _write_cells(ws, mapping: dict) -> None:
    """Ecrit un dict {cell_ref: value} — COMPANY_INFO uniquement.
    Applique garde statique + garde dynamique formule."""
    for cell_ref, value in mapping.items():
        if value is None:
            continue
        # Filtre NaN float
        if isinstance(value, float) and math.isnan(value):
            log.warning(f"[ExcelWriter] SKIP {cell_ref} — valeur NaN ignoree")
            continue
        # Garde 1 statique
        if is_formula_cell(cell_ref):
            log.error(f"[ExcelWriter] BLOQUE (statique) {cell_ref} — cellule formule COMPANY_INFO")
            continue
        # Garde 2 dynamique
        current = ws[cell_ref].value
        if isinstance(current, str) and current.startswith("="):
            log.error(f"[ExcelWriter] BLOQUE (dynamique) {cell_ref} — formule non declaree : {current[:60]}")
            continue
        log.debug(f"[ExcelWriter] WRITE {cell_ref} = {value!r}")
        ws[cell_ref] = value


def _write_comparables(ws_comp, peers: list) -> int:
    """
    Injecte les 5 peers dans l'onglet COMPARABLES (lignes 9-13).
    Colonnes injectees : B (nom), C (ticker), D (price), E (EV $M),
                         F (Revenue $M), G (EBITDA $M), J (EBITDA growth), K (EPS)
    Colonnes formules intouchables : H (EV/EBITDA), I (EV/Rev), L (P/E)
    Lignes 15-18 (Mean/Med/Max/Min) et 20+ (Target + Implied) : intouchables.
    """
    # Cellules formule dans COMPARABLES — ne jamais ecraser
    _COMP_FORMULA_COLS = {"H", "I", "L"}   # par ligne peer
    _COMP_FORMULA_ROWS = set(range(15, 40)) # Mean/Med/Max/Min + Target + Implied

    written = 0
    for i, peer in enumerate(peers[:5]):
        row = 9 + i

        # Garde : ne jamais ecrire dans les lignes formule
        if row in _COMP_FORMULA_ROWS:
            continue

        def _w(col: str, val) -> None:
            nonlocal written
            if val is None:
                return
            if col in _COMP_FORMULA_COLS:
                log.error(f"[ExcelWriter] COMPARABLES : tentative col formule {col}{row}")
                return
            current = ws_comp[f"{col}{row}"].value
            if isinstance(current, str) and current.startswith("="):
                log.error(f"[ExcelWriter] COMPARABLES : formule non declaree {col}{row}")
                return
            log.debug(f"[ExcelWriter] COMPARABLES {col}{row} = {val!r}")
            ws_comp[f"{col}{row}"] = val
            written += 1

        _w("B", getattr(peer, "name", None) or peer.ticker)
        _w("C", peer.ticker)
        _w("D", getattr(peer, "share_price", None))
        _w("E", getattr(peer, "ev", None))
        _w("F", getattr(peer, "revenue_ltm", None))
        _w("G", getattr(peer, "ebitda_ltm", None))
        _w("J", getattr(peer, "ebitda_growth_ntm", None))
        _w("K", getattr(peer, "eps_ltm", None))

    log.info(f"[ExcelWriter] COMPARABLES — {written} cellules ecrites ({len(peers[:5])} peers)")
    return written


def _safe_write_cell(ws, cell_ref: str, value) -> None:
    """Ecriture securisee d'une cellule avec garde formule (statique + dynamique)."""
    if value is None:
        return
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        log.warning(f"[ExcelWriter] SKIP {cell_ref} — valeur NaN/inf ignoree")
        return
    # Garde statique
    if is_formula_cell(cell_ref):
        log.error(f"[ExcelWriter] BLOQUE (statique) {cell_ref} — cellule formule synthesis")
        return
    # Garde dynamique
    current = ws[cell_ref].value
    if isinstance(current, str) and current.startswith("="):
        log.error(f"[ExcelWriter] BLOQUE (dynamique) {cell_ref} — formule : {current[:60]}")
        return
    ws[cell_ref] = value


def _write_synthesis_zone(ws, synthesis) -> None:
    """Zone synthese IA — lignes 123-131, colonne D (zone libre post-mapping).
    Utilise _safe_write_cell pour eviter toute corruption formule.
    Note : '===' ne commence pas par '=' seul, mais on passe quand meme par la garde dynamique.
    """
    _safe_write_cell(ws, "D123", "--- SYNTHESE IA ---")
    _safe_write_cell(ws, "D124", f"Recommandation : {synthesis.recommendation}")
    _safe_write_cell(ws, "D125", f"Conviction : {synthesis.conviction:.0%}")
    _safe_write_cell(ws, "D126", f"Confiance IA : {synthesis.confidence_score:.0%}")
    if synthesis.target_base:
        _safe_write_cell(ws, "D127", f"Cible Base : {synthesis.target_base}")
    if synthesis.target_bull:
        _safe_write_cell(ws, "D128", f"Cible Bull : {synthesis.target_bull}")
    if synthesis.target_bear:
        _safe_write_cell(ws, "D129", f"Cible Bear : {synthesis.target_bear}")
    _safe_write_cell(ws, "D130", synthesis.summary[:200] if synthesis.summary else None)
    _safe_write_cell(ws, "D131", f"Invalidation : {synthesis.invalidation_conditions[:150]}")
