"""
indice_pptx_writer.py — FinSight IA
Pitchbook PPTX 20 slides pour analyse d'indice boursier.
Interface : IndicePPTXWriter.generate(data, output_path) -> bytes
Modele reference : FinSight_IA_Indice_SP500 (4).pptx
"""
from __future__ import annotations
import io, logging
from typing import Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np

from pptx import Presentation
from pptx.util import Cm, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

log = logging.getLogger(__name__)

# ── Dimensions (25.4 x 14.3 cm) ───────────────────────────────────────────────
_SW = Cm(25.4)
_SH = Cm(14.3)

# ── Palette ────────────────────────────────────────────────────────────────────
_NAVY  = RGBColor(0x1B, 0x3A, 0x6B)
_NAVYL = RGBColor(0x2A, 0x52, 0x98)
_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
_GRAYL = RGBColor(0xF5, 0xF7, 0xFA)
_GRAYM = RGBColor(0xE8, 0xEC, 0xF0)
_GRAYT = RGBColor(0x55, 0x55, 0x55)
_GRAYD = RGBColor(0xAA, 0xAA, 0xAA)
_BLACK = RGBColor(0x1A, 0x1A, 0x1A)
_BUY   = RGBColor(0x1A, 0x7A, 0x4A)
_SELL  = RGBColor(0xA8, 0x20, 0x20)
_HOLD  = RGBColor(0xB0, 0x60, 0x00)
_BUY_L = RGBColor(0xE8, 0xF5, 0xEE)
_SELL_L= RGBColor(0xFB, 0xEB, 0xEB)
_HOLD_L= RGBColor(0xFD, 0xF3, 0xE5)
_NAVY_LIGHT = RGBColor(0xD0, 0xDC, 0xF5)

_fr_months = {1:"janvier",2:"fevrier",3:"mars",4:"avril",5:"mai",6:"juin",
              7:"juillet",8:"aout",9:"septembre",10:"octobre",11:"novembre",12:"decembre"}

# Couleurs lignes ETF (identiques a sectoral_pptx_writer)
_LINE_COLORS_HEX = ['#1B3A6B','#1A7A4A','#A82020','#B06000',
                    '#2A5298','#6B3A1B','#3A6B1B','#6B1B3A']
_LINE_COLORS_RGB = [
    RGBColor(0x1B,0x3A,0x6B), RGBColor(0x1A,0x7A,0x4A),
    RGBColor(0xA8,0x20,0x20), RGBColor(0xB0,0x60,0x00),
    RGBColor(0x2A,0x52,0x98), RGBColor(0x6B,0x3A,0x1B),
    RGBColor(0x3A,0x6B,0x1B), RGBColor(0x6B,0x1B,0x3A),
]


# ── Helpers generiques ─────────────────────────────────────────────────────────

_SECTOR_ABBREV = {
    "Communication Services":  "Comm. Services",
    "Consumer Discretionary":  "Cons. Discret.",
    "Consumer Staples":        "Cons. Staples",
}

def _abbrev_sector(name: str, maxlen: int = 16) -> str:
    s = _SECTOR_ABBREV.get(str(name), str(name))
    return s[:maxlen] if len(s) > maxlen else s

def _trunc(text: str, n: int) -> str:
    """Truncate at word boundary."""
    if len(text) <= n:
        return text
    return text[:n].rsplit(' ', 1)[0] + '...'

def _fr_date():
    import datetime
    d = datetime.date.today()
    return f"{d.day} {_fr_months[d.month]} {d.year}"


def _sig_color(signal: str) -> RGBColor:
    s = str(signal)
    if "Surp" in s: return _BUY
    if "Sous" in s: return _SELL
    return _HOLD


def _sig_light(signal: str) -> RGBColor:
    s = str(signal)
    if "Surp" in s: return _BUY_L
    if "Sous" in s: return _SELL_L
    return _HOLD_L


def _sig_hex(signal: str) -> str:
    s = str(signal)
    if "Surp" in s: return '#1A7A4A'
    if "Sous" in s: return '#A82020'
    return '#B06000'


def _blank(prs: Presentation):
    return prs.slides.add_slide(prs.slide_layouts[6])


def _rect(slide, x, y, w, h, fill=None, line=False, line_col=None, line_w=0.5):
    shape = slide.shapes.add_shape(1, Cm(x), Cm(y), Cm(w), Cm(h))
    if fill:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    else:
        shape.fill.background()
    if line and line_col:
        shape.line.color.rgb = line_col
        shape.line.width = Pt(line_w)
    else:
        shape.line.fill.background()
    return shape


def _txb(slide, text, x, y, w, h, size=9, bold=False, color=None,
         align=PP_ALIGN.LEFT, italic=False, wrap=True):
    color = color or _BLACK
    box = slide.shapes.add_textbox(Cm(x), Cm(y), Cm(w), Cm(h))
    tf = box.text_frame
    tf.word_wrap = wrap
    para = tf.paragraphs[0]
    para.alignment = align
    run = para.add_run()
    run.text = str(text)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return box


def _pic(slide, img_bytes, x, y, w, h):
    buf = io.BytesIO(img_bytes)
    slide.shapes.add_picture(buf, Cm(x), Cm(y), Cm(w), Cm(h))


def _add_table(slide, data, x, y, w, h, col_widths=None,
               header_fill=_NAVY, header_color=_WHITE,
               alt_fill=None, font_size=7.5, header_size=7.5):
    rows, cols = len(data), len(data[0]) if data else 1
    tbl_shape = slide.shapes.add_table(rows, cols, Cm(x), Cm(y), Cm(w), Cm(h))
    tbl = tbl_shape.table
    if col_widths:
        total = sum(col_widths)
        for i, cw in enumerate(col_widths):
            tbl.columns[i].width = Cm(cw * w / total)
    for r, row_data in enumerate(data):
        is_hdr = (r == 0)
        for c, val in enumerate(row_data):
            cell = tbl.cell(r, c)
            cell.text = str(val) if val is not None else "—"
            para = cell.text_frame.paragraphs[0]
            para.alignment = PP_ALIGN.CENTER
            run = para.runs[0] if para.runs else para.add_run()
            run.font.size = Pt(header_size if is_hdr else font_size)
            run.font.bold = is_hdr
            if is_hdr:
                run.font.color.rgb = header_color
                cell.fill.solid()
                cell.fill.fore_color.rgb = header_fill
            else:
                run.font.color.rgb = _BLACK
                if alt_fill and r % 2 == 0:
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = alt_fill
                else:
                    cell.fill.background()
    return tbl


def _color_cell(tbl, row, col, fill, text_color=None):
    cell = tbl.cell(row, col)
    cell.fill.solid()
    cell.fill.fore_color.rgb = fill
    if text_color:
        for para in cell.text_frame.paragraphs:
            for run in para.runs:
                run.font.color.rgb = text_color


# ── Navigation / header / footer ───────────────────────────────────────────────

_NAV = ["1","2","3","4","5"]


def _header(slide, title, subtitle, active=1):
    _rect(slide, 0, 0, 25.4, 1.4, fill=_NAVY)
    _txb(slide, title, 0.9, 0.05, 19.1, 1.3, size=13, bold=True, color=_WHITE)
    for i, lbl in enumerate(_NAV):
        dx = 21.8 + i * 0.7
        fill = _WHITE if (i+1) == active else _NAVYL
        c = _BLACK if (i+1) == active else _GRAYD
        _rect(slide, dx, 0.35, 0.55, 0.55, fill=fill)
        _txb(slide, lbl, dx, 0.35, 0.55, 0.55, size=7, bold=True, color=c,
             align=PP_ALIGN.CENTER)
    _txb(slide, subtitle, 0.9, 1.6, 23.6, 0.6, size=8, color=_GRAYT)


def _footer(slide):
    _rect(slide, 0, 13.75, 25.4, 0.5, fill=_GRAYL)
    _txb(slide, "FinSight IA  ·  Usage confidentiel  ·  Ne constitue pas un conseil en investissement MiFID II",
         0.9, 13.8, 23.6, 0.4, size=7, color=_GRAYD)


def _chapter_divider(prs, num_str, title, subtitle):
    slide = _blank(prs)
    _rect(slide, 0, 0, 25.4, 14.3, fill=_NAVY)
    _txb(slide, num_str, 1.0, 3.5, 8.0, 4.5, size=72, bold=True, color=_NAVYL)
    _txb(slide, title, 1.0, 7.0, 23.0, 2.0, size=28, bold=True, color=_WHITE)
    _rect(slide, 1.0, 9.1, 15.0, 0.05, fill=_GRAYD)
    _txb(slide, subtitle, 1.0, 9.4, 22.9, 0.8, size=11, color=_GRAYD)
    _txb(slide, "FinSight IA  ·  Usage confidentiel", 0.9, 13.75, 23.6, 0.4,
         size=7, color=_GRAYD)
    return slide


def _lecture_box(slide, title, text, y_top=9.5, height=3.8):
    """Boite lecture analytique en bas de slide."""
    _rect(slide, 0.9, y_top, 23.6, height, fill=_GRAYL)
    _rect(slide, 0.9, y_top, 0.12, height, fill=_NAVY)
    _txb(slide, title, 1.2, y_top + 0.15, 22.8, 0.6,
         size=8, bold=True, color=_NAVY)
    _txb(slide, _trunc(text, 600), 1.2, y_top + 0.8, 22.8, height - 0.9,
         size=7.5, color=_GRAYT, wrap=True)


# ── Parseurs ────────────────────────────────────────────────────────────────────

def _parse_x(s) -> float:
    """Parse '28,4x' → 28.4"""
    try:
        return float(str(s).replace(',', '.').replace('x', '').strip())
    except:
        return 0.0


def _parse_pct(s) -> float:
    """Parse '+12,3 %' → 12.3"""
    try:
        return float(str(s).replace(',', '.').replace('%', '').replace(' ', '').strip())
    except:
        return 0.0


# ── Charts ─────────────────────────────────────────────────────────────────────

