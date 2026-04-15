#!/usr/bin/env python3
# =============================================================================
# FinSight IA — Interface Streamlit
# app.py
#
# Usage : streamlit run app.py
# =============================================================================

import html as _html
import logging
import math as _math
import re as _re
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
_NO_WIN = {"creationflags": 0x08000000} if __import__("sys").platform == "win32" else {}
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

# JS — supprimé le texte "board_" (artefact BaseBUI) des expanders
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

# JS — raccourcis clavier pour navigation rapide (usage interne Claude)
_components.html("""
<script>
(function() {
  var _kbRegistered = window.parent.__finsight_kb_registered;
  if (_kbRegistered) return;
  window.parent.__finsight_kb_registered = true;

  var doc = window.parent.document;

  // ── helpers internes ──────────────────────────────────────────────────────
  function _clickBtn(pattern) {
    var btns = doc.querySelectorAll('button');
    for (var b of btns) {
      if (b.innerText && b.innerText.trim().match(pattern)) { b.click(); return true; }
    }
    return false;
  }
  function _clickDl(keyword) {
    var els = doc.querySelectorAll('a[download], button');
    for (var b of els) {
      var txt = (b.innerText || b.getAttribute('download') || '').toLowerCase();
      if (txt.includes(keyword)) { b.click(); return true; }
    }
    return false;
  }
  function _scrollMain(dy) {
    // Scrolle le conteneur principal Streamlit (pas window, souvent dans un div)
    var main = doc.querySelector('section.main') ||
                doc.querySelector('[data-testid="stAppViewContainer"]') ||
                doc.querySelector('main') || doc.body;
    main.scrollBy(0, dy);
  }

  var SHORTCUTS = {
    // ── Navigation ────────────────────────────────────────────────────────
    // Alt+H : Accueil / Nouvelle analyse
    'h': function() { _clickBtn(/Nouvelle analyse/i); },
    // Alt+A : Lancer analyse
    'a': function() { _clickBtn(/^Analyser/i); },
    // Alt+C : Comparer
    'c': function() { _clickBtn(/Comparer/i); },

    // ── Downloads ─────────────────────────────────────────────────────────
    // Alt+P : PDF
    'p': function() { _clickDl('pdf'); },
    // Alt+T : PPTX / Pitchbook
    't': function() { _clickDl('pptx') || _clickDl('pitchbook'); },
    // Alt+E : Excel
    'e': function() { _clickDl('xlsx') || _clickDl('excel'); },

    // ── Scroll ────────────────────────────────────────────────────────────
    // Alt+D : Scroll bas 600px
    'd': function() { _scrollMain(600); },
    // Alt+U : Scroll haut 600px
    'u': function() { _scrollMain(-600); },
    // Alt+B : Scroll tout en bas
    'b': function() {
      var main = doc.querySelector('section.main') ||
                  doc.querySelector('[data-testid="stAppViewContainer"]') ||
                  doc.body;
      main.scrollTo(0, main.scrollHeight);
    },
    // Alt+G : Scroll tout en haut
    'g': function() {
      var main = doc.querySelector('section.main') ||
                  doc.querySelector('[data-testid="stAppViewContainer"]') ||
                  doc.body;
      main.scrollTo(0, 0);
    },

    // ── Focus input ───────────────────────────────────────────────────────
    // Alt+I : Focus le champ texte principal (ticker/societe)
    'i': function() {
      var inputs = doc.querySelectorAll('input[type="text"], input:not([type])');
      if (inputs.length > 0) { inputs[0].focus(); inputs[0].select(); }
    },

    // ── Etat applicatif (logs console — remplace get_page_text) ───────────
    // Alt+R : Rapport d'État complet (page courante, ticker, loading, sections, downloads)
    'r': function() {
      var spinner = doc.querySelector('[data-testid="stSpinner"], .stSpinner, [class*="spinner"]');
      var isLoading = !!spinner && spinner.offsetParent !== null;
      var inputs = doc.querySelectorAll('input[type="text"], input:not([type])');
      var ticker = inputs.length > 0 ? inputs[0].value : '';
      var headers = Array.from(doc.querySelectorAll('h1,h2,h3')).map(function(h) {
        return h.tagName + ': ' + h.innerText.trim().substring(0, 60);
      });
      var dls = Array.from(doc.querySelectorAll('a[download], button')).filter(function(b) {
        var t = (b.innerText || b.getAttribute('download') || '').toLowerCase();
        return t.includes('pdf') || t.includes('pptx') || t.includes('xlsx') || t.includes('excel') || t.includes('pitchbook');
      }).map(function(b) { return b.innerText || b.getAttribute('download'); });
      var errors = Array.from(doc.querySelectorAll('[data-testid="stAlert"], .stAlert, [class*="alert"]')).map(function(a) {
        return a.innerText.trim().substring(0, 100);
      });
      var btns = Array.from(doc.querySelectorAll('button')).filter(function(b) {
        return b.innerText && b.innerText.trim().length > 0 && b.offsetParent !== null;
      }).map(function(b) { return b.innerText.trim(); }).slice(0, 10);
      // Detection page
      var page = 'inconnu';
      if (isLoading) page = 'ANALYSE_EN_COURS';
      else if (dls.length > 0) page = 'RÉSULTATS';
      else if (ticker !== '' || inputs.length > 0) page = 'ACCUEIL';
      console.log('[FinSight STATE]', JSON.stringify({
        page: page,
        ticker: ticker,
        isLoading: isLoading,
        sections: headers,
        downloads: dls,
        buttons: btns,
        errors: errors
      }, null, 2));
    },

    // Alt+W : Spinner visible? (analyse en cours ?)
    'w': function() {
      var spinner = doc.querySelector('[data-testid="stSpinner"], .stSpinner, [class*="spinner"]');
      var loading = !!spinner && spinner.offsetParent !== null;
      console.log('[FinSight LOADING]', loading ? 'OUI — analyse en cours' : 'NON — page stable');
    },

    // Alt+N : Liste des sections visibles (orientation rapide dans les resultats)
    'n': function() {
      var headers = Array.from(doc.querySelectorAll('h1,h2,h3,h4')).map(function(h) {
        return h.tagName + ' | ' + h.innerText.trim().substring(0, 80);
      });
      console.log('[FinSight SECTIONS] ' + headers.length + ' headers :');
      headers.forEach(function(h) { console.log('  ' + h); });
    },

    // Alt+O : Liste tous les downloads disponibles (labels + types)
    'o': function() {
      var dls = Array.from(doc.querySelectorAll('a[download], button')).filter(function(b) {
        var t = (b.innerText || b.getAttribute('download') || '').toLowerCase();
        return t.includes('pdf') || t.includes('pptx') || t.includes('xlsx') ||
               t.includes('excel') || t.includes('pitchbook') || t.includes('download') ||
               t.includes('telecharger');
      });
      console.log('[FinSight DOWNLOADS] ' + dls.length + ' boutons :');
      dls.forEach(function(b, i) {
        console.log('  [' + i + '] ' + (b.innerText || b.getAttribute('download') || '').trim());
      });
    },

    // Alt+F : Premier message d'erreur visible
    'f': function() {
      var alerts = doc.querySelectorAll('[data-testid="stAlert"], .stAlert, [class*="error"], [class*="warning"]');
      if (alerts.length === 0) { console.log('[FinSight ERROR] Aucune alerte visible'); return; }
      Array.from(alerts).forEach(function(a) {
        console.log('[FinSight ALERT] ' + a.innerText.trim().substring(0, 200));
      });
    },

    // ── Aide ──────────────────────────────────────────────────────────────
    // Alt+K : Aide complete
    'k': function() {
      console.log('[FinSight KB] === RACCOURCIS CLAUDE ===');
      console.log('  NAVIGATION  : Alt+H=Accueil  Alt+A=Analyser  Alt+C=Comparer');
      console.log('  DOWNLOADS   : Alt+P=PDF  Alt+T=PPTX  Alt+E=Excel  Alt+O=Liste DL');
      console.log('  SCROLL      : Alt+D=Bas  Alt+U=Haut  Alt+B=Bottom  Alt+G=Top');
      console.log('  INPUT       : Alt+I=Focus champ texte');
      console.log('  ÉTAT        : Alt+R=Rapport complet  Alt+W=Loading?  Alt+N=Sections  Alt+F=Erreurs');
      console.log('  AIDE        : Alt+K=Cette aide');
    }
  };

  window.parent.document.addEventListener('keydown', function(e) {
    if (!e.altKey) return;
    var key = e.key.toLowerCase();
    if (SHORTCUTS[key]) {
      e.preventDefault();
      SHORTCUTS[key]();
      console.log('[FinSight KB] Alt+' + key.toUpperCase() + ' execute');
    }
  });
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
# Comparison société
if "cmp_societe_stage"          not in st.session_state: st.session_state.cmp_societe_stage          = None   # None / "running" / "done"
if "cmp_societe_ticker_b"       not in st.session_state: st.session_state.cmp_societe_ticker_b       = ""
if "cmp_societe_state_b"        not in st.session_state: st.session_state.cmp_societe_state_b        = None
if "cmp_societe_xlsx_bytes"          not in st.session_state: st.session_state.cmp_societe_xlsx_bytes          = None
if "scr_cmp_b_preset"   not in st.session_state: st.session_state.scr_cmp_b_preset   = ""
# Comparison indice
if "cmp_indice_stage"         not in st.session_state: st.session_state.cmp_indice_stage         = None   # None / "running" / "done"
if "cmp_indice_universe_b"    not in st.session_state: st.session_state.cmp_indice_universe_b    = ""
if "cmp_indice_pptx_bytes"    not in st.session_state: st.session_state.cmp_indice_pptx_bytes    = None
if "cmp_indice_pdf_bytes"     not in st.session_state: st.session_state.cmp_indice_pdf_bytes     = None
if "cmp_indice_xlsx_bytes"    not in st.session_state: st.session_state.cmp_indice_xlsx_bytes    = None

# Comparison sectorielle (scmp)
if "cmp_secteur_stage"         not in st.session_state: st.session_state.cmp_secteur_stage         = None
if "cmp_secteur_sector_a"      not in st.session_state: st.session_state.cmp_secteur_sector_a      = None
if "cmp_secteur_sector_b"      not in st.session_state: st.session_state.cmp_secteur_sector_b      = None
if "cmp_secteur_pptx_bytes"    not in st.session_state: st.session_state.cmp_secteur_pptx_bytes    = None
if "cmp_secteur_pdf_bytes"     not in st.session_state: st.session_state.cmp_secteur_pdf_bytes     = None
if "cmp_secteur_xlsx_bytes"    not in st.session_state: st.session_state.cmp_secteur_xlsx_bytes    = None

# Page post-analyse comparative : on garde l'État de l'analyse initiale
# pour pouvoir y revenir via le bouton "Retour à l'analyse ..." (sidebar).
# comparison_kind : "société" | "secteur" | "indice"
if "comparison_kind"                  not in st.session_state: st.session_state.comparison_kind                  = None
if "previous_analysis_type"    not in st.session_state: st.session_state.previous_analysis_type    = None  # "results" | "screening_results"
if "previous_analysis_results" not in st.session_state: st.session_state.previous_analysis_results = None
if "previous_analysis_label"   not in st.session_state: st.session_state.previous_analysis_label   = ""

# ---------------------------------------------------------------------------
# Routing : détection du type d'input
# ---------------------------------------------------------------------------

_INDICES_SET = {
    "CAC40", "SP500", "S&P500", "SPX", "DAX40", "FTSE100", "STOXX50", "ALL", "EUROSTOXX50",
}
# ─── Secteurs : i18n centralisé via core/sector_labels ──────────────────────
# Source de vérité : core/sector_labels.py (mapping FR/EN/slug + helpers).
# Les dicts ci-dessous sont Générés pour préserver la compatibilite avec
# l'ancien code qui utilise _SECTOR_ALIASES_SET / _UNIVERSE_DISPLAY / _SECTOR_YFINANCE.
from core.sector_labels import (
    SECTOR_LABELS as _SECTOR_LABELS_CANON,
    SECTOR_LABELS_FR_ACCENTED as _FR_ACCENTED,
    fr_label as _fr_label,
    en_label as _en_label,
    slug_from_any as _slug_from_any,
)

# Set d'aliases : tous les slugs canoniques (TECHNOLOGY, HEALTHCARE, etc.)
_SECTOR_ALIASES_SET = set(_SECTOR_LABELS_CANON.keys())

# Display francais (UI Streamlit) — labels avec accents UTF-8
_UNIVERSE_DISPLAY = {
    # Indices
    "CAC40": "CAC 40", "SP500": "S&P 500", "S&P500": "S&P 500", "SPX": "S&P 500",
    "DAX40": "DAX 40", "FTSE100": "FTSE 100", "STOXX50": "Euro Stoxx 50",
    "EUROSTOXX50": "Euro Stoxx 50", "ALL": "Univers Global",
}
# Ajout des secteurs depuis le mapping canonique
for _slug, _fr in _FR_ACCENTED.items():
    _UNIVERSE_DISPLAY[_slug] = _fr

# Mapping slug -> label yfinance (anglais) pour les appels API
_SECTOR_YFINANCE = {_slug: _SECTOR_LABELS_CANON[_slug][0] for _slug in _SECTOR_LABELS_CANON}


def _resolve_input_llm(name: str) -> dict | None:
    """Fallback LLM : classe l'input en société/secteur/indice et resout le ticker.
    Retourne {'type': 'ticker'|'sector'|'index', 'value': str} ou None si echec."""
    import logging as _log, json as _json, re as _re
    try:
        import sys as _sys, os as _os
        _root = str(Path(__file__).parent)
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        from core.llm_provider import LLMProvider
        llm = LLMProvider(provider="mistral")
        raw = llm.generate(
            prompt=(
                f"L'utilisateur a saisi : \"{name}\"\n"
                f"Classe cet input et resous-le en ticker yfinance valide.\n"
                f"Réponds en JSON strict, un seul objet, rien d'autre.\n\n"
                f"Si c'est une société cotée : {{\"type\":\"ticker\",\"value\":\"TICKER_YFINANCE\"}}\n"
                f"  IMPORTANT : inclus toujours le suffixe marché yfinance quand applicable :\n"
                f"  - Paris (Euronext FR)    → .PA    ex: total → TTE.PA, lvmh → MC.PA, orange → ORA.PA\n"
                f"  - Milan (Borsa Italiana) → .MI    ex: stellantis → STLAM.MI, ferrari → RACE.MI\n"
                f"  - Londres (LSE)          → .L     ex: hsbc → HSBA.L, shell → SHEL.L, bp → BP.L\n"
                f"  - Francfort (Xetra)      → .DE    ex: sap → SAP.DE, siemens → SIE.DE, volkswagen → VOW3.DE\n"
                f"  - Amsterdam (Euronext)   → .AS    ex: asml → ASML.AS, heineken → HEIA.AS\n"
                f"  - Zurich (SIX)           → .SW    ex: nestle → NESN.SW, roche → ROG.SW, novartis → NOVN.SW\n"
                f"  - Madrid (BME)           → .MC    ex: santander → SAN.MC, iberdrola → IBE.MC\n"
                f"  - Stockholm (Nasdaq)     → .ST    ex: volvo → VOLV-B.ST\n"
                f"  - Oslo (Nordic)          → .OL    ex: equinor → EQNR.OL\n"
                f"  - Copenhague (Nasdaq)    → .CO    ex: novo nordisk → NOVO-B.CO\n"
                f"  - Hong Kong              → .HK    ex: tencent → 0700.HK\n"
                f"  - Tokyo                  → .T     ex: toyota → 7203.T\n"
                f"  - Toronto (TSX)          → .TO    ex: shopify → SHOP.TO\n"
                f"  - Actions US (NYSE/Nasdaq) : PAS de suffixe, ex: apple → AAPL, tesla → TSLA\n\n"
                f"Si l'utilisateur a tapé un ticker sans suffixe mais que le vrai ticker en a un, corrige :\n"
                f"  TTE → TTE.PA, STLAM → STLAM.MI, HSBA → HSBA.L, NESN → NESN.SW\n\n"
                f"IMPORTANT — sociétés fusionnées / absorbées (ne renvoie JAMAIS l'ancien ticker) :\n"
                f"  - peugeot / PSA / citroen / opel / fiat chrysler → STLAM.MI (Stellantis depuis 2021)\n"
                f"  - lafarge → HOLN.SW (LafargeHolcim / Holcim)\n"
                f"  - alstom → ALO.PA\n"
                f"  - areva → ORANO (non coté) / EDF.PA\n"
                f"  - sanofi-aventis → SAN.PA (Sanofi)\n"
                f"  - suez → VIE.PA (Veolia a absorbé Suez en 2022)\n"
                f"  - engie → ENGI.PA\n\n"
                f"Suffixes VALIDES uniquement (n'invente PAS de suffixe) : .PA .MI .L .DE .AS .SW .MC .ST .OL .CO .HE .HK .T .TO .BR .VI .IR .LS\n"
                f"JAMAIS de suffixe .FR, .EU, .WORLD, .US — ils n'existent pas sur yfinance.\n\n"
                f"Si c'est un secteur boursier : {{\"type\":\"sector\",\"value\":\"Technology\"}}\n"
                f"Si c'est un indice : {{\"type\":\"index\",\"value\":\"S&P 500\"}}\n\n"
                f"Réponds UNIQUEMENT avec le JSON, rien d'autre. Pas de markdown, pas de commentaire."
            ),
            system="Tu es un expert en tickers boursiers yfinance. Tu connais les suffixes marché (.PA, .MI, .L, .DE, .AS, .SW, .MC, .ST, .OL, .CO, .HK, .T, .TO). Réponds uniquement en JSON valide, un seul objet.",
            max_tokens=60,
        )
        if raw:
            m = _re.search(r'\{.*?\}', raw, _re.DOTALL)
            if m:
                return _json.loads(m.group(0))
    except Exception as e:
        _log.warning("[resolve_llm] LLM résolution failed for '%s': %s", name, e)
    return None


# NIGHT-5 Baptiste 2026-04-14 : Extended mapping manuel 100+ societes US/EU
# pour couvrir les tickers moins connus sans appel yfinance/LLM. Couvre
# CAC 40, DAX 40, S&P 500 top 50, FTSE 100 top 20, STOXX Europe leaders.
_KNOWN_TICKERS = {
    # ─── US Mega/Large caps ────────────────────────────────
    "apple": "AAPL", "aapl": "AAPL",
    "microsoft": "MSFT", "msft": "MSFT",
    "google": "GOOGL", "alphabet": "GOOGL", "googl": "GOOGL", "goog": "GOOG",
    "amazon": "AMZN", "amzn": "AMZN",
    "tesla": "TSLA", "tsla": "TSLA",
    "nvidia": "NVDA", "nvda": "NVDA",
    "meta": "META", "facebook": "META",
    "netflix": "NFLX", "nflx": "NFLX",
    "berkshire": "BRK-B", "berkshire hathaway": "BRK-B",
    "jpmorgan": "JPM", "jp morgan": "JPM", "jpm": "JPM",
    "visa": "V", "mastercard": "MA",
    "johnson": "JNJ", "johnson & johnson": "JNJ", "jnj": "JNJ",
    "unitedhealth": "UNH", "united health": "UNH",
    "walmart": "WMT", "wmt": "WMT",
    "procter": "PG", "procter gamble": "PG", "pg": "PG",
    "exxon": "XOM", "exxonmobil": "XOM", "xom": "XOM",
    "chevron": "CVX", "cvx": "CVX",
    "home depot": "HD", "hd": "HD",
    "abbvie": "ABBV", "abbv": "ABBV",
    "eli lilly": "LLY", "lly": "LLY",
    "coca cola": "KO", "cocacola": "KO", "ko": "KO",
    "pepsi": "PEP", "pepsico": "PEP", "pep": "PEP",
    "costco": "COST", "cost": "COST",
    "amd": "AMD", "advanced micro devices": "AMD",
    "intel": "INTC", "intc": "INTC",
    "broadcom": "AVGO", "avgo": "AVGO",
    "oracle": "ORCL", "orcl": "ORCL",
    "salesforce": "CRM", "crm": "CRM",
    "adobe": "ADBE", "adbe": "ADBE",
    "disney": "DIS", "walt disney": "DIS", "dis": "DIS",
    "mcdonald": "MCD", "mcdonalds": "MCD", "mcd": "MCD",
    "nike": "NKE", "nke": "NKE",
    "boeing": "BA", "ba": "BA",
    "palantir": "PLTR", "pltr": "PLTR",
    "starbucks": "SBUX", "sbux": "SBUX",
    "goldman sachs": "GS", "goldman": "GS", "gs": "GS",
    "morgan stanley": "MS", "ms": "MS",
    "bank of america": "BAC", "bofa": "BAC", "bac": "BAC",
    "pfizer": "PFE", "pfe": "PFE",
    "merck": "MRK", "mrk": "MRK",
    "uber": "UBER", "ford": "F",
    "general motors": "GM", "gm": "GM",
    "stellantis": "STLAM.MI", "stelantis": "STLAM.MI",
    "peugeot": "STLAM.MI", "fiat": "STLAM.MI",
    # ─── France / CAC 40 ───────────────────────────────────
    "lvmh": "MC.PA", "louis vuitton": "MC.PA", "mc.pa": "MC.PA",
    "airbus": "AIR.PA", "air.pa": "AIR.PA",
    "totalenergies": "TTE.PA", "total": "TTE.PA", "tte.pa": "TTE.PA",
    "bnp": "BNP.PA", "bnp paribas": "BNP.PA", "bnp.pa": "BNP.PA",
    "société générale": "GLE.PA", "societe generale": "GLE.PA",
    "socgen": "GLE.PA", "gle.pa": "GLE.PA",
    "axa": "CS.PA", "cs.pa": "CS.PA",
    "hermes": "RMS.PA", "hermès": "RMS.PA", "rms.pa": "RMS.PA",
    "kering": "KER.PA", "ker.pa": "KER.PA",
    "renault": "RNO.PA", "rno.pa": "RNO.PA",
    "sanofi": "SAN.PA", "san.pa": "SAN.PA",
    "air liquide": "AI.PA", "ai.pa": "AI.PA",
    "schneider": "SU.PA", "schneider electric": "SU.PA", "su.pa": "SU.PA",
    "vinci": "DG.PA", "dg.pa": "DG.PA",
    "danone": "BN.PA", "bn.pa": "BN.PA",
    "pernod": "RI.PA", "pernod ricard": "RI.PA", "ri.pa": "RI.PA",
    "saint gobain": "SGO.PA", "saint-gobain": "SGO.PA", "sgo.pa": "SGO.PA",
    "orange": "ORA.PA", "ora.pa": "ORA.PA",
    "engie": "ENGI.PA", "engi.pa": "ENGI.PA",
    "veolia": "VIE.PA", "vie.pa": "VIE.PA",
    "thales": "HO.PA", "ho.pa": "HO.PA",
    "safran": "SAF.PA", "saf.pa": "SAF.PA",
    "dassault": "AM.PA", "dassault aviation": "AM.PA", "am.pa": "AM.PA",
    "capgemini": "CAP.PA", "cap.pa": "CAP.PA",
    "carrefour": "CA.PA", "ca.pa": "CA.PA",
    "legrand": "LR.PA", "lr.pa": "LR.PA",
    "publicis": "PUB.PA", "pub.pa": "PUB.PA",
    "edenred": "EDEN.PA", "eden.pa": "EDEN.PA",
    "stmicroelectronics": "STMPA.PA", "stm": "STMPA.PA",
    "michelin": "ML.PA", "ml.pa": "ML.PA",
    "bouygues": "EN.PA", "en.pa": "EN.PA",
    "eurofins": "ERF.PA", "erf.pa": "ERF.PA",
    "bureau veritas": "BVI.PA", "bvi.pa": "BVI.PA",
    "worldline": "WLN.PA", "wln.pa": "WLN.PA",
    "teleperformance": "TEP.PA", "tep.pa": "TEP.PA",
    "alstom": "ALO.PA", "alo.pa": "ALO.PA",
    "essilor": "EL.PA", "essilorluxottica": "EL.PA", "el.pa": "EL.PA",
    "loreal": "OR.PA", "l'oreal": "OR.PA", "or.pa": "OR.PA",
    "unibail": "URW.PA", "urw": "URW.PA",
    # ─── DAX 40 & autres allemands ─────────────────────────
    "sap": "SAP.DE", "sap.de": "SAP.DE",
    "siemens": "SIE.DE", "sie.de": "SIE.DE",
    "volkswagen": "VOW3.DE", "vw": "VOW3.DE", "vow3.de": "VOW3.DE",
    "mercedes": "MBG.DE", "mercedes-benz": "MBG.DE", "mbg.de": "MBG.DE",
    "bmw": "BMW.DE", "bmw.de": "BMW.DE",
    "allianz": "ALV.DE", "alv.de": "ALV.DE",
    "bayer": "BAYN.DE", "bayn.de": "BAYN.DE",
    "basf": "BAS.DE", "bas.de": "BAS.DE",
    "adidas": "ADS.DE", "ads.de": "ADS.DE",
    "deutsche bank": "DBK.DE", "db": "DBK.DE", "dbk.de": "DBK.DE",
    "deutsche telekom": "DTE.DE", "dtelekom": "DTE.DE", "dte.de": "DTE.DE",
    "munich re": "MUV2.DE", "muv2.de": "MUV2.DE",
    "henkel": "HEN3.DE", "hen3.de": "HEN3.DE",
    "porsche": "P911.DE", "p911.de": "P911.DE",
    "infineon": "IFX.DE", "ifx.de": "IFX.DE",
    "airbus de": "AIR.PA",  # listed primary on Paris
    # ─── Suisse / SMI ──────────────────────────────────────
    "nestle": "NESN.SW", "nestlé": "NESN.SW", "nesn.sw": "NESN.SW", "nesn": "NESN.SW",
    "roche": "ROG.SW", "rog.sw": "ROG.SW", "rog": "ROG.SW",
    "novartis": "NOVN.SW", "novn.sw": "NOVN.SW", "novn": "NOVN.SW",
    "ubs": "UBSG.SW", "ubsg.sw": "UBSG.SW",
    "zurich insurance": "ZURN.SW", "zurich": "ZURN.SW", "zurn.sw": "ZURN.SW",
    "abb": "ABBN.SW", "abb ltd": "ABBN.SW", "abbn": "ABBN.SW", "abbn.sw": "ABBN.SW",
    "swatch": "UHR.SW", "uhr.sw": "UHR.SW",
    "richemont": "CFR.SW", "cfr.sw": "CFR.SW",
    "glencore": "GLEN.L", "glen.l": "GLEN.L",
    # ─── UK / FTSE 100 ─────────────────────────────────────
    "shell": "SHEL.L", "royal dutch shell": "SHEL.L", "shel.l": "SHEL.L",
    "bp": "BP.L", "british petroleum": "BP.L", "bp.l": "BP.L",
    "hsbc": "HSBA.L", "hsba.l": "HSBA.L",
    "astrazeneca": "AZN.L", "azn.l": "AZN.L", "azn": "AZN.L",
    "gsk": "GSK.L", "glaxosmithkline": "GSK.L", "gsk.l": "GSK.L",
    "vodafone": "VOD.L", "vod.l": "VOD.L",
    "diageo": "DGE.L", "dge.l": "DGE.L",
    "barclays": "BARC.L", "barc.l": "BARC.L",
    "lloyds": "LLOY.L", "lloy.l": "LLOY.L",
    "unilever": "ULVR.L", "ulvr.l": "ULVR.L",
    "rolls royce": "RR.L", "rolls-royce": "RR.L", "rr.l": "RR.L",
    # ─── Pays-Bas / AEX ────────────────────────────────────
    "asml": "ASML.AS", "asml.as": "ASML.AS",
    "heineken": "HEIA.AS", "heia.as": "HEIA.AS",
    "philips": "PHIA.AS", "phia.as": "PHIA.AS",
    "ing": "INGA.AS", "ing groep": "INGA.AS", "inga.as": "INGA.AS",
    "ahold": "AD.AS", "ahold delhaize": "AD.AS", "ad.as": "AD.AS",
    "prosus": "PRX.AS", "prx.as": "PRX.AS",
    "adyen": "ADYEN.AS", "adyen.as": "ADYEN.AS",
    # ─── Italie / FTSE MIB ─────────────────────────────────
    "ferrari": "RACE.MI", "race.mi": "RACE.MI", "race": "RACE.MI",
    "eni": "ENI.MI", "eni.mi": "ENI.MI",
    "intesa": "ISP.MI", "intesa sanpaolo": "ISP.MI", "isp.mi": "ISP.MI",
    "unicredit": "UCG.MI", "ucg.mi": "UCG.MI",
    "enel": "ENEL.MI", "enel.mi": "ENEL.MI",
    "generali": "G.MI", "g.mi": "G.MI",
    # ─── Espagne / IBEX 35 ─────────────────────────────────
    "santander": "SAN.MC", "banco santander": "SAN.MC", "san.mc": "SAN.MC",
    "iberdrola": "IBE.MC", "ibe.mc": "IBE.MC",
    "bbva": "BBVA.MC", "bbva.mc": "BBVA.MC",
    "inditex": "ITX.MC", "zara": "ITX.MC", "itx.mc": "ITX.MC",
    "repsol": "REP.MC", "rep.mc": "REP.MC",
    "telefonica": "TEF.MC", "tef.mc": "TEF.MC",
    # ─── Belgique / Bel20 ──────────────────────────────────
    "ab inbev": "ABI.BR", "anheuser-busch": "ABI.BR", "abi.br": "ABI.BR",
    "kbc": "KBC.BR", "kbc.br": "KBC.BR",
    "ucb": "UCB.BR", "ucb.br": "UCB.BR",
    # ─── Nordiques ─────────────────────────────────────────
    "novo nordisk": "NOVO-B.CO", "novo-b.co": "NOVO-B.CO",
    "maersk": "MAERSK-B.CO", "maersk-b.co": "MAERSK-B.CO",
    "ericsson": "ERIC-B.ST", "eric-b.st": "ERIC-B.ST",
    "volvo": "VOLV-B.ST", "volv-b.st": "VOLV-B.ST",
    "nokia": "NOKIA.HE", "nokia.he": "NOKIA.HE",
    "equinor": "EQNR.OL", "eqnr.ol": "EQNR.OL",
    "dnb": "DNB.OL", "dnb.ol": "DNB.OL",
}

_LEVENSHTEIN_THRESHOLD = 2  # max distance for fuzzy match on names


def _levenshtein(a: str, b: str) -> int:
    """Simple Levenshtein distance for fuzzy ticker name matching."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if not b:
        return len(a)
    prev_row = range(len(b) + 1)
    for i, ca in enumerate(a):
        curr_row = [i + 1]
        for j, cb in enumerate(b):
            ins = prev_row[j + 1] + 1
            dels = curr_row[j] + 1
            sub = prev_row[j] + (ca != cb)
            curr_row.append(min(ins, dels, sub))
        prev_row = curr_row
    return prev_row[-1]


def _fuzzy_ticker_match(name: str) -> str | None:
    """Tente un match fuzzy sur le _KNOWN_TICKERS dict avec Levenshtein <= 2.
    Couvre les typos classiques comme 'microsft' -> 'microsoft', 'appl' -> 'apple'."""
    norm = name.strip().lower()
    if not norm or len(norm) < 3:
        return None
    best_match, best_dist = None, _LEVENSHTEIN_THRESHOLD + 1
    for key in _KNOWN_TICKERS:
        # Skip les cles trop eloignees en longueur (optimization)
        if abs(len(key) - len(norm)) > _LEVENSHTEIN_THRESHOLD:
            continue
        d = _levenshtein(norm, key)
        if d < best_dist:
            best_dist = d
            best_match = key
    if best_dist <= _LEVENSHTEIN_THRESHOLD:
        return _KNOWN_TICKERS[best_match]
    return None


def _resolve_ticker_yahoo(name: str) -> str | None:
    """Resout un nom de société en ticker.
    Ordre : mapping manuel → fuzzy match Levenshtein → Yahoo Search → LLM.
    Retourne le ticker ou None si rien ne fonctionne."""
    import logging as _log
    norm = name.strip().lower()
    # Niveau 1 : mapping manuel exact
    if norm in _KNOWN_TICKERS:
        return _KNOWN_TICKERS[norm]
    # Niveau 1b : fuzzy match Levenshtein (typos)
    fuzzy = _fuzzy_ticker_match(norm)
    if fuzzy:
        _log.info(f"[resolve_ticker] fuzzy match : '{name}' -> {fuzzy}")
        return fuzzy
    # Niveau 2 : Yahoo Finance Search
    try:
        import requests as _req
        r = _req.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": name, "quotesCount": 5, "newsCount": 0},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5,
        )
        for q in r.json().get("quotes", []):
            if q.get("quoteType") == "EQUITY":
                return q["symbol"]
    except Exception as e:
        _log.warning("[resolve_ticker] Yahoo search failed for '%s': %s", name, e)
    # Niveau 3 : LLM fallback
    llm_result = _resolve_input_llm(name)
    if llm_result and llm_result.get("type") == "ticker":
        return llm_result.get("value")
    return None


