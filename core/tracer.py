# -*- coding: utf-8 -*-
"""
core/tracer.py — Traçage fin des analyses (niveau 3).

API simple pour instrumenter chaque étape d'une analyse sans polluer le code :

    from core.tracer import trace, trace_llm

    # Contexte job (thread-local) — à set au démarrage du job
    trace.set_job(job_id="abc123", kind="societe", label="AAPL")

    # Step simple (avec auto-close)
    with trace.step("fetch_yfinance", level="fetch", provider="yfinance") as s:
        data = yf.Ticker("AAPL").info
        s.set_output_size(len(str(data)))

    # Step LLM avec comptage tokens + coût
    with trace_llm("groq", "llama-3.3-70b-versatile",
                    prompt=my_prompt, max_tokens=600) as s:
        resp = llm.generate(my_prompt)
        s.finish_llm(response=resp, tokens_in=prompt_tokens, tokens_out=resp_tokens)

    # Cache hit
    trace.cache_hit("piotroski.AAPL")

Chaque step fait un insert dans analysis_traces (Supabase). L'insert est
asynchrone (thread pool) pour ne pas ralentir le pipeline. Fallback silent
si Supabase down.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Optional

log = logging.getLogger(__name__)

# Thread-local context (job_id, kind, label, current_step_id)
_context = threading.local()

# Thread pool pour inserts async Supabase (non-bloquant)
_INSERT_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tracer")


# ═══ Pricing des providers LLM (USD par 1M tokens) ═══════════════════════
# Source : pricing officiel avril 2026. Mis à jour manuellement si change.
_LLM_PRICING: dict[str, dict[str, tuple[float, float]]] = {
    # provider → model → (input_per_M_usd, output_per_M_usd)
    "groq": {
        # Groq est gratuit dans la limite du quota (30 req/min free tier)
        "llama-3.3-70b-versatile":   (0.0, 0.0),
        "llama-3.1-8b-instant":      (0.0, 0.0),
        "mixtral-8x7b-32768":        (0.0, 0.0),
        "*":                         (0.0, 0.0),
    },
    "mistral": {
        "mistral-large-latest":      (2.0, 6.0),
        "mistral-small-latest":      (0.2, 0.6),
        "mistral-medium":            (0.4, 2.0),
        "codestral-latest":          (0.3, 0.9),
        "*":                         (0.4, 1.2),
    },
    "anthropic": {
        "claude-opus-4-7":           (15.0, 75.0),
        "claude-sonnet-4-6":         (3.0, 15.0),
        "claude-haiku-4-5":          (0.8, 4.0),
        "claude-haiku-4-5-20251001": (0.8, 4.0),
        "*":                         (3.0, 15.0),
    },
    "gemini": {
        "gemini-2.0-flash":          (0.075, 0.30),
        "gemini-2.5-pro":            (1.25, 10.0),
        "*":                         (0.30, 1.0),
    },
    "cerebras": {
        "llama-3.3-70b":             (0.85, 1.20),
        "qwen-3-32b":                (0.4, 0.8),
        "*":                         (0.5, 1.0),
    },
    "openai": {
        "gpt-4o":                    (2.5, 10.0),
        "gpt-4o-mini":               (0.15, 0.60),
        "*":                         (0.5, 1.5),
    },
}


def _price_for(provider: str, model: str, tokens_in: int, tokens_out: int) -> float:
    """Retourne le coût USD estimé d'un appel LLM donné (tokens)."""
    try:
        p = _LLM_PRICING.get((provider or "").lower())
        if not p:
            return 0.0
        pricing = p.get(model) or p.get("*") or (0.0, 0.0)
        return round(
            (tokens_in / 1_000_000) * pricing[0]
            + (tokens_out / 1_000_000) * pricing[1],
            6,
        )
    except Exception:
        return 0.0


