"""Cache distribué Redis avec fallback in-memory.

API simple :
  get(key) -> str | None
  set(key, value, ttl_seconds)
  delete(key)
  incr(key, ttl_seconds) -> int

Usage :
  from core.cache import cache
  val = cache.get("yf:AAPL:info")
  if val is None:
      val = expensive_call()
      cache.set("yf:AAPL:info", json.dumps(val), ttl_seconds=300)

Rate limiter sliding window :
  from core.cache import rate_limit
  ok, retry_after = rate_limit("api:key_id:abc", max_requests=30, window_sec=60)
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import deque
from typing import Optional

log = logging.getLogger(__name__)

_REDIS_URL = os.getenv("REDIS_URL", "").strip()
_redis_client = None

# Lock fallback in-process (quand Redis indispo) — protégé par threading.Lock
import threading as _threading
_MEM_LOCK_GUARD = _threading.Lock()
_MEM_LOCKS: dict[str, float] = {}  # key -> expires_at


def _get_client():
    """Lazy init du client Redis. Retourne None si Redis indisponible."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client if _redis_client is not False else None
    if not _REDIS_URL:
        _redis_client = False
        return None
    try:
        import redis
        _redis_client = redis.from_url(_REDIS_URL, decode_responses=True, socket_timeout=2.0)
        # Test la connexion
        _redis_client.ping()
        log.info(f"[cache] Redis OK — {_REDIS_URL[:30]}...")
        return _redis_client
    except Exception as e:
        log.warning(f"[cache] Redis indispo, fallback in-memory: {e}")
        _redis_client = False
        return None


# --- Fallback in-memory (quand Redis indispo) ---
_MEM: dict[str, tuple[float, str]] = {}   # key -> (expires_at, value)
_MEM_COUNTERS: dict[str, deque] = {}      # key -> deque de timestamps


def get(key: str) -> Optional[str]:
    cli = _get_client()
    if cli is not None:
        try:
            return cli.get(key)
        except Exception as e:
            log.debug(f"[cache] get({key}) redis fail: {e}")
            return None
    # in-memory
    entry = _MEM.get(key)
    if entry is None:
        return None
    exp, val = entry
    if exp < time.time():
        _MEM.pop(key, None)
        return None
    return val


def set(key: str, value: str, ttl_seconds: int = 300) -> bool:
    cli = _get_client()
    if cli is not None:
        try:
            cli.set(key, value, ex=ttl_seconds)
            return True
        except Exception as e:
            log.debug(f"[cache] set({key}) redis fail: {e}")
    _MEM[key] = (time.time() + ttl_seconds, value)
    # Garde-fou : nettoyage LRU simple au-delà de 1000 entrées
    if len(_MEM) > 1000:
        # Supprime les 200 plus anciennes
        sorted_items = sorted(_MEM.items(), key=lambda kv: kv[1][0])
        for k, _ in sorted_items[:200]:
            _MEM.pop(k, None)
    return False


def delete(key: str) -> bool:
    cli = _get_client()
    if cli is not None:
        try:
            cli.delete(key)
            return True
        except Exception:
            pass
    _MEM.pop(key, None)
    return False


def get_json(key: str):
    raw = get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def set_json(key: str, value, ttl_seconds: int = 300) -> bool:
    try:
        return set(key, json.dumps(value, default=str), ttl_seconds=ttl_seconds)
    except Exception:
        return False


# --- Rate limiter sliding window ---
def rate_limit(key: str, max_requests: int, window_sec: int) -> tuple[bool, int]:
    """Sliding window counter. Retourne (allowed, retry_after_sec).

    Utilise Redis INCR + EXPIRE en prod (multi-worker safe).
    Fallback deque in-memory par process.
    """
    cli = _get_client()
    if cli is not None:
        try:
            # Sliding window via ZADD / ZREMRANGEBYSCORE
            now = time.time()
            cutoff = now - window_sec
            pipe = cli.pipeline()
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, window_sec + 10)
            _, count_before, _, _ = pipe.execute()
            # count_before = nb avant add. Si count_before >= max : over limit
            if count_before >= max_requests:
                # Calcule retry_after : jusqu'à ce que la plus ancienne expire
                oldest = cli.zrange(key, 0, 0, withscores=True)
                if oldest:
                    retry = max(1, int(oldest[0][1] + window_sec - now))
                else:
                    retry = window_sec
                return False, retry
            return True, 0
        except Exception as e:
            log.debug(f"[cache] rate_limit redis fail: {e}")

    # Fallback in-memory
    now = time.time()
    cutoff = now - window_sec
    dq = _MEM_COUNTERS.setdefault(key, deque(maxlen=max_requests * 2))
    while dq and dq[0] < cutoff:
        dq.popleft()
    if len(dq) >= max_requests:
        retry = max(1, int(dq[0] + window_sec - now))
        return False, retry
    dq.append(now)
    return True, 0


# --- Distributed lock (atomic check-and-set) ---
def acquire_lock(key: str, ttl_seconds: int = 30) -> bool:
    """Tente d'acquérir un lock distribué via Redis SET NX EX.

    Audit code 29/04/2026 P0 (B6 Early Backer race) : utilisé pour
    serialiser les opérations critiques (count + create) qui sinon
    feraient une race condition entre 2 workers FastAPI parallèles.

    Returns:
        True si le lock est acquis (caller doit appeler release_lock).
        False si déjà tenu par un autre process (caller doit retry/abandon).

    Fallback in-memory : utilise un dict + threading.Lock (mono-process safe).
    En prod multi-worker (uvicorn --workers > 1) sans Redis, le fallback
    n'est PAS distribué — c'est mieux que rien mais Redis recommandé.
    """
    cli = _get_client()
    if cli is not None:
        try:
            return bool(cli.set(key, "1", nx=True, ex=ttl_seconds))
        except Exception as e:
            log.warning(f"[cache] acquire_lock({key}) redis fail: {e}")
    # Fallback in-memory
    with _MEM_LOCK_GUARD:
        now = time.time()
        exp = _MEM_LOCKS.get(key)
        if exp is not None and exp > now:
            return False
        _MEM_LOCKS[key] = now + ttl_seconds
        return True


def release_lock(key: str) -> bool:
    """Libère un lock acquis via acquire_lock."""
    cli = _get_client()
    if cli is not None:
        try:
            cli.delete(key)
            return True
        except Exception as e:
            log.debug(f"[cache] release_lock({key}) redis fail: {e}")
    with _MEM_LOCK_GUARD:
        _MEM_LOCKS.pop(key, None)
    return True


# Export "cache" en attribut accessible par cache.get/set
class _CacheNamespace:
    get = staticmethod(get)
    set = staticmethod(set)
    delete = staticmethod(delete)
    get_json = staticmethod(get_json)
    set_json = staticmethod(set_json)
    acquire_lock = staticmethod(acquire_lock)
    release_lock = staticmethod(release_lock)


cache = _CacheNamespace()
