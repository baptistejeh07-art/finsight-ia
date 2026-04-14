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
    """Echappe &, <, > pour injection dans ReportLab Paragraph (parser XML).
    Decode d'abord les entites HTML du LLM (&gt; → >) avant re-escaping."""
    if not s: return ""
    import html as _html
    decoded = _html.unescape(str(s))
    return decoded.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

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
    fig, ax = plt.subplots(figsize=(6.5, 4.55))
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
    title = "Performance relative \u2014 base 100"
    if start_label:
        title += f", {start_label}"
    ax.set_title(title, fontsize=16, color='#1B3A6B', fontweight='bold', pad=10)
    ax.legend(fontsize=13, loc='upper left', frameon=False)
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
    # Guard : si aucune barre disponible (valorisation indisponible), renvoyer graphique vide
    if n == 0:
        fig, ax = plt.subplots(figsize=(10, 4.5))
        ax.text(0.5, 0.5, 'Valorisation non disponible', ha='center', va='center',
                fontsize=13, color='#888')
        ax.axis('off')
        ax.set_facecolor('white'); fig.patch.set_facecolor('white')
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=180, bbox_inches='tight')
        plt.close(fig); buf.seek(0)
        return buf
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


def _make_mc_histogram(data):
    """Histogramme distribution Monte Carlo DCF — P10/P50/P90 en traits verticaux."""
    if not _MATPLOTLIB_OK:
        return _blank_chart_buf(8, 3.0)
    mc_dist = data.get('mc_dist') or []
    p10 = data.get('dcf_mc_p10')
    p50 = data.get('dcf_mc_p50')
    p90 = data.get('dcf_mc_p90')
    cur = data.get('currency', 'USD')
    price = data.get('ff_course') or None
    if not mc_dist or p50 is None:
        return _blank_chart_buf(8, 3.0)
    import numpy as _np
    vals = _np.array(mc_dist, dtype=float)
    vals = vals[_np.isfinite(vals)]
    if len(vals) < 10:
        return _blank_chart_buf(8, 3.0)
    # Cliper les outliers extremes (P0.5-P99.5) pour éviter les barres isolées qui étirent le graphique
    _lo, _hi = _np.percentile(vals, 0.5), _np.percentile(vals, 99.5)
    vals_plot = _np.clip(vals, _lo, _hi)
    fig, ax = plt.subplots(figsize=(8, 3.0))
    ax.hist(vals_plot, bins=60, color='#2A5298', alpha=0.75, edgecolor='white', linewidth=0.3)
    _vlines = [(p10, '#E07B39', 'P10'), (p50, '#1B3A6B', 'P50'), (p90, '#1A7A4A', 'P90')]
    for _v, _c, _lbl in _vlines:
        if _v is not None:
            ax.axvline(_v, color=_c, linewidth=1.8, linestyle='--')
            ax.text(_v, ax.get_ylim()[1] * 0.88, f' {_lbl}\n {_fr(_v, 0)}', color=_c,
                    fontsize=7.5, fontweight='bold', va='top', ha='left')
    if price:
        try:
            _pf = float(price)
            ax.axvline(_pf, color='#E04040', linewidth=1.5, linestyle='-', alpha=0.8)
            ax.text(_pf, ax.get_ylim()[1] * 0.65, f' Cours\n {_fr(_pf, 0)}',
                    color='#E04040', fontsize=7, va='top', ha='left')
        except (ValueError, TypeError):
            pass
    ax.set_xlabel(f'Cours predit a 12 mois ({cur})', fontsize=9, color='#555')
    ax.set_ylabel('Frequence', fontsize=9, color='#555')
    for sp in ['top', 'right']:
        ax.spines[sp].set_visible(False)
    ax.spines['left'].set_color('#D0D5DD')
    ax.spines['bottom'].set_color('#D0D5DD')
    ax.tick_params(labelsize=8)
    ax.set_facecolor('white')
    fig.patch.set_facecolor('white')
    plt.tight_layout(pad=1.0)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=180, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
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
    fig, ax = plt.subplots(figsize=(8, 4.4), dpi=160)

    all_vals_flat = [v for v in gm_vals + em_vals + nm_vals if v is not None]
    ymax = max(all_vals_flat) * 1.12 if all_vals_flat else 100
    ax.set_ylim(bottom=0, top=ymax)

    def _line(vals, color, label):
        valid_x = [x[i] for i, v in enumerate(vals) if v is not None]
        valid_v = [v for v in vals if v is not None]
        if not valid_v:
            return
        ax.plot(valid_x, valid_v, color=color, linewidth=2.2, marker='o',
                markersize=5, label=label, zorder=3)
        # Valeur au-dessus de chaque point
        for xi, vi in zip(valid_x, valid_v):
            ax.annotate(f"{vi:.1f}%", (xi, vi), textcoords="offset points",
                        xytext=(0, 6), ha='center', fontsize=7.5, color=color)

    _line(gm_vals, '#1B3A6B', 'Marge brute')
    _line(em_vals, '#1A7A4A', 'Marge EBITDA')
    _line(nm_vals, '#2A5298', 'Marge nette')

    ax.set_xticks(x)
    ax.set_xticklabels(years, fontsize=9, color='#555')
    ax.tick_params(axis='y', labelsize=9)
    ax.set_ylabel('(%)', fontsize=10, color='#555')
    _em_last  = next((v for v in reversed(em_vals) if v is not None), None)
    _em_first = next((v for v in em_vals if v is not None), None)
    if _em_last is not None and _em_first is not None and sum(1 for v in em_vals if v is not None) > 1:
        _em_delta = _em_last - _em_first
        _em_trend = f"+{_em_delta:.0f}pts" if _em_delta >= 0 else f"{_em_delta:.0f}pts"
        _margin_title = f"Marge EBITDA {_em_last:.0f}% en LTM (\u00e9volution {_em_trend} sur la p\u00e9riode)"
    else:
        _margin_title = 'Ratios de rentabilit\u00e9 \u2014 \u00c9volution'
    ax.set_title(_margin_title, fontsize=12, color='#1B3A6B', fontweight='bold', pad=32)
    for sp in ['top', 'right']:
        ax.spines[sp].set_visible(False)
    ax.spines['left'].set_color('#D0D5DD')
    ax.spines['bottom'].set_color('#D0D5DD')
    ax.set_facecolor('white')
    fig.patch.set_facecolor('white')
    ax.grid(axis='y', alpha=0.25, color='#D0D5DD', linewidth=0.5, zorder=0)
    # Legende AU-DESSUS du graphique (entre les barres et le titre)
    ax.legend(fontsize=9, loc='lower center', bbox_to_anchor=(0.5, 1.01),
              ncol=3, frameon=True, framealpha=0.9, edgecolor='#D0D5DD',
              borderpad=0.5, labelspacing=0.4)
    plt.tight_layout()
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
            if len(_vals) >= 2 and _vals[0] and _vals[0] > 0:
                _cagr = ((_vals[-1] / _vals[0]) ** (1.0 / max(1, len(_vals) - 1)) - 1) * 100
                _rev_title = f"Revenus {_lbls[-1]} : {_vals[-1]:.1f} Md{_cur} — CAGR {_cagr:+.1f}% ({_lbls[0]}\u2192{_lbls[-1]})"
            else:
                _rev_title = 'Revenus annuels consolid\u00e9s'
            ax.set_title(_rev_title, fontsize=12, color='#1B3A6B', fontweight='bold', pad=8)
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
        f'Revenus par segment \u2014 {len(quarters)} trimestrès ({q0} \u2192 {q1}, Md$)',
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

    # Bullet 4 : risques cles (2 max sur la cover — espace limite)
    # Utiliser risk_themes_full (texte analytique complet) si disponible
    _risks_full = data.get('risk_themes_full') or data.get('risk_themes') or []
    _r1 = _risks_full[0] if len(_risks_full) > 0 else 'Voir section Analyse des Risques'
    _r2 = _risks_full[1] if len(_risks_full) > 1 else ''
    def _wrap_risk(txt, maxch=115):
        if len(txt) <= maxch:
            return txt
        cut = txt[:maxch].rfind(' ')
        return txt[:cut] if cut > 80 else txt[:maxch]
    _risk_lines = [_wrap_risk(_r1)]
    if _r2:
        _risk_lines.append(_wrap_risk(_r2))
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

