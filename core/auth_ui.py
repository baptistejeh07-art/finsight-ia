"""UI Streamlit pour l'authentification — page login + composants sidebar.

Composants :
    - render_login_page()  : page de connexion séparée (avant accès app)
    - render_user_sidebar(): bandeau utilisateur (email + déconnexion)
    - handle_oauth_callback(): traite le retour OAuth Google
"""

from __future__ import annotations
import streamlit as st
from urllib.parse import urlencode

from core import auth as _auth


# ---------------------------------------------------------------------------
# Constantes branding
# ---------------------------------------------------------------------------

_APP_URL_DEFAULT = "https://finsight-ia-lxappmzvfqned33anmbuvh5.streamlit.app/"
_CGU_URL = "#"  # placeholder — à remplacer par l'URL site vitrine
_PRIVACY_URL = "#"  # idem


# ---------------------------------------------------------------------------
# CSS login
# ---------------------------------------------------------------------------

_LOGIN_CSS = """
<style>
.login-wrap {
  max-width: 420px;
  margin: 40px auto;
  padding: 32px;
  background: #ffffff;
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  box-shadow: 0 4px 24px rgba(17, 24, 39, 0.06);
}
.login-title {
  font-size: 26px;
  font-weight: 700;
  color: #111827;
  margin: 0 0 6px;
  text-align: center;
  letter-spacing: -0.5px;
}
.login-tag {
  font-size: 13px;
  color: #6B7280;
  text-align: center;
  margin-bottom: 24px;
}
.login-divider {
  display: flex;
  align-items: center;
  margin: 18px 0;
  color: #9CA3AF;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 1px;
}
.login-divider::before, .login-divider::after {
  content: "";
  flex: 1;
  height: 1px;
  background: #E5E7EB;
}
.login-divider::before { margin-right: 12px; }
.login-divider::after  { margin-left: 12px; }
.login-cgu {
  font-size: 11px;
  color: #6B7280;
  text-align: center;
  margin-top: 16px;
  line-height: 1.6;
}
.login-cgu a { color: #1A4480; text-decoration: none; }
.login-cgu a:hover { text-decoration: underline; }
.login-guest {
  text-align: center;
  margin-top: 24px;
  font-size: 12px;
  color: #9CA3AF;
}
.login-guest a {
  color: #6B7280;
  text-decoration: underline;
  cursor: pointer;
}
</style>
"""


# ---------------------------------------------------------------------------
# Page login
# ---------------------------------------------------------------------------

