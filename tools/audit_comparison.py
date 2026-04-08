"""
tools/audit_comparison.py — FinSight IA
Audit autonome du pipeline comparatif : 2 sociétés → XLSX + PPTX + PDF.

Usage :
  python tools/audit_comparison.py AAPL MSFT
  python tools/audit_comparison.py AAPL MSFT --preview
"""
from __future__ import annotations

import sys
import time
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ROOT         = Path(__file__).parent.parent
CMP_DIR      = ROOT / "outputs" / "generated" / "comparisons"
PREVIEW_ROOT = ROOT / "preview"
REPORTS      = ROOT / "outputs" / "generated" / "audits"
CMP_DIR.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT))

import os
_NO_WIN = {"creationflags": 0x08000000} if __import__("sys").platform == "win32" else {}
os.environ.setdefault("FINSIGHT_LLM_OVERRIDE", "mistral")


# ---------------------------------------------------------------------------
# Pipeline runner (en mémoire, vrais objets Python)
# ---------------------------------------------------------------------------

def run_pipeline(ticker: str) -> dict:
    """Lance le pipeline complet LangGraph pour un ticker.
    Retourne le state dict avec vrais objets Python."""
    print(f"  [PIPELINE] {ticker}...")
    from core.graph import build_graph
    graph   = build_graph()
    state: dict = {}
    for chunk in graph.stream(
        {"ticker": ticker.upper(), "errors": [], "logs": [], "qa_retries": 0},
        stream_mode="updates",
    ):
        node_name  = list(chunk.keys())[0]
        node_delta = chunk[node_name]
        state.update(node_delta)
    return state


# ---------------------------------------------------------------------------
# Génération des outputs comparatifs
# ---------------------------------------------------------------------------

def generate_outputs(state_a: dict, state_b: dict, tkr_a: str, tkr_b: str) -> dict:
    """Génère PPTX + PDF comparatifs et les sauvegarde dans CMP_DIR."""
    stem = f"{tkr_a}_vs_{tkr_b}"
    results = {}

    # PPTX
    try:
        from outputs.comparison_pptx_writer import ComparisonPPTXWriter
        pptx_bytes = ComparisonPPTXWriter().generate_bytes(state_a, state_b)
        pptx_path  = CMP_DIR / f"{stem}_comparison.pptx"
        pptx_path.write_bytes(pptx_bytes)
        print(f"  [OK] PPTX -> {pptx_path.name} ({len(pptx_bytes)//1024} Ko)")
        results["pptx"] = pptx_path
    except Exception as e:
        print(f"  [ERR] PPTX : {e}")
        import traceback; traceback.print_exc()
        results["pptx"] = None

    # PDF
    try:
        from outputs.comparison_pdf_writer import ComparisonPDFWriter
        pdf_raw    = ComparisonPDFWriter().generate_bytes(state_a, state_b)
        # generate_bytes peut retourner bytes ou BytesIO
        pdf_bytes  = pdf_raw.getvalue() if hasattr(pdf_raw, "getvalue") else bytes(pdf_raw)
        pdf_path   = CMP_DIR / f"{stem}_comparison.pdf"
        pdf_path.write_bytes(pdf_bytes)
        print(f"  [OK] PDF  -> {pdf_path.name} ({len(pdf_bytes)//1024} Ko)")
        results["pdf"] = pdf_path
    except Exception as e:
        print(f"  [ERR] PDF : {e}")
        import traceback; traceback.print_exc()
        results["pdf"] = None

    return results


# ---------------------------------------------------------------------------
# Render visuel
# ---------------------------------------------------------------------------

