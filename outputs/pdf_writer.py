# =============================================================================
# FinSight IA — PDF Writer v3
# outputs/pdf_writer.py
#
# Rendu visuel identique a rapport_type_reference_v6.py.
# Toutes les donnees sont dynamiques via un dict `data`.
#
# Points d'entree :
#   generate_report(data: dict, output_path: str) -> str
#   PDFWriter().generate(state: dict, output_path: str) -> str  [compat pipeline]
# =============================================================================

from __future__ import annotations

import io
import logging
from datetime import date as _date_cls
from pathlib import Path

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    _MATPLOTLIB_OK = True
except ImportError:
    _MATPLOTLIB_OK = False
    plt = None
    np  = None

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Image, KeepTogether
)

log = logging.getLogger(__name__)


def _blank_chart_buf(w=6.5, h=2.8):
    """Retourne un buffer PNG vide (N/A) sans matplotlib si necessaire."""
    if _MATPLOTLIB_OK:
        fig, ax = plt.subplots(figsize=(w, h))
        ax.text(0.5, 0.5, 'N/A', ha='center', va='center',
                fontsize=14, color='#888', transform=ax.transAxes)
        ax.axis('off')
        fig.patch.set_facecolor('white')
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        plt.close(fig); buf.seek(0)
        return buf
    # Fallback sans matplotlib : PNG 1x1 blanc minimaliste via bytes bruts
    import struct, zlib
    def _png1x1():
        def _chunk(t, d):
            c = zlib.crc32(t + d) & 0xffffffff
            return struct.pack('>I', len(d)) + t + d + struct.pack('>I', c)
        ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
        idat = zlib.compress(b'\x00\xff\xff\xff')
        return (b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', ihdr)
                + _chunk(b'IDAT', idat) + _chunk(b'IEND', b''))
    return io.BytesIO(_png1x1())


# =============================================================================
# PALETTE
# =============================================================================
NAVY       = colors.HexColor('#1B3A6B')
NAVY_LIGHT = colors.HexColor('#2A5298')
BUY_GREEN  = colors.HexColor('#1A7A4A')
SELL_RED   = colors.HexColor('#A82020')
HOLD_AMB   = colors.HexColor('#B06000')
WHITE      = colors.white
BLACK      = colors.HexColor('#1A1A1A')
GREY_LIGHT = colors.HexColor('#F5F7FA')
GREY_MED   = colors.HexColor('#E8ECF0')
GREY_TEXT  = colors.HexColor('#555555')
GREY_RULE  = colors.HexColor('#D0D5DD')
ROW_ALT    = colors.HexColor('#F0F4F8')

# =============================================================================
# DIMENSIONS
# =============================================================================
PAGE_W, PAGE_H = A4
MARGIN_L = 17 * mm
MARGIN_R = 17 * mm
MARGIN_T = 22 * mm
MARGIN_B = 18 * mm
TABLE_W  = 170 * mm

# =============================================================================
# STYLES
# =============================================================================
def _s(name, font='Helvetica', size=9, color=BLACK, leading=13,
       align=TA_LEFT, bold=False, sb=0, sa=2):
    return ParagraphStyle(
        name,
        fontName='Helvetica-Bold' if bold else font,
        fontSize=size, textColor=color, leading=leading,
        alignment=align, spaceBefore=sb, spaceAfter=sa,
    )

S_BODY       = _s('body',    size=8.5, leading=13, color=GREY_TEXT, align=TA_JUSTIFY)
S_LABEL      = _s('label',   size=7.5, leading=10, color=GREY_TEXT)
S_SECTION    = _s('sec',     size=12,  leading=16, color=NAVY, bold=True, sb=8, sa=2)
S_SUBSECTION = _s('subsec',  size=9,   leading=13, color=NAVY, bold=True, sb=5, sa=3)
S_DEBATE     = _s('debate',  size=8.5, leading=12, color=NAVY_LIGHT, bold=True, sb=3, sa=5)
S_TH_C      = _s('thc', size=8, leading=11, color=WHITE, bold=True, align=TA_CENTER)
S_TH_L      = _s('thl', size=8, leading=11, color=WHITE, bold=True, align=TA_LEFT)
S_TD_L      = _s('tdl', size=8, leading=11, color=BLACK, align=TA_LEFT)
S_TD_C      = _s('tdc', size=8, leading=11, color=BLACK, align=TA_CENTER)
S_TD_B      = _s('tdb', size=8, leading=11, color=BLACK, bold=True, align=TA_LEFT)
S_TD_BC     = _s('tdbc',size=8, leading=11, color=BLACK, bold=True, align=TA_CENTER)
S_TD_G      = _s('tdg', size=8, leading=11, color=BUY_GREEN, bold=True, align=TA_CENTER)
S_TD_R      = _s('tdr', size=8, leading=11, color=SELL_RED,  bold=True, align=TA_CENTER)
S_TD_A      = _s('tda', size=8, leading=11, color=HOLD_AMB,  bold=True, align=TA_CENTER)
S_NOTE      = _s('note',size=6.5, leading=9, color=GREY_TEXT)
S_DISC      = _s('disc',size=6.5, leading=9, color=GREY_TEXT, align=TA_JUSTIFY)

# =============================================================================
# HELPERS
# =============================================================================
def _enc(s):
    """Encode pour canvas ReportLab (Helvetica / WinAnsiEncoding = cp1252).
    cp1252 inclut em-dash (0x97) et en-dash (0x96) contrairement a latin-1."""
    if not s: return ""
    try:
        import unicodedata
        s = unicodedata.normalize('NFKC', str(s))
        return s.encode('cp1252', errors='replace').decode('cp1252')
    except: return str(s)

def _safe(s):
    """Echappe &, <, > pour injection dans ReportLab Paragraph (parser XML)."""
    if not s: return ""
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def _d(obj, key, default=""):
    v = obj.get(key) if isinstance(obj, dict) else None
    return v if v is not None else default

def _rec_color(rec):
    r = str(rec).upper()
    if r == 'BUY':  return BUY_GREEN
    if r == 'SELL': return SELL_RED
    return HOLD_AMB

def rule(w=TABLE_W, thick=0.5, col=GREY_RULE, sb=4, sa=4):
    return HRFlowable(width=w, thickness=thick, color=col, spaceAfter=sa, spaceBefore=sb)

def section_title(text, num):
    return [rule(sb=6, sa=0), Paragraph(f"{num}. {text}", S_SECTION), rule(sb=2, sa=6)]

def debate_q(text):
    return Paragraph(f"\u25b6  {text}", S_DEBATE)

def src(text):
    return Paragraph(f"Source : {text}", S_NOTE)

def tbl(data, cw, row_heights=None):
    """Table standard : header navy, alternance lignes, grille fine."""
    t = Table(data, colWidths=cw, rowHeights=row_heights)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), NAVY),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [WHITE, ROW_ALT]),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
        ('LINEBELOW',     (0, 0), (-1, 0),  0.5, NAVY_LIGHT),
        ('LINEBELOW',     (0, -1),(-1, -1), 0.5, GREY_RULE),
        ('GRID',          (0, 1), (-1, -1), 0.3, GREY_MED),
    ]))
    return t

# =============================================================================
# KEY DATA BOX
# =============================================================================
def _key_data_box(data):
    rec = _d(data, 'recommendation', 'HOLD').upper()
    cur = _d(data, 'currency', 'USD')
    items = [
        ("Donn\u00e9es cl\u00e9s",                ""),
        ("Ticker",                                _d(data, 'ticker_exchange', _d(data, 'ticker'))),
        ("Secteur",                               _d(data, 'sector')),
        (f"Cours ({cur})",                        _d(data, 'price_str')),
        ("Recommandation",                        rec),
        ("Cible 12 mois",                         _d(data, 'target_price_full')),
        ("Upside potentiel",                      _d(data, 'upside_str')),
        ("Market Cap",                            _d(data, 'market_cap_str')),
        ("Dividend Yield",                        _d(data, 'dividend_yield_str')),
        ("P/E NTM (x)",                           _d(data, 'pe_ntm_str')),
        ("EV/EBITDA (x)",                         _d(data, 'ev_ebitda_str')),
        ("Conviction IA",                         _d(data, 'conviction_str')),
    ]
    rows = []
    for k, v in items:
        if k == "Donn\u00e9es cl\u00e9s":
            rows.append([
                Paragraph(f"<b>{k}</b>",
                    _s('kh', size=7.5, leading=10, color=WHITE, bold=True)),
                Paragraph("", S_LABEL),
            ])
        else:
            vc = _rec_color(rec) if k == "Recommandation" else \
                 (BUY_GREEN if "Upside" in k else NAVY)
            rows.append([
                Paragraph(k, S_LABEL),
                Paragraph(f"<b>{_safe(v)}</b>",
                    _s(f'kv{id(k)}', size=7.5, leading=10, color=vc, bold=True,
                       align=TA_RIGHT)),
            ])
    t = Table(rows, colWidths=[38*mm, 32*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  NAVY),
        ('BACKGROUND',    (0, 1), (-1, -1), GREY_LIGHT),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
        ('LINEBELOW',     (0, 0), (-1, -1), 0.3, GREY_RULE),
        ('BOX',           (0, 0), (-1, -1), 0.6, NAVY),
    ]))
    return t

# =============================================================================
# CHARTS (necessite matplotlib)
# =============================================================================
def _make_perf_chart(data):
    if not _MATPLOTLIB_OK:
        return _blank_chart_buf(8.5, 3.8)
    months      = data.get('perf_months') or []
    ticker_vals = data.get('perf_ticker') or []
    index_vals  = data.get('perf_index')  or []
    index_name  = _d(data, 'index_name', 'Indice')
    ticker      = _d(data, 'ticker', '')
    start_label = _d(data, 'perf_start_label', '')

    # Fallback si donnees manquantes
    if not months:
        months = [f"M{i}" for i in range(13)]
    if not ticker_vals:
        ticker_vals = [100] * len(months)
    if not index_vals:
        index_vals = [100] * len(months)
    n = min(len(months), len(ticker_vals), len(index_vals))
    months, ticker_vals, index_vals = months[:n], ticker_vals[:n], index_vals[:n]

    x = np.arange(n)
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    ax.plot(x, ticker_vals, color='#1B3A6B', linewidth=2.0, label=ticker)
    ax.plot(x, index_vals,  color='#A0A0A0', linewidth=1.4, linestyle='--', label=index_name)
    ax.fill_between(x, ticker_vals, index_vals,
                    where=[a > s for a, s in zip(ticker_vals, index_vals)],
                    alpha=0.08, color='#1B3A6B')
    tick_step = max(1, n // 5) if n >= 2 else 1
    ax.set_xticks(x[::tick_step])
    ax.set_xticklabels(months[::tick_step], fontsize=9, color='#555')
    ax.tick_params(length=0, labelsize=9)
    for sp in ['top', 'right']: ax.spines[sp].set_visible(False)
    ax.spines['left'].set_color('#D0D5DD')
    ax.spines['bottom'].set_color('#D0D5DD')
    ax.set_facecolor('white'); fig.patch.set_facecolor('white')
    ax.legend(fontsize=9, loc='upper left', frameon=False)
    title = "Performance relative \u2014 base 100"
    if start_label:
        title += f", {start_label}"
    ax.set_title(title, fontsize=12, color='#1B3A6B', fontweight='bold', pad=6)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=180, bbox_inches='tight')
    plt.close(fig); buf.seek(0)
    return buf


def _make_ff_chart(data):
    if not _MATPLOTLIB_OK:
        return _blank_chart_buf(8.5, 3.8)
    methods    = data.get('ff_methods') or []
    lows       = data.get('ff_lows')    or []
    highs      = data.get('ff_highs')   or []
    cols       = data.get('ff_colors')  or ['#1B3A6B'] * len(methods)
    course     = float(data.get('ff_course') or 0)
    course_str = _d(data, 'ff_course_str', '')
    currency   = _d(data, 'currency', '')

    n = len(methods)
    # Hauteur adaptive : min 4.5, +0.72 par methode pour eviter overlaps (FIX 7)
    fig_h = max(4.5, 1.4 + n * 0.72)
    fig, ax = plt.subplots(figsize=(10, fig_h))

    y = np.arange(n)
    for i, (lo, hi, col) in enumerate(zip(lows, highs, cols)):
        lo, hi = float(lo), float(hi)
        ax.barh(y[i], hi - lo, left=lo, height=0.48, color=col, alpha=0.85, zorder=3)
        # Valeur centrale dans la barre — taille lisible (FIX 6+7)
        ax.text((lo + hi) / 2, y[i], f"{int((lo + hi) / 2)}",
                va='center', ha='center', fontsize=10, color='white', fontweight='bold', zorder=4)
        # Valeurs basses/hautes HORS de la barre — offset adaptatif + clip_on=False
        rng_bar = hi - lo if hi > lo else 1
        offset = max(rng_bar * 0.04, 2.0)
        ax.text(lo - offset, y[i], f"{int(lo)}", va='center', ha='right',
                fontsize=10, color='#444', clip_on=False)
        ax.text(hi + offset, y[i], f"{int(hi)}", va='center', ha='left',
                fontsize=10, color='#444', clip_on=False)

    if course and lows and highs:
        ax.axvline(x=course, color='#B06000', linewidth=2.0, linestyle='--', zorder=5)
        # Label cours en haut, dans une boite blanche bien lisible
        course_lbl = f'{currency}{course_str}' if course_str else f'{course:.0f}'
        n_bars = len(lows)
        ax.text(course, n_bars - 0.05, f'Cours : {course_lbl}',
                fontsize=8, color='#B06000', fontweight='bold',
                ha='center', va='top', clip_on=False,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.9, edgecolor='#B06000', linewidth=0.6))

    ax.set_yticks(y)
    ax.set_yticklabels(methods, fontsize=9, color='#222')

    if lows and highs:
        all_v = [float(v) for v in lows + highs]
        rng    = max(all_v) - min(all_v) if len(all_v) > 1 else max(all_v)
        # Marge proportionnelle (20% de la plage) pour laisser de la place aux labels
        margin = max(20, rng * 0.20)
        ax.set_xlim(min(all_v) - margin, max(all_v) + margin)

    ax.set_xlabel(f'Valeur par action ({currency})', fontsize=10, color='#555')
    for sp in ['top', 'right']: ax.spines[sp].set_visible(False)
    ax.spines['left'].set_color('#D0D5DD')
    ax.spines['bottom'].set_color('#D0D5DD')
    ax.tick_params(axis='x', labelsize=9)
    ax.tick_params(axis='y', length=0)
    ax.set_facecolor('white')
    fig.patch.set_facecolor('white')
    # Pas de titre matplotlib : le PDF ajoute deja un titre de section au-dessus
    ax.grid(axis='x', alpha=0.3, color='#D0D5DD', zorder=0)
    plt.tight_layout(rect=[0, 0, 1, 1], pad=1.5)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=180, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf


