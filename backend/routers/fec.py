"""Endpoints upload + parse FEC (Fichier des Écritures Comptables)."""
from __future__ import annotations

import logging
from typing import Annotated, Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend._common import require_user, supabase_creds

log = logging.getLogger(__name__)
router = APIRouter(prefix="/fec", tags=["fec"])

_MAX_SIZE = 50 * 1024 * 1024   # 50 Mo


@router.post("/upload")
async def fec_upload(
    user: Annotated[dict, Depends(require_user)],
    file: UploadFile = File(...),
    siren: Optional[str] = Form(None),
):
    """Upload un FEC (.txt ou .fec, CSV tab/pipe). Parse synchrone + retourne résumé."""
    from core.fec import parse_fec, summarize_fec
    content = await file.read()
    if len(content) > _MAX_SIZE:
        raise HTTPException(status_code=413, detail=f"Fichier trop volumineux (>50 Mo)")
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide")

    try:
        entries = parse_fec(content)
        if not entries:
            raise HTTPException(status_code=400, detail="Aucune écriture détectée — format FEC invalide ?")
        summary = summarize_fec(entries)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse FEC fail: {str(e)[:200]}")

    surl, skey = supabase_creds()
    try:
        r = httpx.post(
            f"{surl}/rest/v1/fec_imports",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}",
                     "Content-Type": "application/json", "Prefer": "return=representation"},
            json={
                "user_id": user["id"],
                "siren": siren,
                "filename": file.filename or "fec.txt",
                "size_bytes": len(content),
                "num_lines": len(entries),
                "exercice": summary.get("detected_year"),
                "parsed_summary": summary,
                "status": "parsed",
            },
            timeout=10.0,
        )
        row = (r.json() or [{}])[0] if r.status_code < 300 else {}
        return {"ok": True, "import_id": row.get("id"), "summary": summary, "entries_count": len(entries)}
    except Exception as e:
        log.warning(f"[fec] persist fail: {e}")
        # On retourne quand même le summary même si persist fail
        return {"ok": True, "import_id": None, "summary": summary, "entries_count": len(entries),
                "warning": "Non persisté"}


@router.get("/list")
async def fec_list(user: Annotated[dict, Depends(require_user)]):
    """Liste les FEC importés par le user."""
    surl, skey = supabase_creds()
    try:
        r = httpx.get(
            f"{surl}/rest/v1/fec_imports",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}"},
            params={"user_id": f"eq.{user['id']}", "order": "created_at.desc", "limit": "50"},
            timeout=5.0,
        )
        return {"fecs": r.json() if r.status_code < 300 else []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"List: {e}")
