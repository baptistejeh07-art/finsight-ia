#!/usr/bin/env python3
# =============================================================================
# FinSight IA — Interface Streamlit
# app.py
#
# Usage : streamlit run app.py
# =============================================================================

import html as _html
import logging
import time
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")   # local dev

import streamlit as st

# Streamlit Community Cloud : injecte st.secrets → os.environ
# (doit être APRÈS import streamlit, AVANT tout import de modules métier)
from core.secrets import inject_secrets
inject_secrets()

# ---------------------------------------------------------------------------
# Config page
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="FinSight",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS fidèle au wireframe Interface_finsight.html
# ---------------------------------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400&family=DM+Mono:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif !important;
    background-color: #fff;
}
* { font-family: 'DM Sans', sans-serif !important; }

/* Evite que * impose #fff dans les boutons colorés */
button *, button *:before, button *:after,
[role="button"] *, [role="button"] *:before {
    background: transparent !important;
    background-color: transparent !important;
}

/* === Chrome Streamlit === */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], [data-testid="stAppDeployButton"] { display: none !important; }

/* === Sidebar FIXE — toujours visible === */
[data-testid="stSidebar"] {
    transform: none !important;
    visibility: visible !important;
    display: block !important;
}
[data-testid="stSidebar"].sb-open {
    min-width: 330px !important;
    max-width: 330px !important;
}
[data-testid="stSidebar"].sb-closed {
    min-width: 54px !important;
    max-width: 54px !important;
}
/* Cacher les boutons collapse natifs Streamlit */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"] { display: none !important; }

/* Fix artefact visuel "board_" Streamlit/BaseBUI */
[class*="board_"], [class^="board_"], [data-baseweb="board"] { color:transparent!important; font-size:0!important; }

.block-container { padding-top: 1.2rem !important; padding-bottom: 2rem !important; max-width: 100% !important; }

