# =============================================================================
# FinSight IA -- Indice Comparison PDF Writer
# outputs/indice_comparison_pdf_writer.py
#
# Rapport PDF comparatif 6-7 pages A4 via ReportLab.
# Usage :
#   from outputs.indice_comparison_pdf_writer import IndiceComparisonPDFWriter
#   buf = IndiceComparisonPDFWriter.generate_bytes(data)  # -> bytes
# =============================================================================
from __future__ import annotations

import io
import logging
from datetime import date as _date_cls
from pathlib import Path

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
    np  = None

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
NAVY       = colors.HexColor('#1B3A6B')
NAVY_LIGHT = colors.HexColor('#2A5298')
COLOR_A    = colors.HexColor('#2E5FA3')
COLOR_B    = colors.HexColor('#1A7A4A')
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
COL_A_PAL  = colors.HexColor('#EEF3FA')
COL_B_PAL  = colors.HexColor('#EAF4EF')

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
S_TH_C      = _s('thc', size=8, leading=11, color=WHITE, bold=True, align=TA_CENTER)
S_TH_L      = _s('thl', size=8, leading=11, color=WHITE, bold=True, align=TA_LEFT)
S_TD_L      = _s('tdl', size=8, leading=11, color=BLACK, align=TA_LEFT)
S_TD_C      = _s('tdc', size=8, leading=11, color=BLACK, align=TA_CENTER)
S_TD_B      = _s('tdb', size=8, leading=11, color=BLACK, bold=True, align=TA_LEFT)
S_TD_BC     = _s('tdbc',size=8, leading=11, color=BLACK, bold=True, align=TA_CENTER)
S_TD_G      = _s('tdg', size=8, leading=11, color=BUY_GREEN, bold=True, align=TA_CENTER)
S_TD_R      = _s('tdr', size=8, leading=11, color=SELL_RED,  bold=True, align=TA_CENTER)
S_NOTE      = _s('note',size=6.5, leading=9, color=GREY_TEXT)
S_DISC      = _s('disc',size=6.5, leading=9, color=GREY_TEXT, align=TA_JUSTIFY)

# =============================================================================
# HELPERS
# =============================================================================
def _enc(s):
    if not s:
        return ""
    try:
        import unicodedata
        s = unicodedata.normalize('NFKC', str(s))
        return s.encode('cp1252', errors='replace').decode('cp1252')
    except Exception:
        return str(s)


def _safe(s):
    """Encode et echappe pour Paragraph ReportLab."""
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


def _sig_c(signal: str):
    s = str(signal)
    if "Surp" in s:
        return BUY_GREEN
    if "Sous" in s:
        return SELL_RED
    return HOLD_AMB


def _sig_bg(signal: str):
    s = str(signal)
    if "Surp" in s:
        return colors.HexColor('#E8F5EE')
    if "Sous" in s:
        return colors.HexColor('#FBEBEB')
    return colors.HexColor('#FDF3E5')


# =============================================================================
# CANVAS CALLBACKS (cover + en-tetes pages)
# =============================================================================