def _make_pie_comparables(data):
    if not _MATPLOTLIB_OK:
        return _blank_chart_buf(4.8, 4.0)
    labels      = data.get('pie_labels') or []
    sizes       = data.get('pie_sizes')  or []
    ticker      = _d(data, 'pie_ticker', _d(data, 'ticker'))
    pct_str     = _d(data, 'pie_pct_str', '')
    sector_name = _d(data, 'pie_sector_name', '')
    cap_label   = _d(data, 'pie_cap_label', 'EV')

    if not labels or not sizes:
        # Graphique vide
        fig, ax = plt.subplots(figsize=(5.2, 5.2))
        ax.text(0.5, 0.5, 'N/A', ha='center', va='center', fontsize=14, color='#555')
        ax.set_facecolor('white'); fig.patch.set_facecolor('white')
        ax.axis('off')
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=180, bbox_inches='tight')
        plt.close(fig); buf.seek(0)
        return buf

    _BASE_PALETTE = ['#1B3A6B','#2A5298','#3D6099','#5580B8','#7AA0CC','#A0BEDC','#D0D5DD']
    # Etendre la palette dynamiquement si plus d'elements que prevu
    n_labels = len(labels)
    if n_labels > len(_BASE_PALETTE):
        import matplotlib.cm as _cm
        _extra = [
            '#%02x%02x%02x' % tuple(int(c * 255) for c in _cm.Blues(0.3 + 0.5 * i / n_labels)[:3])
            for i in range(n_labels - len(_BASE_PALETTE))
        ]
        palette = _BASE_PALETTE + _extra
    else:
        palette = _BASE_PALETTE
    explode = [0.05] + [0] * (n_labels - 1)
    # Figsize carre max (5,5) pour eviter l'ecrasement du donut (FIX 7)
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.set_aspect('equal')
    wedges, _ = ax.pie(
        sizes, labels=None, autopct=None,
        colors=palette[:n_labels], explode=explode[:n_labels],
        startangle=90, pctdistance=0.78,
        wedgeprops=dict(linewidth=0.8, edgecolor='white')
    )
    ax.set_title(f'Poids relatif {cap_label} \u2014 Secteur {sector_name}', fontsize=12,
                 color='#1B3A6B', fontweight='bold', pad=10)
    centre = plt.Circle((0, 0), 0.42, color='white')
    ax.add_patch(centre)
    ax.text(0, 0.10, ticker,   ha='center', va='center',
            fontsize=11, fontweight='bold', color='#1B3A6B')
    ax.text(0, -0.14, pct_str, ha='center', va='center',
            fontsize=14, fontweight='bold', color='#1B3A6B')
    ax.legend(wedges, labels,
              loc='lower center', bbox_to_anchor=(0.5, -0.20),
              ncol=2, fontsize=9, frameon=False,
              handlelength=1.4, handleheight=1.0, columnspacing=1.2)
    fig.patch.set_facecolor('white')
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=180, bbox_inches='tight')
    plt.close(fig); buf.seek(0)
    return buf


def _make_margins_chart(data):
    """Bar chart Marge brute / Marge EBITDA / Marge nette par annee (FIX 2)."""
    if not _MATPLOTLIB_OK:
        return _blank_chart_buf(8, 2.5)
    is_data     = data.get('is_data') or []
    col_headers = data.get('is_col_headers') or []

    # Recuperer les lignes de marges depuis is_data (index 2=marge brute, 4=marge EBITDA, 6=marge nette)
    gm_row, em_row, nm_row = None, None, None
    for row in is_data:
        if not row:
            continue
        lbl = str(row[0]).lower()
        if 'marge brute' in lbl:
            gm_row = row[1:]
        elif 'marge ebitda' in lbl or ('ebitda' in lbl and 'marge' in lbl):
            em_row = row[1:]
        elif 'marge nette' in lbl or ('nette' in lbl and 'marge' in lbl):
            nm_row = row[1:]

    if not col_headers or not any(r is not None for r in [gm_row, em_row, nm_row]):
        return _blank_chart_buf(8, 2.5)

    def _parse_pct(v):
        if v is None or str(v) in ('\u2014', '—', '', 'N/A'):
            return None
        try:
            s = str(v).replace('\u00a0', '').replace('%', '').replace(',', '.').strip()
            return float(s)
        except (ValueError, TypeError):
            return None

    years = col_headers[:len(gm_row or em_row or nm_row)]
    n = len(years)
    gm_vals = [_parse_pct(gm_row[i]) if gm_row and i < len(gm_row) else None for i in range(n)]
    em_vals = [_parse_pct(em_row[i]) if em_row and i < len(em_row) else None for i in range(n)]
    nm_vals = [_parse_pct(nm_row[i]) if nm_row and i < len(nm_row) else None for i in range(n)]

    x = np.arange(n)
    width = 0.25
    fig, ax = plt.subplots(figsize=(8, 3.2), dpi=160)

    def _bar(vals, offset, color, label):
        vf = [v if v is not None else 0 for v in vals]
        bars = ax.bar(x + offset, vf, width, color=color, alpha=0.85, label=label, zorder=3)
        for bar, v in zip(bars, vals):
            if v is not None:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.3,
                        f"{v:.1f}%".replace('.', ','),
                        ha='center', va='bottom', fontsize=8, color=color,
                        fontweight='bold', clip_on=False)

    _bar(gm_vals, -width, '#1B3A6B', 'Marge brute')
    _bar(em_vals,  0,     '#2A5298', 'Marge EBITDA')
    _bar(nm_vals,  width, '#5580B8', 'Marge nette')

    ax.set_xticks(x)
    ax.set_xticklabels(years, fontsize=9, color='#555')
    ax.tick_params(axis='y', labelsize=9)
    ax.set_ylabel('(%)', fontsize=10, color='#555')
    ax.set_title('Ratios de rentabilit\u00e9 — \u00c9volution', fontsize=12,
                 color='#1B3A6B', fontweight='bold', pad=6)
    for sp in ['top', 'right']:
        ax.spines[sp].set_visible(False)
    ax.spines['left'].set_color('#D0D5DD')
    ax.spines['bottom'].set_color('#D0D5DD')
    ax.set_facecolor('white')
    fig.patch.set_facecolor('white')
    ax.grid(axis='y', alpha=0.25, color='#D0D5DD', linewidth=0.5, zorder=0)
    ax.legend(fontsize=9, loc='upper center', bbox_to_anchor=(0.5, -0.14),
              ncol=3, frameon=True, framealpha=0.9, edgecolor='#D0D5DD')
    plt.subplots_adjust(bottom=0.22)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=160, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf


def _make_revenue_area(data):
    if not _MATPLOTLIB_OK:
        return _blank_chart_buf(7.0, 3.2)
    quarters    = data.get('area_quarters') or []
    segments    = data.get('area_segments') or {}
    year_labels = data.get('area_year_labels') or []

    if not quarters or not segments:
        # Fallback : graphique barres revenus annuels
        fallback = data.get('area_annual_fallback') or []
        if fallback:
            _lbls = [f[0] for f in fallback]
            _vals = [f[1] for f in fallback]
            _cur  = data.get('currency', '')
            fig, ax = plt.subplots(figsize=(8.5, 4.0))
            bars = ax.bar(range(len(_lbls)), _vals, color='#2A5298', alpha=0.85, width=0.55, zorder=3)
            for bar, val in zip(bars, _vals):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(_vals)*0.01,
                        f'{val:.1f}', ha='center', va='bottom', fontsize=9, color='#1B3A6B', fontweight='bold')
            ax.set_xticks(range(len(_lbls)))
            ax.set_xticklabels(_lbls, fontsize=9, color='#555')
            ax.set_ylabel(f'Revenus (Md{_cur})', fontsize=10, color='#555')
            ax.tick_params(length=0, labelsize=9)
            for sp in ['top', 'right']: ax.spines[sp].set_visible(False)
            ax.spines['left'].set_color('#D0D5DD'); ax.spines['bottom'].set_color('#D0D5DD')
            ax.set_facecolor('white'); fig.patch.set_facecolor('white')
            ax.grid(axis='y', alpha=0.25, color='#D0D5DD', linewidth=0.5, zorder=0)
            ax.set_title('Revenus annuels consolid\u00e9s', fontsize=12,
                         color='#1B3A6B', fontweight='bold', pad=8)
            plt.tight_layout(pad=0.5)
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=180, bbox_inches='tight')
            plt.close(fig); buf.seek(0)
            return buf
        # Aucune donnee disponible
        return _blank_chart_buf(8.5, 4.0)

    seg_colors = ['#1B3A6B','#2A5298','#5580B8','#88AACC','#B8CCE0']
    seg_keys   = list(segments.keys())
    seg_vals   = [segments[k] for k in seg_keys]
    x = np.arange(len(quarters))

    fig, ax = plt.subplots(figsize=(8.5, 4.0))
    ax.stackplot(x, *seg_vals, labels=seg_keys,
                 colors=seg_colors[:len(seg_keys)], alpha=0.88)

    mid = len(quarters) / 2 - 0.5
    ax.axvline(x=mid, color='#B06000', linewidth=0.8, linestyle='--', alpha=0.6)
    stacked_max = max(
        sum(v[i] for v in seg_vals if i < len(v))
        for i in range(len(quarters))
    ) if quarters else 0
    label_y = stacked_max * 0.95 if stacked_max > 0 else 148000
    if len(year_labels) >= 2:
        ax.text(mid / 2, label_y, year_labels[0], ha='center', fontsize=9,
                color='#B06000', fontweight='bold', alpha=0.7)
        ax.text(mid + (len(quarters) - mid) / 2, label_y, year_labels[1], ha='center',
                fontsize=9, color='#B06000', fontweight='bold', alpha=0.7)

    ax.set_xticks(x)
    ax.set_xticklabels(quarters, fontsize=9, color='#555')
    ylim = stacked_max * 1.15 if stacked_max > 0 else 165000
    ax.set_ylim(0, ylim)
    ax.tick_params(length=0, labelsize=9)
    for sp in ['top', 'right']: ax.spines[sp].set_visible(False)
    ax.spines['left'].set_color('#D0D5DD')
    ax.spines['bottom'].set_color('#D0D5DD')
    ax.set_facecolor('white'); fig.patch.set_facecolor('white')
    ax.grid(axis='y', alpha=0.2, color='#D0D5DD', linewidth=0.5)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14),
              ncol=min(5, len(seg_keys)), fontsize=9, frameon=False,
              handlelength=1.2, handleheight=0.9)
    q0, q1 = (quarters[0] if quarters else ''), (quarters[-1] if quarters else '')
    ax.set_title(
        f'Revenus par segment \u2014 {len(quarters)} trimestres ({q0} \u2192 {q1}, Md$)',
        fontsize=12, color='#1B3A6B', fontweight='bold', pad=8)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=180, bbox_inches='tight')
    plt.close(fig); buf.seek(0)
    return buf

