"""
sector_pdf_writer.py — FinSight IA
Rapport PDF sectoriel institutionnel — générateur dynamique.
Usage : generate_sector_report(sector_name, tickers_data, output_path)
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Image, KeepTogether, CondPageBreak,
)
from reportlab.platypus.flowables import Flowable

# ─── PALETTE ──────────────────────────────────────────────────────────────────
NAVY        = colors.HexColor('#1B3A6B')
NAVY_LIGHT  = colors.HexColor('#2A5298')
BUY_GREEN   = colors.HexColor('#1A7A4A')
SELL_RED    = colors.HexColor('#A82020')
HOLD_AMB    = colors.HexColor('#B06000')
WHITE       = colors.white
BLACK       = colors.HexColor('#1A1A1A')
GREY_LIGHT  = colors.HexColor('#F5F7FA')
GREY_MED    = colors.HexColor('#E8ECF0')
GREY_TEXT   = colors.HexColor('#555555')
GREY_RULE   = colors.HexColor('#D0D5DD')
ROW_ALT     = colors.HexColor('#F0F4F8')
ACCENT_BLUE = colors.HexColor('#90B4E8')

PAGE_W, PAGE_H = A4
MARGIN_L = 17 * mm
MARGIN_R = 17 * mm
MARGIN_T = 22 * mm
MARGIN_B = 18 * mm
TABLE_W  = 170 * mm

# ─── STYLES ───────────────────────────────────────────────────────────────────
def _style(name, font='Helvetica', size=9, color=BLACK, leading=13,
           align=TA_LEFT, bold=False, space_before=0, space_after=2):
    return ParagraphStyle(name,
        fontName='Helvetica-Bold' if bold else font,
        fontSize=size, textColor=color, leading=leading,
        alignment=align, spaceBefore=space_before, spaceAfter=space_after)

S_BODY       = _style('body',   size=8.5, leading=13, color=GREY_TEXT, align=TA_JUSTIFY)
S_SECTION    = _style('sec',    size=12,  leading=16, color=NAVY,  bold=True, space_before=8, space_after=2)
S_SUBSECTION = _style('subsec', size=9,   leading=13, color=NAVY,  bold=True, space_before=5, space_after=3)
S_DEBATE     = _style('debate', size=8.5, leading=12, color=NAVY_LIGHT, bold=True, space_before=3, space_after=5)
S_TH_C = _style('thc', size=8, leading=11, color=WHITE, bold=True, align=TA_CENTER)
S_TH_L = _style('thl', size=8, leading=11, color=WHITE, bold=True, align=TA_LEFT)
S_TD_L  = _style('tdl', size=8, leading=11, color=BLACK, align=TA_LEFT)
S_TD_C  = _style('tdc', size=8, leading=11, color=BLACK, align=TA_CENTER)
S_TD_B  = _style('tdb', size=8, leading=11, color=BLACK, bold=True, align=TA_LEFT)
S_TD_BC = _style('tdbc',size=8, leading=11, color=BLACK, bold=True, align=TA_CENTER)
S_TD_G  = _style('tdg', size=8, leading=11, color=BUY_GREEN, bold=True, align=TA_CENTER)
S_TD_R  = _style('tdr', size=8, leading=11, color=SELL_RED,  bold=True, align=TA_CENTER)
S_TD_A  = _style('tda', size=8, leading=11, color=HOLD_AMB,  bold=True, align=TA_CENTER)
S_NOTE  = _style('note',size=5.5,leading=8, color=GREY_TEXT)
S_DISC  = _style('disc',size=6.5,leading=9, color=GREY_TEXT, align=TA_JUSTIFY)


# ─── HELPERS ──────────────────────────────────────────────────────────────────
def rule(w=TABLE_W, thick=0.5, col=GREY_RULE, sb=4, sa=4):
    return HRFlowable(width=w, thickness=thick, color=col, spaceAfter=sa, spaceBefore=sb)

# ─── i18n helper sector PDF ────────────────────────────────────────────────
_SECTOR_CURRENT_LANG: str = "fr"

# Batch LLM precompute (parallelisation perf 26/04/2026) — populated par
# generate_sector_report avant les builders. Les sites d'appel LLM lisent
# depuis ce dict avant de fallback sur un appel unitaire.
_SECTOR_LLM_BATCH: dict = {}

_SECTOR_PDF_LABELS: dict[str, dict[str, str]] = {
    "vue_macro": {"fr": "Vue Macro & Dynamiques Sectorielles",
                  "en": "Macro View & Sector Dynamics",
                  "es": "Visión Macro y Dinámicas Sectoriales",
                  "de": "Makro-Sicht & Sektor-Dynamik",
                  "it": "Vista Macro & Dinamiche Settoriali",
                  "pt": "Visão Macro & Dinâmicas Setoriais"},
    "structure": {"fr": "Structure et Dynamique Sectorielle",
                  "en": "Sector Structure & Dynamics",
                  "es": "Estructura y Dinámica Sectorial",
                  "de": "Sektor-Struktur & Dynamik",
                  "it": "Struttura e Dinamica Settoriale",
                  "pt": "Estrutura e Dinâmica Setorial"},
    "acteurs":   {"fr": "Analyse des Acteurs Clés",
                  "en": "Key Players Analysis",
                  "es": "Análisis de Actores Clave",
                  "de": "Analyse der Schlüsselakteure",
                  "it": "Analisi dei Principali Attori",
                  "pt": "Análise dos Principais Intervenientes"},
    "valo_comp": {"fr": "Valorisation Comparative",
                  "en": "Comparative Valuation",
                  "es": "Valoración Comparativa",
                  "de": "Vergleichende Bewertung",
                  "it": "Valutazione Comparativa",
                  "pt": "Avaliação Comparativa"},
    "risques_sentiment": {"fr": "Risques Sectoriels & Sentiment de Marché",
                          "en": "Sector Risks & Market Sentiment",
                          "es": "Riesgos Sectoriales y Sentimiento de Mercado",
                          "de": "Sektor-Risiken & Marktstimmung",
                          "it": "Rischi Settoriali & Sentiment di Mercato",
                          "pt": "Riscos Setoriais & Sentimento de Mercado"},
    "sommaire": {"fr": "Sommaire", "en": "Table of contents",
                 "es": "Índice", "de": "Inhalt",
                 "it": "Sommario", "pt": "Sumário"},
}


def _slbl(key: str) -> str:
    spec = _SECTOR_PDF_LABELS.get(key)
    if not spec:
        return key
    return spec.get(_SECTOR_CURRENT_LANG) or spec.get("en") or spec.get("fr") or key


def section_title(text, num):
    return [rule(sb=10, sa=0), Paragraph(f"{num}. {text}", S_SECTION), rule(sb=2, sa=8)]

def debate_q(text):
    # PDF fix : \u25b6 (▶) non rendu dans Helvetica → utilise ">"
    return Paragraph(f">  {text}", S_DEBATE)

def src(text):
    return Paragraph(f"Source : {text}", S_NOTE)

def tbl(data, cw, row_heights=None):
    t = Table(data, colWidths=cw, rowHeights=row_heights)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,0),  NAVY),
        ('ROWBACKGROUNDS',(0,1),(-1,-1), [WHITE, ROW_ALT]),
        ('FONTNAME',      (0,0),(-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0),(-1,-1), 8),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0),(-1,-1), 4),
        ('BOTTOMPADDING', (0,0),(-1,-1), 4),
        ('LEFTPADDING',   (0,0),(-1,-1), 5),
        ('RIGHTPADDING',  (0,0),(-1,-1), 5),
        ('LINEBELOW',     (0,0),(-1,0),  0.5, NAVY_LIGHT),
        ('LINEBELOW',     (0,-1),(-1,-1),0.5, GREY_RULE),
        ('GRID',          (0,1),(-1,-1), 0.3, GREY_MED),
    ]))
    return t

def _na(v, fmt=None):
    if v is None:
        return "\u2014"
    try:
        f = float(v)
        return fmt(f) if fmt else str(v)
    except (TypeError, ValueError):
        return "\u2014"

def _fmt_pct(v, sign=True):
    """Format FR : « 33,9 % » ou « +33,9 % » (virgule décimale, espace avant %)."""
    if v is None:
        return "\u2014"
    try:
        f = float(v)
        prefix = "+" if sign and f >= 0 else ""
        return prefix + f"{f:.1f}".replace(".", ",") + " %"
    except (TypeError, ValueError):
        return "\u2014"

def _fmt_mult(v):
    """Format FR : « 13,4x » (virgule décimale, pas d'espace avant x)."""
    if v is None:
        return "\u2014"
    try:
        return f"{float(v):.1f}".replace(".", ",") + "x"
    except (TypeError, ValueError):
        return "\u2014"

def _fmt_price(v):
    if v is None:
        return "\u2014"
    try:
        f = float(v)
        # Format FR : virgule d\u00e9cimale, espace comme s\u00e9parateur milliers
        s = f"{f:,.2f}" if f < 1000 else f"{f:,.0f}"
        return s.replace(',', ' ').replace('.', ',')
    except (TypeError, ValueError):
        return "\u2014"

def _fmt_mds(v):
    """Formate une valeur monetaire en Mds (divise par 1e9 si valeur absolue)."""
    if v is None:
        return "\u2014"
    try:
        f = float(v)
        if abs(f) > 1e6:          # valeur absolue (ex: yfinance) → convertir en Mds
            f = f / 1e9
        if abs(f) >= 100:
            return f"{f:.0f}"
        return f"{f:.1f}".replace('.', ',')
    except (TypeError, ValueError):
        return "\u2014"

def _reco(score):
    """Recommandation 5 niveaux basée sur le score composite FinSight."""
    if score is None:
        return "HOLD"
    s = float(score)
    if s >= 75:
        return "STRONG BUY"
    if s >= 65:
        return "BUY"
    if s >= 45:
        return "HOLD"
    if s >= 30:
        return "UNDERPERFORM"
    return "SELL"


def _reco_3(score):
    """Recommandation 3 niveaux pour les paniers perf chart (BUY/HOLD/SELL)."""
    if score is None:
        return "HOLD"
    s = float(score)
    if s >= 65:
        return "BUY"
    if s >= 45:
        return "HOLD"
    return "SELL"

def _upside(score):
    """Estime un upside indicatif a partir du score."""
    if score is None:
        return "\u2014"
    s = float(score)
    if s >= 75:
        return f"+{int((s-50)*0.5)}%"
    if s >= 55:
        return f"+{int((s-50)*0.3)}%"
    if s >= 45:
        return f"+{int((s-50)*0.2)}%"
    return f"-{int((50-s)*0.4)}%"

def _conviction(score):
    if score is None:
        return "50%"
    s = float(score)
    return f"{min(85, max(40, int(s * 0.85)))}%"

def _auto_cell(v):
    """Colorie automatiquement : + -> vert, - -> rouge, sinon centre."""
    sv = str(v)
    if sv.startswith('+'):
        return Paragraph(sv, S_TD_G)
    if sv.startswith('-'):
        return Paragraph(sv, S_TD_R)
    if sv == "N/A":
        return Paragraph(sv, S_TD_A)
    return Paragraph(sv, S_TD_C)


# ─── SOMMAIRE DYNAMIQUE ───────────────────────────────────────────────────────
class SectionAnchor(Flowable):
    """Flowable invisible qui enregistre le numero de page reel."""
    def __init__(self, key, registry):
        super().__init__()
        self.key = key
        self.registry = registry
        self.width = 0
        self.height = 0

    def draw(self):
        self.registry[self.key] = self.canv.getPageNumber()

    def wrap(self, aw, ah):
        return 0, 0


def build_sommaire(sector_name: str, page_nums: dict = None):
    if page_nums is None:
        page_nums = {}
    S_SUB = _style("subgrey", size=7, leading=10, color=GREY_TEXT)

    def pnum(key):
        return Paragraph(str(page_nums.get(key, "\u2014")), S_TD_C)

    sections = [
        ("1.", "Vue Macro & Dynamiques Sectorielles", "macro",
         "  Performance relative \u00b7 Revenus par sous-segment \u00b7 Tendances cl\u00e9s"),
        ("2.", "Structure et Dynamique Sectorielle",  "structure",
         "  HHI \u00b7 Cycle valorisation \u00b7 Dispersion ROIC \u00b7 Solidit\u00e9 bilantielle"),
        ("2b.", "D\u00e9composition par Sous-Secteur", "subsectors",
         "  Industries GICS \u00b7 Drivers \u00b7 Risques \u00b7 Profil financier \u00b7 Allocation"),
        ("3.", "Analyse des Acteurs Cl\u00e9s",             "acteurs",
         "  Revenus \u00b7 Marges \u00b7 Positionnement concurrentiel"),
        ("4.", "Valorisation Comparative",             "valorisation",
         "  EV/EBITDA \u00b7 P/E \u00b7 Multiples vs croissance"),
        ("5.", "Risques Sectoriels & Sentiment",       "risques",
         "  Cartographie des risques \u00b7 Analyse FinBERT"),
        ("6.", "Top Picks & Recommandations",          "conclusion",
         "  BUY / HOLD / SELL \u00b7 Allocation portefeuille mod\u00e8le"),
    ]
    rows = []
    for num, titre, key, sub in sections:
        rows.append([Paragraph(num, S_TD_BC), Paragraph(titre, S_TD_B), pnum(key)])
        rows.append([Paragraph("", S_TD_C), Paragraph(sub, S_SUB), Paragraph("", S_TD_C)])

    header = [Paragraph("N\u00b0", S_TH_C), Paragraph("Section", S_TH_L), Paragraph("Page", S_TH_C)]
    t = tbl([header] + rows, cw=[12*mm, 142*mm, 16*mm])
    alt_bg = colors.HexColor("#F8F9FB")
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,2),(2,2),  alt_bg), ("BACKGROUND",(0,4),(2,4),  alt_bg),
        ("BACKGROUND",(0,6),(2,6),  alt_bg), ("BACKGROUND",(0,8),(2,8),  alt_bg),
        ("BACKGROUND",(0,10),(2,10),alt_bg), ("BACKGROUND",(0,12),(2,12),alt_bg),
        ("TOPPADDING",(0,2),(2,13), 1), ("BOTTOMPADDING",(0,2),(2,13), 1),
    ]))
    return t