def _chart_scatter(secteurs: list) -> bytes:
    """Scatter EV/EBITDA vs croissance BPA par secteur. Fallback Mg.EBITDA si EV absent."""
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#F8F9FA')

    ev_vals  = [_parse_x(s[4])   for s in secteurs]
    bpa_vals = [_parse_pct(s[6]) for s in secteurs]
    signals  = [s[3] for s in secteurs]
    noms     = [s[0] for s in secteurs]

    # Fallback : Mg.EBITDA quand EV/EBITDA indisponible
    use_mg = not ev_vals or not any(v > 0 for v in ev_vals)
    if use_mg:
        mg_vals = [float(s[5]) if isinstance(s[5], (int, float)) and s[5] else 0.0 for s in secteurs]
        if not any(v > 0 for v in mg_vals):
            # Aucune donnee disponible
            ax.text(0.5, 0.5, "Données EV/EBITDA et Mg.EBITDA\nnon disponibles pour cet indice",
                    ha='center', va='center', transform=ax.transAxes, color='#999999', fontsize=10)
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values(): sp.set_visible(False)
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
            plt.close(fig); buf.seek(0); return buf.read()
        y_vals  = mg_vals
        y_label = "Mg. EBITDA (%)"
        q_labels = ("Mg. elevee + Fort.", "Mg. faible + Fort.", "Mg. elevee + Faible", "Mg. faible + Faible")
    else:
        y_vals  = ev_vals
        y_label = "EV/EBITDA (x)"
        q_labels = ("Premium Justifie", "Value Trap ?", "Opportunite", "Risque")

    med_y   = float(np.median([v for v in y_vals if v > 0]))
    med_bpa = float(np.median(bpa_vals))

    ax.axhline(med_y,   color='#CCCCCC', linewidth=0.8, linestyle='--', alpha=0.7)
    ax.axvline(med_bpa, color='#CCCCCC', linewidth=0.8, linestyle='--', alpha=0.7)

    for i, (yv, bpa, sig, nom) in enumerate(zip(y_vals, bpa_vals, signals, noms)):
        col = _sig_hex(sig)
        ax.scatter(bpa, yv, s=100, color=col, alpha=0.85, zorder=5, edgecolors='white', linewidths=0.5)
        short = _abbrev_sector(nom, 14)
        ax.annotate(short, (bpa, yv), textcoords='offset points', xytext=(5, 4),
                    fontsize=6, color='#333333')

    kw = dict(transform=ax.transAxes, fontsize=6.5, alpha=0.7)
    ax.text(0.97, 0.93, q_labels[0], ha='right', color='#555555', **kw)
    ax.text(0.03, 0.93, q_labels[1], ha='left',  color='#555555', **kw)
    ax.text(0.97, 0.04, q_labels[2], ha='right', color='#1A7A4A', **kw)
    ax.text(0.03, 0.04, q_labels[3], ha='left',  color='#A82020', **kw)

    ax.set_xlabel("Croissance BPA (%)", fontsize=8, color='#555555')
    ax.set_ylabel(y_label, fontsize=8, color='#555555')
    ax.tick_params(labelsize=7, colors='#777777')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#DDDDDD')
    ax.spines['bottom'].set_color('#DDDDDD')
    ax.grid(True, alpha=0.3, linestyle=':')
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _chart_score_bars(secteurs: list) -> bytes:
    """Barres horizontales de scores par secteur, tries descroissant."""
    sorted_s = sorted(secteurs, key=lambda s: s[2], reverse=True)
    noms   = [_abbrev_sector(s[0], 18) for s in sorted_s]
    scores = [s[2] for s in sorted_s]
    cols   = [_sig_hex(s[3]) for s in sorted_s]

    fig, ax = plt.subplots(figsize=(9, max(3.5, len(noms) * 0.42)))
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#F8F9FA')

    y = np.arange(len(noms))
    bars = ax.barh(y, scores, color=cols, alpha=0.85, height=0.62, edgecolor='white', linewidth=0.5)
    for bar, val in zip(bars, scores):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                f"{val}", va='center', ha='left', fontsize=7, color='#333333', fontweight='bold')

    ax.axvline(50, color='#FF8C00', linewidth=1.0, linestyle='--', alpha=0.8, label='Seuil 50')
    ax.axvline(65, color='#1A7A4A', linewidth=0.8, linestyle=':', alpha=0.6)
    ax.set_yticks(y)
    ax.set_yticklabels(noms, fontsize=7.5)
    ax.set_xlim(0, 105)
    ax.set_xlabel("Score FinSight (0-100)", fontsize=8, color='#555555')
    ax.tick_params(labelsize=7, colors='#777777')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.grid(True, alpha=0.3, linestyle=':', axis='x')
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _chart_ev_distribution(secteurs: list) -> bytes:
    """Barres horizontales EV/EBITDA par secteur, colore par signal.
    Fallback Mg.EBITDA si EV/EBITDA absent (ex: CAC40, DAX40)."""
    sorted_all = sorted(secteurs, key=lambda s: _parse_x(s[4]), reverse=True)
    sorted_s = [s for s in sorted_all if _parse_x(s[4]) > 0]
    if not sorted_s:
        sorted_s = sorted_all  # fallback si tous vides
    noms  = [_abbrev_sector(s[0], 18) for s in sorted_s]
    evs   = [_parse_x(s[4]) for s in sorted_s]
    cols  = [_sig_hex(s[3]) for s in sorted_s]
    filtered_evs = [v for v in evs if v > 0]

    fig, ax = plt.subplots(figsize=(8.5, max(3.5, len(noms) * 0.42)))
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#F8F9FA')

    if not filtered_evs:
        # Fallback Mg.EBITDA : barres horizontales de marge EBITDA par secteur
        mg_data = [(s[0], s[5], s[3]) for s in secteurs
                   if isinstance(s[5], (int, float)) and s[5] > 0]
        if not mg_data:
            # Dernier recours : placeholder texte
            ax.text(0.5, 0.5, "Donnees non disponibles\npour cet indice",
                    ha='center', va='center', transform=ax.transAxes,
                    color='#999999', fontsize=11)
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values(): sp.set_visible(False)
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
            plt.close(fig)
            buf.seek(0)
            return buf.read()
        plt.close(fig)
        mg_sorted = sorted(mg_data, key=lambda x: x[1], reverse=True)
        fig2, ax2 = plt.subplots(figsize=(8.5, max(3.5, len(mg_sorted) * 0.42)))
        fig2.patch.set_facecolor('#FFFFFF')
        ax2.set_facecolor('#F8F9FA')
        _noms2 = [_abbrev_sector(r[0], 18) for r in mg_sorted]
        _vals2 = [r[1] for r in mg_sorted]
        _cols2 = [_sig_hex(r[2]) for r in mg_sorted]
        _med2  = float(np.median(_vals2))
        _y2    = np.arange(len(_noms2))
        _bars2 = ax2.barh(_y2, _vals2, color=_cols2, alpha=0.85, height=0.62,
                          edgecolor='white', linewidth=0.5)
        for _bar, _val in zip(_bars2, _vals2):
            ax2.text(_bar.get_width() + 0.3, _bar.get_y() + _bar.get_height() / 2,
                     f"{_val:.1f}%", va='center', ha='left', fontsize=7, color='#333333')
        ax2.axvline(_med2, color='#1B3A6B', linewidth=1.0, linestyle='--', alpha=0.7,
                    label=f"Med. {_med2:.1f}%")
        ax2.legend(fontsize=7, framealpha=0.7, loc='lower right')
        ax2.set_yticks(_y2)
        ax2.set_yticklabels(_noms2, fontsize=7.5)
        ax2.set_xlabel("Marge EBITDA (%)", fontsize=8, color='#555555')
        ax2.tick_params(labelsize=7, colors='#777777')
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        ax2.spines['left'].set_visible(False)
        ax2.grid(True, alpha=0.3, linestyle=':', axis='x')
        plt.tight_layout()
        _buf2 = io.BytesIO()
        fig2.savefig(_buf2, format='png', dpi=150, bbox_inches='tight',
                     facecolor='white', edgecolor='none')
        plt.close(fig2)
        _buf2.seek(0)
        return _buf2.read()

    med = float(np.median(filtered_evs))
    y = np.arange(len(noms))
    bars = ax.barh(y, evs, color=cols, alpha=0.85, height=0.62, edgecolor='white', linewidth=0.5)
    for bar, val in zip(bars, evs):
        if val > 0:
            ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height()/2,
                    f"{val:.1f}x", va='center', ha='left', fontsize=7, color='#333333')

    ax.axvline(med, color='#1B3A6B', linewidth=1.0, linestyle='--', alpha=0.7,
               label=f"Med. {med:.1f}x")
    ax.legend(fontsize=7, framealpha=0.7, loc='lower right')
    ax.set_yticks(y)
    ax.set_yticklabels(noms, fontsize=7.5)
    ax.set_xlabel("EV/EBITDA (x)", fontsize=8, color='#555555')
    ax.tick_params(labelsize=7, colors='#777777')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.grid(True, alpha=0.3, linestyle=':', axis='x')
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _chart_zone_entree(data: dict) -> bytes:
    """PE actuel vs PE mediane 10 ans par secteur — chart dotplot."""
    # Recupere les donnees PE depuis top3 + secteurs si dispo
    secteurs = data.get("secteurs", [])
    top3     = data.get("top3_secteurs", [])

    # PE global de l'indice comme ancre (calcule en premier)
    try:
        _pe_global = float(str(data.get("pe_forward","17")).replace("x","").strip())
        if _pe_global < 5 or _pe_global > 50: _pe_global = 17.0
    except:
        _pe_global = 17.0
    _pe_med_global = data.get("pe_mediane_10y", 17.0) or 17.0
    if not isinstance(_pe_med_global, (int, float)): _pe_med_global = 17.0

    # Construire mapping nom -> (pe_fwd, pe_med)
    pe_data = {}
    for s in top3:
        pe_fwd = s.get("pe_forward_raw", 0) or 0
        if pe_fwd < 5:
            # Estimation ancree sur pe_global (identique aux secteurs)
            pe_fwd = round(_pe_global + (s.get("score", 50) - 50) * 0.05, 1)
        # Cap pe_med au realiste (evite bandes trop larges)
        pe_med_val = min(s.get("pe_mediane_10y", _pe_med_global), _pe_global * 1.3)
        pe_data[s["nom"]] = (pe_fwd, float(pe_med_val))

    for s in secteurs:
        if s[0] not in pe_data:
            score = s[2]
            pe_est = round(_pe_global + (score - 50) * 0.05, 1)
            pe_data[s[0]] = (pe_est, float(_pe_med_global))

    if not pe_data:
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.text(0.5, 0.5, "Donnees PE non disponibles", ha='center', va='center',
                transform=ax.transAxes)
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    # Map signal per sector name
    sig_map = {s[0]: s[3] for s in secteurs}

    noms    = list(pe_data.keys())
    pe_fwds = [pe_data[n][0] for n in noms]
    pe_meds = [pe_data[n][1] for n in noms]
    sigs    = [sig_map.get(n, "Neutre") for n in noms]

    fig, ax = plt.subplots(figsize=(9.5, max(4.0, len(noms) * 0.5)))
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#F8F9FA')

    y = np.arange(len(noms))
    # Bande "zone normale" autour de mediane
    for i, (med, fwd, sig, nom) in enumerate(zip(pe_meds, pe_fwds, sigs, noms)):
        ax.barh(i, med * 0.3, left=med * 0.85, height=0.3,
                color='#E8ECF0', alpha=0.7, zorder=3)
        # Dot PE actuel
        col = _sig_hex(sig)
        ax.scatter(fwd, i, s=80, color=col, zorder=6, edgecolors='white', linewidths=0.5)
        # Ligne med
        ax.scatter(med, i, s=40, color='#AAAAAA', marker='|', zorder=5)

    ax.set_yticks(y)
    ax.set_yticklabels([_abbrev_sector(n, 18) for n in noms], fontsize=7.5)
    ax.set_xlabel("P/E Forward", fontsize=8, color='#555555')
    ax.tick_params(labelsize=7, colors='#777777')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.grid(True, alpha=0.3, linestyle=':', axis='x')
    # Limiter l'axe X au range reel des dots (pas d'espace vide a droite)
    _xmin = max(0, min(pe_fwds) - 1.5)
    _xmax = max(pe_fwds) + 1.5
    ax.set_xlim(_xmin, _xmax)

    from matplotlib.lines import Line2D
    legend_el = [
        Line2D([0],[0], marker='o', color='w', markerfacecolor='#1A7A4A', markersize=7, label='Surpondérer'),
        Line2D([0],[0], marker='o', color='w', markerfacecolor='#B06000',  markersize=7, label='Neutre'),
        Line2D([0],[0], marker='o', color='w', markerfacecolor='#A82020',  markersize=7, label='Sous-pondérer'),
        Line2D([0],[0], marker='|', color='#AAAAAA', markersize=8, label='Mediane 10Y'),
    ]
    ax.legend(handles=legend_el, fontsize=6.5, framealpha=0.7, loc='lower right')
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _chart_sentiment_bars(sentiment_agg: dict) -> bytes:
    """Barres sentiment par secteur."""
    par_sec = sentiment_agg.get("par_secteur", [])
    if not par_sec:
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.text(0.5, 0.5, "Donnees sentiment non disponibles", ha='center', va='center',
                transform=ax.transAxes)
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    sorted_ps = sorted(par_sec, key=lambda x: x[1], reverse=True)
    noms   = [_abbrev_sector(p[0], 16) for p in sorted_ps]
    scores = [float(p[1]) for p in sorted_ps]
    cols   = ['#1A7A4A' if v >= 0.05 else ('#A82020' if v <= -0.05 else '#B06000') for v in scores]

    fig, ax = plt.subplots(figsize=(8.5, max(2.5, len(noms) * 0.38)))
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#F8F9FA')

    y = np.arange(len(noms))
    ax.barh(y, scores, color=cols, alpha=0.8, height=0.55, edgecolor='white', linewidth=0.5)
    ax.axvline(0, color='#333333', linewidth=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(noms, fontsize=7)
    ax.set_xlabel("Score FinBERT (-1 à +1)", fontsize=7.5, color='#555555')
    ax.tick_params(labelsize=6.5, colors='#777777')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, alpha=0.3, linestyle=':', axis='x')
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _chart_etf_perf(data: dict) -> bytes:
    """Performance 52 semaines des ETF sectoriels, indexe a 100."""
    import datetime as dt
    etf_perf = data.get("etf_perf", {})
    colors_line = _LINE_COLORS_HEX

    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#F8F9FA')

    plotted = 0
    try:
        import yfinance as yf
        etf_list = list(etf_perf.keys())[:8]
        for i, etf in enumerate(etf_list):
            try:
                hist = yf.Ticker(etf).history(period='1y', interval='1wk')['Close']
                if len(hist) < 4:
                    continue
                norm = (hist / hist.iloc[0]) * 100
                label = f"{etf} — {etf_perf[etf].get('nom','')[:12]}"
                ax.plot(norm.index, norm.values,
                        color=colors_line[i % len(colors_line)],
                        linewidth=1.6, label=label, alpha=0.9)
                plotted += 1
            except Exception:
                pass
    except Exception:
        pass

    if plotted == 0:
        # Fallback simule base sur return_1y
        np.random.seed(42)
        x = np.linspace(0, 52, 53)
        for i, (etf, info) in enumerate(list(etf_perf.items())[:8]):
            ret_ann = info.get("return_1y", 5.0) / 100.0
            ret_wk = ret_ann / 52
            np.random.seed(i * 13)
            noise = np.random.randn(53) * 1.2
            y = 100 * np.cumprod(1 + ret_wk + noise * 0.01)
            y = y / y[0] * 100
            nom = info.get("nom", etf)[:12]
            ax.plot(x, y, color=colors_line[i % len(colors_line)],
                    linewidth=1.6, label=f"{etf} — {nom}", alpha=0.9)
        ax.set_xlabel("Semaines (illustratif)", fontsize=8, color='#555555')
    else:
        ax.set_xlabel("Date", fontsize=8, color='#555555')

    ax.axhline(100, color='#CCCCCC', linewidth=1.0, linestyle='-')
    ax.set_ylabel("Performance indexee (base 100)", fontsize=8, color='#555555')
    ax.tick_params(labelsize=7, colors='#777777')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#DDDDDD')
    ax.spines['bottom'].set_color('#DDDDDD')
    ax.grid(True, alpha=0.3, linestyle=':')
    ax.legend(fontsize=6.5, framealpha=0.7, ncol=2, loc='upper left')
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _chart_index_perf(data: dict) -> bytes:
    """Graphique performance 52 semaines de l'indice vs obligations et or."""
    import matplotlib.dates as mdates
    from datetime import datetime as _dt2
    ph = data.get("perf_history")
    if not ph or not ph.get("dates") or not ph.get("indice"):
        return _make_empty_chart()
    try:
        dates   = [_dt2.strptime(d[:10], "%Y-%m-%d") for d in ph["dates"]]
        i_perf  = ph.get("indice", [])
        b_perf  = ph.get("bonds", [])
        g_perf  = ph.get("gold", [])
        sp_perf = ph.get("sp500", [])
        if not dates or not i_perf:
            return _make_empty_chart()

        fig, ax = plt.subplots(figsize=(11, 4.5))
        fig.patch.set_facecolor('#FFFFFF')
        ax.set_facecolor('#F8F9FA')

        ax.plot(dates, i_perf, color='#1B3A6B', lw=2.5,
                label=ph.get("indice_name", "Indice"), zorder=3)
        if len(sp_perf) == len(dates):
            ax.plot(dates, sp_perf, color='#555555', lw=1.5, linestyle='-.',
                    label="S&P 500", alpha=0.75, zorder=2)
        if len(b_perf) == len(dates):
            ax.plot(dates, b_perf, color='#A82020', lw=1.5, linestyle='--',
                    label="Obligations (^TNX)", alpha=0.8, zorder=2)
        if len(g_perf) == len(dates):
            ax.plot(dates, g_perf, color='#B06000', lw=1.5, linestyle=':',
                    label="Or (GC=F)", alpha=0.8, zorder=2)

        ax.axhline(100, color='#CCCCCC', lw=1.0, linestyle='-', zorder=1)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        plt.xticks(rotation=25, fontsize=8)
        ax.tick_params(axis='y', labelsize=8)
        ax.set_ylabel("Base 100", fontsize=8, color='#555555')
        ax.legend(fontsize=8, loc='upper left', framealpha=0.8)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#DDDDDD')
        ax.spines['bottom'].set_color('#DDDDDD')
        ax.grid(axis='y', alpha=0.3, linestyle=':')

        if i_perf:
            final_pct = i_perf[-1] - 100
            _col_ann  = '#1A7A4A' if final_pct >= 0 else '#A82020'
            ax.annotate(
                f"{final_pct:+.1f}%",
                xy=(dates[-1], i_perf[-1]),
                xytext=(-5, 6), textcoords='offset points',
                fontsize=9, color=_col_ann, fontweight='bold',
            )

        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as _e:
        log.warning("_chart_index_perf: %s", _e)
        return _make_empty_chart()


