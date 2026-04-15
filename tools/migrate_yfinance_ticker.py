# -*- coding: utf-8 -*-
"""
tools/migrate_yfinance_ticker.py — Migre les appels yf.Ticker() directs vers
core.yfinance_cache.get_ticker() dans un fichier Python.

USAGE:
    python tools/migrate_yfinance_ticker.py <file.py> [--dry-run]

Cette version (v2) utilise le module `ast` de Python au lieu de regex pour
analyser le code correctement. Elle gère les cas suivants qui cassaient la
v1 regex :

1. **Docstrings multi-ligne** : les chaînes triple-quote au niveau module
   contenant des mots-clés "import" ou "Ticker" n'étaient pas distinguées
   du code. La v1 insérait l'import au milieu d'un docstring → import
   inactif au runtime.

2. **Imports multi-ligne** : `from X import (a, b, c)` qui s'étend sur
   plusieurs lignes. La v1 insérait sa nouvelle ligne après la ligne `from`,
   coupant l'import en deux → SyntaxError.

3. **Commentaires** : les commentaires `# yf.Ticker("AAPL")` étaient
   remplacés comme du code. La v1 y touchait.

L'approche v2 :
- Parse le fichier avec `ast.parse()`
- Trouve tous les nodes Call dont la fonction est `{anything}.Ticker`
  (attrib access)
- Identifie leurs positions source (lineno + col_offset)
- Fait les remplacements textuels précis (pas regex globale)
- Trouve le dernier `ast.Import`/`ast.ImportFrom` node au top-level
  pour placer la nouvelle import line après, PAS avant la fin de son
  multi-line

Idempotent : si import `get_ticker` déjà présent → skip import add.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path


def find_yf_ticker_calls(tree: ast.Module) -> list[tuple[int, int, str]]:
    """Retourne la liste (lineno, col_offset, callable_text) pour tous les
    appels à une fonction `.Ticker(...)`.

    Exemples matchés :
        yf.Ticker(symbol)
        yfinance.Ticker(symbol)
        _yf.Ticker(symbol)
        _yf2.Ticker(symbol)
        obj.yf.Ticker(symbol)  # attrib chain
    """
    matches: list[tuple[int, int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr != "Ticker":
            continue
        # Extrait le nom du module (partie avant .Ticker)
        # ex: yf.Ticker → "yf"
        # ex: obj.yf.Ticker → "obj.yf" (on skip, trop complexe)
        if not isinstance(func.value, ast.Name):
            continue
        module_name = func.value.id
        # Filtre sur les modules yfinance usuels
        if module_name == "yfinance" or module_name == "yf" or module_name.startswith("_yf"):
            matches.append((node.lineno, node.col_offset, module_name))

    return matches


def find_last_toplevel_import(tree: ast.Module) -> int:
    """Retourne le lineno (1-indexed) de la DERNIÈRE ligne du dernier
    import top-level du module. 0 si aucun import trouvé.

    Pour un import multi-ligne type :
        from data.models import (
            A, B, C,
        )
    Retourne la lineno du `)` final, pas celui du `from`.
    """
    last_lineno = 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # end_lineno est dispo depuis Python 3.8
            end = getattr(node, "end_lineno", None) or node.lineno
            if end > last_lineno:
                last_lineno = end
    return last_lineno


def has_get_ticker_import(tree: ast.Module) -> bool:
    """True si le module importe déjà get_ticker depuis core.yfinance_cache."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "core.yfinance_cache":
                for alias in node.names:
                    if alias.name == "get_ticker":
                        return True
    return False


