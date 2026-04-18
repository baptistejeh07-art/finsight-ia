"""FastAPI backend FinSight IA — wrap des fonctions cli_analyze.

Lance localement :
    cd backend
    uvicorn main:app --reload --port 8000

Endpoints :
    GET  /health
    GET  /                          → info API
    POST /analyze/societe           → analyse 1 ticker (sync)
    POST /analyze/secteur           → analyse 1 secteur dans 1 univers
    POST /analyze/indice            → analyse 1 indice complet
    POST /cmp/societe               → comparaison 2 tickers
    POST /cmp/secteur               → comparaison 2 secteurs
    POST /cmp/indice                → comparaison 2 indices
    GET  /tickers/resolve/{query}   → résolution ticker via LLM
    GET  /me                        → user profile (auth requise)
    GET  /history                   → historique analyses du user (auth requise)
    GET  /file/{file_id}            → download fichier PDF/PPTX/XLSX

Auth :
    Header `Authorization: Bearer <JWT_SUPABASE>` pour endpoints user.
    Endpoints publics : /health, /, /analyze/* (mode invité 3/session)
"""

from __future__ import annotations
import os
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, Annotated


def _utcnow() -> datetime:
    """datetime UTC naïf — remplace datetime.utcnow() déprécié en Py 3.12+."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

# Ajoute le root du projet au PYTHONPATH pour importer cli_analyze, agents, etc.
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Charge .env du root
from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from fastapi import FastAPI, HTTPException, Header, Request, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field

import jobstore

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ---------------------------------------------------------------------------
# Lifespan : init/shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("[FastAPI] Démarrage backend FinSight IA")
    log.info(f"[FastAPI] Project root : {_ROOT}")
    yield
    log.info("[FastAPI] Arrêt backend")


# ---------------------------------------------------------------------------
# App FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FinSight IA API",
    description="Backend REST pour la plateforme d'analyse financière FinSight IA",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — autorise le frontend Vercel + dev local
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://finsight-ia.com",
        "https://www.finsight-ia.com",
        "https://finsight-ia.vercel.app",
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth helper — valide JWT Supabase
# ---------------------------------------------------------------------------

def get_current_user(authorization: Annotated[Optional[str], Header()] = None) -> Optional[dict]:
    """Valide le JWT Supabase et retourne le user dict, ou None si pas de token."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    try:
        # Validation locale du JWT via la clé publique Supabase
        # (pour MVP on fait juste un decode sans verification de signature ;
        # à durcir en V2 avec la clé publique Supabase)
        import jwt
        payload = jwt.decode(token, options={"verify_signature": False})
        return {
            "id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role", "authenticated"),
            "exp": payload.get("exp"),
        }
    except Exception as e:
        log.warning(f"[auth] JWT decode failed: {e}")
        return None


