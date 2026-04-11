# -*- coding: utf-8 -*-
"""
Bug autoinflige par tools/restore_accents.py : il a remplace certains noms
de variables Python (median, genere, etc.) par leur version accentuee
(Median, generee), provoquant des NameError au runtime car les variables
sont declarees sans accent ailleurs.

Ce script repare en restaurant les noms de variables Python a leur forme
ASCII, mais UNIQUEMENT dans les contextes "code" (pas dans les strings).

Strategie : grep des occurrences suspectes d'identifiants accentues et
replacement cible par regex word-boundary.
"""
from __future__ import annotations

import re
import sys
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Mots accentues qui peuvent etre des noms de variables Python.
# Pour chacun, on definit la version ASCII a restaurer.
# La regle : on remplace UNIQUEMENT si le mot est utilise comme identifiant
# (precede/suivi de caracteres d'identifiant Python : letters, digits, _).
IDENTIFIER_FIXES = {
    # median (souvent dans des noms type peer_median_X, calc_median_Y)
    "Médian":   "median",
    "Médiane":  "median",  # rare
    "Médianes": "median",
    # genere/generee/generes (verbe -> souvent dans contextes code)
    # ATTENTION : "genere" en tant que verbe francais devrait rester accentue
    # mais en tant qu'identifiant python (genere_text, _genere_synthesis), non.
    # On laisse le sweep de strings tranquille et on traite que les identifiers.
    "généré":   "genere",
    "Généré":   "Genere",
    "généré_":  "genere_",
    "généré ":  "genere ",  # cas string FR : on laisse
}

# Pour identifier un "contexte d'identifier Python", on detecte si le mot
# accentue est precede ou suivi par un underscore, une lettre ascii, ou un
# chiffre. C'est un heuristique simple mais efficace.
def is_python_identifier_context(line: str, start: int, end: int) -> bool:
    """Retourne True si la position (start:end) dans line est probablement
    un nom de variable Python (suivi/precede par _ ou alphanum)."""
    before = line[start - 1] if start > 0 else " "
    after = line[end] if end < len(line) else " "
    # Si entoure par des chars qui font partie d'un identifier Python
    py_id_chars = "_"
    is_id_before = before == "_" or before.isalnum()
    is_id_after = after == "_" or after.isalnum()
    return is_id_before or is_id_after


def fix_file(path: Path) -> tuple[int, list]:
    """Retourne (n_replacements, list_of_changes_for_log)."""
    src = path.read_text(encoding="utf-8")
    lines = src.split("\n")
    n_changes = 0
    log_changes = []

    for i, line in enumerate(lines):
        new_line = line
        for accented, ascii_form in IDENTIFIER_FIXES.items():
            if accented not in new_line:
                continue
            # Trouver toutes les occurrences
            result = []
            last = 0
            for m in re.finditer(re.escape(accented), new_line):
                s, e = m.start(), m.end()
                if is_python_identifier_context(new_line, s, e):
                    result.append(new_line[last:s])
                    result.append(ascii_form)
                    last = e
                    n_changes += 1
                    log_changes.append(
                        f"  L{i+1}: '{accented}' -> '{ascii_form}'"
                    )
            if result:
                result.append(new_line[last:])
                new_line = "".join(result)
        if new_line != line:
            lines[i] = new_line

    if n_changes > 0:
        path.write_text("\n".join(lines), encoding="utf-8")

    return n_changes, log_changes


def main():
    targets = [
        ROOT / "outputs" / "pptx_writer.py",
        ROOT / "outputs" / "pdf_writer.py",
        ROOT / "outputs" / "comparison_pptx_writer.py",
        ROOT / "outputs" / "comparison_pdf_writer.py",
        ROOT / "outputs" / "comparison_writer.py",
        ROOT / "outputs" / "cmp_secteur_pptx_writer.py",
        ROOT / "outputs" / "cmp_secteur_pdf_writer.py",
        ROOT / "outputs" / "cmp_secteur_xlsx_writer.py",
        ROOT / "outputs" / "indice_pptx_writer.py",
        ROOT / "outputs" / "indice_pdf_writer.py",
        ROOT / "outputs" / "indice_excel_writer.py",
        ROOT / "outputs" / "indice_comparison_pptx_writer.py",
        ROOT / "outputs" / "indice_comparison_pdf_writer.py",
        ROOT / "outputs" / "indice_comparison_writer.py",
        ROOT / "outputs" / "sectoral_pptx_writer.py",
        ROOT / "outputs" / "screening_writer.py",
        ROOT / "outputs" / "briefing.py",
        ROOT / "outputs" / "excel_writer.py",
        ROOT / "outputs" / "lbo_model.py",
        ROOT / "agents" / "agent_synthese.py",
        ROOT / "agents" / "agent_lbo.py",
        ROOT / "app.py",
    ]
    print("=" * 70)
    print("  UNFIX PYTHON IDENTIFIERS - restaure les noms de variables ASCII")
    print("=" * 70)
    grand_total = 0
    for path in targets:
        if not path.exists():
            continue
        n, log_lines = fix_file(path)
        if n > 0:
            print(f"\n  {path.name:<40} {n:>4} replacements")
            for log in log_lines[:10]:
                print(log)
            if len(log_lines) > 10:
                print(f"    ... and {len(log_lines)-10} more")
            grand_total += n
            # Verif syntax
            try:
                py_compile.compile(str(path), doraise=True)
                print(f"    [OK syntax]")
            except py_compile.PyCompileError as e:
                print(f"    [FAIL syntax] {e.msg[:120]}")
                sys.exit(1)
    print()
    print("-" * 70)
    print(f"  TOTAL : {grand_total} identifier replacements")
    print("=" * 70)


if __name__ == "__main__":
    main()
