"""Persistence Supabase Postgres via REST API (PostgREST).

On n'utilise PAS le SDK supabase-py (incompat Python 3.14 + dépendances lourdes).
On parle directement à PostgREST avec httpx + clé service_role.

Table SQL à créer dans Supabase (one-shot) :

    CREATE TABLE IF NOT EXISTS analyses_history (
        id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id      uuid NOT NULL,
        kind         text NOT NULL,
        label        text,
        ticker       text,
        status       text NOT NULL DEFAULT 'done',
        created_at   timestamptz NOT NULL DEFAULT now(),
        finished_at  timestamptz,
        files        jsonb,
        meta         jsonb
    );
    CREATE INDEX IF NOT EXISTS idx_analyses_history_user_created
        ON analyses_history (user_id, created_at DESC);

RLS désactivée car on attaque via service_role (server-side).
"""

from __future__ import annotations
import os
import logging
from datetime import datetime
from typing import Optional, Any
import httpx

log = logging.getLogger(__name__)

_SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
_SERVICE_KEY = (
    os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_SECRET_KEY")
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or ""
)


def _enabled() -> bool:
    return bool(_SUPABASE_URL and _SERVICE_KEY)


def _headers() -> dict:
    return {
        "apikey": _SERVICE_KEY,
        "Authorization": f"Bearer {_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def insert_analysis(
    *,
    user_id: str,
    kind: str,
    label: Optional[str] = None,
    ticker: Optional[str] = None,
    status: str = "done",
    files: Optional[dict] = None,
    meta: Optional[dict] = None,
    finished_at: Optional[datetime] = None,
) -> bool:
    """Persiste une analyse terminée dans la table analyses_history.

    Silencieux si Supabase non configuré (renvoie False). Logué si erreur HTTP.
    """
    if not _enabled():
        log.debug("[db] insert_analysis skipped : Supabase non configuré")
        return False

    payload = {
        "user_id": user_id,
        "kind": kind,
        "label": label,
        "ticker": ticker,
        "status": status,
        "files": files,
        "meta": meta,
    }
    if finished_at is not None:
        payload["finished_at"] = finished_at.isoformat()
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        r = httpx.post(
            f"{_SUPABASE_URL}/rest/v1/analyses_history",
            headers=_headers(),
            json=payload,
            timeout=8.0,
        )
        if r.status_code >= 300:
            log.warning(f"[db] insert_analysis HTTP {r.status_code} : {r.text[:200]}")
            return False
        return True
    except Exception as e:
        log.warning(f"[db] insert_analysis exception : {e}")
        return False


_BUCKET = os.getenv("SUPABASE_BUCKET", "analyses")


