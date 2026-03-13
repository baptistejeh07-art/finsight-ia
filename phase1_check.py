#!/usr/bin/env python3
# =============================================================================
# FinSight IA — Phase 1 : Test Agent Data
# phase1_check.py
#
# Condition de passage Phase 1 : données LVMH collectées en < 5s
# Usage : python phase1_check.py [TICKER]
#         python phase1_check.py MC.PA
#         python phase1_check.py AAPL
# =============================================================================

import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s  %(message)s",
)

from agents.agent_data import AgentData

TICKER       = sys.argv[1] if len(sys.argv) > 1 else "MC.PA"
MAX_MS       = 5_000
CRITICAL     = ["revenue", "cogs", "cash", "long_term_debt", "capex"]
TARGET_YEARS = ["2022", "2023"]


def run() -> None:
    print("=" * 68)
    print(f"  FinSight IA -- Phase 1 : Agent Data  [{TICKER}]")
    print(f"  Limite : {MAX_MS} ms")
    print("=" * 68)

    agent = AgentData()
    t0    = time.time()
    snap  = agent.collect(TICKER)
    ms    = int((time.time() - t0) * 1000)

    if snap is None:
        print(f"\n  [!!] ECHEC : aucune donnee pour '{TICKER}'")
        sys.exit(1)

    ci  = snap.company_info
    mkt = snap.market

    print(f"\n  Societe     : {ci.company_name}  ({ci.ticker})")
    print(f"  Secteur     : {ci.sector or '(non renseigne)'}")
    print(f"  Devise      : {ci.currency}  Unites : {ci.units}")
    print(f"\n  Source(s)   : {snap.meta.get('source')}")
    print(f"  Confiance   : {snap.meta.get('confidence_score', 0):.0%}  (champs remplis / total)")
    print(f"  Latence     : {ms} ms  (limite {MAX_MS} ms)")

    print(f"\n  --- Donnees annuelles ---")
    for year_label in ["2022", "2023", "2024_LTM"]:
        fy = snap.years.get(year_label)
        if fy is None:
            print(f"  {year_label:<12}  manquante")
            continue
        rev = f"{fy.revenue:,.0f} M" if fy.revenue else "N/A"
        print(
            f"  {year_label:<12}  "
            f"couverture={fy.coverage():.0%}  "
            f"revenue={rev}  "
            f"cash={fy.cash}  "
            f"capex={fy.capex}"
        )

    print(f"\n  --- Marche ---")
    print(f"  Prix actuel : {mkt.share_price}  Beta : {mkt.beta_levered}")
    print(f"  Actions (M) : {mkt.shares_diluted}")
    print(f"  Historique  : {len(snap.stock_history)} points mensuels")
    if snap.stock_history:
        last = snap.stock_history[-1]
        print(f"  Dernier pt  : {last.month} @ {last.price}")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    warnings = []
    errors   = []

    if ms > MAX_MS:
        errors.append(f"Latence {ms}ms > limite {MAX_MS}ms")

    for year_label in TARGET_YEARS:
        fy = snap.years.get(year_label)
        if fy is None:
            errors.append(f"Annee {year_label} manquante")
            continue
        missing = [f for f in CRITICAL if getattr(fy, f) is None]
        if missing:
            warnings.append(f"{year_label} champs manquants : {missing}")

    if not snap.stock_history:
        warnings.append("Historique cours vide")

    print(f"\n  {'=' * 60}")
    if errors:
        print(f"  [!!] ECHEC :")
        for e in errors:
            print(f"       {e}")
        sys.exit(1)

    if warnings:
        print(f"  Avertissements (non bloquants) :")
        for w in warnings:
            print(f"    [!] {w}")

    print(f"  PHASE 1 VALIDEE -- {TICKER} collecte en {ms} ms")
    print(f"  {'=' * 60}\n")


if __name__ == "__main__":
    run()