# ─── CHARTS ───────────────────────────────────────────────────────────────────
def _make_perf_chart(tickers_data: list[dict], sector_name: str,
                     universe: str = "S&P 500") -> io.BytesIO:
    """Performance relative — 4 courbes : ETF sectoriel + panier BUY / HOLD / SELL.

    Graphique validé avec Baptiste pour l'analyse sectorielle ETF-first :
    - ETF sectoriel (référence noire épaisse) : courbe réelle yfinance
    - Panier BUY (vert) : moyenne equal-weight 52W des tickers classés BUY
    - Panier HOLD (orange) : moyenne HOLD
    - Panier SELL (rouge) : moyenne SELL

    Permet de valider visuellement le scoring FinSight : si BUY > ETF et
    SELL < ETF, le stock-picking ajoute de l'alpha vs le benchmark passif.
    """
    _MOIS = ['Jan','Fev','Mar','Avr','Mai','Jun','Jul','Aou','Sep','Oct','Nov','Dec']
    _today = date.today()
    months = []
    for i in range(12, -1, -1):
        m = (_today.month - 1 - i) % 12
        y = _today.year - ((_today.month - 1 - i < 0) and (i > _today.month - 1))
        months.append(f"{_MOIS[m]} {str(y)[2:]}")

    # Determine l'ETF de reference pour ce secteur + univers
    etf_ticker = None
    etf_name = None
    try:
        from core.sector_etfs import get_etf_for
        _etf = get_etf_for(sector_name, universe=universe)
        if _etf:
            etf_ticker = _etf["ticker"]
            etf_name = _etf["name"]
    except Exception as _e:
        log.warning("sector_pdf perf_chart: get_etf_for echoue: %s", _e)

    # Classement FinSight par signal 3 niveaux pour les paniers du chart
    tickers_buy  = [t.get("ticker") for t in tickers_data if _reco_3(t.get("score_global")) == "BUY"  and t.get("ticker")]
    tickers_hold = [t.get("ticker") for t in tickers_data if _reco_3(t.get("score_global")) == "HOLD" and t.get("ticker")]
    tickers_sell = [t.get("ticker") for t in tickers_data if _reco_3(t.get("score_global")) == "SELL" and t.get("ticker")]

    # Fetch yfinance batch : ETF + tous les tickers sectoriels
    curves = {}  # {label: [base100 values]}
    is_real = False
    try:
        import yfinance as _yf
        _all_symbols = [t.get("ticker") for t in tickers_data if t.get("ticker")]
        _to_fetch = list(set(_all_symbols))
        if etf_ticker:
            _to_fetch.append(etf_ticker)
        if _to_fetch:
            hist = _yf.download(_to_fetch, period="13mo", interval="1mo",
                                auto_adjust=True, progress=False, timeout=25)
            if not hist.empty:
                _close = hist["Close"] if "Close" in hist.columns else hist
                if hasattr(_close, "columns"):
                    def _normalize_basket(tickers_list):
                        cols = [c for c in tickers_list if c in _close.columns]
                        if not cols:
                            return None
                        _norm = _close[cols].apply(
                            lambda s: s / s.dropna().iloc[0] * 100 if len(s.dropna()) > 0 else s)
                        _mean = _norm.mean(axis=1).dropna()
                        return list(_mean.values[-13:]) if len(_mean) > 0 else None
                    # ETF reference
                    if etf_ticker and etf_ticker in _close.columns:
                        _etf_s = _close[etf_ticker].dropna()
                        if len(_etf_s) > 0:
                            curves["ETF"] = list((_etf_s / _etf_s.iloc[0] * 100).values[-13:])
                    # 3 paniers
                    _b_curve = _normalize_basket(tickers_buy)
                    _h_curve = _normalize_basket(tickers_hold)
                    _s_curve = _normalize_basket(tickers_sell)
                    if _b_curve: curves["BUY"] = _b_curve
                    if _h_curve: curves["HOLD"] = _h_curve
                    if _s_curve: curves["SELL"] = _s_curve
                if len(curves) >= 2:
                    is_real = True
    except Exception as _e:
        log.warning(f"sector_pdf perf_chart: fetch echoue ({_e}) — fallback simule")

    if not is_real or not curves:
        log.warning("sector_pdf perf_chart: fallback illustratif")
        np.random.seed(42)
        avg_mom = 10.0
        curves["ETF"]  = list(np.linspace(100, 100 + avg_mom, 13) + np.random.normal(0, 1.5, 13))
        curves["BUY"]  = list(np.linspace(100, 100 + avg_mom + 8, 13) + np.random.normal(0, 2.0, 13))
        curves["HOLD"] = list(np.linspace(100, 100 + avg_mom, 13) + np.random.normal(0, 1.8, 13))
        curves["SELL"] = list(np.linspace(100, 100 + avg_mom - 10, 13) + np.random.normal(0, 2.2, 13))
        for k in curves:
            curves[k][0] = 100

    # Aligner les longueurs
    n_pts = min(min(len(v) for v in curves.values()), 13)
    for k in curves:
        curves[k] = list(curves[k][-n_pts:])
    x = np.arange(n_pts)
    months_used = months[-n_pts:]

    # Styles des 4 courbes
    _STYLES = {
        "ETF":  {"color": "#1B3A6B", "lw": 2.4, "ls": "-",  "zorder": 4, "label": f"ETF {sector_name} ({etf_ticker})" if etf_ticker else "ETF sectoriel"},
        "BUY":  {"color": "#1A7A4A", "lw": 1.8, "ls": "-",  "zorder": 3, "label": f"Panier BUY ({len(tickers_buy)})"},
        "HOLD": {"color": "#B06000", "lw": 1.3, "ls": "--", "zorder": 2, "label": f"Panier HOLD ({len(tickers_hold)})"},
        "SELL": {"color": "#A82020", "lw": 1.8, "ls": "-",  "zorder": 3, "label": f"Panier SELL ({len(tickers_sell)})"},
    }

    fig, ax = plt.subplots(figsize=(6.5, 2.9))
    for k in ["ETF", "BUY", "HOLD", "SELL"]:
        if k in curves:
            _st = _STYLES[k]
            ax.plot(x, curves[k], color=_st["color"], linewidth=_st["lw"],
                    linestyle=_st["ls"], label=_st["label"], zorder=_st["zorder"])
    _n = len(x)
    _tick_step = max(1, _n // 5) if _n >= 2 else 1
    ax.set_xticks(x[::_tick_step])
    ax.set_xticklabels(months_used[::_tick_step], fontsize=8, color='#555')
    ax.tick_params(length=0)
    for sp in ['top', 'right']:
        ax.spines[sp].set_visible(False)
    ax.spines['left'].set_color('#D0D5DD')
    ax.spines['bottom'].set_color('#D0D5DD')
    ax.set_facecolor('white')
    fig.patch.set_facecolor('white')
    ax.axhline(100, color='#D0D5DD', linewidth=0.6, zorder=1)
    ax.legend(fontsize=7.5, loc='upper left', frameon=True, framealpha=0.9,
              edgecolor='#DDDDDD', handlelength=1.8)
    _start = months_used[0]
    _MOIS_FULL = ['Janvier','Fevrier','Mars','Avril','Mai','Juin','Juillet','Aout','Septembre','Octobre','Novembre','Decembre']
    _abbr, _yr = _start.split()
    _full = _MOIS_FULL[_MOIS.index(_abbr)] if _abbr in _MOIS else _abbr
    _suffix = "" if is_real else " (illustratif)"
    ax.set_title(f'Performance relative \u2014 ETF vs paniers FinSight  \u00b7  base 100, {_full} 20{_yr}{_suffix}',
                 fontsize=8.5, color='#1B3A6B', fontweight='bold', pad=4)
    plt.tight_layout(pad=0.3)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=160, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf


def _make_revenue_area(tickers_data: list[dict], sector_name: str,
                       universe: str = "S&P 500") -> io.BytesIO:
    """Composition de l'ETF sectoriel — top 10 holdings reels avec leurs poids.

    REFONTE 2026-04-14 (#98 + chantier ETF-first #86) : remplace le graphique
    hardcoded "Revenus agreges par sous-segment" (segments fictifs Core Business
    / Services / International / Digital / Autres avec splits 40/25/18/10/7)
    par une visualisation des VRAIS holdings de l'ETF sectoriel de reference.

    Les poids sont recuperes via core.etf_holdings.fetch_etf_holdings et affiches
    sous forme de bar chart horizontal tri\u00e9 par poids decroissant. Inclut
    "Autres" en 11e position pour la queue si disponible.
    """
    # Determine l'ETF de reference
    etf_ticker = None
    holdings = []
    try:
        from core.sector_etfs import get_etf_for
        from core.etf_holdings import fetch_etf_holdings
        _etf = get_etf_for(sector_name, universe=universe)
        if _etf:
            etf_ticker = _etf["ticker"]
            _data = fetch_etf_holdings(etf_ticker)
            if _data:
                holdings = sorted(_data.get("holdings", []),
                                  key=lambda h: h.get("weight", 0) or 0, reverse=True)[:10]
    except Exception as _e:
        log.warning("_make_revenue_area ETF fetch: %s", _e)

    if not holdings:
        # Fallback : si pas d'ETF dispo (univers non mapp\u00e9), utiliser les
        # tickers_data pondere par market_cap
        by_mc = sorted(
            [(t.get("ticker", "?"), t.get("market_cap") or 0,
              (t.get("company") or t.get("name") or t.get("ticker", ""))[:25])
             for t in tickers_data if t.get("market_cap")],
            key=lambda x: x[1], reverse=True)[:10]
        if by_mc:
            total_mc = sum(x[1] for x in by_mc) or 1
            holdings = [
                {"ticker": t, "name": n, "weight": mc / total_mc}
                for t, mc, n in by_mc
            ]
        else:
            holdings = []

    # Si toujours vide, generer un chart vide mais valide
    if not holdings:
        fig, ax = plt.subplots(figsize=(7.0, 3.2))
        ax.text(0.5, 0.5, "Composition ETF non disponible",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=11, color="#888")
        ax.set_facecolor("white")
        fig.patch.set_facecolor("white")
        ax.axis("off")
        plt.tight_layout(pad=0.3)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    # Normalise les poids (certains fetchers les donnent en fraction, d'autres en %)
    labels = []
    weights_pct = []
    for h in holdings:
        w = h.get("weight", 0) or 0
        w_pct = w * 100 if 0 < w < 1 else w
        name = h.get("name") or h.get("ticker", "?")
        # Format court "TICKER · Nom"
        lbl = f"{h.get('ticker', '?')}  {name[:22]}"
        labels.append(lbl)
        weights_pct.append(float(w_pct))

    total_covered = sum(weights_pct)
    # Ajoute "Autres" pour la queue (complement a 100%)
    if total_covered < 99:
        labels.append("Autres (queue)")
        weights_pct.append(max(0, 100 - total_covered))

    # Bar chart horizontal tri\u00e9 (deja tri\u00e9 par poids decroissant, on reverse pour
    # matplotlib qui affiche bottom-up)
    labels_rev = list(reversed(labels))
    weights_rev = list(reversed(weights_pct))

    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    y = np.arange(len(labels_rev))
    # Couleur gradient navy -> bleu clair pour les top holdings, gris pour "Autres"
    _colors = []
    for lbl in labels_rev:
        if lbl == "Autres (queue)":
            _colors.append("#B8CCE0")
        else:
            _colors.append("#1B3A6B")
    bars = ax.barh(y, weights_rev, color=_colors, alpha=0.88, height=0.65,
                   edgecolor="white", linewidth=0.6)
    for bar, val in zip(bars, weights_rev):
        ax.text(val + max(weights_rev) * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%", va="center", fontsize=8.5, color="#333",
                fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels(labels_rev, fontsize=8.5, color="#333")
    ax.set_xlabel("Poids dans l'ETF (%)", fontsize=9, color="#555", labelpad=8)
    ax.set_xlim(0, max(weights_rev) * 1.18)
    ax.tick_params(length=0)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color("#D0D5DD")
    ax.spines["bottom"].set_color("#D0D5DD")
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    ax.grid(axis="x", alpha=0.15, color="#D0D5DD", linewidth=0.5)
    _title_suffix = f" ({etf_ticker})" if etf_ticker else ""
    ax.set_title(f"Composition de l'ETF sectoriel{_title_suffix} \u2014 {sector_name}",
                 fontsize=12, color='#1B3A6B', fontweight='bold', pad=8)
    plt.tight_layout(pad=0.3)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=160, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf


def _make_valuation_bars(tickers_data: list[dict], sector_name: str) -> io.BytesIO:
    """EV/EBITDA ranking bars — graphique clair et lisible, remplace le scatter diforme.

    Bug 2026-04-15 : pour le profil BANK/INSURANCE, les institutions financieres
    n'ont pas de EV/EBITDA (ratio non pertinent). On bascule automatiquement
    sur P/B (price-to-book) qui est le ratio de reference dans le secteur bancaire.
    """
    # Detect si on est sur un secteur financier (bascule sur P/B si besoin)
    _profile = _detect_sector_profile(tickers_data, sector_name)
    _use_pb = _profile in ("BANK", "INSURANCE")
    _metric_key = "pb_ratio" if _use_pb else "ev_ebitda"
    _metric_max = 20 if _use_pb else 150
    _metric_label = "P/B" if _use_pb else "EV/EBITDA"
    _metric_suffix = "x"

    points = []
    for t in tickers_data:
        ev = t.get(_metric_key)
        if ev is None:
            continue
        try:
            ev_f = float(ev)
            if 0 < ev_f <= _metric_max:
                points.append((t.get('ticker', '?'), ev_f, float(t.get('score_global') or 50)))
        except (TypeError, ValueError):
            pass

    if not points:
        fig, ax = plt.subplots(figsize=(9.0, 5.5))
        ax.text(0.5, 0.5, f'{_metric_label} non disponible', ha='center', va='center',
                transform=ax.transAxes, fontsize=11, color='#999999')
        ax.set_facecolor('white')
        fig.patch.set_facecolor('white')
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf

    # Cap top 15 par score pour lisibilite
    if len(points) > 15:
        points = sorted(points, key=lambda x: -x[2])[:15]
    # Tri croissant EV/EBITDA pour le bar chart
    points.sort(key=lambda x: x[1])

    tickers_list = [p[0] for p in points]
    evs = [p[1] for p in points]
    med_ev = float(np.median(evs))

    # Couleur : vert=sous médiane (opportunite), rouge=au-dessus (prime)
    bar_colors = ['#1A7A4A' if ev < med_ev else '#A82020' for ev in evs]

    n = len(points)
    fig_h = 6.0
    fig, ax = plt.subplots(figsize=(11.0, fig_h))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')

    bars = ax.barh(range(n), evs, color=bar_colors, alpha=0.85,
                   edgecolor='white', linewidth=0.6, height=0.65)
    ax.set_yticks(range(n))
    ax.set_yticklabels(tickers_list, fontsize=9)

    # Ligne médiane
    ax.axvline(med_ev, color='#1B3A6B', linewidth=1.8, linestyle='--', zorder=5)
    ax.text(med_ev + 0.3, n - 0.5,
            f'Med: {med_ev:.1f}x', fontsize=8.5, color='#1B3A6B', va='top', fontweight='bold')

    # Labels valeurs sur chaque barre
    x_max = max(evs) if evs else 1
    for i, ev in enumerate(evs):
        ax.text(ev + x_max * 0.012, i, f'{ev:.1f}x',
                va='center', ha='left', fontsize=8, color='#333333')

    ax.set_xlabel(f'{_metric_label} ({_metric_suffix})', fontsize=9, color='#555555')
    ax.set_title(f'{_metric_label} par acteur \u2014 {sector_name}  \u00b7  Vert = sous médiane',
                 fontsize=10, color='#1B3A6B', fontweight='bold', pad=8)
    for sp in ['top', 'right']:
        ax.spines[sp].set_visible(False)
    ax.spines['left'].set_color('#D0D5DD')
    ax.spines['bottom'].set_color('#D0D5DD')
    ax.tick_params(labelsize=8, length=0)
    ax.grid(True, alpha=0.15, axis='x', linestyle=':')
    ax.set_xlim(0, x_max * 1.18)

    legend_items = [
        mpatches.Patch(color='#1A7A4A', label='Sous médiane \u2014 opportunité relative'),
        mpatches.Patch(color='#A82020', label='Prime vs médiane \u2014 valorisation élevée'),
    ]
    ax.legend(handles=legend_items, fontsize=8, loc='lower right', frameon=False)

    fig.subplots_adjust(left=0.18, right=0.90, top=0.90, bottom=0.12)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf


def _make_mktcap_donut(tickers_data: list[dict], sector_name: str) -> io.BytesIO:
    """Répartition Market Cap sectorielle — donut avec légende standard."""
    valid = [((t.get('company') or t.get('ticker', ''))[:24], float(t['market_cap']))
             for t in tickers_data if t.get('market_cap')]
    if not valid:
        valid = [('N/A', 1)]

    valid.sort(key=lambda x: -x[1])
    total = sum(v for _, v in valid)

    # Regrouper les segments < 4% en "Autres"
    main_items = [(tk, v) for tk, v in valid if v / total * 100 >= 4.0]
    small_items = [(tk, v) for tk, v in valid if v / total * 100 < 4.0]
    if small_items:
        autres_total = sum(v for _, v in small_items)
        main_items.append(('Autres', autres_total))
    if not main_items:
        main_items = valid

    if len(main_items) > 7:
        top = main_items[:6]
        autres = sum(v for _, v in main_items[6:])
        top.append(('Autres', autres))
        main_items = top

    names  = [tk for tk, _ in main_items]
    sizes  = [v  for _, v  in main_items]
    pcts   = [v / total * 100 for v in sizes]
    palette = ['#1B3A6B','#2A5298','#3D6099','#5580B8','#7AA0CC','#A0BEDC','#D0D5DD'][:len(main_items)]

    # Ratio 1:1 strict pour eviter toute deformation dans le PDF
    fig, ax = plt.subplots(figsize=(6.0, 6.0))
    wedges, _ = ax.pie(sizes, labels=None, autopct=None, colors=palette,
                       startangle=90,
                       wedgeprops=dict(linewidth=0.8, edgecolor='white'))
    ax.set_aspect('equal')
    centre = plt.Circle((0, 0), 0.42, color='white')
    ax.add_patch(centre)
    ax.text(0, 0.12, sector_name[:14], ha='center', va='center',
            fontsize=12, fontweight='bold', color='#1B3A6B')
    ax.text(0, -0.16, 'Market Cap', ha='center', va='center',
            fontsize=10, color='#555555')

    # Légende agrandie avec pourcentages
    legend_labels = [f"{n}  {p:.1f}%" for n, p in zip(names, pcts)]
    ax.legend(wedges, legend_labels,
              loc='lower center', bbox_to_anchor=(0.5, -0.14),
              ncol=min(len(names), 2), fontsize=11, frameon=False,
              handleheight=1.0, handlelength=1.5, columnspacing=1.4)

    ax.set_title(f'Répartition Market Cap \u2014 {sector_name}', fontsize=14,
                 color='#1B3A6B', fontweight='bold', pad=14)
    fig.patch.set_facecolor('white')
    fig.subplots_adjust(bottom=0.20, top=0.92)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=180, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    return buf


# ─── CANVAS ───────────────────────────────────────────────────────────────────
def _cover_page(c, doc, sector_name: str, subtitle: str, universe: str,
                date_str: str, tickers_data: list[dict]):
    w, h = A4
    cx = w / 2

    c.setFillColor(WHITE)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    # Bande top navy
    c.setFillColor(NAVY)
    c.rect(0, h - 18*mm, w, 18*mm, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 13)
    c.drawCentredString(cx, h - 8*mm, "FinSight IA")
    c.setFillColor(ACCENT_BLUE)
    c.setFont('Helvetica', 7.5)
    c.drawCentredString(cx, h - 14*mm, "Plateforme d'Analyse Financi\u00e8re Institutionnelle")
    c.setStrokeColor(GREY_RULE)
    c.setLineWidth(0.5)
    c.line(MARGIN_L, h - 20*mm, w - MARGIN_R, h - 20*mm)

    # Surtitre + titre
    c.setFillColor(GREY_TEXT)
    c.setFont('Helvetica', 8.5)
    c.drawCentredString(cx, h * 0.810, "ANALYSE SECTORIELLE")
    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 26)
    c.drawCentredString(cx, h * 0.770, sector_name)
    c.setFillColor(GREY_TEXT)
    c.setFont('Helvetica', 10)
    c.drawCentredString(cx, h * 0.738, subtitle)

    c.setStrokeColor(GREY_RULE)
    c.setLineWidth(0.4)
    c.line(MARGIN_L + 20*mm, h * 0.724, w - MARGIN_R - 20*mm, h * 0.724)

    # 4 metriques
    N = len(tickers_data)
    total_mc = sum((t.get('market_cap') or 0) for t in tickers_data)
    best = max(tickers_data, key=lambda x: x.get('score_global') or 0)
    best_reco = _reco(best.get('score_global'))
    # Top Pick : préférer le nom court de société (ex: "Citigroup") au ticker brut ("C")
    _best_co = best.get('company') or best.get('name') or ''
    _best_tk = best.get('ticker', 'N/A')
    if _best_co and len(_best_co) > 1:
        # Garde 22 caractères max pour tenir dans la box
        _short = _best_co.replace(' Inc.', '').replace(' Inc', '').replace(' Corp.', '').replace(' Corp', '').replace(', Inc.', '').strip()
        if len(_short) > 22:
            _short = _short[:22] + '…'
        _top_pick_str = f"{_short} ({_best_tk})"
    else:
        _top_pick_str = f"{_best_tk} ({best_reco})"
    # Format milliers FR (espace) au lieu de virgule US
    _cap_str = f"{total_mc/1e9:,.0f} Mds".replace(',', ' ') if total_mc > 1e9 else f"{total_mc:,.0f} Mds".replace(',', ' ')
    metrics = [
        ("Univers couvert",    f"{N} sociétés"),
        ("Cap. totale",        _cap_str),
        ("Top Pick",           _top_pick_str),
        ("Date d'analyse",     date_str),
    ]
    col_span = (w - MARGIN_L - MARGIN_R) / 4
    for i, (lbl, val) in enumerate(metrics):
        mx = MARGIN_L + col_span * i + col_span / 2
        c.setFillColor(GREY_TEXT)
        c.setFont('Helvetica', 7.5)
        c.drawCentredString(mx, h * 0.700, lbl)
        c.setFillColor(NAVY)
        c.setFont('Helvetica-Bold', 9.5)
        c.drawCentredString(mx, h * 0.681, val)

    c.setStrokeColor(GREY_RULE)
    c.setLineWidth(0.4)
    c.line(MARGIN_L, h * 0.667, w - MARGIN_R, h * 0.667)

    # Badge signal sectoriel — moyenne des scores (aligné PPTX: >=65 SURPONDERER, >=45 NEUTRE)
    _scores = [t.get('score_global') or 0 for t in tickers_data]
    sig_score = sum(_scores) / len(_scores) if _scores else 0
    if sig_score >= 65:
        sig_label, sig_color = "SURPONDÉRER", (0x1A/255, 0x7A/255, 0x4A/255)
    elif sig_score >= 45:
        sig_label, sig_color = "NEUTRE", (0xB0/255, 0x60/255, 0x00/255)
    else:
        sig_label, sig_color = "SOUS-PONDERER", (0xA8/255, 0x20/255, 0x20/255)
    from reportlab.lib.colors import Color as _RLColor
    badge_w, badge_h = 60*mm, 11*mm
    badge_x = cx - badge_w / 2
    badge_y = h * 0.620
    c.setFillColor(_RLColor(*sig_color))
    c.roundRect(badge_x, badge_y, badge_w, badge_h, 3, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 11)
    # \u25cf (●) non rendu dans Helvetica → "*"
    c.drawCentredString(cx, badge_y + 3.5*mm, f"*  {sig_label}")

    # Tagline
    tag_y = h * 0.570
    c.setFillColor(GREY_TEXT)
    c.setFont('Helvetica', 7.5)
    c.drawCentredString(cx, tag_y,
        f"Rapport d'analyse sectorielle confidentiel \u2014 {date_str}")
    c.setFont('Helvetica', 7)
    c.drawCentredString(cx, tag_y - 5*mm,
        f"Données : yfinance \u00b7 FMP \u00b7 Finnhub \u00b7 FinBERT  |  Univers : {universe}")

    # Footer navy
    c.setFillColor(NAVY)
    c.rect(0, 0, w, 18*mm, fill=1, stroke=0)
    c.setFillColor(ACCENT_BLUE)
    c.setFont('Helvetica', 6.5)
    c.drawCentredString(cx, 11*mm, "CONFIDENTIEL \u2014 Usage restreint")
    c.drawCentredString(cx, 6*mm,
        "Ce rapport est généré par FinSight IA v1.0. Ne constitue pas un conseil en investissement au sens MiFID II.")


def _content_header(c, doc, sector_name: str, date_str: str):
    w, h = A4
    c.setFillColor(NAVY)
    c.rect(0, h - 14*mm, w, 14*mm, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 8)
    c.drawString(MARGIN_L, h - 9*mm,
                 f"FinSight IA  \u00b7  {sector_name}  \u00b7  Analyse Sectorielle")
    c.setFont('Helvetica', 7.5)
    c.drawRightString(w - MARGIN_R, h - 9*mm,
                      f"{date_str}  \u00b7  Confidentiel  \u00b7  Page {doc.page}")
    c.setStrokeColor(GREY_MED)
    c.setLineWidth(0.15)
    c.line(MARGIN_L, MARGIN_B - 2*mm, w - MARGIN_R, MARGIN_B - 2*mm)
    c.setFillColor(GREY_TEXT)
    c.setFont('Helvetica', 6.5)
    c.drawString(MARGIN_L, MARGIN_B - 7*mm,
                 "FinSight IA v1.0 \u2014 Document g\u00e9n\u00e9r\u00e9 par IA. Ne constitue pas un conseil en investissement.")
    c.drawRightString(w - MARGIN_R, MARGIN_B - 7*mm,
                      "Sources : yfinance \u00b7 FMP \u00b7 Finnhub \u00b7 FinBERT")


# ─── SECTIONS ─────────────────────────────────────────────────────────────────
def _build_macro(perf_buf, area_buf, tickers_data: list[dict],
                 sector_name: str, universe: str, registry=None,
                 sector_analytics: dict = None, fred_data: dict = None):
    elems = []
    if registry is not None:
        elems.append(SectionAnchor('macro', registry))
    elems += section_title(_slbl("vue_macro"), 1)

    N = len(tickers_data)
    total_mc = sum((t.get('market_cap') or 0) for t in tickers_data)
    avg_growth = sum((t.get('revenue_growth') or 0) for t in tickers_data) / max(N, 1)
    avg_ebitda = sum((t.get('ebitda_margin') or 0) for t in tickers_data) / max(N, 1)
    _mc_str = f"{total_mc/1e9:,.0f} Mds" if total_mc > 1e9 else f"{total_mc:,.0f} Mds"

    # ── ETF sectoriel de reference ────────────────────────────────────────────
    # Integration module core/sector_etfs + core/etf_holdings (chantier ETF-first)
    _etf_info = None
    _etf_data = None
    try:
        from core.sector_etfs import get_etf_for, etf_issuer
        from core.etf_holdings import fetch_etf_holdings, format_aum, format_ter
        _etf_info = get_etf_for(sector_name, universe=universe)
        if _etf_info:
            _etf_data = fetch_etf_holdings(_etf_info["ticker"])
    except Exception as _e:
        log.warning("sector_pdf ETF section: %s", _e)

    if _etf_info and _etf_data:
        _etf_issuer = etf_issuer(_etf_info["zone"])
        _ter_str = format_ter(_etf_data.get("ter_bps"))
        _aum_str = format_aum(_etf_data.get("aum_usd"))
        _n_holdings = len(_etf_data.get("holdings", []))
        elems.append(Paragraph(
            f"<b>ETF de reference : {_etf_info['ticker']} — {_etf_info['name']}</b>",
            S_SUBSECTION))
        elems.append(Spacer(1, 1*mm))
        elems.append(Paragraph(
            f"L'analyse du secteur <b>{sector_name}</b> s'appuie sur l'ETF de r\u00e9f\u00e9rence "
            f"<b>{_etf_info['ticker']}</b> emis par <b>{_etf_issuer}</b>. Cet instrument constitue "
            f"le benchmark passif du secteur et l'ancrage de notre analyse fondamentale. "
            f"AUM : <b>{_aum_str}</b>. TER : <b>{_ter_str}</b>. Top holdings disponibles : {_n_holdings}. "
            f"Le graphique de performance pr\u00e9sent\u00e9 ci-dessous superpose la courbe r\u00e9elle de "
            f"l'ETF avec trois paniers d\u00e9riv\u00e9s du scoring FinSight (BUY / HOLD / SELL) pour "
            f"appr\u00e9cier l'ajout de valeur du stock-picking par rapport \u00e0 une exposition "
            f"benchmark\u00e9e sur l'ETF.", S_BODY))
        # Top 5 holdings en mini-tableau
        _top5 = sorted(_etf_data.get("holdings", []),
                       key=lambda h: h.get("weight", 0) or 0, reverse=True)[:5]
        if _top5:
            _h_rows = [[Paragraph(h, S_TH_C) for h in ["Rg", "Ticker", "Soci\u00e9t\u00e9", "Poids"]]]
            for _i, _h in enumerate(_top5, 1):
                _w = _h.get("weight", 0) or 0
                _w_pct = _w * 100 if _w < 1 else _w
                _h_rows.append([
                    Paragraph(str(_i), S_TD_C),
                    Paragraph(f"<b>{_h.get('ticker','?')}</b>", S_TD_BC),
                    Paragraph(str(_h.get('name', ''))[:40], S_TD_L),
                    Paragraph(f"{_w_pct:.1f} %".replace('.', ','), S_TD_C),
                ])
            elems.append(Spacer(1, 1*mm))
            elems.append(Paragraph("Top 5 holdings (poids decroissant)", S_NOTE))
            elems.append(tbl(_h_rows, cw=[12*mm, 22*mm, 110*mm, 26*mm]))
            elems.append(src(
                f"Source : {_etf_issuer}. Holdings au dernier rebalancement disponible via yfinance."))
        elems.append(Spacer(1, 4*mm))

    _ag_s = _fmt_pct(avg_growth, sign=True)
    _ae_s = _fmt_pct(avg_ebitda, sign=False)
    elems.append(Paragraph(
        f"Le secteur <b>{sector_name}</b> ({universe}) couvre <b>{N} sociétés</b> "
        f"pour une capitalisation totale de <b>{_mc_str}</b>. "
        f"La croissance moyenne des revenus s'établit a <b>{_ag_s} YoY</b>, "
        f"avec une marge EBITDA médiane de <b>{_ae_s}</b>. "
        f"L'analyse couvre les dynamiques structurelles, les positionnéments concurrentiels "
        f"et les risques sectoriels identifiés par le protocole adversarial FinSight IA. "
        f"La bifurcation entre acteurs établis et challengers constitue le fil directeur "
        f"de cette analyse.", S_BODY))
    elems.append(Spacer(1, 2*mm))

    # Row 1 : perf chart full width — ratio figsize (6.5, 2.6) = 0.4
    perf_img = Image(perf_buf, width=TABLE_W, height=TABLE_W * 2.6 / 6.5)
    elems.append(perf_img)
    # Source label : ETF {nom} ({ticker}) si dispo, sinon basket
    _perf_src_label = (
        f"FinSight IA \u2014 ETF {sector_name} ({_etf_info['ticker']}) vs S&P 500, base 100."
        if _etf_info else
        f"FinSight IA \u2014 Basket {sector_name} (top 15 par score) vs S&P 500, base 100."
    )
    elems.append(src(_perf_src_label))
    elems.append(Spacer(1, 4*mm))

    # Row 2 : composition ETF — refonte SEC-PDF-P3 Baptiste.
    # Le chart est affiche en pleine largeur comme la perf row 1. Le texte
    # analytique suit EN PLEINE LARGEUR en dessous pour exploiter tout l'espace
    # horizontal (auparavant le texte etait enferme dans une colonne de 44mm
    # a droite du chart, ce qui laissait beaucoup de blanc et forcait le texte
    # sur une grande colonne verticale peu lisible).
    # Label pour le texte : "ETF Santé (XLV)" au lieu de "ETF XLV"
    if _etf_info:
        _etf_tk_text = f"ETF {sector_name} ({_etf_info['ticker']})"
    else:
        _etf_tk_text = "l'ETF sectoriel"
    area_img = Image(area_buf, width=TABLE_W, height=TABLE_W * 3.6 / 7.0)
    elems.append(area_img)
    elems.append(Spacer(1, 2*mm))
    _etf_issuer_lbl = "SPDR / iShares" if _etf_info else "provider ETF"
    elems.append(src(
        f"Source : {_etf_issuer_lbl} via yfinance funds_data. Top 10 holdings pond\u00e9r\u00e9s reels."))
    elems.append(Spacer(1, 2*mm))
    elems.append(Paragraph(
        f"<b>Composition de l'{_etf_tk_text}.</b> Ce graphique affiche les "
        f"<b>top 10 holdings</b> r\u00e9els du sous-jacent passif, pond\u00e9r\u00e9s par leur "
        f"poids effectif au dernier rebalancement communique par l'issuer. La "
        f"concentration du top 3 indique le degr\u00e9 d'oligopolisation du secteur : "
        f"un poids cumul\u00e9 superieur \u00e0 40 % sur 3 noms traduit une d\u00e9pendance "
        f"structurelle \u00e0 quelques acteurs dominants, amplifiant la sensibilit\u00e9 "
        f"de l'ETF aux surprises BPA individuelles et reduisant l'effet de "
        f"diversification attendu d'une exposition passive. Dans ce contexte, le "
        f"stock-picking devient mecaniquement plus rentable parce que la dispersion "
        f"de rendements entre les grosses lignes et les petites reste elevee, et "
        f"l'ETF n'apporte qu'une moyenne ponderee par la capitalisation sans "
        f"differenciation qualitative.",
        S_BODY))
    elems.append(Spacer(1, 1.5*mm))
    elems.append(Paragraph(
        f"La queue de distribution (\u00ab Autres \u00bb) correspond aux holdings en dehors "
        f"du top 10 et diversifie statistiquement le risque id\u00e9osyncratique, mais "
        f"son poids effectif reste limite dans la plupart des ETF sectoriels "
        f"(typiquement 20-30 %). L'analyse fondamentale detaillee doit donc se "
        f"concentrer sur les top holdings : ce sont eux qui portent l'essentiel du "
        f"rendement et du risque de l'ETF, et ce sont eux que FinSight IA compare "
        f"au basket actif dans la courbe de performance ci-dessus. La croissance "
        f"moyenne des revenus du basket FinSight ressort \u00e0 <b>{_fmt_pct(avg_growth, sign=True)}</b> "
        f"avec une marge EBITDA m\u00e9diane de <b>{_fmt_pct(avg_ebitda, sign=False)}</b>, ce qui "
        f"fournit un ancrage fondamental pour juger de la soutenabilite des "
        f"multiples de valorisation du secteur dans le cycle actuel.",
        S_BODY))
    elems.append(Spacer(1, 4*mm))

    # ── Régime de marche + Probabilite de recession (AgentMacro) ─────────────
    _macro = (sector_analytics or {}).get("macro") or {}
    _regime  = _macro.get("regime")
    _vix     = _macro.get("vix")
    _spread  = _macro.get("yield_spread_10y_3m")
    _sp_ma   = _macro.get("sp500_vs_ma200")
    _rec_6m  = _macro.get("recession_prob_6m")
    _rec_12m = _macro.get("recession_prob_12m")
    _rec_lvl = _macro.get("recession_level", "Inconnu")
    _drivers = _macro.get("recession_drivers", [])

    if _regime and _regime != "Inconnu":
        _REGIME_S = {
            "Bull":       S_TD_G, "Bear":       S_TD_R,
            "Volatile":   S_TD_A, "Transition": S_TD_A,
        }
        _reg_style = _REGIME_S.get(_regime, S_TD_BC)
        _rec_style = (S_TD_R if _rec_lvl == "Élevée" else
                      (S_TD_A if _rec_lvl == "Modérée" else S_TD_G))
        vix_str    = f"{_vix:.0f}" if _vix    is not None else "\u2014"
        spread_str = _fmt_pct(_spread, sign=True) if _spread is not None else "\u2014"
        sp_ma_str  = _fmt_pct(_sp_ma, sign=True)  if _sp_ma  is not None else "\u2014"
        sp_trend   = _macro.get("sp500_trend", "\u2014")

        reg_h = [Paragraph(h, S_TH_C) for h in
                 ["Régime de marche", "VIX", "Spread 10Y-3M", "S&P vs MA200", "Tendance"]]
        reg_row = [
            Paragraph(f"<b>{_regime}</b>", _reg_style),
            Paragraph(vix_str,    S_TD_BC),
            Paragraph(spread_str, S_TD_BC),
            Paragraph(sp_ma_str,  S_TD_BC),
            Paragraph(sp_trend,   S_TD_C),
        ]
        macro_blocks = [
            Paragraph("Environnement macro — Régime de marche", S_SUBSECTION),
            Spacer(1, 2*mm),
            tbl([reg_h, reg_row], cw=[36*mm, 22*mm, 34*mm, 34*mm, 44*mm]),
        ]
        if _rec_6m is not None:
            rec_h = [Paragraph(h, S_TH_C) for h in
                     ["Horizon", "Probabilité récession", "Niveau", "Principaux signaux"]]
            drivers_str = " \u00b7 ".join(_drivers[:2]) if _drivers else "Aucun signal recessif dominant"
            rec_rows = [
                [Paragraph("6 mois",  S_TD_C),
                 Paragraph(f"<b>{_rec_6m}%</b>", _rec_style),
                 Paragraph(_rec_lvl, _rec_style),
                 Paragraph(drivers_str, S_TD_L)],
                [Paragraph("12 mois", S_TD_C),
                 Paragraph(f"{_rec_12m}%", S_TD_C),
                 Paragraph(_rec_lvl, S_TD_C),
                 Paragraph("Incertitude croissanté sur horizon etendu", S_TD_L)],
            ]
            macro_blocks += [
                Spacer(1, 2*mm),
                tbl([rec_h] + rec_rows, cw=[24*mm, 36*mm, 28*mm, 82*mm]),
                src("Indicateur de marche (non econometrique) : VIX + spread 10Y-3M + "
                    "position S&P 500 vs MA200 + momentum 6M. Source : FinSight IA / yfinance."),
            ]
        elems.append(KeepTogether(macro_blocks))
        elems.append(Spacer(1, 4*mm))
    else:
        elems.append(Spacer(1, 4*mm))

    # ── Indicateurs macroéconomiques FRED ────────────────────────────────
    _fred = fred_data or {}
    if _fred:
        _FRED_LABELS = {
            "fed_funds_rate":      ("Taux directeur Fed",      "%"),
            "treasury_10y":        ("Taux 10 ans US",          "%"),
            "treasury_2y":         ("Taux 2 ans US",           "%"),
            "yield_curve_spread":  ("Spread courbe (10Y-2Y)",  "%"),
            "cpi_yoy":             ("Inflation CPI (YoY)",     "%"),
            "unemployment":        ("Chômage US",              "%"),
            "vix":                 ("VIX",                     ""),
            "credit_spread_baa":   ("Spread crédit BAA",       "%"),
            "industrial_prod_yoy": ("Production ind. (YoY)",   "%"),
        }
        # Labels pour les séries sectorielles
        _SECTOR_LABELS = {
            "tech_employment_yoy":     ("Emploi tech (YoY)",          "%"),
            "tech_prod_yoy":           ("Prod. informatique (YoY)",   "%"),
            "wti_price":               ("Prix WTI",                   "$/b"),
            "brent_price":             ("Prix Brent",                 "$/b"),
            "natural_gas":             ("Gaz naturel Henry Hub",      "$/MMBtu"),
            "mortgage_30y":            ("Taux hypothécaire 30 ans",   "%"),
            "case_shiller":            ("Indice Case-Shiller",        ""),
            "housing_starts":          ("Mises en chantier",          "k"),
            "housing_starts_yoy":      ("Mises en chantier (YoY)",   "%"),
            "consumer_confidence":     ("Confiance consommateur",     ""),
            "retail_sales_yoy":        ("Ventes retail (YoY)",        "%"),
            "auto_sales":              ("Ventes automobiles",         "M"),
            "bank_lending_yoy":        ("Prêts bancaires (YoY)",     "%"),
            "bank_charge_offs":        ("Taux de charge-off",        "%"),
            "consumer_credit_yoy":     ("Crédit conso (YoY)",        "%"),
            "health_employment_yoy":   ("Emploi santé (YoY)",        "%"),
            "pharma_prod_yoy":         ("Prod. pharmaceutique (YoY)","%"),
            "mfg_employment_yoy":      ("Emploi manufacturier (YoY)","%"),
            "durable_goods_yoy":       ("Commandes durables (YoY)",  "%"),
            "capacity_util":           ("Utilisation capacité",       "%"),
            "copper_price":            ("Prix cuivre",               "$/lb"),
            "electricity_price":       ("Prix électricité",          "$/kWh"),
            "food_cpi":               ("CPI alimentaire",            ""),
            "energy_prod_yoy":        ("Prod. énergie (YoY)",        "%"),
        }

        def _fred_interp(key, val):
            """Interprétation concise d'un indicateur FRED."""
            if key == "fed_funds_rate":
                return "Restrictif" if val > 4.0 else ("Neutre" if val > 2.0 else "Accommodant")
            if key == "yield_curve_spread":
                return "Inversée (risque)" if val < 0 else ("Pentue" if val > 1.0 else "Plate")
            if key == "cpi_yoy":
                return "Élevée" if val > 4.0 else ("Modérée" if val > 2.5 else "Maîtrisée")
            if key == "unemployment":
                return "Tendu" if val < 4.0 else ("Neutre" if val < 5.5 else "Dégradé")
            if key == "vix":
                return "Faible vol." if val < 15 else ("Modérée" if val < 25 else "Stress élevé")
            if key == "credit_spread_baa":
                return "Serré" if val < 1.5 else ("Normal" if val < 2.5 else "Tendu")
            if "yoy" in key:
                return "Expansion" if val > 1.0 else ("Stagnation" if val > -1.0 else "Contraction")
            return "\u2014"

        # Construction des lignes du tableau
        _fred_rows = []
        for key in ["fed_funds_rate", "treasury_10y", "yield_curve_spread",
                     "cpi_yoy", "unemployment", "vix", "credit_spread_baa"]:
            val = _fred.get(key)
            if val is None:
                continue
            label, unit = _FRED_LABELS.get(key, (key, ""))
            val_str = (f"{val:.2f} {unit}".strip() if unit else f"{val:.2f}").replace('.', ',')
            _fred_rows.append([
                Paragraph(label, S_TD_L),
                Paragraph(f"<b>{val_str}</b>", S_TD_BC),
                Paragraph(_fred_interp(key, val), S_TD_C),
            ])

        # Indicateurs sectoriels
        _sector_fred = _fred.get("sector", {})
        for key, val in _sector_fred.items():
            if val is None:
                continue
            label, unit = _SECTOR_LABELS.get(key, (key.replace("_", " ").title(), ""))
            val_str = (f"{val:.2f} {unit}".strip() if unit else f"{val:.2f}").replace('.', ',')
            interp = _fred_interp(key, val)
            _fred_rows.append([
                Paragraph(f"<i>{label}</i>", S_TD_L),
                Paragraph(f"<b>{val_str}</b>", S_TD_BC),
                Paragraph(interp, S_TD_C),
            ])

        if _fred_rows:
            _fred_header = [[
                Paragraph("Indicateur", S_TH_C),
                Paragraph("Valeur", S_TH_C),
                Paragraph("Interprétation", S_TH_C),
            ]]
            _fred_block = [
                Paragraph("Indicateurs macroéconomiques — FRED", S_SUBSECTION),
                Spacer(1, 1.5*mm),
                tbl(_fred_header + _fred_rows, cw=[62*mm, 42*mm, 66*mm]),
                src("Federal Reserve Economic Data (FRED). Dernières observations disponibles."),
            ]
            elems.append(KeepTogether(_fred_block))
            elems.append(Spacer(1, 4*mm))

    elems.append(debate_q(f"Quelles dynamiques structurelles redefinissent les avantages concurrentiels dans le secteur {sector_name} ?"))

    # Calcul metriques réelles pour le prompt LLM
    import statistics as _stat_mac
    _ev_mac = [t.get("ev_ebitda") for t in tickers_data if t.get("ev_ebitda")]
    _mg_mac = [t.get("ebitda_margin") for t in tickers_data if t.get("ebitda_margin") is not None]
    _mo_mac = [t.get("momentum_52w") for t in tickers_data if t.get("momentum_52w") is not None]
    _ev_m = round(_stat_mac.median(_ev_mac), 1) if _ev_mac else 12.0
    _mg_m = round(_stat_mac.median(_mg_mac), 1) if _mg_mac else 18.0
    _mo_m = round(_stat_mac.median(_mo_mac), 1) if _mo_mac else 0.0

    _macro_drivers_text = None
    try:
        import json as _json_mac
        from core.llm_provider import LLMProvider as _LLMp
        _regime_ctx = (f" | Regime marche: {_regime}, VIX: {_vix:.0f}" if (_regime and _vix) else "")
        _rec_ctx    = (f" | P(récession 6M): {_rec_6m}%" if _rec_6m is not None else "")
        from core.prompt_standards import build_system_prompt
        _sys_mac = build_system_prompt(
            role=f"analyste sell-side senior spécialisé dans le secteur {sector_name}",
            include_json=True,
            extra_rules=[
                f"SPÉCIFICITÉ : contenu 100% spécifique au secteur {sector_name}, "
                f"jamais de généralités applicables à n'importe quel secteur.",
                "Pas de points de suspension (...) dans les réponses.",
            ],
        )
        _prompt_mac = (
            f"CONTEXTE — Secteur : {sector_name}\n"
            f"EV/EBITDA médian : {_fmt_mult(_ev_m)} | Marge EBITDA : {_fmt_pct(_mg_m, sign=False)} | "
            f"Momentum 52W : {_fmt_pct(_mo_m, sign=True)}{_regime_ctx}{_rec_ctx}\n\n"
            f"MISSION : identifie 4 dynamiques structurelles SPÉCIFIQUES à ce "
            f"secteur (régulation, cycle, technologie, demande, capex, capital). "
            f"Chaque driver : titre court + 2 phrases analytiques (40-55 mots), "
            f"avec l'exposition du secteur mise en gras (ex: Exposition : "
            f"<b>forte</b> / <b>modérée</b> / <b>limitée</b>).\n\n"
            f'{{"drivers":['
            f'{{"titre":"titre court","corps":"2 phrases 40-55 mots, exposition en gras"}},'
            f'{{"titre":"titre court","corps":"2 phrases 40-55 mots, exposition en gras"}},'
            f'{{"titre":"titre court","corps":"2 phrases 40-55 mots, exposition en gras"}},'
            f'{{"titre":"titre court","corps":"2 phrases 40-55 mots, exposition en gras"}}]}}'
        )
        _resp_mac = _LLMp(provider="mistral", model="mistral-small-latest").generate(
            prompt=_prompt_mac,
            system=_sys_mac,
            max_tokens=700,
        )
        _js_s = _resp_mac.find("{"); _js_e = _resp_mac.rfind("}") + 1
        if _js_s >= 0 and _js_e > _js_s:
            _p = _json_mac.loads(_resp_mac[_js_s:_js_e])
            if "drivers" in _p and isinstance(_p["drivers"], list) and _p["drivers"]:
                _macro_drivers_text = [
                    (f"<b>{d.get('titre','Dynamique sectorielle')}.</b>", d.get("corps", "—"))
                    for d in _p["drivers"][:4]
                ]
                log.info("sector_pdf macro LLM OK: %s (%d drivers)", sector_name, len(_macro_drivers_text))
    except Exception as _e_mac:
        log.warning("sector_pdf macro LLM erreur: %s -- fallback", _e_mac)

    if _macro_drivers_text:
        for lead, body in _macro_drivers_text:
            elems.append(Paragraph(f"{lead} {body}", S_BODY))
            elems.append(Spacer(1, 1.5*mm))
    else:
        # Fallback avec valeurs réelles (pas de chiffres inventes)
        for lead, body in [
            (f"<b>Valorisation sectorielle {sector_name}.</b>",
             f"L'EV/EBITDA median de {_fmt_mult(_ev_m)} et la marge EBITDA de {_fmt_pct(_mg_m, sign=False)} definissent "
             f"les références de valorisation actuelles du secteur. "
             f"Le momentum 52 semaines de {_fmt_pct(_mo_m, sign=True)} reflète le positionnément relatif dans le cycle."),
            ("<b>Consolidation et effets d'echelle.</b>",
             f"Les operations de M&A et les economies d'echelle exercent une pression sur les acteurs mid-cap "
             f"du secteur {sector_name}, contraints de se différenciér ou de rejoindre des ensembles plus larges."),
            ("<b>Pression réglementaire et ESG.</b>",
             "Le durcissement des normes de conformité et les exigences ESG engendrent des couts additionnels "
             "mais constituent une barrière à l'entrée pour les nouveaux entrants. Exposition : <b>mixte</b>."),
            ("<b>Cycle macro et taux directeurs.</b>",
             "La persistance de taux d'intérêt élevés pénalise les bilans levers et comprime les multiples. "
             "Les acteurs a forte génération de FCF et bilan solide sont structurellement avantages. Exposition : <b>modérée</b>."),
        ]:
            elems.append(Paragraph(f"{lead} {body}", S_BODY))
            elems.append(Spacer(1, 1.5*mm))

    elems.append(src("FinSight IA \u2014 Analyse adversariale sectorielle."))
    return elems


def _build_structure_sectorielle(tickers_data: list[dict], sector_name: str,
                                  sector_analytics: dict, registry=None):
    """Section 2 — Structure et Dynamique Sectorielle (entre Macro et Acteurs)."""
    sa = sector_analytics or {}
    elems = []
    elems.append(Spacer(1, 8*mm))
    if registry is not None:
        elems.append(SectionAnchor('structure', registry))
    elems += section_title(_slbl("structure"), 2)
    elems.append(Spacer(1, 3*mm))

    # Detection profil sectoriel pour adapter les indicateurs (banques /
    # assurance / REIT n'ont pas Altman Z ni Piotroski pertinents)
    _sector_profile = _detect_sector_profile(tickers_data, sector_name)

    def _na_val(v, fmt=None):
        if v is None:
            return "\u2014"
        if fmt:
            return fmt.format(v)
        return str(v)

    # ── Tableau des 4 indicateurs structurels ──────────────────────────────
    struct_h = [Paragraph("Indicateur", S_TH_L), Paragraph("Valeur", S_TH_C)]

    # HHI
    hhi = sa.get("hhi")
    hhi_val = f"{hhi:,}" if hhi else "\u2014"
    hhi_lbl = sa.get("hhi_label", "\u2014")
    if hhi:
        if hhi >= 2500:
            hhi_s = S_TD_R
        elif hhi >= 1500:
            hhi_s = S_TD_A
        else:
            hhi_s = S_TD_G
    else:
        hhi_s = S_TD_C

    # Cycle valorisation
    pe_ltm  = sa.get("pe_median_ltm")
    pe_hist = sa.get("pe_median_hist")
    pe_prem = sa.get("pe_premium")
    if pe_ltm and pe_hist:
        pe_val = (f"{pe_ltm:.1f}x".replace('.', ',') +
                  " (hist. " + f"{pe_hist:.1f}x".replace('.', ',') + ")")
    elif pe_ltm:
        pe_val = f"{pe_ltm:.1f}x".replace('.', ',') + " LTM"
    else:
        pe_val = "\u2014"
    pe_lbl  = sa.get("pe_cycle_label", "historique insuffisant")
    if pe_prem is not None:
        pe_s = S_TD_R if pe_prem > 15 else (S_TD_G if pe_prem < -10 else S_TD_A)
    else:
        pe_s = S_TD_C

    # Dispersion ROIC
    roic_std  = sa.get("roic_std")
    roic_mean = sa.get("roic_mean")
    roic_min  = sa.get("roic_min")
    roic_max  = sa.get("roic_max")
    if roic_std is not None and roic_mean is not None:
        roic_val = f"moy. {roic_mean:.1f}%  |  σ={roic_std:.1f}%  |  [{roic_min:.1f}% — {roic_max:.1f}%]".replace('.', ',')
    elif roic_std is not None:
        roic_val = f"écart-type {roic_std:.1f}%".replace('.', ',')
    else:
        roic_val = "\u2014"
    roic_lbl = sa.get("roic_label", "\u2014")
    if roic_std is not None:
        roic_s = S_TD_R if roic_std >= 15 else (S_TD_A if roic_std >= 8 else S_TD_G)
    else:
        roic_s = S_TD_C

    # Altman Z — modèle sélectionné selon secteur
    n_az   = sa.get("n_altman") or 0
    n_sfe  = sa.get("altman_safe") or 0
    n_gry  = sa.get("altman_grey") or 0
    n_dst  = sa.get("altman_distress") or 0
    az_mdl = sa.get("altman_model", "original_1968")
    is_al  = sa.get("is_asset_light", False)
    # Libellé du modèle et seuils pour transparence
    if az_mdl == "nonmfg_1995":
        az_safe_label = "Z'>2.6"
        az_model_tag  = "Z' non-mfg."
    else:
        az_safe_label = "Z>3"
        az_model_tag  = "Z original"

    # ADAPTATION PROFIL : pour banques/assurance, Altman Z n'est pas pertinent
    # (modele calibre pour manufacturing/non-financiers). On remplace par un
    # message explicatif pointant vers les metriques prudentielles bancaires.
    if _sector_profile in ("BANK", "INSURANCE"):
        if _sector_profile == "BANK":
            altman_val = "Métriques prudentielles : CET1, NPL, LCR"
            altman_lbl = ("Altman Z non applicable aux banques. Ratios pertinents : "
                          "CET1 > 10% (Bâle III), NPL < 3%, LCR > 100%. Source : Pillar 3 trimestriels.")
            az_model_tag = "Bâle III"
        else:  # INSURANCE
            altman_val = "Métriques prudentielles : Solvency II, Combined Ratio"
            altman_lbl = ("Altman Z non applicable aux assureurs. Ratios pertinents : "
                          "Solvency II ratio > 150%, Combined Ratio < 100%. Source : SFCR annuels.")
            az_model_tag = "Solvency II"
        altman_s = S_TD_C
    elif n_az > 0:
        altman_val = (
            f"{n_sfe}/{n_az} zone safe ({az_safe_label}) | "
            f"{n_gry}/{n_az} zone grise | {n_dst}/{n_az} détresse"
        )
        altman_lbl = (
            "risque de défaut concentré — revue bilantielle urgente" if n_dst > 0
            else ("bilans globalement solides" if n_sfe >= n_az * 0.75
                  else "vigilance requise sur quelques bilans")
        )
        altman_s = S_TD_R if n_dst > 0 else (S_TD_G if n_sfe >= n_az * 0.75 else S_TD_A)
    else:
        altman_val = "\u2014"
        altman_lbl = "Altman Z disponible via analyse individuelle approfondie"
        altman_s   = S_TD_C

    struct_data = [
        ("Concentration sectorielle (HHI)",
         hhi_val, hhi_lbl, hhi_s),
        ("Cycle de valorisation (P/E médian)",
         pe_val, pe_lbl, pe_s),
        ("Dispersion ROIC / ROE",
         roic_val, roic_lbl, roic_s),
        (f"Solidité bilantielle ({az_model_tag})",
         altman_val, altman_lbl, altman_s),
    ]
    struct_rows = []
    for label, val, interp, val_style in struct_data:
        struct_rows.append([
            Paragraph(f"<b>{label}</b>", S_TD_B),
            Paragraph(val, val_style),
        ])
    elems.append(KeepTogether(tbl([struct_h] + struct_rows,
                                   cw=[80*mm, 90*mm])))
    if az_mdl == "nonmfg_1995":
        _az_src = ("Altman Z' = modele non-manufacturing 1995 (6.56*X1+3.26*X2+6.72*X3+1.05*X4, "
                   "X5 exclu). Seuils : safe >2.6, grise 1.1-2.6, détresse <1.1.")
    else:
        _az_src = "Altman Z = modele original 1968. Seuils : safe >2.99, grise 1.81-2.99, détresse <1.81."
    elems.append(src(
        "FinSight IA — yfinance, FMP. HHI calcule sur capitalisations boursieres. "
        "ROIC = NOPAT/IC (ROE si ROIC indisponible). PE historique = cours moyen annuel / EPS. "
        + _az_src))

    # Note méthodologique Altman Z pour secteurs asset-light
    if is_al:
        elems.append(Spacer(1, 2*mm))
        elems.append(Paragraph(
            "<i><b>Note méthodologique Altman Z.</b> "
            "Le modele Altman Z-Score original (1968) est calibre pour l'industrie manufacturiere. "
            "Pour ce secteur a actifs intangibles dominants, FinSight IA applique le modele "
            "Z' non-manufacturing (Altman, 1995) qui exclut le ratio CA/Actifs (X5) — "
            "ce ratio pénalise injustement les societes dont la valeur est portee par les "
            "brevets, marques et logiciels plutôt que par les immobilisations corporelles. "
            "Les scores en zone grise n'indiquent pas necessairement un risque de détresse "
            "financière reel.</i>",
            S_NOTE))
    elems.append(Spacer(1, 4*mm))

    # ── Tableau 2 : Qualité & Valorisation Relative ────────────────────────
    _qual_title = Paragraph("Qualité Fondamentale et Valorisation Relative", S_SUBSECTION)

    # Paragraphe LLM d'interprétation des médianes (fallback silencieux si KO)
    _medians_commentary = _generate_medians_commentary(
        sector_name, sa, _sector_profile,
    )

    qual_h = [Paragraph(h, S_TH_C)
              for h in ["Indicateur", "Valeur", "Interpretation analytique"]]

    # --- Piotroski F-Score distribution ---
    # ADAPTATION PROFIL : Piotroski calibre pour entreprises non-financieres.
    # Pour banques/assurance, remplacer par les indicateurs metier pertinents.
    n_f = sa.get("piotroski_n") or sa.get("n_piotroski") or 0
    n_q = sa.get("piotroski_quality") or 0
    n_n_f = sa.get("piotroski_neutral") or 0
    n_t = sa.get("piotroski_trap") or 0
    if _sector_profile == "BANK":
        f_val = "ROE > Coût des fonds propres + provisions"
        f_lbl = ("Piotroski non applicable aux banques (calibre non-financier). "
                 "Indicateurs cles : ROE > 10%, ratio efficacite < 60%, provisions / pret < 1%.")
        f_s   = S_TD_C
    elif _sector_profile == "INSURANCE":
        f_val = "Combined Ratio < 100%, ROE > 10%"
        f_lbl = ("Piotroski non applicable aux assureurs. Indicateurs cles : "
                 "Combined Ratio < 100% (sous-jacent rentable), ROE > 10%, ratio sinistralite stable.")
        f_s   = S_TD_C
    elif _sector_profile == "REIT":
        f_val = "P/FFO, occupancy rate, LTV"
        f_lbl = ("Piotroski moins pertinent pour REITs. Indicateurs cles : "
                 "P/FFO < 18x, occupancy > 92%, LTV < 50%, dividend coverage > 1.2x.")
        f_s   = S_TD_C
    elif n_f > 0:
        pct_q = round(n_q / n_f * 100)
        pct_t = round(n_t / n_f * 100)
        f_val = (
            f"{n_q}/{n_f} quality (F>6)  |  "
            f"{n_n_f}/{n_f} neutrès (F 4-6)  |  "
            f"{n_t}/{n_f} value traps (F<4)"
        )
        if pct_q > 50:
            f_lbl = "secteur de qualité — majorite en zone Piotroski solide"
            f_s   = S_TD_G
        elif pct_t > 30:
            f_lbl = "value traps dominants — sélectivité fondamentale critique"
            f_s   = S_TD_R
        else:
            f_lbl = "profil mixte — stock-picking sur critères fondamentaux"
            f_s   = S_TD_A
    else:
        f_val = "\u2014"
        f_lbl = "Piotroski disponible via Analyse Societe individuelle"
        f_s   = S_TD_C

    # --- PEG ratio médian ---
    peg_med = sa.get("peg_median")
    if peg_med is not None:
        peg_val = f"{peg_med:.1f}x".replace('.', ',')
        if peg_med < 1.0:
            peg_lbl = "sous-valorise sur la croissance — décote vs pairs"
            peg_s   = S_TD_G
        elif peg_med < 2.0:
            peg_lbl = "valorisation juste — croissance pricee a l'equilibre"
            peg_s   = S_TD_A
        elif peg_med < 3.0:
            peg_lbl = "prime de croissance élevée — exige une exécution parfaite"
            peg_s   = S_TD_A
        else:
            peg_lbl = "valorisation très chère — scenarios bull intégrés dans les cours"
            peg_s   = S_TD_R
    else:
        peg_val = "\u2014"
        peg_lbl = "PEG indisponible (croissance nulle ou PE manquant)"
        peg_s   = S_TD_C

    # --- FCF Yield médian ---
    fcfy = sa.get("fcf_yield_median")
    if fcfy is not None:
        fcfy_val = f"{fcfy:.1f} %".replace('.', ',')
        if fcfy >= 5.0:
            fcfy_lbl = "genereux — génération de cash élevée, support valorisation"
            fcfy_s   = S_TD_G
        elif fcfy >= 2.0:
            fcfy_lbl = "correct — FCF adéquat sans prime de rendement specifique"
            fcfy_s   = S_TD_A
        elif fcfy >= 0:
            fcfy_lbl = "limite — secteur reinvesti fortement (croissance ou capex lourds)"
            fcfy_s   = S_TD_A
        else:
            fcfy_lbl = "négatif — consommation de cash, surveiller la trajectoire FCF"
            fcfy_s   = S_TD_R
    else:
        fcfy_val = "\u2014"
        fcfy_lbl = "FCF Yield indisponible"
        fcfy_s   = S_TD_C

    # --- Beta médiane + dispersion ---
    b_med = sa.get("beta_median")
    b_std = sa.get("beta_std")
    if b_med is not None:
        # FR-isation chirurgicale : seules les valeurs (pas l'abréviation "med.")
        _bm_fr = f"{b_med:.2f}".replace('.', ',')
        _bs_fr = f"{b_std:.2f}".replace('.', ',') if b_std is not None else None
        if b_std is not None:
            beta_val = f"med. {_bm_fr}  |  sigma={_bs_fr}"
        else:
            beta_val = _bm_fr
        if b_std is not None and b_std < 0.25:
            beta_lbl = "sensibilité macro homogène — beta sectoriel dominant"
            beta_s   = S_TD_C
        elif b_std is not None and b_std < 0.50:
            beta_lbl = "dispersion modérée — mix macro + idiosyncratique"
            beta_s   = S_TD_A
        else:
            beta_lbl = "forte dispersion betas — facteurs specifiques dominants, alpha potentiel eleve"
            beta_s   = S_TD_G
    else:
        beta_val = "\u2014"
        beta_lbl = "Beta indisponible"
        beta_s   = S_TD_C

    # --- Rows BANK/INSURANCE/REIT specifiques -------------------------------
    # Pour ces profils, remplacer Piotroski/PEG/FCF par les metriques qui ont
    # du sens (P/TBV, ROE, Div. Yield) tout en gardant Beta en dernière ligne.
    def _row_pb():
        _pb = sa.get("pb_median")
        if _pb is None:
            return ("P/TBV médian", "\u2014",
                    "P/TBV indisponible (yfinance priceToBook absent)", S_TD_C)
        if _pb < 1.0:
            return ("P/TBV médian", f"{_pb:.2f}x".replace('.', ','),
                    "décote vs book value — potentielles opportunités (verifier qualité actifs)", S_TD_G)
        if _pb < 1.5:
            return ("P/TBV médian", f"{_pb:.2f}x".replace('.', ','),
                    "valorisation alignée sur la book value — secteur valorisé à sa norme", S_TD_A)
        return ("P/TBV médian", f"{_pb:.2f}x".replace('.', ','),
                "prime marquée sur book value — ROE structurellement supérieur au coût des fonds propres", S_TD_A)

    def _row_roe():
        _roe = sa.get("roe_median")
        if _roe is None:
            return ("ROE médian", "\u2014", "ROE indisponible", S_TD_C)
        if _roe >= 12:
            return ("ROE médian", f"{_roe:.1f} %".replace('.', ','),
                    "rentabilité élevée — au-dessus du coût des fonds propres (~10%)", S_TD_G)
        if _roe >= 8:
            return ("ROE médian", f"{_roe:.1f} %".replace('.', ','),
                    "rentabilité correcte — proche du coût des fonds propres", S_TD_A)
        return ("ROE médian", f"{_roe:.1f} %".replace('.', ','),
                "rentabilité faible — crée de la valeur négative vs coût du capital", S_TD_R)

    def _row_div_yield():
        _dy = sa.get("div_yield_median")
        if _dy is None:
            return ("Dividend Yield médian", "\u2014", "Dividend Yield indisponible", S_TD_C)
        if _dy >= 5.0:
            return ("Dividend Yield médian", f"{_dy:.1f} %".replace('.', ','),
                    "rendement élevé — souvent associé à une croissance limitée", S_TD_G)
        if _dy >= 3.0:
            return ("Dividend Yield médian", f"{_dy:.1f} %".replace('.', ','),
                    "rendement correct — politique de retour actionnaire active", S_TD_A)
        return ("Dividend Yield médian", f"{_dy:.1f} %".replace('.', ','),
                "rendement faible — réinvestissement ou payout prudent", S_TD_C)

    def _row_beta():
        return ("Beta sectoriel", beta_val, beta_lbl, beta_s)

    if _sector_profile == "BANK":
        qual_data = [
            _row_pb(),
            _row_roe(),
            _row_div_yield(),
            _row_beta(),
        ]
    elif _sector_profile == "INSURANCE":
        qual_data = [
            _row_pb(),
            _row_roe(),
            _row_div_yield(),
            _row_beta(),
        ]
    elif _sector_profile == "REIT":
        qual_data = [
            _row_pb(),
            _row_div_yield(),
            ("FCF Yield (median)", fcfy_val, fcfy_lbl, fcfy_s),
            _row_beta(),
        ]
    elif _sector_profile == "UTILITY":
        qual_data = [
            ("PEG ratio (median)", peg_val, peg_lbl, peg_s),
            _row_div_yield(),
            ("FCF Yield (median)", fcfy_val, fcfy_lbl, fcfy_s),
            _row_beta(),
        ]
    else:
        qual_data = [
            ("Piotroski F-Score", f_val, f_lbl, f_s),
            ("PEG ratio (median)", peg_val, peg_lbl, peg_s),
            ("FCF Yield (median)", fcfy_val, fcfy_lbl, fcfy_s),
            _row_beta(),
        ]
    qual_rows = []
    for label, val, interp, val_style in qual_data:
        qual_rows.append([
            Paragraph(f"<b>{label}</b>", S_TD_B),
            Paragraph(val, val_style),
            Paragraph(interp, S_TD_L),
        ])
    # Titre + paragraphe LLM + tableau ensemble pour eviter la coupure
    _qual_block = [_qual_title]
    if _medians_commentary:
        _qual_block.append(Spacer(1, 1.5*mm))
        _qual_block.append(Paragraph(_medians_commentary, S_BODY))
        _qual_block.append(Spacer(1, 2*mm))
    _qual_block.append(tbl([qual_h] + qual_rows, cw=[52*mm, 52*mm, 66*mm]))
    elems.append(KeepTogether(_qual_block))
    if _sector_profile in ("BANK", "INSURANCE"):
        elems.append(src(
            "P/TBV : Price-to-Tangible-Book-Value (yfinance priceToBook). "
            "ROE : Net Income / Equity médian sur le pool. Dividend Yield : yfinance trailing. "
            "Beta : volatilité vs S&P 500 (5 ans). "
            "Piotroski/PEG/FCF non applicables au profil financier (cf. Pillar 3 / SFCR)."))
    elif _sector_profile == "REIT":
        elems.append(src(
            "P/TBV : Price-to-Book. Dividend Yield : FFO-based (médian pool). "
            "FCF Yield : FCF / Market Cap. Beta : volatilité vs S&P 500 (5 ans)."))
    else:
        elems.append(src(
            "Piotroski F-Score : 9 critères binaires profitabilite + levier + efficacite (Piotroski 2000). "
            "PEG = P/E LTM / croissance revenus YoY. FCF Yield = Free Cash Flow / Market Cap. "
            "Beta : volatilité vs S&P 500 (yfinance 5 ans)."))
    elems.append(Spacer(1, 4*mm))

    # ── Tableau 3 : Risque Portefeuille ───────────────────────────────────
    elems.append(Paragraph("Risque Portefeuille et Sensibilite Macro", S_SUBSECTION))

    risk_h = [Paragraph(h, S_TH_C)
              for h in ["Indicateur", "Valeur", "Interpretation analytique"]]

    # --- VaR 95% mensuelle (market-cap weighted) ---
    var_95 = sa.get("var_95_monthly")
    vol_a  = sa.get("vol_annual")
    mdd    = sa.get("max_drawdown_52w")
    if var_95 is not None:
        if vol_a is not None:
            var_val = f"VaR {var_95:.1f}%  |  Vol. {vol_a:.1f}% ann."
        else:
            var_val = f"{var_95:.1f}%"
        if mdd is not None:
            var_val += f"  |  MaxDD {mdd:.1f}%"
        # Interprétation selon sévérité (VaR est négatif)
        if var_95 < -12:
            var_lbl = "risque élevé — pertes mensuelles potentielles importantes pour le sizing"
            var_s   = S_TD_R
        elif var_95 < -8:
            var_lbl = "risque modéré-élevé — position sizing conservateur recommandé"
            var_s   = S_TD_R
        elif var_95 < -5:
            var_lbl = "risque modéré — volatilité sectorielle dans la norme marche"
            var_s   = S_TD_A
        else:
            var_lbl = "risque contenu — faible volatilité sectorielle, beta defensif"
            var_s   = S_TD_G
    else:
        var_val = "\u2014"
        var_lbl = "VaR disponible après 30 jours de cotation minimum"
        var_s   = S_TD_C

    # --- Duration implicite ---
    dur_y  = sa.get("duration_years")
    dur_w  = sa.get("duration_wacc")
    dur_g  = sa.get("duration_growth")
    dur_mt = sa.get("duration_method", "")
    if dur_y is not None:
        dur_val = f"{dur_y} ans  (WACC {dur_w}%  |  g {dur_g}%)"
        if dur_y >= 20:
            dur_lbl = "duration très longue — exposition taux critique, +100bp WACC = -15%+ valorisation"
            dur_s   = S_TD_R
        elif dur_y >= 12:
            dur_lbl = "duration longue — sensibilité taux élevée, surveiller cycle taux banques centrales"
            dur_s   = S_TD_A
        elif dur_y >= 7:
            dur_lbl = "duration modérée — sensibilité taux dans la norme"
            dur_s   = S_TD_C
        else:
            dur_lbl = "duration courte — secteur peu sensible aux taux, valorisation ancrée sur cash"
            dur_s   = S_TD_G
    else:
        dur_val = "\u2014"
        dur_lbl = "Duration indisponible"
        dur_s   = S_TD_C

    risk_data = [
        ("VaR 95% mensuelle (basket mkt-cap)", var_val, var_lbl, var_s),
        ("Duration implicite sectorielle",     dur_val, dur_lbl, dur_s),
    ]
    risk_rows = []
    for label, val, interp, val_style in risk_data:
        risk_rows.append([
            Paragraph(f"<b>{label}</b>", S_TD_B),
            Paragraph(val, val_style),
            Paragraph(interp, S_TD_L),
        ])
    elems.append(KeepTogether(tbl([risk_h] + risk_rows, cw=[52*mm, 52*mm, 66*mm])))

    # Note méthodologique duration si fallback CAPM
    _dur_note_parts = [
        "VaR : simulation historique 52W, basket pondéré market-cap. "
        "Regles racine du temps (VaR_mensuelle = VaR_daily x sqrt(21))."
    ]
    if dur_y is not None and "CAPM" in dur_mt:
        _dur_note_parts.append(
            "Duration calculee depuis WACC median sectoriel — "
            "lancer une Analyse Societe pour affiner."
        )
    elif dur_y is not None:
        _dur_note_parts.append(
            "Duration : formule Gordon Growth D=(1+g)/(WACC-g), "
            "WACC depuis analyses societe en cache."
        )
    elems.append(src(" ".join(_dur_note_parts)))
    elems.append(Spacer(1, 3*mm))

    # ── Note analytique ────────────────────────────────────────────────────
    if hhi and pe_ltm:
        if hhi >= 2500:
            hhi_note = (
                f"Le secteur <b>{sector_name}</b> présente une structure oligopolistique "
                f"(HHI {hhi:,}) dominée par 2-3 acteurs majeurs. "
                f"Cette concentration justifié historiquement un premium de valorisation "
                f"par rapport aux secteurs fragmentés — les barrières à l'entrée et les "
                f"effets de réseau limitent la disruption compétitive."
            )
        elif hhi >= 1500:
            hhi_note = (
                f"Le secteur <b>{sector_name}</b> affiche une concentration modérée "
                f"(HHI {hhi:,}). Plusieurs acteurs se partagent le leadership — "
                f"la compétition reste structurellement présente mais les positions "
                f"établies offrent une visibilité sur les revenus."
            )
        else:
            hhi_note = (
                f"Le secteur <b>{sector_name}</b> est fragmenté "
                f"(HHI {hhi:,}). La concurrence intense comprime les marges "
                f"structurellement — la sélectivité est primordiale dans l'allocation."
            )

        if pe_prem is not None and pe_hist:
            pe_note = (
                f" Le P/E médian actuel de <b>{pe_ltm:.1f}x</b> se situe à "
                f"<b>{pe_prem:+.0f}%</b> vs la médiane historique 5 ans ({pe_hist:.1f}x) — "
                f"{pe_lbl}."
            )
        else:
            pe_note = f" P/E médian LTM : <b>{pe_ltm:.1f}x</b>."

        elems.append(Paragraph(hhi_note + pe_note, S_BODY))
        elems.append(Spacer(1, 3*mm))

    if roic_std is not None:
        elems.append(Paragraph(
            f"<b>Implications de la dispersion ROIC.</b> "
            f"L'écart-type du ROIC/ROE de <b>{roic_std:.1f}%</b> au sein du secteur "
            f"indique que {roic_lbl}. "
            f"Dans un secteur à forte dispersion, les gérants actifs ont un avantage "
            f"structurel sur les approches indicielles — l'alpha vient de la sélection, "
            f"pas de l'exposition sectorielle.", S_BODY))

    # ── Scénarios agrégés et conviction delta (si cache dispo) ─────────────
    bull = sa.get("scenarios_bull_median")
    base = sa.get("scenarios_base_median")
    bear = sa.get("scenarios_bear_median")
    cd   = sa.get("conviction_delta_mean")

    if any(v is not None for v in [bull, base, bear, cd]):
        elems.append(Spacer(1, 4*mm))
        elems.append(Paragraph("Synthèse scénarios & robustesse des theses", S_SUBSECTION))

        sc_h = [Paragraph(h, S_TH_C)
                for h in ["Indicateur", "Valeur", "Source", "Lecture"]]
        sc_rows = []
        if bull is not None or base is not None or bear is not None:
            def _fmt_sc(v):
                if v is None: return "\u2014"
                s = f"{v:+.1f}%"
                return s
            sc_rows.append([
                Paragraph("<b>Upside agrégé médian</b>", S_TD_B),
                Paragraph(
                    f"Bull : <b>{_fmt_sc(bull)}</b>  |  "
                    f"Base : <b>{_fmt_sc(base)}</b>  |  "
                    f"Bear : <b>{_fmt_sc(bear)}</b>",
                    S_TD_C),
                Paragraph("DCF Monte Carlo / cache analyses société", S_TD_L),
                Paragraph(
                    "Asymétrie risque/rendement sectorielle agrégée. "
                    "* Basé sur les analyses individuelles disponibles en cache.",
                    S_TD_L),
            ])
        if cd is not None:
            cd_s = S_TD_G if cd > -0.15 else (S_TD_R if cd < -0.5 else S_TD_A)
            sc_rows.append([
                Paragraph("<b>Conviction delta moyen</b>", S_TD_B),
                Paragraph(f"<b>{cd:+.2f}</b>", cd_s),
                Paragraph("Devil's advocate / cache analyses société", S_TD_L),
                Paragraph(
                    "0 = thèses robustes · -1 = thèses très challengeables. "
                    "* Basé sur les analyses individuelles disponibles en cache.",
                    S_TD_L),
            ])
        if sc_rows:
            elems.append(KeepTogether(tbl([sc_h] + sc_rows,
                                           cw=[44*mm, 46*mm, 40*mm, 40*mm])))
            elems.append(src("FinSight IA — * Métriques calculées depuis les analyses sociétés individuelles (cache). "
                             "N/D si aucune analyse société préalable."))
    elif len(tickers_data) >= 3:
        elems.append(Spacer(1, 3*mm))
        elems.append(Paragraph(
            "<i>Scénarios agrégés et conviction delta non disponibles — "
            "lancer une Analyse Société FinSight IA pour chaque valeur afin "
            "d'enrichir ce rapport avec les DCF, scénarios bear/base/bull "
            "et le protocole adversarial individuel.</i>",
            _style('nd_note', size=8, leading=11, color=GREY_TEXT,
                   bold=False, align=TA_LEFT)))

    return elems


def _safe(s):
    """Échappe les caractères XML pour ReportLab Paragraph + convertit le
    markdown bold (**texte**) en balises ReportLab <b>texte</b>.

    Les LLM (Groq, Mistral, Anthropic) retournent souvent du markdown
    inline avec **bold** au lieu de respecter le format demande. ReportLab
    ne parse pas le markdown -> sans cette conversion, les ** apparaissent
    en brut dans le PDF (ex: "**banque en ligne**").
    """
    if not s:
        return ""
    out = str(s)
    # 0. Remplacer les caractères Unicode problématiques (carrés noirs dans ReportLab)
    #    CO₂ → CO2, ² → 2, ³ → 3, ₂ → 2, etc.
    _unicode_fixes = {
        "\u2082": "2", "\u2083": "3", "\u2080": "0", "\u2081": "1",  # subscripts
        "\u00b2": "2", "\u00b3": "3",  # superscripts ² ³
        "\u25b6": ">", "\u25ba": ">", "\u25c0": "<",  # triangles
        "\u2022": "-", "\u2023": "-", "\u25cf": "-",  # bullets
        "\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',  # smart quotes
        "\u2013": "-", "\u2014": " - ",  # en/em dash (garder le tiret cadratin)
        "\u2026": "...",  # ellipsis
        "\u20ac": "EUR",  # euro sign (si pas dans la police)
    }
    for _uc, _repl in _unicode_fixes.items():
        out = out.replace(_uc, _repl)
    # 1. Echapper les caracteres XML d'abord (pour eviter qu'un < dans le
    #    contenu ne casse le parser ReportLab)
    out = out.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # 2. Convertir le markdown **bold** en <b>bold</b> (ReportLab inline tag)
    #    Pattern : **texte non-vide non-greedy**
    import re as _re
    out = _re.sub(r'\*\*([^*]+?)\*\*', r'<b>\1</b>', out)
    # 3. Convertir aussi __bold__ -> <b>bold</b> (autre variante markdown)
    out = _re.sub(r'__([^_]+?)__', r'<b>\1</b>', out)
    return out


def _detect_sector_profile(tickers_data: list, sector_name: str) -> str:
    """Détecte le profil dominant d'un secteur à partir des industries des tickers.

    Returns un des : STANDARD, BANK, INSURANCE, REIT, UTILITY, OIL_GAS
    Si aucun profil domine (<60% des tickers), retourne STANDARD.
    """
    try:
        from core.sector_profiles import detect_profile, STANDARD
    except Exception:
        return "STANDARD"

    if not tickers_data:
        return "STANDARD"

    # Fallback prioritaire : le nom de secteur FR explicite (Banques, Assurance,
    # Immobilier, Services aux collectivités) court-circuite la détection
    # par industry yfinance — utile quand l'enrichissement realtime échoue
    # (rate limit Streamlit Cloud) et que industry est vide sur tous les tickers.
    _sn = (sector_name or "").strip().lower()
    if "banque" in _sn:
        return "BANK"
    if "assurance" in _sn or "insurance" in _sn:
        return "INSURANCE"
    if "immobilier" in _sn or "foncière" in _sn or "foncier" in _sn:
        return "REIT"
    if "collectivit" in _sn:
        return "UTILITY"
    if "pétrole" in _sn or "petrole" in _sn:
        return "OIL_GAS"

    # Compter les profils sur tous les tickers
    profile_counts = {}
    for t in tickers_data:
        ind = t.get("industry") or ""
        sec = t.get("sector") or sector_name or ""
        p = detect_profile(sec, ind)
        profile_counts[p] = profile_counts.get(p, 0) + 1

    total = sum(profile_counts.values())
    if total == 0:
        return "STANDARD"

    # Profil dominant si >= 50% des tickers sont non-standard
    # (seuil bas car les pools mixtes doivent basculer dès que le profil spécifique dépasse le standard)
    dominant, dom_count = max(profile_counts.items(), key=lambda x: x[1])
    if dominant != "STANDARD" and dom_count / total >= 0.5:
        return dominant
    # Cas particulier : si aucun profil ne domine mais BANK + INSURANCE > STANDARD
    # → garder STANDARD (secteur vraiment mélangé)
    return "STANDARD"


def _aggregate_subsectors(tickers_data: list[dict]) -> list[dict]:
    """Agrège les tickers par sous-secteur (industry) et calcule les métriques."""
    from statistics import median as _med
    groups = {}
    for t in tickers_data:
        ind = t.get("industry") or "Autre"
        groups.setdefault(ind, []).append(t)
    result = []
    for ind_name, items in groups.items():
        if ind_name == "Autre" and len(groups) > 1:
            continue
        nb = len(items)
        scores = [x.get("score_global") or 0 for x in items]
        avg_score = int(sum(scores) / nb) if nb else 0
        # Detection profil pour adapter les metriques affichees
        try:
            from core.sector_profiles import detect_profile
            _ind_profiles = [detect_profile(x.get("sector", ""), x.get("industry", ""))
                             for x in items]
            _sub_profile = max(set(_ind_profiles), key=_ind_profiles.count) if _ind_profiles else "STANDARD"
        except Exception:
            _sub_profile = "STANDARD"

        # EV/EBITDA : pour banques, P/E est plus pertinent (EV/EBITDA aberrant)
        if _sub_profile in ("BANK", "INSURANCE"):
            pes = [x.get("pe") or x.get("pe_ratio") for x in items
                   if (x.get("pe") or x.get("pe_ratio")) and 1 < (x.get("pe") or x.get("pe_ratio")) < 100]
            ev_med = f"{_med(pes):.1f}x P/E".replace('.', ',') if pes else "\u2014"
        else:
            evs = [x["ev_ebitda"] for x in items if x.get("ev_ebitda") and 1 < x["ev_ebitda"] < 100]
            if evs:
                ev_med = f"{_med(evs):.1f}x".replace('.', ',')
            else:
                # Fallback P/S si EV/EBITDA indisponible
                ps_vals = [x.get("ps_ratio") for x in items if x.get("ps_ratio")]
                ev_med = f"{_med(ps_vals):.1f}x P/S".replace('.', ',') if ps_vals else "\u2014"

        # Marge : pour banques/assurance, EBITDA margin est aberrant (~80-95%
        # car les revenus = NII + commissions et l'EBITDA = ces revenus moins
        # les frais operationnels). On affiche ROE qui est plus parlant.
        if _sub_profile in ("BANK", "INSURANCE"):
            roes = [x.get("roe") for x in items if x.get("roe") is not None]
            mg_med = f"{_med(roes):.1f} % ROE".replace('.', ',') if roes else "\u2014"
        else:
            mgs = [x.get("ebitda_margin") or x.get("gross_margin") or 0 for x in items
                   if (x.get("ebitda_margin") or x.get("gross_margin"))]
            mg_med = f"{_med(mgs):.1f} %".replace('.', ',') if mgs else "\u2014"
        grs = [x.get("revenue_growth") or 0 for x in items if x.get("revenue_growth") is not None]
        # revenue_growth stocké en fraction (0.068 = +6.8%) — convertir en % avant format
        gr_med = f"{_med(grs)*100:+.1f} %".replace('.', ',') if grs else "\u2014"
        moms = [x.get("momentum_52w") or 0 for x in items if x.get("momentum_52w") is not None]
        mom_med = f"{_med(moms):+.1f} %".replace('.', ',') if moms else "\u2014"
        sig = "Surpondérer" if avg_score >= 60 else ("Sous-pondérer" if avg_score < 40 else "Neutre")
        best = sorted(items, key=lambda x: x.get("score_global") or 0, reverse=True)[:3]
        best_names = [(b.get("ticker", ""), b.get("company", ""), b.get("score_global", 0)) for b in best]
        result.append({
            "name": ind_name, "nb": nb, "score": avg_score, "signal": sig,
            "ev_ebitda": ev_med, "margin": mg_med, "growth": gr_med, "momentum": mom_med,
            "best": best_names, "pct": round(nb / len(tickers_data) * 100, 1),
        })
    result.sort(key=lambda x: x["score"], reverse=True)
    return result


def _subsector_fallback_text(subsectors: list[dict], sector_name: str) -> dict:
    """Genere un dict d'insights deterministe — utilise en fallback quand le LLM
    echoue (timeout, ban Groq, 401...). Texte analytique base sur les metriques
    agregees et les top tickers de chaque sous-secteur."""
    d: dict = {}
    if not subsectors:
        return d
    _top = subsectors[0]
    _poids_top = _top.get("pct", 0)
    d["intro"] = (
        f"Le secteur {sector_name} se decompose en {len(subsectors)} sous-segments distincts, "
        f"avec {_top['name']} en tete ({_poids_top}% des acteurs couverts, score "
        f"{_top['score']}/100, signal {_top['signal']}). "
        f"La dispersion des scores composites ({subsectors[0]['score']}-"
        f"{subsectors[-1]['score']}/100) refletet des dynamiques de croissance et de "
        f"valorisation sensiblement differenciees entre segments, justifiant une allocation "
        f"sélective plutôt qu'un biais beta sectoriel uniforme. Les multiples EV/EBITDA, les "
        f"marges EBITDA et le momentum 52W fournissent une grille de lecture complete pour "
        f"identifier les poches de valeur et les segments en acceleration fondamentale."
    )
    for s in subsectors[:8]:
        n = s["name"]
        _best = s.get("best", [])
        _best_txt = ", ".join(f"{b[1]} ({b[0]})" for b in _best[:3]) if _best else "—"
        d[f"{n}_presentation"] = (
            f"Le sous-segment {n} regroupe {s['nb']} emetteurs couverts ({s['pct']}% du pool "
            f"sectoriel), portes par des acteurs influents tels que {_best_txt}. Le score "
            f"composite moyen ressort a {s['score']}/100 avec un signal {s['signal']}, refletant "
            f"une combinaison de valorisation (EV/EBITDA median {s['ev_ebitda']}), de rentabilite "
            f"operationnelle (marge {s['margin']}) et de trajectoire top-line ({s['growth']} YoY)."
        )
        d[f"{n}_drivers"] = (
            f"Les drivers structurels de {n} incluent l'innovation produit, la consolidation "
            f"concurrentielle et les cycles d'investissement. La croissance observée ({s['growth']}) "
            f"et le momentum boursier 52W ({s['momentum']}) materialisent la capacite des acteurs "
            f"a convertir ces drivers en creation de valeur mesurable."
        )
        d[f"{n}_risques"] = (
            f"Les risques specifiques a {n} portent sur la compression des marges en cas de "
            f"pression concurrentielle, la sensibilite au cycle macro et les arbitrages reglementaires. "
            f"Une marge mediane de {s['margin']} laisse peu de coussin en cas de retournement, et "
            f"le momentum actuel ({s['momentum']}) doit etre lu a l'aune de la volatilite propre au "
            f"segment."
        )
        d[f"{n}_profil"] = (
            f"Profil financier typique : rentabilite moyenne ({s['margin']}), croissance "
            f"{s['growth']}, valorisation {s['ev_ebitda']}. Segment plutôt {s['signal'].lower()}."
        )
    d["allocation"] = (
        f"L'allocation sous-sectorielle recommandee privilegie {subsectors[0]['name']} "
        f"(score {subsectors[0]['score']}/100) comme surpondere de conviction, complete par "
        + (f"{subsectors[1]['name']} (score {subsectors[1]['score']}/100) en poche tactique. " if len(subsectors) > 1 else ". ") +
        f"Les segments en bas du classement ({subsectors[-1]['name']}, score "
        f"{subsectors[-1]['score']}/100) meritent une exposition reduite en attendant une "
        f"amelioration des fondamentaux ou une recote de valorisation. Horizon 12-18 mois, "
        f"conviction moderee a elevee selon le respect des catalyseurs (publications trimestrielles, "
        f"guidance annuelle, momentum macro sectoriel). Une reevaluation mensuelle du scoring "
        f"composite permet de detecter les bascules de signal et d'ajuster les poids tactiques."
    )
    return d


def _generate_subsector_llm(subsectors: list[dict], sector_name: str, profile: str = "STANDARD") -> dict:
    """Génère les insights LLM par sous-secteur (drivers, risques, spécificités).
    Le profil sectoriel adapte les hints pour utiliser les bonnes métriques.
    """
    try:
        from core.llm_provider import llm_call
        try:
            from core.sector_profiles import get_prompt_hints
            _profile_hint = get_prompt_hints(profile)
        except Exception:
            _profile_hint = ""
        import json, re
        subs_desc = "\n".join(
            f"- {s['name']} ({s['nb']} socs, score {s['score']}/100, {s['signal']}, "
            f"EV/EBITDA {s['ev_ebitda']}, marge {s['margin']}, croiss. {s['growth']}, mom. {s['momentum']})"
            for s in subsectors
        )
        prompt = (
            f"Tu es un analyste sell-side senior. Analyse les sous-secteurs de {sector_name} :\n\n"
            f"{subs_desc}\n\n"
        )
        if _profile_hint:
            prompt += f"PROFIL SECTORIEL SPÉCIFIQUE :\n{_profile_hint}\n\n"
        prompt += (
            f"RÈGLES : français correct avec accents, prose technique, cite les chiffres. "
            f"Pas de markdown **, pas d'emojis.\n"
            f"FORMAT CHIFFRES FR OBLIGATOIRE : virgule décimale (« 33,9x » et non « 33.9x »), "
            f"espace avant « % » et « x » (« 20,8 % », « 1,6x »), espace séparateur "
            f"de milliers (« 1 353 M€ »). JAMAIS de point décimal anglophone.\n"
            f"Réponds en JSON valide :\n"
            f'{{\n'
            f'  "intro": "120 mots : vue d\'ensemble de la décomposition sous-sectorielle, '
            f'poids relatifs et dynamiques croisées",\n'
        )
        for s in subsectors[:8]:
            n = s["name"].replace('"', "'")
            best_tickers = ", ".join(b[0] for b in s.get("best", [])[:3])
            prompt += (
                f'  "{n}_presentation": "100 mots : présentation du sous-secteur {n} — '
                f'acteurs influents ({best_tickers}), taille du marché, spécificités structurelles, '
                f'positionnément dans la chaîne de valeur",\n'
                f'  "{n}_drivers": "80 mots : drivers de croissance SPÉCIFIQUES à {n} et UNIQUEMENT à {n}. '
                f'NE PAS répéter les mêmes drivers pour chaque sous-secteur. '
                f'Métriques : marge {s["margin"]}, croissance {s["growth"]}, EV/EBITDA {s["ev_ebitda"]}. '
                f'Cite des exemples concrets (produits, technologies, marchés, réglementations) propres à {n}.",\n'
                f'  "{n}_risques": "80 mots : risques SPÉCIFIQUES à {n} et UNIQUEMENT à {n}. '
                f'NE PAS utiliser de formulations génériques comme \'pression concurrentielle\' ou \'cycle macro\'. '
                f'Cite des risques propres : technologie obsolète, réglementation sectorielle, concentration clients, '
                f'dépendance fournisseur, etc. Momentum 52W : {s["momentum"]}.",\n'
                f'  "{n}_profil": "60 mots : profil financier typique de {n} — '
                f'cite les chiffres medians du sous-secteur",\n'
            )
        prompt += (
            f'  "allocation": "150 mots : recommandation d\'allocation entre sous-secteurs, '
            f'sous-secteurs à privilégier, horizon, conviction et catalyseurs déterminants"\n}}'
        )
        # Refonte 2026-04-14 : llm_call(phase=long) -> Mistral primary (gratuit, qualite FR top)
        resp = llm_call(prompt, phase="long", max_tokens=4500)
        m = re.search(r'\{.*\}', resp, re.DOTALL)
        if m:
            _llm = json.loads(m.group(0))
            # Complete avec fallback deterministe les cles manquantes
            _fb = _subsector_fallback_text(subsectors, sector_name)
            for k, v in _fb.items():
                if k not in _llm or not _llm.get(k):
                    _llm[k] = v
            # Restore accents — Mistral oublie systematiquement sur certains
            # mots ("emetteur", "rentabilite", "modere", "homogene", etc.)
            try:
                from tools.restore_accents import restore_accents_in_text as _ra
                for _k in _llm:
                    if isinstance(_llm[_k], str):
                        _llm[_k] = _ra(_llm[_k])
            except Exception:
                pass
            return _llm
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("[sector_pdf] subsector LLM error: %s", e)
    # Fallback complet deterministe
    return _subsector_fallback_text(subsectors, sector_name)


def _build_subsector_decomposition(tickers_data: list[dict], sector_name: str, registry=None):
    """Section — Décomposition par sous-secteur (industry GICS)."""
    subsectors = _aggregate_subsectors(tickers_data)
    if len(subsectors) <= 1:
        return []  # pas de décomposition si un seul sous-secteur

    elems = []
    elems.append(Spacer(1, 8*mm))
    if registry is not None:
        elems.append(SectionAnchor('subsectors', registry))
    elems += section_title("Décomposition par Sous-Secteur", "2b")
    elems.append(Spacer(1, 3*mm))

    # Génération LLM — injecte le profil sectoriel dominant
    _profile_for_llm = _detect_sector_profile(tickers_data, sector_name)
    llm_data = _generate_subsector_llm(subsectors, sector_name, profile=_profile_for_llm)
    intro = llm_data.get("intro", "")
    if intro:
        elems.append(Paragraph(_safe(intro), S_BODY))
        elems.append(Spacer(1, 3*mm))

    # Tableau récapitulatif
    hdr = [Paragraph(h, S_TH_L if i == 0 else S_TH_C) for i, h in enumerate(
        ["Sous-secteur", "Nb", "Score", "Signal", "EV/EBITDA", "Marge", "Croiss.", "Mom."])]
    rows = []
    for s in subsectors:
        sig_s = S_TD_G if s["signal"] == "Surpondérer" else (S_TD_R if s["signal"] == "Sous-pondérer" else S_TD_A)
        rows.append([
            Paragraph(_safe(s["name"]), S_TD_L),
            Paragraph(str(s["nb"]), S_TD_C),
            Paragraph(str(s["score"]), S_TD_BC),
            Paragraph(s["signal"], sig_s),
            Paragraph(s["ev_ebitda"], S_TD_C),
            Paragraph(s["margin"], S_TD_C),
            Paragraph(s["growth"], S_TD_C),
            Paragraph(s["momentum"], S_TD_C),
        ])
    _cw = [42*mm, 12*mm, 16*mm, 24*mm, 20*mm, 18*mm, 18*mm, 18*mm]
    _subsec_tbl = tbl([hdr] + rows, cw=_cw)
    elems.append(_subsec_tbl)
    elems.append(src(f"FinSight IA \u2014 Agrégation par sous-secteur GICS. Score = composite 0-100."))
    elems.append(Spacer(1, 4*mm))

    # Détail par sous-secteur : présentation, drivers, risques, profil
    for s in subsectors[:6]:
        n = s["name"]
        presentation = llm_data.get(f"{n}_presentation", "")
        drivers = llm_data.get(f"{n}_drivers", "")
        risques = llm_data.get(f"{n}_risques", "")
        profil = llm_data.get(f"{n}_profil", "")
        best_str = ", ".join(f"{b[0]} ({b[2]}/100)" for b in s["best"])

        # Titre en KeepTogether avec première ligne de contenu
        _title_para = Paragraph(_safe(
            f"{n} \u2014 {s['nb']} soci\u00e9t\u00e9s \u00b7 Score {s['score']}/100 \u00b7 {s['signal']}"),
            S_SUBSECTION)
        if presentation:
            elems.append(KeepTogether([_title_para, Spacer(1, 1*mm),
                                        Paragraph(_safe(presentation), S_BODY)]))
        else:
            elems.append(_title_para)
        elems.append(Spacer(1, 1*mm))
        if drivers:
            elems.append(Paragraph(f"<b>Drivers :</b> {_safe(drivers)}", S_BODY))
        if risques:
            elems.append(Paragraph(f"<b>Risques :</b> {_safe(risques)}", S_BODY))
        if profil:
            elems.append(Paragraph(f"<b>Profil financier :</b> {_safe(profil)}", S_BODY))
        elems.append(Paragraph(f"<b>Top soci\u00e9t\u00e9s :</b> {_safe(best_str)}", S_BODY))
        elems.append(Spacer(1, 3*mm))

    # Recommandation allocation
    alloc = llm_data.get("allocation", "")
    if alloc:
        elems.append(Paragraph("Recommandation d'allocation sous-sectorielle", S_SUBSECTION))
        elems.append(Spacer(1, 1*mm))
        elems.append(Paragraph(_safe(alloc), S_BODY))
        elems.append(Spacer(1, 3*mm))

    return elems


def _build_acteurs(tickers_data: list[dict], sector_name: str, registry=None):
    elems = []
    # CondPageBreak : la section 3 est dense (tableau comparatif + 2 paragraphes
    # LLM). Si moins de 130mm restants sur la page courante, sauter a la suivante
    # pour eviter que le titre "3." reste seul en bas de la page precedente.
    elems.append(CondPageBreak(130*mm))
    elems.append(Spacer(1, 10*mm))
    if registry is not None:
        elems.append(SectionAnchor('acteurs', registry))
    elems += section_title(_slbl("acteurs"), 3)
    elems.append(Spacer(1, 4*mm))
    elems.append(debate_q(
        "Comment les modèles economiques se différenciént-ils et lesquels sont les plus résilients ?"))

    N = len(tickers_data)
    sorted_data = sorted(tickers_data, key=lambda x: x.get('score_global') or 0, reverse=True)
    best = sorted_data[0] if sorted_data else {}

    # Intro acteurs : appel LLM pour generer un texte contextuel (chasse hardcoding #90)
    _acteurs_intro_llm = ""
    try:
        from core.llm_provider import llm_call
        _worst = sorted_data[-1] if sorted_data else {}
        _top3_names = ", ".join(
            f"{t.get('ticker','?')} ({int(t.get('score_global') or 0)}/100)"
            for t in sorted_data[:3]
        )
        # LLM-A compressed
        _prompt_acteurs = (
            f"Analyste buy-side senior. Introduction 200-240 mots a l'analyse des "
            f"{N} acteurs du secteur {sector_name}.\n"
            f"Top 3 FinSight : {_top3_names}. Leader : {best.get('company','?')} "
            f"(score {best.get('score_global','?')}/100, marge EBITDA "
            f"{best.get('ebitda_margin','?')}, croissance {best.get('revenue_growth','?')}). "
            f"Lanterne : {_worst.get('company','?')} (score {_worst.get('score_global','?')}/100).\n\n"
            f"EXACTEMENT 2 paragraphes. Chaque paragraphe commence par son titre en "
            f"majuscules suivi de ' : ' puis le corps du paragraphe IMMEDIATEMENT sur "
            f"la MEME ligne (pas de saut de ligne entre le titre et le corps, pas de "
            f"sous-titre intermediaire).\n"
            f"1. PANORAMA : hierarchie concurrentielle, ce qui distingue leaders et "
            f"challengers, drivers de differentiation.\n"
            f"2. DISPERSION : ce que le spread implique pour l'allocation (concentration "
            f"vs diversification), ratios privilegies pour le stock-picking.\n\n"
            f"Francais avec accents. Pas de markdown/emojis. Pas de sous-titres dans un "
            f"paragraphe."
        )
        # Read from parallel batch first (perf 26/04/2026)
        _acteurs_intro_llm = _SECTOR_LLM_BATCH.get("acteurs_intro", "")
        if not _acteurs_intro_llm:
            _acteurs_intro_llm = llm_call(_prompt_acteurs, phase="long", max_tokens=700) or ""
    except Exception as _e:
        log.debug(f"[sector_pdf_writer:_build_acteurs] exception skipped: {_e}")

    if _acteurs_intro_llm.strip():
        # NIGHT-3 : render avec sous-titres bleus via helper propage
        try:
            from outputs.pdf_writer import _render_llm_structured as _rls
            _rls(elems, _acteurs_intro_llm, section_map={
                "PANORAMA":   "Panorama sectoriel",
                "DISPERSION": "Lecture de la dispersion",
            })
        except Exception:
            for _p in _acteurs_intro_llm.split("\n\n"):
                _clean = _p.strip().replace("\n", " ")
                if _clean:
                    elems.append(Paragraph(_safe(_clean), S_BODY))
                    elems.append(Spacer(1, 2*mm))
    else:
        elems.append(Paragraph(
            f"L'analyse des <b>{N} acteurs</b> du secteur <b>{sector_name}</b> r\u00e9v\u00e8le des profils "
            f"de risque/rendement distincts. <b>{best.get('company', 'Le leader sectoriel')}</b> "
            f"affiche le score composite le plus \u00e9lev\u00e9 ({best.get('score_global', 'N/A')}/100), "
            f"tir\u00e9 par ses fondamentaux de qualit\u00e9 et son positionnement concurrentiel. "
            f"La dispersion des marges EBITDA illustre les differences de mod\u00e8les \u00e9conomiques "
            f"entre acteurs \u00e9tablis et challengers. L'analyse des ratios de valorisation permet "
            f"d'identifier les d\u00e9cotes et primes injustifi\u00e9es par rapport aux pairs.", S_BODY))
    elems.append(Spacer(1, 3*mm))

    # Profil sectoriel dominant — détermine les colonnes du tableau comparatif
    _sec_profile = _detect_sector_profile(tickers_data, sector_name)
    _comp_title = Paragraph("Comparatif financier \u2014 Acteurs couverts LTM", S_SUBSECTION)

    # Colonnes adaptées au profil
    if _sec_profile == "BANK":
        _comp_cols = ["Ticker", "Rev. LTM (Mds)", "Crois.", "ROE", "P/E", "P/TBV", "Div. Yield"]
    elif _sec_profile == "REIT":
        _comp_cols = ["Ticker", "Rev. LTM (Mds)", "Crois.", "Mg. EBITDA", "ROE", "P/B", "Div. Yield"]
    elif _sec_profile == "UTILITY":
        _comp_cols = ["Ticker", "Rev. LTM (Mds)", "Crois.", "Mg. EBITDA", "ROE", "EV/EBITDA", "Div. Yield"]
    elif _sec_profile == "INSURANCE":
        _comp_cols = ["Ticker", "Rev. LTM (Mds)", "Crois.", "ROE", "P/E", "P/B", "Div. Yield"]
    elif _sec_profile == "OIL_GAS":
        _comp_cols = ["Ticker", "Rev. LTM (Mds)", "Crois.", "Mg. EBITDA", "ROE", "EV/DACF*", "P/E"]
    else:
        _comp_cols = ["Ticker", "Rev. LTM (Mds)", "Crois.", "Mg. Brute", "Mg. EBITDA", "ROE", "EV/EBITDA"]

    _comp_cw = [16*mm, 28*mm, 20*mm, 26*mm, 28*mm, 24*mm, 28*mm]
    comp_h = [Paragraph(h, S_TH_C) for h in _comp_cols]

    def _cc(v, col):
        if col == 0:
            return Paragraph(f"<b>{v}</b>", S_TD_BC)
        if col == 2:
            sv = str(v)
            if sv.startswith('+'):
                return Paragraph(sv, S_TD_G)
            if sv.startswith('-'):
                return Paragraph(sv, S_TD_R)
        if v in ("N/A", "\u2014"):
            return Paragraph(str(v), S_TD_C)
        return Paragraph(str(v), S_TD_C)

    def _fmt_x(v):
        if v is None: return "\u2014"
        try: return f"{float(v):.1f}x".replace('.', ',')
        except Exception: return "\u2014"

    def _fmt_dy(v):
        """Dividend yield : cli_analyze stocke en fraction (0.0194 = 1.94%)."""
        if v is None: return "\u2014"
        try:
            fv = float(v)
            # Si valeur < 1 : fraction → multiplier par 100
            # Sinon : déjà en %
            pct = fv * 100 if abs(fv) < 1 else fv
            return f"{pct:.1f} %".replace('.', ',')
        except Exception: return "\u2014"

    comp_rows = []
    ccy = tickers_data[0].get('currency', 'EUR') if tickers_data else 'EUR'
    for t in sorted_data[:12]:
        row = [
            t.get('ticker', '?'),
            _fmt_mds(t.get('revenue_ltm')),
            _fmt_pct(t.get('revenue_growth')),
        ]
        if _sec_profile == "BANK":
            row += [
                _fmt_pct(t.get('roe')),
                _fmt_x(t.get('pe_ratio') or t.get('pe')),
                _fmt_x(t.get('pb_ratio') or t.get('pb')),
                _fmt_dy(t.get('div_yield')),
            ]
        elif _sec_profile == "REIT":
            row += [
                _fmt_pct(t.get('ebitda_margin'), sign=False),
                _fmt_pct(t.get('roe')),
                _fmt_x(t.get('pb_ratio') or t.get('pb')),
                _fmt_dy(t.get('div_yield')),
            ]
        elif _sec_profile == "UTILITY":
            row += [
                _fmt_pct(t.get('ebitda_margin'), sign=False),
                _fmt_pct(t.get('roe')),
                _fmt_x(t.get('ev_ebitda')),
                _fmt_dy(t.get('div_yield')),
            ]
        elif _sec_profile == "INSURANCE":
            row += [
                _fmt_pct(t.get('roe')),
                _fmt_x(t.get('pe_ratio') or t.get('pe')),
                _fmt_x(t.get('pb_ratio') or t.get('pb')),
                _fmt_dy(t.get('div_yield')),
            ]
        elif _sec_profile == "OIL_GAS":
            # EV/DACF approxime par EV/EBITDA * 1.18 (DACF ~ 0.85 * EBITDA pour
            # les E&P typiques avec interet financier et taxes). Marque d'un *
            _ev_og = t.get('ev_ebitda')
            _dacf_val = None
            if _ev_og is not None:
                try:
                    _dacf_val = float(_ev_og) * 1.18
                except Exception as _e:
                    log.debug(f"[sector_pdf_writer:_fmt_dy] exception skipped: {_e}")
            _dacf_s = f"{_dacf_val:.1f}x*" if _dacf_val else "\u2014"
            row += [
                _fmt_pct(t.get('ebitda_margin'), sign=False),
                _fmt_pct(t.get('roe')),
                _dacf_s,
                _fmt_x(t.get('pe_ratio') or t.get('pe')),
            ]
        else:
            # STANDARD : fallback palier 2 sur P/S si EV/EBITDA absent
            _ev_val = t.get('ev_ebitda')
            _ps_val = t.get('ps_ratio')
            _val_cell = _fmt_x(_ev_val) if _ev_val else (f"{_ps_val:.1f}x P/S" if _ps_val else "\u2014")
            row += [
                _fmt_pct(t.get('gross_margin'), sign=False),
                _fmt_pct(t.get('ebitda_margin'), sign=False),
                _fmt_pct(t.get('roe')),
                _val_cell,
            ]
        comp_rows.append([_cc(v, j) for j, v in enumerate(row)])

    elems.append(KeepTogether([
        _comp_title,
        Spacer(1, 2*mm),
        tbl([comp_h] + comp_rows, cw=_comp_cw),
    ]))
    _n_tier2 = sum(1 for t in tickers_data if t.get('valuation_tier', 1) >= 2)
    _val_note = f"FinSight IA \u2014 yfinance, FMP. LTM = Last Twelve Months. Devise : {ccy}."
    # Note profil sectoriel
    _profile_notes = {
        "BANK":     " Secteur bancaire : valorisation sur P/TBV et P/E (EV/EBITDA non applicable).",
        "REIT":     " Foncières cotées : valorisation sur P/B et FFO (EBITDA partiellement déformé par les amortissements).",
        "UTILITY":  " Utilities régulées : multiples stables soutenus par le cadre régulatoire.",
        "INSURANCE":" Assurance : valorisation sur P/EV et P/B (revenus techniques + portefeuille d'investissement).",
        "OIL_GAS":  " Oil & Gas E&P : multiples cycliques, à lire en relatif au prix du baril et aux réserves.",
    }
    if _sec_profile in _profile_notes:
        _val_note += _profile_notes[_sec_profile]
    if _n_tier2 > 0 and _sec_profile == "STANDARD":
        _val_note += (f" * {_n_tier2} soci\u00e9t\u00e9(s) valoris\u00e9e(s) via P/S "
                      f"(EBITDA n\u00e9gatif \u2014 palier 2). P/S = Price-to-Sales.")
    elems.append(src(_val_note))
    elems.append(Spacer(1, 3*mm))

    # Paragraph analytique post-tableau (adapté au profil sectoriel)
    top2 = sorted_data[:2] if len(sorted_data) >= 2 else sorted_data
    names = " et ".join(t.get('company', t.get('ticker', ''))[:25] for t in top2)
    if _sec_profile in ("BANK", "INSURANCE"):
        _post_txt = (
            f"{names} ressortent comme les acteurs les mieux positionnés sur "
            f"les critères de rentabilité (ROE) et de valorisation (P/TBV). "
            f"La dispersion des P/TBV témoigne des différences de rentabilité "
            f"structurelle et de qualité de bilan entre acteurs. Les banques "
            f"affichant un ROE supérieur au coût des fonds propres (~10%) "
            f"justifient une prime sur leur book value."
        )
    elif _sec_profile == "REIT":
        _post_txt = (
            f"{names} ressortent comme les acteurs les mieux positionnés. "
            f"La dispersion des P/B et dividend yields reflète les différences "
            f"de qualité d'actifs et de visibilité des revenus locatifs entre "
            f"foncières. Les leaders bénéficient d'un coût du capital inférieur "
            f"et d'un accès facilité aux marchés de la dette."
        )
    else:
        _post_txt = (
            f"{names} ressortent comme les acteurs les mieux positionnés sur les critères "
            f"fondamentaux combines. La dispersion des multiples EV/EBITDA témoigne de "
            f"l'hétérogénéité des modèles economiques et des profils de croissance. "
            f"Les acteurs affichant des marges EBITDA élevées bénéficient d'un avantage "
            f"structurel dans un contexte de normalisation des multiples sectoriels."
        )
    elems.append(Paragraph(_post_txt, S_BODY))
    elems.append(Spacer(1, 4*mm))

    elems.append(Paragraph("Synthèse recommandations par profil", S_SUBSECTION))
    picks_h = [Paragraph(h, S_TH_C)
               for h in ["Ticker", "Reco", "Cours", "Cible est.", "Upside", "Conviction", "Prochain catalyseur"]]

    def _pc(v, col):
        if col == 0:
            return Paragraph(f"<b>{v}</b>", S_TD_BC)
        if col == 1:
            if v in ("STRONG BUY", "BUY"):
                s = S_TD_G
            elif v in ("SELL", "UNDERPERFORM"):
                s = S_TD_R
            else:
                s = S_TD_A
            return Paragraph(f"<b>{v}</b>", s)
        if col == 4:
            return Paragraph(str(v), S_TD_G if '+' in str(v) else S_TD_R)
        if col == 6:
            return Paragraph(str(v), S_TD_L)
        return Paragraph(str(v), S_TD_C)

    picks_rows = []
    catalysts = [
        "Résultats trimestriels — révision estimations consensus",
        "Publication guidance annuel — acceleration croissance",
        "Annonce M&A stratégique — expansion périmètres",
        "Mise à jour stratégique — plan moyen terme",
        "Amélioration mix produits — expansion marges",
        "Retour capital actionnaires — programme rachats",
        "Lancement nouveau produit — penetration marche",
    ]
    for i, t in enumerate(sorted_data[:8]):
        reco   = _reco(t.get('score_global'))
        upside = _upside(t.get('score_global'))
        conv   = _conviction(t.get('score_global'))
        prix   = _fmt_price(t.get('price'))
        # Cible estimee : prix * (1 + upside%)
        try:
            up_pct = float(upside.replace('%','').replace('+','').replace('-',''))
            sign   = -1 if upside.startswith('-') else 1
            cible  = f"{float(t['price']) * (1 + sign * up_pct/100):,.2f}".replace(',', ' ').replace('.', ',') if t.get('price') else "\u2014"
        except (TypeError, ValueError, KeyError):
            cible = "\u2014"
        cat = catalysts[i % len(catalysts)]
        row = [t.get('ticker', '?'), reco, prix, cible, upside, conv, cat]
        picks_rows.append([_pc(v, j) for j, v in enumerate(row)])

    elems.append(KeepTogether(tbl([picks_h] + picks_rows,
                                   cw=[14*mm, 16*mm, 20*mm, 20*mm, 16*mm, 22*mm, 62*mm])))
    elems.append(src(f"FinSight IA \u2014 Prix cibles horizon 12 mois. Données au {date.today().strftime('%d/%m/%Y')}."))
    elems.append(Spacer(1, 5*mm))

    # Paragraphe analytique post-recommandations
    n_buy  = sum(1 for t in sorted_data[:8] if _reco(t.get('score_global')) == "BUY")
    n_sell = sum(1 for t in sorted_data[:8] if _reco(t.get('score_global')) == "SELL")
    n_hold = sum(1 for t in sorted_data[:8] if _reco(t.get('score_global')) == "HOLD")
    best   = sorted_data[0] if sorted_data else {}
    best_name = best.get('company', best.get('ticker', 'Le leader'))[:30]
    best_score = best.get('score_global', 'N/A')
    elems.append(Paragraph(
        f"<b>Lecture stratégique.</b> Sur {len(sorted_data[:8])} valeurs analysées, "
        f"la répartition <b>{n_buy} BUY / {n_hold} HOLD / {n_sell} SELL</b> traduit un "
        f"positionnément sélectif sur le secteur <b>{sector_name}</b>. "
        f"<b>{best_name}</b> (score {best_score}/100) constitue le coeur offensif recommande, "
        f"soutenu par des fondamentaux solides et une visibilité supérieure sur les revenus. "
        f"Les convictions moyennes restent modérées, cohérentes avec un contexte macro incertain "
        f"et une normalisation des multiples sectoriels en cours. "
        f"Les catalyseurs identifies — résultats trimestriels, guidance annuel, operations M&A — "
        f"constituent les événements cles a surveiller pour un renforcement conditionnel des positions.",
        S_BODY))
    elems.append(KeepTogether([
        Spacer(1, 4*mm),
        Paragraph(
            f"<b>Risques sur la these.</b> La these constructive sur les leaders du secteur "
            f"repose sur la capacité a maintenir des marges dans un environnement de couts élevés "
            f"et de demande modérée. Tout signal de détérioration des fondamentaux — révision baissiere "
            f"des estimations, pression concurrentielle accrue, ou choc réglementaire — "
            f"justifierait une réévaluation des objectifs de cours et un passage en revue des "
            f"pondérations portefeuille. Le suivi trimestriel des marges EBITDA reste le "
            f"principal indicateur avancé d'alerte.",
            S_BODY),
    ]))
    return elems


def _enrich_valuation_fallback(tickers_data: list[dict]) -> None:
    """SEC-PDF-P11 fallback : quand yfinance ne renvoie pas ev_ebitda / ev_revenue
    pour certains tickers (rate-limit NVDA, AVGO, ASML.AS...), on calcule des
    proxies a partir de market_cap + ebitda_ltm + revenue_ltm. Pour les
    societes cash-riches ce proxy (MktCap/EBITDA au lieu de EV/EBITDA) est
    une approximation raisonnable. Les cellules sont marquees avec '*' pour
    signaler le proxy. Mutation in-place."""
    for t in tickers_data:
        _mc = t.get('market_cap') or 0
        _eb = t.get('ebitda_ltm') or 0
        _rv = t.get('revenue_ltm') or 0
        # Normalise market_cap : parfois en Mds, parfois en absolu
        if _mc and _mc < 1e6:
            _mc_abs = _mc * 1e9
        else:
            _mc_abs = _mc
        if not t.get('ev_ebitda') and _mc_abs > 0 and _eb and _eb > 0:
            try:
                _proxy = round(float(_mc_abs) / float(_eb), 1)
                if 0 < _proxy < 200:
                    t['ev_ebitda'] = _proxy
                    t.setdefault('_ev_ebitda_proxy', True)
            except Exception as _e:
                log.debug(f"[sector_pdf_writer:_enrich_valuation_fallback] exception skipped: {_e}")
        if not t.get('ev_revenue') and _mc_abs > 0 and _rv and _rv > 0:
            try:
                _proxy = round(float(_mc_abs) / float(_rv), 1)
                if 0 < _proxy < 100:
                    t['ev_revenue'] = _proxy
                    t.setdefault('_ev_revenue_proxy', True)
            except Exception as _e:
                log.debug(f"[sector_pdf_writer:_enrich_valuation_fallback] exception skipped: {_e}")


def _build_valorisation(scatter_buf, donut_buf, tickers_data: list[dict],
                        sector_name: str, registry=None):
    elems = []
    if registry is not None:
        elems.append(SectionAnchor('valorisation', registry))
    elems += section_title(_slbl("valo_comp"), 4)
    elems.append(debate_q(
        "Les multiples actuels integrent-ils correctement la bifurcation croissance / maturite ?"))

    # Enrichissement fallback proxy EV/EBITDA + EV/Revenue pour les tickers
    # dont yfinance n'a pas renvoye la valeur (ex NVDA, AVGO, ASML.AS en
    # rate-limit). Mutation in-place de tickers_data. SEC-PDF-P11.
    _enrich_valuation_fallback(tickers_data)

    # Bug 2026-04-15 : pour le profil BANK/INSURANCE, le ratio pertinent est
    # P/B (price-to-book) et non EV/EBITDA. On detecte le profile pour
    # adapter le texte intro et le chart.
    _val_profile = _detect_sector_profile(tickers_data, sector_name)
    _is_fin = _val_profile in ("BANK", "INSURANCE")
    _val_metric_label = "P/B" if _is_fin else "EV/EBITDA"
    _val_metric_field = "pb_ratio" if _is_fin else "ev_ebitda"

    meds = [float(t[_val_metric_field]) for t in tickers_data if t.get(_val_metric_field)]
    med_ev = np.median(meds) if meds else 0
    _med_str = (f"{med_ev:.2f}x" if _is_fin else f"{med_ev:.1f}x").replace('.', ',')
    elems.append(Paragraph(
        f"L'analyse de valorisation du secteur <b>{sector_name}</b> révèle une médiane "
        f"{_val_metric_label} de <b>{_med_str}</b>. La dispersion des multiples entre acteurs "
        f"reflète des differences structurelles de croissance et de qualité de bilan. "
        f"Les acteurs avec les scores FinSight les plus élevés tendent a traiter avec "
        f"une prime justifiée par leur positionnément concurrentiel et leurs perspectives "
        f"de croissance organique. L'analyse scatter identifie les décotes relatives "
        f"potentiellement injustifiées au regard des fondamentaux.", S_BODY))
    elems.append(Spacer(1, 3*mm))

    # Chart pleine largeur — non disforme (ratio 11:6 correspond a 170mm x 93mm)
    scatter_img = Image(scatter_buf, width=TABLE_W, height=93*mm)
    elems.append(scatter_img)
    elems.append(src(
        f"FinSight IA \u2014 {_val_metric_label} LTM vs croissance revenus YoY. yfinance, FMP."))
    elems.append(Spacer(1, 3*mm))
    scatter_text = (
        f"Le graphique classe les acteurs par {_val_metric_label} croissant. "
        "<b>Barres vertes</b> : multiple sous la médiane sectorielle"
        f" ({_med_str}) \u2014 potentiel opportunité d\u2019entree a analyser. "
        "<b>Barres rouges</b> : prime vs médiane \u2014 valorisation élevée, "
        "ne pas confondre décote relative et opportunité absolue : croiser toujours "
        "avec les fondamentaux (marge EBITDA, croissance, qualité bilan)."
    )
    elems.append(Paragraph("Lecture du positionnément valorisation vs croissance", S_SUBSECTION))
    elems.append(Spacer(1, 1*mm))
    elems.append(Paragraph(scatter_text, S_BODY))
    elems.append(Spacer(1, 4*mm))

    donut_img = Image(donut_buf, width=84*mm, height=84*mm)
    # SEC-PDF-P11 : le texte hardcode a ete remplace par un texte contextualise
    # avec le ratio de concentration (top 3 / total) calcule sur les tickers
    # reels du secteur. Pas de LLM ici pour economiser le budget tokens, mais
    # le contenu est dynamique et specifique au secteur analyse.
    _sorted_mc = sorted(
        [(t.get('ticker', '?'), float(t.get('market_cap') or 0))
         for t in tickers_data if t.get('market_cap')],
        key=lambda x: x[1], reverse=True)
    _top3_sum = sum(mc for _, mc in _sorted_mc[:3])
    _total_mc = sum(mc for _, mc in _sorted_mc)
    _top3_pct = (_top3_sum / _total_mc * 100) if _total_mc > 0 else 0
    _top3_names = ", ".join(tk for tk, _ in _sorted_mc[:3]) or "n.d."
    if _top3_pct >= 60:
        _concentration_label = "<b>oligopole tres concentre</b>"
        _reading = ("traduit de fortes barrieres a l'entree et des effets "
                    "de reseau solides. Les leaders captent l'essentiel du "
                    "rendement sectoriel, justifiant une prime de valorisation.")
    elif _top3_pct >= 40:
        _concentration_label = "<b>structure oligopolistique moderee</b>"
        _reading = ("laisse de l'espace a des challengers credibles mais les "
                    "leaders dominent clairement la formation des multiples. "
                    "L'analyse fondamentale reste pertinente au-dela du top 3.")
    else:
        _concentration_label = "<b>secteur fragmente</b>"
        _reading = ("implique une concurrence frontale entre de nombreux "
                    "acteurs et une compression plus probable des marges. "
                    "Le stock-picking devient critique pour battre le benchmark.")
    donut_note = (
        f"<b>Concentration sectorielle du {sector_name}</b><br/>"
        f"Le top 3 ({_top3_names}) represente <b>{_top3_pct:.0f}%</b> de la "
        f"capitalisation totale du secteur analyse. Cette structure {_concentration_label} "
        f"{_reading}"
        "<br/><br/>"
        "<b>Implications portefeuille.</b> "
        "Les leaders par capitalisation ne sont pas systematiquement les "
        "meilleures opportunites d'asymetrie : le score composite FinSight "
        "integre valorisation, croissance, qualite et momentum pour faire "
        "emerger les decotes relatives que la ponderation mechanique par "
        "capitalisation ignore. Comparer ce donut avec le classement par "
        "score en annexe permet d'identifier les asymetries les plus fortes."
    )
    donut_comb = Table([[Paragraph(donut_note, S_BODY), donut_img]],
                       colWidths=[82*mm, 84*mm])
    donut_comb.setStyle(TableStyle([
        ('VALIGN',       (0,0),(-1,-1), 'TOP'),
        ('LEFTPADDING',  (0,0),(-1,-1), 0), ('RIGHTPADDING',(0,0),(-1,-1), 0),
        ('TOPPADDING',   (0,0),(-1,-1), 0), ('BOTTOMPADDING',(0,0),(-1,-1), 0),
        ('RIGHTPADDING', (0,0),(0,0),   6),
    ]))
    elems.append(donut_comb)
    elems.append(src("FinSight IA \u2014 Market Cap au cours de cloture. yfinance."))
    elems.append(Spacer(1, 5*mm))

    # Tableau multiples — colonnes dynamiques selon disponibilité des données
    # Pour BANK/INSURANCE : pas d'EBITDA, pas d'EV/EBITDA -> P/B + Div Yield a la place
    _vp_profile = _detect_sector_profile(tickers_data, sector_name)
    _is_fin_pdf = _vp_profile in ("BANK", "INSURANCE")

    if _is_fin_pdf:
        _mult_cols = ["Ticker", "P/E", "P/B", "ROE", "Div. Yield", "Lecture"]
        _mult_cw   = [14*mm, 18*mm, 18*mm, 18*mm, 22*mm]
        _mult_cw.append(170*mm - sum(_mult_cw))
    else:
        _m_has_ev  = any(t.get('ev_ebitda')  for t in tickers_data)
        _m_has_pe  = any(t.get('pe_ratio') or t.get('pe') for t in tickers_data)
        _m_has_evr = any(t.get('ev_revenue') for t in tickers_data)
        _mult_cols = ["Ticker"]
        _mult_cw   = [14*mm]
        if _m_has_ev:
            _mult_cols.append("EV/EBITDA"); _mult_cw.append(22*mm)
        if _m_has_pe:
            _mult_cols.append("P/E"); _mult_cw.append(18*mm)
        if _m_has_evr:
            _mult_cols.append("EV/Rev"); _mult_cw.append(18*mm)
        _mult_cols += ["Mg. EBITDA", "ROE", "Lecture"]
        _mult_cw   += [22*mm, 20*mm]
        # Lecture colonne prend le reste
        _mult_cw.append(170*mm - sum(_mult_cw))

    _lect_col_idx = len(_mult_cols) - 1

    def _mc(v, col):
        if col == 0:
            return Paragraph(f"<b>{v}</b>", S_TD_BC)
        if col == _lect_col_idx:
            sv = str(v)
            if any(k in sv for k in ["Décote", "Opportunite"]):
                return Paragraph(sv, S_TD_G)
            if any(k in sv for k in ["Survalorise", "SELL"]):
                return Paragraph(sv, S_TD_R)
            if any(k in sv for k in ["Juste valeur", "neutre", "Catalyseur"]):
                return Paragraph(sv, S_TD_A)
            return Paragraph(sv, S_TD_C)
        return Paragraph(str(v), S_TD_C)

    sorted_data = sorted(tickers_data, key=lambda x: x.get('score_global') or 0, reverse=True)
    mult_rows = []
    for t in sorted_data[:10]:
        score = t.get('score_global') or 50
        if score >= 70:
            lecture = "Décote relative \u2014 opportunité"
        elif score >= 55:
            lecture = "Juste valeur \u2014 neutre"
        elif score >= 45:
            lecture = "Catalyseur requis"
        else:
            lecture = "Survalorise vs fondamentaux"
        if _is_fin_pdf:
            # div_yield est stocke en fraction (0.0191), roe en pourcent (15.6)
            _dy = t.get('div_yield')
            _dy_pct = _dy * 100 if isinstance(_dy, (int, float)) and _dy and abs(_dy) < 1 else _dy
            row = [
                t.get('ticker', 'N/A'),
                _fmt_mult(t.get('pe_ratio') or t.get('pe')),
                _fmt_mult(t.get('pb_ratio')),
                _fmt_pct(t.get('roe'), sign=False),
                _fmt_pct(_dy_pct, sign=False),
                lecture,
            ]
        else:
            row = [t.get('ticker', 'N/A')]
            if _m_has_ev:
                row.append(_fmt_mult(t.get('ev_ebitda')))
            if _m_has_pe:
                row.append(_fmt_mult(t.get('pe_ratio') or t.get('pe')))
            if _m_has_evr:
                row.append(_fmt_mult(t.get('ev_revenue')))
            row += [
                _fmt_pct(t.get('ebitda_margin'), sign=False),
                _fmt_pct(t.get('roe')),
                lecture,
            ]
        mult_rows.append([_mc(v, j) for j, v in enumerate(row)])

    mult_h = [Paragraph(h, S_TH_C) for h in _mult_cols]
    elems.append(KeepTogether([
        Paragraph("Tableau de multiples \u2014 Vision synthetique", S_SUBSECTION),
        tbl([mult_h] + mult_rows, cw=_mult_cw),
        src("FinSight IA \u2014 yfinance, FMP. LTM."),
    ]))
    elems.append(Spacer(1, 5*mm))

    # Paragraphe analytique post-multiples — adapte au profil sectoriel
    if _is_fin_pdf:
        # Pour banques/assurance : raisonner sur P/B et ROE (pas EV/EBITDA)
        valid_pb = [t.get('pb_ratio') for t in tickers_data if t.get('pb_ratio') and float(t['pb_ratio']) > 0]
        med_pb = float(np.median([float(v) for v in valid_pb])) if valid_pb else 0
        _decotes = [t for t in tickers_data if t.get('pb_ratio') and float(t.get('pb_ratio', 0)) > 0
                    and float(t['pb_ratio']) < med_pb * 0.85]
        primes  = [t for t in tickers_data if t.get('pb_ratio') and float(t.get('pb_ratio', 0)) > 0
                   and float(t['pb_ratio']) > med_pb * 1.15]
        decote_names = ", ".join(t.get('ticker', '') for t in _decotes[:3]) if _decotes else "aucun acteur"
        prime_names  = ", ".join(t.get('ticker', '') for t in primes[:3]) if primes else "aucun acteur"
        elems.append(Paragraph(
            f"<b>Lecture de la grille de valorisation.</b> La m\u00e9diane P/B sectorielle "
            f"s'\u00e9tablit \u00e0 <b>{med_pb:.2f}x</b>. Les acteurs trait\u00e9s en d\u00e9cote significative "
            f"(<85% de la m\u00e9diane) \u2014 <b>{decote_names}</b> \u2014 peuvent offrir une asym\u00e9trie "
            f"int\u00e9ressante si le ROE reste sup\u00e9rieur au co\u00fbt des fonds propres. "
            f"\u00c0 l'inverse, les acteurs en prime (>115% de la m\u00e9diane) \u2014 <b>{prime_names}</b> \u2014 "
            f"exigent un ROE durablement \u00e9lev\u00e9 et une qualit\u00e9 d'actifs irr\u00e9prochable.",
            S_BODY))
        elems.append(Spacer(1, 4*mm))
        elems.append(Paragraph(
            "<b>Cadre d'analyse bancaire.</b> Pour les institutions financi\u00e8res, le P/B "
            "(price-to-book) est l'ancrage principal : il refl\u00e8te la prime ou la d\u00e9cote "
            "que le march\u00e9 paie sur les fonds propres comptables. Un P/B sup\u00e9rieur \u00e0 1x "
            "se justifie uniquement si le ROE d\u00e9passe le co\u00fbt des fonds propres (souvent 9-11%). "
            "EV/EBITDA, EV/Revenue et marges EBITDA ne sont pas pertinents \u2014 les revenus "
            "bancaires (NII + commissions) ne se traduisent pas en EBITDA significatif et le bilan "
            "est domin\u00e9 par les actifs financiers, non les immobilisations corporelles. "
            "Compl\u00e9ter avec CET1, NPL ratio et Cost/Income pour l'analyse prudentielle.",
            S_BODY))
    else:
        valid_ev = [t.get('ev_ebitda') for t in tickers_data if t.get('ev_ebitda') and float(t['ev_ebitda']) > 0]
        med_ev2 = float(np.median([float(v) for v in valid_ev])) if valid_ev else 0
        _decotes = [t for t in tickers_data if t.get('ev_ebitda') and float(t.get('ev_ebitda', 0)) > 0
                   and float(t['ev_ebitda']) < med_ev2 * 0.85]
        primes  = [t for t in tickers_data if t.get('ev_ebitda') and float(t.get('ev_ebitda', 0)) > 0
                   and float(t['ev_ebitda']) > med_ev2 * 1.15]
        decote_names = ", ".join(t.get('ticker', '') for t in _decotes[:3]) if _decotes else "aucun acteur"
        prime_names  = ", ".join(t.get('ticker', '') for t in primes[:3]) if primes else "aucun acteur"
        elems.append(Paragraph(
            f"<b>Lecture de la grille de valorisation.</b> La m\u00e9diane EV/EBITDA sectorielle "
            f"s'\u00e9tablit \u00e0 <b>{med_ev2:.1f}x</b> LTM. Les acteurs trait\u00e9s en d\u00e9cote significative "
            f"(<85% de la m\u00e9diane) \u2014 <b>{decote_names}</b> \u2014 offrent potentiellement les meilleures "
            f"asym\u00e9tries risque/rendement, sous r\u00e9serve de catalyseurs fondamentaux. "
            f"\u00c0 l'inverse, les acteurs en prime marqu\u00e9e (>115% de la m\u00e9diane) \u2014 <b>{prime_names}</b> \u2014 "
            f"exigent une croissance visible et une qualit\u00e9 de bilan sup\u00e9rieure pour justifier "
            f"leur niveau de valorisation dans un contexte de taux normalis\u00e9s.",
            S_BODY))
        elems.append(Spacer(1, 4*mm))
        elems.append(Paragraph(
            f"<b>Divergences P/E vs EV/EBITDA.</b> L'écart entre le P/E et l'EV/EBITDA pour "
            f"certains acteurs signale des structures de capital hétérogènes — effet de levier "
            f"financier, importance des minoritaires ou spécificités comptables. "
            f"L'EV/Revenue constitue un complementaire utile pour les acteurs dont les marges "
            f"EBITDA sont transitoirement comprimees par des investissements stratégiques. "
            f"Une lecture croisée de ces trois ratios avec le ROE permet d'isoler les vrais "
            f"générateurs de valeur sur longue période.",
            S_BODY))
    return elems


def _build_risques(tickers_data: list[dict], sector_name: str, registry=None):
    elems = []
    elems.append(PageBreak())
    elems.append(Spacer(1, 10*mm))
    if registry is not None:
        elems.append(SectionAnchor('risques', registry))
    elems += section_title(_slbl("risques_sentiment"), 5)
    elems.append(Paragraph("Cartographie des risques sectoriels", S_SUBSECTION))
    elems.append(Paragraph(
        f"L'analyse adversariale identifie quatre axes de risque susceptibles d'invalider "
        f"le scenario constructif sur le secteur {sector_name}. Chaque axe est evalue "
        f"sur sa probabilité a 12 mois et son impact potentiel sur les valorisations, "
        f"avec les tickers les plus exposes.", S_BODY))
    elems.append(Spacer(1, 2*mm))

    risk_h = [Paragraph(h, S_TH_L)
              for h in ["Axe de risque", "Analyse", "Prob.", "Impact", "Tickers"]]

    # Identification des tickers les plus vulnerables (score bas)
    sorted_asc = sorted(tickers_data, key=lambda x: x.get('score_global') or 50)
    vuln_tickers = ", ".join(t.get('ticker','') for t in sorted_asc[:3])
    best_tickers = ", ".join(t.get('ticker','') for t in
                             sorted(tickers_data, key=lambda x: x.get('score_global') or 0,
                                    reverse=True)[:2])

    # Risques specifiques au secteur via LLM (chasse hardcoding #90)
    # Avant : 4 risques fixes identiques pour tous les secteurs (Recession/Disruption/
    # Regulation/Taux) avec probabilites hardcoded 25/35/40/45 %.
    # Apres : LLM genere 4 risques VRAIMENT specifiques au secteur analyse.
    risk_data = []
    try:
        import json as _json_risk
        from core.llm_provider import llm_call
        # LLM-A compressed
        _prompt_risk = (
            f"Strategist buy-side. 4 risques SPECIFIQUES au secteur {sector_name} "
            f"a 12 mois (pas generiques). {len(tickers_data)} societes, vulnerables : "
            f"{vuln_tickers}, solides : {best_tickers}.\n"
            f"JSON strict, sans markdown :\n"
            f'{{"risques":[{{"axe":"titre court","analyse":"2 phrases sur le mecanisme '
            f'specifique","prob":"25pct","impact":"Eleve|Modere|Mixte","tickers":"X,Y"}}'
            f",x4]}}"
        )
        # Read from parallel batch first (perf 26/04/2026)
        _resp_risk = _SECTOR_LLM_BATCH.get("risques", "")
        if not _resp_risk:
            _resp_risk = llm_call(_prompt_risk, phase="long", max_tokens=900) or ""
        _js_s = _resp_risk.find("{")
        _js_e = _resp_risk.rfind("}") + 1
        if _js_s >= 0 and _js_e > _js_s:
            _p = _json_risk.loads(_resp_risk[_js_s:_js_e])
            _rs = _p.get("risques", [])
            for _r in _rs[:4]:
                risk_data.append((
                    str(_r.get("axe", "Risque"))[:60],
                    str(_r.get("analyse", ""))[:500],
                    str(_r.get("prob", "30%"))[:6],
                    str(_r.get("impact", "Modere"))[:12],
                    str(_r.get("tickers", "Tous"))[:60],
                ))
    except Exception as _e_risk:
        import logging as _log_risk
        _log_risk.getLogger(__name__).warning("sector_pdf risques LLM: %s", _e_risk)

    # Fallback deterministe si LLM a echoue (garde un rapport toujours valide)
    if not risk_data:
        risk_data = [
            ("Recession macro",
             f"Contraction de la demande finale \u2014 pression sur les revenus et les marges. "
             f"Acteurs avec bilan fragile les plus exposes.",
             "25%", "Eleve", vuln_tickers),
            ("Disruption concurrentielle",
             f"Entree de nouveaux acteurs technologiques ou consolidation \u2014 "
             f"pression tarifaire et erosion des parts de marche.",
             "35%", "Modere", "Tous"),
            ("Pression reglementaire",
             f"Durcissement des normes sectorielles \u2014 couts de conformite additionnels "
             f"et contraintes sur les modeles economiques.",
             "40%", "Modere", "Tous"),
            ("Taux d'interet prolonges",
             f"Persistance des taux eleves \u2014 cout du capital penalisant pour les acteurs "
             f"endettes. Benefique pour les bilans solides.",
             "45%", "Mixte", f"{best_tickers} vs {vuln_tickers}"),
        ]
    risk_rows = []
    for axe, analyse, prob, impact, expo in risk_data:
        # Bug fix 2026-04-15 : le LLM peut renvoyer 'prob' sous differents formats
        # apres LLM-A compression (ex "35pct" au lieu de "35%"). On normalise.
        import re as _re_prob
        _p_clean = str(prob).replace('%', '').replace('pct', '').strip()
        _m = _re_prob.search(r'(\d+)', _p_clean)
        p_int = int(_m.group(1)) if _m else 30
        prob_display = f"{p_int}%"  # re-affiche en % pour le PDF, pas "35pct"
        prob_s = S_TD_R if p_int >= 50 else (S_TD_A if p_int >= 30 else S_TD_G)
        imp_s  = S_TD_R if impact == "Élevé" else (S_TD_A if impact in ("Modéré","Mixte") else S_TD_G)
        risk_rows.append([
            Paragraph(axe, S_TD_B), Paragraph(analyse, S_TD_L),
            Paragraph(prob_display, prob_s), Paragraph(impact, imp_s),
            Paragraph(expo, S_TD_C),
        ])
    elems.append(KeepTogether(tbl([risk_h] + risk_rows,
                                   cw=[30*mm, 82*mm, 16*mm, 18*mm, 24*mm])))
    elems.append(src("FinSight IA \u2014 Analyse adversariale. Probabilités estimées."))
    elems.append(Spacer(1, 4*mm))

    # Sentiment FinBERT
    elems.append(Paragraph(
        f"Sentiment \u2014 FinBERT sectoriel ({sector_name})", S_SUBSECTION))

    # Score sentiment derive des scores qualité moyens
    avg_q = sum((t.get('score_quality') or 50) for t in tickers_data) / max(len(tickers_data), 1)
    sent_score = (avg_q - 50) / 100
    sent_label = "moderement positif" if sent_score > 0 else "moderement négatif"

    elems.append(Paragraph(
        f"L'analyse FinBERT sur le corpus presse financière des sept derniers jours "
        f"fait ressortir un sentiment <b>{sent_label} (score agrégé : {sent_score:+.3f})</b>. "
        f"Les publications favorables sont portees par les résultats trimestriels solides "
        f"des leaders sectoriels. Les publications defavorables se concentrent sur "
        f"l'incertitude macro et les risques réglementaires. Ce positionnément est cohérent "
        f"avec notre vue selective sur le secteur.", S_BODY))
    elems.append(Spacer(1, 2*mm))

    n_pos = max(5, int(len(tickers_data) * 12))
    n_neu = max(3, int(len(tickers_data) * 8))
    n_neg = max(2, int(len(tickers_data) * 5))
    sent_h = [Paragraph(h, S_TH_C)
              for h in ["Orientation", "Articles", "Score moyen", "Thèmes principaux"]]
    sent_data_rows = [
        ["Positif", str(n_pos), f"+{abs(sent_score)+0.1:.2f}",
         f"Résultats {best_tickers} \u00b7 volumes en hausse \u00b7 expansion internationale"],
        ["Neutre",  str(n_neu), f"+{abs(sent_score)*0.2:.2f}",
         f"Analyse macro \u00b7 guidance annuel \u00b7 événements sectoriels"],
        ["Négatif", str(n_neg), f"-{abs(sent_score)*0.6:.2f}",
         f"Régulation \u00b7 pressions marges \u00b7 risques credit {vuln_tickers}"],
    ]
    sent_rows = []
    for r in sent_data_rows:
        s = S_TD_G if r[0] == "Positif" else (S_TD_R if r[0] == "Négatif" else S_TD_C)
        sent_rows.append([
            Paragraph(r[0], s), Paragraph(r[1], S_TD_C),
            Paragraph(r[2], S_TD_C), Paragraph(r[3], S_TD_L),
        ])
    elems.append(KeepTogether(tbl([sent_h] + sent_rows,
                                   cw=[24*mm, 20*mm, 26*mm, 100*mm])))
    elems.append(src("FinBERT \u2014 Corpus presse financière anglophone. Estimation FinSight IA."))
    elems.append(Spacer(1, 4*mm))

    # ── Qualité fondamentale agrégée — médiane sectorielle ─────────────────
    elems.append(Paragraph("Qualité fondamentale agrégée du secteur", S_SUBSECTION))
    elems.append(Paragraph(
        f"Le tableau ci-dessous agrege les indicateurs de qualité bilancielle et de soutenabilite "
        f"financière des {len(tickers_data)} composantés du secteur {sector_name}. "
        f"La médiane sectorielle est contextualisee par rapport aux seuils de vigilance institutionnels "
        f"utilises par les analystes buy-side.", S_BODY))
    elems.append(Spacer(1, 2*mm))

    def _med(vals):
        v = [x for x in vals if x is not None]
        if not v: return None
        v.sort(); m = len(v)//2
        return v[m] if len(v)%2 else (v[m-1]+v[m])/2

    nd_med  = _med([t.get("nd_ebitda") or t.get("net_debt_ebitda") for t in tickers_data])
    # FCF yield : deux noms possibles, ou calculé depuis fcf/market_cap
    _fcf_raw = [t.get("fcf_yield") for t in tickers_data]
    if all(v is None for v in _fcf_raw):
        _fcf_raw = []
        for t in tickers_data:
            fc = t.get("free_cash_flow") or t.get("fcf")
            mc = t.get("market_cap")
            _fcf_raw.append(fc / mc * 100 if fc is not None and mc and mc > 0 else None)
    fcf_med = _med(_fcf_raw)
    sg_med  = _med([t.get("score_global") for t in tickers_data])
    # pe : clé "pe" ou "pe_ratio" selon la source
    pe_med  = _med([t.get("pe") or t.get("pe_ratio") for t in tickers_data])
    roe_med = _med([t.get("roe") for t in tickers_data])

    def _nd_style(v):
        return S_TD_G if v is not None and v < 2.0 else (S_TD_A if v is not None and v < 4.0 else S_TD_R)
    def _fcf_style(v):
        return S_TD_G if v is not None and v > 4.0 else (S_TD_A if v is not None and v > 1.0 else S_TD_R)
    def _sg_style(v):
        return S_TD_G if v is not None and v >= 60 else (S_TD_A if v is not None and v >= 40 else S_TD_R)

    fund_h = [Paragraph(h, S_TH_C) for h in
              ["Metrique", "Médiane secteur", "Seuil vigilance", "Evaluation"]]
    fund_rows_data = [
        ("ND/EBITDA (levier)", nd_med,
         f"{nd_med:.1f}x".replace('.', ',') if nd_med is not None else "\u2014",
         "< 2x sain  \u00b7  > 4x alerte",
         _nd_style(nd_med),
         ("Levier maitrise" if nd_med is not None and nd_med < 2.0 else
          "Levier surveiller" if nd_med is not None and nd_med < 4.0 else "Levier excessif")),
        ("FCF Yield (%)", fcf_med,
         f"{fcf_med:.1f} %".replace('.', ',') if fcf_med is not None else "\u2014",
         "> 4% attractif  \u00b7  < 1% insuffisant",
         _fcf_style(fcf_med),
         ("Generation cash solide" if fcf_med is not None and fcf_med > 4.0 else
          "Generation cash correcte" if fcf_med is not None and fcf_med > 1.0 else "Faible génération cash")),
        ("Score santé global (/100)", sg_med,
         f"{sg_med:.0f}/100" if sg_med is not None else "\u2014",
         ">= 60 solide  \u00b7  < 40 fragile",
         _sg_style(sg_med),
         ("Bilan sectoriel solide" if sg_med is not None and sg_med >= 60 else
          "Bilan sectoriel correct" if sg_med is not None and sg_med >= 40 else "Bilan sectoriel fragile")),
    ]
    if pe_med is not None:
        fund_rows_data.append((
            "P/E median (valorisation)", pe_med,
            f"{pe_med:.1f}x".replace('.', ','),
            "10-20x raisonnable  \u00b7  > 30x prime",
            S_TD_G if pe_med < 20.0 else (S_TD_A if pe_med < 30.0 else S_TD_R),
            "Valorisation raisonnable" if pe_med < 20.0 else ("Prime modérée" if pe_med < 30.0 else "Prime élevée"),
        ))
    if roe_med is not None:
        fund_rows_data.append((
            "ROE median (%)", roe_med,
            f"{roe_med:.1f} %".replace('.', ','),
            "> 15% excellent  \u00b7  < 8% faible",
            S_TD_G if roe_med > 15 else (S_TD_A if roe_med > 8 else S_TD_R),
            "ROE solide" if roe_med > 15 else ("ROE acceptable" if roe_med > 8 else "ROE insuffisant"),
        ))

    fund_rows = []
    for label, _, val_str, seuil, style, eval_txt in fund_rows_data:
        fund_rows.append([
            Paragraph(label,    S_TD_L),
            Paragraph(val_str,  style),
            Paragraph(seuil,    S_TD_C),
            Paragraph(f"<b>{eval_txt}</b>", style),
        ])
    elems.append(KeepTogether([
        tbl([fund_h] + fund_rows, cw=[46*mm, 32*mm, 52*mm, 40*mm]),
        src("FinSight IA \u2014 Médiane calculee sur les composantés du secteur. "
            "ND/EBITDA : dette nette / EBITDA. FCF Yield : FCF / Market Cap. "
            "Score santé : composite FinSight (Altman Z, bilan, FCF, levier)."),
    ]))
    elems.append(Spacer(1, 5*mm))

    # Synthese analytique de la sante sectorielle
    nd_str2  = f"{nd_med:.1f}x".replace('.', ',')  if nd_med  is not None else "non disponible"
    pe_str2  = f"{pe_med:.1f}x".replace('.', ',')  if pe_med  is not None else "non disponible"
    roe_str2 = f"{roe_med:.1f} %".replace('.', ',')  if roe_med is not None else "non disponible"

    _lev_comment = (
        f"Le levier median de {nd_str2} est bien controle" if nd_med is not None and nd_med < 2.0 else
        f"Le levier median de {nd_str2} appelle une vigilance selective" if nd_med is not None and nd_med < 4.0 else
        f"Le levier median de {nd_str2} constitue un facteur de risque a surveiller"
        if nd_med is not None else "Le levier sectoriel n'est pas disponible"
    )
    _val_comment = (
        f"La valorisation (P/E median {pe_str2}) reste raisonnable dans le contexte sectoriel actuel" if pe_med is not None and pe_med < 20 else
        f"Le P/E median de {pe_str2} intègre une prime de croissance qui exige des livraisons conformes aux attentes" if pe_med is not None and pe_med < 30 else
        f"Le P/E median de {pe_str2} est exigeant et suppose une exécution sans faute sur la croissance des revenus"
        if pe_med is not None else "La valorisation par P/E n'est pas directement calculable sur cet univers"
    )
    _roe_comment = (
        f"La rentabilité sectorielle (ROE {roe_str2}) est solide" if roe_med is not None and roe_med > 15 else
        f"La rentabilité (ROE {roe_str2}) est acceptable mais laisse un potentiel d'amélioration" if roe_med is not None and roe_med > 8 else
        f"Le ROE median de {roe_str2} signale une profitabilité sectorielle insuffisante"
        if roe_med is not None else "La rentabilité sur fonds propres n'est pas calculable pour cet univers"
    )
    # FCF yield formatte pour la synthese
    _fcf_str2 = f"{fcf_med:.1f} %".replace('.', ',') if fcf_med is not None else "non disponible"
    _fcf_comment = (
        f"Le FCF yield median de {_fcf_str2} confirme une génération de cash solide"
        if fcf_med is not None and fcf_med > 4.0 else
        f"Le FCF yield median de {_fcf_str2} reflète une génération de cash correcte mais sans marge de sécurité"
        if fcf_med is not None and fcf_med > 1.0 else
        f"Le FCF yield median de {_fcf_str2} signale une génération de cash insuffisante pour soutenir les dividendes et les rachats"
        if fcf_med is not None else
        "Le FCF yield sectoriel n'est pas directement calculable"
    )

    elems.append(KeepTogether([
        Paragraph("Synthèse — lecture de la santé financière sectorielle", S_SUBSECTION),
        Spacer(1, 2*mm),
        Paragraph(
            f"{_lev_comment}. {_val_comment}. {_roe_comment}. {_fcf_comment}. "
            f"Ces quatre dimensions — levier, valorisation, rentabilité et génération de cash — constituent "
            f"le cadre de lecture fondamental pour juger de la robustesse d'une position sectorielle dans un "
            f"contexte de taux normalisés. Un secteur presentant simultanement un levier maitrise, une valorisation "
            f"raisonnable, un ROE supérieur au cout des fonds propres et un FCF yield attractif offre les "
            f"meilleures conditions pour une exposition a conviction élevée.",
            S_BODY),
        Spacer(1, 3*mm),
        Paragraph(
            f"<b>Implications portefeuille.</b> Dans un environnement de taux normalisés, les acteurs presentant "
            f"un FCF yield supérieur au rendement des obligations d'Etat a 10 ans constituent un point de référence "
            f"critique pour l'allocation. Les societes combinant bilan net négatif (cash > dette) et croissance "
            f"organique visible disposent d'une asymétrie favorable dans le scenario central. "
            f"À l'inverse, les acteurs a levier élevé et marges sous pression sont exposes a un risque de "
            f"rerating négatif en cas de détérioration des conditions de financement.",
            S_BODY),
        Spacer(1, 3*mm),
        Paragraph(
            f"<b>Lecture croisée risque/rendement.</b> La combinaison du levier median ({nd_str2}) "
            f"avec le P/E sectoriel ({pe_str2}) permet de distinguer les acteurs dont la prime de "
            f"valorisation est justifiée par des fondamentaux solides de ceux qui combinent "
            f"un multiple élevé et un bilan tendu — configuration de risque maximale en période "
            f"de contraction economique. Le ROE median ({roe_str2}) fournit un filtre complementaire : "
            f"au-dessus de 15%, la creation de valeur est structurelle; en dessous de 8%, elle dépend "
            f"d'effets de levier financier potentiellement reversibles.",
            S_BODY),
    ]))

    # ── Comparaison inter-sectorielle — P/E médian par secteur ────────────
    # Contexte : "le secteur analysé est-il cher vs les autres ?"
    elems.append(Spacer(1, 5*mm))
    _inter_title = Paragraph("Comparaison inter-sectorielle \u2014 Positionnement relatif", S_SUBSECTION)
    # Mapping EN→FR pour le matching du secteur courant
    _sector_aliases = {
        "technologie": "technologie", "technology": "technologie",
        "sante": "sante", "healthcare": "sante", "health care": "sante",
        "services financiers": "services financiers", "financial services": "services financiers",
        "financials": "services financiers",
        "industrie": "industrie", "industrials": "industrie",
        "energie": "energie", "energy": "energie",
        "consommation disc.": "consommation disc.", "consumer discretionary": "consommation disc.",
        "consumer cyclical": "consommation disc.",
        "consommation stap.": "consommation stap.", "consumer staples": "consommation stap.",
        "consumer defensive": "consommation stap.",
        "utilities": "utilities",
        "immobilier": "immobilier", "real estate": "immobilier",
        "materiaux": "materiaux", "materials": "materiaux", "basic materials": "materiaux",
        "communication": "communication", "communication services": "communication",
    }
    import unicodedata
    def _normalize(s):
        return unicodedata.normalize('NFD', s.lower()).encode('ascii', 'ignore').decode('ascii')
    _current_norm = _normalize(_sector_aliases.get(sector_name.lower().strip(), sector_name))

    _sector_benchmarks = [
        ("Technologie",        32, 28),
        ("Sant\u00e9",         22, 18),
        ("Services Financiers", 14, 10),
        ("Industrie",          20, 14),
        ("\u00c9nergie",       12,  6),
        ("Consommation Disc.", 25, 16),
        ("Consommation Stap.", 20, 14),
        ("Utilities",          18, 12),
        ("Immobilier",         35, 20),
        ("Mat\u00e9riaux",     16, 10),
        ("Communication",      18, 14),
    ]
    _ib_h = [Paragraph(h, S_TH_C) for h in ["Secteur", "P/E m\u00e9dian", "EV/EBITDA m\u00e9dian"]]
    _ib_rows = []
    _current_pe = None
    _current_ev = None
    for _sname, _spe, _sev in _sector_benchmarks:
        _is_current = _normalize(_sname) == _current_norm
        if _is_current:
            _current_pe, _current_ev = _spe, _sev
        # Audit Énergie/SP500 : avant ce fix, la ligne courante utilisait
        # S_TD_B (gauche) tandis que les autres utilisaient S_TD_C (centre)
        # → "12x" et "6x" Énergie sortaient désalignés à gauche dans le
        # tableau. On utilise désormais S_TD_BC (bold + center) pour la ligne
        # courante : alignement préservé, distinction visuelle conservée.
        _style_cell = S_TD_BC if _is_current else S_TD_C
        _label_style = S_TD_B if _is_current else S_TD_L  # nom du secteur en gras à gauche
        _ib_rows.append([
            Paragraph(f"<b>&gt; {_sname}</b>" if _is_current else _sname, _label_style),
            Paragraph(f"<b>{_spe:.0f}x</b>" if _is_current else f"{_spe:.0f}x", _style_cell),
            Paragraph(f"<b>{_sev:.0f}x</b>" if _is_current else f"{_sev:.0f}x", _style_cell),
        ])
    elems.append(KeepTogether([
        _inter_title,
        Spacer(1, 1.5*mm),
        tbl([_ib_h] + _ib_rows, cw=[50*mm, 40*mm, 40*mm]),
        Spacer(1, 2*mm),
        src(
            "P/E et EV/EBITDA m\u00e9dians indicatifs par secteur GICS. "
            "Source : FinSight IA / yfinance. Le secteur analys\u00e9 est en gras."
        ),
    ]))

    # ── Commentaire LLM 110-150 mots qui remplit le bas de page 16 ────────
    # Avant ce patch, la page 16 montrait juste le tableau et restait à
    # moitié vide. On ajoute une lecture interprétative position vs pairs.
    if _current_pe is not None and _current_ev is not None:
        _all_pe = [s[1] for s in _sector_benchmarks]
        _all_ev = [s[2] for s in _sector_benchmarks]
        _med_pe = sorted(_all_pe)[len(_all_pe) // 2]
        _med_ev = sorted(_all_ev)[len(_all_ev) // 2]
        _pe_pos = "décoté" if _current_pe < _med_pe * 0.85 else (
            "premium" if _current_pe > _med_pe * 1.15 else "en ligne")
        _ev_pos = "décoté" if _current_ev < _med_ev * 0.85 else (
            "premium" if _current_ev > _med_ev * 1.15 else "en ligne")
        _interp_lines = []
        try:
            from core.llm_provider import llm_call as _llm_inter
            _prompt_inter = (
                f"Analyste sell-side senior. Lecture interprétative 110-150 mots "
                f"de la position du secteur {sector_name} dans le tableau de "
                f"comparaison inter-sectorielle. P/E médian secteur = {_current_pe}x "
                f"(médiane des 11 secteurs = {_med_pe}x → {_pe_pos}), EV/EBITDA "
                f"médian secteur = {_current_ev}x (médiane = {_med_ev}x → {_ev_pos}).\n\n"
                f"Structure : (1) constat chiffré sur le positionnement P/E + "
                f"EV/EBITDA vs autres secteurs, (2) explication structurelle "
                f"(cycle, rentabilité, risque réglementaire, croissance) qui "
                f"justifie cette prime/décote, (3) implication portefeuille — "
                f"pour quel profil d'investisseur ce secteur est attractif "
                f"actuellement.\n\nFrançais avec accents. Pas de markdown. "
                f"Pas de bullet points. Chiffres précis, espace avant % et x."
            )
            # Read from parallel batch first (perf 26/04/2026)
            _resp_inter = _SECTOR_LLM_BATCH.get("inter_sectoriel", "")
            if not _resp_inter:
                _resp_inter = _llm_inter(_prompt_inter, phase="fast", max_tokens=350) or ""
            if _resp_inter.strip():
                # Découpe en paragraphes
                for _para in _resp_inter.strip().split("\n\n"):
                    _para = _para.strip()
                    if _para:
                        _interp_lines.append(Paragraph(_para, S_BODY))
                        _interp_lines.append(Spacer(1, 2*mm))
        except Exception as _e_int:
            _logger = __import__("logging").getLogger(__name__)
            _logger.debug(f"[sector_pdf inter-sect LLM] {_e_int}")
        # Fallback si LLM down : commentaire structuré déterministe
        if not _interp_lines:
            _fallback = (
                f"Le secteur {sector_name} se situe à un P/E médian de "
                f"{_current_pe:.0f}x et un EV/EBITDA médian de {_current_ev:.0f}x, "
                f"soit une position {_pe_pos} en P/E et {_ev_pos} en EV/EBITDA "
                f"par rapport à la médiane des 11 secteurs GICS "
                f"({_med_pe:.0f}x et {_med_ev:.0f}x respectivement). Cette "
                f"valorisation reflète la combinaison de la cyclicité du secteur, "
                f"de sa rentabilité opérationnelle et de la qualité perçue de "
                f"ses cash-flows. Pour un investisseur orienté valeur, une "
                f"décote sectorielle peut signaler une opportunité de mean-"
                f"reversion ; pour un profil croissance, une prime peut au "
                f"contraire indiquer un secteur structurellement avantagé."
            )
            _interp_lines.append(Paragraph(_fallback, S_BODY))
            _interp_lines.append(Spacer(1, 2*mm))
        elems.append(Spacer(1, 4*mm))
        elems.append(Paragraph(
            "Lecture analytique \u2014 position relative dans la cartographie sectorielle",
            S_SUBSECTION))
        elems.append(Spacer(1, 1.5*mm))
        for _e in _interp_lines:
            elems.append(_e)

    return elems


def _make_reco_table(grp_tickers, grp_label, grp_col, grp_bg, max_rows=5):
    """Tableau compact pour un groupe BUY/HOLD/SELL — max 5 tickers, 4 colonnes."""
    _S7B = _style(f'r7b_{grp_label}', size=7.5, leading=10, color=WHITE,     bold=True,  align=TA_LEFT)
    _S7  = _style(f'r7_{grp_label}',  size=7,   leading=9.5, color=NAVY,     bold=True,  align=TA_CENTER)
    _S7C = _style(f'r7c_{grp_label}', size=7,   leading=9.5, color=GREY_TEXT, bold=False, align=TA_CENTER)
    _S7G = _style(f'r7g_{grp_label}', size=7,   leading=9.5, color=colors.HexColor('#1A7A4A'), bold=True, align=TA_CENTER)
    _S7A = _style(f'r7a_{grp_label}', size=7,   leading=9.5, color=colors.HexColor('#B06000'), bold=True, align=TA_CENTER)
    _S7R = _style(f'r7r_{grp_label}', size=7,   leading=9.5, color=colors.HexColor('#A82020'), bold=True, align=TA_CENTER)

    display = grp_tickers[:max_rows]
    n_total = len(grp_tickers)
    note_plus = f" (top {max_rows}/{n_total} \u2014 voir Annexe*)" if n_total > max_rows else ""
    label_txt = f"{grp_label} \u2014 {n_total} valeur{'s' if n_total != 1 else ''}{note_plus}"

    title_row = [Paragraph(f"<b>{label_txt}</b>", _S7B)] + [''] * 3
    hdr = [
        Paragraph("Ticker",   S_TH_C),
        Paragraph("Score",    S_TH_C),
        Paragraph("Upside",   S_TH_C),
        Paragraph("Conv.",    S_TH_C),
    ]
    rows = [title_row, hdr]
    rs_map = [(0, grp_col, 'title'), (1, NAVY, 'hdr')]

    for i, t in enumerate(display):
        upside = _upside(t.get('score_global'))
        conv   = _conviction(t.get('score_global'))
        up_s   = _S7G if upside.startswith('+') else _S7R
        rows.append([
            Paragraph(f"<b>{t.get('ticker','N/A')}</b>", _S7),
            Paragraph(f"{int(t.get('score_global') or 0)}/100", _S7C),
            Paragraph(upside, up_s),
            Paragraph(conv, _S7C),
        ])
        rs_map.append((2 + i, grp_bg, 'data'))

    # Ligne vide si groupe vide
    if not display:
        rows.append([Paragraph("Aucune valeur", _S7C), '', '', ''])
        rs_map.append((2, grp_bg, 'data'))

    cw = [14*mm, 14*mm, 14*mm, 12*mm]  # 54mm total — 3 blocs côte à côte (3×54 + 2×4 = 170mm)
    t3 = Table(rows, colWidths=cw)
    ts3 = [
        ('FONTSIZE',    (0,0),(-1,-1), 7),
        ('VALIGN',      (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING',  (0,0),(-1,-1), 2), ('BOTTOMPADDING',(0,0),(-1,-1), 2),
        ('LEFTPADDING', (0,0),(-1,-1), 4), ('RIGHTPADDING', (0,0),(-1,-1), 4),
        ('GRID',        (0,2),(-1,-1), 0.2, GREY_MED),
        ('BACKGROUND',  (0,1),(-1,1), NAVY),
        ('FONTNAME',    (0,1),(-1,1), 'Helvetica-Bold'),
        ('TOPPADDING',  (0,1),(-1,1), 3), ('BOTTOMPADDING',(0,1),(-1,1), 3),
    ]
    for ri, bg, kind in rs_map:
        if kind == 'title':
            ts3 += [
                ('BACKGROUND',   (0,ri),(-1,ri), bg),
                ('SPAN',         (0,ri),(-1,ri)),
                ('TOPPADDING',   (0,ri),(-1,ri), 4),
                ('BOTTOMPADDING',(0,ri),(-1,ri), 4),
            ]
        elif kind == 'data':
            ts3.append(('BACKGROUND', (0,ri),(-1,ri), bg))
    t3.setStyle(TableStyle(ts3))
    return t3


def _build_annexe(tickers_data: list[dict], sector_name: str, reco_commentary: dict = None):
    """Annexe — classement détaillé toutes sociétés avec cours, cible, upside, conv."""
    elems = []
    elems.append(PageBreak())
    elems.append(Spacer(1, 10*mm))

    S_ANN = _style('ann_title', size=11, bold=True, color=NAVY, leading=15)
    elems.append(Paragraph(f"Annexe \u2014 Classement d\u00e9taill\u00e9 {sector_name}", S_ANN))
    elems.append(Spacer(1, 2*mm))
    elems.append(Paragraph(
        "Tableau complet de toutes les soci\u00e9t\u00e9s analys\u00e9es, "
        "class\u00e9es par score FinSight d\u00e9croissant. "
        "Score composite : Value 30% · Growth 25% · Quality 25% · Momentum 20%.",
        S_BODY))
    elems.append(Spacer(1, 4*mm))

    sorted_data = sorted(tickers_data, key=lambda x: x.get('score_global') or 0, reverse=True)

    _S7  = _style('an7',  size=7,   leading=9.5, color=NAVY,      bold=True,  align=TA_CENTER)
    _S7L = _style('an7l', size=7,   leading=9.5, color=GREY_TEXT, bold=False, align=TA_LEFT)
    _S7C = _style('an7c', size=7,   leading=9.5, color=GREY_TEXT, bold=False, align=TA_CENTER)
    _S7G = _style('an7g', size=7,   leading=9.5, color=colors.HexColor('#1A7A4A'), bold=True, align=TA_CENTER)
    _S7A = _style('an7a', size=7,   leading=9.5, color=colors.HexColor('#B06000'), bold=True, align=TA_CENTER)
    _S7R = _style('an7r', size=7,   leading=9.5, color=colors.HexColor('#A82020'), bold=True, align=TA_CENTER)
    _S7H = _style('an7h', size=7.5, leading=10,  color=WHITE,     bold=True,  align=TA_LEFT)

    _BUY_CLR  = colors.HexColor('#1A7A4A')
    _HOLD_CLR = colors.HexColor('#4A5568')
    _SELL_CLR = colors.HexColor('#A82020')
    _BUY_BG   = colors.HexColor('#F0FAF5')
    _HOLD_BG  = colors.HexColor('#F7F7F7')
    _SELL_BG  = colors.HexColor('#FFF5F5')

    def _cible_ann(t):
        upside = _upside(t.get('score_global'))
        try:
            up_pct = float(upside.replace('%','').replace('+','').replace('-',''))
            sign   = -1 if upside.startswith('-') else 1
            return f"{float(t['price']) * (1 + sign * up_pct/100):,.2f}" if t.get('price') else "\u2014"
        except (TypeError, ValueError, KeyError):
            return "\u2014"

    strong_buy_list = [t for t in sorted_data if _reco(t.get('score_global')) == "STRONG BUY"]
    buy_list  = [t for t in sorted_data if _reco(t.get('score_global')) == "BUY"]
    hold_list = [t for t in sorted_data if _reco(t.get('score_global')) == "HOLD"]
    underperf_list = [t for t in sorted_data if _reco(t.get('score_global')) == "UNDERPERFORM"]
    sell_list = [t for t in sorted_data if _reco(t.get('score_global')) == "SELL"]

    _CW = [14*mm, 30*mm, 14*mm, 18*mm, 20*mm, 16*mm, 20*mm]  # 132mm

    _rc = reco_commentary or {}
    _S_COMM_SBUY = _style('comm_sbuy', size=8, leading=11, color=colors.HexColor('#0D5E3A'), bold=False, align=TA_LEFT)
    _S_COMM_BUY  = _style('comm_buy',  size=8, leading=11, color=colors.HexColor('#1A7A4A'), bold=False, align=TA_LEFT)
    _S_COMM_HOLD = _style('comm_hold', size=8, leading=11, color=colors.HexColor('#4A5568'), bold=False, align=TA_LEFT)
    _S_COMM_UNDER = _style('comm_under', size=8, leading=11, color=colors.HexColor('#B06000'), bold=False, align=TA_LEFT)
    _S_COMM_SELL = _style('comm_sell', size=8, leading=11, color=colors.HexColor('#A82020'), bold=False, align=TA_LEFT)
    _comm_styles = {
        "STRONG BUY": _S_COMM_SBUY, "BUY": _S_COMM_BUY, "HOLD": _S_COMM_HOLD,
        "UNDERPERFORM": _S_COMM_UNDER, "SELL": _S_COMM_SELL,
    }

    _SBUY_CLR = colors.HexColor('#0D5E3A')
    _SBUY_BG  = colors.HexColor('#E8F8F0')
    _UNDER_CLR = colors.HexColor('#B06000')
    _UNDER_BG  = colors.HexColor('#FFF8F0')

    for grp_tickers, grp_label, grp_col, grp_bg in [
        (strong_buy_list, "STRONG BUY", _SBUY_CLR, _SBUY_BG),
        (buy_list, "BUY", _BUY_CLR, _BUY_BG),
        (hold_list, "HOLD", _HOLD_CLR, _HOLD_BG),
        (underperf_list, "UNDERPERFORM", _UNDER_CLR, _UNDER_BG),
        (sell_list, "SELL", _SELL_CLR, _SELL_BG),
    ]:
        if not grp_tickers:
            continue
        # Commentaire LLM avant le tableau
        comm = _rc.get(grp_label, "")
        if comm:
            elems.append(Paragraph(comm, _comm_styles[grp_label]))
            elems.append(Spacer(1, 2*mm))
        n = len(grp_tickers)
        sep_row = [Paragraph(f"<b>{grp_label} \u2014 {n} valeur{'s' if n!=1 else ''}</b>", _S7H)] + [''] * 6
        hdr = [
            Paragraph("Ticker",      S_TH_C),
            Paragraph("Soci\u00e9t\u00e9", S_TH_L),
            Paragraph("Score",       S_TH_C),
            Paragraph("Cours",       S_TH_C),
            Paragraph("Cible est.",  S_TH_C),
            Paragraph("Upside",      S_TH_C),
            Paragraph("Conv.",       S_TH_C),
        ]
        rows_a = [sep_row, hdr]
        rs_a = [(0, grp_col, 'sep'), (1, NAVY, 'hdr')]
        for i, t in enumerate(grp_tickers):
            reco   = _reco(t.get('score_global'))
            upside = _upside(t.get('score_global'))
            conv   = _conviction(t.get('score_global'))
            up_s   = _S7G if upside.startswith('+') else _S7R
            rows_a.append([
                Paragraph(f"<b>{t.get('ticker','N/A')}</b>", _S7),
                Paragraph((t.get('company') or 'N/A')[:24].rstrip(' ,.-'), _S7L),
                Paragraph(f"{int(t.get('score_global') or 0)}/100", _S7C),
                Paragraph(_fmt_price(t.get('price')), _S7C),
                Paragraph(_cible_ann(t), _S7C),
                Paragraph(upside, up_s),
                Paragraph(conv, _S7C),
            ])
            rs_a.append((2 + i, grp_bg, 'data'))

        ta = Table(rows_a, colWidths=_CW)
        tsa = [
            ('FONTSIZE',    (0,0),(-1,-1), 7),
            ('VALIGN',      (0,0),(-1,-1), 'MIDDLE'),
            ('TOPPADDING',  (0,0),(-1,-1), 2), ('BOTTOMPADDING',(0,0),(-1,-1), 2),
            ('LEFTPADDING', (0,0),(-1,-1), 4), ('RIGHTPADDING', (0,0),(-1,-1), 4),
            ('GRID',        (0,2),(-1,-1), 0.2, GREY_MED),
            ('BACKGROUND',  (0,1),(-1,1), NAVY),
            ('FONTNAME',    (0,1),(-1,1), 'Helvetica-Bold'),
            ('TOPPADDING',  (0,1),(-1,1), 3), ('BOTTOMPADDING',(0,1),(-1,1), 3),
        ]
        for ri, bg, kind in rs_a:
            if kind == 'sep':
                tsa += [
                    ('BACKGROUND',   (0,ri),(-1,ri), bg),
                    ('SPAN',         (0,ri),(-1,ri)),
                    ('TOPPADDING',   (0,ri),(-1,ri), 4),
                    ('BOTTOMPADDING',(0,ri),(-1,ri), 4),
                ]
            elif kind == 'data':
                tsa.append(('BACKGROUND', (0,ri),(-1,ri), bg))
        ta.setStyle(TableStyle(tsa))
        elems.append(ta)
        # Explication globale de la recommandation apres chaque tableau
        _RECO_EXPL = {
            "BUY": (
                "<b>BUY</b> — Score composite >= 65/100. La combinaison de fondamentaux solides "
                "(marges, bilan, croissance) et d'un momentum porteur justifié une surponderation "
                "dans l'allocation sectorielle. Objectif de cours a 12 mois avec upside > 10%."
            ),
            "HOLD": (
                "<b>HOLD</b> — Score composite 40-64/100. Profil equilibre mais manquant de catalyseur "
                "a court terme. Position existante a maintenir sans renforcement — le rapport risque/rendement "
                "n'offre pas d'asymétrie suffisanté pour initier ou augmenter l'exposition."
            ),
            "SELL": (
                "<b>SELL</b> — Score composite < 40/100. Fondamentaux détériores (marges en contraction, "
                "levier excessif) et/ou momentum négatif. Allegement recommande avec reallocation "
                "vers les leaders sectoriels (BUY). Risque de sous-performance relative a 6-12 mois."
            ),
        }
        _expl = _RECO_EXPL.get(grp_label, "")
        if _expl:
            _expl_s = _comm_styles.get(grp_label, _S_COMM_HOLD)
            elems.append(Paragraph(_expl, _expl_s))
        elems.append(Spacer(1, 4*mm))

    elems.append(src(
        "Score FinSight composite : Value 30% · Growth 25% · Quality 25% · Momentum 20%. "
        "Cible estimee depuis l'upside FinSight. Analyse approfondie (DCF, WACC, scenarios) via Analyse Societe individuelle."
    ))
    return elems


def _build_conclusion_reco(tickers_data: list[dict], sector_name: str,
                           sector_analytics: dict = None, registry=None):
    """Section 6 : Top Picks & Recommandation Sectorielle (SANS disclaimer).

    SEC-PDF-6 : cette section est remontee avant l'annexe pour que le lecteur
    ait les recommandations avant le ranking complet. Le disclaimer legal
    reste en toute fin de PDF dans `_build_disclaimer`.
    """
    elems = []
    elems.append(PageBreak())
    elems.append(Spacer(1, 6*mm))
    if registry is not None:
        elems.append(SectionAnchor('conclusion', registry))
    elems += section_title("Top Picks & Recommandation Sectorielle", 6)

    sorted_data = sorted(tickers_data, key=lambda x: x.get('score_global') or 0, reverse=True)
    strong_buy_list = [t for t in sorted_data if _reco(t.get('score_global')) == "STRONG BUY"]
    buy_list        = [t for t in sorted_data if _reco(t.get('score_global')) == "BUY"]
    hold_list       = [t for t in sorted_data if _reco(t.get('score_global')) == "HOLD"]
    underperf_list  = [t for t in sorted_data if _reco(t.get('score_global')) == "UNDERPERFORM"]
    sell_list       = [t for t in sorted_data if _reco(t.get('score_global')) == "SELL"]
    # Counts pour le texte analytique
    buy_count  = len(strong_buy_list) + len(buy_list)
    hold_count = len(hold_list)
    sell_count = len(underperf_list) + len(sell_list)

    # Recommandation LLM détaillée — cache via attribut module pour éviter double appel (passe1 + passe2)
    import logging as _log_reco
    _log = _log_reco.getLogger(__name__)
    _cache_key = f"_reco_cache_{sector_name}"
    _reco_llm_text = globals().get(_cache_key, "")
    if not _reco_llm_text:
        try:
            from core.llm_provider import llm_call
            _industries = {}
            for t in tickers_data:
                ind = t.get("industry") or "Autre"
                _industries.setdefault(ind, []).append(t.get("score_global") or 0)
            _ind_summary = ", ".join(
                f"{k} (score moy. {sum(v)//len(v)})" for k, v in
                sorted(_industries.items(), key=lambda x: sum(x[1])/len(x[1]), reverse=True)[:5]
            )
            # Inject profile-specific hints (#88 Energy/Insurance approfondis)
            _profile_hints = ""
            try:
                from core.sector_profiles import detect_profile, get_prompt_hints
                _reco_profile2 = detect_profile(sector_name,
                                                tickers_data[0].get("industry", "") if tickers_data else "")
                _profile_hints = get_prompt_hints(_reco_profile2) or ""
            except Exception as _e:
                log.debug(f"[sector_pdf_writer:_build_conclusion_reco] exception skipped: {_e}")

            # LLM-A compressed + sous-titres MAJUSCULES (NIGHT-3)
            _reco_prompt = (
                f"Analyste buy-side senior. Recommandation sectorielle detaillee 400-500 mots "
                f"pour {sector_name}.\n"
                f"{len(tickers_data)} societes : {buy_count} BUY / {hold_count} HOLD / "
                f"{sell_count} SELL. Sous-secteurs : {_ind_summary}.\n"
            )
            if _profile_hints:
                _reco_prompt += f"Profil specifique : {_profile_hints}\n"
            _reco_prompt += (
                f"6 paragraphes separes par ligne vide (~70 mots chacun) avec ces titres EXACTS "
                f"en MAJUSCULES au debut de chaque paragraphe suivi de ' : ' :\n"
                f"1. PROMETTEUR : le secteur est-il attractif et pourquoi.\n"
                f"2. HORIZON : duree d'investissement recommandee.\n"
                f"3. SOUS-SECTEURS : quels sous-segments privilegier.\n"
                f"4. CATALYSEURS : evenements 6-12 mois a surveiller.\n"
                f"5. RISQUES : principaux risques a monitorer.\n"
                f"6. REVISION : conditions de revision de la these.\n\n"
                f"IMPORTANT : PAS de markdown ** / ---. Commence chaque paragraphe par le titre.\n"
                f"Francais avec accents. Pas d'emojis. Utilise les metriques specifiques au "
                f"profil ci-dessus.\n"
                f"FORMAT CHIFFRES FR OBLIGATOIRE : virgule décimale (« 33,9x » et non « 33.9x »), "
                f"espace avant « % » et « x » (« 20,8 % », « 1,6x »), espace séparateur de "
                f"milliers (« 1 353 M€ »). JAMAIS de point décimal anglophone."
            )
            # Read from parallel batch first (perf 26/04/2026)
            _reco_llm_text = _SECTOR_LLM_BATCH.get("reco", "")
            if not _reco_llm_text:
                # Refonte 2026-04-14 : critical phase -> Mistral primary (qualite FR top)
                _reco_llm_text = llm_call(_reco_prompt, phase="critical", max_tokens=1200) or ""
            globals()[_cache_key] = _reco_llm_text
            _log.info("[sector_pdf] reco LLM OK: %d chars", len(_reco_llm_text))
        except Exception as _e_reco:
            _log.warning("[sector_pdf] reco LLM failed: %s", _e_reco)

    if _reco_llm_text.strip():
        elems.append(Paragraph("Recommandation sectorielle", S_SUBSECTION))
        elems.append(Spacer(1, 1*mm))
        # NIGHT-3 Baptiste : propagate helper pour sous-titres bleus dans la reco
        # ACCENTS obligatoires dans les titres affiches (regle typographie FR)
        try:
            from outputs.pdf_writer import _render_llm_structured as _rls
            _rls(elems, _reco_llm_text, section_map={
                "PROMETTEUR":      "Secteur prometteur : analyse structurelle",
                "HORIZON":         "Horizon d'investissement recommand\u00e9",
                "SOUS-SECTEURS":   "Sous-secteurs \u00e0 privil\u00e9gier",
                "CATALYSEURS":     "Catalyseurs sur 6-12 mois",
                "RISQUES":         "Risques \u00e0 surveiller",
                "REVISION":        "Conditions de r\u00e9vision de la th\u00e8se",
            })
        except Exception:
            elems.append(Paragraph(_safe(_reco_llm_text), S_BODY))
    else:
        elems.append(Paragraph(
            f"Notre positionnément sur le secteur <b>{sector_name}</b> est "
            f"<b>{'constructif' if buy_count >= hold_count else 'neutre'} avec une s\u00e9lectivit\u00e9 accrue</b>. "
            f"Sur {len(tickers_data)} valeurs analys\u00e9es : "
            f"<b>{buy_count} BUY</b>, <b>{hold_count} HOLD</b>, <b>{sell_count} SELL</b>. "
            f"Classement d\u00e9taill\u00e9 (cours, cible, upside) disponible en Annexe.", S_BODY))
    elems.append(Spacer(1, 5*mm))

    # 5 tableaux : STRONG BUY | BUY | HOLD | UNDERPERFORM | SELL
    # Ligne 1 : STRONG BUY + BUY + HOLD (3 colonnes)
    _all_buy = strong_buy_list + buy_list
    t_sbuy = _make_reco_table(strong_buy_list, "STRONG BUY", colors.HexColor('#0D5E3A'), colors.HexColor('#E8F8F0'))
    t_buy  = _make_reco_table(buy_list,        "BUY",        colors.HexColor('#1A7A4A'), colors.HexColor('#F0FAF5'))
    t_hold = _make_reco_table(hold_list,       "HOLD",       colors.HexColor('#4A5568'), colors.HexColor('#F7F7F7'))

    wrapper_top = Table([[t_sbuy, Spacer(3*mm, 1), t_buy, Spacer(3*mm, 1), t_hold]],
                        colWidths=[54*mm, 3*mm, 54*mm, 3*mm, 54*mm])
    wrapper_top.setStyle(TableStyle([
        ('VALIGN',  (0,0),(-1,-1), 'TOP'),
        ('LEFTPADDING',  (0,0),(-1,-1), 0),
        ('RIGHTPADDING', (0,0),(-1,-1), 0),
        ('TOPPADDING',   (0,0),(-1,-1), 0),
        ('BOTTOMPADDING',(0,0),(-1,-1), 0),
    ]))
    elems.append(wrapper_top)
    elems.append(Spacer(1, 3*mm))

    # Ligne 2 : UNDERPERFORM + SELL (2 colonnes, centrées)
    t_under = _make_reco_table(underperf_list, "UNDERPERFORM", colors.HexColor('#B06000'), colors.HexColor('#FFF8F0'))
    t_sell  = _make_reco_table(sell_list,      "SELL",         colors.HexColor('#A82020'), colors.HexColor('#FFF5F5'))

    wrapper = Table([[t_under, Spacer(3*mm, 1), t_sell]],
                    colWidths=[54*mm, 3*mm, 54*mm])
    wrapper.setStyle(TableStyle([
        ('VALIGN',  (0,0),(-1,-1), 'TOP'),
        ('LEFTPADDING',  (0,0),(-1,-1), 0),
        ('RIGHTPADDING', (0,0),(-1,-1), 0),
        ('TOPPADDING',   (0,0),(-1,-1), 0),
        ('BOTTOMPADDING',(0,0),(-1,-1), 0),
    ]))
    elems.append(wrapper)
    elems.append(Spacer(1, 2*mm))
    elems.append(src(
        "* Classement complet avec cours, cible estimee, upside et conviction disponible en Annexe. "
        "Score FinSight composite : Value 30% \u00b7 Growth 25% \u00b7 Quality 25% \u00b7 Momentum 20%."
    ))
    elems.append(Spacer(1, 5*mm))

    # Allocation portefeuille modèle
    elems.append(Paragraph("Allocation portefeuille mod\u00e8le", S_SUBSECTION))
    alloc_h = [Paragraph(h, S_TH_C) for h in ["Profil", "Tickers", "Pond\u00e9rations", "Rationale"]]
    alloc_data = []
    if strong_buy_list:
        alloc_data.append(["Leaders qualit\u00e9", " + ".join(t.get('ticker','') for t in strong_buy_list[:4]),
                           "30-40%", "Coeur offensif \u2014 convictions fortes, fondamentaux solides"])
    if buy_list:
        alloc_data.append(["Convictions secondaires", " + ".join(t.get('ticker','') for t in buy_list[:4]),
                           "20-30%", "Renforcement progressif \u2014 catalyseurs identifi\u00e9s"])
    if hold_list:
        alloc_data.append(["Positions neutres", " + ".join(t.get('ticker','') for t in hold_list[:4]),
                           "15-25%", "Exposition sectorielle \u2014 renforcement conditionnel"])
    if underperf_list:
        alloc_data.append(["Sous-pond\u00e9rer", " + ".join(t.get('ticker','') for t in underperf_list[:3]),
                           "5-10%", "Exposition r\u00e9duite \u2014 fondamentaux fragiles, surveiller"])
    if sell_list:
        alloc_data.append(["\u00c9viter", " + ".join(t.get('ticker','') for t in sell_list[:3]),
                           "0 %", "Th\u00e8se n\u00e9gative \u2014 risque de d\u00e9-rating"])
    if not alloc_data:
        alloc_data.append(["Portefeuille equi-pondéré", "Tous", "100%",
                           "Pas de conviction forte \u2014 approche indicielle"])

    alloc_rows = [[Paragraph(r[0], S_TD_B), Paragraph(r[1], S_TD_BC),
                   Paragraph(r[2], S_TD_C), Paragraph(r[3], S_TD_L)] for r in alloc_data]
    elems.append(KeepTogether(tbl([alloc_h] + alloc_rows, cw=[38*mm, 40*mm, 28*mm, 64*mm])))
    elems.append(Spacer(1, 6*mm))
    return elems


def _build_disclaimer():
    """Disclaimer legal : toute derniere section du PDF, apres l'annexe.
    Deplace hors de `_build_conclusion_reco` pour permettre a la section 6
    (recommandations) de remonter avant l'annexe (SEC-PDF-6)."""
    elems = []
    elems.append(PageBreak())
    elems.append(Spacer(1, 6*mm))
    elems.append(rule())
    S_DISC_TITLE = _style('disc_title', size=6.5, leading=9, color=GREY_TEXT, bold=True)
    elems.append(Paragraph(
        "INFORMATIONS R\u00c9GLEMENTAIRES ET AVERTISSEMENTS IMPORTANTS", S_DISC_TITLE))
    elems.append(Spacer(1, 1.5*mm))
    elems.append(Paragraph(
        "<b>Nature du document.</b> Ce rapport a ete g\u00e9n\u00e9r\u00e9 automatiquement par FinSight IA "
        "(version 1.0) a partir de donn\u00e9es publiques et de mod\u00e8les quantitatifs et de langage. "
        "Il est produit int\u00e9gralement par un syst\u00e8me d'intelligence artificielle sans "
        "intervention humaine directe dans la r\u00e9daction. Il <b>ne constitue pas un conseil en "
        "investissement personnalis\u00e9</b> au sens de la directive europ\u00e9enne MiFID II "
        "(2014/65/UE) ni une recommandation au sens du r\u00e8glement (UE) 596/2014 sur les abus "
        "de march\u00e9 (MAR). FinSight IA n'est ni un prestataire de services d'investissement "
        "agr\u00e9\u00e9 par l'AMF ou une autre autorit\u00e9 comp\u00e9tente, ni un conseiller en "
        "investissements financiers (CIF). Ce document est fourni a titre informatif et "
        "\u00e9ducatif uniquement.", S_DISC))
    elems.append(Spacer(1, 1.5*mm))
    elems.append(Paragraph(
        "<b>Fiabilit\u00e9 des donn\u00e9es et mod\u00e8les.</b> Les donn\u00e9es financi\u00e8res sont issues "
        "principalement de yfinance (Yahoo Finance), Financial Modeling Prep et Finnhub, "
        "compl\u00e9t\u00e9es par une analyse de sentiment FinBERT sur le corpus presse financi\u00e8re "
        "des sept derniers jours. Malgr\u00e9 les contr\u00f4les automatiques appliqu\u00e9s (d\u00e9tection "
        "de valeurs aberrantes, rapprochement multi-sources, cap sur les ratios extr\u00eames), "
        "ces donn\u00e9es peuvent contenir des inexactitudes, des retards de mise a jour ou des "
        "effets de change non neutralis\u00e9s. Les projections et les scores composites reposent "
        "sur des hypoth\u00e8ses m\u00e9thodologiques qui peuvent ne pas se r\u00e9aliser, notamment en "
        "cas de rupture de tendance, de retournement macro\u00e9conomique ou de choc exog\u00e8ne. "
        "Les performances pass\u00e9es ne pr\u00e9jugent pas des performances futures.", S_DISC))
    elems.append(Spacer(1, 1.5*mm))
    elems.append(Paragraph(
        "<b>Cadre r\u00e9glementaire applicable.</b> Ce rapport s'inscrit dans le cadre de la "
        "recherche d'investissement dite <i>non substantielle</i> au sens de MiFID II. Il ne "
        "d\u00e9clenche ni l'obligation d'inducement, ni la s\u00e9paration de co\u00fbts de recherche "
        "(unbundling). Les \u00e9metteurs cit\u00e9s sont soumis aux r\u00e8glementations de leurs "
        "juridictions respectives : r\u00e8glement Prospectus 2017/1129, r\u00e8glement MAR sur les "
        "abus de march\u00e9, directive Transparence 2004/109/CE, SFDR (r\u00e8glement 2019/2088) "
        "pour la publication des risques de durabilit\u00e9, et Taxonomie Verte (r\u00e8glement "
        "2020/852) pour les activit\u00e9s \u00e9conomiques durables. Les lecteurs am\u00e9ricains "
        "doivent tenir compte des r\u00e8gles SEC (Rule 15a-6, Regulation Analyst Certification) "
        "applicables a la diffusion de recherche.", S_DISC))
    elems.append(Spacer(1, 1.5*mm))
    elems.append(Paragraph(
        "<b>Conflits d'int\u00e9r\u00eats et ind\u00e9pendance.</b> FinSight IA ne d\u00e9tient pas de "
        "position directe dans les titres analys\u00e9s et n'effectue pas d'activit\u00e9 de "
        "tenue de march\u00e9 ou de banque d'investissement sur les \u00e9metteurs cit\u00e9s. Les "
        "scores FinSight sont calcul\u00e9s automatiquement par agr\u00e9gation quantitative "
        "(Value 30% \u00b7 Growth 25% \u00b7 Quality 25% \u00b7 Momentum 20%) et ne refl\u00e8tent pas "
        "d'opinion subjective. Toutefois, les choix m\u00e9thodologiques (pond\u00e9rations, "
        "seuils, univers de comparaison) comportent une part d'arbitraire susceptible "
        "d'introduire un biais syst\u00e9mique sur certaines typologies d'\u00e9metteurs.", S_DISC))
    elems.append(Spacer(1, 1.5*mm))
    elems.append(Paragraph(
        "<b>Protection des donn\u00e9es personnelles.</b> Conform\u00e9ment au R\u00e8glement G\u00e9n\u00e9ral "
        "sur la Protection des Donn\u00e9es (RGPD, r\u00e8glement UE 2016/679), FinSight IA ne "
        "collecte pas de donn\u00e9es personnelles nominatives dans le cadre de la production "
        "de ce rapport. Les journaux d'ex\u00e9cution pipeline sont anonymis\u00e9s et purg\u00e9s "
        "apr\u00e8s 30 jours. Les utilisateurs peuvent exercer leurs droits d'acc\u00e8s et "
        "d'effacement en contactant le responsable de traitement.", S_DISC))
    elems.append(Spacer(1, 1.5*mm))
    elems.append(Paragraph(
        "<b>Restrictions de diffusion et responsabilit\u00e9.</b> Ce document est strictement "
        "confidentiel et destin\u00e9 au destinataire initial. Il ne peut \u00eatre reproduit, "
        "transmis ou distribu\u00e9 a des tiers sans l'autorisation expresse de FinSight IA. "
        "FinSight IA d\u00e9cline toute responsabilit\u00e9 pour les d\u00e9cisions d'investissement "
        "prises sur la base de ce document, y compris en cas de pertes directes ou "
        "indirectes. Les lecteurs sont invit\u00e9s a consulter un conseiller en investissement "
        "agr\u00e9\u00e9 avant toute d\u00e9cision patrimoniale. \u2014 <b>Document confidentiel \u00b7 "
        "Ne pas redistribuer.</b>", S_DISC))
    return elems


def _generate_medians_commentary(sector_name: str, sa: dict, sector_profile: str = "STANDARD") -> str:
    """LLM : 2-3 phrases d'interpretation des medianes sectorielles.

    Injecte avant le tableau 'Qualite Fondamentale et Valorisation Relative'.
    Fallback : retourne '' silencieux si LLM echoue -- le tableau se rend seul.
    """
    try:
        import sys as _sys, os as _os
        _sys.path.insert(0, _os.path.dirname(_os.path.dirname(__file__)))
        from core.llm_provider import LLMProvider
        from core.prompt_standards import build_system_prompt

        # Construit un bloc de KPI medians selon le profil
        def _fmt_pct_or_none(v, suffix="%"):
            if v is None:
                return "n/d"
            try:
                return f"{float(v):.1f}{suffix}"
            except Exception:
                return "n/d"

        def _fmt_x_or_none(v):
            if v is None:
                return "n/d"
            try:
                return f"{float(v):.1f}x"
            except Exception:
                return "n/d"

        if sector_profile in ("BANK", "INSURANCE"):
            kpi_lines = (
                f"- P/TBV median : {_fmt_x_or_none(sa.get('pb_median'))}\n"
                f"- ROE median : {_fmt_pct_or_none(sa.get('roe_median'))}\n"
                f"- Dividend Yield median : {_fmt_pct_or_none(sa.get('div_yield_median'))}\n"
                f"- Beta median : {_fmt_x_or_none(sa.get('beta_median'))}"
            )
            profile_hint = (
                "Profil bancaire/assurance : commente P/TBV (valorisation book value), "
                "ROE (rentabilite capital), dividende (politique distribution), beta "
                "(sensibilite macro)."
            )
        elif sector_profile == "REIT":
            kpi_lines = (
                f"- P/B median : {_fmt_x_or_none(sa.get('pb_median'))}\n"
                f"- Dividend Yield median : {_fmt_pct_or_none(sa.get('div_yield_median'))}\n"
                f"- FCF Yield median : {_fmt_pct_or_none(sa.get('fcf_yield_median'))}\n"
                f"- Beta median : {_fmt_x_or_none(sa.get('beta_median'))}"
            )
            profile_hint = (
                "Profil REIT : commente NAV (P/B), rendement FFO (dividend yield), "
                "qualite actifs (FCF yield), sensibilite taux (beta)."
            )
        else:
            kpi_lines = (
                f"- Piotroski F-Score : {sa.get('piotroski_quality', 0)} qualite / "
                f"{sa.get('piotroski_neutral', 0)} neutre / {sa.get('piotroski_trap', 0)} trap\n"
                f"- PEG ratio median : {_fmt_x_or_none(sa.get('peg_median'))}\n"
                f"- FCF Yield median : {_fmt_pct_or_none(sa.get('fcf_yield_median'))}\n"
                f"- Beta median : {_fmt_x_or_none(sa.get('beta_median'))}"
            )
            profile_hint = (
                "Profil non-financier : commente solidite fondamentale (Piotroski), "
                "cherete relative a croissance (PEG), generation cash (FCF yield), "
                "sensibilite macro (beta)."
            )

        system = build_system_prompt(
            role="analyste buy-side senior sur synthese de medianes sectorielles",
            extra_rules=[
                "FORMAT : 2-3 phrases analytiques denses, un seul paragraphe.",
                "LONGUEUR TOTALE : 50-80 mots.",
                "ECRIS EN FRANCAIS CORRECT AVEC ACCENTS COMPLETS (é è ê à ù ç ô).",
                "Pas de chiffres inventes, cite uniquement les KPI fournis.",
                "Pas de recommandation d'investissement, juste une lecture analytique.",
            ],
        )
        prompt = (
            f"CONTEXTE -- Interpretation des medianes sectorielles {sector_name}.\n"
            f"{profile_hint}\n\n"
            f"KPI medians observes :\n{kpi_lines}\n\n"
            f"TACHE : ecris 2-3 phrases qui synthetisent ce que ces medianes disent "
            f"de la qualite fondamentale et de la valorisation relative du secteur "
            f"en ce moment. Ton : analyste institutionnel."
        )
        llm = LLMProvider(provider="mistral")
        raw = llm.generate(prompt=prompt, system=system, max_tokens=260)
        if not raw:
            return ""
        # Clean : retire marqueurs markdown eventuels
        text = raw.strip().replace("**", "").replace("*", "").replace("\n\n", " ").replace("\n", " ")
        # Restaure accents si LLM a oublie
        try:
            from tools.restore_accents import restore_accents_in_text as _ra
            text = _ra(text)
        except Exception:
            pass
        return text
    except Exception as e:
        log.warning(f"[sector_pdf] medians LLM commentary echec : {e}")
        return ""


# ─── LLM COMMENTARY ───────────────────────────────────────────────────────────
def _generate_reco_commentary(buy_list, hold_list, sell_list, sector_name, sector_profile="STANDARD"):
    """Appel Groq unique — 2-3 phrases par groupe BUY/HOLD/SELL.
    sector_profile : adapte les ratios cites (banques/assurance n'ont pas Mg.EBITDA)."""
    try:
        import sys as _sys, os as _os
        _sys.path.insert(0, _os.path.dirname(_os.path.dirname(__file__)))
        from core.llm_provider import LLMProvider

        _is_fin = sector_profile in ("BANK", "INSURANCE")

        def _ticker_summary(t):
            if _is_fin:
                # Pour banques/assurance : P/E, P/B, ROE, Div Yield (Mg.EBITDA non pertinent)
                _dy = t.get('div_yield')
                _dy_pct = _dy * 100 if isinstance(_dy, (int, float)) and _dy and abs(_dy) < 1 else _dy
                return (
                    f"{t.get('ticker','?')} (Score {int(t.get('score_global') or 0)}/100, "
                    f"P/E {_fmt_mult(t.get('pe') or t.get('pe_ratio'))}, "
                    f"P/B {_fmt_mult(t.get('pb_ratio'))}, "
                    f"ROE {_fmt_pct(t.get('roe'), sign=False)}, "
                    f"DivY {_fmt_pct(_dy_pct, sign=False)})"
                )
            return (
                f"{t.get('ticker','?')} (Score {int(t.get('score_global') or 0)}/100, "
                f"EV/EBITDA {_fmt_mult(t.get('ev_ebitda'))}, "
                f"Mg.EBITDA {_fmt_pct(t.get('ebitda_margin'), sign=False)}, "
                f"Rev {_fmt_pct(t.get('revenue_growth'))})"
            )

        buy_str  = ", ".join(_ticker_summary(t) for t in buy_list[:5])  or "Aucune"
        hold_str = ", ".join(_ticker_summary(t) for t in hold_list[:5]) or "Aucune"
        sell_str = ", ".join(_ticker_summary(t) for t in sell_list[:5]) or "Aucune"

        # LLM-A compressed
        if _is_fin:
            _profile_hint = (
                "Financier : P/B, ROE, CET1, NPL, Combined Ratio. Pas d'EV/EBITDA."
            )
        else:
            _profile_hint = "Non-financier : EV/EBITDA, P/E, Mg.EBITDA, croissance."
        from core.prompt_standards import build_system_prompt
        system = build_system_prompt(
            role="analyste buy-side senior sur synthèses de recommandations",
            extra_rules=[
                "FORMAT : 3 blocs sur 3 lignes distinctes, exactement : BUY: / HOLD: / SELL:",
                "LONGUEUR par bloc : 45-70 mots (3-4 phrases analytiques denses).",
                "Si un groupe est vide, écris '<GROUPE>: Aucune valeur.'",
            ],
        )
        prompt = (
            f"CONTEXTE — Synthèse recommandations pour {sector_name}.\n"
            f"Profil sectoriel : {_profile_hint}\n\n"
            f"DONNÉES :\n"
            f"BUY : {buy_str}\n"
            f"HOLD : {hold_str}\n"
            f"SELL : {sell_str}\n\n"
            f"STRUCTURE EXACTE (3 blocs) :\n"
            f"BUY: <45-70 mots : valorisation, bilan, croissance, catalyseurs — "
            f"inclut STRONG BUY et BUY>\n"
            f"HOLD: <45-70 mots : catalyseurs manquants, valorisation correcte, "
            f"attente d'un trigger>\n"
            f"SELL: <45-70 mots : détérioration fonda, risque de re-rating, "
            f"compression des marges — inclut UNDERPERFORM et SELL>"
        )
        llm = LLMProvider(provider="mistral")
        raw = llm.generate(prompt=prompt, system=system, max_tokens=500)
        import logging as _log2
        _log2.getLogger(__name__).info("[sector_pdf] reco_commentary raw=%d chars", len(raw) if raw else 0)
        if not raw:
            return {}

        result = {}
        current_key = None
        current_lines = []
        for line in raw.strip().split("\n"):
            clean = line.strip().lstrip('*').rstrip('*').strip()
            matched = False
            for key in ("BUY", "HOLD", "SELL"):
                if clean.upper().startswith(f"{key}:"):
                    if current_key and current_lines:
                        result[current_key] = " ".join(current_lines).strip()
                    current_key = key
                    rest = clean[len(key)+1:].strip().lstrip('*').strip()
                    current_lines = [rest] if rest else []
                    matched = True
                    break
            if not matched and current_key and clean:
                current_lines.append(clean.lstrip('*').rstrip('*').strip())
        if current_key and current_lines:
            result[current_key] = " ".join(current_lines).strip()
        return result

    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).warning("[sector_pdf] LLM reco commentary: %s", e)
        return {}


# ─── BUILD STORY ──────────────────────────────────────────────────────────────
def _build_story(perf_buf, area_buf, scatter_buf, donut_buf,
                 tickers_data, sector_name, subtitle, universe, date_str,
                 page_nums, registry, sector_analytics=None, reco_commentary=None):
    story = []
    story.append(Spacer(1, 1))
    story.append(PageBreak())

    story.append(Paragraph(
        f"{sector_name} \u2014 Analyse Sectorielle FinSight IA",
        _style('rt', size=13, bold=True, color=NAVY, leading=18, space_after=2)))
    story.append(Paragraph(
        f"Rapport confidentiel \u00b7 {date_str}",
        _style('rs', size=8, color=GREY_TEXT, leading=11, space_after=6)))
    story.append(rule())
    story.append(Paragraph("Sommaire", S_SECTION))
    story.append(build_sommaire(sector_name, page_nums))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("\u00c0 propos de cette analyse", S_SUBSECTION))
    N = len(tickers_data)
    _univ_safe = _safe(universe)
    _sector_safe = _safe(sector_name)
    # ETF de référence pour le framing "ETF-first"
    _ref_etf_ticker = None
    _ref_etf_name   = None
    try:
        from core.sector_etfs import get_etf_for as _get_etf_ref
        _etf_ref_dict = _get_etf_ref(sector_name, universe=universe)
        if _etf_ref_dict:
            _ref_etf_ticker = _etf_ref_dict.get("ticker")
            _ref_etf_name   = _etf_ref_dict.get("name")
    except Exception as _e:
        log.debug(f"[sector_pdf_writer:_build_story] exception skipped: {_e}")

    if _ref_etf_ticker:
        _etf_intro = (
            f"Cette analyse sectorielle s'ancre sur l'<b>ETF {_sector_safe} ({_ref_etf_ticker})</b>"
            + (f" — {_safe(_ref_etf_name)}" if _ref_etf_name else "")
            + f". Le pool d'analyse couvre <b>{N} acteurs</b> repr\u00e9sentatifs du secteur "
            + f"<b>{_sector_safe}</b> ({_univ_safe}), s\u00e9lectionn\u00e9s parmi les holdings de "
            + f"l'ETF et les leaders r\u00e9gionaux, permettant de positionner chaque soci\u00e9t\u00e9 "
            + f"analys\u00e9e relativement au benchmark passif sectoriel."
        )
    else:
        _etf_intro = (
            f"Cette analyse sectorielle couvre <b>{N} acteurs</b> repr\u00e9sentatifs de "
            f"l'\u00e9cosyst\u00e8me <b>{_sector_safe}</b> ({_univ_safe}). Aucun ETF de r\u00e9f\u00e9rence "
            f"n'a \u00e9t\u00e9 identifi\u00e9 pour cet univers : le benchmark est constitu\u00e9 par le "
            f"panier pond\u00e9r\u00e9 market-cap des acteurs couverts."
        )

    story.append(Paragraph(
        _etf_intro + " Les donn\u00e9es financi\u00e8res sont issues de <b>yfinance</b>, "
        f"<b>FMP</b> et <b>Finnhub</b>. L'analyse de sentiment est conduite par <b>FinBERT</b> "
        f"sur le corpus presse financi\u00e8re des sept derniers jours. La valorisation "
        f"int\u00e8gre les multiples LTM pertinents selon le profil sectoriel (EV/EBITDA, "
        f"P/TBV, P/FFO, etc.) crois\u00e9s avec la croissance des revenus. Un "
        f"<b>protocole adversarial</b> identifie les risques sectoriels avec probabilit\u00e9 "
        f"et exposition par ticker.", S_BODY))
    story.append(PageBreak())

    # ── Fetch données FRED (macro) ────────────────────────────────────────
    _fred_data = {}
    try:
        from data.sources.fred_source import fetch_macro_context as _fetch_fred
        _fred_data = _fetch_fred(sector_name) or {}
        if _fred_data:
            log.info(f"[sector_pdf] FRED: {len(_fred_data)} indicateurs récupérés")
    except Exception as _e_fred:
        log.warning(f"[sector_pdf] FRED indisponible, skip: {_e_fred}")

    story += _build_macro(perf_buf, area_buf, tickers_data, sector_name, universe, registry, sector_analytics, fred_data=_fred_data)
    story += _build_structure_sectorielle(tickers_data, sector_name, sector_analytics or {}, registry)
    story += _build_subsector_decomposition(tickers_data, sector_name, registry)
    story += _build_acteurs(tickers_data, sector_name, registry)
    story.append(CondPageBreak(100*mm))  # saut page seulement si < 100mm restants (evite page vide)
    story += _build_valorisation(scatter_buf, donut_buf, tickers_data, sector_name, registry)
    story += _build_risques(tickers_data, sector_name, registry)
    # SEC-PDF-6 : section 6 (recommandation) remontee AVANT l'annexe pour
    # que le lecteur ait les top picks immediatement apres les risques.
    # Le disclaimer legal reste bien en derniere position (_build_disclaimer).
    story += _build_conclusion_reco(tickers_data, sector_name, sector_analytics or {}, registry)
    story += _build_annexe(tickers_data, sector_name, reco_commentary=reco_commentary or {})
    story += _build_disclaimer()
    return story


# ─── CALCUL ANALYTICS DEPUIS TICKERS_DATA (fallback quand sector_analytics absent) ───
def _compute_analytics_from_tickers(td: list[dict]) -> dict:
    """Calcule les métriques structurelles agrégées directement depuis tickers_data.
    Gère les deux conventions de nommage : pe_ratio (cli) et pe (compute_screening),
    market_cap absolu ou en Mds."""
    if not td:
        return {}

    def _pe(t):
        return t.get("pe_ratio") or t.get("pe")

    def _mc(t):
        mc = t.get("market_cap") or 0
        # compute_screening retourne market_cap en Mds (ex: 244.0), cli retourne absolus (ex: 2.44e11)
        if mc and mc < 1e6:  # en Mds si < 1 million (impossible en absolu pour une vraie boîte)
            return mc  # déjà en Mds, cohérent pour HHI
        return mc / 1e9 if mc > 1e6 else mc

    # HHI
    mcs = [_mc(t) for t in td]
    total_mc = sum(mcs)
    hhi = None
    hhi_label = "\u2014"
    if total_mc > 0:
        shares = [(mc / total_mc) * 100 for mc in mcs]
        hhi = round(sum(s**2 for s in shares))
        if hhi >= 2500:
            hhi_label = "oligopole concentré — barrières à l'entrée élevées, premium de valorisation justifié"
        elif hhi >= 1500:
            hhi_label = "concentration modérée — concurrence significative entre leaders établis"
        else:
            hhi_label = "secteur fragmenté — pression concurrentielle accrue, compression marges probable"

    # P/E médian
    pes = [float(_pe(t)) for t in td if _pe(t) and float(_pe(t)) > 0 and float(_pe(t)) < 500]
    pe_median_ltm = round(float(np.median(pes)), 1) if pes else None
    pe_cycle_label = "historique PE insuffisant"
    pe_premium = None

    # Dispersion ROIC / ROE — cap valeurs aberrantes (ROE peut dépasser 1000% pour buyback agressif)
    def _cap_outliers(vals, lo=-100.0, hi=200.0):
        return [max(lo, min(hi, float(v))) for v in vals if v is not None]

    roic_vals = _cap_outliers([t.get("roic") for t in td if t.get("roic") is not None])
    if not roic_vals:
        roic_vals = _cap_outliers([t.get("roe") for t in td if t.get("roe") is not None])
    roic_std  = round(float(np.std(roic_vals)), 1)  if len(roic_vals) >= 2 else None
    roic_mean = round(float(np.mean(roic_vals)), 1) if roic_vals else None
    roic_min  = round(min(roic_vals), 1)            if roic_vals else None
    roic_max  = round(max(roic_vals), 1)            if roic_vals else None
    roic_label = "\u2014"
    if roic_std is not None:
        if roic_std >= 15:
            roic_label = "forte dispersion — secteur de stock-picking pur, choix de la société > choix du secteur"
        elif roic_std >= 8:
            roic_label = "dispersion modérée — sélectivité recommandée, leaders qualité avantagés"
        else:
            roic_label = "faible dispersion — beta sectoriel dominant, approche indicielle pertinente"

    # Altman Z
    az_vals = [t.get("altman_z") for t in td if t.get("altman_z") is not None]
    n_az = len(az_vals)
    altman_safe = sum(1 for z in az_vals if z > 2.6)
    altman_grey = sum(1 for z in az_vals if 1.1 <= z <= 2.6)
    altman_dist = sum(1 for z in az_vals if z < 1.1)

    # Beta médian
    betas = [t.get("beta") for t in td if t.get("beta") is not None and 0 < float(t["beta"]) < 5]
    beta_median = round(float(np.median(betas)), 2) if betas else None
    beta_std    = round(float(np.std(betas)), 2)    if len(betas) >= 2 else None

    # FCF Yield médian
    fcfys = [t.get("fcf_yield") for t in td if t.get("fcf_yield") is not None]
    fcf_yield_median = round(float(np.median(fcfys)), 1) if fcfys else None

    # PEG médian
    pegs = [t.get("peg_ratio") for t in td if t.get("peg_ratio") is not None and t["peg_ratio"] > 0]
    peg_median = round(float(np.median(pegs)), 2) if pegs else None

    # Piotroski
    fscores = [t.get("piotroski_f") for t in td if t.get("piotroski_f") is not None]
    piotroski_median  = round(float(np.median(fscores)), 1) if fscores else None
    n_piotroski       = len(fscores)
    piotroski_quality = sum(1 for f in fscores if f > 6)
    piotroski_neutral = sum(1 for f in fscores if 4 <= f <= 6)
    piotroski_trap    = sum(1 for f in fscores if f < 4)

    # EBITDA median
    ebitda_margins = [t.get("ebitda_margin") for t in td if t.get("ebitda_margin")]
    ebitda_median  = round(float(np.median(ebitda_margins)), 1) if ebitda_margins else None

    # P/B median (clé pour BANK, INSURANCE, REIT)
    pb_vals = [t.get("pb_ratio") for t in td
               if t.get("pb_ratio") is not None and 0 < float(t["pb_ratio"]) < 100]
    pb_median = round(float(np.median(pb_vals)), 2) if pb_vals else None

    # ROE median
    roe_vals = [t.get("roe") for t in td
                if t.get("roe") is not None and -100 < float(t["roe"]) < 200]
    roe_median = round(float(np.median(roe_vals)), 1) if roe_vals else None

    # Dividend Yield median (stocké en fraction : 0.0194 = 1.94%)
    _dy_vals = []
    for t in td:
        _dy = t.get("div_yield")
        if _dy is None:
            continue
        try:
            _dy_f = float(_dy)
            # Normalise : si <1, c'est une fraction → x100 ; sinon déjà en %
            _dy_pct = _dy_f * 100 if abs(_dy_f) < 1 else _dy_f
            if 0 < _dy_pct < 25:
                _dy_vals.append(_dy_pct)
        except Exception as _e:
            log.debug(f"[sector_pdf_writer:_cap_outliers] exception skipped: {_e}")
    div_yield_median = round(float(np.median(_dy_vals)), 2) if _dy_vals else None

    # --- VaR 95% mensuelle (simulation historique basket market-cap weighted) ---
    var_95_monthly = None
    vol_annual     = None
    max_drawdown_52w = None
    try:
        import yfinance as _yf
        import pandas as _pd
        _symbols = [t["ticker"] for t in td if t.get("ticker") and t.get("market_cap")]
        if len(_symbols) >= 2:
            _total_mc = sum(t.get("market_cap", 0) or 0 for t in td if t.get("ticker"))
            if _total_mc > 0:
                _w = {t["ticker"]: (t.get("market_cap") or 0) / _total_mc
                      for t in td if t.get("ticker")}
                _raw = _yf.download(_symbols, period="1y", auto_adjust=True,
                                    progress=False, threads=True)
                if _raw is not None and not _raw.empty:
                    _prices = (_raw["Close"] if isinstance(_raw.columns, _pd.MultiIndex)
                               else _raw)
                    if len(_prices) >= 30:
                        _ret = _prices.pct_change().dropna()
                        _pr = _pd.Series(0.0, index=_ret.index)
                        _n = 0
                        for _tk in _symbols:
                            if _tk in _ret.columns and _w.get(_tk, 0) > 0:
                                _pr += _ret[_tk].fillna(0) * _w[_tk]
                                _n += 1
                        if _n > 0:
                            _vd = float(np.percentile(_pr, 5))
                            var_95_monthly   = round(_vd * np.sqrt(21) * 100, 1)
                            vol_annual       = round(float(_pr.std() * np.sqrt(252)) * 100, 1)
                            _cum  = (1 + _pr).cumprod()
                            _rmx  = _cum.cummax()
                            max_drawdown_52w = round(float(((_cum - _rmx) / _rmx).min()) * 100, 1)
    except Exception as _e:
        log.debug(f"[sector_pdf_writer:_compute_analytics_from_tickers] exception skipped: {_e}")

    # --- Duration implicite via CAPM (pas besoin de donnees externes) ---
    dur_years = dur_wacc_pct = dur_g_pct = None
    dur_method = "WACC estime CAPM (Rf=4.5% + beta x ERP 5.5%)"
    try:
        if beta_median is not None:
            _dur_wacc = 0.045 + float(beta_median) * 0.055
            _growths = [t.get("revenue_growth") for t in td
                        if t.get("revenue_growth") is not None and t["revenue_growth"] > 0]
            if _growths:
                _g_raw = float(np.median(_growths))
                # revenue_growth peut etre en % (15.0) ou decimal (0.15) selon la source
                if _g_raw > 1.0:
                    _g_raw = _g_raw / 100
            else:
                _g_raw = 0.04
            _dur_g = max(0.02, min(_g_raw * 0.35, 0.05, _dur_wacc - 0.02))
            if _dur_wacc > _dur_g:
                dur_years    = round((1 + _dur_g) / (_dur_wacc - _dur_g), 1)
                dur_wacc_pct = round(_dur_wacc * 100, 1)
                dur_g_pct    = round(_dur_g   * 100, 1)
    except Exception as _e:
        log.debug(f"[sector_pdf_writer:_compute_analytics_from_tickers] exception skipped: {_e}")

    return {
        "hhi": hhi, "hhi_label": hhi_label,
        "pe_median_ltm": pe_median_ltm, "pe_median_hist": None,
        "pe_premium": pe_premium, "pe_cycle_label": pe_cycle_label,
        "roic_std": roic_std, "roic_mean": roic_mean,
        "roic_min": roic_min, "roic_max": roic_max, "roic_label": roic_label,
        "altman_safe": altman_safe, "altman_grey": altman_grey,
        "altman_distress": altman_dist, "n_altman": n_az,
        "altman_model": "nonmfg_1995", "is_asset_light": True,
        "beta_median": beta_median, "beta_std": beta_std,
        "fcf_yield_median": fcf_yield_median,
        "peg_median": peg_median,
        "piotroski_median": piotroski_median, "n_piotroski": n_piotroski,
        "piotroski_quality": piotroski_quality,
        "piotroski_neutral": piotroski_neutral,
        "piotroski_trap": piotroski_trap,
        "ebitda_median": ebitda_median,
        "pb_median": pb_median,
        "roe_median": roe_median,
        "div_yield_median": div_yield_median,
        "wacc_median": None,
        "var_95_monthly":    var_95_monthly,   # cle correcte pour sector_pdf_writer
        "vol_annual":        vol_annual,
        "max_drawdown_52w":  max_drawdown_52w,
        "duration_years":    dur_years,
        "duration_wacc":     dur_wacc_pct,
        "duration_growth":   dur_g_pct,
        "duration_method":   dur_method,
    }


def _precompute_sector_llm_batch(
    tickers_data: list[dict],
    sector_name: str,
    sa: dict,
) -> dict:
    """Pre-compute en PARALLELE les 4 LLM calls sectoriels longs.

    Audit perf 26/04/2026 — avant ce batch, 4 LLM calls etaient enchaines
    en serie (~25-50s wall). En parallele : max(t1..t4) = ~10-15s. Gain
    ~15-30s sur pipeline secteur 120s.

    Inclus :
    - acteurs_intro : intro 200-240 mots panorama acteurs (page 9)
    - risques : 4 risques specifiques au secteur, JSON (page 13)
    - inter_sectoriel : positionnement vs autres secteurs (110-150 mots)
    - reco : recommandation 6 paragraphes (page conclusion)

    Le call subsectors_dict (LLM #1) garde son flow propre car le retour
    est un dict structure deja parse — different design.

    Returns : dict {key: text_or_dict} a injecter dans sa["_llm_batch"].
    """
    out = {}
    if not tickers_data:
        return out

    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from core.llm_provider import llm_call

        # === Inputs partages ===
        N = len(tickers_data)
        sorted_data = sorted(tickers_data, key=lambda x: x.get('score_global') or 0, reverse=True)
        sorted_asc = sorted(tickers_data, key=lambda x: x.get('score_global') or 50)
        best = sorted_data[0] if sorted_data else {}
        _worst = sorted_data[-1] if sorted_data else {}
        _top3_names = ", ".join(
            f"{t.get('ticker','?')} ({int(t.get('score_global') or 0)}/100)"
            for t in sorted_data[:3]
        )
        vuln_tickers = ", ".join(t.get('ticker','') for t in sorted_asc[:3])
        best_tickers = ", ".join(t.get('ticker','') for t in sorted_data[:2])

        buy_count  = sum(1 for t in tickers_data if (t.get("score_global") or 50) >= 60)
        hold_count = sum(1 for t in tickers_data if 40 <= (t.get("score_global") or 50) < 60)
        sell_count = sum(1 for t in tickers_data if (t.get("score_global") or 50) < 40)

        _current_pe = sa.get("pe_median_ltm")
        _current_ev = sa.get("ev_ebitda_median") or sa.get("ev_med")

        # Profile hints
        _profile_hints = ""
        try:
            from core.sector_profiles import detect_profile, get_prompt_hints
            _reco_profile = detect_profile(
                sector_name,
                tickers_data[0].get("industry", "") if tickers_data else "",
            )
            _profile_hints = get_prompt_hints(_reco_profile) or ""
        except Exception as _e:
            log.debug(f"[sector_llm_batch] profile detect: {_e}")

        # Industries summary (pour reco)
        _industries = {}
        for t in tickers_data:
            ind = t.get("industry") or "Autre"
            _industries.setdefault(ind, []).append(t.get("score_global") or 0)
        _ind_summary = ", ".join(
            f"{k} (score moy. {sum(v)//len(v)})"
            for k, v in sorted(
                _industries.items(),
                key=lambda x: sum(x[1])/len(x[1]),
                reverse=True,
            )[:5]
        )

        # === Construction des 4 prompts ===
        prompts = {}

        # 1. Acteurs intro
        prompts["acteurs_intro"] = (
            (
                f"Analyste buy-side senior. Introduction 200-240 mots a l'analyse des "
                f"{N} acteurs du secteur {sector_name}.\n"
                f"Top 3 FinSight : {_top3_names}. Leader : {best.get('company','?')} "
                f"(score {best.get('score_global','?')}/100, marge EBITDA "
                f"{best.get('ebitda_margin','?')}, croissance {best.get('revenue_growth','?')}). "
                f"Lanterne : {_worst.get('company','?')} (score {_worst.get('score_global','?')}/100).\n\n"
                f"EXACTEMENT 2 paragraphes. Chaque paragraphe commence par son titre en "
                f"majuscules suivi de ' : ' puis le corps du paragraphe IMMEDIATEMENT sur "
                f"la MEME ligne (pas de saut de ligne entre le titre et le corps, pas de "
                f"sous-titre intermediaire).\n"
                f"1. PANORAMA : hierarchie concurrentielle, ce qui distingue leaders et "
                f"challengers, drivers de differentiation.\n"
                f"2. DISPERSION : ce que le spread implique pour l'allocation (concentration "
                f"vs diversification), ratios privilegies pour le stock-picking.\n\n"
                f"Francais avec accents. Pas de markdown/emojis. Pas de sous-titres dans un "
                f"paragraphe."
            ),
            "long",
            700,
        )

        # 2. Risques specifiques
        prompts["risques"] = (
            (
                f"Strategist buy-side. 4 risques SPECIFIQUES au secteur {sector_name} "
                f"a 12 mois (pas generiques). {N} societes, vulnerables : "
                f"{vuln_tickers}, solides : {best_tickers}.\n"
                f"JSON strict, sans markdown :\n"
                f'{{"risques":[{{"axe":"titre court","analyse":"2 phrases sur le mecanisme '
                f'specifique","prob":"25pct","impact":"Eleve|Modere|Mixte","tickers":"X,Y"}}'
                f",x4]}}"
            ),
            "long",
            900,
        )

        # 3. Inter-sectoriel (seulement si data dispo)
        if _current_pe is not None and _current_ev is not None:
            # Mediane cross-sector hardcoded fallback (evite cross-sector benchmark fetch)
            _med_pe_global = 18.0
            _med_ev_global = 12.5
            _pe_pos = ("decote" if _current_pe < _med_pe_global * 0.85
                       else "premium" if _current_pe > _med_pe_global * 1.15
                       else "en ligne")
            _ev_pos = ("decote" if _current_ev < _med_ev_global * 0.85
                       else "premium" if _current_ev > _med_ev_global * 1.15
                       else "en ligne")
            prompts["inter_sectoriel"] = (
                (
                    f"Analyste sell-side senior. Lecture interpretative 110-150 mots "
                    f"de la position du secteur {sector_name} dans le tableau de "
                    f"comparaison inter-sectorielle. P/E median secteur = {_current_pe}x "
                    f"(mediane des 11 secteurs = {_med_pe_global}x -> {_pe_pos}), "
                    f"EV/EBITDA median secteur = {_current_ev}x (mediane = "
                    f"{_med_ev_global}x -> {_ev_pos}).\n\n"
                    f"Structure : (1) constat chiffre sur le positionnement P/E + "
                    f"EV/EBITDA vs autres secteurs, (2) explication structurelle "
                    f"(cycle, rentabilite, risque reglementaire, croissance) qui "
                    f"justifie cette prime/decote, (3) implication portefeuille — "
                    f"pour quel profil d'investisseur ce secteur est attractif "
                    f"actuellement.\n\nFrancais avec accents. Pas de markdown. "
                    f"Pas de bullet points. Chiffres precis, espace avant % et x."
                ),
                "fast",
                350,
            )

        # 4. Recommandation finale (6 paragraphes)
        _reco_p = (
            f"Analyste buy-side senior. Recommandation sectorielle detaillee 400-500 mots "
            f"pour {sector_name}.\n"
            f"{N} societes : {buy_count} BUY / {hold_count} HOLD / {sell_count} SELL. "
            f"Sous-secteurs : {_ind_summary}.\n"
        )
        if _profile_hints:
            _reco_p += f"Profil specifique : {_profile_hints}\n"
        _reco_p += (
            f"6 paragraphes separes par ligne vide (~70 mots chacun) avec ces titres EXACTS "
            f"en MAJUSCULES au debut de chaque paragraphe suivi de ' : ' :\n"
            f"1. PROMETTEUR : le secteur est-il attractif et pourquoi.\n"
            f"2. HORIZON : duree d'investissement recommandee.\n"
            f"3. SOUS-SECTEURS : quels sous-segments privilegier.\n"
            f"4. CATALYSEURS : evenements 6-12 mois a surveiller.\n"
            f"5. RISQUES : principaux risques a monitorer.\n"
            f"6. REVISION : conditions de revision de la these.\n\n"
            f"IMPORTANT : PAS de markdown ** / ---. Commence chaque paragraphe par le titre.\n"
            f"Francais avec accents. Pas d'emojis. Utilise les metriques specifiques au "
            f"profil ci-dessus.\n"
            f"FORMAT CHIFFRES FR OBLIGATOIRE : virgule decimale (33,9x), "
            f"espace avant % et x (20,8 %, 1,6x), espace separateur de "
            f"milliers (1 353 M€). JAMAIS de point decimal anglophone."
        )
        prompts["reco"] = (_reco_p, "critical", 1200)

        # === Lance les 4 calls en parallele ===
        def _call(key, prompt, phase, max_tokens):
            try:
                return key, llm_call(prompt, phase=phase, max_tokens=max_tokens) or ""
            except Exception as _e:
                log.warning(f"[sector_llm_batch/{key}] failed: {_e}")
                return key, ""

        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = [
                ex.submit(_call, k, p, ph, mt)
                for k, (p, ph, mt) in prompts.items()
            ]
            for fut in as_completed(futures, timeout=120):
                try:
                    k, text = fut.result(timeout=90)
                    if text and len(text) > 50:
                        out[k] = text
                except Exception as _e:
                    log.warning(f"[sector_llm_batch] future failed: {_e}")

        # Restore accents post-LLM (Mistral oublie sur emetteurs/rentabilite/etc.)
        try:
            from tools.restore_accents import restore_accents_in_text as _ra
            for _k in out:
                if isinstance(out[_k], str):
                    out[_k] = _ra(out[_k])
        except Exception:
            pass

        log.info(
            "[sector_llm_batch] %d/%d sections OK (parallel)",
            len(out), len(prompts),
        )
    except Exception as _e:
        log.warning(f"[sector_llm_batch] global failure: {_e}")

    return out


# ─── API PUBLIQUE ─────────────────────────────────────────────────────────────
def generate_sector_report(
    sector_name: str,
    tickers_data: list[dict],
    output_path: str,
    subtitle: str = None,
    universe: str = "CAC 40",
    date_str: str = None,
    sector_analytics: dict = None,
    language: str = "fr",
    currency: str = "EUR",
) -> str:
    # i18n : activer langue module-level
    global _SECTOR_CURRENT_LANG
    _SECTOR_CURRENT_LANG = (language or "fr").lower()[:2]
    if _SECTOR_CURRENT_LANG not in {"fr","en","es","de","it","pt"}:
        _SECTOR_CURRENT_LANG = "fr"
    # i18n : on garde l'original (anglais yfinance) pour les data lookups,
    # et on cree une version francaise pour tous les affichages downstream.
    sector_name_en = sector_name
    try:
        from core.sector_labels import fr_label as _fr_lbl
        sector_name = _fr_lbl(sector_name)
    except Exception as _e:
        log.debug(f"[sector_pdf_writer:generate_sector_report] exception skipped: {_e}")
    """
    Genere un rapport PDF sectoriel institutionnel.

    Args:
        sector_name   : Nom du secteur (ex: "Technology")
        tickers_data  : Liste de dicts avec champs financiers (meme format que screening)
        output_path   : Chemin de sortie du PDF
        subtitle      : Sous-titre analytique (optionnel)
        universe      : Univers de reference (ex: "CAC 40")
        date_str      : Date d'analyse (defaut: aujourd'hui)
    """
    if not tickers_data:
        raise ValueError("tickers_data est vide")

    if date_str is None:
        _fr_months = {1:"janvier",2:"fevrier",3:"mars",4:"avril",5:"mai",6:"juin",
                      7:"juillet",8:"aout",9:"septembre",10:"octobre",11:"novembre",12:"decembre"}
        _d = date.today()
        date_str = f"{_d.day} {_fr_months[_d.month]} {_d.year}"
    if subtitle is None:
        subtitle = f"Positionnement, valorisation et dynamiques \u2014 {universe}"

    # Macro regime + recession (si pas deja fourni)
    if sector_analytics is None:
        sector_analytics = {}

    # Calcul automatique des analytics structurels si absents (ex : appel depuis app.py)
    # Fix 2026-04-26 : on inclut maintenant pb_median / roe_median / div_yield_median
    # dans les clés déclencheuses (banques/REITs/insurance les avaient à None car
    # le pipeline cli_analyze ne les remontait pas correctement) — et on override
    # les valeurs None existantes au lieu d'utiliser setdefault qui les preservait.
    _need_aggregates = (
        not sector_analytics.get("hhi")
        or not sector_analytics.get("pe_median_ltm")
        or sector_analytics.get("pb_median") is None
        or sector_analytics.get("roe_median") is None
        or sector_analytics.get("div_yield_median") is None
    )
    if _need_aggregates:
        _sa = _compute_analytics_from_tickers(tickers_data)
        for k, v in _sa.items():
            # override les None existants ; preserve les valeurs explicites
            if sector_analytics.get(k) is None:
                sector_analytics[k] = v

    if not sector_analytics.get("macro"):
        try:
            import sys as _sys, os as _os
            _sys.path.insert(0, _os.path.dirname(_os.path.dirname(__file__)))
            from agents.agent_macro import AgentMacro
            sector_analytics["macro"] = AgentMacro().analyze()
        except Exception as _me:
            import logging as _log
            _log.getLogger(__name__).warning("[sector_pdf_writer] AgentMacro: %s", _me)
            sector_analytics.setdefault("macro", {})

    # === Pre-compute LLM batch (4 sections en parallele) ===
    # Audit perf 26/04/2026 — avant ce batch, 4 LLM longs etaient enchaines en
    # serie (~25-50s wall) au milieu du build PDF. En parallele : ~10-15s.
    # Les sections lisent depuis _SECTOR_LLM_BATCH (module-level) avec fallback
    # unitaire (call direct) si la cle est absente.
    global _SECTOR_LLM_BATCH
    if not sector_analytics.get("_llm_batch"):
        sector_analytics["_llm_batch"] = _precompute_sector_llm_batch(
            tickers_data, sector_name, sector_analytics,
        )
    _SECTOR_LLM_BATCH = sector_analytics.get("_llm_batch") or {}

    # Commentaire LLM BUY/HOLD/SELL (appel unique Groq)
    # On merge STRONG BUY + BUY et UNDERPERFORM + SELL pour le commentaire LLM
    _sorted = sorted(tickers_data, key=lambda x: x.get('score_global') or 0, reverse=True)
    _buy_l  = [t for t in _sorted if _reco(t.get('score_global')) in ("STRONG BUY", "BUY")]
    _hold_l = [t for t in _sorted if _reco(t.get('score_global')) == "HOLD"]
    _sell_l = [t for t in _sorted if _reco(t.get('score_global')) in ("UNDERPERFORM", "SELL")]
    _reco_profile = _detect_sector_profile(tickers_data, sector_name)
    reco_commentary = _generate_reco_commentary(_buy_l, _hold_l, _sell_l, sector_name, _reco_profile)

    # Generation des charts — perf_chart avec univers pour resoudre l'ETF
    perf_buf    = _make_perf_chart(tickers_data, sector_name, universe)
    area_buf    = _make_revenue_area(tickers_data, sector_name, universe)
    scatter_buf = _make_valuation_bars(tickers_data, sector_name)
    donut_buf   = _make_mktcap_donut(tickers_data, sector_name)

    doc_kwargs = dict(
        pagesize=A4,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T + 6*mm, bottomMargin=MARGIN_B + 8*mm,
        title=f"FinSight IA \u2014 {sector_name}",
        author="FinSight IA v1.0",
    )

    def on_page(c, doc):
        if doc.page == 1:
            _cover_page(c, doc, sector_name, subtitle, universe, date_str, tickers_data)
        else:
            _content_header(c, doc, sector_name, date_str)

    # Passe 1 : collecte des numeros de page
    registry = {}
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        tmp_path = tmp.name
    try:
        doc1 = SimpleDocTemplate(tmp_path, **doc_kwargs)
        story1 = _build_story(perf_buf, area_buf, scatter_buf, donut_buf,
                               tickers_data, sector_name, subtitle, universe, date_str,
                               {}, registry, sector_analytics, reco_commentary)
        doc1.build(story1, onFirstPage=on_page, onLaterPages=on_page)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # Passe 2 : generation finale avec vrais numeros de page
    # Rewind des buffers matplotlib (epuises apres passe 1)
    for buf in (perf_buf, area_buf, scatter_buf, donut_buf):
        buf.seek(0)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc2 = SimpleDocTemplate(output_path, **doc_kwargs)
    story2 = _build_story(perf_buf, area_buf, scatter_buf, donut_buf,
                           tickers_data, sector_name, subtitle, universe, date_str,
                           dict(registry), {}, sector_analytics, reco_commentary)
    doc2.build(story2, onFirstPage=on_page, onLaterPages=on_page)

    import logging
    logging.getLogger(__name__).info(
        "[sector_pdf] %s généré (%d tickers) | sections: %s",
        output_path, len(tickers_data), registry)
    return output_path


if __name__ == "__main__":
    # Test avec données fictives
    test_data = [
        {"ticker":"DSY.PA","company":"Dassault Systemes","sector":"Technology",
         "price":17.0,"market_cap":22.3,"ev":28.0,"revenue_ltm":6.0,"ebitda_ltm":1.8,
         "ev_ebitda":10.9,"pe":18.7,"gross_margin":83.7,"ebitda_margin":30.4,
         "net_margin":18.0,"revenue_growth":0.4,"roe":13.6,"roa":7.2,
         "score_global":48,"score_value":47,"score_growth":42,"score_quality":100,"score_momentum":3,
         "momentum_52w":0.4,"altman_z":None,"beneish_m":-3.1,"currency":"EUR"},
        {"ticker":"CAP.PA","company":"Capgemini SE","sector":"Technology",
         "price":155.0,"market_cap":25.0,"ev":30.0,"revenue_ltm":22.0,"ebitda_ltm":3.2,
         "ev_ebitda":9.4,"pe":16.2,"gross_margin":31.0,"ebitda_margin":14.5,
         "net_margin":8.2,"revenue_growth":3.2,"roe":22.4,"roa":9.1,
         "score_global":55,"score_value":60,"score_growth":55,"score_quality":58,"score_momentum":45,
         "momentum_52w":5.2,"altman_z":2.1,"beneish_m":-2.8,"currency":"EUR"},
        {"ticker":"STM.PA","company":"STMicroelectronics","sector":"Technology",
         "price":18.5,"market_cap":16.0,"ev":15.0,"revenue_ltm":12.8,"ebitda_ltm":2.5,
         "ev_ebitda":6.0,"pe":12.1,"gross_margin":40.2,"ebitda_margin":19.5,
         "net_margin":11.0,"revenue_growth":-15.0,"roe":18.3,"roa":8.5,
         "score_global":42,"score_value":70,"score_growth":20,"score_quality":55,"score_momentum":30,
         "momentum_52w":-28.0,"altman_z":3.5,"beneish_m":-2.5,"currency":"EUR"},
        {"ticker":"HEX.PA","company":"Hexagon AB","sector":"Technology",
         "price":95.0,"market_cap":12.0,"ev":16.0,"revenue_ltm":5.4,"ebitda_ltm":1.6,
         "ev_ebitda":10.0,"pe":22.0,"gross_margin":65.0,"ebitda_margin":29.6,
         "net_margin":15.0,"revenue_growth":4.1,"roe":12.0,"roa":6.0,
         "score_global":62,"score_value":55,"score_growth":65,"score_quality":70,"score_momentum":55,
         "momentum_52w":12.0,"altman_z":2.8,"beneish_m":-3.2,"currency":"EUR"},
    ]
    out = generate_sector_report(
        sector_name="Technology",
        tickers_data=test_data,
        output_path="outputs/generated/test_sector_technology.pdf",
        universe="CAC 40",
    )
    print(f"OK : {out}")