def render_outputs(stem: str) -> dict:
    """Rend les fichiers comparatifs en PNG via LibreOffice/COM."""
    renders_dir = CMP_DIR / "renders" / stem
    renders_dir.mkdir(parents=True, exist_ok=True)

    pptx_path = CMP_DIR / f"{stem}_comparison.pptx"
    pdf_path  = CMP_DIR / f"{stem}_comparison.pdf"

    results = {"pptx": [], "pdf": []}

    # Render PPTX via COM PowerPoint
    if pptx_path.exists():
        try:
            import win32com.client as win32
            import pythoncom
            pythoncom.CoInitialize()
            try:
                ppt = win32.GetActiveObject("PowerPoint.Application")
            except Exception:
                ppt = win32.Dispatch("PowerPoint.Application")
            ppt.Visible = True

            pptx_dir = renders_dir / "pptx"
            pptx_dir.mkdir(parents=True, exist_ok=True)

            prs = ppt.Presentations.Open(str(pptx_path.resolve()), WithWindow=False)
            for i, slide in enumerate(prs.Slides, start=1):
                out_png = pptx_dir / f"slide_{i:02d}.png"
                slide.Export(str(out_png), "PNG")
            prs.Close()
            results["pptx"] = sorted(pptx_dir.glob("*.png"))
            print(f"  [RENDER] PPTX : {len(results['pptx'])} slides")
        except Exception as e:
            print(f"  [RENDER-WARN] PPTX COM : {e}")

    # Render PDF via pdfplumber / pymupdf
    if pdf_path.exists():
        try:
            import fitz  # PyMuPDF
            pdf_dir = renders_dir / "pdf"
            pdf_dir.mkdir(parents=True, exist_ok=True)
            doc = fitz.open(str(pdf_path))
            for i, page in enumerate(doc, start=1):
                mat  = fitz.Matrix(2.0, 2.0)
                pix  = page.get_pixmap(matrix=mat)
                out  = pdf_dir / f"pdf_page_{i:02d}.png"
                pix.save(str(out))
            doc.close()
            results["pdf"] = sorted(pdf_dir.glob("*.png"))
            print(f"  [RENDER] PDF  : {len(results['pdf'])} pages")
        except ImportError:
            # Fallback pdftoppm / poppler
            try:
                pdf_dir = renders_dir / "pdf"
                pdf_dir.mkdir(parents=True, exist_ok=True)
                subprocess.run(
                    ["pdftoppm", "-r", "150", str(pdf_path), str(pdf_dir / "pdf_page")],
                    check=True, capture_output=True
                )
                results["pdf"] = sorted(pdf_dir.glob("*.png"))
                print(f"  [RENDER] PDF  : {len(results['pdf'])} pages (pdftoppm)")
            except Exception as e2:
                print(f"  [RENDER-WARN] PDF : {e2}")
        except Exception as e:
            print(f"  [RENDER-WARN] PDF : {e}")

    return results


# ---------------------------------------------------------------------------
# Preview + git push
# ---------------------------------------------------------------------------

def _clear_previews() -> None:
    if not PREVIEW_ROOT.exists():
        return
    for d in list(PREVIEW_ROOT.iterdir()):
        if d.is_dir():
            rel = d.relative_to(ROOT)
            subprocess.run(["git", "rm", "-rf", "--quiet", str(rel)],
                           cwd=str(ROOT), capture_output=True)
            if d.exists():
                shutil.rmtree(str(d))


def copy_to_preview(stem: str) -> Path:
    _clear_previews()
    dest = PREVIEW_ROOT / stem
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    for f in CMP_DIR.glob(f"{stem}_comparison.*"):
        if f.suffix in (".pptx", ".pdf"):
            shutil.copy2(str(f), dest / f.name)
            copied += 1
    (dest / "_timestamp.txt").write_text(str(time.time()), encoding="utf-8")
    print(f"\n  [PREVIEW] {copied} fichier(s) -> {dest}")
    return dest


def git_commit_push(stem: str) -> None:
    subprocess.run(["git", "add", "preview/", "outputs/generated/comparisons/"],
                   cwd=str(ROOT), capture_output=True)
    msg = f"chore(preview): comparatif {stem} outputs"
    subprocess.run(["git", "commit", "-m", msg, "--allow-empty"],
                   cwd=str(ROOT), capture_output=True)
    r = subprocess.run(["git", "push"], cwd=str(ROOT), capture_output=True)
    if r.returncode == 0:
        print("  [PREVIEW] Outputs commites et pousses -> Streamlit Cloud mis a jour.")
    else:
        print(f"  [WARN] git push failed: {r.stderr.decode('utf-8', errors='replace')[:200]}")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    preview_mode = "--preview" in sys.argv

    if len(args) < 2:
        print("Usage: python tools/audit_comparison.py TICKER_A TICKER_B [--preview]")
        sys.exit(1)

    tkr_a, tkr_b = args[0].upper(), args[1].upper()
    stem = f"{tkr_a}_vs_{tkr_b}"

    print(f"\n{'='*60}")
    print(f"  AUDIT COMPARATIF : {tkr_a} vs {tkr_b}")
    print(f"{'='*60}")
    if preview_mode:
        print("  Mode PREVIEW actif\n")

    t0 = time.time()

    # 1. Pipelines
    print("\n[1/3] Pipelines societes...")
    state_a = run_pipeline(tkr_a)
    state_b = run_pipeline(tkr_b)

    # 2. Génération outputs
    print("\n[2/3] Generation outputs comparatifs...")
    outputs = generate_outputs(state_a, state_b, tkr_a, tkr_b)

    # 3. Render
    print("\n[3/3] Render visuels...")
    renders = render_outputs(stem)

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  AUDIT TERMINE en {elapsed:.1f}s")
    print(f"  PPTX : {outputs.get('pptx') or 'ECHEC'}")
    print(f"  PDF  : {outputs.get('pdf')  or 'ECHEC'}")
    print(f"  Renders PPTX : {len(renders.get('pptx', []))} slides")
    print(f"  Renders PDF  : {len(renders.get('pdf',  []))} pages")
    print(f"{'='*60}\n")

    if preview_mode:
        copy_to_preview(stem)
        git_commit_push(stem)
        print(f"\n  [PREVIEW] Outputs en attente de validation dans Streamlit.")


if __name__ == "__main__":
    main()