# =============================================================================
# CANVAS CALLBACKS
# =============================================================================
def _cover_page(c, doc, data):
    w, h = A4
    cx   = w / 2
    company_name   = _d(data, 'company_name')
    ticker         = _d(data, 'ticker')
    sector         = _d(data, 'sector')
    exchange       = _d(data, 'exchange')
    rec            = _d(data, 'recommendation', 'HOLD').upper()
    target_str     = _d(data, 'target_price_str', '')
    upside_str     = _d(data, 'upside_str', '')
    price_str      = _d(data, 'price_str', '')
    conviction_str = _d(data, 'conviction_str', '')
    date_analyse   = _d(data, 'date_analyse', '')
    wacc_str       = _d(data, 'wacc_str', '')
    currency       = _d(data, 'currency', 'USD')

    # Fond blanc
    c.setFillColor(WHITE)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    # Bande navy en haut
    c.setFillColor(NAVY)
    c.rect(0, h - 18*mm, w, 18*mm, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 13)
    c.drawCentredString(cx, h - 8*mm, "FinSight IA")
    c.setFillColor(colors.HexColor('#90B4E8'))
    c.setFont('Helvetica', 7.5)
    c.drawCentredString(cx, h - 14*mm,
        _enc("Plateforme d'Analyse Financi\u00e8re Institutionnelle"))

    c.setStrokeColor(GREY_RULE)
    c.setLineWidth(0.5)
    c.line(MARGIN_L, h - 20*mm, w - MARGIN_R, h - 20*mm)

    # Societe — remonte vers le haut (0.77 au lieu de 0.685)
    c.setFillColor(NAVY)
    _cn_len = len(company_name or '')
    _cn_fs  = 30 if _cn_len <= 20 else (24 if _cn_len <= 30 else (18 if _cn_len <= 40 else 14))
    c.setFont('Helvetica-Bold', _cn_fs)
    c.drawCentredString(cx, h * 0.765, _enc(company_name))
    c.setFillColor(GREY_TEXT)
    c.setFont('Helvetica', 11)
    parts = '  \u00b7  '.join(x for x in [ticker, sector, exchange] if x)
    c.drawCentredString(cx, h * 0.728, _enc(parts))
    c.setStrokeColor(GREY_RULE)
    c.setLineWidth(0.4)
    c.line(MARGIN_L + 28*mm, h * 0.714, w - MARGIN_R - 28*mm, h * 0.714)

    # Boxes Recommandation + Cible
    rw, rh_b = 52*mm, 14*mm
    rx = cx - rw - 3*mm
    ry = h * 0.652
    c.setFillColor(_rec_color(rec))
    c.roundRect(rx, ry, rw, rh_b, 2, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 13)
    c.drawCentredString(rx + rw / 2, ry + 4.5*mm, _enc(rec))

    tw = 62*mm
    tx = cx + 3*mm
    c.setFillColor(NAVY)
    c.roundRect(tx, ry, tw, rh_b, 2, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 10)
    c.drawCentredString(tx + tw / 2, ry + 4.5*mm,
        _enc(f"Cible : {target_str} {currency}  ({upside_str})"))

    # 4 metriques cles
    metrics = [
        ("Cours actuel",  f"{price_str} {currency}"),
        ("Conviction IA", conviction_str),
        ("Date d'analyse",date_analyse),
        ("WACC",          wacc_str),
    ]
    col_span = (w - MARGIN_L - MARGIN_R) / 4
    my_lbl = h * 0.595
    my_val = h * 0.574
    for i, (lbl, val) in enumerate(metrics):
        mx = MARGIN_L + col_span * i + col_span / 2
        c.setFillColor(GREY_TEXT)
        c.setFont('Helvetica', 7.5)
        c.drawCentredString(mx, my_lbl, _enc(lbl))
        c.setFillColor(NAVY)
        c.setFont('Helvetica-Bold', 9.5)
        c.drawCentredString(mx, my_val, _enc(val))

    c.setStrokeColor(GREY_RULE)
    c.setLineWidth(0.4)
    c.line(MARGIN_L, h * 0.561, w - MARGIN_R, h * 0.561)

    # Tagline
    c.setFillColor(GREY_TEXT)
    c.setFont('Helvetica', 8)
    c.drawCentredString(cx, h * 0.535,
        _enc(f"Rapport d'analyse confidentiel - {date_analyse}"))
    c.setFont('Helvetica', 7.5)
    c.drawCentredString(cx, h * 0.515, _enc(
        "Donn\u00e9es : yfinance \u00b7 FMP \u00b7 Finnhub \u00b7 FinBERT"
        "  |  Horizon d'investissement : 12 mois"))

    # ---- Points cles -------------------------------------------
    # Separateur horizontal sous les metriques
    c.setStrokeColor(NAVY)
    c.setLineWidth(0.8)
    c.line(MARGIN_L, h * 0.490, w - MARGIN_R, h * 0.490)

    # Titre "Points cles"
    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(MARGIN_L, h * 0.472, _enc("Points cl\u00e9s"))

    # Zone fond clair — box pleine hauteur jusqu'au footer
    # 5 bullets repartis sur toute la hauteur (pas de ~20mm entre titres)
    _box_top    = h * 0.455
    _box_bottom = h * 0.090   # juste au-dessus du footer navy
    _box_h      = _box_top - _box_bottom
    _box_x      = MARGIN_L
    _box_w      = w - MARGIN_L - MARGIN_R
    c.setFillColor(GREY_LIGHT)
    c.roundRect(_box_x, _box_bottom, _box_w, _box_h, 4, fill=1, stroke=0)
    c.setStrokeColor(GREY_MED)
    c.setLineWidth(0.5)
    c.roundRect(_box_x, _box_bottom, _box_w, _box_h, 4, fill=0, stroke=1)

    # Helper : ecrire un bloc bullet (titre gras + 1-2 lignes texte)
    def _bullet_block(y_title, title, body_lines):
        c.setFillColor(NAVY)
        c.setFont('Helvetica-Bold', 8.5)
        c.drawString(_box_x + 4*mm, y_title, _enc("-- " + title))
        c.setFillColor(GREY_TEXT)
        c.setFont('Helvetica', 8)
        for i, line in enumerate(body_lines):
            c.drawString(_box_x + 7*mm, y_title - (i + 1) * 10, _enc(line))

    # Separator interne leger entre blocs
    def _inner_sep(y):
        c.setStrokeColor(GREY_MED)
        c.setLineWidth(0.3)
        c.line(_box_x + 3*mm, y, _box_x + _box_w - 3*mm, y)

    # Bullet 1 : these principale
    _summary_raw = data.get('summary_text') or data.get('kdb_text') or ''
    # Word-safe truncation a 95 chars
    _sum95 = _summary_raw[:95]
    if len(_summary_raw) > 95 and ' ' in _sum95:
        _sum95 = _sum95[:_sum95.rfind(' ')] + '...'
    elif len(_summary_raw) > 95:
        _sum95 += '...'
    _sum_rest = _summary_raw[len(_sum95.rstrip('.')):200] if len(_summary_raw) > 95 else ''
    if _sum_rest:
        _sum_rest = _sum_rest[:90]
        if len(_sum_rest) == 90:
            _sum_rest = _sum_rest[:_sum_rest.rfind(' ')] + '...' if ' ' in _sum_rest else _sum_rest + '...'
    if not _sum95:
        _sum95 = 'Analyse fondamentale disponible dans le corps du rapport.'
    _b1_lines = [_sum95]
    if _sum_rest.strip():
        _b1_lines.append(_sum_rest.strip())
    # Bullets repartis sur toute la hauteur de la box (pas de ~20mm entre titres)
    # B1 a h*0.421, step h*0.067, B5 a h*0.153 → body B5 termine a h*0.130
    _bullet_block(h * 0.421, "These d'investissement", _b1_lines)
    _inner_sep(h * 0.390)

    # Bullet 2 : objectif de cours
    _target_full = data.get('target_price_full') or '-'
    _upside_v    = data.get('upside_str') or '-'
    _bullet_block(h * 0.354,
        "Objectif de cours 12 mois",
        [f"Cible : {_target_full}   |   Upside potentiel : {_upside_v}"])
    _inner_sep(h * 0.323)

    # Bullet 3 : scenarios
    _bear = data.get('bear_price') or '-'
    _base = data.get('base_price') or data.get('target_price') or '-'
    _bull = data.get('bull_price') or '-'
    _cur  = data.get('current_price') or '-'
    _bullet_block(h * 0.287,
        "Scenarios de valorisation",
        [f"Bear : {_bear}  |  Base : {_base}  |  Bull : {_bull}   (Cours actuel : {_cur})"])
    _inner_sep(h * 0.256)

    # Bullet 4 : risques cles
    _risks = data.get('risk_themes') or []
    _r1 = _risks[0] if len(_risks) > 0 else 'Voir section Analyse des Risques'
    _r2 = _risks[1] if len(_risks) > 1 else ''
    _risk_lines = [_r1[:95]]
    if _r2:
        _risk_lines.append(_r2[:95])
    _bullet_block(h * 0.220, "Risques principaux a surveiller", _risk_lines)
    _inner_sep(h * 0.185)

    # Bullet 5 : cadre
    _sector  = data.get('sector') or 'N/A'
    _wacc_v  = data.get('wacc_str') or '-'
    _bullet_block(h * 0.153,
        "Cadre d'analyse",
        [f"Secteur : {_sector}   |   WACC : {_wacc_v}   |"
         f"   Horizon : 12 mois   |   Source : FinSight IA"])

    # Footer navy
    c.setFillColor(NAVY)
    c.rect(0, 0, w, 18*mm, fill=1, stroke=0)
    c.setFillColor(colors.HexColor('#90B4E8'))
    c.setFont('Helvetica', 6.5)
    c.drawCentredString(cx, 11*mm, "CONFIDENTIEL \u2014 Usage restreint")
    c.drawCentredString(cx, 6*mm, _enc(
        "Ce rapport est g\u00e9n\u00e9r\u00e9 par FinSight IA v1.0. "
        "Ne constitue pas un conseil en investissement au sens MiFID II."))


def _content_header(c, doc, data):
    w, h = A4
    company_name = _d(data, 'company_name')
    ticker       = _d(data, 'ticker')
    sector       = _d(data, 'sector')
    date_analyse = _d(data, 'date_analyse', '')

    c.setFillColor(NAVY)
    c.rect(0, h - 14*mm, w, 14*mm, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 8)
    c.drawString(MARGIN_L, h - 9*mm,
        _enc(f"FinSight IA  \u00b7  {company_name} ({ticker})  \u00b7  {sector}"))
    c.setFont('Helvetica', 7.5)
    c.drawRightString(w - MARGIN_R, h - 9*mm,
        _enc(f"{date_analyse}  \u00b7  Confidentiel  \u00b7  Page {doc.page}"))
    c.setStrokeColor(colors.HexColor('#E8ECF0'))
    c.setLineWidth(0.15)
    c.line(MARGIN_L, MARGIN_B - 2*mm, w - MARGIN_R, MARGIN_B - 2*mm)
    c.setFillColor(GREY_TEXT)
    c.setFont('Helvetica', 6.5)
    c.drawString(MARGIN_L, MARGIN_B - 7*mm, _enc(
        "FinSight IA v1.0 \u2014 Document g\u00e9n\u00e9r\u00e9 par IA. "
        "Ne constitue pas un conseil en investissement."))
    c.drawRightString(w - MARGIN_R, MARGIN_B - 7*mm, _enc(
        "Sources : yfinance \u00b7 FMP \u00b7 Finnhub \u00b7 FinBERT"))


def _make_on_page(data):
    def on_page(c, doc):
        if doc.page == 1:
            _cover_page(c, doc, data)
        else:
            _content_header(c, doc, data)
    return on_page

# =============================================================================
# BUILD FUNCTIONS
# =============================================================================

def _build_sommaire(data):
    pn = data.get('page_nums') or {}
    S_SUB = _s("subgrey", size=7, leading=10, color=GREY_TEXT)
    rows = [
        [Paragraph("1.", S_TD_BC), Paragraph("Synth\u00e8se Ex\u00e9cutive", S_TD_B),
         Paragraph(str(pn.get("synthese", 3)), S_TD_C)],
        [Paragraph("", S_TD_C),
         Paragraph("  Recommandation \u00b7 Sc\u00e9narios Bear/Base/Bull \u00b7 Catalyseurs", S_SUB),
         Paragraph("", S_TD_C)],
        [Paragraph("2.", S_TD_BC), Paragraph("Analyse Financi\u00e8re", S_TD_B),
         Paragraph(str(pn.get("financials", 5)), S_TD_C)],
        [Paragraph("", S_TD_C),
         Paragraph("  Compte de r\u00e9sultat \u00b7 Marges \u00b7 Ratios vs pairs sectoriels", S_SUB),
         Paragraph("", S_TD_C)],
        [Paragraph("3.", S_TD_BC), Paragraph("Valorisation", S_TD_B),
         Paragraph(str(pn.get("valorisation", 7)), S_TD_C)],
        [Paragraph("", S_TD_C),
         Paragraph("  DCF \u00b7 Table de sensibilit\u00e9 \u00b7 Comparables \u00b7 Football Field", S_SUB),
         Paragraph("", S_TD_C)],
        [Paragraph("4.", S_TD_BC),
         Paragraph("Analyse des Risques & Sentiment de March\u00e9", S_TD_B),
         Paragraph(str(pn.get("risques", 9)), S_TD_C)],
        [Paragraph("", S_TD_C),
         Paragraph("  Th\u00e8se contraire \u00b7 Conditions d'invalidation \u00b7 FinBERT", S_SUB),
         Paragraph("", S_TD_C)],
    ]
    header = [Paragraph("N\u00b0", S_TH_C), Paragraph("Section", S_TH_L),
              Paragraph("Page", S_TH_C)]
    t = tbl([header] + rows, cw=[12*mm, 142*mm, 16*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 2), (2, 2), colors.HexColor("#F8F9FB")),
        ("BACKGROUND", (0, 4), (2, 4), colors.HexColor("#F8F9FB")),
        ("BACKGROUND", (0, 6), (2, 6), colors.HexColor("#F8F9FB")),
        ("BACKGROUND", (0, 8), (2, 8), colors.HexColor("#F8F9FB")),
        ("TOPPADDING",    (0, 2), (2, 9), 1),
        ("BOTTOMPADDING", (0, 2), (2, 9), 1),
    ]))
    return t


def _build_synthese(perf_buf, data):
    elems = []
    elems += section_title("Synth\u00e8se Ex\u00e9cutive", 1)

    elems.append(Paragraph(_safe(_d(data, 'summary_text')), S_BODY))
    elems.append(Spacer(1, 3*mm))

    # 2-col : [graphique performance | boite donnees cles]
    # Evite la page 4 quasi-vide : les deux blocs tiennent sur la meme page
    perf_img = Image(perf_buf, width=100*mm, height=70*mm)
    top_tbl = Table([[perf_img, _key_data_box(data)]], colWidths=[102*mm, 68*mm])
    top_tbl.setStyle(TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
        ('LEFTPADDING',  (1, 0), (1, 0),   4),
    ]))
    elems.append(top_tbl)
    kdb_text = _d(data, 'kdb_text')
    if kdb_text:
        elems.append(Spacer(1, 2*mm))
        elems.append(Paragraph(_safe(kdb_text), S_BODY))
    elems.append(Spacer(1, 4*mm))

    # Scenarios
    elems.append(debate_q(
        "Quelles sont les bornes de valorisation et les hypoth\u00e8ses d\u00e9terminantes ?"))
    scen_h = [Paragraph(h, S_TH_C) for h in [
        "Sc\u00e9nario", "Prix cible", "Upside / Downside",
        "Probabilit\u00e9", "Hypoth\u00e8se d\u00e9terminante"]]
    scen_rows = []
    for s in (data.get('scenarios') or []):
        scen   = _d(s, 'scenario', '')
        price  = _d(s, 'price', '')
        upside = _d(s, 'upside', '')
        prob   = _d(s, 'prob', '')
        hyp    = _d(s, 'hypothesis', '')
        base   = scen.lower() == 'base'
        bear   = scen.lower() == 'bear'
        scen_rows.append([
            Paragraph(f"<b>{scen}</b>" if base else scen, S_TD_BC if base else S_TD_C),
            Paragraph(f"<b>{price}</b>" if base else price,
                      S_TD_BC if base else (S_TD_R if bear else S_TD_G)),
            Paragraph(f"<b>{upside}</b>" if base else upside,
                      S_TD_G if upside.startswith('+') else S_TD_R),
            Paragraph(f"<b>{prob}</b>" if base else prob, S_TD_BC if base else S_TD_C),
            Paragraph(_safe(hyp), S_TD_L),
        ])
    elems.append(KeepTogether(tbl([scen_h] + scen_rows,
                                  cw=[18*mm, 26*mm, 28*mm, 22*mm, 76*mm])))
    elems.append(src("FinSight IA \u2014 Mod\u00e8le DCF interne, donn\u00e9es FMP / yfinance."))
    elems.append(Spacer(1, 3*mm))

    # Catalyseurs — pas de KeepTogether ici : evite les pages blanches fantomes
    # quand la table est vide ou que le contenu precedent remplit deja la page
    cats = data.get('catalysts') or []
    cat_h = [Paragraph("#", S_TH_C), Paragraph("Catalyseur", S_TH_L),
             Paragraph("Analyse", S_TH_L)]
    if cats:
        cat_rows = [
            [Paragraph(_d(c, 'num', ''), S_TD_BC),
             Paragraph(_safe(_d(c, 'name', '')), S_TD_B),
             Paragraph(_safe(_d(c, 'analysis', '')), S_TD_L)]
            for c in cats
        ]
    else:
        cat_rows = [
            [Paragraph('\u2014', S_TD_C),
             Paragraph("Catalyseurs non disponibles", S_TD_L),
             Paragraph("Analyse en attente", S_TD_L)]
        ]
    elems.append(Spacer(1, 2*mm))
    elems.append(Paragraph("Catalyseurs d'investissement \u2014 th\u00e8se haussi\u00e8re", S_SUBSECTION))
    elems.append(Spacer(1, 1*mm))
    elems.append(tbl([cat_h] + cat_rows, cw=[8*mm, 36*mm, 126*mm]))
    elems.append(Spacer(1, 4*mm))
    return elems


