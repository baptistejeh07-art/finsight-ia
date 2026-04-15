# -*- coding: utf-8 -*-
"""
tools/log_silent_exceptions.py — Remplace les `except Exception: pass` par
des log.debug() avec contexte de fonction (fichier + nom def enclosing).

USAGE:
    python tools/log_silent_exceptions.py outputs/pdf_writer.py [--dry-run]

Le script :
1. Parse le fichier pour identifier les lignes `except Exception:` suivies de `pass`
2. Remonte dans le fichier pour trouver le `def` englobant (par indentation)
3. Remplace le `pass` par `log.debug(f"[{module}:{fn_name}] exception skipped: {_e}")`
4. Ajoute `as _e` à la clause except si absent

Idempotent : si un except a déjà `as _e` ou `log.`, on skip.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def transform_file(path: Path, dry_run: bool = False) -> tuple[int, int]:
    """Transforme un fichier Python. Retourne (n_matches, n_transformed)."""
    src = path.read_text(encoding="utf-8").splitlines(keepends=False)
    module = path.stem

    # Identifie les `def` successifs : liste (line_idx, indent, name)
    def_stack: list[tuple[int, int, str]] = []
    defs_by_line: list[tuple[int, int, str]] = []  # append-only timeline
    def_re = re.compile(r"^(\s*)def\s+(\w+)\s*\(")
    for i, line in enumerate(src):
        m = def_re.match(line)
        if m:
            indent = len(m.group(1))
            name = m.group(2)
            defs_by_line.append((i, indent, name))

    def enclosing_def(line_idx: int, except_indent: int) -> str:
        """Retourne le nom du def englobant la ligne {line_idx}."""
        # Cherche en arrière la def avec indent < except_indent
        best = None
        for (di, di_indent, dname) in defs_by_line:
            if di >= line_idx:
                break
            if di_indent < except_indent:
                best = (di, di_indent, dname)
        return best[2] if best else "<module>"

    # Match "except Exception:" (ou "except:") suivi de "pass" sur la ligne suivante
    n_matches = 0
    n_transformed = 0

    out_lines: list[str] = []
    i = 0
    N = len(src)
    while i < N:
        line = src[i]
        # Match except (bare or with type, without `as`)
        m = re.match(r"^(\s*)except(\s+Exception)?\s*:\s*$", line)
        if m and i + 1 < N:
            next_line = src[i + 1]
            # Match just `pass` at deeper indent
            m_pass = re.match(r"^(\s*)pass\s*$", next_line)
            if m_pass:
                except_indent = len(m.group(1))
                pass_indent = len(m_pass.group(1))
                if pass_indent > except_indent:
                    # On a trouvé un except + pass à transformer
                    n_matches += 1
                    fn_name = enclosing_def(i, except_indent)
                    # Rewriting
                    new_except = f"{' ' * except_indent}except Exception as _e:"
                    new_pass = (
                        f"{' ' * pass_indent}"
                        f'log.debug(f"[{module}:{fn_name}] exception skipped: {{_e}}")'
                    )
                    out_lines.append(new_except)
                    out_lines.append(new_pass)
                    i += 2
                    n_transformed += 1
                    continue
        out_lines.append(line)
        i += 1

    if not dry_run and n_transformed > 0:
        path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    return n_matches, n_transformed


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    files = [a for a in args if not a.startswith("--")]
    if not files:
        print("Usage: python tools/log_silent_exceptions.py <file.py> [file2.py ...] [--dry-run]")
        return 1

    total_matches = 0
    total_transformed = 0
    for f in files:
        p = Path(f)
        if not p.exists():
            print(f"SKIP {f} (not found)")
            continue
        n, t = transform_file(p, dry_run=dry)
        print(f"{p} : {t}/{n} transformés" + (" (dry-run)" if dry else ""))
        total_matches += n
        total_transformed += t
    print(f"\nTOTAL : {total_transformed}/{total_matches}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
