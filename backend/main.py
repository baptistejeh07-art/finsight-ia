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

# Public API v1 router (sous /api/v1/*, auth par clé X-API-Key)
try:
    from backend.api_v1 import router as api_v1_router
    app.include_router(api_v1_router)
except Exception as _e:
    import logging as _lg
    _lg.getLogger(__name__).warning(f"[startup] api_v1 import failed: {_e}")

# Routers extraits (progressive refactor #154)
try:
    from backend.routers.share import router as share_router
    app.include_router(share_router)
except Exception as _e:
    import logging as _lg
    _lg.getLogger(__name__).warning(f"[startup] share router import failed: {_e}")

try:
    from backend.routers.api_keys import router as api_keys_router
    app.include_router(api_keys_router)
except Exception as _e:
    import logging as _lg
    _lg.getLogger(__name__).warning(f"[startup] api_keys router import failed: {_e}")

try:
    from backend.routers.sentinel import router as sentinel_router
    app.include_router(sentinel_router)
except Exception as _e:
    import logging as _lg
    _lg.getLogger(__name__).warning(f"[startup] sentinel router import failed: {_e}")

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


def require_not_banned(user: Annotated[dict, Depends(require_user)]) -> dict:
    """Bloque les users bannis. À utiliser sur tous les /analyze/*."""
    import httpx as _httpx
    import os as _os
    _surl = _os.getenv("SUPABASE_URL", "").rstrip("/")
    _skey = (_os.getenv("SUPABASE_SERVICE_KEY")
             or _os.getenv("SUPABASE_SECRET_KEY")
             or _os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    if not _surl or not _skey:
        return user  # fail-open si Supabase non configuré (dev local)
    try:
        r = _httpx.get(
            f"{_surl}/rest/v1/user_preferences?user_id=eq.{user['id']}&select=banned_at,banned_reason",
            headers={"apikey": _skey, "Authorization": f"Bearer {_skey}"},
            timeout=3.0,
        )
        rows = r.json() if r.status_code == 200 else []
        if rows and rows[0].get("banned_at"):
            reason = rows[0].get("banned_reason") or "Compte suspendu"
            raise HTTPException(status_code=403, detail=f"Compte banni : {reason}")
    except HTTPException:
        raise
    except Exception:
        pass  # fail-open en cas d'erreur réseau
    return user


def require_admin(user: Annotated[dict, Depends(require_user)]) -> dict:
    """Dépendance qui exige un utilisateur admin (is_admin=true dans user_preferences)."""
    import httpx as _httpx
    import os as _os
    _surl = _os.getenv("SUPABASE_URL", "").rstrip("/")
    _skey = (_os.getenv("SUPABASE_SERVICE_KEY")
             or _os.getenv("SUPABASE_SECRET_KEY")
             or _os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    if not _surl or not _skey:
        raise HTTPException(status_code=500, detail="Supabase non configuré — admin check impossible")
    try:
        r = _httpx.get(
            f"{_surl}/rest/v1/user_preferences?user_id=eq.{user['id']}&select=is_admin",
            headers={"apikey": _skey, "Authorization": f"Bearer {_skey}"},
            timeout=5.0,
        )
        rows = r.json() if r.status_code == 200 else []
        if rows and rows[0].get("is_admin"):
            return user
    except Exception:
        pass
    raise HTTPException(status_code=403, detail="Accès admin uniquement")


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


class PmeRequest(BaseModel):
    """Analyse PME (société non cotée) par SIREN."""
    siren: str = Field(..., description="SIREN (9 chiffres)")
    use_pappers_comptes: bool = Field(True, description="Télécharger comptes via Pappers XLSX")


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



def _do_societe(ticker: str, language: str = "fr", currency: str = "EUR") -> dict:
    """Exécute l'analyse société + retourne {data, files}.
    `language`/`currency` propagés au graph → AgentSynthese + writers."""
    from cli_analyze import run_societe as _run_societe
    import json

    outputs_dir = _ROOT / "outputs" / "generated" / "cli_tests"
    _run_societe(ticker, language=language, currency=currency)

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

    # Audit data : détection des champs critiques manquants (None/vides)
    try:
        from core.data_audit import audit_state
        warnings = audit_state(data) if data else []
        if warnings:
            data["warnings"] = warnings
            log.info(f"[audit] {ticker} — {len(warnings)} warning(s) détecté(s)")
    except Exception as e:
        log.debug(f"[audit] failed: {e}")

    files = _upload_files_to_storage(files, prefix=f"societe/{ticker}")
    return {"data": data, "files": files, "ticker": ticker}


def _do_portrait(ticker: str, _progress_cb=None) -> dict:
    """Génère le Portrait d'entreprise PDF + retourne {data, files}.

    _progress_cb(pct:int, msg:str): callback fourni par jobstore pour progress live.
    """
    from core.portrait import generate_portrait
    from outputs.portrait_pdf_writer import write_portrait_pdf

    outputs_dir = _ROOT / "outputs" / "generated" / "portraits"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    state = generate_portrait(ticker, progress_cb=_progress_cb)
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


def _do_secteur(secteur: str, univers: str, language: str = "fr", currency: str = "EUR") -> dict:
    from cli_analyze import run_secteur as _run_secteur

    sector_data = _run_secteur(secteur, univers, prefix="secteur",
                               language=language, currency=currency) or {}
    outputs_dir = _ROOT / "outputs" / "generated" / "cli_tests"
    stem = f"secteur_{secteur.replace(' ', '_')}_{univers.replace(' ', '_')}"
    files = {}
    # XLSX possible si secteur Énergie (template scoring multi-factoriel)
    for ext in ("pdf", "pptx", "xlsx"):
        p = outputs_dir / f"{stem}.{ext}"
        if p.exists():
            files[ext] = str(p.relative_to(_ROOT))
    files = _upload_files_to_storage(files, prefix=f"secteur/{stem}")
    # Slim les tickers pour limiter la taille du payload
    slim_tickers = []
    for t in sector_data.get("tickers", [])[:15]:
        if isinstance(t, dict):
            slim_tickers.append({
                "ticker": t.get("ticker") or t.get("symbol"),
                "name": t.get("name") or t.get("company_name"),
                "market_cap": t.get("market_cap"),
                "ratios": t.get("ratios") or {},
            })
    return {
        "data": {
            "kind": "secteur",
            "sector": sector_data.get("sector", secteur),
            "universe": sector_data.get("universe", univers),
            "tickers": slim_tickers,
            "sector_analytics": sector_data.get("sector_analytics", {}),
        },
        "files": files,
    }


def _do_indice(indice: str, language: str = "fr", currency: str = "EUR") -> dict:
    from cli_analyze import run_indice as _run_indice

    indice_data = _run_indice(indice, language=language, currency=currency) or {}
    outputs_dir = _ROOT / "outputs" / "generated" / "cli_tests"
    stem = f"indice_{indice.replace(' ', '_').replace('&', '')}"
    files = {}
    for ext in ("pdf", "pptx", "xlsx"):
        p = outputs_dir / f"{stem}.{ext}"
        if p.exists():
            files[ext] = str(p.relative_to(_ROOT))
    files = _upload_files_to_storage(files, prefix=f"indice/{stem}")
    # Slim secteurs : garde les métriques clés par secteur pour Q&A + UI
    slim_secteurs = []
    for s in indice_data.get("secteurs", [])[:15]:
        if isinstance(s, dict):
            slim_secteurs.append({
                "name": s.get("name") or s.get("sector"),
                "weight": s.get("weight") or s.get("poids"),
                "performance": s.get("performance") or s.get("perf_1y"),
                "top_tickers": (s.get("top_tickers") or s.get("tickers") or [])[:5],
            })
    return {
        "data": {
            "kind": "indice",
            "universe": indice_data.get("universe", indice),
            "secteurs": slim_secteurs,
            "indice_stats": indice_data.get("indice_stats", {}),
            "macro": indice_data.get("macro", {}),
            "allocation": indice_data.get("allocation", {}),
            "top_performers": indice_data.get("top_performers", [])[:10],
        },
        "files": files,
    }


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


def _do_pme(siren: str, use_pappers_comptes: bool = True,
            language: str = "fr", currency: str = "EUR") -> dict:
    """Pipeline PME : Pappers identité + (XLSX comptes) + peers + BODACC
    + analytics + outputs PDF/XLSX/PPTX.
    `language`/`currency` propagés aux writers pour i18n des outputs."""
    import os
    from core.pappers.client import PappersClient, PappersAPIError
    from core.pappers.xlsx_parser import parse_pappers_xlsx, download_pappers_xlsx
    from core.pappers.peers_client import PeersClient
    from core.pappers.bodacc_client import BodaccClient
    from core.pappers.sector_profiles import resolve_profile
    from core.pappers.analytics import analyze_pme
    from core.pappers.benchmark import build_benchmark
    from outputs.pme_pdf_writer import PmePdfContext, write_pme_pdf
    from outputs.pme_xlsx_writer import write_pme_xlsx
    from outputs.pme_pptx_writer import write_pme_pptx

    t0 = _utcnow()
    pappers = PappersClient()
    company = None
    # 1. Essaie Pappers d'abord (si credits dispo)
    try:
        company = pappers.fetch_company(siren, with_bodacc=False)
    except PappersAPIError as _pe:
        log.warning(f"[pme] Pappers échec ({_pe}) — fallback INPI")
    except Exception as _pe:
        log.warning(f"[pme] Pappers exception ({_pe}) — fallback INPI")
    # 2. Fallback INPI si Pappers KO ou non configuré
    if company is None or not company.denomination:
        try:
            from core.inpi import fetch_pme_inpi
            from core.inpi.parser import parse_inpi_to_pappers
            raw = fetch_pme_inpi(siren)
            if raw:
                inpi_company = parse_inpi_to_pappers(raw)
                if inpi_company and inpi_company.denomination:
                    company = inpi_company
                    log.info(f"[pme] {siren} → fallback INPI OK ({company.denomination})")
        except Exception as _ie:
            log.warning(f"[pme] INPI fallback échec : {_ie}")
    if company is None:
        raise PappersAPIError(f"SIREN {siren} introuvable (Pappers + INPI échec)", status_code=404)
    profile = resolve_profile(company.code_naf)
    log.info(f"[pme] {siren} → {company.denomination} (profil: {profile.code})")

    # Tente de télécharger et parser les comptes Pappers — boucle multi-années.
    # Pappers renvoie une liste `comptes` (souvent 2 entrées par année : sociaux
    # + consolidés ou XLSX/PDF). On dédoublonne par année et on télécharge
    # jusqu'à 5 années en parallèle (les téléchargements via token sont gratuits).
    yearly_accounts = []
    if use_pappers_comptes and company.comptes:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Dédoublonne : 1 candidat par année (le premier non confidentiel avec token)
        seen_years: dict[int, dict] = {}
        for c in company.comptes:
            if not isinstance(c, dict):
                continue
            yr = c.get("annee_cloture")
            tok = c.get("token_xlsx")
            conf = c.get("confidentialite_compte_de_resultat") or False
            if not yr or not tok or conf:
                continue
            if yr not in seen_years:
                seen_years[yr] = c

        # Garde les 5 années les plus récentes
        years_sorted = sorted(seen_years.keys(), reverse=True)[:5]
        log.info(f"[pme] {siren} : tentative téléchargement {len(years_sorted)} années {years_sorted}")

        tmp_dir = _ROOT / "logs" / "cache" / "pappers_xlsx"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        def _fetch_one(year: int):
            entry = seen_years[year]
            tok = entry.get("token_xlsx")
            try:
                xlsx_path = tmp_dir / f"{siren}_{year}.xlsx"
                if not xlsx_path.exists():
                    download_pappers_xlsx(tok, pappers.api_key, xlsx_path)
                parsed = parse_pappers_xlsx(xlsx_path, annee_cloture=year)
                return year, parsed, None
            except Exception as e:
                return year, None, str(e)

        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = [ex.submit(_fetch_one, y) for y in years_sorted]
            for fut in as_completed(futures):
                year, parsed, err = fut.result()
                if parsed:
                    yearly_accounts.append(parsed)
                    log.info(f"[pme] comptes {year} parsés OK")
                else:
                    log.warning(f"[pme] comptes {year} : échec ({err or 'parsing vide'})")

        # Trie par année croissante (pour analytics)
        yearly_accounts.sort(key=lambda y: y.annee)

    if not yearly_accounts:
        # Fallback : pas de comptes → analyse identité + BODACC seuls (niveau "screening")
        log.warning(f"[pme] {siren} : pas de comptes publics → mode screening")

    # Analyse
    analysis = analyze_pme(siren, yearly_accounts, profile)
    benchmark = None
    if yearly_accounts:
        last_y = max(analysis.ratios_by_year.keys())
        benchmark = build_benchmark(analysis.ratios_by_year[last_y], [], profile)

    # BODACC (gratuit, toujours)
    bodacc = BodaccClient().fetch(siren)

    # Génération outputs (si comptes dispo)
    outputs_dir = _ROOT / "outputs" / "generated" / "cli_tests"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    stem = f"pme_{siren}"
    files = {}
    if yearly_accounts and benchmark:
        try:
            ctx = PmePdfContext(
                siren=siren,
                denomination=company.denomination,
                forme_juridique=company.forme_juridique,
                code_naf=company.code_naf,
                libelle_naf=company.libelle_naf,
                ville_siege=company.ville_siege,
                date_creation=company.date_creation,
                capital=company.capital,
                dirigeants=company.dirigeants,
                analysis=analysis,
                benchmark=benchmark,
                yearly_accounts=yearly_accounts,
                bodacc=bodacc,
                commentaires={},
                language=language,
                currency=currency,
            )
            pdf_path = outputs_dir / f"{stem}.pdf"
            write_pme_pdf(ctx, pdf_path)
            files["pdf"] = str(pdf_path.relative_to(_ROOT))
        except Exception as e:
            log.error(f"[pme] PDF fail: {e}")

        try:
            xlsx_path = outputs_dir / f"{stem}.xlsx"
            write_pme_xlsx(xlsx_path, yearly_accounts, analysis, benchmark, bodacc,
                           siren, company.denomination,
                           language=language, currency=currency)
            files["xlsx"] = str(xlsx_path.relative_to(_ROOT))
        except Exception as e:
            log.error(f"[pme] XLSX fail: {e}")

        try:
            pptx_path = outputs_dir / f"{stem}.pptx"
            write_pme_pptx(pptx_path, yearly_accounts, analysis, benchmark, bodacc,
                           siren, company.denomination, profile.name,
                           language=language, currency=currency)
            files["pptx"] = str(pptx_path.relative_to(_ROOT))
        except Exception as e:
            log.error(f"[pme] PPTX fail: {e}")

    files = _upload_files_to_storage(files, prefix=f"pme/{stem}")

    # Traduit les catégories textuelles côté backend (forme juridique, dirigeants,
    # types BODACC) selon la langue user — le frontend affiche tel quel.
    from core.i18n import legal_form_label, director_quality_label, bodacc_label
    _dirs_translated = []
    for d in (company.dirigeants or [])[:10]:
        d_copy = dict(d)
        if d_copy.get("qualite"):
            d_copy["qualite"] = director_quality_label(d_copy["qualite"], language)
        _dirs_translated.append(d_copy)

    # Payload frontend (slim)
    data = {
        "kind": "pme",
        "siren": siren,
        "denomination": company.denomination,
        "forme_juridique": legal_form_label(company.forme_juridique, language) if company.forme_juridique else None,
        "code_naf": company.code_naf,
        "libelle_naf": company.libelle_naf,
        "ville_siege": company.ville_siege,
        "capital": company.capital,
        "dirigeants": _dirs_translated,
        "profile": {"code": profile.code, "name": profile.name},
        "has_accounts": len(yearly_accounts) > 0,
        "years": [y.annee for y in yearly_accounts],
        "analysis_summary": {
            "health_score": analysis.health_score,
            "altman_z": analysis.altman_z,
            "altman_verdict": analysis.altman_verdict,
            "bankability_score": analysis.bankability_score,
            "debt_capacity_estimate": analysis.debt_capacity_estimate,
        } if yearly_accounts else None,
        "bodacc": {
            "total_annonces": bodacc.total_annonces,
            "procedures_collectives": len(bodacc.procedures_collectives),
            "derniere_procedure": bodacc_label(bodacc.derniere_procedure, language) if bodacc.derniere_procedure else None,
            "dernier_depot_comptes": bodacc.dernier_depot_comptes,
            "radie": bodacc.radie,
            "penalty": bodacc.bodacc_score_penalty,
        },
    }
    elapsed = int((_utcnow() - t0).total_seconds() * 1000)
    log.info(f"[pme] {siren} terminé en {elapsed}ms")

    # Dataset anonymisé
    try:
        from core.analysis_log_helper import log_pme_analysis
        log_pme_analysis(siren, company.denomination, analysis, duration_ms=elapsed,
                          language=language)
    except Exception as _log_e:
        log.debug(f"[pme] analysis_log skip : {_log_e}")

    return {"data": data, "files": files}


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
async def analyze_societe(req: SocieteRequest, request: Request):
    """Analyse société synchrone (~1-3 min). Préférer /jobs/analyze/societe pour async.
    Locale propagée via headers X-User-Language / X-User-Currency."""
    lang, ccy = _user_locale(request)
    return _sync_response("analyze/societe", _do_societe, req.ticker, lang, ccy)


@app.post("/analyze/secteur", response_model=AnalyseResponse)
async def analyze_secteur(req: SecteurRequest, request: Request):
    lang, ccy = _user_locale(request)
    return _sync_response("analyze/secteur", _do_secteur, req.secteur, req.univers, lang, ccy)


@app.post("/analyze/indice", response_model=AnalyseResponse)
async def analyze_indice(req: IndiceRequest, request: Request):
    """⚠️ Bloquant 5-8 min — prefer /jobs/analyze/indice."""
    lang, ccy = _user_locale(request)
    return _sync_response("analyze/indice", _do_indice, req.indice, lang, ccy)


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


@app.post("/analyze/pme", response_model=AnalyseResponse)
async def analyze_pme_endpoint(req: PmeRequest, request: Request):
    """Analyse PME (société non cotée FR) par SIREN.
    Pipeline : Pappers identité+comptes Cerfa → peers → BODACC → analytics → PDF/XLSX/PPTX.
    Locale (langue + devise) lue depuis headers X-User-Language / X-User-Currency."""
    lang, ccy = _user_locale(request)
    return _sync_response(
        "analyze/pme", _do_pme,
        req.siren, req.use_pappers_comptes, lang, ccy,
    )


@app.get("/search/pme")
async def search_pme(q: str, limit: int = 8):
    """Recherche PME par nom/dirigeant via recherche-entreprises.api.gouv.fr (gratuit, sans auth).
    Renvoie une liste de suggestions avec SIREN, dénomination, ville, NAF, dirigeant principal."""
    import requests as _rq

    q = (q or "").strip()
    if len(q) < 2:
        return {"results": []}

    limit = max(1, min(limit, 20))
    try:
        r = _rq.get(
            "https://recherche-entreprises.api.gouv.fr/search",
            params={"q": q, "page": 1, "per_page": limit, "etat_administratif": "A"},
            timeout=8,
        )
        if r.status_code != 200:
            log.warning(f"[search_pme] HTTP {r.status_code} q={q}")
            return {"results": []}
        data = r.json()
    except Exception as e:
        log.warning(f"[search_pme] erreur réseau: {e}")
        return {"results": []}

    results = []
    for item in data.get("results", [])[:limit]:
        siege = item.get("siege") or {}
        dirs = item.get("dirigeants") or []
        first_dir = dirs[0] if dirs else {}
        nom_dir = " ".join(
            x for x in [first_dir.get("prenoms"), first_dir.get("nom")] if x
        ).strip() or first_dir.get("denomination") or None

        results.append({
            "siren": item.get("siren"),
            "denomination": item.get("nom_complet") or item.get("nom_raison_sociale"),
            "ville": siege.get("libelle_commune"),
            "code_postal": siege.get("code_postal"),
            "code_naf": item.get("activite_principale"),
            "nature_juridique": item.get("nature_juridique"),
            "categorie": item.get("categorie_entreprise"),
            "date_creation": item.get("date_creation"),
            "dirigeant": nom_dir,
        })
    return {"results": results, "total": data.get("total_results", len(results))}


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


@app.get("/admin/monitoring")
async def admin_monitoring(limit: int = 30):
    """Tableau de bord monitoring (Baptiste only — pas d'auth pour V1).

    Retourne pour chaque job récent : kind, status, label, timing total
    + breakdown par node (fetch/synthesis/qa/output) + provider LLM utilisé
    + tailles fichiers + warnings audit.

    Pas d'auth pour V1 : à protéger avant ouverture publique.
    """
    raw = jobstore.list_jobs(limit)
    enriched = []
    for j in raw:
        full = jobstore.get(j.get("job_id")) or j
        result = full.get("result") or {}
        data = result.get("data") if isinstance(result, dict) else None
        logs = (data or {}).get("logs") if isinstance(data, dict) else []
        synth = (data or {}).get("synthesis") if isinstance(data, dict) else None
        synth_meta = synth.get("meta") if isinstance(synth, dict) else None
        warnings = (data or {}).get("warnings") if isinstance(data, dict) else []

        timing = {}
        for entry in (logs or []):
            node = entry.get("node")
            if node:
                timing[node] = entry.get("latency_ms")
        # Sub-timings output
        out_entry = next((e for e in (logs or []) if e.get("node") == "output_node"), {})
        files = result.get("files") if isinstance(result, dict) else None
        synth_entry = next((e for e in (logs or []) if e.get("node") == "synthesis_node"), {})

        elapsed_total = None
        try:
            from datetime import datetime as _dt
            s, f = full.get("started_at"), full.get("finished_at")
            if s and f:
                elapsed_total = int(
                    (_dt.fromisoformat(f) - _dt.fromisoformat(s)).total_seconds() * 1000
                )
        except Exception:
            pass

        enriched.append({
            "job_id": full.get("job_id"),
            "kind": full.get("kind"),
            "status": full.get("status"),
            "label": full.get("label"),
            "started_at": full.get("started_at"),
            "finished_at": full.get("finished_at"),
            "elapsed_ms": elapsed_total,
            "timing": timing,
            "synthesis_provider": synth_entry.get("provider"),
            "synthesis_provider_ms": (synth_meta or {}).get("provider_ms"),
            "providers_failed": synth_entry.get("providers_failed"),
            "writers_ms": {
                "excel_ms": out_entry.get("excel_ms"),
                "pptx_ms": out_entry.get("pptx_ms"),
                "pdf_ms": out_entry.get("pdf_ms"),
            },
            "files": files,
            "warnings": warnings or [],
            "error": full.get("error"),
        })
    return {"jobs": enriched, "count": len(enriched)}


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
    """Résumé compact du state pour le contexte LLM.

    Gère 3 kinds : société (raw_data+synthesis), secteur (tickers+analytics),
    indice (secteurs+macro+allocation).
    """
    if not isinstance(state, dict):
        return ""

    kind = state.get("kind", "societe")

    # ─── SECTEUR ──────────────────────────────────────────────────────
    if kind == "secteur":
        lines = [
            f"Analyse sectorielle : {state.get('sector', '?')} (univers {state.get('universe', '?')})",
        ]
        tickers = state.get("tickers", [])
        if tickers:
            lines.append(f"Sociétés analysées ({len(tickers)}) :")
            for t in tickers[:10]:
                r = t.get("ratios") or {}
                bits = [f"{t.get('ticker', '?')}"]
                if t.get("name"): bits.append(t["name"])
                if r.get("pe_ratio"): bits.append(f"P/E {r['pe_ratio']:.1f}x")
                if r.get("ev_ebitda"): bits.append(f"EV/EBITDA {r['ev_ebitda']:.1f}x")
                if r.get("ebitda_margin"): bits.append(f"mEBITDA {r['ebitda_margin']*100:.1f}%")
                lines.append("  • " + " · ".join(str(b) for b in bits))
        sa = state.get("sector_analytics") or {}
        if sa.get("median_pe"):
            lines.append(f"Médianes sectorielles : P/E {sa.get('median_pe', '?')} · EV/EBITDA {sa.get('median_ev_ebitda', '?')}")
        if sa.get("top_performers"):
            lines.append(f"Top performers : {', '.join(sa['top_performers'][:5])}")
        return "\n".join(lines)

    # ─── INDICE ───────────────────────────────────────────────────────
    if kind == "indice":
        lines = [f"Analyse d'indice : {state.get('universe', '?')}"]
        stats = state.get("indice_stats") or {}
        if stats:
            bits = []
            if stats.get("median_pe"): bits.append(f"P/E médian {stats['median_pe']:.1f}x")
            if stats.get("perf_1y"): bits.append(f"perf 1Y {stats['perf_1y']}")
            if bits: lines.append("Stats globales : " + " · ".join(bits))
        secteurs = state.get("secteurs", [])
        if secteurs:
            lines.append(f"Secteurs ({len(secteurs)}) :")
            for s in secteurs[:12]:
                bits = [str(s.get("name", "?"))]
                if s.get("weight"): bits.append(f"poids {s['weight']}")
                if s.get("performance") is not None: bits.append(f"perf {s['performance']}")
                tops = s.get("top_tickers") or []
                if tops: bits.append(f"top: {', '.join(str(t) for t in tops[:3])}")
                lines.append("  • " + " · ".join(bits))
        macro = state.get("macro") or {}
        if macro:
            bits = []
            if macro.get("regime"): bits.append(f"régime {macro['regime']}")
            if macro.get("vix"): bits.append(f"VIX {macro['vix']}")
            if bits: lines.append("Contexte macro : " + " · ".join(bits))
        top = state.get("top_performers") or []
        if top:
            lines.append(f"Top performers indice : {', '.join(str(t) for t in top[:7])}")
        return "\n".join(lines)

    # ─── SOCIÉTÉ (défaut) ─────────────────────────────────────────────
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


def _build_qa_messages(req: "QARequest", state: dict, language: str = "fr",
                        explanatory: bool = False) -> tuple[str, str]:
    """Construit (system_prompt, user_prompt) pour le QA depuis state + messages.
    `language` : code ISO court (fr/en/es/de/it/pt) — détermine la langue de réponse.
    `explanatory` : mode explicatif — l'assistant vulgarise chaque ratio/concept
    pour un non-initié (définitions courtes, pas de jargon).
    """
    from core.i18n import system_language_directive, normalize_language

    language = normalize_language(language)
    context = _build_qa_context(state)
    if not req.messages:
        raise HTTPException(400, "Aucun message")
    if req.messages[-1].role != "user":
        raise HTTPException(400, "Le dernier message doit être de l'utilisateur")
    ticker = (state.get("ticker") or (state.get("raw_data") or {}).get("ticker") or "—")
    lang_directive = system_language_directive(language)
    explanatory_directive = ""
    if explanatory:
        explanatory_directive = (
            " Explanatory mode is ON: whenever you mention a financial ratio or "
            "concept (P/E, EV/EBITDA, WACC, FCF, beta, DCF, etc.), add a short "
            "plain-language definition in parentheses so a beginner can follow. "
            "Prefer everyday analogies over jargon."
        )
    system = (
        f"You are an expert financial AI analyst. You answer the user's "
        f"questions about the FinSight analysis below. {lang_directive}"
        f"{explanatory_directive} "
        f"Be factual, concise (2-4 paragraphs max), cite figures from the "
        f"context when relevant. If a question is out of scope, say so clearly.\n\n"
        f"=== Analysis context {ticker} ===\n{context}\n=== End of context ==="
    )
    # Étiquettes interlocuteurs traduites
    user_label = {
        "fr": "Utilisateur", "en": "User", "es": "Usuario",
        "de": "Benutzer", "it": "Utente", "pt": "Utilizador",
    }.get(language, "User")
    asst_label = {
        "fr": "Assistant", "en": "Assistant", "es": "Asistente",
        "de": "Assistent", "it": "Assistente", "pt": "Assistente",
    }.get(language, "Assistant")

    convo_lines = []
    for m in req.messages[:-1]:
        prefix = user_label if m.role == "user" else asst_label
        convo_lines.append(f"{prefix}: {m.content}")
    convo_lines.append(f"{user_label}: {req.messages[-1].content}")
    convo_lines.append(f"{asst_label}:")
    return system, "\n".join(convo_lines)


def _user_locale(request: Request) -> tuple[str, str]:
    """Extrait (language, currency) des headers HTTP du frontend.
    Defaults : fr / EUR.
    """
    from core.i18n import normalize_language, normalize_currency
    lang = request.headers.get("x-user-language") or request.headers.get("X-User-Language")
    ccy = request.headers.get("x-user-currency") or request.headers.get("X-User-Currency")
    return normalize_language(lang), normalize_currency(ccy)


@app.post("/qa/stream")
async def qa_stream_endpoint(req: QARequest, request: Request):
    """Q&A en streaming SSE. Renvoie des events `data: {"chunk": "..."}` puis
    `data: {"done": true}` à la fin. Fallback non-streamé si tous providers
    streaming échouent.
    Langue de réponse pilotée par le header `X-User-Language`.
    """
    from fastapi.responses import StreamingResponse
    import asyncio
    import json as _json

    language, _ccy = _user_locale(request)
    explanatory = (request.headers.get("x-explanatory-mode") or "").lower() in ("1", "true", "on", "yes")
    state = _load_job_state(req.job_id)
    system, user_prompt = _build_qa_messages(req, state, language=language, explanatory=explanatory)

    async def _gen():
        # Tente Groq streaming en priorité (le plus rapide pour stream)
        try:
            from groq import Groq
            from core.llm_provider import _get_secret  # type: ignore
            key = _get_secret("GROQ_API_KEY")
            if not key:
                raise RuntimeError("GROQ_API_KEY absente")
            client = Groq(api_key=key)
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=800,
                temperature=0.4,
                stream=True,
            )
            full = []
            for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    full.append(delta)
                    yield f"data: {_json.dumps({'chunk': delta})}\n\n"
                    await asyncio.sleep(0)  # libère event loop
            # Restauration accents post-stream (évite "sous-evalue")
            try:
                from core.accent_runtime import restore_accents as _ra
                final = _ra("".join(full))
                if final != "".join(full):
                    yield f"data: {_json.dumps({'replace': final})}\n\n"
            except Exception:
                pass
            yield f"data: {_json.dumps({'done': True})}\n\n"
            return
        except Exception as e:
            log.warning(f"[/qa/stream] Groq stream failed: {e}, fallback non-stream")

        # Fallback : appel non-streamé via LLMProvider, on renvoie en un chunk
        try:
            from core.llm_provider import LLMProvider
            for prov, model in [("mistral", None), ("anthropic", None), ("gemini", None)]:
                try:
                    llm = LLMProvider(provider=prov, model=model)
                    answer = llm.generate(user_prompt, system=system, max_tokens=800)
                    if answer and answer.strip():
                        yield f"data: {_json.dumps({'chunk': answer.strip()})}\n\n"
                        yield f"data: {_json.dumps({'done': True})}\n\n"
                        return
                except Exception as e2:
                    log.warning(f"[/qa/stream] fallback {prov} failed: {e2}")
                    continue
            yield f"data: {_json.dumps({'error': 'Tous les providers LLM ont échoué'})}\n\n"
        except Exception as e3:
            yield f"data: {_json.dumps({'error': str(e3)})}\n\n"

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # désactive buffering nginx/proxy
        },
    )