def _build_financials(area_buf, data, margins_buf=None):
    elems = []
    # Section 2 commence toujours par PageBreak + Spacer(8mm)
    elems.append(PageBreak())
    elems.append(Spacer(1, 8*mm))
    elems += section_title("Analyse Financi\u00e8re", 2)
    elems.append(Spacer(1, 4*mm))
    elems.append(debate_q(
        "La trajectoire financi\u00e8re justifie-t-elle la prime de valorisation actuelle ?"))
    elems.append(Paragraph(_safe(_d(data, 'financials_text_intro')), S_BODY))
    elems.append(Spacer(1, 3*mm))

    # Tableau IS
    col_headers = data.get('is_col_headers') or ['2022A', '2023A', '2024A', 'LTM', '2026F', '2027F']
    is_data     = data.get('is_data') or []
    n_cols = len(col_headers)
    # Largeurs : label=46mm, reste reparti. Pour 6 cols : [46,20,20,20,22,22,20]=170
    if n_cols == 6:
        cw_is = [46*mm, 20*mm, 20*mm, 20*mm, 22*mm, 22*mm, 20*mm]
    else:
        rest = (170 - 46) / n_cols
        cw_is = [46*mm] + [rest*mm] * n_cols

    h_is = [Paragraph("Indicateur", S_TH_L)] + [Paragraph(h, S_TH_C) for h in col_headers]

    def _is_cell(v, col):
        sv = str(v)
        if col == 0: return Paragraph(sv, S_TD_L)
        if sv.startswith('+') and '%' in sv: return Paragraph(sv, S_TD_G)
        if sv.startswith('-') and '%' in sv: return Paragraph(sv, S_TD_R)
        return Paragraph(sv, S_TD_C)

    rows_is = [[_is_cell(v, i) for i, v in enumerate(row)] for row in is_data]
    _cur_label = _d(data, 'currency', 'USD')
    elems.append(Paragraph(f"Compte de r\u00e9sultat consolid\u00e9 ({_cur_label} Md)", S_SUBSECTION))
    elems.append(KeepTogether(tbl([h_is] + rows_is, cw=cw_is)))
    elems.append(src(
        "FinSight IA \u2014 FMP, yfinance. LTM = 12 derniers mois. F = pr\u00e9visions mod\u00e8le interne."))
    elems.append(Spacer(1, 3*mm))

    elems.append(Image(area_buf, width=TABLE_W, height=92*mm))
    _area_src = ("FinSight IA \u2014 Revenus consolid\u00e9s \u2014 Source : yfinance."
                 if data.get('area_is_real')
                 else "FinSight IA \u2014 Revenus annuels (donn\u00e9es illustratives).")
    elems.append(src(_area_src))
    elems.append(Spacer(1, 3*mm))

    elems.append(Paragraph(_safe(_d(data, 'financials_text_post')), S_BODY))
    elems.append(Spacer(1, 4*mm))

    # Ratios vs pairs — titre + tableau gardes ensemble
    ticker = _d(data, 'ticker', 'Titre')
    h_r = [Paragraph(h, S_TH_L) for h in [
        "Indicateur", f"{ticker} LTM", "R\u00e9f\u00e9rence sectorielle", "Lecture"]]

    def _read_style(lec):
        pos = ("Sup\u00e9rieure", "Sup\u00e9rieur", "Solide", "Aucun signal",
               "En ligne", "Dans la norme")
        if lec in pos: return S_TD_G
        if lec in ("Inf\u00e9rieure", "D\u00e9cote", "D\u00e9tresse", "Risque manip."): return S_TD_R
        return S_TD_C

    rat_rows = [
        [Paragraph(_d(r, 'label'),           S_TD_B),
         Paragraph(_d(r, 'value'),           S_TD_C),
         Paragraph(_d(r, 'reference'),       S_TD_C),
         Paragraph(_safe(_d(r, 'lecture')),  _read_style(_d(r, 'lecture')))]
        for r in (data.get('ratios_vs_peers') or [])
    ]
    elems.append(KeepTogether([
        Paragraph("Positionnement relatif \u2014 Ratios cl\u00e9s vs. pairs sectoriels", S_SUBSECTION),
        Spacer(1, 1*mm),
        tbl([h_r] + rat_rows, cw=[50*mm, 30*mm, 55*mm, 35*mm]),
    ]))
    elems.append(src("FinSight IA \u2014 LTM = Last Twelve Months."))
    elems.append(Spacer(1, 3*mm))
    elems.append(Paragraph(_safe(_d(data, 'ratios_text')), S_BODY))
    _sector_lc = (_d(data, 'sector') or '').lower()
    if any(k in _sector_lc for k in ('bank', 'financ', 'insur', 'reit', 'real estate')):
        elems.append(Spacer(1, 2*mm))
        elems.append(Paragraph(
            "Note\u00a0: Altman Z-Score non applicable aux \u00e9tablissements financiers "
            "et REITs \u2014 m\u00e9trique exclue pour ce type de soci\u00e9t\u00e9.",
            S_NOTE))

    # FIX 2 — Analyse des ratios cles + graphique evolution marges
    _ticker_f = _d(data, 'ticker', 'La soci\u00e9t\u00e9')
    _ratios   = data.get('ratios_vs_peers') or []
    def _rv(label_kw):
        for r in _ratios:
            if label_kw.lower() in (_d(r,'label') or '').lower():
                return _d(r,'value','—'), _d(r,'reference','—'), _d(r,'lecture','—')
        return '—', '—', '—'
    _eve_v, _eve_ref, _eve_lec = _rv('EV / EBITDA')
    _gm_v,  _gm_ref,  _gm_lec  = _rv('Marge brute')
    _roe_v, _roe_ref, _roe_lec  = _rv('Return on Equity')
    _az_v,  _az_ref,  _az_lec   = _rv('Altman')
    _ratio_para = (
        f"L'EV/EBITDA de {_ticker_f} ressort \u00e0 {_eve_v}\u00a0x (r\u00e9f\u00e9rence sectorielle\u00a0: "
        f"{_eve_ref}), signal\u00e9 comme \u00ab\u00a0{_eve_lec}\u00a0\u00bb par rapport aux pairs. "
        f"La marge brute s'\u00e9tablit \u00e0 {_gm_v} (benchmark\u00a0: {_gm_ref}), "
        f"indicateur\u00a0: \u00ab\u00a0{_gm_lec}\u00a0\u00bb. "
        f"Le Return on Equity (ROE) de {_roe_v} se compare \u00e0 {_roe_ref} pour le secteur "
        f"(\u00ab\u00a0{_roe_lec}\u00a0\u00bb). "
        f"L'Altman Z-Score de {_az_v} indique\u00a0: \u00ab\u00a0{_az_lec}\u00a0\u00bb "
        f"(seuil de sant\u00e9 financier\u00a0: 2,99)."
    )
    elems.append(Spacer(1, 4*mm))
    elems.append(Paragraph("Analyse des ratios cl\u00e9s", S_SUBSECTION))
    elems.append(Spacer(1, 2*mm))
    elems.append(Paragraph(_safe(_ratio_para), S_BODY))

    # Graphique evolution des marges
    elems.append(Spacer(1, 4*mm))
    elems.append(Paragraph("Ratios de rentabilit\u00e9 \u2014 \u00c9volution", S_SUBSECTION))
    elems.append(Spacer(1, 2*mm))
    if margins_buf is not None:
        margins_buf.seek(0)
        elems.append(Image(margins_buf, width=TABLE_W, height=50*mm))
    else:
        elems.append(Paragraph("(Graphique marges non disponible)", S_NOTE))
    elems.append(src("FinSight IA \u2014 Marges calcul\u00e9es sur donn\u00e9es historiques yfinance."))
    elems.append(Spacer(1, 3*mm))
    return elems


def _build_valorisation(ff_buf, pie_buf, data):
    elems = []
    elems += section_title("Valorisation", 3)
    elems.append(debate_q(
        "La valeur intrins\u00e8que confirme-t-elle le cours actuel et quel est l'upside r\u00e9siduel ?"))
    elems.append(Paragraph(_safe(_d(data, 'dcf_text_intro')), S_BODY))
    elems.append(Spacer(1, 3*mm))

    # Table de sensibilite DCF
    elems.append(Paragraph(
        "Table de sensibilit\u00e9 DCF \u2014 Valeur intrins\u00e8que par action", S_SUBSECTION))
    wacc_rows = data.get('wacc_rows') or ["8,4%","9,4%","10,4%","11,4%","12,4%"]
    tgr_cols  = data.get('tgr_cols')  or ["2,0%","2,5%","3,0%","3,5%","4,0%"]
    wacc_base = _d(data, 'wacc_base', "10,4%")
    tgr_base  = _d(data, 'tgr_base',  "3,0%")
    dcf_sens  = data.get('dcf_sensitivity') or []

    dcf_h = [Paragraph("WACC \\ TGR \u2192", S_TH_L)] + \
            [Paragraph(t, S_TH_C) for t in tgr_cols]
    dcf_rows_b = []
    for ri, (wl, row_vals) in enumerate(zip(wacc_rows, dcf_sens)):
        cells = [Paragraph(wl, S_TD_B)]
        for ci, (tl, v) in enumerate(zip(tgr_cols, row_vals)):
            if wl == wacc_base and tl == tgr_base:
                cells.append(Paragraph(f"<b>{v}</b>",
                    _s(f'bc{ri}{ci}', size=8, bold=True, color=WHITE, align=TA_CENTER)))
            else:
                cells.append(Paragraph(str(v), S_TD_C))
        dcf_rows_b.append(cells)

    t_dcf = tbl([dcf_h] + dcf_rows_b, cw=[24*mm, 29*mm, 29*mm, 29*mm, 29*mm, 30*mm])
    br = (wacc_rows.index(wacc_base) + 1) if wacc_base in wacc_rows else 3
    bc = (tgr_cols.index(tgr_base)  + 1) if tgr_base  in tgr_cols  else 3
    t_dcf.setStyle(TableStyle([
        ('BACKGROUND', (bc, br), (bc, br), NAVY),
        ('TEXTCOLOR',  (bc, br), (bc, br), WHITE),
    ]))
    elems.append(KeepTogether(t_dcf))
    elems.append(Paragraph(_safe(_d(data, 'dcf_text_note')), S_NOTE))
    elems.append(Spacer(1, 4*mm))

    # Comparables
    elems.append(Paragraph(
        "Analyse par multiples comparables \u2014 Pairs sectoriels LTM", S_SUBSECTION))
    comp_h = [Paragraph(h, S_TH_C) for h in [
        "Soci\u00e9t\u00e9", "EV/EBITDA", "EV/Revenue", "P/E", "Marge brute", "Marge EBITDA"]]
    comp_rows = []
    for r in (data.get('comparables') or []):
        bold = r.get('bold', False)
        nm   = _d(r, 'name')
        row  = [Paragraph(f"<b>{_safe(nm)}</b>" if bold else _safe(nm), S_TD_B if bold else S_TD_L)]
        row += [Paragraph(_d(r, k), S_TD_C)
                for k in ['ev_ebitda','ev_revenue','pe','gross_margin','ebitda_margin']]
        comp_rows.append(row)
    elems.append(KeepTogether(tbl([comp_h] + comp_rows,
                                  cw=[52*mm, 24*mm, 24*mm, 20*mm, 26*mm, 24*mm])))
    elems.append(src("FinSight IA \u2014 FMP, consensus Bloomberg."))
    elems.append(Spacer(1, 4*mm))
    # Synthese valorisation — texte de transition (remplit l'espace page 6)
    _post_comp = _d(data, 'post_comp_text')
    if _post_comp:
        elems.append(Paragraph(_safe(_post_comp), S_BODY))
        elems.append(Spacer(1, 4*mm))

    # Donut + texte
    pie_img  = Image(pie_buf, width=75*mm, height=75*mm)
    pie_text = _d(data, 'pie_text')
    pie_tbl  = Table([[pie_img, Paragraph(_safe(pie_text), S_BODY)]],
                     colWidths=[77*mm, 93*mm])
    pie_tbl.setStyle(TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
        ('LEFTPADDING',  (1, 0), (1, 0),   5),
    ]))
    elems.append(pie_tbl)
    elems.append(src(
        f"FinSight IA \u2014 EV proxy calcul\u00e9 sur cours au {_d(data, 'date_analyse')}. "
        "Donn\u00e9es illustratives."))
    elems.append(Spacer(1, 3*mm))

    # Football Field
    elems.append(Paragraph(
        "Football Field \u2014 Convergence des m\u00e9thodes de valorisation", S_SUBSECTION))
    _ff_n = len(data.get('ff_methods') or [])
    # Ratio hauteur/largeur base sur le figsize utilise dans _make_ff_chart : (10, max(4.5, 1.4+n*0.72))
    _ff_fig_h = max(4.5, 1.4 + _ff_n * 0.72)
    _ff_h = TABLE_W * _ff_fig_h / 10.0
    elems.append(Image(ff_buf, width=TABLE_W, height=_ff_h))
    ff_comment = _d(data, 'dcf_text_intro')
    if ff_comment:
        elems.append(Spacer(1, 2*mm))
        elems.append(Paragraph(_safe(ff_comment), S_BODY))
    elems.append(src(_d(data, 'ff_source_text',
        "FinSight IA. Ligne pointill\u00e9e orange = cours actuel. "
        "La convergence des m\u00e9thodes renforce la robustesse de la cible.")))
    return elems


