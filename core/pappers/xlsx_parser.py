"""
Parser XLSX Pappers — extrait les comptes annuels depuis le XLSX fourni par
Pappers API v2 (endpoint `/v2/document/telechargement`).

Le XLSX reproduit les formulaires CERFA officiels :
- 2050 (Bilan Actif) + 2051 (Bilan Passif)
- 2052 (Compte de résultat Charges) + 2053 (Produits)

Stratégie de parsing :
1. Ouvrir le XLSX via zipfile + ElementTree (openpyxl plante sur les styles
   Pappers, bug Python 3.14).
2. Pour chaque feuille pertinente (Actif/Passif/Bilan/Compte de résultat) :
   - Scanner toutes les cellules
   - Identifier les cellules contenant un **code Cerfa** (2 lettres A-Z)
   - Pour chaque code : trouver la valeur numérique "Net exercice N" dans
     la même ligne (heuristique : dernière valeur numérique de la ligne)
3. Mapper les codes Cerfa aux champs YearAccounts via `cerfa_codes.py`.
4. Agréger (plusieurs codes → même champ ex: AB+AD+AF+AH+AJ = immo incorporelles).
"""

from __future__ import annotations

import logging
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from core.pappers.analytics import YearAccounts
from core.pappers.cerfa_codes import (
    BILAN_ACTIF,
    BILAN_PASSIF,
    COMPTE_RESULTAT_CHARGES,
    CR_PRODUITS,
    get_mapping_for_sheet,
    is_valid_cerfa_code,
)

log = logging.getLogger(__name__)

_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


# ==============================================================================
# Lecture XLSX bas niveau
# ==============================================================================

def _col_letter_to_index(letter: str) -> int:
    idx = 0
    for ch in letter:
        idx = idx * 26 + (ord(ch.upper()) - ord("A") + 1)
    return idx - 1


def _parse_cell_ref(ref: str) -> tuple[int, int]:
    i = 0
    while i < len(ref) and ref[i].isalpha():
        i += 1
    col = _col_letter_to_index(ref[:i])
    row = int(ref[i:]) - 1
    return row, col


def _load_shared_strings(z: zipfile.ZipFile) -> list[str]:
    try:
        with z.open("xl/sharedStrings.xml") as f:
            tree = ET.parse(f)
    except KeyError:
        return []
    result: list[str] = []
    for si in tree.getroot().findall("main:si", _NS):
        t = si.find("main:t", _NS)
        if t is not None and t.text:
            result.append(t.text)
        else:
            parts = [
                r.find("main:t", _NS).text or ""
                for r in si.findall("main:r", _NS)
                if r.find("main:t", _NS) is not None
            ]
            result.append("".join(parts))
    return result


def _sheet_paths(z: zipfile.ZipFile) -> dict[str, str]:
    mapping: dict[str, str] = {}
    try:
        with z.open("xl/workbook.xml") as f:
            wb = ET.parse(f).getroot()
    except KeyError:
        return mapping
    rels: dict[str, str] = {}
    try:
        with z.open("xl/_rels/workbook.xml.rels") as f:
            rtree = ET.parse(f).getroot()
            for rel in rtree:
                rid = rel.attrib.get("Id")
                target = rel.attrib.get("Target", "")
                if rid and target:
                    rels[rid] = (
                        f"xl/{target}" if not target.startswith("/") else target.lstrip("/")
                    )
    except KeyError:
        pass
    sheets_node = wb.find("main:sheets", _NS)
    if sheets_node is None:
        return mapping
    for sheet in sheets_node.findall("main:sheet", _NS):
        name = sheet.attrib.get("name", "")
        rid = sheet.attrib.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        if rid and rid in rels:
            mapping[name] = rels[rid]
    return mapping


def _read_sheet_cells(
    z: zipfile.ZipFile, sheet_path: str, shared: list[str]
) -> dict[tuple[int, int], Any]:
    cells: dict[tuple[int, int], Any] = {}
    try:
        with z.open(sheet_path) as f:
            tree = ET.parse(f)
    except KeyError:
        return cells
    sheet_data = tree.getroot().find("main:sheetData", _NS)
    if sheet_data is None:
        return cells
    for row in sheet_data.findall("main:row", _NS):
        for c in row.findall("main:c", _NS):
            ref = c.attrib.get("r")
            if not ref:
                continue
            t = c.attrib.get("t", "")
            v = c.find("main:v", _NS)
            raw = v.text if v is not None else None
            if raw is None:
                continue
            try:
                r, col = _parse_cell_ref(ref)
            except Exception:
                continue
            if t == "s":
                try:
                    cells[(r, col)] = shared[int(raw)]
                except (IndexError, ValueError):
                    cells[(r, col)] = raw
            elif t == "b":
                cells[(r, col)] = bool(int(raw))
            elif t in ("str", "inlineStr"):
                cells[(r, col)] = raw
            else:
                try:
                    cells[(r, col)] = float(raw)
                except ValueError:
                    cells[(r, col)] = raw
    return cells


