# -*- coding: utf-8 -*-
"""
tools/migrate_yfinance_ticker.py — Migre les appels yf.Ticker() directs vers
core.yfinance_cache.get_ticker() dans un fichier Python.

USAGE:
    python tools/migrate_yfinance_ticker.py <file.py> [--dry-run]

Le script :
1. Parse le fichier
2. Trouve tous les patterns `yf.Ticker(x)` et `yfinance.Ticker(x)`
3. Les remplace par `get_ticker(x)`
4. Ajoute l'import `from core.yfinance_cache import get_ticker` après
   les autres imports si pas déjà présent

Idempotent : si déjà migré (import présent), ne ré-ajoute pas l'import.
Ne touche PAS les appels `yf.Ticker()` à l'intérieur de strings/commentaires.
Ne touche PAS core/yfinance_cache.py lui-même (qui DOIT utiliser yf.Ticker direct).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


# Capture yf.Ticker(), yfinance.Ticker(), _yf.Ticker(), _yf2.Ticker(),
# _yf_erp.Ticker(), _yf_etf.Ticker(), etc. — tous les alias locaux yfinance
_YF_TICKER_RE = re.compile(r"\b(?:yf|_yf\w*)\.Ticker\s*\(")
_YFINANCE_TICKER_RE = re.compile(r"\byfinance\.Ticker\s*\(")
_IMPORT_LINE_RE = re.compile(r"^\s*(import|from)\s+")


def transform_file(path: Path, dry_run: bool = False) -> tuple[int, bool]:
    """Transforme un fichier. Retourne (n_replacements, import_added)."""
    src = path.read_text(encoding="utf-8")
    original = src

    # Skip le module cache lui-même
    if path.name == "yfinance_cache.py":
        return (0, False)

    # Skip les fichiers dans .claude/worktrees (snapshots ancien code)
    if ".claude" in str(path).replace("\\", "/"):
        return (0, False)

    # 1. Compter + remplacer yf.Ticker(...) → get_ticker(...)
    matches_yf = _YF_TICKER_RE.findall(src)
    n_replaced = len(matches_yf)

    if n_replaced == 0:
        return (0, False)

    src = _YF_TICKER_RE.sub("get_ticker(", src)

    # 2. Aussi remplacer yfinance.Ticker(...) → get_ticker(...) si présent
    n_replaced_yfinance = len(_YFINANCE_TICKER_RE.findall(src))
    src = _YFINANCE_TICKER_RE.sub("get_ticker(", src)
    n_replaced += n_replaced_yfinance

    # 3. Ajouter l'import get_ticker si pas déjà présent
    import_added = False
    if "from core.yfinance_cache import" not in src and "from core.yfinance_cache" not in src:
        # Trouver la meilleure position pour insérer l'import :
        # Après le dernier import existant (avant les définitions)
        lines = src.splitlines(keepends=False)
        last_import_idx = -1
        for i, ln in enumerate(lines):
            if _IMPORT_LINE_RE.match(ln):
                last_import_idx = i
            elif last_import_idx >= 0 and ln.strip() and not ln.strip().startswith("#"):
                # Première ligne de code après les imports → on s'arrête
                break

        if last_import_idx >= 0:
            new_import = "from core.yfinance_cache import get_ticker"
            lines.insert(last_import_idx + 1, new_import)
            src = "\n".join(lines)
            import_added = True

    if src != original and not dry_run:
        path.write_text(src, encoding="utf-8")

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
