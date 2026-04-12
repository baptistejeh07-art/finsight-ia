# =============================================================================
# FinSight IA — Indice Comparison PDF Writer (13 pages IB-grade)
# outputs/indice_comparison_pdf_writer.py
#
# Rapport PDF comparatif d'indices boursiers, format aligné cmp société/secteur.
#   - Cover avec bandeau navy (identique aux autres pages)
#   - 13 pages avec texte LLM enrichi à chaque section
#   - Texte LLM = titre navy + paragraphe justifié (pas de box, réservées au PPTX)
#   - Mentions légales et méthodologie étoffées
#
# Usage :
#   from outputs.indice_comparison_pdf_writer import IndiceComparisonPDFWriter
#   pdf_bytes = IndiceComparisonPDFWriter.generate_bytes(data)
# =============================================================================
from __future__ import annotations

import io
import logging
from datetime import date as _date_cls
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    _MPL = True
except ImportError:
    _MPL = False
    plt = None
    np = None

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Image, KeepTogether, CondPageBreak
)

# =============================================================================
# PALETTE
# =============================================================================
NAVY        = colors.HexColor('#1B3A6B')
NAVY_LIGHT  = colors.HexColor('#2A5298')
NAVY_PALE   = colors.HexColor('#EEF3FA')
NAVY_MID    = colors.HexColor('#2E5FA3')
COLOR_A     = colors.HexColor('#2E5FA3')
COLOR_B     = colors.HexColor('#1A7A4A')
GOLD        = colors.HexColor('#C9A227')
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
COL_A_PAL   = colors.HexColor('#EEF3FA')
COL_B_PAL   = colors.HexColor('#EAF4EF')
GOLD_PAL    = colors.HexColor('#FDF6E3')

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
       align=TA_LEFT, bold=False, italic=False, sb=0, sa=2):
    fn = font
    if bold:
        fn = 'Helvetica-Bold'
    elif italic:
        fn = 'Helvetica-Oblique'
    return ParagraphStyle(
        name,
        fontName=fn,
        fontSize=size, textColor=color, leading=leading,
        alignment=align, spaceBefore=sb, spaceAfter=sa,
    )

S_BODY       = _s('body',    size=8.5, leading=13, color=GREY_TEXT, align=TA_JUSTIFY)
S_BODY_DARK  = _s('bodyd',   size=8.5, leading=13, color=BLACK,     align=TA_JUSTIFY)
S_LABEL      = _s('label',   size=7.5, leading=10, color=GREY_TEXT)
S_SECTION    = _s('sec',     size=12,  leading=16, color=NAVY, bold=True, sb=8, sa=2)
S_SUBSECTION = _s('subsec',  size=9,   leading=13, color=NAVY, bold=True, sb=5, sa=3)
S_TH_C       = _s('thc', size=8, leading=11, color=WHITE, bold=True, align=TA_CENTER)
S_TH_L       = _s('thl', size=8, leading=11, color=WHITE, bold=True, align=TA_LEFT)
S_TD_L       = _s('tdl', size=8, leading=11, color=BLACK, align=TA_LEFT)
S_TD_C       = _s('tdc', size=8, leading=11, color=BLACK, align=TA_CENTER)
S_TD_B       = _s('tdb', size=8, leading=11, color=BLACK, bold=True, align=TA_LEFT)
S_TD_BC      = _s('tdbc', size=8, leading=11, color=BLACK, bold=True, align=TA_CENTER)
S_TD_G       = _s('tdg', size=8, leading=11, color=BUY_GREEN, bold=True, align=TA_CENTER)
S_TD_R       = _s('tdr', size=8, leading=11, color=SELL_RED,  bold=True, align=TA_CENTER)
S_NOTE       = _s('note', size=6.5, leading=9, color=GREY_TEXT)
S_LLM_TTL    = _s('llm_t', size=9, leading=12, color=NAVY, bold=True)
S_LLM_BODY   = _s('llm_b', size=8.5, leading=13, color=GREY_TEXT, align=TA_JUSTIFY)
S_DISC       = _s('disc', size=6.5, leading=9.5, color=GREY_TEXT, align=TA_JUSTIFY)
S_DISC_TTL   = _s('disc_t', size=8, leading=11, color=NAVY, bold=True)


# =============================================================================
# HELPERS
# =============================================================================

def _enc(s):
    """Encodage cp1252 défensif (compatible accents français)."""
    if not s:
        return ""
    try:
        import unicodedata
        s = unicodedata.normalize('NFKC', str(s))
        return s.encode('cp1252', errors='replace').decode('cp1252')
    except Exception:
        return str(s)


def _safe(s):
    """Encode et échappe pour Paragraph ReportLab."""
    if not s:
        return ""
    try:
        import unicodedata
        s = unicodedata.normalize('NFKC', str(s))
        s = s.encode('cp1252', errors='replace').decode('cp1252')
        s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return s
    except Exception:
        return str(s)


def _pct(v, signed=False) -> str:
    if v is None:
        return "\u2014"
    try:
        fv = float(v)
        if abs(fv) <= 2:
            fv = fv * 100
        s = f"{fv:+.1f}" if signed else f"{fv:.1f}"
        return _enc(s.replace(".", ",") + "\u00a0%")
    except Exception:
        return "\u2014"


def _pct_s(v) -> str:
    return _pct(v, signed=True)


def _num(v, dp=1) -> str:
    if v is None:
        return "\u2014"
    try:
        return _enc(f"{float(v):.{dp}f}".replace(".", ","))
    except Exception:
        return "\u2014"


def _safe_float(v):
    if v is None:
        return None
    try:
        f = float(v)
        return f if not (f != f) else None
    except Exception:
        return None


def _sig_c(signal: str):
    s = str(signal)
    if "Surp" in s or "Positif" in s:
        return BUY_GREEN
    if "Sous" in s or "Négatif" in s or "Négatif" in s:
        return SELL_RED
    return HOLD_AMB


def _sig_bg(signal: str):
    s = str(signal)
    if "Surp" in s or "Positif" in s:
        return colors.HexColor('#E8F5EE')
    if "Sous" in s or "Négatif" in s or "Négatif" in s:
        return colors.HexColor('#FBEBEB')
    return colors.HexColor('#FDF3E5')


def _favorise_lower(va, vb, na, nb) -> str:
    fa = _safe_float(va)
    fb = _safe_float(vb)
    if fa is None or fb is None:
        return "\u2014"
    if fa < fb:
        return _enc(na[:14])
    if fb < fa:
        return _enc(nb[:14])
    return "Égalité"


def _favorise_higher(va, vb, na, nb) -> str:
    fa = _safe_float(va)
    fb = _safe_float(vb)
    if fa is None or fb is None:
        return "\u2014"
    if abs(fa) <= 1:
        fa *= 100
    if abs(fb) <= 1:
        fb *= 100
    if fa > fb:
        return _enc(na[:14])
    if fb > fa:
        return _enc(nb[:14])
    return "Égalité"


def _ecart_pct(va, vb) -> str:
    fa = _safe_float(va)
    fb = _safe_float(vb)
    if fa is None or fb is None:
        return "\u2014"
    if abs(fa) <= 2:
        fa *= 100
    if abs(fb) <= 2:
        fb *= 100
    diff = fa - fb
    return _enc(f"{diff:+.1f}".replace(".", ",") + "\u00a0pp")


def _ecart_mult(va, vb) -> str:
    fa = _safe_float(va)
    fb = _safe_float(vb)
    if fa is None or fb is None:
        return "\u2014"
    diff = fa - fb
    return _enc(f"{diff:+.1f}".replace(".", ",") + "x")


# =============================================================================
# CANVAS CALLBACKS
# =============================================================================

def _on_page(canvas, doc, data):
    """En-tête et pied de page sur chaque page (cover page 1 épurée)."""
    canvas.saveState()
    page_num = doc.page

    if page_num == 1:
        # Cover — bandeau navy en haut (comme les autres pages)
        name_a = _enc(data.get("name_a", "Indice A"))
        name_b = _enc(data.get("name_b", "Indice B"))
        canvas.setFillColor(NAVY)
        canvas.rect(0, PAGE_H - 14*mm, PAGE_W, 14*mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(MARGIN_L, PAGE_H - 9*mm,
                          f"FinSight IA  |  Comparatif Indices : {name_a} vs {name_b}")
        canvas.setFont("Helvetica", 7.5)
        date_str = _enc(data.get("date", str(_date_cls.today())))
        canvas.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 9*mm,
                               f"{date_str}  |  Confidentiel  |  Page {page_num}")
        # Footer minimal
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, PAGE_W, 10*mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica", 6.5)
        canvas.drawString(MARGIN_L, 3.5*mm,
                          "FinSight IA  \u00b7  Document confidentiel")
        canvas.drawRightString(PAGE_W - MARGIN_R, 3.5*mm, date_str)

    else:
        # Pages intérieures : header navy
        name_a = _enc(data.get("name_a", "Indice A"))
        name_b = _enc(data.get("name_b", "Indice B"))
        canvas.setFillColor(NAVY)
        canvas.rect(0, PAGE_H - 14*mm, PAGE_W, 14*mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(MARGIN_L, PAGE_H - 9*mm,
                          f"FinSight IA  |  Comparatif Indices : {name_a} vs {name_b}")
        canvas.setFont("Helvetica", 7.5)
        canvas.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 9*mm,
                               f"{_enc(data.get('date', ''))}  |  Confidentiel  |  Page {page_num}")

        # Footer
        canvas.setStrokeColor(GREY_MED)
        canvas.setLineWidth(0.15)
        canvas.line(MARGIN_L, MARGIN_B - 2*mm, PAGE_W - MARGIN_R, MARGIN_B - 2*mm)
        canvas.setFillColor(GREY_TEXT)
        canvas.setFont("Helvetica", 6.5)
        canvas.drawString(MARGIN_L, MARGIN_B - 7*mm,
                          "FinSight IA v1.0 — Document généré par IA. Ne constitue pas un conseil en investissement.")
        canvas.drawRightString(PAGE_W - MARGIN_R, MARGIN_B - 7*mm,
                               "Sources : yfinance")

    canvas.restoreState()