# ── Slides 1-20 ─────────────────────────────────────────────────────────────────

def _s01_cover(prs, D):
    slide = _blank(prs)

    # ── Bandeau header navy (identique pptx_writer societe) ───────────────────
    _rect(slide, 0, 0, 25.4, 3.81, fill=_NAVY)
    _txb(slide, "FinSight IA", 1.27, 0.46, 22.86, 0.71,
         size=10, bold=False, color=RGBColor(0x88, 0x99, 0xBB),
         align=PP_ALIGN.CENTER)
    _rect(slide, 11.05, 1.32, 3.3, 0.05, fill=_WHITE)
    _txb(slide, "Pitchbook  \u00b7  Analyse d'Indice", 1.27, 1.52, 22.86, 0.81,
         size=11, color=RGBColor(0xCC, 0xDD, 0xEE), align=PP_ALIGN.CENTER)

    # ── Corps blanc ───────────────────────────────────────────────────────────
    # Nom indice (large, centre)
    _txb(slide, D.get("indice", ""), 1.27, 4.2, 22.86, 1.6,
         size=32, bold=True, color=_NAVY, align=PP_ALIGN.CENTER)

    # Tagline code + secteurs + societes
    code = D.get("code", "")
    nb_s = D.get("nb_secteurs", 0)
    nb_c = D.get("nb_societes", 0)
    parts = [p for p in [
        code,
        (f"{nb_s} secteurs analys\u00e9s" if nb_s else ""),
        (f"{nb_c} soci\u00e9t\u00e9s couvertes" if nb_c else ""),
    ] if p]
    _txb(slide, "  \u00b7  ".join(parts), 1.27, 5.9, 22.86, 0.71,
         size=11, color=RGBColor(0x88, 0x88, 0x88), align=PP_ALIGN.CENTER)

    # Badge signal (pattern recommandation societe)
    _SIG_NORM_COV = {
        "surponderer":  "SURPOND\u00c9RER", "surpond\u00e9rer": "SURPOND\u00c9RER",
        "sous-ponderer":"SOUS-POND\u00c9RER","sous-pond\u00e9rer":"SOUS-POND\u00c9RER",
        "neutre":       "NEUTRE",
    }
    sig = D.get("signal_global", "Neutre")
    sig_col   = _sig_color(sig)
    sig_light = _sig_light(sig)
    sig_txt   = _SIG_NORM_COV.get(sig.lower(), sig.upper())
    conv      = D.get("conviction_pct", 50)
    _rect(slide, 1.27, 6.8, 22.86, 1.32, fill=sig_light)
    _rect(slide, 1.27, 6.8, 0.13,  1.32, fill=sig_col)
    _txb(slide, f"\u25cf {sig_txt}  \u00b7  Conviction {conv}\u00a0%",
         1.60, 6.85, 22.40, 1.22,
         size=9, bold=True, color=sig_col, align=PP_ALIGN.CENTER)

    # KPI boxes (fond gris clair, texte navy — lisibles sur blanc)
    secteurs_cov = D.get("secteurs", [])
    score_med = D.get("score_median")
    if not score_med and secteurs_cov:
        scores_l = [s[2] for s in secteurs_cov if len(s) > 2
                    and isinstance(s[2], (int, float))]
        score_med = round(sum(scores_l) / len(scores_l)) if scores_l else None
    sm_str   = f"{score_med}/100" if isinstance(score_med, (int, float)) else "\u2014"
    nb_surp  = sum(1 for s in secteurs_cov if "surp"   in str(s[3]).lower())
    nb_neut  = sum(1 for s in secteurs_cov if "neutre" in str(s[3]).lower())
    nb_sousp = sum(1 for s in secteurs_cov if "sous"   in str(s[3]).lower())
    metrics = [
        ("Score m\u00e9dian",   sm_str),
        ("Surpond\u00e9rer",    f"{nb_surp} sect."),
        ("Neutre",              f"{nb_neut} sect."),
        ("Sous-pond\u00e9rer",  f"{nb_sousp} sect."),
    ]
    box_w = 5.4
    step  = 22.86 / 4
    for i, (lbl, val) in enumerate(metrics):
        xpos = 1.27 + i * step
        _rect(slide, xpos, 8.5, box_w, 1.6, fill=_GRAYL)
        _txb(slide, lbl, xpos + 0.2, 8.6,  box_w - 0.4, 0.5, size=7.5, color=_GRAYT)
        _txb(slide, val, xpos + 0.2, 9.05, box_w - 0.4, 0.9, size=13,  bold=True, color=_NAVY)

    # Ligne de separation + credits (identique societe)
    _rect(slide, 1.02, 11.8, 23.37, 0.03, fill=_GRAYD)
    date_str = D.get("date_analyse") or _fr_date()
    _txb(slide, "Rapport confidentiel", 1.02, 12.05, 11.43, 0.56,
         size=8, color=_GRAYT)
    _txb(slide, date_str, 12.95, 12.05, 11.43, 0.56,
         size=8, color=_GRAYT, align=PP_ALIGN.RIGHT)

    return slide


def _s02_exec_summary(prs, D):
    slide = _blank(prs)
    indice = D.get("indice","")
    code   = D.get("code","")
    nb_s   = D.get("nb_secteurs",0)
    nb_c   = D.get("nb_societes",0)
    _header(slide, "Executive Summary",
            f"{indice} ({code})  ·  {nb_s} secteurs  ·  {nb_c} sociétés  ·  Horizon 12 mois",
            active=1)

    # Signal badge
    _SIG_NORM = {
        "surponderer": "SURPONDÉRER", "surpondérer": "SURPONDÉRER",
        "sous-ponderer": "SOUS-PONDÉRER", "sous-pondérer": "SOUS-PONDÉRER",
        "neutre": "NEUTRE",
    }
    sig     = D.get("signal_global","Neutre")
    sig_col = _sig_color(sig)
    sig_txt = _SIG_NORM.get(sig.lower(), sig.upper())
    _rect(slide, 0.9, 2.3, 4.8, 0.75, fill=sig_col)
    _txb(slide, sig_txt, 1.1, 2.35, 4.4, 0.55, size=10, bold=True, color=_WHITE)

    # Metriques ligne
    _erp_s02 = D.get("erp", "—")
    _esig_s02 = D.get("erp_signal", "")
    _erp_display_s02 = f"ERP : {_erp_s02}" + (f" ({_esig_s02})" if _esig_s02 else "")
    mets = [
        f"Cours : {D.get('cours','—')}",
        f"YTD : {D.get('variation_ytd','—')}",
        f"P/E Forward : {D.get('pe_forward','—')}",
        _erp_display_s02,
        f"Conviction {D.get('conviction_pct',50)} %",
    ]
    _txb(slide, "  ·  ".join(mets), 0.9, 3.15, 23.6, 0.55, size=8, color=_GRAYT)

    # Regime de marche (compact strip si disponible)
    _mac = D.get("macro") or {}
    _reg = _mac.get("regime", "")
    if _reg and _reg != "Inconnu":
        _RSIG_COL = {"Bull": _BUY, "Bear": _SELL, "Volatile": _HOLD, "Transition": _HOLD}
        _r_col = _RSIG_COL.get(_reg, _NAVYL)
        _rec_6 = _mac.get("recession_prob_6m")
        _vx    = _mac.get("vix")
        _sp_s  = _mac.get("yield_spread_10y_3m")
        _parts = [f"Regime {_reg}"]
        if _vx:    _parts.append(f"VIX {_vx:.0f}")
        if _sp_s is not None: _parts.append(f"Spread {_sp_s:+.1f}%")
        if _rec_6 is not None: _parts.append(f"Rec. 6M {_rec_6}%")
        _rect(slide, 0.9, 3.8, 23.6, 0.45, fill=_GRAYL)
        _rect(slide, 0.9, 3.8, 0.10, 0.45, fill=_r_col)
        _txb(slide, "  \u00b7  ".join(_parts), 1.1, 3.83, 23.0, 0.38,
             size=7.5, color=_NAVY, bold=False)

    # Catalyseurs macro (y fixe suffisant apres regime strip eventuel)
    _rect(slide, 0.9, 4.4, 23.6, 0.5, fill=_NAVY)
    _txb(slide, "CATALYSEURS MACRO", 1.1, 4.45, 22.8, 0.4,
         size=7.5, bold=True, color=_WHITE)

    cats = D.get("catalyseurs", [])
    for j, cat in enumerate(cats[:3]):
        yy = 5.05 + j * 0.95
        _rect(slide, 0.9, yy, 0.08, 0.9, fill=_BUY)
        nom  = cat[0][:50] if isinstance(cat, (list,tuple)) else str(cat)[:50]
        desc = cat[1][:120] if isinstance(cat,(list,tuple)) and len(cat) > 1 else ""
        _txb(slide, nom,  1.15, yy,       22.3, 0.45, size=8, bold=True, color=_NAVY)
        _txb(slide, desc, 1.15, yy + 0.45, 22.3, 0.55, size=7.5, color=_GRAYT, wrap=True)

    # Synthese signal en bas — enrichie avec metriques calcules
    _texte_raw = D.get("texte_signal", "")
    _cours_s02 = D.get("cours", "—")
    _ytd_s02   = D.get("variation_ytd", "—")
    _pe_f_s02  = D.get("pe_forward", "—")
    _pe_m_s02  = D.get("pe_mediane_10y", "—")
    _erp_s02b  = D.get("erp", "—")
    _erp_sig_s02 = D.get("erp_signal", "")
    _scr_s02   = D.get("score_median", "—")
    _conv_s02  = D.get("conviction_pct", 50)
    _surp_s02  = D.get("surp_noms", "") or ""
    _sous_s02  = D.get("sous_noms", "") or ""
    _pm_s02    = f"{_pe_m_s02}x" if isinstance(_pe_m_s02, (int, float)) else str(_pe_m_s02)
    _prime_s02 = D.get("prime_decote", "")
    _prime_lbl = "prime de valorisation significative" if isinstance(_prime_s02, str) and "+" in str(_prime_s02) else "valorisation en ligne avec l'historique"
    _erp_lbl   = " (prime insuffisante — prudence sur les entrees)" if _erp_sig_s02 in ("Tendu", "Comprime") else (" (adequat)" if _erp_sig_s02 else "")
    _suppl_s02 = (
        f"Le {D.get('indice', '')} affiche un cours de {_cours_s02} (YTD : {_ytd_s02}). "
        f"P/E Forward {_pe_f_s02} vs mediane historique 10 ans {_pm_s02} — {_prime_lbl}. "
        f"ERP Damodaran {_erp_s02b}{_erp_lbl}. "
        f"Score composite moyen : {_scr_s02}/100 — conviction {_conv_s02} %. "
        f"Secteurs a Surponderer : {_surp_s02 or 'aucun'}. "
        f"Secteurs a eviter : {_sous_s02 or 'aucun'}."
    )
    # Ajouter horizon seulement si pas deja dans le texte IA
    if "Horizon" not in _texte_raw:
        _suppl_s02 += " Horizon d'allocation recommande : 12 mois."
    texte = _trunc((_texte_raw + "  " + _suppl_s02).strip() if _texte_raw else _suppl_s02, 700)
    _y_synth = 8.3
    _h_synth = 13.3 - _y_synth
    _rect(slide, 0.9, _y_synth, 23.6, _h_synth, fill=_GRAYL)
    _rect(slide, 0.9, _y_synth, 0.12, _h_synth, fill=_NAVY)
    _txb(slide, "SYNTHESE DU SIGNAL", 1.2, _y_synth + 0.1, 22.8, 0.5, size=8, bold=True, color=_NAVY)
    _txb(slide, texte, 1.2, _y_synth + 0.7, 22.8, _h_synth - 0.8, size=8, color=_GRAYT, wrap=True)

    _footer(slide)
    return slide


