"""UI Streamlit auth — modal Bloomberg-style + boutons nav top.

Composants exposés :
    - inject_auth_buttons_in_nav() : injecte 2 boutons "Se connecter" / "S'inscrire"
                                     dans la navbar top, alignés à droite
    - handle_oauth_callback()      : traite le retour OAuth Google (?code=...)
    - render_user_sidebar()        : ligne user en haut sidebar (email + déconn.)

L'auth est OPTIONNELLE : l'app reste accessible sans connexion. Les boutons
ouvrent une modal popup (st.dialog) qui réplique l'UX Bloomberg :
    - Logo + titre "Se connecter" / "Créer un compte"
    - Champ email + mot de passe + bouton Continuer
    - Séparateur "ou"
    - Bouton "Continuer avec Google"
    - Lien switch entre Sign in / Sign up
"""

from __future__ import annotations
import streamlit as st

from core import auth as _auth


# ---------------------------------------------------------------------------
# CSS — modal style Bloomberg
# ---------------------------------------------------------------------------

_AUTH_CSS = """
<style>
/* === Boutons nav top "Se connecter / S'inscrire" === */
.fs-nav-auth {
  position: absolute;
  top: 14px;
  right: 24px;
  display: flex;
  gap: 10px;
  z-index: 9999;
  align-items: center;
}
.fs-nav-auth button {
  font-size: 13px !important;
  font-weight: 500 !important;
  padding: 6px 16px !important;
  border-radius: 6px !important;
  min-height: 34px !important;
  height: 34px !important;
}

/* === Modal Bloomberg-style === */
.auth-dialog {
  text-align: center;
  padding: 8px 4px 0;
}
.auth-dialog-logo {
  font-size: 18px;
  font-weight: 700;
  color: #000000;
  margin: 0 0 28px;
  letter-spacing: -0.3px;
  text-align: center;
}
.auth-dialog-title {
  font-size: 22px;
  font-weight: 600;
  color: #111827;
  margin: 0 0 16px;
  letter-spacing: -0.4px;
  text-align: center;
}
/* Cache le header (titre) par défaut de st.dialog (redondant avec notre logo) */
div[role="dialog"] h2,
div[role="dialog"] h3,
div[role="dialog"] [data-testid="stHeading"] {
  display: none !important;
}
.auth-dialog-cgu {
  font-size: 11.5px;
  color: #4B5563;
  line-height: 1.55;
  margin: 0 auto 22px;
  max-width: 360px;
}
.auth-dialog-cgu a {
  color: #111827;
  text-decoration: underline;
  font-weight: 500;
}
.auth-divider {
  display: flex;
  align-items: center;
  margin: 18px 0;
  color: #9CA3AF;
  font-size: 12px;
  text-transform: lowercase;
}
.auth-divider::before, .auth-divider::after {
  content: "";
  flex: 1;
  height: 1px;
  background: #E5E7EB;
}
.auth-divider::before { margin-right: 14px; }
.auth-divider::after  { margin-left:  14px; }
.auth-switch {
  text-align: center;
  font-size: 13px;
  color: #4B5563;
  margin-top: 22px;
}
.auth-switch a {
  color: #111827;
  text-decoration: underline;
  font-weight: 500;
  cursor: pointer;
}
.auth-help {
  text-align: center;
  font-size: 12px;
  color: #6B7280;
  margin-top: 8px;
}
.auth-help a {
  color: #6B7280;
  text-decoration: underline;
}
/* Bouton Google bordure noire pleine largeur */
div[data-testid="stLinkButton"] a,
div[data-testid="baseLinkButton-secondary"] a {
  border: 1px solid #111827 !important;
  background: #FFFFFF !important;
  color: #111827 !important;
}
</style>
"""


# ---------------------------------------------------------------------------
# Boutons nav top
# ---------------------------------------------------------------------------