def render_login_page() -> None:
    """Page de connexion AVANT l'accès à l'app.

    Sections (de haut en bas) :
      1. Titre + tagline
      2. Bouton Google (gros, primaire)
      3. Séparateur "ou"
      4. Onglets Connexion / Créer un compte (email + password)
      5. Lien discret "Continuer sans compte"
      6. Mentions CGU
    """
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    # Restaurer session si déjà loggé via cookies
    if _auth.restore_session_from_cookies():
        st.rerun()

    # Traiter callback OAuth Google si retour avec code
    handle_oauth_callback()

    st.markdown('<div class="login-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="login-title">FinSight IA</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="login-tag">Plateforme d\'analyse financière institutionnelle</div>',
        unsafe_allow_html=True,
    )

    # ── Google OAuth ────────────────────────────────────────────────────────
    google_url = _auth.sign_in_google(redirect_to=_get_app_url())
    if google_url:
        st.link_button(
            "🔐  Continuer avec Google",
            google_url,
            use_container_width=True,
            type="primary",
        )
    else:
        st.button(
            "🔐  Continuer avec Google",
            use_container_width=True,
            disabled=True,
            help="Google OAuth non configuré côté Supabase. Utilisez email/mot de passe.",
        )

    st.markdown('<div class="login-divider">ou</div>', unsafe_allow_html=True)

    # ── Onglets Connexion / Création ────────────────────────────────────────
    tab_login, tab_signup = st.tabs(["Se connecter", "Créer un compte"])

    with tab_login:
        with st.form("login_form", clear_on_submit=False):
            email_l = st.text_input(
                "Email", placeholder="vous@exemple.com", key="login_email"
            )
            pwd_l = st.text_input(
                "Mot de passe", type="password", key="login_password"
            )
            ok = st.form_submit_button("Se connecter", use_container_width=True, type="primary")
        if ok:
            if not email_l or not pwd_l:
                st.error("Email et mot de passe requis.")
            else:
                success, msg = _auth.sign_in_email(email_l.strip(), pwd_l)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    with tab_signup:
        with st.form("signup_form", clear_on_submit=False):
            email_s = st.text_input(
                "Email", placeholder="vous@exemple.com", key="signup_email"
            )
            pwd_s = st.text_input(
                "Mot de passe", type="password", key="signup_password",
                help="Minimum 6 caractères.",
            )
            cgu_ok = st.checkbox(
                "J'accepte les conditions d'utilisation et la politique de confidentialité.",
                key="signup_cgu",
            )
            ok = st.form_submit_button("Créer mon compte", use_container_width=True, type="primary")
        if ok:
            if not email_s or not pwd_s:
                st.error("Email et mot de passe requis.")
            elif len(pwd_s) < 6:
                st.error("Mot de passe trop court (minimum 6 caractères).")
            elif not cgu_ok:
                st.error("Vous devez accepter les conditions d'utilisation.")
            else:
                success, msg = _auth.sign_up_email(email_s.strip(), pwd_s)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    # ── Lien discret mode invité ────────────────────────────────────────────
    st.markdown(
        '<div class="login-guest">— ou —</div>',
        unsafe_allow_html=True,
    )
    if st.button("Continuer sans compte", key="guest_btn", use_container_width=False):
        _auth.set_guest_mode(True)
        st.rerun()

    # ── CGU ─────────────────────────────────────────────────────────────────
    st.markdown(
        f'<div class="login-cgu">'
        f'En créant un compte vous acceptez nos '
        f'<a href="{_CGU_URL}" target="_blank">conditions d\'utilisation</a> et notre '
        f'<a href="{_PRIVACY_URL}" target="_blank">politique de confidentialité</a>.'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# OAuth callback handler
# ---------------------------------------------------------------------------

def handle_oauth_callback() -> None:
    """Si l'URL contient ?code=XXX (retour Google OAuth), échange contre session."""
    try:
        params = st.query_params
        code = params.get("code")
        if code:
            success, msg = _auth.exchange_oauth_code(code)
            if success:
                # Nettoie l'URL (retire ?code=... pour pas re-déclencher)
                try:
                    st.query_params.clear()
                except Exception:
                    pass
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Sidebar utilisateur (à appeler depuis render_sidebar)
# ---------------------------------------------------------------------------

def render_user_sidebar() -> None:
    """Affiche dans la sidebar : email + bouton se déconnecter (ou rien en invité)."""
    user = _auth.get_current_user()
    if user:
        email = user.get("email") or "—"
        # Petit affichage discret
        st.markdown(
            f'<div style="font-size:11px;color:#6B7280;padding:6px 0 2px;">'
            f'Connecté en tant que</div>'
            f'<div style="font-size:13px;color:#111827;font-weight:500;'
            f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'
            f'{_e(email)}</div>',
            unsafe_allow_html=True,
        )
        if st.button("Se déconnecter", key="btn_logout", use_container_width=True):
            _auth.sign_out()
            st.rerun()
    elif _auth.is_guest():
        # Pas de badge, juste un bouton pour créer un compte (discret)
        if st.button("Créer un compte", key="btn_to_signup", use_container_width=True):
            _auth.set_guest_mode(False)
            st.rerun()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _e(s: str) -> str:
    """Escape HTML."""
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _get_app_url() -> str:
    """Retourne l'URL de l'app (pour le redirect OAuth)."""
    import os
    # 1. Variable d'environnement explicite
    url = os.getenv("FINSIGHT_APP_URL", "").strip()
    if url:
        return url
    # 2. Streamlit secrets
    try:
        url = st.secrets.get("FINSIGHT_APP_URL", "")
        if url:
            return str(url)
    except Exception:
        pass
    # 3. Default cloud URL
    return _APP_URL_DEFAULT