def _build_investment_case(data):
    """
    Page 'Investment Case' JPM-style :
    - Thèse d'investissement (bullets positive_themes)
    - Catalyseurs à surveiller 12M
    - Valorisation synthétique (P/E + EV/EBITDA + cible DCF vs mediane pairs)
    - Risques principaux (bullets risk_themes)
    Insérée après le sommaire, avant la synthèse exécutive.
    """
    elems = []
    ticker   = _d(data, 'ticker', '')
    rec      = _d(data, 'recommendation', 'HOLD').upper()
    cur      = _d(data, 'currency', 'USD')
    upside   = _d(data, 'upside_str', '\u2014')
    tbase    = _d(data, 'target_price_full', '\u2014')
    pe_val   = _d(data, 'pe_ntm_str', '\u2014')
    ev_val   = _d(data, 'ev_ebitda_str', '\u2014')

    # Bullets thèse (positive_themes depuis data)
    pos_themes  = data.get('pos_themes_ic') or []
    cats        = data.get('catalysts') or []
    risk_themes = data.get('risk_themes') or []
    risk_full   = data.get('risk_themes_full') or []

    # ---- Bandeau titre --------------------------------------------------------
    rec_col = _rec_color(rec)
    banner_rows = [[
        Paragraph(f"<b>INVESTMENT CASE \u2014 {_safe(ticker)}</b>",
                  _s('ic_banner_t', size=12, bold=True, color=WHITE, leading=16)),
        Paragraph(
            f"<b>{rec}</b>   |   Cible : {_safe(tbase)}   |   Upside : {_safe(upside)}",
            _s('ic_banner_r', size=9, color=WHITE, leading=13, align=TA_RIGHT)),
    ]]
    banner_tbl = Table(banner_rows, colWidths=[90*mm, 80*mm])
    banner_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), NAVY),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elems.append(banner_tbl)
    elems.append(Spacer(1, 4*mm))

    # ---- Ligne 1 : Thèse | Risques (2 colonnes) ------------------------------
    S_BULL = _s('ic_bull', size=8.5, leading=13, color=GREY_TEXT)
    S_IC_H = _s('ic_hdr', size=9, bold=True, color=WHITE, leading=12)
    S_IC_B = _s('ic_b',   size=8.5, leading=12, color=GREY_TEXT, align=TA_JUSTIFY)

    # -- Colonne gauche : Thèse --
    left_elems = []

    # Sous-titre thèse
    h_these = Table([[Paragraph("TH\u00c8SE D'INVESTISSEMENT", S_IC_H)]],
                    colWidths=[82*mm])
    h_these.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), NAVY),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ('RIGHTPADDING',  (0,0), (-1,-1), 6),
    ]))
    left_elems.append(h_these)
    left_elems.append(Spacer(1, 2*mm))

    # Bullets thèse
    for i in range(3):
        txt = pos_themes[i] if i < len(pos_themes) else '\u2014'
        left_elems.append(Paragraph(
            f"\u2022  {_safe(txt)}", S_IC_B))
        left_elems.append(Spacer(1, 2*mm))

    left_elems.append(Spacer(1, 3*mm))

    # Sous-titre Catalyseurs
    h_cat = Table([[Paragraph("CATALYSEURS \u00c0 SURVEILLER (12M)", S_IC_H)]],
                  colWidths=[82*mm])
    h_cat.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), BUY_GREEN),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ('RIGHTPADDING',  (0,0), (-1,-1), 6),
    ]))
    left_elems.append(h_cat)
    left_elems.append(Spacer(1, 2*mm))

    for i in range(3):
        if i < len(cats):
            c_name = _d(cats[i], 'name', '\u2014')
            c_anal = _d(cats[i], 'analysis', '')
            _anal_limit = 220
            _anal_trim = c_anal[:_anal_limit] + ('\u2026' if len(c_anal) > _anal_limit else '')
            _inner = f"{_safe(c_name)}" + (f" \u2014 {_safe(_anal_trim)}" if c_anal else "")
        else:
            _inner = '\u2014'
        left_elems.append(Paragraph(f"\u2022  {_inner}", S_IC_B))
        left_elems.append(Spacer(1, 2*mm))

    left_col = Table([[e] for e in left_elems],
                     colWidths=[82*mm])
    left_col.setStyle(TableStyle([
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
    ]))

    # -- Colonne droite : Valorisation + Risques --
    right_elems = []

    # Sous-titre Valorisation
    h_val = Table([[Paragraph("VALORISATION SYNTH\u00c9TIQUE", S_IC_H)]],
                  colWidths=[82*mm])
    h_val.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), NAVY_LIGHT),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ('RIGHTPADDING',  (0,0), (-1,-1), 6),
    ]))
    right_elems.append(h_val)
    right_elems.append(Spacer(1, 2*mm))

    # Tableau valorisation — avec palier adaptatif
    val_h = [
        Paragraph("Multiple",         S_TH_L),
        Paragraph("Soci\u00e9t\u00e9", S_TH_C),
        Paragraph("R\u00e9f. secteur", S_TH_C),
    ]
    pe_ref  = _d(data, 'pe_ref_str',  '15\u201325x')
    ev_ref  = _d(data, 'ev_ref_str',  '8\u201318x')
    ps_val  = _d(data, 'ps_ratio_str', '\u2014')

    # Détection palier : si EV/EBITDA "—" mais revenue_ltm existe → palier 2
    _ev_missing = str(ev_val) in ('\u2014', '—', '', 'None', 'n.m.', None)
    _val_tier_note = ""
    val_rows = [
        [Paragraph("P/E NTM (x)",       S_TD_B),
         Paragraph(_safe(pe_val),        S_TD_C),
         Paragraph(_safe(pe_ref),        S_TD_C)],
    ]
    if _ev_missing and ps_val not in ('\u2014', '—', '', 'None'):
        # Palier 2 : afficher P/S au lieu de EV/EBITDA
        val_rows.append([
            Paragraph("P/S LTM (x) *",   S_TD_B),
            Paragraph(_safe(ps_val),      S_TD_C),
            Paragraph("1\u20138x",         S_TD_C)])
        _val_tier_note = "* Palier 2 : EBITDA n\u00e9gatif ou indisponible \u2014 valorisation via P/S (Price-to-Sales)."
    else:
        val_rows.append([
            Paragraph("EV/EBITDA (x)",    S_TD_B),
            Paragraph(_safe(ev_val),      S_TD_C),
            Paragraph(_safe(ev_ref),      S_TD_C)])
    val_rows.append([
        Paragraph(f"Cible DCF Base ({cur})", S_TD_B),
        Paragraph(_safe(tbase),         S_TD_C),
        Paragraph(f"Upside {_safe(upside)}", S_TD_C)])
    val_tbl = tbl([val_h] + val_rows, cw=[44*mm, 19*mm, 19*mm])
    right_elems.append(val_tbl)
    if _val_tier_note:
        right_elems.append(Spacer(1, 1*mm))
        right_elems.append(Paragraph(f"<i>{_val_tier_note}</i>", S_NOTE))
    right_elems.append(Spacer(1, 4*mm))

    # Sous-titre Risques
    h_risk = Table([[Paragraph("RISQUES PRINCIPAUX", S_IC_H)]],
                   colWidths=[82*mm])
    h_risk.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), SELL_RED),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ('RIGHTPADDING',  (0,0), (-1,-1), 6),
    ]))
    right_elems.append(h_risk)
    right_elems.append(Spacer(1, 2*mm))

    for i in range(3):
        risk_lbl  = risk_themes[i] if i < len(risk_themes) else '\u2014'
        risk_body = risk_full[i]   if i < len(risk_full)   else ''
        txt = _safe(risk_lbl)
        if risk_body and risk_body != risk_lbl:
            _body_limit = 260
            body_short = risk_body[:_body_limit] + ('\u2026' if len(risk_body) > _body_limit else '')
            txt = f"<b>{_safe(risk_lbl)}</b> \u2014 {_safe(body_short)}"
        else:
            txt = f"<b>{_safe(risk_lbl)}</b>"
        right_elems.append(Paragraph(f"\u2022  {txt}", S_IC_B))
        right_elems.append(Spacer(1, 2*mm))

    right_col = Table([[e] for e in right_elems],
                      colWidths=[82*mm])
    right_col.setStyle(TableStyle([
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
    ]))

    # ---- Assemblage 2 colonnes -----------------------------------------------
    two_col = Table(
        [[left_col, right_col]],
        colWidths=[86*mm, 84*mm],
    )
    two_col.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING',   (1,0), (1,0),   6),
    ]))
    elems.append(KeepTogether(two_col))
    elems.append(Spacer(1, 4*mm))
    elems.append(Paragraph(
        "Source : FinSight IA \u2014 Mod\u00e8le DCF interne, donn\u00e9es yfinance / Finnhub. "
        "Ce r\u00e9sum\u00e9 ne constitue pas un conseil en investissement.",
        S_NOTE))
    return elems


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
        elems.append(Paragraph("Lecture des indicateurs cl\u00e9s", S_SUBSECTION))
        elems.append(Spacer(1, 1*mm))
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
    if not scen_rows:
        scen_rows = [[Paragraph('\u2014', S_TD_C)] * 5]
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
    if not rows_is:
        rows_is = [[Paragraph('\u2014', S_TD_C)] * (n_cols + 1)]
    _cur_label = _d(data, 'currency', 'USD')
    elems.append(Paragraph(f"Compte de r\u00e9sultat consolid\u00e9 ({_cur_label} Md)", S_SUBSECTION))
    elems.append(KeepTogether(tbl([h_is] + rows_is, cw=cw_is)))
    elems.append(src(
        "FinSight IA \u2014 FMP, yfinance. LTM = 12 derniers mois. F = pr\u00e9visions mod\u00e8le interne."))
    elems.append(Spacer(1, 3*mm))

    elems.append(Image(area_buf, width=TABLE_W, height=76*mm))
    _area_src = ("FinSight IA \u2014 Revenus consolid\u00e9s \u2014 Source : yfinance."
                 if data.get('area_is_real')
                 else "FinSight IA \u2014 Revenus annuels (donn\u00e9es illustratives).")
    elems.append(src(_area_src))
    elems.append(Spacer(1, 3*mm))

    _fin_post = _d(data, 'financials_text_post')
    if _fin_post:
        elems.append(Paragraph("Trajectoire financi\u00e8re et perspectives", S_SUBSECTION))
        elems.append(Spacer(1, 1*mm))
        elems.append(Paragraph(_safe(_fin_post), S_BODY))
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
    if not rat_rows:
        rat_rows = [[Paragraph('\u2014', S_TD_C)] * 4]
    elems.append(KeepTogether([
        Paragraph("Positionnement relatif \u2014 Ratios cl\u00e9s vs. pairs sectoriels", S_SUBSECTION),
        Spacer(1, 1*mm),
        tbl([h_r] + rat_rows, cw=[50*mm, 30*mm, 55*mm, 35*mm]),
    ]))
    elems.append(src("FinSight IA \u2014 LTM = Last Twelve Months."))
    elems.append(Spacer(1, 3*mm))
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
    # Titre LLM analytique pour les ratios — traduit les chiffres en insights
    _ratio_title = (
        f"Lecture des ratios cl\u00e9s \u2014 {_ticker_f} vs pairs sectoriels"
    )
    _ratio_para = (
        f"L'EV/EBITDA ({_eve_v}\u00a0x vs {_eve_ref} sectoriel) mesure la cherté de l'entreprise "
        f"rapportée à sa capacité bénéficiaire opérationnelle : un multiple inférieur aux pairs "
        f"signale une sous-valorisation potentielle, un multiple supérieur traduit une prime de "
        f"croissance ou de qualité. Ici, le ratio est jugé « {_eve_lec} ». "
        f"La marge brute ({_gm_v} vs {_gm_ref}) révèle le pouvoir de fixation des prix et "
        f"l'avantage concurrentiel structurel : une marge élevée témoigne d'un fossé économique "
        f"(pricing power, barrières à l'entrée). Lecture : « {_gm_lec} ». "
        f"Le ROE ({_roe_v} vs {_roe_ref}) quantifie la rentabilité des capitaux propres et donc "
        f"la capacité du management à créer de la valeur pour l'actionnaire au-delà du coût du "
        f"capital. Appréciation : « {_roe_lec} ». "
        f"L'Altman Z-Score ({_az_v}, seuil de solvabilité : 2,99) est un indicateur composite "
        f"de santé financière intégrant liquidité, profitabilité, levier et rotation des actifs : "
        f"un score supérieur à 2,99 écarte le risque de détresse financière à horizon 2 ans. "
        f"Diagnostic : « {_az_lec} »."
    )
    elems.append(Spacer(1, 4*mm))
    elems.append(Paragraph(_safe(_ratio_title), S_SUBSECTION))
    elems.append(Spacer(1, 2*mm))
    elems.append(Paragraph(_safe(_ratio_para), S_BODY))

    # Graphique evolution des marges
    elems.append(Spacer(1, 4*mm))
    elems.append(Paragraph("Ratios de rentabilit\u00e9 \u2014 \u00c9volution", S_SUBSECTION))
    elems.append(Spacer(1, 2*mm))
    if margins_buf is not None:
        margins_buf.seek(0)
        elems.append(Image(margins_buf, width=TABLE_W, height=88*mm))
    else:
        elems.append(Paragraph("(Graphique marges non disponible)", S_NOTE))
    elems.append(src("FinSight IA \u2014 Marges calcul\u00e9es sur donn\u00e9es historiques yfinance."))
    elems.append(Spacer(1, 2*mm))
    _margins_comment = _d(data, 'ratios_text') or ''
    if not _margins_comment:
        _ticker_m = _d(data, 'ticker', 'La soci\u00e9t\u00e9')
        _margins_comment = (
            f"Le graphique pr\u00e9sente l'\u00e9volution des trois marges cl\u00e9s de {_ticker_m} "
            f"sur la p\u00e9riode historique et les exercices projet\u00e9s. "
            f"La marge brute refl\u00e8te l'efficacit\u00e9 op\u00e9rationnelle, "
            f"la marge EBITDA mesure la g\u00e9n\u00e9ration de cash avant capex, "
            f"et la marge nette traduit la rentabilit\u00e9 finale pour l'actionnaire."
        )
    elems.append(Paragraph("\u00c9volution des marges \u2014 interpr\u00e9tation", S_SUBSECTION))
    elems.append(Spacer(1, 1*mm))
    elems.append(Paragraph(_margins_comment, S_BODY))
    elems.append(Spacer(1, 4*mm))

    # Analyse LLM approfondie : qualité du mix, drivers de marge, positionnement concurrentiel
    _ticker_fin = _d(data, 'ticker', 'La soci\u00e9t\u00e9')
    _sector_fin = _d(data, 'sector', '')
    _ratios_lines = []
    _em = "\u2014"  # extrait hors de la f-string : Python <3.12 interdit \ dans une expression f-string
    for r in (data.get('ratios_vs_peers') or [])[:6]:
        _ratios_lines.append(f"{_d(r, 'label', '')}: {_d(r, 'value', _em)} "
                             f"(r\u00e9f {_d(r, 'reference', _em)})")
    _ratios_str = " | ".join(_ratios_lines) if _ratios_lines else "donn\u00e9es ratios non disponibles"

    _llm_margin_analysis = ""
    try:
        from core.llm_provider import LLMProvider
        _llm_m = LLMProvider(provider="groq", model="llama-3.3-70b-versatile")
        _prompt_margin = (
            f"Tu es un analyste sell-side senior (buy-side tier-1). R\u00e9dige une analyse "
            f"(270 mots) de la qualit\u00e9 op\u00e9rationnelle et du positionnement concurrentiel "
            f"de {_ticker_fin} (secteur {_sector_fin}).\n"
            f"Donn\u00e9es ratios cl\u00e9s : {_ratios_str}.\n\n"
            f"Structure en 3 paragraphes distincts s\u00e9par\u00e9s par une ligne vide :\n"
            f"1. Qualit\u00e9 des marges : drivers structurels (mix produit, pricing power, "
            f"effet de levier op\u00e9rationnel), durabilit\u00e9 dans le cycle actuel\n"
            f"2. Structure de co\u00fbts : intensit\u00e9 R&D/capex/marketing, barri\u00e8res "
            f"\u00e0 l'entr\u00e9e, vuln\u00e9rabilit\u00e9 aux chocs co\u00fbts mati\u00e8res premi\u00e8res/main d'oeuvre\n"
            f"3. Positionnement concurrentiel : moat (foss\u00e9 \u00e9conomique), avantages "
            f"structurels vs pairs sectoriels, risque d'\u00e9rosion comp\u00e9titive\n\n"
            f"Chaque paragraphe : 80-90 mots. Cite des chiffres pr\u00e9cis. "
            f"Fran\u00e7ais correct avec accents. "
            f"IMPORTANT : texte brut uniquement. "
            f"N'utilise AUCUNE balise HTML (<b>, <i>, <p>). "
            f"N'utilise AUCUN markdown (**, __, ##). "
            f"Pas de listes \u00e0 puces. Pas d'emojis."
        )
        _llm_margin_analysis = _llm_m.generate(_prompt_margin, max_tokens=700) or ""
    except Exception:
        pass

    if _llm_margin_analysis.strip():
        # Échappement léger : préserve les retours ligne, on force pas de HTML
        _cleaned = _llm_margin_analysis.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        # Double saut de ligne → nouveau paragraphe visuel
        _paras = [p.strip() for p in _cleaned.split('\n\n') if p.strip()]
        elems.append(Paragraph(
            "Qualit\u00e9 op\u00e9rationnelle et positionnement concurrentiel", S_SUBSECTION))
        elems.append(Spacer(1, 1*mm))
        for _p in _paras:
            # Remet les retours ligne simples en espaces pour wrapping propre
            _p_clean = _p.replace('\n', ' ')
            elems.append(Paragraph(_p_clean, S_BODY))
            elems.append(Spacer(1, 1.5*mm))
    return elems


