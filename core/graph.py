# =============================================================================
# FinSight IA — LangGraph Pipeline
# core/graph.py
#
# Transforme la pipeline sequentielle en graphe avec edges conditionnels.
#
# Flux :
#   START
#     └─ fetch_node  (data + sentiment PARALLEL via asyncio)
#          ├─ data_quality < 0.7 ──> fallback_node ──> quant_node
#          └─ data_quality >= 0.7 ──────────────────> quant_node
#               └─ synthesis_node
#                    ├─ confidence < 0.65 ──> END (bloque, Article 1)
#                    └─ confidence >= 0.65 ──> qa_node
#                         ├─ QA echec + retries < 1 ──> synthesis_node (retry)
#                         └─ OK ──> devil_node ──> output_node ──> END
#
# Usage :
#   from core.graph import build_graph
#   graph  = build_graph()
#   result = graph.invoke({"ticker": "TSLA"})
# =============================================================================

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FinSightState — etat partage entre tous les noeuds
# ---------------------------------------------------------------------------

class FinSightState(TypedDict, total=False):
    # Input
    ticker: str

    # Donnees brutes
    raw_data:  Optional[Any]   # FinancialSnapshot
    sentiment: Optional[Any]   # SentimentResult

    # Ratios
    ratios: Optional[Any]      # RatiosResult

    # Synthese
    synthesis:               Optional[Any]    # SynthesisResult
    confidence_score:        Optional[float]
    invalidation_conditions: Optional[str]
    recommendation:          Optional[str]

    # QA
    qa_python:  Optional[Any]
    qa_haiku:   Optional[Any]
    qa_passed:  bool
    qa_retries: int            # compteur retry synthesis (max 1)

    # Devil
    devil: Optional[Any]

    # Outputs
    excel_path:  Optional[str]
    pdf_path:    Optional[str]
    pptx_path:   Optional[str]
    excel_bytes: Optional[bytes]
    pdf_bytes:   Optional[bytes]
    pptx_bytes:  Optional[bytes]

    # Monitoring
    data_quality: float        # 0.0–1.0 (confidence snapshot)
    errors:       list         # erreurs non-bloquantes accumulees
    logs:         list         # entrees de log structurees (pour Agent RH)
    blocked:      bool         # True si pipeline bloque (confidence < 0.65)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _err(state: FinSightState, msg: str) -> dict:
    errs = list(state.get("errors") or [])
    errs.append(msg)
    return {"errors": errs}


def _log_entry(state: FinSightState, node: str, latency_ms: int, **kw) -> dict:
    entries = list(state.get("logs") or [])
    entries.append({"node": node, "latency_ms": latency_ms, **kw})
    return {"logs": entries}


# ---------------------------------------------------------------------------
# NODE 1 — fetch_node : data + sentiment en parallele
# ---------------------------------------------------------------------------

def fetch_node(state: FinSightState) -> dict:
    """
    Lance AgentData et AgentSentiment en parallele via ThreadPoolExecutor.
    N'utilise pas asyncio.run() pour rester compatible avec la boucle Streamlit.
    """
    from agents.agent_data      import AgentData
    from agents.agent_sentiment import AgentSentiment

    ticker = state["ticker"]
    t0     = time.time()

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_data = pool.submit(AgentData().collect, ticker)
        f_sent = pool.submit(AgentSentiment().analyze, ticker)
        snapshot  = f_data.result()
        sentiment = f_sent.result()

    ms = int((time.time() - t0) * 1000)

    if snapshot is None:
        log.error(f"[fetch_node] Aucune donnee pour {ticker}")
        return {
            "raw_data":    None,
            "sentiment":   sentiment,
            "data_quality": 0.0,
            **_err(state, f"AgentData returned None for {ticker}"),
            **_log_entry(state, "fetch_node", ms, status="error"),
        }

    quality = float(snapshot.meta.get("confidence_score", 0.0)) if snapshot.meta else 0.0
    log.info(f"[fetch_node] {ticker} — data_quality={quality:.0%} — {ms}ms")

    return {
        "raw_data":    snapshot,
        "sentiment":   sentiment,
        "data_quality": quality,
        "errors":      list(state.get("errors") or []),
        **_log_entry(state, "fetch_node", ms,
                     status="ok", data_quality=quality,
                     sentiment_ok=sentiment is not None),
    }


# ---------------------------------------------------------------------------
# NODE 2 — fallback_node : tente FMP / Finnhub si data_quality < 0.7
# ---------------------------------------------------------------------------