@app.post("/qa", response_model=QAResponse)
async def qa_endpoint(req: QARequest, request: Request):
    """Q&A multi-tour sur une analyse. L'historique est passé par le client.
    Langue pilotée par header X-User-Language."""
    language, _ccy = _user_locale(request)
    explanatory = (request.headers.get("x-explanatory-mode") or "").lower() in ("1", "true", "on", "yes")
    state = _load_job_state(req.job_id)
    system, user_prompt = _build_qa_messages(req, state, language=language, explanatory=explanatory)

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

    # Fallback 1 : résolveur nom→ticker (dict hardcodé + LLM Groq)
    try:
        from core.ticker_resolver import resolve as _resolve_name
        resolved = _resolve_name(q)
        if resolved:
            return ResolveResponse(query=q, kind="societe", ticker=resolved)
    except Exception as e:
        log.warning(f"[resolve] name_to_ticker fail: {e}")

    # Fallback 2 : suffixes exchange sur ticker court (ABBN → ABBN.SW)
    try:
        from data.sources.yfinance_source import _resolve_ticker_with_suffix
        ticker = _resolve_ticker_with_suffix(q)
        if ticker and ticker != q and ("." in ticker or "-" in ticker):
            return ResolveResponse(query=q, kind="societe", ticker=ticker)
    except Exception as e:
        log.warning(f"[resolve] yfinance resolve fail: {e}")

    return ResolveResponse(query=q, kind="unknown")