def _build_valorisation(ff_buf, pie_buf, mc_buf, data):
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

    _dcf_fallback = not dcf_rows_b
    if _dcf_fallback:
        dcf_rows_b = [[Paragraph('\u2014', S_TD_C)] * 6]
    t_dcf = tbl([dcf_h] + dcf_rows_b, cw=[24*mm, 29*mm, 29*mm, 29*mm, 29*mm, 30*mm])
    if _dcf_fallback:
        br, bc = 1, 1  # seule ligne = fallback, ne pas depasser
    else:
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
    if not comp_rows:
        comp_rows = [[Paragraph('\u2014', S_TD_C)] * 6]
    elems.append(KeepTogether(tbl([comp_h] + comp_rows,
                                  cw=[52*mm, 24*mm, 24*mm, 20*mm, 26*mm, 24*mm])))
    elems.append(src("FinSight IA \u2014 FMP, consensus Bloomberg."))
    elems.append(Spacer(1, 4*mm))
    # Synthese valorisation — texte de transition (remplit l'espace page 6)
    _post_comp = _d(data, 'post_comp_text')
    if _post_comp:
        elems.append(Paragraph(_safe(_post_comp), S_BODY))
        elems.append(Spacer(1, 4*mm))

    # Donut + texte — titre lié au donut dans un KeepTogether (évite orphelin)
    _sec_for_title = _d(data, 'sector', '') or _d(data, 'pie_sector_name', '')
    _cap_lbl_title = _d(data, 'pie_cap_label', 'EV')
    _pie_title_txt = (f"Poids relatif {_cap_lbl_title} \u2014 positionnement "
                      f"sectoriel de la soci\u00e9t\u00e9")
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
    # Keep title + donut together
    elems.append(KeepTogether([
        Paragraph(_pie_title_txt, S_SUBSECTION),
        Spacer(1, 2*mm),
        pie_tbl,
    ]))
    elems.append(src(
        f"FinSight IA \u2014 EV proxy calcul\u00e9 sur cours au {_d(data, 'date_analyse')}. "
        "Donn\u00e9es illustratives."))
    elems.append(Spacer(1, 3*mm))

    # Football Field — titre LLM analytique
    _ticker_ff = _d(data, 'ticker', 'la soci\u00e9t\u00e9')
    elems.append(Paragraph(
        f"Football Field \u2014 Zone de convergence des valorisations de {_ticker_ff}", S_SUBSECTION))
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
    elems.append(Spacer(1, 4*mm))

    # Monte Carlo DCF — distribution + P10/P50/P90
    mc_p10 = data.get('dcf_mc_p10')
    mc_p50 = data.get('dcf_mc_p50')
    mc_p90 = data.get('dcf_mc_p90')
    mc_n   = data.get('dcf_mc_n_sim') or 0
    cur    = _d(data, 'currency', 'USD')
    if mc_p50 is not None:
        mc_h = [Paragraph(h, S_TH_C)
                for h in ["Percentile", "Cours pr\u00e9dit (12 mois)", "Lecture"]]
        mc_rows = [
            [Paragraph("P10 (sc\u00e9nario pessimiste)", S_TD_L),
             Paragraph(f"<b>{_fr(mc_p10, 0)}\u00a0{cur}</b>", S_TD_BC),
             Paragraph("9 trajectoires sur 10 terminent au-dessus", S_TD_L)],
            [Paragraph("P50 \u2014 m\u00e9diane", S_TD_BC),
             Paragraph(f"<b>{_fr(mc_p50, 0)}\u00a0{cur}</b>", S_TD_BC),
             Paragraph("Cours central probabiliste \u00e0 12 mois", S_TD_L)],
            [Paragraph("P90 (sc\u00e9nario optimiste)", S_TD_L),
             Paragraph(f"<b>{_fr(mc_p90, 0)}\u00a0{cur}</b>", S_TD_BC),
             Paragraph("9 trajectoires sur 10 terminent en dessous", S_TD_L)],
        ]
        _mc_tbl = tbl([mc_h] + mc_rows, cw=[52*mm, 36*mm, 82*mm])
        _PASTEL_BLUE = colors.HexColor('#C8D8F0')
        _mc_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 2), (-1, 2), _PASTEL_BLUE),
            ('TEXTCOLOR',  (0, 2), (-1, 2), BLACK),
            ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#1A7A4A')),
            ('TEXTCOLOR',  (0, 3), (-1, 3), WHITE),
        ]))
        _mc_desc = Paragraph(
            "Distribution probabiliste du cours \u00e0 12 mois issue de 10\u00a0000 simulations "
            "GBM (Geometric Brownian Motion). Le mod\u00e8le utilise la volatilit\u00e9 et la "
            "tendance historiques propres \u00e0 la soci\u00e9t\u00e9 (2 ans de donn\u00e9es journali\u00e8res). "
            "Ligne rouge = cours actuel.",
            S_BODY)
        elems.append(KeepTogether([
            Paragraph(
                "Monte Carlo GBM \u2014 Pr\u00e9diction probabiliste du cours \u00e0 12 mois",
                S_SUBSECTION),
            Spacer(1, 2*mm),
            _mc_desc,
            Spacer(1, 3*mm),
            _mc_tbl,
        ]))
        # Histogramme
        if mc_buf is not None:
            try:
                mc_buf.seek(0)
                _mc_img = Image(mc_buf, width=TABLE_W, height=TABLE_W * 3.0 / 8.0)
                elems.append(Spacer(1, 2*mm))
                elems.append(_mc_img)
            except Exception:
                pass
        _mc_sim_str = f"{mc_n:,}".replace(",", "\u00a0") if mc_n else "10\u00a0000"
        elems.append(src(
            f"FinSight IA \u2014 {_mc_sim_str} simulations GBM. "
            "Param\u00e8très : d\u00e9rive et volatilit\u00e9 annualis\u00e9es calcul\u00e9es sur 2 ans "
            "de donn\u00e9es journali\u00e8res propres \u00e0 la soci\u00e9t\u00e9 (yfinance). "
            "Ligne rouge = cours actuel."))
        # Titre LLM + commentaire d'interprétation sous le graphique
        elems.append(Spacer(1, 3*mm))
        elems.append(Paragraph(
            f"Interpr\u00e9tation probabiliste \u2014 trajectoire m\u00e9diane et dispersion \u00e0 12 mois",
            S_SUBSECTION))
        elems.append(Spacer(1, 2*mm))
        _price = data.get('ff_course') or data.get('current_price')
        if mc_p50 is not None and _price:
            _diff_pct = (mc_p50 / _price - 1) * 100 if _price > 0 else None
            if _diff_pct is not None and _diff_pct > 20:
                _mc_interp = (
                    f"Le mod\u00e8le GBM pr\u00e9dit un cours m\u00e9dian de {mc_p50:,.0f}\u00a0{cur} "
                    f"dans 12 mois, soit {_diff_pct:+.0f}\u00a0% par rapport au cours actuel "
                    f"({_price:,.0f}\u00a0{cur}). La fourchette P10\u2013P90 "
                    f"({mc_p10:,.0f}\u2013{mc_p90:,.0f}\u00a0{cur}) traduit la dispersion "
                    "historique du titre."
                )
            elif _diff_pct is not None and _diff_pct < -20:
                _mc_interp = (
                    f"Le mod\u00e8le GBM pr\u00e9dit un cours m\u00e9dian de {mc_p50:,.0f}\u00a0{cur} "
                    f"dans 12 mois, soit {_diff_pct:+.0f}\u00a0% par rapport au cours actuel "
                    f"({_price:,.0f}\u00a0{cur}). La fourchette P10\u2013P90 "
                    f"({mc_p10:,.0f}\u2013{mc_p90:,.0f}\u00a0{cur}) refl\u00e8te "
                    "la volatilit\u00e9 historique du titre."
                )
            else:
                _mc_interp = (
                    f"Le mod\u00e8le GBM pr\u00e9dit un cours m\u00e9dian de {mc_p50:,.0f}\u00a0{cur} "
                    f"dans 12 mois, proche du cours actuel ({_price:,.0f}\u00a0{cur}). "
                    f"La fourchette P10\u2013P90 ({mc_p10:,.0f}\u2013{mc_p90:,.0f}\u00a0{cur}) "
                    "d\u00e9limite le corridor de prix probable selon la volatilit\u00e9 historique."
                )
            # Enrichissement : comparaison P50 vs cible + interpretation volatilite
            _target_mc = data.get('target_price') or data.get('ff_course')
            _extra_mc  = ""
            if _target_mc and mc_p50:
                try:
                    _gap = (float(mc_p50) / float(_target_mc) - 1) * 100
                    if abs(_gap) > 5:
                        _extra_mc += (f" Le P50 GBM ({mc_p50:,.0f}\u00a0{cur}) "
                                      f"{('depasse' if _gap > 0 else 'reste sous')} "
                                      f"le prix cible analytique de {abs(_gap):.0f}\u00a0% "
                                      f"({'convergence haussiere' if _gap > 0 else 'scenario central plus conservateur que la cible DCF'}).")
                except Exception:
                    pass
            _syn_fc = ((data.get('synthesis') or {}).get('financial_commentary') or "")
            if _syn_fc and not _extra_mc:
                _extra_mc = " " + _syn_fc[:200] + ("..." if len(_syn_fc) > 200 else "")
            # Enrichissement : volatilite implicite + limite du modele GBM
            _vol = data.get('volatility_annualized') or data.get('hist_vol')
            _vol_note = ""
            if _vol is not None:
                try:
                    _vol_pct = float(_vol) * 100
                    _vol_note = (f" La volatilit\u00e9 annualis\u00e9e du titre ({_vol_pct:.0f}\u00a0%) "
                                 f"{'est élevée, amplifiant la dispersion des scenarios' if _vol_pct > 40 else 'est modérée, resserrant le corridor P10-P90'}. "
                                 "Le mod\u00e8le GBM suppose une distribution log-normale des rendements — "
                                 "les chocs exogenes (récession, r\u00e9gulation, disruption sectorielle) "
                                 "ne sont pas captur\u00e9s. Le P50 constitue un ancrage probabiliste, "
                                 "non un prix cible analytique.")
                except: pass
            if not _vol_note:
                _vol_note = (" Le mod\u00e8le GBM suppose une distribution log-normale des rendements — "
                             "les chocs exogenes (récession, r\u00e9gulation, disruption sectorielle) "
                             "ne sont pas captur\u00e9s. Le P50 est un ancrage probabiliste, "
                             "non un prix cible. Croiser avec le DCF et les comparables.")
            elems.append(Spacer(1, 3*mm))
            elems.append(Paragraph(_safe(_mc_interp + _extra_mc + _vol_note), S_BODY))
    return elems


def _build_extra_risk_scores(elems: list, data: dict):
    """
    Ajoute les sections Scoring Composite, M&A, Microstructure et Regime Macro
    a la fin de la section Risques. Rendu conditionnel : affiche seulement les
    donnees disponibles, jamais de bloc vide.
    """
    distress  = data.get('composite_distress')     or {}
    ma        = data.get('ma_score')               or {}
    micro     = data.get('microstructure')         or {}
    macro     = data.get('macro')                  or {}
    eq        = data.get('earnings_quality')       or {}
    cap_str   = data.get('capital_structure')      or {}
    div_sust  = data.get('dividend_sustainability') or {}

    has_distress = distress.get('score') is not None
    has_ma       = ma.get('score')       is not None
    has_eq       = eq.get('cash_conversion') is not None
    has_cap      = cap_str.get('short_term_ratio') is not None
    has_div      = div_sust.get('has_dividend') is True and div_sust.get('fcf_coverage') is not None
    has_micro    = bool(micro)
    has_macro    = macro.get('regime') not in (None, 'Inconnu')

    if not any([has_distress, has_ma, has_eq, has_cap, has_div, has_micro, has_macro]):
        return

    elems.append(KeepTogether([
        debate_q("Quels sont les niveaux de risque systemique et d\u2019attractivité M&A ?"),
        Spacer(1, 2*mm),
    ]))

    # --- Tableau Scoring Composite (Distress + M&A) -------------------------
    if has_distress or has_ma:
        _LABEL_COLOR = {
            'Sain':    BUY_GREEN, 'Modere': HOLD_AMB, 'Moderé': HOLD_AMB,
            'Vigilance': HOLD_AMB, 'Critique': SELL_RED,
            'Très attractive': BUY_GREEN, 'Attractive': BUY_GREEN,
            'Moderate': HOLD_AMB, 'Peu attractive': SELL_RED,
        }
        scoring_h = [
            Paragraph("Indicateur", S_TH_L),
            Paragraph("Score (0-100)", S_TH_C),
            Paragraph("Niveau", S_TH_C),
            Paragraph("Interpretation", S_TH_L),
        ]
        scoring_rows = []
        if has_distress:
            d_score = distress.get('score', 0)
            d_label = distress.get('label', '-')
            d_col   = _LABEL_COLOR.get(d_label, BLACK)
            # Interpretation : composantes
            comp = distress.get('components', {})
            az_c = comp.get('altman_z', {})
            bm_c = comp.get('beneish_m', {})
            interp_parts = []
            if az_c:
                interp_parts.append(f"Altman Z={az_c.get('value','?')} ({az_c.get('label','?')})")
            if bm_c:
                interp_parts.append(f"Beneish M={bm_c.get('value','?')} ({bm_c.get('label','?')})")
            interp_str = " \u00b7 ".join(interp_parts) or "Voir ratios ci-dessus"
            scoring_rows.append([
                Paragraph("Score Detresse Composite", S_TD_B),
                Paragraph(f"<b>{d_score}</b>", ParagraphStyle('sc', fontName='Helvetica-Bold',
                    fontSize=9, textColor=d_col, leading=12, alignment=1)),
                Paragraph(f"<b>{d_label}</b>", ParagraphStyle('sl', fontName='Helvetica-Bold',
                    fontSize=9, textColor=d_col, leading=12, alignment=1)),
                Paragraph(_safe(interp_str), S_TD_L),
            ])

        if has_ma:
            m_score = ma.get('score', 0)
            m_label = ma.get('label', '-')
            m_col   = _LABEL_COLOR.get(m_label, BLACK)
            signals = ma.get('signals', [])
            ma_interp = " \u00b7 ".join(signals[:2]) if signals else "Cf. ratios FCF/levier/valorisation"
            scoring_rows.append([
                Paragraph("Attractivité Cible M&A", S_TD_B),
                Paragraph(f"<b>{m_score}</b>", ParagraphStyle('ms', fontName='Helvetica-Bold',
                    fontSize=9, textColor=m_col, leading=12, alignment=1)),
                Paragraph(f"<b>{m_label}</b>", ParagraphStyle('ml', fontName='Helvetica-Bold',
                    fontSize=9, textColor=m_col, leading=12, alignment=1)),
                Paragraph(_safe(ma_interp), S_TD_L),
            ])

        # Earnings Quality row
        if has_eq:
            eq_cc    = eq.get('cash_conversion', 0.0)
            eq_label = eq.get('label', '-')
            eq_col   = colors.HexColor(f"#{eq.get('color', '1B3A6B')}")
            eq_sig   = eq.get('signal', '')
            eq_bm    = eq.get('bm_alert')
            eq_full  = _safe(eq_sig + (f' | {eq_bm}' if eq_bm else ''))
            scoring_rows.append([
                Paragraph("Qualité des earnings", S_TD_B),
                Paragraph(f"<b>{eq_cc:.2f}x</b>", ParagraphStyle('eqs', fontName='Helvetica-Bold',
                    fontSize=9, textColor=eq_col, leading=12, alignment=1)),
                Paragraph(f"<b>{eq_label}</b>", ParagraphStyle('eql', fontName='Helvetica-Bold',
                    fontSize=9, textColor=eq_col, leading=12, alignment=1)),
                Paragraph(eq_full, S_TD_L),
            ])

        # Dividend Sustainability row (conditional)
        if has_div:
            dv_cov   = div_sust.get('fcf_coverage', 0.0)
            dv_label = div_sust.get('label', '-')
            dv_col   = colors.HexColor(f"#{div_sust.get('color', '1B3A6B')}")
            dv_sig   = div_sust.get('signal', '')
            scoring_rows.append([
                Paragraph("Dividende — soutenabilite FCF", S_TD_B),
                Paragraph(f"<b>{dv_cov:.1f}x</b>", ParagraphStyle('dvs', fontName='Helvetica-Bold',
                    fontSize=9, textColor=dv_col, leading=12, alignment=1)),
                Paragraph(f"<b>{dv_label}</b>", ParagraphStyle('dvl', fontName='Helvetica-Bold',
                    fontSize=9, textColor=dv_col, leading=12, alignment=1)),
                Paragraph(_safe(dv_sig), S_TD_L),
            ])

        if scoring_rows:
            elems.append(tbl([scoring_h] + scoring_rows,
                              cw=[42*mm, 24*mm, 28*mm, 76*mm]))
            src_parts = [
                "Composite Distress : Altman Z (40%) + Beneish M (35%) + indicateurs bilan (25%). Score 0-100.",
                "M&A Score : FCF yield, levier, valorisation vs secteur, croissance.",
                "Qualité earnings : FCF/NI (>= 1.0x = excellente, < 0.4x = faible).",
            ]
            if has_div:
                src_parts.append("Dividende : couverture FCF/dividendes verses.")
            elems.append(src(" ".join(src_parts) + " Source : FinSight IA / yfinance."))
            elems.append(Spacer(1, 3*mm))

    # --- Tableau Microstructure + Regime Macro + Capital Structure ----------
    if has_micro or has_macro or has_cap:
        macro_h = [
            Paragraph("Indicateur", S_TH_L),
            Paragraph("Valeur", S_TH_C),
            Paragraph("Lecture", S_TH_L),
        ]
        macro_rows = []

        if has_macro:
            regime  = macro.get('regime', 'Inconnu')
            vix     = macro.get('vix')
            spread  = macro.get('yield_spread_10y_3m')
            rec_6m  = macro.get('recession_prob_6m')
            rec_lvl = macro.get('recession_level', 'Inconnu')

            vix_str    = f"VIX {vix:.0f}" if vix else '—'
            spread_str = f"Spread 10Y-3M : {spread:+.1f}%" if spread is not None else '—'
            rec_str    = f"{rec_6m}% a 6M ({rec_lvl})" if rec_6m is not None else '—'

            _REGIME_COLORS = {
                'Bull': BUY_GREEN, 'Bear': SELL_RED,
                'Volatile': HOLD_AMB, 'Transition': HOLD_AMB,
            }
            reg_col = _REGIME_COLORS.get(regime, BLACK)
            macro_rows.append([
                Paragraph("Régime de marche", S_TD_B),
                Paragraph(f"<b>{regime}</b>", ParagraphStyle('rg', fontName='Helvetica-Bold',
                    fontSize=9, textColor=reg_col, leading=12, alignment=1)),
                Paragraph(f"{vix_str}  \u00b7  {spread_str}", S_TD_L),
            ])
            macro_rows.append([
                Paragraph("Proba. récession", S_TD_B),
                Paragraph(rec_str, S_TD_C),
                Paragraph(
                    ("Environnement macro favorable aux actifs risques."
                     if (rec_6m or 0) < 25 else
                     "Prudence recommandee sur l'exposition cyclique."),
                    S_TD_L),
            ])

        # Capital Structure row
        if has_cap:
            cs_ratio = cap_str.get('short_term_ratio', 0.0)
            cs_label = cap_str.get('label', '-')
            cs_col   = colors.HexColor(f"#{cap_str.get('color', '1B3A6B')}")
            cs_sig   = cap_str.get('signal', '')
            macro_rows.append([
                Paragraph("Structure dette", S_TD_B),
                Paragraph(f"<b>{cs_label}</b>", ParagraphStyle('csl', fontName='Helvetica-Bold',
                    fontSize=9, textColor=cs_col, leading=12, alignment=1)),
                Paragraph(_safe(cs_sig), S_TD_L),
            ])

        if has_micro:
            amihud  = micro.get('amihud')
            roll    = micro.get('roll_spread')
            hl      = micro.get('hl_spread')
            liq_lbl = micro.get('liq_label', '—')
            a_str   = f"Amihud x10^6 : {amihud * 1e6:.3f}" if amihud else '—'
            r_str   = f"Roll spread : {roll:.3f}%" if roll else '—'
            hl_str  = f"H/L spread : {hl:.2f}%" if hl else '—'
            macro_rows.append([
                Paragraph("Liquidité de marche", S_TD_B),
                Paragraph(liq_lbl, S_TD_C),
                Paragraph(f"{a_str}  \u00b7  {r_str}  \u00b7  {hl_str}", S_TD_L),
            ])

        if macro_rows:
            elems.append(tbl([macro_h] + macro_rows,
                              cw=[42*mm, 30*mm, 98*mm]))
            src_parts2 = [
                "Régime : VIX + spread 10Y-3M + position S&P 500 vs MA200.",
                "Récession : indicateur de marche, non econometrique.",
                "Structure dette : proportion dette court terme / dette totale (seuil risque : > 40% CT).",
                "Liquidité : ratio Amihud (|ret|/vol$), Roll spread, proxy H/L.",
                "Source : FinSight IA / yfinance.",
            ]
            elems.append(src(" ".join(src_parts2)))
            elems.append(Spacer(1, 3*mm))


