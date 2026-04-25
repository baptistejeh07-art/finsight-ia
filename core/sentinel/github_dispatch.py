"""core/sentinel/github_dispatch.py — Déclenche un workflow GitHub Actions
à chaque erreur sentinel détectée en prod, qui spawne un Claude Code
agent en mode headless pour fixer automatiquement.

Architecture (Option C — choix Baptiste 2026-04-25) :
    pipeline_errors (Supabase)
       └── trigger_wakeup_if_new()
              └── github_dispatch.send_event()  ← ce module
                     └── POST /repos/{owner}/{repo}/dispatches
                            └── workflow .github/workflows/sentinel-fix.yml
                                   └── claude code --print prompt
                                          └── git commit + push fix

Avantages vs Claude Code routine claude.ai/code :
- Clé Anthropic standard (sk-ant-api03-...) qui n'expire pas
- Audit trail complet (chaque session = un run GitHub Actions identifiable)
- Possibilité de rejouer un fix manuellement depuis l'UI GitHub
- Concurrent-safe via concurrency.group dans le workflow YAML
- Pas de dépendance au plan Max Baptiste (utilise les minutes Actions du repo)

ENV VARS REQUISES (Railway) :
- GITHUB_DISPATCH_TOKEN : PAT classique avec scope `repo` ou fine-grained
  avec `Actions: write` + `Contents: read` sur le repo finsight-ia.
- GITHUB_REPO : "baptistejeh07-art/finsight-ia" (default codé en dur ici)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

log = logging.getLogger(__name__)


_DEFAULT_REPO = "baptistejeh07-art/finsight-ia"
_API_URL = "https://api.github.com"

# Cache in-process pour dédupliquer les dispatches : même fingerprint
# (error_type + ticker) ne déclenche pas 50 workflows en parallèle si
# le bug se répète vite. 30 minutes par défaut.
_DISPATCH_CACHE: dict[str, datetime] = {}
_DISPATCH_DEDUP_WINDOW = timedelta(minutes=30)


def _fingerprint(error_type: str, ticker: Optional[str]) -> str:
    """Clé stable pour dédup."""
    return f"{error_type}::{ticker or '_'}"


def send_event(*, error_type: str, severity: str, ticker: Optional[str],
                kind: Optional[str], message: str, row_id: Optional[str],
                context: Optional[dict] = None) -> bool:
    """POST repository_dispatch à GitHub avec event_type=sentinel-error.

    Retourne True si le dispatch a été envoyé avec succès (HTTP 204).
    Silencieux et best-effort : aucune exception remontée pour ne pas
    casser le pipeline principal sur une erreur sentinel.
    """
    token = os.getenv("GITHUB_DISPATCH_TOKEN", "").strip()
    repo = os.getenv("GITHUB_REPO", _DEFAULT_REPO).strip() or _DEFAULT_REPO

    if not token:
        log.info("[sentinel/dispatch] GITHUB_DISPATCH_TOKEN absent — skip")
        return False

    fp = _fingerprint(error_type, ticker)
    now = datetime.now(timezone.utc)
    last = _DISPATCH_CACHE.get(fp)
    if last and (now - last) < _DISPATCH_DEDUP_WINDOW:
        elapsed = (now - last).total_seconds()
        log.info(f"[sentinel/dispatch] dédup {fp} (last fired {elapsed:.0f}s ago)")
        return False

    payload = {
        "event_type": "sentinel-error",
        # client_payload est limité à 10 propriétés top-level par GitHub.
        # On structure compact + on tronque les chaînes longues.
        "client_payload": {
            "error_type": error_type,
            "severity": severity,
            "ticker": ticker or "",
            "kind": kind or "",
            "message": (message or "")[:1500],
            "row_id": row_id or "",
            "fired_at": now.isoformat(),
            "context": _trim_context(context or {}),
        },
    }

    try:
        r = httpx.post(
            f"{_API_URL}/repos/{repo}/dispatches",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "FinSight-Sentinel/1.0",
            },
            json=payload,
            timeout=10.0,
        )
        if r.status_code == 204:
            _DISPATCH_CACHE[fp] = now
            log.info(f"[sentinel/dispatch] ✅ workflow déclenché pour {error_type}/{ticker}")
            return True
        log.warning(
            f"[sentinel/dispatch] HTTP {r.status_code} : {r.text[:300]}")
        return False
    except Exception as e:
        log.warning(f"[sentinel/dispatch] exception: {e}")
        return False


def _trim_context(ctx: dict, max_chars: int = 800) -> dict:
    """Tronque récursivement le contexte pour éviter de dépasser la
    limite de 64 Ko du payload repository_dispatch GitHub.

    Garde les clés les plus utiles (`rule`, `data_quality_score`, `n_tickers`,
    `penalty`, `sector`, `universe`) et tronque le reste.
    """
    if not ctx:
        return {}
    priority = ("rule", "data_quality_score", "n_tickers", "penalty",
                "sector", "universe", "triggered_by")
    out: dict = {}
    for k in priority:
        if k in ctx:
            v = ctx[k]
            if isinstance(v, str) and len(v) > max_chars:
                v = v[:max_chars] + "…"
            out[k] = v
    # Inclut les autres clés simples
    remaining_budget = max_chars
    for k, v in ctx.items():
        if k in out:
            continue
        if remaining_budget <= 0:
            break
        if isinstance(v, (str, int, float, bool)) or v is None:
            sv = str(v)
            if len(sv) > 200:
                sv = sv[:200] + "…"
            out[k] = sv
            remaining_budget -= len(sv)
    return out