# ==============================================================================
# Détection année de clôture
# ==============================================================================

def _detect_year(
    cells_by_sheet: dict[str, dict[tuple[int, int], Any]],
    fallback: int | None = None,
) -> int:
    """Cherche un motif 'clos le 31/12/20XX' ou 'Exercice clos le ... 20XX'
    dans les premières lignes de chaque feuille."""
    for sheet_cells in cells_by_sheet.values():
        for (r, _), val in sheet_cells.items():
            if r > 10 or not isinstance(val, str):
                continue
            if "clos" in val.lower() or "exercice" in val.lower():
                m = re.search(r"20(\d{2})", val)
                if m:
                    return 2000 + int(m.group(1))
    return fallback or 2024


# ==============================================================================
# Heuristique : trouver la valeur "Net Exercice N" associée à un code Cerfa
# ==============================================================================

def _find_value_for_code(
    cells: dict[tuple[int, int], Any],
    row: int,
    code_col: int,
    is_bilan: bool,
) -> float | None:
    """Trouve la valeur numérique pertinente sur la même ligne qu'un code Cerfa.

    Pour le bilan (2050-2051) : le code est suivi de "Brut" / "Amort." / "Net".
    On cherche la valeur "Net exercice N" qui est typiquement la **dernière
    valeur numérique strictement positive** de la ligne (avant la colonne
    "Net exercice N-1").

    Pour le compte de résultat (2052-2053) : valeurs "Exercice N" et "Exercice N-1"
    côte à côte. On prend la première valeur numérique après le code.

    Stratégie robuste (marche pour les 2 cas) :
      1. Récupère toutes les valeurs numériques non-nulles de la ligne à
         partir de la colonne suivante du code.
      2. Si bilan : prend la valeur MAX (généralement la Net qui est >= Brut
         - Amort, ou Net > Amort).
      3. Si compte résultat : prend la PREMIÈRE valeur numérique non-nulle.
    """
    values: list[tuple[int, float]] = []
    for (r, c), v in cells.items():
        if r == row and c > code_col and isinstance(v, (int, float)):
            if abs(v) > 0.01:  # ignore zéros parasites
                values.append((c, float(v)))
    if not values:
        return None

    values.sort(key=lambda p: p[0])  # trier par colonne croissante

    if is_bilan:
        # Dernier cluster de valeurs = Exercice N. Dans un bilan on a souvent
        # [Brut, Amort, Net(ExN), Net(Ex N-1)]. La valeur "Net Ex N" est
        # généralement l'avant-dernière (si N-1 présent) ou la dernière.
        # Heuristique : si 3+ valeurs, on prend la 3ème (indice 2).
        # Si 2 valeurs, la 1ère est probablement Ex N, la 2e Ex N-1.
        if len(values) >= 3:
            return values[2][1]  # position 3 = Net Ex N typique
        return values[0][1]

    # Compte de résultat : la valeur Ex N est typiquement la 1ère après le code
    return values[0][1]


# ==============================================================================
# Extraction
# ==============================================================================

# Champs "aggrégés" : plusieurs codes Cerfa → même champ. On ADDITIONNE.
_AGGREGATE_FIELDS = {
    # Champs pour lesquels plusieurs lignes de Cerfa contribuent vraiment à
    # l'agrégat (ex: "reserves" = réserve légale + statutaire + réglementée + autres).
    "immobilisations_incorporelles",   # AB + AD + AF + AH + AJ + AL
    "immobilisations_corporelles",     # AN + AP + AR + AT + AV + AX
    "immobilisations_financieres",     # CS + CU + BB + BD + BF + BH
    "stocks",                          # BL + BN + BP + BR + BT
    "autres_creances",                 # BZ + CB + CH + BV
    "disponibilites",                  # CD + CF
    "reserves",                        # DD + DE + DF + DG + DH
    "dettes_financieres",              # DU + DV + DW + DX
    "provisions_risques",              # DR + DS
    "autres_dettes",                   # DY + EB + EC + ED
    "produits_financiers",             # GA + GB + GC + GD + GE + GF
    "produits_exceptionnels",          # HA + HB + HC
    "charges_exceptionnelles",         # HE + HF + HG
    "capital_social",                  # DA + DB + DC (primes)
}