def _build_multiples_historiques(data):
    """Page PDF : Multiples de valorisation historiques P/E + EV/EBITDA sur 5 ans."""
    import math as _math_mh
    elems = []
    elems += section_title("Multiples Historiques de Valorisation", 4)
    elems.append(debate_q(
        "Comment ont \u00e9volu\u00e9 les multiples de valorisation sur 5 ans ? Y a-t-il expansion ou compression ?"))

    years_data = data.get('ratios_years_data') or []
    cur        = data.get('currency', 'USD')

    # ── Chart matplotlib P/E + EV/EBITDA ──
    if _MATPLOTLIB_OK and len(years_data) >= 2:
        try:
            labels  = [d['label']  for d in years_data]
            pe_vals = [d['pe']     for d in years_data]
            ev_vals = [d['ev_eb']  for d in years_data]
            x = list(range(len(labels)))

            fig, ax1 = plt.subplots(figsize=(6.5, 2.8))
            pe_plot = [v if v is not None else float('nan') for v in pe_vals]
            ev_plot = [v if v is not None else float('nan') for v in ev_vals]

            if any(v == v for v in pe_plot):
                ax1.plot(x, pe_plot, color='#1B3A6B', lw=2.2, marker='o', ms=5, label='P/E', zorder=4)
                ax1.fill_between(x, pe_plot, alpha=0.07, color='#1B3A6B')
            if any(v == v for v in ev_plot):
                ax1.plot(x, ev_plot, color='#1A7A4A', lw=2.2, marker='s', ms=5, ls='--', label='EV/EBITDA', zorder=4)

            # Auto-scale pour inclure toutes les séries
            _all_vals = [v for v in pe_plot + ev_plot if v == v]
            if _all_vals:
                _margin = (max(_all_vals) - min(_all_vals)) * 0.12 or 2.0
                ax1.set_ylim(max(0, min(_all_vals) - _margin), max(_all_vals) + _margin)

            ax1.set_xticks(x); ax1.set_xticklabels(labels, fontsize=8)
            ax1.set_ylabel('Multiple (x)', fontsize=8, color='#333')
            ax1.tick_params(axis='y', labelsize=7.5)
            ax1.legend(fontsize=7.5, loc='upper right', framealpha=0.9)
            ax1.spines['top'].set_visible(False); ax1.spines['right'].set_visible(False)
            ax1.spines['left'].set_color('#D0D5DD'); ax1.spines['bottom'].set_color('#D0D5DD')
            ax1.set_facecolor('white'); fig.patch.set_facecolor('white')
            ax1.grid(axis='y', alpha=0.25, color='#D0D5DD')
            plt.tight_layout(pad=0.8)
            buf_mh = io.BytesIO()
            fig.savefig(buf_mh, format='png', dpi=160, bbox_inches='tight')
            plt.close(fig); buf_mh.seek(0)
            elems.append(Image(buf_mh, width=130*mm, height=56*mm))
        except Exception as _e:
            log.warning("PDF multiples_historiques chart: %s", _e)

    # ── Tableau synthèse ──
    if years_data:
        elems.append(Spacer(1, 3*mm))
        elems.append(Paragraph("Tableau r\u00e9capitulatif des multiples", S_SUBSECTION))
        mh_h = [Paragraph(h, S_TH_C) for h in ["Ann\u00e9e", "P/E (x)", "EV/EBITDA (x)", "P/B (x)", "Tendance P/E"]]
        mh_rows = []
        pe_prev = None
        for d in years_data:
            pe_v = d['pe']; ev_v = d['ev_eb']; pb_v = d['pb']
            if pe_v is not None and pe_prev is not None:
                trend = "\u2197 Expansion" if pe_v > pe_prev else "\u2198 Compression"
                ts = S_TD_G if pe_v > pe_prev else S_TD_R
            else:
                trend = "\u2014"; ts = S_TD_C
            mh_rows.append([
                Paragraph(_safe(d['label']), S_TD_B),
                Paragraph(_safe(_fr(pe_v, 1) + 'x' if pe_v else '\u2014'), S_TD_C),
                Paragraph(_safe(_fr(ev_v, 1) + 'x' if ev_v else '\u2014'), S_TD_C),
                Paragraph(_safe(_fr(pb_v, 1) + 'x' if pb_v else '\u2014'), S_TD_C),
                Paragraph(_safe(trend), ts),
            ])
            if pe_v is not None: pe_prev = pe_v
        elems.append(KeepTogether(tbl([mh_h] + mh_rows, cw=[30*mm, 32*mm, 42*mm, 32*mm, 44*mm])))

    # ── Commentary analytique ──
    pe_clean = [d['pe'] for d in years_data if d['pe'] is not None]
    ev_clean = [d['ev_eb'] for d in years_data if d['ev_eb'] is not None]
    pb_clean = [d['pb']    for d in years_data if d.get('pb') is not None]
    if pe_clean and len(pe_clean) >= 2:
        delta = pe_clean[-1] - pe_clean[0]
        _dir  = "expansion multiple" if delta > 0 else "compression multiple"
        _ev_mov = ""
        if ev_clean and len(ev_clean) >= 2:
            _ev_delta = ev_clean[-1] - ev_clean[0]
            _ev_dir   = "expansion" if _ev_delta > 0 else "compression"
            _ev_label = ("signal que le march\u00e9 paye davantage l\u2019EBITDA operational"
                         if _ev_delta > 0 else
                         "refletant une moindre valorisation de la capacite b\u00e9n\u00e9ficiaire")
            _ev_mov = (f" L\u2019EV/EBITDA affiche une {_ev_dir} "
                       f"de {abs(_ev_delta):.1f}x ({ev_clean[0]:.1f}x -> {ev_clean[-1]:.1f}x), "
                       f"{_ev_label}.")
        _pb_note = ""
        if pb_clean and len(pb_clean) >= 2:
            _pb_delta = pb_clean[-1] - pb_clean[0]
            _pb_label = ("indiquant une dilution de la valeur comptable"
                         if _pb_delta < 0 else
                         "signe d\u2019une creation de valeur reconnue par le march\u00e9")
            _pb_note = (f" Le P/B de {pb_clean[0]:.1f}x \u00e0 {pb_clean[-1]:.1f}x, "
                        f"{_pb_label}.")
        _peers_note = ""
        _peers_ev = data.get('peers_median_ev_ebitda') or data.get('ev_ebitda_median_peers')
        if _peers_ev and ev_clean:
            try:
                _prem = (ev_clean[-1] / float(_peers_ev) - 1) * 100
                _peers_note = (f" La soci\u00e9t\u00e9 se n\u00e9gocie avec une "
                               f"{'prime' if _prem > 0 else 'décote'} de {abs(_prem):.0f}\u00a0% "
                               f"vs la m\u00e9diane des pairs sur l\u2019EV/EBITDA.")
            except Exception:
                pass
        _txt_fallback  = (f"Le P/E affiche une {_dir} de {abs(delta):.1f}x sur la p\u00e9riode "
                 f"({pe_clean[0]:.1f}x -> {pe_clean[-1]:.1f}x)."
                 + _ev_mov + _pb_note + _peers_note
                 + (" Un re-rating positif soutient la th\u00e8se haussi\u00e8re, mais amplifie le risque de valorisation." if delta > 0 else " La compression multiple refl\u00e8te une d\u00e9t\u00e9rioration du profil risk/reward et limite l\u2019upside."))

        # Enrichissement LLM — commentaire multi-paragraphes sur l'historique des multiples
        _llm_text_mh = ""
        try:
            from core.llm_provider import LLMProvider
            _llm = LLMProvider(provider="groq", model="llama-3.3-70b-versatile")
            _ticker_mh = _d(data, 'ticker', 'La soci\u00e9t\u00e9')
            _sector_mh = _d(data, 'sector', '')
            _pe_series = ", ".join(f"{pe:.1f}x" for pe in pe_clean)
            _ev_series = ", ".join(f"{ev:.1f}x" for ev in ev_clean) if ev_clean else "n.d."
            _pb_series = ", ".join(f"{pb:.1f}x" for pb in pb_clean) if pb_clean else "n.d."
            _peers_str = f" Médiane pairs EV/EBITDA: {_peers_ev:.1f}x." if _peers_ev else ""
            _prompt_mh = (
                f"Tu es un analyste sell-side senior. Rédige un commentaire analytique "
                f"(250 mots max) sur l'évolution des multiples de valorisation de {_ticker_mh} "
                f"sur 5 ans, secteur {_sector_mh}.\n"
                f"Données : P/E {_pe_series} | EV/EBITDA {_ev_series} | P/B {_pb_series}.{_peers_str}\n\n"
                f"Structure :\n"
                f"1. Lecture de la tendance P/E et EV/EBITDA (expansion/compression) avec hypothèses économiques\n"
                f"2. Analyse du mean-reversion potentiel et positionnement relatif aux pairs\n"
                f"3. Implications pour la thèse d'investissement (re-rating vs de-rating)\n"
                f"4. Risques spécifiques au cycle de valorisation actuel\n\n"
                f"Français correct avec accents. Pas de markdown. Pas d'emojis. "
                f"Cite les chiffres précis."
            )
            _llm_text_mh = _llm.generate(_prompt_mh, max_tokens=600) or ""
        except Exception:
            pass
        _txt = _llm_text_mh.strip() or _txt_fallback
    else:
        _txt = "Historique de multiples insuffisant pour \u00e9tablir une tendance significative."
    elems.append(Spacer(1, 3*mm))
    elems.append(Paragraph("Interpr\u00e9tation de l'historique des multiples", S_SUBSECTION))
    elems.append(Spacer(1, 1*mm))
    elems.append(Paragraph(_safe(_txt), S_BODY))
    elems.append(src("FinSight IA \u2014 yfinance, calculs internes."))
    return elems


