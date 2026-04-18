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
from datetime import datetime
from typing import Optional, Annotated

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
    return {"status": "ok", "service": "finsight-api", "ts": datetime.utcnow().isoformat()}


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


# ─── Analyse société ────────────────────────────────────────────────────────

@app.post("/analyze/societe", response_model=AnalyseResponse)
async def analyze_societe(
    req: SocieteRequest,
    background: BackgroundTasks,
    user: Annotated[Optional[dict], Depends(get_current_user)] = None,
):
    """Lance l'analyse complète d'une société.

    Mode synchrone : retourne le résultat complet (ratios, synthèse, fichiers).
    Pour analyses longues (>30s), le frontend devrait utiliser /analyze/societe/async.
    """
    import uuid
    request_id = str(uuid.uuid4())
    t0 = datetime.utcnow()

    try:
        # Import lazy pour ne pas charger tout au démarrage du serveur
        from cli_analyze import run_societe as _run_societe

        # Run l'analyse (fonction CLI existante — synchrone bloquante)
        # NB : c'est bloquant pendant 1-3 minutes par appel. Pour V1 acceptable
        # mais V2 → migrer en task celery/redis pour async vrai.
        log.info(f"[analyze/societe] {req.ticker} — request_id={request_id[:8]}")

        # Capture output dir avant l'appel
        from pathlib import Path
        outputs_dir = Path(_ROOT) / "outputs" / "generated" / "cli_tests"

        # On execute mais sans capturer stdout pour V1 — la vraie réponse
        # vient des fichiers générés
        _run_societe(req.ticker)

        # Récupère les fichiers générés
        ticker_safe = req.ticker.replace(".", "_")
        files = {}
        for ext, key in [("pdf", "pdf"), ("pptx", "pptx"), ("xlsx", "xlsx")]:
            f_path = outputs_dir / f"{req.ticker}_{'report' if ext == 'pdf' else 'pitchbook' if ext == 'pptx' else 'financials'}.{ext}"
            if f_path.exists():
                files[key] = str(f_path.relative_to(_ROOT))

        # Lit le state.json pour les données
        import json
        state_file = outputs_dir / f"{req.ticker}_state.json"
        data = {}
        if state_file.exists():
            try:
                with open(state_file, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                log.warning(f"state.json parse fail: {e}")

        elapsed = int((datetime.utcnow() - t0).total_seconds() * 1000)
        log.info(f"[analyze/societe] {req.ticker} OK en {elapsed}ms")

        return AnalyseResponse(
            success=True,
            request_id=request_id,
            elapsed_ms=elapsed,
            data=data,
            files=files,
        )
    except Exception as e:
        log.error(f"[analyze/societe] {req.ticker} FAIL: {e}", exc_info=True)
        return AnalyseResponse(
            success=False,
            request_id=request_id,
            elapsed_ms=int((datetime.utcnow() - t0).total_seconds() * 1000),
            error=str(e),
        )


@app.post("/analyze/secteur", response_model=AnalyseResponse)
async def analyze_secteur(
    req: SecteurRequest,
    user: Annotated[Optional[dict], Depends(get_current_user)] = None,
):
    """Lance l'analyse d'un secteur dans un univers."""
    import uuid
    request_id = str(uuid.uuid4())
    t0 = datetime.utcnow()
    try:
        from cli_analyze import run_secteur as _run_secteur
        log.info(f"[analyze/secteur] {req.secteur} / {req.univers} — {request_id[:8]}")
        _run_secteur(req.secteur, req.univers, prefix="secteur")

        # Récupère les fichiers générés
        outputs_dir = _ROOT / "outputs" / "generated" / "cli_tests"
        stem = f"secteur_{req.secteur.replace(' ', '_')}_{req.univers.replace(' ', '_')}"
        files = {}
        for ext in ("pdf", "pptx"):
            p = outputs_dir / f"{stem}.{ext}"
            if p.exists():
                files[ext] = str(p.relative_to(_ROOT))

        elapsed = int((datetime.utcnow() - t0).total_seconds() * 1000)
        return AnalyseResponse(
            success=True, request_id=request_id,
            elapsed_ms=elapsed, files=files,
        )
    except Exception as e:
        log.error(f"[analyze/secteur] FAIL: {e}", exc_info=True)
        return AnalyseResponse(
            success=False, request_id=request_id,
            elapsed_ms=int((datetime.utcnow() - t0).total_seconds() * 1000),
            error=str(e),
        )


@app.post("/analyze/indice", response_model=AnalyseResponse)
async def analyze_indice(
    req: IndiceRequest,
    user: Annotated[Optional[dict], Depends(get_current_user)] = None,
):
    """Lance l'analyse d'un indice complet (~5-8 min)."""
    import uuid
    request_id = str(uuid.uuid4())
    t0 = datetime.utcnow()
    try:
        from cli_analyze import run_indice as _run_indice
        log.info(f"[analyze/indice] {req.indice} — {request_id[:8]}")
        _run_indice(req.indice)

        # Récupère les fichiers générés
        outputs_dir = _ROOT / "outputs" / "generated" / "cli_tests"
        stem = f"indice_{req.indice.replace(' ', '_').replace('&', '')}"
        files = {}
        for ext in ("pdf", "pptx", "xlsx"):
            p = outputs_dir / f"{stem}.{ext}"
            if p.exists():
                files[ext] = str(p.relative_to(_ROOT))

        elapsed = int((datetime.utcnow() - t0).total_seconds() * 1000)
        return AnalyseResponse(
            success=True, request_id=request_id,
            elapsed_ms=elapsed, files=files,
        )
    except Exception as e:
        log.error(f"[analyze/indice] FAIL: {e}", exc_info=True)
        return AnalyseResponse(
            success=False, request_id=request_id,
            elapsed_ms=int((datetime.utcnow() - t0).total_seconds() * 1000),
            error=str(e),
        )


# ─── Comparaisons ───────────────────────────────────────────────────────────

@app.post("/cmp/societe", response_model=AnalyseResponse)
async def cmp_societe(req: CmpSocieteRequest):
    """Comparaison 2 sociétés : analyse A + B puis génère PDF/PPTX/XLSX comparatifs."""
    import uuid
    request_id = str(uuid.uuid4())
    t0 = datetime.utcnow()
    try:
        from core.graph import build_graph
        from outputs.cmp_societe_pptx_writer import CmpSocietePPTXWriter
        from outputs.cmp_societe_pdf_writer import CmpSocietePDFWriter
        from outputs.cmp_societe_xlsx_writer import CmpSocieteXlsxWriter

        log.info(f"[cmp/societe] {req.ticker_a} vs {req.ticker_b} — {request_id[:8]}")
        graph = build_graph()
        state_a = graph.invoke({"ticker": req.ticker_a})
        state_b = graph.invoke({"ticker": req.ticker_b})

        outputs_dir = _ROOT / "outputs" / "generated" / "cli_tests"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        stem = f"cmp_societe_{req.ticker_a}_vs_{req.ticker_b}".replace(".", "_")
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

        elapsed = int((datetime.utcnow() - t0).total_seconds() * 1000)
        return AnalyseResponse(
            success=bool(files), request_id=request_id,
            elapsed_ms=elapsed, files=files,
        )
    except Exception as e:
        log.error(f"[cmp/societe] FAIL: {e}", exc_info=True)
        return AnalyseResponse(
            success=False, request_id=request_id,
            elapsed_ms=int((datetime.utcnow() - t0).total_seconds() * 1000),
            error=str(e),
        )


@app.post("/cmp/secteur", response_model=AnalyseResponse)
async def cmp_secteur(req: CmpSecteurRequest):
    """Comparaison 2 secteurs."""
    import uuid
    request_id = str(uuid.uuid4())
    t0 = datetime.utcnow()
    try:
        from cli_analyze import run_cmp_secteur as _run_cmp
        log.info(f"[cmp/secteur] {req.secteur_a}/{req.univers_a} vs {req.secteur_b} — {request_id[:8]}")
        _run_cmp(req.secteur_a, req.univers_a, req.secteur_b, req.univers_b or req.univers_a)
        elapsed = int((datetime.utcnow() - t0).total_seconds() * 1000)
        return AnalyseResponse(success=True, request_id=request_id, elapsed_ms=elapsed)
    except Exception as e:
        return AnalyseResponse(
            success=False, request_id=request_id,
            elapsed_ms=int((datetime.utcnow() - t0).total_seconds() * 1000),
            error=str(e),
        )


@app.post("/cmp/indice", response_model=AnalyseResponse)
async def cmp_indice(req: CmpIndiceRequest):
    """Comparaison 2 indices."""
    import uuid
    request_id = str(uuid.uuid4())
    t0 = datetime.utcnow()
    return AnalyseResponse(
        success=False, request_id=request_id,
        elapsed_ms=int((datetime.utcnow() - t0).total_seconds() * 1000),
        error="cmp_indice not implemented yet (V1 stub)",
    )


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

    # Ticker direct (regex simple)
    import re
    if re.fullmatch(r"[A-Z0-9.\-]{1,12}", q_norm):
        return ResolveResponse(query=q, kind="societe", ticker=q_norm)

    # Fallback : LLM ticker resolution
    try:
        from data.sources.yfinance_source import _resolve_ticker_with_suffix
        ticker = _resolve_ticker_with_suffix(q)
        if ticker:
            return ResolveResponse(query=q, kind="societe", ticker=ticker)
    except Exception as e:
        log.warning(f"[resolve] LLM resolve fail: {e}")

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


# ─── Historique user (TODO V2) ──────────────────────────────────────────────

@app.get("/history")
async def get_history(user: Annotated[dict, Depends(require_user)]):
    """Historique des analyses du user connecté.

    V1 stub : retourne liste vide. V2 : query Supabase Postgres.
    """
    return {"user_id": user["id"], "history": []}


# ---------------------------------------------------------------------------
# Entrée locale
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