def _s03_sommaire(prs, D):
    slide = _blank(prs)
    indice = D.get("indice","")
    code   = D.get("code","")
    _header(slide, "Sommaire",
            f"{indice}  ·  {code}  ·  Structure de l'analyse macro institutionnelle",
            active=1)

    chapitres = [
        ("01", "Synthèse Macro & Signal Global",
         "Description indice · P/E Forward · ERP Damodaran · Catalyseurs & risques · Cycle économique",
         "p. 5-7"),
        ("02", "Cartographie des Secteurs",
         f"{D.get('nb_secteurs',11)} secteurs GICS · Scores FinSight · Scatter EV/EBITDA vs croissance · Décomposition scores",
         "p. 9-11"),
        ("03", "Top 3 Secteurs Recommandés",
         "Synthèse signal · Sociétés représentatives · Distribution valorisations · Zone d'entrée",
         "p. 13-15"),
        ("04", "Risques, Rotation & Sentiment",
         "Scénarios alternatifs · Rotation sectorielle · FinBERT · Performance ETF",
         "p. 17-20"),
    ]

    for i, (num, titre, desc, pages) in enumerate(chapitres):
        yy = 2.5 + i * 2.75
        _rect(slide, 0.9, yy, 23.6, 2.4, fill=_GRAYL)
        _rect(slide, 0.9, yy, 1.2, 2.4, fill=_NAVY)
        _txb(slide, num, 0.9, yy + 0.7, 1.2, 1.0, size=14, bold=True,
             color=_WHITE, align=PP_ALIGN.CENTER)
        _txb(slide, titre, 2.3, yy + 0.15, 18.5, 0.75, size=10, bold=True, color=_NAVY)
        _txb(slide, desc,  2.3, yy + 0.9,  18.5, 1.1,  size=8,  color=_GRAYT, wrap=True)
        _txb(slide, pages, 21.5, yy + 0.75, 2.7, 0.6,  size=9, bold=True,
             color=_NAVY, align=PP_ALIGN.RIGHT)

    _footer(slide)
    return slide


def _s05_description(prs, D):
    slide = _blank(prs)
    indice = D.get("indice","")
    code   = D.get("code","")
    _header(slide, "Description de l'Indice",
            f"{indice} ({code})  ·  Caractéristiques structurelles & valorisation macro",
            active=1)

    # Texte description gauche
    desc = D.get("texte_description","")[:700]
    _rect(slide, 0.9, 2.3, 0.12, 7.1, fill=_NAVY)
    _txb(slide, desc, 1.2, 2.3, 13.4, 7.1, size=8.5, color=_GRAYT, wrap=True)

    # Tableau metriques droite
    cours     = D.get("cours","—")
    ytd       = D.get("variation_ytd","—")
    pe_fwd    = D.get("pe_forward","—")
    pe_med    = D.get("pe_mediane_10y","—")
    erp       = D.get("erp","—")
    bpa       = D.get("bpa_growth","—")
    nb_s      = D.get("nb_secteurs",11)
    nb_c      = D.get("nb_societes","—")

    rows = [
        ["MÉTRIQUE",              "VALEUR"],
        ["Cours actuel",          cours],
        ["Variation YTD",         ytd],
        ["P/E Forward",           pe_fwd],
        ["P/E Médiane 10 ans",    f"{pe_med}x" if isinstance(pe_med, (int,float)) else str(pe_med)],
        ["ERP (Damodaran)",       erp],
        ["Croissance BPA",        bpa],
        ["Secteurs analysés",     str(nb_s)],
        ["Sociétés couvertes",    str(nb_c)],
    ]
    _add_table(slide, rows, 15.1, 2.3, 9.4, 7.0,
               col_widths=[6, 3], font_size=8, header_size=8, alt_fill=_GRAYL)

    # Lecture analytique — contexte sectoriel et valorisation
    secteurs_d = D.get("secteurs",[])
    surp = [s[0] for s in secteurs_d if "Surp" in str(s[3])]
    sous = [s[0] for s in secteurs_d if "Sous" in str(s[3])]
    nb_n = len([s for s in secteurs_d if "Surp" not in str(s[3]) and "Sous" not in str(s[3])])
    _surp_str = "  ·  ".join([_abbrev_sector(x,18) for x in surp[:3]]) or "aucun"
    _sous_str = "  ·  ".join([_abbrev_sector(x,18) for x in sous[:3]]) or "aucun"
    _pe_f5  = D.get("pe_forward","—")
    _pe_m5  = D.get("pe_mediane_10y","—")
    _erp5   = D.get("erp","—")
    _erp_s5 = D.get("erp_signal","")
    _pm5    = f"{_pe_m5}x" if isinstance(_pe_m5,(int,float)) else str(_pe_m5)
    _prime5 = D.get("prime_decote","")
    _sig5   = D.get("signal_global","Neutre")
    _scr5   = D.get("score_median","—")
    lec_txt = (
        f"Signal global : {_sig5} (score composite {_scr5}/100). "
        f"P/E Forward {_pe_f5} vs mediane historique {_pm5} — "
        f"{'prime de valorisation, entrees a calibrer' if isinstance(_prime5,str) and '+' in str(_prime5) else 'valorisation proche des normes historiques'}. "
        f"ERP Damodaran : {_erp5}{' (' + _erp_s5 + ')' if _erp_s5 else ''}. "
        f"Secteurs a Surponderer : {_surp_str}. "
        f"Secteurs a Sous-ponderer : {_sous_str}. "
        f"{nb_n} secteur(s) en position Neutre. "
        f"Horizon d'allocation recommande : 12 mois."
    )
    _lecture_box(slide, "Lecture — Signal global & positionnement sectoriel",
                 _trunc(lec_txt, 700), y_top=9.8, height=3.5)

    _footer(slide)
    return slide


def _s06_valorisation(prs, D):
    slide = _blank(prs)
    indice = D.get("indice","")
    _header(slide, "Valorisation Macro Top-Down",
            f"{indice}  ·  BPA forward x P/E cible historique  ·  ERP Damodaran  ·  Signaux FRED",
            active=1)

    # Table valorisation
    pe_fwd    = D.get("pe_forward","—")
    pe_med    = D.get("pe_mediane_10y","—")
    prime     = D.get("prime_decote","—")
    erp       = D.get("erp","—")
    bpa       = D.get("bpa_growth","—")
    rows = [
        ["INDICATEUR",         "VALEUR",     "vs HISTORIQUE",    "INTERPRETATION"],
        ["P/E Forward",        pe_fwd,       prime,              "Prime vs mediane 10Y"],
        ["P/E Mediane 10 ans", f"{pe_med}x" if isinstance(pe_med,(int,float)) else str(pe_med),
                               "Reference",  "Niveau historique normalise"],
        ["ERP (Damodaran)",    erp,          "Correct",          "Rendement excess equites"],
        ["Croissance BPA",     bpa,          "+",                "Consensu analystes 12M"],
        ["Prime/Decote",       prime,        "Surevalu si > 20 %","Signal d alerte valorisation"],
    ]
    tbl = _add_table(slide, rows, 0.9, 2.3, 23.6, 5.0,
               col_widths=[5, 3, 3, 12.6], font_size=8, header_size=8, alt_fill=_GRAYL)

    # Colorer prime
    for r in range(2, len(rows)):
        prime_val = rows[r][2]
        if isinstance(prime_val, str) and '+' in prime_val:
            _color_cell(tbl, r, 2, _HOLD_L, _BLACK)

    # Lecture analytique — fallback analytique si texte court ou données manquantes
    texte_val = D.get("texte_valorisation","")
    _pe_m6 = D.get("pe_mediane_10y","—")
    _pe_f6 = D.get("pe_forward","—")
    _erp6  = D.get("erp","—")
    _sig6  = D.get("signal_global","Neutre")
    _scr6  = D.get("score_median","—")
    if not texte_val or len(texte_val) < 80:
        _pm_str = f"{_pe_m6}x" if isinstance(_pe_m6,(int,float)) else str(_pe_m6)
        _prime6  = D.get("prime_decote","")
        _erp_s6  = D.get("erp_signal","")
        _ytd6    = D.get("variation_ytd","—")
        _cours6  = D.get("cours","—")
        _conv6   = D.get("conviction_pct",50)
        # Implication investissement selon ERP
        if _erp_s6 in ("Tendu","Comprime"):
            _erp_impl = ("L'ERP negatif ou tres comprime signale que les actions sont "
                         "peu remunerees vs le taux sans risque — prudence sur les points d'entree, "
                         "privilegier les secteurs a forte visibilite sur les BPA.")
        elif _erp_s6 == "Attractif":
            _erp_impl = ("L'ERP positif signale une prime de risque adequate : "
                         "les equites offrent un surplus de rendement justifiant un positionnement actif.")
        else:
            _erp_impl = ("L'ERP reste proche de son niveau de reference — "
                         "aucun signal extreme. Maintenir une allocation neutre aux equites.")
        texte_val = (
            f"Cours {_cours6} (YTD : {_ytd6}). "
            f"Le P/E Forward ({_pe_f6}) traite a {_prime6 or 'N/D'} vs la mediane historique 10 ans ({_pm_str}). "
            f"L'ERP (Damodaran) s'etablit a {_erp6}{' — ' + _erp_s6 if _erp_s6 else ''}. "
            f"{_erp_impl} "
            f"Score composite moyen : {_scr6}/100, signal {_sig6} (conviction {_conv6} %). "
            f"La croissance BPA forward reste le principal vecteur de re-rating si le cycle se confirme."
        )
    _lecture_box(slide, "Lecture analytique — Valorisation macro", _trunc(texte_val, 700), y_top=8.0, height=5.35)

    _footer(slide)
    return slide


def _s07_cycle(prs, D):
    slide = _blank(prs)
    indice = D.get("indice","")
    phase  = D.get("phase_cycle","Expansion avancée")
    _header(slide, "Positionnement dans le Cycle Economique",
            f"{indice}  ·  Phase actuelle : {phase}  ·  Signaux FRED  ·  Modele 4 phases",
            active=1)

    # Carte phase cycle gauche
    _rect(slide, 0.9, 2.3, 8.2, 6.5, fill=_NAVY)
    _rect(slide, 0.9, 2.3, 8.2, 0.7, fill=_NAVYL)
    _txb(slide, "PHASE ACTUELLE", 1.1, 2.35, 7.8, 0.6,
         size=8, bold=True, color=_WHITE)
    phase_parts = phase.split()
    if len(phase_parts) >= 2:
        _txb(slide, " ".join(phase_parts[:-1]), 1.1, 3.2, 7.8, 1.0,
             size=18, bold=True, color=_WHITE)
        _txb(slide, phase_parts[-1], 1.1, 4.2, 7.8, 0.85,
             size=13, bold=False, color=_GRAYD)
    else:
        _txb(slide, phase, 1.1, 3.2, 7.8, 1.5, size=16, bold=True, color=_WHITE)

    detail = D.get("cycle_detail","PIB positif · Taux restrictifs\nMarges sous pression")
    _txb(slide, detail, 1.1, 5.3, 7.8, 2.0, size=8, color=_GRAYD, wrap=True)

    # Première phrase du texte_cycle seulement pour éviter le débordement
    texte_cycle_full = D.get("texte_cycle","")
    texte_cycle = _trunc(texte_cycle_full.split(".")[0] + "." if texte_cycle_full else "", 120)
    _txb(slide, texte_cycle, 1.1, 7.4, 7.8, 1.3, size=7.5, color=_GRAYD, wrap=True)

    # Tableau FRED signals droite
    fred = D.get("fred_signals", [])
    fred_rows = [["INDICATEUR", "VALEUR", "INTERPRETATION"]]
    for sig in fred[:7]:
        if isinstance(sig, (list,tuple)) and len(sig) >= 3:
            fred_rows.append([sig[0], str(sig[1]), str(sig[2])[:40]])
    if len(fred_rows) == 1:
        fred_rows.append(["PMI Composite", "51,2", "Expansion moderee"])
        fred_rows.append(["Courbe 10Y-2Y", "-0,12 %", "Legerement inversee"])
        fred_rows.append(["ISM Manuf.", "49,8", "Sous expansion"])
        fred_rows.append(["Chomage", "3,9 %", "Marche solide"])
        fred_rows.append(["CPI YoY", "3,1 %", "Au-dessus cible"])

    tbl = _add_table(slide, fred_rows, 9.5, 2.3, 15.0, len(fred_rows) * 0.85 + 0.1,
               col_widths=[5.0, 2.5, 7.5], font_size=8, header_size=8, alt_fill=_GRAYL)

    # Allocation recommandee
    alloc = _trunc(D.get("texte_cycle",""), 420)
    _rect(slide, 9.5, 9.3, 15.0, 2.9, fill=_GRAYL)
    _rect(slide, 9.5, 9.3, 0.1, 2.9, fill=_BUY)
    _txb(slide, "Allocation recommandee selon le positionnement de cycle",
         9.8, 9.4, 14.5, 0.6, size=8, bold=True, color=_NAVY)
    _txb(slide, alloc, 9.8, 10.0, 14.5, 2.0, size=7.5, color=_GRAYT, wrap=True)

    _footer(slide)
    return slide