@app.get("/market/performance/{ticker}")
async def market_performance(ticker: str):
    """Renvoie perf%/plus haut/bas/volatilité pour 9 périodes en un seul call."""
    from core.market import fetch_performance
    return fetch_performance(ticker)


@app.get("/market/series/{ticker}")
async def market_series(ticker: str, period: str = "1mo"):
    """Série temporelle close-price pour une période donnée.
    period : 1d, 5d, 1mo, 3mo, 6mo, ytd, 1y, 3y, 5y.
    """
    from core.market import fetch_price_series
    return fetch_price_series(ticker, period=period)


@app.get("/tickers/resolve/{query}")
async def resolve_ticker(query: str):
    """Résout un nom (ex: 'hermes', 'lvmh') vers un ticker yfinance.
    Utilise dict hardcodé 200 capis puis fallback LLM Groq validé fast_info.
    """
    try:
        from core.ticker_resolver import resolve as _resolve_name
        ticker = _resolve_name(query)
        if not ticker:
            # Dernier recours : suffixes exchange
            from data.sources.yfinance_source import _resolve_ticker_with_suffix
            cand = _resolve_ticker_with_suffix(query)
            if cand and cand != query and ("." in cand or "-" in cand):
                ticker = cand
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


# ─── Stripe : checkout + portal + webhook ───────────────────────────────────