def transform_file(path: Path, dry_run: bool = False) -> tuple[int, bool]:
    """Transforme un fichier. Retourne (n_replacements, import_added)."""
    # Skip le module cache lui-même et .claude worktrees
    if path.name == "yfinance_cache.py":
        return (0, False)
    if ".claude" in str(path).replace("\\", "/"):
        return (0, False)

    src = path.read_text(encoding="utf-8")

    # Parse AST
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as e:
        print(f"  SKIP {path} : syntax error L{e.lineno}")
        return (0, False)

    # Trouve les appels
    matches = find_yf_ticker_calls(tree)
    if not matches:
        return (0, False)

    # Trie par position descendante pour faire les replacements de la
    # fin vers le début (préserve les offsets)
    matches.sort(key=lambda m: (m[0], m[1]), reverse=True)

    # Split source en lignes pour édition
    lines = src.splitlines(keepends=True)

    n_replaced = 0
    for lineno, col_offset, module_name in matches:
        # lineno is 1-indexed
        line = lines[lineno - 1]
        # On cherche "{module_name}.Ticker(" à partir de col_offset
        pattern = f"{module_name}.Ticker("
        # Python col_offset est en bytes mais pour du code source normal,
        # 1 byte = 1 char. On tolère qu'il y ait quelques diff d'indent
        idx = line.find(pattern, col_offset)
        if idx < 0:
            # Fallback : cherche n'importe où sur la ligne
            idx = line.find(pattern)
        if idx < 0:
            continue
        # Remplace par "get_ticker("
        new_line = line[:idx] + "get_ticker(" + line[idx + len(pattern):]
        lines[lineno - 1] = new_line
        n_replaced += 1

    if n_replaced == 0:
        return (0, False)

    # Reconstruit le src modifié
    new_src = "".join(lines)

    # Ajoute l'import si absent
    import_added = False
    if not has_get_ticker_import(tree):
        # Ré-parse le src modifié pour trouver la bonne position d'insertion
        try:
            new_tree = ast.parse(new_src, filename=str(path))
        except SyntaxError:
            print(f"  WARN {path} : post-replace syntax error, skip import add")
            new_tree = tree  # fallback
        last_import_end = find_last_toplevel_import(new_tree)
        if last_import_end > 0:
            # Insère après la fin du dernier import
            new_lines = new_src.splitlines(keepends=True)
            import_line = "from core.yfinance_cache import get_ticker\n"
            # Insertion à la position last_import_end (0-indexed = last_import_end - 1 + 1)
            insert_at = last_import_end  # 0-indexed position = 1-indexed lineno
            new_lines.insert(insert_at, import_line)
            new_src = "".join(new_lines)
            import_added = True
        else:
            # Pas d'import existant : insérer au début après le docstring
            new_lines = new_src.splitlines(keepends=True)
            # Skip shebang + docstring
            insert_at = 0
            for i, ln in enumerate(new_lines):
                if ln.startswith("#!"):
                    insert_at = i + 1
                    continue
                break
            new_lines.insert(insert_at, "from core.yfinance_cache import get_ticker\n")
            new_src = "".join(new_lines)
            import_added = True

    # Valide que le nouveau source parse toujours
    try:
        ast.parse(new_src, filename=str(path))
    except SyntaxError as e:
        print(f"  FAIL {path} : post-transform syntax error L{e.lineno} — NOT WRITING")
        return (0, False)

    if not dry_run:
        path.write_text(new_src, encoding="utf-8")

    return (n_replaced, import_added)


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    files = [a for a in args if not a.startswith("--")]
    if not files:
        print("Usage: python tools/migrate_yfinance_ticker.py <file.py> [file2.py ...] [--dry-run]")
        return 1

    total_replaced = 0
    total_imports = 0
    for f in files:
        p = Path(f)
        if not p.exists():
            print(f"SKIP {f} (not found)")
            continue
        n, imp = transform_file(p, dry_run=dry)
        if n > 0:
            imp_s = " + import added" if imp else ""
            print(f"{p} : {n} replacements{imp_s}" + (" (dry-run)" if dry else ""))
        total_replaced += n
        total_imports += 1 if imp else 0
    print(f"\nTOTAL : {total_replaced} replacements, {total_imports} imports added")
    return 0


if __name__ == "__main__":
    sys.exit(main())