def fallback_node(state: FinSightState) -> dict:
    """
    Tente d'enrichir le snapshot via FMP ou Finnhub.
    Ne bloque pas si echec — pipeline continue avec les donnees existantes.
    """
    from agents.agent_data import AgentData

    ticker = state["ticker"]
    t0 = time.time()
    log.warning(f"[fallback_node] data_quality={state.get('data_quality'):.0%} < 0.7 — tentative enrichissement")

    try:
        # AgentData a deja un mecanisme fallback interne (yfinance > FMP > Finnhub)
        # On le relance avec force_refresh pour tenter les sources secondaires
        agent    = AgentData()
        snapshot = agent.collect(ticker)
        quality  = float(snapshot.meta.get("confidence_score", 0.0)) if snapshot and snapshot.meta else 0.0
        ms = int((time.time() - t0) * 1000)
        log.info(f"[fallback_node] Apres fallback : data_quality={quality:.0%}")
        return {
            "raw_data":    snapshot if snapshot else state.get("raw_data"),
            "data_quality": quality,
            **_log_entry(state, "fallback_node", ms, status="ok", new_quality=quality),
        }
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        log.error(f"[fallback_node] Echec : {e}")
        return {
            **_err(state, f"fallback_node error: {e}"),
            **_log_entry(state, "fallback_node", ms, status="error"),
        }


# ---------------------------------------------------------------------------
# NODE 3 — quant_node
# ---------------------------------------------------------------------------

def quant_node(state: FinSightState) -> dict:
    from agents.agent_quant import AgentQuant

    snapshot = state.get("raw_data")
    if snapshot is None:
        return {**_err(state, "quant_node: snapshot manquant")}

    t0 = time.time()
    try:
        ratios = AgentQuant().compute(snapshot)
        ms = int((time.time() - t0) * 1000)
        log.info(f"[quant_node] {len(ratios.years)} annees de ratios — {ms}ms")
        return {
            "ratios": ratios,
            **_log_entry(state, "quant_node", ms, status="ok",
                         years=len(ratios.years)),
        }
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        log.error(f"[quant_node] Erreur : {e}")
        return {
            "ratios": None,
            **_err(state, f"quant_node: {e}"),
            **_log_entry(state, "quant_node", ms, status="error"),
        }


# ---------------------------------------------------------------------------
# NODE 4 — synthesis_node
# ---------------------------------------------------------------------------

def synthesis_node(state: FinSightState) -> dict:
    from agents.agent_synthese import AgentSynthese

    snapshot  = state.get("raw_data")
    ratios    = state.get("ratios")
    sentiment = state.get("sentiment")

    if not snapshot or not ratios:
        return {**_err(state, "synthesis_node: donnees insuffisantes")}

    t0 = time.time()
    try:
        synthesis = AgentSynthese().synthesize(snapshot, ratios, sentiment)
        ms = int((time.time() - t0) * 1000)
        conf = getattr(synthesis, "confidence_score", None)
        rec  = getattr(synthesis, "recommendation", None)
        log.info(f"[synthesis_node] confidence={conf} rec={rec} — {ms}ms")
        return {
            "synthesis":               synthesis,
            "confidence_score":        conf,
            "invalidation_conditions": getattr(synthesis, "invalidation_conditions", None),
            "recommendation":          rec,
            **_log_entry(state, "synthesis_node", ms, status="ok",
                         confidence=conf, recommendation=rec),
        }
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        log.error(f"[synthesis_node] Erreur : {e}")
        return {
            "synthesis": None,
            "confidence_score": 0.0,
            **_err(state, f"synthesis_node: {e}"),
            **_log_entry(state, "synthesis_node", ms, status="error"),
        }


# ---------------------------------------------------------------------------
# NODE 5 — qa_node : AgentQAPython + AgentQAHaiku en parallele
# ---------------------------------------------------------------------------

def qa_node(state: FinSightState) -> dict:
    from agents.agent_qa_python import AgentQAPython
    from agents.agent_qa_haiku  import AgentQAHaiku

    snapshot  = state.get("raw_data")
    ratios    = state.get("ratios")
    synthesis = state.get("synthesis")

    t0 = time.time()
    qa_python = qa_haiku = None
    qa_passed = True

    try:
        qa_python = AgentQAPython().validate(snapshot, ratios, synthesis)
    except Exception as e:
        log.warning(f"[qa_node] AgentQAPython erreur : {e}")

    try:
        qa_haiku = AgentQAHaiku().validate(synthesis, qa_python)
    except Exception as e:
        log.warning(f"[qa_node] AgentQAHaiku erreur : {e}")

    # Determiner si QA passe : pas d'erreur critique en QAPython
    if qa_python:
        flags = getattr(qa_python, "flags", []) or []
        errors = [f for f in flags if getattr(f, "level", "") == "ERROR"]
        if errors:
            qa_passed = False
            log.warning(f"[qa_node] {len(errors)} erreur(s) critique(s) QA")

    ms = int((time.time() - t0) * 1000)
    retries = state.get("qa_retries") or 0

    return {
        "qa_python":  qa_python,
        "qa_haiku":   qa_haiku,
        "qa_passed":  qa_passed,
        "qa_retries": retries,
        **_log_entry(state, "qa_node", ms,
                     status="ok" if qa_passed else "fail",
                     qa_passed=qa_passed, retries=retries),
    }


