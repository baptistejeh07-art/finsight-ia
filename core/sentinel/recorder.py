"""Enregistrement des erreurs pipeline + détection data missing.

Tout est silencieux en cas d'échec de log (jamais de crash sentinel qui
masquerait la vraie erreur).
"""
from __future__ import annotations

import functools
import hashlib
import logging
import os
import traceback as _tb
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import httpx

log = logging.getLogger(__name__)


def _supabase_creds() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_KEY")
           or os.getenv("SUPABASE_SECRET_KEY")
           or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "")
    return url, key


def record_error(
    *,
    severity: str,
    error_type: str,
    message: str,
    node: Optional[str] = None,
    ticker: Optional[str] = None,
    kind: Optional[str] = None,
    field_path: Optional[str] = None,
    stack: Optional[str] = None,
    context: Optional[dict] = None,
    user_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> Optional[str]:
    """Enregistre une erreur dans pipeline_errors.

    severity ∈ {'info', 'warn', 'error', 'critical'}
    Retourne l'id de la ligne créée, ou None si échec.
    """
    if severity not in ("info", "warn", "error", "critical"):
        severity = "warn"

    surl, skey = _supabase_creds()
    if not surl or not skey:
        log.info(f"[sentinel] {severity}/{error_type} {ticker or ''} — Supabase absent")
        return None

    payload = {
        "severity": severity,
        "error_type": error_type,
        "message": message[:2000] if message else "",
        "node": node,
        "ticker": ticker,
        "kind": kind,
        "field_path": field_path,
        "stack": stack[:4000] if stack else None,
        "context": context or {},
        "user_id": user_id,
        "job_id": job_id,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        r = httpx.post(
            f"{surl}/rest/v1/pipeline_errors",
            headers={"apikey": skey, "Authorization": f"Bearer {skey}",
                     "Content-Type": "application/json",
                     "Prefer": "return=representation"},
            json=payload,
            timeout=5.0,
        )
        if r.status_code >= 300:
            log.warning(f"[sentinel] record_error HTTP {r.status_code}: {r.text[:200]}")
            return None
        rows = r.json() or []
        row_id = rows[0]["id"] if rows else None

        # Wake-up Claude si critical ou error nouveau (non vu dans la dernière heure)
        if severity in ("critical", "error"):
            trigger_wakeup_if_new(error_type=error_type, ticker=ticker,
                                  message=message, row_id=row_id, context=context or {})
        return row_id
    except Exception as e:
        log.warning(f"[sentinel] record_error exception: {e}")
        return None


def _fingerprint(error_type: str, ticker: Optional[str]) -> str:
    """Hash stable pour dédupliquer par (error_type, ticker)."""
    key = f"{error_type}::{ticker or ''}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


# In-memory dédup cache (survive la durée du process Railway)
_WAKEUP_CACHE: dict[str, datetime] = {}
_WAKEUP_DEDUP_WINDOW = timedelta(hours=1)


def trigger_wakeup_if_new(*, error_type: str, ticker: Optional[str],
                           message: str, row_id: Optional[str],
                           context: dict) -> bool:
    """Déclenche un wake-up Claude via la routine claude.ai SI le bug est nouveau.

    Dédup : ne re-déclenche pas pour la même (error_type, ticker) dans la
    dernière heure. Évite de cramer le plan Max.
    """
    fp = _fingerprint(error_type, ticker)
    now = datetime.now(timezone.utc)
    last = _WAKEUP_CACHE.get(fp)
    if last and (now - last) < _WAKEUP_DEDUP_WINDOW:
        log.info(f"[sentinel] wake-up skipped (dédup {fp}, last {last.isoformat()})")
        return False
    _WAKEUP_CACHE[fp] = now

    routine_url = os.getenv("CLAUDE_ROUTINE_FIRE_URL", "").strip()
    routine_token = os.getenv("CLAUDE_ROUTINE_TOKEN", "").strip()
    if not routine_url or not routine_token:
        log.info(f"[sentinel] wake-up skipped (CLAUDE_ROUTINE_* not configured)")
        return False

    payload_text = (
        f"Type erreur : {error_type}\n"
        f"Ticker : {ticker or 'N/A'}\n"
        f"Message : {message[:500]}\n"
        f"Row ID : {row_id or 'N/A'}\n"
        f"Contexte : {str(context)[:500]}\n"
        f"Timestamp : {now.isoformat()}"
    )
    try:
        r = httpx.post(
            routine_url,
            headers={
                "Authorization": f"Bearer {routine_token}",
                "Content-Type": "application/json",
                "anthropic-beta": "experimental-cc-routine-2026-04-01",
                "anthropic-version": "2023-06-01",
            },
            json={"text": payload_text},
            timeout=8.0,
        )
        if r.status_code >= 300:
            log.warning(f"[sentinel] wake-up HTTP {r.status_code}: {r.text[:200]}")
            return False
        log.info(f"[sentinel] wake-up Claude déclenché pour {error_type}/{ticker}")

        # Marquer row_id comme fired (best-effort)
        if row_id:
            surl, skey = _supabase_creds()
            if surl and skey:
                try:
                    httpx.patch(
                        f"{surl}/rest/v1/pipeline_errors",
                        headers={"apikey": skey, "Authorization": f"Bearer {skey}",
                                 "Content-Type": "application/json",
                                 "Prefer": "return=minimal"},
                        params={"id": f"eq.{row_id}"},
                        json={"wakeup_fired": True,
                              "wakeup_reason": f"new {error_type}"},
                        timeout=3.0,
                    )
                except Exception:
                    pass
        return True
    except Exception as e:
        log.warning(f"[sentinel] wake-up exception: {e}")
        return False


# ---------------------------------------------------------------------------
# Détection data missing
# ---------------------------------------------------------------------------

_CRITICAL_FIELDS = {
    "synthesis": ["recommendation", "target_base", "thesis"],
    "raw_data.company_info": ["ticker", "company_name", "sector"],
    "raw_data.market": ["share_price"],
}


def check_missing_data(state: dict, *, ticker: Optional[str] = None,
                        kind: Optional[str] = None, job_id: Optional[str] = None) -> list[dict]:
    """Parcourt state et identifie les champs critiques absents. Logue chaque miss.

    Retourne la liste des issues trouvées (pour possible affichage UI).
    """
    issues: list[dict] = []
    tk = ticker or state.get("ticker")

    def _get(path: str):
        cur: Any = state
        for part in path.split("."):
            if cur is None:
                return None
            cur = cur.get(part) if isinstance(cur, dict) else getattr(cur, part, None)
        return cur

    # Synthesis
    synthesis = _get("synthesis")
    if synthesis is None:
        issues.append({"field": "synthesis", "severity": "error",
                       "reason": "synthesis absent (LLM failed)"})
    else:
        for f in _CRITICAL_FIELDS["synthesis"]:
            val = getattr(synthesis, f, None) if not isinstance(synthesis, dict) else synthesis.get(f)
            if val is None or (isinstance(val, str) and not val.strip()):
                issues.append({"field": f"synthesis.{f}", "severity": "warn",
                               "reason": f"champ vide/None"})

    # Raw data
    rd = _get("raw_data")
    if rd:
        for field in ["ticker", "company_name", "sector"]:
            ci = rd.get("company_info") if isinstance(rd, dict) else getattr(rd, "company_info", None)
            val = None
            if ci:
                val = ci.get(field) if isinstance(ci, dict) else getattr(ci, field, None)
            if not val:
                issues.append({"field": f"raw_data.company_info.{field}", "severity": "warn",
                               "reason": "absent"})

    # Record chaque issue en pipeline_errors (warn-level)
    for issue in issues:
        record_error(
            severity=issue["severity"],
            error_type=f"missing_data.{issue['field'].split('.')[-1]}",
            message=f"{issue['field']} : {issue['reason']}",
            field_path=issue["field"],
            ticker=tk,
            kind=kind,
            job_id=job_id,
        )

    return issues


# ---------------------------------------------------------------------------
# Décorateur @watched_node
# ---------------------------------------------------------------------------

def watched_node(node_name: str):
    """Wrap un node de graph : capture les exceptions et les loggue en sentinel,
    ré-raise ensuite pour ne pas interférer avec le flow du graph.
    """
    def _decorator(fn):
        @functools.wraps(fn)
        def _wrapped(state: dict, *args, **kwargs):
            try:
                result = fn(state, *args, **kwargs)
                return result
            except Exception as e:
                tk = None
                try:
                    tk = state.get("ticker")
                    if not tk and state.get("raw_data"):
                        rd = state["raw_data"]
                        tk = rd.get("ticker") if isinstance(rd, dict) else getattr(rd, "ticker", None)
                except Exception:
                    pass
                record_error(
                    severity="critical",
                    error_type=f"{node_name}_crash",
                    message=f"{type(e).__name__}: {str(e)[:500]}",
                    node=node_name,
                    ticker=tk,
                    stack=_tb.format_exc(),
                )
                raise
        return _wrapped
    return _decorator