def _build_capital_returns(data):
    """Page PDF : FCF yield, allocation du capital, dividendes et retour total."""
    elems = []
    elems += section_title("Capital Returns & Free Cash Flow", 5)
    elems.append(debate_q(
        "La soci\u00e9t\u00e9 g\u00e9n\u00e8re-t-elle un FCF suffisant pour financer sa croissance et r\u00e9mun\u00e9rer ses actionnaires ?"))

    years_data = data.get('ratios_years_data') or []
    cur        = data.get('currency', 'USD')

    # ── Chart FCF + Dividendes ──
    if _MATPLOTLIB_OK and years_data:
        try:
            labels_c = [d['label'] for d in years_data]
            fcf_c    = [d['fcf']       for d in years_data]
            div_c    = [abs(d['div_paid']) if d['div_paid'] is not None else 0 for d in years_data]
            x = list(range(len(labels_c)))

            fig, ax = plt.subplots(figsize=(6.5, 2.5))
            bw = 0.35
            import numpy as np2
            xarr = np2.array(x)
            bars1 = ax.bar(xarr - bw/2, [f/1000 if f else 0 for f in fcf_c], bw,
                           label='FCF (Mds)', color='#1A7A4A', alpha=0.85)
            bars2 = ax.bar(xarr + bw/2, [d/1000 for d in div_c], bw,
                           label='Div. vers\u00e9s (Mds)', color='#2E5FA3', alpha=0.85)
            ax.set_xticks(list(x)); ax.set_xticklabels(labels_c, fontsize=8)
            ax.set_ylabel(f"Mds {cur}", fontsize=8)
            ax.legend(fontsize=7.5, loc='upper left', framealpha=0.9)
            ax.tick_params(labelsize=7.5)
            ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('#D0D5DD'); ax.spines['bottom'].set_color('#D0D5DD')
            ax.set_facecolor('white'); fig.patch.set_facecolor('white')
            ax.grid(axis='y', alpha=0.25, color='#D0D5DD')
            plt.tight_layout(pad=0.8)
            buf_cr = io.BytesIO()
            fig.savefig(buf_cr, format='png', dpi=160, bbox_inches='tight')
            plt.close(fig); buf_cr.seek(0)
            elems.append(Image(buf_cr, width=130*mm, height=50*mm))
        except Exception as _e:
            log.warning("PDF capital_returns chart: %s", _e)

    # ── Tableau allocation ──
    if years_data:
        elems.append(Spacer(1, 3*mm))
        elems.append(Paragraph("Tableau d\u2019allocation du capital", S_SUBSECTION))
        cr_h = [Paragraph(h, S_TH_C) for h in ["Ann\u00e9e", "FCF", "FCF Yield", "Div. Payout", "Capex/Rev"]]
        cr_rows = []
        for d in years_data:
            cr_rows.append([
                Paragraph(_safe(d['label']), S_TD_B),
                Paragraph(_safe(_fr(d['fcf']/1000 if d['fcf'] else None, 1, ' Mds')), S_TD_C),
                Paragraph(_safe(_frpct(d['fcf_yield'])), S_TD_C),
                Paragraph(_safe(_frpct(d['div_pout']) if d.get('div_pout') is not None else "0%"),  S_TD_C),
                Paragraph(_safe(_frpct(d['capex_r'])),   S_TD_C),
            ])
        elems.append(KeepTogether(tbl([cr_h] + cr_rows, cw=[30*mm, 38*mm, 34*mm, 36*mm, 32*mm])))

    # ── Commentary ──
    fcf_vals  = [d['fcf']       for d in years_data if d['fcf'] is not None]
    fy_vals   = [d['fcf_yield'] for d in years_data if d['fcf_yield'] is not None]
    cx_vals   = [d['capex_r']   for d in years_data if d.get('capex_r') is not None]
    div_vals  = [d['div_paid']  for d in years_data if d.get('div_paid') is not None]
    if fcf_vals and len(fcf_vals) >= 2:
        delta_fcf = fcf_vals[-1] - fcf_vals[0]
        _dir = "croissance" if delta_fcf > 0 else "contraction"
        # Detection peak FCF (volatilite intra-periode)
        _fcf_peak = max(fcf_vals)
        _fcf_peak_idx = fcf_vals.index(_fcf_peak)
        _fcf_drawdown_note = ""
        if _fcf_peak > 0 and fcf_vals[-1] < _fcf_peak * 0.7 and _fcf_peak_idx < len(fcf_vals) - 1:
            _dd_pct = (1 - fcf_vals[-1] / _fcf_peak) * 100
            _fcf_drawdown_note = (
                f" Le FCF s\u2019est contract\u00e9 de {_dd_pct:.0f}\u202f% par rapport au pic de p\u00e9riode, "
                f"refl\u00e9tant un cycle d\u2019investissement \u00e9lev\u00e9 (capex) ou une pression sur le BFR.")
        _fy  = _frpct(fy_vals[-1]) if fy_vals else "\u2014"
        _capex_note = ""
        if cx_vals:
            _cx_avg = sum(cx_vals) / len(cx_vals)
            _capex_label = ("élevée, signe d\u2019un profil invest-heavy"
                            if _cx_avg and _cx_avg > 0.08 else
                            "modérée, compatible avec un profil générateur de FCF")
            _capex_note = (f" L\u2019intensit\u00e9 Capex/CA moyenne de {_frpct(_cx_avg)} "
                           f"({_capex_label}).")
        _div_note = ""
        div_any = any(d != 0 for d in div_vals if d is not None)
        if not div_any:
            _div_note = (" La soci\u00e9t\u00e9 n\u2019a vers\u00e9 aucun dividende sur la p\u00e9riode, "
                         "orient\u00e9e vers la croissance et le r\u00e9investissement interne.")
        elif div_vals:
            _div_last = abs(div_vals[-1]) / 1000 if div_vals[-1] else 0
            _div_note = f" Le versement de dividendes de {_fr(_div_last, 1)}\u00a0Mds t\u00e9moigne d\u2019un partage partiel de la valeur avec les actionnaires."
        _syn_note = ""
        _syn_fc = ((data.get('synthesis') or {}).get('financial_commentary') or "")
        if _syn_fc:
            _syn_note = " " + _syn_fc[:180] + ("..." if len(_syn_fc) > 180 else "")
        _fy_qual = ('est attractif pour un investisseur long-only (>4\u00a0%)'
                    if fy_vals and fy_vals[-1] and float(fy_vals[-1]) > 0.04
                    else 'reste modeste au regard du co\u00fbt du capital')
        # Payout ratio : enrichissement si disponible
        _payout_vals = [d['div_pout'] for d in years_data if d.get('div_pout') is not None]
        _payout_note = ""
        if _payout_vals:
            _pout_last = _payout_vals[-1]
            _pout_lbl = ("conservateur, pr\u00e9servant la flexibilit\u00e9 financi\u00e8re"
                         if _pout_last < 0.35
                         else ("mod\u00e9r\u00e9, \u00e9quilibrant distribution et r\u00e9investissement"
                               if _pout_last < 0.60
                               else "elev\u00e9, r\u00e9duisant la marge de s\u00e9curit\u00e9 du dividende"))
            _payout_note = (f" Le taux de distribution (payout) de {_frpct(_pout_last)} "
                            f"est {_pout_lbl}.")
        # Qualite FCF : conversion EBITDA -> FCF
        _fcf_conv_note = ""
        fcf_last = fcf_vals[-1] if fcf_vals else None
        ebitda_last = years_data[-1].get('ebitda') if years_data else None
        if fcf_last and ebitda_last and ebitda_last != 0:
            try:
                _conv = abs(float(fcf_last)) / abs(float(ebitda_last))
                _conv_excellent = "est excellente (>70\u00a0%), signe d\u2019un mod\u00e8le capital-light"
                _conv_standard  = "indique des besoins de capex ou BFR importants"
                _conv_qual = _conv_excellent if _conv > 0.7 else _conv_standard
                _fcf_conv_note = f" La conversion EBITDA->FCF de {_conv:.0%} {_conv_qual}."
            except: pass
        _txt_fallback = (f"La g\u00e9n\u00e9ration de FCF affiche une {_dir} de "
                f"{_fr(abs(delta_fcf)/1000, 1)}\u00a0Mds sur la p\u00e9riode. "
                f"Le FCF yield courant de {_fy} {_fy_qual}."
                + _fcf_drawdown_note + _capex_note + _payout_note + _fcf_conv_note + _div_note + _syn_note)

        # Enrichissement LLM
        _llm_text_cr = ""
        try:
            from core.llm_provider import LLMProvider
            _llm = LLMProvider(provider="groq", model="llama-3.3-70b-versatile")
            _ticker_cr = _d(data, 'ticker', 'La soci\u00e9t\u00e9')
            _sector_cr = _d(data, 'sector', '')
            _fcf_series = ", ".join(f"{f/1000:.1f}Mds" for f in fcf_vals[-4:])
            _fy_series = ", ".join(_frpct(f) for f in fy_vals[-4:]) if fy_vals else "n.d."
            _cx_last = _frpct(cx_vals[-1]) if cx_vals else "n.d."
            _prompt_cr = (
                f"Tu es un analyste sell-side senior. Rédige un commentaire "
                f"(250 mots) sur le Capital Returns & Free Cash Flow de {_ticker_cr} "
                f"(secteur {_sector_cr}).\n"
                f"Données : FCF sur 4 ans {_fcf_series} | FCF Yield {_fy_series} | "
                f"Capex/CA actuel {_cx_last}.\n\n"
                f"Structure :\n"
                f"1. Tendance de génération de cash et qualité du FCF (conversion EBITDA→FCF)\n"
                f"2. Politique d'allocation du capital (capex, dividendes, rachats, acquisitions)\n"
                f"3. Soutenabilité du modèle face au coût du capital\n"
                f"4. Implications pour la thèse d'investissement (profil cash generator vs growth reinvestment)\n\n"
                f"Français correct avec accents. Pas de markdown. Pas d'emojis. Cite les chiffres."
            )
            _llm_text_cr = _llm.generate(_prompt_cr, max_tokens=600) or ""
        except Exception:
            pass
        _txt = _llm_text_cr.strip() or _txt_fallback
    else:
        _txt = "Donn\u00e9es FCF insuffisantes pour l\u2019analyse de l\u2019allocation du capital."
    elems.append(Spacer(1, 3*mm))
    elems.append(Paragraph("Analyse du Capital Returns et g\u00e9n\u00e9ration de cash", S_SUBSECTION))
    elems.append(Spacer(1, 1*mm))
    elems.append(Paragraph(_safe(_txt), S_BODY))
    elems.append(src("FinSight IA \u2014 yfinance, cash flow statements."))
    return elems