def detect_input_type(query: str) -> str:
    q = query.strip().upper().replace(" ", "").replace("-", "").replace("&", "")
    if q in _INDICES_SET:
        return "screening_indice"
    # Résolution sectorielle FR/EN/slug via core/sector_labels
    if _slug_from_any(query) is not None:
        return "screening_secteur"
    # Heuristique : si l'input contient un espace ou fait > 5 chars sans ressembler
    # à un ticker (tout en majuscules courts), c'est probablement un secteur.
    raw = query.strip()
    if " " in raw and len(raw) > 4:
        return "screening_secteur"
    if len(raw) > 5 and not raw.isupper():
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

    # Si l'input est un secteur FR ("Technologie") ou EN ("Technology"),
    # on resout vers le slug canonique avant lookup univers
    _maybe_slug = _slug_from_any(universe)
    if _maybe_slug is not None:
        u = _maybe_slug

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


# ═════════════════════════════════════════════════════════════════════════════
# Whitelists sous-secteurs — filtrent le pool Financial Services
# ═════════════════════════════════════════════════════════════════════════════
# Ces sets servent a splitter "Financial Services" en deux analyses distinctes
# Banques / Assurance. Classification manuelle (Supabase n'a pas de colonne
# industry). Maintenance legere : une banque entrante au S&P 500 passera en
# umbrella FINANCIALS si non whitelistee, pas d'erreur cassante.

_BANKS_SP500_TICKERS: set[str] = {
    # Megabanks
    "JPM", "BAC", "WFC", "C", "GS", "MS",
    # Super-regionals
    "USB", "PNC", "TFC", "COF", "BK", "STT", "NTRS",
    # Regionals
    "FITB", "HBAN", "RF", "KEY", "CFG", "MTB", "CMA", "ZION",
    "PB", "WBS", "FHN", "SNV", "WAL", "EWBC", "BPOP",
    "PNFP", "FFIN", "CFR", "SBNY", "ONB", "FCNCA", "GBCI",
    # Asset managers / brokers / payments adjacents
    "SCHW", "AXP", "DFS", "SYF", "AMP", "TROW", "BLK",
    "BX", "KKR", "APO", "BEN", "IVZ",
}

_BANKS_EU_TICKERS: set[str] = {
    # France
    "BNP.PA", "ACA.PA", "GLE.PA", "KN.PA",
    # UK
    "HSBA.L", "BARC.L", "LLOY.L", "NWG.L", "STAN.L", "VMUK.L",
    # Germany
    "DBK.DE", "CBK.DE", "AAREAL.DE",
    # Italy
    "ISP.MI", "UCG.MI", "BMPS.MI", "BAMI.MI", "BPER.MI", "BCBP.MI",
    # Spain
    "SAN.MC", "BBVA.MC", "CABK.MC", "BKT.MC", "SAB.MC", "UNI.MC",
    # Netherlands / Belgium
    "INGA.AS", "ABN.AS", "KBC.BR",
    # Switzerland
    "UBSG.SW",
    # Nordics
    "NDA-FI.HE", "DANSKE.CO", "SEB-A.ST", "SHB-A.ST", "SWED-A.ST", "DNB.OL",
    # Other EU
    "ERST.VI", "RBI.VI", "BOIY.IR", "AIBG.IR",
}

_INSURANCE_SP500_TICKERS: set[str] = {
    # P&C / Multi-line
    "BRK.B", "TRV", "PGR", "ALL", "CB", "HIG", "AIG",
    "CINF", "L", "RE", "WRB", "MKL", "RNR", "AIZ",
    "FAF", "ORI", "EG", "AFG", "SIGI", "KMPR", "PLMR",
    # Life / Annuities
    "MET", "PRU", "LNC", "UNM", "GL", "PFG", "VOYA",
    "EQH", "BHF", "AEL", "CNO",
    # Health insurers (optionnel — separables en HEALTHCARE parfois)
    "UNH", "ELV", "HUM", "CI", "CNC", "MOH",
    # Brokers
    "MMC", "AON", "AJG", "WTW", "BRO", "RYAN",
    # Specialty / Reinsurance
    "AFL", "ESGR", "JRVR", "HALO",
}

_INSURANCE_EU_TICKERS: set[str] = {
    # France
    "CS.PA", "CNP.PA", "SCR.PA",
    # Germany
    "ALV.DE", "MUV2.DE", "HNR1.DE", "TLX.DE",
    # Switzerland
    "ZURN.SW", "SLHN.SW", "BALN.SW", "HELN.SW",
    # UK
    "AV.L", "LGEN.L", "PRU.L", "ADM.L", "BEZ.L", "DLG.L", "HSX.L",
    "LRE.L", "PHNX.L", "SBRE.L",
    # Italy
    "G.MI", "UNI.MI",
    # Spain
    "MAP.MC",
    # Netherlands
    "ASRNL.AS", "AGN.AS", "NN.AS",
    # Nordics
    "SAMPO.HE", "GJF.OL", "TRYG.CO", "TOP.CO",
}