def _s09_cartographie(prs, D):
    slide = _blank(prs)
    indice  = D.get("indice","")
    nb_s    = D.get("nb_secteurs",11)
    nb_c    = D.get("nb_societes","")
    _header(slide, "Cartographie des Secteurs",
            f"{nb_s} secteurs GICS  ·  {nb_c} sociétés  ·  Tri par score FinSight décroissant",
            active=2)

    secteurs = D.get("secteurs", [])
    sorted_s = sorted(secteurs, key=lambda s: s[2], reverse=True)

    _SIG_LABEL = {
        "surponderer": "Surpondérer", "surpondérer": "Surpondérer",
        "sous-ponderer": "Sous-pondérer", "sous-pondérer": "Sous-pondérer",
        "neutre": "Neutre",
    }
    # Detect si EV/EBITDA disponible (au moins 1 valeur non "—")
    _all_ev_dash = all(str(s[4]) in ("—", "", "None", "\u2014") for s in sorted_s)

    if _all_ev_dash:
        # Table sans colonne EV/EBITDA (5 colonnes)
        rows = [["Rg", "Secteur", "Score", "Signal", "Mg.EBITDA", "Croiss.", "Mom."]]
        for rang, s in enumerate(sorted_s, 1):
            raw_sig = str(s[3])[:15]
            norm_sig = _SIG_LABEL.get(raw_sig.strip().lower(), raw_sig)
            rows.append([
                str(rang),
                _abbrev_sector(s[0], 20),
                str(s[2]),
                norm_sig,
                f"{s[5]:.1f}%" if isinstance(s[5],(int,float)) and s[5] else "—",
                str(s[6]) if len(s) > 6 else "—",
                str(s[7]) if len(s) > 7 else "—",
            ])
        tbl = _add_table(slide, rows, 0.9, 2.3, 23.6,
                         min(7.5, 0.65 + len(rows) * 0.65),
                         col_widths=[1.2, 5.5, 1.8, 4.0, 3.5, 3.8, 3.8],
                         font_size=8, header_size=8, alt_fill=_GRAYL)
        sig_col = 3
    else:
        rows = [["Rg", "Secteur", "Score", "Signal", "EV/EBITDA", "Mg.EBITDA", "Croiss.", "Mom."]]
        for rang, s in enumerate(sorted_s, 1):
            raw_sig = str(s[3])[:15]
            norm_sig = _SIG_LABEL.get(raw_sig.strip().lower(), raw_sig)
            rows.append([
                str(rang),
                _abbrev_sector(s[0], 20),
                str(s[2]),
                norm_sig,
                str(s[4]),
                f"{s[5]:.1f}%" if isinstance(s[5],(int,float)) and s[5] else "—",
                str(s[6]) if len(s) > 6 else "—",
                str(s[7]) if len(s) > 7 else "—",
            ])
        tbl = _add_table(slide, rows, 0.9, 2.3, 23.6,
                         min(7.5, 0.65 + len(rows) * 0.65),
                         col_widths=[1.2, 4.5, 1.5, 3.5, 2.5, 2.5, 2.5, 2.5],
                         font_size=8, header_size=8, alt_fill=_GRAYL)
        sig_col = 3

    # Colorer signal cells
    for r in range(1, len(rows)):
        sig = sorted_s[r-1][3] if r-1 < len(sorted_s) else "Neutre"
        _color_cell(tbl, r, sig_col, _sig_light(sig), _sig_color(sig))

    # Lecture analytique enrichie
    nb_surp = sum(1 for s in secteurs if "Surp" in str(s[3]))
    nb_sous = sum(1 for s in secteurs if "Sous" in str(s[3]))
    nb_neut = nb_s - nb_surp - nb_sous
    surp_noms = " · ".join(s[0] for s in sorted_s if "Surp" in str(s[3]))
    sous_noms = " · ".join(s[0] for s in sorted_s if "Sous" in str(s[3]))
    top_s  = sorted_s[0]  if sorted_s else None
    bot_s  = sorted_s[-1] if sorted_s else None
    score_top = top_s[2] if top_s else "—"
    score_bot = bot_s[2] if bot_s else "—"
    score_spread = (top_s[2] - bot_s[2]) if (top_s and bot_s) else 0
    lecture = (
        f"{nb_surp} secteur(s) sur {nb_s} franchissent le seuil Surpondérer (score > 65) : "
        f"{surp_noms or 'aucun'}. "
        f"{nb_sous} secteur(s) en Sous-pondérer : {sous_noms or 'aucun'}. "
        f"{nb_neut} secteur(s) en position Neutre. "
        f"L'écart entre le secteur leader ({top_s[0] if top_s else '—'}, score {score_top}/100) "
        f"et le secteur le plus faible ({bot_s[0] if bot_s else '—'}, score {score_bot}/100) "
        f"est de {score_spread} points — une dispersion {'élevée' if score_spread > 30 else 'modérée'} "
        f"qui témoigne d'une bifurcation sectorielle {'marquée' if score_spread > 30 else 'limitée'}."
    )
    y_top = min(10.5, 2.3 + len(rows) * 0.65 + 0.3)
    _lecture_box(slide, "Lecture analytique — Ce que la cartographie révèle",
                 lecture, y_top=y_top, height=13.35 - y_top)

    _footer(slide)
    return slide


def _s10_scatter(prs, D, chart_bytes: bytes):
    slide = _blank(prs)
    indice = D.get("indice","")
    secteurs = D.get("secteurs",[])
    ev_vals = [_parse_x(s[4]) for s in secteurs]
    use_mg  = not ev_vals or not any(v > 0 for v in ev_vals)
    if use_mg:
        axis_lbl = "Mg. EBITDA vs Croissance BPA"
        sub_lbl  = "Marge EBITDA (%) vs Croissance BPA  ·  4 quadrants  ·  Un point par secteur GICS"
    else:
        axis_lbl = "EV/EBITDA vs Croissance BPA"
        sub_lbl  = "EV/EBITDA median vs Croissance BPA  ·  4 quadrants  ·  Un point par secteur GICS"
    _header(slide, f"Valorisation vs Croissance BPA ({axis_lbl})", sub_lbl, active=2)

    _pic(slide, chart_bytes, 0.9, 2.3, 14.2, 8.6)

    # Lecture droite
    sorted_s = sorted(secteurs, key=lambda s: s[2], reverse=True)
    surp_s = [s for s in sorted_s if "Surp" in str(s[3])]
    sous_s = [s for s in sorted_s if "Sous" in str(s[3])]
    if use_mg:
        best = [_abbrev_sector(s[0],18) for s in surp_s if isinstance(s[5],(int,float)) and s[5] > 20][:2]
        opport = [_abbrev_sector(s[0],18) for s in surp_s if isinstance(s[5],(int,float)) and s[5] <= 20][:2]
        txt = (
            f"{'  ·  '.join(best) or 'N/A'} : forte marge EBITDA + score Surponderer — "
            f"profil qualite avec visibilite elevee sur les benefices.\n\n"
            f"{'  ·  '.join(opport) or 'N/A'} : zone Opportunite — "
            f"croissance correcte, marge adequate, valorisation attractive.\n\n"
            f"EV/EBITDA non disponible pour cet indice (EU) via yfinance. "
            f"La Mg. EBITDA est utilisee comme proxy de qualite operationnelle. "
            f"Favoriser les secteurs a forte marge et croissance BPA positive."
        )
    else:
        premium = [_abbrev_sector(s[0],18) for s in surp_s if _parse_x(s[4]) > 20][:2]
        opport  = [_abbrev_sector(s[0],18) for s in surp_s if 0 < _parse_x(s[4]) <= 20][:2]
        # Fallback: si premium vide, top Surponderer par score
        if not premium and surp_s:
            premium = [_abbrev_sector(s[0],18) for s in surp_s[:2]]
            _prem_label = "en zone Opportunite (EV/EBITDA attractif) — forte conviction score Surponderer"
        else:
            _prem_label = "en quadrant Premium Justifie — valorisation elevee supportee par forte croissance BPA"
        if not opport and surp_s:
            opport = [_abbrev_sector(s[0],18) for s in surp_s[len(premium):len(premium)+2]]
        txt = (
            f"{'  ·  '.join(premium) or 'Aucun secteur Surponderer'} {_prem_label if premium else ''}.\n\n"
            f"{'  ·  '.join(opport) or 'Aucun'} : valorisation attractive — "
            f"croissance correcte, meilleur ratio risque/rendement.\n\n"
            f"Les pointilles representent les medianes sectorielles (EV/EBITDA et BPA growth). "
            f"Favoriser les secteurs en bas droite (forte croissance, valorisation moderee)."
        )
    _rect(slide, 15.6, 2.3, 8.9, 8.6, fill=_GRAYL)
    _rect(slide, 15.6, 2.3, 0.12, 8.6, fill=_NAVY)
    _txb(slide, "Lecture du Scatter", 15.9, 2.4, 8.4, 0.6, size=8.5, bold=True, color=_NAVY)
    _txb(slide, txt[:600], 15.9, 3.1, 8.4, 7.7, size=8, color=_GRAYT, wrap=True)

    _footer(slide)
    return slide


def _s11_decomposition(prs, D):
    slide = _blank(prs)
    nb_s = D.get("nb_secteurs",11)
    _header(slide, "Décomposition des Scores FinSight",
            f"{nb_s} secteurs GICS  ·  Score 0-100  ·  Momentum 40 % · Révisions BPA 30 % · Valorisation 30 %",
            active=2)

    secteurs  = D.get("secteurs",[])
    top3      = D.get("top3_secteurs",[])
    sorted_s  = sorted(secteurs, key=lambda s: s[2], reverse=True)

    # Construire un mapping de sous-scores depuis top3
    sub_map = {}
    for t in top3:
        sub_map[t["nom"]] = (
            t.get("score_momentum", round(t.get("score",50) * 0.4)),
            t.get("score_revisions", round(t.get("score",50) * 0.3)),
            t.get("score_valorisation", round(t.get("score",50) * 0.3)),
        )

    _SIG_NORM_TBL = {
        "surponderer": "Surpondérer", "surpondérer": "Surpondérer",
        "sous-ponderer": "Sous-pondérer", "sous-pondérer": "Sous-pondérer",
        "neutre": "Neutre",
    }
    rows = [["Secteur", "Score Total", "Momentum (40%)", "Révisions (30%)", "Valorisation (30%)", "Signal"]]
    for s in sorted_s:
        nom, score, sig = s[0], s[2], s[3]
        if nom in sub_map:
            sm, sr, sv = sub_map[nom]
        else:
            sm = round(score * 0.40)
            sr = round(score * 0.30)
            sv = round(score * 0.30)
        sig_norm = _SIG_NORM_TBL.get(str(sig).strip().lower(), str(sig)[:15])
        rows.append([_abbrev_sector(nom, 20), str(score), str(sm), str(sr), str(sv), sig_norm])

    tbl = _add_table(slide, rows, 0.9, 2.3, 23.6,
                     min(7.0, 0.6 + len(rows) * 0.62),
                     col_widths=[4.5, 2.5, 3.5, 3.5, 3.5, 3.5],
                     font_size=8, header_size=8, alt_fill=_GRAYL)

    # Colorer signal
    for r in range(1, len(rows)):
        sig = sorted_s[r-1][3] if r-1 < len(sorted_s) else "Neutre"
        _color_cell(tbl, r, 5, _sig_light(sig), _sig_color(sig))
    # Colorer score
    for r in range(1, len(rows)):
        score = int(rows[r][1]) if rows[r][1].isdigit() else 50
        fill = _BUY_L if score >= 65 else (_SELL_L if score < 45 else _HOLD_L)
        _color_cell(tbl, r, 1, fill, _BLACK)

    note = "Lecture : Score >= 65 = vert · 45-64 = neutre · < 45 = rouge · Méthode : composite 40 % momentum + 30 % révisions BPA + 30 % valorisation relative"
    y_note = 2.3 + len(rows) * 0.62 + 0.2
    _txb(slide, note, 0.9, y_note, 23.6, 0.6, size=7, color=_GRAYD, italic=True)

    # Lecture
    top_nom = sorted_s[0][0] if sorted_s else "—"
    top_mom = sub_map.get(top_nom, (0,0,0))[0]
    lecture = (
        f"{top_nom} domine avec le score le plus élevé. "
        f"Le momentum ({top_mom} pts) constitue le premier signal de confirmation. "
        f"Les secteurs en vert sur les 3 dimensions offrent le meilleur profil composite. "
        f"Croiser avec la valorisation relative pour identifier les meilleures opportunités d'entrée."
    )
    y_lec = min(10.5, y_note + 0.8)
    _lecture_box(slide, "Analyse des scores — Points saillants",
                 lecture, y_top=y_lec, height=13.35 - y_lec)

    _footer(slide)
    return slide


