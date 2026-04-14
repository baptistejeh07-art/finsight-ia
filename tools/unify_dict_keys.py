# -*- coding: utf-8 -*-
"""
Unifie les cles de dict accentuees vers leur equivalent ASCII pour eviter
les bugs silencieux ou une cle est definie avec accent et utilisee sans
(ou inversement).

Liste des renames basee sur l'audit AST : 44 dict-keys brisees identifiees.

Usage : python tools/unify_dict_keys.py
"""
import re
import sys
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Rename cles dict (longest-first pour eviter substring conflicts)
# Format : (string accentuee, string ASCII)
RENAMES = [
    # Doubles guillemets
    ('"defensive_return"',     '"defensive_return"'),  # déjà OK, no-op
    ('"defensif_ret"',         '"defensif_ret"'),
    ('"defensive_return"',     '"defensive_return"'),
    ('"prime_decote"',         '"prime_decote"'),
    ('"nb_societes"',          '"nb_societes"'),
    ('"societes"',             '"societes"'),
    ('"analyst_revision"',     '"analyst_revision"'),
    ('"cmp_societe"',          '"cmp_societe"'),
    ('"decote_dcf"',           '"decote_dcf"'),
    ('"score_societe"',        '"score_societe"'),
    ('"these_a"',              '"these_a"'),
    ('"these_b"',              '"these_b"'),
    ('"these_long_a"',         '"these_long_a"'),
    ('"these_long_b"',         '"these_long_b"'),
    ('"sector_median_pe"',     '"sector_median_pe"'),
    ('"sector_median_pe"',     '"sector_median_pe"'),
    ('"sector_median_ev_ebitda"', '"sector_median_ev_ebitda"'),
    ('"sector_median_ev_ebitda"', '"sector_median_ev_ebitda"'),
    ('"risk_themes_full"',     '"risk_themes_full"'),
    ('"pos_themes_ic"',        '"pos_themes_ic"'),
    ('"pos_themes"',           '"pos_themes"'),
    ('"neg_themes"',           '"neg_themes"'),
    ('"themes_full"',          '"themes_full"'),
    ('"scenarios"',            '"scenarios"'),
    ('"declencheurs"',         '"declencheurs"'),
    ('"economique"',           '"economique"'),
    # Apostrophes simples
    ("'defensive_return'",     "'defensive_return'"),
    ("'defensif_ret'",         "'defensif_ret'"),
    ("'defensive_return'",     "'defensive_return'"),
    ("'prime_decote'",         "'prime_decote'"),
    ("'nb_societes'",          "'nb_societes'"),
    ("'societes'",             "'societes'"),
    ("'analyst_revision'",     "'analyst_revision'"),
    ("'cmp_societe'",          "'cmp_societe'"),
    ("'decote_dcf'",           "'decote_dcf'"),
    ("'score_societe'",        "'score_societe'"),
    ("'these_a'",              "'these_a'"),
    ("'these_b'",              "'these_b'"),
    ("'these_long_a'",         "'these_long_a'"),
    ("'these_long_b'",         "'these_long_b'"),
    ("'sector_median_pe'",     "'sector_median_pe'"),
    ("'sector_median_pe'",     "'sector_median_pe'"),
    ("'sector_median_ev_ebitda'", "'sector_median_ev_ebitda'"),
    ("'sector_median_ev_ebitda'", "'sector_median_ev_ebitda'"),
    ("'risk_themes_full'",     "'risk_themes_full'"),
    ("'pos_themes_ic'",        "'pos_themes_ic'"),
    ("'pos_themes'",           "'pos_themes'"),
    ("'neg_themes'",           "'neg_themes'"),
    ("'themes_full'",          "'themes_full'"),
    ("'scenarios'",            "'scenarios'"),
    ("'declencheurs'",         "'declencheurs'"),
    ("'economique'",           "'economique'"),
]

# Liste des targets : tous les .py du repo (sauf worktrees)
TARGETS_DIRS = [
    ROOT,
]


def main():
    print("=" * 78)
    print("  UNIFY DICT KEYS — accentees -> ASCII")
    print("=" * 78)
    grand_total = 0
    files_touched = 0
    for tgt in TARGETS_DIRS:
        for py_file in tgt.rglob("*.py"):
            if "worktree" in str(py_file) or "__pycache__" in str(py_file):
                continue
            try:
                src = py_file.read_text(encoding="utf-8")
            except Exception:
                continue
            new_src = src
            file_total = 0
            for old, new in RENAMES:
                if old == new:
                    continue
                cnt = new_src.count(old)
                if cnt > 0:
                    new_src = new_src.replace(old, new)
                    file_total += cnt
            if file_total > 0 and new_src != src:
                rel = py_file.relative_to(ROOT)
                py_file.write_text(new_src, encoding="utf-8")
                try:
                    py_compile.compile(str(py_file), doraise=True)
                except py_compile.PyCompileError as e:
                    print(f"  [FAIL syntax] {rel}: {e.msg}")
                    sys.exit(1)
                grand_total += file_total
                files_touched += 1
                print(f"  {rel}: {file_total} replacement(s)")
    print("=" * 78)
    print(f"TOTAL : {grand_total} replacement(s) in {files_touched} file(s)")


if __name__ == "__main__":
    main()
