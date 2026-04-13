# -*- coding: utf-8 -*-
"""
Refactor : renomme les writers comparison_* / indice_comparison_* vers
cmp_societe_* / cmp_indice_* pour adopter la convention deja utilisee par
cmp_secteur_*.

Etapes :
1. Renomme les classes (ComparisonWriter -> CmpSocieteXlsxWriter, etc.)
2. Renomme les imports (from outputs.comparison_X -> from outputs.cmp_societe_X)
3. Les fichiers eux-memes sont renommes via git mv (script bash separe).

Usage : python tools/rename_writers.py
"""
from __future__ import annotations

import re
import sys
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ============================================================================
# Tables de renommage
# ============================================================================

# Classes (ordre : longest first pour eviter les collisions de prefixes)
CLASS_RENAMES = [
    ("IndiceComparisonPPTXWriter", "CmpIndicePPTXWriter"),
    ("IndiceComparisonPDFWriter",  "CmpIndicePDFWriter"),
    ("IndiceComparisonWriter",     "CmpIndiceXlsxWriter"),
    ("ComparisonPPTXWriter",       "CmpSocietePPTXWriter"),
    ("ComparisonPDFWriter",        "CmpSocietePDFWriter"),
    ("ComparisonWriter",           "CmpSocieteXlsxWriter"),
]

# Imports / module paths (longest first)
IMPORT_RENAMES = [
    ("outputs.indice_comparison_pptx_writer", "outputs.cmp_indice_pptx_writer"),
    ("outputs.indice_comparison_pdf_writer",  "outputs.cmp_indice_pdf_writer"),
    ("outputs.indice_comparison_writer",      "outputs.cmp_indice_xlsx_writer"),
    ("outputs.comparison_pptx_writer",        "outputs.cmp_societe_pptx_writer"),
    ("outputs.comparison_pdf_writer",         "outputs.cmp_societe_pdf_writer"),
    ("outputs.comparison_writer",             "outputs.cmp_societe_xlsx_writer"),
]


def rename_in_file(path: Path) -> tuple[int, int]:
    """Applique les renames a un fichier. Retourne (n_keys_renamed, n_total_replacements)."""
    if not path.exists():
        return 0, 0
    src = path.read_text(encoding="utf-8")
    new_src = src
    n_keys = 0
    n_total = 0

    # 1. Imports / module paths (litteraux, sans word boundary car contient des points)
    for old, new in IMPORT_RENAMES:
        cnt = new_src.count(old)
        if cnt > 0:
            new_src = new_src.replace(old, new)
            n_keys += 1
            n_total += cnt
            print(f"  IMPORT {old!s:42s} -> {new!s:38s} {cnt:>3} occurrences")

    # 2. Classes (avec word boundary)
    for old, new in CLASS_RENAMES:
        pattern = r'\b' + re.escape(old) + r'\b'
        cnt = len(re.findall(pattern, new_src))
        if cnt > 0:
            new_src = re.sub(pattern, new, new_src)
            n_keys += 1
            n_total += cnt
            print(f"  CLASS  {old!s:42s} -> {new!s:38s} {cnt:>3} occurrences")

    if new_src != src:
        path.write_text(new_src, encoding="utf-8")
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
        ROOT / "outputs" / "cmp_societe_xlsx_writer.py",   # apres git mv
        ROOT / "outputs" / "cmp_societe_pdf_writer.py",
        ROOT / "outputs" / "cmp_societe_pptx_writer.py",
        ROOT / "outputs" / "cmp_indice_xlsx_writer.py",
        ROOT / "outputs" / "cmp_indice_pdf_writer.py",
        ROOT / "outputs" / "cmp_indice_pptx_writer.py",
        ROOT / "tools" / "audit_comparison.py",
        ROOT / "tools" / "audit_indice_cmp.py",
        ROOT / "tools" / "investigate_data_chain.py",
        ROOT / "tools" / "investigate_verdict.py",
    ]
    print("=" * 78)
    print("  RENAME WRITERS / IMPORTS / CLASSES  -  cmp_societe + cmp_indice")
    print("=" * 78)
    grand_total = 0
    for path in targets:
        print(f"\n>>> {path.relative_to(ROOT)}")
        if not path.exists():
            print("  [SKIP] not found (peut-etre pas encore git mv)")
            continue
        keys, total = rename_in_file(path)
        if total > 0:
            grand_total += total
            print(f"  {keys} type(s), {total} remplacement(s)")
        else:
            print("  (rien a renommer)")
    print("=" * 78)
    print(f"  DONE — {grand_total} remplacement(s) total")
    print("=" * 78)


if __name__ == "__main__":
    main()