# ---------------------------------------------------------------------------
# NODE 6 — devil_node
# ---------------------------------------------------------------------------

def devil_node(state: FinSightState) -> dict:
    from agents.agent_devil import AgentDevil

    synthesis = state.get("synthesis")
    ratios    = state.get("ratios")

    t0 = time.time()
    try:
        devil = AgentDevil().challenge(synthesis, ratios)
        ms    = int((time.time() - t0) * 1000)
        log.info(f"[devil_node] conviction_delta={getattr(devil, 'conviction_delta', None)} — {ms}ms")
        return {
            "devil": devil,
            **_log_entry(state, "devil_node", ms, status="ok",
                         conviction_delta=getattr(devil, "conviction_delta", None)),
        }
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        log.error(f"[devil_node] Erreur : {e}")
        return {
            "devil": None,
            **_err(state, f"devil_node: {e}"),
            **_log_entry(state, "devil_node", ms, status="error"),
        }


# ---------------------------------------------------------------------------
# NODE 7 — output_node : Excel + PPTX + PDF
# ---------------------------------------------------------------------------

def output_node(state: FinSightState) -> dict:
    from outputs.excel_writer import ExcelWriter
    from outputs.pptx_builder import PPTXBuilder
    from outputs.pdf_report   import generate_pdf
    from data.sources.comparables_source import collect_comparables

    snapshot  = state.get("raw_data")
    ratios    = state.get("ratios")
    synthesis = state.get("synthesis")
    qa_python = state.get("qa_python")
    devil     = state.get("devil")

    t0 = time.time()
    excel_path = pptx_path = pdf_path = None
    excel_bytes = pptx_bytes = pdf_bytes = None

    # Comparables
    comparables = None
    try:
        ci = snapshot.company_info
        comparables = collect_comparables(
            ticker=state["ticker"],
            sector=getattr(ci, "sector", "") or "",
        )
    except Exception as e:
        log.warning(f"[output_node] comparables: {e}")

    try:
        p = ExcelWriter().write(snapshot, synthesis, ratios, comparables=comparables)
        excel_path  = str(p)
        excel_bytes = Path(p).read_bytes()
    except Exception as e:
        log.error(f"[output_node] ExcelWriter FAILED: {e}", exc_info=True)

    try:
        p = PPTXBuilder().build(snapshot, ratios, synthesis, qa_python, devil)
        pptx_path  = str(p)
        pptx_bytes = Path(p).read_bytes()
    except Exception as e:
        log.error(f"[output_node] PPTXBuilder FAILED: {e}", exc_info=True)

    try:
        p = generate_pdf(snapshot, ratios, synthesis,
                         state.get("sentiment"), qa_python, devil)
        pdf_path  = str(p)
        pdf_bytes = Path(p).read_bytes()
    except Exception as e:
        log.error(f"[output_node] PDFReport FAILED: {e}", exc_info=True)

    ms = int((time.time() - t0) * 1000)
    log.info(f"[output_node] Excel={bool(excel_path)} PPTX={bool(pptx_path)} PDF={bool(pdf_path)} — {ms}ms")

    return {
        "excel_path":  excel_path,
        "pptx_path":   pptx_path,
        "pdf_path":    pdf_path,
        "excel_bytes": excel_bytes,
        "pptx_bytes":  pptx_bytes,
        "pdf_bytes":   pdf_bytes,
        **_log_entry(state, "output_node", ms,
                     excel=bool(excel_path), pptx=bool(pptx_path), pdf=bool(pdf_path)),
    }


# ---------------------------------------------------------------------------
# NODE bloque — Article 1 Constitution : confidence < 0.65
# ---------------------------------------------------------------------------

def blocked_node(state: FinSightState) -> dict:
    conf = state.get("confidence_score") or 0.0
    msg  = (f"[Constitution Article 1] Pipeline bloque : "
            f"confidence_score={conf:.0%} < 65% — output interdit")
    log.warning(msg)
    return {
        "blocked": True,
        **_err(state, msg),
        **_log_entry(state, "blocked_node", 0,
                     status="blocked", confidence=conf),
    }


