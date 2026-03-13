# =============================================================================
# FinSight IA — Secrets Injector
# core/secrets.py
#
# Pont entre st.secrets (Streamlit Cloud) et os.environ (code existant).
#
# En production (Streamlit Community Cloud) :
#   - st.secrets lit .streamlit/secrets.toml (injecte dans l'app)
#   - inject_secrets() copie chaque clé dans os.environ
#   - Tous les os.getenv() existants fonctionnent sans modification
#
# En local (dev) :
#   - load_dotenv() charge .env → os.environ  (fait dans app.py)
#   - inject_secrets() est un no-op silencieux
#
# Usage dans app.py (AVANT tout autre import de modules métier) :
#   from core.secrets import inject_secrets
#   inject_secrets()
# =============================================================================

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


def inject_secrets() -> None:
    """
    Injecte st.secrets dans os.environ pour Streamlit Community Cloud.
    Ne remplace pas une variable déjà présente (os.environ.setdefault).
    Silencieux en dev local (st.secrets non disponible → no-op).
    """
    try:
        import streamlit as st

        # st.secrets lève FileNotFoundError si secrets.toml absent
        # et n'est disponible qu'une fois le runtime Streamlit démarré
        secrets = st.secrets.to_dict() if hasattr(st.secrets, "to_dict") else dict(st.secrets)

        injected = 0
        for key, val in secrets.items():
            if isinstance(val, str) and val:
                os.environ.setdefault(key, val)
                injected += 1
            elif isinstance(val, dict):
                # Sections TOML (ex: [anthropic]) — on les aplatit
                for sub_key, sub_val in val.items():
                    env_key = f"{key.upper()}_{sub_key.upper()}"
                    if isinstance(sub_val, str) and sub_val:
                        os.environ.setdefault(env_key, sub_val)
                        injected += 1

        if injected:
            log.info(f"[Secrets] {injected} cle(s) injectee(s) depuis st.secrets")

    except Exception:
        # Local dev : secrets.toml absent ou Streamlit non demarre — normal
        pass


def is_cloud() -> bool:
    """
    Retourne True si l'app tourne sur Streamlit Community Cloud.
    Détection via variable d'environnement injectée par SCC.
    """
    return bool(os.getenv("STREAMLIT_SHARING_MODE") or os.getenv("IS_CLOUD"))
