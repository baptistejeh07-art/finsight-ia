# =============================================================================
# FinSight IA — Briefing Matinal
# outputs/briefing.py
#
# Génère un briefing texte/markdown prêt pour email ou Slack.
# Zéro LLM — formatage Python pur.
#
# Usage :
#   briefing = generate_briefing(snapshot, ratios, synthesis, sentiment,
#                                qa_python, devil)
#   print(briefing)
#   save_briefing(briefing, ticker)
# =============================================================================

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_OUTPUT_DIR = Path(__file__).parent / "generated"


# ---------------------------------------------------------------------------
# Générateur principal
# ---------------------------------------------------------------------------

def generate_briefing(
    snapshot,
    ratios,
    synthesis,
    sentiment=None,
    qa_python=None,
    devil=None,
    language: str = "fr",
    currency: str = "EUR",
) -> str:
    """
    Retourne le briefing formaté en markdown.
    """
    ci     = snapshot.company_info
    mkt    = snapshot.market
    today  = date.today().isoformat()
    latest = ratios.latest_year
    yr     = ratios.years.get(latest)

    lines = []
    A = lines.append

    def _sep(n=60): A("─" * n)
    def _p(v): return f"{v*100:.1f}%" if v is not None else "N/A"
    def _x(v): return f"{v:.2f}x"     if v is not None else "N/A"
    def _n(v): return f"{v:.2f}"      if v is not None else "N/A"
    def _f(v): return f"{v:,.0f}"     if v is not None else "N/A"

    # ------------------------------------------------------------------
    # En-tête
    # ------------------------------------------------------------------
    _sep()
    A(f"  FINSIGHT IA — BRIEFING MATINAL")
    A(f"  {ci.company_name} ({ci.ticker})  |  {today}")
    _sep()

    # ------------------------------------------------------------------
    # Recommandation
    # ------------------------------------------------------------------
    if synthesis:
        reco = synthesis.recommendation
        badge = {"BUY": "[BUY]", "SELL": "[SELL]", "HOLD": "[HOLD]"}.get(reco, f"[{reco}]")
        A(f"\n  RECOMMANDATION  : {badge}")
        A(f"  Conviction      : {synthesis.conviction:.0%}")
        A(f"  Confiance IA    : {synthesis.confidence_score:.0%}")

        if any([synthesis.target_base, synthesis.target_bull, synthesis.target_bear]):
            cur = f"{mkt.share_price:.2f} {ci.currency}" if mkt.share_price else "N/A"
            A(f"  Cours actuel    : {cur}")
            if synthesis.target_bear:
                A(f"  Cible Bear      : {synthesis.target_bear:.0f} {ci.currency}")
            if synthesis.target_base:
                A(f"  Cible Base      : {synthesis.target_base:.0f} {ci.currency}")
            if synthesis.target_bull:
                A(f"  Cible Bull      : {synthesis.target_bull:.0f} {ci.currency}")

    # ------------------------------------------------------------------
    # Synthèse
    # ------------------------------------------------------------------
    if synthesis and synthesis.summary:
        A(f"\n  SYNTHÈSE :")
        # Wrap à 70 chars
        words = synthesis.summary.split()
        line, buf = "  ", []
        for w in words:
            if len(line) + len(w) + 1 > 72:
                A(line.rstrip())
                line = "  " + w + " "
            else:
                line += w + " "
        if line.strip():
            A(line.rstrip())

    # ------------------------------------------------------------------
    # Ratios clés
    # ------------------------------------------------------------------
    A(f"\n  RATIOS CLES ({latest}) :")
    if yr:
        metrics = [
            ("Gross Margin",      _p(yr.gross_margin)),
            ("EBITDA Margin",     _p(yr.ebitda_margin)),
            ("Net Margin",        _p(yr.net_margin)),
            ("ROE",               _p(yr.roe)),
            ("Net Debt/EBITDA",   _x(yr.net_debt_ebitda)),
            ("EV/EBITDA",         _x(yr.ev_ebitda)),
            ("P/E",               _x(yr.pe_ratio)),
            ("FCF Yield",         _p(yr.fcf_yield)),
            ("Current Ratio",     _n(yr.current_ratio)),
        ]
        for label, val in metrics:
            A(f"    {label:<20} {val}")

        if yr.altman_z is not None:
            z = yr.altman_z
            z_flag = (" [SAIN]" if z >= 2.99
                      else " [ZONE GRISE]" if z >= 1.81
                      else " [DETRESSE]")
            A(f"    {'Altman Z':<20} {z:.2f}{z_flag}")

        if yr.beneish_m is not None:
            m_flag = " [RISQUE MANIP.]" if yr.beneish_m > -2.22 else " [OK]"
            A(f"    {'Beneish M':<20} {yr.beneish_m:.3f}{m_flag}")

        if yr.revenue_growth is not None:
            A(f"    {'Revenue Growth':<20} {_p(yr.revenue_growth)}")
    else:
        A("    Ratios non disponibles.")

    # ------------------------------------------------------------------
    # Sentiment marché
    # ------------------------------------------------------------------
    A(f"\n  SENTIMENT MARCHÉ :")
    if sentiment:
        A(f"    {sentiment.label} | Score : {sentiment.score:+.3f} | "
          f"Confiance : {sentiment.confidence:.0%} | "
          f"Articles : {sentiment.articles_analyzed}")
    else:
        A("    Non disponible.")

    # ------------------------------------------------------------------
    # Points forts & risques
    # ------------------------------------------------------------------
    if synthesis:
        if synthesis.strengths:
            A(f"\n  POINTS FORTS :")
            for s in synthesis.strengths[:3]:
                A(f"    + {s}")
        if synthesis.risks:
            A(f"\n  RISQUES :")
            for r in synthesis.risks[:3]:
                A(f"    - {r}")

    # ------------------------------------------------------------------
    # QA
    # ------------------------------------------------------------------
    if qa_python:
        status = "VALIDE" if qa_python.passed else "ÉCHEC"
        A(f"\n  QA PYTHON : {status}  (score {qa_python.qa_score:.0%})")
        errors   = [f for f in qa_python.flags if f.level == "ERROR"]
        warnings = [f for f in qa_python.flags if f.level == "WARNING"]
        for fl in errors[:3]:
            A(f"    [ERREUR] {fl.message[:100]}")
        for fl in warnings[:3]:
            A(f"    [AVERT]  {fl.message[:100]}")

    # ------------------------------------------------------------------
    # Devil's Advocate
    # ------------------------------------------------------------------
    if devil:
        delta_str = f"{devil.conviction_delta:+.2f}"
        solidity  = ("Thèse fragile" if devil.conviction_delta < -0.2
                     else "Thèse robuste" if devil.conviction_delta > 0.2
                     else "Thèse modérément solide")
        A(f"\n  AVOCAT DU DIABLE : {devil.original_reco} → {devil.counter_reco}")
        A(f"  Delta conviction : {delta_str}  ({solidity})")
        if devil.counter_thesis:
            A(f"  Contre-Thèse : {devil.counter_thesis[:180]}")
        for a in devil.key_assumptions[:2]:
            A(f"    ? {a[:100]}")

    # ------------------------------------------------------------------
    # Conditions d'invalidation
    # ------------------------------------------------------------------
    if synthesis and synthesis.invalidation_conditions:
        A(f"\n  INVALIDATION :")
        A(f"    {synthesis.invalidation_conditions[:200]}")

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------
    A("")
    _sep()
    A(f"  Généré par FinSight IA  |  {today}  |  Confidentiel")
    _sep()

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sauvegarde fichier
# ---------------------------------------------------------------------------

def save_briefing(briefing: str, ticker: str) -> Path:
    """Sauvegarde le briefing en .txt dans outputs/generated/."""
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    path  = _OUTPUT_DIR / f"{ticker.replace('.','_')}_{today}_briefing.txt"
    path.write_text(briefing, encoding="utf-8")
    log.info(f"[Briefing] Sauvegardé : {path.name}")
    return path