def inject_auth_buttons_in_nav() -> None:
    """Injecte les 2 boutons d'auth dans la navbar top de l'app.

    À appeler dans main() APRÈS le rendu de la navbar mais AVANT le routing.
    Si l'utilisateur est déjà connecté, n'affiche rien (le bandeau sidebar
    s'occupe de l'identité).
    """
    st.markdown(_AUTH_CSS, unsafe_allow_html=True)

    # Si déjà connecté, pas de boutons (juste le bandeau sidebar)
    if _auth.is_authenticated():
        return

    # Conteneur HTML des 2 boutons en absolute position
    # Streamlit ne permet pas de placer natif des boutons en absolute,
    # donc on utilise un container avec class CSS qui le repositionne.
    _ph = st.container()
    with _ph:
        c1, c2, _ = st.columns([1, 1, 18])
        with c1:
            if st.button("Se connecter", key="nav_signin_btn",
                         use_container_width=True):
                st.session_state["_auth_dialog_mode"] = "signin"
                _open_auth_dialog()
        with c2:
            if st.button("S'inscrire", key="nav_signup_btn",
                         use_container_width=True, type="primary"):
                st.session_state["_auth_dialog_mode"] = "signup"
                _open_auth_dialog()


# ---------------------------------------------------------------------------
# Modal Bloomberg-style (st.dialog)
# ---------------------------------------------------------------------------

def _open_auth_dialog() -> None:
    """Wrapper qui invoque @st.dialog (Streamlit >= 1.36)."""
    _auth_dialog()