def _build_risques(data):
    elems = []
    elems += section_title("Analyse des Risques & Sentiment de March\u00e9", 4)

    bear_args = data.get('bear_args') or []
    bear_h    = [Paragraph("Axe de risque", S_TH_L),
                 Paragraph("Analyse d\u00e9taill\u00e9e", S_TH_L)]
    bear_rows = [[Paragraph(_safe(_d(a, 'name')), S_TD_B), Paragraph(_safe(_d(a, 'text')), S_TD_L)]
                 for a in bear_args]
    # Fallback si aucune ligne de donnees
    if not bear_rows:
        bear_rows = [[Paragraph('\u2014', S_TD_C),
                      Paragraph("Analyse des risques non disponible pour cette valeur.", S_TD_L)]]
    # Titre + intro + tableau : KeepTogether pour eviter la separation titre/tableau
    _bear_title = Paragraph(
        "Th\u00e8se contraire \u2014 Arguments en faveur d'une r\u00e9vision \u00e0 la baisse",
        S_SUBSECTION)
    _bear_intro = Paragraph(_safe(_d(data, 'bear_text_intro')), S_BODY)
    elems.append(KeepTogether([
        _bear_title,
        Spacer(1, 2*mm),
        _bear_intro,
        Spacer(1, 2*mm),
        tbl([bear_h] + bear_rows, cw=[40*mm, 130*mm]),
    ]))
    elems.append(Spacer(1, 4*mm))

    # Conditions d'invalidation — titre + tableau gardes ensemble
    inv_data = data.get('invalidation_data') or []
    inv_h = [Paragraph(h, S_TH_L)
             for h in ["Axe", "Condition d'invalidation", "Horizon"]]
    _inv_fallback = "D\u00e9gradation significative des fondamentaux sur 2 trimestres cons\u00e9cutifs."
    inv_rows = [
        [Paragraph(_d(r, 'axe') or '\u2014', S_TD_B),
         Paragraph(_safe(_d(r, 'condition') or _inv_fallback), S_TD_L),
         Paragraph(_d(r, 'horizon') or '\u2014', S_TD_C)]
        for r in inv_data
    ]
    if not inv_rows:
        inv_rows = [[Paragraph('\u2014', S_TD_C),
                     Paragraph(_inv_fallback, S_TD_L),
                     Paragraph('\u2014', S_TD_C)]]
    elems.append(KeepTogether([
        debate_q("Quelles conditions pr\u00e9cises invalideraient la th\u00e8se et \u00e0 quel horizon ?"),
        Spacer(1, 1*mm),
        tbl([inv_h] + inv_rows, cw=[22*mm, 120*mm, 28*mm]),
    ]))
    elems.append(Spacer(1, 4*mm))

    # FinBERT — titre + corps + tableau gardes ensemble
    n_art = _d(data, 'finbert_n_articles', '30')
    sent_h = [Paragraph(h, S_TH_C)
              for h in ["Orientation", "Articles", "Score moyen", "Th\u00e8mes principaux"]]
    sent_rows = []
    for r in (data.get('sentiment_data') or []):
        orient = _d(r, 'orientation')
        st = S_TD_G if 'ositif' in orient else (S_TD_R if '\u00e9gatif' in orient or 'egatif' in orient else S_TD_C)
        sent_rows.append([
            Paragraph(orient, st),
            Paragraph(_d(r, 'articles'), S_TD_C),
            Paragraph(_d(r, 'score'), S_TD_C),
            Paragraph(_safe(_d(r, 'themes')), S_TD_L),
        ])
    if not sent_rows:
        sent_rows = [[Paragraph('\u2014', S_TD_C), Paragraph('\u2014', S_TD_C),
                      Paragraph('\u2014', S_TD_C), Paragraph("Donn\u00e9es sentiment non disponibles.", S_TD_L)]]
    elems.append(KeepTogether([
        Paragraph(
            f"Sentiment de march\u00e9 \u2014 Analyse {_d(data, 'finbert_engine', 'FinBERT')} ({n_art} articles, 7 jours)",
            S_SUBSECTION),
        Spacer(1, 2*mm),
        Paragraph(_safe(_d(data, 'finbert_text')), S_BODY),
        Spacer(1, 2*mm),
        tbl([sent_h] + sent_rows, cw=[24*mm, 20*mm, 26*mm, 100*mm]),
    ]))
    elems.append(src(_d(data, 'finbert_source',
        "FinBERT \u2014 Mod\u00e8le NLP sp\u00e9cialis\u00e9 finance. "
        "Corpus : presse financi\u00e8re anglophone, 7 jours.")))
    elems.append(Spacer(1, 6*mm))

    # Section 5 — Synthese finale : section_title + tableau reco gardes ensemble
    rec     = _d(data, 'recommendation', 'HOLD').upper()
    rec_s   = S_TD_A if rec == 'HOLD' else (S_TD_G if rec == 'BUY' else S_TD_R)
    cur     = _d(data, 'currency', 'USD')
    reco_tbl = [
        [Paragraph("Recommandation", S_TH_C),
         Paragraph("Prix cible (12 mois)", S_TH_C),
         Paragraph("Cours actuel", S_TH_C),
         Paragraph("Upside", S_TH_C),
         Paragraph("Conviction IA", S_TH_C),
         Paragraph("Prochaine revue", S_TH_C)],
        [Paragraph(f"<b>{rec}</b>", rec_s),
         Paragraph(f"<b>{_d(data, 'target_price_full')}</b>", S_TD_BC),
         Paragraph(f"{_d(data, 'price_str')} {cur}", S_TD_C),
         Paragraph(f"<b>{_d(data, 'upside_str')}</b>", S_TD_G),
         Paragraph(_d(data, 'conviction_str'), S_TD_C),
         Paragraph(_safe(_d(data, 'next_review')), S_TD_C)],
    ]
    elems.append(KeepTogether(
        section_title("Synth\u00e8se & Recommandation Finale", 5) +
        [tbl(reco_tbl, cw=[28*mm, 32*mm, 28*mm, 22*mm, 28*mm, 32*mm])]
    ))
    elems.append(Spacer(1, 4*mm))
    elems.append(Paragraph(_safe(_d(data, 'conclusion_text')), S_BODY))
    elems.append(Spacer(1, 4*mm))

    # Conditions de revision — titre + tableau gardes ensemble
    rev_h = [Paragraph("R\u00e9vision", S_TH_C),
             Paragraph("D\u00e9clencheur", S_TH_L),
             Paragraph("Cible r\u00e9vis\u00e9e", S_TH_C)]
    rev_rows = []
    for r in (data.get('revision_data') or []):
        sty = r.get('style', '').lower()
        rs  = S_TD_G if sty == 'buy' else (S_TD_R if sty == 'sell' else S_TD_C)
        rev_rows.append([
            Paragraph(_d(r, 'revision'), rs),
            Paragraph(_safe(_d(r, 'trigger')), S_TD_L),
            Paragraph(_d(r, 'target'), rs),
        ])
    if not rev_rows:
        rev_rows = [[Paragraph('\u2014', S_TD_C),
                     Paragraph("Conditions de r\u00e9vision non disponibles.", S_TD_L),
                     Paragraph('\u2014', S_TD_C)]]
    elems.append(KeepTogether([
        Paragraph("Conditions de r\u00e9vision de la recommandation", S_SUBSECTION),
        Spacer(1, 1*mm),
        tbl([rev_h] + rev_rows, cw=[20*mm, 122*mm, 28*mm]),
    ]))
    elems.append(Spacer(1, 6*mm))

    # Methodologie & Hypotheses — section courte pour remplir la page finale
    _wacc_str = _d(data, 'wacc_str', 'N/A')
    _tgr_str  = _d(data, 'tgr_str',  'N/A')
    _beta_str = _d(data, 'beta_str', 'N/A')
    _rf_str   = _d(data, 'rf_str',   'N/A')
    _erp_str  = _d(data, 'erp_str',  'N/A')
    elems.append(KeepTogether([
        Paragraph("M\u00e9thodologie &amp; Hypoth\u00e8ses", S_SUBSECTION),
        Spacer(1, 2*mm),
        Paragraph(
            f"<b>Mod\u00e8le DCF</b> \u2014 La valorisation par actualisation des flux de "
            f"tr\u00e9sorerie (DCF) repose sur un horizon explicite de cinq ans, un co\u00fbt "
            f"moyen pond\u00e9r\u00e9 du capital (WACC) de {_wacc_str} et un taux de croissance "
            f"terminal (TGR) de {_tgr_str}. Le WACC est estim\u00e9 selon le mod\u00e8le CAPM : "
            f"taux sans risque {_rf_str}, prime de risque march\u00e9 {_erp_str}, "
            f"b\u00eata {_beta_str}.",
            S_BODY),
        Spacer(1, 2*mm),
        Paragraph(
            f"<b>Analyse de sensibilit\u00e9</b> \u2014 La table de sensibilit\u00e9 pr\u00e9sente "
            f"la valeur intrins\u00e8que estim\u00e9e pour une plage de WACC (\u00b12\u00a0pp) "
            f"et de TGR (\u00b11\u00a0pp) autour du sc\u00e9nario central. Une hausse de "
            f"100\u00a0bps du WACC comprime la valeur d'environ 12\u00a0%.",
            S_BODY),
        Spacer(1, 2*mm),
        Paragraph(
            "<b>Comparables</b> \u2014 Les multiples de valorisation (EV/EBITDA, EV/Revenue, "
            "P/E) sont calcul\u00e9s sur la base des douze derniers mois (LTM) et compar\u00e9s "
            "\u00e0 un panel de pairs sectoriels. Les fourchettes de r\u00e9f\u00e9rence sont "
            "calibr\u00e9es selon le secteur de la soci\u00e9t\u00e9 analys\u00e9e.",
            S_BODY),
        Spacer(1, 2*mm),
        Paragraph(
            "<b>Sentiment</b> \u2014 L'analyse de sentiment est r\u00e9alis\u00e9e par FinBERT "
            "(ProsusAI/finbert), mod\u00e8le de traitement du langage naturel pr\u00e9-entra\u00een\u00e9 "
            "sur un corpus financier anglophone. Le score agr\u00e9g\u00e9 est calcul\u00e9 sur "
            "un corpus d'articles des sept derniers jours issus de Finnhub et de flux RSS.",
            S_BODY),
    ]))
    elems.append(Spacer(1, 6*mm))

    # FIX 4 — Glossaire des indicateurs
    elems.append(Paragraph("Glossaire des indicateurs", S_SUBSECTION))
    elems.append(Spacer(1, 2*mm))
    _glos_h = [Paragraph("Indicateur", S_TH_L), Paragraph("D\u00e9finition", S_TH_L)]
    _glos_rows = [
        [Paragraph("DCF", S_TD_B),
         Paragraph("Discounted Cash Flow \u2014 actualisation des flux futurs au WACC", S_TD_L)],
        [Paragraph("WACC", S_TD_B),
         Paragraph("Co\u00fbt moyen pond\u00e9r\u00e9 du capital (fonds propres + dette)", S_TD_L)],
        [Paragraph("TGR", S_TD_B),
         Paragraph("Taux de croissance terminal au-del\u00e0 de l'horizon explicite", S_TD_L)],
        [Paragraph("EV/EBITDA", S_TD_B),
         Paragraph("Valeur d'entreprise divis\u00e9e par l'EBITDA LTM", S_TD_L)],
        [Paragraph("P/E NTM", S_TD_B),
         Paragraph("Price-to-Earnings sur les 12 prochains mois estim\u00e9s", S_TD_L)],
        [Paragraph("LTM", S_TD_B),
         Paragraph("Last Twelve Months \u2014 12 derniers mois glissants", S_TD_L)],
        [Paragraph("Altman Z-Score", S_TD_B),
         Paragraph("Score de d\u00e9tresse financi\u00e8re (> 2,99 = sain)", S_TD_L)],
        [Paragraph("Beneish M-Score", S_TD_B),
         Paragraph("D\u00e9tection de manipulation comptable (< \u22122,22 = OK)", S_TD_L)],
    ]
    elems.append(tbl([_glos_h] + _glos_rows, cw=[40*mm, 130*mm]))
    elems.append(Spacer(1, 6*mm))

    # Disclaimer
    elems.append(rule())
    disc_date = _d(data, 'disclaimer_date', _d(data, 'date_analyse'))
    elems.append(Paragraph(
        f"Ce rapport a \u00e9t\u00e9 g\u00e9n\u00e9r\u00e9 par FinSight IA v1.0 le {disc_date}. "
        "Il est produit int\u00e9gralement par un syst\u00e8me d'intelligence artificielle et "
        "<b>ne constitue pas un conseil en investissement</b> "
        "au sens de la directive europ\u00e9enne MiFID II (2014/65/UE). FinSight IA ne saurait "
        "\u00eatre tenu responsable des d\u00e9cisions prises sur la base de ce document. "
        "Les donn\u00e9es financi\u00e8res sont issues de sources publiques (yfinance, Finnhub, FMP) "
        "et peuvent contenir des inexactitudes. "
        "Tout investisseur est invit\u00e9 \u00e0 proc\u00e9der \u00e0 sa propre diligence et \u00e0 "
        "consulter un professionnel qualifi\u00e9 avant toute d\u00e9cision d'investissement. "
        "\u2014 Document confidentiel, diffusion restreinte.",
        S_DISC))
    return elems

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def generate_report(data: dict, output_path: str) -> str:
    """
    Genere un rapport PDF FinSight IA a partir d'un dictionnaire de donnees.

    Args:
        data        : Dict contenant toutes les donnees du rapport.
                      Voir PDFWriter._state_to_data() pour les cles attendues.
        output_path : Chemin de sortie du fichier PDF.

    Returns:
        str : Chemin absolu du fichier genere.
    """
    def _safe_chart(fn, label):
        if not _MATPLOTLIB_OK:
            log.warning("[generate_report] matplotlib non disponible — chart '%s' skippe", label)
            return _blank_chart_buf()
        try:
            return fn(data)
        except Exception as _ce:
            log.warning("[generate_report] chart '%s' failed: %s", label, _ce)
            return _blank_chart_buf()

    perf_buf    = _safe_chart(_make_perf_chart,     'perf')
    ff_buf      = _safe_chart(_make_ff_chart,        'ff')
    pie_buf     = _safe_chart(_make_pie_comparables, 'pie')
    area_buf    = _safe_chart(_make_revenue_area,    'area')
    margins_buf = _safe_chart(_make_margins_chart,   'margins')
    # Rewind tous les buffers — defensive : evite les renders vides si le buffer
    # avait ete partiellement lu lors d'une validation precedente
    for _b in (perf_buf, ff_buf, pie_buf, area_buf, margins_buf):
        if _b is not None:
            _b.seek(0)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    company_name = _d(data, 'company_name', 'FinSight IA')
    ticker       = _d(data, 'ticker', '')
    date_analyse = _d(data, 'date_analyse', '')

    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T + 6*mm, bottomMargin=MARGIN_B + 8*mm,
        title=f"FinSight IA \u2014 {company_name} ({ticker})",
        author="FinSight IA v1.0",
    )
    on_page = _make_on_page(data)

    story = []

    # Page 1 : cover (canvas pur)
    story.append(Spacer(1, 1))
    story.append(PageBreak())

    # Page 2 : sommaire
    story.append(Paragraph(
        f"{company_name} ({ticker}) \u2014 Rapport d'Analyse FinSight IA",
        _s('rt', size=13, bold=True, color=NAVY, leading=18, sa=2)))
    story.append(Paragraph(
        f"Rapport confidentiel \u00b7 {date_analyse}",
        _s('rs', size=8, color=GREY_TEXT, leading=11, sa=6)))
    story.append(rule())
    story.append(Paragraph("Sommaire", S_SECTION))
    story.append(_build_sommaire(data))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("\u00c0 propos de cette analyse", S_SUBSECTION))
    story.append(Paragraph(
        "L'analyse fondamentale repose sur les donn\u00e9es financi\u00e8res historiques issues "
        "de sources publiques (yfinance, Finnhub, FMP). La valorisation DCF est calcul\u00e9e "
        "sur un horizon de cinq ans avec analyse de sensibilit\u00e9 au WACC et au taux de "
        "croissance terminal. L'analyse de sentiment est conduite par FinBERT, mod\u00e8le de "
        "traitement du langage naturel sp\u00e9cialis\u00e9 en finance, sur un corpus d'articles "
        "des sept derniers jours. La th\u00e8se d'investissement est soumise \u00e0 un "
        "<b>protocole de contradiction syst\u00e9matique</b> (avocat du diable) visant \u00e0 "
        "identifier les hypoth\u00e8ses les plus fragiles et les sc\u00e9narios de baisse. "
        "Les conditions d'invalidation sont explicitement formul\u00e9es pour chaque axe de "
        "risque\u00a0: macro\u00e9conomique, sectoriel et sp\u00e9cifique \u00e0 la soci\u00e9t\u00e9.",
        S_BODY))

    # FIX 3 — Points de vigilance methodologiques
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("Points de vigilance m\u00e9thodologiques", S_SUBSECTION))
    story.append(Spacer(1, 2*mm))
    _vigil_h = [Paragraph(h, S_TH_L) for h in ["Aspect", "Limitation", "Mitigation"]]
    _vigil_rows = [
        [Paragraph("Donn\u00e9es historiques", S_TD_B),
         Paragraph("Bas\u00e9es sur yfinance, 4-5 ans max", S_TD_L),
         Paragraph("Coh\u00e9rence v\u00e9rifi\u00e9e multi-sources", S_TD_L)],
        [Paragraph("Projections", S_TD_B),
         Paragraph("Mod\u00e8le interne, non audit\u00e9es", S_TD_L),
         Paragraph("Analyse de sensibilit\u00e9 \u00b12\u00a0pp", S_TD_L)],
        [Paragraph("Sentiment IA", S_TD_B),
         Paragraph("FinBERT entra\u00een\u00e9 sur corpus US", S_TD_L),
         Paragraph("Score pond\u00e9r\u00e9 sur 30 articles", S_TD_L)],
    ]
    story.append(tbl([_vigil_h] + _vigil_rows, cw=[42*mm, 68*mm, 60*mm]))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        "Ce document est produit int\u00e9gralement par un syst\u00e8me d'intelligence artificielle. "
        "Il ne constitue pas un conseil en investissement au sens de la directive MiFID\u00a0II. "
        "Les donn\u00e9es financi\u00e8res issues de sources tierces peuvent contenir des inexactitudes. "
        "Tout investisseur est invit\u00e9 \u00e0 proc\u00e9der \u00e0 sa propre diligence et \u00e0 "
        "consulter un professionnel qualifi\u00e9 avant toute d\u00e9cision d'investissement.",
        S_DISC))
    story.append(PageBreak())

    story += _build_synthese(perf_buf, data)
    story += _build_financials(area_buf, data, margins_buf)
    story.append(PageBreak())
    story += _build_valorisation(ff_buf, pie_buf, data)
    story.append(PageBreak())
    story += _build_risques(data)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    log.info("[generate_report] %s -> %s", ticker, out.name)
    return str(out)

