# =============================================================================
# FinSight IA — Cache Redis
# cache/redis_cache.py
#
# Redis (localhost:6379 ou REDIS_URL) + fallback dict en mémoire.
# Impact mesuré brief §5 : 27s → 3s sur requêtes répétées.
# Clé : "finsight:{ticker}:{date}:{scope}"
# =============================================================================

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fallback en mémoire (si Redis indisponible)
# ---------------------------------------------------------------------------
_mem: dict[str, tuple[Any, float]] = {}  # {key: (value, expire_at)}


def _mem_get(key: str) -> Optional[Any]:
    entry = _mem.get(key)
    if entry is None:
        return None
    value, expire_at = entry
    if expire_at and time.time() > expire_at:
        del _mem[key]
        return None
    return value


def _mem_set(key: str, value: Any, ttl: int) -> None:
    _mem[key] = (value, time.time() + ttl if ttl > 0 else 0)


# ---------------------------------------------------------------------------
# Client Redis (lazy init)
# ---------------------------------------------------------------------------
_redis = None
_redis_ok = None   # None = not yet tried, True = OK, False = unavailable


def _get_redis():
    global _redis, _redis_ok
    if _redis_ok is not None:
        return _redis if _redis_ok else None
    try:
        import redis as redis_lib
        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        r = redis_lib.from_url(url, decode_responses=True, socket_connect_timeout=2)
        r.ping()
        _redis = r
        _redis_ok = True
        log.info(f"[Cache] Redis connecté : {url}")
    except Exception as e:
        _redis_ok = False
        log.info(f"[Cache] Redis indisponible ({e}) — fallback mémoire")
    return _redis if _redis_ok else None


# ---------------------------------------------------------------------------
# Interface publique
# ---------------------------------------------------------------------------

def get(key: str) -> Optional[dict]:
    """Récupère une valeur depuis le cache (Redis ou mémoire)."""
    r = _get_redis()
    if r:
        try:
            raw = r.get(key)
            if raw:
                log.debug(f"[Cache] HIT Redis : {key}")
                return json.loads(raw)
        except Exception as e:
            log.warning(f"[Cache] Erreur lecture Redis : {e}")

    val = _mem_get(key)
    if val is not None:
        log.debug(f"[Cache] HIT mem : {key}")
    return val


def set(key: str, value: dict, ttl: int = 3600) -> None:
    """Stocke une valeur dans le cache avec TTL en secondes."""
    r = _get_redis()
    if r:
        try:
            r.setex(key, ttl, json.dumps(value, ensure_ascii=False))
            log.debug(f"[Cache] SET Redis : {key} (TTL={ttl}s)")
            return
        except Exception as e:
            log.warning(f"[Cache] Erreur écriture Redis : {e}")

    _mem_set(key, value, ttl)
    log.debug(f"[Cache] SET mem : {key} (TTL={ttl}s)")


def make_key(ticker: str, scope: str, date: str = "") -> str:
    """Construit une clé de cache normalisée."""
    parts = ["finsight", ticker.upper().replace(".", "_"), scope]
    if date:
        parts.append(date)
    return ":".join(parts)