def _on_page(canvas, doc, data):
    """En-tete et pied de page sur chaque page (sauf cover page 1)."""
    canvas.saveState()
    page_num = doc.page

    if page_num == 1:
        # ── Cover ───────────────────────────────────────────────────────────
        # Bande navy haut
        canvas.setFillColor(NAVY)
        canvas.rect(0, PAGE_H - 42*mm, PAGE_W, 42*mm, fill=1, stroke=0)

        # Titre
        name_a = _enc(data.get("name_a", "Indice A"))
        name_b = _enc(data.get("name_b", "Indice B"))
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 22)
        canvas.drawCentredString(PAGE_W/2, PAGE_H - 18*mm,
                                 f"{name_a}  vs  {name_b}")
        canvas.setFont("Helvetica", 10)
        canvas.setFillColor(colors.HexColor('#AABBDD'))
        canvas.drawCentredString(PAGE_W/2, PAGE_H - 27*mm,
                                 "Comparaison d'Indices  \u2014  FinSight IA")

        # Signal A
        sig_a = _enc(data.get("signal_a", "Neutre"))
        sc_a  = int(data.get("score_a", 50))
        col_a = _sig_c(data.get("signal_a", "Neutre"))
        canvas.setFillColor(col_a)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(MARGIN_L, PAGE_H - 37*mm,
                          f"{name_a}  :  {sig_a}  ({sc_a}/100)")

        # Signal B
        sig_b = _enc(data.get("signal_b", "Neutre"))
        sc_b  = int(data.get("score_b", 50))
        col_b = _sig_c(data.get("signal_b", "Neutre"))
        canvas.setFillColor(col_b)
        canvas.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 37*mm,
                               f"{name_b}  :  {sig_b}  ({sc_b}/100)")

        # Bande navy bas
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, PAGE_W, 18*mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica", 7)
        date_str = _enc(data.get("date", str(_date_cls.today())))
        canvas.drawString(MARGIN_L, 7*mm, f"FinSight IA  \u00b7  Usage confidentiel")
        canvas.drawRightString(PAGE_W - MARGIN_R, 7*mm, date_str)

    else:
        # ── En-tete pages suivantes ──────────────────────────────────────────
        name_a = _enc(data.get("name_a", "Indice A"))
        name_b = _enc(data.get("name_b", "Indice B"))
        canvas.setFillColor(NAVY)
        canvas.rect(0, PAGE_H - 12*mm, PAGE_W, 12*mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(MARGIN_L, PAGE_H - 7*mm,
                          f"FinSight IA  \u00b7  {name_a} vs {name_b}")
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 7*mm,
                               f"Page {page_num}")

        # Pied de page
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, PAGE_W, 10*mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica", 6.5)
        canvas.drawString(MARGIN_L, 3.5*mm,
                          "Usage confidentiel  \u00b7  Ne constitue pas un conseil en investissement")

    canvas.restoreState()


# =============================================================================
# CONTENT BUILDERS
# =============================================================================

def _section_header(title: str) -> list:
    return [
        CondPageBreak(60 * mm),
        Spacer(1, 4 * mm),
        Paragraph(_safe(title), S_SECTION),
        HRFlowable(width=TABLE_W, thickness=0.8, color=NAVY, spaceAfter=3*mm),
    ]


def _row_has_data(row) -> bool:
    for cell in row[1:]:
        c = str(cell)
        if c and c not in ("\u2014", "—", "-", "N/A", ""):
            return True
    return False


def _tbl(col_widths_mm, rows, hdr_fill=NAVY) -> Table:
    """Construit une Table ReportLab stylisee."""
    col_ws = [w * mm for w in col_widths_mm]
    tbl = Table(rows, colWidths=col_ws, repeatRows=1)
    n = len(rows)

    style = [
        ('BACKGROUND', (0, 0), (-1, 0), hdr_fill),
        ('TEXTCOLOR',  (0, 0), (-1, 0), WHITE),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, 0), 7.5),
        ('FONTSIZE',   (0, 1), (-1, -1), 7.5),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('GRID',       (0, 0), (-1, -1), 0.3, GREY_MED),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, ROW_ALT]),
    ]
    tbl.setStyle(TableStyle(style))
    return tbl