# ═══ Context manager principal ═══════════════════════════════════════════
@dataclass
class _Step:
    """Représente une étape en cours — retournée par `with trace.step(...)`."""
    row_id: Optional[int] = None
    started_at: float = field(default_factory=time.time)
    level: str = "other"
    step_name: str = ""
    provider: Optional[str] = None
    model: Optional[str] = None
    parent_id: Optional[int] = None
    input_preview: Optional[str] = None
    output_preview: Optional[str] = None
    input_size: int = 0
    output_size: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    cache_hit: bool = False
    fallback_level: int = 0
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_stack: Optional[str] = None
    status: str = "ok"
    metadata: dict = field(default_factory=dict)

    def set_input(self, s: str, max_preview: int = 500) -> None:
        self.input_size = len(s or "")
        self.input_preview = (s or "")[:max_preview]

    def set_output(self, s: str, max_preview: int = 500) -> None:
        self.output_size = len(s or "")
        self.output_preview = (s or "")[:max_preview]

    def set_output_size(self, n: int) -> None:
        self.output_size = n

    def finish_llm(self, response: str | None = None,
                    tokens_in: int = 0, tokens_out: int = 0) -> None:
        """Ferme une étape LLM avec tokens + calcul de coût."""
        if response is not None:
            self.set_output(response)
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.cost_usd = _price_for(self.provider or "", self.model or "",
                                    tokens_in, tokens_out)

    def set_error(self, exc: BaseException) -> None:
        self.status = "error"
        self.error_type = type(exc).__name__
        self.error_message = (str(exc) or "")[:1000]
        try:
            self.error_stack = traceback.format_exc()[:4000]
        except Exception:
            self.error_stack = None


class _StepCtx:
    """Context manager retourné par trace.step()."""

    def __init__(self, tracer: "_Tracer", step: _Step):
        self._t = tracer
        self._s = step

    def __enter__(self) -> _Step:
        # Insert row "ouverte" (finished_at null) pour que SSE puisse voir
        self._s.row_id = self._t._insert_open(self._s)
        # Push dans la pile pour parent_id des steps imbriqués
        _get_stack().append(self._s.row_id)
        return self._s

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        # Pop la pile
        stk = _get_stack()
        if stk and stk[-1] == self._s.row_id:
            stk.pop()
        # Erreur → capture
        if exc_type is not None and exc_val is not None:
            self._s.set_error(exc_val)
        # Close row
        self._t._close_step(self._s)
        return False  # ne pas swallow l'exception


def _get_stack() -> list:
    if not hasattr(_context, "stack"):
        _context.stack = []
    return _context.stack


