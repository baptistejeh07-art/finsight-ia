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
from datetime import datetime
from typing import Callable, Optional, Any

log = logging.getLogger(__name__)

_LOCK = threading.Lock()
_JOBS: "OrderedDict[str, dict]" = OrderedDict()
MAX_JOBS = 100


def _purge():
    """Supprime les jobs les plus anciens si on dépasse MAX_JOBS."""
    while len(_JOBS) > MAX_JOBS:
        _JOBS.popitem(last=False)


def submit(kind: str, fn: Callable[..., Any], *args, **kwargs) -> str:
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
            "created_at": datetime.utcnow().isoformat(),
            "started_at": None,
            "finished_at": None,
        }
        _purge()

    def _wrapper():
        with _LOCK:
            _JOBS[job_id]["status"] = "running"
            _JOBS[job_id]["started_at"] = datetime.utcnow().isoformat()
        log.info(f"[jobs/{kind}] {job_id[:8]} started")
        try:
            result = fn(*args, **kwargs)
            with _LOCK:
                _JOBS[job_id]["status"] = "done"
                _JOBS[job_id]["result"] = result
                _JOBS[job_id]["progress"] = 100
                _JOBS[job_id]["finished_at"] = datetime.utcnow().isoformat()
            log.info(f"[jobs/{kind}] {job_id[:8]} done")
        except Exception as e:
            log.error(f"[jobs/{kind}] {job_id[:8]} FAIL: {e}", exc_info=True)
            with _LOCK:
                _JOBS[job_id]["status"] = "error"
                _JOBS[job_id]["error"] = str(e)
                _JOBS[job_id]["finished_at"] = datetime.utcnow().isoformat()

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


def list_jobs(limit: int = 50) -> list[dict]:
    """Liste les N derniers jobs (debug)."""
    with _LOCK:
        items = list(_JOBS.values())[-limit:]
    return [
        {k: v for k, v in j.items() if k != "result"}  # exclu result (lourd)
        for j in items
    ]