class CheckoutRequest(BaseModel):
    plan: str = Field(..., description="Plan slug: decouverte | pro | enterprise")
    interval: str = Field("month", description="month | year")


@app.post("/stripe/checkout")
async def stripe_create_checkout(
    payload: CheckoutRequest,
    request: Request,
    user: Annotated[dict, Depends(require_user)],
):
    """Crée une Stripe Checkout Session. Retourne l'URL de redirection."""
    import os as _os
    skey = _os.getenv("STRIPE_SECRET_KEY")
    if not skey:
        raise HTTPException(status_code=503, detail="Stripe non configuré")

    # Résolution price_id via STRIPE_PRICE_IDS env (JSON)
    import json as _json
    try:
        price_map = _json.loads(_os.getenv("STRIPE_PRICE_IDS", "{}"))
    except Exception:
        price_map = {}
    key = f"{payload.plan}_{payload.interval}"
    price_id = price_map.get(key)
    if not price_id:
        raise HTTPException(
            status_code=400,
            detail=f"Price ID introuvable pour {key}. Env STRIPE_PRICE_IDS à configurer.",
        )

    try:
        import stripe
        stripe.api_key = skey

        # Récupère ou crée le Stripe Customer via user_preferences
        import httpx as _httpx
        surl = _os.getenv("SUPABASE_URL", "").rstrip("/")
        supa_key = (_os.getenv("SUPABASE_SERVICE_KEY")
                    or _os.getenv("SUPABASE_SECRET_KEY")
                    or _os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
        cust_id = None
        try:
            r = _httpx.get(
                f"{surl}/rest/v1/user_preferences?user_id=eq.{user['id']}&select=stripe_customer_id",
                headers={"apikey": supa_key, "Authorization": f"Bearer {supa_key}"},
                timeout=3.0,
            )
            rows = r.json() if r.status_code == 200 else []
            cust_id = rows[0].get("stripe_customer_id") if rows else None
        except Exception:
            pass

        if not cust_id:
            cust = stripe.Customer.create(
                email=user.get("email"),
                metadata={"user_id": user["id"]},
            )
            cust_id = cust.id
            # Persist dans user_preferences
            try:
                _httpx.patch(
                    f"{surl}/rest/v1/user_preferences?user_id=eq.{user['id']}",
                    headers={"apikey": supa_key, "Authorization": f"Bearer {supa_key}",
                             "Content-Type": "application/json", "Prefer": "return=minimal"},
                    json={"stripe_customer_id": cust_id},
                    timeout=3.0,
                )
            except Exception:
                pass

        # URL de retour
        origin = request.headers.get("origin") or "https://finsight-ia.com"
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=cust_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{origin}/parametres/facturation?status=success",
            cancel_url=f"{origin}/parametres/facturation?status=cancel",
            metadata={"user_id": user["id"], "plan": payload.plan},
            subscription_data={"metadata": {"user_id": user["id"], "plan": payload.plan}},
            allow_promotion_codes=True,
            billing_address_collection="required",
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"[stripe] checkout exception : {e}")
        raise HTTPException(status_code=500, detail=f"Stripe error: {e}")


