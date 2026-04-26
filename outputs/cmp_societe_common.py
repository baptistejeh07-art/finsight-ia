# -*- coding: utf-8 -*-
"""
outputs/cmp_societe_common.py — Common context builder pour les writers cmp société.

Refactor #185 Baptiste : les 3 writers comparatifs société (xlsx, pptx, pdf)
avaient chacun leur propre duplication de la logique :
1. Lire state_a/state_b (raw_data, ratios, synthesis, sentiment)
2. Appeler _fetch_supplements() pour A et B
3. Appeler extract_metrics() pour A et B
4. Déterminer le winner (finsight_score fallback + llm_choice prioritaire)
5. Appeler _generate_synthesis() pour générer le verdict LLM
6. Post-processing (strip markdown, etc.)

Ce module centralise tout dans build_cmp_context() qui retourne un dataclass
CmpSocieteContext typé. Les 3 writers l'appellent et n'ont plus qu'à consommer
ctx.m_a, ctx.synthesis, ctx.winner, etc.

Avantages :
- Bug fix centralisé : une modif du flow data → propagation automatique aux 3 writers
- Cache session_state Streamlit exploité une seule fois (cf refonte #167 #172)
- Type safety : auto-complete IDE, pas de typos sur les clés
- Tests unitaires possibles (mock state_a/state_b, inspect ctx)

Usage typique dans un writer :

    from outputs.cmp_societe_common import build_cmp_context

    ctx = build_cmp_context(state_a, state_b, force_regenerate_llm=False)
    # ctx.tkr_a, ctx.tkr_b, ctx.name_a, ctx.name_b
    # ctx.m_a, ctx.m_b : metrics dicts
    # ctx.supp_a, ctx.supp_b : yfinance supplements
    # ctx.synthesis : dict avec verdict_text, exec_summary, bull_a/b, bear_a/b, llm_choice
    # ctx.winner : "TKR_A" | "TKR_B" | None (si NEUTRAL LLM)
    # ctx.winner_source : "llm" | "llm_neutral" | "finsight_fallback"
"""
from __future__ import annotations

import logging
import re as _re_md
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# DATACLASS — contexte partagé entre les 3 writers
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class CmpSocieteContext:
    """Contexte complet pour la génération d'un comparatif société.

    Utilisé par cmp_societe_xlsx_writer, cmp_societe_pptx_writer,
    cmp_societe_pdf_writer pour éviter de dupliquer la logique de
    construction du contexte.
    """
    # Identité
    tkr_a: str
    tkr_b: str
    name_a: str
    name_b: str

    # Metrics complètes (dict retournés par extract_metrics)
    m_a: dict = field(default_factory=dict)
    m_b: dict = field(default_factory=dict)

    # Suppléments yfinance bruts (avant extract_metrics)
    supp_a: dict = field(default_factory=dict)
    supp_b: dict = field(default_factory=dict)

    # Synthèse LLM (dict avec exec_summary, verdict_text, bull_a/b, bear_a/b,
    # financial_text, valuation_text, quality_text, llm_choice)
    synthesis: dict = field(default_factory=dict)

    # Winner résolu (priorité LLM choice, fallback finsight_score)
    winner: Optional[str] = None            # ticker ou None si neutre
    winner_source: str = "finsight_fallback"  # "llm" | "llm_neutral" | "finsight_fallback"

    # Scores FinSight (extraits pour affichage rapide — déjà dans m_a/m_b mais dupliqué ici)
    finsight_a: int = 0
    finsight_b: int = 0


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS — ticker extraction + strip markdown
# ═════════════════════════════════════════════════════════════════════════════

def _get_ticker(state: dict, default: str = "A") -> str:
    """Extrait le ticker depuis un state pipeline (raw_data ou snapshot)."""
    snap = state.get("raw_data") or state.get("snapshot")
    if snap is not None and not isinstance(snap, (str, dict)):
        try:
            return snap.ticker or default
        except Exception:
            pass
    if isinstance(snap, dict):
        t = snap.get("ticker") or snap.get("company_info", {}).get("ticker")
        if t:
            return t
    return state.get("ticker", default)


