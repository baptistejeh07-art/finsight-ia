"""Sales agent — API admin pour le pipeline LinkedIn (FinSight 2026-04-25).

Tous les endpoints sont sous /admin/sales-agent/* et protégés require_admin.
Le frontend Next.js consomme ces endpoints depuis /admin/sales-agent.

Architecture (cf memory/sales_agent_architecture.md) :
- Discovery : import CSV manuel (phase 1) → MCP scraping (phase 2)
- Qualification : Claude Haiku score 0-100 sur 5 axes
- Personalization : DM rédigé + PDF démo auto sur le ticker pertinent
- Tracking : Supabase + relances auto J+3 / J+7
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from backend._common import require_admin

# Permet d'importer tools.sales_agent.* (pas dans le PYTHONPATH par défaut)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

log = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/sales-agent", tags=["admin-sales"])


# ─── Discovery / Import ────────────────────────────────────────────────

@router.post("/import-csv")
async def import_csv(
    user: Annotated[dict, Depends(require_admin)],
    file: UploadFile = File(...),
):
    """Import bulk de prospects depuis un CSV (phase 1).

    Le CSV doit avoir au minimum une colonne `linkedin_url`. Voir
    tools/sales_agent/discovery_csv.py pour le format complet (headers
    optionnels : name, headline, bio, recent_post_1/2/3).

    Retourne le nombre de prospects insérés (ou updated si déjà existants).
    """
    from tools.sales_agent.discovery_csv import parse_csv
    from tools.sales_agent.tracking import insert_prospect

    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    prospects = parse_csv(text)
    if not prospects:
        raise HTTPException(400, "Aucun prospect valide trouvé dans le CSV. "
                                  "Vérifiez la colonne linkedin_url.")
    inserted = 0
    failed = 0
    for p in prospects:
        pid = insert_prospect(
            linkedin_url=p.linkedin_url,
            name=p.name,
            headline=p.headline,
            bio=p.bio,
            recent_posts=p.recent_posts,
        )
        if pid:
            inserted += 1
        else:
            failed += 1
    log.info(f"[sales] CSV import : {inserted} ok, {failed} fail")
    return {
        "ok": True,
        "imported": inserted,
        "failed": failed,
        "total": len(prospects),
    }


@router.get("/csv-template")
async def get_template(user: Annotated[dict, Depends(require_admin)]):
    """Retourne le template CSV à fournir à l'admin."""
    from tools.sales_agent.discovery_csv import get_csv_template
    return {"csv": get_csv_template()}


# ─── Qualification + Personalization ──────────────────────────────────

@router.post("/qualify/{prospect_id}")
async def qualify_one(
    user: Annotated[dict, Depends(require_admin)],
    prospect_id: str,
    generate_pdf: bool = True,
):
    """Pipeline complet pour 1 prospect : qualification + personalization.

    1. Lit le prospect en Supabase
    2. Lance qualification (Claude Haiku, ~2-3s, ~0.001$)
    3. Si score >= 70 : lance personalization (DM + PDF démo)
    4. Update la ligne Supabase

    Returns : {ok, score, breakdown, dm_text?, pdf_path?, target_ticker?}
    """
    from tools.sales_agent.qualification import qualify_prospect
    from tools.sales_agent.personalization import personalize_prospect
    from tools.sales_agent.tracking import get_prospect, insert_prospect

    p = get_prospect(prospect_id)
    if not p:
        raise HTTPException(404, "Prospect introuvable")
    qual = qualify_prospect(
        name=p.get("name") or "",
        headline=p.get("headline") or "",
        bio=p.get("bio"),
        recent_posts=p.get("recent_posts") or [],
    )
    out: dict = {
        "ok": True,
        "score": qual.score,
        "breakdown": qual.breakdown,
        "reasoning": qual.reasoning,
        "target_ticker": qual.target_ticker,
    }
    dm_text = None
    pdf_path = None
    if qual.score >= 70:
        # Hook = premier post récent si dispo
        recent_post = None
        rp = p.get("recent_posts") or []
        if isinstance(rp, list) and rp:
            recent_post = (rp[0].get("text") if isinstance(rp[0], dict)
                            else None)
        perso = personalize_prospect(
            name=p.get("name") or "",
            headline=p.get("headline") or "",
            recent_post=recent_post,
            target_ticker=qual.target_ticker,
            generate_pdf=generate_pdf,
        )
        dm_text = perso.dm_text
        pdf_path = perso.pdf_demo_path
        out.update({"dm_text": dm_text, "pdf_path": pdf_path,
                     "hook_style": perso.hook_style})
    # Update prospect avec qualif + DM
    insert_prospect(
        linkedin_url=p["linkedin_url"],
        name=p.get("name"),
        headline=p.get("headline"),
        bio=p.get("bio"),
        recent_posts=p.get("recent_posts"),
        qualification_score=qual.score,
        qualification_breakdown=qual.breakdown,
        qualification_reasoning=qual.reasoning,
        target_ticker=qual.target_ticker,
        dm_draft=dm_text,
        pdf_demo_path=pdf_path,
    )
    return out


