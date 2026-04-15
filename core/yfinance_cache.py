# -*- coding: utf-8 -*-
"""
core/yfinance_cache.py — Singleton cache pour les appels yfinance.

Centralise les appels `yf.Ticker()` qui étaient éparpillés dans 26 fichiers
du projet. Avant ce refactor :
- Chaque fichier instanciait son propre yf.Ticker() pour le même symbol
- Aucun cache mutualisé → potentiellement 10 appels yfinance pour un seul
  ticker lors d'une analyse complète (fetch_node, agent_entry_zone,
  comparables, currency, pdf_writer, pptx_writer...)
- Rate limit yfinance fréquent sur Streamlit Cloud
- Tests unitaires impossibles à mocker proprement

APRÈS :
- `get_ticker(symbol)` retourne un objet `yf.Ticker` caché (TTL 15 min)
- Appels successifs à `.info`, `.fast_info`, `.history()`, `.balance_sheet`,
  etc. sur le même objet → bénéficient du cache HTTP interne yfinance
- Migration des 26 fichiers : remplacer `yf.Ticker(x)` par `get_ticker(x)`
- Zéro impact fonctionnel — même API, juste cached

## Thread safety

Le cache est protégé par un `threading.Lock` pour supporter les fetch
parallèles (ThreadPoolExecutor dans agent_data, comparables, etc.).

## TTL Philosophy

- **15 min** pour Ticker objects : assez long pour mutualiser une session
  d'analyse Streamlit complète, assez court pour rafraîchir les prix
  intraday si l'utilisateur relance 20 min plus tard.
- Les sous-attributs (info, fast_info, balance_sheet, etc.) ont leur
  propre cache HTTP interne yfinance (yfinance lru_cache sur requests),
  donc on bénéficie du cache à 2 niveaux.

## Invalidation

- `clear_ticker_cache()` : clear tout (tests unitaires)
- `clear_ticker(symbol)` : clear un ticker spécifique
- Expiration automatique au bout du TTL

## Usage

    from core.yfinance_cache import get_ticker

    tk = get_ticker("AAPL")
    info = tk.info  # cached par yfinance en interne
    hist = tk.history(period="1y")  # cached aussi

Au lieu de :

    import yfinance as yf
    tk = yf.Ticker("AAPL")
    info = tk.info
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

log = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════

_TTL_SEC = 15 * 60  # 15 minutes
_CACHE: dict[str, tuple[Any, float]] = {}  # {symbol: (Ticker, timestamp)}
_LOCK = threading.Lock()
_CACHE_HITS = 0
_CACHE_MISSES = 0


# ═════════════════════════════════════════════════════════════════════════════
# API
# ═════════════════════════════════════════════════════════════════════════════

def get_ticker(symbol: str):
    """Retourne un objet yf.Ticker pour {symbol}, caché 15 min.

    Args:
        symbol : ticker yfinance (ex: "AAPL", "MC.PA", "NESN.SW")

    Returns:
        yf.Ticker object (peut être appelé normalement : .info, .history(),
        .balance_sheet, .income_stmt, .cash_flow, .fast_info, etc.)

    Thread-safe via _LOCK.
    """
    global _CACHE_HITS, _CACHE_MISSES

    if not symbol:
        raise ValueError("get_ticker: symbol is empty")

    _key = str(symbol).strip().upper()
    now = time.time()

    with _LOCK:
        if _key in _CACHE:
            tk, ts = _CACHE[_key]
            if (now - ts) < _TTL_SEC:
                _CACHE_HITS += 1
                return tk
            # Expired
            del _CACHE[_key]

        # Miss : create fresh Ticker
        _CACHE_MISSES += 1
        try:
            import yfinance as yf
        except ImportError as e:
            raise RuntimeError(f"yfinance non installé : {e}")

        tk = yf.Ticker(symbol)
        _CACHE[_key] = (tk, now)
        return tk


def clear_ticker_cache() -> None:
    """Clear tout le cache. Utile pour les tests unitaires ou un re-fetch forcé."""
    global _CACHE_HITS, _CACHE_MISSES
    with _LOCK:
        _CACHE.clear()
        _CACHE_HITS = 0
        _CACHE_MISSES = 0
    log.info("[yfinance_cache] cleared")


def clear_ticker(symbol: str) -> bool:
    """Clear un ticker spécifique du cache. Retourne True si trouvé et supprimé."""
    _key = str(symbol).strip().upper()
    with _LOCK:
        if _key in _CACHE:
            del _CACHE[_key]
            return True
    return False


def cache_stats() -> dict:
    """Retourne les statistiques du cache (pour debug/monitoring).

    Returns:
        {
            "size": int,       # nb de tickers cachés
            "hits": int,
            "misses": int,
            "hit_ratio": float,  # 0.0 - 1.0
            "symbols": list[str],
        }
    """
    with _LOCK:
        total = _CACHE_HITS + _CACHE_MISSES
        ratio = (_CACHE_HITS / total) if total > 0 else 0.0
        return {
            "size":     len(_CACHE),
            "hits":     _CACHE_HITS,
            "misses":   _CACHE_MISSES,
            "hit_ratio": round(ratio, 3),
            "symbols":  list(_CACHE.keys()),
        }


def set_ttl(seconds: int) -> None:
    """Override le TTL (pour tests ou tuning). Valeur par défaut : 900s (15 min)."""
    global _TTL_SEC
    if seconds > 0:
        _TTL_SEC = int(seconds)
        log.info(f"[yfinance_cache] TTL set to {seconds}s")