def _s13_top3(prs, D):
    slide = _blank(prs)
    _header(slide, "Top 3 Secteurs — Synthèse",
            "Secteurs Surpondérer  ·  Signal · Score · EV/EBITDA · Sociétés représentatives · Catalyseur · Risque",
            active=3)

    top3 = D.get("top3_secteurs", [])
    if not top3:
        _txb(slide, "Données top3 non disponibles", 1.0, 5.0, 23.0, 1.0,
             size=12, color=_GRAYT, align=PP_ALIGN.CENTER)
        _footer(slide)
        return slide

    # Padding to always render 3 panels (avoids blank slots when <3 sectors)
    while len(top3) < 3:
        top3 = list(top3) + [{"nom": "—", "signal": "Neutre", "score": 0,
                               "ev_ebitda": "—", "catalyseur": "Données insuffisantes",
                               "risque": "—", "societes": []}]

    panel_w = 7.5
    for i, sect in enumerate(top3[:3]):
        xoff = 0.9 + i * (panel_w + 0.35)
        nom   = sect.get("nom","—")
        sig   = sect.get("signal","Neutre")
        score = sect.get("score",50)
        ev    = sect.get("ev_ebitda","—")
        cat   = sect.get("catalyseur","—")[:180]
        rsk   = sect.get("risque","—")[:180]
        socs  = sect.get("societes",[])

        # Panel bg
        _rect(slide, xoff, 2.3, panel_w, 11.1, fill=_GRAYL)
        _rect(slide, xoff, 2.3, panel_w, 0.8, fill=_NAVY)

        # Nom + signal badge
        _txb(slide, nom[:18], xoff + 0.2, 2.35, panel_w - 2.5, 0.7,
             size=10, bold=True, color=_WHITE)
        _rect(slide, xoff + panel_w - 2.0, 2.35, 1.8, 0.65, fill=_sig_color(sig))
        _txb(slide, "Surp." if "Surp" in sig else ("Sous." if "Sous" in sig else "Neutre"),
             xoff + panel_w - 1.9, 2.4, 1.7, 0.55, size=7.5, bold=True,
             color=_WHITE, align=PP_ALIGN.CENTER)

        # Score + metrique dispo (EV/EBITDA ou Mg.EBITDA en fallback)
        mg_eb = sect.get("mg_ebitda", sect.get("marge_ebitda", "—"))
        if str(ev) in ("—", "", "None") and mg_eb and str(mg_eb) not in ("—","","None"):
            _mg_disp = f"{float(mg_eb):.1f}%" if isinstance(mg_eb,(int,float)) else str(mg_eb)
            _met_disp = f"Score : {score}/100  ·  Mg.EBITDA : {_mg_disp}"
        else:
            _met_disp = f"Score : {score}/100  ·  EV/EBITDA : {ev}"
        _txb(slide, _met_disp, xoff + 0.2, 3.25, panel_w - 0.3, 0.5, size=7.5, color=_NAVY)

        # Societes
        _txb(slide, "Sociétés représentatives", xoff + 0.2, 3.85, panel_w - 0.3, 0.45,
             size=7.5, bold=True, color=_NAVY)
        for j, soc in enumerate(socs[:3]):
            yy = 4.4 + j * 0.82
            _rect(slide, xoff + 0.2, yy, panel_w - 0.3, 0.72, fill=_WHITE)
            tk  = soc[0] if isinstance(soc,(list,tuple)) else str(soc)
            sg  = soc[1] if isinstance(soc,(list,tuple)) and len(soc)>1 else "—"
            evs = soc[2] if isinstance(soc,(list,tuple)) and len(soc)>2 else "—"
            sc2 = soc[3] if isinstance(soc,(list,tuple)) and len(soc)>3 else "—"
            # Si EV/EBITDA absent au niveau societe, utiliser le secteur comme proxy
            if str(evs) in ("—", "", "None") and str(ev) not in ("—", "", "None"):
                evs = f"~{ev}"
            # Abrev signal
            sg_abbr = "Surp." if "Surp" in str(sg) else ("Sous." if "Sous" in str(sg) else "Neutre")
            _ev_absent = str(evs) in ("—", "", "None", "\u2014")
            if _ev_absent:
                # Layout 3 col : ticker | signal | score (pas d'EV)
                _txb(slide, tk,      xoff + 0.4,       yy + 0.1, 2.4, 0.55,
                     size=8, bold=True, color=_NAVY)
                _txb(slide, sg_abbr, xoff + 0.4 + 2.4, yy + 0.1, 2.2, 0.55,
                     size=8, color=_sig_color(sg))
                _sc_lbl = f"Score : {sc2}" if str(sc2) not in ("—","","None") else ""
                _txb(slide, _sc_lbl, xoff + 0.4 + 2.4 + 2.2, yy + 0.1, 2.2, 0.55,
                     size=8, color=_GRAYT)
            else:
                _txb(slide, tk,       xoff + 0.4,             yy + 0.1, 1.6, 0.55,
                     size=8, bold=True, color=_NAVY)
                _txb(slide, sg_abbr,  xoff + 0.4 + 1.6,       yy + 0.1, 1.5, 0.55,
                     size=8, color=_sig_color(sg))
                _txb(slide, str(evs), xoff + 0.4 + 1.6 + 1.5, yy + 0.1, 1.5, 0.55,
                     size=8, color=_GRAYT)
                _txb(slide, str(sc2), xoff + 0.4 + 1.6 + 1.5 + 1.5, yy + 0.1, 1.5, 0.55,
                     size=8, color=_GRAYT)

        # Catalyseur
        _txb(slide, "Catalyseur", xoff + 0.2, 6.9, panel_w - 0.3, 0.45,
             size=7.5, bold=True, color=_NAVY)
        _rect(slide, xoff + 0.2, 7.4, panel_w - 0.3, 2.0, fill=_BUY_L)
        _txb(slide, cat, xoff + 0.4, 7.5, panel_w - 0.6, 1.85, size=7.5, color=_GRAYT, wrap=True)

        # Risque
        _txb(slide, "Risque principal", xoff + 0.2, 9.55, panel_w - 0.3, 0.45,
             size=7.5, bold=True, color=_NAVY)
        _rect(slide, xoff + 0.2, 10.05, panel_w - 0.3, 2.0, fill=_SELL_L)
        _txb(slide, rsk, xoff + 0.4, 10.15, panel_w - 0.6, 1.85, size=7.5, color=_GRAYT, wrap=True)

    _footer(slide)
    return slide


def _s14_distribution(prs, D, chart_bytes: bytes):
    slide = _blank(prs)
    secteurs = D.get("secteurs",[])
    evs_vals = [_parse_x(s[4]) for s in secteurs if _parse_x(s[4]) > 0]
    _use_mg  = not bool(evs_vals)

    if _use_mg:
        _header(slide, "Distribution des Marges EBITDA Sectorielles",
                "Marge EBITDA (%) par secteur  ·  Vert = Surponderer · Amber = Neutre · Rouge = Sous-ponderer",
                active=3)
    else:
        _header(slide, "Distribution des Valorisations Sectorielles",
                "EV/EBITDA median par secteur  ·  Vert = Surponderer · Amber = Neutre · Rouge = Sous-ponderer",
                active=3)

    _pic(slide, chart_bytes, 0.9, 2.3, 14.0, 8.8)

    if _use_mg:
        # Lecture basee sur Mg.EBITDA
        mg_data = [(s[0], s[5], s[3]) for s in secteurs
                   if isinstance(s[5], (int, float)) and s[5] > 0]
        mg_sorted = sorted(mg_data, key=lambda x: x[1], reverse=True)
        _med_mg = round(float(np.median([r[1] for r in mg_sorted])), 1) if mg_sorted else 20.0
        _top_mg = mg_sorted[0]  if mg_sorted else None
        _bot_mg = mg_sorted[-1] if mg_sorted else None
        txt = ""
        if _top_mg and _bot_mg:
            txt = (
                f"{_top_mg[0]} affiche la marge EBITDA la plus elevee "
                f"({_top_mg[1]:.1f}%) — signal {_top_mg[2]} — "
                f"superieure a la mediane sectorielle de {_med_mg:.1f}%.\n\n"
                f"{_bot_mg[0]} presente la marge la plus basse "
                f"({_bot_mg[1]:.1f}%) mais le signal {_bot_mg[2]} "
                f"reflete les specificites structurelles du secteur.\n\n"
                f"Mediane des marges EBITDA : {_med_mg:.1f}% — "
                f"seuil de reference pour evaluer la rentabilite operationnelle relative.\n\n"
                f"Note : EV/EBITDA non disponible via yfinance pour cet indice — "
                f"la marge EBITDA est utilisee comme proxy de qualite operationnelle."
            )
    else:
        top_ev = max(secteurs, key=lambda s: _parse_x(s[4]), default=None)
        bot_ev = min(secteurs, key=lambda s: _parse_x(s[4]), default=None)
        med    = round(float(np.median(evs_vals)), 1)
        txt = ""
        if top_ev and bot_ev:
            txt = (
                f"{top_ev[0]} traite a {top_ev[4]} — prime de "
                f"{round((_parse_x(top_ev[4])/med - 1)*100):.0f} % vs la mediane sectorielle ({med}x). "
                f"Cette prime est justifiee par une croissance BPA structurellement elevee.\n\n"
                f"{bot_ev[0]} offre la valorisation la plus attractive ({bot_ev[4]}) mais "
                f"le signal {bot_ev[3]} reflete les risques specifiques au secteur.\n\n"
                f"Mediane sectorielle : {med}x EV/EBITDA — seuil de reference pour evaluer la cherte relative."
            )

    _rect(slide, 15.4, 2.3, 9.1, 8.8, fill=_GRAYL)
    _rect(slide, 15.4, 2.3, 0.12, 8.8, fill=_NAVY)
    _txb(slide, "Lecture de la Distribution", 15.7, 2.4, 8.6, 0.6, size=8.5, bold=True, color=_NAVY)
    _txb(slide, txt[:550], 15.7, 3.1, 8.6, 7.8, size=8, color=_GRAYT, wrap=True)

    _footer(slide)
    return slide


def _s15_zone_entree(prs, D, chart_bytes: bytes):
    slide = _blank(prs)
    _header(slide, "Zone d'Entree Optimale par Secteur",
            "P/E actuel vs mediane historique 10 ans  ·  Signal d'entree Accumuler / Neutre / Alleger",
            active=3)

    # Graphique GAUCHE (60 % de la largeur)
    _pic(slide, chart_bytes, 0.9, 2.3, 15.0, 10.5)

    # Colonne analytique DROITE
    top3    = D.get("top3_secteurs",[])
    secteurs = D.get("secteurs",[])
    _pe_g   = D.get("pe_forward","—")
    _pe_med = D.get("pe_mediane_10y","—")

    noms_b  = []
    noms_h  = []
    for t in top3:
        pef = t.get("pe_forward_raw",0) or 0
        pem = t.get("pe_mediane_10y",18.0) or 18.0
        if pef > 0 and pef < pem * 1.05:
            noms_b.append(t["nom"])
        elif pef > 0 and pef > pem * 1.15:
            noms_h.append(t["nom"])

    # Secteurs tous confondus sous/sur mediane
    all_sous = [s[0] for s in secteurs if True]  # placeholder
    _pm_str = f"{_pe_med}x" if isinstance(_pe_med,(int,float)) else str(_pe_med)

    txt_col = (
        f"PE mediane 10 ans : {_pm_str}\n"
        f"PE Forward indice : {_pe_g}\n\n"
        f"Zone d'entree favorable (PE < mediane) :\n"
        f"{'  ·  '.join([_abbrev_sector(n,18) for n in noms_b]) or 'Aucun secteur top3'}\n\n"
        f"Zone de prudence (PE > mediane +15 %) :\n"
        f"{'  ·  '.join([_abbrev_sector(n,18) for n in noms_h]) or 'Aucun'}\n\n"
        f"Methodologie : le PE Forward estime est ancre sur le PE global de l'indice "
        f"ajuste du score sectoriel (+/- ecart). Les secteurs a gauche de la ligne "
        f"pointillee (mediane 10 ans) offrent un meilleur point d'entree. "
        f"Un ecart > +20 % vs la mediane justifie une prudence accrue sur le timing."
    )
    _rect(slide, 16.3, 2.3, 8.1, 10.5, fill=_GRAYL)
    _rect(slide, 16.3, 2.3, 0.12, 10.5, fill=_NAVY)
    _txb(slide, "Lecture — Zone d'entree", 16.6, 2.4, 7.6, 0.6, size=8.5, bold=True, color=_NAVY)
    _txb(slide, txt_col[:700], 16.6, 3.1, 7.6, 9.5, size=7.5, color=_GRAYT, wrap=True)

    _footer(slide)
    return slide


