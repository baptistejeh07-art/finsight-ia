#!/usr/bin/env python3
# =============================================================================
# FinSight IA -- Phase 4 : Pipeline 6 agents
# phase4_check.py
#
# Condition de passage : "Pipeline 6 agents stable"
# Pipeline : AgentData || AgentSentiment
#         -> AgentQuant
#         -> AgentSynthese
#         -> AgentQAPython
#         -> AgentQAHaiku || AgentDevil
#
# Usage : python phase4_check.py [TICKER]
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

TICKER  = sys.argv[1] if len(sys.argv) > 1 else "MC.PA"
MAX_MS  = 60_000   # Phase 4 : 60s (2 appels LLM supplementaires)


def _sep(title: str = "") -> None:
    if title:
        print(f"\n  --- {title} ---")
    else:
        print(f"  {'=' * 64}")


def run() -> None:
    print("=" * 68)
    print(f"  FinSight IA -- Phase 4 : Pipeline 6 agents  [{TICKER}]")
    print(f"  Limite : {MAX_MS / 1000:.0f}s | {date.today()}")
    print("=" * 68)

    t0 = time.time()

    # ------------------------------------------------------------------
    # 0. Cache check (requete repetee)
    # ------------------------------------------------------------------
    cache_key_full = cache.make_key(TICKER, "phase4", date.today().isoformat())
    cached = cache.get(cache_key_full)
    if cached:
        elapsed = int((time.time() - t0) * 1000)
        print(f"\n  [CACHE HIT] Pipeline complet depuis cache en {elapsed}ms")
        _print_phase4(cached)
        _sep()
        print(f"  PHASE 4 VALIDEE (cache) -- {TICKER} en {elapsed}ms")
        _sep()
        return

    # ------------------------------------------------------------------
    # 1. AgentData + AgentSentiment EN PARALLELE
    # ------------------------------------------------------------------
    _sep("Collecte parallele : AgentData + AgentSentiment")

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_data = pool.submit(AgentData().collect, TICKER)
        f_sent = pool.submit(AgentSentiment().analyze, TICKER)

    snapshot  = f_data.result()
    sentiment = f_sent.result()

    t1 = int((time.time() - t0) * 1000)
    print(f"  AgentData + AgentSentiment : {t1}ms")

    if snapshot is None:
        print(f"  [!!] ECHEC AgentData : aucune donnee pour '{TICKER}'")
        sys.exit(1)

    ci = snapshot.company_info
    print(f"  Societe : {ci.company_name} ({ci.ticker}) | {ci.currency}")
    if sentiment:
        print(f"  Sentiment : {sentiment.label} {sentiment.score:+.3f}")

    # ------------------------------------------------------------------
    # 2. AgentQuant
    # ------------------------------------------------------------------
    _sep("AgentQuant -- 33 ratios")

    ratios = AgentQuant().compute(snapshot)
    t2 = int((time.time() - t0) * 1000)
    print(f"  Ratios calcules en {t2}ms")

    latest = ratios.latest_year
    yr = ratios.years.get(latest)
    if yr:
        def _p(v): return f"{v*100:.1f}%" if v is not None else "N/A"
        def _x(v): return f"{v:.2f}x"    if v is not None else "N/A"
        print(f"  [{latest}] GM={_p(yr.gross_margin)} | EM={_p(yr.ebitda_margin)} | "
              f"NM={_p(yr.net_margin)} | ROE={_p(yr.roe)} | P/E={_x(yr.pe_ratio)}")

    # ------------------------------------------------------------------
    # 3. AgentSynthese
    # ------------------------------------------------------------------
    _sep("AgentSynthese -- Claude Haiku")

    synthesis = AgentSynthese().synthesize(snapshot, ratios, sentiment)
    t3 = int((time.time() - t0) * 1000)

    if synthesis is None:
        print("  [!] AgentSynthese indisponible")
        sys.exit(1)

    print(f"  Synthese : {synthesis.recommendation} conviction={synthesis.conviction:.0%} ({t3}ms)")

    # ------------------------------------------------------------------
    # 4. AgentQAPython (deterministe, instantane)
    # ------------------------------------------------------------------
    _sep("AgentQA Python -- validations deterministes")

    qa_python = AgentQAPython().validate(snapshot, ratios, synthesis)
    t4 = int((time.time() - t0) * 1000)

    print(f"  QA Python : passed={qa_python.passed} score={qa_python.qa_score:.2f} "
          f"flags={len(qa_python.flags)} ({t4}ms)")

    for f in qa_python.flags:
        sym = "[E]" if f.level == "ERROR" else "[W]" if f.level == "WARNING" else "[I]"
        print(f"    {sym} {f.code} : {f.message[:80]}")

    # ------------------------------------------------------------------
    # 5. AgentQAHaiku + AgentDevil EN PARALLELE
    # ------------------------------------------------------------------
    _sep("AgentQA Haiku + AgentDevil -- en parallele")

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_qa_haiku = pool.submit(AgentQAHaiku().validate, synthesis, qa_python)
        f_devil    = pool.submit(AgentDevil().challenge, synthesis, ratios)

    qa_haiku = f_qa_haiku.result()
    devil    = f_devil.result()

    t5 = int((time.time() - t0) * 1000)
    print(f"  QA Haiku + Devil : {t5}ms")

    # QA Haiku
    if qa_haiku:
        print(f"\n  QA Haiku :")
        print(f"    Readability : {qa_haiku.readability_score:.0%} | "
              f"IB Standard : {'OUI' if qa_haiku.ib_standard else 'NON'}")
        print(f"    Tone : {qa_haiku.tone_assessment[:100]}")
        for issue in qa_haiku.issues[:3]:
            print(f"    [issue] {issue[:80]}")
        if qa_haiku.improved_summary:
            print(f"    [improved] {qa_haiku.improved_summary[:120]}...")
    else:
        print("  [!] AgentQAHaiku indisponible")

    # Devil's Advocate
    if devil:
        delta_str = f"{devil.conviction_delta:+.2f}"
        solidity  = ("these fragile" if devil.conviction_delta < -0.2
                     else "these robuste" if devil.conviction_delta > 0.2
                     else "these moderement solide")
        print(f"\n  Devil's Advocate :")
        print(f"    {devil.original_reco} vs {devil.counter_reco} | "
              f"delta={delta_str} ({solidity})")
        print(f"    Contre-these : {devil.counter_thesis[:120]}")
        for r in devil.counter_risks[:2]:
            print(f"    [-] {r[:80]}")
        for a in devil.key_assumptions[:2]:
            print(f"    [?] {a[:80]}")
    else:
        print("  [!] AgentDevil indisponible")

    # ------------------------------------------------------------------
    # 6. Synthese finale QA
    # ------------------------------------------------------------------
    _sep("Verdict Pipeline 6 agents")

    elapsed_ms = int((time.time() - t0) * 1000)

    errors = []
    if elapsed_ms > MAX_MS:
        errors.append(f"Latence {elapsed_ms}ms > limite {MAX_MS}ms")
    if not ratios.years:
        errors.append("AgentQuant : aucun ratio")
    if synthesis is None:
        errors.append("AgentSynthese : echec")
    if not qa_python.passed and len(qa_python.errors) > 0:
        err_codes = ", ".join(f.code for f in qa_python.errors)
        errors.append(f"QA Python erreurs bloquantes : {err_codes}")

    # Cache du pipeline complet
    pipeline_result = {
        "ticker": TICKER,
        "date": date.today().isoformat(),
        "elapsed_ms": elapsed_ms,
        "synthesis": synthesis.to_dict(),
        "qa_python": qa_python.to_dict(),
        "qa_haiku": qa_haiku.to_dict() if qa_haiku else None,
        "devil": devil.to_dict() if devil else None,
    }
    cache.set(cache_key_full, pipeline_result, ttl=3600)
    print(f"  [Cache] Pipeline mis en cache (TTL 1h)")

    _sep()
    if errors:
        print(f"  [!!] ECHEC Phase 4 :")
        for e in errors:
            print(f"       {e}")
        sys.exit(1)

    print(f"  PHASE 4 VALIDEE -- Pipeline 6 agents stable")
    print(f"  {TICKER} analyse complete en {elapsed_ms}ms")
    _sep()


def _print_phase4(d: dict) -> None:
    syn = d.get("synthesis", {})
    qap = d.get("qa_python", {})
    dev = d.get("devil", {})

    print(f"\n  Synthese : {syn.get('recommendation')} "
          f"conviction={syn.get('conviction', 0):.0%}")
    print(f"  QA Python : passed={qap.get('passed')} score={qap.get('qa_score', 0):.2f}")
    if dev:
        print(f"  Devil : {dev.get('original_reco')} vs {dev.get('counter_reco')} "
              f"delta={dev.get('conviction_delta', 0):+.2f}")


if __name__ == "__main__":
    run()
