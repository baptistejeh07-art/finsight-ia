# -*- coding: utf-8 -*-
"""
Fix les identifiants Python brisés par restore_accents.py et les clés de dict
qui ne matchent plus AgentMacro depuis qu'il a été nettoyé.

Usage : python tools/fix_broken_identifiers.py
"""
import re
import sys
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Remplacements (longest-first pour éviter les substring conflicts)
RENAMES = [
    # Clés dict AgentMacro (cassées par restore_accents)
    ('"récession_prob_12m"',  '"recession_prob_12m"'),
    ('"récession_prob_6m"',   '"recession_prob_6m"'),
    ('"récession_drivers"',   '"recession_drivers"'),
    ('"récession_level"',     '"recession_level"'),
    ("'récession_prob_12m'",  "'recession_prob_12m'"),
    ("'récession_prob_6m'",   "'recession_prob_6m'"),
    ("'récession_drivers'",   "'recession_drivers'"),
    ("'récession_level'",     "'recession_level'"),
    ('"régime_v"',            '"regime"'),
    ("'régime_v'",            "'regime'"),

    # Variables Python brisées (causent NameError au runtime)
    ('peer_Médian_ev_e',      'peer_median_ev_e'),
    ('_régime_var_lbl',       '_regime_lbl'),
    ('_régime_var',           '_regime'),
    ('régime_v',              'regime_v'),  # nettoie l'identifier (pas dict key)
    ('_complément',           '_complement'),
    ('_défensif',             '_defensif'),
    ('_miss_conséquence',     '_miss_consequence'),
    ('_prime_décote_str',     '_prime_decote_str'),
    ('décote_val',            'decote_val'),
    ('nb_surp_réel',          'nb_surp_reel'),
]

TARGETS = [
    ROOT / "app.py",
    ROOT / "outputs" / "indice_pdf_writer.py",
    ROOT / "outputs" / "indice_pptx_writer.py",
    ROOT / "outputs" / "indice_excel_writer.py",
    ROOT / "outputs" / "pptx_writer.py",
    ROOT / "outputs" / "pdf_writer.py",
    ROOT / "outputs" / "sectoral_pptx_writer.py",
    ROOT / "outputs" / "sector_pdf_writer.py",
    ROOT / "outputs" / "cmp_societe_pdf_writer.py",
    ROOT / "outputs" / "cmp_societe_pptx_writer.py",
    ROOT / "outputs" / "cmp_societe_xlsx_writer.py",
    ROOT / "outputs" / "cmp_secteur_pdf_writer.py",
    ROOT / "outputs" / "cmp_secteur_pptx_writer.py",
    ROOT / "outputs" / "cmp_secteur_xlsx_writer.py",
    ROOT / "outputs" / "cmp_indice_pdf_writer.py",
    ROOT / "outputs" / "cmp_indice_pptx_writer.py",
    ROOT / "outputs" / "cmp_indice_xlsx_writer.py",
    ROOT / "outputs" / "screening_writer.py",
    ROOT / "outputs" / "excel_writer.py",
    ROOT / "outputs" / "briefing.py",
    ROOT / "cli_analyze.py",
]


def fix_file(path: Path) -> tuple[int, int]:
    """Applique les renames a un fichier. Retourne (n_keys, n_total)."""
    if not path.exists():
        return 0, 0
    src = path.read_text(encoding="utf-8")
    new_src = src
    n_keys = 0
    n_total = 0
    for old, new in RENAMES:
        cnt = new_src.count(old)
        if cnt > 0:
            new_src = new_src.replace(old, new)
            n_keys += 1
            n_total += cnt
            print(f"  {old!s:32s} -> {new!s:30s} {cnt:>3}")
    if new_src != src:
        path.write_text(new_src, encoding="utf-8")
        try:
            py_compile.compile(str(path), doraise=True)
            print(f"  [OK syntax] {path.name}")
        except py_compile.PyCompileError as e:
            print(f"  [FAIL] {path.name}: {e.msg}")
            sys.exit(1)
    return n_keys, n_total


def main():
    print("=" * 72)
    print("  FIX BROKEN PYTHON IDENTIFIERS (post restore_accents.py regression)")
    print("=" * 72)
    grand_total = 0
    for path in TARGETS:
        if not path.exists():
            continue
        rel = path.relative_to(ROOT)
        keys, total = fix_file(path)
        if total > 0:
            grand_total += total
            print(f">>> {rel} : {keys} pattern(s), {total} occurrence(s)")
    print("=" * 72)
    print(f"TOTAL : {grand_total} replacement(s)")


if __name__ == "__main__":
    main()
