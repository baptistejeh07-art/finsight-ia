"""
tools/render_outputs.py — FinSight IA
Convertit les outputs PDF, PPTX et XLSX en images PNG pour revue visuelle.

Usage :
  python tools/render_outputs.py AAPL
  python tools/render_outputs.py AAPL --only pdf
  python tools/render_outputs.py AAPL --only pptx
  python tools/render_outputs.py AAPL --only xlsx
  python tools/render_outputs.py AAPL --only xlsx --sheet INPUT
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

POPPLER_PATH = os.getenv("POPPLER_PATH")
CLI_DIR = Path(__file__).parent.parent / "outputs" / "generated" / "cli_tests"


def render_pdf(pdf_path: Path, out_dir: Path, dpi: int = 150) -> list[Path]:
    """Convertit chaque page du PDF en PNG via pdf2image + Poppler."""
    from pdf2image import convert_from_path

    out_dir.mkdir(parents=True, exist_ok=True)
    images = convert_from_path(
        str(pdf_path),
        dpi=dpi,
        poppler_path=POPPLER_PATH,
    )
    paths = []
    for i, img in enumerate(images, start=1):
        p = out_dir / f"pdf_page_{i:02d}.png"
        img.save(str(p), "PNG")
        paths.append(p)
    print(f"[PDF] {len(paths)} pages -> {out_dir}")
    return paths


def render_pptx(pptx_path: Path, out_dir: Path, width_px: int = 1920) -> list[Path]:
    """Convertit chaque slide PPTX en PNG via PowerPoint COM (Office 16)."""
    import win32com.client

    out_dir.mkdir(parents=True, exist_ok=True)

    # DispatchEx = nouvelle instance isolee
    ppt = win32com.client.DispatchEx("PowerPoint.Application")
    try:
        ppt.Visible = False
    except Exception:
        pass  # Certaines versions de PPT refusent Visible=False

    try:
        prs = ppt.Presentations.Open(str(pptx_path.resolve()), ReadOnly=True, Untitled=False, WithWindow=False)
        paths = []
        for i, slide in enumerate(prs.Slides, start=1):
            p = out_dir / f"slide_{i:02d}.png"
            slide.Export(str(p.resolve()), "PNG", width_px, int(width_px * 9 / 16))
            paths.append(p)
        prs.Close()
        print(f"[PPTX] {len(paths)} slides -> {out_dir}")
        return paths
    finally:
        ppt.Quit()


def _make_clean_xlsx(src: Path) -> Path:
    """
    Crée une copie du xlsx sans charts ni drawings (qui bloquent Excel COM).
    Nettoie aussi Content_Types.xml et les rels des feuilles en conséquence.
    """
    import zipfile, re

    SKIP = re.compile(r'xl/(charts|drawings)/')
    tmp = Path(tempfile.mkdtemp()) / f"clean_{src.stem}.xlsx"

    with zipfile.ZipFile(src, 'r') as zin, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if SKIP.search(item.filename):
                continue
            data = zin.read(item.filename)

            # Nettoie Content_Types.xml : supprime les Override pointant vers charts/drawings
            if item.filename == '[Content_Types].xml':
                data = re.sub(
                    rb'<Override[^>]*(charts|drawings)[^>]*/>\s*',
                    b'',
                    data
                )

            # Nettoie les rels des feuilles : supprime refs aux drawings
            if '_rels/sheet' in item.filename:
                data = re.sub(
                    rb'<Relationship[^>]*/drawings/[^>]*/>\s*',
                    b'',
                    data
                )

            # Nettoie les sheet XMLs : supprime la balise <drawing> inline
            if 'worksheets/sheet' in item.filename and '_rels' not in item.filename:
                data = re.sub(
                    rb'<drawing[^/]*/>\s*',
                    b'',
                    data
                )

            # Nettoie workbook.xml : supprime les definedNames _xlchart
            if item.filename == 'xl/workbook.xml':
                data = re.sub(
                    rb'<definedName[^>]*_xlchart[^<]*</definedName>\s*',
                    b'',
                    data
                )

            zout.writestr(item, data)

    return tmp


def render_xlsx(xlsx_path: Path, out_dir: Path, sheets: list[str] | None = None, dpi: int = 150) -> list[Path]:
    """
    Convertit chaque feuille Excel en PNG via Excel COM + export PDF intermédiaire.
    sheets : liste de noms de feuilles à rendre (None = toutes).
    """
    import win32com.client
    from pdf2image import convert_from_path

    out_dir.mkdir(parents=True, exist_ok=True)

    # Crée une copie data-only pour contourner les liens externes
    clean_path = _make_clean_xlsx(xlsx_path)

    # DispatchEx = nouvelle instance isolee, evite de fermer les fichiers Excel deja ouverts
    xl = win32com.client.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False

    paths = []
    try:
        # CorruptLoad=1 (xlRepairFile) nécessaire car le template a des formules complexes
        # ReadOnly=False obligatoire pour que CalculateFull() fonctionne (recalcul formules)
        wb = xl.Workbooks.Open(str(clean_path), UpdateLinks=0, ReadOnly=False, CorruptLoad=1)

        # Forcer le recalcul complet avant export — sans ca les formules restent vides
        try:
            xl.CalculateFull()
        except Exception:
            try:
                wb.RefreshAll()
            except Exception:
                pass

        sheet_names = [ws.Name for ws in wb.Worksheets]
        to_render = [s for s in sheet_names if sheets is None or s in sheets]

        for sheet_name in to_render:
            ws = wb.Worksheets(sheet_name)
            ws.Activate()

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_pdf = tmp.name

            # xlTypePDF = 0
            try:
                ws.ExportAsFixedFormat(0, tmp_pdf)
            except Exception as e:
                print(f"[XLSX] Skip feuille '{sheet_name}' (export impossible : {e})")
                try:
                    os.unlink(tmp_pdf)
                except Exception:
                    pass
                continue

            try:
                images = convert_from_path(tmp_pdf, dpi=dpi, poppler_path=POPPLER_PATH)
            finally:
                try:
                    os.unlink(tmp_pdf)
                except Exception:
                    pass

            safe_name = sheet_name.replace(" ", "_").replace("/", "-")
            for j, img in enumerate(images, start=1):
                suffix = f"_p{j:02d}" if len(images) > 1 else ""
                p = out_dir / f"xlsx_{safe_name}{suffix}.png"
                img.save(str(p), "PNG")
                paths.append(p)

        wb.Close(SaveChanges=False)
        print(f"[XLSX] {len(paths)} image(s) ({len(to_render)} feuille(s)) -> {out_dir}")
        return paths
    finally:
        xl.Quit()
        try:
            os.unlink(clean_path)
        except Exception:
            pass


def render_indice(universe: str) -> dict:
    """Render PDF + PPTX pour un indice complet (stem : indice_SP_500)."""
    stem = f"indice_{universe.replace(' ', '_').replace('&', '')}"
    renders_dir = CLI_DIR / "renders" / stem

    pdf_files  = sorted(CLI_DIR.glob(f"{stem}*.pdf"))
    pptx_files = sorted(CLI_DIR.glob(f"{stem}*.pptx"))

    if not pdf_files and not pptx_files:
        print(f"Aucun output trouve pour {stem} dans {CLI_DIR}")
        return {}

    result = {}
    if pdf_files:
        result["pdf"] = render_pdf(pdf_files[-1], renders_dir / "pdf")
    if pptx_files:
        result["pptx"] = render_pptx(pptx_files[-1], renders_dir / "pptx")
    return result


def render_sector(sector: str, universe: str, mode: str = "secteur") -> dict:
    """Render PDF + PPTX pour un secteur ou indice."""
    stem = f"{mode}_{sector.replace(' ', '_')}_{universe.replace(' ', '_')}"
    renders_dir = CLI_DIR / "renders" / stem

    pdf_files  = sorted(CLI_DIR.glob(f"{stem}*.pdf"))
    pptx_files = sorted(CLI_DIR.glob(f"{stem}*.pptx"))

    if not pdf_files and not pptx_files:
        print(f"Aucun output trouve pour {stem} dans {CLI_DIR}")
        return {}

    result = {}
    if pdf_files:
        result["pdf"] = render_pdf(pdf_files[-1], renders_dir / "pdf")
    if pptx_files:
        result["pptx"] = render_pptx(pptx_files[-1], renders_dir / "pptx")
    return result


def render(ticker: str, only: str | None = None, sheet: str | None = None) -> dict:
    ticker = ticker.upper().replace("/", "-")
    renders_dir = CLI_DIR / "renders" / ticker

    pdf_files  = sorted(CLI_DIR.glob(f"{ticker}*report*.pdf"))
    pptx_files = sorted(CLI_DIR.glob(f"{ticker}*pitchbook*.pptx"))
    xlsx_files = sorted(CLI_DIR.glob(f"{ticker}*financials*.xlsx"))

    if not pdf_files and not pptx_files and not xlsx_files:
        print(f"Aucun output trouve pour {ticker} dans {CLI_DIR}")
        sys.exit(1)

    result = {}

    if only in (None, "pdf") and pdf_files:
        result["pdf"] = render_pdf(pdf_files[-1], renders_dir / "pdf")

    if only in (None, "pptx") and pptx_files:
        result["pptx"] = render_pptx(pptx_files[-1], renders_dir / "pptx")

    if only in (None, "xlsx") and xlsx_files:
        sheets = [sheet] if sheet else None
        result["xlsx"] = render_xlsx(xlsx_files[-1], renders_dir / "xlsx", sheets=sheets)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", nargs="?", help="Ticker societe (ex: AAPL)")
    parser.add_argument("--sector", default=None, help="Nom du secteur (ex: Technology)")
    parser.add_argument("--universe", default=None, help="Univers (ex: S&P 500)")
    parser.add_argument("--indice", default=None, help="Indice complet (ex: S&P 500)")
    parser.add_argument("--mode", default="secteur", choices=["secteur", "indice"])
    parser.add_argument("--only", choices=["pdf", "pptx", "xlsx"], default=None)
    parser.add_argument("--sheet", default=None, help="Nom de la feuille Excel (ex: INPUT)")
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()

    if args.indice:
        render_indice(args.indice)
    elif args.sector and args.universe:
        render_sector(args.sector, args.universe, mode=args.mode)
    elif args.ticker:
        render(args.ticker, only=args.only, sheet=args.sheet)
    else:
        parser.print_help()
        sys.exit(1)
