"""Scanne tous les .py pour détecter des imports placés à l'intérieur d'un
docstring de module (bug silencieux — l'import n'est jamais exécuté).

Usage : python tools/scan_docstring_imports.py
"""
from __future__ import annotations

import ast
import pathlib


def scan():
    root = pathlib.Path(__file__).parent.parent
    suspicious = []
    for path in root.rglob("*.py"):
        s = str(path).replace("\\", "/")
        if any(x in s for x in ("venv", ".next", "/test", "/__pycache__")):
            continue
        try:
            src = path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(src)
        except Exception:
            continue
        if not (
            tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        ):
            continue
        docstring = tree.body[0].value.value
        for line_no, line in enumerate(docstring.split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith(("from ", "import ")):
                if any(
                    kw in stripped
                    for kw in ("from core.", "from outputs.", "from agents.", "from data.")
                ):
                    suspicious.append((path, line_no, stripped[:80]))
                    break

    if not suspicious:
        print("Aucun import dans docstring détecté.")
        return 0
    print(f"SUSPECT : {len(suspicious)} imports trouvés dans des docstrings :")
    for p, ln, txt in suspicious:
        print(f"  {p}:docstring-line-{ln}: {txt}")
    return 1


if __name__ == "__main__":
    raise SystemExit(scan())