def _strip_md(s):
    """Pre-strip markdown asterisks des textes LLM."""
    if not s:
        return s
    s = _re_md.sub(r'\*\*(.+?)\*\*', r'\1', str(s), flags=_re_md.DOTALL)
    s = _re_md.sub(r'\*(.+?)\*', r'\1', s, flags=_re_md.DOTALL)
    s = _re_md.sub(r'\*+', '', s)
    return s


def _strip_md_dict(d: dict) -> dict:
    """Strip markdown sur toutes les string values d'un dict."""
    if not isinstance(d, dict):
        return d
    return {
        k: _strip_md(v) if isinstance(v, str) else v
        for k, v in d.items()
    }


# ═════════════════════════════════════════════════════════════════════════════
# MAIN BUILDER
# ═════════════════════════════════════════════════════════════════════════════

def build_cmp_context(
    state_a: dict,
    state_b: dict,
    force_regenerate_llm: bool = False,
    with_synthesis: bool = True,
) -> CmpSocieteContext:
    """Build le contexte complet comparatif société à partir des 2 states pipeline.

    Flow :
    1. Extract tickers depuis state_a / state_b
    2. Tente de lire le cache session_state ["_cmp_cache"] (optim #167 refactor perf)
    3. Si cache hit et tickers match : réutilise supp/m/synthesis direct
    4. Sinon : fetch + extract + winner compute + synthesis LLM (si with_synthesis)
    5. Résout le winner final (priorité llm_choice, fallback finsight)
    6. Strip markdown sur toutes les strings de synthesis
    7. Retourne CmpSocieteContext

    Args:
        state_a : state pipeline de la société A (avec raw_data, ratios, synthesis, sentiment)
        state_b : state pipeline de la société B
        force_regenerate_llm : si True, ignore le cache et regénère la synthèse LLM
                                (utilisé par ex: tests, debug)
        with_synthesis : si False, ne génère pas la synthèse LLM (pour les writers
                         qui n'en ont pas besoin comme XLSX). Le cache session_state
                         est toujours lu si dispo — utile quand XLSX tourne après
                         PPTX/PDF qui l'ont déjà peuplé.

    Returns:
        CmpSocieteContext prêt à être consommé par les writers.
    """
    from outputs.cmp_societe_xlsx_writer import extract_metrics, _fetch_supplements

    tkr_a = _get_ticker(state_a, "A")
    tkr_b = _get_ticker(state_b, "B")
    log.info(f"[cmp_common] build_cmp_context {tkr_a} vs {tkr_b}")

    # ── Step 1 : reuse cache Streamlit si dispo ──────────────────────────
    _cached = None
    if not force_regenerate_llm:
        try:
            import streamlit as _st
            _cached = _st.session_state.get("_cmp_cache")
            if _cached:
                _cma = _cached.get("m_a", {}).get("ticker_a") or ""
                _cmb = _cached.get("m_b", {}).get("ticker_b") or ""
                if _cma.upper() != tkr_a.upper() or _cmb.upper() != tkr_b.upper():
                    _cached = None  # mismatch → invalidate
        except Exception:
            _cached = None

    if _cached:
        log.info("[cmp_common] cache hit — reuse supp/m/synthesis")
        supp_a = _cached["supp_a"]
        supp_b = _cached["supp_b"]
        m_a    = _cached["m_a"]
        m_b    = _cached["m_b"]
        synthesis = _cached["synthesis"]
    else:
        # ── Step 2 : fetch fresh ─────────────────────────────────────────
        # Audit perf 26/04/2026 — fetch_supplements A et B en parallele.
        # Avant : ~3s + 3s sequentiel. Apres : max(3, 3) = 3s. Gain ~3s.
        log.info("[cmp_common] cache miss — fresh fetch (parallel A/B)")
        from concurrent.futures import ThreadPoolExecutor as _CmpTPE
        with _CmpTPE(max_workers=2) as _ex_cmp:
            _f_a = _ex_cmp.submit(_fetch_supplements, tkr_a)
            _f_b = _ex_cmp.submit(_fetch_supplements, tkr_b)
            supp_a = _f_a.result()
            supp_b = _f_b.result()
        m_a = extract_metrics(state_a, supp_a)
        m_b = extract_metrics(state_b, supp_b)

        # Force les tickers corrects dans m_a/m_b pour la synthèse LLM
        m_a["ticker_a"] = tkr_a
        m_b["ticker_b"] = tkr_b
        m_a["company_name_a"] = m_a.get("company_name_a") or tkr_a
        m_b["company_name_b"] = m_b.get("company_name_b") or tkr_b

        # ── Step 3 : compute finsight winner (fallback si LLM neutre) ────
        fs_a_raw = m_a.get("finsight_score") or 0
        fs_b_raw = m_b.get("finsight_score") or 0
        if fs_a_raw != fs_b_raw:
            _fs_winner = tkr_a if fs_a_raw > fs_b_raw else tkr_b
        else:
            pio_a = m_a.get("piotroski_score") or 0
            pio_b = m_b.get("piotroski_score") or 0
            _fs_winner = tkr_a if pio_a >= pio_b else tkr_b
        m_a["winner"] = m_b["winner"] = _fs_winner

        # ── Step 4 : synthesis LLM (refonte #175 — LLM libre) ────────────
        if with_synthesis:
            from outputs.cmp_societe_pptx_writer import _generate_synthesis
            log.info("[cmp_common] generate synthesis LLM...")
            synthesis = _generate_synthesis(m_a, m_b)
        else:
            log.info("[cmp_common] skip synthesis LLM (with_synthesis=False)")
            synthesis = {}

    # ── Step 5 : strip markdown ──────────────────────────────────────────
    synthesis = _strip_md_dict(synthesis) if synthesis else {}

    # ── Step 6 : résolution winner finale (LLM prioritaire) ──────────────
    _llm_choice = synthesis.get("llm_choice") if isinstance(synthesis, dict) else None
    if _llm_choice in (tkr_a.upper(), tkr_b.upper()):
        winner = _llm_choice
        winner_source = "llm"
    elif _llm_choice == "NEUTRAL":
        winner = None
        winner_source = "llm_neutral"
    else:
        # Fallback au winner finsight déjà stocké dans m_a["winner"]
        winner = m_a.get("winner")
        winner_source = "finsight_fallback"

    # Sync m_a/m_b avec le winner final pour compat downstream (certains
    # writers lisent m_a["winner"] directement)
    m_a["winner"] = m_b["winner"] = winner
    m_a["winner_source"] = m_b["winner_source"] = winner_source

    # ── Step 7 : metadata d'identité ─────────────────────────────────────
    name_a = m_a.get("company_name_a") or tkr_a
    name_b = m_b.get("company_name_b") or tkr_b
    try:
        fs_a = int(m_a.get("finsight_score") or 0)
        fs_b = int(m_b.get("finsight_score") or 0)
    except (TypeError, ValueError):
        fs_a, fs_b = 0, 0

    log.info(
        f"[cmp_common] OK — {tkr_a}({fs_a}) vs {tkr_b}({fs_b}), "
        f"winner={winner} (source={winner_source})"
    )

    return CmpSocieteContext(
        tkr_a=tkr_a, tkr_b=tkr_b,
        name_a=name_a, name_b=name_b,
        m_a=m_a, m_b=m_b,
        supp_a=supp_a or {}, supp_b=supp_b or {},
        synthesis=synthesis,
        winner=winner,
        winner_source=winner_source,
        finsight_a=fs_a,
        finsight_b=fs_b,
    )