# =============================================================================
# CONTENT BUILDERS
# =============================================================================

def _llm_box_std(title: str, text: str, width=TABLE_W) -> list:
    """Texte LLM : titre navy + paragraphe justifié, sans box (boxes réservées au PPTX)."""
    if not text:
        return []
    elems = [
        Paragraph(_safe(title.upper()), S_LLM_TTL),
        Spacer(1, 1.5*mm),
        Paragraph(_safe(text), S_LLM_BODY),
        Spacer(1, 3*mm),
    ]
    return [KeepTogether(elems)]


def _section_header(title: str, num: str = "") -> list:
    title_str = f"{num}. {title}" if num else title
    return [
        Paragraph(_safe(title_str), S_SECTION),
        HRFlowable(width=TABLE_W, thickness=0.8, color=NAVY, spaceAfter=3*mm),
    ]


def _tbl(col_widths_mm, rows, hdr_fill=NAVY) -> Table:
    col_ws = [w * mm for w in col_widths_mm]
    tbl = Table(rows, colWidths=col_ws, repeatRows=1)
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), hdr_fill),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7.5),
        ('FONTSIZE', (0, 1), (-1, -1), 7.5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.3, GREY_MED),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, ROW_ALT]),
    ]
    tbl.setStyle(TableStyle(style))
    return tbl


def _chart_buf_mpl(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=160, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf


# =============================================================================
# CHARTS
# =============================================================================

def _perf_chart_img(data: dict, width=170*mm, height=80*mm) -> Optional[Image]:
    if not _MPL:
        return None
    ph = data.get("perf_history")
    if not ph or not ph.get("dates") or not ph.get("indice_a") or not ph.get("indice_b"):
        return None
    try:
        name_a = data.get("name_a", "Indice A")
        name_b = data.get("name_b", "Indice B")
        dates_raw = ph["dates"]
        n = len(dates_raw)
        step = max(1, n // 80)
        idx = list(range(0, n, step))
        if n > 0 and idx[-1] != n - 1:
            idx.append(n - 1)
        ys_a = ph["indice_a"]
        ys_b = ph["indice_b"]
        xs = list(range(len(idx)))

        fig, ax = plt.subplots(figsize=(11, 5.5))
        fig.patch.set_facecolor('white')
        ax.set_facecolor('#FAFBFD')
        ax.plot(xs, [ys_a[i] for i in idx], color='#2E5FA3', linewidth=2.2,
                label=name_a[:24], zorder=3)
        ax.plot(xs, [ys_b[i] for i in idx], color='#1A7A4A', linewidth=2.2,
                label=name_b[:24], zorder=3)
        ax.axhline(100, color='#CCCCCC', linewidth=0.9, linestyle='--')
        ax.fill_between(xs, [ys_a[i] for i in idx], 100, alpha=0.10, color='#2E5FA3')
        ax.fill_between(xs, [ys_b[i] for i in idx], 100, alpha=0.10, color='#1A7A4A')

        ret_a = ys_a[-1] - 100
        ret_b = ys_b[-1] - 100
        leader = name_a if ret_a > ret_b else name_b
        spread = abs(ret_a - ret_b)
        ax.set_title(
            f"52 semaines : {name_a} {ret_a:+.1f}% vs {name_b} {ret_b:+.1f}% — "
            f"{leader} surperforme de {spread:.1f} pts",
            fontsize=12, fontweight='bold', color='#1B3A6B', pad=12
        )

        tick_step = max(1, len(xs) // 8)
        lbls = [dates_raw[i][:7] for i in idx]
        ax.set_xticks(xs[::tick_step])
        ax.set_xticklabels(lbls[::tick_step], rotation=25, ha='right', fontsize=9)
        ax.set_ylabel("Base 100", fontsize=10)
        ax.tick_params(labelsize=9)
        ax.legend(loc='upper left', fontsize=11, framealpha=0.95)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='y', alpha=0.3)
        fig.tight_layout(pad=0.5)

        buf = _chart_buf_mpl(fig)
        return Image(buf, width=width, height=height)
    except Exception as e:
        log.warning(f"[indice_cmp_pdf] perf chart error: {e}")
        return None


def _perf_decomposition_chart(data: dict, width=170*mm, height=70*mm) -> Optional[Image]:
    if not _MPL:
        return None
    try:
        name_a = data.get("name_a", "Indice A")
        name_b = data.get("name_b", "Indice B")
        horizons = ["YTD", "1 an", "3 ans", "5 ans"]
        keys = ["perf_ytd", "perf_1y", "perf_3y", "perf_5y"]
        va = []
        vb = []
        for k in keys:
            a = _safe_float(data.get(k + "_a")) or 0
            b = _safe_float(data.get(k + "_b")) or 0
            if abs(a) <= 2:
                a *= 100
            if abs(b) <= 2:
                b *= 100
            va.append(a)
            vb.append(b)

        x = np.arange(len(horizons))
        bw = 0.36
        fig, ax = plt.subplots(figsize=(11, 4.8))
        fig.patch.set_facecolor('white')
        ax.set_facecolor('#FAFBFD')
        b1 = ax.bar(x - bw / 2, va, bw, label=name_a[:24], color='#2E5FA3', alpha=0.88)
        b2 = ax.bar(x + bw / 2, vb, bw, label=name_b[:24], color='#1A7A4A', alpha=0.88)
        ax.set_xticks(x)
        ax.set_xticklabels(horizons, fontsize=11)
        ax.set_ylabel("Performance (%)", fontsize=10)
        ax.legend(fontsize=10, framealpha=0.95)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.axhline(0, color='#666', linewidth=0.8)
        ax.grid(axis='y', alpha=0.3)
        for bar in list(b1) + list(b2):
            h = bar.get_height()
            ax.annotate(f"{h:+.1f}%",
                        xy=(bar.get_x() + bar.get_width() / 2, h),
                        xytext=(0, 4 if h >= 0 else -10),
                        textcoords="offset points",
                        ha='center', va='bottom' if h >= 0 else 'top',
                        fontsize=9, fontweight='bold')
        fig.tight_layout(pad=0.5)
        buf = _chart_buf_mpl(fig)
        return Image(buf, width=width, height=height)
    except Exception as e:
        log.warning(f"[indice_cmp_pdf] perf decomp chart error: {e}")
        return None


def _risque_chart_img(data: dict, width=170*mm, height=60*mm) -> Optional[Image]:
    if not _MPL:
        return None
    try:
        name_a = data.get("name_a", "Indice A")
        name_b = data.get("name_b", "Indice B")
        cats = ["Volatilité", "Sharpe", "Max Drawdown"]
        vol_a = _safe_float(data.get("vol_1y_a")) or 0
        vol_b = _safe_float(data.get("vol_1y_b")) or 0
        sha_a = _safe_float(data.get("sharpe_1y_a")) or 0
        sha_b = _safe_float(data.get("sharpe_1y_b")) or 0
        dd_a = _safe_float(data.get("max_dd_a")) or 0
        dd_b = _safe_float(data.get("max_dd_b")) or 0
        if abs(dd_a) < 1:
            dd_a *= 100
        if abs(dd_b) < 1:
            dd_b *= 100
        va = [vol_a, sha_a, abs(dd_a)]
        vb = [vol_b, sha_b, abs(dd_b)]

        x = np.arange(len(cats))
        bw = 0.36
        fig, ax = plt.subplots(figsize=(11, 4.0))
        fig.patch.set_facecolor('white')
        ax.set_facecolor('#FAFBFD')
        b1 = ax.bar(x - bw / 2, va, bw, label=name_a[:24], color='#2E5FA3', alpha=0.88)
        b2 = ax.bar(x + bw / 2, vb, bw, label=name_b[:24], color='#1A7A4A', alpha=0.88)
        ax.set_xticks(x)
        ax.set_xticklabels(cats, fontsize=11)
        ax.legend(fontsize=10, framealpha=0.95)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='y', alpha=0.3)
        for bar in list(b1) + list(b2):
            h = bar.get_height()
            ax.annotate(f"{h:.1f}",
                        xy=(bar.get_x() + bar.get_width() / 2, h),
                        xytext=(0, 4),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=9)
        fig.tight_layout(pad=0.5)
        buf = _chart_buf_mpl(fig)
        return Image(buf, width=width, height=height)
    except Exception as e:
        log.warning(f"[indice_cmp_pdf] risque chart error: {e}")
        return None


def _valuation_chart_img(data: dict, width=170*mm, height=60*mm) -> Optional[Image]:
    if not _MPL:
        return None
    try:
        name_a = data.get("name_a", "Indice A")
        name_b = data.get("name_b", "Indice B")
        cats = []
        va = []
        vb = []
        if data.get("pe_fwd_a") is not None or data.get("pe_fwd_b") is not None:
            cats.append("P/E Forward")
            va.append(_safe_float(data.get("pe_fwd_a")) or 0)
            vb.append(_safe_float(data.get("pe_fwd_b")) or 0)
        if data.get("pb_a") is not None or data.get("pb_b") is not None:
            cats.append("P/B")
            va.append(_safe_float(data.get("pb_a")) or 0)
            vb.append(_safe_float(data.get("pb_b")) or 0)
        if not cats:
            return None
        x = np.arange(len(cats))
        bw = 0.36
        fig, ax = plt.subplots(figsize=(11, 4.0))
        fig.patch.set_facecolor('white')
        ax.set_facecolor('#FAFBFD')
        b1 = ax.bar(x - bw / 2, va, bw, label=name_a[:24], color='#2E5FA3', alpha=0.88)
        b2 = ax.bar(x + bw / 2, vb, bw, label=name_b[:24], color='#1A7A4A', alpha=0.88)
        ax.set_xticks(x)
        ax.set_xticklabels(cats, fontsize=12)
        ax.set_ylabel("Multiple (x)", fontsize=11)
        ax.legend(fontsize=10, framealpha=0.95)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='y', alpha=0.3)
        for bar in list(b1) + list(b2):
            h = bar.get_height()
            if h > 0:
                ax.annotate(f"{h:.1f}x",
                            xy=(bar.get_x() + bar.get_width() / 2, h),
                            xytext=(0, 4),
                            textcoords="offset points",
                            ha='center', va='bottom', fontsize=10)
        fig.tight_layout(pad=0.5)
        buf = _chart_buf_mpl(fig)
        return Image(buf, width=width, height=height)
    except Exception as e:
        log.warning(f"[indice_cmp_pdf] valuation chart error: {e}")
        return None