@router.post("/qualify-all")
async def qualify_all(
    user: Annotated[dict, Depends(require_admin)],
    limit: int = 30,
):
    """Lance la qualification + personalization sur les prospects pas
    encore scorés (score IS NULL). Cap à `limit` pour budget LLM."""
    import httpx
    import os
    from tools.sales_agent.tracking import _supabase_creds, _headers

    surl, skey = _supabase_creds()
    if not surl or not skey:
        raise HTTPException(500, "Supabase non configuré")
    r = httpx.get(
        f"{surl}/rest/v1/sales_prospects",
        headers=_headers(skey),
        params={"qualification_score": "is.null",
                 "limit": str(min(50, max(1, limit)))},
        timeout=8.0,
    )
    todo = r.json() if r.status_code < 300 else []
    results = []
    for p in todo:
        try:
            res = await qualify_one(user, p["id"], generate_pdf=False)
            results.append({"id": p["id"], "score": res.get("score")})
        except Exception as e:
            log.warning(f"[sales] qualify_all error on {p['id']} : {e}")
            results.append({"id": p["id"], "error": str(e)[:200]})
    return {"ok": True, "qualified": len(results), "results": results}


# ─── Top today + status ────────────────────────────────────────────────

@router.get("/top-today")
async def top_today(
    user: Annotated[dict, Depends(require_admin)],
    limit: int = 10,
    min_score: int = 70,
):
    """Top N prospects qualifiés et pas encore contactés."""
    from tools.sales_agent.tracking import list_top_today
    return {"prospects": list_top_today(limit=limit, min_score=min_score)}


@router.post("/status/{prospect_id}")
async def set_status(
    user: Annotated[dict, Depends(require_admin)],
    prospect_id: str,
    status: str,
    response_text: Optional[str] = None,
    notes: Optional[str] = None,
    conversion_amount: Optional[float] = None,
):
    """Update le statut d'un prospect.

    status ∈ {queued, sent, replied, converted, ghosted}
    """
    from tools.sales_agent.tracking import update_status
    if status not in ("queued", "sent", "replied", "converted", "ghosted"):
        raise HTTPException(400, "status invalide")
    ok = update_status(prospect_id, status,
                          response_text=response_text,
                          notes=notes,
                          conversion_amount=conversion_amount)
    if not ok:
        raise HTTPException(500, "Update échoué (cf logs)")
    return {"ok": True}


@router.get("/stats")
async def stats(user: Annotated[dict, Depends(require_admin)]):
    """Stats hebdo + cap journalier restant."""
    from tools.sales_agent.tracking import stats_weekly
    return stats_weekly()


# ─── Relances J+3 / J+7 ────────────────────────────────────────────────

@router.get("/relances/queue")
async def get_relances(user: Annotated[dict, Depends(require_admin)]):
    """Retourne les prospects qui devraient recevoir une relance
    (séparés J+3 et J+7). Le texte de relance est rédigé à la demande
    via /relances/draft-pending pour économiser le LLM."""
    from tools.sales_agent.relance import find_pending_relances
    return find_pending_relances()


@router.post("/relances/draft-pending")
async def draft_pending_relances(
    user: Annotated[dict, Depends(require_admin)],
    limit: int = 20,
):
    """Génère le texte de toutes les relances en attente (J+3 + J+7).

    Stocke chaque texte rédigé en `sales_prospect_status.relance_X_text`
    sans marquer l'envoi (Baptiste cliquera "Envoyé" après avoir collé
    dans LinkedIn natif). Cap `limit` pour budget LLM.
    """
    from tools.sales_agent.relance import find_pending_relances, draft_relance
    pending = find_pending_relances()
    drafted = []
    failed = []
    count = 0
    for row in pending["prospects_to_relance_3"]:
        if count >= limit:
            break
        if row.get("relance_1_text"):
            continue  # déjà rédigée
        text = draft_relance(row, "J3")
        if text:
            drafted.append({"id": row["id"], "type": "J3",
                              "text_preview": text[:120]})
            count += 1
        else:
            failed.append(row["id"])
    for row in pending["prospects_to_relance_7"]:
        if count >= limit:
            break
        if row.get("relance_2_text"):
            continue
        text = draft_relance(row, "J7")
        if text:
            drafted.append({"id": row["id"], "type": "J7",
                              "text_preview": text[:120]})
            count += 1
        else:
            failed.append(row["id"])
    return {"ok": True, "drafted": drafted, "failed": failed,
              "count": len(drafted)}


@router.post("/relances/sent/{prospect_status_id}")
async def mark_relance_sent_endpoint(
    user: Annotated[dict, Depends(require_admin)],
    prospect_status_id: str,
    relance_type: str,
):
    """Marque la relance comme envoyée (Baptiste a copié dans LinkedIn).

    relance_type ∈ {J3, J7}.
    """
    from tools.sales_agent.relance import mark_relance_sent
    if relance_type not in ("J3", "J7"):
        raise HTTPException(400, "relance_type doit être J3 ou J7")
    ok = mark_relance_sent(prospect_status_id, relance_type)
    if not ok:
        raise HTTPException(500, "Update échoué")
    return {"ok": True}


@router.post("/relances/auto-ghost")
async def auto_ghost(
    user: Annotated[dict, Depends(require_admin)],
    days_threshold: int = 14,
):
    """Hygiène queue : marque comme 'ghosted' les prospects sans réponse
    après les 2 relances + days_threshold jours."""
    from tools.sales_agent.relance import auto_ghost_old_prospects
    n = auto_ghost_old_prospects(days_threshold=days_threshold)
    return {"ok": True, "ghosted": n}
