#!/usr/bin/env python3
# =============================================================================
# FinSight IA — Phase 2 : Test Agent Sentiment FinBERT
# phase2_check.py
#
# Condition de passage Phase 2 : "Score sentiment AAPL généré"
# Usage : python phase2_check.py [TICKER]
# =============================================================================

import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s  %(message)s")

from agents.agent_sentiment import AgentSentiment

TICKER = sys.argv[1] if len(sys.argv) > 1 else "AAPL"


def _bar(score_normalized: float, width: int = 30) -> str:
    """Barre visuelle [-1 → 0 → +1]."""
    pos = int(score_normalized * width)
    bar = "-" * pos + "|" + "-" * (width - pos)
    return f"[{bar}]"


def run() -> None:
    print("=" * 68)
    print(f"  FinSight IA -- Phase 2 : Agent Sentiment  [{TICKER}]")
    print("=" * 68)

    agent = AgentSentiment()
    t0    = time.time()
    result = agent.analyze(TICKER)
    ms    = int((time.time() - t0) * 1000)

    if result is None:
        print(f"\n  [!!] ECHEC : analyse retourne None pour '{TICKER}'")
        sys.exit(1)

    print(f"\n  Ticker     : {result.ticker}")
    print(f"  Timestamp  : {result.timestamp}")
    print(f"\n  Label      : {result.label}")
    print(f"  Score      : {result.score:+.4f}  {_bar(result.score_normalized)}")
    print(f"  Confiance  : {result.confidence:.0%}")
    print(f"  Articles   : {result.articles_analyzed} analyses / {result.articles_total} collectes")
    print(f"  Sources    : {', '.join(result.sources) or 'aucune'}")
    print(f"  Latence    : {ms} ms")

    if result.breakdown:
        bd = result.breakdown
        print(f"\n  Breakdown  :")
        print(f"    positive  {bd.get('avg_positive', 0):.3f}")
        print(f"    negative  {bd.get('avg_negative', 0):.3f}")
        print(f"    neutral   {bd.get('avg_neutral',  0):.3f}")

    if result.samples:
        print(f"\n  Exemples articles :")
        for s in result.samples:
            print(f"    [{s['label']:<8}] {s['score']:+.3f}  {s['headline'][:65]}")

    print(f"\n  Invalidation : {result.meta.get('invalidation_conditions', '')}")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    print(f"\n  {'=' * 60}")
    errors = []

    if result.label not in ("POSITIVE", "NEGATIVE", "NEUTRAL"):
        errors.append(f"label invalide : '{result.label}'")
    if not (-1.0 <= result.score <= 1.0):
        errors.append(f"score hors plage : {result.score}")
    if result.confidence < 0 or result.confidence > 1:
        errors.append(f"confidence hors plage : {result.confidence}")

    if errors:
        print(f"  [!!] ECHEC :")
        for e in errors:
            print(f"       {e}")
        sys.exit(1)

    if result.articles_analyzed == 0:
        print(f"  [!] Score NEUTRAL par defaut (aucune news collectee pour '{TICKER}')")
        print(f"      Verifier : cle Finnhub valide + connexion internet")

    print(f"  PHASE 2 VALIDEE -- sentiment '{TICKER}' genere en {ms} ms")
    print(f"  {'=' * 60}\n")


if __name__ == "__main__":
    run()