def upload_file(local_path, remote_path: str, content_type: Optional[str] = None) -> Optional[str]:
    """Upload un fichier local vers Supabase Storage.

    Retourne l'URL publique du fichier, ou None si échec / Storage non configuré.
    Le bucket doit exister (créé manuellement dans Supabase, public-read).
    """
    from pathlib import Path as _P
    if not _enabled():
        return None
    p = _P(local_path)
    if not p.exists() or not p.is_file():
        log.warning(f"[db] upload_file: fichier introuvable {local_path}")
        return None

    ct = content_type or {
        ".pdf": "application/pdf",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(p.suffix.lower(), "application/octet-stream")

    try:
        with open(p, "rb") as fh:
            data = fh.read()
        url = f"{_SUPABASE_URL}/storage/v1/object/{_BUCKET}/{remote_path}"
        r = httpx.post(
            url,
            headers={
                "apikey": _SERVICE_KEY,
                "Authorization": f"Bearer {_SERVICE_KEY}",
                "Content-Type": ct,
                "x-upsert": "true",
            },
            content=data,
            timeout=30.0,
        )
        if r.status_code >= 300:
            log.warning(f"[db] upload_file HTTP {r.status_code} : {r.text[:200]}")
            return None
        # URL publique (bucket public-read)
        return f"{_SUPABASE_URL}/storage/v1/object/public/{_BUCKET}/{remote_path}"
    except Exception as e:
        log.warning(f"[db] upload_file exception : {e}")
        return None


def upsert_job_state(job: dict) -> bool:
    """Persiste l'état complet d'un job dans la table jobs_state.

    Schema attendu :
        CREATE TABLE IF NOT EXISTS jobs_state (
            job_id      uuid PRIMARY KEY,
            kind        text NOT NULL,
            status      text NOT NULL,
            progress    int DEFAULT 0,
            user_id     text,
            label       text,
            created_at  timestamptz DEFAULT now(),
            started_at  timestamptz,
            finished_at timestamptz,
            result      jsonb,
            error       text
        );

    Best-effort : silencieux si Supabase non configuré.
    """
    if not _enabled() or not job.get("job_id"):
        return False
    payload = {
        "job_id": job["job_id"],
        "kind": job.get("kind"),
        "status": job.get("status"),
        "progress": job.get("progress") or 0,
        "user_id": job.get("user_id"),
        "label": job.get("label"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "result": job.get("result"),
        "error": job.get("error"),
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        r = httpx.post(
            f"{_SUPABASE_URL}/rest/v1/jobs_state",
            headers={**_headers(), "Prefer": "resolution=merge-duplicates"},
            json=payload,
            timeout=8.0,
        )
        if r.status_code >= 300:
            log.warning(f"[db] upsert_job_state HTTP {r.status_code} : {r.text[:200]}")
            return False
        return True
    except Exception as e:
        log.warning(f"[db] upsert_job_state exception : {e}")
        return False


def get_job_state(job_id: str) -> Optional[dict]:
    """Fetch un job depuis jobs_state. None si pas trouvé ou DB off."""
    if not _enabled():
        return None
    try:
        r = httpx.get(
            f"{_SUPABASE_URL}/rest/v1/jobs_state",
            headers=_headers(),
            params={"job_id": f"eq.{job_id}", "limit": "1"},
            timeout=6.0,
        )
        if r.status_code >= 300:
            return None
        rows = r.json() or []
        return rows[0] if rows else None
    except Exception as e:
        log.debug(f"[db] get_job_state exception : {e}")
        return None


# ==============================================================================
# Documents uploadés par l'user (analysis_documents)
# ==============================================================================

_DOCS_BUCKET = os.getenv("SUPABASE_DOCS_BUCKET", "analysis_documents")


def upload_user_document(
    user_id: str,
    file_bytes: bytes,
    filename: str,
    content_type: str,
) -> Optional[str]:
    """Upload binaire dans le bucket privé analysis_documents, dossier user_id/.

    Renvoie le storage_path (relatif au bucket) ou None si échec.
    """
    if not _enabled():
        return None
    import uuid as _uuid

    safe_name = filename.replace("/", "_").replace("\\", "_")
    storage_path = f"{user_id}/{_uuid.uuid4().hex}_{safe_name}"
    try:
        r = httpx.post(
            f"{_SUPABASE_URL}/storage/v1/object/{_DOCS_BUCKET}/{storage_path}",
            headers={
                "apikey": _SERVICE_KEY,
                "Authorization": f"Bearer {_SERVICE_KEY}",
                "Content-Type": content_type or "application/octet-stream",
                "x-upsert": "false",
            },
            content=file_bytes,
            timeout=30.0,
        )
        if r.status_code >= 300:
            log.warning(f"[db] upload_user_document HTTP {r.status_code} : {r.text[:200]}")
            return None
        return storage_path
    except Exception as e:
        log.warning(f"[db] upload_user_document exception : {e}")
        return None


def delete_user_document(storage_path: str) -> bool:
    if not _enabled():
        return False
    try:
        r = httpx.delete(
            f"{_SUPABASE_URL}/storage/v1/object/{_DOCS_BUCKET}/{storage_path}",
            headers={"apikey": _SERVICE_KEY, "Authorization": f"Bearer {_SERVICE_KEY}"},
            timeout=10.0,
        )
        return r.status_code < 300
    except Exception as e:
        log.warning(f"[db] delete_user_document exception : {e}")
        return False


def download_user_document(storage_path: str) -> Optional[bytes]:
    if not _enabled():
        return None
    try:
        r = httpx.get(
            f"{_SUPABASE_URL}/storage/v1/object/{_DOCS_BUCKET}/{storage_path}",
            headers={"apikey": _SERVICE_KEY, "Authorization": f"Bearer {_SERVICE_KEY}"},
            timeout=30.0,
        )
        if r.status_code >= 300:
            return None
        return r.content
    except Exception as e:
        log.warning(f"[db] download_user_document exception : {e}")
        return None


def insert_document_row(
    *,
    user_id: str,
    analysis_id: Optional[str],
    filename: str,
    mime_type: str,
    size_bytes: int,
    file_hash: str,
    storage_path: str,
) -> Optional[str]:
    """Insert une row dans analysis_documents, renvoie l'id créé ou None."""
    if not _enabled():
        return None
    payload = {
        "user_id": user_id,
        "analysis_id": analysis_id,
        "filename": filename,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "file_hash": file_hash,
        "storage_path": storage_path,
        "status": "uploaded",
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        r = httpx.post(
            f"{_SUPABASE_URL}/rest/v1/analysis_documents",
            headers={**_headers(), "Prefer": "return=representation"},
            json=payload,
            timeout=8.0,
        )
        if r.status_code >= 300:
            log.warning(f"[db] insert_document_row HTTP {r.status_code} : {r.text[:300]}")
            return None
        rows = r.json()
        return rows[0]["id"] if rows else None
    except Exception as e:
        log.warning(f"[db] insert_document_row exception : {e}")
        return None


def update_document_row(doc_id: str, fields: dict) -> bool:
    if not _enabled():
        return False
    fields = {k: v for k, v in fields.items() if v is not None}
    if not fields:
        return True
    try:
        r = httpx.patch(
            f"{_SUPABASE_URL}/rest/v1/analysis_documents",
            headers=_headers(),
            params={"id": f"eq.{doc_id}"},
            json=fields,
            timeout=8.0,
        )
        return r.status_code < 300
    except Exception as e:
        log.warning(f"[db] update_document_row exception : {e}")
        return False


def get_document_row(doc_id: str, user_id: str) -> Optional[dict]:
    if not _enabled():
        return None
    try:
        r = httpx.get(
            f"{_SUPABASE_URL}/rest/v1/analysis_documents",
            headers=_headers(),
            params={
                "id": f"eq.{doc_id}",
                "user_id": f"eq.{user_id}",
                "limit": "1",
            },
            timeout=6.0,
        )
        if r.status_code >= 300:
            return None
        rows = r.json() or []
        return rows[0] if rows else None
    except Exception as e:
        log.debug(f"[db] get_document_row exception : {e}")
        return None


def list_documents(user_id: str, analysis_id: Optional[str] = None) -> list[dict]:
    if not _enabled():
        return []
    params = {
        "user_id": f"eq.{user_id}",
        "select": "id,analysis_id,filename,mime_type,size_bytes,type_detected,status,validated,extracted_data,extraction_error,created_at",
        "order": "created_at.desc",
        "limit": "100",
    }
    if analysis_id:
        params["analysis_id"] = f"eq.{analysis_id}"
    try:
        r = httpx.get(
            f"{_SUPABASE_URL}/rest/v1/analysis_documents",
            headers=_headers(),
            params=params,
            timeout=8.0,
        )
        if r.status_code >= 300:
            log.warning(f"[db] list_documents HTTP {r.status_code} : {r.text[:200]}")
            return []
        return r.json() or []
    except Exception as e:
        log.warning(f"[db] list_documents exception : {e}")
        return []


def delete_document_row(doc_id: str) -> bool:
    if not _enabled():
        return False
    try:
        r = httpx.delete(
            f"{_SUPABASE_URL}/rest/v1/analysis_documents",
            headers=_headers(),
            params={"id": f"eq.{doc_id}"},
            timeout=8.0,
        )
        return r.status_code < 300
    except Exception as e:
        log.warning(f"[db] delete_document_row exception : {e}")
        return False


def find_document_by_hash(user_id: str, file_hash: str) -> Optional[dict]:
    """Cache : si user a déjà uploadé ce fichier (même hash), réutilise."""
    if not _enabled() or not file_hash:
        return None
    try:
        r = httpx.get(
            f"{_SUPABASE_URL}/rest/v1/analysis_documents",
            headers=_headers(),
            params={
                "user_id": f"eq.{user_id}",
                "file_hash": f"eq.{file_hash}",
                "limit": "1",
            },
            timeout=6.0,
        )
        if r.status_code >= 300:
            return None
        rows = r.json() or []
        return rows[0] if rows else None
    except Exception as e:
        log.debug(f"[db] find_document_by_hash exception : {e}")
        return None


def list_analyses(user_id: str, limit: int = 50) -> list[dict]:
    """Retourne les N dernières analyses du user (plus récentes d'abord).

    Retourne [] si Supabase non configuré ou si la table n'existe pas.
    """
    if not _enabled():
        return []

    try:
        r = httpx.get(
            f"{_SUPABASE_URL}/rest/v1/analyses_history",
            headers={**_headers(), "Prefer": "count=none"},
            params={
                "user_id": f"eq.{user_id}",
                "select": "id,kind,label,ticker,status,created_at,finished_at,files",
                "order": "created_at.desc",
                "limit": str(limit),
            },
            timeout=8.0,
        )
        if r.status_code >= 300:
            log.warning(f"[db] list_analyses HTTP {r.status_code} : {r.text[:200]}")
            return []
        return r.json() or []
    except Exception as e:
        log.warning(f"[db] list_analyses exception : {e}")
        return []
