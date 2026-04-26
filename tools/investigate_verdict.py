# -*- coding: utf-8 -*-
"""
Investigation : LLM verdict vs scores quanti pour AAPL vs MSFT.
Charge les states existants, recree les metriques, appelle _generate_synthesis,
et dump TOUT (raisonnement LLM + scores quanti + diagnostic).

Usage : python tools/investigate_verdict.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    print("=" * 70)
    print("  INVESTIGATION VERDICT — AAPL vs MSFT")
    print("=" * 70)

    # 1. Charger les states
    state_a_path = Path("outputs/generated/cli_tests/AAPL_state.json")
    state_b_path = Path("outputs/generated/cli_tests/MSFT_state.json")

    if not state_a_path.exists() or not state_b_path.exists():
        print(f"[ERR] States manquants : {state_a_path}, {state_b_path}")
        sys.exit(1)

    state_a = json.loads(state_a_path.read_text(encoding="utf-8"))
    state_b = json.loads(state_b_path.read_text(encoding="utf-8"))

    print(f"\n[OK] States charges :")
    print(f"  AAPL : {state_a_path}")
    print(f"  MSFT : {state_b_path}")

    # 2. Extraire les metriques via comparison_writer
    from outputs.cmp_societe_xlsx_writer import extract_metrics, _fetch_supplements
    print("\n[INFO] Fetch supplements (peut prendre 30s)...")
    supp_a = _fetch_supplements("AAPL")
    supp_b = _fetch_supplements("MSFT")
    m_a = extract_metrics(state_a, supp_a)
    m_b = extract_metrics(state_b, supp_b)
    m_a["ticker_a"] = "AAPL"
    m_b["ticker_b"] = "MSFT"

    # 3. Scores quanti (avant synthese LLM)
    print("\n" + "=" * 70)
    print("  SCORES QUANTI BRUTS (avant LLM)")
    print("=" * 70)

    keys_to_dump = [
        "finsight_score", "piotroski_score", "altman_z", "beneish_mscore",
        "pe_ratio", "ev_ebitda", "pb_ratio",
        "ebitda_margin_ltm", "net_margin_ltm", "roic_ltm", "roe_ltm",
        "revenue_cagr_3y", "ebitda_cagr_3y",
        "net_debt_ebitda", "fcf_yield", "dividend_yield",
        "perf_1m", "perf_3m", "perf_1y", "beta", "var_95_1m",
        "momentum_score", "volatility_52w", "wacc",
    ]
    print(f"\n{'Metrique':<28} {'AAPL':>15} {'MSFT':>15} {'Winner':>10}")
    print("-" * 70)

    aapl_wins = 0
    msft_wins = 0
    for k in keys_to_dump:
        va = m_a.get(k)
        vb = m_b.get(k)
        # Pour ces metriques, plus haut = mieux
        higher_better = k in {
            "finsight_score", "piotroski_score", "altman_z",
            "ebitda_margin_ltm", "net_margin_ltm", "roic_ltm", "roe_ltm",
            "revenue_cagr_3y", "ebitda_cagr_3y",
            "fcf_yield", "dividend_yield",
            "perf_1m", "perf_3m", "perf_1y",
            "momentum_score",
        }
        # Plus bas = mieux
        lower_better = k in {
            "pe_ratio", "ev_ebitda", "pb_ratio",
            "beneish_mscore", "net_debt_ebitda", "beta",
            "var_95_1m", "volatility_52w", "wacc",
        }
        winner = "?"
        try:
            fa = float(va) if va is not None else None
            fb = float(vb) if vb is not None else None
            if fa is not None and fb is not None:
                if higher_better:
                    if fa > fb: winner = "AAPL"; aapl_wins += 1
                    elif fb > fa: winner = "MSFT"; msft_wins += 1
                    else: winner = "="
                elif lower_better:
                    if fa < fb: winner = "AAPL"; aapl_wins += 1
                    elif fb < fa: winner = "MSFT"; msft_wins += 1
                    else: winner = "="
        except Exception:
            pass

        def _fmt(v):
            if v is None: return "None"
            try:
                fv = float(v)
                if abs(fv) < 0.01: return f"{fv:.4f}"
                if abs(fv) < 10: return f"{fv:.3f}"
                return f"{fv:.2f}"
            except Exception: return str(v)[:14]

        print(f"{k:<28} {_fmt(va):>15} {_fmt(vb):>15} {winner:>10}")

    print("-" * 70)
    print(f"{'TOTAL VICTOIRES':<28} {aapl_wins:>15} {msft_wins:>15}")
    print(f"{'WINNER QUANTI BRUT':<28} {('AAPL' if aapl_wins > msft_wins else 'MSFT' if msft_wins > aapl_wins else '='):>15}")

    # FinSight score officiel
    fs_a = m_a.get("finsight_score") or 0
    fs_b = m_b.get("finsight_score") or 0
    fs_winner = "AAPL" if fs_a > fs_b else "MSFT" if fs_b > fs_a else "="
    print(f"\n  FinSight Score (officiel) : AAPL={fs_a}/100  MSFT={fs_b}/100  -> {fs_winner}")

    # Winner de m_a/m_b (calcule par CmpSocietePPTXWriter)
    if fs_a != fs_b:
        winner_quanti = "AAPL" if fs_a > fs_b else "MSFT"
    else:
        pio_a = m_a.get("piotroski_score") or 0
        pio_b = m_b.get("piotroski_score") or 0
        winner_quanti = "AAPL" if pio_a >= pio_b else "MSFT"
    m_a["winner"] = m_b["winner"] = winner_quanti
    print(f"  Winner que CmpSocietePPTXWriter va passer au LLM : {winner_quanti}")

    # 4. Appeler _generate_synthesis et dumper le verdict + bull/bear
    print("\n" + "=" * 70)
    print("  APPEL _generate_synthesis (LLM)")
    print("=" * 70)
    from outputs.cmp_societe_pptx_writer import _generate_synthesis
    synthesis = _generate_synthesis(m_a, m_b)

    print("\n--- VERDICT TEXT (synthese LLM) ---")
    print(synthesis.get("verdict_text") or "(vide)")
    print("\n--- BULL A (AAPL) ---")
    print(synthesis.get("bull_a") or "(vide)")
    print("\n--- BEAR A (AAPL) ---")
    print(synthesis.get("bear_a") or "(vide)")
    print("\n--- BULL B (MSFT) ---")
    print(synthesis.get("bull_b") or "(vide)")
    print("\n--- BEAR B (MSFT) ---")
    print(synthesis.get("bear_b") or "(vide)")
    print("\n--- VALUATION TEXT ---")
    print(synthesis.get("valuation_text") or "(vide)")
    print("\n--- QUALITY TEXT ---")
    print(synthesis.get("quality_text") or "(vide)")

    # 5. Diagnostic
    print("\n" + "=" * 70)
    print("  DIAGNOSTIC FINAL")
    print("=" * 70)
    verdict_low = (synthesis.get("verdict_text") or "").lower()
    aapl_in = "aapl" in verdict_low or "apple" in verdict_low
    msft_in = "msft" in verdict_low or "microsoft" in verdict_low
    print(f"  Mention AAPL dans verdict : {aapl_in}")
    print(f"  Mention MSFT dans verdict : {msft_in}")
    print(f"  Winner officiel (FinSight Score) : {fs_winner}")
    print(f"  Winner quanti par majorite : {('AAPL' if aapl_wins > msft_wins else 'MSFT')}")
    print(f"  Le LLM raconte quoi en premier ? regarder le verdict ci-dessus")

    # Dump complet en JSON pour archivage
    out = Path("tools/investigate_verdict_dump.json")
    dump = {
        "scores_quanti": {k: {"AAPL": m_a.get(k), "MSFT": m_b.get(k)} for k in keys_to_dump},
        "victoires_par_metrique": {"AAPL": aapl_wins, "MSFT": msft_wins},
        "finsight_score": {"AAPL": fs_a, "MSFT": fs_b, "winner": fs_winner},
        "winner_passe_au_llm": winner_quanti,
        "synthesis": {k: synthesis.get(k) for k in [
            "verdict_text", "bull_a", "bear_a", "bull_b", "bear_b",
            "valuation_text", "quality_text"]},
    }
    out.write_text(json.dumps(dump, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[OK] Dump complet sauvegarde -> {out}")


if __name__ == "__main__":
    main()