def _extract_from_sheet(
    sheet_name: str,
    cells: dict[tuple[int, int], Any],
) -> dict[str, float]:
    """Extrait les lignes PCG d'une feuille via les codes Cerfa.

    Pour le compte de résultat (charges ET produits sur la même feuille Pappers),
    on track la section courante via un balayage ligne par ligne :
      "PRODUITS D'EXPLOITATION" → section = produits (CR_PRODUITS)
      "CHARGES D'EXPLOITATION"  → section = charges (COMPTE_RESULTAT_CHARGES)
      "RÉSULTAT FINANCIER"      → section neutre (codes GG/GT peu ambigus)
      etc.
    """
    is_bilan = (
        "actif" in sheet_name.lower()
        or "passif" in sheet_name.lower()
        or "bilan" in sheet_name.lower()
    )
    is_cr = (
        ("compte" in sheet_name.lower() and "r" in sheet_name.lower())
        or "resultat" in sheet_name.lower()
        or "résultat" in sheet_name.lower()
    )

    # Pour le bilan : mapping fixe
    if is_bilan:
        mapping = get_mapping_for_sheet(sheet_name)
        return _scan_with_mapping(cells, mapping, is_bilan=True)

    # Pour le compte de résultat : scan par sections
    if is_cr:
        return _scan_compte_resultat(cells)

    # Autres feuilles (Immobilisations, Provisions) → rien à extraire pour l'instant
    return {}


def _scan_with_mapping(
    cells: dict[tuple[int, int], Any],
    mapping: dict[str, str],
    is_bilan: bool,
) -> dict[str, float]:
    """Scan simple avec un mapping fixe."""
    if not mapping:
        return {}
    extracted: dict[str, float] = {}
    for (r, c), val in cells.items():
        if not is_valid_cerfa_code(val):
            continue
        code = val.strip()
        field = mapping.get(code)
        if field is None or field.startswith("_"):
            continue
        value = _find_value_for_code(cells, r, c, is_bilan)
        if value is None:
            continue
        if field in _AGGREGATE_FIELDS:
            extracted[field] = extracted.get(field, 0.0) + value
        else:
            if field not in extracted or abs(value) > abs(extracted[field]):
                extracted[field] = value
    return extracted


def _scan_compte_resultat(cells: dict[tuple[int, int], Any]) -> dict[str, float]:
    """Scan la feuille Compte de résultat en distinguant produits vs charges
    selon la section courante (lue dans col A ou col G)."""
    extracted: dict[str, float] = {}
    section: str = "unknown"  # "produits_expl" | "charges_expl" | "fi_produits" | "fi_charges" | "exc_produits" | "exc_charges" | "impots"

    # Rassemble les lignes triées par numéro
    rows_with_cells: dict[int, list[tuple[int, Any]]] = {}
    for (r, c), v in cells.items():
        rows_with_cells.setdefault(r, []).append((c, v))

    sorted_rows = sorted(rows_with_cells.keys())

    for row_idx in sorted_rows:
        row_cells = dict(rows_with_cells[row_idx])

        # Détection section : cherche un texte en col A ou G qui annonce une section
        for col_text in [0, 6]:  # A et G
            txt = row_cells.get(col_text)
            if not isinstance(txt, str):
                continue
            upper = txt.upper()
            if "PRODUITS D'EXPL" in upper or "PRODUITS D EXPL" in upper:
                section = "produits_expl"
            elif "CHARGES D'EXPL" in upper or "CHARGES D EXPL" in upper:
                section = "charges_expl"
            elif "PRODUITS FINAN" in upper:
                section = "fi_produits"
            elif "CHARGES FINAN" in upper:
                section = "fi_charges"
            elif "PRODUITS EXCEP" in upper:
                section = "exc_produits"
            elif "CHARGES EXCEP" in upper:
                section = "exc_charges"
            elif "PARTICIPATION" in upper or "IMPOTS SUR" in upper or "IMP�TS SUR" in upper:
                section = "impots"

        # Scan les codes Cerfa de cette ligne
        for col, val in row_cells.items():
            if not is_valid_cerfa_code(val):
                continue
            code = val.strip()

            # Choix du mapping selon la section
            if section == "produits_expl" or section == "fi_produits" or section == "exc_produits":
                mapping = CR_PRODUITS
            elif section in ("charges_expl", "fi_charges", "exc_charges", "impots"):
                mapping = COMPTE_RESULTAT_CHARGES
            else:
                # Section inconnue : tente produits en priorité (lignes du début)
                mapping = {**CR_PRODUITS, **COMPTE_RESULTAT_CHARGES}

            field = mapping.get(code)
            if field is None or field.startswith("_"):
                continue
            value = _find_value_for_code(cells, row_idx, col, is_bilan=False)
            if value is None:
                continue
            if field in _AGGREGATE_FIELDS:
                extracted[field] = extracted.get(field, 0.0) + value
            else:
                if field not in extracted or abs(value) > abs(extracted[field]):
                    extracted[field] = value

    return extracted


