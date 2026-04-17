"""Wrapper Supabase Auth pour FinSight IA.

Gère l'authentification utilisateur (Google OAuth + email/password) et
le mode invité illimité. Sessions persistantes via cookies (refresh
token + access token stockés côté client).

API publique :
    - get_client()                  : renvoie le client Supabase singleton
    - sign_up_email(email, password): crée un compte email/password
    - sign_in_email(email, password): connexion email/password
    - sign_in_google()              : renvoie l'URL OAuth Google a rediriger
    - sign_out()                    : ferme la session courante
    - get_current_user()            : dict {id, email, name, avatar_url} ou None
    - is_authenticated()            : True si session active
    - is_guest()                    : True si mode invité actif
    - set_guest_mode(True)          : active le mode invité
    - restore_session_from_cookies(): a appeler au démarrage de l'app
    - persist_session_to_cookies()  : a appeler après sign_in/sign_up
"""

from __future__ import annotations
import os
import logging
from typing import Optional

log = logging.getLogger(__name__)

# Streamlit + cookies imports lazy (pour permettre les tests unitaires hors UI)
_st = None
_cookie_manager = None


def _get_st():
    global _st
    if _st is None:
        import streamlit as st
        _st = st
    return _st


def _get_cookie_manager():
    """Récupère un CookieManager unique par session Streamlit."""
    global _cookie_manager
    st = _get_st()
    if "_finsight_cookie_mgr" not in st.session_state:
        try:
            import extra_streamlit_components as stx
            st.session_state["_finsight_cookie_mgr"] = stx.CookieManager(
                key="finsight_auth_cookies"
            )
        except Exception as e:
            log.warning(f"[auth] CookieManager init failed: {e}")
            st.session_state["_finsight_cookie_mgr"] = None
    return st.session_state["_finsight_cookie_mgr"]


# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

def _get_supabase_url_key() -> tuple[str, str]:
    """Récupère URL + clé anon depuis env / secrets Streamlit."""
    url = os.getenv("SUPABASE_URL", "").strip()
    # Priorité ANON_KEY (frontend safe), fallback PUBLISHABLE_KEY ou SECRET_KEY
    key = (os.getenv("SUPABASE_ANON_KEY", "").strip()
           or os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
           or os.getenv("SUPABASE_SECRET_KEY", "").strip())
    # Fallback Streamlit secrets
    if not url or not key:
        try:
            st = _get_st()
            url = url or st.secrets.get("SUPABASE_URL", "")
            key = (key
                   or st.secrets.get("SUPABASE_ANON_KEY", "")
                   or st.secrets.get("SUPABASE_PUBLISHABLE_KEY", "")
                   or st.secrets.get("SUPABASE_SECRET_KEY", ""))
        except Exception:
            pass
    return url, key


def get_client():
    """Singleton Supabase client. None si configuration absente.

    Flow OAuth = "implicit" (vs PKCE par défaut) car PKCE nécessite un
    code_verifier en localStorage entre le sign_in et le callback, ce que
    Streamlit ne peut pas faire nativement côté serveur. Implicit retourne
    directement les tokens dans l'URL fragment.
    """
    st = _get_st()
    if "_supabase_client" in st.session_state:
        return st.session_state["_supabase_client"]
    url, key = _get_supabase_url_key()
    if not url or not key:
        log.warning("[auth] SUPABASE_URL/KEY manquant — auth désactivée")
        st.session_state["_supabase_client"] = None
        return None
    try:
        from supabase import create_client
        try:
            from supabase.lib.client_options import ClientOptions
            options = ClientOptions(flow_type="implicit")
            client = create_client(url, key, options=options)
        except Exception:
            # Fallback si import ClientOptions échoue : flow PKCE par défaut
            client = create_client(url, key)
        st.session_state["_supabase_client"] = client
        return client
    except Exception as e:
        log.error(f"[auth] Échec création client Supabase : {e}")
        st.session_state["_supabase_client"] = None
        return None


# ---------------------------------------------------------------------------
# Cookies — persistance access_token + refresh_token
# ---------------------------------------------------------------------------

_COOKIE_ACCESS  = "finsight_access_token"
_COOKIE_REFRESH = "finsight_refresh_token"
_COOKIE_GUEST   = "finsight_guest_mode"
_COOKIE_EXPIRY_DAYS = 30  # refresh token valide 30 jours


def persist_session_to_cookies() -> None:
    """Sauvegarde access + refresh token dans les cookies après login."""
    st = _get_st()
    cm = _get_cookie_manager()
    if cm is None:
        return
    sess = st.session_state.get("_supabase_session")
    if not sess:
        return
    try:
        from datetime import datetime, timedelta
        expiry = datetime.utcnow() + timedelta(days=_COOKIE_EXPIRY_DAYS)
        cm.set(_COOKIE_ACCESS,  sess.access_token,  expires_at=expiry, key="set_access")
        cm.set(_COOKIE_REFRESH, sess.refresh_token, expires_at=expiry, key="set_refresh")
        # Reset guest cookie quand on est connecté
        cm.delete(_COOKIE_GUEST, key="del_guest")
    except Exception as e:
        log.warning(f"[auth] persist cookies failed: {e}")


