#!/usr/bin/env python3
# =============================================================================
# FinSight IA -- Phase 5 : Outputs
# phase5_check.py
#
# Condition de passage : Excel + PPTX + Briefing generes avec succes
# Pipeline complet : 6 agents + 3 outputs
#
# Usage : python phase5_check.py [TICKER]
# =============================================================================

import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s  %(message)s")

import cache.redis_cache as cache
from agents.agent_data        import AgentData
from agents.agent_sentiment   import AgentSentiment
from agents.agent_quant       import AgentQuant
from agents.agent_synthese    import AgentSynthese
from agents.agent_qa_python   import AgentQAPython
from agents.agent_qa_haiku    import AgentQAHaiku
from agents.agent_devil       import AgentDevil
from outputs.excel_writer     import ExcelWriter
from outputs.pptx_builder     import PPTXBuilder
from outputs.briefing         import generate_briefing, save_briefing

TICKER = sys.argv[1] if len(sys.argv) > 1 else "MC.PA"


def _sep(title: str = "") -> None:
    if title:
        print(f"\n  --- {title} ---")
    else:
        print(f"  {'=' * 64}")


def run() -> None:
    print("=" * 68)
    print(f"  FinSight IA -- Phase 5 : Outputs  [{TICKER}]")
    print(f"  {date.today()}")
    print("=" * 68)

    t0 = time.time()

    # ------------------------------------------------------------------
    # Pipeline 6 agents (depuis cache si possible)
    # ------------------------------------------------------------------
    cache_key = cache.make_key(TICKER, "phase4", date.today().isoformat())
    cached    = cache.get(cache_key)

    if cached:
        print(f"\n  [CACHE HIT] Pipeline Phase 4 charge depuis cache")
        # Reconstruire les objets depuis le cache est complexe —
        # on re-run le pipeline léger (sans LLM si cache synthesis dispo)
        _run_pipeline_fresh(t0)
    else:
        _run_pipeline_fresh(t0)


def _run_pipeline_fresh(t0: float) -> None:
    # ------------------------------------------------------------------
    # 1–4 : Pipeline agents (réutilise cache synthesis si disponible)
    # ------------------------------------------------------------------
    _sep("Pipeline 6 agents")

    syn_key = cache.make_key(TICKER, "synthesis", date.today().isoformat())
    cached_syn = cache.get(syn_key)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_data = pool.submit(AgentData().collect, TICKER)
        f_sent = pool.submit(AgentSentiment().analyze, TICKER)

    snapshot  = f_data.result()
    sentiment = f_sent.result()

    if snapshot is None:
        print(f"  [!!] ECHEC AgentData")
        sys.exit(1)

    ratios = AgentQuant().compute(snapshot)

    # Synthese : depuis cache si dispo, sinon re-run
    if cached_syn:
        from agents.agent_synthese import SynthesisResult
        d = cached_syn
        synthesis = SynthesisResult(
            ticker       = d["ticker"],
            company_name = d["company_name"],
            recommendation = d["recommendation"],
            conviction   = d["conviction"],
            target_base  = d.get("target_base"),
            target_bull  = d.get("target_bull"),
            target_bear  = d.get("target_bear"),
            summary      = d.get("summary", ""),
            strengths    = d.get("strengths", []),
            risks        = d.get("risks", []),
            valuation_comment = d.get("valuation_comment", ""),
            confidence_score  = d.get("confidence_score", 0.5),
            invalidation_conditions = d.get("invalidation_conditions", ""),
            meta = d.get("meta", {}),
        )
        print(f"  [Cache] Synthese chargee : {synthesis.recommendation} {synthesis.conviction:.0%}")
    else:
        synthesis = AgentSynthese().synthesize(snapshot, ratios, sentiment)
        if synthesis:
            cache.set(syn_key, synthesis.to_dict(), ttl=3600)

    if synthesis is None:
        print("  [!] AgentSynthese indisponible — outputs partiels")

    qa_python = AgentQAPython().validate(snapshot, ratios, synthesis) if synthesis else None

    # QA Haiku + Devil en parallele
    qa_haiku, devil = None, None
    if synthesis:
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_qah = pool.submit(AgentQAHaiku().validate, synthesis, qa_python)
            f_dev = pool.submit(AgentDevil().challenge, synthesis, ratios)
        qa_haiku = f_qah.result()
        devil    = f_dev.result()

    t_pipeline = int((time.time() - t0) * 1000)
    print(f"  Pipeline 6 agents : {t_pipeline}ms")

    # ------------------------------------------------------------------
    # 5. Excel
    # ------------------------------------------------------------------
    _sep("Output 1 : Excel TEMPLATE.xlsx")
    try:
        excel_path = ExcelWriter().write(snapshot, synthesis, ratios)
        t_excel = int((time.time() - t0) * 1000)
        size_kb = excel_path.stat().st_size // 1024
        print(f"  Excel genere : {excel_path.name}  ({size_kb} KB, {t_excel}ms)")
    except Exception as e:
        print(f"  [!!] Excel ECHEC : {e}")
        excel_path = None

    # ------------------------------------------------------------------
    # 6. PPTX
    # ------------------------------------------------------------------
    _sep("Output 2 : Pitchbook PPTX")
    try:
        pptx_path = PPTXBuilder().build(snapshot, ratios, synthesis, qa_python, devil)
        t_pptx = int((time.time() - t0) * 1000)
        size_kb = pptx_path.stat().st_size // 1024
        print(f"  PPTX genere  : {pptx_path.name}  ({size_kb} KB, {t_pptx}ms)")
    except Exception as e:
        print(f"  [!!] PPTX ECHEC : {e}")
        pptx_path = None

    # ------------------------------------------------------------------
    # 7. Briefing matinal
    # ------------------------------------------------------------------
    _sep("Output 3 : Briefing Matinal")
    try:
        briefing_text = generate_briefing(
            snapshot, ratios, synthesis, sentiment, qa_python, devil
        )
        briefing_path = save_briefing(briefing_text, TICKER)
        t_brief = int((time.time() - t0) * 1000)
        lines = briefing_text.count("\n")
        print(f"  Briefing     : {briefing_path.name}  ({lines} lignes, {t_brief}ms)")
        print()
        # Affichage du briefing (encoding-safe pour Windows cp1252)
        import sys
        for line in briefing_text.split("\n"):
            safe = f"  {line}".encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8", errors="replace")
            print(safe)
    except Exception as e:
        print(f"  [!!] Briefing ECHEC : {e}")
        import traceback; traceback.print_exc()
        briefing_path = None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    elapsed_ms = int((time.time() - t0) * 1000)
    _sep()

    errors = []
    if excel_path is None:
        errors.append("Excel non genere")
    if pptx_path is None:
        errors.append("PPTX non genere")
    if briefing_path is None:
        errors.append("Briefing non genere")

    if errors:
        print(f"  [!!] ECHEC Phase 5 :")
        for e in errors:
            print(f"       {e}")
        sys.exit(1)

    print(f"  PHASE 5 VALIDEE -- 3 outputs generes en {elapsed_ms}ms")
    print(f"  Dossier : {(Path(__file__).parent / 'outputs' / 'generated').resolve()}")
    _sep()


if __name__ == "__main__":
    run()
