"""
cli_analyze.py — FinSight IA
Declenche le pipeline complet (vrais LLMs + donnees) et sauvegarde les outputs.

Usage :
  python cli_analyze.py société  AAPL
  python cli_analyze.py société  MC.PA
  python cli_analyze.py secteur  Technology "CAC 40"
  python cli_analyze.py indice   Technology "S&P 500"
"""
from __future__ import annotations

import sys
import os
import json
import logging
import time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("cli_analyze")

OUT_DIR = Path(__file__).parent / "outputs" / "generated" / "cli_tests"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _save(path: Path, data: bytes) -> None:
    path.write_bytes(data)
    log.info("Sauvegarde : %s  (%d Ko)", path.name, len(data) // 1024)


def run_societe(ticker: str) -> None:
    """Pipeline société complet → PDF + PPTX + briefing."""
    from core.graph import build_graph

    log.info("=== ANALYSE SOCIÉTÉ : %s ===", ticker)
    t0 = time.time()

    state = build_graph().invoke({"ticker": ticker})

    elapsed = time.time() - t0
    log.info("Pipeline terminé en %.1fs", elapsed)

    # ── Résumé console ──────────────────────────────────────────────────────
    synth = state.get("synthesis")
    if synth:
        print(f"\n{'='*60}")
        print(f"  {ticker}  —  {getattr(synth, 'recommendation', '?')}  "
              f"(conviction {getattr(synth, 'conviction', 0):.0%})")
        print(f"  Prix cible base  : {getattr(synth, 'target_base', 'N/A')}")
        print(f"  Prix cible bull  : {getattr(synth, 'target_bull', 'N/A')}")
        print(f"  Prix cible bear  : {getattr(synth, 'target_bear', 'N/A')}")
        print(f"  Résumé : {getattr(synth, 'summary', '')[:120]}")
        print(f"{'='*60}\n")

    # ── Sauvegarde fichiers ──────────────────────────────────────────────────
    pdf_bytes = state.get("pdf_bytes")
    if pdf_bytes:
        _save(OUT_DIR / f"{ticker}_report.pdf", pdf_bytes)
    else:
        log.warning("pdf_bytes absent du state")

    pptx_bytes = state.get("pptx_bytes")
    if pptx_bytes:
        _save(OUT_DIR / f"{ticker}_pitchbook.pptx", pptx_bytes)

    briefing = state.get("briefing_text") or state.get("briefing")
    if briefing:
        p = OUT_DIR / f"{ticker}_briefing.txt"
        p.write_text(str(briefing), encoding="utf-8")
        log.info("Sauvegarde : %s", p.name)

    # ── Dump JSON state (hors bytes) ─────────────────────────────────────────
    safe_state = {k: v for k, v in state.items()
                  if not isinstance(v, (bytes, bytearray))}
    try:
        p = OUT_DIR / f"{ticker}_state.json"
        p.write_text(
            json.dumps(safe_state, default=str, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info("Sauvegarde : %s", p.name)
    except Exception as e:
        log.warning("Dump state JSON échoué : %s", e)

    print(f"\nFichiers générés dans : {OUT_DIR}")
    print(f"  • {ticker}_report.pdf")
    print(f"  • {ticker}_pitchbook.pptx")
    print(f"  • {ticker}_briefing.txt")
    print(f"  • {ticker}_state.json")
    print(f"\nTemps total : {elapsed:.1f}s")


def run_secteur(sector: str, universe: str = "CAC 40") -> None:
    """Pipeline sectoriel → PDF sectoriel + PPTX sectoriel."""
    from agents.agent_data import AgentData
    from outputs.sector_pdf_writer import generate_sector_report
    from outputs.sectoral_pptx_writer import SectoralPPTXWriter

    log.info("=== ANALYSE SECTORIELLE : %s / %s ===", sector, universe)
    t0 = time.time()

    # Données synthétiques pour test immédiat (remplacer par vraies données si dispo)
    tickers = _make_test_tickers(sector, 6)

    pdf_path  = OUT_DIR / f"secteur_{sector.replace(' ','_')}_{universe.replace(' ','_')}.pdf"
    pptx_path = OUT_DIR / f"secteur_{sector.replace(' ','_')}_{universe.replace(' ','_')}.pptx"

    generate_sector_report(sector, tickers, str(pdf_path), universe=universe)
    log.info("PDF sectoriel : %s  (%d Ko)", pdf_path.name, pdf_path.stat().st_size // 1024)

    SectoralPPTXWriter.generate(tickers, sector, universe, str(pptx_path))
    log.info("PPTX sectoriel : %s  (%d Ko)", pptx_path.name, pptx_path.stat().st_size // 1024)

    print(f"\nFichiers générés dans : {OUT_DIR}")
    print(f"  • {pdf_path.name}")
    print(f"  • {pptx_path.name}")
    print(f"\nTemps total : {time.time() - t0:.1f}s")


def run_indice(sector: str, universe: str = "S&P 500") -> None:
    """Pipeline indice → PDF indice."""
    from outputs.indice_pdf_writer import IndicePDFWriter

    log.info("=== ANALYSE INDICE : %s / %s ===", sector, universe)
    t0 = time.time()

    tickers = _make_test_tickers(sector, 15)
    data    = _make_indice_data(tickers, sector, universe)

    pdf_path = OUT_DIR / f"indice_{sector.replace(' ','_')}_{universe.replace(' ','_')}.pdf"
    IndicePDFWriter.generate(data, str(pdf_path))
    log.info("PDF indice : %s  (%d Ko)", pdf_path.name, pdf_path.stat().st_size // 1024)

    print(f"\nFichiers générés dans : {OUT_DIR}")
    print(f"  • {pdf_path.name}")
    print(f"\nTemps total : {time.time() - t0:.1f}s")


# ── Helpers données de test ────────────────────────────────────────────────────

def _make_test_tickers(sector: str, n: int) -> list[dict]:
    import random
    random.seed(42)
    tickers = []
    for i in range(n):
        score = max(25, min(92, 60 + (i - n // 2) * 4))
        tickers.append({
            "ticker": f"{sector[:3].upper()}{i+1}",
            "company": f"{sector} Corp {i+1}",
            "sector": sector,
            "score_global": score,
            "score_value": score * 0.25,
            "score_growth": score * 0.25,
            "score_quality": score * 0.25,
            "score_momentum": score * 0.25,
            "ev_ebitda": 8.0 + i * 1.5,
            "ev_revenue": 2.0 + i * 0.4,
            "pe_ratio": 15.0 + i * 2,
            "ebitda_margin": 20 + i * 0.8,
            "gross_margin": 40 + i * 0.5,
            "net_margin": 12 + i * 0.4,
            "roe": 15.0 + i,
            "revenue_growth": 0.05 + i * 0.015,
            "momentum_52w": 5 + i * 3.0,
            "altman_z": 2.8 + i * 0.1,
            "beneish_m": -2.5,
            "beta": 1.0 + i * 0.05,
            "price": 80 + i * 10,
            "market_cap": (80 + i * 10) * 1e8,
            "revenue_ltm": 1e10 + i * 5e8,
            "currency": "USD",
            "sentiment_score": round(0.1 + i * 0.03, 2),
        })
    return tickers


def _make_indice_data(tickers: list, sector: str, universe: str) -> dict:
    import statistics
    scores = [t["score_global"] for t in tickers]
    avg    = statistics.mean(scores)
    signal = ("Surponderer" if avg > 60 else ("Sous-ponderer" if avg < 40 else "Neutre"))
    return {
        "sector": sector, "universe": universe,
        "signal": signal, "score": round(avg, 1),
        "score_prev": round(avg - 2, 1), "score_delta": 2.0,
        "tickers_data": tickers,
        "top3_buy":  tickers[:3],
        "top3_sell": tickers[-3:],
        "market_context": {
            "tendance": "Hausse modérée",
            "catalyseur": "Publication résultats T1",
            "risque_principal": "Tensions commerciales",
        },
        "sentiment_agg": {
            "label": "Neutre", "score": 0.08,
            "positif": {"nb": 12, "score": "0.45", "themes": "Résultats, IA"},
            "negatif": {"nb": 5,  "score": "-0.38", "themes": "Régulation"},
            "par_secteur": [(sector, "0.08", "Neutre")],
        },
        "methodologie": [
            ("Score sectoriel", "Composite 0-100"),
            ("Signal", "Surponderer (>60) / Neutre (40-60) / Sous-ponderer (<40)"),
            ("Valorisation", "EV/EBITDA médian LTM"),
        ],
        "perf_history": None,
    }


# ── Entrée ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    mode   = sys.argv[1].lower()
    arg1   = sys.argv[2]
    arg2   = sys.argv[3] if len(sys.argv) > 3 else "CAC 40"

    if mode in ("societe", "société", "s"):
        run_societe(arg1)
    elif mode in ("secteur", "sec"):
        run_secteur(arg1, arg2)
    elif mode in ("indice", "idx"):
        run_indice(arg1, arg2)
    else:
        print(f"Mode inconnu : {mode}. Utiliser : société | secteur | indice")
        sys.exit(1)
