"""Smoke tests pour tous les writers d'outputs FinSight.

Génère un output minimal pour chaque writer et vérifie qu'il ne crash pas.
Utile pour détecter les régressions après un bulk fix (accents, paliers, etc.).

Usage :
    python tools/test_outputs.py [--verbose]

Retourne exit code 0 si tout passe, 1 si au moins un test échoue.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Callable

# Ajouter la racine au path pour les imports
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "outputs" / "generated" / "cli_tests" / "smoke_tests"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _test(name: str, fn: Callable) -> bool:
    """Execute un test et retourne True/False. Print result."""
    try:
        fn()
        print(f"  [OK]   {name}")
        return True
    except Exception as e:
        print(f"  [FAIL] {name}")
        print(f"         {type(e).__name__}: {str(e)[:200]}")
        if "--verbose" in sys.argv:
            traceback.print_exc()
        return False


# -----------------------------------------------------------------------------
# Sector (PDF + PPTX)
# -----------------------------------------------------------------------------
def test_sector_pdf():
    from cli_analyze import _fetch_real_sector_data
    from outputs.sector_pdf_writer import generate_sector_report
    data = _fetch_real_sector_data("Healthcare", "S&P 500", max_tickers=6)
    out = generate_sector_report(
        sector_name="Healthcare",
        tickers_data=sorted(data, key=lambda x: x.get("score_global") or 0, reverse=True),
        output_path=str(OUT_DIR / "sector_healthcare.pdf"),
        universe="S&P 500",
    )
    assert Path(out).exists() and Path(out).stat().st_size > 10000


def test_sector_pptx():
    from cli_analyze import _fetch_real_sector_data
    from outputs.sectoral_pptx_writer import SectoralPPTXWriter
    data = _fetch_real_sector_data("Healthcare", "S&P 500", max_tickers=6)
    pptx = SectoralPPTXWriter.generate(
        tickers_data=sorted(data, key=lambda x: x.get("score_global") or 0, reverse=True),
        sector_name="Healthcare",
        universe="S&P 500",
    )
    assert pptx and len(pptx) > 10000


# -----------------------------------------------------------------------------
# Société (PDF + PPTX + Excel)
# -----------------------------------------------------------------------------
def test_societe_pdf():
    """Test que le pipeline société génère un PDF sans erreur."""
    # Utilise cli_analyze directement pour avoir le snap + ratios + synthesis complets
    import subprocess
    result = subprocess.run(
        ["python", "cli_analyze.py", "société", "AAPL"],
        capture_output=True, text=True, timeout=300,
        cwd=str(ROOT),
    )
    pdf = ROOT / "outputs/generated/cli_tests/AAPL_report.pdf"
    assert pdf.exists() and pdf.stat().st_size > 50000, \
        f"AAPL PDF manquant ou vide. Stderr: {result.stderr[-300:]}"


# -----------------------------------------------------------------------------
# Indice (PDF + PPTX + Excel)
# -----------------------------------------------------------------------------
def test_indice_pdf():
    import subprocess
    result = subprocess.run(
        ["python", "cli_analyze.py", "indice", "Technology", "S&P 500"],
        capture_output=True, text=True, timeout=180,
        cwd=str(ROOT),
    )
    pdf = ROOT / "outputs/generated/cli_tests/indice_Technology.pdf"
    assert pdf.exists() and pdf.stat().st_size > 50000, \
        f"indice PDF manquant ou vide. Stderr: {result.stderr[-300:]}"


# -----------------------------------------------------------------------------
# Imports (catch syntax errors immédiatement)
# -----------------------------------------------------------------------------
def test_all_writers_import():
    writers = [
        "outputs.pdf_writer",
        "outputs.pptx_writer",
        "outputs.excel_writer",
        "outputs.sector_pdf_writer",
        "outputs.sectoral_pptx_writer",
        "outputs.indice_pdf_writer",
        "outputs.indice_pptx_writer",
        "outputs.indice_excel_writer",
        "outputs.cmp_secteur_pdf_writer",
        "outputs.cmp_secteur_pptx_writer",
        "outputs.cmp_secteur_xlsx_writer",
        "outputs.comparison_pdf_writer",
        "outputs.comparison_pptx_writer",
        "outputs.comparison_writer",
        "outputs.indice_comparison_pdf_writer",
        "outputs.indice_comparison_pptx_writer",
        "outputs.indice_comparison_writer",
        "outputs.briefing",
        "outputs.screening_writer",
    ]
    import importlib
    for m in writers:
        importlib.import_module(m)


def main():
    _section("FinSight outputs smoke tests")

    tests = [
        ("Imports tous les writers",     test_all_writers_import),
        ("Sector PDF (Healthcare/SP500)", test_sector_pdf),
        ("Sector PPTX (Healthcare/SP500)", test_sector_pptx),
        ("Indice PDF (Technology/SP500)", test_indice_pdf),
        # test_societe_pdf est long (~80s), désactivé par défaut
        # ("Société PDF (AAPL)",            test_societe_pdf),
    ]
    if "--full" in sys.argv:
        tests.append(("Société PDF (AAPL)", test_societe_pdf))

    passed = 0
    failed = 0
    for name, fn in tests:
        if _test(name, fn):
            passed += 1
        else:
            failed += 1

    _section(f"Résultats : {passed} OK, {failed} FAIL")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