@st.dialog("\u200b", width="small")  # zero-width space → titre header invisible
def _auth_dialog() -> None:
    """Modal popup — Bloomberg-style."""
    mode = st.session_state.get("_auth_dialog_mode", "signin")
    st.markdown(_AUTH_CSS, unsafe_allow_html=True)

    # Logo
    st.markdown('<div class="auth-dialog-logo">FinSight</div>',
                unsafe_allow_html=True)

    # Titre dynamique
    title_txt = "Se connecter" if mode == "signin" else "Créer un compte"
    st.markdown(f'<div class="auth-dialog-title">{title_txt}</div>',
                unsafe_allow_html=True)

    # CGU au-dessus du form (style Bloomberg)
    if mode == "signup":
        st.markdown(
            '<div class="auth-dialog-cgu">'
            'En continuant, j\'accepte que FinSight m\'envoie des informations '
            'sur ses produits. Je reconnais avoir lu la '
            '<a href="#" target="_blank">Politique de confidentialité</a> et '
            'j\'accepte les '
            '<a href="#" target="_blank">Conditions d\'utilisation</a>.'
            '</div>',
            unsafe_allow_html=True,
        )

    # ── Form email + password ───────────────────────────────────────────────
    with st.form(f"auth_form_{mode}", clear_on_submit=False, border=False):
        email = st.text_input(
            "Email", placeholder="vous@exemple.com",
            key=f"auth_email_{mode}", label_visibility="collapsed",
        )
        password = st.text_input(
            "Mot de passe", type="password",
            placeholder="Mot de passe (min. 6 caractères)" if mode == "signup" else "Mot de passe",
            key=f"auth_pwd_{mode}", label_visibility="collapsed",
        )
        btn_label = "Continuer" if mode == "signin" else "Créer mon compte"
        submit = st.form_submit_button(
            btn_label, use_container_width=True, type="primary",
        )
    if submit:
        _handle_form_submit(mode, email.strip() if email else "", password)

    # ── Séparateur "ou" ─────────────────────────────────────────────────────
    st.markdown('<div class="auth-divider">ou</div>', unsafe_allow_html=True)

    # ── Bouton Google ───────────────────────────────────────────────────────
    # NB : on N'UTILISE PAS st.link_button qui force target="_blank" (ouvre
    # nouvel onglet → l'utilisateur ne revient pas sur l'app après auth).
    # À la place : bouton normal + JS qui redirige la fenêtre principale
    # via window.top.location.href = url (dans la même fenêtre).
    google_url = _auth.sign_in_google(redirect_to=_get_app_url())
    if google_url:
        if st.button("Continuer avec Google", key=f"google_btn_{mode}",
                     use_container_width=True):
            # Stocke l'URL dans session_state pour déclencher la redirection
            st.session_state["_pending_google_redirect"] = google_url
            st.rerun()
    else:
        st.button(
            "Continuer avec Google",
            use_container_width=True,
            disabled=True,
            help="Connexion Google indisponible",
        )

    # Si une redirection Google est en attente, on l'exécute via JS dans
    # la fenêtre principale (window.top, sortir de l'iframe Streamlit)
    _pending = st.session_state.pop("_pending_google_redirect", None)
    if _pending:
        try:
            from streamlit.components.v1 import html as _html
            _safe_url = _pending.replace('"', '\\"')
            _html(
                f"""
                <script>
                  try {{
                    const top = window.top || window.parent || window;
                    top.location.href = "{_safe_url}";
                  }} catch(e) {{
                    console.error('[auth] Redirect failed:', e);
                    document.body.innerHTML = '<a href="{_safe_url}" target="_top" style="display:block;padding:12px;background:#1B2A4A;color:white;text-align:center;text-decoration:none;border-radius:6px;">Cliquer ici pour continuer avec Google</a>';
                  }}
                </script>
                """,
                height=60, width=400,
            )
            # Fallback visible : lien cliquable au cas où le JS échouerait
            st.markdown(
                f'<div style="margin-top:8px;text-align:center;">'
                f'<a href="{_pending}" target="_top" '
                f'style="font-size:12px;color:#6B7280;text-decoration:underline;">'
                f'Si rien ne se passe, cliquez ici</a></div>',
                unsafe_allow_html=True,
            )
        except Exception as _e:
            st.error(f"Erreur redirect : {_e}")

    # ── Lien switch ─────────────────────────────────────────────────────────
    if mode == "signin":
        st.markdown(
            '<div class="auth-switch">Pas encore de compte ?</div>',
            unsafe_allow_html=True,
        )
        if st.button("Créer un compte", key="auth_to_signup",
                     use_container_width=True):
            st.session_state["_auth_dialog_mode"] = "signup"
            st.rerun()
    else:
        st.markdown(
            '<div class="auth-switch">Déjà un compte ?</div>',
            unsafe_allow_html=True,
        )
        if st.button("Se connecter", key="auth_to_signin",
                     use_container_width=True):
            st.session_state["_auth_dialog_mode"] = "signin"
            st.rerun()


def _handle_form_submit(mode: str, email: str, password: str) -> None:
    """Traite la soumission du form auth modal."""
    if not email or not password:
        st.error("Email et mot de passe requis.")
        return
    if mode == "signup":
        if len(password) < 6:
            st.error("Mot de passe trop court (minimum 6 caractères).")
            return
        success, msg = _auth.sign_up_email(email, password)
    else:
        success, msg = _auth.sign_in_email(email, password)
    if success:
        st.success(msg)
        st.rerun()
    else:
        st.error(msg)


# ---------------------------------------------------------------------------
# OAuth callback handler
# ---------------------------------------------------------------------------