def restore_session_from_cookies() -> bool:
    """Au démarrage de l'app, tente de restaurer la session depuis cookies.

    Retourne True si une session valide a été restaurée.
    """
    st = _get_st()
    if st.session_state.get("_supabase_user"):
        return True  # déjà restauré dans cette session Streamlit
    cm = _get_cookie_manager()
    if cm is None:
        return False
    try:
        cookies = cm.get_all() or {}
    except Exception:
        cookies = {}
    # 1. Mode invité prioritaire
    if cookies.get(_COOKIE_GUEST) == "1":
        st.session_state["_finsight_guest_mode"] = True
        return True
    # 2. Session Supabase
    access  = cookies.get(_COOKIE_ACCESS)
    refresh = cookies.get(_COOKIE_REFRESH)
    if not access or not refresh:
        return False
    client = get_client()
    if client is None:
        return False
    try:
        # Set la session Supabase directement avec les tokens stockés
        client.auth.set_session(access, refresh)
        user_resp = client.auth.get_user()
        if user_resp and user_resp.user:
            st.session_state["_supabase_user"] = _user_to_dict(user_resp.user)
            st.session_state["_supabase_session"] = {
                "access_token":  access,
                "refresh_token": refresh,
            }
            return True
    except Exception as e:
        log.info(f"[auth] Session expirée ou invalide : {e}")
        # Cookies corrompus -> nettoyage
        try:
            cm.delete(_COOKIE_ACCESS,  key="del_access_invalid")
            cm.delete(_COOKIE_REFRESH, key="del_refresh_invalid")
        except Exception:
            pass
    return False


def _user_to_dict(user) -> dict:
    """Convertit un user Supabase en dict simple."""
    meta = (user.user_metadata or {}) if hasattr(user, "user_metadata") else {}
    return {
        "id":         getattr(user, "id", None),
        "email":      getattr(user, "email", None),
        "name":       meta.get("full_name") or meta.get("name") or "",
        "avatar_url": meta.get("avatar_url", ""),
        "provider":   meta.get("provider") or (user.app_metadata or {}).get("provider", "email")
                       if hasattr(user, "app_metadata") else "email",
    }


# ---------------------------------------------------------------------------
# Sign up / sign in / sign out
# ---------------------------------------------------------------------------

def sign_up_email(email: str, password: str) -> tuple[bool, str]:
    """Crée un compte avec email + password.

    Retourne (success, message). Si Supabase a "Confirm email" désactivé,
    l'utilisateur est connecté immédiatement.
    """
    client = get_client()
    if client is None:
        return False, "Service d'authentification indisponible."
    try:
        resp = client.auth.sign_up({"email": email, "password": password})
        if resp.user:
            st = _get_st()
            st.session_state["_supabase_user"] = _user_to_dict(resp.user)
            if resp.session:
                st.session_state["_supabase_session"] = resp.session
                persist_session_to_cookies()
                return True, "Compte créé. Bienvenue !"
            # Si email confirmation activée, pas de session
            return True, ("Compte créé. Vérifiez votre email pour confirmer "
                          "(si la confirmation est activée) ou reconnectez-vous.")
        return False, "Échec création de compte."
    except Exception as e:
        msg = str(e)
        # Messages courants traduits
        if "already registered" in msg.lower() or "already exists" in msg.lower():
            return False, "Cet email est déjà inscrit. Connectez-vous."
        if "password" in msg.lower() and ("short" in msg.lower() or "weak" in msg.lower()):
            return False, "Mot de passe trop court (minimum 6 caractères)."
        if "invalid" in msg.lower() and "email" in msg.lower():
            return False, "Email invalide."
        return False, f"Erreur : {msg}"


def sign_in_email(email: str, password: str) -> tuple[bool, str]:
    """Connexion avec email + password."""
    client = get_client()
    if client is None:
        return False, "Service d'authentification indisponible."
    try:
        resp = client.auth.sign_in_with_password({"email": email, "password": password})
        if resp.user and resp.session:
            st = _get_st()
            st.session_state["_supabase_user"] = _user_to_dict(resp.user)
            st.session_state["_supabase_session"] = resp.session
            st.session_state.pop("_finsight_guest_mode", None)
            persist_session_to_cookies()
            return True, "Connexion réussie."
        return False, "Identifiants invalides."
    except Exception as e:
        msg = str(e)
        if "invalid" in msg.lower() and ("credentials" in msg.lower() or "login" in msg.lower()):
            return False, "Email ou mot de passe incorrect."
        if "not confirmed" in msg.lower():
            return False, "Email non confirmé. Vérifiez votre boîte de réception."
        return False, f"Erreur : {msg}"