# ═══ Tracer singleton ════════════════════════════════════════════════════
class _Tracer:
    def set_job(self, job_id: str, kind: str = "", label: str = "") -> None:
        _context.job_id = job_id
        _context.kind = kind
        _context.label = label
        _context.stack = []

    def get_job_id(self) -> Optional[str]:
        return getattr(_context, "job_id", None)

    def step(self, step_name: str, level: str = "other",
             provider: Optional[str] = None, model: Optional[str] = None,
             metadata: Optional[dict] = None) -> _StepCtx:
        """Context manager. Usage :
            with trace.step("fetch_yfinance", level="fetch") as s:
                ...
        """
        s = _Step(
            level=level,
            step_name=step_name,
            provider=provider,
            model=model,
            metadata=metadata or {},
            parent_id=_get_stack()[-1] if _get_stack() else None,
        )
        return _StepCtx(self, s)

    def cache_hit(self, key: str, level: str = "cache") -> None:
        """Note un cache hit (step instantané)."""
        s = _Step(
            level=level,
            step_name=f"cache_hit:{key}",
            status="cache_hit",
            cache_hit=True,
        )
        s.row_id = self._insert_open(s)
        self._close_step(s)

    def event(self, step_name: str, level: str = "other",
              metadata: Optional[dict] = None) -> None:
        """Log un événement ponctuel (durée 0)."""
        s = _Step(
            level=level,
            step_name=step_name,
            metadata=metadata or {},
        )
        s.row_id = self._insert_open(s)
        self._close_step(s)

    # ── internals ───────────────────────────────────────────────────────
    def _insert_open(self, s: _Step) -> Optional[int]:
        """Insert le row "ouvert" (pas encore fini). Retourne l'id."""
        if not self.get_job_id():
            return None
        # Insert ASYNC pour ne pas ralentir le pipeline
        fut = _INSERT_POOL.submit(self._insert_row_sync, s, is_open=True)
        try:
            return fut.result(timeout=0.5)  # attend max 500ms pour l'id
        except Exception:
            return None

    def _close_step(self, s: _Step) -> None:
        """Met à jour finished_at + duration + éventuelles erreurs."""
        if not s.row_id or not self.get_job_id():
            return
        _INSERT_POOL.submit(self._update_row_sync, s)

    def _insert_row_sync(self, s: _Step, is_open: bool = False) -> Optional[int]:
        url, key = _supabase_creds()
        if not url or not key:
            return None
        import httpx
        try:
            payload = {
                "job_id": self.get_job_id(),
                "kind": getattr(_context, "kind", ""),
                "label": getattr(_context, "label", ""),
                "level": s.level,
                "step_name": s.step_name,
                "parent_id": s.parent_id,
                "provider": s.provider,
                "model": s.model,
                "input_preview": s.input_preview,
                "output_preview": s.output_preview,
                "input_size": s.input_size,
                "output_size": s.output_size,
                "tokens_in": s.tokens_in or 0,
                "tokens_out": s.tokens_out or 0,
                "cost_usd": s.cost_usd or 0,
                "cache_hit": s.cache_hit,
                "fallback_level": s.fallback_level,
                "status": s.status,
                "metadata": s.metadata,
            }
            r = httpx.post(
                f"{url}/rest/v1/analysis_traces",
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation",
                },
                json=payload,
                timeout=3.0,
            )
            if r.status_code < 300:
                rows = r.json() or []
                if rows:
                    return int(rows[0].get("id"))
        except Exception as e:
            log.debug(f"[tracer] insert fail silent: {e}")
        return None

    def _update_row_sync(self, s: _Step) -> None:
        url, key = _supabase_creds()
        if not url or not key:
            return
        import httpx
        try:
            duration_ms = int((time.time() - s.started_at) * 1000)
            payload = {
                "finished_at": "now()",
                "duration_ms": duration_ms,
                "output_preview": s.output_preview,
                "output_size": s.output_size,
                "tokens_in": s.tokens_in or 0,
                "tokens_out": s.tokens_out or 0,
                "cost_usd": s.cost_usd or 0,
                "status": s.status,
                "error_type": s.error_type,
                "error_message": s.error_message,
                "error_stack": s.error_stack,
                "metadata": s.metadata,
            }
            httpx.patch(
                f"{url}/rest/v1/analysis_traces?id=eq.{s.row_id}",
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=3.0,
            )
        except Exception as e:
            log.debug(f"[tracer] update fail silent: {e}")


def _supabase_creds() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_KEY")
           or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
           or os.getenv("SUPABASE_SECRET_KEY") or "")
    return url, key


# Export singleton
trace = _Tracer()


def trace_llm(provider: str, model: str, prompt: str = "", **kwargs) -> _StepCtx:
    """Raccourci pour trace.step() + set_input(prompt) automatiquement.

    Usage :
        with trace_llm("groq", "llama-3.3", prompt=p) as s:
            resp = llm.generate(p)
            s.finish_llm(resp, tokens_in=..., tokens_out=...)
    """
    metadata = kwargs.pop("metadata", {})
    ctx = trace.step(
        step_name=f"{provider}:{model}",
        level="llm",
        provider=provider,
        model=model,
        metadata=metadata,
    )
    # Hack : set input après entry — on wrap le __enter__
    original_enter = ctx.__enter__

    def _wrap() -> _Step:
        s = original_enter()
        if prompt:
            s.set_input(prompt)
        return s

    ctx.__enter__ = _wrap  # type: ignore[assignment]
    return ctx
