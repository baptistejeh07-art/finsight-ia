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

    # Zone d'entree
    entry_zone: Optional[Any]

    # Outputs
    excel_path:  Optional[str]
    pdf_path:    Optional[str]
    pptx_path:   Optional[str]
    excel_bytes: Optional[bytes]
    pdf_bytes:   Optional[bytes]
    pptx_bytes:  Optional[bytes]
    pptx_error:  Optional[str]
    pdf_error:   Optional[str]

    # Monitoring
    data_quality: float        # 0.0–1.0 (confidence snapshot)
    errors:       list         # erreurs non-bloquantes accumulees
    logs:         list         # entrees de log structurees (pour Agent RH)
    blocked:      bool         # True si pipeline bloque (confidence < 0.65)

    # Paramètres utilisateur — devise d'affichage et portée de conversion
    display_currency: Optional[str]  # "USD" (défaut), "EUR", "GBP", etc.
    display_scope:    Optional[str]  # "interface" (UI seulement) | "all" (UI + PDF/PPTX)


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
        _lang = state.get("language") or "fr"
        synthesis = AgentSynthese(language=_lang).synthesize(snapshot, ratios, sentiment)
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
        # ROBUST-2 Baptiste 2026-04-14 : eleve conf = max(LLM auto-reporte,
        # data_quality). Un LLM prudent retournait 0.30-0.40 sur META malgre
        # un snapshot complete (data_quality >= 0.90). Le MAX evite de bloquer
        # a tort les mega-caps sur auto-evaluation conservatrice.
        _data_q = state.get("data_quality") or 0.0
        if _data_q and _data_q > conf:
            log.info(f"[synthesis_node] conf LLM={conf:.0%} ecrase par data_quality={_data_q:.0%}")
            conf = _data_q
        # Floor : confidence_score < 0.1 anormalement bas → utiliser data_quality
        if conf < 0.1:
            conf = _data_q or 0.70
            log.warning(f"[synthesis_node] confidence_score anormalement bas — remplace par {conf:.0%}")

        # Capture le provider qui a finalement réussi (info précieuse pour debug perf)
        meta = getattr(synthesis, "meta", None) or {}
        provider_used = meta.get("provider") or meta.get("provider_used") or "unknown"
        provider_errors = meta.get("provider_errors") or {}
        log.info(f"[synthesis_node] provider={provider_used} confidence={conf} rec={rec} — {ms}ms")
        return {
            "synthesis":               synthesis,
            "confidence_score":        conf,
            "invalidation_conditions": synthesis.invalidation_conditions,
            "recommendation":          rec,
            **_log_entry(state, "synthesis_node", ms, status="ok",
                         confidence=conf, recommendation=rec,
                         provider=provider_used,
                         providers_failed=list(provider_errors.keys())),
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
    """QA + Devil en parallele (Devil ne depend pas de QA, gain ~6-8s).

    AgentQAPython est rapide (deterministe) mais AgentQAHaiku + AgentDevil
    sont des appels LLM qui peuvent etre paralleles : ils ne se referencent
    pas mutuellement et lisent uniquement synthesis/ratios.
    """
    from agents.agent_qa_python import AgentQAPython
    from agents.agent_qa_haiku  import AgentQAHaiku
    from agents.agent_devil     import AgentDevil

    snapshot  = state.get("raw_data")
    ratios    = state.get("ratios")
    synthesis = state.get("synthesis")

    t0 = time.time()
    qa_python = qa_haiku = devil = None
    qa_passed = True

    # qa_python deterministe rapide → execute en main thread
    try:
        qa_python = AgentQAPython().validate(snapshot, ratios, synthesis)
    except Exception as e:
        log.warning(f"[qa_node] AgentQAPython erreur : {e}")

    # qa_haiku + devil = 2 LLM calls independants → ThreadPoolExecutor
    def _run_qa_haiku():
        try:
            return AgentQAHaiku().validate(synthesis, qa_python)
        except Exception as e:
            log.warning(f"[qa_node] AgentQAHaiku erreur : {e}")
            return None

    def _run_devil():
        try:
            return AgentDevil().challenge(synthesis, ratios)
        except Exception as e:
            log.warning(f"[qa_node] AgentDevil erreur : {e}")
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_haiku = executor.submit(_run_qa_haiku)
        f_devil = executor.submit(_run_devil)
        qa_haiku = f_haiku.result()
        devil    = f_devil.result()

    # Determiner si QA passe : pas d'erreur critique en QAPython
    if qa_python:
        flags = getattr(qa_python, "flags", []) or []
        errors = [f for f in flags if getattr(f, "level", "") == "ERROR"]
        if errors:
            qa_passed = False
            log.warning(f"[qa_node] {len(errors)} erreur(s) critique(s) QA")

    ms = int((time.time() - t0) * 1000)
    retries = state.get("qa_retries") or 0
    log.info(f"[qa_node] qa+devil parallel — {ms}ms")

    return {
        "qa_python":  qa_python,
        "qa_haiku":   qa_haiku,
        "devil":      devil,
        "qa_passed":  qa_passed,
        "qa_retries": retries,
        **_log_entry(state, "qa_node", ms,
                     status="ok" if qa_passed else "fail",
                     qa_passed=qa_passed, retries=retries),
    }


# ---------------------------------------------------------------------------
# NODE 5b — entry_zone_node : calcul zone d'entrée optimale
# ---------------------------------------------------------------------------

def entry_zone_node(state: FinSightState) -> dict:
    from agents.agent_entry_zone import AgentEntryZone

    snapshot  = state.get("raw_data")
    ratios    = state.get("ratios")
    synthesis = state.get("synthesis")
    qa_python = state.get("qa_python")
    sentiment = state.get("sentiment")

    t0 = time.time()
    try:
        entry_zone = AgentEntryZone().compute(
            snapshot, ratios, synthesis, qa_python, sentiment
        )
        ms = int((time.time() - t0) * 1000)
        sat = getattr(entry_zone, "satisfied_count", 0)
        log.info(f"[entry_zone_node] {sat}/5 conditions satisfaites — {ms}ms")
        return {
            "entry_zone": entry_zone,
            **_log_entry(state, "entry_zone_node", ms, status="ok",
                         satisfied_count=sat),
        }
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        log.error(f"[entry_zone_node] Erreur : {e}")
        return {
            "entry_zone": None,
            **_err(state, f"entry_zone_node: {e}"),
            **_log_entry(state, "entry_zone_node", ms, status="error"),
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
    pptx_error = None
    pdf_error = None

    # Comparables (bloquant car Excel en a besoin — 1-2s yfinance)
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

    # Parallélisation #194 : Excel + PPTX + PDF sont indépendants.
    # Avant : série 2s + 33s + 44s = 81s. Après : max(44) = 44s. Gain ~37s.
    import tempfile

    def _gen_excel():
        _t = time.time()
        try:
            from outputs.excel_writer import ExcelWriter
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            ExcelWriter().write(snapshot, synthesis, ratios,
                                comparables=comparables, output_path=tmp_path)
            data = tmp_path.read_bytes()
            tmp_path.unlink(missing_ok=True)
            _ms = int((time.time() - _t) * 1000)
            log.info(f"[output_node] Excel OK — {len(data)} bytes — {_ms}ms")
            return (data, None, _ms)
        except Exception as e:
            _ms = int((time.time() - _t) * 1000)
            log.error(f"[output_node] ExcelWriter FAILED: {e}", exc_info=True)
            return (None, f"{type(e).__name__}: {e}", _ms)

    def _gen_pptx():
        _t = time.time()
        try:
            from outputs.pptx_writer import PPTXWriter
            with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            PPTXWriter().generate(state, str(tmp_path))
            data = tmp_path.read_bytes()
            tmp_path.unlink(missing_ok=True)
            _ms = int((time.time() - _t) * 1000)
            log.info(f"[output_node] PPTX OK — {len(data)} bytes — {_ms}ms")
            return (data, None, _ms)
        except Exception as e:
            _ms = int((time.time() - _t) * 1000)
            import traceback as _tb2
            log.error(f"[output_node] PPTXWriter FAILED: {e}", exc_info=True)
            return (None, f"{type(e).__name__}: {e}\n{_tb2.format_exc()}", _ms)

    def _gen_pdf():
        _t = time.time()
        try:
            from outputs.pdf_writer import PDFWriter
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            PDFWriter().generate(state, str(tmp_path))
            data = tmp_path.read_bytes()
            tmp_path.unlink(missing_ok=True)
            _ms = int((time.time() - _t) * 1000)
            log.info(f"[output_node] PDF OK — {len(data)} bytes — {_ms}ms")
            return (data, None, _ms)
        except Exception as e:
            _ms = int((time.time() - _t) * 1000)
            import traceback as _tb
            log.error(f"[output_node] PDFWriter FAILED: {e}", exc_info=True)
            return (None, f"{type(e).__name__}: {e}\n{_tb.format_exc()}", _ms)

    with ThreadPoolExecutor(max_workers=3) as executor:
        f_excel = executor.submit(_gen_excel)
        f_pptx  = executor.submit(_gen_pptx)
        f_pdf   = executor.submit(_gen_pdf)
        excel_bytes, _excel_err, excel_ms = f_excel.result()
        pptx_bytes,  pptx_error, pptx_ms  = f_pptx.result()
        pdf_bytes,   pdf_error,  pdf_ms   = f_pdf.result()

    # Paths logiques (pas physiques — les bytes sont dans state)
    today_iso = date.today().isoformat()
    if excel_bytes is not None:
        excel_path = f"{snapshot.ticker}_{today_iso}.xlsx"
    if pptx_bytes is not None:
        pptx_path = f"{snapshot.ticker}_{today_iso}_pitchbook.pptx"
    if pdf_bytes is not None:
        pdf_path = f"{snapshot.ticker}_{today_iso}_report.pdf"

    ms = int((time.time() - t0) * 1000)
    log.info(f"[output_node] Excel={bool(excel_path)} PPTX={bool(pptx_path)} PDF={bool(pdf_path)} — {ms}ms")

    return {
        "excel_path":  excel_path,
        "pptx_path":   pptx_path,
        "pdf_path":    pdf_path,
        "excel_bytes": excel_bytes,
        "pptx_bytes":  pptx_bytes,
        "pdf_bytes":   pdf_bytes,
        "pptx_error":  pptx_error,
        "pdf_error":   pdf_error,
        **_log_entry(state, "output_node", ms,
                     excel=bool(excel_path), pptx=bool(pptx_path), pdf=bool(pdf_path),
                     excel_ms=excel_ms, pptx_ms=pptx_ms, pdf_ms=pdf_ms),
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
    """Apres synthesis : si confidence < 0.45 -> bloque, sinon QA.

    ROBUST-2 Baptiste 2026-04-14 : META (mega-cap US complete) etait bloque
    alors que data_quality etait a 0.95+. Cause : le LLM reportait un
    confidence_score auto-evalue trop prudent (0.30-0.40). Correction :
    on prend le MAX entre le confidence LLM auto-reporte et data_quality,
    parce qu'une snapshot complete est par construction fiable meme si
    le LLM a ete conservateur dans son auto-evaluation.
    """
    llm_conf = state.get("confidence_score")
    data_q   = state.get("data_quality") or 0.0
    if llm_conf is None:
        effective_conf = data_q or 0.70
        log.warning(f"[route_after_synthesis] confidence_score=None — proxy data_quality={effective_conf:.0%}")
    else:
        effective_conf = max(float(llm_conf), float(data_q))
        if effective_conf > llm_conf:
            log.info(f"[route_after_synthesis] llm_conf={llm_conf:.0%} ecrase par data_quality={data_q:.0%}")
    if effective_conf < 0.45:
        log.warning(f"[route_after_synthesis] confidence={effective_conf:.0%} < 45% — pipeline bloque")
        return "blocked_node"
    return "qa_node"


def route_after_qa(state: FinSightState) -> str:
    """Apres QA : route directement vers entry_zone (retry désactivé #194).

    Historique : le retry synthesis était déclenché si QAPython trouvait un
    flag ERROR. En pratique, le 2e call synthesis produit EXACTEMENT la même
    sortie (mêmes inputs snapshot/ratios/sentiment → même recommendation,
    même conviction, même target), donc le retry coûte ~20s pour zéro gain.

    Le retry reste bloqué derrière un seuil confidence très bas (<20%),
    cas pathologique où la synthèse est probablement corrompue. Sur les cas
    courants (mega-caps avec 6 flags QA récurrents), on skip le retry.
    """
    synthesis = state.get("synthesis")
    if synthesis is not None:
        conf = getattr(synthesis, "confidence_score", None) or 0
        if conf < 0.20:
            retries = state.get("qa_retries") or 0
            if retries < 1:
                log.warning(
                    f"[route_after_qa] confidence={conf:.0%} anormalement bas "
                    f"— retry synthesis (1/1)"
                )
                return "synthesis_retry"
    return "entry_zone_node"


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
    graph.add_node("qa_node",          qa_node)
    graph.add_node("entry_zone_node",  entry_zone_node)
    graph.add_node("devil_node",       devil_node)
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
            "synthesis_retry":  "synthesis_retry",
            "entry_zone_node":  "entry_zone_node",
        },
    )
    graph.add_edge("synthesis_retry",  "qa_node")
    # devil_node desormais execute en parallele dans qa_node (gain ~6-8s)
    graph.add_edge("entry_zone_node",  "output_node")
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
