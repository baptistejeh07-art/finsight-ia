# =============================================================================
# FinSight IA — Log structuré universel
# logs/db_logger.py
#
# Chaque requête → Supabase (PostgreSQL) + fallback JSON local.
# Structure de log : brief §4 "Structure du log universel"
# =============================================================================

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

_LOCAL_DIR = Path(__file__).parent / "local"
_LOCAL_DIR.mkdir(parents=True, exist_ok=True)


def log_request(meta: dict, output: dict) -> None:
    """
    Enregistre un log structuré (brief §4).
    Tente Supabase d'abord, fallback JSON local si indisponible.
    """
    record = {
        "request_id":              meta.get("request_id"),
        "timestamp":               meta.get("timestamp", datetime.utcnow().isoformat()),
        "ticker":                  meta.get("ticker"),
        "agents_called":           meta.get("sources_tried", []),
        "source":                  meta.get("source"),
        "confidence_score":        meta.get("confidence_score"),
        "invalidation_conditions": meta.get("invalidation_conditions"),
        "latency_ms":              meta.get("latency_ms"),
        "tokens_used":             meta.get("tokens_used", 0),
        "output":                  output,
        "logged_at":               datetime.utcnow().isoformat(),
    }

    if _try_supabase(record):
        return
    _write_local(record)


def _try_supabase(record: dict) -> bool:
    """Insère dans la table finsight_logs. Retourne True si succès."""
    url    = os.getenv("SUPABASE_URL", "").strip()
    secret = os.getenv("SUPABASE_SECRET_KEY", "").strip()

    if not url or not secret:
        return False

    try:
        from supabase import create_client
        client = create_client(url, secret)

        row = {
            "request_id":              record["request_id"],
            "timestamp":               record["timestamp"],
            "ticker":                  record["ticker"],
            "source":                  record["source"],
            "confidence_score":        record["confidence_score"],
            "latency_ms":              record["latency_ms"],
            "tokens_used":             record["tokens_used"],
            "invalidation_conditions": record["invalidation_conditions"],
            "output":                  json.dumps(record["output"], ensure_ascii=False),
        }

        client.table("finsight_logs").insert(row).execute()
        log.info(f"[DBLogger] Supabase OK — {record['request_id'][:8]}")
        return True

    except Exception as e:
        log.warning(f"[DBLogger] Supabase indisponible : {e}")
        return False


def log_pipeline_v2(request_log) -> None:
    """
    Enregistre un RequestLog v2 complet (fin de pipeline).
    Fichier : logs/local/v2_{request_id[:8]}_{ticker}.json
    """
    record = request_log.to_dict()
    _write_local_v2(record)


def _write_local_v2(record: dict) -> None:
    """JSON local pour les logs v2 pipeline."""
    rid    = record.get("request_id", "unknown")
    ticker = record.get("ticker", "unk")

    def _safe(obj):
        if isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        if isinstance(obj, dict):
            return {k: _safe(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_safe(v) for v in obj]
        return str(obj)

    fname = _LOCAL_DIR / f"v2_{rid[:8]}_{ticker}.json"
    try:
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(_safe(record), f, indent=2, ensure_ascii=False)
        log.info(f"[DBLogger] Log v2 : {fname.name}")
    except Exception as e:
        log.error(f"[DBLogger] Erreur ecriture v2 : {e}")


def _write_local(record: dict) -> None:
    """Fallback : JSON local dans logs/local/."""
    rid   = record.get("request_id", "unknown")
        # Rendre le contenu sérialisable (évite les objets non-JSON)
    def _safe(obj):
        if isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        if isinstance(obj, dict):
            return {k: _safe(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_safe(v) for v in obj]
        return str(obj)

    fname = _LOCAL_DIR / f"{rid[:8]}_{record.get('ticker', 'unk')}.json"
    try:
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(_safe(record), f, indent=2, ensure_ascii=False)
        log.info(f"[DBLogger] Log local : {fname.name}")
    except Exception as e:
        log.error(f"[DBLogger] Erreur ecriture locale : {e}")