# ---------------------------------------------------------------------------
# Routing functions (edges conditionnels)
# ---------------------------------------------------------------------------

def route_after_fetch(state: FinSightState) -> str:
    """Apres fetch : si data manquante ou qualite < 0.7 → fallback."""
    if state.get("raw_data") is None:
        return END          # pas de donnees du tout — abandon
    if (state.get("data_quality") or 0.0) < 0.7:
        return "fallback_node"
    return "quant_node"


def route_after_synthesis(state: FinSightState) -> str:
    """Apres synthesis : si synthesis None → END, si confidence < 0.65 → bloque."""
    if state.get("synthesis") is None:
        return END   # synthesis a completement echoue
    conf = state.get("confidence_score") or 0.0
    if conf < 0.65:
        return "blocked_node"
    return "qa_node"


def route_after_qa(state: FinSightState) -> str:
    """Apres QA : si echec + retries < 1 → retry synthesis, sinon continuer."""
    if not state.get("qa_passed", True):
        retries = state.get("qa_retries") or 0
        if retries < 1:
            log.warning("[route_after_qa] QA echec — retry synthesis (1/1)")
            # Incrementer le compteur avant de retourner
            return "synthesis_retry"
    return "devil_node"


# ---------------------------------------------------------------------------
# Construction du graphe
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """
    Construit et compile le graphe LangGraph FinSight.
    """
    graph = StateGraph(FinSightState)

    # Noeuds
    graph.add_node("fetch_node",      fetch_node)
    graph.add_node("fallback_node",   fallback_node)
    graph.add_node("quant_node",      quant_node)
    graph.add_node("synthesis_node",  synthesis_node)
    graph.add_node("synthesis_retry", _synthesis_retry_node)
    graph.add_node("qa_node",         qa_node)
    graph.add_node("devil_node",      devil_node)
    graph.add_node("output_node",     output_node)
    graph.add_node("blocked_node",    blocked_node)

    # Point d'entree
    graph.set_entry_point("fetch_node")

    # Edges conditionnels
    graph.add_conditional_edges(
        "fetch_node",
        route_after_fetch,
        {
            "fallback_node": "fallback_node",
            "quant_node":    "quant_node",
            END:              END,
        },
    )
    graph.add_edge("fallback_node", "quant_node")
    graph.add_edge("quant_node",    "synthesis_node")

    graph.add_conditional_edges(
        "synthesis_node",
        route_after_synthesis,
        {
            "blocked_node": "blocked_node",
            "qa_node":      "qa_node",
            END:             END,
        },
    )
    graph.add_edge("blocked_node", END)

    graph.add_conditional_edges(
        "qa_node",
        route_after_qa,
        {
            "synthesis_retry": "synthesis_retry",
            "devil_node":      "devil_node",
        },
    )
    graph.add_edge("synthesis_retry", "qa_node")
    graph.add_edge("devil_node",      "output_node")
    graph.add_edge("output_node",     END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Node interne : synthesis retry (incremente le compteur avant de re-synthétiser)
# ---------------------------------------------------------------------------

def _synthesis_retry_node(state: FinSightState) -> dict:
    """Incremente qa_retries puis re-execute synthesis_node."""
    retries = (state.get("qa_retries") or 0) + 1
    log.info(f"[synthesis_retry] Retry {retries}/1")
    # On met a jour le compteur puis synthesis_node sera appele via l'edge
    result = {"qa_retries": retries}
    result.update(synthesis_node(state))
    return result


# ---------------------------------------------------------------------------
# Entrypoint direct
# ---------------------------------------------------------------------------

def run(ticker: str, verbose: bool = True) -> FinSightState:
    """Lance le graphe sur un ticker et retourne l'etat final."""
    if verbose:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)-8s %(message)s",
            datefmt="%H:%M:%S",
        )

    graph  = build_graph()
    t0     = time.time()
    result = graph.invoke({"ticker": ticker, "errors": [], "logs": [], "qa_retries": 0})
    elapsed = int((time.time() - t0) * 1000)

    log.info(f"\n{'='*60}")
    log.info(f"  FinSight Graph — {ticker} termine en {elapsed/1000:.1f}s")
    log.info(f"  Recommandation : {result.get('recommendation')}")
    log.info(f"  Confidence     : {result.get('confidence_score', 0):.0%}")
    log.info(f"  Data quality   : {result.get('data_quality', 0):.0%}")
    log.info(f"  Bloque         : {result.get('blocked', False)}")
    log.info(f"  Erreurs        : {result.get('errors', [])}")
    log.info(f"  Excel          : {result.get('excel_path')}")
    log.info(f"{'='*60}")

    return result
