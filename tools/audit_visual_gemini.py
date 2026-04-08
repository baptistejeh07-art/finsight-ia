"""
audit_visual_gemini.py — FinSight IA
Audit visuel des renders PNG via Gemini Vision.

Usage :
    python tools/audit_visual_gemini.py AAPL
    python tools/audit_visual_gemini.py AAPL --only pptx
    python tools/audit_visual_gemini.py AAPL --only pdf
    python tools/audit_visual_gemini.py AAPL --batch 4   (slides par appel, defaut 4)

Workflow :
    1. Cherche les PNGs dans outputs/generated/cli_tests/renders/{TICKER}/pptx/ et /pdf/
    2. Envoie par batch de N slides a Gemini Vision (gemini-2.5-flash ou flash-latest)
    3. Chaque appel = un batch d images + prompt d'audit
    4. Affiche le rapport consolide + sauvegarde {TICKER}_visual_audit.md

Notes :
    - 4 slides / appel = environ 5 appels pour un PPTX 20 slides
    - Pas de boucle infinie : chaque batch = 1 appel, max 2 retries 503
    - Necessite GEMINI_API_KEY dans .env
"""
from __future__ import annotations

import base64
import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

# Racine projet
_ROOT = Path(__file__).resolve().parent.parent
_RENDERS = _ROOT / "outputs" / "generated" / "cli_tests" / "renders"

# Modeles Gemini a essayer (vision disponible sur tous)
_MODELS = ["models/gemini-2.5-flash", "models/gemini-flash-latest"]

# Prompt d'audit par batch
_PROMPT_PPTX = """Tu es un auditeur qualite pour un pitchbook financier institutionnel (style JPMorgan/Goldman).
Analyse ces {n} slides consecutifs (slides {start} a {end}).

Pour chaque slide, identifie UNIQUEMENT les problemes reels :
- Texte tronque, debordant, coupe par les bords
- Zone vide ou manquante (graphique absent, placeholder visible)
- Titre ou footer absent
- Donnees aberrantes ou incoherentes visibles (ex: "—" partout, NaN, erreur Python)
- Mise en page cassee (elements qui se chevauchent, mauvais alignement evident)
- Caracteres corrompus ou encodage bizarre

Format de reponse (une ligne par slide) :
Slide N: OK
Slide N: [PROBLEME] description courte et precise

Si un slide est visuellement correct, ecris juste "Slide N: OK".
Sois factuel et concis. Pas de commentaires sur le style ou les couleurs."""

_PROMPT_PDF = """Tu es un auditeur qualite pour un rapport PDF financier institutionnel.
Analyse ces {n} pages consecutives (pages {start} a {end}).

Pour chaque page, identifie UNIQUEMENT les problemes reels :
- Texte tronque, coupe ou debordant hors zone
- Section vide ou manquante
- Tableau avec toutes les valeurs a "—"
- En-tete ou pied de page manquant
- Graphique absent (zone blanche a la place)
- Caracteres corrompus ou encodage bizarre

Format de reponse (une ligne par page) :
Page N: OK
Page N: [PROBLEME] description courte et precise

Si une page est visuellement correcte, ecris juste "Page N: OK".
Sois factuel et concis."""


def _gemini_vision(img_bytes_list: list[bytes], prompt: str) -> str | None:
    """Envoie un batch d images + prompt a Gemini Vision. Retourne le texte ou None."""
    gk = os.getenv("GEMINI_API_KEY")
    if not gk:
        print("[audit_vision] GEMINI_API_KEY absent — impossible de faire l'audit vision")
        return None

    from google import genai as _genai

    # Un seul client (evite l'erreur "client closed")
    client = _genai.Client(api_key=gk)

    # Construction du contenu multimodal
    # Format dict universel (fonctionne avec toutes les versions google-genai)
    contents = []
    for img_bytes in img_bytes_list:
        contents.append({
            "inlineData": {
                "mimeType": "image/png",
                "data": base64.b64encode(img_bytes).decode("utf-8")
            }
        })
    contents.append({"text": prompt})

    for model in _MODELS:
        for attempt in range(2):
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config={"max_output_tokens": 1500, "temperature": 0.1},
                )
                txt = (resp.text or "").strip()
                if txt:
                    print(f"  [Gemini Vision] {model} — OK")
                    return txt
                break
            except Exception as e:
                emsg = str(e)
                if "503" in emsg and attempt == 0:
                    print(f"  [Gemini Vision] {model} 503 — retry 15s...")
                    time.sleep(15)
                    continue
                # Quota 0 sur ce modele → passer au suivant
                if "RESOURCE_EXHAUSTED" in emsg or "limit: 0" in emsg:
                    print(f"  [Gemini Vision] {model} quota 0, modele suivant")
                    break
                print(f"  [Gemini Vision] {model} : {emsg[:120]}")
                break

    return None