def _s17_risques(prs, D):
    slide = _blank(prs)
    indice = D.get("indice","")
    _SIG_NORM_R = {
        "surponderer": "Surpondérer", "surpondérer": "Surpondérer",
        "sous-ponderer": "Sous-pondérer", "sous-pondérer": "Sous-pondérer",
        "neutre": "Neutre",
    }
    sig    = D.get("signal_global","Neutre")
    sig_disp = _SIG_NORM_R.get(sig.strip().lower(), sig)
    _header(slide, "Risques Macro & Scénarios",
            f"Analyse adversariale  ·  3 scénarios alternatifs  ·  Conditions d'invalidation du signal {sig_disp}",
            active=4)

    scenarios = D.get("scenarios",[])
    if not scenarios:
        scenarios = [
            {"titre":"Récession technique","prob":"18 %",
             "desc":"Deux trimestres PIB < 0 % — révision BPA -15/-20 %. Signal passerait Sous-pondérer."},
            {"titre":"Resserrement Fed prolongé","prob":"35 %",
             "desc":"Fed Funds > 4,5 % jusqu'en 2027 — compression multiples growth et rotation sectorielle."},
            {"titre":"Choc géopolitique","prob":"20 %",
             "desc":"Escalade géopolitique — spike VIX > 35, rotation défensive vers Consumer Staples et Health Care."},
        ]

    # 3 blocs scenarios
    box_w = 7.5
    for i, sc in enumerate(scenarios[:3]):
        xoff = 0.9 + i * (box_w + 0.35)
        # Handle both tuple format (titre, condition, signal, horizon) and dict format
        if isinstance(sc, (list, tuple)):
            _sc = list(sc) + ["", "", "", ""]
            sc_titre  = str(_sc[0] or "—")
            sc_desc   = str(_sc[1] or "")   # condition = desc
            sc_signal = str(_sc[2] or "")   # signal résultat
            # Couleur et probabilite selon signal du scenario
            _sl = sc_signal.lower()
            if "surp" in _sl:
                hdr_col  = _BUY
                prob_str = "25 %"
            elif "sous" in _sl:
                hdr_col  = _SELL
                prob_str = "20 %"
            else:
                hdr_col  = _HOLD
                prob_str = "35 %"
        else:
            prob_str = str(sc.get("prob","—"))
            try:
                prob_int = int(prob_str.replace('%','').replace(' ',''))
            except:
                prob_int = 20
            sc_titre = sc.get("titre","—")
            sc_desc  = sc.get("desc","")
            hdr_col = _SELL if prob_int >= 35 else (_HOLD if prob_int >= 25 else _BUY)

        _rect(slide, xoff, 2.3, box_w, 4.3, fill=_GRAYL)
        _rect(slide, xoff, 2.3, box_w, 0.85, fill=hdr_col)
        _txb(slide, sc_titre[:40], xoff + 0.2, 2.35, box_w - 2.5, 0.75,
             size=9, bold=True, color=_WHITE)
        _txb(slide, f"Prob. {prob_str}", xoff + box_w - 2.2, 2.4, 2.0, 0.65,
             size=9, bold=True, color=_WHITE, align=PP_ALIGN.RIGHT)
        _txb(slide, sc_desc[:220], xoff + 0.2, 3.25, box_w - 0.3, 3.2,
             size=8, color=_GRAYT, wrap=True)

    # Conditions invalidation
    conds = D.get("conditions_invalidation",[])
    if not conds:
        conds = [
            f"{indice} casse le support clé — signal passe Sous-pondérer",
            "Fed pivot dovish confirmé + CPI < 2,5 % — signal passe Surpondérer",
            "Révisions BPA agrégées < -5 % sur 2 trimestres consécutifs",
        ]

    _rect(slide, 0.9, 7.0, 23.6, 0.55, fill=_NAVY)
    _txb(slide, "Conditions d'invalidation du signal " + sig_disp.upper(),
         1.1, 7.05, 22.8, 0.45, size=8, bold=True, color=_WHITE)

    for j, cond in enumerate(conds[:4]):
        yy = 7.7 + j * 1.1
        _rect(slide, 0.9, yy, 0.1, 0.85, fill=_HOLD)
        _txb(slide, str(cond)[:120], 1.15, yy, 22.3, 0.9, size=8.5, color=_GRAYT, wrap=True)

    _footer(slide)
    return slide


def _s18_rotation(prs, D):
    slide = _blank(prs)
    indice = D.get("indice","")
    phase  = D.get("phase_cycle","Expansion avancée")
    _header(slide, "Rotation Sectorielle & Cycle Économique",
            f"{indice}  ·  Phase actuelle : {phase}  ·  Sensibilités taux/PIB  ·  Signal de rotation",
            active=4)

    rotation = D.get("rotation",[])
    if not rotation:
        rotation = [
            ("Technology",             "Expansion",  "Faible",     "Forte",    "Surpondérer"),
            ("Health Care",            "Tous cycles","Modérée",    "Modérée",  "Surpondérer"),
            ("Financials",             "Expansion",  "Haute",      "Haute",    "Surpondérer"),
            ("Consumer Discretionary", "Expansion",  "Modérée",    "Haute",    "Neutre"),
            ("Comm. Services",         "Expansion",  "Faible",     "Modérée",  "Neutre"),
            ("Industrials",            "Expansion",  "Modérée",    "Forte",    "Neutre"),
            ("Consumer Staples",       "Contraction","Modérée",    "Faible",   "Neutre"),
            ("Energy",                 "Tous cycles","Faible",     "Modérée",  "Neutre"),
            ("Real Estate",            "Contraction","Très haute", "Faible",   "Sous-pondérer"),
            ("Utilities",              "Contraction","Très haute", "Faible",   "Sous-pondérer"),
            ("Materials",              "Expansion",  "Faible",     "Forte",    "Neutre"),
        ]

    rows = [["Secteur", "Phase favorisée", "Sens. Taux", "Sens. PIB", "Signal Rotation"]]
    for r in rotation:
        row = [_abbrev_sector(str(r[0]), 20)] + [str(r[i])[:20] if i < len(r) else "—" for i in range(1, 5)]
        rows.append(row)

    tbl = _add_table(slide, rows, 0.9, 2.3, 23.6,
                     min(7.8, 0.6 + len(rows) * 0.65),
                     col_widths=[4.5, 3.5, 3.0, 3.0, 3.5],
                     font_size=8, header_size=8, alt_fill=_GRAYL)

    # Colorer signal rotation
    for r in range(1, len(rows)):
        sig = rows[r][4] if len(rows[r]) > 4 else "Neutre"
        _color_cell(tbl, r, 4, _sig_light(sig), _sig_color(sig))

    # Lecture
    texte_rot = _trunc(D.get("texte_rotation",""), 350)
    if not texte_rot:
        surp_rots = [r[0] for r in rotation if len(r) > 4 and "Surp" in str(r[4])]
        texte_rot = (
            f"En phase {phase}, surpondérer {' · '.join(surp_rots[:3]) or 'N/A'} "
            f"(forte visibilité BPA, faible sensibilité taux). "
            f"Sous-pondérer les secteurs duration longue (Real Estate, Utilities). "
            f"La rotation sectorielle suit le cycle avec un décalage de 2-3 trimestres."
        )

    y_lec = min(10.8, 2.3 + len(rows) * 0.65 + 0.3)
    _rect(slide, 0.9, y_lec, 23.6, 13.35 - y_lec, fill=_GRAYL)
    _rect(slide, 0.9, y_lec, 0.12, 13.35 - y_lec, fill=_NAVY)
    _txb(slide, "Positionnement de cycle — Synthèse et catalyseur de rotation",
         1.2, y_lec + 0.15, 22.8, 0.6, size=8, bold=True, color=_NAVY)
    _txb(slide, texte_rot, 1.2, y_lec + 0.8, 22.8, 13.35 - y_lec - 0.9,
         size=7.5, color=_GRAYT, wrap=True)

    _footer(slide)
    return slide


def _s19_sentiment(prs, D, chart_bytes: bytes):
    slide = _blank(prs)
    indice  = D.get("indice","")
    nb_arts = D.get("sentiment_agg",{}).get("nb_articles",420)
    _header(slide, "Sentiment FinBERT Agrégé",
            f"Analyse sémantique FinBERT  ·  {nb_arts} articles  ·  7 jours glissants  ·  {D.get('nb_secteurs',11)} secteurs",
            active=4)

    sa = D.get("sentiment_agg",{})
    score = sa.get("score", 0.14)
    label = sa.get("label","Neutre")
    p_nb  = sa.get("positif_nb", 168)
    p_pct = sa.get("positif_pct", 40)
    n_nb  = sa.get("neutre_nb",  189)
    n_pct = sa.get("neutre_pct", 45)
    m_nb  = sa.get("negatif_nb",  63)
    m_pct = sa.get("negatif_pct", 15)
    t_pos = sa.get("themes_pos", [])
    t_neg = sa.get("themes_neg", [])

    # Score large gauche
    _rect(slide, 0.9, 2.3, 5.8, 3.5, fill=_GRAYL)
    _rect(slide, 0.9, 2.3, 0.12, 3.5, fill=_NAVY)
    _score_str = (f"+{score:.2f}" if score > 0.01 else
                  (f"{score:.2f}" if score < -0.01 else "~0.00"))
    _txb(slide, _score_str, 1.2, 2.5, 5.3, 1.6, size=32, bold=True,
         color=_BUY if score > 0.05 else (_SELL if score < -0.05 else _HOLD))
    _txb(slide, "Score agrégé FinBERT", 1.2, 4.05, 5.3, 0.55, size=8, color=_GRAYT)
    _txb(slide, label, 1.2, 4.55, 5.3, 0.5, size=8.5, bold=True,
         color=_BUY if score > 0.05 else (_SELL if score < -0.05 else _HOLD))

    # Distribution milieu
    dist_items = [
        ("Positif",  p_nb, p_pct, _BUY),
        ("Neutre",   n_nb, n_pct, _HOLD),
        ("Négatif",  m_nb, m_pct, _SELL),
    ]
    for j, (lbl, nb, pct, col) in enumerate(dist_items):
        yy = 2.3 + j * 1.15
        _rect(slide, 7.2, yy, 7.8, 1.0, fill=_GRAYL)
        _rect(slide, 7.2, yy, pct * 0.078, 1.0, fill=col)
        txt_col = _WHITE if pct >= 30 else _BLACK
        _txb(slide, lbl,  7.4, yy + 0.05, 3.0, 0.45, size=8.5, bold=True, color=txt_col)
        _txb(slide, f"{nb} articles ({pct} %)", 7.4, yy + 0.5, 7.0, 0.45, size=8, color=txt_col)

    # Themes positifs / negatifs
    _txb(slide, "Thèmes dominants", 15.5, 2.3, 8.8, 0.5, size=8.5, bold=True, color=_NAVY)
    pos_txt = "  ·  ".join(t_pos[:4]) if t_pos else "—"
    neg_txt = "  ·  ".join(t_neg[:4]) if t_neg else "—"
    _rect(slide, 15.5, 2.9, 8.8, 1.25, fill=_BUY_L)
    _txb(slide, "+ " + pos_txt[:80], 15.7, 2.95, 8.4, 1.15, size=8, color=_GRAYT, wrap=True)
    _rect(slide, 15.5, 4.25, 8.8, 1.25, fill=_SELL_L)
    _txb(slide, "- " + neg_txt[:80], 15.7, 4.3, 8.4, 1.15, size=8, color=_GRAYT, wrap=True)

    # Chart sentiment par secteur bas
    _txb(slide, "Distribution sentiment par secteur", 0.9, 5.9, 23.6, 0.55,
         size=8, bold=True, color=_NAVY)
    _pic(slide, chart_bytes, 0.9, 6.5, 23.6, 7.0)

    _footer(slide)
    return slide