/* NAV */
.fs-nav { height:48px; border-bottom:1px solid #e8e8e8; display:flex; align-items:center; justify-content:space-between; margin-bottom:28px; }
.fs-logo { font-size:14px; font-weight:700; letter-spacing:3px; text-transform:uppercase; color:#111; }
.fs-nav-r { font-family:'DM Mono',monospace; font-size:10px; color:#aaa; letter-spacing:1px; }

/* SIDEBAR */
[data-testid="stSidebar"] { background:#fff !important; border-right:1px solid #e8e8e8 !important; }
[data-testid="stSidebar"] > div:first-child { padding:16px 16px !important; }
.sb-logo { font-size:13px; font-weight:700; letter-spacing:3px; text-transform:uppercase; color:#111; margin-bottom:20px; display:block; }
.sb-label { font-size:10px; font-weight:600; letter-spacing:1.5px; text-transform:uppercase; color:#777; margin-bottom:10px; display:block; padding-top:4px; }
.sb-section { border-bottom:1px solid #f0f0f0; padding-bottom:14px; margin-bottom:14px; }
.menu-item { display:flex; align-items:center; justify-content:space-between; padding:9px 0; border-bottom:1px solid #f5f5f5; cursor:pointer; }
.menu-item:last-child { border-bottom:none; }
.menu-name { font-size:13px; color:#888; }
.menu-name.sp { color:#111; font-weight:600; }
.menu-action { font-family:'DM Mono',monospace; font-size:10px; color:#aaa; }
.src-row { display:flex; justify-content:space-between; align-items:center; padding:6px 0; font-size:12px; color:#555; border-bottom:1px solid #f8f8f8; }
.src-row:last-child { border-bottom:none; }
.src-ok  { font-family:'DM Mono',monospace; font-size:10px; padding:2px 7px; color:#1a7a52; background:#f0faf5; border:1px solid #c8e8d8; }
.src-warn{ font-family:'DM Mono',monospace; font-size:10px; padding:2px 7px; color:#b8922a; background:#fdf8f0; border:1px solid #e8d8b0; }
.sb-disc { padding-top:12px; margin-top:4px; border-top:1px solid #f0f0f0; font-size:11px; color:#888; line-height:1.7; }

/* Download buttons overrides */
.stDownloadButton > button { width:100% !important; font-size:11px !important; font-weight:400 !important; border:1px solid #e0e0e0 !important; color:#555 !important; background:#fff !important; padding:9px 8px !important; border-radius:0 !important; text-align:center !important; justify-content:center !important; white-space:nowrap !important; overflow:hidden !important; text-overflow:ellipsis !important; margin-bottom:2px !important; }
.stDownloadButton > button:hover { border-color:#111 !important; color:#111 !important; }
div[data-testid="stButton"] > button { border-radius:0 !important; }

/* Primary buttons — navy blue */
button[kind="primary"],
button[data-testid="stBaseButton-primary"],
div[data-testid="stButton"] > button[kind="primary"] {
    background-color: #1B2A4A !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 0 !important;
}
button[kind="primary"]:hover,
button[data-testid="stBaseButton-primary"]:hover {
    background-color: #263d6e !important;
    color: #ffffff !important;
}

/* Remove white rectangles — Streamlit container wrappers transparent */
[data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"],
[data-testid="column"],
[data-testid="stElementContainer"],
[data-testid="stWidgetLabel"],
[data-testid="stButtonGroup"],
.stColumn,
div.element-container,
div.stButton { background: transparent !important; }
/* Expander */
[data-testid="stExpander"] { background: transparent !important; border: 1px solid #f0f0f0 !important; }
[data-testid="stExpanderDetails"] { background: #fff !important; }
/* Quick ticker buttons (non-primary) restent blancs, texte sur une ligne */
div[data-testid="stButton"] > button:not([kind="primary"]):not([data-testid="stBaseButton-primary"]) {
    background-color: #fff !important;
    color: #333 !important;
    border: 1px solid #e0e0e0 !important;
    white-space: nowrap !important;
    font-size: 11px !important;
    padding-left: 6px !important;
    padding-right: 6px !important;
    text-align: center !important;
    justify-content: center !important;
}

/* HOME */
.home-eyebrow { font-size:11px; font-weight:500; letter-spacing:3px; text-transform:uppercase; color:#888; text-align:center; margin-bottom:48px; }
.search-q { font-size:13px; font-weight:500; letter-spacing:1px; text-transform:uppercase; color:#666; margin-bottom:16px; text-align:center; }
.quote-block { text-align:center; max-width:420px; margin:36px auto 0; }
.quote-text { font-size:15px; font-weight:300; font-style:italic; line-height:1.8; color:#777; margin-bottom:10px; }
.quote-author { font-size:10px; font-weight:500; color:#999; letter-spacing:1px; text-transform:uppercase; }

/* RESULT HEADER */
.rc { font-size:34px; font-weight:700; letter-spacing:-1px; line-height:1; color:#111; margin-bottom:8px; }
.rm { font-family:'DM Mono',monospace; font-size:11px; color:#777; letter-spacing:.5px; margin-bottom:24px; }
.verdict-row { display:flex; align-items:flex-start; gap:40px; padding:22px 26px; border:1px solid #f0f0f0; margin-bottom:44px; }
.v-lbl { font-size:10px; font-weight:600; color:#777; letter-spacing:1.5px; text-transform:uppercase; margin-bottom:6px; }
.v-buy  { font-size:22px; font-weight:700; color:#1a7a52; }
.v-hold { font-size:22px; font-weight:700; color:#b8922a; }
.v-sell { font-size:22px; font-weight:700; color:#c0392b; }
.v-num  { font-size:28px; font-weight:700; color:#111; line-height:1; }
.v-tgt  { font-size:28px; font-weight:700; color:#b8922a; line-height:1; }
.v-bar  { width:140px; height:3px; background:#e8e8e8; border-radius:1px; margin-top:8px; }
.v-div  { width:1px; background:#e8e8e8; min-height:50px; margin-top:10px; }

/* Section titles */
.sec-t { font-size:11px; font-weight:600; letter-spacing:1.5px; text-transform:uppercase; color:#777; margin-bottom:16px; margin-top:8px; display:flex; align-items:center; gap:14px; }
.sec-t::after { content:''; flex:1; height:1px; background:#f0f0f0; }

/* Market strip */
.mkt-strip { display:grid; grid-template-columns:repeat(5,1fr); border:1px solid #f0f0f0; margin-bottom:44px; }
.mkt-cell { padding:14px 16px; border-right:1px solid #f0f0f0; }
.mkt-cell:last-child { border-right:none; }
.mkt-n { font-size:10px; font-weight:600; color:#777; letter-spacing:.5px; text-transform:uppercase; margin-bottom:5px; }
.mkt-v { font-family:'DM Mono',monospace; font-size:16px; font-weight:500; color:#111; margin-bottom:2px; }
.mkt-up { font-family:'DM Mono',monospace; font-size:11px; color:#1a7a52; }
.mkt-dn { font-family:'DM Mono',monospace; font-size:11px; color:#c0392b; }
.mkt-na { font-family:'DM Mono',monospace; font-size:11px; color:#777; }

/* Ratios grid */
.ratios-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:1px; background:#f0f0f0; border:1px solid #f0f0f0; margin-bottom:44px; }
.ratio-cell { background:#fff; padding:18px 16px; transition:background .15s; }
.ratio-cell:hover { background:#fafafa; }
.r-name { font-size:10px; font-weight:600; color:#777; letter-spacing:.5px; text-transform:uppercase; margin-bottom:7px; }
.r-val  { font-size:22px; font-weight:700; color:#111; line-height:1; margin-bottom:4px; }
.r-sub  { font-size:11px; color:#777; margin-bottom:7px; }
.r-bar  { height:2px; background:#f0f0f0; border-radius:1px; }
.bg  { background:#1a7a52; } .bn { background:#b8922a; } .br { background:#c0392b; }

/* Scenarios */
.scen-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:1px; background:#f0f0f0; border:1px solid #f0f0f0; margin-bottom:44px; }
.scen-cell { background:#fff; padding:26px 18px; text-align:center; }
.scen-tag { font-size:10px; font-weight:600; color:#777; letter-spacing:1px; text-transform:uppercase; margin-bottom:10px; }
.scen-bar { height:2px; background:#f0f0f0; margin-top:14px; border-radius:1px; }
.sp-bull { font-size:28px; font-weight:700; color:#2d7a5a; margin-bottom:5px; }
.sp-base { font-size:28px; font-weight:700; color:#8a7040; margin-bottom:5px; }
.sp-bear { font-size:28px; font-weight:700; color:#a04040; margin-bottom:5px; }
.scen-prob { font-size:12px; color:#666; margin-bottom:4px; }

/* IA section */
.ia-section { border:1px solid #f0f0f0; margin-bottom:44px; }
.ia-bar { display:flex; align-items:center; justify-content:space-between; padding:14px 22px; border-bottom:1px solid #f0f0f0; background:#fafafa; }
.ia-bar-t { font-size:11px; font-weight:600; color:#888; letter-spacing:1px; text-transform:uppercase; }
.ia-model { font-family:'DM Mono',monospace; font-size:11px; color:#888; }
.ia-body { padding:32px 38px; }
.ia-block { margin-bottom:28px; }
.ia-block:last-child { margin-bottom:0; }
.ia-block-t { font-size:11px; font-weight:600; letter-spacing:1px; text-transform:uppercase; color:#666; margin-bottom:12px; padding-bottom:9px; border-bottom:1px solid #f5f5f5; }
.ia-text { font-size:14px; line-height:1.85; color:#444; }
.ia-hl { color:#b8922a; font-weight:600; }
.ia-good { color:#1a7a52; font-weight:600; }
.ia-risk { color:#c0392b; font-weight:600; }
.formula-block { margin:16px 0; padding:14px 18px; background:#f8f8f8; border:1px solid #f0f0f0; border-left:3px solid #e0e0e0; }
.formula-lbl { font-size:10px; font-weight:600; color:#888; letter-spacing:1px; text-transform:uppercase; margin-bottom:8px; }
.formula { font-family:'DM Mono',monospace; font-size:12px; color:#666; line-height:1.8; }

/* Footer */
.page-footer { padding:20px 0 40px; margin-top:24px; border-top:1px solid #f5f5f5; font-size:11px; color:#999; display:flex; justify-content:space-between; }

/* SCREENING */
.scr-rank { font-family:'DM Mono',monospace; font-size:12px; color:#aaa; padding:10px 0; }
.scr-ticker { font-family:'DM Mono',monospace; font-size:10px; color:#999; }
.scr-sector { font-size:11px; color:#777; padding:10px 0; }
.score-pill { display:inline-block; font-family:'DM Mono',monospace; font-size:13px; font-weight:600; padding:3px 10px; }
.score-hi { color:#1a7a52; background:#f0faf5; border:1px solid #c8e8d8; }
.score-md { color:#b8922a; background:#fdf8f0; border:1px solid #e8d8b0; }
.score-lo { color:#c0392b; background:#fdf0f0; border:1px solid #e8c0c0; }
</style>
""", unsafe_allow_html=True)

# JS — supprime le texte "board_" (artefact BaseBUI) des expanders
import streamlit.components.v1 as _components
_sb_class = "sb-open" if st.session_state.get("sidebar_open", True) else "sb-closed"
_components.html(f"""
<script>
(function() {{
  var sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
  if (sidebar) {{
    sidebar.classList.remove('sb-open','sb-closed');
    sidebar.classList.add('{_sb_class}');
  }}
}})();
</script>
""", height=0)

_components.html("""
<script>
(function() {
  function clearBoardText() {
    try {
      var walker = document.createTreeWalker(
        window.parent.document.body, NodeFilter.SHOW_TEXT, null, false
      );
      var node;
      while ((node = walker.nextNode())) {
        if (/^board_/.test(node.nodeValue.trim())) {
          node.nodeValue = "";
        }
      }
    } catch(e) {}
  }

  // Scan immédiat + MutationObserver persistant
  clearBoardText();
  try {
    new MutationObserver(clearBoardText).observe(
      window.parent.document.body,
      { childList: true, subtree: true }
    );
  } catch(e) {}
})();
</script>
""", height=0)

# ---------------------------------------------------------------------------
# Utilitaire : échappement HTML pour tout texte utilisateur/LLM
# ---------------------------------------------------------------------------

def _e(text) -> str:
    """Échappe les caractères HTML dans les chaînes LLM avant injection HTML."""
    if text is None:
        return ""
    return _html.escape(str(text))


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "sidebar_open"       not in st.session_state: st.session_state.sidebar_open       = True
if "stage"              not in st.session_state: st.session_state.stage              = "home"
if "results"            not in st.session_state: st.session_state.results            = None
if "ticker"             not in st.session_state: st.session_state.ticker             = ""
if "screening_results"  not in st.session_state: st.session_state.screening_results  = None
if "screening_universe" not in st.session_state: st.session_state.screening_universe = ""
if "from_screening"     not in st.session_state: st.session_state.from_screening     = False
if "screening_parent"   not in st.session_state: st.session_state.screening_parent   = None

# ---------------------------------------------------------------------------
# Routing : détection du type d'input
# ---------------------------------------------------------------------------

_INDICES_SET = {
    "CAC40", "SP500", "S&P500", "SPX", "DAX40", "FTSE100", "STOXX50", "ALL", "EUROSTOXX50",
}
_SECTOR_ALIASES_SET = {
    "TECHNOLOGY", "TECH", "HEALTHCARE", "HEALTH",
    "FINANCIALS", "FINANCE", "FINANCIAL", "FINANCIALSERVICES",
    "CONSUMER", "CONSUMERCYCLICAL", "CONSUMERDEFENSIVE",
    "ENERGY", "INDUSTRIALS", "MATERIALS", "BASICMATERIALS",
    "REALESTATE", "UTILITIES", "COMMUNICATION", "COMMUNICATIONSERVICES", "TELECOM",
}
_UNIVERSE_DISPLAY = {
    "CAC40": "CAC 40", "SP500": "S&P 500", "S&P500": "S&P 500", "SPX": "S&P 500",
    "DAX40": "DAX 40", "FTSE100": "FTSE 100", "STOXX50": "Euro Stoxx 50",
    "EUROSTOXX50": "Euro Stoxx 50", "ALL": "Univers Global",
    "TECHNOLOGY": "Technology", "TECH": "Technology",
    "HEALTHCARE": "Health Care", "HEALTH": "Health Care",
    "FINANCIALS": "Financial Services", "FINANCE": "Financial Services",
    "FINANCIAL": "Financial Services", "FINANCIALSERVICES": "Financial Services",
    "CONSUMER": "Consumer Cyclical", "CONSUMERCYCLICAL": "Consumer Cyclical",
    "CONSUMERDEFENSIVE": "Consumer Defensive",
    "ENERGY": "Energy", "INDUSTRIALS": "Industrials",
    "MATERIALS": "Basic Materials", "BASICMATERIALS": "Basic Materials",
    "REALESTATE": "Real Estate", "UTILITIES": "Utilities",
    "COMMUNICATION": "Communication Services",
    "COMMUNICATIONSERVICES": "Communication Services", "TELECOM": "Communication Services",
}
_SECTOR_YFINANCE = {
    "TECHNOLOGY": "Technology", "TECH": "Technology",
    "HEALTHCARE": "Health Care", "HEALTH": "Health Care",
    "FINANCIALS": "Financial Services", "FINANCE": "Financial Services",
    "FINANCIAL": "Financial Services", "FINANCIALSERVICES": "Financial Services",
    "CONSUMER": "Consumer Cyclical", "CONSUMERCYCLICAL": "Consumer Cyclical",
    "CONSUMERDEFENSIVE": "Consumer Defensive",
    "ENERGY": "Energy", "INDUSTRIALS": "Industrials",
    "MATERIALS": "Basic Materials", "BASICMATERIALS": "Basic Materials",
    "REALESTATE": "Real Estate", "UTILITIES": "Utilities",
    "COMMUNICATION": "Communication Services",
    "COMMUNICATIONSERVICES": "Communication Services", "TELECOM": "Communication Services",
}


def detect_input_type(query: str) -> str:
    q = query.strip().upper().replace(" ", "").replace("-", "").replace("&", "")
    if q in _INDICES_SET:
        return "screening_indice"
    if q in _SECTOR_ALIASES_SET:
        return "screening_secteur"
    return "analyse_individuelle"


@st.cache_data(show_spinner=False, ttl=86400)
def _get_universe_tickers(universe: str) -> list:
    """Return ticker list for a given universe key (uppercased, normalized)."""
    import sys as _sys
    _scripts = str(Path(__file__).parent / "scripts")
    if _scripts not in _sys.path:
        _sys.path.insert(0, _scripts)

    u = universe.upper().replace("-", "").replace(" ", "").replace("&", "")

    if u == "CAC40":
        from cache_update import CAC40_TICKERS
        return CAC40_TICKERS
    elif u == "DAX40":
        from cache_update import DAX40_TICKERS
        return DAX40_TICKERS
    elif u == "STOXX50" or u == "EUROSTOXX50":
        from cache_update import STOXX50_TICKERS
        return STOXX50_TICKERS
    elif u == "FTSE100":
        from cache_update import FTSE100_TICKERS
        return FTSE100_TICKERS
    elif u in ("SP500", "SPX"):
        from cache_update import fetch_sp500
        return fetch_sp500()
    elif u == "ALL":
        from cache_update import (CAC40_TICKERS, DAX40_TICKERS,
                                   STOXX50_TICKERS, FTSE100_TICKERS, fetch_sp500)
        return list(dict.fromkeys(
            fetch_sp500() + CAC40_TICKERS + DAX40_TICKERS + STOXX50_TICKERS + FTSE100_TICKERS
        ))
    else:
        # Treat as sector name
        return _fetch_sector_tickers(u)


def _fetch_sector_tickers(sector_key: str) -> list:
    """Query Supabase for tickers in a given sector."""
    import os, requests as _req
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SECRET_KEY", "")
    if not url or not key:
        return []
    sector_name = _SECTOR_YFINANCE.get(sector_key, sector_key.title())
    tickers = []
    offset = 0
    while True:
        resp = _req.get(
            f"{url}/rest/v1/tickers_cache",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Range": f"{offset}-{offset+999}"},
            params={"select": "ticker", "sector": f"eq.{sector_name}"},
            timeout=15,
        )
        if resp.status_code not in (200, 206):
            break
        batch = resp.json()
        if not batch:
            break
        tickers.extend(r["ticker"] for r in batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return tickers


# ---------------------------------------------------------------------------
# Contexte macro
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=600)
def fetch_market_context() -> list:
    try:
        import yfinance as yf
        items = [
            ("^GSPC",    "S&P 500"),
            ("^FCHI",    "CAC 40"),
            ("^VIX",     "VIX"),
            ("^TNX",     "Taux 10Y US"),
            ("EURUSD=X", "EUR / USD"),
        ]
        result = []
        for sym, label in items:
            try:
                hist = yf.Ticker(sym).history(period="2d")
                if len(hist) >= 2:
                    prev = hist["Close"].iloc[-2]
                    last = hist["Close"].iloc[-1]
                    chg  = (last - prev) / prev * 100
                    result.append({"name": label, "value": last, "chg": chg})
                elif len(hist) == 1:
                    result.append({"name": label, "value": hist["Close"].iloc[-1], "chg": None})
                else:
                    result.append({"name": label, "value": None, "chg": None})
            except Exception:
                result.append({"name": label, "value": None, "chg": None})
        return result
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar(results) -> None:
    with st.sidebar:
        # Sidebar fermée : juste le bouton de réouverture
        if not st.session_state.get("sidebar_open", True):
            st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
            if st.button("›", use_container_width=True, help="Ouvrir le panneau"):
                st.session_state.sidebar_open = True
                st.rerun()
            return

        # Sidebar ouverte : bouton fermeture + logo
        col_logo, col_close = st.columns([4, 1])
        with col_logo:
            st.markdown('<span class="sb-logo">FinSight</span>', unsafe_allow_html=True)
        with col_close:
            if st.button("‹", use_container_width=True, help="Fermer le panneau"):
                st.session_state.sidebar_open = False
                st.rerun()

        # ---------------------------------------------------------------------------
        # Helper : git push authentifie avec GITHUB_TOKEN si disponible
        # ---------------------------------------------------------------------------
        def _git_push_authenticated(_root_path):
            import subprocess as _gsp, os as _os
            _r = _gsp.run(["git", "push"], cwd=str(_root_path), capture_output=True)
            if _r.returncode == 0:
                return True
            try:
                _token = st.secrets.get("GITHUB_TOKEN", "") or _os.environ.get("GITHUB_TOKEN", "")
            except Exception:
                _token = _os.environ.get("GITHUB_TOKEN", "")
            if not _token:
                return False
            try:
                _url_r = _gsp.run(["git", "remote", "get-url", "origin"],
                                   cwd=str(_root_path), capture_output=True, text=True)
                _url = _url_r.stdout.strip()
                if _url.startswith("https://"):
                    _auth_url = _url.replace("https://", f"https://x-access-token:{_token}@")
                    _gsp.run(["git", "remote", "set-url", "origin", _auth_url],
                             cwd=str(_root_path), capture_output=True)
                    _r2 = _gsp.run(["git", "push"], cwd=str(_root_path), capture_output=True)
                    _gsp.run(["git", "remote", "set-url", "origin", _url],
                             cwd=str(_root_path), capture_output=True)
                    return _r2.returncode == 0
            except Exception:
                pass
            return False

        # Aperçu Claude — previews en attente d'approbation (section dev, en haut pour acces rapide)
        _preview_root = Path(__file__).parent / "preview"
        if "prev_dismissed" not in st.session_state:
            st.session_state["prev_dismissed"] = set()
        def _preview_sort_key(d: Path) -> float:
            ts_file = d / "_timestamp.txt"
            try:
                if ts_file.exists():
                    return float(ts_file.read_text(encoding="utf-8").strip())
            except Exception:
                pass
            return 0.0
        try:
            _all_preview = sorted(
                [d for d in _preview_root.iterdir()
                 if d.is_dir() and d.name not in st.session_state["prev_dismissed"]],
                key=_preview_sort_key, reverse=True
            ) if _preview_root.exists() else []
        except Exception:
            _all_preview = [
                d for d in _preview_root.iterdir()
                if d.is_dir() and d.name not in st.session_state["prev_dismissed"]
            ] if _preview_root.exists() else []
        _preview_tickers = _all_preview[:1]

        st.markdown('<div class="sb-section">', unsafe_allow_html=True)
        st.markdown('<span class="sb-label">Aperçu Claude</span>', unsafe_allow_html=True)
        if _preview_tickers:
            st.markdown(
                '<div style="font-size:11px;color:#888;margin-bottom:6px">'
                'Outputs générés par Claude — en attente de validation</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="font-size:11px;color:#888;padding:4px 0 8px">'
                'Aucun fichier en attente.<br>'
                '<code style="font-size:10px">python tools/audit.py --preview AAPL</code>'
                '</div>',
                unsafe_allow_html=True,
            )
        if _preview_tickers:
            _prod_root = Path(__file__).parent / "outputs" / "generated" / "cli_tests"
            _prod_root.mkdir(parents=True, exist_ok=True)
            for _ticker_dir in _preview_tickers:
                _ticker = _ticker_dir.name
                _files  = sorted(_ticker_dir.glob("*"))
                if not _files:
                    continue
                st.markdown(f'<div style="font-size:12px;font-weight:600;margin:8px 0 4px">{_ticker}</div>',
                            unsafe_allow_html=True)
                _rejected_key = f"prev_rejected_{_ticker}"
                if _rejected_key not in st.session_state:
                    st.session_state[_rejected_key] = set()
                for _f in _files:
                    if _f.suffix.lower() == '.json' or _f.name == '_timestamp.txt':
                        continue
                    _ext  = _f.suffix.lower()
                    _mime = {"pdf": "application/pdf", "pptx": "application/vnd.ms-powerpoint",
                             "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             "txt": "text/plain"}.get(_ext.lstrip("."), "application/octet-stream")
                    _is_rejected = _f.name in st.session_state[_rejected_key]
                    _c_dl, _c_x = st.columns([5, 1])
                    with _c_dl:
                        if _is_rejected:
                            st.markdown(
                                f'<div style="font-size:11px;color:#888;text-decoration:line-through;'
                                f'padding:6px 0">{_f.name}</div>',
                                unsafe_allow_html=True,
                            )
                        else:
                            import datetime as _dt
                            _mtime = _dt.datetime.fromtimestamp(_f.stat().st_mtime)
                            _ext_label = {"pdf": "Rapport PDF", "pptx": "Pitchbook", "xlsx": "Excel", "txt": "Briefing"}.get(_ext.lstrip("."), _f.suffix.upper())
                            _dl_label = f"{_ext_label}  ({_mtime.strftime('%d/%m %H:%M')})"
                            _dl_fname = f"{_f.stem}_{_mtime.strftime('%Y%m%d')}{_f.suffix}"
                            st.download_button(
                                _dl_label,
                                _f.read_bytes(),
                                file_name=_dl_fname,
                                mime=_mime,
                                use_container_width=True,
                                key=f"prev_dl_{_ticker}_{_f.name}",
                            )
                    with _c_x:
                        if _is_rejected:
                            if st.button("↩", key=f"prev_restore_{_ticker}_{_f.name}",
                                         help="Restaurer", use_container_width=True):
                                st.session_state[_rejected_key].discard(_f.name)
                                st.rerun()
                        else:
                            if st.button("✗", key=f"prev_rej_{_ticker}_{_f.name}",
                                         help="Rejeter ce fichier", use_container_width=True):
                                st.session_state[_rejected_key].add(_f.name)
                                st.rerun()
                _kept = [_f for _f in _files if _f.name not in st.session_state[_rejected_key]
                         and _f.suffix.lower() != '.json' and _f.name != '_timestamp.txt']
                _confirm_key = f"prev_confirm_{_ticker}"
                if _confirm_key not in st.session_state:
                    st.session_state[_confirm_key] = None
                _pending = st.session_state[_confirm_key]
                if _pending is None:
                    _nb_kept = len(_kept)
                    _nb_rej  = len(_files) - _nb_kept
                    _lbl_ok  = f"✓ Valider ({_nb_kept})" if _nb_rej else "✓ Valider tout"
                    _col_ok, _col_ko = st.columns(2)
                    with _col_ok:
                        if st.button(_lbl_ok, key=f"prev_ok_{_ticker}", use_container_width=True,
                                     disabled=_nb_kept == 0):
                            st.session_state[_confirm_key] = "ok"
                            st.rerun()
                    with _col_ko:
                        if st.button("✗ Tout rejeter", key=f"prev_ko_{_ticker}", use_container_width=True):
                            st.session_state[_confirm_key] = "ko"
                            st.rerun()
                elif _pending == "ok":
                    _nb = len(_kept)
                    st.warning(f"Valider {_nb} fichier(s) pour {_ticker} ?")
                    _c1, _c2 = st.columns(2)
                    with _c1:
                        if st.button("Confirmer", key=f"prev_ok_confirm_{_ticker}", use_container_width=True):
                            _git_ok = False
                            try:
                                import shutil as _shutil
                                import subprocess as _sp
                                for _f in _kept:
                                    _shutil.copy2(_f, _prod_root / _f.name)
                                _root = Path(__file__).parent
                                _sp.run(["git", "rm", "-rf", f"preview/{_ticker}/"],
                                        cwd=str(_root), capture_output=True)
                                _sp.run(["git", "commit", "-m",
                                         f"chore(preview): valide et supprime {_ticker}"],
                                        cwd=str(_root), capture_output=True)
                                _git_ok = _git_push_authenticated(_root)
                                _shutil.rmtree(str(_ticker_dir), ignore_errors=True)
                            except Exception:
                                pass
                            st.session_state.pop(_confirm_key, None)
                            st.session_state.pop(_rejected_key, None)
                            st.session_state["prev_dismissed"].add(_ticker)
                            if _git_ok:
                                st.success(f"{_ticker} : {_nb} fichier(s) valide(s) et synchronise(s)")
                            else:
                                st.warning(f"{_ticker} : {_nb} fichier(s) valide(s) — ajoutez GITHUB_TOKEN dans les secrets Streamlit")
                            st.rerun()
                    with _c2:
                        if st.button("Annuler", key=f"prev_ok_cancel_{_ticker}", use_container_width=True):
                            st.session_state[_confirm_key] = None
                            st.rerun()
                elif _pending == "ko":
                    st.warning(f"Supprimer definitivement {_ticker} ?")
                    _c1, _c2 = st.columns(2)
                    with _c1:
                        if st.button("Confirmer", key=f"prev_ko_confirm_{_ticker}", use_container_width=True):
                            try:
                                import shutil as _shutil
                                _shutil.rmtree(_ticker_dir)
                            except Exception:
                                pass
                            try:
                                import subprocess as _sp2
                                _root = Path(__file__).parent
                                _sp2.run(["git", "rm", "-rf", f"preview/{_ticker}/"], cwd=str(_root), capture_output=True)
                                _sp2.run(["git", "commit", "-m", f"chore(preview): supprime {_ticker}"], cwd=str(_root), capture_output=True)
                                _git_push_authenticated(_root)
                            except Exception:
                                pass
                            st.session_state.pop(_confirm_key, None)
                            st.session_state.pop(_rejected_key, None)
                            st.session_state["prev_dismissed"].add(_ticker)
                            st.info(f"{_ticker} rejete")
                            st.rerun()
                    with _c2:
                        if st.button("Annuler", key=f"prev_ko_cancel_{_ticker}", use_container_width=True):
                            st.session_state[_confirm_key] = None
                            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        if results and not results.get("error"):
            if st.button("＋  Nouvelle analyse", use_container_width=True, type="primary"):
                st.session_state.stage        = "home"
                st.session_state.results      = None
                st.session_state.ticker       = ""
                st.session_state.from_screening = False
                st.rerun()

        if st.session_state.get("from_screening") and st.session_state.get("screening_results"):
            if st.button("← Retour au screening", use_container_width=True):
                st.session_state.from_screening = False
                st.session_state.stage = "screening_results"
                st.rerun()

        # Livrables
        st.markdown('<div class="sb-section">', unsafe_allow_html=True)
        st.markdown('<span class="sb-label">Livrables</span>', unsafe_allow_html=True)

        # Screening Excel + sector PDF (if available)
        scr = st.session_state.get("screening_results")
        if scr and scr.get("excel_bytes"):
            scr_name = scr.get("display_name", "screening")
            st.download_button(
                f"Screening {scr_name} ↓ .xlsx",
                scr["excel_bytes"],
                file_name=f"screening_{scr_name.lower().replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        if scr and scr.get("pdf_bytes"):
            scr_name = scr.get("display_name", "secteur")
            _pdf_slug = scr_name.lower().replace(' ', '_').replace('\u2014', '').strip()
            st.download_button(
                "Rapport sectoriel ↓ .pdf",
                scr["pdf_bytes"],
                file_name=f"rapport_{_pdf_slug}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        if scr and scr.get("pptx_bytes"):
            scr_name = scr.get("display_name", "secteur")
            _pptx_slug = scr_name.lower().replace(' ', '_').replace('\u2014', '').strip()
            st.download_button(
                "Pitchbook sectoriel ↓ .pptx",
                scr["pptx_bytes"],
                file_name=f"pitchbook_{_pptx_slug}.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                use_container_width=True,
            )

        if results and not results.get("error"):
            ticker_slug = results.get("ticker", "report")

            pptx_data = results.get("pptx_bytes")
            if not pptx_data:
                pptx = results.get("pptx_path")
                if pptx and Path(pptx).exists():
                    pptx_data = open(pptx, "rb").read()
            if pptx_data:
                st.download_button("Pitchbook Financier ↓ .pptx", pptx_data,
                    file_name=f"{ticker_slug}_pitchbook.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True)

            xlsx_data = results.get("excel_bytes")
            if not xlsx_data:
                xlsx = results.get("excel_path")
                if xlsx and Path(xlsx).exists():
                    xlsx_data = open(xlsx, "rb").read()
            if xlsx_data:
                st.download_button("Ratios & Graphiques ↓ .xlsx", xlsx_data,
                    file_name=f"{ticker_slug}_ratios.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True)

            pdf_data = results.get("pdf_bytes")
            if not pdf_data:
                pdf = results.get("pdf_path")
                if pdf and Path(pdf).exists():
                    pdf_data = open(pdf, "rb").read()
            if pdf_data:
                st.download_button("Rapport PDF ↓ .pdf", pdf_data,
                    file_name=f"{ticker_slug}_report.pdf",
                    mime="application/pdf",
                    use_container_width=True)
            elif results.get("pdf_error"):
                st.error("PDF : " + results["pdf_error"].split("\n")[0])
                if "pdf_err_open" not in st.session_state:
                    st.session_state["pdf_err_open"] = False
                if st.button("Détail erreur PDF ▼" if not st.session_state["pdf_err_open"] else "Détail erreur PDF ▲",
                             key="btn_pdf_err_toggle"):
                    st.session_state["pdf_err_open"] = not st.session_state["pdf_err_open"]
                    st.rerun()
                if st.session_state["pdf_err_open"]:
                    st.code(results["pdf_error"], language="text")

            # Raisonnement IA — scroll vers la section
            st.markdown(
                '<div class="menu-item"><span class="menu-name sp">Raisonnement IA</span>'
                '<span class="menu-action">→ voir</span></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="font-size:11px;color:#ccc;padding:6px 0 12px;">'
                'Disponibles après analyse</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

        # Sources financières
        st.markdown('<div class="sb-section">', unsafe_allow_html=True)
        st.markdown('<span class="sb-label">Sources financières</span>', unsafe_allow_html=True)
        for name, ok in [("Yahoo Finance", True), ("Financial Modeling Prep", True),
                          ("Finnhub", True), ("EODHD", True)]:
            badge = f'<span class="src-ok">Actif</span>' if ok else f'<span class="src-warn">Inactif</span>'
            st.markdown(f'<div class="src-row"><span>{name}</span>{badge}</div>',
                        unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Sources contextuelles
        st.markdown('<div class="sb-section">', unsafe_allow_html=True)
        st.markdown('<span class="sb-label">Sources contextuelles</span>', unsafe_allow_html=True)
        for name in ["Claude AI (Anthropic)", "Reuters / Actualités", "Macro — Fed / BCE"]:
            st.markdown(f'<div class="src-row"><span>{name}</span><span class="src-ok">Actif</span></div>',
                        unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Veille IA ───────────────────────────────────────────────────────
        st.markdown('<div class="sb-section">', unsafe_allow_html=True)
        st.markdown('<span class="sb-label">Veille IA</span>', unsafe_allow_html=True)
        _veille_running = st.session_state.get("veille_running", False)
        if _veille_running:
            st.markdown(
                '<div style="font-size:11px;color:#888;padding:6px 0">Veille en cours...</div>',
                unsafe_allow_html=True,
            )
        else:
            if st.button("Lancer la veille", key="btn_veille", use_container_width=True, type="primary"):
                st.session_state["veille_running"] = True
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # Lancement effectif (hors bouton pour eviter re-render)
        if st.session_state.get("veille_running"):
            with st.spinner("Veille en cours — collecte + resumes IA..."):
                try:
                    import sys as _sys
                    _veille_root = Path(__file__).parent
                    if str(_veille_root) not in _sys.path:
                        _sys.path.insert(0, str(_veille_root))
                    from tools.veille import run_veille
                    _pdf = run_veille(days=7)
                    st.session_state["veille_last_pdf"] = str(_pdf)
                    try:
                        import os as _os
                        _os.startfile(str(_pdf))
                    except Exception:
                        pass
                    st.success(f"Veille generee : {_pdf.name}")
                except Exception as _e:
                    st.error(f"Erreur veille : {_e}")
                finally:
                    st.session_state["veille_running"] = False

        # ── Historique veille ────────────────────────────────────────────────
        _veille_dir = Path(__file__).parent / "outputs" / "veille"
        _veille_pdfs = sorted(_veille_dir.glob("veille_*.pdf"), reverse=True) if _veille_dir.exists() else []
        st.markdown('<div class="sb-section">', unsafe_allow_html=True)
        st.markdown('<span class="sb-label">Historique</span>', unsafe_allow_html=True)
        if _veille_pdfs:
            for _vp in _veille_pdfs[:10]:
                _vdate = _vp.stem.replace("veille_", "")
                _col_dl, _col_open, _col_del = st.columns([5, 1, 1])
                with _col_dl:
                    _parts = _vdate.split("_")
                    _day = f"{_parts[0][6:8]}/{_parts[0][4:6]}"
                    _num = _parts[1] if len(_parts) > 1 else "1"
                    st.download_button(
                        f"Veille {_day} #{_num}",
                        _vp.read_bytes(),
                        file_name=_vp.name,
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"hist_{_vp.name}",
                    )
                with _col_open:
                    if st.button("↗", key=f"open_{_vp.name}", help="Ouvrir",
                                 use_container_width=True):
                        try:
                            import os as _os
                            _os.startfile(str(_vp))
                        except Exception:
                            pass
                with _col_del:
                    if st.button("🗑", key=f"del_{_vp.name}", help="Supprimer",
                                 use_container_width=True):
                        try:
                            import subprocess as _sp_del
                            _root_del = Path(__file__).parent
                            # Chemin RELATIF obligatoire pour git rm sur Windows
                            _rel = _vp.relative_to(_root_del)
                            # Si le fichier n'est pas encore trace, l'ajouter puis supprimer
                            _sp_del.run(["git", "add", str(_rel)], cwd=str(_root_del), capture_output=True)
                            _sp_del.run(["git", "rm", "-f", str(_rel)], cwd=str(_root_del), capture_output=True)
                            if _vp.exists():
                                _vp.unlink()
                            _sp_del.run(["git", "commit", "-m", f"chore(veille): supprime {_vp.name}"], cwd=str(_root_del), capture_output=True)
                            _sp_del.run(["git", "push"], cwd=str(_root_del), capture_output=True)
                            st.rerun()
                        except Exception:
                            pass
        else:
            st.markdown(
                '<div style="font-size:11px;color:#888;padding:4px 0">Aucune veille g\u00e9n\u00e9r\u00e9e.</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

        # Diagnostic API — toggle manuel (evite l'artefact "board_" de st.expander)
        if "diag_open" not in st.session_state:
            st.session_state["diag_open"] = False
        _diag_label = "🔧 Diagnostic API ▲" if st.session_state["diag_open"] else "🔧 Diagnostic API ▼"
        if st.button(_diag_label, key="btn_diag_toggle", use_container_width=True):
            st.session_state["diag_open"] = not st.session_state["diag_open"]
            st.rerun()
        if st.session_state["diag_open"]:
            import os
            from core.secrets import get_secret
            for k in ["ANTHROPIC_API_KEY", "GROQ_API_KEY", "FINNHUB_API_KEY", "FMP_API_KEY"]:
                env_val    = os.getenv(k)
                secret_val = get_secret(k)
                if env_val:
                    st.markdown(f"`✅ {k}` (os.environ)")
                elif secret_val:
                    st.markdown(f"`⚠️ {k}` (st.secrets direct — inject KO)")
                else:
                    st.markdown(f"`❌ {k}` (absent)")

            if st.button("Tester Anthropic + Groq", key="btn_diag_test", use_container_width=True):
                from core.llm_provider import LLMProvider
                for provider in ["anthropic", "groq"]:
                    try:
                        llm = LLMProvider(provider=provider)
                        resp = llm.generate("Réponds juste: OK", max_tokens=5)
                        st.success(f"{provider}: ✅ `{resp[:20]}`")
                    except Exception as ex:
                        st.error(f"{provider}: ❌ `{type(ex).__name__}: {str(ex)[:80]}`")

        st.markdown(
            '<div class="sb-disc">Outil d\'aide à la décision.<br>'
            'Ne constitue pas un conseil<br>en investissement. Données<br>'
            'potentiellement variables.</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Page HOME
# ---------------------------------------------------------------------------

QUOTES = [
    ('"Le prix est ce que vous payez. La valeur est ce que vous obtenez."',
     "— Warren Buffett · Lettre aux actionnaires, 2008"),
    ('"Les marchés peuvent rester irrationnels plus longtemps que vous ne pouvez rester solvable."',
     "— John Maynard Keynes"),
    ('"Investir, c\'est simple. Mais ce n\'est pas facile."',
     "— Warren Buffett"),
    ('"Le risque vient de ne pas savoir ce que l\'on fait."',
     "— Warren Buffett · Berkshire Hathaway"),
    ('"En bourse, le temps est l\'ami des bonnes entreprises et l\'ennemi des mauvaises."',
     "— Warren Buffett"),
    ('"La bourse est un dispositif qui transfère l\'argent des impatients vers les patients."',
     "— Warren Buffett"),
    ('"Il faut être avide quand les autres sont craintifs, et craintif quand les autres sont avides."',
     "— Warren Buffett"),
    ('"La diversification est une protection contre l\'ignorance. Elle n\'a guère de sens pour ceux qui savent ce qu\'ils font."',
     "— Warren Buffett"),
    ('"Un investissement dans la connaissance rapporte les meilleurs intérêts."',
     "— Benjamin Franklin"),
    ('"Le marché boursier est rempli d\'individus qui savent le prix de tout et la valeur de rien."',
     "— Philip Fisher"),
    ('"Dans le court terme, la bourse est une machine à voter. Dans le long terme, c\'est une machine à peser."',
     "— Benjamin Graham"),
    ('"Ne mettez jamais tout votre argent dans une seule action — voilà pourquoi j\'en recommande trois."',
     "— Will Rogers"),
    ('"Les arbres ne montent pas jusqu\'au ciel, mais ils ne s\'arrêtent pas de pousser non plus."',
     "— André Kostolany"),
    ('"Il y a des récessions, il y aura d\'autres krachs boursiers. Si vous ne savez pas que cela va arriver, vous n\'êtes pas prêt."',
     "— Peter Lynch"),
    ('"Le meilleur moment pour investir, c\'était il y a vingt ans. Le deuxième meilleur moment, c\'est maintenant."',
     "— Proverbe chinois"),
    ('"L\'analyse financière est l\'art de transformer l\'incertitude en une décision raisonnée."',
     "— Benjamin Graham · Security Analysis"),
    ('"Un titre n\'est pas juste un symbole sur un écran — c\'est une participation dans une vraie entreprise."',
     "— Peter Lynch · One Up on Wall Street"),
    ('"Les opportunités d\'investissement les plus intéressantes surgissent quand les conditions semblent les plus sombres."',
     "— John Templeton"),
    ('"Connaître les chiffres, c\'est bien. Comprendre l\'entreprise derrière, c\'est mieux."',
     "— Charlie Munger"),
    ('"Le cash est le roi en période de crise, mais le couard en période de croissance."',
     "— Howard Marks · Oaktree Capital"),
]

def render_home() -> None:
    import random
    _, col, _ = st.columns([1, 2.2, 1])
    with col:
        st.markdown('<div style="height:56px"></div>', unsafe_allow_html=True)
        st.markdown('<div class="home-eyebrow">Analyse Financière IA</div>', unsafe_allow_html=True)
        st.markdown('<div class="search-q">Société, indice ou secteur ?</div>', unsafe_allow_html=True)

        ticker_input = st.text_input(
            "ticker", placeholder="AAPL, CAC40, Technology...",
            label_visibility="collapsed", max_chars=30,
        ).strip()

        go = st.button("Analyser →", use_container_width=True, type="primary")

        def _quick_label(text):
            st.markdown(
                f'<div style="margin-top:8px;margin-bottom:2px;font-size:9px;font-weight:600;'
                f'letter-spacing:1.5px;text-transform:uppercase;color:#bbb;text-align:center;">'
                f'{text}</div>',
                unsafe_allow_html=True,
            )

        _quick_label("Sociétés")
        q_cols = st.columns(6)
        quick = ["AAPL", "TSLA", "MSFT", "MC.PA", "OR.PA", "NVDA"]
        clicked = None
        for i, qt in enumerate(quick):
            with q_cols[i]:
                if st.button(qt, key=f"qt_{qt}", use_container_width=True):
                    clicked = qt

        _quick_label("Secteurs")
        quick_sec = ["Technology", "Healthcare", "Financials", "Energy", "Industrials"]
        sec_cols = st.columns(5)
        for i, qs in enumerate(quick_sec):
            with sec_cols[i]:
                if st.button(qs, key=f"qs_{qs}", use_container_width=True):
                    clicked = qs

        _quick_label("Indices")
        idx_cols = st.columns(5)
        quick_idx = ["CAC40", "SP500", "DAX40", "FTSE100", "STOXX50"]
        for i, qi in enumerate(quick_idx):
            with idx_cols[i]:
                if st.button(qi, key=f"qi_{qi}", use_container_width=True):
                    clicked = qi

        target = clicked or (ticker_input if go and ticker_input else None)
        if target:
            input_type = detect_input_type(target)
            if input_type == "analyse_individuelle":
                st.session_state.ticker = target.upper()
                st.session_state.stage  = "running"
            else:
                u_key = target.upper().replace("-", "").replace(" ", "").replace("&", "")
                st.session_state.screening_universe = u_key
                st.session_state.stage = "screening_running"
            st.rerun()

        if "quote_idx" not in st.session_state:
            st.session_state.quote_idx = random.randint(0, len(QUOTES) - 1)
        q = QUOTES[st.session_state.quote_idx]
        st.markdown(
            f'<div class="quote-block">'
            f'<div class="quote-text">{_e(q[0])}</div>'
            f'<div class="quote-author">{_e(q[1])}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Page RUNNING
# ---------------------------------------------------------------------------

def render_running() -> None:
    ticker = st.session_state.ticker
    _, col, _ = st.columns([1, 2, 1])

    with col:
        st.markdown(
            f'<div style="text-align:center;margin-top:64px;">'
            f'<div style="font-size:52px;font-weight:700;letter-spacing:-1px;color:#111;margin-bottom:6px;">{_e(ticker)}</div>'
            f'<div style="font-size:12px;color:#777;margin-bottom:44px;">Analyse en cours — veuillez patienter</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        progress_bar = st.progress(0)
        status_lbl   = st.empty()

        steps = [
            (0.20, "Collecte des données financières"),
            (0.40, "Calcul des 33 ratios"),
            (0.60, "Synthèse IA"),
            (0.80, "Validation QA + Avocat du Diable"),
            (1.00, "Génération des livrables"),
        ]

        def step(pct, label):
            progress_bar.progress(pct)
            status_lbl.markdown(
                f'<div style="text-align:center;font-size:12px;font-weight:500;color:#666;">{_e(label)}…</div>',
                unsafe_allow_html=True,
            )

        from core.graph      import build_graph
        from logs.request_log import RequestLog, AgentEntry
        from logs.db_logger   import log_pipeline_v2

        # Mapping noeud LangGraph → (progression, label)
        _NODE_PROGRESS = {
            "fetch_node":       (0.20, steps[0][1]),
            "fallback_node":    (0.28, "Enrichissement des données (fallback)"),
            "quant_node":       (0.40, steps[1][1]),
            "synthesis_node":   (0.60, steps[2][1]),
            "synthesis_retry":  (0.65, "Retry synthèse (correction QA)"),
            "qa_node":          (0.80, steps[3][1]),
            "devil_node":       (0.87, "Avocat du Diable"),
            "output_node":      (0.95, steps[4][1]),
            "blocked_node":     (1.00, "Analyse bloquée — confiance insuffisante"),
        }

        t0    = time.time()
        graph = build_graph()
        step(0.05, "Initialisation du graphe d'analyse...")

        # --- Streaming LangGraph : mise à jour progress en temps réel ---
        final_state: dict = {}
        try:
            for chunk in graph.stream(
                {"ticker": ticker, "errors": [], "logs": [], "qa_retries": 0},
                stream_mode="updates",
            ):
                node_name  = list(chunk.keys())[0]
                node_delta = chunk[node_name]
                final_state.update(node_delta)
                pct, label = _NODE_PROGRESS.get(node_name, (0.5, node_name))
                step(pct, label)
        except Exception as _ex:
            log.error(f"[app] LangGraph pipeline error: {_ex}", exc_info=True)
            st.error(f"Erreur pipeline : {_ex}")
            if st.button("← Retour"):
                st.session_state.stage = "home"
                st.rerun()
            return

        # --- Extraction des résultats depuis l'état final ---
        snapshot  = final_state.get("raw_data")
        sentiment = final_state.get("sentiment")
        ratios    = final_state.get("ratios")
        synthesis = final_state.get("synthesis")
        qa_python = final_state.get("qa_python")
        qa_haiku  = final_state.get("qa_haiku")
        devil     = final_state.get("devil")
        excel_path  = final_state.get("excel_path")
        pptx_path   = final_state.get("pptx_path")
        pdf_path    = final_state.get("pdf_path")
        excel_bytes = final_state.get("excel_bytes")
        pptx_bytes  = final_state.get("pptx_bytes")
        pdf_bytes   = final_state.get("pdf_bytes")
        blocked    = final_state.get("blocked", False)
        errors     = final_state.get("errors") or []

        if snapshot is None:
            st.error(f"Aucune donnée disponible pour « {ticker} ».")
            if errors:
                st.code("\n".join(str(e) for e in errors), language="text")
            if st.button("← Retour"):
                st.session_state.stage = "home"
                st.rerun()
            return

        elapsed = int((time.time() - t0) * 1000)

        # --- Log V2 pipeline complet ---
        req_log = RequestLog(ticker=ticker)
        for entry in (final_state.get("logs") or []):
            req_log.add(AgentEntry(
                agent=entry.get("node", "?"),
                status=entry.get("status", "ok"),
                latency_ms=entry.get("latency_ms", 0),
                extra={k: v for k, v in entry.items()
                       if k not in ("node", "status", "latency_ms")},
            ))
        req_log.finalize(synthesis=synthesis, snapshot=snapshot, total_ms=elapsed)
        try:
            log_pipeline_v2(req_log)
        except Exception as _ex:
            log.warning(f"[app] log_pipeline_v2: {_ex}")

        progress_bar.progress(1.0)
        status_lbl.markdown(
            f'<div style="text-align:center;font-size:12px;font-weight:600;color:#1a7a52;">'
            f'Analyse terminée en {elapsed/1000:.1f}s</div>',
            unsafe_allow_html=True,
        )
        time.sleep(0.5)

        st.session_state.results = {
            "ticker": ticker, "snapshot": snapshot, "ratios": ratios,
            "synthesis": synthesis, "sentiment": sentiment,
            "qa_python": qa_python, "qa_haiku": qa_haiku, "devil": devil,
            "excel_path": excel_path, "pptx_path": pptx_path, "pdf_path": pdf_path,
            "excel_bytes": excel_bytes, "pptx_bytes": pptx_bytes, "pdf_bytes": pdf_bytes,
            "pdf_error": final_state.get("pdf_error"),
            "blocked": blocked, "elapsed_ms": elapsed,
        }
        st.session_state.stage = "results"
        st.rerun()


# ---------------------------------------------------------------------------
# Helpers dynamiques pour IndicePDFWriter (pas de hardcoding)
# ---------------------------------------------------------------------------

def _gen_catalyseurs(secteurs_list, signal_global, avg_score):
    """Génère 3 catalyseurs depuis les données réelles du screening."""
    cats = []
    # Cat 1 : secteur avec meilleur momentum
    def _mom_val(s):
        try: return float(str(s[7]).replace('%','').replace('+',''))
        except: return 0.0
    if secteurs_list:
        best_mom = max(secteurs_list, key=_mom_val)
        mv = best_mom[7]
        cats.append((
            f"Momentum {best_mom[0][:18]}",
            f"Performance {mv} sur 52 semaines (score {best_mom[2]}/100) — "
            "continuation probable si les BPA NTM confirment la tendance.",
            "3-6 mois"
        ))
    # Cat 2 : derive du signal
    pts_to_surp = max(1, 60 - avg_score)
    if signal_global == "Surpond\xe9rer":
        cats.append(("Expansion des marges",
            f"Score composite {avg_score}/100 — pricing power et levier operationnel "
            "permettent une expansion EBITDA. Re-rating multiple possible.",
            "6-12 mois"))
    elif signal_global == "Neutre":
        cats.append(("Passage en Surponderer",
            f"Score a {pts_to_surp} points du seuil Surponderer (60/100). "
            "Surprise BPA positive ou confirmation acceleration du cycle suffisante.",
            "6-12 mois"))
    else:
        cats.append(("Stabilisation des estimations",
            "Arret des revisions BPA baissiers — signal de retournement sur les "
            "secteurs les plus deverses de l'univers.",
            "9-15 mois"))
    # Cat 3 : macro standard adapté au signal
    if avg_score >= 55:
        cats.append(("Conditions financieres accommodantes",
            "Assouplissement du credit et reduction de la prime de risque — "
            "soutien aux multiples des secteurs a duration elevee.",
            "12-18 mois"))
    else:
        cats.append(("Pivot des banques centrales",
            "Baisse des taux directeurs — re-rating des secteurs croissance "
            "et reduction de la pression sur les bilans endettes.",
            "12-24 mois"))
    return cats[:3]


def _gen_risques(secteurs_list, signal_global, avg_score):
    """Génère 3 risques macro avec probabilités dérivées du score réel."""
    # Probabilites derivees du score (plus le score est bas, plus le risque de recession est eleve)
    p_rec  = 40 if avg_score < 45 else (30 if avg_score < 55 else 20)
    p_inf  = 45 if avg_score < 50 else 35
    p_geo  = 25
    pts_to_sous = max(1, avg_score - 40)
    # Secteurs sensibles aux taux dans l'univers
    rate_secs = [s[0] for s in secteurs_list if s[0] in ("Real Estate","Utilities","Consumer Discretionary")]
    rate_note = (f"Secteurs {', '.join(rate_secs[:2])} tres exposes"
                 if rate_secs else "Compression des multiples de valorisation")
    return [
        ("Recession / ralentissement PIB",
         f"Contraction economique — revision baissiere BPA estimee a "
         f"{5 + max(0, int((50-avg_score)*0.3))}-15%. Score composite "
         f"passerait sous 40 ({pts_to_sous} pts de marge actuelle).",
         f"{p_rec}%", "Eleve"),
        ("Inflation persistante / hausse taux",
         f"Maintien des taux longs — {rate_note}. "
         "Compression des multiples des actifs a duration elevee.",
         f"{p_inf}%", "Modere"),
        ("Choc geopolitique / matieres premieres",
         "Disruption des chaines d'approvisionnement et/ou hausse brutale "
         "du prix des matieres premieres — impact direct sur les marges.",
         f"{p_geo}%", "Eleve"),
    ]


def _gen_scenarios(signal_global, avg_score):
    """Génère les scénarios d'invalidation depuis le signal et score courants."""
    pts_to_surp = max(1, 60 - avg_score)
    pts_to_sous = max(1, avg_score - 40)
    if signal_global == "Surpond\xe9rer":
        bull = f"Maintien score > 60 sur 3 mois + BPA NTM > +8% YoY + conditions financieres stables"
        bear = f"Score < 50 sur 2 mois consecutifs + contraction macro confirmee"
    elif signal_global == "Neutre":
        bull = (f"Score > 60 ({pts_to_surp} pts manquants) + surprise BPA Q2 > +5% "
                f"+ CPI < 2,5% sur 2M consecutifs")
        bear = (f"Score < 40 ({pts_to_sous} pts de marge) via recession technique "
                f"(2T PIB < 0%) ou choc geopolitique majeur")
    else:
        bull = f"Score > 50 sur 2M + reversal technique + stabilisation des flux"
        bear = f"Score < 30 — degradation acceleree BPA + deterioration bilans sectoriels"
    return [
        ("Bull case", bull, "Surponderer", "3-6 mois"),
        ("Bear case", bear, "Sous-ponderer", "6-12 mois"),
        ("Stagflation",
         f"CPI > 3,5% + PIB < 1% — compression multiple "
         f"{5 + max(0, int(avg_score * 0.05)):.0f}-15% attendue",
         "Sous-ponderer selectif", "6-9 mois"),
    ]


def _fetch_perf_history(sym, indice_name, today):
    """Charge l'historique réel de prix depuis yfinance pour le graphique."""
    if not sym:
        return None
    try:
        import yfinance as _yf2
        from datetime import timedelta as _td2
        _start = (today - _td2(days=380)).strftime("%Y-%m-%d")
        _h = _yf2.Ticker(sym).history(start=_start)
        _hb = _yf2.Ticker("^TNX").history(start=_start)
        _hg = _yf2.Ticker("GC=F").history(start=_start)
        if _h is None or _h.empty:
            return None
        _base = float(_h["Close"].iloc[0])
        if _base == 0:
            return None
        _dates = [str(d)[:10] for d in _h.index]
        _i_perf = [round(float(v) / _base * 100, 1) for v in _h["Close"]]
        def _rebase(hist):
            if hist is None or hist.empty:
                return [100.0] * len(_dates)
            b = float(hist["Close"].iloc[0]) or 1
            r = hist["Close"].reindex(_h.index, method="ffill").fillna(b)
            return [round(float(v) / b * 100, 1) for v in r]
        return {
            "dates":  _dates,
            "indice": _i_perf,
            "bonds":  _rebase(_hb),
            "gold":   _rebase(_hg),
            "label_start": _dates[0][:7] if _dates else "",
            "label_end":   _dates[-1][:7] if _dates else "",
            "indice_name": indice_name,
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Helper : construction du dict data pour IndicePDFWriter
# ---------------------------------------------------------------------------

def _build_indice_data(tickers_data: list, display_name: str, universe: str) -> dict:
    """Construit le dict data attendu par IndicePDFWriter depuis tickers_data."""
    from statistics import median as _med
    from datetime import date as _date

    # Date en francais
    _MOIS_FR = {1:"janvier",2:"fevrier",3:"mars",4:"avril",5:"mai",6:"juin",
                7:"juillet",8:"aout",9:"septembre",10:"octobre",11:"novembre",12:"decembre"}
    _d = _date.today()
    today_str = f"{_d.day} {_MOIS_FR[_d.month]} {_d.year}"

    # ── Agrégation par secteur ─────────────────────────────────────────────
    sectors: dict = {}
    for t in tickers_data:
        sec = t.get("sector") or "Autre"
        sectors.setdefault(sec, []).append(t)

    secteurs_list = []
    for sec_name, items in sectors.items():
        nb   = len(items)
        sc   = sum((x.get("score_global") or 0) for x in items) / nb
        # EV/EBITDA : filtrer valeurs aberrantes (< 1 = banques/non-pertinent, > 100 = outlier)
        evs  = [x["ev_ebitda"] for x in items
                if x.get("ev_ebitda") is not None and 1.0 < x["ev_ebitda"] < 100]
        ev   = f"{_med(evs):.1f}x" if evs else "\u2014"
        # Marges : ebitda_margin > 100 = aberrant (banques), fallback gross_margin
        def _get_margin(x):
            em = x.get("ebitda_margin")
            if em is not None and 0 < em <= 100:
                return em
            gm = x.get("gross_margin")
            if gm is not None and 0 < gm <= 100:
                return gm
            return None
        mgs  = [m for m in (_get_margin(x) for x in items) if m is not None]
        mg   = round(_med(mgs), 1) if mgs else 0.0
        # Momentum : deja en % dans compute_screening — pas de x100
        moms = [x["momentum_52w"] for x in items if x.get("momentum_52w") is not None]
        mom_pct = round(_med(moms), 1) if moms else 0.0
        mom_str = f"+{mom_pct:.1f}%" if mom_pct >= 0 else f"{mom_pct:.1f}%"
        # Revenue growth : deja en % dans compute_screening — pas de x100
        revg = [x.get("revenue_growth") for x in items if x.get("revenue_growth") is not None]
        croi_pct = round(_med(revg), 1) if revg else 0.0
        croi_str = f"+{croi_pct:.1f}%" if croi_pct >= 0 else f"{croi_pct:.1f}%"
        sig  = ("Surpond\xe9rer" if sc >= 60 else ("Sous-pond\xe9rer" if sc < 40 else "Neutre"))
        secteurs_list.append((sec_name, nb, int(sc), sig, ev, mg, croi_str, mom_str))

    secteurs_list.sort(key=lambda x: x[2], reverse=True)
    # Supprimer le secteur fourre-tout "Autre" des affichages sectoriels
    secteurs_list = [s for s in secteurs_list if s[0] != "Autre"]

    # ── Signal global ──────────────────────────────────────────────────────
    all_scores = [x.get("score_global") or 0 for x in tickers_data]
    avg_score  = sum(all_scores) / len(all_scores) if all_scores else 50
    signal_global = ("Surpond\xe9rer" if avg_score >= 60
                     else ("Sous-pond\xe9rer" if avg_score < 40 else "Neutre"))
    conviction = min(95, max(50, int(avg_score)))

    # ── Top 3 secteurs — Surponderer en priorite, puis meilleurs Neutre ────
    _SIG_SURP = "Surpond\xe9rer"
    surp_secs   = [s for s in secteurs_list if s[3] == _SIG_SURP]
    other_secs  = [s for s in secteurs_list if s[3] != _SIG_SURP]
    # On prend les Surponderer d'abord, puis complement avec les meilleurs Neutre si < 3
    top3_secs = surp_secs[:3] + other_secs[: max(0, 3 - len(surp_secs))]

    def _build_top3_entry(s):
        sec_name  = s[0]
        sec_items = sectors.get(sec_name, [])
        top_tkrs  = sorted(sec_items, key=lambda x: x.get("score_global") or 0, reverse=True)[:3]
        societes  = []
        for tkr in top_tkrs:
            _ev_raw = tkr.get("ev_ebitda")
            ev_t = (f"{_ev_raw:.1f}x"
                    if (_ev_raw is not None and 1.0 < _ev_raw < 100) else "\u2014")
            sig_t = ("Surpond\xe9rer" if (tkr.get("score_global") or 0) >= 60
                     else ("Sous-pond\xe9rer" if (tkr.get("score_global") or 0) < 40 else "Neutre"))
            societes.append((tkr.get("ticker","?"), sig_t, ev_t, tkr.get("score_global") or 0))
        return {
            "nom":        sec_name,
            "signal":     s[3],
            "score":      s[2],
            "ev_ebitda":  s[4],
            "catalyseur": (
                f"Score {s[2]}/100 · momentum {s[7]} · EV/EBITDA {s[4]}"
                + (f" · Mg.EBITDA {s[5]:.1f}%" if isinstance(s[5],(int,float)) and s[5] else "")
            ),
            "risque":     (
                f"Croiss. revenus {s[6]} sur LTM — "
                + ("sensibilite taux moderee" if s[0] in ("Real Estate","Utilities") else
                   "compression multiple si cycle se retourne")
            ),
            "societes":   societes if societes else [("\u2014", "Neutre", "\u2014", 0)],
        }

    top3 = [_build_top3_entry(s) for s in top3_secs]

    # ── Rotation (phases par défaut) ──────────────────────────────────────
    _phase_map = {
        "Technology": ("Expansion","Faible","Elevee","Accumuler"),
        "Health Care": ("Toutes","Faible","Faible","Accumuler"),
        "Financials": ("Expansion","Positive","Moderee","Accumuler"),
        "Consumer Discretionary": ("Expansion","Moderee","Elevee","Neutre"),
        "Industrials": ("Expansion","Faible","Elevee","Neutre"),
        "Communication Services": ("Expansion","Moderee","Moderee","Neutre"),
        "Consumer Staples": ("Recession","Faible","Faible","Neutre"),
        "Energy": ("Expansion","Faible","Moderee","Neutre"),
        "Real Estate": ("Reprise","Elevee","Moderee","All\xe9ger"),
        "Materials": ("Reprise","Faible","Elevee","Neutre"),
        "Utilities": ("Recession","Elevee","Faible","All\xe9ger"),
    }
    rotation = []
    for s in secteurs_list:
        ph = _phase_map.get(s[0], ("Expansion","Moderee","Moderee","Neutre"))
        rot_sig = ("Accumuler" if s[3] == "Surpond\xe9rer"
                   else ("All\xe9ger" if s[3] == "Sous-pond\xe9rer" else "Neutre"))
        rotation.append((s[0], ph[0], ph[1], ph[2], rot_sig))

    # ── nb_societes et cours indice ───────────────────────────────────────
    _cours_map = {
        # Indices boursiers
        "CAC40":"^FCHI", "SP500":"^GSPC", "DAX40":"^GDAXI",
        "FTSE100":"^FTSE", "STOXX50":"^STOXX50E", "EUROSTOXX50":"^STOXX50E",
        # ETF SPDR sectoriels US (fallback pour screenings sectoriels)
        "ENERGY":"XLE", "TECHNOLOGY":"XLK", "FINANCIALS":"XLF",
        "HEALTH CARE":"XLV", "CONSUMER DISCRETIONARY":"XLY",
        "CONSUMER STAPLES":"XLP", "INDUSTRIALS":"XLI",
        "UTILITIES":"XLU", "REAL ESTATE":"XLRE",
        "MATERIALS":"XLB", "COMMUNICATION SERVICES":"XLC",
    }
    cours_str = "—"; ytd_str = "—"; pe_str = "—"
    try:
        import yfinance as _yf
        _sym = _cours_map.get(universe.upper())
        if _sym:
            _tk = _yf.Ticker(_sym)
            _info = _tk.info
            _px = _info.get("regularMarketPrice") or _info.get("previousClose")
            if _px:
                cours_str = f"{_px:,.2f}".replace(",","X").replace(".",",").replace("X",".")
            # YTD depuis le 1er janvier
            try:
                _hist = _tk.history(start=f"{_d.year}-01-01")
                if _hist is not None and not _hist.empty:
                    _px_jan = float(_hist["Close"].iloc[0])
                    _px_now = float(_hist["Close"].iloc[-1])
                    if _px_jan > 0:
                        _ytd = (_px_now - _px_jan) / _px_jan * 100
                        ytd_str = f"+{_ytd:.1f}%" if _ytd >= 0 else f"{_ytd:.1f}%"
            except Exception:
                pass
            _pe = _info.get("trailingPE") or _info.get("forwardPE")
            if _pe:
                pe_str = f"{_pe:.1f}x"
    except Exception:
        pass
    # P/E fallback : médiane des constituants si l'indice ne retourne pas de P/E
    if pe_str == "\u2014" or pe_str == "—":
        try:
            _pe_vals = [t["pe_ratio"] for t in tickers_data
                        if t.get("pe_ratio") and 5 < t["pe_ratio"] < 80]
            if _pe_vals:
                pe_str = f"{_med(_pe_vals):.1f}x"
        except Exception:
            pass

    # ── Textes synthétiques ───────────────────────────────────────────────
    _SIG_S = "Surpond\xe9rer"; _SIG_N = "Neutre"; _SIG_R = "Sous-pond\xe9rer"
    _nb_s = sum(1 for s in secteurs_list if s[3] == _SIG_S)
    _nb_n = sum(1 for s in secteurs_list if s[3] == _SIG_N)
    _nb_r = sum(1 for s in secteurs_list if s[3] == _SIG_R)
    _surp_noms = " / ".join(s[0] for s in secteurs_list if s[3] == _SIG_S) or "aucun"
    _sous_noms = " / ".join(s[0] for s in secteurs_list if s[3] == _SIG_R) or "aucun"
    top_noms   = " / ".join(s[0] for s in secteurs_list[:3])
    _nb_sec = len(secteurs_list)
    _sec_lbl = "secteur" if _nb_sec == 1 else "secteurs"
    texte_macro = (
        f"Le {display_name} presente un signal global <b>{signal_global} (conviction {conviction}%)</b> "
        f"base sur l'analyse de {len(tickers_data)} societes reparties sur {_nb_sec} {_sec_lbl}. "
        f"Le score composite moyen de {avg_score:.0f}/100 reflete un equilibre entre momentum, "
        f"valorisation et revision des BPA. Les secteurs les plus solides sont : <b>{top_noms}</b>."
    )
    _s_lbl  = "secteur" if _nb_s == 1 else "secteurs"
    _n_lbl  = "Neutre"  if _nb_n == 1 else "Neutres"
    _r_lbl  = "Sous-ponderer" if _nb_r <= 1 else "Sous-ponderer"
    texte_signal = (
        f"Signal global <b>{signal_global} (conviction {conviction}%)</b>. "
        f"L'analyse sectorielle identifie {_nb_s} {_s_lbl} Surponderer, "
        f"{_nb_n} {_n_lbl} et {_nb_r} Sous-ponderer. "
        "Horizon d'allocation recommande : 12 mois."
    )
    _verbe_rot = "Favoriser" if _surp_noms != "aucun" else "Surveiller"
    _cible_rot = _surp_noms if _surp_noms != "aucun" else top_noms
    texte_rotation = (
        "L'analyse du cycle economique actuel oriente le positionnement vers les secteurs "
        "a forte visibilite de BPA et resilience des marges. La sensibilite aux taux reste "
        f"le principal facteur de differentiation. {_verbe_rot} <b>{_cible_rot}</b> "
        "dans un contexte de croissance moderee."
    )

    # ── ERP / 10Y Treasury ───────────────────────────────────────────────
    import yfinance as _yf_erp
    rf_rate_f   = 0.045
    rf_pct_str  = "4.50%"
    erp_pct     = "—"
    erp_signal_s = "—"
    try:
        _tnx = _yf_erp.Ticker("^TNX").history(period="5d")
        if not _tnx.empty:
            rf_rate_f  = float(_tnx["Close"].iloc[-1]) / 100
            rf_pct_str = f"{rf_rate_f*100:.2f}%"
        _sym_idx = _cours_map.get(universe.upper())
        _pe_erp  = None
        if _sym_idx:
            try:
                _idx_info = _yf_erp.Ticker(_sym_idx).info or {}
                _pe_erp = _idx_info.get("forwardPE") or _idx_info.get("trailingPE")
            except Exception:
                pass
        if not (_pe_erp and 0 < _pe_erp < 100):
            try:
                _spy_info = _yf_erp.Ticker("SPY").info or {}
                _pe_erp = _spy_info.get("forwardPE") or _spy_info.get("trailingPE")
            except Exception:
                pass
        if _pe_erp and 0 < _pe_erp < 100:
            _erp_val     = 1 / _pe_erp - rf_rate_f
            erp_pct      = f"{_erp_val*100:.1f}%"
            erp_signal_s = ("Tendu" if _erp_val < 0.02
                            else "Favorable" if _erp_val > 0.04
                            else "Neutre")
    except Exception:
        pass

    # ── ETF SPDR — P/B, DivYield, corrélation, portfolio optim ──────────
    _ETF_MAP_APP = {
        "XLK":"Technology","XLV":"Health Care","XLF":"Financials",
        "XLC":"Communication Services","XLY":"Consumer Discretionary",
        "XLP":"Consumer Staples","XLI":"Industrials","XLE":"Energy",
        "XLB":"Materials","XLRE":"Real Estate","XLU":"Utilities",
    }
    _PB_GENERIC_APP = {
        "Technology":8.5,"Health Care":4.2,"Financials":1.5,
        "Consumer Discretionary":5.8,"Communication Services":3.6,
        "Industrials":4.9,"Consumer Staples":5.2,"Energy":2.3,
        "Materials":3.8,"Real Estate":2.1,"Utilities":1.8,
    }
    _DY_GENERIC_APP = {
        "Technology":0.7,"Health Care":1.6,"Financials":2.1,
        "Consumer Discretionary":0.8,"Communication Services":0.9,
        "Industrials":1.5,"Consumer Staples":2.8,"Energy":3.5,
        "Materials":2.0,"Real Estate":3.8,"Utilities":3.2,
    }
    _GROWTH_APP = {
        "Technology":13.0,"Health Care":8.0,"Financials":7.0,
        "Consumer Discretionary":9.0,"Communication Services":8.5,
        "Industrials":7.0,"Consumer Staples":5.0,"Energy":4.0,
        "Materials":6.0,"Real Estate":5.0,"Utilities":4.0,
    }
    pb_by_sector = {}; dy_by_sector = {}; erp_by_sector = {}
    corr_matrix  = None; sector_weights = {}; sector_contribution = []
    breadth_score = None; factor_tilts = None
    optimal_portfolios = {}
    try:
        import numpy as _np_app
        import yfinance as _yf_etf
        _etfs = list(_ETF_MAP_APP.keys())
        _hist_etf = _yf_etf.download(
            _etfs, period="1y", interval="1mo", progress=False, auto_adjust=True
        )["Close"]
        _hist_etf = _hist_etf.dropna(how="all")
        _ret_1y   = {}
        for _e in _etfs:
            if _e in _hist_etf.columns and len(_hist_etf[_e].dropna()) >= 2:
                _s = _hist_etf[_e].dropna()
                _ret_1y[_e] = (_s.iloc[-1] / _s.iloc[0] - 1) * 100

        # P/B + DivYield depuis info ETF
        for _e, _nom in _ETF_MAP_APP.items():
            try:
                _inf = _yf_etf.Ticker(_e).info or {}
                _pb  = _inf.get("priceToBook")
                _dy  = _inf.get("yield") or _inf.get("dividendYield")
                if _dy and _dy < 0.5: _dy = round(_dy * 100, 2)
                elif _dy: _dy = round(float(_dy), 2)
                pb_by_sector[_nom] = round(float(_pb), 1) if _pb else _PB_GENERIC_APP.get(_nom)
                dy_by_sector[_nom] = _dy or _DY_GENERIC_APP.get(_nom)
            except Exception:
                pb_by_sector[_nom] = _PB_GENERIC_APP.get(_nom)
                dy_by_sector[_nom] = _DY_GENERIC_APP.get(_nom)
            _dy_dec = (dy_by_sector.get(_nom) or 0) / 100
            _gr     = _GROWTH_APP.get(_nom, 6.0) / 100
            erp_by_sector[_nom] = round((_dy_dec + _gr - rf_rate_f) * 100, 1)

        # Corrélation 52S quotidienne
        _hist_daily = _yf_etf.download(
            _etfs, period="1y", interval="1d", progress=False, auto_adjust=True
        )["Close"].dropna(how="all")
        _dret = _hist_daily.pct_change().dropna(how="all")
        _etfs_c = [e for e in _etfs if e in _dret.columns and _dret[e].dropna().shape[0] > 30]
        if len(_etfs_c) >= 4:
            _corr = _dret[_etfs_c].corr()
            _noms_c = [_ETF_MAP_APP[e] for e in _etfs_c]
            corr_matrix = {"etfs": _etfs_c, "noms": _noms_c,
                           "values": _corr.values.tolist(),
                           "corr_median": round(float(_corr.values[_corr.values < 1].mean()), 2)}

            # Breadth & factor tilts
            _cyc = ["Technology","Consumer Discretionary","Financials","Industrials","Energy","Materials","Communication Services"]
            _def = ["Consumer Staples","Health Care","Utilities","Real Estate"]
            _ret_by_nom = {_ETF_MAP_APP[e]: _ret_1y.get(e, 0) for e in _etfs_c}
            _cyc_ret = _np_app.mean([_ret_by_nom.get(s, 0) for s in _cyc if s in _ret_by_nom])
            _def_ret = _np_app.mean([_ret_by_nom.get(s, 0) for s in _def if s in _ret_by_nom])
            breadth_score = sum(1 for v in _ret_by_nom.values() if v > 0) / len(_ret_by_nom) * 100
            factor_tilts  = {"cyclique_ret": round(_cyc_ret, 1), "defensif_ret": round(_def_ret, 1)}

            # Contribution sectorielle
            _tot_ret = sum(_ret_by_nom.values()) or 1
            _sec_w_uniform = 1 / len(_ret_by_nom)
            sector_contribution = sorted(
                [(nom, round(_sec_w_uniform * ret, 2), round(ret, 1))
                 for nom, ret in _ret_by_nom.items()],
                key=lambda x: x[1], reverse=True
            )

            # Portfolio optimization
            try:
                from scipy.optimize import minimize as _sp_min2
                _n2 = len(_etfs_c)
                _vols2 = _dret[_etfs_c].std().values * _np_app.sqrt(252)
                _corr2 = _corr.values
                _cov2  = _np_app.outer(_vols2, _vols2) * _corr2
                _mu2   = _np_app.array([_ret_1y.get(e, 0) / 100 for e in _etfs_c])
                _x02   = _np_app.array([1/_n2]*_n2)
                _bds2  = [(0.0, 0.40)]*_n2
                _con2  = [{"type":"eq","fun": lambda w: _np_app.sum(w)-1}]
                def _pstats(w):
                    vol = float(_np_app.sqrt(max(w @ _cov2 @ w, 1e-12)))
                    return round(float(w @ _mu2)*100,1), round(vol*100,1), round((float(w@_mu2)-rf_rate_f)/vol,2)
                _rmv  = _sp_min2(lambda w: float(w@_cov2@w), _x02, method="SLSQP", bounds=_bds2, constraints=_con2)
                _w_mv = _rmv.x if _rmv.success else _x02
                def _neg_sh(w):
                    vol = float(_np_app.sqrt(max(w@_cov2@w,1e-12)))
                    return -(float(w@_mu2)-rf_rate_f)/vol
                _rtg  = _sp_min2(_neg_sh, _x02, method="SLSQP", bounds=_bds2, constraints=_con2)
                _w_tg = _rtg.x if _rtg.success else _x02
                def _erc2(w):
                    var = float(w@_cov2@w)
                    if var < 1e-12: return 1e10
                    rc = w*(_cov2@w)
                    return float(_np_app.sum((rc - var/_n2)**2))
                _rerc = _sp_min2(_erc2, _x02, method="SLSQP",
                                 bounds=[(0.01,0.40)]*_n2, constraints=_con2)
                _w_erc = _rerc.x if _rerc.success else _x02
                optimal_portfolios = {
                    "sectors": [_ETF_MAP_APP[e] for e in _etfs_c],
                    "rf_rate": round(rf_rate_f*100, 2),
                    "min_var":  {"weights":[round(float(w)*100,1) for w in _w_mv],  **dict(zip(["return","vol","sharpe"],_pstats(_w_mv)))},
                    "tangency": {"weights":[round(float(w)*100,1) for w in _w_tg],  **dict(zip(["return","vol","sharpe"],_pstats(_w_tg)))},
                    "erc":      {"weights":[round(float(w)*100,1) for w in _w_erc], **dict(zip(["return","vol","sharpe"],_pstats(_w_erc)))},
                }
            except Exception:
                pass
    except Exception:
        pass

    # ── Finbert par défaut ────────────────────────────────────────────────
    finbert = {
        "nb_articles": 0,
        "score_agrege": 0.0,
        "positif": {"nb": 0, "score": "N/A", "themes": "Donnees non disponibles"},
        "neutre":  {"nb": 0, "score": "N/A", "themes": "Donnees non disponibles"},
        "negatif": {"nb": 0, "score": "N/A", "themes": "Donnees non disponibles"},
        "par_secteur": [(s[0], "N/A", "Neutre") for s in secteurs_list],
    }

    # ── P/E mediane historique 10 ans + prime/décote ─────────────────────────
    _PE_HIST_APP = {
        "S&P 500":   (13.0, 24.0), "SP500":     (13.0, 24.0),
        "NASDAQ":    (18.0, 38.0), "NASDAQ 100":(18.0, 38.0),
        "CAC 40":    (11.0, 20.0), "CAC40":     (11.0, 20.0),
        "DAX":       (10.0, 19.0), "DAX40":     (10.0, 19.0),
        "FTSE 100":  (10.0, 17.0), "FTSE100":   (10.0, 17.0),
    }
    _pe_range_app = (11.0, 22.0)
    for _k, _v in _PE_HIST_APP.items():
        if _k.lower() in display_name.lower() or display_name.lower() in _k.lower():
            _pe_range_app = _v
            break
    _pe_med_app = round((_pe_range_app[0] + _pe_range_app[1]) / 2, 1)
    _pe_med_str = f"{_pe_med_app:.1f}"
    _prime_decote_str = "—"
    try:
        _pe_num = float(pe_str.replace("x","").replace(",",".").strip())
        _prime_val = (_pe_num - _pe_med_app) / _pe_med_app * 100
        _prime_decote_str = f"+{_prime_val:.0f}% prime" if _prime_val > 0 else f"{_prime_val:.0f}% decote"
    except Exception:
        pass

    return {
        "indice":         display_name,
        "code":           universe[:6].upper(),
        "nb_secteurs":    len(secteurs_list),
        "nb_societes":    len(tickers_data),
        "signal_global":  signal_global,
        "conviction_pct": conviction,
        "date_analyse":   today_str,
        "cours":          cours_str,
        "variation_ytd":  ytd_str,
        "pe_forward":     pe_str,
        "pe_mediane_10y": _pe_med_str,
        "prime_decote":   _prime_decote_str,
        "score_global":   int(avg_score),
        "secteurs":       secteurs_list,
        "texte_macro":    texte_macro,
        "texte_signal":   texte_signal,
        "texte_rotation": texte_rotation,
        "catalyseurs":  _gen_catalyseurs(secteurs_list, signal_global, int(avg_score)),
        "risques":      _gen_risques(secteurs_list, signal_global, int(avg_score)),
        "scenarios":    _gen_scenarios(signal_global, int(avg_score)),
        "perf_history": _fetch_perf_history(_cours_map.get(universe.upper()), display_name, _d),
        "top3_secteurs":  top3,
        "surp_noms":      _surp_noms,
        "sous_noms":      _sous_noms,
        "rotation":       rotation,
        "finbert":        finbert,
        "erp":            erp_pct,
        "rf_rate":        rf_pct_str,
        "erp_signal":     erp_signal_s,
        "pb_by_sector":   pb_by_sector,
        "dy_by_sector":   dy_by_sector,
        "erp_by_sector":  erp_by_sector,
        "corr_matrix":    corr_matrix,
        "sector_contribution": sector_contribution,
        "breadth_score":  breadth_score,
        "factor_tilts":   factor_tilts,
        "optimal_portfolios": optimal_portfolios,
        "methodologie": [
            ("Score sectoriel",   "Composite 0-100 : 40% momentum, 30% rev. BPA, 30% valorisation"),
            ("Signal",            "Surponderer (>60) / Neutre (40-60) / Sous-ponderer (<40)"),
            ("Valorisation",      "EV/EBITDA median LTM — source FMP / yfinance"),
            ("Momentum",          "Performance relative 52 semaines"),
            ("Univers",           f"{display_name} — {len(tickers_data)} societes analysees"),
            ("Mise a jour",       today_str),
        ],
    }


# ---------------------------------------------------------------------------
# Page SCREENING RUNNING
# ---------------------------------------------------------------------------

def render_screening_running() -> None:
    import sys as _sys
    universe     = st.session_state.screening_universe
    display_name = _UNIVERSE_DISPLAY.get(universe, universe)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown(
            f'<div style="text-align:center;margin-top:64px;">'
            f'<div style="font-size:42px;font-weight:700;letter-spacing:-1px;color:#111;margin-bottom:6px;">{_e(display_name)}</div>'
            f'<div style="font-size:12px;color:#777;margin-bottom:44px;">Screening en cours — calcul des ratios</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        status_lbl = st.empty()

        def _status(msg):
            status_lbl.markdown(
                f'<div style="text-align:center;font-size:12px;font-weight:500;color:#666;">{_e(msg)}...</div>',
                unsafe_allow_html=True,
            )

        _status("Chargement des tickers")
        tickers = _get_universe_tickers(universe)

        if not tickers:
            st.error(f"Aucun ticker trouve pour \"{display_name}\".")
            if st.button("<- Retour"):
                st.session_state.stage = "home"
                st.rerun()
            return

        _status(f"Calcul des ratios pour {len(tickers)} societes")

        import os as _os

        # Sur Streamlit Cloud, pas de .env — les secrets viennent de st.secrets via inject_secrets()
        # inject_secrets() a déjà tourné au démarrage de app.py et peuplé os.environ
        # Si des clés manquent encore, on tente un re-inject direct depuis st.secrets
        _missing = [k for k in ("SUPABASE_URL", "SUPABASE_SECRET_KEY") if not _os.getenv(k)]
        if _missing:
            try:
                for _k in _missing:
                    _v = st.secrets.get(_k)
                    if _v:
                        _os.environ[_k] = str(_v)
            except Exception:
                pass

        # Vérification finale
        if not _os.getenv("SUPABASE_URL") or not _os.getenv("SUPABASE_SECRET_KEY"):
            st.error(
                "Clés Supabase manquantes. "
                "Sur Streamlit Cloud : ajouter SUPABASE_URL et SUPABASE_SECRET_KEY dans Settings > Secrets. "
                "En local : vérifier le fichier .env."
            )
            if st.button("<- Retour", key="scr_back_nosup"):
                st.session_state.stage = "home"
                st.rerun()
            return

        _scripts = str(Path(__file__).parent / "scripts")
        if _scripts not in _sys.path:
            _sys.path.insert(0, _scripts)

        try:
            from compute_screening import build_tickers_data
        except ImportError as ex:
            st.error(f"Erreur import compute_screening : {ex}")
            if st.button("<- Retour"):
                st.session_state.stage = "home"
                st.rerun()
            return

        t0 = time.time()
        try:
            tickers_data = build_tickers_data(tickers, workers=4)
        except Exception as ex:
            st.error(f"Erreur screening : {ex}")
            if st.button("<- Retour"):
                st.session_state.stage = "home"
                st.rerun()
            return

        _status("Generation du fichier Excel")

        from outputs.screening_writer import ScreeningWriter
        out_dir = Path(__file__).parent / "outputs" / "generated"
        out_dir.mkdir(exist_ok=True)
        slug    = universe.replace("/", "_").replace(" ", "_")
        out_path = str(out_dir / f"screening_{slug}.xlsx")
        # template_path resolu depuis app.py (non cache par sys.modules)
        _tpl = Path(__file__).parent / "assets" / "FinSight_IA_Screening_CAC40_v3.xlsx"
        _tpl_arg = str(_tpl) if _tpl.exists() else None
        print(f"[app] template_path={_tpl_arg!r} exists={_tpl.exists()}", flush=True)
        try:
            ScreeningWriter.generate(tickers_data, display_name, out_path,
                                     template_path=_tpl_arg)
        except Exception as ex:
            import traceback
            print(f"[app] ScreeningWriter EXCEPTION: {ex}", flush=True)
            traceback.print_exc()
            log.warning(f"[app] ScreeningWriter error: {ex}")

        elapsed = int((time.time() - t0) * 1000)

        xlsx_bytes = None
        try:
            xlsx_bytes = open(out_path, "rb").read()
        except Exception:
            pass

        # ── Génération rapport PDF + PPTX ──────────────────────────────────
        _is_sector = universe in _SECTOR_ALIASES_SET
        pdf_bytes_out  = None
        pptx_bytes_out = None

        if _is_sector:
            _status("Generation du rapport PDF sectoriel")
            try:
                import importlib, outputs.sector_pdf_writer as _spw
                importlib.reload(_spw)
                _pdf_slug = display_name.lower().replace(" ", "_").replace("&", "").replace("/", "_")
                _pdf_path = str(out_dir / f"sector_{_pdf_slug}.pdf")
                _spw.generate_sector_report(
                    sector_name=display_name,
                    tickers_data=sorted(tickers_data, key=lambda x: x.get("score_global") or 0, reverse=True),
                    output_path=_pdf_path,
                    universe="Global",
                )
                pdf_bytes_out = open(_pdf_path, "rb").read()
            except Exception as _ex_pdf:
                import traceback
                log.warning(f"[app] sector_pdf_writer error: {_ex_pdf}")
                traceback.print_exc()

            _status("Generation du pitchbook PPTX sectoriel")
            try:
                import outputs.sectoral_pptx_writer as _sppw
                _sec_sorted = sorted(tickers_data, key=lambda x: x.get("score_global") or 0, reverse=True)
                pptx_bytes_out = _sppw.SectoralPPTXWriter.generate(
                    tickers_data=_sec_sorted,
                    sector_name=display_name,
                    universe="Global",
                )
            except Exception as _ex_pptx:
                import traceback
                log.warning(f"[app] SectoralPPTXWriter error: {_ex_pptx}")
                traceback.print_exc()
        else:
            _status("Generation du rapport PDF indice")
            _indice_data = None
            try:
                from outputs.indice_pdf_writer import IndicePDFWriter
                _indice_data = _build_indice_data(tickers_data, display_name, universe)
                _pdf_slug = display_name.lower().replace(" ", "_").replace("&", "").replace("/", "_")
                _pdf_path = str(out_dir / f"indice_{_pdf_slug}.pdf")
                IndicePDFWriter.generate(_indice_data, _pdf_path)
                pdf_bytes_out = open(_pdf_path, "rb").read()
            except Exception as _ex_pdf:
                import traceback
                log.warning(f"[app] IndicePDFWriter error: {_ex_pdf}")
                traceback.print_exc()

            _status("Generation du pitchbook PPTX indice")
            try:
                from outputs.indice_pptx_writer import IndicePPTXWriter
                if _indice_data is None:
                    _indice_data = _build_indice_data(tickers_data, display_name, universe)
                pptx_bytes_out = IndicePPTXWriter.generate(_indice_data)
            except Exception as _ex_pptx:
                import traceback
                log.warning(f"[app] IndicePPTXWriter error: {_ex_pptx}")
                traceback.print_exc()

        status_lbl.markdown(
            f'<div style="text-align:center;font-size:12px;font-weight:600;color:#1a7a52;">'
            f'Screening termine en {elapsed/1000:.1f}s — {len(tickers_data)} societes</div>',
            unsafe_allow_html=True,
        )
        time.sleep(0.4)

        st.session_state.screening_results = {
            "universe":     universe,
            "display_name": display_name,
            "tickers_data": tickers_data,
            "excel_path":   out_path,
            "excel_bytes":  xlsx_bytes,
            "pdf_bytes":    pdf_bytes_out,
            "pptx_bytes":   pptx_bytes_out,
            "elapsed_ms":   elapsed,
        }
        st.session_state.stage = "screening_results"
        st.rerun()


# ---------------------------------------------------------------------------
# Page SCREENING RESULTS
# ---------------------------------------------------------------------------

def render_screening_results(results: dict) -> None:
    from statistics import median as _med

    tickers_data = results.get("tickers_data") or []
    display_name = results.get("display_name", "Screening")
    elapsed_ms   = results.get("elapsed_ms", 0)
    n            = len(tickers_data)
    today        = date.today().strftime("%d.%m.%Y")

    if not tickers_data:
        st.warning("Aucune donnee de screening disponible.")
        if st.button("<- Retour"):
            st.session_state.stage = "home"
            st.rerun()
        return

    # --- Navigation ---
    parent = st.session_state.get("screening_parent")
    nav_cols = st.columns([1, 1, 4])
    with nav_cols[0]:
        if st.button("+ Nouvelle recherche", type="primary", use_container_width=True):
            st.session_state.screening_parent = None
            st.session_state.stage = "home"
            st.rerun()
    with nav_cols[1]:
        if parent:
            if st.button(f"<- {parent['display_name']}", use_container_width=True):
                st.session_state.screening_results = parent
                st.session_state.screening_parent  = None
                st.rerun()

    # --- Header ---
    st.markdown(f'<div class="rc">{_e(display_name)} — Screening</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="rm">{n} societes analysees · {today} · '
        f'<span style="color:#1a7a52">{elapsed_ms/1000:.1f}s</span></div>',
        unsafe_allow_html=True,
    )

    # --- KPI Strip ---
    best   = tickers_data[0] if tickers_data else {}
    scores = [t.get("score_global") or 0 for t in tickers_data]
    med_sc = _med(scores) if scores else 0

    sec_counts: dict = {}
    for t in tickers_data:
        s = t.get("sector") or "Autres"
        sec_counts[s] = sec_counts.get(s, 0) + 1
    top_sector = max(sec_counts, key=sec_counts.get) if sec_counts else "—"

    cells = "".join([
        f'<div class="mkt-cell"><div class="mkt-n">SOCIETES</div>'
        f'<div class="mkt-v">{n}</div><div class="mkt-na">dans l\'univers</div></div>',

        f'<div class="mkt-cell"><div class="mkt-n">MEILLEUR SCORE</div>'
        f'<div class="mkt-v">{best.get("score_global") or 0:.0f}/100</div>'
        f'<div class="mkt-na">{_e((best.get("company") or "")[:22])}</div></div>',

        f'<div class="mkt-cell"><div class="mkt-n">SCORE MEDIAN</div>'
        f'<div class="mkt-v">{med_sc:.0f}/100</div><div class="mkt-na">univers</div></div>',

        f'<div class="mkt-cell"><div class="mkt-n">SECTEUR DOM.</div>'
        f'<div class="mkt-v" style="font-size:13px;">{_e(top_sector[:18])}</div>'
        f'<div class="mkt-na">{sec_counts.get(top_sector, 0)} socs</div></div>',

        f'<div class="mkt-cell"><div class="mkt-n">DATE</div>'
        f'<div class="mkt-v">{today}</div><div class="mkt-na">screening</div></div>',
    ])
    st.markdown(f'<div class="mkt-strip">{cells}</div>', unsafe_allow_html=True)

    # --- Downloads (sidebar handles Excel + PDF) ---

    # --- Top 10 Global ---
    st.markdown('<div class="sec-t" style="margin-top:32px;">Top 10 — Score global</div>',
                unsafe_allow_html=True)
    top10 = tickers_data[:10]

    hcols = st.columns([0.4, 2.4, 1.6, 1.0, 1.0, 1.0, 1.0, 1.2])
    for hc, h in zip(hcols, ["#", "Societe", "Secteur", "Score", "Value", "Growth", "Quality", ""]):
        with hc:
            st.markdown(
                f'<div style="font-size:10px;font-weight:600;color:#777;letter-spacing:1px;'
                f'text-transform:uppercase;padding-bottom:8px;border-bottom:1px solid #f0f0f0;">{h}</div>',
                unsafe_allow_html=True,
            )

    for i, t in enumerate(top10):
        score    = t.get("score_global") or 0
        sc_cls   = "score-hi" if score >= 60 else ("score-md" if score >= 40 else "score-lo")
        ticker_v = t.get("ticker") or ""
        rcols    = st.columns([0.4, 2.4, 1.6, 1.0, 1.0, 1.0, 1.0, 1.2])

        with rcols[0]:
            st.markdown(f'<div class="scr-rank">{i+1}</div>', unsafe_allow_html=True)
        with rcols[1]:
            st.markdown(
                f'<div style="padding:2px 0;">'
                f'<div style="font-size:13px;font-weight:600;color:#111;">'
                f'{_e((t.get("company") or "")[:28])}</div>'
                f'<div class="scr-ticker">{_e(ticker_v)}</div></div>',
                unsafe_allow_html=True,
            )
        with rcols[2]:
            st.markdown(
                f'<div class="scr-sector">{_e((t.get("sector") or "—")[:20])}</div>',
                unsafe_allow_html=True,
            )
        with rcols[3]:
            st.markdown(
                f'<div style="padding:2px 0;"><span class="score-pill {sc_cls}">{score:.0f}</span></div>',
                unsafe_allow_html=True,
            )
        with rcols[4]:
            v = t.get("score_value") or 0
            st.markdown(
                f'<div style="font-family:\'DM Mono\',monospace;font-size:12px;color:#555;">{v:.0f}</div>',
                unsafe_allow_html=True,
            )
        with rcols[5]:
            g = t.get("score_growth") or 0
            st.markdown(
                f'<div style="font-family:\'DM Mono\',monospace;font-size:12px;color:#555;">{g:.0f}</div>',
                unsafe_allow_html=True,
            )
        with rcols[6]:
            q = t.get("score_quality") or 0
            st.markdown(
                f'<div style="font-family:\'DM Mono\',monospace;font-size:12px;color:#555;">{q:.0f}</div>',
                unsafe_allow_html=True,
            )
        with rcols[7]:
            if st.button("Analyser", key=f"scr_ana_{ticker_v}_{i}", type="primary"):
                st.session_state.ticker       = ticker_v
                st.session_state.from_screening = True
                st.session_state.stage        = "running"
                st.rerun()

    # --- Top 5 par categorie ---
    st.markdown('<div class="sec-t" style="margin-top:36px;">Top 5 par categorie</div>',
                unsafe_allow_html=True)
    cat_cols = st.columns(4)
    categories = [
        ("Value",     "score_value",    "#b8922a"),
        ("Growth",    "score_growth",   "#1a7a52"),
        ("Quality",   "score_quality",  "#1B2A4A"),
        ("Momentum",  "score_momentum", "#7a3a9a"),
    ]
    for cc, (cat_name, sk, color) in zip(cat_cols, categories):
        top5 = sorted(tickers_data, key=lambda x: x.get(sk) or 0, reverse=True)[:5]
        with cc:
            st.markdown(
                f'<div style="font-size:10px;font-weight:600;color:{color};letter-spacing:1.5px;'
                f'text-transform:uppercase;margin-bottom:12px;padding-bottom:8px;'
                f'border-bottom:2px solid {color};">{cat_name}</div>',
                unsafe_allow_html=True,
            )
            for t in top5:
                sc = t.get(sk) or 0
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'padding:7px 0;border-bottom:1px solid #f5f5f5;">'
                    f'<div>'
                    f'<div style="font-size:12px;font-weight:500;color:#111;">'
                    f'{_e((t.get("company") or "")[:20])}</div>'
                    f'<div style="font-family:\'DM Mono\',monospace;font-size:10px;color:#999;">'
                    f'{_e(t.get("ticker") or "")}</div>'
                    f'</div>'
                    f'<div style="font-family:\'DM Mono\',monospace;font-size:13px;'
                    f'font-weight:600;color:{color};">{sc:.0f}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # --- Composition sectorielle ---
    st.markdown('<div class="sec-t" style="margin-top:36px;">Composition sectorielle</div>',
                unsafe_allow_html=True)

    sector_data: dict = {}
    for t in tickers_data:
        s = t.get("sector") or "Autres"
        sector_data.setdefault(s, []).append(t)
    sectors_sorted = sorted(sector_data.items(), key=lambda x: len(x[1]), reverse=True)

    shcols = st.columns([2.0, 0.6, 0.9, 2.0, 1.1, 1.2])
    for shc, h in zip(shcols, ["Secteur", "N", "Score moy.", "Top societe", "EV/EBITDA med.", ""]):
        with shc:
            st.markdown(
                f'<div style="font-size:10px;font-weight:600;color:#777;letter-spacing:1px;'
                f'text-transform:uppercase;padding-bottom:8px;border-bottom:1px solid #f0f0f0;">{h}</div>',
                unsafe_allow_html=True,
            )

    for idx_s, (sec_name, sec_list) in enumerate(sectors_sorted):
        avg_sc = sum((t.get("score_global") or 0) for t in sec_list) / len(sec_list)
        top_t  = max(sec_list, key=lambda x: x.get("score_global") or 0)
        evs    = [t.get("ev_ebitda") for t in sec_list if t.get("ev_ebitda") is not None]
        ev_str = f"{_med(evs):.1f}x" if evs else "—"
        sc_col = "#1a7a52" if avg_sc >= 60 else ("#b8922a" if avg_sc >= 40 else "#c0392b")

        sccols = st.columns([2.0, 0.6, 0.9, 2.0, 1.1, 1.2])
        with sccols[0]:
            st.markdown(f'<div style="padding:7px 0;font-size:13px;color:#333;">{_e(sec_name)}</div>',
                        unsafe_allow_html=True)
        with sccols[1]:
            st.markdown(
                f'<div style="padding:7px 0;font-family:\'DM Mono\',monospace;font-size:12px;color:#777;">'
                f'{len(sec_list)}</div>', unsafe_allow_html=True)
        with sccols[2]:
            st.markdown(
                f'<div style="padding:7px 0;font-family:\'DM Mono\',monospace;font-size:12px;'
                f'font-weight:600;color:{sc_col};">{avg_sc:.0f}</div>', unsafe_allow_html=True)
        with sccols[3]:
            st.markdown(
                f'<div style="padding:7px 0;font-size:12px;color:#555;">'
                f'{_e((top_t.get("company") or "")[:24])}</div>', unsafe_allow_html=True)
        with sccols[4]:
            st.markdown(
                f'<div style="padding:7px 0;font-family:\'DM Mono\',monospace;font-size:12px;color:#777;">'
                f'{ev_str}</div>', unsafe_allow_html=True)
        with sccols[5]:
            if st.button("Analyser", key=f"sec_ana_{idx_s}_{sec_name[:8]}",
                         use_container_width=True):
                sec_sorted = sorted(sec_list, key=lambda x: x.get("score_global") or 0, reverse=True)
                _sec_out_dir = Path(__file__).parent / "outputs" / "generated"
                _sec_out_dir.mkdir(exist_ok=True)
                _sec_slug = sec_name.lower().replace(" ", "_").replace(".", "")
                _sec_display = f"{sec_name} — {display_name}"
                # Generation screening Excel sectoriel
                sec_xlsx_bytes = None
                try:
                    from outputs.screening_writer import ScreeningWriter
                    _tpl = Path(__file__).parent / "assets" / "FinSight_IA_Screening_CAC40_v3.xlsx"
                    _sec_xlsx_path = str(_sec_out_dir / f"screening_{_sec_slug}.xlsx")
                    ScreeningWriter.generate(sec_sorted, _sec_display, _sec_xlsx_path,
                                             template_path=str(_tpl) if _tpl.exists() else None)
                    sec_xlsx_bytes = open(_sec_xlsx_path, "rb").read()
                except Exception as _ex0:
                    log.warning(f"[app] sector XLSX error: {_ex0}")
                # Generation rapport PDF sectoriel
                sec_pdf_bytes = None
                try:
                    import importlib, outputs.sector_pdf_writer as _spw
                    importlib.reload(_spw)
                    generate_sector_report = _spw.generate_sector_report
                    _sec_path = str(_sec_out_dir / f"sector_{_sec_slug}.pdf")
                    generate_sector_report(
                        sector_name=sec_name,
                        tickers_data=sec_sorted,
                        output_path=_sec_path,
                        universe=results.get("display_name", display_name),
                    )
                    sec_pdf_bytes = open(_sec_path, "rb").read()
                except Exception as _ex:
                    log.warning(f"[app] sector PDF error: {_ex}")
                # Generation pitchbook PPTX sectoriel
                sec_pptx_bytes = None
                try:
                    import outputs.sectoral_pptx_writer as _sppw
                    sec_pptx_bytes = _sppw.SectoralPPTXWriter.generate(
                        tickers_data=sec_sorted,
                        sector_name=sec_name,
                        universe=results.get("display_name", display_name),
                    )
                except Exception as _ex2:
                    log.warning(f"[app] sector PPTX error: {_ex2}")
                st.session_state.screening_parent  = results
                st.session_state.screening_results = {
                    "universe":     f"{sec_name}|{results.get('universe', '')}",
                    "display_name": _sec_display,
                    "tickers_data": sec_sorted,
                    "excel_bytes":  sec_xlsx_bytes,
                    "pdf_bytes":    sec_pdf_bytes,
                    "pptx_bytes":   sec_pptx_bytes,
                    "elapsed_ms":   0,
                }
                st.rerun()

    # --- Footer ---
    st.markdown(
        f'<div class="page-footer">'
        f'<span>FINSIGHT SCREENING · v1.0</span>'
        f'<span>Donnees au {today}</span>'
        f'<span>© {date.today().year} — Outil d\'aide a la decision uniquement</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Constructeur de la section Raisonnement IA (fidèle au wireframe)
# ---------------------------------------------------------------------------

def _build_ia_html(snapshot, ratios, synthesis, qa_python, qa_haiku, devil, sentiment) -> str:
    """
    Construit le HTML de la section Raisonnement IA à partir des données.
    Utilise uniquement du texte interprété — aucun JSON brut visible.
    """
    ci     = snapshot.company_info
    mkt    = snapshot.market
    latest = ratios.latest_year if ratios else None
    yr     = ratios.years.get(latest) if ratios and latest else None

    def _p(v): return f"{v*100:.1f}%" if v is not None else "N/A"
    def _x(v): return f"{v:.2f}×"    if v is not None else "N/A"
    def _n(v): return f"{v:.2f}"     if v is not None else "N/A"
    def _hl(t): return f'<span class="ia-hl">{_e(str(t))}</span>'
    def _good(t): return f'<span class="ia-good">{_e(str(t))}</span>'
    def _risk(t): return f'<span class="ia-risk">{_e(str(t))}</span>'

    blocks = []

    # ---- Bloc 0 : Synthèse narrative ----
    if synthesis and synthesis.summary:
        text = _e(synthesis.summary)
        if synthesis.strengths:
            bullets = "".join(
                f"<br>{_good('✓')} {_e(s)}" for s in synthesis.strengths[:3]
            )
            text += bullets
        if synthesis.valuation_comment:
            text += f"<br><br>{_e(synthesis.valuation_comment)}"
        blocks.append(("Thèse d'investissement", text))

    # ---- Bloc 1 : Valorisation ----
    if yr and synthesis:
        pe_comment = ""
        if yr.pe_ratio is not None:
            if yr.pe_ratio < 15:
                pe_comment = "en dessous des niveaux historiques sectoriels, suggérant une décote potentielle"
            elif yr.pe_ratio < 25:
                pe_comment = "dans la norme sectorielle, reflétant une valorisation équilibrée"
            else:
                pe_comment = "au-dessus de la médiane sectorielle, intégrant des attentes de croissance élevées"

        ev_comment = ""
        if yr.ev_ebitda is not None:
            if yr.ev_ebitda < 8:
                ev_comment = "attractif par rapport aux comparables"
            elif yr.ev_ebitda < 15:
                ev_comment = "cohérent avec les niveaux sectoriels"
            else:
                ev_comment = "élevé, justifié par la qualité des actifs et le pricing power"

        text = (
            f"Le P/E de {_hl(_x(yr.pe_ratio))} est {_e(pe_comment)}. "
            f"L'EV/EBITDA de {_hl(_x(yr.ev_ebitda))} est {_e(ev_comment)}. "
        )
        if mkt.share_price and synthesis.target_base:
            upside = (synthesis.target_base - mkt.share_price) / mkt.share_price * 100
            sign = "hausse" if upside > 0 else "baisse"
            text += (
                f"Le cours cible base case de {_hl(f'{synthesis.target_base:.0f} {ci.currency}')} "
                f"représente un potentiel de {_hl(f'{abs(upside):.1f}%')} de {_e(sign)} "
                f"par rapport au cours actuel de {_e(f'{mkt.share_price:.0f} {ci.currency}')}."
            )

        formula_block = ""
        if yr.pe_ratio and yr.net_income and yr.market_cap:
            formula_block = (
                f'<div class="formula-block">'
                f'<div class="formula-lbl">P/E implicite</div>'
                f'<div class="formula">P/E = Market Cap / Net Income = '
                f'{yr.market_cap:,.0f}M / {yr.net_income:,.0f}M = {_x(yr.pe_ratio)}</div>'
                f'</div>'
            )

        blocks.append(("Lecture des ratios de valorisation", text + formula_block))

    # ---- Bloc 2 : Fondamentaux opérationnels ----
    if yr:
        gm_qual = _good(_p(yr.gross_margin)) if (yr.gross_margin or 0) > 0.3 else _hl(_p(yr.gross_margin))
        em_qual = _good(_p(yr.ebitda_margin)) if (yr.ebitda_margin or 0) > 0.15 else _hl(_p(yr.ebitda_margin))
        roe_qual = _good(_p(yr.roe)) if (yr.roe or 0) > 0.12 else _risk(_p(yr.roe))

        lev_comment = ""
        if yr.net_debt_ebitda is not None:
            if yr.net_debt_ebitda < 1.5:
                lev_comment = "très confortable"
            elif yr.net_debt_ebitda < 3:
                lev_comment = "modéré"
            elif yr.net_debt_ebitda < 5:
                lev_comment = "élevé — surveillance requise"
            else:
                lev_comment = "critique — risque de refinancement"

        fcf_comment = ""
        if yr.fcf_yield is not None:
            if yr.fcf_yield > 0.05:
                fcf_comment = f"attractif à {_good(_p(yr.fcf_yield))}"
            elif yr.fcf_yield > 0:
                fcf_comment = f"positif à {_hl(_p(yr.fcf_yield))}"
            else:
                fcf_comment = f"{_risk(_p(yr.fcf_yield))} — génération de cash sous pression"

        text = (
            f"La marge brute de {gm_qual} et la marge EBITDA de {em_qual} "
            f"témoignent de la capacité de l'entreprise à préserver sa profitabilité. "
            f"Le ROE de {roe_qual} reflète l'efficacité d'allocation du capital. "
            f"L'endettement net / EBITDA de {_hl(_x(yr.net_debt_ebitda))} est {_e(lev_comment)}. "
            f"Le FCF yield est {fcf_comment}."
        )

        formula = ""
        if yr.gross_profit and yr.ebitda and snapshot.years.get(latest) and snapshot.years[latest].revenue:
            rev = snapshot.years[latest].revenue
            formula = (
                f'<div class="formula-block">'
                f'<div class="formula-lbl">Profitabilité ({latest})</div>'
                f'<div class="formula">'
                f'Marge Brute = {yr.gross_profit:,.0f}M / {rev:,.0f}M = {_p(yr.gross_margin)}<br>'
                f'EBITDA = {yr.ebitda:,.0f}M → Marge EBITDA = {_p(yr.ebitda_margin)}'
                f'</div></div>'
            )
        blocks.append(("Qualité des fondamentaux opérationnels", text + formula))

    # ---- Bloc 3 : Hypothèses valorisation / WACC ----
    if mkt and (mkt.wacc or mkt.beta_levered or mkt.risk_free_rate):
        wacc_str = _p(mkt.wacc) if mkt.wacc else "~8–10% (estimé)"
        beta_str = f"{mkt.beta_levered:.2f}" if mkt.beta_levered else "N/A"
        tgr_str  = _p(mkt.terminal_growth) if mkt.terminal_growth else "~2.5% (prudence)"

        text = (
            f"Le WACC retenu de {_hl(wacc_str)} intègre un bêta de {_hl(beta_str)}, "
            f"reflétant le profil de risque spécifique du secteur. "
            f"Le taux de croissance terminal de {_hl(tgr_str)} est ancré sur la croissance "
            f"structurelle long-terme du secteur, avec une décote de prudence pour la maturité "
            f"des marchés développés."
        )
        if mkt.beta_levered and mkt.risk_free_rate and mkt.erp:
            ke = mkt.risk_free_rate + mkt.beta_levered * mkt.erp
            formula = (
                f'<div class="formula-block">'
                f'<div class="formula-lbl">WACC — CAPM</div>'
                f'<div class="formula">'
                f'Ke = Rf + β × (Rm − Rf) = {_p(mkt.risk_free_rate)} + {beta_str} × {_p(mkt.erp)} = {_p(ke)}<br>'
                f'WACC = {wacc_str}'
                f'</div></div>'
            )
            text += formula
        blocks.append(("Hypothèses DCF &amp; Taux d'actualisation", text))

    # ---- Bloc 4 : Risques & Devil's Advocate ----
    risk_text = ""
    if synthesis and synthesis.risks:
        risk_items = "".join(
            f"<br>{_risk('Risque')} : {_e(r)}"
            for r in synthesis.risks[:3]
        )
        risk_text = risk_items

    if devil:
        delta = devil.conviction_delta
        solidity = ("thèse fragile — arguments contra solides" if delta < -0.2
                    else "thèse robuste" if delta > 0.2
                    else "thèse modérément solide")
        rec_orig = getattr(synthesis, "recommendation", "N/A") if synthesis else "N/A"
        alt_map  = {"BUY": "HOLD/SELL", "HOLD": "SELL", "SELL": "BUY"}
        counter_reco = alt_map.get(rec_orig, "HOLD")
        risk_text += (
            f"<br><br>{_risk('Avocat du Diable')} ({rec_orig} → {counter_reco}, "
            f"delta conviction {delta:+.2f} — {_e(solidity)}) : "
            f"{_e(devil.counter_thesis[:280] if devil.counter_thesis else '')}"
        )
        for risk in (getattr(devil, "counter_risks", []) or [])[:2]:
            risk_text += f"<br><span class=\"ia-hl\">? Risque sous-estimé</span> : {_e(risk)}"

    if synthesis and synthesis.invalidation_conditions:
        risk_text += (
            f"<br><br>{_risk('Conditions d&apos;invalidation')} : "
            f"{_e(synthesis.invalidation_conditions[:250])}"
        )

    if risk_text:
        blocks.append(("Risques &amp; Avocat du Diable", risk_text.lstrip("<br>")))

    # ---- Bloc 5 : Sentiment ----
    if sentiment:
        lbl_map = {"POSITIVE": ("Positif", "ia-good"), "NEGATIVE": ("Négatif", "ia-risk"), "NEUTRAL": ("Neutre", "ia-hl")}
        lbl_fr, lbl_cls = lbl_map.get(sentiment.label, ("Neutre", "ia-hl"))
        engine = "FinBERT" if (sentiment.meta or {}).get("engine") == "finbert" else "VADER"
        sent_text = (
            f"Analyse {engine} de {sentiment.articles_analyzed} article(s) : "
            f"sentiment <span class=\"{lbl_cls}\">{lbl_fr}</span> "
            f"(score {int(sentiment.score_normalized*100)}%, confiance {int(sentiment.confidence*100)}%). "
        )
        if sentiment.breakdown:
            pos = sentiment.breakdown.get("avg_positive", 0) or 0
            neg = sentiment.breakdown.get("avg_negative", 0) or 0
            sent_text += f"Distribution — Positif : {int(pos*100)}%, Négatif : {int(neg*100)}%."
        if sentiment.samples:
            s = sentiment.samples[0]
            lbl_s = s.get("label", "")
            txt_s = (s.get("headline") or s.get("text") or "")[:120]
            sent_text += f"<br><br>Exemple : <em>{_e(txt_s)}</em> [{lbl_s}]"
        blocks.append(("Sentiment de marché", sent_text))

    # ---- Bloc 6 : QA ----
    if qa_python or qa_haiku:
        qa_text = ""
        if qa_python:
            status = _good("VALIDÉ") if qa_python.passed else _risk("ÉCHEC")
            qa_text += f"Score QA quantitatif : {status} ({qa_python.qa_score:.0%}). "
            for fl in qa_python.flags[:4]:
                sym   = "⚠" if fl.level == "WARNING" else ("✗" if fl.level == "ERROR" else "✓")
                color = "ia-risk" if fl.level == "ERROR" else ("ia-hl" if fl.level == "WARNING" else "ia-good")
                qa_text += f'<br><span class="{color}">{sym}</span> {_e(fl.message)}'
        if qa_haiku:
            ib = _good("IB standard ✓") if qa_haiku.ib_standard else _risk("standard IB à revoir")
            qa_text += f"<br><br>Lecture rédactionnelle : {ib}, lisibilité {_hl(f'{qa_haiku.readability_score:.0%}')}. "
            if qa_haiku.tone_assessment:
                qa_text += _e(qa_haiku.tone_assessment)
        blocks.append(("Validation QA", qa_text.lstrip("<br>")))

    # ---- Assemblage HTML ----
    model = ""
    if synthesis:
        model = synthesis.meta.get("model", "FinSight IA")

    html_parts = [
        f'<div class="ia-section">',
        f'<div class="ia-bar">',
        f'<div class="ia-bar-t">Raisonnement IA — Interprétation &amp; Hypothèses</div>',
        f'<div class="ia-model">{_e(model)}</div>',
        f'</div>',
        f'<div class="ia-body">',
    ]
    for title, content in blocks:
        html_parts.append(
            f'<div class="ia-block">'
            f'<div class="ia-block-t">{title}</div>'
            f'<div class="ia-text">{content}</div>'
            f'</div>'
        )
    html_parts += ["</div>", "</div>"]
    return "\n".join(html_parts)


# ---------------------------------------------------------------------------
# Page RESULTS
# ---------------------------------------------------------------------------

def render_results(results: dict) -> None:
    # Back to screening button
    if st.session_state.get("from_screening") and st.session_state.get("screening_results"):
        if st.button("← Retour au screening", type="primary"):
            st.session_state.from_screening = False
            st.session_state.stage = "screening_results"
            st.rerun()
        st.markdown('<div style="margin-bottom:12px;"></div>', unsafe_allow_html=True)

    if results.get("error"):
        st.error(results["error"])
        if st.button("← Retour"):
            st.session_state.stage = "home"
            st.rerun()
        return

    if results.get("blocked"):
        st.warning(
            "Analyse partielle — confiance LLM insuffisante. "
            "Les données financières et livrables restent disponibles."
        )

    snapshot  = results["snapshot"]
    ratios    = results["ratios"]
    synthesis = results["synthesis"]
    sentiment = results["sentiment"]
    qa_python = results["qa_python"]
    qa_haiku  = results["qa_haiku"]
    devil     = results["devil"]

    ci     = snapshot.company_info
    mkt    = snapshot.market
    latest = ratios.latest_year if ratios else None
    yr     = ratios.years.get(latest) if ratios and latest else None

    def _p(v): return f"{v*100:.1f}%" if v is not None else "N/A"
    def _x(v): return f"{v:.2f}×"    if v is not None else "N/A"
    def _n(v): return f"{v:.2f}"     if v is not None else "N/A"

    today   = date.today().strftime("%d.%m.%Y")
    elapsed = results.get("elapsed_ms", 0)

    # ------------------------------------------------------------------
    # En-tête
    # ------------------------------------------------------------------
    st.markdown(f'<div class="rc">{_e(ci.company_name)}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="rm">'
        f'{_e(ci.ticker)} · {_e((ci.sector or "—").upper())} · '
        f'{_e(ci.currency)} · {today} · '
        f'<span style="color:#1a7a52">{elapsed/1000:.1f}s</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # Verdict row
    # ------------------------------------------------------------------
    if synthesis:
        reco    = synthesis.recommendation
        reco_fr = {"BUY": "ACHETER", "SELL": "VENDRE", "HOLD": "CONSERVER"}.get(reco, reco)
        reco_cls = {"BUY": "v-buy", "SELL": "v-sell"}.get(reco, "v-hold")
        conv    = int(synthesis.conviction * 100)
        price   = f"{ci.currency} {mkt.share_price:,.0f}" if mkt.share_price else "N/A"
        tgt     = f"{ci.currency} {synthesis.target_base:,.0f}" if synthesis.target_base else "N/A"

        st.markdown(f"""
        <div class="verdict-row">
          <div>
            <div class="v-lbl">Recommandation</div>
            <div class="{reco_cls}">{reco_fr}</div>
          </div>
          <div class="v-div"></div>
          <div>
            <div class="v-lbl">Conviction IA</div>
            <div class="v-num">{conv}%</div>
            <div class="v-bar"><div style="width:{conv}%;height:100%;background:#111;border-radius:1px"></div></div>
          </div>
          <div class="v-div"></div>
          <div>
            <div class="v-lbl">Cours actuel</div>
            <div class="v-num">{_e(price)}</div>
          </div>
          <div class="v-div"></div>
          <div>
            <div class="v-lbl">Cible base case</div>
            <div class="v-tgt">{_e(tgt)}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Synthèse narrative
    # ------------------------------------------------------------------
    if synthesis and synthesis.summary:
        st.markdown('<div class="sec-t">Synthèse de l\'analyse</div>', unsafe_allow_html=True)
        summary_html = (
            f'<div style="font-size:14px;line-height:1.85;color:#333;padding:16px 0 8px;">'
            f'{_e(synthesis.summary)}'
            f'</div>'
        )
        if synthesis.strengths:
            bullets = "".join(
                f'<li style="margin-bottom:6px;">{_e(s)}</li>'
                for s in synthesis.strengths[:3]
            )
            summary_html += (
                f'<ul style="font-size:13px;color:#444;line-height:1.7;'
                f'padding-left:20px;margin-bottom:24px;">{bullets}</ul>'
            )
        else:
            summary_html += '<div style="margin-bottom:24px;"></div>'
        st.markdown(summary_html, unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Sentiment de marché
    # ------------------------------------------------------------------
    if sentiment:
        lbl_map   = {"POSITIVE": ("Positif", "#1a7a52"), "NEGATIVE": ("Négatif", "#c0392b"), "NEUTRAL": ("Neutre", "#b8922a")}
        lbl_fr, lbl_col = lbl_map.get(sentiment.label, ("Neutre", "#b8922a"))
        score_pct = int(sentiment.score_normalized * 100)
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:28px;padding:12px 0 28px;'
            f'border-bottom:1px solid #f5f5f5;margin-bottom:28px;">'
            f'<div style="font-size:11px;font-weight:600;letter-spacing:1px;'
            f'text-transform:uppercase;color:#888;">Sentiment de marché</div>'
            f'<div style="font-size:16px;font-weight:700;color:{lbl_col};">{_e(lbl_fr)}</div>'
            f'<div style="font-size:13px;color:#666;">Score : <b>{score_pct}%</b> · '
            f'Confiance : <b>{int(sentiment.confidence*100)}%</b> · '
            f'{sentiment.articles_analyzed} article(s) analysé(s)</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ------------------------------------------------------------------
    # Contexte marché
    # ------------------------------------------------------------------
    st.markdown('<div class="sec-t">Contexte de marché</div>', unsafe_allow_html=True)
    mkt_data = fetch_market_context()
    if mkt_data:
        cells = ""
        for m in mkt_data:
            val_s = f"{m['value']:,.2f}" if m.get("value") else "—"
            if m.get("chg") is not None:
                arrow = "▲" if m["chg"] >= 0 else "▼"
                cls   = "mkt-up" if m["chg"] >= 0 else "mkt-dn"
                chg_h = f'<div class="{cls}">{arrow} {m["chg"]:+.2f}%</div>'
            else:
                chg_h = '<div class="mkt-na">—</div>'
            cells += (
                f'<div class="mkt-cell">'
                f'<div class="mkt-n">{_e(m["name"])}</div>'
                f'<div class="mkt-v">{val_s}</div>'
                f'{chg_h}</div>'
            )
        st.markdown(f'<div class="mkt-strip">{cells}</div>', unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Ratios financiers
    # ------------------------------------------------------------------
    st.markdown(
        f'<div class="sec-t">Ratios financiers &amp; Benchmark sectoriel — {_e(latest)}</div>',
        unsafe_allow_html=True,
    )

    if yr is None:
        st.markdown(
            '<div style="padding:20px;color:#aaa;font-size:12px;border:1px solid #f0f0f0;margin-bottom:44px;">'
            'Ratios non disponibles — couverture données insuffisante.</div>',
            unsafe_allow_html=True,
        )
    if yr:
        def _rc(name, val, sub="", bar_pct=50, bar_cls="bn"):
            return (
                f'<div class="ratio-cell">'
                f'<div class="r-name">{_e(name)}</div>'
                f'<div class="r-val">{_e(val)}</div>'
                f'<div class="r-sub">{_e(sub)}</div>'
                f'<div class="r-bar"><div class="{bar_cls}" style="width:{bar_pct}%"></div></div>'
                f'</div>'
            )

        def _cls_margin(v):
            if v is None: return "bn", 50
            if v > 0.20:  return "bg", min(int(v * 200), 100)
            if v > 0:     return "bn", max(int(v * 200), 10)
            return "br", 5

        def _cls_roe(v):
            if v is None: return "bn", 50
            if v > 0.15:  return "bg", min(int(v * 300), 100)
            if v > 0:     return "bn", max(int(v * 300), 10)
            return "br", 5

        gm_c, gm_w = _cls_margin(yr.gross_margin)
        em_c, em_w = _cls_margin(yr.ebitda_margin)
        nm_c, nm_w = _cls_margin(yr.net_margin)
        roe_c, roe_w = _cls_roe(yr.roe)

        lev = yr.net_debt_ebitda
        lev_c = "bg" if lev is not None and lev < 2 else ("bn" if lev is not None and lev < 4 else "br")
        lev_w = max(10, min(95, int(100 - (lev or 0) * 14))) if lev is not None else 50

        pe = yr.pe_ratio
        pe_c = "bg" if pe is not None and 0 < pe < 18 else ("bn" if pe is not None and pe < 28 else "br")
        pe_w = max(10, min(90, int(100 - (pe or 25) * 1.6))) if pe is not None and pe > 0 else 50

        rg = yr.revenue_growth
        rg_c = "bg" if rg is not None and rg > 0.03 else ("bn" if rg is not None and rg >= 0 else "br")
        rg_w = min(100, max(5, int((rg or 0) * 600 + 50))) if rg is not None else 50

        cells = "".join([
            _rc("P/E Ratio",         _x(yr.pe_ratio),      f"Valeur actuelle · {'Favorable' if pe_c=='bg' else 'Neutre'}", pe_w,  pe_c),
            _rc("EV / EBITDA",       _x(yr.ev_ebitda),     "Multiple entreprise", 65, "bn"),
            _rc("Marge EBITDA",      _p(yr.ebitda_margin), f"Secteur ref · {'Fort' if em_c=='bg' else 'Neutre'}", em_w, em_c),
            _rc("ROE",               _p(yr.roe),           f"Return on Equity · {'Solide' if roe_c=='bg' else 'Neutre'}", roe_w, roe_c),
            _rc("Marge Nette",       _p(yr.net_margin),    "Net Income / Revenue", nm_w, nm_c),
            _rc("ROIC",              _p(yr.roic),          "Return on Invested Capital", 60, "bn"),
            _rc("Dette N./EBITDA",   _x(yr.net_debt_ebitda), f"Levier · {'Sain' if lev_c=='bg' else 'Élevé' if lev_c=='br' else 'Modéré'}", lev_w, lev_c),
            _rc("Free Cash Flow",    _p(yr.fcf_yield),     f"FCF Yield · {'Attractif' if (yr.fcf_yield or 0)>0.04 else 'Neutre'}", min(100, int((yr.fcf_yield or 0)*1000+40)), "bg" if (yr.fcf_yield or 0)>0.04 else "bn"),
            _rc("Marge Brute",       _p(yr.gross_margin),  "Gross Profit / Revenue", gm_w, gm_c),
            _rc("Current Ratio",     _n(yr.current_ratio), ">1.0 Sain · >2.0 Fort", min(100, int((yr.current_ratio or 0)*35)), "bg" if (yr.current_ratio or 0)>1.5 else "bn"),
            _rc("Croissance CA",     _p(yr.revenue_growth), "YoY · vs exercice précédent", rg_w, rg_c),
            _rc("Altman Z-Score",    _n(yr.altman_z),
                f">2.99 Sain · <1.81 Détresse",
                min(100, int((yr.altman_z or 0) * 13)) if yr.altman_z else 50,
                "bg" if yr.altman_z and yr.altman_z > 2.99 else ("bn" if yr.altman_z and yr.altman_z > 1.81 else "br")),
        ])
        st.markdown(f'<div class="ratios-grid">{cells}</div>', unsafe_allow_html=True)

        # Beneish
        if yr.beneish_m is not None:
            col  = "#c0392b" if yr.beneish_m > -2.22 else "#1a7a52"
            flag = "RISQUE MANIPULATION COMPTABLE" if yr.beneish_m > -2.22 else "Pas de signal de manipulation"
            st.markdown(
                f'<div style="font-size:11px;padding:8px 12px;border:1px solid {col}30;'
                f'color:{col};background:{col}08;margin-bottom:40px;">'
                f'Beneish M-Score : {yr.beneish_m:.3f} — {flag}</div>',
                unsafe_allow_html=True,
            )

    # ------------------------------------------------------------------
    # Scénarios
    # ------------------------------------------------------------------
    st.markdown('<div class="sec-t">Scénarios de valorisation — Distribution triangulaire</div>', unsafe_allow_html=True)

    if synthesis:
        cur  = mkt.share_price or 0
        tb   = synthesis.target_bull or 0
        tba  = synthesis.target_base or 0
        tbr  = synthesis.target_bear or 0

        def _up(t):
            if cur and t:
                u = (t - cur) / cur * 100
                return f"{'▲' if u>=0 else '▼'} {u:+.1f}%"
            return ""

        scen = f"""
        <div class="scen-grid">
          <div class="scen-cell">
            <div class="scen-tag">Bull Case</div>
            <div class="sp-bull">{_e(ci.currency)} {tb:,.0f}</div>
            <div class="scen-prob">{_e(_up(tb))}</div>
            <div class="scen-bar"><div style="width:30%;height:100%;background:#2d7a5a;border-radius:1px"></div></div>
          </div>
          <div class="scen-cell">
            <div class="scen-tag">Base Case</div>
            <div class="sp-base">{_e(ci.currency)} {tba:,.0f}</div>
            <div class="scen-prob">{_e(_up(tba))}</div>
            <div class="scen-bar"><div style="width:55%;height:100%;background:#8a7040;border-radius:1px"></div></div>
          </div>
          <div class="scen-cell">
            <div class="scen-tag">Bear Case</div>
            <div class="sp-bear">{_e(ci.currency)} {tbr:,.0f}</div>
            <div class="scen-prob">{_e(_up(tbr))}</div>
            <div class="scen-bar"><div style="width:15%;height:100%;background:#a04040;border-radius:1px"></div></div>
          </div>
        </div>
        """
        st.markdown(scen, unsafe_allow_html=True)

        if synthesis.valuation_comment:
            st.markdown(
                f'<div style="font-size:13px;color:#555;line-height:1.7;padding:12px 0 28px;">'
                f'{_e(synthesis.valuation_comment)}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ------------------------------------------------------------------
    # IA Section — toggle manuel (evite l'artefact "board_" de st.expander)
    # ------------------------------------------------------------------
    st.markdown('<div class="sec-t">Raisonnement IA</div>', unsafe_allow_html=True)

    if "ia_section_open" not in st.session_state:
        st.session_state["ia_section_open"] = False
    _ia_label = "Interprétation & Hypothèses ▲" if st.session_state["ia_section_open"] else "Interprétation & Hypothèses ▼"
    if st.button(_ia_label, key="btn_ia_toggle", use_container_width=True):
        st.session_state["ia_section_open"] = not st.session_state["ia_section_open"]
        st.rerun()
    if st.session_state["ia_section_open"]:
        ia_html = _build_ia_html(snapshot, ratios, synthesis, qa_python, qa_haiku, devil, sentiment)
        st.markdown(ia_html, unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------
    st.markdown(
        f'<div class="page-footer">'
        f'<span>FINSIGHT · v1.2</span>'
        f'<span>Données au {today}</span>'
        f'<span>© {date.today().year} — Outil d\'aide à la décision uniquement</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    st.markdown(
        '<div class="fs-nav">'
        '<div class="fs-logo">FinSight</div>'
        '<div class="fs-nav-r">Analyse Financière IA · V1.2</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    results = st.session_state.results
    render_sidebar(results)

    stage = st.session_state.stage

    if stage == "home":
        render_home()
    elif stage == "running":
        render_running()
    elif stage == "screening_running":
        render_screening_running()
    elif stage == "results" and results:
        try:
            render_results(results)
        except Exception as _render_err:
            import traceback as _tb
            st.error(f"Erreur affichage résultats : {_render_err}")
            st.code(_tb.format_exc(), language="text")
            st.markdown("**Livrables disponibles :**")
            for _lbl, _key, _fname, _mime in [
                ("Rapport PDF", "pdf_bytes", f"{results.get('ticker','report')}_report.pdf", "application/pdf"),
                ("Pitchbook", "pptx_bytes", f"{results.get('ticker','report')}_pitchbook.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
                ("Ratios Excel", "excel_bytes", f"{results.get('ticker','report')}_ratios.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ]:
                _b = results.get(_key)
                if _b:
                    st.download_button(_lbl, _b, file_name=_fname, mime=_mime)
    elif stage == "screening_results":
        scr = st.session_state.get("screening_results")
        if scr:
            render_screening_results(scr)
        else:
            st.session_state.stage = "home"
            st.rerun()
    else:
        st.session_state.stage = "home"
        st.rerun()


if __name__ == "__main__":
    main()