def _build_lbo(data):
    """Page PDF : Analyse LBO — entry/exit multiples, levier, IRR/MOIC — niveau PE."""
    import math as _math_lbo
    elems = []
    elems += section_title("Analyse LBO \u2014 Leveraged Buyout", 6)
    elems.append(debate_q(
        "La soci\u00e9t\u00e9 est-elle une cible PE viable ? A quel prix d\u2019entr\u00e9e un fonds atteint-il un IRR de 20%+ ?"))

    years_data = data.get('ratios_years_data') or []
    cur        = data.get('currency', 'USD')

    # EBITDA + FCF LTM
    latest = years_data[-1] if years_data else {}
    ebitda_raw   = latest.get('ebitda')
    fcf_raw      = latest.get('fcf')
    net_debt_raw = latest.get('net_debt')
    rev_growth   = latest.get('rev_growth')

    ebitda   = float(ebitda_raw)   if ebitda_raw   is not None else None
    fcf      = float(fcf_raw)      if fcf_raw      is not None else None
    net_debt = float(net_debt_raw) if net_debt_raw is not None else None
    _g_rate  = min(float(rev_growth), 0.20) if rev_growth and float(rev_growth) > 0.001 else 0.05

    # ── Hypothèses ──
    entry_multiples = [8.0, 10.0, 12.0, 14.0]
    exit_multiples  = [8.0, 10.0, 12.0]
    leverage_ratio  = 4.0
    hold_years      = 5
    debt_repay_pct  = 0.50

    def _lbo_irr(em, xm):
        if ebitda is None or ebitda <= 0: return None, None
        entry_ev     = ebitda * em
        entry_debt   = min(ebitda * leverage_ratio, entry_ev * 0.65)
        entry_equity = max(entry_ev - entry_debt, 1)
        ebitda_exit  = ebitda * ((1 + _g_rate) ** hold_years)
        exit_ev      = ebitda_exit * xm
        exit_debt    = entry_debt * (1 - debt_repay_pct)
        exit_equity  = max(exit_ev - exit_debt, 0.01)
        moic = exit_equity / entry_equity
        irr  = moic ** (1 / hold_years) - 1
        return irr, moic

    # ── Table IRR/MOIC ──
    exit_hdrs = [f"Exit {xm:.0f}x" for xm in exit_multiples]
    irr_h = [Paragraph("Entry mult.", S_TH_L)] + [Paragraph(h, S_TH_C) for h in exit_hdrs]
    irr_rows_pdf = []
    irr_styles   = []
    for ri, em in enumerate(entry_multiples):
        row = [Paragraph(f"{em:.0f}x EBITDA", S_TD_B)]
        for ci_idx, xm in enumerate(exit_multiples):
            irr, moic = _lbo_irr(em, xm)
            if irr is not None:
                cell_txt = f"{irr*100:.1f}% / {moic:.1f}x"
                if irr >= 0.20:
                    st = S_TD_G
                    irr_styles.append(('BACKGROUND', (ci_idx+1, ri+1), (ci_idx+1, ri+1),
                                       colors.HexColor('#EAF4EF')))
                elif irr >= 0.15:
                    st = S_TD_A
                    irr_styles.append(('BACKGROUND', (ci_idx+1, ri+1), (ci_idx+1, ri+1),
                                       colors.HexColor('#FDF6E8')))
                else:
                    st = S_TD_R
                    irr_styles.append(('BACKGROUND', (ci_idx+1, ri+1), (ci_idx+1, ri+1),
                                       colors.HexColor('#FAF0EF')))
            else:
                cell_txt = "\u2014"; st = S_TD_C
            row.append(Paragraph(_safe(cell_txt), st))
        irr_rows_pdf.append(row)

    cws = [40*mm] + [43*mm] * len(exit_multiples)
    t_irr = tbl([irr_h] + irr_rows_pdf, cw=cws)
    if irr_styles:
        t_irr.setStyle(TableStyle(irr_styles))
    elems.append(KeepTogether(t_irr))
    elems.append(Paragraph(
        f"Hypoth\u00e8ses : Levier {leverage_ratio:.0f}x EBITDA \u00b7 {hold_years} ans holding "
        f"\u00b7 {debt_repay_pct*100:.0f}% remboursement \u00b7 EBITDA +{_g_rate*100:.0f}%/an  "
        f"\u25cf vert \u2265 20% \u25cf ambre 15\u201320% \u25cf rouge < 15%",
        S_NOTE))
    elems.append(Spacer(1, 4*mm))

    # ── Paramètres LBO ──
    elems.append(Paragraph("Param\u00e8très LBO LTM", S_SUBSECTION))
    _hypo = [
        ("EBITDA LTM",          _fr(ebitda/1000 if ebitda else None, 1) + f" Mds {cur}"),
        ("FCF LTM",             _fr(fcf/1000    if fcf    else None, 1) + f" Mds {cur}"),
        ("Levier PE",           f"{leverage_ratio:.0f}x EBITDA"),
        ("Dette d\u2019entr\u00e9e",
         _fr(ebitda * leverage_ratio / 1000 if ebitda else None, 1) + f" Mds {cur}"),
        ("EBITDA exit (est.)",
         _fr(ebitda * ((1+_g_rate)**hold_years) / 1000 if ebitda else None, 1) + f" Mds {cur}"),
        ("IRR cible tier-1",    "\u2265 20%"),
    ]
    lbo_h = [Paragraph("Param\u00e8tre", S_TH_L), Paragraph("Valeur", S_TH_C)]
    lbo_rows = [[Paragraph(_safe(k), S_TD_B), Paragraph(_safe(v), S_TD_C)] for k, v in _hypo]
    elems.append(KeepTogether(tbl([lbo_h] + lbo_rows, cw=[90*mm, 80*mm])))
    elems.append(Spacer(1, 4*mm))

    # ── Commentary ──
    irr_base, moic_base = _lbo_irr(10.0, 10.0)
    if irr_base is not None:
        _signal = "attractive" if irr_base >= 0.20 else ("limite (15-20%)" if irr_base >= 0.15 else "insuffisanté (<15%)")
        # Chercher le multiple d'entree max qui delivre IRR >= 20%
        _entry_20_max = next((em for em in entry_multiples if (_lbo_irr(em, 10.0)[0] or 0) >= 0.20), None)
        _entry_note = (f"Un fonds tier-1 ciblant \u226520% IRR doit entrer \u2264{_entry_20_max:.0f}x EBITDA."
                       if _entry_20_max else "Aucun multiple d'entree standard ne delivre un IRR >= 20% avec sortie a 10x.")
        # Qualite du levier : ratio debt/ebitda
        _net_debt_ebitda = (net_debt / ebitda) if (net_debt is not None and ebitda and ebitda > 0) else None
        if _net_debt_ebitda is not None:
            _lev_comment = (f"La dette nette actuelle repr\u00e9sente {_net_debt_ebitda:.1f}x EBITDA, "
                            + ("un levier \u00e9lev\u00e9 qui limite l'espace d'endettement additionnel. "
                               if _net_debt_ebitda > 3.0
                               else "un levier raisonnable qui pr\u00e9serve la capacit\u00e9 de LBO. "))
        else:
            _lev_comment = ""
        # FCF comme moteur de desendettement
        _fcf_abs_mds = fcf / 1000 if fcf else None
        _fcf_comment = (f"La FCF génération ({_fr(_fcf_abs_mds, 1)} Mds) constitue le moteur de d\u00e9sendettement : "
                        f"un rem boursement de {debt_repay_pct*100:.0f}% de la dette en {hold_years} ans suppose "
                        f"un FCF stable ou croissant sur la p\u00e9riode de holding. "
                        if _fcf_abs_mds else "")
        _txt_fallback = (f"A 10x EBITDA d\u2019entr\u00e9e / 10x de sortie, le LBO g\u00e9n\u00e8re un IRR "
                f"de {irr_base*100:.1f}% (MOIC {moic_base:.1f}x) \u2014 attractivit\u00e9 PE {_signal}. "
                f"{_entry_note} "
                f"{_lev_comment}"
                f"{_fcf_comment}"
                f"La viabilit\u00e9 LBO reste conditionnelle \u00e0 la visibilit\u00e9 du free cash flow, "
                f"au niveau de taux d\u2019int\u00e9r\u00eat sur la dette senior, et \u00e0 la capacit\u00e9 "
                f"du management \u00e0 ex\u00e9cuter le plan op\u00e9rationnel dans un environnement de levier {leverage_ratio:.0f}x.")

        # Enrichissement LLM — commentaire LBO détaillé
        _llm_text_lbo = ""
        try:
            from core.llm_provider import LLMProvider
            _llm = LLMProvider(provider="groq", model="llama-3.3-70b-versatile")
            _ticker_lbo = _d(data, 'ticker', 'La soci\u00e9t\u00e9')
            _sector_lbo = _d(data, 'sector', '')
            _ebitda_lbo = f"{ebitda/1000:.1f} Mds" if ebitda else "n.d."
            _fcf_lbo = f"{fcf/1000:.1f} Mds" if fcf else "n.d."
            _debt_lbo = f"{_net_debt_ebitda:.1f}x EBITDA" if _net_debt_ebitda is not None else "n.d."
            _prompt_lbo = (
                f"Tu es un analyste Private Equity senior (profil MD dans un fonds tier-1). "
                f"R\u00e9dige un commentaire (270 mots) sur la viabilit\u00e9 LBO de {_ticker_lbo} "
                f"(secteur {_sector_lbo}).\n"
                f"Donn\u00e9es : EBITDA LTM {_ebitda_lbo}, FCF LTM {_fcf_lbo}, "
                f"dette nette actuelle {_debt_lbo}, IRR base (10x/10x) {irr_base*100:.1f}%, "
                f"MOIC {moic_base:.1f}x.\n\n"
                f"Structure :\n"
                f"1. Attractivit\u00e9 en tant que cible PE : forces du mod\u00e8le \u00e9conomique pour un LBO\n"
                f"2. Capacit\u00e9 d'endettement et levier soutenable (FCF/int\u00e9r\u00eats, couverture)\n"
                f"3. Leviers de cr\u00e9ation de valeur post-acquisition (op\u00e9rationnel, financier, multiple arbitrage)\n"
                f"4. Risques sp\u00e9cifiques au LBO (volatilit\u00e9 FCF, cyclicit\u00e9, risque de refinancement)\n\n"
                f"Fran\u00e7ais correct avec accents. Pas de markdown. Pas d'emojis. Cite les chiffres."
            )
            _llm_text_lbo = _llm.generate(_prompt_lbo, max_tokens=650) or ""
        except Exception:
            pass
        _txt = _llm_text_lbo.strip() or _txt_fallback
    else:
        _txt = "EBITDA LTM non disponible \u2014 analyse LBO indicative impossible."
    elems.append(Paragraph("Analyse de viabilit\u00e9 PE", S_SUBSECTION))
    elems.append(Spacer(1, 1*mm))
    elems.append(Paragraph(_safe(_txt), S_BODY))
    elems.append(Paragraph(
        "Note : Analyse indicative uniquement. Ne tient pas compte des frais de transaction, "
        "de la structure fiscale optimis\u00e9e ni du management package. "
        "Sources : FinSight IA, calculs internes.", S_DISC))
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
    _inv_fallback = "D\u00e9gradation significative des fondamentaux sur 2 trimestrès cons\u00e9cutifs."
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
    elems.append(Spacer(1, 4*mm))

    # Zone d'entrée optimale (Chantier 3)
    ez_conds   = data.get('entry_zone_conditions') or []
    ez_sat     = data.get('entry_zone_satisfied_count')
    ez_all_met = data.get('entry_zone_all_met', False)
    ez_wr      = data.get('entry_zone_backtest_wr')
    ez_n       = data.get('entry_zone_backtest_n') or 0
    ez_note    = data.get('entry_zone_backtest_note') or ''
    ez_h = [Paragraph(h, S_TH_C)
            for h in ["Condition", "Seuil / Crit\u00e8re", "Valeur observee", "Statut"]]
    ez_rows = []
    for c in ez_conds:
        sat  = c.get('satisfied', False)
        val  = c.get('value')
        sty  = S_TD_G if sat else S_TD_R
        icon = "OK" if sat else "NON"
        val_str = str(val) if val is not None else '\u2014'
        ez_rows.append([
            Paragraph(_safe(c.get('name', '')), S_TD_B),
            Paragraph(_safe(c.get('threshold', '') or '\u2014'), S_TD_L),
            Paragraph(_safe(val_str), S_TD_C),
            Paragraph(f"<b>{icon}</b>", sty),
        ])
    if not ez_rows:
        ez_rows = [[Paragraph('\u2014', S_TD_C)] * 4]

    if ez_sat is not None:
        _ez_verdict_txt = (
            f"Toutes les conditions satisfaites \u2014 zone d\u2019entr\u00e9e signal\u00e9e ({ez_sat}/5)"
            if ez_all_met else
            f"{ez_sat}/5 conditions satisfaites \u2014 entr\u00e9e non d\u00e9clench\u00e9e"
        )
    else:
        _ez_verdict_txt = "Zone d\u2019entr\u00e9e non calcul\u00e9e"

    _ez_bt_txt = ''
    if ez_note and 'insuffisant' in ez_note.lower():
        _ez_bt_txt = f"Backtest : {ez_note}"
    elif ez_wr is not None and ez_n:
        _ez_bt_txt = (f"Backtest 5 ans : {_frpct(ez_wr)} de retours positifs a 12 mois "
                      f"quand toutes les conditions etaient reunies (N={ez_n}).")
    elif ez_n:
        _ez_bt_txt = f"Backtest 5 ans : N={ez_n} occurrences."

    elems.append(KeepTogether([
        debate_q("Toutes les conditions d\u2019entr\u00e9e optimale sont-elles reunies ?"),
        Spacer(1, 1*mm),
        Paragraph(_ez_verdict_txt, S_BODY),
        Spacer(1, 2*mm),
        tbl([ez_h] + ez_rows, cw=[62*mm, 60*mm, 30*mm, 18*mm]),
    ]))
    if _ez_bt_txt:
        elems.append(src(_ez_bt_txt))
    elems.append(Spacer(1, 4*mm))

    # ── Scoring Composite + Environnement Macro ────────────────────────────
    _build_extra_risk_scores(elems, data)

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
            Paragraph(_d(r, 'révision'), rs),
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

    # Methodologie & Hypotheses — section étoffée (alignée cmp société)
    _wacc_str = _d(data, 'wacc_str', 'N/A')
    _tgr_str  = _d(data, 'tgr_str',  'N/A')
    _beta_str = _d(data, 'beta_str', 'N/A')
    _rf_str   = _d(data, 'rf_str',   'N/A')
    _erp_str  = _d(data, 'erp_str',  'N/A')
    elems.append(KeepTogether([
        Paragraph("M\u00e9thodologie &amp; Hypoth\u00e8ses", S_SUBSECTION),
        Spacer(1, 2*mm),
        Paragraph(
            f"<b>Mod\u00e8le DCF (Discounted Cash Flow)</b> \u2014 La valorisation par actualisation des flux de "
            f"tr\u00e9sorerie repose sur un horizon explicite de cinq ans, prolongé par une valeur "
            f"terminale en perpétuité de Gordon-Shapiro. Le coût moyen pondéré du capital (WACC) retenu "
            f"est de {_wacc_str}, le taux de croissance terminal (TGR) de {_tgr_str}. "
            f"Le WACC est estimé via le modèle CAPM : taux sans risque {_rf_str} (OAT/Treasury 10 ans), "
            f"prime de risque marché {_erp_str} (consensus Damodaran), bêta {_beta_str} (régression "
            f"sur 2 ans de rendements hebdomadaires vs l'indice de référence). Les flux de trésorerie "
            f"disponibles (FCF) sont projetés sur la base des taux de croissance historiques ajustés "
            f"du consensus analystes. La valeur terminale représente typiquement 60-80\u00a0% de la "
            f"valeur d'entreprise, d'où la sensibilité élevée au TGR et au WACC.",
            S_BODY),
        Spacer(1, 2*mm),
        Paragraph(
            f"<b>Analyse de sensibilité</b> \u2014 La table de sensibilité présente "
            f"la valeur intrinsèque estimée pour une plage de WACC (\u00b12\u00a0pp) "
            f"et de TGR (\u00b11\u00a0pp) autour du scénario central. Ce croisement bidimensionnel "
            f"permet de visualiser l'impact marginal de chaque paramètre sur la valorisation. "
            f"Une hausse de 100\u00a0bps du WACC comprime la valeur d'environ 12\u00a0%. "
            f"La diagonale du tableau représente les combinaisons les plus probables. Les cases "
            f"extrêmes (WACC bas / TGR haut) sont peu réalistes et servent de borne supérieure.",
            S_BODY),
        Spacer(1, 2*mm),
        Paragraph(
            "<b>Multiples de valorisation (Comparables)</b> \u2014 Les multiples EV/EBITDA, EV/Revenue "
            "et P/E sont calculés sur la base des douze derniers mois (LTM) et comparés "
            "à un panel de 4-5 pairs sectoriels sélectionnés par proximité de modèle économique, "
            "de taille et de géographie. Les fourchettes de référence sont calibrées au percentile "
            "25-75 du panel. Un multiple au-dessus du P75 signale une prime de croissance ou de "
            "qualité ; en dessous du P25, une décote potentielle. Le Football Field confronte "
            "les résultats des trois approches (DCF, comparables, Monte Carlo) pour identifier "
            "les zones de convergence et renforcer la robustesse de la cible.",
            S_BODY),
        Spacer(1, 2*mm),
        Paragraph(
            "<b>Monte Carlo (Geometric Brownian Motion)</b> \u2014 10\u00a0000 trajectoires de prix "
            "sont simulées sur 252 jours de bourse en utilisant la dérive et la volatilité "
            "annualisées estimées sur 2 ans de données journalières. Le modèle GBM suppose une "
            "distribution log-normale des rendements et ne capture pas les chocs exogènes "
            "(récession, régulation, disruption). Les percentiles P10/P50/P90 délimitent le "
            "corridor probabiliste du cours à 12 mois.",
            S_BODY),
        Spacer(1, 2*mm),
        Paragraph(
            "<b>Sentiment de marché</b> \u2014 L'analyse de sentiment combine deux approches : "
            "(1) FinBERT (ProsusAI/finbert), modèle NLP pré-entraîné sur un corpus financier "
            "anglophone, appliqué aux titrès d'articles Finnhub ; (2) classification LLM "
            "(Groq llama-3.3-70b) pour les articles en français. Le score agrégé pondère les "
            "résultats sur un corpus de 7 jours. Le sentiment est un indicateur contrarian : "
            "un pessimisme extrême peut signaler un point d'entrée, un optimisme excessif un "
            "risque de correction.",
            S_BODY),
        Spacer(1, 2*mm),
        Paragraph(
            "<b>M\u00e9triques alternatives de valorisation (paliers)</b> \u2014 Lorsque "
            "l'EV/EBITDA n'est pas applicable (EBITDA n\u00e9gatif), FinSight bascule sur des "
            "multiples adapt\u00e9s au profil de la soci\u00e9t\u00e9 : "
            "<b>P/S (Price-to-Sales)</b> pour les soci\u00e9t\u00e9s en croissance sans "
            "profitabilit\u00e9 \u00e9tablie (SaaS, biotech avanc\u00e9e) ; "
            "<b>EV/Gross Profit</b> pour celles \u00e0 marge brute positive mais EBITDA "
            "n\u00e9gatif (R&amp;D lourd) ; "
            "<b>Rule of 40</b> (croissance revenue % + marge EBITDA % &gt; 40 = sant\u00e9 "
            "op\u00e9rationnelle d\u00e9montr\u00e9e) pour les SaaS. "
            "Le <b>palier de valorisation</b> est indiqu\u00e9 dans le tableau de synth\u00e8se : "
            "Palier 1 = profitable (EV/EBITDA), Palier 2 = croissance (P/S), "
            "Palier 3 = pr\u00e9-revenue (P/B).",
            S_BODY),
        Spacer(1, 2*mm),
        Paragraph(
            "<b>Sources de données</b> \u2014 Cours et fondamentaux : yfinance (Yahoo Finance API). "
            "News et événements : Finnhub, flux RSS Yahoo Finance. Comparables et ratios : FMP "
            "(Financial Modeling Prep, plan gratuit). Les données peuvent présenter un décalage "
            "de 15-20 minutes par rapport au temps réel. Les estimations consensus sont indicatives.",
            S_BODY),
    ]))
    elems.append(Spacer(1, 6*mm))

    # Glossaire retiré du PDF — disponible uniquement sur l'interface Streamlit

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
# =============================================================================
# SCORES ADDITIONNELS : Composite Distress + M&A + Microstructure + Macro
# =============================================================================