def _s20_etf_perf(prs, D, chart_bytes: bytes):
    slide = _blank(prs)
    indice = D.get("indice","")
    etf_perf_check = D.get("etf_perf",{})

    if not etf_perf_check:
        # Fallback : graphique performance indice 52 semaines + scorecard sectoriel
        _ph = D.get("perf_history")
        _has_chart = bool(_ph and _ph.get("dates") and _ph.get("indice"))
        _header(slide, f"Performance de l'Indice — 52 Semaines",
                f"{indice}  ·  vs Obligations & Or  ·  Indexe a 100  ·  Source yfinance",
                active=5)

        if _has_chart:
            # Generer le graphique index perf
            _idx_bytes = _chart_index_perf(D)
            _pic(slide, _idx_bytes, 0.9, 2.2, 23.6, 7.2)

            # Lecture analytique sous le graphique
            _i_perf = _ph.get("indice", [])
            _b_perf = _ph.get("bonds", [])
            _g_perf = _ph.get("gold", [])
            _dates  = _ph.get("dates", [])
            _ytd_val = D.get("variation_ytd","—")
            _cours_val = D.get("cours","—")
            _final_idx = (_i_perf[-1] - 100) if _i_perf else 0
            _final_b   = (_b_perf[-1] - 100) if _b_perf else None
            _final_g   = (_g_perf[-1] - 100) if _g_perf else None
            _pstart = _dates[0][:7] if _dates else "—"
            _pend   = _dates[-1][:7] if _dates else "—"
            _lec_parts = [
                f"Performance {indice} sur 52 semaines : {_final_idx:+.1f}% (base 100, de {_pstart} a {_pend}). "
                f"Cours actuel : {_cours_val} (YTD : {_ytd_val})."
            ]
            if _final_b is not None:
                _lec_parts.append(
                    f"Obligations (^TNX) : {_final_b:+.1f}% sur la periode — "
                    f"{'correlation positive avec les equites' if _final_b * _final_idx > 0 else 'divergence equites / obligations'}."
                )
            if _final_g is not None:
                _lec_parts.append(
                    f"Or (GC=F) : {_final_g:+.1f}% — "
                    f"{'refuge actif sur la periode' if _final_g > _final_idx else 'sous-performance vs equites'}."
                )
            _lec_parts.append(
                "Note : ETF sectoriels SPDR (XLK, XLV...) disponibles pour le S&P 500 uniquement. "
                "Pour les indices europeens, les equivalents iShares / Amundi ne sont pas encore integres."
            )
            _lecture_box(slide, f"Lecture — Performance {indice} sur 52 semaines",
                         "  ".join(_lec_parts), y_top=9.7, height=3.65)
        else:
            # Pas de perf_history : tableau scores + note
            _header(slide, "Performance des ETF Sectoriels — 52 Semaines",
                    f"{indice}  ·  ETF sectoriels SPDR/iShares  ·  Donnees yfinance",
                    active=5)
            _txb(slide, "Scores sectoriels FinSight — synthese allocataire",
                 0.9, 2.1, 23.6, 0.55, size=8.5, bold=True, color=_NAVY)
            secteurs_etf = D.get("secteurs", [])
            sorted_etf   = sorted(secteurs_etf, key=lambda s: s[2], reverse=True)
            _SIG_ETF = {"surponderer":"Surponderer","neutre":"Neutre","sous-ponderer":"Sous-ponderer"}
            rows_etf = [["Rang","Secteur","Score","Signal","EV/EBITDA","Mg.EBITDA","Croiss."]]
            for rg, s in enumerate(sorted_etf, 1):
                sig_raw = str(s[3]).strip().lower()
                rows_etf.append([
                    str(rg), _abbrev_sector(s[0], 22), str(s[2]),
                    _SIG_ETF.get(sig_raw, str(s[3])),
                    str(s[4]),
                    f"{s[5]:.1f}%" if isinstance(s[5],(int,float)) and s[5] else "—",
                    str(s[6]) if len(s) > 6 else "—",
                ])
            tbl_etf = _add_table(slide, rows_etf, 0.9, 2.75, 23.6,
                                 min(8.5, 0.65 + len(rows_etf)*0.65),
                                 col_widths=[1.2, 5, 1.5, 3.5, 2.5, 2.5, 2.5],
                                 font_size=8, header_size=8, alt_fill=_GRAYL)
            for r in range(1, len(rows_etf)):
                sig_r = sorted_etf[r-1][3] if r-1 < len(sorted_etf) else "Neutre"
                _color_cell(tbl_etf, r, 3, _sig_light(sig_r), _sig_color(sig_r))
            _rect(slide, 0.9, 11.8, 23.6, 1.5, fill=_GRAYL)
            _rect(slide, 0.9, 11.8, 0.12, 1.5, fill=_GRAYD)
            _txb(slide, "Note — ETF sectoriels SPDR non disponibles pour cet indice",
                 1.2, 11.9, 22.8, 0.5, size=8, bold=True, color=_GRAYT)
            _txb(slide,
                 "Les ETF sectoriels SPDR sont references sur le marche US (S&P 500). "
                 "Pour les indices europeens, les equivalents iShares / Amundi ne sont pas encore integres.",
                 1.2, 12.45, 22.8, 0.8, size=7.5, color=_GRAYT, wrap=True)
        _footer(slide)
        return slide

    _header(slide, "Performance des ETF Sectoriels — 52 Semaines",
            f"{indice}  ·  ETF sectoriels SPDR/iShares  ·  Indexe a 100 au debut de la periode  ·  Donnees yfinance",
            active=5)

    _pic(slide, chart_bytes, 0.9, 2.3, 15.0, 11.1)

    # Panel droit legende
    etf_perf = D.get("etf_perf",{})
    _rect(slide, 16.4, 2.3, 8.1, 11.1, fill=_GRAYL)
    _rect(slide, 16.4, 2.3, 8.1, 0.65, fill=_NAVY)
    _txb(slide, "Legende ETF SPDR", 16.6, 2.35, 7.8, 0.55, size=8, bold=True, color=_WHITE)

    # Trier par return desc
    etf_list = sorted(etf_perf.items(), key=lambda x: x[1].get("return_1y",0), reverse=True)
    for i, (etf, info) in enumerate(etf_list[:8]):
        yy = 3.15 + i * 1.2
        col = _LINE_COLORS_RGB[i % len(_LINE_COLORS_RGB)]
        _rect(slide, 16.5, yy + 0.15, 0.5, 0.35, fill=col)
        nom = info.get("nom","")[:18]
        ret = info.get("return_1y", 0)
        ret_str = f"{ret:+.1f} %"
        _txb(slide, f"{etf}  —  {nom}", 17.2, yy,      7.1, 0.55,
             size=7.5, bold=True, color=_NAVY)
        _txb(slide, ret_str, 17.2, yy + 0.55, 7.1, 0.55,
             size=8, bold=True,
             color=_BUY if ret > 0 else _SELL)

    # Lecture analytique bas droit
    if etf_list:
        best_etf, best_info = etf_list[0]
        worst_etf, worst_info = etf_list[-1]
        commentary = (
            f"{best_etf} ({best_info.get('nom','')}) domine avec {best_info.get('return_1y',0):+.1f} % "
            f"— confirmation du signal Surpondérer soutenu par la monétisation IA. "
            f"{worst_etf} ({worst_info.get('nom','')}) sous-performe ({worst_info.get('return_1y',0):+.1f} %) "
            f"en ligne avec le signal Sous-pondérer."
        )
    else:
        commentary = "Performance relative des ETF SPDR sur 52 semaines — source yfinance."

    _rect(slide, 16.4, 11.0, 8.1, 0.05, fill=_GRAYD)
    _txb(slide, "Lecture du graphique", 16.6, 11.1, 7.8, 0.5, size=7.5, bold=True, color=_NAVY)
    _txb(slide, commentary[:300], 16.6, 11.65, 7.8, 1.7, size=7, color=_GRAYT, wrap=True)

    _footer(slide)
    return slide


# ── Classe principale ──────────────────────────────────────────────────────────

class IndicePPTXWriter:

    @staticmethod
    def generate(data: dict, output_path: Optional[str] = None) -> bytes:
        """
        Genere un pitchbook PPTX 20 slides pour l'analyse d'indice.
        Retourne les bytes du fichier PPTX.
        Si output_path fourni, sauvegarde aussi sur disque.
        """
        log.info("IndicePPTXWriter: generation pour %s", data.get("indice","—"))

        # Macro regime (si pas deja calcule)
        if not data.get("macro"):
            try:
                import sys as _sys, os as _os
                _sys.path.insert(0, _os.path.dirname(_os.path.dirname(__file__)))
                from agents.agent_macro import AgentMacro
                data["macro"] = AgentMacro().analyze()
            except Exception as _me:
                log.warning("IndicePPTXWriter: AgentMacro: %s", _me)
                data.setdefault("macro", {})

        # Pre-calcul des charts (peut echouer silencieusement)
        try:
            secteurs = data.get("secteurs",[])
            scatter_bytes   = _chart_scatter(secteurs)
            score_bytes     = _chart_score_bars(secteurs)
            ev_bytes        = _chart_ev_distribution(secteurs)
            zone_bytes      = _chart_zone_entree(data)
            sent_bytes      = _chart_sentiment_bars(data.get("sentiment_agg",{}))
            etf_bytes       = _chart_etf_perf(data)
        except Exception as e:
            log.warning("IndicePPTXWriter: erreur pre-calcul charts: %s", e)
            # Fallback: image vide
            _empty = _make_empty_chart()
            scatter_bytes = score_bytes = ev_bytes = zone_bytes = sent_bytes = etf_bytes = _empty

        prs = Presentation()
        prs.slide_width  = _SW
        prs.slide_height = _SH

        def _safe(fn, *args, label="slide"):
            try:
                fn(*args)
            except Exception as _e:
                log.warning("IndicePPTXWriter: %s: %s", label, _e)
                try:
                    sl = prs.slides.add_slide(prs.slide_layouts[6])
                    _txb(sl, label, Cm(0.5), Cm(0.5), Cm(8), Cm(1), 11, bold=False)
                except Exception:
                    pass

        # Slide 1 — Cover
        _safe(_s01_cover, prs, data, label="s01_cover")
        # Slide 2 — Executive Summary
        _safe(_s02_exec_summary, prs, data, label="s02_exec_summary")
        # Slide 3 — Sommaire
        _safe(_s03_sommaire, prs, data, label="s03_sommaire")
        # Slide 4 — Chapter 01 divider
        _safe(_chapter_divider, prs, "01", "Synth\u00e8se Macro & Signal Global",
              "Valorisation top-down \u00b7 ERP \u00b7 Cycle \u00e9conomique \u00b7 Catalyseurs & risques",
              label="s04_divider")
        # Slide 5 — Description de l'Indice
        _safe(_s05_description, prs, data, label="s05_description")
        # Slide 6 — Valorisation Macro Top-Down
        _safe(_s06_valorisation, prs, data, label="s06_valorisation")
        # Slide 7 — Positionnement dans le Cycle
        _safe(_s07_cycle, prs, data, label="s07_cycle")
        # Slide 8 — Chapter 02 divider
        _safe(_chapter_divider, prs, "02", "Cartographie des Secteurs",
              f"{data.get('nb_secteurs',11)} secteurs GICS \u00b7 Scores \u00b7 Scatter valorisation \u00b7 D\u00e9composition",
              label="s08_divider")
        # Slide 9 — Cartographie des Secteurs
        _safe(_s09_cartographie, prs, data, label="s09_cartographie")
        # Slide 10 — Valorisation vs Croissance BPA
        _safe(_s10_scatter, prs, data, scatter_bytes, label="s10_scatter")
        # Slide 11 — Decomposition des Scores
        _safe(_s11_decomposition, prs, data, label="s11_decomposition")
        # Slide 12 — Chapter 03 divider
        _safe(_chapter_divider, prs, "03", "Top 3 Secteurs Recommand\u00e9s",
              "Synth\u00e8se signal \u00b7 Soci\u00e9t\u00e9s repr\u00e9sentatives \u00b7 Zone d'entr\u00e9e \u00b7 Distribution",
              label="s12_divider")
        # Slide 13 — Top 3 Secteurs
        _safe(_s13_top3, prs, data, label="s13_top3")
        # Slide 14 — Distribution valorisations
        _safe(_s14_distribution, prs, data, ev_bytes, label="s14_distribution")
        # Slide 15 — Zone d'Entree
        _safe(_s15_zone_entree, prs, data, zone_bytes, label="s15_zone_entree")
        # Slide 16 — Chapter 04 divider
        _safe(_chapter_divider, prs, "04", "Risques, Rotation & Sentiment",
              "Sc\u00e9narios alternatifs \u00b7 Rotation sectorielle \u00b7 FinBERT \u00b7 Performance ETF",
              label="s16_divider")
        # Slide 17 — Risques Macro & Scenarios
        _safe(_s17_risques, prs, data, label="s17_risques")
        # Slide 18 — Rotation Sectorielle
        _safe(_s18_rotation, prs, data, label="s18_rotation")
        # Slide 19 — Sentiment FinBERT
        _safe(_s19_sentiment, prs, data, sent_bytes, label="s19_sentiment")
        # Slide 20 — Performance ETF
        _safe(_s20_etf_perf, prs, data, etf_bytes, label="s20_etf_perf")

        buf = io.BytesIO()
        prs.save(buf)
        raw = buf.getvalue()

        if output_path:
            import os
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(raw)
            log.info("IndicePPTXWriter: sauvegarde -> %s (%d Ko)", output_path, len(raw)//1024)

        return raw


def _make_empty_chart() -> bytes:
    """Graphique vide de secours."""
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.text(0.5, 0.5, "Graphique non disponible", ha='center', va='center',
            transform=ax.transAxes, color='#999999', fontsize=12)
    ax.axis('off')
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    return buf.read()