def _sector_chart_img(data: dict, width=170*mm, height=85*mm) -> Optional[Image]:
    if not _MPL:
        return None
    sc_cmp = data.get("sector_comparison", [])
    if not sc_cmp:
        return None
    try:
        name_a = data.get("name_a", "Indice A")
        name_b = data.get("name_b", "Indice B")
        sects = [str(s[0])[:24] for s in sc_cmp[:11]]
        wa = [float(s[1] or 0) for s in sc_cmp[:11]]
        wb = [float(s[2] or 0) for s in sc_cmp[:11]]
        y = np.arange(len(sects))
        bh = 0.36
        fig, ax = plt.subplots(figsize=(11, 6.0))
        fig.patch.set_facecolor('white')
        ax.set_facecolor('#FAFBFD')
        ax.barh(y + bh / 2, wa, bh, label=name_a[:24], color='#2E5FA3', alpha=0.88)
        ax.barh(y - bh / 2, wb, bh, label=name_b[:24], color='#1A7A4A', alpha=0.88)
        ax.set_yticks(y)
        ax.set_yticklabels(sects, fontsize=10)
        ax.invert_yaxis()
        ax.set_xlabel("Poids (%)", fontsize=10)
        ax.legend(loc='lower right', fontsize=10, framealpha=0.95)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='x', alpha=0.3)
        fig.tight_layout(pad=0.5)
        buf = _chart_buf_mpl(fig)
        return Image(buf, width=width, height=height)
    except Exception as e:
        log.warning(f"[indice_cmp_pdf] sector chart error: {e}")
        return None


def _risk_return_chart(data: dict, width=170*mm, height=80*mm) -> Optional[Image]:
    if not _MPL:
        return None
    try:
        name_a = data.get("name_a", "Indice A")
        name_b = data.get("name_b", "Indice B")
        vol_a = _safe_float(data.get("vol_1y_a")) or 0
        vol_b = _safe_float(data.get("vol_1y_b")) or 0
        p1y_a = _safe_float(data.get("perf_1y_a")) or 0
        p1y_b = _safe_float(data.get("perf_1y_b")) or 0
        if abs(p1y_a) <= 2:
            p1y_a *= 100
        if abs(p1y_b) <= 2:
            p1y_b *= 100

        fig, ax = plt.subplots(figsize=(11, 5.5))
        fig.patch.set_facecolor('white')
        ax.set_facecolor('#FAFBFD')
        ax.scatter([vol_a], [p1y_a], s=550, color='#2E5FA3', alpha=0.85,
                   edgecolors='white', linewidths=2, label=name_a[:24], zorder=5)
        ax.scatter([vol_b], [p1y_b], s=550, color='#1A7A4A', alpha=0.85,
                   edgecolors='white', linewidths=2, label=name_b[:24], zorder=5)
        ax.annotate(name_a[:18], (vol_a, p1y_a),
                    xytext=(8, 8), textcoords="offset points",
                    fontsize=11, fontweight='bold', color='#2E5FA3')
        ax.annotate(name_b[:18], (vol_b, p1y_b),
                    xytext=(8, 8), textcoords="offset points",
                    fontsize=11, fontweight='bold', color='#1A7A4A')
        x_max = max(vol_a, vol_b) * 1.5 + 5
        y_max = max(p1y_a, p1y_b, 5) * 1.5
        y_min = min(p1y_a, p1y_b, -5) * 1.5
        ax.axhline(0, color='#999', linewidth=0.7, linestyle='--', alpha=0.7)
        ax.set_xlim(0, x_max)
        ax.set_ylim(y_min - 5, y_max + 5)
        ax.set_xlabel("Volatilité annualisée (%)", fontsize=11)
        ax.set_ylabel("Performance 1 an (%)", fontsize=11)
        ax.set_title("Profil rendement / risque sur 12 mois",
                     fontsize=13, fontweight='bold', color='#1B3A6B', pad=12)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(alpha=0.3)
        ax.legend(loc='lower right', fontsize=11, framealpha=0.95)
        fig.tight_layout(pad=0.5)
        buf = _chart_buf_mpl(fig)
        return Image(buf, width=width, height=height)
    except Exception as e:
        log.warning(f"[indice_cmp_pdf] risk-return chart error: {e}")
        return None


# =============================================================================
# DOCUMENT BUILDER — 13 PAGES
# =============================================================================