@app.post("/stripe/portal")
async def stripe_customer_portal(
    request: Request,
    user: Annotated[dict, Depends(require_user)],
):
    """Ouvre le Stripe Customer Portal (self-service : cancel, update CB...)."""
    import os as _os
    skey = _os.getenv("STRIPE_SECRET_KEY")
    if not skey:
        raise HTTPException(status_code=503, detail="Stripe non configuré")

    import httpx as _httpx
    surl = _os.getenv("SUPABASE_URL", "").rstrip("/")
    supa_key = (_os.getenv("SUPABASE_SERVICE_KEY")
                or _os.getenv("SUPABASE_SECRET_KEY")
                or _os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    try:
        r = _httpx.get(
            f"{surl}/rest/v1/user_preferences?user_id=eq.{user['id']}&select=stripe_customer_id",
            headers={"apikey": supa_key, "Authorization": f"Bearer {supa_key}"},
            timeout=3.0,
        )
        rows = r.json() if r.status_code == 200 else []
        cust_id = rows[0].get("stripe_customer_id") if rows else None
    except Exception:
        cust_id = None

    if not cust_id:
        raise HTTPException(status_code=400, detail="Aucun abonnement actif")

    try:
        import stripe
        stripe.api_key = skey
        origin = request.headers.get("origin") or "https://finsight-ia.com"
        portal = stripe.billing_portal.Session.create(
            customer=cust_id,
            return_url=f"{origin}/parametres/facturation",
        )
        return {"portal_url": portal.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe portal error: {e}")


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    """Reçoit les events Stripe (subscription.*, invoice.*). Signature vérifiée."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        from stripe_webhook_handler import verify_webhook, handle_event
    except Exception:
        from backend.stripe_webhook_handler import verify_webhook, handle_event
    event = verify_webhook(payload, sig)
    if event is None:
        raise HTTPException(status_code=400, detail="Signature invalide ou Stripe non configuré")
    ok = handle_event(event)
    return {"received": True, "ok": ok}


# ─── Admin dashboard ─────────────────────────────────────────────────────────

@app.get("/admin/stats")
async def admin_stats(user: Annotated[dict, Depends(require_admin)]):
    """Dashboard admin — KPIs business : trafic, analyses, utilisateurs, revenus.

    Query Supabase via service role pour récupérer les agrégats. Seuls les
    admins (is_admin=true) ont accès — enforcement via require_admin dep.
    """
    import httpx as _httpx
    import os as _os
    from datetime import datetime as _dt, timedelta as _td
    _surl = _os.getenv("SUPABASE_URL", "").rstrip("/")
    _skey = (_os.getenv("SUPABASE_SERVICE_KEY")
             or _os.getenv("SUPABASE_SECRET_KEY")
             or _os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    headers = {"apikey": _skey, "Authorization": f"Bearer {_skey}"}

    now = _dt.utcnow()
    day_ago = (now - _td(days=1)).isoformat()
    week_ago = (now - _td(days=7)).isoformat()
    month_ago = (now - _td(days=30)).isoformat()

    def _count(url: str) -> int:
        try:
            r = _httpx.get(url, headers={**headers, "Prefer": "count=exact"}, timeout=5.0)
            cr = r.headers.get("content-range", "*/0")
            return int(cr.split("/")[-1]) if "/" in cr else 0
        except Exception:
            return 0

    # Analyses tracking (analysis_log anonymisé)
    an_day = _count(f"{_surl}/rest/v1/analysis_log?created_at=gte.{day_ago}&select=id")
    an_week = _count(f"{_surl}/rest/v1/analysis_log?created_at=gte.{week_ago}&select=id")
    an_month = _count(f"{_surl}/rest/v1/analysis_log?created_at=gte.{month_ago}&select=id")
    an_total = _count(f"{_surl}/rest/v1/analysis_log?select=id")

    # Breakdown par kind
    kind_breakdown = {}
    try:
        r = _httpx.get(
            f"{_surl}/rest/v1/analysis_log?created_at=gte.{month_ago}&select=kind",
            headers=headers, timeout=5.0
        )
        for row in (r.json() or []):
            k = row.get("kind") or "unknown"
            kind_breakdown[k] = kind_breakdown.get(k, 0) + 1
    except Exception:
        pass

    # Breakdown par recommandation (société/PME uniquement)
    reco_breakdown = {"BUY": 0, "HOLD": 0, "SELL": 0}
    try:
        r = _httpx.get(
            f"{_surl}/rest/v1/analysis_log?created_at=gte.{month_ago}&recommendation=not.is.null&select=recommendation",
            headers=headers, timeout=5.0
        )
        for row in (r.json() or []):
            rc = (row.get("recommendation") or "").upper()
            if rc in reco_breakdown:
                reco_breakdown[rc] += 1
    except Exception:
        pass

    # Top tickers (30 jours)
    top_tickers: list[dict] = []
    try:
        r = _httpx.get(
            f"{_surl}/rest/v1/analysis_log?created_at=gte.{month_ago}&ticker=not.is.null&select=ticker,company_name",
            headers=headers, timeout=5.0
        )
        counts = {}
        names = {}
        for row in (r.json() or []):
            t = row["ticker"]
            counts[t] = counts.get(t, 0) + 1
            if not names.get(t) and row.get("company_name"):
                names[t] = row["company_name"]
        sorted_t = sorted(counts.items(), key=lambda x: -x[1])[:10]
        top_tickers = [{"ticker": t, "company_name": names.get(t), "count": c} for t, c in sorted_t]
    except Exception:
        pass

    # Utilisateurs
    users_total = _count(f"{_surl}/rest/v1/user_preferences?select=user_id")
    users_banned = _count(f"{_surl}/rest/v1/user_preferences?banned_at=not.is.null&select=user_id")

    return {
        "analyses": {
            "day": an_day,
            "week": an_week,
            "month": an_month,
            "total": an_total,
            "by_kind": kind_breakdown,
            "by_recommendation": reco_breakdown,
            "top_tickers_30d": top_tickers,
        },
        "users": {
            "total": users_total,
            "banned": users_banned,
            "active": max(0, users_total - users_banned),
        },
        "revenues": {
            "mrr_eur": 0,
            "arr_eur": 0,
            "note": "Stripe pas encore intégré",
        },
        "generated_at": now.isoformat() + "Z",
    }


@app.get("/admin/users")
async def admin_list_users(user: Annotated[dict, Depends(require_admin)],
                            limit: int = 100, banned_only: bool = False):
    """Liste users (pour ban/unban). Admin only."""
    import httpx as _httpx
    import os as _os
    _surl = _os.getenv("SUPABASE_URL", "").rstrip("/")
    _skey = (_os.getenv("SUPABASE_SERVICE_KEY")
             or _os.getenv("SUPABASE_SECRET_KEY")
             or _os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    headers = {"apikey": _skey, "Authorization": f"Bearer {_skey}"}
    try:
        # Requête user_preferences jointe aux emails via RPC ou double query
        url = f"{_surl}/rest/v1/user_preferences?select=user_id,is_admin,banned_at,banned_reason,created_at&order=created_at.desc&limit={limit}"
        if banned_only:
            url += "&banned_at=not.is.null"
        r = _httpx.get(url, headers=headers, timeout=5.0)
        prefs = r.json() if r.status_code == 200 else []

        # Récupérer emails auth.users
        out = []
        for p in prefs:
            uid = p["user_id"]
            try:
                ar = _httpx.get(
                    f"{_surl}/auth/v1/admin/users/{uid}",
                    headers=headers, timeout=3.0
                )
                ad = ar.json() if ar.status_code == 200 else {}
                out.append({
                    "user_id": uid,
                    "email": ad.get("email"),
                    "created_at": ad.get("created_at") or p.get("created_at"),
                    "is_admin": p.get("is_admin", False),
                    "banned_at": p.get("banned_at"),
                    "banned_reason": p.get("banned_reason"),
                })
            except Exception:
                out.append({"user_id": uid, **p})
        return {"users": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")


class BanRequest(BaseModel):
    user_id: str
    reason: Optional[str] = None


@app.post("/admin/ban")
async def admin_ban(payload: BanRequest, user: Annotated[dict, Depends(require_admin)]):
    """Ban soft-delete un user. Admin only. user_preferences.banned_at = now()."""
    import httpx as _httpx
    import os as _os
    from datetime import datetime as _dt
    _surl = _os.getenv("SUPABASE_URL", "").rstrip("/")
    _skey = (_os.getenv("SUPABASE_SERVICE_KEY")
             or _os.getenv("SUPABASE_SECRET_KEY")
             or _os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    try:
        r = _httpx.patch(
            f"{_surl}/rest/v1/user_preferences?user_id=eq.{payload.user_id}",
            headers={"apikey": _skey, "Authorization": f"Bearer {_skey}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"},
            json={"banned_at": _dt.utcnow().isoformat(), "banned_reason": payload.reason or "banni par admin"},
            timeout=5.0,
        )
        if r.status_code >= 300:
            raise HTTPException(status_code=500, detail=f"Ban failed: {r.text[:200]}")
        return {"ok": True, "user_id": payload.user_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ban error: {e}")


@app.post("/admin/unban")
async def admin_unban(payload: BanRequest, user: Annotated[dict, Depends(require_admin)]):
    """Unban : reset banned_at=null."""
    import httpx as _httpx
    import os as _os
    _surl = _os.getenv("SUPABASE_URL", "").rstrip("/")
    _skey = (_os.getenv("SUPABASE_SERVICE_KEY")
             or _os.getenv("SUPABASE_SECRET_KEY")
             or _os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    try:
        r = _httpx.patch(
            f"{_surl}/rest/v1/user_preferences?user_id=eq.{payload.user_id}",
            headers={"apikey": _skey, "Authorization": f"Bearer {_skey}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"},
            json={"banned_at": None, "banned_reason": None},
            timeout=5.0,
        )
        if r.status_code >= 300:
            raise HTTPException(status_code=500, detail=f"Unban failed: {r.text[:200]}")
        return {"ok": True, "user_id": payload.user_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unban error: {e}")


# ─── Alertes / Rappels post-analyse ─────────────────────────────────────────

class AlertCreateRequest(BaseModel):
    history_id: Optional[str] = None
    ticker: Optional[str] = None
    trigger_type: str  # price_target, earnings_date, dividend_exdate, news, custom_date, quarterly_results
    trigger_value: dict = Field(default_factory=dict)
    channels: list[str] = Field(default_factory=lambda: ["email"])
    label: Optional[str] = None


class AlertPatchRequest(BaseModel):
    enabled: Optional[bool] = None
    label: Optional[str] = None
    channels: Optional[list[str]] = None
    trigger_value: Optional[dict] = None


class PushSubscribeRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth_key: str
    user_agent: Optional[str] = None


def _supabase_creds() -> tuple[str, str]:
    import os as _os
    _surl = _os.getenv("SUPABASE_URL", "").rstrip("/")
    _skey = (_os.getenv("SUPABASE_SERVICE_KEY")
             or _os.getenv("SUPABASE_SECRET_KEY")
             or _os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    if not _surl or not _skey:
        raise HTTPException(status_code=500, detail="Supabase non configuré")
    return _surl, _skey


@app.post("/alerts/create")
async def alert_create(payload: AlertCreateRequest, user: Annotated[dict, Depends(require_user)]):
    """Crée un rappel pour l'user connecté."""
    import httpx as _httpx
    _surl, _skey = _supabase_creds()
    if payload.trigger_type not in {"price_target", "earnings_date", "dividend_exdate",
                                     "news", "custom_date", "quarterly_results"}:
        raise HTTPException(status_code=400, detail="trigger_type invalide")
    body = {
        "user_id": user["id"],
        "history_id": payload.history_id,
        "ticker": (payload.ticker or "").upper().strip() or None,
        "trigger_type": payload.trigger_type,
        "trigger_value": payload.trigger_value,
        "channels": payload.channels or ["email"],
        "label": payload.label,
    }
    body = {k: v for k, v in body.items() if v is not None}
    try:
        r = _httpx.post(
            f"{_surl}/rest/v1/analysis_alerts",
            headers={"apikey": _skey, "Authorization": f"Bearer {_skey}",
                     "Content-Type": "application/json", "Prefer": "return=representation"},
            json=body,
            timeout=5.0,
        )
        if r.status_code >= 300:
            raise HTTPException(status_code=500, detail=f"Insert failed: {r.text[:200]}")
        rows = r.json() or []
        return {"ok": True, "alert": rows[0] if rows else None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Create error: {e}")


@app.get("/alerts")
async def alerts_list(user: Annotated[dict, Depends(require_user)]):
    """Liste tous les rappels de l'user (enabled + disabled + fired)."""
    import httpx as _httpx
    _surl, _skey = _supabase_creds()
    try:
        r = _httpx.get(
            f"{_surl}/rest/v1/analysis_alerts?user_id=eq.{user['id']}&order=created_at.desc",
            headers={"apikey": _skey, "Authorization": f"Bearer {_skey}"},
            timeout=5.0,
        )
        return {"alerts": r.json() if r.status_code < 300 else []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"List error: {e}")


@app.patch("/alerts/{alert_id}")
async def alert_patch(alert_id: str, payload: AlertPatchRequest,
                      user: Annotated[dict, Depends(require_user)]):
    """Toggle enabled, renomme, change trigger_value ou channels."""
    import httpx as _httpx
    _surl, _skey = _supabase_creds()
    fields: dict = {}
    if payload.enabled is not None: fields["enabled"] = payload.enabled
    if payload.label is not None: fields["label"] = payload.label
    if payload.channels is not None: fields["channels"] = payload.channels
    if payload.trigger_value is not None: fields["trigger_value"] = payload.trigger_value
    if not fields:
        raise HTTPException(status_code=400, detail="Aucun champ")
    try:
        r = _httpx.patch(
            f"{_surl}/rest/v1/analysis_alerts?id=eq.{alert_id}&user_id=eq.{user['id']}",
            headers={"apikey": _skey, "Authorization": f"Bearer {_skey}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"},
            json=fields, timeout=5.0,
        )
        if r.status_code >= 300:
            raise HTTPException(status_code=500, detail=f"Patch failed: {r.text[:200]}")
        return {"ok": True, "fields": fields}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Patch error: {e}")


@app.delete("/alerts/{alert_id}")
async def alert_delete(alert_id: str, user: Annotated[dict, Depends(require_user)]):
    import httpx as _httpx
    _surl, _skey = _supabase_creds()
    try:
        r = _httpx.delete(
            f"{_surl}/rest/v1/analysis_alerts?id=eq.{alert_id}&user_id=eq.{user['id']}",
            headers={"apikey": _skey, "Authorization": f"Bearer {_skey}",
                     "Prefer": "return=minimal"},
            timeout=5.0,
        )
        if r.status_code >= 300:
            raise HTTPException(status_code=500, detail=f"Delete failed: {r.text[:200]}")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete error: {e}")


# ─── Web Push subscriptions ─────────────────────────────────────────────────

@app.post("/push/subscribe")
async def push_subscribe(payload: PushSubscribeRequest, user: Annotated[dict, Depends(require_user)]):
    """Enregistre une subscription Web Push (service worker côté client).
    Upsert par (user_id, endpoint) pour éviter les doublons.
    """
    import httpx as _httpx
    _surl, _skey = _supabase_creds()
    body = {
        "user_id": user["id"],
        "endpoint": payload.endpoint,
        "p256dh": payload.p256dh,
        "auth_key": payload.auth_key,
        "user_agent": payload.user_agent,
    }
    body = {k: v for k, v in body.items() if v is not None}
    try:
        r = _httpx.post(
            f"{_surl}/rest/v1/push_subscriptions",
            headers={"apikey": _skey, "Authorization": f"Bearer {_skey}",
                     "Content-Type": "application/json",
                     "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=body, timeout=5.0,
        )
        if r.status_code >= 300:
            raise HTTPException(status_code=500, detail=f"Subscribe failed: {r.text[:200]}")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Subscribe error: {e}")


@app.get("/push/vapid-public-key")
async def push_vapid_public():
    """Retourne la clé publique VAPID pour que le client puisse s'abonner."""
    import os as _os
    pub = _os.getenv("VAPID_PUBLIC_KEY", "").strip()
    if not pub:
        raise HTTPException(status_code=500, detail="VAPID_PUBLIC_KEY non configurée")
    return {"public_key": pub}


# ─── Cron check alerts (appelé toutes les 6h par Railway cron) ──────────────

@app.post("/cron/check-alerts")
async def cron_check_alerts(request: Request):
    """Worker cron : parcourt les alerts enabled + fired_at IS NULL,
    évalue chaque trigger, notifie si condition satisfaite.
    Auth : header X-Cron-Secret = CRON_SECRET env var.
    """
    import os as _os
    expected = _os.getenv("CRON_SECRET", "").strip()
    provided = request.headers.get("x-cron-secret") or request.headers.get("X-Cron-Secret") or ""
    if not expected or provided != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from core.alerts.checker import run_check_cycle
    result = run_check_cycle()
    return result




# ─── RGPD : export données + suppression compte (art. 17 + 20) ──────────────

@app.get("/user/export-data")
async def user_export_data(user: Annotated[dict, Depends(require_user)]):
    """Droit à la portabilité (RGPD art. 20) : export JSON des données user."""
    import httpx as _httpx
    import os as _os
    _surl = _os.getenv("SUPABASE_URL", "").rstrip("/")
    _skey = (_os.getenv("SUPABASE_SERVICE_KEY")
             or _os.getenv("SUPABASE_SECRET_KEY")
             or _os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    if not _surl or not _skey:
        raise HTTPException(status_code=500, detail="Supabase non configuré")

    h = {"apikey": _skey, "Authorization": f"Bearer {_skey}"}
    uid = user["id"]

    def _fetch(table: str, extra: str = "") -> list:
        try:
            r = _httpx.get(
                f"{_surl}/rest/v1/{table}?user_id=eq.{uid}{extra}",
                headers=h, timeout=8.0,
            )
            return r.json() if r.status_code < 300 else []
        except Exception:
            return []

    return {
        "exported_at": _utcnow().isoformat(),
        "user": {"id": uid, "email": user.get("email")},
        "preferences": _fetch("user_preferences"),
        "analyses_history": _fetch("analyses_history", "&order=created_at.desc"),
        "documents": _fetch("analysis_documents", "&select=id,filename,mime_type,size_bytes,created_at"),
        "subscriptions": _fetch("user_subscriptions"),
    }


@app.post("/user/delete-account")
async def user_delete_account(user: Annotated[dict, Depends(require_user)]):
    """Droit à l'effacement (RGPD art. 17) : suppression complète du compte.

    Supprime en cascade : analyses_history, user_preferences, user_subscriptions,
    analysis_documents, puis l'auth user via Supabase admin API.
    """
    import httpx as _httpx
    import os as _os
    _surl = _os.getenv("SUPABASE_URL", "").rstrip("/")
    _skey = (_os.getenv("SUPABASE_SERVICE_KEY")
             or _os.getenv("SUPABASE_SECRET_KEY")
             or _os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    if not _surl or not _skey:
        raise HTTPException(status_code=500, detail="Supabase non configuré")

    h = {"apikey": _skey, "Authorization": f"Bearer {_skey}",
         "Content-Type": "application/json", "Prefer": "return=minimal"}
    uid = user["id"]
    deleted: dict[str, bool] = {}

    for table in ("analyses_history", "user_subscriptions",
                  "analysis_documents", "user_preferences"):
        try:
            r = _httpx.delete(
                f"{_surl}/rest/v1/{table}?user_id=eq.{uid}",
                headers=h, timeout=10.0,
            )
            deleted[table] = r.status_code < 300
        except Exception as e:
            log.warning(f"[rgpd] delete {table} failed: {e}")
            deleted[table] = False

    try:
        r = _httpx.delete(
            f"{_surl}/auth/v1/admin/users/{uid}",
            headers={"apikey": _skey, "Authorization": f"Bearer {_skey}"},
            timeout=10.0,
        )
        deleted["auth.users"] = r.status_code < 300
    except Exception as e:
        log.warning(f"[rgpd] delete auth user failed: {e}")
        deleted["auth.users"] = False

    return {"ok": True, "deleted": deleted}


# ─── Sentinelle : admin errors dashboard ────────────────────────────────────

# ─── Historique user : renommage + favoris ──────────────────────────────────

class HistoryPatchRequest(BaseModel):
    display_name: Optional[str] = None
    is_favorite: Optional[bool] = None


@app.patch("/history/{history_id}")
async def patch_history(
    history_id: str,
    payload: HistoryPatchRequest,
    user: Annotated[dict, Depends(require_user)],
):
    """Rename (display_name) ou toggle favori (is_favorite) sur une row d'historique."""
    import httpx as _httpx
    import os as _os
    _surl = _os.getenv("SUPABASE_URL", "").rstrip("/")
    _skey = (_os.getenv("SUPABASE_SERVICE_KEY")
             or _os.getenv("SUPABASE_SECRET_KEY")
             or _os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    if not _surl or not _skey:
        raise HTTPException(status_code=500, detail="Supabase non configuré")

    fields: dict[str, Any] = {}
    if payload.display_name is not None:
        fields["display_name"] = payload.display_name.strip()[:120] or None
    if payload.is_favorite is not None:
        fields["is_favorite"] = payload.is_favorite
    if not fields:
        raise HTTPException(status_code=400, detail="Aucun champ à modifier")

    try:
        r = _httpx.patch(
            f"{_surl}/rest/v1/analyses_history?id=eq.{history_id}&user_id=eq.{user['id']}",
            headers={"apikey": _skey, "Authorization": f"Bearer {_skey}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"},
            json=fields,
            timeout=5.0,
        )
        if r.status_code >= 300:
            raise HTTPException(status_code=500, detail=f"Patch failed: {r.text[:200]}")
        return {"ok": True, "fields": fields}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Patch error: {e}")


@app.delete("/history/{history_id}")
async def delete_history(
    history_id: str,
    user: Annotated[dict, Depends(require_user)],
):
    """Supprime une row d'historique (user peut nettoyer sa liste)."""
    import httpx as _httpx
    import os as _os
    _surl = _os.getenv("SUPABASE_URL", "").rstrip("/")
    _skey = (_os.getenv("SUPABASE_SERVICE_KEY")
             or _os.getenv("SUPABASE_SECRET_KEY")
             or _os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    if not _surl or not _skey:
        raise HTTPException(status_code=500, detail="Supabase non configuré")
    try:
        r = _httpx.delete(
            f"{_surl}/rest/v1/analyses_history?id=eq.{history_id}&user_id=eq.{user['id']}",
            headers={"apikey": _skey, "Authorization": f"Bearer {_skey}",
                     "Prefer": "return=minimal"},
            timeout=5.0,
        )
        if r.status_code >= 300:
            raise HTTPException(status_code=500, detail=f"Delete failed: {r.text[:200]}")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete error: {e}")


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
                    "history_id": str(row.get("id", "")),
                    "job_id": str(row.get("id", "")),
                    "kind": row.get("kind"),
                    "label": row.get("label"),
                    "display_name": row.get("display_name"),
                    "is_favorite": bool(row.get("is_favorite", False)),
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
# Documents uploadés par l'user (PDF/XLSX/contrats) — extraction Gemini Vision
# ---------------------------------------------------------------------------

from fastapi import UploadFile, File, Form

_MAX_DOC_SIZE = 20 * 1024 * 1024  # 20 Mo
_ALLOWED_DOC_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "image/png",
    "image/jpeg",
    "image/webp",
    "text/plain",
    "text/csv",
}


@app.post("/documents/upload")
async def upload_document(
    user: Annotated[dict, Depends(require_user)],
    file: UploadFile = File(...),
    analysis_id: Optional[str] = Form(None),
):
    """Upload d'un document utilisateur (PDF/XLSX/image/contrat) lié à une analyse.

    - Vérifie taille (max 20 Mo) et MIME accepté.
    - Cache : si l'user a déjà uploadé ce hash, renvoie l'existant.
    - Stocke dans Supabase Storage (bucket privé `analysis_documents`, RLS).
    - Crée la row DB (status=uploaded). L'extraction se déclenche via /extract.
    """
    import db as _db
    from core.documents.extractor import file_hash as _hash

    content = await file.read()
    if not content:
        raise HTTPException(400, "Fichier vide")
    if len(content) > _MAX_DOC_SIZE:
        raise HTTPException(413, f"Fichier trop volumineux (>{_MAX_DOC_SIZE // 1024 // 1024} Mo)")

    mime = file.content_type or "application/octet-stream"
    if mime not in _ALLOWED_DOC_MIMES:
        raise HTTPException(415, f"Type de fichier non accepté : {mime}")

    fhash = _hash(content)

    # Cache : déjà uploadé ?
    existing = _db.find_document_by_hash(user["id"], fhash)
    if existing:
        log.info(f"[documents] cache HIT user={user['id']} hash={fhash[:10]}")
        return {
            "id": existing["id"],
            "status": existing.get("status"),
            "filename": existing.get("filename"),
            "type_detected": existing.get("type_detected"),
            "extracted_data": existing.get("extracted_data"),
            "validated": existing.get("validated"),
            "cached": True,
        }

    storage_path = _db.upload_user_document(user["id"], content, file.filename or "doc", mime)
    if not storage_path:
        raise HTTPException(500, "Échec upload Supabase Storage")

    doc_id = _db.insert_document_row(
        user_id=user["id"],
        analysis_id=analysis_id,
        filename=file.filename or "doc",
        mime_type=mime,
        size_bytes=len(content),
        file_hash=fhash,
        storage_path=storage_path,
    )
    if not doc_id:
        # rollback Storage si DB échoue
        _db.delete_user_document(storage_path)
        raise HTTPException(500, "Échec insertion DB")

    log.info(f"[documents] upload OK id={doc_id} user={user['id']} {len(content)}o")
    return {
        "id": doc_id,
        "status": "uploaded",
        "filename": file.filename,
        "size_bytes": len(content),
        "mime_type": mime,
    }


@app.post("/documents/{doc_id}/extract")
async def extract_document_endpoint(
    doc_id: str,
    user: Annotated[dict, Depends(require_user)],
):
    """Lance l'extraction Gemini Vision (ou XLSX parser) sur un document uploadé.

    Met à jour la row DB avec extracted_data + status='extracted' (ou 'error').
    Renvoie le JSON extrait directement.
    """
    import db as _db
    from core.documents.extractor import extract_document

    row = _db.get_document_row(doc_id, user["id"])
    if not row:
        raise HTTPException(404, "Document introuvable")

    # Si déjà extrait avec succès et user n'a pas demandé reprocess → renvoie cache
    if row.get("status") == "extracted" and row.get("extracted_data"):
        return {
            "id": doc_id,
            "type_detected": row.get("type_detected"),
            "extracted_data": row.get("extracted_data"),
            "cached": True,
        }

    _db.update_document_row(doc_id, {"status": "extracting"})

    content = _db.download_user_document(row["storage_path"])
    if content is None:
        _db.update_document_row(
            doc_id, {"status": "error", "extraction_error": "Téléchargement Storage échoué"}
        )
        raise HTTPException(500, "Téléchargement fichier échoué")

    result = extract_document(
        file_bytes=content,
        filename=row.get("filename") or "doc",
        mime_type=row.get("mime_type"),
    )

    if result.error:
        _db.update_document_row(
            doc_id,
            {
                "status": "error",
                "extraction_error": result.error,
                "type_detected": result.type_detected.value,
            },
        )
        raise HTTPException(500, f"Extraction échouée : {result.error}")

    _db.update_document_row(
        doc_id,
        {
            "status": "extracted",
            "type_detected": result.type_detected.value,
            "extracted_data": result.data,
            "extraction_error": None,
        },
    )

    return {
        "id": doc_id,
        "type_detected": result.type_detected.value,
        "extracted_data": result.data,
        "confidence": result.confidence,
        "source": result.source,
    }


@app.patch("/documents/{doc_id}")
async def update_document(
    doc_id: str,
    user: Annotated[dict, Depends(require_user)],
    body: dict,
):
    """User valide ou édite les données extraites avant intégration scoring.

    Body accepté : {"extracted_data": {...}, "validated": true|false}
    """
    import db as _db

    row = _db.get_document_row(doc_id, user["id"])
    if not row:
        raise HTTPException(404, "Document introuvable")

    fields: dict = {}
    if "extracted_data" in body:
        fields["extracted_data"] = body["extracted_data"]
    if "validated" in body:
        fields["validated"] = bool(body["validated"])
        if fields["validated"]:
            fields["status"] = "validated"

    if not fields:
        raise HTTPException(400, "Aucun champ à mettre à jour")

    ok = _db.update_document_row(doc_id, fields)
    if not ok:
        raise HTTPException(500, "Échec update DB")

    updated = _db.get_document_row(doc_id, user["id"])
    return updated or {"id": doc_id, "ok": True}


@app.get("/analyses/{analysis_id}/documents")
async def list_analysis_documents(
    analysis_id: str,
    user: Annotated[dict, Depends(require_user)],
):
    """Liste tous les documents de l'user liés à une analyse."""
    import db as _db
    docs = _db.list_documents(user["id"], analysis_id=analysis_id)
    return {"analysis_id": analysis_id, "documents": docs}


@app.get("/documents")
async def list_user_documents(user: Annotated[dict, Depends(require_user)]):
    """Liste tous les documents de l'user (toutes analyses)."""
    import db as _db
    return {"documents": _db.list_documents(user["id"])}


@app.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    user: Annotated[dict, Depends(require_user)],
):
    """Supprime un document (Storage + DB)."""
    import db as _db
    row = _db.get_document_row(doc_id, user["id"])
    if not row:
        raise HTTPException(404, "Document introuvable")
    _db.delete_user_document(row["storage_path"])
    _db.delete_document_row(doc_id)
    return {"id": doc_id, "deleted": True}


# ---------------------------------------------------------------------------
# Entrée locale
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
