# =============================================================================
# FinSight IA — Phase 8 Check : LangGraph
# phase8_check.py
# =============================================================================

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

TICKER = sys.argv[1] if len(sys.argv) > 1 else "TSLA"

if __name__ == "__main__":
    log.info(f"[Phase8] Test LangGraph sur {TICKER}")
    from core.graph import build_graph
    import time

    graph = build_graph()
    log.info("[Phase8] Graphe compile OK")

    t0     = time.time()
    result = graph.invoke({
        "ticker":     TICKER,
        "errors":     [],
        "logs":       [],
        "qa_retries": 0,
    })
    elapsed = int((time.time() - t0) * 1000)

    # Rapport
    print("\n" + "="*60)
    print(f"  FinSight LangGraph — {TICKER}")
    print("="*60)
    print(f"  Temps total    : {elapsed/1000:.1f}s")
    print(f"  Data quality   : {result.get('data_quality', 0):.0%}")
    print(f"  Confidence     : {result.get('confidence_score', 0):.0%}")
    print(f"  Recommandation : {result.get('recommendation')}")
    print(f"  Bloque         : {result.get('blocked', False)}")
    print(f"  Excel          : {bool(result.get('excel_path'))}")
    print(f"  PPTX           : {bool(result.get('pptx_path'))}")
    print(f"  PDF            : {bool(result.get('pdf_path'))}")

    nodes_run = [e["node"] for e in (result.get("logs") or [])]
    print(f"  Noeuds         : {' -> '.join(nodes_run)}")

    errs = result.get("errors") or []
    if errs:
        print(f"  Erreurs        : {errs}")
    print("="*60)

    # Condition passage
    ok = (
        result.get("raw_data") is not None
        and result.get("ratios") is not None
        and not result.get("blocked")
        and elapsed < 60_000
    )
    print(f"\nPhase 8 : {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)