def _build_story(data: dict) -> list:
    name_a = data.get("name_a", "Indice A")
    name_b = data.get("name_b", "Indice B")
    sig_a = data.get("signal_a", "Neutre")
    sig_b = data.get("signal_b", "Neutre")
    sc_a = int(data.get("score_a", 50))
    sc_b = int(data.get("score_b", 50))
    cur_a = data.get("currency_a", "USD")
    cur_b = data.get("currency_b", "USD")
    date_s = data.get("date", str(_date_cls.today()))
    llm = data.get("llm", {}) or {}

    story = []

    # ── PAGE 1 : COVER (épurée, sans bandeau navy) ─────────────────────────
    story.append(Spacer(1, 32 * mm))
    story.append(Paragraph(_safe("Comparatif d'Indices"),
                           _s('ct', size=14, color=GREY_TEXT, align=TA_CENTER)))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(_safe(f"{name_a}  vs  {name_b}"),
                           _s('cov', size=24, leading=32, color=NAVY,
                              bold=True, align=TA_CENTER)))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(_safe(f"Univers : {cur_a}  \u00b7  {cur_b}"),
                           _s('csub', size=11, color=GREY_TEXT, align=TA_CENTER)))
    story.append(Spacer(1, 12 * mm))
    story.append(HRFlowable(width=TABLE_W, thickness=0.5, color=GREY_RULE,
                            spaceAfter=6*mm))

    # 2 colonnes signal
    sig_data = [[
        Paragraph(
            f"<b>{_safe(name_a)}</b><br/>"
            f"Score FinSight : <b>{sc_a}/100</b><br/>"
            f"Signal : <b>{_safe(sig_a)}</b><br/>"
            f"Perf 1Y : <b>{_pct_s(data.get('perf_1y_a'))}</b>",
            ParagraphStyle('sa', fontName='Helvetica', fontSize=10,
                           textColor=_sig_c(sig_a), leading=16,
                           alignment=TA_CENTER)),
        Paragraph(
            f"<b>{_safe(name_b)}</b><br/>"
            f"Score FinSight : <b>{sc_b}/100</b><br/>"
            f"Signal : <b>{_safe(sig_b)}</b><br/>"
            f"Perf 1Y : <b>{_pct_s(data.get('perf_1y_b'))}</b>",
            ParagraphStyle('sb', fontName='Helvetica', fontSize=10,
                           textColor=_sig_c(sig_b), leading=16,
                           alignment=TA_CENTER)),
    ]]
    sig_tbl = Table(sig_data, colWidths=[TABLE_W/2, TABLE_W/2])
    sig_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), _sig_bg(sig_a)),
        ('BACKGROUND', (1, 0), (1, 0), _sig_bg(sig_b)),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
    ]))
    story.append(sig_tbl)
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(_safe(date_s),
                           _s('date', size=10, color=GREY_TEXT, align=TA_CENTER)))
    story.append(PageBreak())

    # ── PAGE 2 : SYNTHÈSE COMPARATIVE ─────────────────────────────────────
    story += _section_header("Synthèse Comparative", "1")

    exec_text = llm.get("exec_summary") or (
        f"Comparaison {name_a} vs {name_b}. {name_a} affiche un score FinSight de {sc_a}/100 "
        f"({sig_a}) contre {sc_b}/100 ({sig_b}) pour {name_b}. Le différentiel de performance, "
        f"de risque et de valorisation oriente la recommandation d'allocation détaillée dans les "
        f"sections suivantes."
    )
    story.append(Paragraph(_safe(exec_text), S_BODY))
    story.append(Spacer(1, 4 * mm))

    # Tableau métriques clés
    rows = [
        [Paragraph("Indicateur", S_TH_L),
         Paragraph(_safe(name_a[:18]), S_TH_C),
         Paragraph(_safe(name_b[:18]), S_TH_C),
         Paragraph("Avantage", S_TH_C)],
        [Paragraph("Score FinSight", S_TD_B),
         Paragraph(f"{sc_a}/100", S_TD_C),
         Paragraph(f"{sc_b}/100", S_TD_C),
         Paragraph(_enc(name_a[:14] if sc_a >= sc_b else name_b[:14]), S_TD_BC)],
        [Paragraph("Performance YTD", S_TD_B),
         Paragraph(_pct_s(data.get("perf_ytd_a")), S_TD_C),
         Paragraph(_pct_s(data.get("perf_ytd_b")), S_TD_C),
         Paragraph(_favorise_higher(data.get("perf_ytd_a"), data.get("perf_ytd_b"), name_a, name_b), S_TD_BC)],
        [Paragraph("Performance 1 an", S_TD_B),
         Paragraph(_pct_s(data.get("perf_1y_a")), S_TD_C),
         Paragraph(_pct_s(data.get("perf_1y_b")), S_TD_C),
         Paragraph(_favorise_higher(data.get("perf_1y_a"), data.get("perf_1y_b"), name_a, name_b), S_TD_BC)],
        [Paragraph("Performance 3 ans", S_TD_B),
         Paragraph(_pct_s(data.get("perf_3y_a")), S_TD_C),
         Paragraph(_pct_s(data.get("perf_3y_b")), S_TD_C),
         Paragraph(_favorise_higher(data.get("perf_3y_a"), data.get("perf_3y_b"), name_a, name_b), S_TD_BC)],
        [Paragraph("Performance 5 ans", S_TD_B),
         Paragraph(_pct_s(data.get("perf_5y_a")), S_TD_C),
         Paragraph(_pct_s(data.get("perf_5y_b")), S_TD_C),
         Paragraph(_favorise_higher(data.get("perf_5y_a"), data.get("perf_5y_b"), name_a, name_b), S_TD_BC)],
        [Paragraph("Volatilité 1 an", S_TD_B),
         Paragraph(_num(data.get("vol_1y_a")) + " %", S_TD_C),
         Paragraph(_num(data.get("vol_1y_b")) + " %", S_TD_C),
         Paragraph(_favorise_lower(data.get("vol_1y_a"), data.get("vol_1y_b"), name_a, name_b), S_TD_BC)],
        [Paragraph("Sharpe Ratio 1 an", S_TD_B),
         Paragraph(_num(data.get("sharpe_1y_a"), 2), S_TD_C),
         Paragraph(_num(data.get("sharpe_1y_b"), 2), S_TD_C),
         Paragraph(_favorise_higher(data.get("sharpe_1y_a"), data.get("sharpe_1y_b"), name_a, name_b), S_TD_BC)],
        [Paragraph("Max Drawdown", S_TD_B),
         Paragraph(_pct_s(data.get("max_dd_a")), S_TD_C),
         Paragraph(_pct_s(data.get("max_dd_b")), S_TD_C),
         Paragraph(_favorise_higher(data.get("max_dd_a"), data.get("max_dd_b"), name_a, name_b), S_TD_BC)],
        [Paragraph("P/E Forward", S_TD_B),
         Paragraph(_num(data.get("pe_fwd_a"), 1) + "x", S_TD_C),
         Paragraph(_num(data.get("pe_fwd_b"), 1) + "x", S_TD_C),
         Paragraph(_favorise_lower(data.get("pe_fwd_a"), data.get("pe_fwd_b"), name_a, name_b), S_TD_BC)],
        [Paragraph("P/B (Book Value)", S_TD_B),
         Paragraph(_num(data.get("pb_a"), 1) + "x", S_TD_C),
         Paragraph(_num(data.get("pb_b"), 1) + "x", S_TD_C),
         Paragraph(_favorise_lower(data.get("pb_a"), data.get("pb_b"), name_a, name_b), S_TD_BC)],
        [Paragraph("Rendement dividende", S_TD_B),
         Paragraph(_pct(data.get("div_yield_a")), S_TD_C),
         Paragraph(_pct(data.get("div_yield_b")), S_TD_C),
         Paragraph(_favorise_higher(data.get("div_yield_a"), data.get("div_yield_b"), name_a, name_b), S_TD_BC)],
    ]
    story.append(_tbl([55, 35, 35, 45], rows))
    story.append(Spacer(1, 4 * mm))

    synth_read = llm.get("synthesis_read") or (
        f"Le tableau de synthèse révèle les forces et faiblesses relatives de chaque indice. "
        f"L'écart de score FinSight ({abs(sc_a - sc_b)} pts) traduit l'avantage structurel global. "
        f"Les sections suivantes détaillent chacune des dimensions : profil & composition, "
        f"performance & risque, valorisation, et décision d'allocation."
    )
    _winner = name_a if sc_a >= sc_b else name_b
    _gap = abs(sc_a - sc_b)
    _synth_title = f"{_winner} en avance — score FinSight {max(sc_a, sc_b)}/100 ({_gap} pts d'écart)"
    story += _llm_box_std(_synth_title, synth_read)
    story.append(PageBreak())

    # ── PAGE 3 : PROFIL & COMPOSITION SECTORIELLE ──────────────────────────
    story += _section_header("Profil & Composition Sectorielle", "2")

    profil_intro = llm.get("profil_intro") or (
        f"{name_a} et {name_b} présentent des compositions sectorielles distinctes qui "
        f"déterminent leur sensibilité aux cycles macroéconomiques. {name_a} ({cur_a}) regroupe "
        f"les sociétés cotées sur son univers de référence, avec un biais sectoriel structurel. "
        f"{name_b} ({cur_b}) offre une exposition différenciée, complémentaire ou substituable "
        f"selon l'objectif de diversification recherché."
    )
    story.append(Paragraph(_safe(profil_intro), S_BODY))
    story.append(Spacer(1, 4 * mm))

    sec_img = _sector_chart_img(data)
    if sec_img:
        story.append(sec_img)
    story.append(Spacer(1, 3 * mm))

    sectoral_read = llm.get("sectoral_read") or (
        f"Les écarts de pondération sectorielle entre {name_a} et {name_b} expliquent une "
        f"large part de leur performance relative. Un indice surpondéré sur la technologie "
        f"bénéficie des cycles d'innovation et de baisse des taux, tandis qu'un indice "
        f"financials-heavy profite des hausses de taux. À pondérer selon le régime macro et "
        f"les anticipations de cycle."
    )
    # JPM-style dynamic title : plus gros écart sectoriel
    _sect_title = f"{name_a} vs {name_b} — biais sectoriels structurels"
    try:
        _sc = data.get("sector_comparison") or []
        if _sc:
            _spreads = [(s[0], float(s[1] or 0) - float(s[2] or 0)) for s in _sc[:11]]
            _max = max(_spreads, key=lambda x: abs(x[1]))
            _winner = name_a if _max[1] > 0 else name_b
            _sect_title = f"{_winner} surpondère {_max[0]} (+{abs(_max[1]):.1f} pts) — divergence structurelle clé"
    except Exception:
        pass
    story += _llm_box_std(_sect_title, sectoral_read)
    story.append(PageBreak())

    # ── PAGE 4 : TOP HOLDINGS COMPARÉS ─────────────────────────────────────
    story += _section_header("Principaux Constituants", "3")

    top_intro = llm.get("top_intro") or (
        f"Les top constituants de chaque indice déterminent le risque idiosyncrasique : leur "
        f"poids cumulé peut représenter 20-30 % du total, amplifiant l'impact des publications "
        f"individuelles sur la performance globale de l'indice. La concentration sur quelques "
        f"leaders sectoriels (effet 'magnificent 7') est particulièrement marquée sur certains "
        f"indices US."
    )
    story.append(Paragraph(_safe(top_intro), S_BODY))
    story.append(Spacer(1, 4 * mm))

    # Top 5 A
    story.append(Paragraph(_safe(f"Top 5  —  {name_a}"), S_SUBSECTION))
    top5_a = data.get("top5_a", [])
    rows_a = [[Paragraph("Société", S_TH_L), Paragraph("Ticker", S_TH_C),
               Paragraph("Poids", S_TH_C), Paragraph("Secteur", S_TH_C)]]
    for item in top5_a[:5]:
        company = _safe(str(item[0] if len(item) > 0 else "\u2014")[:35])
        ticker = _safe(str(item[1] if len(item) > 1 else ""))
        weight = item[2] if len(item) > 2 else None
        sector = _safe(str(item[3] if len(item) > 3 else "")[:24])
        wt_s = _num(weight, 1) + "\u00a0%" if weight is not None else "\u2014"
        rows_a.append([Paragraph(company, S_TD_B),
                       Paragraph(ticker, S_TD_C),
                       Paragraph(wt_s, S_TD_C),
                       Paragraph(sector, S_TD_L)])
    while len(rows_a) < 6:
        rows_a.append([Paragraph("\u2014", S_TD_B), Paragraph("\u2014", S_TD_C),
                       Paragraph("\u2014", S_TD_C), Paragraph("\u2014", S_TD_L)])
    story.append(_tbl([65, 25, 25, 55], rows_a, hdr_fill=COLOR_A))
    story.append(Spacer(1, 4 * mm))

    # Top 5 B
    story.append(Paragraph(_safe(f"Top 5  —  {name_b}"), S_SUBSECTION))
    top5_b = data.get("top5_b", [])
    rows_b = [[Paragraph("Société", S_TH_L), Paragraph("Ticker", S_TH_C),
               Paragraph("Poids", S_TH_C), Paragraph("Secteur", S_TH_C)]]
    for item in top5_b[:5]:
        company = _safe(str(item[0] if len(item) > 0 else "\u2014")[:35])
        ticker = _safe(str(item[1] if len(item) > 1 else ""))
        weight = item[2] if len(item) > 2 else None
        sector = _safe(str(item[3] if len(item) > 3 else "")[:24])
        wt_s = _num(weight, 1) + "\u00a0%" if weight is not None else "\u2014"
        rows_b.append([Paragraph(company, S_TD_B),
                       Paragraph(ticker, S_TD_C),
                       Paragraph(wt_s, S_TD_C),
                       Paragraph(sector, S_TD_L)])
    while len(rows_b) < 6:
        rows_b.append([Paragraph("\u2014", S_TD_B), Paragraph("\u2014", S_TD_C),
                       Paragraph("\u2014", S_TD_C), Paragraph("\u2014", S_TD_L)])
    story.append(_tbl([65, 25, 25, 55], rows_b, hdr_fill=COLOR_B))
    story.append(Spacer(1, 4 * mm))

    concentration_read = llm.get("concentration_read") or (
        f"La concentration des principaux constituants détermine le risque idiosyncrasique de "
        f"l'indice. Une concentration élevée amplifie l'impact des publications individuelles "
        f"(effet 'magnificent 7' sur le S&P 500). À l'inverse, une dispersion plus large offre "
        f"une diversification intrinsèque mais réduit la sensibilité aux leaders sectoriels."
    )
    story += _llm_box_std(f"{name_a} vs {name_b} — concentration top constituants et risque idiosyncrasique", concentration_read)
    story.append(PageBreak())

    # ── PAGE 5 : PERFORMANCE 52W + MACRO ───────────────────────────────────
    story += _section_header("Performance Historique  —  52 Semaines", "4")

    perf_img = _perf_chart_img(data)
    if perf_img:
        story.append(perf_img)
    story.append(Spacer(1, 3 * mm))

    perf_macro = llm.get("perf_macro_read") or (
        f"Sur les 52 dernières semaines, le contexte macro a été marqué par la stabilisation "
        f"des taux directeurs (Fed 4,25-4,50 %, BCE 3,00 % après le pivot mi-2024), un "
        f"atterrissage en douceur de l'économie américaine (chômage 4,1 %, inflation core PCE "
        f"convergeant vers 2,5 %) et une rotation sectorielle au profit des valeurs de qualité. "
        f"Le dollar est resté fort vs euro (EUR/USD ~1,06), pénalisant les revenus européens "
        f"convertis. La trajectoire des deux indices reflète ces dynamiques croisées et leur "
        f"exposition différenciée. Catalyseurs 3-6 mois : publications T1/T2, guidance annuelle, "
        f"décisions Fed/BCE, évolutions réglementaires sectorielles."
    )
    _p1y_a = data.get("perf_1y_a") or 0
    _p1y_b = data.get("perf_1y_b") or 0
    _perf_winner = name_a if _p1y_a >= _p1y_b else name_b
    _perf_max = max(_p1y_a, _p1y_b)
    _macro_title = f"{_perf_winner} surperforme sur 12 mois ({_perf_max:+.1f}%) — contexte macro favorable"
    story += _llm_box_std(_macro_title, perf_macro)
    story.append(PageBreak())

    # ── PAGE 6 : DÉCOMPOSITION PERFS ────────────────────────────────────────
    story += _section_header("Décomposition de la Performance", "5")

    decomp_img = _perf_decomposition_chart(data)
    if decomp_img:
        story.append(decomp_img)
    story.append(Spacer(1, 3 * mm))

    # Tableau écarts
    perf_rows = [
        [Paragraph("Horizon", S_TH_L),
         Paragraph(_safe(name_a[:18]), S_TH_C),
         Paragraph(_safe(name_b[:18]), S_TH_C),
         Paragraph("Écart", S_TH_C)],
    ]
    for h, k in [("YTD", "perf_ytd"), ("1 an", "perf_1y"), ("3 ans", "perf_3y"), ("5 ans", "perf_5y")]:
        perf_rows.append([
            Paragraph(_safe(h), S_TD_B),
            Paragraph(_pct_s(data.get(k + "_a")), S_TD_C),
            Paragraph(_pct_s(data.get(k + "_b")), S_TD_C),
            Paragraph(_ecart_pct(data.get(k + "_a"), data.get(k + "_b")), S_TD_C),
        ])
    story.append(_tbl([35, 45, 45, 45], perf_rows))
    story.append(Spacer(1, 4 * mm))

    perf_decomp = llm.get("perf_decomp_read") or (
        f"La comparaison sur 4 horizons révèle si la surperformance d'un indice est récente "
        f"(momentum court terme) ou structurelle (avantage long terme). Un indice qui surperforme "
        f"YTD mais sous-performe sur 5 ans peut traduire une rotation tactique passagère, "
        f"tandis qu'une surperformance constante signale un avantage compétitif durable. "
        f"À croiser avec les valorisations relatives pour identifier les opportunités de mean reversion."
    )
    _ytd_a = data.get("perf_ytd_a") or 0
    _ytd_b = data.get("perf_ytd_b") or 0
    _ytd_winner = name_a if _ytd_a >= _ytd_b else name_b
    _decomp_title = f"{_ytd_winner} mène YTD ({max(_ytd_a, _ytd_b):+.1f}%) — décomposition multi-horizons"
    story += _llm_box_std(_decomp_title, perf_decomp)
    story.append(PageBreak())

    # ── PAGE 7 : RISQUE COMPARATIF ────────────────────────────────────────
    story += _section_header("Risque Comparatif", "6")

    # Tableau risque
    risk_rows = [
        [Paragraph("Indicateur", S_TH_L),
         Paragraph(_safe(name_a[:18]), S_TH_C),
         Paragraph(_safe(name_b[:18]), S_TH_C),
         Paragraph("Avantage", S_TH_C)],
        [Paragraph("Volatilité annualisée", S_TD_B),
         Paragraph(_num(data.get("vol_1y_a")) + " %", S_TD_C),
         Paragraph(_num(data.get("vol_1y_b")) + " %", S_TD_C),
         Paragraph(_favorise_lower(data.get("vol_1y_a"), data.get("vol_1y_b"), name_a, name_b), S_TD_BC)],
        [Paragraph("Sharpe ratio (1 an)", S_TD_B),
         Paragraph(_num(data.get("sharpe_1y_a"), 2), S_TD_C),
         Paragraph(_num(data.get("sharpe_1y_b"), 2), S_TD_C),
         Paragraph(_favorise_higher(data.get("sharpe_1y_a"), data.get("sharpe_1y_b"), name_a, name_b), S_TD_BC)],
        [Paragraph("Max Drawdown (1 an)", S_TD_B),
         Paragraph(_pct_s(data.get("max_dd_a")), S_TD_C),
         Paragraph(_pct_s(data.get("max_dd_b")), S_TD_C),
         Paragraph(_favorise_higher(data.get("max_dd_a"), data.get("max_dd_b"), name_a, name_b), S_TD_BC)],
    ]
    story.append(_tbl([60, 35, 35, 40], risk_rows))
    story.append(Spacer(1, 3 * mm))

    risk_img = _risque_chart_img(data)
    if risk_img:
        story.append(risk_img)
    story.append(Spacer(1, 3 * mm))

    risque_read = llm.get("risque_read") or (
        f"Le profil de risque détermine la taille de position en portefeuille : un indice plus "
        f"volatil impose une pondération réduite pour maintenir un budget risque équivalent. "
        f"Le Sharpe ratio mesure l'efficience du couple rendement/risque (Sharpe > 1 = excellent, "
        f"0,5-1 = correct, < 0,5 = décevant). Le Max Drawdown capture le pire scénario réalisé "
        f"sur la période et informe sur la résilience en phase de stress."
    )
    _vol_a = data.get("vol_1y_a") or 0
    _vol_b = data.get("vol_1y_b") or 0
    _safer = name_a if _vol_a < _vol_b else name_b
    _risk_title = f"{_safer} moins volatil ({min(_vol_a, _vol_b):.1f}%) — profil risque/rendement supérieur"
    story += _llm_box_std(_risk_title, risque_read)

    # Risk-return scatter sur la même page si possible (compact)
    rr_img = _risk_return_chart(data, width=170*mm, height=70*mm)
    if rr_img:
        story.append(Spacer(1, 3 * mm))
        story.append(rr_img)
    story.append(PageBreak())

    # ── PAGE 8 : VALORISATION AGRÉGÉE ──────────────────────────────────────
    story += _section_header("Valorisation Comparée", "7")

    val_rows = [
        [Paragraph("Indicateur", S_TH_L),
         Paragraph(_safe(name_a[:18]), S_TH_C),
         Paragraph(_safe(name_b[:18]), S_TH_C),
         Paragraph("Écart", S_TH_C),
         Paragraph("Avantage", S_TH_C)],
        [Paragraph("P/E Forward", S_TD_B),
         Paragraph(_num(data.get("pe_fwd_a"), 1) + "x", S_TD_C),
         Paragraph(_num(data.get("pe_fwd_b"), 1) + "x", S_TD_C),
         Paragraph(_ecart_mult(data.get("pe_fwd_a"), data.get("pe_fwd_b")), S_TD_C),
         Paragraph(_favorise_lower(data.get("pe_fwd_a"), data.get("pe_fwd_b"), name_a, name_b), S_TD_BC)],
        [Paragraph("P/B (Book Value)", S_TD_B),
         Paragraph(_num(data.get("pb_a"), 1) + "x", S_TD_C),
         Paragraph(_num(data.get("pb_b"), 1) + "x", S_TD_C),
         Paragraph(_ecart_mult(data.get("pb_a"), data.get("pb_b")), S_TD_C),
         Paragraph(_favorise_lower(data.get("pb_a"), data.get("pb_b"), name_a, name_b), S_TD_BC)],
        [Paragraph("Rendement dividende", S_TD_B),
         Paragraph(_pct(data.get("div_yield_a")), S_TD_C),
         Paragraph(_pct(data.get("div_yield_b")), S_TD_C),
         Paragraph(_ecart_pct(data.get("div_yield_a"), data.get("div_yield_b")), S_TD_C),
         Paragraph(_favorise_higher(data.get("div_yield_a"), data.get("div_yield_b"), name_a, name_b), S_TD_BC)],
    ]
    story.append(_tbl([45, 30, 30, 30, 35], val_rows))
    story.append(Spacer(1, 3 * mm))

    val_img = _valuation_chart_img(data)
    if val_img:
        story.append(val_img)
    story.append(Spacer(1, 3 * mm))

    val_read = llm.get("valorisation_read") or (
        f"Les multiples agrégés des indices reflètent la prime de valorisation que le marché "
        f"attribue à chaque univers. Un P/E élevé peut traduire (1) des anticipations de "
        f"croissance supérieures, (2) une qualité bilancielle premium, ou (3) une exubérance "
        f"de marché. Le P/B complète l'analyse en mesurant la prime sur les actifs nets. "
        f"Le rendement du dividende informe sur la maturité bilancielle et la politique de "
        f"distribution agrégée. À comparer aux moyennes historiques 5-10 ans pour identifier "
        f"les anomalies de mean reversion."
    )
    _pe_a = data.get("pe_fwd_a") or 0
    _pe_b = data.get("pe_fwd_b") or 0
    _cheap = name_a if _pe_a < _pe_b else name_b
    _val_title = f"{_cheap} décoté ({min(_pe_a, _pe_b):.1f}x P/E fwd) — opportunité valorisation relative"
    story += _llm_box_std(_val_title, val_read)
    story.append(PageBreak())

    # ── PAGE 9 : ERP FOCUS ────────────────────────────────────────────────
    story += _section_header("Equity Risk Premium (ERP)", "8")

    erp_a = data.get("erp_a", "\u2014")
    erp_b = data.get("erp_b", "\u2014")

    # Boxes ERP
    erp_data_tbl = [[
        Paragraph(
            f"<b>{_safe(name_a)}</b><br/><br/>"
            f"<font size=22 color=\"#2E5FA3\"><b>{_safe(str(erp_a))}</b></font><br/><br/>"
            f"<font size=8 color=\"#555555\">ERP estimé sur 12 mois</font>",
            ParagraphStyle('erpa', fontName='Helvetica', fontSize=10,
                           alignment=TA_CENTER, leading=14)),
        Paragraph(
            f"<b>{_safe(name_b)}</b><br/><br/>"
            f"<font size=22 color=\"#1A7A4A\"><b>{_safe(str(erp_b))}</b></font><br/><br/>"
            f"<font size=8 color=\"#555555\">ERP estimé sur 12 mois</font>",
            ParagraphStyle('erpb', fontName='Helvetica', fontSize=10,
                           alignment=TA_CENTER, leading=14)),
    ]]
    erp_tbl = Table(erp_data_tbl, colWidths=[TABLE_W/2, TABLE_W/2])
    erp_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), COL_A_PAL),
        ('BACKGROUND', (1, 0), (1, 0), COL_B_PAL),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 18),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 18),
        ('LINEBEFORE', (0, 0), (0, -1), 3, COLOR_A),
        ('LINEBEFORE', (1, 0), (1, -1), 3, COLOR_B),
    ]))
    story.append(erp_tbl)
    story.append(Spacer(1, 5 * mm))

    erp_read = llm.get("erp_read") or (
        f"L'Equity Risk Premium (ERP) mesure la prime exigée par les investisseurs pour détenir "
        f"des actions plutôt que des obligations souveraines (proxy taux 10 ans local). Un ERP "
        f"élevé (>4 %) traduit une valorisation actions historiquement attractive : le surplus "
        f"de rendement compense largement le risque additionnel. Un ERP faible (<2 %) signale "
        f"au contraire une prime insuffisanté, exposant à un re-rating baissier en cas de hausse "
        f"des taux ou de déception sur les bénéfices. La comparaison ERP entre deux indices "
        f"permet d'identifier le mieux rémunéré relativement au risque pris."
    )
    story += _llm_box_std(f"ERP {name_a} {erp_a} vs {name_b} {erp_b} — prime de risque actions comparée", erp_read)
    story.append(PageBreak())

    # ── PAGE 10 : THÈSES BULL/BEAR ────────────────────────────────────────
    story += _section_header("Thèses d'Investissement Bull / Bear", "9")

    theses_intro = llm.get("Thèses_intro") or (
        f"L'analyse bull/bear comparée permet d'identifier les arguments structurels en faveur "
        f"de chaque indice et d'évaluer les risques majeurs susceptibles d'invalider la thèse. "
        f"Cette grille de lecture est essentielle pour calibrer la conviction d'allocation et "
        f"définir les seuils de réévaluation tactique."
    )
    story.append(Paragraph(_safe(theses_intro), S_BODY))
    story.append(Spacer(1, 4 * mm))

    bull_a = llm.get("bull_a") or (
        f"{name_a} bénéficie d'une composition sectorielle alignée avec les moteurs de croissance "
        f"long terme et d'un univers liquide accessible via ETF à coût réduit. Le profil "
        f"rendement-risque historique sur 5 ans est attractif pour un mandat balanced."
    )
    bear_a = llm.get("bear_a") or (
        f"{name_a} reste exposé aux cycles macro globaux et au risque de re-rating en cas de "
        f"hausse des taux longs. La concentration sur les leaders sectoriels amplifie l'impact "
        f"des publications individuelles et des révisions de consensus."
    )
    bull_b = llm.get("bull_b") or (
        f"{name_b} offre une diversification complémentaire et une exposition à un univers "
        f"géographique/sectoriel différencié. Les multiples sont parfois plus attractifs vs "
        f"moyennes historiques, ouvrant un potentiel de mean reversion."
    )
    bear_b = llm.get("bear_b") or (
        f"{name_b} est sensible aux flux de capitaux et aux décisions des banques centrales "
        f"locales. Sa corrélation avec les chocs systémiques globaux limite la diversification "
        f"effective en phase de stress aigu."
    )

    # Table 2x2 bull/bear
    theses_tbl = [
        [Paragraph(f"<b>BULL  —  {_safe(name_a)}</b>", S_TH_L),
         Paragraph(f"<b>BULL  —  {_safe(name_b)}</b>", S_TH_L)],
        [Paragraph(_safe(bull_a), S_TD_L),
         Paragraph(_safe(bull_b), S_TD_L)],
        [Paragraph(f"<b>BEAR  —  {_safe(name_a)}</b>",
                   _s('thbe_a', size=8, color=WHITE, bold=True)),
         Paragraph(f"<b>BEAR  —  {_safe(name_b)}</b>",
                   _s('thbe_b', size=8, color=WHITE, bold=True))],
        [Paragraph(_safe(bear_a),
                   _s('tdr_a', size=8, color=BLACK, leading=11)),
         Paragraph(_safe(bear_b),
                   _s('tdr_b', size=8, color=BLACK, leading=11))],
    ]
    th_tbl = Table(theses_tbl, colWidths=[TABLE_W/2, TABLE_W/2])
    th_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), BUY_GREEN),
        ('BACKGROUND', (1, 0), (1, 0), BUY_GREEN),
        ('BACKGROUND', (0, 2), (1, 2), SELL_RED),
        ('BACKGROUND', (0, 1), (1, 1), colors.HexColor('#F0F8F4')),
        ('BACKGROUND', (0, 3), (1, 3), colors.HexColor('#FBEBEB')),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.4, GREY_RULE),
    ]))
    story.append(th_tbl)
    story.append(PageBreak())

    # ── PAGE 11 : CONDITIONS D'INVALIDATION ────────────────────────────────
    story += _section_header("Conditions d'Invalidation", "10")

    inv_rows = [
        [Paragraph("Type de signal", S_TH_L),
         Paragraph("Condition d'invalidation", S_TH_L),
         Paragraph("Horizon", S_TH_C)],
        [Paragraph("Macro", S_TD_B),
         Paragraph(_safe("Récession confirmée (2 trimestrès consécutifs de PIB négatif) ou "
                         "hausse rapide des taux 10 ans > 100 bps en 3 mois"), S_TD_L),
         Paragraph("3-6 mois", S_TD_C)],
        [Paragraph("Bénéfices", S_TD_B),
         Paragraph(_safe("Révision baissière du consensus EPS > -10 % sur 2 trimestrès "
                         "consécutifs sur l'indice gagnant"), S_TD_L),
         Paragraph("3-6 mois", S_TD_C)],
        [Paragraph("Réglementaire", S_TD_B),
         Paragraph(_safe("Choc réglementaire majeur (sanctions, taxation extraordinaire, "
                         "démantèlement) sur les top 5 constituants"), S_TD_L),
         Paragraph("6-12 mois", S_TD_C)],
        [Paragraph("Géopolitique", S_TD_B),
         Paragraph(_safe("Conflit majeur ou rupture commerciale impactant la zone "
                         "économique de référence de l'indice"), S_TD_L),
         Paragraph("0-12 mois", S_TD_C)],
        [Paragraph("Technique", S_TD_B),
         Paragraph(_safe("Cassure technique majeure (-15 % vs plus haut 52 semaines) "
                         "non rachetée en 2 mois"), S_TD_L),
         Paragraph("1-3 mois", S_TD_C)],
    ]
    story.append(_tbl([35, 100, 35], inv_rows))
    story.append(Spacer(1, 4 * mm))

    inv_text = llm.get("invalidation_read") or (
        f"Les conditions d'invalidation listées ci-dessus ne constituent pas des seuils de "
        f"sortie automatiques mais des signaux de réévaluation systématique de la thèse. Pour "
        f"un investisseur tactique, l'invalidation peut être déclenchée par une combinaison de "
        f"facteurs plutôt qu'un seul critère isolé : par exemple, une compression des marges "
        f"corporate concomitante à une révision baissière du consensus EPS et à une rotation "
        f"négative du momentum 52S. L'investisseur doit calibrer son seuil d'action en fonction "
        f"de son horizon (court terme : réaction rapide ; long terme : tolérance plus élevée). "
        f"Méthodologie de monitoring : revue mensuelle des seuils, alertes automatiques en cas "
        f"de franchissement, réévaluation complète sur 2 trimestrès consécutifs de divergence."
    )
    # winner pre-calcule pour le titre JPM (l'usage detaille est repete plus bas)
    _winner_inv = name_a if sc_a >= sc_b else name_b
    story += _llm_box_std(f"Monitoring de la thèse {_winner_inv} — seuils de réévaluation et signaux d'invalidation", inv_text)
    story.append(PageBreak())

    # ── PAGE 12 : RECOMMANDATION D'ALLOCATION ──────────────────────────────
    story += _section_header("Recommandation d'Allocation", "11")

    winner = name_a if sc_a >= sc_b else name_b
    loser = name_b if winner == name_a else name_a
    diff = abs(sc_a - sc_b)

    verdict = llm.get("verdict_read") or (
        f"{winner} présente le profil risque/rendement le plus attractif sur l'horizon 6-12 mois. "
        f"Le score FinSight de {max(sc_a, sc_b)}/100 traduit une supériorité structurelle sur "
        f"les dimensions performance, risque et valorisation. L'écart de {diff} pts vs {loser} "
        f"({min(sc_a, sc_b)}/100) légitime une surpondération tactique, sous réserve de stabilité "
        f"macroéconomique et d'absence de choc réglementaire majeur."
    )
    story.append(Paragraph(_safe(verdict), S_BODY))
    story.append(Spacer(1, 4 * mm))

    impl_text = llm.get("allocation_impl") or (
        f"<b>Mise en œuvre opérationnelle</b> : la traduction du signal en allocation portefeuille "
        f"dépend du mandat et de l'horizon de l'investisseur. Pour un portefeuille diversifié "
        f"type 60/40, une surpondération tactique de {winner} se traduit en pratique par une "
        f"exposition de +200 à +400 bps au-dessus du benchmark sectoriel. L'écart de score de "
        f"{diff} pts oriente la position size proportionnellement.<br/><br/>"
        f"<b>Véhicules d'investissement</b> : ETF physiques répliquant l'indice (frais < 20 bps), "
        f"ETF à effet de levier (à éviter sauf trading actif court terme), futures sur indice "
        f"(pour mandats institutionnels uniquement). Le choix dépend de la liquidité requise et "
        f"du coût d'exécution.<br/><br/>"
        f"<b>Calibration risque</b> : la position doit être dimensionnée en fonction de la "
        f"volatilité de l'indice et de la volatilité globale du portefeuille. Un stop-loss "
        f"tactique peut être fixé à -10 % sur le composite pour protéger le capital en cas de "
        f"détérioration brutale du sentiment ou des fondamentaux.<br/><br/>"
        f"<b>Rebalancement</b> : revue trimestrielle systématique après chaque saison de "
        f"publications, ajustement progressif si l'écart de score se compressé < 5 pts ou "
        f"s'inverse. Réévaluation complète à chaque trimestre."
    )
    story.append(Paragraph(_safe(impl_text), S_BODY))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        _safe("Note : Surpondérer = score >= 65  |  Neutre = score >= 45  |  Sous-pondérer = score < 45. "
              "Le Score FinSight est un indicateur propriétaire multidimensionnel. Il ne constitue "
              "pas un conseil en investissement."),
        S_NOTE))
    story.append(PageBreak())

    # ── PAGE 13 : MÉTHODOLOGIE & MENTIONS LÉGALES ──────────────────────────
    story += _section_header("Méthodologie & Mentions Légales", "12")

    disclaimers = [
        ("Caractère informatif et pédagogique",
         "Ce document est produit exclusivement à des fins d'information et de démonstration "
         "pédagogique. Il ne constitue en aucun cas un conseil en investissement, une recommandation "
         "personnalisée d'achat ou de vente, ni une offre ou sollicitation de souscription au sens "
         "du Règlement Général de l'AMF. Toute décision d'investissement demeure de la seule "
         "responsabilité de l'utilisateur, qui doit consulter un conseiller en investissement "
         "financier (CIF) agréé avant toute opération."),
        ("Méthodologie du scoring FinSight",
         "Le Score FinSight est un indicateur propriétaire 0-100 agrégeant performance ajustée du "
         "risque (Sharpe ratio), valorisation relative (P/E Forward, P/B), résilience (Max Drawdown) "
         "et qualité de la rémunération de l'actionnaire (rendement dividende). Seuils d'allocation : "
         "≥ 65 = Surpondérer, 45-64 = Neutre, < 45 = Sous-pondérer. L'Equity Risk Premium (ERP) est "
         "calculé comme la différence entre la performance 1 an de l'indice et le taux sans risque "
         "local (proxy : taux 10 ans souverain)."),
        ("Sources et qualité des données",
         "Les données financières sont collectées automatiquement via yfinance (Yahoo Finance) — "
         "cours, P/E forward, P/B, rendements dividende. La composition sectorielle est fournie par "
         "yfinance ou estimée pour les principaux indices. Top 5 constituants par market cap. "
         "Données retardées de 24 h sur free tier. FinSight IA ne garantit ni l'exhaustivité ni "
         "l'exactitude de ces données, qui peuvent présenter des erreurs ou des retards de mise à jour."),
        ("Limites et biais connus",
         "Les modèles sont mécaniques, statiques (snapshot point-in-time) et n'intègrent pas "
         "l'analyse qualitative (gouvernance d'indice, méthodologie de pondération, frais de "
         "réplication). Les ratios agrégés (P/E, P/B) sont des médianes des constituants et peuvent "
         "diverger des chiffres officiels publiés par les fournisseurs d'indices. Le LLM utilisé pour "
         "les textes analytiques peut produire des affirmations imprécises : les chiffres doivent "
         "être vérifiés par l'utilisateur."),
        ("Absence de due diligence",
         "FinSight IA est un outil algorithmique de screening basé sur des données publiques. Aucune "
         "due diligence spécifique, expertise sectorielle approfondie ou validation manuelle n'est "
         "réalisée. FinSight IA et ses auteurs déclinent toute responsabilité quant aux pertes ou "
         "préjudices découlant de l'utilisation de ce document."),
        ("Risques d'investissement",
         "Tout investissement en valeurs mobilières comporte un risque de perte partielle ou totale "
         "en capital. Les performances passées et les données historiques ne préjugent pas des "
         "performances futures. Les conditions de marché, le contexte macroéconomique, les décisions "
         "des banques centrales et les évènements géopolitiques peuvent évoluer rapidement et "
         "invalider les signaux présentés. La diversification, un horizon adapté au profil de risque, "
         "et une revue régulière des positions sont fortement recommandés."),
        ("Confidentialité et propriété intellectuelle",
         "Ce document est destiné à un usage privé et confidentiel. Sa reproduction, distribution, "
         "publication ou diffusion, même partielle, est strictement interdite sans autorisation "
         "écrite expresse de FinSight IA. Le scoring FinSight, la méthodologie et les visuels sont "
         "la propriété intellectuelle exclusive de FinSight IA. Toute exploitation commerciale est "
         "prohibée. Ce document ne doit pas être utilisé comme base exclusive pour une décision "
         "d'investissement."),
    ]
    for title, text in disclaimers:
        story.append(KeepTogether([
            Paragraph(_safe(title), S_DISC_TTL),
            Paragraph(_safe(text), S_DISC),
            Spacer(1, 2 * mm),
        ]))
    story.append(HRFlowable(width=TABLE_W, thickness=0.3, color=GREY_RULE,
                            spaceAfter=3*mm))
    story.append(Paragraph(
        _safe(f"Généré par FinSight IA  |  {date_s}  |  Usage confidentiel — ne pas diffuser"),
        _s('fin', size=6.5, color=GREY_TEXT, align=TA_CENTER)))

    return story