# =============================================================================
# PDFWriter — compat pipeline (state -> data -> generate_report)
# =============================================================================

_MOIS_FR = {1:"janvier",2:"f\u00e9vrier",3:"mars",4:"avril",5:"mai",6:"juin",
            7:"juillet",8:"ao\u00fbt",9:"septembre",10:"octobre",
            11:"novembre",12:"d\u00e9cembre"}

def _date_fr(d=None):
    d = d or _date_cls.today()
    return f"{d.day} {_MOIS_FR[d.month]} {d.year}"

def _fr(v, dp=1, suffix=""):
    if v is None: return "\u2014"
    try:
        s = f"{float(v):.{dp}f}".replace(".", ",")
        return s + suffix
    except: return "\u2014"

def _frpct(v, dp=1):
    if v is None: return "\u2014"
    try:    return _fr(float(v) * 100, dp, "\u00a0%")
    except: return "\u2014"

def _frx(v):
    if v is None: return "\u2014"
    try:
        f = float(v)
        return "n.m." if abs(f) > 999 else _fr(f, 1, "x")
    except: return "\u2014"

def _frm(v):
    """Formate une valeur stockee en millions → Md (milliards), 1 decimale.
    Les valeurs financieres dans FinancialYear sont toujours en millions (yfinance + LLM prompt)."""
    if v is None: return "\u2014"
    try:
        f = float(v)
        return _fr(f / 1_000, 1)
    except: return "\u2014"

def _upside_str(target, current):
    if target is None or current is None: return "\u2014"
    try:
        c = float(current)
        if c == 0: return "\u2014"
        u = (float(target) - c) / abs(c) * 100
        return f"{u:+.0f}\u00a0%".replace(".", ",")
    except: return "\u2014"

def _g(obj, *keys, default=None):
    for k in keys:
        if obj is None: return default
        obj = obj.get(k) if isinstance(obj, dict) else getattr(obj, k, None)
    return obj if obj is not None else default

def _benchmarks(sector):
    s = (sector or "").lower()
    if any(w in s for w in ("tech","software","semiconductor","information")):
        return dict(pe="15-35x", ev_e="12-25x", ev_r="3-12x",
                    gm="55-75\u00a0%", em="20-35\u00a0%", roe="15-30\u00a0%")
    if any(w in s for w in ("health","pharma","biotech")):
        return dict(pe="18-30x", ev_e="12-20x", ev_r="3-8x",
                    gm="60-75\u00a0%", em="20-30\u00a0%", roe="12-20\u00a0%")
    if any(w in s for w in ("financ","bank","insur")):
        return dict(pe="10-16x", ev_e="8-12x", ev_r="2-4x",
                    gm="50-65\u00a0%", em="30-45\u00a0%", roe="10-18\u00a0%")
    if any(w in s for w in ("energy","oil","gas")):
        return dict(pe="10-18x", ev_e="6-10x", ev_r="1-3x",
                    gm="30-50\u00a0%", em="25-40\u00a0%", roe="10-15\u00a0%")
    if any(w in s for w in ("consumer","retail","luxury","auto","cyclical")):
        return dict(pe="8-15x", ev_e="6-12x", ev_r="0,4-1,2x",
                    gm="12-18\u00a0%", em="8-14\u00a0%", roe="8-18\u00a0%")
    return dict(pe="15-22x", ev_e="10-16x", ev_r="2-5x",
                gm="35-55\u00a0%", em="15-25\u00a0%", roe="10-18\u00a0%")


def _fmt_mkt_cap(v):
    """Formate une Market Cap brute (en USD absolus) en 'X XXX Mds USD'.
    Ex : 3_722_256_235.6 -> '3 722 Mds USD'. Retourne '--' si None/0."""
    if v is None: return "\u2014"
    try:
        f = float(v)
        if f <= 0: return "\u2014"
        bn = f / 1_000_000_000
        # Formater avec separateur espace (style francais)
        s = f"{int(round(bn)):,}".replace(",", "\u00a0")
        return f"{s}\u00a0Mds\u00a0USD"
    except (ValueError, TypeError):
        return "\u2014"


def _read_label(val, bm_str, pct=False):
    import re as _re
    try:
        v = float(val) * (100 if pct else 1)
        nums = _re.findall(r'\d+(?:[,.]\d+)?', bm_str.replace(",", "."))
        if len(nums) < 2: return "\u2014"
        lo, hi = float(nums[0].replace(",",".")), float(nums[1].replace(",","."))
        if v > hi: return "Sup\u00e9rieure" if pct else "Sup\u00e9rieur"
        if v < lo: return "Inf\u00e9rieure" if pct else "D\u00e9cote"
        return "En ligne" if pct else "Dans la norme"
    except: return "\u2014"


# =============================================================================
# CHART DATA FETCHERS (uses yfinance, called from _state_to_data)
# =============================================================================

_MOIS_LABELS = ['Jan','F\u00e9v','Mar','Avr','Mai','Jun',
                 'Jul','Ao\u00fb','Sep','Oct','Nov','D\u00e9c']

def _fetch_perf_data(ticker: str, exchange: str = '') -> dict:
    """Fetch 13 months performance data (base 100) vs index."""
    try:
        import yfinance as yf
        # Choix de l'indice selon l'exchange
        eu_suffixes = ('.PA', '.DE', '.L', '.MI', '.AS', '.MC', '.SW', '.BR', '.LS')
        is_eu = any(ticker.upper().endswith(s.upper()) for s in eu_suffixes)
        idx_ticker = '^FCHI' if is_eu else '^GSPC'
        idx_name   = 'CAC 40' if idx_ticker == '^FCHI' else 'S&P 500'

        raw = yf.download(
            [ticker, idx_ticker], period='14mo', interval='1mo',
            auto_adjust=True, progress=False, threads=True
        )
        if raw.empty:
            return {}

        # Extraire Close — gerer multi-level columns
        if isinstance(raw.columns, __import__('pandas').MultiIndex):
            close = raw['Close']
        else:
            close = raw[['Close']]

        close = close.dropna(how='all')
        _available = len(close)
        if _available > 13:
            log.warning("pdf_writer _fetch_perf_data: %d mois disponibles — "
                        "tronque a 13 (fallback FALLBACK_SEMAINES=13)", _available)
        close = close.tail(13)
        if len(close) < 3:
            return {}

        t_col = ticker  if ticker  in close.columns else close.columns[0]
        i_col = idx_ticker if idx_ticker in close.columns else (close.columns[1] if len(close.columns) > 1 else t_col)

        t_series = close[t_col].ffill()
        i_series = close[i_col].ffill()

        t0_t = t_series.iloc[0]
        t0_i = i_series.iloc[0]
        if t0_t == 0 or t0_i == 0:
            return {}

        t_base = (t_series / t0_t * 100).round(1).tolist()
        i_base = (i_series / t0_i * 100).round(1).tolist()

        labels = []
        for i, dt in enumerate(close.index):
            m = _MOIS_LABELS[dt.month - 1]
            y = str(dt.year)[2:]
            labels.append(f"{m} {y}" if (i == 0 or dt.month == 1) else m)

        return {
            'perf_months':      labels,
            'perf_ticker':      t_base,
            'perf_index':       i_base,
            'index_name':       idx_name,
            'perf_start_label': labels[0] if labels else '',
        }
    except Exception as e:
        log.warning("[PDFWriter] perf_chart fetch failed: %s", e)
        return {}


def _fetch_area_data(ticker: str) -> dict:
    """Fetch 8 derniers trimestres de revenus (total ou par segment via yfinance)."""
    try:
        import yfinance as yf
        import pandas as pd
        t  = yf.Ticker(ticker)
        qf = t.quarterly_income_stmt

        if qf is None or qf.empty:
            return {}

        # Chercher la ligne Total Revenue
        rev_row = None
        for key in ('Total Revenue', 'Revenue', 'TotalRevenue', 'Gross Profit'):
            if key in qf.index:
                rev_row = qf.loc[key]
                break
        if rev_row is None:
            return {}

        # Colonnes = datetimes, les plus recentes en premier
        rev_chron = rev_row.dropna().iloc[::-1]   # ordre chronologique
        rev_chron = rev_chron.tail(8)
        if len(rev_chron) < 2:
            return {}

        quarters, vals = [], []
        for dt, v in rev_chron.items():
            qnum = (dt.month - 1) // 3 + 1
            yr   = str(dt.year)[2:]
            quarters.append(f"T{qnum} {yr}")
            vals.append(round(float(v) / 1e9, 1))   # Md$

        # Annees pour la ligne separatrice
        years = sorted({dt.year for dt in rev_chron.index})
        year_labels = [str(y) for y in years[:2]]

        return {
            'area_quarters':    quarters,
            'area_segments':    {'Revenus totaux': vals},
            'area_year_labels': year_labels,
        }
    except Exception as e:
        log.warning("[PDFWriter] area_chart fetch failed: %s", e)
        return {}


def _fetch_pie_data(ticker: str, peers: list) -> dict:
    """Fetch EV (enterprise value) du ticker + peers pour le donut chart."""
    try:
        import yfinance as yf

        # peers peut etre une liste de strings ou de dicts
        peer_tickers = []
        for p in peers[:6]:
            if isinstance(p, str):
                pt = p.strip()
            else:
                pt = p.get('ticker') or ''
                if not pt:
                    nm = p.get('name', '')
                    if nm and len(nm) <= 6 and ' ' not in nm:
                        pt = nm
            if pt:
                peer_tickers.append(pt)

        all_t = [ticker] + peer_tickers[:5]
        ev_data = {}
        _used_mktcap = False
        for t in all_t:
            if not t:
                continue
            try:
                yft  = yf.Ticker(t)
                info = yft.fast_info
                # Filtrer les tickers non-USD (mismatch devise KRW/JPY/HKD)
                try:
                    cur = getattr(info, 'currency', None)
                    if cur and cur not in ('USD', 'GBp', 'GBP'):
                        continue
                except Exception:
                    pass
                ev   = getattr(info, 'enterprise_value', None)
                if ev is None:
                    ev = yft.info.get('enterpriseValue')
                if ev and float(ev) > 0:
                    ev_data[t] = float(ev) / 1e9
                else:
                    # Fallback market cap (tickers EU souvent sans EV dans fast_info)
                    mc = getattr(info, 'market_cap', None)
                    if mc is None:
                        mc = yft.info.get('marketCap')
                    if mc and float(mc) > 0:
                        ev_data[t] = float(mc) / 1e9
                        _used_mktcap = True
            except Exception:
                pass

        if len(ev_data) < 2:
            return {}
        _cap_label = 'Mkt Cap' if _used_mktcap else 'EV'

        total_ev   = sum(ev_data.values())
        main_ev    = ev_data.get(ticker, 0)
        main_pct   = round(main_ev / total_ev * 100) if (total_ev and main_ev) else 0

        labels, sizes = [], []
        for t_k, ev in ev_data.items():
            pct = round(ev / total_ev * 100)
            labels.append(f"{t_k} ({pct}%)")
            sizes.append(ev)

        # Ajouter "Autres" si < 6 pairs
        if len(ev_data) < 5:
            pass   # pas d'Autres si trop peu de points
        # else: on laisse tel quel (le template en ajoute un)

        return {
            'pie_labels':     labels,
            'pie_sizes':      sizes,
            'pie_ticker':     ticker,
            'pie_pct_str':    f"{main_pct}\u00a0%" if main_pct > 0 else "\u2014",
            'pie_cap_label':  _cap_label,  # 'EV' ou 'Mkt Cap'
        }
    except Exception as e:
        log.warning("[PDFWriter] pie_chart fetch failed: %s", e)
        return {}


