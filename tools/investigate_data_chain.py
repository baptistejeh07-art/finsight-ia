# -*- coding: utf-8 -*-
"""
Investigation chaine data : run_pipeline -> extract_metrics -> m_a/m_b.
But : identifier ce qui est REELLEMENT None apres la chaine complete (objets en memoire).

Usage : python tools/investigate_data_chain.py [TICKER_A] [TICKER_B]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import os
os.environ.setdefault("FINSIGHT_LLM_OVERRIDE", "mistral")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    tkr_a = args[0].upper() if len(args) > 0 else "AAPL"
    tkr_b = args[1].upper() if len(args) > 1 else "MSFT"

    print(f"=== INVESTIGATION DATA CHAIN : {tkr_a} vs {tkr_b} ===\n")

    # 1. Pipelines en memoire (vrais objets Python)
    from core.graph import build_graph
    print(f"[1/3] Pipeline {tkr_a}...")
    g = build_graph()
    state_a = {}
    for ch in g.stream({"ticker": tkr_a, "errors": [], "logs": [], "qa_retries": 0},
                       stream_mode="updates"):
        state_a.update(ch[list(ch.keys())[0]])

    print(f"[1/3] Pipeline {tkr_b}...")
    g = build_graph()
    state_b = {}
    for ch in g.stream({"ticker": tkr_b, "errors": [], "logs": [], "qa_retries": 0},
                       stream_mode="updates"):
        state_b.update(ch[list(ch.keys())[0]])

    print("\n[2/3] Inspection raw_data (FinancialSnapshot)...")
    rd_a = state_a.get("raw_data")
    if rd_a is not None:
        print(f"  type(raw_data {tkr_a}) = {type(rd_a).__name__}")
        # Dump tous les attributs interessants
        for attr in ["ticker", "company_info", "income_statements", "balance_sheets",
                     "cashflows", "market_data", "ratios", "meta"]:
            v = getattr(rd_a, attr, None)
            if v is None:
                print(f"  {attr}: None")
            elif isinstance(v, list):
                print(f"  {attr}: list len={len(v)}")
            elif hasattr(v, "__dict__"):
                # dataclass : list keys
                fields = [f for f in vars(v).keys()]
                print(f"  {attr}: {type(v).__name__}({len(fields)} fields)")
            else:
                print(f"  {attr}: {type(v).__name__}")

    print("\n[3/3] extract_metrics + dump m_a/m_b...")
    from outputs.cmp_societe_xlsx_writer import extract_metrics, _fetch_supplements
    supp_a = _fetch_supplements(tkr_a)
    supp_b = _fetch_supplements(tkr_b)
    m_a = extract_metrics(state_a, supp_a)
    m_b = extract_metrics(state_b, supp_b)

    keys = sorted(set(list(m_a.keys()) + list(m_b.keys())))

    nones_a = [k for k in keys if m_a.get(k) is None]
    nones_b = [k for k in keys if m_b.get(k) is None]
    filled_a = [k for k in keys if m_a.get(k) is not None]
    filled_b = [k for k in keys if m_b.get(k) is not None]

    print(f"\n  m_a : {len(filled_a)} rempli(s) / {len(nones_a)} None")
    print(f"  m_b : {len(filled_b)} rempli(s) / {len(nones_b)} None")

    print(f"\n--- CHAMPS REMPLIS (m_a {tkr_a}) ---")
    for k in filled_a:
        v = m_a.get(k)
        s = repr(v)[:60]
        print(f"  {k}: {s}")

    print(f"\n--- CHAMPS NONE (m_a {tkr_a}) ---")
    for k in nones_a:
        print(f"  {k}")

    print(f"\n--- CHAMPS REMPLIS (m_b {tkr_b}) ---")
    for k in filled_b:
        v = m_b.get(k)
        s = repr(v)[:60]
        print(f"  {k}: {s}")

    print(f"\n--- CHAMPS NONE (m_b {tkr_b}) ---")
    for k in nones_b:
        print(f"  {k}")

    # Dump JSON pour analyse posterieure
    out = ROOT / "tools" / f"data_chain_dump_{tkr_a}_vs_{tkr_b}.json"
    def _safe(v):
        try:
            json.dumps(v)
            return v
        except Exception:
            return repr(v)[:200]
    dump = {
        "m_a": {k: _safe(m_a.get(k)) for k in keys},
        "m_b": {k: _safe(m_b.get(k)) for k in keys},
        "summary": {
            "m_a_filled": len(filled_a),
            "m_a_nones":  len(nones_a),
            "m_b_filled": len(filled_b),
            "m_b_nones":  len(nones_b),
        },
    }
    out.write_text(json.dumps(dump, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[OK] Dump -> {out}")


if __name__ == "__main__":
    main()
