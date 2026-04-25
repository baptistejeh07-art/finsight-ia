"""Endpoint admin pour le dashboard Sentinelle (pipeline_errors)."""
from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException

from backend._common import require_admin, supabase_creds, utcnow

router = APIRouter(prefix="/admin", tags=["admin-sentinel"])


@router.get("/errors")
async def admin_errors(user: Annotated[dict, Depends(require_admin)],
                        severity: Optional[str] = None,
                        hours: int = 24,
                        limit: int = 200):
    """Liste pipeline_errors des N dernières heures (admin only)."""
    surl, skey = supabase_creds()
    cutoff = (utcnow() - timedelta(hours=max(1, min(720, hours)))).isoformat()
    params = {
        "created_at": f"gte.{cutoff}",
        "order": "created_at.desc",
        "limit": str(max(1, min(500, limit))),
    }
    if severity and severity in ("info", "warn", "error", "critical"):
        params["severity"] = f"eq.{severity}"
    try:
        r = httpx.get(
            f"{surl}/rest/v1/pipeline_errors",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}"},
            params=params,
            timeout=8.0,
        )
        errors = r.json() if r.status_code < 300 else []
        stats = {"critical": 0, "error": 0, "warn": 0, "info": 0}
        by_type: dict[str, int] = {}
        for e in errors:
            sev = e.get("severity", "info")
            stats[sev] = stats.get(sev, 0) + 1
            et = e.get("error_type", "unknown")
            by_type[et] = by_type.get(et, 0) + 1
        return {"errors": errors, "stats": stats, "by_type": by_type,
                "window_hours": hours}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errors fetch: {e}")


@router.post("/sentinel/test")
async def admin_sentinel_test(user: Annotated[dict, Depends(require_admin)],
                                severity: str = "error"):
    """Déclenche un faux sentinel issue pour tester le pipeline complet :
    insertion table pipeline_errors + envoi email Resend admin.

    Usage : POST /admin/sentinel/test?severity=error
    Réponse : {"row_id": "...", "wakeup_attempted": true, "ts": "..."}

    À appeler une seule fois pour valider que l'email arrive bien dans
    la boîte SENTINEL_ADMIN_EMAIL. Utile aussi pour tester quand on
    suspecte que l'environnement Railway ne propage pas RESEND_API_KEY.
    """
    if severity not in ("warn", "error", "critical"):
        raise HTTPException(400, "severity must be warn|error|critical")
    from core.sentinel.recorder import record_error
    row_id = record_error(
        severity=severity,
        error_type="sentinel_test_manual",
        message=(f"Test manuel déclenché depuis /admin/sentinel/test à "
                  f"{utcnow().isoformat()}. Si vous lisez cet email, le canal "
                  f"d'alerte sentinel fonctionne de bout en bout."),
        ticker="TEST",
        kind="test",
        node="manual",
        context={"rule": "manual_test", "triggered_by": user.get("email")},
        user_id=user.get("id"),
    )
    return {
        "ok": True,
        "row_id": row_id,
        "severity": severity,
        "message": "Test envoyé. Vérifiez la boîte mail SENTINEL_ADMIN_EMAIL.",
        "ts": utcnow().isoformat(),
    }