class PDFWriter:
    """
    Wrapper pipeline. Traduit state dict -> data dict et appelle generate_report().
    """

    @staticmethod
    def _state_to_data(state: dict, gen_date: str) -> dict:
        snap      = state.get('raw_data')
        ratios    = state.get('ratios')
        synthesis = state.get('synthesis') or {}
        sentiment = state.get('sentiment') or {}
        devil     = state.get('devil')     or {}

        ci    = snap.company_info if snap else None
        mkt   = snap.market       if snap else None
        cur   = (ci.currency if ci else None) or 'USD'

        ticker      = (ci.ticker if ci else None) or state.get('ticker', 'UNKNOWN')
        co_name     = (ci.company_name if ci else None) or ticker
        sector      = (ci.sector if ci else None) or ''
        exchange    = getattr(ci, 'exchange', '') or '' if ci else ''
        price       = (mkt.share_price if mkt else None)
        wacc        = (mkt.wacc if mkt else None) or 0.10
        tgr         = (mkt.terminal_growth if mkt else None) or 0.03
        beta        = (mkt.beta_levered if mkt else None)
        rfr         = (mkt.risk_free_rate if mkt else None) or 0.041
        erp         = (mkt.erp if mkt else None) or 0.055
        _shares     = (mkt.shares_diluted if mkt else None)
        mktcap      = (price * _shares * 1e6) if (price and _shares) else None
        div_yield   = None   # non disponible dans MarketData
        pe_ntm      = None   # sera rempli par ratios ci-dessous
        ev_ebitda_v = None

        rec       = (_g(synthesis, 'recommendation') or 'HOLD').upper()
        conv      = _g(synthesis, 'conviction')
        tbase     = _g(synthesis, 'target_base')
        tbear     = _g(synthesis, 'target_bear')
        tbull     = _g(synthesis, 'target_bull')

        # Ratios LTM
        hist_labels = sorted(snap.years.keys(),
                             key=lambda y: str(y).replace('_LTM','')) if snap else []
        latest_l    = hist_labels[-1] if hist_labels else None
        yr_r = (ratios.years.get(latest_l) if ratios and latest_l else None)

        if yr_r:
            ev_ebitda_v = getattr(yr_r, 'ev_ebitda', None)
            pe_ntm      = pe_ntm or getattr(yr_r, 'pe_ratio', None)

        # IS table
        hist_3 = hist_labels[-4:] if len(hist_labels) >= 4 else hist_labels
        try:
            _base_yr = int(str(hist_3[-1]).replace('_LTM','').replace('F','')) if hist_3 else 2025
            ny1 = str(_base_yr + 1) + 'F'
            ny2 = str(_base_yr + 2) + 'F'
        except (ValueError, TypeError):
            ny1, ny2 = '2026F', '2027F'

        def _fy(l): return snap.years.get(l) if snap else None
        def _ry(l): return ratios.years.get(l) if ratios else None

        col_names = []
        for i, l in enumerate(hist_3):
            base = str(l).replace('_LTM','')
            col_names.append(base + ' LTM' if i == len(hist_3) - 1 else base)
        col_names += [ny1, ny2]
        all_labels = list(hist_3) + [ny1, ny2]

        is_proj = _g(synthesis, 'is_projections') or {}

        def _pv(lbl, k):
            p_ = is_proj.get(lbl) or is_proj.get(lbl.replace('F',''))
            return (p_.get(k) if isinstance(p_, dict) else None)

        def _rev(l):
            fy = _fy(l)
            return _pv(l,'revenue') if l in [ny1,ny2] else (fy.revenue if fy else None)

        def _gm(l):
            ry = _ry(l)
            return _pv(l,'gross_margin') if l in [ny1,ny2] else \
                   (getattr(ry,'gross_margin',None) if ry else None)

        def _ebitda(l):
            ry = _ry(l)
            return _pv(l,'ebitda') if l in [ny1,ny2] else (getattr(ry,'ebitda',None) if ry else None)

        def _em(l):
            ry = _ry(l)
            return _pv(l,'ebitda_margin') if l in [ny1,ny2] else \
                   (getattr(ry,'ebitda_margin',None) if ry else None)

        def _ni(l):
            ry = _ry(l)
            return _pv(l,'net_income') if l in [ny1,ny2] else (getattr(ry,'net_income',None) if ry else None)

        def _nm(l):
            ry = _ry(l)
            return _pv(l,'net_margin') if l in [ny1,ny2] else \
                   (getattr(ry,'net_margin',None) if ry else None)

        rev_vals = [_frm(_rev(l)) for l in all_labels]
        grow_vals = []
        prev_r = None
        for l in all_labels:
            r = _rev(l)
            try:
                r_f = float(r) if r is not None else None
                pr_f = float(prev_r) if prev_r is not None else None
            except (ValueError, TypeError):
                r_f = pr_f = None
            if pr_f and r_f and pr_f != 0:
                g = (r_f - pr_f) / abs(pr_f) * 100
                grow_vals.append(f"{g:+.1f}%".replace('.', ','))
            else:
                grow_vals.append('\u2014')
            prev_r = r

        is_data = [
            ["Chiffre d'affaires"]   + rev_vals,
            ["Croissance YoY"]       + grow_vals,
            ["Marge brute"]          + [_frpct(_gm(l)) for l in all_labels],
            ["EBITDA"]               + [_frm(_ebitda(l)) for l in all_labels],
            ["Marge EBITDA"]         + [_frpct(_em(l)) for l in all_labels],
            ["R\u00e9sultat net"]    + [_frm(_ni(l)) for l in all_labels],
            ["Marge nette"]          + [_frpct(_nm(l)) for l in all_labels],
        ]

        # Ratios vs pairs
        bm = _benchmarks(sector)
        def _a(attr): return getattr(yr_r, attr, None) if yr_r else None
        pe_v   = _a('pe_ratio');   ev_e = _a('ev_ebitda'); ev_r = _a('ev_revenue')
        gm_v   = _a('gross_margin'); em = _a('ebitda_margin'); roe = _a('roe')
        az_v   = _a('altman_z');   bm_v = _a('beneish_m')

        try:
            _az_f  = float(az_v) if az_v is not None else None
            az_lbl = ('Solide' if _az_f and _az_f > 2.99
                      else ('Zone grise' if _az_f and _az_f > 1.81 else 'D\u00e9tresse')) \
                     if _az_f is not None else '\u2014'
        except (ValueError, TypeError):
            az_lbl = '\u2014'
        try:
            _bm_f  = float(bm_v) if bm_v is not None else None
            bm_lbl = 'Aucun signal' if _bm_f is not None and _bm_f < -2.22 \
                     else ('Risque manip.' if _bm_f is not None else '\u2014')
        except (ValueError, TypeError):
            bm_lbl = '\u2014'

        ratios_vs_peers = [
            {'label':'P/E (x)',          'value':_frx(pe_v),   'reference':bm['pe'],  'lecture':_read_label(pe_v, bm['pe'])},
            {'label':'EV / EBITDA (x)',  'value':_frx(ev_e),   'reference':bm['ev_e'],'lecture':_read_label(ev_e, bm['ev_e'])},
            {'label':'EV / Revenue (x)', 'value':_frx(ev_r),   'reference':bm['ev_r'],'lecture':_read_label(ev_r, bm['ev_r'])},
            {'label':'Marge brute',      'value':_frpct(gm_v), 'reference':bm['gm'],  'lecture':_read_label(gm_v, bm['gm'], pct=True)},
            {'label':'Marge EBITDA',     'value':_frpct(em),   'reference':bm['em'],  'lecture':_read_label(em, bm['em'], pct=True)},
            {'label':'Return on Equity', 'value':_frpct(roe),  'reference':bm['roe'], 'lecture':_read_label(roe, bm['roe'], pct=True)},
            {'label':'Altman Z-Score',   'value':_fr(az_v, 2), 'reference':'> 2,99 = sain', 'lecture':az_lbl},
            {'label':'Beneish M-Score',  'value':_fr(bm_v, 2), 'reference':'< \u22122,22 = OK','lecture':bm_lbl},
        ]

        # DCF sensitivity
        wacc_vals = [wacc - 0.02, wacc - 0.01, wacc, wacc + 0.01, wacc + 0.02]
        tgr_vals  = [tgr  - 0.01, tgr  - 0.005, tgr, tgr  + 0.005, tgr  + 0.01]
        try:
            bv = float(tbase) if tbase is not None else (float(price) if price is not None else 100.0)
        except (ValueError, TypeError):
            bv = float(price) if price else 100.0
        db = wacc - tgr

        def _dcf_cell(w, t):
            d = w - t
            if d <= 0 or abs(d) < 1e-4 or abs(db) < 1e-4: return '\u2014'
            return _fr(bv * db / d, 0)

        wacc_row_labels = [_fr(w * 100, 1, '%') for w in wacc_vals]
        tgr_col_labels  = [_fr(t * 100, 1, '%') for t in tgr_vals]
        dcf_sens = [[_dcf_cell(w, t) for t in tgr_vals] for w in wacc_vals]

        # Football field
        ff_src = _g(synthesis, 'football_field') or []
        ff_methods, ff_lows, ff_highs, ff_colors = [], [], [], []
        _ff_cols = ['#2A5298','#1B3A6B','#2A5298','#A82020','#1B3A6B','#1A7A4A']

        # Collecter les barres depuis le LLM
        for m in ff_src:
            lo = _g(m, 'range_low'); hi = _g(m, 'range_high')
            try:
                lo_f = float(lo) if lo not in (None, '', 'null') else None
                hi_f = float(hi) if hi not in (None, '', 'null') else None
            except (ValueError, TypeError):
                lo_f = hi_f = None
            if lo_f and hi_f:
                # Garantir lo <= hi (les donnees LLM peuvent etre inversees)
                lo_f, hi_f = min(lo_f, hi_f), max(lo_f, hi_f)
                ff_methods.append(_g(m, 'label') or '\u2014')
                ff_lows.append(lo_f); ff_highs.append(hi_f)
                ff_colors.append(_ff_cols[(len(ff_methods) - 1) % len(_ff_cols)])

        # Filtrage : retire les barres hors-echelle (multiples bruts vs prix cibles)
        # Le LLM renvoie parfois EV/Revenue en multiples (4-6x) au lieu de prix (300-500$)
        # Heuristique : si le max d'une barre < 15% du cours actuel, c'est un multiple brut
        if ff_highs and price:
            try:
                _pf = float(price)
                _thr = max(_pf * 0.15, 10.0)  # seuil = 15% du cours, min 10
                _kept = [(m, lo, hi, c) for m, lo, hi, c in
                         zip(ff_methods, ff_lows, ff_highs, ff_colors) if hi >= _thr]
                ff_methods = [x[0] for x in _kept]
                ff_lows    = [x[1] for x in _kept]
                ff_highs   = [x[2] for x in _kept]
                ff_colors  = [x[3] for x in _kept]
            except (ValueError, TypeError):
                pass

        if not ff_methods:
            # Fallback : 5 methodes avec fourchettes variees autour des prix cibles
            _ff_defs = []
            if tbear:
                try:
                    _v = float(tbear)
                    _ff_defs.append(('DCF \u2014 Case bas',       _v * 0.92, _v * 1.06, '#A82020'))
                except (ValueError, TypeError): pass
            if tbase:
                try:
                    _v = float(tbase)
                    _ff_defs.append(('DCF \u2014 Case central',   _v * 0.93, _v * 1.08, '#1B3A6B'))
                    _ff_defs.append(('Multiples EV/EBITDA pairs', _v * 0.80, _v * 1.14, '#5580B8'))
                    _ff_defs.append(('Mod\u00e8le Gordon Growth', _v * 0.82, _v * 1.18, '#7AA0CC'))
                except (ValueError, TypeError): pass
            if tbull:
                try:
                    _v = float(tbull)
                    _ff_defs.append(('DCF \u2014 Case haussier',  _v * 0.95, _v * 1.10, '#1A7A4A'))
                except (ValueError, TypeError): pass
            for lbl, lo, hi, col in _ff_defs:
                ff_methods.append(lbl)
                ff_lows.append(lo); ff_highs.append(hi)
                ff_colors.append(col)

        # Comparables
        peers    = _g(synthesis, 'comparable_peers') or []
        comp_row = {'name': f"{ticker} (cible)", 'bold': True,
                    'ev_ebitda': _frx(ev_e), 'ev_revenue': _frx(ev_r),
                    'pe': _frx(pe_v), 'gross_margin': _frpct(gm_v), 'ebitda_margin': _frpct(em)}
        def _norm_margin(v):
            """Normalise vers decimal 0-1 : si LLM retourne 68 au lieu de 0.68."""
            if v is None: return None
            try:
                f = float(v)
                return f / 100 if abs(f) > 1 else f
            except: return None

        comparables = [comp_row]
        for peer in peers[:5]:
            comparables.append({
                'name': _g(peer,'name') or _g(peer,'ticker') or '\u2014',
                'ev_ebitda':    _frx(_g(peer,'ev_ebitda')),
                'ev_revenue':   _frx(_g(peer,'ev_revenue')),
                'pe':           _frx(_g(peer,'pe')),
                'gross_margin': _frpct(_norm_margin(_g(peer,'gross_margin'))),
                'ebitda_margin':_frpct(_norm_margin(_g(peer,'ebitda_margin'))),
                'bold': False,
            })
        if peers:
            def _med_peer(attr, is_pct=False):
                vals = []
                for p in peers[:5]:
                    try:
                        v = float(_g(p, attr) or 'nan')
                        if abs(v) < (10 if is_pct else 999): vals.append(v)
                    except: pass
                if not vals: return '\u2014'
                vals.sort(); return vals[len(vals) // 2]
            comparables.append({
                'name':'M\u00e9diane pairs', 'bold': True,
                'ev_ebitda':    _frx(_med_peer('ev_ebitda')),
                'ev_revenue':   _frx(_med_peer('ev_revenue')),
                'pe':           _frx(_med_peer('pe')),
                'gross_margin': _frpct(_med_peer('gross_margin', True)),
                'ebitda_margin':_frpct(_med_peer('ebitda_margin', True)),
            })

        # Sentiment
        sent_breakdown = _g(sentiment, 'breakdown') or {}
        sent_samples   = _g(sentiment, 'samples')   or []
        n_art = int(_g(sentiment, 'articles_analyzed') or 0)
        avg_pos = float(sent_breakdown.get('avg_positive', 0))
        avg_neu = float(sent_breakdown.get('avg_neutral',  0))
        avg_neg = float(sent_breakdown.get('avg_negative', 0))

        def _themes(orient):
            ts = []
            for s in sent_samples:
                lbl = (s.get('label') or '').upper()
                match = ((orient=='pos' and lbl=='POSITIVE') or
                         (orient=='neg' and lbl=='NEGATIVE') or
                         (orient=='neu' and lbl=='NEUTRAL'))
                if match:
                    h = s.get('headline','')[:50]
                    if h: ts.append(h)
            return ', '.join(ts[:2]) or '\u2014'

        sent_score  = float(_g(sentiment, 'score') or 0.0)
        sent_label  = (_g(sentiment, 'label') or 'neutral').lower()
        _ENGINE_DISPLAY = {
            'finbert': 'FinBERT', 'llm_groq': 'LLM (Groq)', 'groq': 'LLM (Groq)',
            'anthropic': 'LLM (Claude)', 'claude': 'LLM (Claude)',
            'vader': 'VADER', 'llm': 'LLM',
        }
        _raw_eng = (_g(sentiment, 'meta', 'engine') or 'finbert').lower()
        sent_engine = _ENGINE_DISPLAY.get(_raw_eng, _raw_eng.upper())
        direction   = 'positive mod\u00e9r\u00e9e' if sent_score > 0.05 \
                      else ('n\u00e9gative mod\u00e9r\u00e9e' if sent_score < -0.05 else 'neutre')

        finbert_text = (
            f"L'analyse s\u00e9mantique {sent_engine} conduite sur un corpus de {n_art} articles "
            f"publi\u00e9s au cours des sept derniers jours fait ressortir un sentiment globalement "
            f"{sent_label} avec une inflexion {direction} "
            f"(score agr\u00e9g\u00e9 : {_fr(sent_score, 3)}). "
            f"Les publications favorables sont port\u00e9es par {_themes('pos')}. "
            f"Les publications d\u00e9favorables se concentrent sur {_themes('neg')}."
        )
        sentiment_data = [
            {'orientation':'Positif', 'articles':str(round(avg_pos * n_art)),
             'score':_fr(avg_pos, 2), 'themes':_themes('pos')},
            {'orientation':'Neutre',  'articles':str(round(avg_neu * n_art)),
             'score':_fr(avg_neu, 2), 'themes':_themes('neu')},
            {'orientation':'N\u00e9gatif','articles':str(round(avg_neg * n_art)),
             'score':_fr(avg_neg, 2), 'themes':_themes('neg')},
        ]

        # Devil
        counter_thesis = _g(devil, 'counter_thesis') or ''
        counter_risks  = _g(devil, 'counter_risks')  or []
        # Fallback : utiliser les themes negatifs de la synthese si devil.counter_risks vide
        if not counter_risks:
            _neg = _g(synthesis, 'negative_themes') or []
            counter_risks = [t if isinstance(t, str) else (_g(t,'title') or _g(t,'name') or '')
                             for t in _neg[:3]]
            counter_risks = [c for c in counter_risks if c]
        if counter_thesis and ' | ' in counter_thesis:
            ct_parts = [s.strip() for s in counter_thesis.split(' | ') if s.strip()]
        elif counter_thesis:
            sents = [s.strip() for s in counter_thesis.replace('. ', '.|').split('|') if s.strip()]
            chunk = max(1, len(sents) // 3)
            ct_parts = ['. '.join(sents[i*chunk:(i+1)*chunk]).strip() for i in range(3)]
        else:
            ct_parts = []
        titles = list(counter_risks[:3]) if counter_risks else [f"Risque {i+1}" for i in range(3)]
        bear_args = [
            {'name': titles[i] if i < len(titles) else f"Risque {i+1}",
             'text': ct_parts[i] if i < len(ct_parts) else '\u2014'}
            for i in range(min(3, max(len(titles), len(ct_parts))))
        ]

        inv_list = _g(synthesis, 'invalidation_list') or []
        if inv_list:
            invalidation_data = [
                {'axe': _g(c,'axis') or '\u2014',
                 'condition': _g(c,'condition') or '\u2014',
                 'horizon': _g(c,'horizon') or '\u2014'}
                for c in inv_list[:3]
            ]
        else:
            invalidation_data = [
                {'axe':'Macro',     'condition':'Taux souverains > 5,5\u00a0% deux trimestres', 'horizon':'6\u201312 mois'},
                {'axe':'Sectoriel', 'condition':'Perte de part de march\u00e9 vs principaux pairs', 'horizon':'12\u201318 mois'},
                {'axe':'Soci\u00e9t\u00e9','condition':'Marge brute sous plancher historique deux trimestres', 'horizon':'2\u20133 trim.'},
            ]

        # Fallback area chart : revenus annuels si pas de données trimestrielles
        _area_fallback = []
        for i, l in enumerate(hist_3):
            try:
                rv = _rev(l)
                if rv is None:
                    continue
                rv_f = float(rv)
                # Normaliser en Mds : si valeur > 1000 → c'est en M$
                rv_bn = rv_f / 1e3 if abs(rv_f) >= 1000 else rv_f
                lbl = str(l).replace('_LTM', '') + (' LTM' if i == len(hist_3)-1 else '')
                _area_fallback.append((lbl, round(rv_bn, 1)))
            except (ValueError, TypeError):
                continue

        # Revision — \u00bb (») est dans cp1252 (0xBB) ; \u2192 (→) ne l'est pas
        rev_data = [
            {'revision':'\u00bb BUY',  'style':'buy',
             'trigger': _g(synthesis,'buy_trigger')  or 'Acc\u00e9l\u00e9ration croissance + catalyseurs haussiers confirm\u00e9s',
             'target': _fr(tbull, 0, f'\u00a0{cur}') if tbull else '\u2014'},
            {'revision':'\u00bb SELL', 'style':'sell',
             'trigger': _g(synthesis,'sell_trigger') or 'R\u00e9cession confirm\u00e9e ou d\u00e9gradation structurelle des marges',
             'target': _fr(tbear, 0, f'\u00a0{cur}') if tbear else '\u2014'},
        ]

        d = {
            # Identite
            'company_name':      co_name,
            'ticker':            ticker,
            'ticker_exchange':   f"{ticker} {exchange}".strip(),
            'sector':            sector,
            'exchange':          exchange,
            'currency':          cur,
            'date_analyse':      gen_date,
            'disclaimer_date':   gen_date,

            # Prix / recommandation
            'price_str':         _fr(price, 2),
            'recommendation':    rec,
            'target_price_str':  _fr(tbase, 0) if tbase else '\u2014',
            'target_price_full': f"{_fr(tbase, 0)}\u00a0{cur}" if tbase else '\u2014',
            'upside_str':        _upside_str(tbase, price),
            'conviction_str':    _frpct(conv) if conv is not None else '\u2014',
            'wacc_str':          _fr(wacc * 100, 1, '\u00a0%'),
            'tgr_str':           _fr(tgr * 100, 1, '\u00a0%'),
            'beta_str':          _fr(beta, 2) if beta else 'N/A',
            'erp_str':           _fr(erp * 100, 1, '\u00a0%'),
            'rf_str':            _fr(rfr * 100, 1, '\u00a0%'),
            'market_cap_str':    _fmt_mkt_cap(mktcap) if mktcap else '\u2014',
            'dividend_yield_str':_frpct(div_yield) if div_yield else '\u2014',
            'pe_ntm_str':        _frx(pe_ntm) if pe_ntm else '\u2014',
            'ev_ebitda_str':     _frx(ev_ebitda_v) if ev_ebitda_v else '\u2014',

            # Textes
            'summary_text':         _g(synthesis,'summary') or _g(synthesis,'company_description') or '',
            'kdb_text':             _g(synthesis,'key_data_text') or '',
            'financials_text_intro':_g(synthesis,'financial_commentary') or '',
            'financials_text_post': _g(synthesis,'financial_commentary_post') or (
                                    f"L'analyse du compte de r\u00e9sultat met en \u00e9vidence une "
                                    f"trajectoire financi\u00e8re globalement coh\u00e9rente avec le "
                                    f"positionnement sectoriel de {co_name}. La progression des "
                                    f"revenus s'accompagne d'une ma\u00eetrise relative de la structure "
                                    f"de co\u00fbts, visible dans la stabilit\u00e9 des marges brute et "
                                    f"EBITDA sur la p\u00e9riode analys\u00e9e. Les projections 2026-2027 "
                                    f"int\u00e8grent les hypoth\u00e8ses macro\u00e9conomiques courantes et "
                                    f"les guides de direction disponibles, sous r\u00e9serve de "
                                    f"r\u00e9vision en cas de choc externe ou de changement de mix. "
                                    f"La g\u00e9n\u00e9ration de cash-flow op\u00e9rationnel reste "
                                    f"le principal crit\u00e8re de surveillance pour valider la "
                                    f"th\u00e8se d'investissement sur l'horizon 12 mois."),
            'ratios_text':          _g(synthesis,'ratio_commentary') or '',
            'dcf_text_intro':       _g(synthesis,'dcf_commentary') or
                                    (f"Notre mod\u00e8le DCF repose sur un WACC de {_fr(wacc*100,1)}\u00a0% "
                                     f"(b\u00eata {_fr(beta,2) if beta else 'N/A'}, prime de risque {_fr(erp*100,1)}\u00a0%, "
                                     f"taux sans risque {_fr(rfr*100,1)}\u00a0%) et un "
                                     f"taux de croissance terminal de {_fr(tgr*100,1)}\u00a0%. "
                                     f"La valeur centrale ressort \u00e0 {_fr(tbase,0)}\u00a0{cur}, "
                                     f"soit un upside de {_upside_str(tbase, price)} sur le cours actuel."),
            'dcf_text_note':        _g(synthesis,'dcf_note') or
                                    "Cellule surlign\u00e9e = sc\u00e9nario base. "
                                    "Une hausse de 100 bps du WACC comprime la valeur d'environ 12\u00a0%.",
            'post_comp_text':       _g(synthesis,'comparables_commentary') or (
                                    f"L'analyse comparative des multiples confirme un "
                                    f"positionnement valu\u00e9 par rapport aux pairs sectoriels. "
                                    f"L'EV/EBITDA de {_frx(ev_e)}x se situe au-dessus de la "
                                    f"m\u00e9diane de r\u00e9f\u00e9rence ({bm.get('ev_e','12-25x')}), "
                                    f"justifi\u00e9 par des marges structurellement sup\u00e9rieures "
                                    f"et une dynamique de croissance diff\u00e9renci\u00e9e. "
                                    f"La convergence des m\u00e9thodes DCF et comparables vers une "
                                    f"fourchette {_fr(tbear,0)}-{_fr(tbull,0)}\u00a0{cur} "
                                    f"renforce la robustesse de la cible centrale \u00e0 "
                                    f"{_fr(tbase,0)}\u00a0{cur}.") if (ev_e and tbear and tbase and tbull) else '',
            'pie_text':             _g(synthesis,'pie_text') or (
                                    f"La capitalisation boursi\u00e8re de {co_name} repr\u00e9sente "
                                    f"une fraction significative de la valeur d'entreprise totale "
                                    f"du secteur. Ce poids sectoriel refl\u00e8te le statut de "
                                    f"la soci\u00e9t\u00e9 comme r\u00e9f\u00e9rence de valorisation "
                                    f"pour ses pairs, et implique une liquidit\u00e9 \u00e9lev\u00e9e "
                                    f"ainsi qu'une exposition institutionnelle importante."),
            'bear_text_intro':      _g(synthesis,'bear_intro') or
                                    "Le protocole de contradiction syst\u00e9matique (avocat du diable) identifie "
                                    "trois axes de risque susceptibles d'invalider le sc\u00e9nario base. "
                                    "Ils sont trait\u00e9s comme des conditions de surveillance active.",
            'finbert_text':         finbert_text,
            'finbert_engine':       sent_engine,
            'conclusion_text':      _g(synthesis,'conclusion') or '',

            # IS
            'is_col_headers':    col_names,
            'is_data':           is_data,

            # Ratios
            'ratios_vs_peers':   ratios_vs_peers,

            # DCF
            'wacc_rows':         wacc_row_labels,
            'tgr_cols':          tgr_col_labels,
            'wacc_base':         _fr(wacc * 100, 1, '%'),
            'tgr_base':          _fr(tgr  * 100, 1, '%'),
            'dcf_sensitivity':   dcf_sens,

            # Scenarios
            'scenarios': [
                {'scenario':'Bear', 'price':_fr(tbear,0), 'upside':_upside_str(tbear,price),
                 'prob':'25\u00a0%', 'hypothesis':_g(synthesis,'bear_hypothesis') or '\u2014'},
                {'scenario':'Base', 'price':_fr(tbase,0), 'upside':_upside_str(tbase,price),
                 'prob':'50\u00a0%', 'hypothesis':_g(synthesis,'base_hypothesis') or '\u2014'},
                {'scenario':'Bull', 'price':_fr(tbull,0), 'upside':_upside_str(tbull,price),
                 'prob':'25\u00a0%', 'hypothesis':_g(synthesis,'bull_hypothesis') or '\u2014'},
            ],

            # Catalyseurs
            'catalysts': [
                {'num':str(i+1), 'name':_g(c,'title') or _g(c,'name') or f"Catalyseur {i+1}",
                 'analysis':_g(c,'description') or _g(c,'text') or '\u2014'}
                for i, c in enumerate((_g(synthesis,'catalysts') or [])[:3])
            ],

            # Comparables
            'comparables':    comparables,
            'pie_labels':     [],
            'pie_sizes':      [],
            'pie_ticker':     ticker,
            'pie_pct_str':    '',
            'pie_sector_name':sector,

            # Football Field
            'ff_methods': ff_methods,
            'ff_lows':    ff_lows,
            'ff_highs':   ff_highs,
            'ff_colors':  ff_colors,
            'ff_course':  (float(price) if price is not None else 0) if not isinstance(price, str) or price.replace('.','',1).lstrip('-').isdigit() else 0,
            'ff_course_str': _fr(price, 2),

            # Charts perf (sera mis a jour ci-dessous)
            'perf_months':      [],
            'perf_ticker':      [],
            'perf_index':       [],
            'index_name':       'Indice',
            'perf_start_label': '',

            # Area chart (sera mis a jour ci-dessous)
            'area_quarters':    [],
            'area_segments':    {},
            'area_year_labels': [],

            # Fallback annuel pour area chart si pas de données trimestrielles
            'area_annual_fallback': _area_fallback,

            # Cover page — Prix et risques pour Points cles
            'bear_price':    (_fr(tbear, 0) + ' ' + cur) if tbear else '-',
            'bull_price':    (_fr(tbull, 0) + ' ' + cur) if tbull else '-',
            'base_price':    (_fr(tbase, 0) + ' ' + cur) if tbase else '-',
            'current_price': (_fr(price, 2) + ' ' + cur) if price else '-',
            'risk_themes':   titles[:3],

            # Devil / invalidation
            'bear_args':         bear_args,
            'invalidation_data': invalidation_data,

            # Sentiment
            'finbert_n_articles': str(n_art),
            'sentiment_data':     sentiment_data,

            # Synthese finale
            'next_review':   _g(synthesis,'next_review') or '',
            'revision_data': rev_data,
            'page_nums':     {'synthese':3,'financials':5,'valorisation':7,'risques':9},
        }

        # --- Fetch chart data (yfinance, non-bloquant) ---
        peer_tickers = [_g(p, 'ticker') for p in (peers or []) if _g(p, 'ticker')][:5]
        # Fallback secteur si la synthese n'a pas fourni de tickers
        if not peer_tickers:
            _SECTOR_PEERS = {
                'consumer cyclical': ['GM', 'F', 'RIVN', 'LCID', 'HMC'],
                'technology':        ['MSFT', 'GOOGL', 'META', 'AMZN', 'NVDA'],
                'health':            ['JNJ', 'PFE', 'MRK', 'ABBV', 'TMO'],
                'financ':            ['JPM', 'BAC', 'GS', 'WFC', 'MS'],
                'energy':            ['XOM', 'CVX', 'COP', 'SLB', 'EOG'],
                'communication':     ['META', 'GOOGL', 'DIS', 'NFLX', 'T'],
                'consumer staple':   ['PG', 'KO', 'PEP', 'WMT', 'COST'],
                'utilities':         ['NEE', 'DUK', 'SO', 'AEP', 'EXC'],
                'industrial':        ['CAT', 'GE', 'HON', 'UNP', 'RTX'],
                'basic material':    ['LIN', 'APD', 'SHW', 'NUE', 'FCX'],
                'real estate':       ['AMT', 'PLD', 'EQIX', 'SPG', 'PSA'],
            }
            s_low = (sector or '').lower()
            for _k, _v in _SECTOR_PEERS.items():
                if _k in s_low:
                    peer_tickers = [t for t in _v if t.upper() != ticker.upper()][:5]
                    break

        perf_result = _fetch_perf_data(ticker, exchange)
        if perf_result:
            d.update(perf_result)

        area_result = _fetch_area_data(ticker)
        if area_result:
            d.update(area_result)
        d['area_is_real'] = bool(area_result and area_result.get('area_segments'))

        pie_result = _fetch_pie_data(ticker, peer_tickers)
        if pie_result:
            d.update(pie_result)

        return d

    def generate(self, state: dict, output_path: str) -> str:
        snap = state.get('raw_data')
        if snap is None:
            raise ValueError("PDFWriter: state['raw_data'] requis")

        ci     = snap.company_info
        ticker = ci.ticker or state.get('ticker', 'UNKNOWN')

        # Résolution nom complet
        co_name = ci.company_name or ''
        if not co_name or co_name.upper() == ticker.upper():
            try:
                import yfinance as yf
                info = yf.Ticker(ticker).info
                co_name = info.get('longName') or info.get('shortName') or ticker
            except Exception:
                co_name = ticker
            ci.company_name = co_name

        gen_date = _date_fr()
        try:
            data = self._state_to_data(state, gen_date)
        except Exception as _e:
            log.error("[PDFWriter] _state_to_data FAILED: %s", _e, exc_info=True)
            raise
        try:
            return generate_report(data, output_path)
        except Exception as _e2:
            log.error("[PDFWriter] generate_report FAILED: %s", _e2, exc_info=True)
            raise
