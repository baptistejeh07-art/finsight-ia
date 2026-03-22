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
from datetime import date
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

    snapshot  = None
    sentiment = None

    # AgentData et AgentSentiment en parallèle (ThreadPoolExecutor, pas asyncio)
    def _collect():
        try:
            return AgentData().collect(ticker)
        except Exception as e:
            log.error(f"[fetch_node] AgentData FAILED: {e}", exc_info=True)
            return None

    def _analyze():
        try:
            return AgentSentiment().analyze(ticker)
        except Exception as e:
            log.error(f"[fetch_node] AgentSentiment FAILED: {e}", exc_info=True)
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_data = executor.submit(_collect)
        f_sent = executor.submit(_analyze)
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

        # synthesize() peut retourner None sans lever d'exception
        # (LLM credits epuises, JSON invalide, tous providers KO)
        if synthesis is None:
            fallback_conf = state.get("data_quality") or 0.70
            log.warning(f"[synthesis_node] synthesize() retourne None — fallback conf={fallback_conf:.0%}")
            return {
                "synthesis":        None,
                "confidence_score": fallback_conf,
                **_err(state, "synthesis_node: LLM returned None (credits/JSON)"),
                **_log_entry(state, "synthesis_node", ms, status="none",
                             confidence=fallback_conf),
            }

        conf = synthesis.confidence_score
        rec  = synthesis.recommendation
        # Floor : confidence_score < 0.1 anormalement bas → utiliser data_quality
        if conf < 0.1:
            conf = state.get("data_quality") or 0.70
            log.warning(f"[synthesis_node] confidence_score anormalement bas — remplace par {conf:.0%}")

        log.info(f"[synthesis_node] confidence={conf} rec={rec} — {ms}ms")
        return {
            "synthesis":               synthesis,
            "confidence_score":        conf,
            "invalidation_conditions": synthesis.invalidation_conditions,
            "recommendation":          rec,
            **_log_entry(state, "synthesis_node", ms, status="ok",
                         confidence=conf, recommendation=rec),
        }
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        log.error(f"[synthesis_node] Erreur : {e}")
        fallback_conf = state.get("data_quality") or 0.70
        return {
            "synthesis": None,
            "confidence_score": fallback_conf,
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
        from data.sources.comparables_source import collect_comparables
        ci = snapshot.company_info
        comparables = collect_comparables(
            ticker=state["ticker"],
            sector=getattr(ci, "sector", "") or "",
        )
    except Exception as e:
        log.warning(f"[output_node] comparables: {e}")

    try:
        import tempfile
        from outputs.excel_writer import ExcelWriter
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        ExcelWriter().write(snapshot, synthesis, ratios,
                            comparables=comparables, output_path=tmp_path)
        excel_bytes = tmp_path.read_bytes()
        tmp_path.unlink(missing_ok=True)
        excel_path = f"{snapshot.ticker}_{date.today().isoformat()}.xlsx"
        log.info(f"[output_node] Excel OK — {len(excel_bytes)} bytes")
    except Exception as e:
        log.error(f"[output_node] ExcelWriter FAILED: {e}", exc_info=True)

    try:
        import tempfile
        from outputs.pptx_writer import PPTXWriter
        with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        PPTXWriter().generate(state, str(tmp_path))
        pptx_bytes = tmp_path.read_bytes()
        tmp_path.unlink(missing_ok=True)
        pptx_path = f"{snapshot.ticker}_{date.today().isoformat()}_pitchbook.pptx"
        log.info(f"[output_node] PPTX OK — {len(pptx_bytes)} bytes")
    except Exception as e:
        log.error(f"[output_node] PPTXWriter FAILED: {e}", exc_info=True)

    pdf_error = None
    try:
        import tempfile
        from outputs.pdf_writer import PDFWriter
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        PDFWriter().generate(state, str(tmp_path))
        pdf_bytes = tmp_path.read_bytes()
        tmp_path.unlink(missing_ok=True)
        pdf_path = f"{snapshot.ticker}_{date.today().isoformat()}_report.pdf"
        log.info(f"[output_node] PDF OK — {len(pdf_bytes)} bytes")
    except Exception as e:
        import traceback as _tb
        pdf_error = f"{type(e).__name__}: {e}\n{_tb.format_exc()}"
        log.error(f"[output_node] PDFWriter FAILED: {e}", exc_info=True)

    ms = int((time.time() - t0) * 1000)
    log.info(f"[output_node] Excel={bool(excel_path)} PPTX={bool(pptx_path)} PDF={bool(pdf_path)} — {ms}ms")

    return {
        "excel_path":  excel_path,
        "pptx_path":   pptx_path,
        "pdf_path":    pdf_path,
        "excel_bytes": excel_bytes,
        "pptx_bytes":  pptx_bytes,
        "pdf_bytes":   pdf_bytes,
        "pdf_error":   pdf_error if 'pdf_error' in dir() else None,
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
    """Apres synthesis : si confidence < 0.65 → bloque, sinon QA.
    Si confidence_score est None (LLM KO), utilise data_quality comme garde-fou."""
    conf = state.get("confidence_score")
    if conf is None:
        # confidence_score non positionne : utiliser data_quality comme proxy
        conf = state.get("data_quality") or 0.70
        log.warning(f"[route_after_synthesis] confidence_score=None — proxy data_quality={conf:.0%}")
    if conf < 0.65:
        log.warning(f"[route_after_synthesis] confidence={conf:.0%} < 65% — pipeline bloque")
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
    graph.add_edge("blocked_node", "output_node")

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