def handle_oauth_callback() -> None:
    """Gère le retour OAuth Google.

    Avec flow_type="implicit" (configuré dans get_client), Supabase retourne
    les tokens dans le fragment URL : #access_token=XXX&refresh_token=YYY
    Ce fragment N'EST PAS accessible côté serveur Python (jamais envoyé au
    serveur). On utilise un petit JS qui :
      1. Lit window.location.hash
      2. Extrait access_token + refresh_token
      3. Réécrit l'URL avec ces tokens en query params (?at=XXX&rt=YYY)
      4. Streamlit re-run → Python lit st.query_params → set_session

    Si les query params contiennent at + rt, on set la session.
    Si l'URL contient ?code=... (PKCE flow legacy), on tente l'exchange.
    """
    try:
        params = st.query_params
        # Cas 1 : flow implicit — tokens en query params (après JS parse hash)
        at = params.get("at")
        rt = params.get("rt")
        if at and rt:
            success, msg = _auth.set_session_from_tokens(at, rt)
            try:
                st.query_params.clear()
            except Exception:
                pass
            if success:
                st.success("✓ " + msg)
                st.rerun()
            else:
                st.error(f"Erreur set session : {msg}")
            return
        # Cas 2 : OAuth error renvoyé par Supabase
        err = params.get("error") or params.get("error_description")
        if err:
            st.error(f"Erreur OAuth : {params.get('error_description') or err}")
            try:
                st.query_params.clear()
            except Exception:
                pass
            return
        # Cas 3 : flow PKCE legacy — code en query param (NE DEVRAIT PAS arriver
        # avec response_type=token, mais fallback)
        code = params.get("code")
        if code:
            success, msg = _auth.exchange_oauth_code(code)
            if success:
                try:
                    st.query_params.clear()
                except Exception:
                    pass
                st.success("✓ " + msg)
                st.rerun()
            else:
                st.error(f"Erreur OAuth (PKCE non supporté avec Streamlit) : {msg}")
            return
        # Cas 4 : injection JS pour parser le hash URL (#access_token=...)
        _inject_hash_to_query_parser()
    except Exception as _e_cb:
        st.error(f"Exception OAuth callback : {_e_cb}")


def _inject_hash_to_query_parser() -> None:
    """Composant invisible qui parse window.top.location.hash et redirige.

    NB : Streamlit Cloud encapsule l'app dans un iframe, ET les composants
    custom (streamlit.components.v1.html) dans un sous-iframe. Donc :
      - window = composant iframe (le plus interne)
      - window.parent = iframe Streamlit
      - window.top = fenêtre utilisateur (URL visible avec le hash)
    On doit utiliser window.top pour atteindre l'URL utilisateur.
    """
    try:
        from streamlit.components.v1 import html as _components_html
        _components_html(
            """
            <script>
            (function() {
              try {
                const top = window.top || window.parent || window;
                const hash = top.location.hash || '';
                if (hash.length < 2) return;
                const params = new URLSearchParams(hash.substring(1));
                const at = params.get('access_token');
                const rt = params.get('refresh_token');
                if (at && rt) {
                  const url = new URL(top.location.href);
                  url.hash = '';
                  url.searchParams.set('at', at);
                  url.searchParams.set('rt', rt);
                  top.location.replace(url.toString());
                }
              } catch (e) {
                // Cross-origin error : on ne peut pas accéder à window.top
                console.warn('[auth] Hash parser bloqué cross-origin:', e);
              }
            })();
            </script>
            """,
            height=0,
            width=0,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Sidebar utilisateur (à appeler depuis render_sidebar)
# ---------------------------------------------------------------------------

def render_user_sidebar() -> None:
    """Affiche dans la sidebar : email + bouton se déconnecter (si connecté)."""
    user = _auth.get_current_user()
    if not user:
        return
    email = user.get("email") or "—"
    st.markdown(
        f'<div style="font-size:11px;color:#6B7280;padding:6px 0 2px;">'
        f'Connecté en tant que</div>'
        f'<div style="font-size:13px;color:#111827;font-weight:500;'
        f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'
        f'{_e(email)}</div>',
        unsafe_allow_html=True,
    )
    if st.button("Se déconnecter", key="btn_logout_sb", use_container_width=True):
        _auth.sign_out()
        st.rerun()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _e(s: str) -> str:
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _get_app_url() -> str:
    import os
    url = os.getenv("FINSIGHT_APP_URL", "").strip()
    if url:
        return url
    try:
        url = st.secrets.get("FINSIGHT_APP_URL", "")
        if url:
            return str(url)
    except Exception:
        pass
    return "https://finsight-ia-lxappmzvfqned33anmbuvh5.streamlit.app/"