def _count_numeric_cells(cells: dict[tuple[int, int], Any]) -> int:
    return sum(
        1
        for v in cells.values()
        if isinstance(v, (int, float)) and abs(v) > 0.01
    )


# ==============================================================================
# Parser principal
# ==============================================================================

def parse_pappers_xlsx(
    xlsx_path: str | Path,
    annee_cloture: int | None = None,
) -> YearAccounts | None:
    """Parse un XLSX Pappers → YearAccounts.

    Retourne None si :
      - fichier invalide
      - comptes confidentiels (aucune valeur numérique dans les feuilles Cerfa)
    """
    xlsx_path = Path(xlsx_path)
    if not xlsx_path.exists():
        raise FileNotFoundError(xlsx_path)

    try:
        with zipfile.ZipFile(xlsx_path) as z:
            shared = _load_shared_strings(z)
            sheets_by_name = _sheet_paths(z)

            # Lit toutes les feuilles utiles
            relevant: dict[str, dict[tuple[int, int], Any]] = {}
            for name, path in sheets_by_name.items():
                lname = name.lower()
                if any(
                    k in lname
                    for k in ["bilan", "actif", "passif", "résultat", "resultat", "compte"]
                ):
                    cells = _read_sheet_cells(z, path, shared)
                    if cells:
                        relevant[name] = cells
    except zipfile.BadZipFile:
        log.error("[pappers_xlsx] fichier non-XLSX: %s", xlsx_path)
        return None

    if not relevant:
        log.warning("[pappers_xlsx] aucune feuille Cerfa trouvée")
        return None

    # Check : est-ce que les feuilles ont des valeurs numériques ?
    total_numeric = sum(_count_numeric_cells(c) for c in relevant.values())
    if total_numeric < 10:
        log.warning(
            "[pappers_xlsx] comptes confidentiels ou vides (%d valeurs num.)",
            total_numeric,
        )
        return None

    # Année de clôture
    year = _detect_year(relevant, annee_cloture)

    # Extraction par feuille
    all_extracted: dict[str, float] = {}
    for sheet_name, cells in relevant.items():
        extracted = _extract_from_sheet(sheet_name, cells)
        for field, value in extracted.items():
            if field in _AGGREGATE_FIELDS:
                all_extracted[field] = all_extracted.get(field, 0.0) + value
            elif field not in all_extracted or abs(value) > abs(all_extracted[field]):
                all_extracted[field] = value

    if not all_extracted:
        return None

    return YearAccounts(annee=year, **all_extracted)


# ==============================================================================
# Downloader
# ==============================================================================

def download_pappers_xlsx(
    token_xlsx: str,
    api_key: str,
    output_path: str | Path,
    timeout: int = 30,
) -> Path:
    """Télécharge un XLSX Pappers via son token."""
    import requests

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(
        "https://api.pappers.fr/v2/document/telechargement",
        params={"api_token": api_key, "token": token_xlsx},
        timeout=timeout,
    )
    if r.status_code != 200:
        raise RuntimeError(
            f"Pappers download failed: HTTP {r.status_code} — {r.text[:200]}"
        )
    if "spreadsheet" not in r.headers.get("content-type", ""):
        raise RuntimeError(
            f"Pappers returned non-XLSX: {r.headers.get('content-type')}"
        )
    output_path.write_bytes(r.content)
    return output_path
