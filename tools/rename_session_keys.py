# -*- coding: utf-8 -*-
"""
Refactor : renomme toutes les session_state keys cmp_/scmp_/icmp_ pour adopter
une convention coherente cmp_societe_/cmp_secteur_/cmp_indice_.

Usage : python tools/rename_session_keys.py

Fait les remplacements en place dans app.py et verifie le syntax apres.
Ne touche pas aux noms de classes, modules, ni variables locales internes
aux writers (qui sont isoles).
"""
from __future__ import annotations

import re
import sys
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ============================================================================
# Tables de renommage — une seule entree par cle exacte
# ============================================================================

# Group A : cmp_* (societe)
CMP_SOCIETE = {
    "cmp_stage":         "cmp_societe_stage",
    "cmp_kind":          "comparison_kind",
    "cmp_ticker_b":      "cmp_societe_ticker_b",
    "cmp_ticker_input":  "cmp_societe_ticker_input",
    "cmp_state_b":       "cmp_societe_state_b",
    "cmp_bytes":         "cmp_societe_xlsx_bytes",
    "cmp_pdf_bytes":     "cmp_societe_pdf_bytes",
    "cmp_pptx_bytes":    "cmp_societe_pptx_bytes",
    "cmp_synthesis":     "cmp_societe_synthesis",
}

# Group B : scmp_* (secteur)
CMP_SECTEUR = {
    "scmp_stage":         "cmp_secteur_stage",
    "scmp_sector_a":      "cmp_secteur_sector_a",
    "scmp_sector_b":      "cmp_secteur_sector_b",
    "scmp_sector_b_sel":  "cmp_secteur_sector_b_sel",
    "scmp_sector_a_isec": "cmp_secteur_sector_a_isec",
    "scmp_pptx_bytes":    "cmp_secteur_pptx_bytes",
    "scmp_pdf_bytes":     "cmp_secteur_pdf_bytes",
    "scmp_xlsx_bytes":    "cmp_secteur_xlsx_bytes",
    "scmp_tickers_a":     "cmp_secteur_tickers_a",
    "scmp_tickers_b":     "cmp_secteur_tickers_b",
    "scmp_universe_b":    "cmp_secteur_universe_b",
    "scmp_cmp_data":      "cmp_secteur_data",
    "scmp_run":           "cmp_secteur_run",
    "scmp_reset":         "cmp_secteur_reset",
}

# Group C : icmp_* (indice)
CMP_INDICE = {
    "icmp_stage":         "cmp_indice_stage",
    "icmp_universe_a":    "cmp_indice_universe_a",
    "icmp_universe_b":    "cmp_indice_universe_b",
    "icmp_pptx_bytes":    "cmp_indice_pptx_bytes",
    "icmp_pdf_bytes":     "cmp_indice_pdf_bytes",
    "icmp_xlsx_bytes":    "cmp_indice_xlsx_bytes",
    "icmp_cmp_data":      "cmp_indice_data",
    "icmp_reset":         "cmp_indice_reset",
    "icmp_btn":           "cmp_indice_btn",
    "icmp_sel_b":         "cmp_indice_sel_b",
}

# Ordre d'application : longest first pour eviter les substring conflicts
ALL_RENAMES = []
for d in (CMP_SOCIETE, CMP_SECTEUR, CMP_INDICE):
    for old, new in d.items():
        ALL_RENAMES.append((old, new))
# Tri par longueur decroissante de la cle source
ALL_RENAMES.sort(key=lambda x: -len(x[0]))


def rename_in_file(path: Path) -> tuple[int, int]:
    """Applique les renames a un fichier. Retourne (n_keys_renamed, n_total_replacements)."""
    if not path.exists():
        return 0, 0
    src = path.read_text(encoding="utf-8")
    new_src = src
    n_keys = 0
    n_total = 0
    for old, new in ALL_RENAMES:
        # Word boundary regex : evite de matcher dans des sous-strings
        # comme "scmp_b" -> "cmp_secteur_b" si la cle est "scmp_". On ne match
        # que des mots complets (precede et suivi par non-[a-zA-Z0-9_])
        pattern = r'\b' + re.escape(old) + r'\b'
        cnt = len(re.findall(pattern, new_src))
        if cnt > 0:
            new_src = re.sub(pattern, new, new_src)
            n_keys += 1
            n_total += cnt
            print(f"  {old!s:30s} -> {new!s:35s} {cnt:>4} occurrences")
    if new_src != src:
        path.write_text(new_src, encoding="utf-8")
        # Verif syntax
        try:
            py_compile.compile(str(path), doraise=True)
            print(f"  [OK syntax] {path.name}")
        except py_compile.PyCompileError as e:
            print(f"  [FAIL syntax] {path.name}: {e.msg}")
            sys.exit(1)
    return n_keys, n_total


def main():
    targets = [
        ROOT / "app.py",
    ]
    print("=" * 72)
    print("  RENAME SESSION_STATE KEYS  -  unification cmp_societe/secteur/indice")
    print("=" * 72)
    for path in targets:
        print(f"\n>>> {path.name}")
        if not path.exists():
            print("  [SKIP] not found")
            continue
        keys, total = rename_in_file(path)
        print(f"  {keys} cle(s) renommee(s), {total} remplacement(s) total")
    print("=" * 72)
    print("  DONE")
    print("=" * 72)


if __name__ == "__main__":
    main()
