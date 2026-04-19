"""Parser XLSX déterministe pour comptes uploadés par l'user.

Stratégie :
1. Lit toutes les feuilles via parsing XML brut (évite bug openpyxl Python 3.14
   sur certains styles personnalisés).
2. Détecte le type de tableau (compte de résultat / bilan) via mots-clefs
   dans col A et 1ères lignes.
3. Pour chaque ligne avec un libellé reconnu (ex "Chiffre d'affaires"),
   extrait la valeur numérique de la ligne.

Si aucun libellé connu détecté → renvoie type "autre" et signale au caller
qu'il faut fallback vers Gemini Vision (qui sait lire des formats libres).
"""

from __future__ import annotations

import logging
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from typing import Any

log = logging.getLogger(__name__)

_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


# ─── Mapping libellés FR → champs normalisés ──────────────────────────────────

# Libellés normalisés (sans accents, lowercase, espaces multiples → 1)
_CR_MAPPING = {
    # Produits
    "chiffre d affaires": "chiffre_affaires",
    "chiffre d affaires net": "chiffre_affaires",
    "ca": "chiffre_affaires",
    "ventes de marchandises": "production_vendue_biens",
    "production vendue biens": "production_vendue_biens",
    "production vendue services": "production_vendue_services",
    "prestations de services": "production_vendue_services",
    # Charges
    "achats de marchandises": "achats_marchandises",
    "achats matieres premieres": "achats_matieres_premieres",
    "achats de matieres premieres": "achats_matieres_premieres",
    "autres achats et charges externes": "autres_achats_charges_externes",
    "autres achats charges externes": "autres_achats_charges_externes",
    "impots taxes et versements assimiles": "impots_taxes",
    "impots et taxes": "impots_taxes",
    "salaires et traitements": "salaires_traitements",
    "charges sociales": "charges_sociales",
    "dotations aux amortissements": "dotations_amortissements",
    "dotations amortissements": "dotations_amortissements",
    # Soldes
    "excedent brut d exploitation": "ebe_estime",
    "ebe": "ebe_estime",
    "ebitda": "ebe_estime",
    "resultat d exploitation": "resultat_exploitation",
    "resultat exploitation": "resultat_exploitation",
    "resultat financier": "resultat_financier",
    "resultat courant avant impots": "resultat_courant",
    "resultat courant": "resultat_courant",
    "resultat exceptionnel": "resultat_exceptionnel",
    "impots sur les benefices": "impots_benefices",
    "impot sur les societes": "impots_benefices",
    "is": "impots_benefices",
    "resultat net": "resultat_net",
    "resultat de l exercice": "resultat_net",
    "benefice net": "resultat_net",
}

_BILAN_MAPPING = {
    # Actif
    "actif immobilise": "actif_immobilise",
    "immobilisations incorporelles": "immobilisations_incorporelles",
    "immobilisations corporelles": "immobilisations_corporelles",
    "immobilisations financieres": "immobilisations_financieres",
    "actif circulant": "actif_circulant",
    "stocks": "stocks",
    "creances clients": "creances_clients",
    "creances clients et comptes rattaches": "creances_clients",
    "autres creances": "autres_creances",
    "disponibilites": "disponibilites",
    "tresorerie": "disponibilites",
    "total actif": "total_actif",
    # Passif
    "capitaux propres": "capitaux_propres",
    "capital social": "capital_social",
    "capital": "capital_social",
    "reserves": "reserves",
    "resultat de l exercice": "resultat_exercice",
    "resultat exercice": "resultat_exercice",
    "provisions pour risques et charges": "provisions_risques",
    "provisions risques": "provisions_risques",
    "dettes financieres": "dettes_financieres",
    "emprunts": "dettes_financieres",
    "dettes fournisseurs": "dettes_fournisseurs",
    "dettes fournisseurs et comptes rattaches": "dettes_fournisseurs",
    "dettes fiscales et sociales": "dettes_fiscales_sociales",
    "autres dettes": "autres_dettes",
    "total passif": "total_passif",
}

# Mots-clefs pour détection rapide du type
_CR_KEYWORDS = {"chiffre d affaires", "resultat net", "resultat d exploitation", "ebe", "ebitda"}
_BILAN_KEYWORDS = {"actif", "passif", "capitaux propres", "total actif", "total passif"}


def _norm(s: str) -> str:
    """Normalise un libellé : lowercase, sans accents, espaces simples."""
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().replace("'", " ")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ─── Lecture XLSX bas niveau (XML brut) ───────────────────────────────────────

def _load_shared_strings(z: zipfile.ZipFile) -> list[str]:
    try:
        with z.open("xl/sharedStrings.xml") as f:
            tree = ET.parse(f)
    except KeyError:
        return []
    out: list[str] = []
    for si in tree.getroot().findall("main:si", _NS):
        t = si.find("main:t", _NS)
        if t is not None and t.text:
            out.append(t.text)
        else:
            parts = []
            for r in si.findall("main:r", _NS):
                tt = r.find("main:t", _NS)
                if tt is not None and tt.text:
                    parts.append(tt.text)
            out.append("".join(parts))
    return out


def _sheet_paths(z: zipfile.ZipFile) -> list[str]:
    try:
        with z.open("xl/workbook.xml") as f:
            wb = ET.parse(f).getroot()
        with z.open("xl/_rels/workbook.xml.rels") as f:
            rels_root = ET.parse(f).getroot()
    except KeyError:
        return []
    rels = {r.attrib.get("Id"): r.attrib.get("Target", "") for r in rels_root}
    paths = []
    sheets_node = wb.find("main:sheets", _NS)
    if sheets_node is None:
        return paths
    for s in sheets_node.findall("main:sheet", _NS):
        rid = s.attrib.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        if rid and rid in rels:
            target = rels[rid]
            paths.append(f"xl/{target}" if not target.startswith("/") else target.lstrip("/"))
    return paths


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


