"""Système de jobs en mémoire pour analyses longues.

Les analyses /analyze/indice peuvent prendre 5-8 minutes. Railway peut
couper la requête HTTP avant la fin. On expose donc des endpoints
asynchrones :

    POST /jobs/analyze/societe   → 202 + {job_id}
    GET  /jobs/{job_id}          → {status, progress, result?, error?}

Le frontend poll toutes les 5s jusqu'à status=done|error.

Limites V1 :
- En mémoire (perdu au redémarrage du worker)
- Single-process : si plusieurs workers Railway, sticky session requise.
  Pour V1 on tourne en `--workers 1` côté Railway, c'est OK.
- 100 jobs max conservés (FIFO eviction).
"""

from __future__ import annotations
import threading
import uuid
import logging
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Callable, Optional, Any

import db


def _now_iso() -> str:
    """ISO timestamp UTC naïf (sans suffixe +00:00) pour compat frontend."""
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

log = logging.getLogger(__name__)

_LOCK = threading.Lock()
_JOBS: "OrderedDict[str, dict]" = OrderedDict()
MAX_JOBS = 100


def _purge():
    """Supprime les jobs les plus anciens si on dépasse MAX_JOBS."""
    while len(_JOBS) > MAX_JOBS:
        _JOBS.popitem(last=False)


def submit(kind: str, fn: Callable[..., Any], *args, user_id: Optional[str] = None, label: Optional[str] = None, **kwargs) -> str:
    """Démarre un job dans un thread daemon. Retourne le job_id."""
    job_id = str(uuid.uuid4())
    with _LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "kind": kind,
            "status": "queued",
            "progress": 0,
            "result": None,
            "error": None,
            "created_at": _now_iso(),
            "started_at": None,
            "finished_at": None,
            "user_id": user_id,
            "label": label,
        }
        _purge()

    def _wrapper():
        with _LOCK:
            _JOBS[job_id]["status"] = "running"
            _JOBS[job_id]["started_at"] = _now_iso()
        log.info(f"[jobs/{kind}] {job_id[:8]} started")
        try:
            result = fn(*args, **kwargs)
            with _LOCK:
                _JOBS[job_id]["status"] = "done"
                _JOBS[job_id]["result"] = result
                _JOBS[job_id]["progress"] = 100
                _JOBS[job_id]["finished_at"] = _now_iso()
            log.info(f"[jobs/{kind}] {job_id[:8]} done")
            # Persistance Postgres (best-effort, ne fail pas le job)
            if user_id:
                try:
                    files = result.get("files") if isinstance(result, dict) else None
                    ticker = (
                        result.get("ticker") if isinstance(result, dict) else None
                    ) or label
                    db.insert_analysis(
                        user_id=user_id,
                        kind=kind,
                        label=label,
                        ticker=ticker,
                        status="done",
                        files=files,
                        finished_at=datetime.now(timezone.utc),
                    )
                except Exception as e:
                    log.warning(f"[jobs/{kind}] {job_id[:8]} db persist failed: {e}")
        except Exception as e:
            log.error(f"[jobs/{kind}] {job_id[:8]} FAIL: {e}", exc_info=True)
            with _LOCK:
                _JOBS[job_id]["status"] = "error"
                _JOBS[job_id]["error"] = str(e)
                _JOBS[job_id]["finished_at"] = _now_iso()

    t = threading.Thread(target=_wrapper, daemon=True, name=f"job-{kind}-{job_id[:8]}")
    t.start()
    return job_id


def get(job_id: str) -> Optional[dict]:
    """Retourne le state du job (snapshot)."""
    with _LOCK:
        j = _JOBS.get(job_id)
        return dict(j) if j else None


def update_progress(job_id: str, progress: int, message: Optional[str] = None):
    """Mise à jour incrémentale du progress (appelé depuis le worker si possible)."""
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id]["progress"] = progress
            if message:
                _JOBS[job_id]["progress_message"] = message


def list_jobs(limit: int = 50, user_id: Optional[str] = None) -> list[dict]:
    """Liste les N derniers jobs (debug). Filtre par user_id si fourni."""
    with _LOCK:
        items = list(_JOBS.values())
    if user_id is not None:
        items = [j for j in items if j.get("user_id") == user_id]
    items = items[-limit:]
    return [
        {k: v for k, v in j.items() if k != "result"}  # exclu result (lourd)
        for j in items
    ]
