"""
tools/render_outputs.py — FinSight IA
Convertit les outputs PDF et PPTX en images PNG pour revue visuelle.

Usage :
  python tools/render_outputs.py AAPL
  python tools/render_outputs.py AAPL --only pdf
  python tools/render_outputs.py AAPL --only pptx
"""
from __future__ import annotations

import argparse
import os
import sys
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
    pptx_abs = str(pptx_path.resolve())
    out_abs   = str(out_dir.resolve())

    ppt = win32com.client.Dispatch("PowerPoint.Application")
    try:
        ppt.Visible = False
    except Exception:
        pass  # Certaines versions de PPT refusent Visible=False

    try:
        prs = ppt.Presentations.Open(pptx_abs, ReadOnly=True, Untitled=False, WithWindow=False)
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


def render(ticker: str, only: str | None = None) -> dict:
    ticker = ticker.upper().replace("/", "-")
    renders_dir = CLI_DIR / "renders" / ticker

    # Cherche les fichiers générés pour ce ticker
    pdf_files  = sorted(CLI_DIR.glob(f"{ticker}*report*.pdf"))
    pptx_files = sorted(CLI_DIR.glob(f"{ticker}*pitchbook*.pptx"))

    if not pdf_files and not pptx_files:
        print(f"Aucun output trouvé pour {ticker} dans {CLI_DIR}")
        sys.exit(1)

    result = {}

    if only != "pptx" and pdf_files:
        pdf_path = pdf_files[-1]
        pdf_out  = renders_dir / "pdf"
        result["pdf"] = render_pdf(pdf_path, pdf_out)

    if only != "pdf" and pptx_files:
        pptx_path = pptx_files[-1]
        pptx_out  = renders_dir / "pptx"
        result["pptx"] = render_pptx(pptx_path, pptx_out)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    parser.add_argument("--only", choices=["pdf", "pptx"], default=None)
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()

    render(args.ticker, only=args.only)