def _read_sheet(
    z: zipfile.ZipFile, path: str, shared: list[str]
) -> dict[tuple[int, int], Any]:
    cells: dict[tuple[int, int], Any] = {}
    try:
        with z.open(path) as f:
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
            elif t in ("str", "inlineStr"):
                cells[(r, col)] = raw
            elif t == "b":
                cells[(r, col)] = bool(int(raw))
            else:
                try:
                    cells[(r, col)] = float(raw)
                except ValueError:
                    cells[(r, col)] = raw
    return cells


# ─── Détection type + extraction ──────────────────────────────────────────────

def _detect_table_type(cells: dict[tuple[int, int], Any]) -> str:
    """Compte hits CR vs Bilan pour deviner le type."""
    cr_hits = 0
    bilan_hits = 0
    for v in cells.values():
        if not isinstance(v, str):
            continue
        n = _norm(v)
        if any(k in n for k in _CR_KEYWORDS):
            cr_hits += 1
        if any(k in n for k in _BILAN_KEYWORDS):
            bilan_hits += 1
    if cr_hits == 0 and bilan_hits == 0:
        return "autre"
    return "compte_resultat" if cr_hits >= bilan_hits else "bilan"


def _extract_year(cells: dict[tuple[int, int], Any]) -> int | None:
    """Cherche une année 20XX dans les premières lignes/colonnes."""
    for (r, _), v in cells.items():
        if r > 15:
            continue
        if isinstance(v, (int, float)) and 2000 <= v <= 2100:
            return int(v)
        if isinstance(v, str):
            m = re.search(r"20(\d{2})", v)
            if m:
                return 2000 + int(m.group(1))
    return None


def _extract_values_for_mapping(
    cells: dict[tuple[int, int], Any], mapping: dict[str, str]
) -> dict[str, float]:
    """Pour chaque ligne, vérifie si col A contient un libellé connu → prend
    la dernière valeur numérique de la ligne (typiquement la plus récente).
    """
    rows: dict[int, list[tuple[int, Any]]] = {}
    for (r, c), v in cells.items():
        rows.setdefault(r, []).append((c, v))

    out: dict[str, float] = {}
    for row_idx, row_cells in rows.items():
        # libellé = première cellule string non vide, qu'elle soit en col 0 ou ailleurs
        labels = [v for _, v in sorted(row_cells) if isinstance(v, str) and v.strip()]
        if not labels:
            continue
        label_norm = _norm(labels[0])
        if label_norm not in mapping:
            # essaye aussi labels[1] (parfois col A vide, libellé en col B)
            if len(labels) > 1 and _norm(labels[1]) in mapping:
                label_norm = _norm(labels[1])
            else:
                continue
        field = mapping[label_norm]
        # valeurs numériques de la ligne, triées par colonne
        nums = sorted(
            [(c, float(v)) for c, v in row_cells if isinstance(v, (int, float))],
            key=lambda p: p[0],
        )
        if not nums:
            continue
        # prends la dernière valeur numérique non nulle (= année la plus récente
        # dans un layout standard)
        last_val = next((v for _, v in reversed(nums) if abs(v) > 0.01), None)
        if last_val is None:
            continue
        # ne pas écraser une valeur déjà extraite avec quelque chose de plus petit
        if field not in out or abs(last_val) > abs(out[field]):
            out[field] = abs(last_val)  # toujours positif
    return out


def parse_xlsx_document(file_bytes: bytes) -> dict[str, Any]:
    """Parse un XLSX uploadé → dict normalisé compatible avec ExtractionResult.

    Renvoie au minimum {"type": "compte_resultat"|"bilan"|"autre", ...}.
    Si "autre" : signale qu'on ne reconnaît pas, le caller peut fallback Gemini.
    """
    bio = BytesIO(file_bytes)
    try:
        with zipfile.ZipFile(bio) as z:
            shared = _load_shared_strings(z)
            sheets = _sheet_paths(z)
            # Lit toutes les feuilles, prend celle qui a le plus de hits
            best_cells: dict[tuple[int, int], Any] = {}
            best_type = "autre"
            best_hits = 0
            for path in sheets:
                cells = _read_sheet(z, path, shared)
                if not cells:
                    continue
                t = _detect_table_type(cells)
                hits = sum(
                    1
                    for v in cells.values()
                    if isinstance(v, str)
                    and (
                        any(k in _norm(v) for k in _CR_KEYWORDS)
                        or any(k in _norm(v) for k in _BILAN_KEYWORDS)
                    )
                )
                if hits > best_hits:
                    best_hits = hits
                    best_cells = cells
                    best_type = t
    except zipfile.BadZipFile:
        return {"type": "autre", "_confidence": 0.0, "remarques": "fichier XLSX invalide"}

    if best_type == "autre" or not best_cells:
        return {
            "type": "autre",
            "_confidence": 0.0,
            "remarques": "aucun libellé comptable reconnu — fallback LLM recommandé",
        }

    mapping = _CR_MAPPING if best_type == "compte_resultat" else _BILAN_MAPPING
    extracted = _extract_values_for_mapping(best_cells, mapping)
    year = _extract_year(best_cells)

    out: dict[str, Any] = {
        "type": best_type,
        "annee": year,
        "devise": "EUR",
        "unite": "1",
        "_confidence": 0.85 if extracted else 0.3,
        **extracted,
    }
    if not extracted:
        out["remarques"] = "feuille reconnue mais aucune valeur extraite"
    return out
