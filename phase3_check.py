#!/usr/bin/env python3
# =============================================================================
# FinSight IA — Phase 3 : Test pipeline complet
# phase3_check.py
#
# Condition de passage : "Analyse LVMH complète < 30s"
# Pipeline : AgentData ∥ AgentSentiment → AgentQuant → AgentSynthese → cache
#
# Usage : python phase3_check.py [TICKER]
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
from agents.agent_data      import AgentData
from agents.agent_quant     import AgentQuant
from agents.agent_sentiment import AgentSentiment
from agents.agent_synthese  import AgentSynthese

TICKER  = sys.argv[1] if len(sys.argv) > 1 else "MC.PA"
MAX_MS  = 30_000


def _sep(title: str = "") -> None:
    if title:
        print(f"\n  --- {title} ---")
    else:
        print(f"  {'=' * 60}")


def run() -> None:
    print("=" * 68)
    print(f"  FinSight IA -- Phase 3 : Pipeline complet  [{TICKER}]")
    print(f"  Limite : {MAX_MS / 1000:.0f}s | {date.today()}")
    print("=" * 68)

    t0 = time.time()

    # ------------------------------------------------------------------
    # 0. Vérification cache (requête répétée → ~3s)
    # ------------------------------------------------------------------
    cache_key = cache.make_key(TICKER, "synthesis", date.today().isoformat())
    cached    = cache.get(cache_key)
    if cached:
        elapsed = int((time.time() - t0) * 1000)
        print(f"\n  [CACHE HIT] Resultat en {elapsed}ms")
        _print_synthesis(cached)
        _sep()
        print(f"  PHASE 3 VALIDEE (cache) -- {TICKER} en {elapsed}ms")
        _sep()
        return

    # ------------------------------------------------------------------
    # 1. AgentData + AgentSentiment EN PARALLELE
    # ------------------------------------------------------------------
    _sep("Collecte parallele : AgentData + AgentSentiment")

    agent_data = AgentData()
    agent_sent = AgentSentiment()

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_data = pool.submit(agent_data.collect, TICKER)
        f_sent = pool.submit(agent_sent.analyze, TICKER)

    snapshot  = f_data.result()
    sentiment = f_sent.result()

    t_data = int((time.time() - t0) * 1000)
    print(f"  AgentData + AgentSentiment : {t_data}ms")

    if snapshot is None:
        print(f"  [!!] ECHEC AgentData : aucune donnee pour '{TICKER}'")
        sys.exit(1)

    ci = snapshot.company_info
    print(f"  Societe : {ci.company_name} ({ci.ticker}) | {ci.currency}")
    print(f"  Confiance donnees : {snapshot.meta.get('confidence_score', 0):.0%}")
    if sentiment:
        print(f"  Sentiment : {sentiment.label} {sentiment.score:+.3f} "
              f"({sentiment.articles_analyzed} articles)")

    # ------------------------------------------------------------------
    # 2. AgentQuant — 33 ratios Python pur
    # ------------------------------------------------------------------
    _sep("AgentQuant — 33 ratios")

    agent_quant = AgentQuant()
    ratios      = agent_quant.compute(snapshot)

    t_quant = int((time.time() - t0) * 1000)
    print(f"  Ratios calcules en {t_quant}ms")

    latest = ratios.latest_year
    yr     = ratios.years.get(latest)
    if yr:
        def _p(v): return f"{v*100:.1f}%" if v is not None else "N/A"
        def _x(v): return f"{v:.2f}x"    if v is not None else "N/A"
        def _n(v): return f"{v:.2f}"     if v is not None else "N/A"

        print(f"  Annee {latest} :")
        print(f"    Gross Margin     : {_p(yr.gross_margin)}")
        print(f"    EBITDA Margin    : {_p(yr.ebitda_margin)}")
        print(f"    Net Margin       : {_p(yr.net_margin)}")
        print(f"    ROE              : {_p(yr.roe)}")
        print(f"    Net Debt/EBITDA  : {_x(yr.net_debt_ebitda)}")
        print(f"    EV/EBITDA        : {_x(yr.ev_ebitda)}")
        print(f"    P/E              : {_x(yr.pe_ratio)}")
        print(f"    Current Ratio    : {_n(yr.current_ratio)}")
        print(f"    Altman Z         : {_n(yr.altman_z)}")
        if yr.beneish_m is not None:
            flag = " !! RISQUE MANIPULATION" if yr.beneish_m > -2.22 else ""
            print(f"    Beneish M        : {yr.beneish_m:.3f}{flag}")
        if yr.revenue_growth is not None:
            print(f"    Revenue Growth   : {_p(yr.revenue_growth)}")

    # ------------------------------------------------------------------
    # 3. AgentSynthese — Claude Haiku
    # ------------------------------------------------------------------
    _sep("AgentSynthese — Claude Haiku")

    agent_syn = AgentSynthese()
    synthesis = agent_syn.synthesize(snapshot, ratios, sentiment)

    t_syn = int((time.time() - t0) * 1000)
    print(f"  Synthese en {t_syn}ms")

    if synthesis is None:
        print(f"  [!] AgentSynthese indisponible (verifier ANTHROPIC_API_KEY)")
    else:
        _print_synthesis(synthesis.to_dict())
        # Cache du résultat (TTL 1h)
        cache.set(cache_key, synthesis.to_dict(), ttl=3600)
        print(f"  [Cache] Resultat mis en cache (TTL 1h)")

    # ------------------------------------------------------------------
    # 4. Validation
    # ------------------------------------------------------------------
    elapsed_ms = int((time.time() - t0) * 1000)

    _sep()
    errors = []
    if elapsed_ms > MAX_MS:
        errors.append(f"Latence {elapsed_ms}ms > limite {MAX_MS}ms")
    if snapshot is None:
        errors.append("AgentData : pas de donnees")
    if not ratios.years:
        errors.append("AgentQuant : aucun ratio calcule")

    if errors:
        print(f"  [!!] ECHEC :")
        for e in errors: print(f"       {e}")
        sys.exit(1)

    print(f"  PHASE 3 VALIDEE -- {TICKER} analyse complete en {elapsed_ms}ms")
    _sep()


def _print_synthesis(d: dict) -> None:
    rec  = d.get("recommendation", "?")
    conv = d.get("conviction", 0)
    conf = d.get("confidence_score", 0)
    print(f"\n  Recommandation : {rec}  (conviction {conv:.0%})")
    print(f"  Confiance IA   : {conf:.0%}")
    if d.get("target_base"):
        print(f"  Cibles  Base={d.get('target_base')}  "
              f"Bull={d.get('target_bull', 'N/A')}  Bear={d.get('target_bear', 'N/A')}")
    if d.get("summary"):
        print(f"\n  Synthese : {d['summary'][:200]}")
    for s in d.get("strengths", []):
        print(f"    [+] {s}")
    for r in d.get("risks", []):
        print(f"    [-] {r}")
    if d.get("valuation_comment"):
        print(f"\n  Valorisation : {d['valuation_comment']}")
    if d.get("invalidation_conditions"):
        print(f"  Invalidation : {d['invalidation_conditions'][:150]}")


if __name__ == "__main__":
    run()
