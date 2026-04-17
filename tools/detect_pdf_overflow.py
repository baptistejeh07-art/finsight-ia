#!/usr/bin/env python
"""Détecteur d'overflow PDF — chasse aux problèmes visuels.

Détecte les anomalies visuelles dans les PDFs FinSight :
1. CID encoding fallback (« (cid:127) » = bullet/glyphe non rendu)
2. Texte sortant des marges de page (x1 > page_width - margin)
3. Texte qui chevauche (deux mots avec bbox overlap horizontal + vertical)
4. Fragments orphelins en bas de page (1-2 lignes orphelines en début page)
5. Pages quasi-vides (< 100 chars) suggérant un page break suboptimal

Usage:
    python tools/detect_pdf_overflow.py path/to/file.pdf
    python tools/detect_pdf_overflow.py path/to/file.pdf --margin 40
    python tools/detect_pdf_overflow.py path/to/file.pdf --only-issues
"""

from __future__ import annotations
import sys
import argparse
import re
from pathlib import Path

# Force UTF-8 stdout (Windows cp1252 par défaut)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    import pdfplumber
except ImportError:
    print("ERREUR : pip install pdfplumber", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Patterns détection
# ---------------------------------------------------------------------------

CID_PATTERN = re.compile(r"\(cid:\d+\)")

# Mots typiques d'un page break suboptimal (orphan/widow)
ORPHAN_KEYWORDS = (
    "Source ", "Note :", "(*) ", "Méthodologie",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _color(s: str, code: str) -> str:
    return f"\033[{code}m{s}\033[0m"


def _overlap(w1: dict, w2: dict, tol: float = 0.5) -> bool:
    """Retourne True si deux bboxes se chevauchent (overlap horizontal + vertical)."""
    h_overlap = max(0, min(w1["x1"], w2["x1"]) - max(w1["x0"], w2["x0"]))
    v_overlap = max(0, min(w1["bottom"], w2["bottom"]) - max(w1["top"], w2["top"]))
    if h_overlap <= tol or v_overlap <= tol:
        return False
    # Overlap significatif : > 30% de la largeur du plus petit mot
    min_width = min(w1["x1"] - w1["x0"], w2["x1"] - w2["x0"])
    return h_overlap >= 0.3 * min_width


# ---------------------------------------------------------------------------
# Analyse principale
# ---------------------------------------------------------------------------

def analyze_pdf(
    pdf_path: Path,
    margin_pt: float = 30.0,
    min_page_chars: int = 100,
) -> dict:
    """Analyse chaque page du PDF, retourne un rapport.

    margin_pt : marge de tolérance par rapport au bord de page (points).
    min_page_chars : seuil sous lequel une page est considérée quasi-vide.
    """
    report = {
        "file": str(pdf_path),
        "n_pages": 0,
        "issues": [],
        "summary": {
            "cid_chars": 0,
            "margin_overflow": 0,
            "text_overlap": 0,
            "empty_pages": 0,
            "orphan_lines": 0,
        },
    }

    with pdfplumber.open(str(pdf_path)) as pdf:
        report["n_pages"] = len(pdf.pages)
        for pi, page in enumerate(pdf.pages, start=1):
            page_w = page.width
            page_h = page.height
            text = page.extract_text() or ""

            # 1. CID fallback chars
            cid_matches = CID_PATTERN.findall(text)
            if cid_matches:
                report["summary"]["cid_chars"] += len(cid_matches)
                report["issues"].append({
                    "page": pi,
                    "type": "CID",
                    "count": len(cid_matches),
                    "preview": "Glyphes non rendus : " + ", ".join(set(cid_matches[:5])),
                })

            # 2. Page quasi-vide
            if len(text.strip()) < min_page_chars:
                report["summary"]["empty_pages"] += 1
                report["issues"].append({
                    "page": pi,
                    "type": "EMPTY_PAGE",
                    "count": len(text.strip()),
                    "preview": f"Page contient seulement {len(text.strip())} chars : {text[:60]!r}",
                })

            # 3. Mots dépassant les marges
            try:
                words = page.extract_words(use_text_flow=True)
            except Exception:
                words = []

            margin_violations = []
            for w in words:
                if w["x1"] > page_w - margin_pt + 1.0:  # tolérance 1pt
                    margin_violations.append((w["text"], round(w["x1"], 1), round(w["top"], 1)))
                elif w["x0"] < margin_pt - 1.0:
                    margin_violations.append((w["text"], round(w["x0"], 1), round(w["top"], 1)))

            if margin_violations:
                report["summary"]["margin_overflow"] += len(margin_violations)
                report["issues"].append({
                    "page": pi,
                    "type": "MARGIN",
                    "count": len(margin_violations),
                    "preview": "Mots hors marges : " + ", ".join(
                        f"{t!r}@({x},{y})" for t, x, y in margin_violations[:3]
                    ),
                })

            # 4. Détection chevauchements (overlap)
            overlaps = []
            sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
            for i, w1 in enumerate(sorted_words):
                for w2 in sorted_words[i+1:i+15]:  # fenêtre de 15 mots suivants
                    if abs(w2["top"] - w1["top"]) > 5:
                        break  # mots trop éloignés verticalement
                    if _overlap(w1, w2):
                        overlaps.append((w1["text"], w2["text"]))
                        break  # 1 overlap par mot suffit
            if overlaps:
                report["summary"]["text_overlap"] += len(overlaps)
                report["issues"].append({
                    "page": pi,
                    "type": "OVERLAP",
                    "count": len(overlaps),
                    "preview": "Mots se chevauchent : " + ", ".join(
                        f"{a!r}<>{b!r}" for a, b in overlaps[:3]
                    ),
                })

            # 5. Lignes orphelines (1-2 lignes seules en début/fin de page)
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            if 1 <= len(lines) <= 2 and pi > 1:
                report["summary"]["orphan_lines"] += 1
                report["issues"].append({
                    "page": pi,
                    "type": "ORPHAN",
                    "count": len(lines),
                    "preview": f"Page avec seulement {len(lines)} ligne(s) : {lines[0][:60]!r}",
                })

    return report


# ---------------------------------------------------------------------------
# Affichage console
# ---------------------------------------------------------------------------

def print_report(report: dict, only_issues: bool = False) -> None:
    print()
    print(f"{'='*80}")
    print(f"  Détection overflow PDF -- {report['file']}")
    print(f"{'='*80}")
    print(f"  Pages : {report['n_pages']}")
    s = report["summary"]
    total_issues = sum(s.values())
    if total_issues == 0:
        print(f"  {_color('Aucun probleme detecte', '32')}")
    else:
        parts = []
        if s["cid_chars"]:
            parts.append(_color(f"{s['cid_chars']} CID", "31"))
        if s["margin_overflow"]:
            parts.append(_color(f"{s['margin_overflow']} marges", "31"))
        if s["text_overlap"]:
            parts.append(_color(f"{s['text_overlap']} overlap", "31"))
        if s["empty_pages"]:
            parts.append(_color(f"{s['empty_pages']} pages vides", "33"))
        if s["orphan_lines"]:
            parts.append(_color(f"{s['orphan_lines']} orphelines", "33"))
        print(f"  Bilan : {' . '.join(parts)}")
    print()

    # Group by page
    by_page: dict[int, list] = {}
    for issue in report["issues"]:
        by_page.setdefault(issue["page"], []).append(issue)

    for page_num in sorted(by_page.keys()):
        print(f"--- PAGE {page_num} ---")
        for it in by_page[page_num]:
            color = "31" if it["type"] in ("CID", "MARGIN", "OVERLAP") else "33"
            tag = _color(f"[{it['type']:12s}]", color)
            print(f"  {tag} count={it['count']:>3}  -->  {it['preview']}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", help="Chemin du fichier PDF")
    parser.add_argument("--margin", type=float, default=30.0,
                        help="Marge tolerance (pt) — defaut 30")
    parser.add_argument("--min-page-chars", type=int, default=100,
                        help="Seuil page quasi-vide (chars) — defaut 100")
    parser.add_argument("--only-issues", action="store_true",
                        help="N'affiche que les pages avec problemes")
    args = parser.parse_args()

    p = Path(args.pdf)
    if not p.exists():
        print(f"ERREUR : fichier introuvable : {p}", file=sys.stderr)
        return 1

    report = analyze_pdf(
        p, margin_pt=args.margin, min_page_chars=args.min_page_chars,
    )
    print_report(report, only_issues=args.only_issues)
    s = report["summary"]
    return 1 if (s["cid_chars"] + s["margin_overflow"] + s["text_overlap"]) else 0


if __name__ == "__main__":
    sys.exit(main())