def _chart_buf_mpl(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf


def _perf_table(data: dict) -> list:
    name_a = _safe(data.get("name_a", "Indice A"))[:22]
    name_b = _safe(data.get("name_b", "Indice B"))[:22]

    hdr = [Paragraph("Horizon", S_TH_L),
           Paragraph(name_a, S_TH_C),
           Paragraph(name_b, S_TH_C),
           Paragraph("Ecart (pp)", S_TH_C)]

    def _e(va, vb):
        if va is None or vb is None:
            return "\u2014"
        fa = float(va) * 100 if abs(float(va)) < 2 else float(va)
        fb = float(vb) * 100 if abs(float(vb)) < 2 else float(vb)
        diff = fa - fb
        return _enc(f"{diff:+.1f}".replace(".", ",") + "\u00a0pp")

    rows = [hdr]
    for horizon, key_a, key_b in [
        ("YTD",    "perf_ytd_a", "perf_ytd_b"),
        ("1 an",   "perf_1y_a",  "perf_1y_b"),
        ("3 ans",  "perf_3y_a",  "perf_3y_b"),
        ("5 ans",  "perf_5y_a",  "perf_5y_b"),
    ]:
        va, vb = data.get(key_a), data.get(key_b)
        row = [Paragraph(_enc(horizon), S_TD_B),
               Paragraph(_pct_s(va), S_TD_C),
               Paragraph(_pct_s(vb), S_TD_C),
               Paragraph(_e(va, vb), S_TD_C)]
        rows.append(row)

    return [_tbl([30, 40, 40, 40], rows)]


def _risque_table(data: dict) -> list:
    name_a = _safe(data.get("name_a", "Indice A"))[:22]
    name_b = _safe(data.get("name_b", "Indice B"))[:22]

    hdr = [Paragraph("Indicateur", S_TH_L),
           Paragraph(name_a, S_TH_C),
           Paragraph(name_b, S_TH_C)]

    rows_data = [
        ("Volatilite annualisee",
         _enc(_num(data.get("vol_1y_a")) + "\u00a0%"),
         _enc(_num(data.get("vol_1y_b")) + "\u00a0%")),
        ("Sharpe ratio (1 an)",
         _num(data.get("sharpe_1y_a"), 2),
         _num(data.get("sharpe_1y_b"), 2)),
        ("Max Drawdown (1 an)",
         _pct_s(data.get("max_dd_a")),
         _pct_s(data.get("max_dd_b"))),
    ]

    rows = [hdr]
    for label, va, vb in rows_data:
        rows.append([Paragraph(_enc(label), S_TD_B),
                     Paragraph(va, S_TD_C),
                     Paragraph(vb, S_TD_C)])

    return [_tbl([70, 45, 45], rows)]


def _val_table(data: dict) -> list:
    name_a = _safe(data.get("name_a", "Indice A"))[:22]
    name_b = _safe(data.get("name_b", "Indice B"))[:22]

    hdr = [Paragraph("Indicateur", S_TH_L),
           Paragraph(name_a, S_TH_C),
           Paragraph(name_b, S_TH_C),
           Paragraph("Favorise", S_TH_C)]

    def _fav_low(va, vb):
        if not va or not vb:
            return "\u2014"
        return data.get("name_a", "A")[:14] if float(va) < float(vb) else data.get("name_b", "B")[:14]

    def _fav_high(va, vb):
        if not va or not vb:
            return "\u2014"
        fa = float(va) * 100 if abs(float(va)) < 1 else float(va)
        fb = float(vb) * 100 if abs(float(vb)) < 1 else float(vb)
        return data.get("name_a", "A")[:14] if fa > fb else data.get("name_b", "B")[:14]

    pe_a = data.get("pe_fwd_a")
    pe_b = data.get("pe_fwd_b")
    pb_a = data.get("pb_a")
    pb_b = data.get("pb_b")
    dy_a = data.get("div_yield_a")
    dy_b = data.get("div_yield_b")
    erp_a= data.get("erp_a", "\u2014")
    erp_b= data.get("erp_b", "\u2014")

    rows_data = [
        ("P/E Forward",
         _enc(_num(pe_a, 1) + "x"), _enc(_num(pe_b, 1) + "x"),
         _enc(_fav_low(pe_a, pe_b))),
        ("P/B (Book Value)",
         _enc(_num(pb_a, 1) + "x"), _enc(_num(pb_b, 1) + "x"),
         _enc(_fav_low(pb_a, pb_b))),
        ("Rendement dividende",
         _pct(dy_a), _pct(dy_b),
         _enc(_fav_high(dy_a, dy_b))),
        ("ERP (prime de risque)",
         _enc(str(erp_a)), _enc(str(erp_b)), "\u2014"),
    ]

    rows = [hdr]
    for label, va, vb, fav in rows_data:
        rows.append([Paragraph(_enc(label), S_TD_B),
                     Paragraph(va, S_TD_C),
                     Paragraph(vb, S_TD_C),
                     Paragraph(fav, S_TD_C)])

    return [_tbl([55, 35, 35, 35], rows)]


def _sector_table(data: dict) -> list:
    name_a = _safe(data.get("name_a", "Indice A"))[:20]
    name_b = _safe(data.get("name_b", "Indice B"))[:20]
    sc_cmp = data.get("sector_comparison", [])

    if not sc_cmp:
        return [Paragraph("Donnees sectorielles non disponibles.", S_BODY)]

    hdr = [Paragraph("Secteur", S_TH_L),
           Paragraph(name_a, S_TH_C),
           Paragraph(name_b, S_TH_C),
           Paragraph("Ecart", S_TH_C)]

    rows = [hdr]
    for item in sc_cmp[:12]:
        sector = _enc(str(item[0] if len(item) > 0 else "")[:30])
        wa     = float(item[1]) if len(item) > 1 and item[1] is not None else None
        wb     = float(item[2]) if len(item) > 2 and item[2] is not None else None
        wa_s   = _enc(f"{wa:.1f}".replace(".", ",") + "\u00a0%") if wa is not None else "\u2014"
        wb_s   = _enc(f"{wb:.1f}".replace(".", ",") + "\u00a0%") if wb is not None else "\u2014"
        if wa is not None and wb is not None:
            diff = wa - wb
            diff_s = _enc(f"{diff:+.1f}".replace(".", ",") + "\u00a0pp")
        else:
            diff_s = "\u2014"
        rows.append([Paragraph(sector, S_TD_B),
                     Paragraph(wa_s, S_TD_C),
                     Paragraph(wb_s, S_TD_C),
                     Paragraph(diff_s, S_TD_C)])

    return [_tbl([65, 30, 30, 30], rows)]


def _top5_table(data: dict, which: str) -> list:
    name   = _safe(data.get("name_a" if which == "a" else "name_b", "Indice"))[:25]
    top5   = data.get("top5_a" if which == "a" else "top5_b", [])
    color  = COLOR_A if which == "a" else COLOR_B

    hdr = [Paragraph("Societe", S_TH_L),
           Paragraph("Ticker", S_TH_C),
           Paragraph("Poids (%)", S_TH_C),
           Paragraph("Secteur", S_TH_C)]

    rows = [hdr]
    for item in top5[:5]:
        company = _enc(str(item[0] if len(item) > 0 else "\u2014")[:40])
        ticker  = _enc(str(item[1] if len(item) > 1 else ""))
        weight  = item[2] if len(item) > 2 else None
        sector  = _enc(str(item[3] if len(item) > 3 else "")[:25])
        wt_s    = _enc(_num(weight, 1) + "\u00a0%") if weight is not None else "\u2014"
        rows.append([Paragraph(company, S_TD_B),
                     Paragraph(ticker, S_TD_C),
                     Paragraph(wt_s, S_TD_C),
                     Paragraph(sector, S_TD_L)])

    return [_tbl([65, 20, 25, 50], rows, hdr_fill=color)]


def _perf_chart_img(data: dict) -> Optional[Image]:
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
        step = max(1, n // 60)
        idx  = list(range(0, n, step))
        if n > 0 and idx[-1] != n-1:
            idx.append(n-1)

        ys_a = ph["indice_a"]
        ys_b = ph["indice_b"]
        xs   = list(range(len(idx)))

        fig, ax = plt.subplots(figsize=(9, 3.2))
        fig.patch.set_facecolor('white')
        ax.set_facecolor('#FAFBFD')

        ax.plot(xs, [ys_a[i] for i in idx], color='#2E5FA3', linewidth=1.8,
                label=name_a[:20], zorder=3)
        ax.plot(xs, [ys_b[i] for i in idx], color='#1A7A4A', linewidth=1.8,
                label=name_b[:20], zorder=3)
        ax.axhline(100, color='#CCCCCC', linewidth=0.7, linestyle='--')

        ax.fill_between(xs, [ys_a[i] for i in idx], 100, alpha=0.07, color='#2E5FA3')
        ax.fill_between(xs, [ys_b[i] for i in idx], 100, alpha=0.07, color='#1A7A4A')

        tick_step = max(1, len(xs)//7)
        lbls = [dates_raw[i][:7] for i in idx]
        ax.set_xticks(xs[::tick_step])
        ax.set_xticklabels(lbls[::tick_step], rotation=25, ha='right', fontsize=7)
        ax.set_ylabel("Base 100", fontsize=7)
        ax.yaxis.set_tick_params(labelsize=7)
        ax.legend(loc='upper left', fontsize=7.5, framealpha=0.9)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='y', alpha=0.3)
        fig.tight_layout(pad=0.4)

        buf = _chart_buf_mpl(fig)
        return Image(buf, width=160*mm, height=55*mm)
    except Exception as e:
        log.warning(f"[indice_cmp_pdf] perf chart error: {e}")
        return None


def _sector_chart_img(data: dict) -> Optional[Image]:
    if not _MPL:
        return None
    sc_cmp = data.get("sector_comparison", [])
    if not sc_cmp:
        return None
    try:
        name_a = data.get("name_a", "Indice A")
        name_b = data.get("name_b", "Indice B")
        sects  = [str(s[0])[:18] for s in sc_cmp[:10]]
        wa     = [float(s[1] or 0) for s in sc_cmp[:10]]
        wb     = [float(s[2] or 0) for s in sc_cmp[:10]]

        y  = np.arange(len(sects))
        bh = 0.3

        fig, ax = plt.subplots(figsize=(9, 4.0))
        fig.patch.set_facecolor('white')
        ax.set_facecolor('#FAFBFD')
        ax.barh(y + bh/2, wa, bh, label=name_a[:18], color='#2E5FA3', alpha=0.85)
        ax.barh(y - bh/2, wb, bh, label=name_b[:18], color='#1A7A4A', alpha=0.85)
        ax.set_yticks(y)
        ax.set_yticklabels(sects, fontsize=7.5)
        ax.invert_yaxis()
        ax.set_xlabel("Poids (%)", fontsize=8)
        ax.legend(loc='lower right', fontsize=8, framealpha=0.9)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='x', alpha=0.3)
        fig.tight_layout(pad=0.4)

        buf = _chart_buf_mpl(fig)
        return Image(buf, width=160*mm, height=70*mm)
    except Exception as e:
        log.warning(f"[indice_cmp_pdf] sector chart error: {e}")
        return None


# =============================================================================
# DOCUMENT BUILDER
# =============================================================================

def _build_story(data: dict) -> list:
    name_a  = data.get("name_a", "Indice A")
    name_b  = data.get("name_b", "Indice B")
    sig_a   = data.get("signal_a", "Neutre")
    sig_b   = data.get("signal_b", "Neutre")
    sc_a    = int(data.get("score_a", 50))
    sc_b    = int(data.get("score_b", 50))
    date_s  = data.get("date", str(_date_cls.today()))

    story = []

    # ── COVER ─────────────────────────────────────────────────────────────────
    # Espace pour laisser la place a l'en-tete canvas
    story.append(Spacer(1, 45*mm))

    # Signal boxes
    sig_tbl_rows = [[
        Paragraph(f"<b>{_safe(name_a)}</b><br/>"
                  f"Signal : <b>{_safe(sig_a)}</b>  |  Score {sc_a}/100",
                  ParagraphStyle('sa', fontName='Helvetica', fontSize=9,
                                 textColor=_sig_c(sig_a), leading=14,
                                 alignment=TA_CENTER)),
        Paragraph(f"<b>{_safe(name_b)}</b><br/>"
                  f"Signal : <b>{_safe(sig_b)}</b>  |  Score {sc_b}/100",
                  ParagraphStyle('sb', fontName='Helvetica', fontSize=9,
                                 textColor=_sig_c(sig_b), leading=14,
                                 alignment=TA_CENTER)),
    ]]
    sig_tbl = Table(sig_tbl_rows, colWidths=[TABLE_W/2, TABLE_W/2])
    sig_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), _sig_bg(sig_a)),
        ('BACKGROUND', (1, 0), (1, 0), _sig_bg(sig_b)),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, GREY_RULE),
    ]))
    story.append(sig_tbl)
    story.append(Spacer(1, 8*mm))

    # KPI Perf table (cover summary)
    kpi_rows = [[
        Paragraph("<b>Horizon</b>", ParagraphStyle('kh', fontName='Helvetica-Bold',
                  fontSize=8, textColor=WHITE, alignment=TA_LEFT)),
        Paragraph(f"<b>{_safe(name_a[:18])}</b>", ParagraphStyle('kha', fontName='Helvetica-Bold',
                  fontSize=8, textColor=WHITE, alignment=TA_CENTER)),
        Paragraph(f"<b>{_safe(name_b[:18])}</b>", ParagraphStyle('khb', fontName='Helvetica-Bold',
                  fontSize=8, textColor=WHITE, alignment=TA_CENTER)),
        Paragraph("<b>Ecart</b>", ParagraphStyle('khe', fontName='Helvetica-Bold',
                  fontSize=8, textColor=WHITE, alignment=TA_CENTER)),
    ]]
    for horizon, key_a, key_b in [
        ("YTD",   "perf_ytd_a", "perf_ytd_b"),
        ("1 an",  "perf_1y_a",  "perf_1y_b"),
        ("3 ans", "perf_3y_a",  "perf_3y_b"),
        ("5 ans", "perf_5y_a",  "perf_5y_b"),
    ]:
        va, vb = data.get(key_a), data.get(key_b)
        if va is None and vb is None:
            continue
        fa = float(va) * 100 if va and abs(float(va)) < 2 else (float(va) if va else None)
        fb = float(vb) * 100 if vb and abs(float(vb)) < 2 else (float(vb) if vb else None)
        ecart = (f"{fa-fb:+.1f}".replace(".", ",") + " pp"
                 if fa is not None and fb is not None else "\u2014")
        kpi_rows.append([
            Paragraph(_enc(horizon), S_TD_B),
            Paragraph(_pct_s(va), S_TD_C),
            Paragraph(_pct_s(vb), S_TD_C),
            Paragraph(_enc(ecart), S_TD_C),
        ])
    kpi_tbl = Table(kpi_rows, colWidths=[30*mm, 42*mm, 42*mm, 42*mm])
    kpi_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR',  (0, 0), (-1, 0), WHITE),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 7.5),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID',       (0, 0), (-1, -1), 0.3, GREY_MED),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, ROW_ALT]),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph(_safe(f"Rapport genere le {date_s}  "
                                 f"\u00b7  FinSight IA  "
                                 f"\u00b7  Donnees : yfinance"), S_NOTE))
    story.append(PageBreak())

    # ── SECTION 1 : PERFORMANCE ───────────────────────────────────────────────
    story.extend(_section_header("1. Performance Historique"))

    # Chart
    chart = _perf_chart_img(data)
    if chart:
        story.append(chart)
        story.append(Spacer(1, 4*mm))

    story.extend(_perf_table(data))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        _safe(f"Comparaison de la performance annualisee de {name_a} et {name_b}. "
              f"L'ecart est exprime en points de pourcentage (pp)."),
        S_NOTE))

    # ── SECTION 2 : RISQUE ───────────────────────────────────────────────────
    story.extend(_section_header("2. Risque Comparatif"))
    story.extend(_risque_table(data))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        _safe("Volatilite : ecart-type annualise des rendements quotidiens. "
              "Sharpe ratio : (rendement - taux sans risque 10Y) / volatilite. "
              "Max Drawdown : perte maximale du plus haut au plus bas."),
        S_NOTE))

    # ── SECTION 3 : VALORISATION ─────────────────────────────────────────────
    story.extend(_section_header("3. Valorisation"))
    story.extend(_val_table(data))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        _safe(f"P/E Forward : consensus analystes. "
              f"ERP (a) : {data.get('erp_a', 'N/D')}  |  "
              f"ERP (b) : {data.get('erp_b', 'N/D')}. "
              f"Source : yfinance / calcul Damodaran."),
        S_NOTE))

    # ── SECTION 4 : COMPOSITION SECTORIELLE ──────────────────────────────────
    story.extend(_section_header("4. Composition Sectorielle"))
    chart2 = _sector_chart_img(data)
    if chart2:
        story.append(chart2)
        story.append(Spacer(1, 3*mm))
    story.extend(_sector_table(data))

    # ── SECTION 5 : TOP 5 CONSTITUANTS ───────────────────────────────────────
    story.extend(_section_header(f"5. Principaux Constituants"))

    story.append(Paragraph(_safe(f"Top 5  \u2014  {name_a}"), S_SUBSECTION))
    story.extend(_top5_table(data, "a"))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(_safe(f"Top 5  \u2014  {name_b}"), S_SUBSECTION))
    story.extend(_top5_table(data, "b"))

    # ── SECTION 6 : VERDICT ──────────────────────────────────────────────────
    story.extend(_section_header("6. Verdict Comparatif"))

    sc_a = int(data.get("score_a", 50))
    sc_b = int(data.get("score_b", 50))
    winner = name_a if sc_a > sc_b else (name_b if sc_b > sc_a else None)

    if winner:
        loser = name_b if winner == name_a else name_a
        verdict_txt = (
            f"Sur la base du score FinSight composite, {winner} (score {max(sc_a,sc_b)}/100) "
            f"offre un meilleur profil que {loser} (score {min(sc_a,sc_b)}/100). "
        )
    else:
        verdict_txt = (
            f"Les deux indices presentent des profils comparables "
            f"({name_a} : {sc_a}/100  vs  {name_b} : {sc_b}/100). "
            f"Le choix dependra de l'objectif investisseur."
        )

    # Ajouter arguments
    pe_a = data.get("pe_fwd_a")
    pe_b = data.get("pe_fwd_b")
    if pe_a and pe_b:
        cheaper = name_a if float(pe_a) < float(pe_b) else name_b
        verdict_txt += (
            f"Sur le plan de la valorisation, {cheaper} se traite a une decote "
            f"relative (P/E : {name_a} {_num(pe_a,1)}x vs {name_b} {_num(pe_b,1)}x). "
        )

    sha_a = data.get("sharpe_1y_a")
    sha_b = data.get("sharpe_1y_b")
    if sha_a and sha_b:
        better = name_a if float(sha_a) > float(sha_b) else name_b
        verdict_txt += (
            f"{better} offre un meilleur Sharpe ratio "
            f"({_num(sha_a,2)} vs {_num(sha_b,2)}), "
            f"signalant un rendement ajuste du risque superieur. "
        )

    story.append(Paragraph(_safe(verdict_txt), S_BODY))
    story.append(Spacer(1, 4*mm))

    # Tableau bilan final
    ver_rows = [
        [Paragraph("Critere", S_TH_L),
         Paragraph(_safe(name_a[:20]), S_TH_C),
         Paragraph(_safe(name_b[:20]), S_TH_C)],
        [Paragraph("Score FinSight", S_TD_B),
         Paragraph(f"{sc_a}/100", S_TD_C),
         Paragraph(f"{sc_b}/100", S_TD_C)],
        [Paragraph("Signal", S_TD_B),
         Paragraph(_safe(data.get("signal_a", "\u2014")), S_TD_C),
         Paragraph(_safe(data.get("signal_b", "\u2014")), S_TD_C)],
        [Paragraph("Perf. 1 an", S_TD_B),
         Paragraph(_pct_s(data.get("perf_1y_a")), S_TD_C),
         Paragraph(_pct_s(data.get("perf_1y_b")), S_TD_C)],
        [Paragraph("P/E Forward", S_TD_B),
         Paragraph(_enc(_num(data.get("pe_fwd_a"),1) + "x"), S_TD_C),
         Paragraph(_enc(_num(data.get("pe_fwd_b"),1) + "x"), S_TD_C)],
        [Paragraph("Volatilite", S_TD_B),
         Paragraph(_enc(_num(data.get("vol_1y_a")) + " %"), S_TD_C),
         Paragraph(_enc(_num(data.get("vol_1y_b")) + " %"), S_TD_C)],
    ]
    ver_tbl = _tbl([65, 45, 45], ver_rows)
    story.append(ver_tbl)

    # Disclaimer
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width=TABLE_W, thickness=0.5, color=GREY_RULE))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        _safe("Ce rapport est genere automatiquement par FinSight IA a titre informatif. "
              "Il ne constitue pas un conseil en investissement. "
              "Les donnees proviennent de yfinance et peuvent presenter des retards. "
              "Tout investissement comporte un risque de perte en capital."),
        S_DISC))

    return story


# =============================================================================
# CLASSE PRINCIPALE
# =============================================================================

class IndiceComparisonPDFWriter:

    @staticmethod
    def generate_bytes(data: dict) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=MARGIN_L, rightMargin=MARGIN_R,
            topMargin=MARGIN_T,  bottomMargin=MARGIN_B,
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