def sign_in_google(redirect_to: Optional[str] = None) -> Optional[str]:
    """Lance le flow OAuth Google en mode IMPLICIT (response_type=token).

    Force l'implicit flow côté serveur Supabase via query_params, car le
    PKCE flow par défaut nécessite un code_verifier en localStorage que
    Streamlit ne peut pas persister entre rerun + redirect.

    Retourne l'URL d'autorisation Google. Après auth, Supabase redirige
    vers `redirect_to` avec les tokens dans le FRAGMENT URL :
        https://app.com/#access_token=XXX&refresh_token=YYY&expires_in=...
    """
    client = get_client()
    if client is None:
        return None
    try:
        options = {"query_params": {"response_type": "token"}}
        if redirect_to:
            options["redirect_to"] = redirect_to
        resp = client.auth.sign_in_with_oauth({
            "provider": "google",
            "options": options,
        })
        return getattr(resp, "url", None)
    except Exception as e:
        log.error(f"[auth] sign_in_google failed: {e}")
        return None


def exchange_oauth_code(code: str) -> tuple[bool, str]:
    """[LEGACY PKCE] Échange le code OAuth contre une session.

    Conservé pour compatibilité mais NON UTILISÉ avec flow_type="implicit"
    qui retourne directement access_token + refresh_token dans l'URL fragment.
    Voir set_session_from_tokens() pour le flow implicit.
    """
    client = get_client()
    if client is None:
        return False, "Service indisponible."
    try:
        resp = client.auth.exchange_code_for_session({"auth_code": code})
        if resp.user and resp.session:
            st = _get_st()
            st.session_state["_supabase_user"] = _user_to_dict(resp.user)
            st.session_state["_supabase_session"] = resp.session
            st.session_state.pop("_finsight_guest_mode", None)
            persist_session_to_cookies()
            return True, "Connexion Google réussie."
        return False, "Échec échange code OAuth."
    except Exception as e:
        return False, f"Erreur OAuth : {e}"


def set_session_from_tokens(access_token: str, refresh_token: str) -> tuple[bool, str]:
    """Set la session depuis access + refresh tokens (flow implicit).

    Appelé après que JavaScript ait extrait les tokens de l'URL fragment
    (#access_token=...&refresh_token=...) et les ait passés en query params.
    """
    client = get_client()
    if client is None:
        return False, "Service indisponible."
    try:
        resp = client.auth.set_session(access_token, refresh_token)
        if resp and resp.user:
            st = _get_st()
            st.session_state["_supabase_user"] = _user_to_dict(resp.user)
            st.session_state["_supabase_session"] = {
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
            st.session_state.pop("_finsight_guest_mode", None)
            persist_session_to_cookies()
            return True, "Connexion Google réussie."
        return False, "Échec validation session."
    except Exception as e:
        return False, f"Erreur session : {e}"


def sign_out() -> None:
    """Ferme la session courante (Supabase + cookies + session_state)."""
    st = _get_st()
    client = get_client()
    if client is not None:
        try:
            client.auth.sign_out()
        except Exception as e:
            log.warning(f"[auth] sign_out Supabase: {e}")
    # Nettoyage session_state
    for k in ("_supabase_user", "_supabase_session", "_finsight_guest_mode"):
        st.session_state.pop(k, None)
    # Nettoyage cookies
    cm = _get_cookie_manager()
    if cm is not None:
        try:
            cm.delete(_COOKIE_ACCESS,  key="del_access_signout")
            cm.delete(_COOKIE_REFRESH, key="del_refresh_signout")
            cm.delete(_COOKIE_GUEST,   key="del_guest_signout")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Mode invité
# ---------------------------------------------------------------------------

def set_guest_mode(active: bool = True) -> None:
    """Active ou désactive le mode invité (persisté en cookie)."""
    st = _get_st()
    if active:
        st.session_state["_finsight_guest_mode"] = True
        # Logout user si besoin
        st.session_state.pop("_supabase_user", None)
        st.session_state.pop("_supabase_session", None)
    else:
        st.session_state.pop("_finsight_guest_mode", None)
    cm = _get_cookie_manager()
    if cm is not None:
        try:
            from datetime import datetime, timedelta
            if active:
                expiry = datetime.utcnow() + timedelta(days=_COOKIE_EXPIRY_DAYS)
                cm.set(_COOKIE_GUEST, "1", expires_at=expiry, key="set_guest")
            else:
                cm.delete(_COOKIE_GUEST, key="del_guest_off")
        except Exception as e:
            log.warning(f"[auth] set_guest cookie failed: {e}")


# ---------------------------------------------------------------------------
# Statut session
# ---------------------------------------------------------------------------

def get_current_user() -> Optional[dict]:
    """Renvoie le dict utilisateur ou None si non connecté."""
    st = _get_st()
    return st.session_state.get("_supabase_user")


def is_authenticated() -> bool:
    """True si un utilisateur Supabase est connecté."""
    return get_current_user() is not None


def is_guest() -> bool:
    """True si l'utilisateur navigue en mode invité."""
    st = _get_st()
    return bool(st.session_state.get("_finsight_guest_mode"))


def has_access() -> bool:
    """True si l'utilisateur a accès à l'app (connecté OU invité)."""
    return is_authenticated() or is_guest()