def require_user(user: Annotated[Optional[dict], Depends(get_current_user)]) -> dict:
    """Dépendance qui exige un utilisateur connecté."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentification requise")
    return user


# ---------------------------------------------------------------------------
# Models Pydantic
# ---------------------------------------------------------------------------

class SocieteRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20, description="Ticker yfinance (ex: AAPL, MC.PA)")
    devise: Optional[str] = Field("USD", description="Devise d'affichage")
    scope: Optional[str] = Field("interface", description="interface | files (PDF/PPTX inclus)")


class SecteurRequest(BaseModel):
    secteur: str = Field(..., description="Nom secteur (ex: Technology, Santé)")
    univers: str = Field(..., description="Univers (ex: S&P 500, CAC 40)")


class IndiceRequest(BaseModel):
    indice: str = Field(..., description="Nom indice (ex: CAC 40, FTSE 100)")


class CmpSocieteRequest(BaseModel):
    ticker_a: str
    ticker_b: str


class CmpSecteurRequest(BaseModel):
    secteur_a: str
    univers_a: str
    secteur_b: str
    univers_b: Optional[str] = None


class CmpIndiceRequest(BaseModel):
    indice_a: str
    indice_b: str


class AnalyseResponse(BaseModel):
    success: bool
    request_id: str
    elapsed_ms: int
    data: Optional[dict] = None
    files: Optional[dict] = None  # {pdf_url, pptx_url, xlsx_url}
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    """Healthcheck pour Railway."""
    return {"status": "ok", "service": "finsight-api", "ts": _utcnow().isoformat()}


@app.get("/")
def root():
    """Info API."""
    return {
        "name": "FinSight IA API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": [
            "/health",
            "/analyze/societe",
            "/analyze/secteur",
            "/analyze/indice",
            "/cmp/societe",
            "/cmp/secteur",
            "/cmp/indice",
            "/tickers/resolve/{query}",
            "/me",
            "/history",
        ],
    }


@app.get("/me")
def get_me(user: Annotated[dict, Depends(require_user)]):
    """Profil utilisateur connecté."""
    return user


# ─── Workers internes (réutilisés par sync + async) ─────────────────────────

def _upload_files_to_storage(files: dict, prefix: str) -> dict:
    """Upload chaque fichier vers Supabase Storage, retourne {ext: url}.

    Si Storage non configuré ou upload fail, garde les chemins relatifs locaux.
    `prefix` ex: 'societe/AAPL_20260418_103045' (sans extension).
    """
    import db as _db
    if not _db._enabled():
        return files
    from datetime import datetime as _dt
    ts = _dt.utcnow().strftime("%Y%m%d_%H%M%S")
    out = {}
    for ext, rel_path in files.items():
        local = _ROOT / rel_path
        remote = f"{prefix}_{ts}.{ext}"
        url = _db.upload_file(local, remote)
        out[ext] = url or rel_path
    return out



def _do_societe(ticker: str) -> dict:
    """Exécute l'analyse société + retourne {data, files}."""
    from cli_analyze import run_societe as _run_societe
    import json

    outputs_dir = _ROOT / "outputs" / "generated" / "cli_tests"
    _run_societe(ticker)

    files = {}
    for ext, label in [("pdf", "report"), ("pptx", "pitchbook"), ("xlsx", "financials")]:
        p = outputs_dir / f"{ticker}_{label}.{ext}"
        if p.exists():
            files[ext] = str(p.relative_to(_ROOT))

    data = {}
    state_file = outputs_dir / f"{ticker}_state.json"
    if state_file.exists():
        try:
            with open(state_file, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log.warning(f"state.json parse fail: {e}")
    files = _upload_files_to_storage(files, prefix=f"societe/{ticker}")
    return {"data": data, "files": files, "ticker": ticker}


def _do_portrait(ticker: str) -> dict:
    """Génère le Portrait d'entreprise PDF + retourne {data, files}."""
    from core.portrait import generate_portrait
    from outputs.portrait_pdf_writer import write_portrait_pdf

    outputs_dir = _ROOT / "outputs" / "generated" / "portraits"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    state = generate_portrait(ticker)
    pdf_path = outputs_dir / f"{ticker}_portrait.pdf"
    write_portrait_pdf(state, str(pdf_path))

    files = {}
    if pdf_path.exists():
        files["pdf"] = str(pdf_path.relative_to(_ROOT))
    files = _upload_files_to_storage(files, prefix=f"portrait/{ticker}")

    data = {
        "ticker": ticker,
        "company_name": state.context.name,
        "sections_count": sum(
            1 for v in [
                state.snapshot, state.history, state.vision, state.business_model,
                state.segments, state.leadership_intro, state.market, state.risks,
                state.strategy, state.devil_advocate, state.verdict,
            ] if v
        ),
        "warnings": state.warnings,
    }
    return {"data": data, "files": files, "ticker": ticker, "kind": "portrait"}


def _do_secteur(secteur: str, univers: str) -> dict:
    from cli_analyze import run_secteur as _run_secteur

    _run_secteur(secteur, univers, prefix="secteur")
    outputs_dir = _ROOT / "outputs" / "generated" / "cli_tests"
    stem = f"secteur_{secteur.replace(' ', '_')}_{univers.replace(' ', '_')}"
    files = {}
    for ext in ("pdf", "pptx"):
        p = outputs_dir / f"{stem}.{ext}"
        if p.exists():
            files[ext] = str(p.relative_to(_ROOT))
    files = _upload_files_to_storage(files, prefix=f"secteur/{stem}")
    return {"data": {}, "files": files}


def _do_indice(indice: str) -> dict:
    from cli_analyze import run_indice as _run_indice

    _run_indice(indice)
    outputs_dir = _ROOT / "outputs" / "generated" / "cli_tests"
    stem = f"indice_{indice.replace(' ', '_').replace('&', '')}"
    files = {}
    for ext in ("pdf", "pptx", "xlsx"):
        p = outputs_dir / f"{stem}.{ext}"
        if p.exists():
            files[ext] = str(p.relative_to(_ROOT))
    files = _upload_files_to_storage(files, prefix=f"indice/{stem}")
    return {"data": {}, "files": files}


def _do_cmp_societe(ticker_a: str, ticker_b: str) -> dict:
    from core.graph import build_graph
    from outputs.cmp_societe_pptx_writer import CmpSocietePPTXWriter
    from outputs.cmp_societe_pdf_writer import CmpSocietePDFWriter
    from outputs.cmp_societe_xlsx_writer import CmpSocieteXlsxWriter

    graph = build_graph()
    state_a = graph.invoke({"ticker": ticker_a})
    state_b = graph.invoke({"ticker": ticker_b})

    outputs_dir = _ROOT / "outputs" / "generated" / "cli_tests"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    stem = f"cmp_societe_{ticker_a}_vs_{ticker_b}".replace(".", "_")
    files = {}
    try:
        pdf_bytes = CmpSocietePDFWriter().generate_bytes(state_a, state_b)
        p = outputs_dir / f"{stem}.pdf"
        p.write_bytes(pdf_bytes)
        files["pdf"] = str(p.relative_to(_ROOT))
    except Exception as e:
        log.warning(f"[cmp/societe] PDF fail: {e}")
    try:
        pptx_bytes = CmpSocietePPTXWriter().generate_bytes(state_a, state_b)
        p = outputs_dir / f"{stem}.pptx"
        p.write_bytes(pptx_bytes)
        files["pptx"] = str(p.relative_to(_ROOT))
    except Exception as e:
        log.warning(f"[cmp/societe] PPTX fail: {e}")
    try:
        xlsx_bytes = CmpSocieteXlsxWriter().write(state_a, state_b)
        p = outputs_dir / f"{stem}.xlsx"
        p.write_bytes(xlsx_bytes)
        files["xlsx"] = str(p.relative_to(_ROOT))
    except Exception as e:
        log.warning(f"[cmp/societe] XLSX fail: {e}")

    # Snapshot company_info pour affichage frontend
    data = {
        "ticker_a": ticker_a,
        "ticker_b": ticker_b,
        "company_a": (state_a.get("snapshot") or {}).get("company_info", {}),
        "company_b": (state_b.get("snapshot") or {}).get("company_info", {}),
    }
    files = _upload_files_to_storage(files, prefix=f"cmp_societe/{stem}")
    return {"data": data, "files": files}


def _do_cmp_secteur(secteur_a: str, univers_a: str, secteur_b: str, univers_b: str) -> dict:
    from cli_analyze import run_cmp_secteur as _run_cmp

    _run_cmp(secteur_a, univers_a, secteur_b, univers_b)
    outputs_dir = _ROOT / "outputs" / "generated" / "cli_tests"
    stem = (
        f"cmp_secteur_{secteur_a.replace(' ', '_')}_{univers_a.replace(' ', '_')}"
        f"_vs_{secteur_b.replace(' ', '_')}_{univers_b.replace(' ', '_')}"
    )
    files = {}
    for ext in ("pdf", "pptx"):
        p = outputs_dir / f"{stem}.{ext}"
        if p.exists():
            files[ext] = str(p.relative_to(_ROOT))
    files = _upload_files_to_storage(files, prefix=f"cmp_secteur/{stem}")
    return {"data": {}, "files": files}


# ─── Helpers HTTP : wrap workers en réponse uniforme ────────────────────────

def _sync_response(kind: str, fn, *args, **kwargs) -> AnalyseResponse:
    import uuid
    request_id = str(uuid.uuid4())
    t0 = _utcnow()
    try:
        log.info(f"[{kind}] sync — {request_id[:8]}")
        result = fn(*args, **kwargs)
        elapsed = int((_utcnow() - t0).total_seconds() * 1000)
        return AnalyseResponse(
            success=True, request_id=request_id, elapsed_ms=elapsed,
            data=result.get("data"), files=result.get("files"),
        )
    except Exception as e:
        log.error(f"[{kind}] sync FAIL: {e}", exc_info=True)
        return AnalyseResponse(
            success=False, request_id=request_id,
            elapsed_ms=int((_utcnow() - t0).total_seconds() * 1000),
            error=str(e),
        )


# ─── Endpoints sync (V1 — bloquants, OK pour société rapide) ────────────────

@app.post("/analyze/societe", response_model=AnalyseResponse)
async def analyze_societe(req: SocieteRequest):
    """Analyse société synchrone (~1-3 min). Préférer /jobs/analyze/societe pour async."""
    return _sync_response("analyze/societe", _do_societe, req.ticker)


@app.post("/analyze/secteur", response_model=AnalyseResponse)
async def analyze_secteur(req: SecteurRequest):
    return _sync_response("analyze/secteur", _do_secteur, req.secteur, req.univers)


@app.post("/analyze/indice", response_model=AnalyseResponse)
async def analyze_indice(req: IndiceRequest):
    """⚠️ Bloquant 5-8 min — prefer /jobs/analyze/indice."""
    return _sync_response("analyze/indice", _do_indice, req.indice)


@app.post("/cmp/societe", response_model=AnalyseResponse)
async def cmp_societe(req: CmpSocieteRequest):
    return _sync_response("cmp/societe", _do_cmp_societe, req.ticker_a, req.ticker_b)


@app.post("/cmp/secteur", response_model=AnalyseResponse)
async def cmp_secteur(req: CmpSecteurRequest):
    return _sync_response(
        "cmp/secteur", _do_cmp_secteur,
        req.secteur_a, req.univers_a, req.secteur_b, req.univers_b or req.univers_a,
    )


@app.post("/cmp/indice", response_model=AnalyseResponse)
async def cmp_indice(req: CmpIndiceRequest):
    """Comparaison 2 indices — non implémenté V1."""
    import uuid
    return AnalyseResponse(
        success=False, request_id=str(uuid.uuid4()),
        elapsed_ms=0, error="cmp_indice not implemented yet (V1)",
    )


# ─── Endpoints async (jobs en mémoire) ──────────────────────────────────────

class JobSubmitResponse(BaseModel):
    job_id: str
    status: str
    kind: str


class JobStatusResponse(BaseModel):
    job_id: str
    kind: str
    status: str  # "queued" | "running" | "done" | "error"
    progress: int = 0
    progress_message: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


@app.post("/jobs/analyze/societe", response_model=JobSubmitResponse, status_code=202)
async def submit_societe(
    req: SocieteRequest,
    user: Annotated[Optional[dict], Depends(get_current_user)] = None,
):
    job_id = jobstore.submit(
        "analyze/societe", _do_societe, req.ticker,
        user_id=(user or {}).get("id"), label=req.ticker,
    )
    return JobSubmitResponse(job_id=job_id, status="queued", kind="analyze/societe")


@app.post("/jobs/analyze/secteur", response_model=JobSubmitResponse, status_code=202)
async def submit_secteur(
    req: SecteurRequest,
    user: Annotated[Optional[dict], Depends(get_current_user)] = None,
):
    job_id = jobstore.submit(
        "analyze/secteur", _do_secteur, req.secteur, req.univers,
        user_id=(user or {}).get("id"), label=f"{req.secteur} / {req.univers}",
    )
    return JobSubmitResponse(job_id=job_id, status="queued", kind="analyze/secteur")


@app.post("/jobs/analyze/indice", response_model=JobSubmitResponse, status_code=202)
async def submit_indice(
    req: IndiceRequest,
    user: Annotated[Optional[dict], Depends(get_current_user)] = None,
):
    job_id = jobstore.submit(
        "analyze/indice", _do_indice, req.indice,
        user_id=(user or {}).get("id"), label=req.indice,
    )
    return JobSubmitResponse(job_id=job_id, status="queued", kind="analyze/indice")


@app.post("/jobs/cmp/societe", response_model=JobSubmitResponse, status_code=202)
async def submit_cmp_societe(
    req: CmpSocieteRequest,
    user: Annotated[Optional[dict], Depends(get_current_user)] = None,
):
    job_id = jobstore.submit(
        "cmp/societe", _do_cmp_societe, req.ticker_a, req.ticker_b,
        user_id=(user or {}).get("id"), label=f"{req.ticker_a} vs {req.ticker_b}",
    )
    return JobSubmitResponse(job_id=job_id, status="queued", kind="cmp/societe")


class PortraitRequest(BaseModel):
    ticker: str


@app.post("/portrait/societe", response_model=JobSubmitResponse, status_code=202)
async def submit_portrait(
    req: PortraitRequest,
    user: Annotated[Optional[dict], Depends(get_current_user)] = None,
):
    """Génère un Portrait d'entreprise (PDF 15 pages). Async via jobstore."""
    job_id = jobstore.submit(
        "portrait/societe", _do_portrait, req.ticker,
        user_id=(user or {}).get("id"), label=f"Portrait {req.ticker}",
    )
    return JobSubmitResponse(job_id=job_id, status="queued", kind="portrait/societe")


@app.post("/jobs/cmp/secteur", response_model=JobSubmitResponse, status_code=202)
async def submit_cmp_secteur(
    req: CmpSecteurRequest,
    user: Annotated[Optional[dict], Depends(get_current_user)] = None,
):
    job_id = jobstore.submit(
        "cmp/secteur", _do_cmp_secteur,
        req.secteur_a, req.univers_a, req.secteur_b, req.univers_b or req.univers_a,
        user_id=(user or {}).get("id"),
        label=f"{req.secteur_a}/{req.univers_a} vs {req.secteur_b}/{req.univers_b or req.univers_a}",
    )
    return JobSubmitResponse(job_id=job_id, status="queued", kind="cmp/secteur")


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str):
    j = jobstore.get(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Job introuvable ou expiré")
    return JobStatusResponse(**j)


@app.get("/jobs")
async def list_jobs(limit: int = 50):
    """Debug : liste les N derniers jobs."""
    return {"jobs": jobstore.list_jobs(limit)}


# ─── Résolution tickers + classification requête ────────────────────────────

KNOWN_INDICES = {
    "CAC 40", "S&P 500", "SP500", "DAX 40", "DAX",
    "FTSE 100", "FTSE", "Euro Stoxx 50", "EUROSTOXX 50",
    "NASDAQ 100", "NASDAQ", "Dow Jones", "DJIA",
    "Nikkei 225", "Nikkei", "IBEX 35", "AEX",
}

KNOWN_SECTORS_FR = {
    "Technologie", "Sante", "Santé", "Banques", "Energie", "Énergie",
    "Industrie", "Industrials", "Luxe", "Luxury", "Immobilier",
    "Utilities", "Consumer", "Consommation", "Matieres premieres",
    "Materiaux", "Matériaux", "Telecoms", "Communication",
    "Financials", "Technology", "Healthcare", "Energy",
    "Real Estate", "Basic Materials", "Consumer Defensive",
    "Consumer Cyclical", "Communication Services", "Financial Services",
}


class ResolveResponse(BaseModel):
    query: str
    kind: str  # "societe" | "secteur" | "indice" | "unknown"
    ticker: Optional[str] = None
    universe: Optional[str] = None
    sector: Optional[str] = None


# ───────────────────────────────────────────────────────────────────────────
# Q&A chatbot (post-analyse) — multi-tour avec historique côté client.
# Le state du job est chargé pour fournir le contexte à l'LLM.
# ───────────────────────────────────────────────────────────────────────────

class QAMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class QARequest(BaseModel):
    job_id: str
    messages: list[QAMessage] = Field(default_factory=list)


class QAResponse(BaseModel):
    answer: str


def _build_qa_context(state: dict) -> str:
    """Résumé compact du state pour le contexte LLM."""
    if not isinstance(state, dict):
        return ""

    rd = state.get("raw_data") or {}
    ci = (rd.get("company_info") or {}) if isinstance(rd, dict) else {}
    syn = state.get("synthesis") or {}
    ratios = state.get("ratios") or {}
    latest_yr = ratios.get("latest_year")
    latest_ratios = (ratios.get("years") or {}).get(latest_yr, {}) if latest_yr else {}

    lines = []
    if ci:
        lines.append(f"Société : {ci.get('company_name','?')} ({ci.get('ticker','?')})")
        lines.append(f"Secteur : {ci.get('sector','?')} · Devise : {ci.get('currency','?')}")
    if syn:
        lines.append(f"Recommandation : {syn.get('recommendation','?')} · Conviction {syn.get('conviction','?')}")
        if syn.get('target_bull') or syn.get('target_base') or syn.get('target_bear'):
            lines.append(
                f"Cibles : Bull {syn.get('target_bull','?')} · Base {syn.get('target_base','?')} · Bear {syn.get('target_bear','?')}"
            )
        if syn.get('summary'):
            lines.append(f"Synthèse : {syn['summary'][:600]}")
        if syn.get('thesis'):
            lines.append(f"Thèse : {syn['thesis'][:400]}")
    if latest_ratios:
        keys = ['pe_ratio','ev_ebitda','ebitda_margin','net_margin','roe','roic','net_debt_ebitda','fcf_yield','revenue_growth','altman_z']
        bits = [f"{k}={latest_ratios[k]}" for k in keys if latest_ratios.get(k) is not None]
        if bits:
            lines.append(f"Ratios {latest_yr} : " + " · ".join(bits))
    peers = syn.get('comparable_peers') or []
    if peers:
        lines.append(
            "Peers : "
            + ", ".join(f"{p.get('ticker')} EV/EBITDA={p.get('ev_ebitda')}" for p in peers[:5])
        )
    return "\n".join(lines)


def _load_job_state(job_id: str) -> dict:
    """Charge le state d'un job done depuis jobstore (en mémoire)."""
    job = jobstore.get(job_id)
    if not job:
        raise HTTPException(404, "Job introuvable")
    if job.get("status") != "done":
        raise HTTPException(409, "Analyse pas encore terminée")
    result = job.get("result") or {}
    return (result.get("data") or {}) if isinstance(result, dict) else {}


@app.post("/qa", response_model=QAResponse)
async def qa_endpoint(req: QARequest):
    """Q&A multi-tour sur une analyse. L'historique est passé par le client."""
    state = _load_job_state(req.job_id)
    context = _build_qa_context(state)

    if not req.messages:
        raise HTTPException(400, "Aucun message")
    if req.messages[-1].role != "user":
        raise HTTPException(400, "Le dernier message doit être de l'utilisateur")

    # System prompt : analyste IA expert, français correct avec accents
    ticker = (state.get("ticker") or (state.get("raw_data") or {}).get("ticker") or "—")
    system = (
        "Tu es un analyste financier IA expert. Tu réponds aux questions de "
        "l'utilisateur sur l'analyse FinSight ci-dessous. Tu écris en français "
        "correct avec accents (é è ê à ç). Tu es factuel, concis (2-4 paragraphes "
        "max), tu cites les chiffres du contexte quand pertinent. Si la question "
        "sort du périmètre de l'analyse, tu le dis clairement.\n\n"
        f"=== Contexte analyse {ticker} ===\n{context}\n=== Fin contexte ==="
    )

    # Construit la conversation : historique + dernière question
    convo_lines = []
    for m in req.messages[:-1]:
        prefix = "Utilisateur" if m.role == "user" else "Assistant"
        convo_lines.append(f"{prefix}: {m.content}")
    convo_lines.append(f"Utilisateur: {req.messages[-1].content}")
    convo_lines.append("Assistant:")
    user_prompt = "\n".join(convo_lines)

    # Appel LLM (Groq par défaut → fallback Mistral / Anthropic en cas d'erreur)
    from core.llm_provider import LLMProvider
    answer = None
    last_err = None
    for prov, model in [
        ("groq", "llama-3.3-70b-versatile"),
        ("mistral", None),
        ("anthropic", None),
    ]:
        try:
            llm = LLMProvider(provider=prov, model=model)
            answer = llm.generate(user_prompt, system=system, max_tokens=800)
            if answer and answer.strip():
                break
        except Exception as e:
            last_err = e
            log.warning(f"[/qa] {prov} failed: {e}")
            continue

    if not answer:
        raise HTTPException(503, f"Tous les providers LLM ont échoué : {last_err}")

    return QAResponse(answer=answer.strip())


@app.get("/resolve/{query:path}", response_model=ResolveResponse)
async def resolve_query(query: str):
    """Classifie une requête en société/secteur/indice.

    Logique :
    - Si la requête matche un indice connu → kind=indice
    - Si la requête matche un secteur connu → kind=secteur (univers par défaut: S&P 500)
    - Sinon, tente une résolution ticker yfinance → kind=societe
    """
    q = query.strip()
    q_norm = q.upper().replace("&", "").replace("  ", " ")

    # Match indice
    for idx in KNOWN_INDICES:
        if idx.upper().replace("&", "") == q_norm or idx.lower() == q.lower():
            return ResolveResponse(query=q, kind="indice", universe=idx)

    # Match secteur
    for sec in KNOWN_SECTORS_FR:
        if sec.lower() == q.lower():
            return ResolveResponse(
                query=q, kind="secteur", sector=sec, universe="S&P 500"
            )

    # Ticker direct : forme courte typique en MAJUSCULES (1-6 lettres + suffixe .XX optionnel)
    # ex: AAPL, MSFT, MC.PA, ABBN.SW. Refuse les saisies en bas-de-casse pour éviter
    # de transformer "apple" en ticker "APPLE" (qui échouerait côté yfinance).
    import re
    is_upper = q == q.upper()
    if is_upper and re.fullmatch(r"[A-Z]{1,6}(\.[A-Z]{1,3})?", q_norm):
        return ResolveResponse(query=q, kind="societe", ticker=q_norm)

    # Fallback : résolution via yfinance_source (suffixes pays + validation fast_info)
    try:
        from data.sources.yfinance_source import _resolve_ticker_with_suffix
        ticker = _resolve_ticker_with_suffix(q)
        # _resolve_ticker_with_suffix retourne l'input inchangé si pas de match,
        # donc on valide ici : le ticker doit être différent OU contenir un suffixe
        if ticker and ticker != q and ("." in ticker or "-" in ticker):
            return ResolveResponse(query=q, kind="societe", ticker=ticker)
    except Exception as e:
        log.warning(f"[resolve] yfinance resolve fail: {e}")

    return ResolveResponse(query=q, kind="unknown")


@app.get("/tickers/resolve/{query}")
async def resolve_ticker(query: str):
    """Résout un nom (ex: 'apple', 'lvmh') vers un ticker yfinance via LLM."""
    try:
        from data.sources.yfinance_source import _resolve_ticker_with_suffix
        ticker = _resolve_ticker_with_suffix(query)
        return {"query": query, "ticker": ticker}
    except Exception as e:
        return {"query": query, "ticker": None, "error": str(e)}


# ─── Téléchargement fichiers ────────────────────────────────────────────────

@app.get("/file/{file_path:path}")
async def download_file(file_path: str):
    """Télécharge un fichier généré (PDF/PPTX/XLSX)."""
    full_path = _ROOT / file_path
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    # Vérifie qu'on ne sort pas du dossier outputs (sécurité)
    if "outputs/generated" not in str(full_path):
        raise HTTPException(status_code=403, detail="Accès refusé")
    return FileResponse(
        path=full_path,
        filename=full_path.name,
        media_type="application/octet-stream",
    )


# ─── Historique user ────────────────────────────────────────────────────────

@app.get("/history")
async def get_history(user: Annotated[dict, Depends(require_user)]):
    """Historique des analyses du user connecté.

    Persisté côté Supabase Postgres (table analyses_history). Si Supabase
    indispo ou table vide, fallback sur les jobs en mémoire de la session.
    """
    import db as _db

    persisted = _db.list_analyses(user["id"], limit=100)
    if persisted:
        return {
            "user_id": user["id"],
            "history": [
                {
                    "job_id": str(row.get("id", "")),
                    "kind": row.get("kind"),
                    "label": row.get("label"),
                    "ticker": row.get("ticker"),
                    "created_at": row.get("created_at"),
                    "finished_at": row.get("finished_at"),
                    "files": row.get("files"),
                }
                for row in persisted
            ],
        }

    # Fallback in-memory (session courante uniquement)
    jobs = jobstore.list_jobs(limit=100, user_id=user["id"])
    done = [j for j in jobs if j.get("status") == "done"]
    done.reverse()
    return {
        "user_id": user["id"],
        "history": [
            {
                "job_id": j["job_id"],
                "kind": j["kind"],
                "label": j.get("label"),
                "created_at": j["created_at"],
                "finished_at": j.get("finished_at"),
            }
            for j in done
        ],
    }


# ---------------------------------------------------------------------------
# Entrée locale
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
