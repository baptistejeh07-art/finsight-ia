# =============================================================================
# FinSight IA — Secrets Injector
# core/secrets.py
# =============================================================================

from __future__ import annotations

import logging
import os
from typing import Optional

log = logging.getLogger(__name__)


def get_secret(key: str) -> Optional[str]:
    """
    Lit une clé API depuis os.environ, puis st.secrets en fallback direct.
    Fonctionne en local (via .env / os.environ) et sur SCC (st.secrets).
    C'est la fonction à utiliser partout à la place de os.getenv() pour les clés API.
    """
    val = os.getenv(key)
    if val:
        return val
    try:
        import streamlit as st
        v = st.secrets.get(key)
        if v:
            return str(v)
    except Exception:
        pass
    return None


def inject_secrets() -> None:
    """
    Injecte st.secrets dans os.environ pour Streamlit Community Cloud.
    Appelé une fois au démarrage dans app.py — accélère les appels suivants.
    """
    try:
        import streamlit as st

        # Itérer directement sur st.secrets (compatible toutes versions Streamlit)
        injected = 0
        for key in st.secrets:
            val = st.secrets[key]
            if isinstance(val, str) and val:
                os.environ.setdefault(key, val)
                injected += 1
            elif hasattr(val, "items"):
                # Section TOML [section] — injecter chaque sous-clé directement
                for sub_key, sub_val in val.items():
                    if isinstance(sub_val, str) and sub_val:
                        os.environ.setdefault(sub_key, sub_val)
                        injected += 1

        if injected:
            log.info(f"[Secrets] {injected} cle(s) injectee(s) depuis st.secrets")

    except Exception:
        # Local dev : secrets.toml absent — normal
        pass


def is_cloud() -> bool:
    return bool(os.getenv("STREAMLIT_SHARING_MODE") or os.getenv("IS_CLOUD"))