def _audit_dir(png_dir: Path, label: str, batch_size: int, is_pdf: bool = False) -> list[str]:
    """Audite un repertoire de PNGs. Retourne la liste des lignes du rapport."""
    pngs = sorted(png_dir.glob("*.png"))
    if not pngs:
        return [f"  {label}: aucun PNG trouve dans {png_dir}"]

    print(f"\n[audit_vision] {label}: {len(pngs)} images en batches de {batch_size}")
    lines = [f"\n## {label} ({len(pngs)} {'pages' if is_pdf else 'slides'})"]

    for batch_start in range(0, len(pngs), batch_size):
        batch = pngs[batch_start: batch_start + batch_size]
        n_batch = len(batch)
        idx_start = batch_start + 1
        idx_end   = batch_start + n_batch

        # Charge les bytes
        imgs = []
        for p in batch:
            try:
                imgs.append(p.read_bytes())
            except Exception as ex:
                print(f"  Lecture {p.name} impossible : {ex}")

        if not imgs:
            lines.append(f"  Batch {idx_start}-{idx_end}: impossible de lire les images")
            continue

        # Prompt
        if is_pdf:
            prompt = _PROMPT_PDF.format(n=n_batch, start=idx_start, end=idx_end)
        else:
            prompt = _PROMPT_PPTX.format(n=n_batch, start=idx_start, end=idx_end)

        print(f"  Batch {idx_start}-{idx_end} ({n_batch} imgs)...", end=" ", flush=True)
        result = _gemini_vision(imgs, prompt)

        if result:
            # Normalise les numeros (Gemini peut dire "Slide 1" quand c'est slide 5 du total)
            # On remet juste les lignes brutes telles quelles
            for line in result.split("\n"):
                stripped = line.strip()
                if stripped:
                    lines.append(f"  {stripped}")
        else:
            lines.append(f"  Batch {idx_start}-{idx_end}: echec appel Gemini Vision")

    return lines


def run_audit(ticker: str, only: str | None = None, batch_size: int = 4) -> str:
    """
    Lance l'audit visuel pour un ticker.
    only : 'pptx' | 'pdf' | None (les deux)
    Retourne le texte du rapport.
    """
    ticker_up  = ticker.upper()
    render_dir = _RENDERS / ticker_up

    if not render_dir.exists():
        # Cherche en insensible a la casse
        candidates = [d for d in _RENDERS.iterdir() if d.name.upper() == ticker_up]
        if candidates:
            render_dir = candidates[0]
        else:
            return (f"[audit_vision] Aucun repertoire render trouve pour {ticker_up}.\n"
                    f"Lance d'abord : python tools/render_outputs.py {ticker}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    report_lines = [
        f"# Audit Visuel Gemini — {ticker_up}",
        f"Date : {now}",
        f"Repertoire : {render_dir}",
    ]

    pptx_dir = render_dir / "pptx"
    pdf_dir  = render_dir / "pdf"

    if only in (None, "pptx") and pptx_dir.exists():
        lines = _audit_dir(pptx_dir, "PPTX", batch_size, is_pdf=False)
        report_lines.extend(lines)
    elif only == "pptx" and not pptx_dir.exists():
        report_lines.append(f"\n## PPTX : repertoire {pptx_dir} introuvable")

    if only in (None, "pdf") and pdf_dir.exists():
        lines = _audit_dir(pdf_dir, "PDF", batch_size, is_pdf=True)
        report_lines.extend(lines)
    elif only == "pdf" and not pdf_dir.exists():
        report_lines.append(f"\n## PDF : repertoire {pdf_dir} introuvable")

    report_lines.append("\n---")
    report_lines.append("Source : Gemini Vision (google-genai)  |  FinSight IA")

    report = "\n".join(report_lines)

    # Sauvegarde
    out_path = _ROOT / "outputs" / "generated" / "cli_tests" / f"{ticker_up}_visual_audit.md"
    try:
        out_path.write_text(report, encoding="utf-8")
        print(f"\n[audit_vision] Rapport sauvegarde : {out_path}")
    except Exception as ex:
        print(f"[audit_vision] Sauvegarde impossible : {ex}")

    return report


def main():
    from dotenv import load_dotenv
    load_dotenv()

    args = sys.argv[1:]
    if not args:
        print("Usage: python tools/audit_visual_gemini.py TICKER [--only pptx|pdf] [--batch N]")
        sys.exit(1)

    ticker     = args[0]
    only       = None
    batch_size = 4

    i = 1
    while i < len(args):
        if args[i] == "--only" and i + 1 < len(args):
            only = args[i + 1].lower()
            i += 2
        elif args[i] == "--batch" and i + 1 < len(args):
            try:
                batch_size = int(args[i + 1])
            except ValueError:
                pass
            i += 2
        else:
            i += 1

    print(f"[audit_vision] Audit {ticker.upper()} | only={only or 'pptx+pdf'} | batch={batch_size}")

    report = run_audit(ticker, only=only, batch_size=batch_size)
    print("\n" + "=" * 60)
    print(report)


if __name__ == "__main__":
    main()