def _compute_extra_scores(ticker: str, yr_r) -> dict:
    """
    Calcule les scores additionnels injectes dans data pour Section 4 (Risques).
    Appele depuis _state_to_data. Echec silencieux : retourne dict vide.
    """
    result = {}

    # -- Composite Distress Score -------------------------------------------
    if yr_r is not None:
        try:
            from agents.agent_quant import compute_composite_distress
            result['composite_distress'] = compute_composite_distress(yr_r)
        except Exception as _e:
            log.warning("[extra_scores] composite_distress: %s", _e)

    # -- M&A Attractiveness Score -------------------------------------------
    if yr_r is not None:
        try:
            from agents.agent_quant import compute_ma_score
            result['ma_score'] = compute_ma_score(yr_r)
        except Exception as _e:
            log.warning("[extra_scores] ma_score: %s", _e)

    # -- Earnings Quality (cash conversion FCF/NI) --------------------------
    if yr_r is not None:
        try:
            from agents.agent_quant import compute_earnings_quality
            result['earnings_quality'] = compute_earnings_quality(yr_r)
        except Exception as _e:
            log.warning("[extra_scores] earnings_quality: %s", _e)

    # -- Capital Structure (short-term debt ratio) --------------------------
    if yr_r is not None:
        try:
            from agents.agent_quant import compute_capital_structure
            result['capital_structure'] = compute_capital_structure(yr_r)
        except Exception as _e:
            log.warning("[extra_scores] capital_structure: %s", _e)

    # -- Dividend Sustainability (FCF coverage) -----------------------------
    if yr_r is not None:
        try:
            from agents.agent_quant import compute_dividend_sustainability
            result['dividend_sustainability'] = compute_dividend_sustainability(yr_r)
        except Exception as _e:
            log.warning("[extra_scores] dividend_sustainability: %s", _e)

    # -- Microstructure -----------------------------------------------------
    if ticker:
        try:
            from agents.agent_quant import compute_microstructure
            result['microstructure'] = compute_microstructure(ticker)
        except Exception as _e:
            log.warning("[extra_scores] microstructure: %s", _e)

    # -- Macro Regime + Recession -------------------------------------------
    try:
        from agents.agent_macro import AgentMacro
        result['macro'] = AgentMacro().analyze()
    except Exception as _e:
        log.warning("[extra_scores] macro: %s", _e)

    return result


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
    mc_buf      = _safe_chart(_make_mc_histogram,    'mc')
    # Rewind tous les buffers — defensive : evite les renders vides si le buffer
    # avait ete partiellement lu lors d'une validation precedente
    for _b in (perf_buf, ff_buf, pie_buf, area_buf, margins_buf, mc_buf):
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

    # Page Investment Case (JPM-style) — insérée avant la synthèse exécutive
    story += _build_investment_case(data)
    story.append(PageBreak())

    story += _build_synthese(perf_buf, data)
    story += _build_financials(area_buf, data, margins_buf)
    story.append(PageBreak())
    story += _build_valorisation(ff_buf, pie_buf, mc_buf, data)
    story.append(PageBreak())
    try:
        story += _build_multiples_historiques(data)
        story.append(PageBreak())
    except Exception as _e_mh:
        log.error("[PDFWriter] _build_multiples_historiques FAILED: %s", _e_mh, exc_info=True)
    try:
        story += _build_capital_returns(data)
        story.append(PageBreak())
    except Exception as _e_cr:
        log.error("[PDFWriter] _build_capital_returns FAILED: %s", _e_cr, exc_info=True)
    try:
        story += _build_lbo(data)
        story.append(PageBreak())
    except Exception as _e_lbo:
        log.error("[PDFWriter] _build_lbo FAILED: %s", _e_lbo, exc_info=True)
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
    Les valeurs financieres dans FinancialYear sont toujours en millions (yfinance + LLM prompt).
    Si le LLM retourne une valeur en EUR/USD absolu (>1e9), normalise automatiquement en millions."""
    if v is None: return "\u2014"
    try:
        f = float(v)
        if abs(f) > 1_000_000_000:  # valeur en absolu (ex: 195_000_000_000 EUR) → convertir en millions
            f = f / 1_000_000
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

def _valid_hist_labels_pdf(snap) -> list:
    """Retourne les annees triees avec CA disponible et positif (exclut annees sans données yfinance)."""
    if not (snap and snap.years):
        return []
    result = []
    for y, fy in snap.years.items():
        if fy is None:
            continue
        # Inclure uniquement les annees avec un CA positif (exclut None et 0)
        rev = getattr(fy, 'revenue', None)
        if rev is None:
            continue
        try:
            if float(rev) <= 0:
                continue
        except (ValueError, TypeError):
            continue
        result.append(y)
    return sorted(result, key=lambda y: str(y).replace("_LTM", ""))


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
    """Fetch 8 derniers trimestrès de revenus (total ou par segment via yfinance)."""
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
                    if cur and cur not in ('USD', 'GBp', 'GBP', 'EUR', 'CHF', 'CAD'):
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

        if len(ev_data) < 1:
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
        snap       = state.get('raw_data')
        ratios     = state.get('ratios')
        synthesis  = state.get('synthesis')   or {}
        sentiment  = state.get('sentiment')   or {}
        devil      = state.get('devil')       or {}
        entry_zone = state.get('entry_zone')

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
        hist_labels = _valid_hist_labels_pdf(snap) if snap else []
        latest_l    = hist_labels[-1] if hist_labels else None
        yr_r = (ratios.years.get(latest_l) if ratios and latest_l else None)
        # Fallback: si yr_r all-None, chercher l'annee precedente avec donnees
        if yr_r is not None and all(getattr(yr_r, a, None) is None
                                     for a in ('pe_ratio', 'ev_ebitda', 'gross_margin')):
            for _yl in reversed(hist_labels[:-1]):
                _yr_cand = ratios.years.get(_yl) if ratios else None
                if _yr_cand and any(getattr(_yr_cand, a, None) is not None
                                    for a in ('pe_ratio', 'ev_ebitda', 'gross_margin')):
                    yr_r = _yr_cand
                    break

        if yr_r:
            ev_ebitda_v = getattr(yr_r, 'ev_ebitda', None)
            pe_ntm      = pe_ntm or getattr(yr_r, 'pe_ratio', None)
            # Dividend yield depuis dividendes verses / (cours * actions)
            _div_paid = getattr(yr_r, 'dividends_paid_abs', None)
            if _div_paid is not None:
                if _div_paid and _shares and float(_shares) > 0 and price:
                    div_yield = float(_div_paid) / float(_shares) / float(price)
                else:
                    div_yield = 0.0  # dividendes nuls explicitement
            else:
                div_yield = 0.0  # pas de donnees dividendes -> 0% (aucun dividende)

        # Forward estimates (consensus analystes via yfinance)
        _fwd_eps      = None
        _fwd_pe       = None
        _trailing_eps = None
        try:
            import yfinance as yf
            _yf_info = yf.Ticker(ticker).info or {}
            _fwd_eps      = _yf_info.get("forwardEps")
            _fwd_pe       = _yf_info.get("forwardPE")
            _trailing_eps = _yf_info.get("trailingEps")
        except Exception:
            pass

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

        def _norm_pct(v):
            """Normalise marge LLM vers decimal 0-1.
            Cas gérés :
            - 0.19       (fraction) → 0.19
            - 19.0       (pourcentage direct) → 0.19
            - 1900.0     (LLM bug ×10000) → 0.19
            - 190.0      (×100 bug) → 0.19
            """
            if v is None: return None
            try:
                fv = float(v)
                afv = abs(fv)
                # Limites raisonnables pour une marge : [-100%, +100%]
                # Divise par 100 jusqu'à rentrer dans [-1.5, 1.5]
                while afv > 1.5:
                    fv = fv / 100.0
                    afv = abs(fv)
                    if afv < 0.00001:  # garde-fou
                        break
                return fv
            except: return None

        def _rev(l):
            fy = _fy(l)
            return _pv(l,'revenue') if l in [ny1,ny2] else (fy.revenue if fy else None)

        def _gm(l):
            ry = _ry(l)
            return _norm_pct(_pv(l,'gross_margin')) if l in [ny1,ny2] else \
                   (getattr(ry,'gross_margin',None) if ry else None)

        def _ebitda(l):
            ry = _ry(l)
            return _pv(l,'ebitda') if l in [ny1,ny2] else (getattr(ry,'ebitda',None) if ry else None)

        def _em(l):
            ry = _ry(l)
            return _norm_pct(_pv(l,'ebitda_margin')) if l in [ny1,ny2] else \
                   (getattr(ry,'ebitda_margin',None) if ry else None)

        def _ni(l):
            ry = _ry(l)
            return _pv(l,'net_income') if l in [ny1,ny2] else (getattr(ry,'net_income',None) if ry else None)

        def _nm(l):
            ry = _ry(l)
            return _norm_pct(_pv(l,'net_margin')) if l in [ny1,ny2] else \
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

        # col LTM = index (len(hist_3) - 1), col N+1E = index len(hist_3)
        _ltm_idx  = len(hist_3) - 1
        _ny1_idx  = len(hist_3)
        _n_cols   = len(all_labels)
        _dash_row = ['\u2014'] * _n_cols

        # Fallback EPS LTM depuis données financières si yfinance n'a pas retourné la valeur
        # net_income et shares_diluted sont tous deux en millions → division directe
        if _trailing_eps is None and hist_3:
            _ni_ltm = _ni(hist_3[-1])
            if _ni_ltm is not None and _shares and float(_shares) > 0:
                try:
                    _trailing_eps = round(float(_ni_ltm) / float(_shares), 2)
                except (ValueError, ZeroDivisionError):
                    pass
        # Fallback P/E : cours / EPS LTM si P/E Forward consensus non disponible
        if _fwd_pe is None and _trailing_eps is not None and price:
            try:
                _fwd_pe = round(float(price) / float(_trailing_eps), 1)
            except (ValueError, ZeroDivisionError):
                pass

        # EPS historique calculé par année depuis résultat net / actions (même méthode que fallback LTM)
        _eps_hist = list(_dash_row)
        if _shares and float(_shares) > 0:
            for _i, _l in enumerate(all_labels):
                if _i == _ny1_idx and _fwd_eps is not None:
                    try: _eps_hist[_i] = _fr(float(_fwd_eps), 2)
                    except: pass
                elif _i == _ny1_idx + 1:
                    pass  # ny2 : pas d'EPS disponible
                else:
                    _ni_yr = _ni(_l)
                    if _ni_yr is not None:
                        try:
                            _eps_yr = round(float(_ni_yr) / float(_shares), 2)
                            _eps_hist[_i] = _fr(_eps_yr, 2)
                        except: pass
            # Remplacer LTM par la valeur yfinance si plus précise
            if _trailing_eps is not None:
                try: _eps_hist[_ltm_idx] = _fr(float(_trailing_eps), 2)
                except: pass

        # Ligne P/E : LTM (trailing) + N+1E (forward)
        _pe_row = list(_dash_row)
        if _fwd_pe is not None:
            try: _pe_row[_ny1_idx] = _frx(float(_fwd_pe))
            except: pass
        if _trailing_eps is not None and price:
            try: _pe_row[_ltm_idx] = _frx(round(float(price) / float(_trailing_eps), 1))
            except: pass
        _pe_label = "P/E (LTM / Fwd)"

        is_data = [
            ["Chiffre d'affaires"]      + rev_vals,
            ["Croissance YoY"]          + grow_vals,
            ["Marge brute"]             + [_frpct(_gm(l)) for l in all_labels],
            ["EBITDA"]                  + [_frm(_ebitda(l)) for l in all_labels],
            ["Marge EBITDA"]            + [_frpct(_em(l)) for l in all_labels],
            ["R\u00e9sultat net"]       + [_frm(_ni(l)) for l in all_labels],
            ["Marge nette"]             + [_frpct(_nm(l)) for l in all_labels],
            ["EPS ($)"]                 + _eps_hist,
            [_pe_label]                 + _pe_row,
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

        # Profil sectoriel — adapte les ratios selon banque / REIT / utility / etc.
        try:
            from core.sector_profiles import detect_profile, is_non_standard, STANDARD, BANK, INSURANCE, REIT, UTILITY, OIL_GAS
            _industry_raw = getattr(ci, 'industry', None) or _g(snap.company_info, 'industry', '')
            _profile = detect_profile(sector, _industry_raw)
        except Exception:
            _profile = "STANDARD"

        # Ratios standards (corporate classique)
        _ratios_std = [
            {'label':'P/E (x)',          'value':_frx(pe_v),   'reference':bm['pe'],  'lecture':_read_label(pe_v, bm['pe'])},
            {'label':'EV / EBITDA (x)',  'value':_frx(ev_e),   'reference':bm['ev_e'],'lecture':_read_label(ev_e, bm['ev_e'])},
            {'label':'EV / Revenue (x)', 'value':_frx(ev_r),   'reference':bm['ev_r'],'lecture':_read_label(ev_r, bm['ev_r'])},
            {'label':'Marge brute',      'value':_frpct(gm_v), 'reference':bm['gm'],  'lecture':_read_label(gm_v, bm['gm'], pct=True)},
            {'label':'Marge EBITDA',     'value':_frpct(em),   'reference':bm['em'],  'lecture':_read_label(em, bm['em'], pct=True)},
            {'label':'Return on Equity', 'value':_frpct(roe),  'reference':bm['roe'], 'lecture':_read_label(roe, bm['roe'], pct=True)},
            {'label':'Altman Z-Score',   'value':_fr(az_v, 2), 'reference':'> 2,99 = sain', 'lecture':az_lbl},
            {'label':'Beneish M-Score',  'value':_fr(bm_v, 2), 'reference':'< \u22122,22 = OK','lecture':bm_lbl},
        ]

        # Ratios adaptés au profil sectoriel — références en string pour _read_label
        if _profile == "BANK":
            _pb_v = _a('pb_ratio') if hasattr(yr_r, 'pb_ratio') else None
            _dy_v = _g(snap.market, 'dividend_yield', None) if snap and snap.market else None
            ratios_vs_peers = [
                {'label':'P/TBV (x)',        'value':_frx(_pb_v),  'reference':'0,8\u20131,5x', 'lecture':_read_label(_pb_v, '0.8-1.5')},
                {'label':'P/E (x)',          'value':_frx(pe_v),   'reference':'8\u201314x',    'lecture':_read_label(pe_v, '8-14')},
                {'label':'Return on Equity', 'value':_frpct(roe),  'reference':'8\u201315 %',   'lecture':_read_label(roe, '8-15', pct=True)},
                {'label':'Dividend Yield',   'value':_frpct(_dy_v),'reference':'3\u20137 %',    'lecture':_read_label(_dy_v, '3-7', pct=True)},
                {'label':'Altman Z-Score',   'value':_fr(az_v, 2), 'reference':'n/a banque',    'lecture':'n/a'},
                {'label':'Beneish M-Score',  'value':_fr(bm_v, 2), 'reference':'< \u22122,22 = OK','lecture':bm_lbl},
            ]
        elif _profile == "REIT":
            ratios_vs_peers = [
                {'label':'P/E (x)',          'value':_frx(pe_v),   'reference':'15\u201325x',   'lecture':_read_label(pe_v, '15-25')},
                {'label':'EV / EBITDA (x)',  'value':_frx(ev_e),   'reference':'15\u201325x',   'lecture':_read_label(ev_e, '15-25')},
                {'label':'P/Book (x)',       'value':_frx(_a('pb_ratio')),'reference':'0,8\u20131,4x',  'lecture':_read_label(_a('pb_ratio'), '0.8-1.4')},
                {'label':'Marge EBITDA',     'value':_frpct(em),   'reference':'60\u201380 %',  'lecture':_read_label(em, '60-80', pct=True)},
                {'label':'Return on Equity', 'value':_frpct(roe),  'reference':'6\u201312 %',   'lecture':_read_label(roe, '6-12', pct=True)},
                {'label':'Altman Z-Score',   'value':_fr(az_v, 2), 'reference':'n/a REIT',      'lecture':'n/a'},
            ]
        elif _profile == "UTILITY":
            ratios_vs_peers = [
                {'label':'P/E (x)',          'value':_frx(pe_v),   'reference':'12\u201318x',   'lecture':_read_label(pe_v, '12-18')},
                {'label':'EV / EBITDA (x)',  'value':_frx(ev_e),   'reference':'8\u201312x',    'lecture':_read_label(ev_e, '8-12')},
                {'label':'Marge brute',      'value':_frpct(gm_v), 'reference':bm['gm'],        'lecture':_read_label(gm_v, bm['gm'], pct=True)},
                {'label':'Marge EBITDA',     'value':_frpct(em),   'reference':'25\u201335 %',  'lecture':_read_label(em, '25-35', pct=True)},
                {'label':'Return on Equity', 'value':_frpct(roe),  'reference':'7\u201311 %',   'lecture':_read_label(roe, '7-11', pct=True)},
                {'label':'Altman Z-Score',   'value':_fr(az_v, 2), 'reference':'> 1,81 = sain (levier)', 'lecture':az_lbl},
            ]
        elif _profile == "INSURANCE":
            _pb_v = _a('pb_ratio')
            _dy_v = _g(snap.market, 'dividend_yield', None) if snap and snap.market else None
            ratios_vs_peers = [
                {'label':'P/Book (x)',       'value':_frx(_pb_v),  'reference':'0,8\u20131,5x', 'lecture':_read_label(_pb_v, '0.8-1.5')},
                {'label':'P/E (x)',          'value':_frx(pe_v),   'reference':'8\u201314x',    'lecture':_read_label(pe_v, '8-14')},
                {'label':'Return on Equity', 'value':_frpct(roe),  'reference':'8\u201314 %',   'lecture':_read_label(roe, '8-14', pct=True)},
                {'label':'Dividend Yield',   'value':_frpct(_dy_v),'reference':'4\u20137 %',    'lecture':_read_label(_dy_v, '4-7', pct=True)},
                {'label':'Altman Z-Score',   'value':_fr(az_v, 2), 'reference':'n/a assurance', 'lecture':'n/a'},
                {'label':'Beneish M-Score',  'value':_fr(bm_v, 2), 'reference':'< \u22122,22 = OK','lecture':bm_lbl},
            ]
        elif _profile == "OIL_GAS":
            ratios_vs_peers = [
                {'label':'P/E (x)',          'value':_frx(pe_v),   'reference':'8\u201312x',    'lecture':_read_label(pe_v, '8-12')},
                {'label':'EV / EBITDA (x)',  'value':_frx(ev_e),   'reference':'3\u20135x',     'lecture':_read_label(ev_e, '3-5')},
                {'label':'EV / Revenue (x)', 'value':_frx(ev_r),   'reference':'1\u20133x',     'lecture':_read_label(ev_r, '1-3')},
                {'label':'Marge EBITDA',     'value':_frpct(em),   'reference':'20\u201340 %',  'lecture':_read_label(em, '20-40', pct=True)},
                {'label':'Return on Equity', 'value':_frpct(roe),  'reference':'10\u201320 %',  'lecture':_read_label(roe, '10-20', pct=True)},
                {'label':'Altman Z-Score',   'value':_fr(az_v, 2), 'reference':'> 2,99 = sain', 'lecture':az_lbl},
            ]
        else:
            ratios_vs_peers = _ratios_std

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

        # Fallback final : Monte Carlo si synthesis absente (LLM indisponible)
        if not ff_methods and ratios and getattr(ratios, 'meta', None):
            _mc_p10 = ratios.meta.get('dcf_mc_p10')
            _mc_p50 = ratios.meta.get('dcf_mc_p50')
            _mc_p90 = ratios.meta.get('dcf_mc_p90')
            if _mc_p50:
                try:
                    _p50 = float(_mc_p50)
                    _p10 = float(_mc_p10) if _mc_p10 else _p50 * 0.60
                    _p90 = float(_mc_p90) if _mc_p90 else _p50 * 1.60
                    ff_methods.append('GBM \u2014 Monte Carlo (P10\u2013P90)')
                    ff_lows.append(_p10); ff_highs.append(_p90)
                    ff_colors.append('#1B3A6B')
                    ff_methods.append('GBM \u2014 M\u00e9diane probabiliste (P50)')
                    ff_lows.append(_p50 * 0.94); ff_highs.append(_p50 * 1.06)
                    ff_colors.append('#1A7A4A')
                except (ValueError, TypeError):
                    pass

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
                    h = s.get('headline','')[:60]
                    if h: ts.append(h)
            if ts:
                return ', '.join(ts[:2])
            # Fallback : synthesis positive/negative themes si samples insuffisants
            if orient == 'pos':
                _raw = _g(synthesis, 'positive_themes') or []
                ts = [t if isinstance(t, str) else (_g(t,'title') or _g(t,'name') or '') for t in _raw[:2]]
            elif orient == 'neg':
                _raw = _g(synthesis, 'negative_themes') or []
                ts = [t if isinstance(t, str) else (_g(t,'title') or _g(t,'name') or '') for t in _raw[:2]]
            return ', '.join(t for t in ts if t) or '\u2014'

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
        _neg_full = []
        if not counter_risks:
            _neg = _g(synthesis, 'negative_themes') or []
            _neg_full = [t if isinstance(t, str) else (_g(t,'title') or _g(t,'name') or '')
                         for t in _neg[:3]]
            _neg_full = [c for c in _neg_full if c]
            # Titre court : coupe avant la 1ere virgule/parenthese, 7 mots max
            import re as _re
            def _short_risk(text):
                cut = _re.split(r'[,\(]', text)[0].strip()
                words = cut.split()
                return ' '.join(words[:7]) if len(words) > 7 else cut
            counter_risks = [_short_risk(n) for n in _neg_full]
        if counter_thesis and ' | ' in counter_thesis:
            ct_parts = [s.strip() for s in counter_thesis.split(' | ') if s.strip()]
        elif counter_thesis:
            sents = [s.strip() for s in counter_thesis.replace('. ', '.|').split('|') if s.strip()]
            chunk = max(1, len(sents) // 3)
            ct_parts = ['. '.join(sents[i*chunk:(i+1)*chunk]).strip() for i in range(3)]
        elif _neg_full:
            # Pas de counter_thesis : texte detaille = theme negatif complet
            ct_parts = _neg_full
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
            {'révision':'\u00bb BUY',  'style':'buy',
             'trigger': _g(synthesis,'buy_trigger')  or 'Acc\u00e9l\u00e9ration croissance + catalyseurs haussiers confirm\u00e9s',
             'target': _fr(tbull, 0, f'\u00a0{cur}') if tbull else '\u2014'},
            {'révision':'\u00bb SELL', 'style':'sell',
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
            'dividend_yield_str':_frpct(div_yield) if div_yield is not None else '\u2014',
            'pe_ntm_str':        _frx(pe_ntm) if pe_ntm else '\u2014',
            'ev_ebitda_str':     _frx(ev_ebitda_v) if ev_ebitda_v else '\u2014',

            # Textes
            'summary_text':         _g(synthesis,'summary') or _g(synthesis,'company_description') or '',
            'kdb_text':             _g(synthesis,'key_data_text') or '',
            'financials_text_intro':_g(synthesis,'financial_commentary') or '',
            'financials_text_post': _g(synthesis,'financial_commentary_post') or '',
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
            'post_comp_text':       _g(synthesis,'comparables_commentary') or _g(synthesis,'peers_commentary') or (
                                    f"L'analyse comparative des multiples confirme un "
                                    f"positionnément valu\u00e9 par rapport aux pairs sectoriels. "
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
                                    counter_thesis.replace(' | ', ' ') if counter_thesis else
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

            # Investment Case — données spécifiques
            'pos_themes_ic': [
                t if isinstance(t, str) else (_g(t,'title') or _g(t,'name') or '')
                for t in (_g(synthesis,'positive_themes') or [])[:3]
            ],
            'pe_ref_str':  bm.get('pe', '15\u201322x'),
            'ev_ref_str':  bm.get('ev_e', '10\u201316x'),

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
            'risk_themes':      titles[:3],
            'risk_themes_full': (ct_parts[:3] if ct_parts else _neg_full[:3]) or titles[:3],

            # Devil / invalidation
            'bear_args':         bear_args,
            'invalidation_data': invalidation_data,

            # Sentiment
            'finbert_n_articles': str(n_art),
            'sentiment_data':     sentiment_data,

            # Synthese finale
            'next_review':   _g(synthesis,'next_review') or '',
            'revision_data': rev_data,
            'page_nums':     {'synthese':4,'financials':6,'valorisation':8,'risques':10},

            # Monte Carlo DCF (Chantier 1)
            'dcf_mc_p10':  (ratios.meta.get('dcf_mc_p10')  if ratios and getattr(ratios, 'meta', None) else None),
            'dcf_mc_p50':  (ratios.meta.get('dcf_mc_p50')  if ratios and getattr(ratios, 'meta', None) else None),
            'dcf_mc_p90':  (ratios.meta.get('dcf_mc_p90')  if ratios and getattr(ratios, 'meta', None) else None),
            'dcf_mc_p2':   (ratios.meta.get('dcf_mc_p2')   if ratios and getattr(ratios, 'meta', None) else None),
            'dcf_mc_p98':  (ratios.meta.get('dcf_mc_p98')  if ratios and getattr(ratios, 'meta', None) else None),
            'dcf_mc_n_sim':(ratios.meta.get('dcf_mc_n_sim')   if ratios and getattr(ratios, 'meta', None) else None),
            'mc_dist':     (ratios.meta.get('mc_dist')      if ratios and getattr(ratios, 'meta', None) else None) or [],

            # Ratios historiques IB/PE (Chantiers multiples historiques + capital returns + LBO)
            'ratios_years_data': (
                [{'label': lbl.replace('_LTM', ' LTM'),
                  'pe':    getattr(ratios.years[lbl], 'pe_ratio',        None),
                  'ev_eb': getattr(ratios.years[lbl], 'ev_ebitda',       None),
                  'pb':    getattr(ratios.years[lbl], 'pb_ratio',        None),
                  'fcf':   getattr(ratios.years[lbl], 'fcf',             None),
                  'fcf_yield': getattr(ratios.years[lbl], 'fcf_yield',   None),
                  'div_pout':  getattr(ratios.years[lbl], 'dividend_payout', None),
                  'capex_r':   getattr(ratios.years[lbl], 'capex_ratio', None),
                  'ebitda':    getattr(ratios.years[lbl], 'ebitda',      None),
                  'net_debt':  getattr(ratios.years[lbl], 'net_debt',    None),
                  'rev_growth':getattr(ratios.years[lbl], 'revenue_growth', None),
                  'div_paid':  getattr(ratios.years[lbl], 'dividends_paid_abs', None),
                 }
                 for lbl in sorted(ratios.years.keys(), key=lambda k: str(k).replace('_LTM','Z'))
                 # Exclure annees sans donnees utiles (yfinance manque de donnees historiques lointaines)
                 if any(getattr(ratios.years[lbl], a, None) is not None
                        for a in ('pe_ratio', 'ev_ebitda', 'pb_ratio', 'ebitda'))
                ][-5:]
                if ratios and getattr(ratios, 'years', None) else []
            ),

            # Zone d'entrée (Chantier 3)
            'entry_zone_conditions': (
                [{'name': getattr(c, 'label', getattr(c, 'name', '')),
                  'satisfied': getattr(c, 'satisfied', False),
                  'value': getattr(c, 'value_str', getattr(c, 'value', None)),
                  'threshold': getattr(c, 'threshold', '')}
                 for c in getattr(entry_zone, 'conditions', [])]
                if entry_zone else []),
            'entry_zone_satisfied_count': getattr(entry_zone, 'satisfied_count', None),
            'entry_zone_all_met':         getattr(entry_zone, 'all_conditions_met', False),
            'entry_zone_backtest_wr':     getattr(entry_zone, 'backtest_win_rate', None),
            'entry_zone_backtest_n':      getattr(entry_zone, 'backtest_n', 0),
            'entry_zone_backtest_note':   getattr(entry_zone, 'backtest_note', None),

            # Scores additionnels (Composite Distress, M&A, Microstructure, Macro)
            **_compute_extra_scores(ticker, yr_r),
        }

        # --- Fetch chart data (yfinance, non-bloquant) ---
        peer_tickers = [_g(p, 'ticker') for p in (peers or []) if _g(p, 'ticker')][:5]
        # Fallback secteur si la synthese n'a pas fourni assez de tickers (<3)
        if len(peer_tickers) < 3:
            _SECTOR_PEERS = {
                'consumer cyclical': ['GM', 'F', 'RIVN', 'LCID', 'HMC'],
                'technology':        ['AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'NVDA'],
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
            _fallback_peers = []
            for _k, _v in _SECTOR_PEERS.items():
                if _k in s_low:
                    _fallback_peers = [t for t in _v if t.upper() != ticker.upper()]
                    break
            # Compléter avec le fallback sans dupliquer
            _existing_up = {t.upper() for t in peer_tickers}
            for _fp in _fallback_peers:
                if _fp.upper() not in _existing_up:
                    peer_tickers.append(_fp)
                    _existing_up.add(_fp.upper())
                    if len(peer_tickers) >= 5:
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
            # Enrichir pie_text avec les donnees reelles si le LLM n'en a pas fourni
            if not _g(synthesis, 'pie_text'):
                _pct_str  = d.get('pie_pct_str', '\u2014')
                _cap_lbl  = d.get('pie_cap_label', 'EV')
                _pie_szs  = pie_result.get('pie_sizes') or []
                _pie_lbs  = pie_result.get('pie_labels') or []
                _main_ev  = next((s for l, s in zip(_pie_lbs, _pie_szs)
                                  if ticker in l), None)
                _tot_ev   = sum(_pie_szs) if _pie_szs else None
                if _main_ev and _tot_ev:
                    d['pie_text'] = (
                        f"{co_name} repr\u00e9sente {_pct_str} de la {_cap_lbl} sectorielle, "
                        f"soit {_fr(_main_ev, 1)} Mds sur un total de {_fr(_tot_ev, 1)} Mds. "
                        f"Ce poids relatif conf\u00e8re au titre le statut d\u2019acteur "
                        f"de r\u00e9f\u00e9rence dans son secteur, avec une prime de liquidit\u00e9 "
                        f"institutionnelle associ\u00e9e. Les fonds sectoriels et indices \u00e9pond\u00e9r\u00e9s "
                        f"par la capitalisation sont structurellement surexpos\u00e9s \u00e0 ce titre, "
                        f"ce qui amplifie les mouvements de flux en cas de r\u00e9allocation sectorielle. "
                        f"L\u2019\u00e9volution de ce poids sectoriel constitue un signal de flux "
                        f"de capitaux \u00e0 surveiller activement."
                    )

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