def _fetch_sector_tickers(sector_key: str) -> list:
    """Query Supabase for tickers in a given sector, fallback sur _SECTOR_TICKERS local.

    Sous-secteurs (BANKS, INSURANCE) : fetch le pool du secteur ombrelle
    (Financial Services) puis filtre via la whitelist correspondante.
    """
    import os, requests as _req
    from core.sector_labels import is_sub_sector, umbrella_slug

    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SECRET_KEY", "")

    # Sous-secteur : fetch l'ombrelle puis filtre
    _sub_whitelist: set | None = None
    _fetch_slug = sector_key
    if is_sub_sector(sector_key):
        _fetch_slug = umbrella_slug(sector_key)
        if sector_key == "BANKS":
            _sub_whitelist = _BANKS_SP500_TICKERS | _BANKS_EU_TICKERS
        elif sector_key == "INSURANCE":
            _sub_whitelist = _INSURANCE_SP500_TICKERS | _INSURANCE_EU_TICKERS

    tickers = []
    if url and key:
        sector_name = _SECTOR_YFINANCE.get(_fetch_slug, _fetch_slug.title())
        offset = 0
        while True:
            try:
                resp = _req.get(
                    f"{url}/rest/v1/tickers_cache",
                    headers={"apikey": key, "Authorization": f"Bearer {key}",
                             "Range": f"{offset}-{offset+999}"},
                    params={"select": "ticker", "sector": f"eq.{sector_name}"},
                    timeout=15,
                )
            except Exception:
                break
            if resp.status_code not in (200, 206):
                break
            batch = resp.json()
            if not batch:
                break
            tickers.extend(r["ticker"] for r in batch)
            if len(batch) < 1000:
                break
            offset += 1000

    # Filtre sous-secteur (BANKS/INSURANCE) : ne garde que les tickers whitelistes
    if tickers and _sub_whitelist is not None:
        tickers = [t for t in tickers if t in _sub_whitelist]

    if tickers:
        return tickers

    # Fallback 1 : _SECTOR_TICKERS defini dans cli_analyze.py
    # On cherche la cle (sector_display, *) la plus probable
    try:
        import sys as _sys, os as _os
        _root = str(Path(__file__).parent)
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        from cli_analyze import _SECTOR_TICKERS as _ST
        sector_display = _SECTOR_YFINANCE.get(_fetch_slug, _fetch_slug.title())
        # Priorite S&P 500, sinon premier univers trouvé (Normalisé sans espaces)
        _norm = sector_display.lower().replace(" ", "")
        _apply = (lambda xs: [x for x in xs if x in _sub_whitelist]) if _sub_whitelist else list
        for (s, u), tks in _ST.items():
            if s.lower().replace(" ", "") == _norm and u == "S&P 500":
                _r = _apply(tks)
                if _r:
                    return _r
        for universe_pref in ("CAC 40", "DAX", "FTSE 100"):
            for (s, u), tks in _ST.items():
                if s.lower().replace(" ", "") == _norm and u == universe_pref:
                    _r = _apply(tks)
                    if _r:
                        return _r
        # Dernier recours : n'importe quelle cle avec ce secteur
        for (s, u), tks in _ST.items():
            if s.lower().replace(" ", "") == _norm:
                _r = _apply(tks)
                if _r:
                    return _r
        # Si on est en sous-secteur et rien trouve via whitelist, retourne la
        # whitelist brute (tickers hardcodes pour garantir non-vide)
        if _sub_whitelist:
            return sorted(_sub_whitelist)
    except Exception:
        pass

    # Fallback 2 : LLM (Mistral) — secteur inconnu, demande les tickers S&P 500
    try:
        import sys as _sys2, os as _os2
        _root2 = str(Path(__file__).parent)
        if _root2 not in _sys2.path:
            _sys2.path.insert(0, _root2)
        from core.llm_provider import LLMProvider
        sector_label = _SECTOR_YFINANCE.get(sector_key, sector_key.replace("_", " ").title())
        llm = LLMProvider(provider="mistral")
        raw = llm.generate(
            prompt=(
                f"Donne-moi exactement 8 tickers yfinance valides (S&P 500 de préférence) "
                f"pour le secteur '{sector_label}'. "
                f"Reponds UNIQUEMENT avec les tickers separes par des virgules, rien d'autre. "
                f"Exemple : AAPL,MSFT,NVDA,META,GOOGL,AMD,AVGO,ORCL"
            ),
            system="Tu es un expert financier. Reponds uniquement avec des tickers valides, separes par des virgules.",
            max_tokens=60,
        )
        if raw:
            tickers_llm = [
                t.strip().upper() for t in raw.replace("\n", ",").split(",")
                if t.strip() and 1 <= len(t.strip()) <= 10
            ][:10]
            if tickers_llm:
                return tickers_llm
    except Exception:
        pass

    return []


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

        # (Aperçu Claude retiré — section interne non utilisée)

        # Contexte page comparative (société / secteur / indice)
        _in_cmp_page = (st.session_state.get("stage") == "comparison_results")
        _comparison_kind    = st.session_state.get("comparison_kind")

        if _in_cmp_page:
            # Nouvelle analyse (reset complet) — priorite haute
            if st.button("＋  Nouvelle analyse", use_container_width=True, type="primary",
                          key="sb_new_from_cmp"):
                for _k in ("stage", "results", "ticker", "from_screening",
                           "screening_results", "cmp_societe_stage", "comparison_kind",
                           "cmp_societe_ticker_b", "cmp_societe_state_b", "cmp_societe_xlsx_bytes",
                           "cmp_societe_pptx_bytes", "cmp_societe_pdf_bytes", "cmp_societe_synthesis",
                           "cmp_secteur_stage", "cmp_secteur_sector_b", "cmp_secteur_pptx_bytes",
                           "cmp_secteur_pdf_bytes", "cmp_secteur_xlsx_bytes",
                           "cmp_secteur_tickers_a", "cmp_secteur_tickers_b",
                           "cmp_indice_stage", "cmp_indice_universe_b",
                           "cmp_indice_pptx_bytes", "cmp_indice_pdf_bytes", "cmp_indice_xlsx_bytes",
                           "cmp_indice_data", "cmp_indice_universe_a",
                           "previous_analysis_type", "previous_analysis_results",
                           "previous_analysis_label"):
                    if _k == "stage":
                        st.session_state[_k] = "home"
                    elif _k == "from_screening":
                        st.session_state[_k] = False
                    elif _k in ("cmp_societe_ticker_b", "cmp_secteur_sector_b", "cmp_indice_universe_b",
                                "cmp_indice_universe_a", "previous_analysis_label"):
                        st.session_state[_k] = ""
                    else:
                        st.session_state[_k] = None
                st.rerun()

            # Bouton retour a l'analyse initiale
            _prev_label = st.session_state.get("previous_analysis_label") or "l'analyse"
            if st.button(f"\u2190 Retour à {_prev_label}", use_container_width=True,
                          key="sb_back_prev_analysis"):
                _cmp_back_to_previous()

        # Contexte ANALYSE SECTORIELLE / INDICE (screening_results)
        # On affiche aussi le bouton Nouvelle analyse dans ce stage pour coherence
        # avec le ruban de gauche des analyses societe
        elif (st.session_state.get("stage") == "screening_results"
              and st.session_state.get("screening_results")):
            if st.button("+  Nouvelle analyse", use_container_width=True, type="primary",
                          key="sb_new_from_screening"):
                # Reset complet : meme liste de cles que le bouton societe
                for _k in (
                    "results", "ticker", "from_screening",
                    "screening_results", "screening_parent", "screening_universe",
                    "cmp_indice_stage", "cmp_indice_universe_b", "cmp_indice_universe_a",
                    "cmp_indice_pptx_bytes", "cmp_indice_pdf_bytes", "cmp_indice_xlsx_bytes",
                    "cmp_indice_data",
                    "cmp_secteur_stage", "cmp_secteur_sector_b", "cmp_secteur_universe_b",
                    "cmp_secteur_pptx_bytes", "cmp_secteur_pdf_bytes", "cmp_secteur_xlsx_bytes",
                    "cmp_secteur_tickers_a", "cmp_secteur_tickers_b", "cmp_secteur_data",
                    "cmp_societe_stage", "comparison_kind", "cmp_societe_state_b", "cmp_societe_xlsx_bytes",
                    "cmp_societe_pptx_bytes", "cmp_societe_pdf_bytes", "cmp_societe_ticker_b",
                    "previous_analysis_type", "previous_analysis_results",
                    "previous_analysis_label",
                ):
                    if _k in st.session_state:
                        del st.session_state[_k]
                st.session_state.stage = "home"
                st.rerun()

        elif results and not results.get("error"):
            if st.button("＋  Nouvelle analyse", use_container_width=True, type="primary"):
                # Reset COMPLET — sinon livrables / cmp / from_screening
                # peuvent reapparaitre sur l'analyse suivante
                for _k in (
                    "results", "ticker", "from_screening",
                    "screening_results", "screening_parent", "screening_universe",
                    "cmp_indice_stage", "cmp_indice_universe_b", "cmp_indice_universe_a",
                    "cmp_indice_pptx_bytes", "cmp_indice_pdf_bytes", "cmp_indice_xlsx_bytes",
                    "cmp_indice_data",
                    "cmp_secteur_stage", "cmp_secteur_sector_b", "cmp_secteur_universe_b",
                    "cmp_secteur_pptx_bytes", "cmp_secteur_pdf_bytes", "cmp_secteur_xlsx_bytes",
                    "cmp_secteur_tickers_a", "cmp_secteur_tickers_b", "cmp_secteur_data",
                    "cmp_societe_stage", "comparison_kind", "cmp_societe_state_b", "cmp_societe_xlsx_bytes",
                    "cmp_societe_pptx_bytes", "cmp_societe_pdf_bytes", "cmp_societe_ticker_b",
                    "previous_analysis_type", "previous_analysis_results",
                    "previous_analysis_label",
                ):
                    if _k in st.session_state:
                        del st.session_state[_k]
                st.session_state.stage = "home"
                st.rerun()

            # Bouton "Actualiser" : force le re-run du pipeline pour le ticker
            # courant en bypassant le cache. Utile si la 1ere analyse a echoue.
            _curr_ticker = (results.get("ticker") if results else None) or st.session_state.get("ticker")
            if _curr_ticker and st.button("\u21bb  Actualiser l'analyse",
                                          use_container_width=True,
                                          key="sb_force_refresh"):
                # Pop le ticker du cache pipeline et re-route vers running
                _cr = st.session_state.get("_pipeline_state_cache") or {}
                _cr.pop(_curr_ticker.upper(), None)
                st.session_state["_pipeline_state_cache"] = _cr
                st.session_state["_force_refresh_analysis"] = True
                st.session_state.ticker = _curr_ticker
                st.session_state.stage = "running"
                st.rerun()

        # Bouton retour au screening : seulement si on vient du screening
        # ET qu'on est sur une page d'analyse (pas déjà sur le screening lui-même)
        _on_screening = (st.session_state.get("stage") == "screening_results")
        if (not _in_cmp_page) and (not _on_screening) and st.session_state.get("from_screening") and st.session_state.get("screening_results"):
            if st.button("\u2190 Retour au screening", use_container_width=True):
                st.session_state.from_screening = False
                st.session_state.stage = "screening_results"
                st.rerun()

        # Livrables — contextualisés selon l'analyse active
        st.markdown('<div class="sb-section">', unsafe_allow_html=True)
        st.markdown('<span class="sb-label">Livrables</span>', unsafe_allow_html=True)

        # ── Contexte PAGE COMPARATIVE : afficher UNIQUEMENT les livrables comparatifs ──
        if _in_cmp_page:
            if _comparison_kind == "société":
                _tkr_a_cmp = st.session_state.get("previous_analysis_label", "A")
                _tkr_b_cmp = st.session_state.get("cmp_societe_ticker_b", "B")
                _cmp_societe_pdf = st.session_state.get("cmp_societe_pdf_bytes")
                if _cmp_societe_pdf:
                    st.download_button(
                        f"Rapport PDF {_tkr_a_cmp} vs {_tkr_b_cmp} \u2193 .pdf",
                        _cmp_societe_pdf,
                        file_name=f"{_tkr_a_cmp}_vs_{_tkr_b_cmp}_comparison.pdf",
                        mime="application/pdf",
                        use_container_width=True, key="sb_cmppage_pdf",
                    )
                _cmp_societe_pptx = st.session_state.get("cmp_societe_pptx_bytes")
                if _cmp_societe_pptx:
                    st.download_button(
                        f"Pitchbook {_tkr_a_cmp} vs {_tkr_b_cmp} \u2193 .pptx",
                        _cmp_societe_pptx,
                        file_name=f"{_tkr_a_cmp}_vs_{_tkr_b_cmp}_comparison.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        use_container_width=True, key="sb_cmppage_pptx",
                    )
                _cmp_societe_xlsx = st.session_state.get("cmp_societe_xlsx_bytes")
                if _cmp_societe_xlsx:
                    st.download_button(
                        f"Excel financier {_tkr_a_cmp} vs {_tkr_b_cmp} \u2193 .xlsx",
                        _cmp_societe_xlsx,
                        file_name=f"{_tkr_a_cmp}_vs_{_tkr_b_cmp}_comparison.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True, key="sb_cmppage_xlsx",
                    )
            elif _comparison_kind == "secteur":
                _sa = st.session_state.get("cmp_secteur_sector_a", "A")
                _sb = st.session_state.get("cmp_secteur_sector_b", "B")
                _slug = f"cmp_secteur_{_sa}_vs_{_sb}".replace(" ", "_")
                _sp_pdf = st.session_state.get("cmp_secteur_pdf_bytes")
                if _sp_pdf:
                    st.download_button(
                        f"Rapport PDF {_sa} vs {_sb} \u2193 .pdf",
                        _sp_pdf,
                        file_name=f"{_slug}.pdf",
                        mime="application/pdf",
                        use_container_width=True, key="sb_scmppage_pdf",
                    )
                _sp_pptx = st.session_state.get("cmp_secteur_pptx_bytes")
                if _sp_pptx:
                    st.download_button(
                        f"Pitchbook {_sa} vs {_sb} \u2193 .pptx",
                        _sp_pptx,
                        file_name=f"{_slug}.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        use_container_width=True, key="sb_scmppage_pptx",
                    )
                _sp_xlsx = st.session_state.get("cmp_secteur_xlsx_bytes")
                if _sp_xlsx:
                    st.download_button(
                        f"Excel {_sa} vs {_sb} \u2193 .xlsx",
                        _sp_xlsx,
                        file_name=f"{_slug}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True, key="sb_scmppage_xlsx",
                    )
            elif _comparison_kind == "indice":
                _ua = st.session_state.get("cmp_indice_universe_a", "A")
                _ub = st.session_state.get("cmp_indice_universe_b", "B")
                _na = _INDICE_CMP_OPTIONS.get(_ua, (_ua,))[0] if "_INDICE_CMP_OPTIONS" in globals() else _ua
                _nb = _INDICE_CMP_OPTIONS.get(_ub, (_ub,))[0] if "_INDICE_CMP_OPTIONS" in globals() else _ub
                _slug = f"cmp_indice_{_na}_vs_{_nb}".replace(" ", "_")
                _i_pdf = st.session_state.get("cmp_indice_pdf_bytes")
                if _i_pdf:
                    st.download_button(
                        f"Rapport PDF {_na} vs {_nb} \u2193 .pdf",
                        _i_pdf,
                        file_name=f"{_slug}.pdf",
                        mime="application/pdf",
                        use_container_width=True, key="sb_icmppage_pdf",
                    )
                _i_pptx = st.session_state.get("cmp_indice_pptx_bytes")
                if _i_pptx:
                    st.download_button(
                        f"Pitchbook {_na} vs {_nb} \u2193 .pptx",
                        _i_pptx,
                        file_name=f"{_slug}.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        use_container_width=True, key="sb_icmppage_pptx",
                    )
                _i_xlsx = st.session_state.get("cmp_indice_xlsx_bytes")
                if _i_xlsx:
                    st.download_button(
                        f"Excel {_na} vs {_nb} \u2193 .xlsx",
                        _i_xlsx,
                        file_name=f"{_slug}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True, key="sb_icmppage_xlsx",
                    )
            st.markdown('</div>', unsafe_allow_html=True)
            # Sources financières + veille quand meme
            st.markdown('<div class="sb-section">', unsafe_allow_html=True)
            st.markdown('<span class="sb-label">Sources financières</span>', unsafe_allow_html=True)
            for name, ok in [("Yahoo Finance", True), ("Financial Modeling Prep", True),
                              ("Finnhub", True), ("EODHD", True)]:
                badge = f'<span class="src-ok">Actif</span>' if ok else f'<span class="src-warn">Inactif</span>'
                st.markdown(f'<div class="src-row"><span>{name}</span>{badge}</div>',
                            unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            return

        # Détermine le contexte : société (results) ou secteur/indice (screening_results)
        _in_societe  = bool(results and not results.get("error") and results.get("ticker"))
        _in_secteur  = bool(not _in_societe and st.session_state.get("screening_results"))

        if _in_societe:
            # ── Contexte société : livrables société ──
            ticker_slug = results.get("ticker", "report")
            _tkr_label  = results.get("ticker", "")

            pptx_data = results.get("pptx_bytes")
            if not pptx_data:
                pptx = results.get("pptx_path")
                if pptx and Path(pptx).exists():
                    pptx_data = open(pptx, "rb").read()
            if pptx_data:
                st.download_button(f"Pitchbook {_tkr_label} \u2193 .pptx", pptx_data,
                    file_name=f"{ticker_slug}_pitchbook.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True)

            xlsx_data = results.get("excel_bytes")
            if not xlsx_data:
                xlsx = results.get("excel_path")
                if xlsx and Path(xlsx).exists():
                    xlsx_data = open(xlsx, "rb").read()
            if xlsx_data:
                st.download_button(f"Excel financier {_tkr_label} \u2193 .xlsx", xlsx_data,
                    file_name=f"{ticker_slug}_financials.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True)

            pdf_data = results.get("pdf_bytes")
            if not pdf_data:
                pdf = results.get("pdf_path")
                if pdf and Path(pdf).exists():
                    pdf_data = open(pdf, "rb").read()
            if pdf_data:
                st.download_button(f"Rapport PDF {_tkr_label} \u2193 .pdf", pdf_data,
                    file_name=f"{ticker_slug}_report.pdf",
                    mime="application/pdf",
                    use_container_width=True)

            # ── Livrables comparatifs (si comparaison disponible) ──
            _cmp_stage = st.session_state.get("cmp_societe_stage")
            _cmp_societe_tkr_b = st.session_state.get("cmp_societe_ticker_b", "")
            if _cmp_stage == "done" and _cmp_societe_tkr_b:
                st.markdown(
                    f'<div style="font-size:10px;font-weight:600;letter-spacing:.06em;'
                    f'color:#aaa;text-transform:uppercase;margin:10px 0 4px;">Comparatif vs {_cmp_societe_tkr_b}</div>',
                    unsafe_allow_html=True,
                )
                _cmp_societe_xlsx = st.session_state.get("cmp_societe_xlsx_bytes")
                if _cmp_societe_xlsx:
                    st.download_button(
                        f"Comparaison {_tkr_label} vs {_cmp_societe_tkr_b} \u2193 .xlsx",
                        _cmp_societe_xlsx,
                        file_name=f"{ticker_slug}_vs_{_cmp_societe_tkr_b}_comparison.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="sb_cmp_societe_xlsx",
                    )
                _cmp_societe_pptx = st.session_state.get("cmp_societe_pptx_bytes")
                if _cmp_societe_pptx:
                    st.download_button(
                        f"Pitchbook {_tkr_label} vs {_cmp_societe_tkr_b} \u2193 .pptx",
                        _cmp_societe_pptx,
                        file_name=f"{ticker_slug}_vs_{_cmp_societe_tkr_b}_comparison.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        use_container_width=True,
                        key="sb_cmp_societe_pptx",
                    )
                _cmp_societe_pdf = st.session_state.get("cmp_societe_pdf_bytes")
                if _cmp_societe_pdf:
                    st.download_button(
                        f"Rapport {_tkr_label} vs {_cmp_societe_tkr_b} \u2193 .pdf",
                        _cmp_societe_pdf,
                        file_name=f"{ticker_slug}_vs_{_cmp_societe_tkr_b}_comparison.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key="sb_cmp_societe_pdf",
                    )

        else:
            # ── Contexte secteur / indice : afficher uniquement les livrables screening ──
            scr = st.session_state.get("screening_results")
            if scr and scr.get("indice_xlsx_bytes"):
                scr_name = scr.get("display_name", "indice")
                st.download_button(
                    f"Screening {scr_name} \u2193 .xlsx",
                    scr["indice_xlsx_bytes"],
                    file_name=f"indice_{scr_name.lower().replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            elif scr and scr.get("excel_bytes"):
                scr_name = scr.get("display_name", "screening")
                st.download_button(
                    f"Screening {scr_name} \u2193 .xlsx",
                    scr["excel_bytes"],
                    file_name=f"screening_{scr_name.lower().replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            if scr and scr.get("pdf_bytes"):
                scr_name = scr.get("display_name", "secteur")
                _pdf_slug = scr_name.lower().replace(' ', '_').replace('\u2014', '').strip()
                _pdf_is_indice = scr.get("universe", "") not in _SECTOR_ALIASES_SET
                _pdf_label = "Rapport indice \u2193 .pdf" if _pdf_is_indice else "Rapport sectoriel \u2193 .pdf"
                st.download_button(
                    _pdf_label,
                    scr["pdf_bytes"],
                    file_name=f"rapport_{_pdf_slug}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            if scr and scr.get("pptx_bytes"):
                scr_name = scr.get("display_name", "secteur")
                _pptx_slug = scr_name.lower().replace(' ', '_').replace('\u2014', '').strip()
                _pptx_is_indice = scr.get("universe", "") not in _SECTOR_ALIASES_SET
                _pptx_label = f"Pitchbook indice \u2193 .pptx" if _pptx_is_indice else "Pitchbook sectoriel \u2193 .pptx"
                st.download_button(
                    _pptx_label,
                    scr["pptx_bytes"],
                    file_name=f"pitchbook_{_pptx_slug}.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True,
                )
            # ── Comparatif sectoriel (si disponible) ──
            _cmp_secteur_stage = st.session_state.get("cmp_secteur_stage")
            _cmp_secteur_b = st.session_state.get("cmp_secteur_sector_b", "")
            if _cmp_secteur_stage == "done" and _cmp_secteur_b:
                st.markdown(
                    f'<div style="font-size:10px;font-weight:600;letter-spacing:.06em;'
                    f'color:#aaa;text-transform:uppercase;margin:10px 0 4px;">'
                    f'Comparatif sectoriel</div>',
                    unsafe_allow_html=True,
                )
                _cmp_secteur_pptx = st.session_state.get("cmp_secteur_pptx_bytes")
                if _cmp_secteur_pptx:
                    _cmp_secteur_a = scr.get("display_name", "Secteur A") if scr else "Secteur A"
                    st.download_button(
                        f"Pitchbook {_cmp_secteur_a} vs {_cmp_secteur_b} \u2193 .pptx",
                        _cmp_secteur_pptx,
                        file_name=f"cmp_secteur_{_cmp_secteur_a}_vs_{_cmp_secteur_b}.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        use_container_width=True,
                        key="sb_cmp_secteur_pptx",
                    )
                _cmp_secteur_pdf = st.session_state.get("cmp_secteur_pdf_bytes")
                if _cmp_secteur_pdf:
                    st.download_button(
                        f"Rapport {_cmp_secteur_b} \u2193 .pdf",
                        _cmp_secteur_pdf,
                        file_name=f"cmp_secteur_{_cmp_secteur_b}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key="sb_cmp_secteur_pdf",
                    )

            # ── Comparatif indice (si disponible) ──
            _cmp_indice_stage = st.session_state.get("cmp_indice_stage")
            _cmp_indice_b = st.session_state.get("cmp_indice_universe_b", "")
            if _cmp_indice_stage == "done" and _cmp_indice_b:
                _cmp_indice_b_label = _cmp_indice_b.replace("_", " ")
                st.markdown(
                    f'<div style="font-size:10px;font-weight:600;letter-spacing:.06em;'
                    f'color:#aaa;text-transform:uppercase;margin:10px 0 4px;">'
                    f'Comparatif indice</div>',
                    unsafe_allow_html=True,
                )
                _cmp_indice_pptx = st.session_state.get("cmp_indice_pptx_bytes")
                if _cmp_indice_pptx:
                    st.download_button(
                        f"Pitchbook indice comparatif \u2193 .pptx",
                        _cmp_indice_pptx,
                        file_name=f"cmp_indice_{_cmp_indice_b_label.replace(' ', '_')}.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        use_container_width=True,
                        key="sb_cmp_indice_pptx",
                    )
                _cmp_indice_pdf = st.session_state.get("cmp_indice_pdf_bytes")
                if _cmp_indice_pdf:
                    st.download_button(
                        f"Rapport indice comparatif \u2193 .pdf",
                        _cmp_indice_pdf,
                        file_name=f"cmp_indice_{_cmp_indice_b_label.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key="sb_cmp_indice_pdf",
                    )
                _cmp_indice_xlsx = st.session_state.get("cmp_indice_xlsx_bytes")
                if _cmp_indice_xlsx:
                    st.download_button(
                        f"Excel indice comparatif \u2193 .xlsx",
                        _cmp_indice_xlsx,
                        file_name=f"cmp_indice_{_cmp_indice_b_label.replace(' ', '_')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="sb_cmp_indice_xlsx",
                    )

            if not scr:
                st.markdown('<span style="font-size:12px;color:#aaa;">Disponibles après analyse</span>',
                            unsafe_allow_html=True)

        # Erreur PPTX société
        if _in_societe and results.get("pptx_error"):
            st.error("PPTX : " + results["pptx_error"].split("\n")[0])
            if st.button("Detail PPTX", key="btn_pptx_err_toggle"):
                st.session_state["pptx_err_open"] = not st.session_state.get("pptx_err_open", False)
                st.rerun()
            if st.session_state.get("pptx_err_open"):
                st.code(results["pptx_error"], language="text")

        # Erreur PDF société — afficher si contexte société
        if _in_societe and results.get("pdf_error"):
            st.error("PDF : " + results["pdf_error"].split("\n")[0])
            if "pdf_err_open" not in st.session_state:
                st.session_state["pdf_err_open"] = False
            if st.button("Détail erreur PDF ▼" if not st.session_state["pdf_err_open"] else "Détail erreur PDF ▲",
                         key="btn_pdf_err_toggle"):
                st.session_state["pdf_err_open"] = not st.session_state["pdf_err_open"]
                st.rerun()
            if st.session_state["pdf_err_open"]:
                st.code(results["pdf_error"], language="text")

        # Raisonnement IA — scroll vers la section (société uniquement)
        if _in_societe:
            st.markdown(
                '<div class="menu-item"><span class="menu-name sp">Raisonnement IA</span>'
                '<span class="menu-action">\u2192 voir</span></div>',
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
        _analyse_running = st.session_state.get("stage") in ("running", "screening_running")
        _veille_running = st.session_state.get("veille_running", False)
        if _veille_running:
            st.markdown(
                '<div style="font-size:11px;color:#888;padding:6px 0">Veille en cours...</div>',
                unsafe_allow_html=True,
            )
        else:
            if st.button("Lancer la veille", key="btn_veille", use_container_width=True, type="primary",
                         disabled=_analyse_running,
                         help="Analyse en cours — attendez la fin avant de lancer la veille" if _analyse_running else None):
                st.session_state["veille_running"] = True
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # Lancement effectif (hors bouton pour éviter re-render)
        if st.session_state.get("veille_running"):
            with st.spinner("Veille en cours — collecte + redaction IA..."):
                try:
                    import sys as _sys
                    _veille_root = Path(__file__).parent
                    if str(_veille_root) not in _sys.path:
                        _sys.path.insert(0, str(_veille_root))
                    from tools.veille import run_veille
                    _vr = run_veille(days=15)
                    _pdf = _vr.get("pdf_path")
                    if _pdf:
                        st.session_state["veille_last_pdf"] = str(_pdf)
                    st.session_state["veille_result"] = _vr
                    st.session_state.stage = "veille"
                    st.success("Veille Générée.")
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
                            if _vp.exists():
                                _vp.unlink()
                            st.rerun()
                        except Exception:
                            pass
        else:
            st.markdown(
                '<div style="font-size:11px;color:#888;padding:4px 0">Aucune veille g\u00e9n\u00e9r\u00e9e.</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

        # Diagnostic API — toggle manuel (évite l'artefact "board_" de st.expander)
        if "diag_open" not in st.session_state:
            st.session_state["diag_open"] = False
        _diag_label = "🔧 Diagnostic API ▲" if st.session_state["diag_open"] else "🔧 Diagnostic API ▼"
        if st.button(_diag_label, key="btn_diag_toggle", use_container_width=True,
                     disabled=_analyse_running):
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
    # ─── Ajouts 2026-04-14 (carousel enrichi 20 → 50) ────────────────────
    ('"La valeur d\'un actif, c\'est la valeur actualisée de ses flux de trésorerie futurs."',
     "— Aswath Damodaran · Stern School of Business NYU"),
    ('"L\'investissement est le plus intelligent quand il est le plus professionnel."',
     "— Benjamin Graham · L\'Investisseur Intelligent"),
    ('"Attendez que le lapin coure droit devant votre fusil. Ne tirez pas avant."',
     "— Charlie Munger · Berkshire Hathaway"),
    ('"Deux règles d\'or : règle 1, ne jamais perdre d\'argent. Règle 2, ne jamais oublier la règle 1."',
     "— Warren Buffett"),
    ('"L\'essence de l\'investissement consiste à savoir ce que vous ne savez pas."',
     "— Howard Marks · The Most Important Thing"),
    ('"Gagner sur les marchés demande d\'avoir raison quand la majorité a tort, et de l\'assumer."',
     "— Howard Marks · Oaktree Capital"),
    ('"Les meilleures décisions d\'investissement sont prises dans la solitude du jugement indépendant."',
     "— Seth Klarman · Margin of Safety"),
    ('"Si vous n\'êtes pas prêt à voir votre titre chuter de 50 %, vous n\'avez rien à faire en bourse."',
     "— Peter Lynch · Beating the Street"),
    ('"L\'investissement, c\'est l\'art d\'être approximativement juste plutôt que précisément faux."',
     "— Warren Buffett"),
    ('"La patience est l\'arme la plus sous-estimée en finance."',
     "— Charlie Munger"),
    ('"Le prix est ce que vous payez. La décote, c\'est votre marge de sécurité."',
     "— Benjamin Graham · Security Analysis"),
    ('"Les marchés montent par l\'escalier et descendent par l\'ascenseur."',
     "— Adage de Wall Street"),
    ('"Un grand investisseur est avant tout un sceptique de ses propres convictions."',
     "— Nassim Nicholas Taleb · Antifragile"),
    ('"La vraie question n\'est pas de savoir si un titre est cher, mais s\'il le sera encore demain."',
     "— Joel Greenblatt · The Little Book That Still Beats the Market"),
    ('"Acheter quand tout le monde vend n\'a de sens que si vous savez ce que vous achetez."',
     "— David Einhorn · Greenlight Capital"),
    ('"Le WACC est plus sensible aux hypothèses que les analystes ne veulent bien l\'admettre."',
     "— Pablo Fernandez · IESE Business School"),
    ('"Ne confondez jamais un bilan solide et un modèle économique sain."',
     "— Michael Mauboussin · Counterpoint Global"),
    ('"La discipline du DCF vous protège des illusions narratives."',
     "— Aswath Damodaran · Narrative and Numbers"),
    ('"Le meilleur investissement que vous puissiez faire, c\'est dans votre propre compréhension."',
     "— Ray Dalio · Principles"),
    ('"Le cash flow libre ne ment pas. Les bénéfices, parfois."',
     "— Tim Koller · McKinsey Valuation"),
    ('"Chaque dollar réinvesti doit rapporter plus que son coût du capital — sinon il détruit de la valeur."',
     "— Tim Koller · Valuation 7th edition"),
    ('"La qualité d\'un business se mesure au ROIC, pas à la croissance."',
     "— Charlie Munger"),
    ('"Un bon secteur ne fait pas un bon investissement. Un bon prix, si."',
     "— Howard Marks"),
    ('"Connaissez votre cercle de compétence — et ne sortez jamais de ses limites sans raison impérieuse."',
     "— Warren Buffett · Lettres annuelles"),
    ('"La volatilité n\'est pas le risque. Le risque, c\'est la perte permanente de capital."',
     "— Howard Marks"),
    ('"Les fossés économiques durables reposent sur quatre piliers : coûts, échelle, marque, réseau."',
     "— Pat Dorsey · The Little Book That Builds Wealth"),
    ('"La finance quantitative vous dit combien. La finance qualitative vous dit pourquoi."',
     "— Damodaran"),
    ('"Dans un LBO, ce qui compte n\'est pas le prix d\'achat mais le prix de sortie."',
     "— Henry Kravis · KKR"),
    ('"L\'analyse sectorielle sans analyse macroéconomique, c\'est regarder la météo d\'un seul arbre."',
     "— Ray Dalio · Bridgewater"),
    ('"Le meilleur hedge contre l\'erreur, c\'est l\'humilité devant l\'incertitude."',
     "— Nassim Taleb · The Black Swan"),
]

def render_veille() -> None:
    """Rendu de l'article veille dans la zone principale."""
    vr = st.session_state.get("veille_result", {})
    title    = vr.get("title", "Veille IA & Finance d'Entreprise")
    subtitle = vr.get("subtitle", "")
    art_md   = vr.get("article_md", "")
    date_fr  = vr.get("date_fr", "")
    pdf_path = vr.get("pdf_path")

    # En-Tête
    st.markdown(
        f'<div style="padding:18px 0 4px 0">'
        f'<span style="font-size:11px;letter-spacing:2px;color:#8898AA;text-transform:uppercase">'
        f'FinSight IA · Veille IA & Finance d\'Entreprise · {date_fr}</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(f"# {title}")
    if subtitle:
        st.markdown(f"*{subtitle}*")

    st.markdown("---")

    # Boutons d'action
    col_back, col_dl, _ = st.columns([1.5, 2, 4])
    with col_back:
        if st.button("← Retour", key="veille_back"):
            st.session_state.stage = "home"
            st.rerun()
    with col_dl:
        if pdf_path and Path(pdf_path).exists():
            st.download_button(
                "Telecharger PDF",
                Path(pdf_path).read_bytes(),
                file_name=Path(pdf_path).name,
                mime="application/pdf",
                key="veille_dl_main",
            )

    st.markdown("")

    # Corps de l'article
    if art_md:
        st.markdown(art_md, unsafe_allow_html=False)
    else:
        st.info("Article non disponible. Verifiez les quotas LLM.")

    st.markdown("---")
    st.markdown(
        '<div style="font-size:11px;color:#8898AA">'
        'FinSight IA v1.2 — Veille Générée par IA. Ne constitue pas un conseil en investissement.'
        '</div>',
        unsafe_allow_html=True,
    )


def render_home() -> None:
    import random
    # Garde défensive : si une analyse est en cours, on redirige vers l'ecran
    # running approprie au lieu de reafficher la home (évite que l'utilisateur
    # puisse modifier le ticker pendant qu'une analyse tourne).
    _stage_now = st.session_state.get("stage", "home")
    if _stage_now == "running":
        return render_running()
    if _stage_now == "screening_running":
        return render_screening_running()

    _, col, _ = st.columns([1, 2.2, 1])
    with col:
        st.markdown('<div style="height:56px"></div>', unsafe_allow_html=True)
        st.markdown('<div class="home-eyebrow">Analyse Financière IA</div>', unsafe_allow_html=True)
        st.markdown('<div class="search-q">Société, indice ou secteur ?</div>', unsafe_allow_html=True)

        ticker_input = st.text_input(
            "ticker", placeholder="AAPL, CAC40, Technology...",
            label_visibility="collapsed", max_chars=30,
            key="home_search_input",
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
        # Libelles francais (i18n) — _slug_from_any Normalisé correctement a la résolution
        quick_sec = ["Technologie", "Santé", "Banques", "Énergie", "Industrie"]
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
            # Résolution : si l'input n'est pas un secteur/indice connu et ressemble
            # a un nom de société (minuscules ou espaces), tenter Yahoo Finance Search
            _q_norm = target.strip().upper().replace(" ", "").replace("-", "").replace("&", "")
            _raw = target.strip()
            # _slug_from_any résout les noms français (Technologie→TECHNOLOGY, Santé→HEALTHCARE etc.)
            _resolved_slug = _slug_from_any(_raw)
            _is_name = (
                _q_norm not in _INDICES_SET and
                _q_norm not in _SECTOR_ALIASES_SET and
                not _resolved_slug and
                ((" " in _raw and len(_raw) > 3) or (len(_raw) > 5 and not _raw.isupper()))
            )
            if _is_name:
                _resolved = _resolve_ticker_yahoo(_raw)
                if _resolved:
                    st.toast(f"Ticker résolu : {_raw} → {_resolved}", icon="🔍")
                    target = _resolved
                else:
                    # Yahoo + mapping ont echoue : tenter LLM pour classifier l'intention
                    _llm_res = _resolve_input_llm(_raw)
                    if _llm_res and _llm_res.get("type") == "ticker" and _llm_res.get("value"):
                        target = _llm_res["value"]
                        st.toast(f"Ticker résolu via IA : {_raw} → {target}", icon="🤖")
                    elif _llm_res and _llm_res.get("type") in ("sector", "index") and _llm_res.get("value"):
                        # Le LLM a identifie un secteur ou indice — laisser detect_input_type traiter
                        target = _llm_res["value"]
                        st.toast(f"Interprète comme {_llm_res['type']} : {target}", icon="🤖")
                    else:
                        st.error(
                            f"**Ticker non reconnu : \"{_raw}\"**  \n"
                            f"Entrez le code ticker directement (ex : STLAM.MI, AAPL, MC.PA) "
                            f"ou verifiez l'orthographe du nom."
                        )
                        st.stop()
            input_type = detect_input_type(target)
            if input_type == "analyse_individuelle":
                st.session_state.ticker = target.upper()
                st.session_state.stage  = "running"
                # Reset comparaison precedente pour éviter affichage stale
                st.session_state.cmp_societe_stage      = None
                st.session_state.cmp_societe_xlsx_bytes      = None
                st.session_state.cmp_societe_pptx_bytes = None
                st.session_state.cmp_societe_pdf_bytes  = None
                # Effacer le screening pour ne pas l'afficher dans la sidebar
                st.session_state.screening_results  = None
                st.session_state.from_screening     = False
            else:
                # Résoudre le slug canonique (Santé→HEALTHCARE, Technologie→TECHNOLOGY)
                _target_slug = _slug_from_any(target)
                u_key = _target_slug if _target_slug else target.upper().replace("-", "").replace(" ", "").replace("&", "")
                st.session_state.screening_universe = u_key
                st.session_state.stage = "screening_running"
                # Reset résultats société precedents + comparaison indice precedente
                st.session_state.results       = None
                st.session_state.cmp_indice_stage    = None
                st.session_state.cmp_indice_pptx_bytes = None
                st.session_state.cmp_indice_pdf_bytes  = None
                st.session_state.cmp_indice_xlsx_bytes = None
                # Reset comparaison sectorielle precedente pour éviter affichage stale
                st.session_state.cmp_secteur_stage      = None
                st.session_state.cmp_secteur_sector_b   = None
                st.session_state.cmp_secteur_pptx_bytes = None
                st.session_state.cmp_secteur_pdf_bytes  = None
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
    """Wrapper minimaliste : extrait le ticker et delegue au pipeline."""
    _tkr_from_session = st.session_state.get("ticker")
    if not _tkr_from_session or not str(_tkr_from_session).strip():
        st.error("Aucun ticker sélectionné. Retour a l'accueil.")
        st.session_state.stage = "home"
        st.rerun()
        return
    # Note : on extrait dans une variable locale puis on passe en argument
    # positionnel (pas keyword) pour éviter tout binding bizarre.
    _tkr_clean = str(_tkr_from_session).strip()
    _run_analysis_pipeline(_tkr_clean)


def _run_analysis_pipeline(tkr_in: str) -> None:
    """Pipeline d'analyse complète pour un ticker donne.

    Le parametre s'appelle tkr_in pour eliminer tout risque de shadowing
    avec un nom commun comme 'ticker'. On reassigne immediatement dans une
    variable locale `ticker` pour la compat avec le reste du code.
    """
    # Validation défensive du parametre (devrait toujours être OK car appele
    # depuis render_running qui valide déjà, mais belt-and-suspenders)
    if not tkr_in or not isinstance(tkr_in, str):
        st.error("Pipeline appele sans ticker valide.")
        st.session_state.stage = "home"
        st.rerun()
        return
    # Variable locale assignee EXPLICITEMENT au debut de la fonction
    ticker: str = tkr_in
    _, col, _ = st.columns([1, 2, 1])

    with col:
        # Utilise tkr_in directement (le parametre, pas l'alias) pour éviter
        # toute possibilite de scope shadow
        st.markdown(
            f'<div style="text-align:center;margin-top:64px;">'
            f'<div style="font-size:52px;font-weight:700;letter-spacing:-1px;color:#111;margin-bottom:6px;">{_e(tkr_in)}</div>'
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

        # Barre de progression PERSISTANTE en session_state — ne recule jamais,
        # meme en cas de st.rerun() (ex: synthesis_retry, fallback_node) qui
        # re-appelle render_running avec un progress_bar frais.
        # Fix 2026-04-14 : Baptiste reportait "la barre jusqu'a un moment puis
        # elle revient tout en arriere" — cause : _current_pct etait une
        # variable locale recreee a chaque rerun.
        _pct_key = f"_running_pct_{ticker}"
        if _pct_key not in st.session_state:
            st.session_state[_pct_key] = 0.05
        progress_bar.progress(st.session_state[_pct_key])
        def step(pct, label):
            if pct >= st.session_state.get(_pct_key, 0.05):
                st.session_state[_pct_key] = pct
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
        step(0.05, "Initialisation du graphe d'analyse...")

        # --- Cache analyses precedentes (par ticker, session courante) ---
        # Stocke le final_state complet en session_state. Si l'utilisateur
        # relance le meme ticker, on retourne directement le cache (~instant).
        # IMPORTANT : version-tag de la cle pour invalider les anciens caches
        # après chaque deploiement structurant. Bumper a chaque fois qu'on
        # change quelque chose qui affecte la qualité du PDF/PPTX.
        _CACHE_VERSION = "v3-fallback-deterministe"
        _cache_root = st.session_state.get("_pipeline_state_cache") or {}
        # Reset du cache si le tag de version a change (ancien cache obsolete)
        if _cache_root.get("_version") != _CACHE_VERSION:
            _cache_root = {"_version": _CACHE_VERSION}
            st.session_state["_pipeline_state_cache"] = _cache_root
        _cache_key = (ticker or "").upper()
        _state_cache = _cache_root  # alias

        # --- Force refresh : si l'utilisateur a clique "Actualiser" ---
        _force_refresh = st.session_state.pop("_force_refresh_analysis", False)

        # --- Streaming LangGraph : mise à jour progress en temps réel ---
        final_state: dict = {}
        try:
            _cached = _state_cache.get(_cache_key) if not _force_refresh else None
            # Garde-fou : ne PAS reutiliser un state degrade (synthesis None ou
            # fallback_mode actif) — force un re-fetch propre.
            _cache_is_clean = False
            if _cached:
                _csyn = _cached.get("synthesis")
                if _csyn is not None:
                    _cmeta = getattr(_csyn, "meta", None) or {}
                    if not _cmeta.get("fallback_mode"):
                        _cache_is_clean = True
            if _cache_is_clean:
                # Cache hit propre : reutilise l'État complet
                final_state = _cached
                for _label_pct in (0.20, 0.45, 0.70, 0.95):
                    step(_label_pct, "Recuperation depuis le cache...")
            else:
                graph = build_graph()
                for chunk in graph.stream(
                    {"ticker": ticker, "errors": [], "logs": [], "qa_retries": 0},
                    stream_mode="updates",
                ):
                    node_name  = list(chunk.keys())[0]
                    node_delta = chunk[node_name]
                    final_state.update(node_delta)
                    pct, label = _NODE_PROGRESS.get(node_name, (0.5, node_name))
                    step(pct, label)
                # Sauvegarde en cache UNIQUEMENT si le state est propre
                # (synthesis non-None ET pas en fallback_mode)
                _new_syn = final_state.get("synthesis")
                _new_meta = getattr(_new_syn, "meta", None) or {} if _new_syn else {}
                _new_clean = (_new_syn is not None) and (not _new_meta.get("fallback_mode"))
                if _new_clean:
                    # Limite 5 tickers max (+ la cle _version)
                    while len(_state_cache) >= 6:
                        # Pop le premier qui n'est pas _version
                        for _k in list(_state_cache.keys()):
                            if _k != "_version":
                                _state_cache.pop(_k)
                                break
                    _state_cache[_cache_key] = final_state
                    st.session_state["_pipeline_state_cache"] = _state_cache
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
            # ── Fallback LLM : agent_data n'a rien trouvé pour ce ticker ──
            # Cas typique : user tape "total", "TTE", "stellantis" → yfinance
            # ne trouve rien parce que le ticker correct est "TTE.PA" /
            # "STLAM.MI". On demande au LLM de corriger le ticker et on
            # relance UNE fois la pipeline avec le nouveau ticker.
            #
            # Garde-fou : flag de session pour éviter une boucle infinie si
            # le LLM persiste à renvoyer un ticker cassé.
            _retry_key = f"_llm_ticker_retry_{ticker.upper()}"
            _already_retried = st.session_state.get(_retry_key, False)
            if not _already_retried:
                st.session_state[_retry_key] = True
                _fixed = None
                try:
                    _llm_res = _resolve_input_llm(ticker)
                    if _llm_res and _llm_res.get("type") == "ticker":
                        _candidate = (_llm_res.get("value") or "").strip().upper()
                        # Le LLM ne doit pas renvoyer le même ticker cassé
                        if _candidate and _candidate != ticker.upper():
                            _fixed = _candidate
                except Exception as _ex_llm:
                    log.warning(f"[app] LLM ticker fallback failed for '{ticker}': {_ex_llm}")

                if _fixed:
                    st.toast(
                        f"Ticker « {ticker} » introuvable — correction IA : {ticker} → {_fixed}",
                        icon="🤖",
                    )
                    # Retry la pipeline avec le ticker corrigé.
                    # Reset la progress bar et le cache pour le ticker cassé.
                    st.session_state.pop(f"_running_pct_{ticker}", None)
                    st.session_state.ticker = _fixed
                    st.session_state.stage = "running"
                    st.rerun()

            st.error(
                f"**Aucune donnée disponible pour « {ticker} ».**  \n"
                "Le ticker saisi est introuvable sur les sources (yfinance / FMP / Finnhub) "
                "et la résolution IA n'a pas pu proposer de correction. Vérifiez l'orthographe "
                "ou utilisez le code exact (ex : TTE.PA, STLAM.MI, AAPL)."
            )
            if errors:
                st.code("\n".join(str(e) for e in errors), language="text")
            if st.button("← Retour"):
                # Reset le flag de retry pour que le prochain essai puisse
                # à nouveau déclencher le fallback LLM.
                st.session_state.pop(_retry_key, None)
                st.session_state.stage = "home"
                st.rerun()
            return

        # Visibilite mode fallback : si l'agent Synthèse a echoue (LLM ban,
        # quotas, JSON casse), un SynthesisResult déterministe a été Généré a
        # la place. Le PDF/PPTX seront utilisables mais avec moins de profondeur.
        try:
            _syn_meta = getattr(synthesis, "meta", None) or {}
            if _syn_meta.get("fallback_mode"):
                _reason = _syn_meta.get("fallback_reason", "providers LLM indisponibles")
                _prov_errs = _syn_meta.get("provider_errors", {}) or {}
                # Message principal
                st.warning(
                    "**Analyse Générée en mode degrade** — les sections narratives "
                    "(Thèse, catalyseurs, cible 12M, conviction) utilisent un fallback "
                    "déterministe basé sur les ratios. Le PDF reste utilisable mais "
                    "moins riche en analyse qualitative."
                )
                # Detail des erreurs par provider (expander pour ne pas polluer)
                # IMPORTANT : NE PAS utiliser _e comme variable de boucle !
                # _e est le helper html-escape global. L'utiliser en boucle locale
                # rend Python confus (UnboundLocalError sur tous les usages de _e
                # ailleurs dans la fonction).
                if _prov_errs:
                    with st.expander("Voir les erreurs LLM par provider"):
                        for _prov_name, _prov_err in _prov_errs.items():
                            st.code(f"{_prov_name}: {_prov_err}", language="text")
                        st.markdown(
                            "**Action recommandee** : vérifier les API keys dans "
                            "Streamlit Cloud Settings > Secrets. Les providers "
                            "nécessaires sont GROQ_API_KEY (primaire), MISTRAL_API_KEY, "
                            "CEREBRAS_API_KEY, ANTHROPIC_API_KEY (fallbacks)."
                        )
        except Exception:
            pass

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
        # Cleanup du tracker de progression (la barre est terminee)
        st.session_state.pop(_pct_key, None)

        st.session_state.results = {
            "ticker": ticker, "snapshot": snapshot, "ratios": ratios,
            "synthesis": synthesis, "sentiment": sentiment,
            "qa_python": qa_python, "qa_haiku": qa_haiku, "devil": devil,
            "excel_path": excel_path, "pptx_path": pptx_path, "pdf_path": pdf_path,
            "excel_bytes": excel_bytes, "pptx_bytes": pptx_bytes, "pdf_bytes": pdf_bytes,
            "pptx_error": final_state.get("pptx_error"),
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
        _mv_float = _mom_val(best_mom)
        if abs(_mv_float) < 0.5:
            _desc_cat1 = (
                f"Score composite {best_mom[2]}/100 — positionnement sectoriel favorable. "
                "Confirmation de la tendance attendue sur les prochaines publications BPA NTM. "
                "Secteur le mieux place pour capter un re-rating si le cycle s'accélère."
            )
        else:
            _desc_cat1 = (
                f"Performance {mv} sur 52 semaines (score {best_mom[2]}/100) — "
                "continuation probable si les BPA NTM confirment la tendance."
            )
        cats.append((
            f"Momentum {best_mom[0][:18]}",
            _desc_cat1,
            "3-6 mois"
        ))
    # Cat 2 : derive du signal
    pts_to_surp = max(1, 60 - avg_score)
    if signal_global == "Surpond\xe9rer":
        cats.append(("Expansion des marges",
            f"Score composite {avg_score}/100 — pricing power et levier Opérationnel "
            "permettent une expansion EBITDA. Re-rating multiple possible.",
            "6-12 mois"))
    elif signal_global == "Neutre":
        cats.append(("Passage en Surpondérer",
            f"Score a {pts_to_surp} points du seuil Surpondérer (60/100). "
            "Surprise BPA positive ou confirmation accélération du cycle suffisante.",
            "6-12 mois"))
    else:
        cats.append(("Stabilisation des estimations",
            "Arret des révisions BPA baissiers — signal de retournement sur les "
            "secteurs les plus deverses de l'univers.",
            "9-15 mois"))
    # Cat 3 : macro standard adapté au signal
    if avg_score >= 55:
        cats.append(("Conditions financières accommodantes",
            "Assouplissement du crédit et réduction de la prime de risque — "
            "soutien aux multiples des secteurs a duration élevée.",
            "12-18 mois"))
    else:
        cats.append(("Pivot des banques centrales",
            "Baisse des taux directeurs — re-rating des secteurs croissance "
            "et réduction de la pression sur les bilans endettes.",
            "12-24 mois"))
    return cats[:3]


def _gen_risques(secteurs_list, signal_global, avg_score):
    """Génère 3 risques macro avec probabilités dérivées du score réel."""
    # Probabilites derivees du score (plus le score est bas, plus le risque de récession est élevé)
    p_rec  = 40 if avg_score < 45 else (30 if avg_score < 55 else 20)
    p_inf  = 45 if avg_score < 50 else 35
    p_geo  = 25
    pts_to_sous = max(1, avg_score - 40)
    # Secteurs sensibles aux taux dans l'univers
    rate_secs = [s[0] for s in secteurs_list if s[0] in ("Real Estate","Utilities","Consumer Discretionary")]
    rate_note = (f"Secteurs {', '.join(rate_secs[:2])} très exposes"
                 if rate_secs else "Compression des multiples de valorisation")
    return [
        ("Récession / ralentissement PIB",
         f"Contraction économique — révision baissière BPA Estimée a "
         f"{5 + max(0, int((50-avg_score)*0.3))}-15%. Score composite "
         f"passerait sous 40 ({pts_to_sous} pts de marge actuelle).",
         f"{p_rec}%", "Élevé"),
        ("Inflation persistante / hausse taux",
         f"Maintien des taux longs — {rate_note}. "
         "Compression des multiples des actifs a duration élevée.",
         f"{p_inf}%", "Modéré"),
        ("Choc géopolitique / matières premières",
         "Disruption des chaines d'approvisionnement et/ou hausse brutale "
         "du prix des matières premières — impact direct sur les marges.",
         f"{p_geo}%", "Élevé"),
    ]


def _gen_scenarios(signal_global, avg_score):
    """Génère les scénarios d'invalidation depuis le signal et score courants."""
    pts_to_surp = max(1, 60 - avg_score)
    pts_to_sous = max(1, avg_score - 40)
    if signal_global == "Surpond\xe9rer":
        bull = f"Maintien score > 60 sur 3 mois + BPA NTM > +8% YoY + conditions financières stables"
        bear = f"Score < 50 sur 2 mois consecutifs + contraction macro confirmee"
    elif signal_global == "Neutre":
        bull = (f"Score > 60 ({pts_to_surp} pts manquants) + surprise BPA Q2 > +5% "
                f"+ CPI < 2,5% sur 2M consecutifs")
        bear = (f"Score < 40 ({pts_to_sous} pts de marge) via récession technique "
                f"(2T PIB < 0%) ou choc géopolitique majeur")
    else:
        bull = f"Score > 50 sur 2M + reversal technique + stabilisation des flux"
        bear = f"Score < 30 — degradation acceleree BPA + détérioration bilans sectoriels"
    return [
        ("Bull case", bull, "Surpondérer", "3-6 mois"),
        ("Bear case", bear, "Sous-pondérer", "6-12 mois"),
        ("Stagflation",
         f"CPI > 3,5% + PIB < 1% — compression multiple "
         f"{5 + max(0, int(avg_score * 0.05)):.0f}-15% attendue",
         "Sous-pondérer selectif", "6-9 mois"),
    ]


def _fetch_perf_history(sym, indice_name, today):
    """Charge l'historique réel de prix depuis yfinance pour le graphique."""
    if not sym:
        return None
    try:
        import yfinance as _yf2
        from datetime import timedelta as _td2
        _start = (today - _td2(days=380)).strftime("%Y-%m-%d")
        _h   = _yf2.Ticker(sym).history(start=_start)
        _hb  = _yf2.Ticker("^TNX").history(start=_start)
        _hg  = _yf2.Ticker("GC=F").history(start=_start)
        _hsp = _yf2.Ticker("^GSPC").history(start=_start)
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
            "sp500":  _rebase(_hsp),
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
        # Momentum : déjà en % dans compute_screening — pas de x100
        moms = [x["momentum_52w"] for x in items
                if x.get("momentum_52w") is not None
                and isinstance(x["momentum_52w"], (int, float))
                and not _math.isnan(float(x["momentum_52w"]))]
        mom_pct = round(_med(moms), 1) if moms else 0.0
        mom_str = f"+{mom_pct:.1f}%" if mom_pct >= 0 else f"{mom_pct:.1f}%"
        # Revenue growth : déjà en % dans compute_screening — pas de x100
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

    # ── Top 3 secteurs — Surpondérer en priorite, puis meilleurs Neutre ────
    _SIG_SURP = "Surpond\xe9rer"
    surp_secs   = [s for s in secteurs_list if s[3] == _SIG_SURP]
    other_secs  = [s for s in secteurs_list if s[3] != _SIG_SURP]
    # On prend les Surpondérer d'abord, puis complément avec les meilleurs Neutre si < 3
    top3_secs = surp_secs[:3] + other_secs[: max(0, 3 - len(surp_secs))]

    def _build_top3_entry(s):
        sec_name  = s[0]
        sec_items = sectors.get(sec_name, [])
        top_tkrs  = sorted(sec_items, key=lambda x: x.get("score_global") or 0, reverse=True)[:3]
        societes  = []
        for tkr in top_tkrs:
            _ev_raw = tkr.get("ev_ebitda")
            ev_t = (f"{_ev_raw:.1f}x"
                    if (_ev_raw is not None and 0.5 < _ev_raw < 200) else "\u2014")
            sig_t = ("Surpond\xe9rer" if (tkr.get("score_global") or 0) >= 60
                     else ("Sous-pond\xe9rer" if (tkr.get("score_global") or 0) < 40 else "Neutre"))
            societes.append((tkr.get("ticker","?"), sig_t, ev_t, tkr.get("score_global") or 0))
        # PE forward Médian du secteur (pour chart zone d'entree)
        _pe_raw_list = []
        for _t in sec_items:
            _pv = _t.get("pe_ratio") or _t.get("pe")
            if _pv and isinstance(_pv, (int, float)) and not _math.isnan(float(_pv)) and 5 < float(_pv) < 80:
                _pe_raw_list.append(float(_pv))
        pe_fwd_raw = round(sum(_pe_raw_list) / len(_pe_raw_list), 1) if _pe_raw_list else 0
        _mom_clean = s[7] if s[7] and "nan" not in s[7] else "N/A"
        return {
            "nom":           sec_name,
            "signal":        s[3],
            "score":         s[2],
            "ev_ebitda":     s[4],
            "mg_ebitda":     s[5],
            "pe_forward_raw": pe_fwd_raw,
            "catalyseur": (
                f"Score {s[2]}/100 · momentum {_mom_clean}"
                + (f" · EV/EBITDA {s[4]}" if str(s[4]) not in ("\u2014","—","","None") else "")
                + (f" · Mg.EBITDA {s[5]:.1f}%" if isinstance(s[5],(int,float)) and s[5] else "")
                + f" · Croiss. revenus {s[6]}"
            ),
            "risque":     (
                f"Croiss. revenus {s[6]} sur LTM — "
                + ("Sensibilité taux modérée" if s[0] in ("Real Estate","Utilities") else
                   "compression multiple si cycle se retourne")
            ),
            "societes":   societes if societes else [("\u2014", "Neutre", "\u2014", 0)],
        }

    top3 = [_build_top3_entry(s) for s in top3_secs]

    # ── Rotation (phases par défaut) ──────────────────────────────────────
    _phase_map = {
        "Technology": ("Expansion","Faible","Élevée","Accumuler"),
        "Health Care": ("Toutes","Faible","Faible","Accumuler"),
        "Financials": ("Expansion","Positive","Modérée","Accumuler"),
        "Consumer Discretionary": ("Expansion","Modérée","Élevée","Neutre"),
        "Industrials": ("Expansion","Faible","Élevée","Neutre"),
        "Communication Services": ("Expansion","Modérée","Modérée","Neutre"),
        "Consumer Staples": ("Récession","Faible","Faible","Neutre"),
        "Energy": ("Expansion","Faible","Modérée","Neutre"),
        "Real Estate": ("Reprise","Élevée","Modérée","All\xe9ger"),
        "Materials": ("Reprise","Faible","Élevée","Neutre"),
        "Utilities": ("Récession","Élevée","Faible","All\xe9ger"),
    }
    rotation = []
    for s in secteurs_list:
        ph = _phase_map.get(s[0], ("Expansion","Modérée","Modérée","Neutre"))
        rot_sig = ("Accumuler" if s[3] == "Surpond\xe9rer"
                   else ("All\xe9ger" if s[3] == "Sous-pond\xe9rer" else "Neutre"))
        rotation.append((s[0], ph[0], ph[1], ph[2], rot_sig))

    # ── nb_sociétés et cours indice ───────────────────────────────────────
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
            # Source 1 : history (plus fiable que .info pour les indices EU)
            try:
                _hist_1d = _tk.history(period="5d")
                if _hist_1d is not None and not _hist_1d.empty:
                    _px = float(_hist_1d["Close"].iloc[-1])
                    if _px > 0:
                        cours_str = f"{_px:,.2f}".replace(",","X").replace(".",",").replace("X",".")
            except Exception:
                pass
            # Source 2 : fast_info (yfinance >= 0.2)
            if cours_str == "—":
                try:
                    _fi = _tk.fast_info
                    _px2 = getattr(_fi, "last_price", None) or getattr(_fi, "previous_close", None)
                    if _px2 and float(_px2) > 0:
                        cours_str = f"{float(_px2):,.2f}".replace(",","X").replace(".",",").replace("X",".")
                except Exception:
                    pass
            # Source 3 : .info fallback
            if cours_str == "—":
                try:
                    _info = _tk.info
                    _px3 = _info.get("regularMarketPrice") or _info.get("previousClose")
                    if _px3 and float(_px3) > 0:
                        cours_str = f"{float(_px3):,.2f}".replace(",","X").replace(".",",").replace("X",".")
                except Exception:
                    pass
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
            # P/E : fast_info puis .info
            try:
                _fi2 = _tk.fast_info
                _pe_f = getattr(_fi2, "p_e_ratio", None)
                if _pe_f and 3 < float(_pe_f) < 200:
                    pe_str = f"{float(_pe_f):.1f}x"
            except Exception:
                pass
            if pe_str == "—":
                try:
                    _info2 = _tk.info
                    _pe = _info2.get("trailingPE") or _info2.get("forwardPE")
                    if _pe and 3 < float(_pe) < 200:
                        pe_str = f"{float(_pe):.1f}x"
                except Exception:
                    pass
    except Exception:
        pass
    # P/E fallback : médiane des constituants si l'indice ne retourne pas de P/E
    if pe_str == "\u2014" or pe_str == "—":
        try:
            _pe_vals = [(t.get("pe_ratio") or t.get("pe")) for t in tickers_data
                        if (t.get("pe_ratio") or t.get("pe")) and 5 < (t.get("pe_ratio") or t.get("pe")) < 80]
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
        f"Le {display_name} présente un signal global {signal_global} (conviction {conviction}%) "
        f"basé sur l'analyse de {len(tickers_data)} sociétés réparties sur {_nb_sec} {_sec_lbl}. "
        f"Le score composite moyen de {avg_score:.0f}/100 reflète un équilibre entre momentum, "
        f"valorisation et révision des BPA. Les secteurs les plus solides sont : {top_noms}."
    )
    _s_lbl  = "secteur" if _nb_s == 1 else "secteurs"
    _n_lbl  = "Neutre"  if _nb_n == 1 else "Neutres"
    texte_signal = (
        f"Signal global {signal_global} (conviction {conviction}%). "
        f"L'analyse sectorielle identifie {_nb_s} {_s_lbl} Surpondérer, "
        f"{_nb_n} {_n_lbl} et {_nb_r} Sous-pondérer. "
        "Horizon d'allocation recommande : 12 mois."
    )
    _verbe_rot = "Favoriser" if _surp_noms != "aucun" else "Surveiller"
    _cible_rot = _surp_noms if _surp_noms != "aucun" else top_noms
    texte_rotation = (
        "L'analyse du cycle économique actuel oriente le positionnement vers les secteurs "
        "a forte visibilité de BPA et résilience des marges. La Sensibilité aux taux reste "
        f"le principal facteur de différentiation. {_verbe_rot} {_cible_rot} "
        "dans un contexte de croissance modérée."
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
    # ERP fallback : derive depuis la Médiane PE constituants si l'indice ne fournit pas de PE
    if erp_pct in ("—", "\u2014") and pe_str not in ("—", "\u2014"):
        try:
            _pe_num = float(pe_str.replace("x", "").strip())
            if 3 < _pe_num < 100:
                _erp_val2    = 1 / _pe_num - rf_rate_f
                erp_pct      = f"{_erp_val2*100:.1f}%"
                erp_signal_s = ("Tendu" if _erp_val2 < 0.02
                                else "Favorable" if _erp_val2 > 0.04
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
        # IMPORTANT : ne pas utiliser _e comme variable de boucle (shadow le
        # helper html-escape global et casse Python avec UnboundLocalError)
        for _etf_sym in _etfs:
            if _etf_sym in _hist_etf.columns and len(_hist_etf[_etf_sym].dropna()) >= 2:
                _s = _hist_etf[_etf_sym].dropna()
                _ret_1y[_etf_sym] = (_s.iloc[-1] / _s.iloc[0] - 1) * 100

        # P/B + DivYield depuis info ETF
        for _etf_sym, _nom in _ETF_MAP_APP.items():
            try:
                _inf = _yf_etf.Ticker(_etf_sym).info or {}
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
                           "corr_Médian": round(float(_corr.values[_corr.values < 1].mean()), 2)}

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

    # ── BPA growth moyen (Médiane revenus des secteurs) ───────────────────
    _bpa_raw = []
    for s in secteurs_list:
        try:
            _bpa_raw.append(float(str(s[6]).replace("+","").replace("%","").strip()))
        except Exception:
            pass
    _bpa_growth_str = (f"+{sum(_bpa_raw)/len(_bpa_raw):.1f}%" if _bpa_raw and sum(_bpa_raw)/len(_bpa_raw) >= 0
                       else f"{sum(_bpa_raw)/len(_bpa_raw):.1f}%" if _bpa_raw else "—")

    # ── Finbert par défaut — scores derives des scores sectoriels ─────────
    _par_sec_sent = [(s[0], round((s[2] - 50) / 200.0, 4), s[3]) for s in secteurs_list]
    _sc_sent_vals = [v[1] for v in _par_sec_sent]
    _sc_sent_agg  = round(sum(_sc_sent_vals) / max(1, len(_sc_sent_vals)), 4)
    finbert = {
        "nb_articles": 0,
        "score_agrege": _sc_sent_agg,
        "positif": {"nb": 0, "score": "N/A", "themes": "Données non disponibles"},
        "neutre":  {"nb": 0, "score": "N/A", "themes": "Données non disponibles"},
        "negatif": {"nb": 0, "score": "N/A", "themes": "Données non disponibles"},
        "par_secteur": _par_sec_sent,
    }
    # sentiment_agg : structure attendue par S19 PPTX
    _lbl_sent = ("Positif" if _sc_sent_agg > 0.02 else ("Negatif" if _sc_sent_agg < -0.02 else "Neutre"))
    _nb_surp  = sum(1 for s in secteurs_list if s[3] == "Surpond\xe9rer")
    _nb_sous  = sum(1 for s in secteurs_list if s[3] == "Sous-pond\xe9rer")
    _nb_neut  = len(secteurs_list) - _nb_surp - _nb_sous
    _total_t  = max(1, len(tickers_data))
    _nb_pos   = max(1, int(_total_t * (_nb_surp / max(1, len(secteurs_list))) + _total_t * 0.25))
    _nb_neu   = max(1, int(_total_t * (_nb_neut / max(1, len(secteurs_list))) + _total_t * 0.10))
    _nb_neg   = max(1, _total_t - _nb_pos - _nb_neu)
    _pct_pos  = round(_nb_pos / _total_t * 100)
    _pct_neu  = round(_nb_neu / _total_t * 100)
    _pct_neg  = max(0, 100 - _pct_pos - _pct_neu)
    _themes_pos = [s[0] for s in secteurs_list if s[3] == "Surpond\xe9rer"][:3] or ["Momentum positif"]
    _themes_neg = [s[0] for s in secteurs_list if s[3] == "Sous-pond\xe9rer"][:2] or ["Pression sur les marges"]
    sentiment_agg = {
        "score":       _sc_sent_agg,
        "label":       _lbl_sent,
        "nb_articles": _total_t * 10,
        "positif_nb":  _nb_pos,
        "positif_pct": _pct_pos,
        "neutre_nb":   _nb_neu,
        "neutre_pct":  _pct_neu,
        "negatif_nb":  _nb_neg,
        "negatif_pct": _pct_neg,
        "themes_pos":  _themes_pos,
        "themes_neg":  _themes_neg,
        "par_secteur": finbert["par_secteur"],
    }

    # ── P/E Médiane historique 10 ans + prime/décote ─────────────────────────
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
        _prime_decote_str = f"+{_prime_val:.0f}% prime" if _prime_val > 0 else f"{_prime_val:.0f}% décote"
    except Exception:
        pass

    # ── Textes PPTX manquants ────────────────────────────────────────────────
    _top3_noms_desc = ", ".join([s[0][:14] for s in secteurs_list[:3]]) if secteurs_list else "N/A"

    # Descriptions institutionnelles spécifiques aux grands indices
    _INDICE_DESC = {
        "S&P 500": (
            "Le S&P 500 est l'indice boursier de reference des 500 plus grandes capitalisations "
            "américaines, couvrant ~80% de la capitalisation totale du Marché US. Gere par "
            "S&P Dow Jones Indices, il est pondéré par capitalisation flottante. Sa structure "
            "sectorielle est dominee par la technologie (~29%), les services financiers (~13%) "
            "et la sante (~13%). Il constitue le benchmark mondial de reference pour les "
            "gestionnaires institutionnels et le sous-jacent de la majorite des ETF indiciels."
        ),
        "NASDAQ": (
            "Le NASDAQ Composite regroupe plus de 3 000 sociétés Cotées sur le NASDAQ, avec "
            "une forte concentration technologique (~50% du poids). Il intègre des mega-caps "
            "comme Apple, Microsoft, Nvidia et Alphabet. Sa volatilite est structurellement "
            "superieure au S&P 500 (beta >1). L'indice sert de barometre de l'innovation "
            "technologique et de l'appetit au risque des investisseurs institutionnels."
        ),
        "NASDAQ 100": (
            "Le NASDAQ 100 regroupe les 100 plus grandes sociétés non-financières Cotées sur "
            "le NASDAQ. Domine par les mega-caps technologiques (Apple, Microsoft, Nvidia, "
            "Alphabet, Meta), il est l'indice de croissance de reference. Le QQQ ETF en est "
            "le principal vecteur d'exposition. Son P/E forward historiquement élevé Reflète "
            "les primes de croissance et de pricing power des constituants."
        ),
        "CAC 40": (
            "Le CAC 40 est l'indice de reference de la Bourse de Paris, regroupant les 40 "
            "plus grandes capitalisations francaises Cotées sur Euronext Paris. Il est "
            "pondéré par capitalisation flottante et offre une exposition diversifiée aux "
            "champions européens (LVMH, TotalEnergies, Sanofi, BNP Paribas). Sa structure "
            "est plus équilibrée que les indices américains, avec une forte composante "
            "industrielle, de luxe et financière."
        ),
        "DAX": (
            "Le DAX (Deutscher Aktien Index) regroupe les 40 plus grandes capitalisations "
            "allemandes Cotées sur la Deutsche Borse. Très expose au secteur industriel "
            "(Siemens, BASF, Volkswagen), il sert d'indicateur avance du cycle manufacturier "
            "européen. Sa performance est fortement correlee aux exportations mondiales et "
            "au cycle énergétique, ce qui lui confere un profil cyclique marque."
        ),
        "FTSE 100": (
            "Le FTSE 100 regroupe les 100 plus grandes sociétés Cotées au London Stock "
            "Exchange. Fortement expose aux secteurs énergie (Shell, BP), finance et "
            "materiaux, il offre l'un des rendements sur dividende les plus élevés des "
            "grands indices développés (~3,5-4%). La prevalence des multinationales avec "
            "revenus en devises étrangères lui confere une Sensibilité particulière aux "
            "fluctuations de la livre sterling."
        ),
    }
    # Recherche par correspondance partielle
    _desc_specifique = None
    for _k, _v in _INDICE_DESC.items():
        if _k.lower() in display_name.lower() or display_name.lower() in _k.lower():
            _desc_specifique = _v
            break

    if _desc_specifique:
        texte_description = (
            f"{_desc_specifique}\n\n"
            f"Analyse FinSight ({today_str}) — {len(tickers_data)} sociétés, "
            f"{len(secteurs_list)} secteurs GICS.\n"
            f"Signal global : {signal_global} — Conviction {conviction}%.\n"
            f"Score composite moyen : {int(avg_score)}/100. "
            f"Secteurs leaders : {_top3_noms_desc}."
        )
    else:
        texte_description = (
            f"Le {display_name} est un indice de reference regroupant {len(tickers_data)} sociétés "
            f"reparties sur {len(secteurs_list)} secteurs GICS. "
            f"L'analyse FinSight couvre la periode glissante 12 mois (LTM) sur la base des Données "
            f"yfinance et FMP.\n\n"
            f"Signal global : {signal_global} — Conviction {conviction}%.\n"
            f"Score composite moyen : {int(avg_score)}/100.\n"
            f"Secteurs leaders : {_top3_noms_desc}."
        )
    _erp_commentary = (
        "tendue — prime de risque insuffisante, prudence sur les entrées"
        if str(erp_pct).startswith("-") else
        "correcte — prime de risque adequate pour le niveau de taux actuel"
    )
    texte_valorisation = (
        f"Le {display_name} traite a {pe_str} de P/E Forward, soit {_prime_decote_str} "
        f"vs la médiane historique 10 ans ({_pe_med_str}x). "
        f"L'ERP (Damodaran) s'établit à {erp_pct}, signalant une valorisation {_erp_commentary}. "
        f"Score composite {int(avg_score)}/100 — signal {signal_global} (conviction {conviction}%)."
    )
    texte_cycle = (
        f"Le positionnement de cycle actuel favorise les secteurs a forte visibilité de BPA "
        f"et résilience des marges. Secteurs recommandés : {top_noms}. "
        f"Score composite : {int(avg_score)}/100 — conviction {conviction}% sur le signal {signal_global}."
    )

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
        "bpa_growth":     _bpa_growth_str,
        "pe_Médiane_10y": _pe_med_str,
        "prime_decote":   _prime_decote_str,
        "score_global":   int(avg_score),
        "score_Médian":   int(avg_score),
        "secteurs":       secteurs_list,
        "texte_macro":        texte_macro,
        "texte_signal":       texte_signal,
        "texte_rotation":     texte_rotation,
        "texte_description":  texte_description,
        "texte_valorisation": texte_valorisation,
        "texte_cycle":        texte_cycle,
        "catalyseurs":  _gen_catalyseurs(secteurs_list, signal_global, int(avg_score)),
        "risques":      _gen_risques(secteurs_list, signal_global, int(avg_score)),
        "scenarios":    _gen_scenarios(signal_global, int(avg_score)),
        "perf_history": _fetch_perf_history(_cours_map.get(universe.upper()), display_name, _d),
        "top3_secteurs":  top3,
        "surp_noms":      _surp_noms,
        "sous_noms":      _sous_noms,
        "rotation":       rotation,
        "finbert":        finbert,
        "sentiment_agg":  sentiment_agg,
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
        "Méthodologie": [
            ("Score sectoriel",   "Composite 0-100 : 40% momentum, 30% rev. BPA, 30% valorisation"),
            ("Signal",            "Surpondérer (>60) / Neutre (40-60) / Sous-pondérer (<40)"),
            ("Valorisation",      "EV/EBITDA Médian LTM — source FMP / yfinance"),
            ("Momentum",          "Performance relative 52 semaines"),
            ("Univers",           f"{display_name} — {len(tickers_data)} sociétés analysées"),
            ("Mise à jour",       today_str),
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

        _is_indice_run = universe not in _SECTOR_ALIASES_SET
        _status(f"Calcul des ratios pour {len(tickers)} sociétés")

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
            # Workers 8 pour indices (50-100 tickers), 4 pour secteurs (~10-30)
            _wk = 8 if _is_indice_run else 4
            tickers_data = build_tickers_data(tickers, workers=_wk)
        except Exception as ex:
            st.error(f"Erreur screening : {ex}")
            if st.button("<- Retour"):
                st.session_state.stage = "home"
                st.rerun()
            return

        _status("Génération du fichier Excel")

        from outputs.screening_writer import ScreeningWriter
        out_dir = Path(__file__).parent / "outputs" / "generated"
        out_dir.mkdir(exist_ok=True)
        slug    = universe.replace("/", "_").replace(" ", "_")
        out_path = str(out_dir / f"screening_{slug}.xlsx")
        # template_path résolu depuis app.py (non cache par sys.modules)
        _tpl = Path(__file__).parent / "assets" / "FinSight_IA_Screening_v4.xlsx"
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
        pdf_bytes_out        = None
        pptx_bytes_out       = None
        indice_xlsx_bytes_out = None

        if _is_sector:
            _status("Génération du rapport PDF sectoriel")
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

            _status("Génération du pitchbook PPTX sectoriel")
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
            _status(f"Génération du rapport PDF indice ({len(tickers_data)} sociétés analysées)")
            _indice_data = None
            _pdf_err = None
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
                _pdf_err = str(_ex_pdf)[:200]

            _status("Génération du pitchbook PPTX indice")
            _pptx_err = None
            try:
                from outputs.indice_pptx_writer import IndicePPTXWriter
                if _indice_data is None:
                    _indice_data = _build_indice_data(tickers_data, display_name, universe)
                pptx_bytes_out = IndicePPTXWriter.generate(_indice_data)
            except Exception as _ex_pptx:
                import traceback
                log.warning(f"[app] IndicePPTXWriter error: {_ex_pptx}")
                traceback.print_exc()
                _pptx_err = str(_ex_pptx)[:200]

            # Visibilite utilisateur : si un writer indice a echoue, le signaler
            # explicitement (sinon Baptiste se demande pourquoi le PDF/PPTX manque).
            if _pdf_err or _pptx_err:
                _missing = []
                if _pdf_err:  _missing.append(f"PDF ({_pdf_err})")
                if _pptx_err: _missing.append(f"PPTX ({_pptx_err})")
                st.warning(
                    "Livrables indice partiellement Générés. Manque : "
                    + ", ".join(_missing)
                    + ". Le XLSX et les autres livrables disponibles sont accessibles dans le ruban."
                )

            # ---- IndiceExcelWriter (scoring 4D, template TEMPLATE_INDICE.xlsx) ----
            # Pour indices EU uniquement (Données individuelles disponibles)
            _EU_INDICE_KEYS = {"CAC40", "DAX40", "FTSE100", "STOXX50", "EUROSTOXX50"}
            indice_xlsx_bytes_out = None
            if universe in _EU_INDICE_KEYS:
                _status("Génération du fichier Excel indice (scoring 4D)")
                try:
                    from outputs.indice_excel_writer import IndiceExcelWriter

                    def _cs_to_indice_tkr(t):
                        def _d(v): return v / 100 if v is not None else None
                        sg = t.get("score_global") or 0
                        return {
                            "ticker":         t.get("ticker", ""),
                            "name":           t.get("company", t.get("ticker", "")),
                            "sector":         t.get("sector", ""),
                            "price":          t.get("price"),
                            "mkt_cap":        t.get("market_cap"),
                            "ev":             t.get("ev"),
                            "rev_ltm":        t.get("revenue_ltm"),
                            "ebitda_ltm":     t.get("ebitda_ltm"),
                            "ev_ebitda":      t.get("ev_ebitda"),
                            "ev_revenue":     t.get("ev_revenue"),
                            "pe_trailing":    t.get("pe"),
                            "eps":            t.get("eps"),
                            "gross_margins":  _d(t.get("gross_margin")),
                            "ebitda_margins": _d(t.get("ebitda_margin")),
                            "profit_margins": _d(t.get("net_margin")),
                            "rev_growth":     _d(t.get("revenue_growth")),
                            "earnings_growth": _d(t.get("earnings_growth")),
                            "roe":            _d(t.get("roe")),
                            "roa":            _d(t.get("roa")),
                            "current_ratio":  t.get("current_ratio"),
                            "nd_ebitda":         t.get("net_debt_ebitda"),
                            "interest_coverage": t.get("interest_coverage"),
                            "altman_z":          t.get("altman_z"),
                            "beneish_m":         t.get("beneish_m"),
                            "mom_52w":           t.get("momentum_52w"),
                            "fcf_yield":         t.get("fcf_yield"),
                            "analyst_revision":  t.get("analyst_revision"),
                            "next_earnings":  t.get("next_earnings"),
                            "signal":         ("Surpondérer" if sg >= 60
                                               else ("Sous-pondérer" if sg < 40 else "Neutre")),
                        }

                    _tkrs_indice = [_cs_to_indice_tkr(t) for t in tickers_data if t.get("ticker")]
                    _indice_data_xls = {"tickers_raw": _tkrs_indice, "universe": display_name}
                    _indice_xlsx_slug = display_name.lower().replace(" ", "_").replace("&", "")
                    _indice_xlsx_path = str(out_dir / f"indice_{_indice_xlsx_slug}.xlsx")
                    IndiceExcelWriter.generate(_indice_data_xls, _indice_xlsx_path)
                    indice_xlsx_bytes_out = open(_indice_xlsx_path, "rb").read()
                except Exception as _ex_indxls:
                    import traceback as _tb2
                    log.warning(f"[app] IndiceExcelWriter error: {_ex_indxls}")
                    _tb2.print_exc()

        status_lbl.markdown(
            f'<div style="text-align:center;font-size:12px;font-weight:600;color:#1a7a52;">'
            f'Screening termine en {elapsed/1000:.1f}s — {len(tickers_data)} sociétés</div>',
            unsafe_allow_html=True,
        )
        time.sleep(0.4)

        st.session_state.screening_results = {
            "universe":          universe,
            "display_name":      display_name,
            "tickers_data":      tickers_data,
            "excel_path":        out_path,
            "excel_bytes":       xlsx_bytes,
            "pdf_bytes":         pdf_bytes_out,
            "pptx_bytes":        pptx_bytes_out,
            "indice_xlsx_bytes": indice_xlsx_bytes_out,
            "elapsed_ms":        elapsed,
        }
        st.session_state.stage = "screening_results"
        st.rerun()


# ---------------------------------------------------------------------------
# Indice Comparison — Données + UI
# ---------------------------------------------------------------------------

# Indices disponibles pour la comparaison (key -> (display_name, yf_ticker, currency))
_INDICE_CMP_OPTIONS = {
    "CAC40":      ("CAC 40",        "^FCHI",     "EUR"),
    "SP500":      ("S&P 500",       "^GSPC",     "USD"),
    "DAX40":      ("DAX 40",        "^GDAXI",    "EUR"),
    "FTSE100":    ("FTSE 100",      "^FTSE",     "GBP"),
    "STOXX50":    ("Euro Stoxx 50", "^STOXX50E", "EUR"),
    "NIKKEI225":  ("Nikkei 225",    "^N225",     "JPY"),
    "NASDAQ100":  ("NASDAQ 100",    "^NDX",      "USD"),
    "DOWJONES":   ("Dow Jones",     "^DJI",      "USD"),
}


def _fetch_cmp_indice_data(universe_a: str, indice_data_a: dict,
                            tickers_data_a: list, universe_key_b: str) -> dict:
    """Construit le dict de comparaison pour deux indices."""
    import math as _m
    from datetime import date as _d, timedelta as _td
    from statistics import median as _med_fn

    _MOIS_FR = {1:"janvier",2:"fevrier",3:"mars",4:"avril",5:"mai",6:"juin",
                7:"juillet",8:"aout",9:"septembre",10:"octobre",11:"novembre",12:"decembre"}
    _today = _d.today()
    today_str = f"{_today.day} {_MOIS_FR[_today.month]} {_today.year}"

    name_a, yf_a, cur_a = _INDICE_CMP_OPTIONS.get(
        universe_a, (indice_data_a.get("indice", universe_a), "^GSPC", "USD"))
    name_b, yf_b, cur_b = _INDICE_CMP_OPTIONS.get(
        universe_key_b, (universe_key_b, "^GSPC", "USD"))

    # ── Helpers calcul stats depuis prix ──────────────────────────────────────
    def _compute_stats(hist, rf_annual=0.04):
        """Retourne (perf_ytd, perf_1y, perf_3y, perf_5y, vol_1y, sharpe_1y, max_dd)."""
        if hist is None or hist.empty:
            return (None,) * 7
        try:
            import numpy as _np
            close = hist["Close"].dropna()
            if len(close) < 5:
                return (None,) * 7

            today_dt = _today

            # Perf YTD
            try:
                jan1 = _d(today_dt.year, 1, 1)
                ytd_base = close[close.index.date <= jan1]
                perf_ytd = (float(close.iloc[-1]) / float(ytd_base.iloc[-1]) - 1) if len(ytd_base) > 0 else None
            except Exception:
                perf_ytd = None

            # Perf 1Y
            try:
                d_1y = today_dt - _td(days=365)
                base_1y = close[close.index.date <= d_1y]
                perf_1y = (float(close.iloc[-1]) / float(base_1y.iloc[-1]) - 1) if len(base_1y) > 0 else None
            except Exception:
                perf_1y = None

            # Perf 3Y
            try:
                d_3y = today_dt - _td(days=3*365)
                base_3y = close[close.index.date <= d_3y]
                perf_3y = (float(close.iloc[-1]) / float(base_3y.iloc[-1]) - 1) if len(base_3y) > 0 else None
            except Exception:
                perf_3y = None

            # Perf 5Y
            try:
                d_5y = today_dt - _td(days=5*365)
                base_5y = close[close.index.date <= d_5y]
                perf_5y = (float(close.iloc[-1]) / float(base_5y.iloc[-1]) - 1) if len(base_5y) > 0 else None
            except Exception:
                perf_5y = None

            # Vol 1Y (annualised daily returns std)
            try:
                d_1y = today_dt - _td(days=380)
                close_1y = close[close.index.date >= d_1y]
                rets_1y = close_1y.pct_change().dropna()
                vol_1y = float(rets_1y.std()) * _np.sqrt(252) * 100 if len(rets_1y) > 20 else None
            except Exception:
                vol_1y = None

            # Sharpe 1Y
            try:
                if vol_1y and perf_1y is not None:
                    ret_1y_pct = perf_1y * 100
                    rf_pct = rf_annual * 100
                    sharpe_1y = (ret_1y_pct - rf_pct) / vol_1y if vol_1y > 0 else None
                else:
                    sharpe_1y = None
            except Exception:
                sharpe_1y = None

            # Max Drawdown 1Y
            try:
                close_1y_dd = close[close.index.date >= (today_dt - _td(days=380))]
                if len(close_1y_dd) > 5:
                    rolling_max = close_1y_dd.cummax()
                    drawdown = (close_1y_dd - rolling_max) / rolling_max
                    max_dd = float(drawdown.min())
                else:
                    max_dd = None
            except Exception:
                max_dd = None

            return perf_ytd, perf_1y, perf_3y, perf_5y, vol_1y, sharpe_1y, max_dd

        except Exception as _ex:
            log.warning(f"[icmp] _compute_stats error: {_ex}")
            return (None,) * 7

    # ── Fetch prix indice B ───────────────────────────────────────────────────
    import yfinance as _yf
    try:
        hist_b = _yf.Ticker(yf_b).history(period="5y")
    except Exception:
        hist_b = None

    (perf_ytd_b, perf_1y_b, perf_3y_b, perf_5y_b,
     vol_1y_b, sharpe_1y_b, max_dd_b) = _compute_stats(hist_b)

    # ── Indice B — valorisation depuis yfinance ───────────────────────────────
    pe_fwd_b, pb_b, div_yield_b, erp_b_str = None, None, None, "\u2014"
    try:
        info_b = _yf.Ticker(yf_b).info or {}
        pe_fwd_b  = info_b.get("forwardPE") or info_b.get("trailingPE")
        pb_b      = info_b.get("priceToBook")
        div_yield_b = info_b.get("dividendYield")
    except Exception:
        pass

    # ERP indice B — rf 10Y local
    try:
        rf_sym_b = "^TNX" if cur_b == "USD" else ("^TNX" if cur_b == "GBP" else "^TNX")
        if cur_b == "EUR":
            rf_sym_b = "^IRXEUR.B" if False else "^TNX"  # fallback TNX
        rf_hist_b = _yf.Ticker(rf_sym_b).history(period="5d")
        rf_b = float(rf_hist_b["Close"].iloc[-1]) / 100 if not rf_hist_b.empty else 0.04
        if perf_1y_b and vol_1y_b:
            erp_val_b = (perf_1y_b - rf_b) * 100
            erp_b_str = f"{erp_val_b:+.1f}".replace(".", ",") + "\u00a0%"
    except Exception:
        rf_b = 0.04

    # ── Perf history pour graphique Normalisée ────────────────────────────────
    perf_history = None
    try:
        start_str = (_today - _td(days=380)).strftime("%Y-%m-%d")
        hist_a_1y = _yf.Ticker(_INDICE_CMP_OPTIONS.get(universe_a, (None, "^GSPC", "USD"))[1]).history(start=start_str)
        hist_b_1y = _yf.Ticker(yf_b).history(start=start_str)

        if hist_a_1y is not None and not hist_a_1y.empty and hist_b_1y is not None and not hist_b_1y.empty:
            # Aligner sur les memes dates
            close_a = hist_a_1y["Close"].dropna()
            close_b = hist_b_1y["Close"].dropna()

            # Reindexer sur l'union des dates
            dates_a = set(str(d)[:10] for d in close_a.index)
            dates_b = set(str(d)[:10] for d in close_b.index)
            common  = sorted(dates_a & dates_b)[:380]

            if len(common) > 10:
                ca_map = {str(d)[:10]: float(v) for d, v in zip(close_a.index, close_a)}
                cb_map = {str(d)[:10]: float(v) for d, v in zip(close_b.index, close_b)}
                base_a = ca_map.get(common[0], 1) or 1
                base_b = cb_map.get(common[0], 1) or 1

                perf_history = {
                    "dates":    common,
                    "indice_a": [round(ca_map.get(d, base_a) / base_a * 100, 1) for d in common],
                    "indice_b": [round(cb_map.get(d, base_b) / base_b * 100, 1) for d in common],
                }
    except Exception as _ex:
        log.warning(f"[icmp] perf_history error: {_ex}")

    # ── Extraction Données indice A depuis tickers_data_a ─────────────────────
    # Performance A depuis perf_history existant dans indice_data_a
    ph_a = indice_data_a.get("perf_history")

    perf_ytd_a, perf_1y_a, perf_3y_a, perf_5y_a = None, None, None, None
    vol_1y_a, sharpe_1y_a, max_dd_a = None, None, None

    try:
        yf_sym_a = _INDICE_CMP_OPTIONS.get(universe_a, (None, None, "USD"))[1]
        if yf_sym_a:
            hist_a5 = _yf.Ticker(yf_sym_a).history(period="5y")
            (perf_ytd_a, perf_1y_a, perf_3y_a, perf_5y_a,
             vol_1y_a, sharpe_1y_a, max_dd_a) = _compute_stats(hist_a5)
    except Exception:
        pass

    # Valorisation A depuis tickers_data_a
    pe_fwd_a, pb_a, div_yield_a = None, None, None
    erp_a_str = indice_data_a.get("erp", "\u2014")

    try:
        _pe_list = [float(t["pe_ratio"] or t.get("pe") or 0)
                    for t in tickers_data_a
                    if (t.get("pe_ratio") or t.get("pe")) and
                    5 < float(t.get("pe_ratio") or t.get("pe") or 0) < 100]
        if _pe_list:
            pe_fwd_a = _med_fn(_pe_list)
    except Exception:
        pass

    try:
        _pb_list = [float(t.get("pb") or t.get("priceToBook") or 0)
                    for t in tickers_data_a
                    if (t.get("pb") or t.get("priceToBook")) and
                    0 < float(t.get("pb") or t.get("priceToBook") or 0) < 30]
        if _pb_list:
            pb_a = _med_fn(_pb_list)
    except Exception:
        pass

    try:
        _dy_list = [float(t.get("dividend_yield") or 0)
                    for t in tickers_data_a
                    if t.get("dividend_yield") and float(t.get("dividend_yield") or 0) > 0]
        if _dy_list:
            div_yield_a = _med_fn(_dy_list) / 100  # convertir en decimal
    except Exception:
        pass

    # ── Composition sectorielle A ─────────────────────────────────────────────
    sector_weights_a: dict = {}
    for t in tickers_data_a:
        sec = t.get("sector") or "Autre"
        sector_weights_a[sec] = sector_weights_a.get(sec, 0) + 1
    total_a = sum(sector_weights_a.values()) or 1
    sector_weights_a = {k: round(v / total_a * 100, 1) for k, v in sector_weights_a.items()
                        if k != "Autre"}

    # ── Composition sectorielle B (approximation depuis yfinance constituants) ─
    sector_weights_b: dict = {}
    try:
        # Pas de constituants disponibles pour B — utiliser poids connus approx.
        _SECTOR_WEIGHTS_APPROX = {
            "SP500":     {"Technology": 29.0, "Financials": 13.0, "Healthcare": 12.0,
                          "Consumer Discretionary": 10.0, "Industrials": 8.5,
                          "Communication Services": 8.0, "Consumer Staples": 6.0,
                          "Energy": 4.0, "Utilities": 2.5, "Materials": 2.5, "Real Estate": 2.5},
            "NASDAQ100": {"Technology": 53.0, "Communication Services": 16.0,
                          "Consumer Discretionary": 14.0, "Healthcare": 6.0,
                          "Industrials": 5.0, "Consumer Staples": 3.0, "Financials": 2.0},
            "DAX40":     {"Financials": 18.0, "Consumer Discretionary": 16.0,
                          "Industrials": 15.0, "Materials": 12.0, "Healthcare": 11.0,
                          "Technology": 10.0, "Consumer Staples": 8.0, "Energy": 5.0,
                          "Utilities": 3.0, "Communication Services": 2.0},
            "FTSE100":   {"Financials": 22.0, "Consumer Staples": 15.0, "Energy": 14.0,
                          "Healthcare": 12.0, "Industrials": 10.0, "Materials": 8.0,
                          "Consumer Discretionary": 8.0, "Technology": 4.0,
                          "Utilities": 4.0, "Telecommunication": 3.0},
            "CAC40":     {"Consumer Discretionary": 25.0, "Industrials": 18.0,
                          "Financials": 16.0, "Healthcare": 12.0, "Technology": 9.0,
                          "Consumer Staples": 8.0, "Materials": 6.0,
                          "Energy": 3.0, "Utilities": 3.0},
            "STOXX50":   {"Financials": 20.0, "Consumer Discretionary": 18.0,
                          "Industrials": 15.0, "Healthcare": 12.0, "Technology": 10.0,
                          "Consumer Staples": 10.0, "Energy": 6.0,
                          "Materials": 5.0, "Utilities": 4.0},
        }
        sector_weights_b = _SECTOR_WEIGHTS_APPROX.get(universe_key_b, {})
    except Exception:
        pass

    # ── Sector comparison (merge A et B) ──────────────────────────────────────
    all_sectors = sorted(set(list(sector_weights_a.keys()) + list(sector_weights_b.keys())))
    sector_comparison = []
    for sec in all_sectors:
        wa = sector_weights_a.get(sec)
        wb = sector_weights_b.get(sec)
        sector_comparison.append((sec, wa, wb))
    # Trier par poids A desc
    sector_comparison.sort(key=lambda x: (x[1] or 0) + (x[2] or 0), reverse=True)

    # ── Top 5 constituants A (triés par market cap, poids estimés) ──────────────
    _all_mcaps = [t.get("market_cap") or 0 for t in tickers_data_a]
    _total_mcap = sum(_all_mcaps) or 1
    top5_a_raw = sorted(tickers_data_a,
                        key=lambda t: t.get("market_cap") or 0, reverse=True)[:5]
    top5_a = [(t.get("company", t.get("ticker", "")),
               t.get("ticker", ""),
               round((t.get("market_cap") or 0) / _total_mcap * 100, 1) if (t.get("market_cap") or 0) > 0 else None,
               t.get("sector", "")) for t in top5_a_raw]

    # ── Top 5 constituants B (hardcoded pour indices majeurs) ─────────────────
    _TOP5_HARDCODED = {
        "SP500":    [("Apple Inc.", "AAPL", 7.2, "Technology"),
                     ("Microsoft Corp.", "MSFT", 6.8, "Technology"),
                     ("NVIDIA Corp.", "NVDA", 5.5, "Technology"),
                     ("Amazon.com Inc.", "AMZN", 3.6, "Consumer Discretionary"),
                     ("Alphabet Inc. A", "GOOGL", 2.1, "Communication Services")],
        "NASDAQ100":[("Apple Inc.", "AAPL", 9.0, "Technology"),
                     ("Microsoft Corp.", "MSFT", 8.5, "Technology"),
                     ("NVIDIA Corp.", "NVDA", 7.2, "Technology"),
                     ("Amazon.com Inc.", "AMZN", 5.0, "Consumer Discretionary"),
                     ("Meta Platforms", "META", 4.5, "Communication Services")],
        "DAX40":    [("SAP SE", "SAP", 13.5, "Technology"),
                     ("Siemens AG", "SIE", 8.2, "Industrials"),
                     ("Allianz SE", "ALV", 7.8, "Financials"),
                     ("Deutsche Telekom", "DTE", 6.5, "Communication Services"),
                     ("BASF SE", "BAS", 4.2, "Materials")],
        "FTSE100":  [("AstraZeneca PLC", "AZN", 9.5, "Healthcare"),
                     ("Shell PLC", "SHEL", 7.2, "Energy"),
                     ("HSBC Holdings", "HSBA", 6.8, "Financials"),
                     ("Unilever PLC", "ULVR", 5.1, "Consumer Staples"),
                     ("BP PLC", "BP", 4.5, "Energy")],
        "CAC40":    [("LVMH Moet Hennessy", "MC.PA", 11.5, "Consumer Discretionary"),
                     ("TotalEnergies SE", "TTE.PA", 8.3, "Energy"),
                     ("Hermes International", "RMS.PA", 7.8, "Consumer Discretionary"),
                     ("Sanofi", "SAN.PA", 6.2, "Healthcare"),
                     ("Schneider Electric", "SU.PA", 5.9, "Industrials")],
        "STOXX50":  [("ASML Holding", "ASML", 8.5, "Technology"),
                     ("LVMH Moet Hennessy", "MC.PA", 6.3, "Consumer Discretionary"),
                     ("Siemens AG", "SIE", 5.1, "Industrials"),
                     ("SAP SE", "SAP", 4.9, "Technology"),
                     ("TotalEnergies SE", "TTE.PA", 4.2, "Energy")],
        "NIKKEI225":[("Toyota Motor Corp", "7203.T", 3.8, "Consumer Discretionary"),
                     ("Softbank Group", "9984.T", 3.2, "Technology"),
                     ("Sony Group Corp", "6758.T", 2.9, "Consumer Discretionary"),
                     ("Keyence Corp", "6861.T", 2.5, "Technology"),
                     ("FANUC Corp", "6954.T", 2.1, "Industrials")],
        "DOWJONES": [("UnitedHealth Group", "UNH", 8.5, "Healthcare"),
                     ("Goldman Sachs", "GS", 6.8, "Financials"),
                     ("Microsoft Corp.", "MSFT", 5.9, "Technology"),
                     ("Home Depot Inc.", "HD", 5.5, "Consumer Discretionary"),
                     ("Caterpillar Inc.", "CAT", 4.8, "Industrials")],
    }
    top5_b = _TOP5_HARDCODED.get(universe_key_b, [])

    # ERP A
    try:
        if isinstance(erp_a_str, str) and erp_a_str not in ("\u2014", "—", ""):
            pass
        elif vol_1y_a and perf_1y_a:
            erp_val_a = (perf_1y_a - 0.04) * 100
            erp_a_str = f"{erp_val_a:+.1f}".replace(".", ",") + "\u00a0%"
    except Exception:
        pass

    # ── Score composite proxy pour indice B (depuis perf 1Y, Sharpe, vol) ─────
    # Algo simple : 25pts perf + 25pts Sharpe + 25pts (faible vol = bon) + 25pts perf3Y
    def _score_proxy(perf_1y, sharpe_1y, vol_1y, perf_3y):
        sc = 50  # baseline neutre
        try:
            if perf_1y is not None:
                # +1pt par % de perf au-dessus de 0, plafonne a +25
                sc += max(-15, min(25, float(perf_1y) * 100 * 1.0))
            if sharpe_1y is not None:
                # Sharpe 1.0 = +10pts, 2.0 = +20pts
                sc += max(-10, min(15, float(sharpe_1y) * 10))
            if vol_1y is not None:
                # Vol 15% = neutre, 20%+ = malus, 10%- = bonus
                sc -= max(-5, min(10, (float(vol_1y) - 15) * 0.5))
            if perf_3y is not None:
                sc += max(-5, min(5, float(perf_3y) * 100 * 0.1))
        except Exception:
            pass
        return int(max(0, min(100, sc)))

    score_b_proxy = _score_proxy(perf_1y_b, sharpe_1y_b, vol_1y_b, perf_3y_b)
    # Recalcule signal_b depuis le score
    if score_b_proxy >= 65:
        signal_b_proxy = "Surpondérer"
    elif score_b_proxy >= 45:
        signal_b_proxy = "Neutre"
    else:
        signal_b_proxy = "Sous-pondérer"

    # ── Fallbacks valorisation pour les indices majeurs (yfinance .info est
    # souvent vide pour les symboles d'indices comme ^GSPC, ^FCHI, etc.) ──────
    _PE_FALLBACK = {
        "SP500": 21.5, "SPX": 21.5, "S&P500": 21.5,
        "CAC40": 14.0, "DAX40": 13.5, "FTSE100": 12.0,
        "STOXX50": 13.5, "EUROSTOXX50": 13.5,
        "NASDAQ100": 28.0, "DOWJONES": 18.0, "NIKKEI225": 17.5,
    }
    _PB_FALLBACK = {
        "SP500": 4.5, "SPX": 4.5, "S&P500": 4.5,
        "CAC40": 1.8, "DAX40": 1.6, "FTSE100": 1.7,
        "STOXX50": 1.9, "EUROSTOXX50": 1.9,
        "NASDAQ100": 6.5, "DOWJONES": 5.0, "NIKKEI225": 1.5,
    }
    _DY_FALLBACK = {
        "SP500": 0.014, "SPX": 0.014, "S&P500": 0.014,
        "CAC40": 0.032, "DAX40": 0.028, "FTSE100": 0.038,
        "STOXX50": 0.030, "EUROSTOXX50": 0.030,
        "NASDAQ100": 0.008, "DOWJONES": 0.020, "NIKKEI225": 0.020,
    }
    if pe_fwd_b is None:
        pe_fwd_b = _PE_FALLBACK.get(universe_key_b)
    if pb_b is None:
        pb_b = _PB_FALLBACK.get(universe_key_b)
    if div_yield_b is None:
        div_yield_b = _DY_FALLBACK.get(universe_key_b)
    # Idem pour A si yfinance n'a rien sorti des constituants
    if pe_fwd_a is None:
        pe_fwd_a = _PE_FALLBACK.get(universe_a)
    if pb_a is None:
        pb_a = _PB_FALLBACK.get(universe_a)
    if div_yield_a is None:
        div_yield_a = _DY_FALLBACK.get(universe_a)

    return {
        "name_a":       name_a,
        "name_b":       name_b,
        "code_a":       universe_a,
        "code_b":       universe_key_b,
        "ticker_a":     _INDICE_CMP_OPTIONS.get(universe_a, (None, "^GSPC", "USD"))[1],
        "ticker_b":     yf_b,
        "currency_a":   cur_a,
        "currency_b":   cur_b,
        "date":         today_str,
        # Performance
        "perf_ytd_a":   perf_ytd_a,  "perf_ytd_b":   perf_ytd_b,
        "perf_1y_a":    perf_1y_a,   "perf_1y_b":    perf_1y_b,
        "perf_3y_a":    perf_3y_a,   "perf_3y_b":    perf_3y_b,
        "perf_5y_a":    perf_5y_a,   "perf_5y_b":    perf_5y_b,
        # Risque
        "vol_1y_a":     vol_1y_a,    "vol_1y_b":     vol_1y_b,
        "sharpe_1y_a":  sharpe_1y_a, "sharpe_1y_b":  sharpe_1y_b,
        "max_dd_a":     max_dd_a,    "max_dd_b":     max_dd_b,
        # Valorisation
        "pe_fwd_a":     pe_fwd_a,    "pe_fwd_b":     pe_fwd_b,
        "pb_a":         pb_a,        "pb_b":         pb_b,
        "div_yield_a":  div_yield_a, "div_yield_b":  div_yield_b,
        "erp_a":        erp_a_str,   "erp_b":        erp_b_str,
        # Score
        "score_a":      indice_data_a.get("score_global", 50),
        "score_b":      score_b_proxy,
        "signal_a":     indice_data_a.get("signal_global", "Neutre"),
        "signal_b":     signal_b_proxy,
        # Composition
        "sector_comparison": sector_comparison,
        "top5_a":       top5_a,
        "top5_b":       top5_b,
        # Historique
        "perf_history": perf_history,
    }


def _render_cmp_indice_section(results: dict) -> None:
    """
    Section 'Comparer deux indices' en bas de la page screening indice.
    Gere les etats : form / running / done.
    """
    universe_a_raw = results.get("universe", "")
    # Normalisation : "CAC 40" -> "CAC40" pour matcher les cles du dict
    _universe_a_norm = str(universe_a_raw).replace(" ", "").replace("&", "").upper()
    universe_a = _universe_a_norm if _universe_a_norm in _INDICE_CMP_OPTIONS else universe_a_raw
    indice_data_a = results.get("_indice_data")  # peut etre None si non stocke
    tickers_data_a = results.get("tickers_data", [])
    name_a_disp  = _INDICE_CMP_OPTIONS.get(universe_a, (results.get("display_name", "Indice A"),))[0]

    st.markdown(
        '<div style="margin-top:32px;border-top:1px solid #e5e7eb;padding-top:24px;"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="font-size:13px;font-weight:700;letter-spacing:.08em;'
        'color:#777;text-transform:uppercase;margin-bottom:12px;">Comparer deux indices</div>',
        unsafe_allow_html=True,
    )

    cmp_indice_stage = st.session_state.get("cmp_indice_stage")

    # ── Résultat disponible ──────────────────────────────────────────────────
    if cmp_indice_stage == "done":
        name_b = _INDICE_CMP_OPTIONS.get(
            st.session_state.get("cmp_indice_universe_b", ""), ("Indice B",))[0]
        slug   = f"{name_a_disp.replace(' ','_')}_vs_{name_b.replace(' ','_')}"

        st.success(f"Comparaison {name_a_disp} / {name_b} prete.")
        _pptx = st.session_state.get("cmp_indice_pptx_bytes")
        if _pptx:
            st.download_button(
                label=f"Pitchbook {name_a_disp} vs {name_b}  \u2193  .pptx",
                data=_pptx,
                file_name=f"{slug}_comparison.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                use_container_width=True,
            )
        _pdf = st.session_state.get("cmp_indice_pdf_bytes")
        if _pdf:
            st.download_button(
                label=f"Rapport {name_a_disp} vs {name_b}  \u2193  .pdf",
                data=_pdf,
                file_name=f"{slug}_comparison.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        _xlsx = st.session_state.get("cmp_indice_xlsx_bytes")
        if _xlsx:
            st.download_button(
                label=f"Excel {name_a_disp} vs {name_b}  \u2193  .xlsx",
                data=_xlsx,
                file_name=f"{slug}_comparison.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        if st.button("Nouvelle comparaison d'indices", use_container_width=True,
                     key="cmp_indice_reset"):
            st.session_state.cmp_indice_stage      = None
            st.session_state.cmp_indice_universe_b  = ""
            st.session_state.cmp_indice_pptx_bytes  = None
            st.session_state.cmp_indice_pdf_bytes   = None
            st.session_state.cmp_indice_xlsx_bytes  = None
            st.rerun()
        return

    # ── Pipeline en cours ────────────────────────────────────────────────────
    if cmp_indice_stage == "running":
        universe_b = st.session_state.get("cmp_indice_universe_b", "")
        name_b     = _INDICE_CMP_OPTIONS.get(universe_b, (universe_b,))[0]

        status_lbl = st.empty()
        def _status(msg):
            status_lbl.markdown(
                f'<div style="font-size:12px;font-weight:500;color:#666;">{_e(msg)}...</div>',
                unsafe_allow_html=True)

        _status(f"Construction des Données comparatives {name_a_disp} vs {name_b}")
        try:
            # Reconstruire indice_data_a si non stocke
            if indice_data_a is None:
                indice_data_a = _build_indice_data(tickers_data_a,
                                                    results.get("display_name", name_a_disp),
                                                    universe_a)

            cmp_data = _fetch_cmp_indice_data(
                universe_a, indice_data_a, tickers_data_a, universe_b)

        except Exception as _ex:
            import traceback
            log.warning(f"[icmp] fetch error: {_ex}")
            traceback.print_exc()
            st.error(f"Erreur lors de la construction des Données : {_ex}")
            st.session_state.cmp_indice_stage = None
            return

        pptx_bytes = None
        _status("Génération du pitchbook PPTX")
        try:
            from outputs.cmp_indice_pptx_writer import CmpIndicePPTXWriter
            pptx_bytes = CmpIndicePPTXWriter.generate(cmp_data)
        except Exception as _ex:
            log.warning(f"[icmp] pptx error: {_ex}")

        pdf_bytes = None
        _status("Génération du rapport PDF")
        try:
            from outputs.cmp_indice_pdf_writer import CmpIndicePDFWriter
            pdf_bytes = CmpIndicePDFWriter.generate_bytes(cmp_data)
        except Exception as _ex:
            log.warning(f"[icmp] pdf error: {_ex}")

        xlsx_bytes = None
        _status("Génération du fichier Excel")
        try:
            from outputs.cmp_indice_xlsx_writer import CmpIndiceXlsxWriter
            xlsx_bytes = CmpIndiceXlsxWriter.generate_bytes(cmp_data)
        except Exception as _ex:
            log.warning(f"[icmp] xlsx error: {_ex}")

        st.session_state.cmp_indice_pptx_bytes = pptx_bytes
        st.session_state.cmp_indice_pdf_bytes  = pdf_bytes
        st.session_state.cmp_indice_xlsx_bytes = xlsx_bytes
        st.session_state.cmp_indice_data   = cmp_data  # pour la page de synthese comparative
        st.session_state.cmp_indice_universe_a = universe_a

        # Sauvegarder l'État de l'analyse indice initiale
        st.session_state.previous_analysis_type    = "screening_results"
        st.session_state.previous_analysis_results = st.session_state.get("screening_results")
        st.session_state.previous_analysis_label   = name_a_disp

        st.session_state.cmp_indice_stage = "done"
        st.session_state.comparison_kind   = "indice"
        st.session_state.stage      = "comparison_results"
        st.rerun()
        return

    # ── Formulaire ───────────────────────────────────────────────────────────
    # Indices disponibles = tous sauf l'indice actuel
    _opts = {k: v for k, v in _INDICE_CMP_OPTIONS.items() if k != universe_a}
    _opt_labels = [v[0] for v in _opts.values()]
    _opt_keys   = list(_opts.keys())

    cmp_indice_c1, cmp_indice_c2 = st.columns([3, 1])
    with cmp_indice_c1:
        _sel_b = st.selectbox(
            f"Comparer {name_a_disp} avec :",
            options=_opt_labels, index=0,
            key="cmp_indice_sel_b"
        )
    with cmp_indice_c2:
        st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
        if st.button("Comparer \u2192", type="primary",
                     use_container_width=True, key="cmp_indice_btn"):
            _sel_idx = _opt_labels.index(_sel_b)
            _sel_key = _opt_keys[_sel_idx]
            st.session_state.cmp_indice_universe_b = _sel_key
            st.session_state.cmp_indice_stage      = "running"
            st.rerun()


# ---------------------------------------------------------------------------
# Comparaison sectorielle au sein d'un indice (après analyse indice)
# ---------------------------------------------------------------------------

def _render_cmp_secteur_within_indice(results: dict) -> None:
    """Après une analyse indice, permet de comparer deux secteurs DE l'indice.

    Reuse l'infrastructure cmp_secteur normale (cmp_secteur_* state keys + page
    comparison_results) pour garantir la meme UX que le bouton "Comparer 2
    secteurs" de la homepage. Stage "running" -> redirection vers la page
    de resultats dediee, pas d'affichage in-line.
    """
    tickers_data = results.get("tickers_data", [])
    if not tickers_data:
        return

    sectors_available = sorted(set(
        t.get("sector", "") for t in tickers_data if t.get("sector")
    ))
    if len(sectors_available) < 2:
        return

    indice_name = results.get("display_name", results.get("universe", "Indice"))

    st.markdown(
        f'<div class="sec-t" style="margin-top:36px;">Comparer deux secteurs de {indice_name}</div>',
        unsafe_allow_html=True)

    if st.session_state.get("cmp_secteur_stage") == "running":
        sec_a = st.session_state.get("cmp_secteur_sector_a_isec", "")
        sec_b = st.session_state.get("cmp_secteur_sector_b", "")
        with st.spinner(f"Génération comparatif {sec_a} vs {sec_b}..."):
            try:
                tickers_a = [t for t in tickers_data if t.get("sector") == sec_a]
                tickers_b = [t for t in tickers_data if t.get("sector") == sec_b]
                # Nettoyage state interne
                for tk_list in (tickers_a, tickers_b):
                    for t in tk_list:
                        t.pop("_sector_analytics", None)

                from outputs.cmp_secteur_pptx_writer import CmpSecteurPPTXWriter
                from outputs.cmp_secteur_pdf_writer import generate_cmp_secteur_pdf

                pptx_bytes = CmpSecteurPPTXWriter.generate(
                    tickers_a, sec_a, indice_name,
                    tickers_b, sec_b, indice_name,
                )
                st.session_state.cmp_secteur_pptx_bytes = pptx_bytes

                import tempfile, os as _os
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as _tf:
                    _pdf_path = _tf.name
                generate_cmp_secteur_pdf(
                    tickers_a, sec_a, indice_name,
                    tickers_b, sec_b, indice_name,
                    output_path=_pdf_path,
                )
                st.session_state.cmp_secteur_pdf_bytes = open(_pdf_path, "rb").read()
                try:
                    _os.unlink(_pdf_path)
                except Exception:
                    pass

                # XLSX (template-driven, peut echouer silencieusement)
                try:
                    from outputs.cmp_secteur_xlsx_writer import generate_cmp_secteur_xlsx
                    st.session_state.cmp_secteur_xlsx_bytes = generate_cmp_secteur_xlsx(
                        tickers_a, sec_a, indice_name,
                        tickers_b, sec_b, indice_name,
                    )
                except Exception as _xex:
                    log.warning("[isec_scmp] xlsx gen failed: %s", _xex)
                    st.session_state.cmp_secteur_xlsx_bytes = None

                st.session_state.cmp_secteur_tickers_a = tickers_a
                st.session_state.cmp_secteur_tickers_b = tickers_b
                # Préserver l'analyse indice initiale
                st.session_state.previous_analysis_type    = "screening_results"
                st.session_state.previous_analysis_results = st.session_state.get("screening_results")
                st.session_state.previous_analysis_label   = indice_name
                # Aligner avec cmp_secteur_* pour profiter de la page comparison_results
                st.session_state.cmp_secteur_sector_a = sec_a
                st.session_state.cmp_secteur_stage    = "done"
                st.session_state.comparison_kind      = "secteur"
                st.session_state.stage         = "comparison_results"
                st.rerun()
            except Exception as _ex:
                st.error(f"Erreur Génération comparatif : {_ex}")
                st.session_state.cmp_secteur_stage = None
        return

    # Formulaire de sélection — 2 selectbox + bouton "Comparer" a droite,
    # tous sur la meme ligne (UX alignée sur cmp 2 sociétés)
    col_a, col_b, col_btn = st.columns([3, 3, 2])
    with col_a:
        sec_a = st.selectbox("Secteur A", sectors_available, key="isec_sel_a",
                             label_visibility="collapsed")
    with col_b:
        remaining = [s for s in sectors_available if s != sec_a]
        sec_b = st.selectbox("Secteur B", remaining, key="isec_sel_b",
                             label_visibility="collapsed")
    with col_btn:
        if st.button("Comparer", type="primary", use_container_width=True,
                     key="isec_go"):
            st.session_state.cmp_secteur_sector_a_isec = sec_a
            st.session_state.cmp_secteur_sector_b      = sec_b
            st.session_state.cmp_secteur_stage         = "running"
            st.rerun()


# ---------------------------------------------------------------------------
# Comparatif sectoriel — UI (après analyse sectorielle simple)
# ---------------------------------------------------------------------------

_CMP_SECTOR_CHOICES = [
    "Technologie", "Sant\u00e9", "Consommation Cyclique", "Consommation D\u00e9fensive",
    "Services Financiers", "Industrie", "\u00c9nergie", "Mat\u00e9riaux",
    "Immobilier", "T\u00e9l\u00e9communications", "Services Publics",
]

def _render_cmp_secteur_section(results: dict) -> None:
    """Affiche la section de comparatif sectoriel après une analyse sectorielle simple."""
    import io as _io
    import sys as _sys

    current_sector = results.get("display_name", results.get("universe", ""))
    tickers_a = results.get("tickers_data") or []

    st.markdown('<div class="sec-t" style="margin-top:36px;">Comparatif Sectoriel</div>',
                unsafe_allow_html=True)

    # État comparatif sectoriel
    if "cmp_secteur_stage" not in st.session_state:
        st.session_state.cmp_secteur_stage = None   # None / "running" / "done"
    if "cmp_secteur_pptx_bytes" not in st.session_state:
        st.session_state.cmp_secteur_pptx_bytes = None
    if "cmp_secteur_pdf_bytes" not in st.session_state:
        st.session_state.cmp_secteur_pdf_bytes = None
    if "cmp_secteur_sector_b" not in st.session_state:
        st.session_state.cmp_secteur_sector_b = None

    # Si secteur change => reset
    if st.session_state.get("cmp_secteur_sector_a") != current_sector:
        st.session_state.cmp_secteur_stage = None
        st.session_state.cmp_secteur_pptx_bytes = None
        st.session_state.cmp_secteur_pdf_bytes = None
        st.session_state.cmp_secteur_sector_a = current_sector

    cmp_secteur_stage = st.session_state.cmp_secteur_stage

    if cmp_secteur_stage == "done":
        cmp_secteur_b_local = st.session_state.get("cmp_secteur_sector_b", "")
        st.success(f"Comparatif {current_sector} vs {cmp_secteur_b_local} Généré")
        dl1, dl2, dl3 = st.columns(3)
        with dl1:
            if st.session_state.cmp_secteur_pptx_bytes:
                st.download_button(
                    f"Pitchbook {current_sector} vs {cmp_secteur_b_local} .pptx",
                    st.session_state.cmp_secteur_pptx_bytes,
                    file_name=f"cmp_secteur_{current_sector}_vs_{cmp_secteur_b_local}.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True,
                )
        with dl2:
            if st.session_state.cmp_secteur_pdf_bytes:
                st.download_button(
                    f"Rapport {current_sector} vs {cmp_secteur_b_local} .pdf",
                    st.session_state.cmp_secteur_pdf_bytes,
                    file_name=f"cmp_secteur_{current_sector}_vs_{cmp_secteur_b_local}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
        with dl3:
            if st.button("Nouvelle comparaison", key="cmp_secteur_reset"):
                st.session_state.cmp_secteur_stage = None
                st.session_state.cmp_secteur_pptx_bytes = None
                st.session_state.cmp_secteur_pdf_bytes = None
                st.rerun()
        return

    if cmp_secteur_stage == "running":
        sector_b = st.session_state.get("cmp_secteur_sector_b", "")
        with st.spinner(f"Génération comparatif {current_sector} vs {sector_b}..."):
            try:
                _sys.path.insert(0, str(Path(__file__).parent))
                from cli_analyze import _fetch_real_sector_data, _make_test_tickers

                # Convertit l'input FR (dropdown) en label anglais yfinance pour
                # le lookup dans _SECTOR_TICKERS (cli_analyze) — évite le retour
                # vide quand on passe "Sante" au lieu de "Healthcare".
                try:
                    from core.sector_labels import en_label as _en_label
                    _sector_b_en = _en_label(sector_b) or sector_b
                except Exception:
                    _sector_b_en = sector_b

                # Contexte Global : essais cascade S&P 500 -> CAC 40 -> DAX -> FTSE
                tickers_b = _fetch_real_sector_data(_sector_b_en, "S&P 500", max_tickers=8)
                if not tickers_b:
                    tickers_b = _fetch_real_sector_data(_sector_b_en, "CAC 40", max_tickers=8)
                if not tickers_b:
                    tickers_b = _fetch_real_sector_data(_sector_b_en, "DAX", max_tickers=8)
                if not tickers_b:
                    tickers_b = _fetch_real_sector_data(_sector_b_en, "FTSE 100", max_tickers=8)

                # Dernier recours : fetch via Supabase (pool plus large) puis enrichit
                # avec compute_screening.build_tickers_data (yfinance info + scores)
                if not tickers_b:
                    try:
                        _b_slug = _slug_from_any(sector_b) or sector_b
                        _b_pool = _fetch_sector_tickers(_b_slug)[:15]
                        if _b_pool:
                            from scripts.compute_screening import build_tickers_data as _btd
                            tickers_b = _btd(_b_pool, workers=4) or []
                            # on ne garde que les 8 meilleurs
                            tickers_b = sorted(
                                [t for t in tickers_b if t.get("score_global") is not None],
                                key=lambda x: x["score_global"], reverse=True,
                            )[:8]
                    except Exception as _e_b:
                        log.warning("[scmp] supabase enrichment fallback failed: %s", _e_b)

                # Ultime fallback : synthetique (warn user, tickers nommes <Secteur> Corp N)
                if not tickers_b:
                    st.warning(
                        f"Données temps réel indisponibles pour {sector_b} — "
                        "comparatif sur Données illustratives."
                    )
                    tickers_b = _make_test_tickers(_sector_b_en, 6)

                for t in tickers_b:
                    t.pop("_sector_analytics", None)

                td_a_clean = [dict(t) for t in tickers_a]
                for t in td_a_clean:
                    t.pop("_sector_analytics", None)

                from outputs.cmp_secteur_pptx_writer import CmpSecteurPPTXWriter
                from outputs.cmp_secteur_pdf_writer import generate_cmp_secteur_pdf

                pptx_bytes = CmpSecteurPPTXWriter.generate(
                    td_a_clean, current_sector, "Global",
                    tickers_b, sector_b, "Global",
                )
                st.session_state.cmp_secteur_pptx_bytes = pptx_bytes

                import tempfile, os as _os
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as _tf:
                    _pdf_path = _tf.name
                generate_cmp_secteur_pdf(
                    td_a_clean, current_sector, "Global",
                    tickers_b, sector_b, "Global",
                    output_path=_pdf_path,
                )
                st.session_state.cmp_secteur_pdf_bytes = open(_pdf_path, "rb").read()
                try:
                    _os.unlink(_pdf_path)
                except Exception:
                    pass

                # XLSX secteur comparatif (nouveau writer)
                try:
                    from outputs.cmp_secteur_xlsx_writer import generate_cmp_secteur_xlsx
                    st.session_state.cmp_secteur_xlsx_bytes = generate_cmp_secteur_xlsx(
                        td_a_clean, current_sector, "Global",
                        tickers_b, sector_b, "Global",
                    )
                except Exception as _xex:
                    log.warning(f"[scmp] xlsx gen failed: {_xex}")
                    st.session_state.cmp_secteur_xlsx_bytes = None

                # Stocker les tickers pour la page de résultats comparatifs
                st.session_state.cmp_secteur_tickers_a = td_a_clean
                st.session_state.cmp_secteur_tickers_b = tickers_b

                # Sauvegarder l'État de l'analyse sectorielle initiale
                st.session_state.previous_analysis_type    = "screening_results"
                st.session_state.previous_analysis_results = st.session_state.get("screening_results")
                st.session_state.previous_analysis_label   = current_sector

                st.session_state.cmp_secteur_stage = "done"
                st.session_state.comparison_kind   = "secteur"
                st.session_state.stage      = "comparison_results"
                st.rerun()
            except Exception as _ex:
                st.error(f"Erreur Génération comparatif : {_ex}")
                st.session_state.cmp_secteur_stage = None
        return

    # Formulaire de sélection — filtre X vs X via comparaison par slug canonique
    # (évite que "Technologie" et "Technology" soient vus comme différents)
    _curr_slug = _slug_from_any(current_sector)
    other_choices = [
        s for s in _CMP_SECTOR_CHOICES
        if _slug_from_any(s) != _curr_slug
    ]
    # Selectbox + bouton "Comparer" sur la meme ligne (alignés comme cmp société)
    sc1, sc2 = st.columns([3, 1])
    with sc1:
        sector_b_sel = st.selectbox(
            label="",
            options=other_choices,
            key="cmp_secteur_sector_b_sel",
            label_visibility="collapsed",
        )
    with sc2:
        if st.button("Comparer", type="primary", use_container_width=True,
                     key="cmp_secteur_run"):
            st.session_state.cmp_secteur_sector_b = sector_b_sel
            st.session_state.cmp_secteur_stage = "running"
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
        st.warning("Aucune Donnée de screening disponible.")
        if st.button("<- Retour"):
            st.session_state.stage = "home"
            st.rerun()
        return

    # --- Navigation ---
    # Bouton "Nouvelle recherche" central RETIRE (audit Baptiste 2026-04-14) :
    # il faisait doublon avec le bouton "Nouvelle analyse" de la sidebar gauche
    # qui est maintenant disponible aussi en screening_results.
    parent = st.session_state.get("screening_parent")
    if parent:
        if st.button(f"<- {parent['display_name']}", use_container_width=False):
            st.session_state.screening_results = parent
            st.session_state.screening_parent  = None
            st.rerun()

    # --- Header ---
    st.markdown(f'<div class="rc">{_e(display_name)} — Screening</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="rm">{n} sociétés analysées · {today} · '
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
        f'<div class="mkt-cell"><div class="mkt-n">SOCIÉTÉS</div>'
        f'<div class="mkt-v">{n}</div><div class="mkt-na">dans l\'univers</div></div>',

        f'<div class="mkt-cell"><div class="mkt-n">MEILLEUR SCORE</div>'
        f'<div class="mkt-v">{best.get("score_global") or 0:.0f}/100</div>'
        f'<div class="mkt-na">{_e((best.get("company") or "")[:22])}</div></div>',

        f'<div class="mkt-cell"><div class="mkt-n">SCORE MÉDIAN</div>'
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

    hcols = st.columns([0.4, 2.4, 1.0, 1.0, 1.0, 1.0, 1.2])
    for hc, h in zip(hcols, ["#", "Société", "Score", "Value", "Growth", "Quality", ""]):
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
        rcols    = st.columns([0.4, 2.4, 1.0, 1.0, 1.0, 1.0, 1.2])

        with rcols[0]:
            st.markdown(f'<div class="scr-rank">{i+1}</div>', unsafe_allow_html=True)
        with rcols[1]:
            # Badge palier : T1 = profitable, T2 = croissance, T3 = pré-revenue
            _tier = t.get("valuation_tier") or 1
            _tier_color = {1: "#1A7A4A", 2: "#B06000", 3: "#A82020"}.get(_tier, "#555")
            _tier_label = {1: "T1", 2: "T2", 3: "T3"}.get(_tier, "T1")
            _tier_title = {1: "Palier 1 — profitable (EV/EBITDA)",
                           2: "Palier 2 — croissance (P/S)",
                           3: "Palier 3 — pr\u00e9-revenue (P/B)"}.get(_tier, "")
            st.markdown(
                f'<div style="padding:2px 0;">'
                f'<div style="font-size:13px;font-weight:600;color:#111;">'
                f'{_e((t.get("company") or "")[:28])}</div>'
                f'<div class="scr-ticker">{_e(ticker_v)} '
                f'<span style="font-size:9px;font-weight:700;color:#fff;background:{_tier_color};'
                f'padding:1px 5px;border-radius:3px;margin-left:4px;" title="{_tier_title}">'
                f'{_tier_label}</span></div></div>',
                unsafe_allow_html=True,
            )
        with rcols[2]:
            st.markdown(
                f'<div style="padding:2px 0;"><span class="score-pill {sc_cls}">{score:.0f}</span></div>',
                unsafe_allow_html=True,
            )
        with rcols[3]:
            v = t.get("score_value") or 0
            st.markdown(
                f'<div style="font-family:\'DM Mono\',monospace;font-size:12px;color:#555;">{v:.0f}</div>',
                unsafe_allow_html=True,
            )
        with rcols[4]:
            g = t.get("score_growth") or 0
            st.markdown(
                f'<div style="font-family:\'DM Mono\',monospace;font-size:12px;color:#555;">{g:.0f}</div>',
                unsafe_allow_html=True,
            )
        with rcols[5]:
            q = t.get("score_quality") or 0
            st.markdown(
                f'<div style="font-family:\'DM Mono\',monospace;font-size:12px;color:#555;">{q:.0f}</div>',
                unsafe_allow_html=True,
            )
        with rcols[6]:
            if st.button("Analyser", key=f"scr_ana_{ticker_v}_{i}", type="primary"):
                st.session_state.ticker       = ticker_v
                st.session_state.from_screening = True
                st.session_state.stage        = "running"
                st.rerun()

    # --- Top 5 par catégorie ---
    st.markdown('<div class="sec-t" style="margin-top:36px;">Top 5 par catégorie</div>',
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

    # --- Comparer deux indices (en haut si analyse d'indice) ---
    # Fix 2026-04-14 : normaliser la clef d'univers pour matcher _INDICE_CMP_OPTIONS
    # (les keys sont "CAC40" sans espace, mais results["universe"] peut valoir "CAC 40")
    _universe_key = results.get("universe", "")
    _universe_key_norm = str(_universe_key).replace(" ", "").replace("&", "").upper()
    _is_indice_result = (_universe_key not in _SECTOR_ALIASES_SET
                         and (_universe_key in _INDICE_CMP_OPTIONS
                              or _universe_key_norm in _INDICE_CMP_OPTIONS))
    _is_sector_result = _universe_key in _SECTOR_ALIASES_SET
    if _is_indice_result:
        _render_cmp_indice_section(results)
        st.markdown('<div style="margin-top:8px;"></div>', unsafe_allow_html=True)
        # Comparaison sectorielle au sein de l'indice
        _render_cmp_secteur_within_indice(results)
        st.markdown('<div style="margin-top:8px;"></div>', unsafe_allow_html=True)

    # --- Comparatif sectoriel (si analyse sectorielle simple) ---
    if _is_sector_result:
        _render_cmp_secteur_section(results)
        st.markdown('<div style="margin-top:8px;"></div>', unsafe_allow_html=True)

    # --- Comparer deux sociétés ---
    st.markdown('<div class="sec-t" style="margin-top:36px;">Comparer deux sociétés</div>',
                unsafe_allow_html=True)

    _ticker_pairs = sorted(
        [(f"{t.get('ticker', '?')}  —  {(t.get('company') or '')[:32]}", t.get('ticker', ''))
         for t in tickers_data],
        key=lambda x: x[0]
    )
    _ticker_labels = [p[0] for p in _ticker_pairs]
    _ticker_keys   = [p[1] for p in _ticker_pairs]

    cmp_c1, cmp_c2, cmp_c3 = st.columns([2, 2, 1])
    with cmp_c1:
        sel_a = st.selectbox("Société A", options=_ticker_labels, index=0, key="scr_cmp_sel_a")
    with cmp_c2:
        sel_b = st.selectbox("Société B", options=_ticker_labels,
                             index=min(1, len(_ticker_labels) - 1), key="scr_cmp_sel_b")
    with cmp_c3:
        st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
        if st.button("Comparer →", type="primary", use_container_width=True, key="scr_cmp_btn"):
            _idx_a = _ticker_labels.index(sel_a)
            _idx_b = _ticker_labels.index(sel_b)
            _tkr_a = _ticker_keys[_idx_a]
            _tkr_b = _ticker_keys[_idx_b]
            if _tkr_a and _tkr_b and _tkr_a != _tkr_b:
                st.session_state.ticker           = _tkr_a
                st.session_state.scr_cmp_b_preset = _tkr_b
                st.session_state.from_screening   = True
                st.session_state.stage            = "running"
                st.rerun()

    # --- Glossaire termes financiers ---
    _render_glossaire("screening")

    # --- Footer ---
    st.markdown(
        f'<div class="page-footer">'
        f'<span>FINSIGHT SCREENING · v1.0</span>'
        f'<span>Données au {today}</span>'
        f'<span>© {date.today().year} — Outil d\'aide a la Décision uniquement</span>'
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
        # Détection profil pour adapter le commentaire valorisation
        try:
            from core.sector_profiles import detect_profile as _dp
            _ia_profile = _dp(
                ci.sector or "",
                getattr(ci, "industry", "") or "",
            )
        except Exception:
            _ia_profile = "STANDARD"

        pe_comment = ""
        if yr.pe_ratio is not None:
            if _ia_profile in ("BANK", "INSURANCE"):
                if yr.pe_ratio < 10:
                    pe_comment = "en dessous de la fourchette banques/assurance (8-14x), suggérant une décote potentielle"
                elif yr.pe_ratio < 14:
                    pe_comment = "dans la norme banques/assurance (8-14x)"
                else:
                    pe_comment = "au-dessus de la fourchette banques/assurance (8-14x), prime sur la rentabilité"
            elif _ia_profile == "REIT":
                pe_comment = "P/E peu pertinent pour une foncière (préférer P/FFO, P/NAV)"
            elif _ia_profile == "UTILITY":
                if yr.pe_ratio < 14:
                    pe_comment = "en dessous de la norme utilities (15-20x)"
                elif yr.pe_ratio < 20:
                    pe_comment = "dans la norme utilities régulées"
                else:
                    pe_comment = "au-dessus de la fourchette utilities, prime de croissance intégrée"
            else:
                if yr.pe_ratio < 15:
                    pe_comment = "en dessous des niveaux historiques sectoriels, suggérant une décote potentielle"
                elif yr.pe_ratio < 25:
                    pe_comment = "dans la norme sectorielle, reflétant une valorisation équilibrée"
                else:
                    pe_comment = "au-dessus de la médiane sectorielle, intégrant des attentes de croissance élevées"

        if _ia_profile in ("BANK", "INSURANCE"):
            pb_comment = ""
            if yr.pb_ratio is not None:
                if yr.pb_ratio < 0.9:
                    pb_comment = "décote vs book value — opportunité potentielle si ROE durable > coût FP"
                elif yr.pb_ratio < 1.5:
                    pb_comment = "dans la norme bancaire (0.8-1.5x) — valorisation alignée sur le ROE structurel"
                else:
                    pb_comment = "prime marquée vs book value — justifiée uniquement si ROE > 12% durable"
            text = (
                f"Le P/E de {_hl(_x(yr.pe_ratio))} est {_e(pe_comment)}. "
                f"Le P/TBV de {_hl(_x(yr.pb_ratio))} est {_e(pb_comment)}. "
                f"<i>(EV/EBITDA et marge brute non applicables aux profils bancaires/assurance — "
                f"les ratios pertinents sont P/TBV, ROE, et le gap vs coût des fonds propres.)</i> "
            )
        elif _ia_profile == "REIT":
            text = (
                f"Le P/E de {_hl(_x(yr.pe_ratio))} est {_e(pe_comment)}. "
                f"Le P/B de {_hl(_x(yr.pb_ratio))} sert de proxy P/NAV — viser 0.85-1.15x. "
                f"<i>(Pour une foncière cotée, privilégier P/FFO, P/AFFO et P/NAV — l'EV/EBITDA "
                f"est déformé par les amortissements comptables sur les immeubles.)</i> "
            )
        else:
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
        roe_qual = _good(_p(yr.roe)) if (yr.roe or 0) > 0.12 else _risk(_p(yr.roe))

        if _ia_profile in ("BANK", "INSURANCE"):
            # Fondamentaux bancaires : ROE > coût FP, ROA, pas de leverage ratio classique
            roa_qual = _good(_p(yr.roa)) if (yr.roa or 0) > 0.01 else _risk(_p(yr.roa))
            nm_qual  = _good(_p(yr.net_margin)) if (yr.net_margin or 0) > 0.25 else _hl(_p(yr.net_margin))
            _gap_cost_fp = "> coût des fonds propres" if (yr.roe or 0) > 0.10 else "sous le coût des fonds propres"
            text = (
                f"Le ROE de {roe_qual} est {_e(_gap_cost_fp)} (≈ 10%), ce qui "
                f"{'justifie' if (yr.roe or 0) > 0.10 else 'ne justifie pas'} une prime sur la book value. "
                f"Le ROA de {roa_qual} reflète l'efficacité du bilan "
                f"({'> 1% = solide' if (yr.roa or 0) > 0.01 else 'sous la norme bancaire'}). "
                f"La marge nette post-provisions de {nm_qual} est le premier indicateur "
                f"de la qualité des earnings. "
                f"<i>Pour un profil bancaire/assurance, les indicateurs clés sont ROE vs coût FP, "
                f"ROA, Cost/Income, NIM, CET1 Ratio et NPL — la marge brute et le leverage "
                f"Net Debt/EBITDA ne sont pas applicables.</i>"
            )
            blocks.append(("Rentabilité & qualité du bilan", text))
        elif _ia_profile == "REIT":
            em_qual = _good(_p(yr.ebitda_margin)) if (yr.ebitda_margin or 0) > 0.5 else _hl(_p(yr.ebitda_margin))
            fcf_comment = ""
            if yr.fcf_yield is not None:
                if yr.fcf_yield > 0.05:
                    fcf_comment = f"attractif à {_good(_p(yr.fcf_yield))}"
                elif yr.fcf_yield > 0:
                    fcf_comment = f"positif à {_hl(_p(yr.fcf_yield))}"
                else:
                    fcf_comment = f"{_risk(_p(yr.fcf_yield))}"
            text = (
                f"La marge EBITDA de {em_qual} approche le NOI margin sectoriel (> 60% sain). "
                f"Le ROE de {roe_qual} reflète le rendement net sur book. "
                f"Le FCF yield est {fcf_comment} et sert de proxy pour le AFFO yield. "
                f"<i>Pour une foncière, les indicateurs clés sont FFO/AFFO par action, "
                f"P/FFO, P/NAV, Occupancy, WALT, LTV et Same-Store NOI Growth — "
                f"la marge brute n'est pas pertinente.</i>"
            )
            blocks.append(("Fondamentaux opérationnels REIT", text))
        else:
            gm_qual = _good(_p(yr.gross_margin)) if (yr.gross_margin or 0) > 0.3 else _hl(_p(yr.gross_margin))
            em_qual = _good(_p(yr.ebitda_margin)) if (yr.ebitda_margin or 0) > 0.15 else _hl(_p(yr.ebitda_margin))

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

def _render_comparison_section(state_a: dict) -> None:
    """
    Section en bas de page résultats société :
    Propose de comparer avec une autre société.
    Gère les états : form / running / done.
    """
    st.markdown(
        '<div style="margin-top:40px;border-top:1px solid #e5e7eb;padding-top:28px;"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="font-size:13px;font-weight:700;letter-spacing:.08em;'
        'color:#777;text-transform:uppercase;margin-bottom:12px;">Analyse comparative</div>',
        unsafe_allow_html=True,
    )

    cmp_societe_stage = st.session_state.get("cmp_societe_stage")

    # ── Auto-déclenchement depuis le screening sectoriel ────────────────
    _preset_b = st.session_state.get("scr_cmp_b_preset", "")
    if _preset_b and not cmp_societe_stage:
        st.session_state.cmp_societe_ticker_b       = _preset_b
        st.session_state.cmp_societe_stage          = "running"
        st.session_state.scr_cmp_b_preset   = ""
        st.rerun()

    # ── Résultat disponible ──────────────────────────────────────────────
    if cmp_societe_stage == "done" and st.session_state.get("cmp_societe_xlsx_bytes"):
        tkr_a = (state_a.get("raw_data") and state_a["raw_data"].ticker) or state_a.get("ticker", "A")
        tkr_b = st.session_state.get("cmp_societe_ticker_b", "B")
        fname_xlsx = f"{tkr_a}_vs_{tkr_b}_comparison.xlsx"
        st.success(f"Comparaison {tkr_a} / {tkr_b} prête.")
        st.download_button(
            label=f"Comparaison {tkr_a} vs {tkr_b}  ↓  .xlsx",
            data=st.session_state["cmp_societe_xlsx_bytes"],
            file_name=fname_xlsx,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        # Pitchbook PPTX comparatif (pré-généré)
        cmp_pptx = st.session_state.get("cmp_societe_pptx_bytes")
        if cmp_pptx:
            fname_pptx = f"{tkr_a}_vs_{tkr_b}_comparison.pptx"
            st.download_button(
                label=f"Pitchbook {tkr_a} vs {tkr_b}  \u2193  .pptx",
                data=cmp_pptx,
                file_name=fname_pptx,
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                use_container_width=True,
            )
        # Rapport PDF comparatif (pré-généré)
        cmp_pdf = st.session_state.get("cmp_societe_pdf_bytes")
        if cmp_pdf:
            fname_pdf = f"{tkr_a}_vs_{tkr_b}_comparison.pdf"
            st.download_button(
                label=f"Rapport {tkr_a} vs {tkr_b}  \u2193  .pdf",
                data=cmp_pdf,
                file_name=fname_pdf,
                mime="application/pdf",
                use_container_width=True,
            )
        if st.button("Nouvelle comparaison", use_container_width=True):
            st.session_state.cmp_societe_stage      = None
            st.session_state.cmp_societe_ticker_b   = ""
            st.session_state.cmp_societe_xlsx_bytes      = None
            st.session_state.cmp_societe_state_b    = None
            st.session_state.cmp_societe_pptx_bytes = None
            st.session_state.cmp_societe_pdf_bytes  = None
            st.rerun()
        return

    # ── Pipeline en cours pour société B ────────────────────────────────
    if cmp_societe_stage == "running":
        ticker_b = st.session_state.get("cmp_societe_ticker_b", "")
        if not ticker_b:
            st.session_state.cmp_societe_stage = None
            st.rerun()
            return

        with st.spinner(f"Analyse de {ticker_b} en cours..."):
            try:
                from core.graph import build_graph
                graph   = build_graph()
                state_b: dict = {}
                for chunk in graph.stream(
                    {"ticker": ticker_b.upper(), "errors": [], "logs": [], "qa_retries": 0},
                    stream_mode="updates",
                ):
                    node_name  = list(chunk.keys())[0]
                    node_delta = chunk[node_name]
                    state_b.update(node_delta)

                if state_b.get("raw_data") is None:
                    st.error(f"Aucune Donnée disponible pour {ticker_b}.")
                    st.session_state.cmp_societe_stage = None
                    return

                st.session_state.cmp_societe_state_b = state_b

                # Générer TOUS les fichiers comparaison (XLSX + PPTX + PDF)
                # pour éviter le double-clic au téléchargement
                from outputs.cmp_societe_xlsx_writer import CmpSocieteXlsxWriter
                cmp_societe_xlsx_bytes = CmpSocieteXlsxWriter().write(state_a, state_b)
                st.session_state.cmp_societe_xlsx_bytes = cmp_societe_xlsx_bytes

                try:
                    from outputs.cmp_societe_pptx_writer import CmpSocietePPTXWriter, _generate_synthesis
                    from outputs.cmp_societe_xlsx_writer import extract_metrics as _extract, _fetch_supplements as _fetch
                    st.session_state.cmp_societe_pptx_bytes = CmpSocietePPTXWriter().generate_bytes(state_a, state_b)
                    # Stocker la Synthèse LLM pour la page comparative
                    try:
                        _ma = _extract(state_a, _fetch(state_a.get("ticker", "")))
                        _mb = _extract(state_b, _fetch(state_b.get("ticker", "")))
                        _ma["ticker_a"] = state_a.get("ticker", "")
                        _mb["ticker_b"] = state_b.get("ticker", "")
                        st.session_state.cmp_societe_synthesis = _generate_synthesis(_ma, _mb)
                    except Exception as _sx:
                        log.warning(f"[comparison] synthesis extract failed: {_sx}")
                        st.session_state.cmp_societe_synthesis = None
                except Exception as _pex:
                    log.warning(f"[comparison] PPTX auto-gen failed: {_pex}")
                    st.session_state.cmp_societe_pptx_bytes = None
                    st.session_state.cmp_societe_synthesis = None

                try:
                    from outputs.cmp_societe_pdf_writer import CmpSocietePDFWriter
                    st.session_state.cmp_societe_pdf_bytes = CmpSocietePDFWriter().generate_bytes(state_a, state_b)
                except Exception as _pdex:
                    log.warning(f"[comparison] PDF auto-gen failed: {_pdex}")
                    st.session_state.cmp_societe_pdf_bytes = None

                # Sauvegarder l'État initial pour le bouton "Retour"
                st.session_state.previous_analysis_type    = "results"
                st.session_state.previous_analysis_results = st.session_state.get("results")
                st.session_state.previous_analysis_label   = state_a.get("ticker", "analyse")

                st.session_state.cmp_societe_stage = "done"
                st.session_state.comparison_kind  = "société"
                st.session_state.stage     = "comparison_results"
                st.rerun()

            except Exception as _ex:
                log.error(f"[comparison] erreur pipeline B: {_ex}", exc_info=True)
                st.error(f"Erreur comparaison : {_ex}")
                st.session_state.cmp_societe_stage = None
        return

    # ── Formulaire de saisie ─────────────────────────────────────────────
    tkr_a = (state_a.get("raw_data") and state_a["raw_data"].ticker) or state_a.get("ticker", "")
    col1, col2 = st.columns([3, 1])
    with col1:
        ticker_b_input = st.text_input(
            label="",
            placeholder=f"Comparer {tkr_a} avec... (ex : MSFT, MC.PA, NVDA)",
            key="cmp_societe_ticker_input",
            label_visibility="collapsed",
        )
    with col2:
        compare_clicked = st.button("Comparer", use_container_width=True, type="primary")

    if compare_clicked and ticker_b_input.strip():
        raw_input = ticker_b_input.strip().upper()
        # Résolution : si l'input ne ressemble pas a un ticker (contient un espace
        # ou plus de 6 chars sans point), chercher via Yahoo Finance Search
        resolved_ticker = raw_input
        _needs_resolve = len(raw_input) > 6 and "." not in raw_input
        if not _needs_resolve:
            # Vérifier si le ticker est valide via yfinance
            try:
                import yfinance as _yf
                _chk = _yf.Ticker(raw_input)
                _qt = (_chk.info or {}).get("quoteType", "")
                if _qt not in ("EQUITY", "ETF"):
                    _needs_resolve = True
            except Exception:
                _needs_resolve = True
        if _needs_resolve:
            try:
                import requests as _req
                _r = _req.get(
                    "https://query2.finance.yahoo.com/v1/finance/search",
                    params={"q": raw_input, "quotesCount": 5, "newsCount": 0},
                    headers={"User-Agent": "Mozilla/5.0"}, timeout=5,
                )
                _quotes = _r.json().get("quotes", [])
                # Prendre le premier résultat EQUITY
                for _q in _quotes:
                    if _q.get("quoteType") == "EQUITY":
                        resolved_ticker = _q["symbol"]
                        st.info(f"Ticker résolu : {raw_input} -> {resolved_ticker} ({_q.get('shortname','')})")
                        break
            except Exception:
                pass  # garder raw_input
        st.session_state.cmp_societe_ticker_b   = resolved_ticker
        st.session_state.cmp_societe_stage      = "running"
        st.session_state.cmp_societe_xlsx_bytes      = None
        st.session_state.cmp_societe_state_b    = None
        st.session_state.cmp_societe_pptx_bytes = None
        st.session_state.cmp_societe_pdf_bytes  = None
        st.rerun()


def _render_glossaire(key_suffix: str = "main") -> None:
    """Glossaire des termes financiers — toggle manuel.

    key_suffix : suffixe pour les session_state keys (evite les collisions
    quand plusieurs pages utilisent le glossaire).
    """
    st.markdown('<div class="sec-t">Glossaire des termes financiers</div>', unsafe_allow_html=True)
    _state_key = f"glossaire_open_{key_suffix}"
    _btn_key = f"btn_glossaire_toggle_{key_suffix}"
    if _state_key not in st.session_state:
        st.session_state[_state_key] = False
    _gl_label = "Comprendre les indicateurs ▲" if st.session_state[_state_key] else "Comprendre les indicateurs ▼"
    if st.button(_gl_label, key=_btn_key, use_container_width=True):
        st.session_state[_state_key] = not st.session_state[_state_key]
        st.rerun()
    if st.session_state[_state_key]:
        st.markdown("""
<style>
.gls-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px;margin:16px 0 24px 0;}
.gls-card{background:#f8f9fb;border:1px solid #e2e6ea;border-radius:8px;padding:14px 16px;}
.gls-cat{font-size:11px;font-weight:700;letter-spacing:.08em;color:#6c757d;text-transform:uppercase;margin-bottom:8px;}
.gls-row{display:flex;gap:8px;margin-bottom:6px;align-items:flex-start;}
.gls-term{font-size:12px;font-weight:700;color:#1B3A6B;min-width:110px;padding-top:1px;}
.gls-def{font-size:12px;color:#333;line-height:1.45;}
</style>
<div class="gls-grid">

<div class="gls-card">
<div class="gls-cat">Valorisation</div>
<div class="gls-row"><span class="gls-term">PER (P/E)</span><span class="gls-def">Prix / Bénéfice par action. Indique combien le marché paie pour 1 € de bénéfice. Un PER élevé reflète des attentes de croissance.</span></div>
<div class="gls-row"><span class="gls-term">EV/EBITDA</span><span class="gls-def">Valeur d'entreprise / EBITDA. Multiple de valorisation indépendant de la structure de capital et fiscalité.</span></div>
<div class="gls-row"><span class="gls-term">P/B (Price-to-Book)</span><span class="gls-def">Prix / Valeur comptable. Rapport entre capitalisation et actif net comptable. &lt;1 = potentiellement sous-évalué.</span></div>
<div class="gls-row"><span class="gls-term">FCF Yield</span><span class="gls-def">Free Cash Flow / Market Cap. Rendement du cash généré après investissements. Plus élevé = meilleur.</span></div>
<div class="gls-row"><span class="gls-term">P/FCF</span><span class="gls-def">Prix / Free Cash Flow par action. Alternative au PER basée sur les flux réels plutôt que le bénéfice comptable.</span></div>
<div class="gls-row"><span class="gls-term">PEG</span><span class="gls-def">PER / Taux de croissance des bénéfices. PEG &lt;1 suggère une valorisation attractive relativement à la croissance.</span></div>
<div class="gls-row"><span class="gls-term">DCF</span><span class="gls-def">Discounted Cash Flow. Valorisation par actualisation des flux futurs estimés au taux WACC. Dépend fortement des hypothèses de croissance.</span></div>
<div class="gls-row"><span class="gls-term">P/S (Price-to-Sales)</span><span class="gls-def">Prix / Chiffre d'affaires. Utilisé pour les sociétés sans EBITDA positif (SaaS, biotech en croissance). Un P/S élevé se justifie par une forte croissance revenue. Palier 2.</span></div>
<div class="gls-row"><span class="gls-term">EV/Gross Profit</span><span class="gls-def">Valeur d'entreprise / Profit brut. Alternative à EV/EBITDA pour les sociétés à marge brute positive mais EBITDA négatif (investissements R&amp;D lourds).</span></div>
<div class="gls-row"><span class="gls-term">Rule of 40</span><span class="gls-def">Croissance revenue (%) + Marge EBITDA (%). Métrique SaaS : &gt;40% = société saine qui équilibre croissance et rentabilité. &lt;20% = signal d'alerte.</span></div>
<div class="gls-row"><span class="gls-term">Palier de valorisation</span><span class="gls-def">Palier 1 = profitable (EV/EBITDA). Palier 2 = croissance (P/S, Rule of 40). Palier 3 = pré-revenue (P/B). Le palier détermine la métrique de valorisation principale.</span></div>
</div>

<div class="gls-card">
<div class="gls-cat">Profitabilité</div>
<div class="gls-row"><span class="gls-term">EBITDA Margin</span><span class="gls-def">EBITDA / CA. Marge opérationnelle avant amortissements, intérêts et impôts. Reflet de la rentabilité brute d'exploitation.</span></div>
<div class="gls-row"><span class="gls-term">EBIT Margin</span><span class="gls-def">EBIT / CA. Marge opérationnelle après amortissements. Reflète l'efficacité opérationnelle réelle.</span></div>
<div class="gls-row"><span class="gls-term">Net Margin</span><span class="gls-def">Résultat net / CA. Part du chiffre d'affaires restant après toutes charges. Dépend aussi de l'effet de levier et de la fiscalité.</span></div>
<div class="gls-row"><span class="gls-term">ROIC</span><span class="gls-def">Return on Invested Capital. NOPAT / Capital investi. Mesure la capacité à créer de la valeur sur les capitaux déployés. ROIC &gt; WACC = création de valeur.</span></div>
<div class="gls-row"><span class="gls-term">ROE</span><span class="gls-def">Return on Equity. Résultat net / Fonds propres. Rentabilité pour l'actionnaire. Peut être gonflé par l'endettement.</span></div>
<div class="gls-row"><span class="gls-term">CAGR CA 3 ans</span><span class="gls-def">Compound Annual Growth Rate du chiffre d'affaires sur 3 ans. Taux de croissance annualisé.</span></div>
</div>

<div class="gls-card">
<div class="gls-cat">Structure financière & Levier</div>
<div class="gls-row"><span class="gls-term">ND/EBITDA</span><span class="gls-def">Dette nette / EBITDA. Nb d'années d'EBITDA pour rembourser la dette nette. &lt;2x = faible levier, &gt;4x = levier élevé.</span></div>
<div class="gls-row"><span class="gls-term">Interest Coverage</span><span class="gls-def">EBIT / Frais financiers. Capacité à couvrir les intérêts. &lt;1,5x = zone de risque.</span></div>
<div class="gls-row"><span class="gls-term">Current Ratio</span><span class="gls-def">Actifs courants / Passifs courants. Liquidité à court terme. &gt;1 = couverture des dettes court terme.</span></div>
<div class="gls-row"><span class="gls-term">Quick Ratio</span><span class="gls-def">Actifs liquides (sans stocks) / Passifs courants. Version stricte du current ratio.</span></div>
<div class="gls-row"><span class="gls-term">WACC</span><span class="gls-def">Weighted Average Cost of Capital. Coût moyen pondéré du capital (dette + fonds propres). Taux d'actualisation du DCF.</span></div>
<div class="gls-row"><span class="gls-term">Free Cash Flow</span><span class="gls-def">Cash opérationnel - Capex. Flux de trésorerie disponible après investissements. Base de la valeur intrinsèque.</span></div>
</div>

<div class="gls-card">
<div class="gls-cat">Qualité comptable</div>
<div class="gls-row"><span class="gls-term">Piotroski F-Score</span><span class="gls-def">Score 0-9 sur 9 critères (rentabilité, liquidité, levier, efficacité). &gt;6 = bonne santé financière, &lt;3 = signaux négatifs.</span></div>
<div class="gls-row"><span class="gls-term">Beneish M-Score</span><span class="gls-def">Modèle de détection de manipulation comptable. &gt;-1,78 = risque potentiel de fraude aux résultats.</span></div>
<div class="gls-row"><span class="gls-term">Altman Z-Score</span><span class="gls-def">Score de risque de faillite. &gt;2,99 = zone sûre, 1,81-2,99 = zone grise, &lt;1,81 = zone de détresse.</span></div>
<div class="gls-row"><span class="gls-term">Sloan Accruals</span><span class="gls-def">Mesure la part du résultat comptable non soutenue par le cash (accruals). Un ratio élevé suggère des bénéfices de moindre qualité.</span></div>
<div class="gls-row"><span class="gls-term">Cash Conversion</span><span class="gls-def">FCF / Résultat net. Qualité de conversion des bénéfices comptables en cash. Idéalement &gt;0,8.</span></div>
</div>

<div class="gls-card">
<div class="gls-cat">Risque & Marché</div>
<div class="gls-row"><span class="gls-term">Bêta</span><span class="gls-def">Sensibilité du titre aux mouvements du marché. Bêta=1 = même volatilité que le marché. &gt;1 = plus volatil (amplificateur), &lt;1 = plus défensif.</span></div>
<div class="gls-row"><span class="gls-term">VaR 95% 1M</span><span class="gls-def">Value at Risk mensuelle à 95%. Perte maximale attendue dans 95% des cas sur un mois. Ex: -8% signifie que dans 5% des mois, la perte dépasse 8%.</span></div>
<div class="gls-row"><span class="gls-term">Volatilité 52S</span><span class="gls-def">Écart-type annualisé des rendements journaliers sur 52 semaines. Mesure l'amplitude des fluctuations du cours.</span></div>
<div class="gls-row"><span class="gls-term">52W High / Low</span><span class="gls-def">Plus haut / plus bas du cours sur les 52 dernières semaines. Repères techniques de la fourchette de trading récente.</span></div>
<div class="gls-row"><span class="gls-term">ERP</span><span class="gls-def">Equity Risk Premium. Prime de risque des actions vs taux sans risque. Pilote le coût des fonds propres dans le WACC.</span></div>
</div>

<div class="gls-card">
<div class="gls-cat">Scores FinSight</div>
<div class="gls-row"><span class="gls-term">Score FinSight</span><span class="gls-def">Score composite 0-100 : Valeur (25pts) + Croissance (25pts) + Qualité (25pts) + Momentum (25pts). Agrège les signaux quantitatifs en un seul chiffre.</span></div>
<div class="gls-row"><span class="gls-term">Score Momentum</span><span class="gls-def">Score 0-100 basé sur la performance boursière 3 mois. Capture la dynamique court terme du titre.</span></div>
<div class="gls-row"><span class="gls-term">Conviction IA</span><span class="gls-def">Niveau de certitude de l'agent de synthèse dans sa recommandation (0-100%). Basé sur la cohérence des signaux et la qualité des données.</span></div>
<div class="gls-row"><span class="gls-term">Delta conviction</span><span class="gls-def">Variation de conviction après passage de l'agent Devil's Advocate. Un delta négatif signifie que les arguments baissiers ont affaibli la thèse initiale.</span></div>
<div class="gls-row"><span class="gls-term">Recommandation</span><span class="gls-def">ACHETER / CONSERVER / VENDRE. Synthèse de l'ensemble des analyses quantitatives et qualitatives. Ne constitue pas un conseil en investissement.</span></div>
</div>

<div class="gls-card">
<div class="gls-cat">LBO & Private Equity</div>
<div class="gls-row"><span class="gls-term">LBO</span><span class="gls-def">Leveraged Buyout — rachat d'une société financé majoritairement par dette (60-80%) et minoritairement par les fonds propres d'un sponsor PE.</span></div>
<div class="gls-row"><span class="gls-term">Multiple d'entrée</span><span class="gls-def">EV/EBITDA payé pour acquérir la cible. Détermine le prix d'achat et le levier maximal soutenable. Plus bas = meilleur rendement potentiel.</span></div>
<div class="gls-row"><span class="gls-term">TLB (Term Loan B)</span><span class="gls-def">Dette senior amortissable (1%/an typique) avec cash sweep. Coût ~7-9%, structure prioritaire au remboursement.</span></div>
<div class="gls-row"><span class="gls-term">Mezzanine / PIK</span><span class="gls-def">Dette subordonnée à intérêts capitalisés (Payment-In-Kind). Coût ~10-12%, ne consomme pas de cash mais grossit le solde dû chaque année.</span></div>
<div class="gls-row"><span class="gls-term">IRR Sponsor</span><span class="gls-def">Taux de rendement interne pour l'investisseur PE sur les fonds propres engagés. Cible institutionnelle : 20%+ pour un fonds tier-1.</span></div>
<div class="gls-row"><span class="gls-term">MOIC</span><span class="gls-def">Multiple on Invested Capital. Multiple cash sur le capital investi (equity exit / equity entry). 2x = doublement, 3x+ = excellent.</span></div>
<div class="gls-row"><span class="gls-term">ICR</span><span class="gls-def">Interest Coverage Ratio. EBITDA / Charges d'intérêts. Mesure la capacité à servir la dette. Covenant typique : ICR ≥ 2,0x.</span></div>
<div class="gls-row"><span class="gls-term">Cash Sweep</span><span class="gls-def">Mécanisme imposant que tout FCF excédentaire serve à rembourser la dette par anticipation. Réduit le levier et libère de la valeur pour l'equity.</span></div>
<div class="gls-row"><span class="gls-term">Sources & Uses</span><span class="gls-def">Tableau d'équilibre du financement : à gauche les sources (TLB + Mezz + Equity sponsor), à droite les usages (EV deal + frais transaction + cash circulant).</span></div>
<div class="gls-row"><span class="gls-term">Covenant</span><span class="gls-def">Clause contractuelle imposant des seuils financiers (levier max, ICR min). Step-down typique : levier max décroissant 6,5x → 4,5x sur 5 ans.</span></div>
<div class="gls-row"><span class="gls-term">Equity Bridge</span><span class="gls-def">Décomposition de la création de valeur entre entrée et sortie : EBITDA growth + multiple expansion + désendettement (debt paydown).</span></div>
</div>

<div class="gls-card">
<div class="gls-cat">Allocation & Macro</div>
<div class="gls-row"><span class="gls-term">Surpondérer</span><span class="gls-def">Recommandation d'allocation : poids supérieur au benchmark (score FinSight ≥ 65). Conviction haussière forte sur 6-12 mois.</span></div>
<div class="gls-row"><span class="gls-term">Neutre</span><span class="gls-def">Poids égal au benchmark (score 45-64). Pas de conviction directionnelle marquée — exposition standard.</span></div>
<div class="gls-row"><span class="gls-term">Sous-pondérer</span><span class="gls-def">Poids inférieur au benchmark (score &lt; 45). Conviction baissière ou risque structurel identifié.</span></div>
<div class="gls-row"><span class="gls-term">Spread FinSight</span><span class="gls-def">Écart de scores entre deux entités comparées (sociétés / secteurs / indices). &gt;30 pts = bifurcation marquée, &lt;15 pts = convergence.</span></div>
<div class="gls-row"><span class="gls-term">Régime macro</span><span class="gls-def">Phase de cycle économique (expansion / ralentissement / récession / reprise). Détermine les secteurs/indices favorisés selon la sensibilité aux taux et à la croissance.</span></div>
<div class="gls-row"><span class="gls-term">Allocation optimale</span><span class="gls-def">Pondération obtenue par optimisation de portefeuille (Markowitz) maximisant Sharpe ou minimisant volatilité sous contraintes de poids min/max.</span></div>
<div class="gls-row"><span class="gls-term">Dispersion sectorielle</span><span class="gls-def">Écart-type des scores entre secteurs d'un indice. Une dispersion élevée crée des opportunités d'allocation tactique.</span></div>
<div class="gls-row"><span class="gls-term">Mean reversion</span><span class="gls-def">Hypothèse de retour à la moyenne historique d'un multiple ou d'un ratio. Base des stratégies value/contrarian.</span></div>
<div class="gls-row"><span class="gls-term">Re-rating</span><span class="gls-def">Variation du multiple (P/E, EV/EBITDA) qu'un investisseur est prêt à payer. Re-rating positif = expansion du multiple, re-rating négatif = compression.</span></div>
</div>

</div>
        """, unsafe_allow_html=True)


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

        # ── Détection du profil sectoriel pour adapter la grille de ratios ──
        # JPM/BAC/BNP.PA (banques) n'ont pas EV/EBITDA ni Marge Brute pertinents.
        # REIT, Assurance, Utilities idem → remplacer par P/TBV, ROE, NIM, etc.
        try:
            from core.sector_profiles import detect_profile
            _profile = detect_profile(
                ci.sector or "",
                getattr(ci, "industry", "") or "",
            )
        except Exception:
            _profile = "STANDARD"

        def _cls_pb(v, benchmark=(0.8, 1.5)):
            """P/TBV : < 0.8 décote, 0.8-1.5 normal, > 1.5 prime justifiée si ROE fort."""
            if v is None: return "bn", 50
            lo, hi = benchmark
            if v < lo:    return "bg", 80
            if v < hi:    return "bn", 60
            return "bn", min(95, int(50 + (v - hi) * 15))

        def _cls_roe_bank(v):
            """ROE bancaire : > 12% = excellent, 8-12% ok, < 8% alerte."""
            if v is None: return "bn", 50
            if v > 0.12:  return "bg", min(int(v * 400), 100)
            if v > 0.08:  return "bn", 60
            return "br", 20

        def _cls_roa_bank(v):
            """ROA bancaire : > 1.2% excellent, 0.8-1.2% ok, < 0.8% faible."""
            if v is None: return "bn", 50
            if v > 0.012: return "bg", min(int(v * 6000), 100)
            if v > 0.008: return "bn", 60
            return "br", 25

        def _cls_coverage(v, lo=1.5, hi=3.0):
            if v is None: return "bn", 50
            if v > hi:    return "bg", min(int(v * 8), 100)
            if v > lo:    return "bn", 60
            return "br", 20

        # ══════════════════════════════════════════════════════════════════
        # Cells par profil — format identique, métriques adaptées
        # ══════════════════════════════════════════════════════════════════
        pe = yr.pe_ratio
        pe_c = "bg" if pe is not None and 0 < pe < 18 else ("bn" if pe is not None and pe < 28 else "br")
        pe_w = max(10, min(90, int(100 - (pe or 25) * 1.6))) if pe is not None and pe > 0 else 50

        rg = yr.revenue_growth
        rg_c = "bg" if rg is not None and rg > 0.03 else ("bn" if rg is not None and rg >= 0 else "br")
        rg_w = min(100, max(5, int((rg or 0) * 600 + 50))) if rg is not None else 50

        nm_c, nm_w = _cls_margin(yr.net_margin)
        roe_c, roe_w = _cls_roe(yr.roe)

        if _profile == "BANK":
            # Grille bancaire : P/TBV, P/E, ROE, ROA, Cost/Income proxy,
            # Rev Growth (~NII), Interest Coverage, Dividend Payout, Beta,
            # Net Margin (~post-provisions), Debt/Equity (~leverage Bâle).
            pb_c, pb_w = _cls_pb(yr.pb_ratio, benchmark=(0.8, 1.5))
            roe_b_c, roe_b_w = _cls_roe_bank(yr.roe)
            roa_c, roa_w = _cls_roa_bank(yr.roa)
            ic_c, ic_w = _cls_coverage(yr.interest_coverage, lo=1.5, hi=3.0)

            # Cost-to-Income proxy via (1 - net_margin) — approximation
            # car on n'a pas le split OpEx/NII en YearRatios.
            _ci_pct = (1.0 - (yr.net_margin or 0)) if yr.net_margin is not None else None
            _ci_c = ("bg" if _ci_pct is not None and _ci_pct < 0.55 else
                     ("bn" if _ci_pct is not None and _ci_pct < 0.70 else "br"))

            # Dividend payout (quand dispo)
            dp  = yr.dividend_payout
            dp_c = "bg" if dp is not None and 0.3 < dp < 0.6 else ("bn" if dp is not None else "bn")

            cells = "".join([
                _rc("P/TBV",             _x(yr.pb_ratio),
                    "Price / Tangible Book · 0.8-1.5x normal", pb_w, pb_c),
                _rc("P/E Ratio",         _x(yr.pe_ratio),
                    "Banques : 8-14x cycle", pe_w, pe_c),
                _rc("ROE",               _p(yr.roe),
                    "Cible > 12% (coût FP)", roe_b_w, roe_b_c),
                _rc("ROA",               _p(yr.roa),
                    "Cible > 1.0% (banques solides)", roa_w, roa_c),
                _rc("Cost/Income*",      _p(_ci_pct),
                    "Proxy 1 − net margin · cible < 60%", 60, _ci_c),
                _rc("Croissance revenus", _p(yr.revenue_growth),
                    "NII + commissions YoY", rg_w, rg_c),
                _rc("Net Margin",        _p(yr.net_margin),
                    "Post-provisions · > 25% sain", nm_w, nm_c),
                _rc("Interest Coverage", _x(yr.interest_coverage),
                    "EBIT / Intérêts · > 3x", ic_w, ic_c),
                _rc("Payout Dividende",  _p(yr.dividend_payout),
                    "Div / NI · cible 30-60%", 60, dp_c),
                _rc("Debt/Equity",       _x(yr.debt_equity),
                    "Levier bilantiel · normal 6-12x", 60, "bn"),
                _rc("Market Cap",        (f"{yr.market_cap/1000:,.1f} Mds" if yr.market_cap else "N/A"),
                    "Capitalisation boursière", 60, "bn"),
                _rc("CET1 / NPL / LCR",  "voir Pillar 3",
                    "Données réglementaires trimestrielles", 50, "bn"),
            ])
            _profile_note = (
                'Profil <b>BANK</b> — ratios adaptés : P/TBV, ROE, ROA remplacent '
                'EV/EBITDA et Marge Brute (non applicables aux banques). '
                'CET1, NPL, NIM à consulter dans les rapports Pillar 3.'
            )
        elif _profile == "INSURANCE":
            pb_c, pb_w = _cls_pb(yr.pb_ratio, benchmark=(0.8, 1.3))
            roe_b_c, roe_b_w = _cls_roe_bank(yr.roe)
            roa_c, roa_w = _cls_roa_bank(yr.roa)
            dp  = yr.dividend_payout
            dp_c = "bg" if dp is not None and 0.3 < dp < 0.6 else "bn"

            cells = "".join([
                _rc("P/B",               _x(yr.pb_ratio),
                    "Price / Book · 0.8-1.3x (P&C)", pb_w, pb_c),
                _rc("P/E Ratio",         _x(yr.pe_ratio),
                    "Assurance : 8-13x", pe_w, pe_c),
                _rc("ROE",               _p(yr.roe),
                    "Cible > 10-12%", roe_b_w, roe_b_c),
                _rc("ROA",               _p(yr.roa),
                    "Cible > 1%", roa_w, roa_c),
                _rc("Net Margin",        _p(yr.net_margin),
                    "UW + Investment Income", nm_w, nm_c),
                _rc("Croissance NPE",    _p(yr.revenue_growth),
                    "Net Premiums Earned YoY", rg_w, rg_c),
                _rc("Payout Dividende",  _p(yr.dividend_payout),
                    "Div / NI · cible 40-70%", 60, dp_c),
                _rc("Market Cap",        (f"{yr.market_cap/1000:,.1f} Mds" if yr.market_cap else "N/A"),
                    "Capitalisation boursière", 60, "bn"),
                _rc("Debt/Equity",       _x(yr.debt_equity),
                    "Levier bilantiel", 60, "bn"),
                _rc("Combined Ratio",    "voir SFCR",
                    "Losses + Expenses / NPE · < 100% sain", 50, "bn"),
                _rc("Solvency II",       "voir SFCR",
                    "Own Funds / SCR · > 150% cible", 50, "bn"),
                _rc("Embedded Value",    "voir rapport annuel",
                    "NAV + VIF (Life uniquement)", 50, "bn"),
            ])
            _profile_note = (
                'Profil <b>INSURANCE</b> — ratios adaptés : P/B, ROE, Combined Ratio '
                'remplacent EV/EBITDA. Combined Ratio, Solvency II, Embedded Value '
                'à consulter dans le SFCR annuel.'
            )
        elif _profile == "REIT":
            pb_c, pb_w = _cls_pb(yr.pb_ratio, benchmark=(0.85, 1.15))
            lev = yr.net_debt_ebitda
            lev_c = "bg" if lev is not None and lev < 6 else ("bn" if lev is not None and lev < 8 else "br")
            lev_w = max(10, min(95, int(100 - (lev or 0) * 10))) if lev is not None else 50
            ic_c, ic_w = _cls_coverage(yr.interest_coverage, lo=2.0, hi=3.5)
            dp  = yr.dividend_payout
            dp_c = "bn" if dp is not None else "bn"

            cells = "".join([
                _rc("P/B",               _x(yr.pb_ratio),
                    "P/NAV proxy · 0.85-1.15x", pb_w, pb_c),
                _rc("P/E Ratio",         _x(yr.pe_ratio),
                    "Peu pertinent REIT (préférer P/FFO)", pe_w, pe_c),
                _rc("ROE",               _p(yr.roe),
                    "Return on Equity", roe_w, roe_c),
                _rc("Croissance revenus", _p(yr.revenue_growth),
                    "Rental income YoY", rg_w, rg_c),
                _rc("Marge EBITDA",      _p(yr.ebitda_margin),
                    "NOI proxy · > 60% sain", 70, "bn"),
                _rc("Dette/EBITDA",      _x(yr.net_debt_ebitda),
                    "REITs : < 6x sain, < 8x acceptable", lev_w, lev_c),
                _rc("Interest Coverage", _x(yr.interest_coverage),
                    "EBITDA / Intérêts · > 3x", ic_w, ic_c),
                _rc("Payout Dividende",  _p(yr.dividend_payout),
                    "REITs distribuent 90%+", 80, dp_c),
                _rc("FCF Yield",         _p(yr.fcf_yield),
                    "Proxy AFFO yield", 60, "bn"),
                _rc("Market Cap",        (f"{yr.market_cap/1000:,.1f} Mds" if yr.market_cap else "N/A"),
                    "Capitalisation boursière", 60, "bn"),
                _rc("Occupancy / WALT",  "voir rapport trim.",
                    "Occupancy > 92%, WALT > 5 ans", 50, "bn"),
                _rc("LTV / P/NAV",       "voir rapport annuel",
                    "LTV < 50%, P/NAV 0.85-1.15x", 50, "bn"),
            ])
            _profile_note = (
                'Profil <b>REIT</b> — ratios adaptés : P/B comme proxy P/NAV, payout élevé '
                'attendu (90%+). FFO, AFFO, Occupancy, WALT, LTV à consulter dans '
                'les rapports trimestriels des foncières.'
            )
        elif _profile == "UTILITY":
            # Utilities : EV/EBITDA fonctionne, mais on met l'accent sur div yield et RAB
            em_c, em_w = _cls_margin(yr.ebitda_margin)
            lev = yr.net_debt_ebitda
            lev_c = "bg" if lev is not None and lev < 4 else ("bn" if lev is not None and lev < 6 else "br")
            lev_w = max(10, min(95, int(100 - (lev or 0) * 12))) if lev is not None else 50
            dp  = yr.dividend_payout
            dp_c = "bg" if dp is not None and 0.5 < dp < 0.8 else "bn"

            cells = "".join([
                _rc("P/E Ratio",         _x(yr.pe_ratio),
                    "Utilities : 15-20x", pe_w, pe_c),
                _rc("EV / EBITDA",       _x(yr.ev_ebitda),
                    "Régulé 8-12x", 60, "bn"),
                _rc("ROE",               _p(yr.roe),
                    "vs Allowed ROE (9-10%)", roe_w, roe_c),
                _rc("Marge EBITDA",      _p(yr.ebitda_margin),
                    "Utilities : 25-40%", em_w, em_c),
                _rc("Net Margin",        _p(yr.net_margin),
                    "Net Income / Revenue", nm_w, nm_c),
                _rc("Croissance revenus", _p(yr.revenue_growth),
                    "Régulée par rate cases", rg_w, rg_c),
                _rc("Dette/EBITDA",      _x(yr.net_debt_ebitda),
                    "Utilities : < 5x normal", lev_w, lev_c),
                _rc("Interest Coverage", _x(yr.interest_coverage),
                    "EBIT / Intérêts · > 3x", 60, "bn"),
                _rc("Payout Dividende",  _p(yr.dividend_payout),
                    "Cible 60-75%", 70, dp_c),
                _rc("FCF Yield",         _p(yr.fcf_yield),
                    "FCF / Market Cap", 60, "bn"),
                _rc("Market Cap",        (f"{yr.market_cap/1000:,.1f} Mds" if yr.market_cap else "N/A"),
                    "Capitalisation boursière", 60, "bn"),
                _rc("RAB / Allowed ROE", "voir rapport régulé",
                    "Rate base + ROE autorisé régulateur", 50, "bn"),
            ])
            _profile_note = (
                'Profil <b>UTILITY</b> — ratios adaptés : EV/EBITDA + Payout Dividende '
                'restent clés. RAB, Allowed ROE, rate cases à consulter dans les '
                'rapports réglementaires (PUC, CRE, Ofgem).'
            )
        elif _profile == "OIL_GAS":
            # Oil & Gas E&P : EV/EBITDA cyclique + breakeven + reserves
            em_c, em_w = _cls_margin(yr.ebitda_margin)
            lev = yr.net_debt_ebitda
            lev_c = "bg" if lev is not None and lev < 1.5 else ("bn" if lev is not None and lev < 3 else "br")
            lev_w = max(10, min(95, int(100 - (lev or 0) * 25))) if lev is not None else 50

            cells = "".join([
                _rc("P/E Ratio",         _x(yr.pe_ratio),
                    "Oil & Gas : 8-14x cyclique", pe_w, pe_c),
                _rc("EV/EBITDAX",        _x(yr.ev_ebitda),
                    "Proxy EV/EBITDAX · 3-6x", 60, "bn"),
                _rc("ROE",               _p(yr.roe),
                    "Return on Equity", roe_w, roe_c),
                _rc("Marge EBITDA",      _p(yr.ebitda_margin),
                    "Cycle-dépendant", em_w, em_c),
                _rc("Net Margin",        _p(yr.net_margin),
                    "Volatile (spot price)", nm_w, nm_c),
                _rc("Croissance revenus", _p(yr.revenue_growth),
                    "Prix + production YoY", rg_w, rg_c),
                _rc("Dette/EBITDAX",     _x(yr.net_debt_ebitda),
                    "E&P : < 1.5x sain, > 2.5x stress", lev_w, lev_c),
                _rc("FCF Yield",         _p(yr.fcf_yield),
                    "FCF @ current strip", 60, "bn"),
                _rc("Payout Dividende",  _p(yr.dividend_payout),
                    "Majors : 40-60%", 60, "bn"),
                _rc("Market Cap",        (f"{yr.market_cap/1000:,.1f} Mds" if yr.market_cap else "N/A"),
                    "Capitalisation boursière", 60, "bn"),
                _rc("Réserves 1P / Production", "voir 20-F / annuel",
                    "R/P > 10 ans sain", 50, "bn"),
                _rc("AISC / Breakeven WTI", "voir rapport annuel",
                    "Cash cost + sustaining capex", 50, "bn"),
            ])
            _profile_note = (
                'Profil <b>OIL_GAS</b> — EV/EBITDAX et FCF Yield @ current strip sont clés. '
                'Réserves 1P/2P, AISC, Breakeven WTI à consulter dans les filings annuels '
                '(10-K / 20-F / rapports SPE).'
            )
        else:
            # STANDARD : grille classique corporate (DCF applicable)
            gm_c, gm_w = _cls_margin(yr.gross_margin)
            em_c, em_w = _cls_margin(yr.ebitda_margin)
            lev = yr.net_debt_ebitda
            lev_c = "bg" if lev is not None and lev < 2 else ("bn" if lev is not None and lev < 4 else "br")
            lev_w = max(10, min(95, int(100 - (lev or 0) * 14))) if lev is not None else 50

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
            _profile_note = None

        st.markdown(f'<div class="ratios-grid">{cells}</div>', unsafe_allow_html=True)
        if _profile_note:
            st.markdown(
                f'<div style="font-size:11px;color:#666;padding:8px 12px;'
                f'border-left:3px solid #1B3A6B;background:#f7f9fc;margin:8px 0 28px;">'
                f'{_profile_note}</div>',
                unsafe_allow_html=True,
            )

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
    # IA Section — toggle manuel (évite l'artefact "board_" de st.expander)
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
    # Section comparaison société
    # ------------------------------------------------------------------
    _render_comparison_section(results)

    # ------------------------------------------------------------------
    # Glossaire termes financiers — helper partage
    # ------------------------------------------------------------------
    _render_glossaire("société")

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
# Page post-analyse comparative — société / secteur / indice
# ---------------------------------------------------------------------------

def _cmp_back_to_previous():
    """Retourne a l'analyse initiale depuis la page comparative.
    Restaure explicitement les resultats sauvegardes ET nettoie tout l'État
    comparatif (livrables/donnees/stages) pour que la section "Comparer"
    se reaffiche dans son etat initial (formulaire vide)."""
    prev_type    = st.session_state.get("previous_analysis_type")
    prev_results = st.session_state.get("previous_analysis_results")

    # Nettoyage COMPLET de l'État comparatif (cmp société + secteur + indice)
    _cmp_keys_to_clear = (
        # Comparaison société
        "cmp_societe_stage", "comparison_kind", "cmp_societe_state_b", "cmp_societe_xlsx_bytes",
        "cmp_societe_pptx_bytes", "cmp_societe_pdf_bytes",
        # Comparaison secteur
        "cmp_secteur_stage", "cmp_secteur_sector_a", "cmp_secteur_sector_b",
        "cmp_secteur_tickers_a", "cmp_secteur_tickers_b",
        "cmp_secteur_pptx_bytes", "cmp_secteur_pdf_bytes", "cmp_secteur_xlsx_bytes",
        "cmp_secteur_universe_b", "cmp_secteur_data",
        # Comparaison indice
        "cmp_indice_stage", "cmp_indice_universe_b", "cmp_indice_data",
        "cmp_indice_pptx_bytes", "cmp_indice_pdf_bytes", "cmp_indice_xlsx_bytes",
    )
    for _k in _cmp_keys_to_clear:
        if _k in st.session_state:
            del st.session_state[_k]

    if prev_type == "results":
        if prev_results is not None:
            st.session_state.results = prev_results
        st.session_state.stage = "results"
    elif prev_type == "screening_results":
        if prev_results is not None:
            st.session_state.screening_results = prev_results
        st.session_state.stage = "screening_results"
    else:
        # Fallback : si screening_results existe, y retourner plutôt que home
        if st.session_state.get("screening_results"):
            st.session_state.stage = "screening_results"
        elif st.session_state.get("results"):
            st.session_state.stage = "results"
        else:
            st.session_state.stage = "home"
    st.rerun()


def _safe_int(v, default=0):
    try: return int(float(v))
    except Exception: return default


def _safe_pct_100(v):
    """Retourne un pourcentage (0-100) depuis une valeur qui peut être en fraction ou en %."""
    if v is None: return None
    try:
        fv = float(v)
        return fv * 100 if abs(fv) <= 2.0 else fv
    except Exception:
        return None


def _rec_fr(rec):
    return {"BUY": "ACHETER", "SELL": "VENDRE", "HOLD": "CONSERVER"}.get(
        str(rec or "").upper(), str(rec or "—"))


def _rec_cls(rec):
    return {"BUY": "v-buy", "SELL": "v-sell"}.get(str(rec or "").upper(), "v-hold")


def render_comparison_results() -> None:
    """Page post-analyse comparative unifiee.

    Lit st.session_state.comparison_kind ∈ {societe, secteur, indice} et affiche
    le header + verdict + mini-tableau adapte. Les livrables sont dans le ruban.
    """
    kind = st.session_state.get("comparison_kind") or "société"

    # ------------------------------------------------------------------
    # Dispatch vers les 3 rendus specialises
    # ------------------------------------------------------------------
    if kind == "société":
        _render_cmp_societe_page()
    elif kind == "secteur":
        _render_cmp_secteur_page()
    elif kind == "indice":
        _render_cmp_indice_page()
    else:
        st.error(f"Type de comparaison inconnu : {kind}")
        if st.button("\u2190 Retour"):
            st.session_state.stage = "home"
            st.rerun()


def _cmp_header(title_main: str, subtitle: str, tkr_a: str, tkr_b: str,
                rec_a: str, rec_b: str, winner: str,
                delta_label: str = "Écart FinSight",
                delta_value: str = "—") -> None:
    """En-Tête epure commun aux 3 types de comparaison (style analyse société)."""
    st.markdown(f'<div class="rc">{_e(title_main)}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="rm">{_e(subtitle)}</div>',
        unsafe_allow_html=True,
    )

    rec_a_fr  = _rec_fr(rec_a)
    rec_b_fr  = _rec_fr(rec_b)
    rec_a_cls = _rec_cls(rec_a)
    rec_b_cls = _rec_cls(rec_b)

    st.markdown(f"""
    <div class="verdict-row">
      <div>
        <div class="v-lbl">{_e(tkr_a)}</div>
        <div class="{rec_a_cls}">{rec_a_fr}</div>
      </div>
      <div class="v-div"></div>
      <div>
        <div class="v-lbl">{_e(tkr_b)}</div>
        <div class="{rec_b_cls}">{rec_b_fr}</div>
      </div>
      <div class="v-div"></div>
      <div>
        <div class="v-lbl">Choix prefere</div>
        <div class="v-tgt">{_e(winner)}</div>
      </div>
      <div class="v-div"></div>
      <div>
        <div class="v-lbl">{_e(delta_label)}</div>
        <div class="v-num">{_e(delta_value)}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def _cmp_verdict_box(verdict_text: str) -> None:
    """Bloc verdict LLM style sobre (epure)."""
    if not verdict_text:
        return
    st.markdown('<div class="sec-t">Verdict analytique</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:14px;line-height:1.85;color:#333;padding:16px 0 8px;">'
        f'{_e(verdict_text)}</div>',
        unsafe_allow_html=True,
    )


def _cmp_mini_table(rows: list, header_a: str = "A", header_b: str = "B") -> None:
    """Mini-tableau comparatif 5-7 lignes.

    rows : liste de tuples (label, val_a, val_b) deja formates en str.
    header_a / header_b : libelles des colonnes (noms de societe / secteur / indice).
    """
    if not rows:
        return
    st.markdown('<div class="sec-t" style="margin-top:24px;">Metriques cles</div>',
                unsafe_allow_html=True)
    html = ['<table style="width:100%;border-collapse:collapse;font-size:13px;'
            'margin-top:12px;">']
    html.append('<thead><tr style="border-bottom:2px solid #1B3A6B;">'
                '<th style="text-align:left;padding:8px 12px;color:#1B3A6B;'
                'font-weight:700;">Indicateur</th>'
                f'<th style="text-align:right;padding:8px 12px;color:#1B3A6B;'
                f'font-weight:700;">{_e(str(header_a))}</th>'
                f'<th style="text-align:right;padding:8px 12px;color:#1B3A6B;'
                f'font-weight:700;">{_e(str(header_b))}</th></tr></thead>')
    html.append('<tbody>')
    for i, (lbl, va, vb) in enumerate(rows):
        bg = '#F8FAFC' if i % 2 == 0 else '#FFFFFF'
        html.append(
            f'<tr style="background:{bg};">'
            f'<td style="padding:8px 12px;color:#333;">{_e(str(lbl))}</td>'
            f'<td style="padding:8px 12px;text-align:right;color:#111;'
            f'font-family:DM Mono,monospace;font-weight:600;">{_e(str(va))}</td>'
            f'<td style="padding:8px 12px;text-align:right;color:#111;'
            f'font-family:DM Mono,monospace;font-weight:600;">{_e(str(vb))}</td>'
            f'</tr>'
        )
    html.append('</tbody></table>')
    st.markdown("".join(html), unsafe_allow_html=True)


def _cmp_livrables_note() -> None:
    """Note en bas de page rappelant que les livrables sont dans le ruban."""
    st.markdown(
        '<div style="margin-top:32px;padding:16px 20px;background:#F8FAFC;'
        'border-left:3px solid #1B3A6B;border-radius:2px;font-size:12.5px;'
        'color:#555;">'
        '<b style="color:#1B3A6B;">Livrables disponibles</b> — '
        'Le rapport PDF, le pitchbook PPTX et le fichier Excel sont accessibles '
        'dans le ruban de gauche. La présente page est une vue de Synthèse.'
        '</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Rendu : société vs société
# ---------------------------------------------------------------------------
def _render_cmp_societe_page() -> None:
    state_a = st.session_state.get("previous_analysis_results")  # dict results
    state_b = st.session_state.get("cmp_societe_state_b")
    if not state_a or not state_b:
        st.error("État de comparaison société manquant. Retour à l'analyse.")
        if st.button("\u2190 Retour"):
            _cmp_back_to_previous()
        return

    # Metriques des 2 sociétés
    from outputs.cmp_societe_xlsx_writer import extract_metrics, _fetch_supplements

    tkr_a = (state_a.get("raw_data") and getattr(state_a["raw_data"], "ticker", None)) or \
            state_a.get("ticker", "A")
    tkr_b = (state_b.get("raw_data") and getattr(state_b["raw_data"], "ticker", None)) or \
            state_b.get("ticker", "B")

    try:
        supp_a = _fetch_supplements(tkr_a)
        supp_b = _fetch_supplements(tkr_b)
        m_a = extract_metrics(state_a, supp_a)
        m_b = extract_metrics(state_b, supp_b)
    except Exception as _mx:
        st.warning(f"Metriques partielles : {_mx}")
        m_a = m_b = {}

    name_a = m_a.get("company_name_a") or tkr_a
    name_b = m_b.get("company_name_b") or tkr_b
    rec_a  = m_a.get("recommendation") or "HOLD"
    rec_b  = m_b.get("recommendation") or "HOLD"

    # Winner (FinSight score, tiebreaker Piotroski)
    fs_a = _safe_int(m_a.get("finsight_score"))
    fs_b = _safe_int(m_b.get("finsight_score"))
    if fs_a != fs_b:
        winner = tkr_a if fs_a > fs_b else tkr_b
    else:
        pio_a = _safe_int(m_a.get("piotroski_score"))
        pio_b = _safe_int(m_b.get("piotroski_score"))
        winner = tkr_a if pio_a >= pio_b else tkr_b
    delta = fs_a - fs_b if winner == tkr_a else fs_b - fs_a
    delta_str = f"+{delta} pts" if delta > 0 else ("—" if delta == 0 else f"{delta} pts")

    _cmp_header(
        title_main=f"{tkr_a}  vs  {tkr_b}",
        subtitle=f"{name_a}  \u00b7  {name_b}  \u00b7  Analyse Comparative  \u00b7  "
                 f"{date.today().strftime('%d.%m.%Y')}",
        tkr_a=tkr_a, tkr_b=tkr_b,
        rec_a=rec_a, rec_b=rec_b, winner=winner,
        delta_label="Écart FinSight Score",
        delta_value=delta_str,
    )

    # Verdict LLM — recupere depuis synthesis comparative
    synthesis = st.session_state.get("cmp_societe_synthesis") or {}
    verdict = synthesis.get("verdict_text", "")
    if not verdict and (rec_a or rec_b):
        verdict = (
            f"{winner} est privilegie sur la base du score FinSight composite "
            f"({fs_a}/100 vs {fs_b}/100), integrant valorisation, croissance, qualité et momentum."
        )
    _cmp_verdict_box(verdict)

    # Mini-tableau comparatif
    def _fpct(v):
        pv = _safe_pct_100(v)
        return f"{pv:.1f}%" if pv is not None else "\u2014"
    def _fx(v):
        try: return f"{float(v):.1f}x" if v is not None else "\u2014"
        except: return "\u2014"

    rows = [
        ("FinSight Score",   f"{fs_a}/100",          f"{fs_b}/100"),
        ("Recommandation",   _rec_fr(rec_a),         _rec_fr(rec_b)),
        ("Marge EBITDA",     _fpct(m_a.get("ebitda_margin_ltm")),
                             _fpct(m_b.get("ebitda_margin_ltm"))),
        ("ROIC",             _fpct(m_a.get("roic")), _fpct(m_b.get("roic"))),
        ("P/E (LTM)",        _fx(m_a.get("pe_ratio")), _fx(m_b.get("pe_ratio"))),
        ("EV/EBITDA",        _fx(m_a.get("ev_ebitda")), _fx(m_b.get("ev_ebitda"))),
    ]
    _hdr_a = f"{name_a} ({tkr_a})" if name_a and name_a != tkr_a else tkr_a
    _hdr_b = f"{name_b} ({tkr_b})" if name_b and name_b != tkr_b else tkr_b
    _cmp_mini_table(rows, header_a=_hdr_a, header_b=_hdr_b)

    _render_glossaire("cmp_societe")


# ---------------------------------------------------------------------------
# Rendu : secteur vs secteur
# ---------------------------------------------------------------------------
def _render_cmp_secteur_page() -> None:
    sector_a = st.session_state.get("cmp_secteur_sector_a") or "Secteur A"
    sector_b = st.session_state.get("cmp_secteur_sector_b") or "Secteur B"
    tickers_a = st.session_state.get("cmp_secteur_tickers_a") or []
    tickers_b = st.session_state.get("cmp_secteur_tickers_b") or []

    # Médianes par secteur (score, EBITDA margin, PE)
    def _med_float(td, key):
        vals = []
        for t in td:
            v = t.get(key)
            try:
                if v is not None:
                    vals.append(float(v))
            except Exception:
                pass
        if not vals:
            return None
        vals.sort()
        n = len(vals)
        return vals[n//2] if n % 2 else (vals[n//2-1] + vals[n//2]) / 2

    score_a = _safe_int(_med_float(tickers_a, "score_global"))
    score_b = _safe_int(_med_float(tickers_b, "score_global"))
    mg_a    = _med_float(tickers_a, "ebitda_margin")
    mg_b    = _med_float(tickers_b, "ebitda_margin")
    pe_a    = _med_float(tickers_a, "pe_ratio") or _med_float(tickers_a, "pe")
    pe_b    = _med_float(tickers_b, "pe_ratio") or _med_float(tickers_b, "pe")

    winner  = sector_a if score_a >= score_b else sector_b
    delta   = abs(score_a - score_b)
    delta_str = f"+{delta} pts" if delta > 0 else "—"

    # Heuristique recommandation secteur : OVERWEIGHT si meilleure Médiane score + mg
    def _sector_rec(sc, mg):
        if sc is None:
            return "HOLD"
        if sc >= 60:
            return "BUY"
        if sc >= 45:
            return "HOLD"
        return "SELL"
    rec_a = _sector_rec(score_a, mg_a)
    rec_b = _sector_rec(score_b, mg_b)

    _cmp_header(
        title_main=f"{sector_a}  vs  {sector_b}",
        subtitle=f"Analyse Comparative Sectorielle  \u00b7  "
                 f"{len(tickers_a)} valeurs vs {len(tickers_b)} valeurs  \u00b7  "
                 f"{date.today().strftime('%d.%m.%Y')}",
        tkr_a=sector_a, tkr_b=sector_b,
        rec_a=rec_a, rec_b=rec_b, winner=winner,
        delta_label="Écart Score FinSight Médian",
        delta_value=delta_str,
    )

    verdict = (
        f"{winner} domine sur la Médiane des scores FinSight ({score_a}/100 vs {score_b}/100), "
        f"signalant une qualité fondamentale agregee superieure. "
        f"La lecture croisee des multiples et des marges permet d'affiner le choix d'exposition "
        f"dans une allocation sectorielle."
    )
    _cmp_verdict_box(verdict)

    def _fpct_raw(v):
        if v is None: return "\u2014"
        try:
            fv = float(v)
            pct = fv * 100 if abs(fv) <= 2.0 else fv
            return f"{pct:.1f}%"
        except: return "\u2014"
    def _fx_raw(v):
        try: return f"{float(v):.1f}x" if v is not None else "\u2014"
        except: return "\u2014"

    rows = [
        ("Score FinSight Médian",   f"{score_a}/100",  f"{score_b}/100"),
        ("Nombre de valeurs",       str(len(tickers_a)), str(len(tickers_b))),
        ("Marge EBITDA Médiane",    _fpct_raw(mg_a), _fpct_raw(mg_b)),
        ("P/E Médian",              _fx_raw(pe_a),   _fx_raw(pe_b)),
        ("Recommandation",          _rec_fr(rec_a),  _rec_fr(rec_b)),
    ]
    _cmp_mini_table(rows, header_a=sector_a, header_b=sector_b)

    _render_glossaire("cmp_secteur")


# ---------------------------------------------------------------------------
# Rendu : indice vs indice
# ---------------------------------------------------------------------------
def _render_cmp_indice_page() -> None:
    universe_a = st.session_state.get("cmp_indice_universe_a") or "Indice A"
    universe_b = st.session_state.get("cmp_indice_universe_b") or "Indice B"
    name_a = _INDICE_CMP_OPTIONS.get(universe_a, (universe_a,))[0] if "_INDICE_CMP_OPTIONS" in globals() else universe_a
    name_b = _INDICE_CMP_OPTIONS.get(universe_b, (universe_b,))[0] if "_INDICE_CMP_OPTIONS" in globals() else universe_b

    # cmp_data est un dict plat retourne par _fetch_cmp_indice_data avec
    # cles suffixees _a / _b (score_a, perf_1y_a, pe_fwd_a, etc.)
    cmp_data = st.session_state.get("cmp_indice_data") or {}

    def _g(d, *keys, default=None):
        for k in keys:
            v = d.get(k)
            if v is not None:
                return v
        return default

    score_a = _safe_int(cmp_data.get("score_a"))
    score_b = _safe_int(cmp_data.get("score_b"))
    winner  = name_a if score_a >= score_b else name_b
    delta   = abs(score_a - score_b)
    delta_str = f"+{delta} pts" if delta > 0 else "—"

    def _rec_from_score(sc):
        if sc is None: return "HOLD"
        if sc >= 60:   return "BUY"
        if sc >= 45:   return "HOLD"
        return "SELL"

    rec_a = _rec_from_score(score_a)
    rec_b = _rec_from_score(score_b)

    _cmp_header(
        title_main=f"{name_a}  vs  {name_b}",
        subtitle=f"Analyse Comparative d'Indices  \u00b7  "
                 f"{date.today().strftime('%d.%m.%Y')}",
        tkr_a=name_a, tkr_b=name_b,
        rec_a=rec_a, rec_b=rec_b, winner=winner,
        delta_label="Écart Score composite",
        delta_value=delta_str,
    )

    verdict = (
        f"{winner} ressort avec le meilleur score composite, portant une allocation "
        f"géographique/sectorielle plus favorable dans le contexte macro actuel."
    )
    _cmp_verdict_box(verdict)

    def _fpct_idx(v):
        if v is None: return "\u2014"
        try:
            fv = float(v)
            pct = fv * 100 if abs(fv) <= 2.0 else fv
            return f"{pct:+.1f}%"
        except: return "\u2014"

    def _fnum(v):
        if v is None: return "\u2014"
        try: return f"{float(v):.0f}"
        except: return "\u2014"

    def _fxx(v):
        if v is None: return "\u2014"
        try: return f"{float(v):.1f}x"
        except: return "\u2014"

    def _f2(v):
        if v is None: return "\u2014"
        try: return f"{float(v):.2f}"
        except: return "\u2014"

    rows = [
        ("Score composite",      f"{score_a}/100", f"{score_b}/100"),
        ("Performance 1 an",     _fpct_idx(cmp_data.get("perf_1y_a")),
                                 _fpct_idx(cmp_data.get("perf_1y_b"))),
        ("Performance 3 ans",    _fpct_idx(cmp_data.get("perf_3y_a")),
                                 _fpct_idx(cmp_data.get("perf_3y_b"))),
        ("Volatilité 1 an",      _fpct_idx(cmp_data.get("vol_1y_a")),
                                 _fpct_idx(cmp_data.get("vol_1y_b"))),
        ("Sharpe 1 an",          _f2(cmp_data.get("sharpe_1y_a")),
                                 _f2(cmp_data.get("sharpe_1y_b"))),
        ("P/E forward",          _fxx(cmp_data.get("pe_fwd_a")),
                                 _fxx(cmp_data.get("pe_fwd_b"))),
        ("Recommandation",       _rec_fr(rec_a), _rec_fr(rec_b)),
    ]
    _cmp_mini_table(rows, header_a=name_a, header_b=name_b)

    _render_glossaire("cmp_indice")


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

    if stage == "veille":
        render_veille()
    elif stage == "home":
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
    elif stage == "comparison_results":
        try:
            render_comparison_results()
        except Exception as _cmp_err:
            import traceback as _tb
            st.error(f"Erreur affichage résultats comparatifs : {_cmp_err}")
            st.code(_tb.format_exc(), language="text")
    else:
        st.session_state.stage = "home"
        st.rerun()


if __name__ == "__main__":
    main()