# =============================================================================
# GÉNÉRATEUR LLM
# =============================================================================

def _generate_indice_llm_pdf(data: dict) -> dict:
    """Un seul appel LLM pour les textes analytiques du PDF comparatif indice."""
    try:
        from core.llm_provider import LLMProvider
        llm = LLMProvider(provider="mistral", model="mistral-small-latest")
        name_a = data.get("name_a", "Indice A")
        name_b = data.get("name_b", "Indice B")
        sc_a = data.get("score_a", 50)
        sc_b = data.get("score_b", 50)
        sig_a = data.get("signal_a", "Neutre")
        sig_b = data.get("signal_b", "Neutre")

        def _f(v, default=0):
            try:
                return float(v) if v is not None else default
            except Exception:
                return default

        ytd_a = _f(data.get("perf_ytd_a")) * 100 if abs(_f(data.get("perf_ytd_a"))) <= 2 else _f(data.get("perf_ytd_a"))
        ytd_b = _f(data.get("perf_ytd_b")) * 100 if abs(_f(data.get("perf_ytd_b"))) <= 2 else _f(data.get("perf_ytd_b"))
        p1a = _f(data.get("perf_1y_a")) * 100 if abs(_f(data.get("perf_1y_a"))) <= 2 else _f(data.get("perf_1y_a"))
        p1b = _f(data.get("perf_1y_b")) * 100 if abs(_f(data.get("perf_1y_b"))) <= 2 else _f(data.get("perf_1y_b"))
        vol_a = _f(data.get("vol_1y_a"))
        vol_b = _f(data.get("vol_1y_b"))
        sha_a = _f(data.get("sharpe_1y_a"))
        sha_b = _f(data.get("sharpe_1y_b"))
        pe_a = _f(data.get("pe_fwd_a"))
        pe_b = _f(data.get("pe_fwd_b"))
        pb_a = _f(data.get("pb_a"))
        pb_b = _f(data.get("pb_b"))
        dy_a = _f(data.get("div_yield_a")) * 100 if abs(_f(data.get("div_yield_a"))) < 1 else _f(data.get("div_yield_a"))
        dy_b = _f(data.get("div_yield_b")) * 100 if abs(_f(data.get("div_yield_b"))) < 1 else _f(data.get("div_yield_b"))
        erp_a = data.get("erp_a", "—")
        erp_b = data.get("erp_b", "—")

        prompt = (
            f"Tu es un analyste sell-side senior (style JPMorgan Research). Rédige des textes "
            f"analytiques rigoureux pour un rapport PDF comparatif d'indices boursiers : "
            f"{name_a} vs {name_b}.\n\n"
            f"DONNÉES :\n"
            f"- {name_a} : Score {sc_a}/100 ({sig_a}), Perf YTD {ytd_a:+.1f}%, "
            f"1Y {p1a:+.1f}%, Vol {vol_a:.1f}%, Sharpe {sha_a:.2f}, "
            f"P/E Fwd {pe_a:.1f}x, P/B {pb_a:.1f}x, Div {dy_a:.1f}%, ERP {erp_a}\n"
            f"- {name_b} : Score {sc_b}/100 ({sig_b}), Perf YTD {ytd_b:+.1f}%, "
            f"1Y {p1b:+.1f}%, Vol {vol_b:.1f}%, Sharpe {sha_b:.2f}, "
            f"P/E Fwd {pe_b:.1f}x, P/B {pb_b:.1f}x, Div {dy_b:.1f}%, ERP {erp_b}\n\n"
            f"RÈGLES TYPOGRAPHIE : français correct avec TOUS les accents (é è ê à ù ç î ô), "
            f"cédilles, apostrophes droites ' et guillemets français « ». N'écris JAMAIS sans "
            f"accents — ce serait du français cassé, inacceptable en rapport IB-grade.\n"
            f"RÈGLES STYLE : prose technique sell-side senior, raisonnements économiques précis, "
            f"cite les chiffres fournis. Pas de markdown **, pas d'emojis. Développe chaque analyse "
            f"en profondeur avec des arguments structurés et des chiffres contextualisés.\n"
            f"Réponds UNIQUEMENT en JSON valide.\n\n"
            f'{{\n'
            f'  "exec_summary": "200 mots : synthèse complète de la comparaison, qui privilégier, pourquoi, catalyseurs clés",\n'
            f'  "synthesis_read": "150 mots : lecture détaillée du tableau de synthèse, écarts significatifs",\n'
            f'  "profil_intro": "150 mots : présentation des deux indices, devise, biais géographique et sectoriel",\n'
            f'  "sectoral_read": "180 mots : analyse approfondie de la composition sectorielle, écarts et implications",\n'
            f'  "top_intro": "120 mots : intro sur les top constituants, concentration et implications pour le risque",\n'
            f'  "concentration_read": "180 mots : analyse de la concentration, risque idiosyncrasique, comparaison Herfindahl",\n'
            f'  "perf_macro_read": "200 mots : contexte macro 12 mois, événements marquants, catalyseurs et risques",\n'
            f'  "perf_decomp_read": "180 mots : décomposition perfs par horizon, momentum vs structurel, attribution",\n'
            f'  "risque_read": "180 mots : profil de risque détaillé, vol/Sharpe/drawdown, régimes de marché",\n'
            f'  "valorisation_read": "180 mots : analyse multiples P/E P/B div yield, mean reversion, prime/décote historique",\n'
            f'  "erp_read": "180 mots : interprétation ERP, prime de risque actions vs obligations, implications allocation",\n'
            f'  "Thèses_intro": "120 mots : intro thèses bull/bear, cadre d analyse et hypothèses",\n'
            f'  "bull_a": "100 mots : thèse bull argumentée pour {name_a}",\n'
            f'  "bear_a": "100 mots : thèse bear argumentée pour {name_a}",\n'
            f'  "bull_b": "100 mots : thèse bull argumentée pour {name_b}",\n'
            f'  "bear_b": "100 mots : thèse bear argumentée pour {name_b}",\n'
            f'  "invalidation_read": "200 mots : méthodologie de monitoring, seuils d invalidation, signaux de réévaluation",\n'
            f'  "verdict_read": "180 mots : verdict d allocation détaillé, indice à privilégier, raisons quantitatives",\n'
            f'  "allocation_impl": "200 mots : mise en œuvre opérationnelle, véhicules ETF, calibration, horizons"\n'
            f'}}'
        )
        import json, re
        resp = llm.generate(prompt, max_tokens=4500)
        m = re.search(r'\{.*\}', resp, re.DOTALL)
        if m:
            data_out = json.loads(m.group(0))
            log.info("[indice_cmp_pdf] LLM texts OK (%d champs)", len(data_out))
            return data_out
    except Exception as e:
        log.warning("[indice_cmp_pdf] LLM génération failed: %s", e)
    return {}


# =============================================================================
# CLASSE PRINCIPALE
# =============================================================================

class IndiceComparisonPDFWriter:
    """Rapport PDF comparatif d'indices boursiers — 13 pages IB-grade."""

    @staticmethod
    def generate_bytes(data: dict) -> bytes:
        data = dict(data)
        data["llm"] = _generate_indice_llm_pdf(data)
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=MARGIN_L, rightMargin=MARGIN_R,
            topMargin=MARGIN_T, bottomMargin=MARGIN_B,
            title=f"FinSight IA — Comparaison {data.get('name_a','')} vs {data.get('name_b','')}",
        )
        story = _build_story(data)
        doc.build(story,
                  onFirstPage=lambda c, d: _on_page(c, d, data),
                  onLaterPages=lambda c, d: _on_page(c, d, data))
        return buf.getvalue()

    @staticmethod
    def generate(data: dict, output_path: str) -> str:
        pdf_bytes = IndiceComparisonPDFWriter.generate_bytes(data)
        Path(output_path).write_bytes(pdf_bytes)
        return output_path
