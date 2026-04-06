# =============================================================================
# FinSight IA -- Comparison PDF Writer v2
# outputs/comparison_pdf_writer.py
#
# Rapport PDF comparatif 7-8 pages A4 via ReportLab.
# Cover : fond blanc + bande navy top (style pdf_writer.py societe).
# Sections fluides via CondPageBreak (PAS PageBreak systematique).
# Filtrage des lignes "--" (row_has_data).
# Textes analytiques computed (sans LLM) pour Profil, Bilan, DCF, Risque.
#
# Usage :
#   from outputs.comparison_pdf_writer import ComparisonPDFWriter
#   path = ComparisonPDFWriter().generate(state_a, state_b, output_path)
#   buf  = ComparisonPDFWriter().generate_bytes(state_a, state_b)
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
# PALETTE (identique pdf_writer.py)
# =============================================================================
NAVY        = colors.HexColor('#1B3A6B')
NAVY_LIGHT  = colors.HexColor('#2A5298')
NAVY_MID    = colors.HexColor('#2E5FA3')
COLOR_A     = colors.HexColor('#2E5FA3')   # Societe A -- bleu
COLOR_B     = colors.HexColor('#2E8B57')   # Societe B -- vert
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
COLOR_A_PAL = colors.HexColor('#EEF3FA')
COLOR_B_PAL = colors.HexColor('#EAF4EF')

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
S_TD_A      = _s('tda', size=8, leading=11, color=HOLD_AMB,  bold=True, align=TA_CENTER)
S_NOTE      = _s('note',size=6.5, leading=9, color=GREY_TEXT)
S_DISC      = _s('disc',size=6.5, leading=9, color=GREY_TEXT, align=TA_JUSTIFY)

# =============================================================================
# HELPERS
# =============================================================================
def _enc(s):
    """Encode cp1252 pour Helvetica / canvas ReportLab."""
    if not s: return ""
    try:
        import unicodedata
        s = unicodedata.normalize('NFKC', str(s))
        return s.encode('cp1252', errors='replace').decode('cp1252')
    except: return str(s)

def _safe(s):
    """Echappe &, <, > pour Paragraph ReportLab. Supprime le markdown LLM."""
    if not s: return ""
    import re
    s = str(s)
    s = re.sub(r'\*\*(.+?)\*\*', r'\1', s)
    s = re.sub(r'\*(.+?)\*', r'\1', s)
    s = re.sub(r'\*+', '', s)
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def rule(w=TABLE_W, thick=0.5, col=GREY_RULE, sb=4, sa=4):
    return HRFlowable(width=w, thickness=thick, color=col, spaceAfter=sa, spaceBefore=sb)

def section_title(text, num=""):
    prefix = f"{num}. " if num else ""
    return [rule(sb=6, sa=0), Paragraph(f"{prefix}{text}", S_SECTION), rule(sb=2, sa=6)]

def src(text):
    return Paragraph(f"Source : {text}", S_NOTE)

def tbl(data, cw, row_heights=None):
    """Table standard : header navy, alternance lignes."""
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

def _blank_buf(w=6.5, h=2.8):
    if _MPL:
        fig, ax = plt.subplots(figsize=(w, h))
        ax.text(0.5, 0.5, 'N/A', ha='center', va='center',
                fontsize=14, color='#888', transform=ax.transAxes)
        ax.axis('off')
        fig.patch.set_facecolor('white')
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        plt.close(fig); buf.seek(0)
        return buf
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
# FORMATAGE NUMERIQUE
# =============================================================================
def _fr(v, dp=1, suffix=""):
    if v is None: return "\u2014"
    try: return f"{float(v):,.{dp}f}".replace(",", " ").replace(".", ",") + suffix
    except: return "\u2014"

def _frpct(v, signed=False):
    if v is None: return "\u2014"
    try:
        fv = float(v)
        if abs(fv) > 2.0: fv /= 100.0
        s = f"{fv * 100:+.1f}" if signed else f"{fv * 100:.1f}"
        return s.replace(".", ",") + " %"
    except: return "\u2014"

def _frx(v):
    if v is None: return "\u2014"
    try: return f"{float(v):.1f}".replace(".", ",") + "x"
    except: return "\u2014"

def _frm(v, cur="$"):
    if v is None: return "\u2014"
    try:
        v = float(v)
        if abs(v) > 1_000_000_000: v = v / 1_000_000
        if cur == "EUR":
            sym_big, sym_small = "Md\u20ac", "M\u20ac"
        else:
            sym_big, sym_small = "Mds" + cur, "M" + cur
        if abs(v) >= 1000:
            return _fr(v / 1000, 1) + " " + sym_big
        return _fr(v, 0) + " " + sym_small
    except: return "\u2014"

def _rec_color(rec):
    r = str(rec or "").upper()
    if r == 'BUY':  return BUY_GREEN
    if r == 'SELL': return SELL_RED
    return HOLD_AMB

def _rec_label(rec):
    r = str(rec or "").upper()
    if r == 'BUY':  return "ACHAT"
    if r == 'SELL': return "VENTE"
    if r == 'HOLD': return "NEUTRE"
    return r or "\u2014"

def _hex_str(c):
    """Retourne la chaine hex sans # pour une couleur ReportLab."""
    try:
        h = c.hexval()
        return h[2:] if h.startswith('0x') else h
    except:
        return "1A1A1A"

# =============================================================================
# FILTRE LIGNES "--"
# =============================================================================
_DASH_VALUES = ("\u2014", "\u2013", "--", "—", "–", "", "None", "none")

def _row_has_data(r):
    """Retourne True si au moins col 1 ou col 2 est != dash/vide."""
    v1 = r[1] if not isinstance(r[1], Paragraph) else ""
    v2 = r[2] if not isinstance(r[2], Paragraph) else ""
    ok1 = str(v1).strip() not in _DASH_VALUES
    ok2 = str(v2).strip() not in _DASH_VALUES
    return ok1 or ok2

# =============================================================================
# TEXTES ANALYTIQUES COMPUTED (sans LLM)
# =============================================================================
def _profil_text(m_a, m_b, tkr_a, tkr_b):
    sec_a  = m_a.get("sector_a") or m_a.get("sector") or "N/A"
    mc_a   = _frm(m_a.get("market_cap"))
    mc_b   = _frm(m_b.get("market_cap"))
    dy_a   = _frpct(m_a.get("dividend_yield"))
    dy_b   = _frpct(m_b.get("dividend_yield"))
    beta_a = _fr(m_a.get("beta"), 2)
    beta_b = _fr(m_b.get("beta"), 2)
    return (
        f"{tkr_a} (Market Cap : {mc_a}) et {tkr_b} ({mc_b}) operent tous deux dans le "
        f"secteur {sec_a}. {tkr_a} offre un rendement du dividende de {dy_a} vs {dy_b} pour {tkr_b}. "
        f"Beta {tkr_a} : {beta_a}x vs {beta_b}x pour {tkr_b}, "
        f"refletant leur sensibilite respective au marche."
    )

def _bilan_text(m_a, m_b, tkr_a, tkr_b):
    nd_a = _frx(m_a.get("net_debt_ebitda"))
    nd_b = _frx(m_b.get("net_debt_ebitda"))
    cr_a = _frx(m_a.get("current_ratio"))
    cr_b = _frx(m_b.get("current_ratio"))
    ic_a = _frx(m_a.get("interest_coverage"))
    ic_b = _frx(m_b.get("interest_coverage"))
    return (
        f"Structure bilancielle : {tkr_a} affiche un ND/EBITDA de {nd_a} vs {nd_b} pour {tkr_b}. "
        f"Liquidite : Current Ratio {tkr_a} {cr_a} vs {cr_b}. "
        f"Couverture des interets : {tkr_a} {ic_a} vs {ic_b} pour {tkr_b} -- "
        f"les deux titres disposent d'une structure a surveiller sur horizon 12 mois."
    )

def _dcf_text(m_a, m_b, tkr_a, tkr_b):
    up_a   = m_a.get("upside_str") or "N/A"
    up_b   = m_b.get("upside_str") or "N/A"
    base_a = _fr(m_a.get("dcf_base"), 0)
    base_b = _fr(m_b.get("dcf_base"), 0)
    wacc_a = _frpct(m_a.get("wacc"))
    return (
        f"Le modele DCF (WACC {wacc_a}) retient une valeur intrinseque base de {base_a} pour {tkr_a} "
        f"(upside : {up_a}) et {base_b} pour {tkr_b} (upside : {up_b}). "
        f"La simulation Monte Carlo renforce la distribution autour du scenario base."
    )

def _risque_text(m_a, m_b, tkr_a, tkr_b):
    beta_a = _fr(m_a.get("beta"), 2)
    beta_b = _fr(m_b.get("beta"), 2)
    p1m_a  = _frpct(m_a.get("perf_1m"), True)
    p1m_b  = _frpct(m_b.get("perf_1m"), True)
    p3m_a  = _frpct(m_a.get("perf_3m"), True)
    p3m_b  = _frpct(m_b.get("perf_3m"), True)
    return (
        f"Profil de risque : beta {tkr_a} {beta_a}x vs {beta_b}x pour {tkr_b}. "
        f"Performance 1 mois : {p1m_a} vs {p1m_b}. Performance 3 mois : {p3m_a} vs {p3m_b}. "
        f"Le radar de risque ci-dessous synthetise levier, momentum, qualite, liquidite et croissance."
    )

# =============================================================================
# CHARTS
# =============================================================================
def _chart_margins(m_a, m_b, tkr_a, tkr_b) -> io.BytesIO:
    """Barres groupees : marges EBITDA / EBIT / Nette cote a cote."""
    if not _MPL:
        return _blank_buf(8, 3)
    try:
        def _pv(v):
            if v is None: return 0.0
            fv = float(v)
            return fv * 100 if abs(fv) <= 2.0 else fv
        labels  = ["Marge\nEBITDA", "Marge\nEBIT", "Marge\nNette"]
        vals_a  = [_pv(m_a.get("ebitda_margin_ltm")), _pv(m_a.get("ebit_margin")), _pv(m_a.get("net_margin_ltm"))]
        vals_b  = [_pv(m_b.get("ebitda_margin_ltm")), _pv(m_b.get("ebit_margin")), _pv(m_b.get("net_margin_ltm"))]
        x = np.arange(len(labels))
        width = 0.35
        fig, ax = plt.subplots(figsize=(7, 3.2))
        bars_a = ax.bar(x - width/2, vals_a, width, label=tkr_a, color='#2E5FA3', alpha=0.9)
        bars_b = ax.bar(x + width/2, vals_b, width, label=tkr_b, color='#2E8B57', alpha=0.9)
        for bar in list(bars_a) + list(bars_b):
            h = bar.get_height()
            if h != 0:
                ax.text(bar.get_x() + bar.get_width()/2., h + 0.5,
                        f"{h:.1f}%", ha='center', va='bottom', fontsize=7.5, color='#333')
        ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9)
        ax.set_ylabel("(%)", fontsize=9, color='#555')
        ax.legend(fontsize=9, frameon=False)
        for sp in ['top', 'right']: ax.spines[sp].set_visible(False)
        ax.spines['left'].set_color('#D0D5DD'); ax.spines['bottom'].set_color('#D0D5DD')
        ax.set_facecolor('white'); fig.patch.set_facecolor('white')
        ax.yaxis.grid(True, alpha=0.3, color='#D0D5DD'); ax.set_axisbelow(True)
        plt.tight_layout(pad=0.6)
        buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig); buf.seek(0); return buf
    except Exception as e:
        log.warning(f"[cmp_pdf] chart_margins error: {e}")
        return _blank_buf(8, 3)


def _chart_returns(m_a, m_b, tkr_a, tkr_b) -> io.BytesIO:
    """Barres groupees : ROIC / ROE / Rev CAGR 3y."""
    if not _MPL:
        return _blank_buf(8, 3)
    try:
        def _pct_val(v):
            if v is None: return 0.0
            fv = float(v)
            return fv * 100 if abs(fv) <= 2.0 else fv
        labels = ["ROIC", "ROE", "Rev CAGR 3y"]
        vals_a = [_pct_val(m_a.get("roic")), _pct_val(m_a.get("roe")), _pct_val(m_a.get("revenue_cagr_3y"))]
        vals_b = [_pct_val(m_b.get("roic")), _pct_val(m_b.get("roe")), _pct_val(m_b.get("revenue_cagr_3y"))]
        x = np.arange(len(labels)); width = 0.35
        fig, ax = plt.subplots(figsize=(7, 3.2))
        ax.bar(x - width/2, vals_a, width, label=tkr_a, color='#2E5FA3', alpha=0.9)
        ax.bar(x + width/2, vals_b, width, label=tkr_b, color='#2E8B57', alpha=0.9)
        ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9)
        ax.set_ylabel("(%)", fontsize=9, color='#555')
        ax.legend(fontsize=9, frameon=False)
        ax.axhline(0, color='#888', linewidth=0.7)
        for sp in ['top', 'right']: ax.spines[sp].set_visible(False)
        ax.spines['left'].set_color('#D0D5DD'); ax.spines['bottom'].set_color('#D0D5DD')
        ax.set_facecolor('white'); fig.patch.set_facecolor('white')
        ax.yaxis.grid(True, alpha=0.3, color='#D0D5DD'); ax.set_axisbelow(True)
        plt.tight_layout(pad=0.6)
        buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig); buf.seek(0); return buf
    except Exception as e:
        log.warning(f"[cmp_pdf] chart_returns error: {e}")
        return _blank_buf(8, 3)


def _chart_multiples(m_a, m_b, tkr_a, tkr_b) -> io.BytesIO:
    """Barres horizontales : P/E, EV/EBITDA, P/B, EV/Sales."""
    if not _MPL:
        return _blank_buf(8, 3.5)
    try:
        def _fv(v): return float(v or 0) or 0
        labels = ["P/E", "EV/EBITDA", "P/B", "EV/Sales"]
        vals_a = [_fv(m_a.get("pe_ratio")), _fv(m_a.get("ev_ebitda")), _fv(m_a.get("price_to_book")), _fv(m_a.get("ev_sales"))]
        vals_b = [_fv(m_b.get("pe_ratio")), _fv(m_b.get("ev_ebitda")), _fv(m_b.get("price_to_book")), _fv(m_b.get("ev_sales"))]
        y = np.arange(len(labels)); height = 0.35
        fig, ax = plt.subplots(figsize=(7, 3.5))
        ax.barh(y + height/2, vals_a, height, label=tkr_a, color='#2E5FA3', alpha=0.9)
        ax.barh(y - height/2, vals_b, height, label=tkr_b, color='#2E8B57', alpha=0.9)
        ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=9)
        ax.set_xlabel("(x)", fontsize=9, color='#555')
        ax.legend(fontsize=9, frameon=False)
        for sp in ['top', 'right']: ax.spines[sp].set_visible(False)
        ax.spines['left'].set_color('#D0D5DD'); ax.spines['bottom'].set_color('#D0D5DD')
        ax.set_facecolor('white'); fig.patch.set_facecolor('white')
        ax.xaxis.grid(True, alpha=0.3, color='#D0D5DD'); ax.set_axisbelow(True)
        plt.tight_layout(pad=0.6)
        buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig); buf.seek(0); return buf
    except Exception as e:
        log.warning(f"[cmp_pdf] chart_multiples error: {e}")
        return _blank_buf(8, 3.5)


def _chart_risk_radar(m_a, m_b, tkr_a, tkr_b) -> io.BytesIO:
    """Radar : 5 axes de risque."""
    if not _MPL:
        return _blank_buf(5, 4)
    try:
        categories = ["Levier", "Momentum", "Qualite", "Liquidite", "Croissance"]
        N = len(categories)
        angles = [n / float(N) * 2 * np.pi for n in range(N)]
        angles += angles[:1]

        def _norm(v, lo, hi):
            if v is None: return 3.0
            try:
                fv = float(v)
                if hi == lo: return 3.0
                return max(1.0, min(5.0, 1.0 + 4.0 * (fv - lo) / (hi - lo)))
            except: return 3.0

        def _vals(m):
            nd_ebitda = m.get("net_debt_ebitda") or 0.0
            mom_1m    = m.get("perf_1m") or 0.0
            pio       = m.get("piotroski_score") or 5
            current   = m.get("current_ratio") or 1.5
            rev_cagr  = m.get("revenue_cagr_3y") or 0.0
            levier    = _norm(float(nd_ebitda or 0), 5, 0)
            momentum  = _norm(float(mom_1m or 0) * 100, -20, 20)
            qualite   = _norm(float(pio or 0), 0, 9)
            liquidite = _norm(float(current or 0), 0.5, 3.0)
            croissance= _norm(float(rev_cagr or 0) * 100, -10, 30)
            return [levier, momentum, qualite, liquidite, croissance]

        vals_a = _vals(m_a) + [_vals(m_a)[0]]
        vals_b = _vals(m_b) + [_vals(m_b)[0]]

        fig, ax = plt.subplots(figsize=(4.5, 4), subplot_kw=dict(polar=True))
        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=8, color='#333')
        ax.set_ylim(0, 5)
        ax.set_yticks([1, 2, 3, 4, 5])
        ax.set_yticklabels(["1", "2", "3", "4", "5"], fontsize=6, color='#aaa')
        ax.plot(angles, vals_a, 'o-', color='#2E5FA3', linewidth=1.8, label=tkr_a)
        ax.fill(angles, vals_a, alpha=0.12, color='#2E5FA3')
        ax.plot(angles, vals_b, 's-', color='#2E8B57', linewidth=1.8, label=tkr_b)
        ax.fill(angles, vals_b, alpha=0.12, color='#2E8B57')
        ax.set_facecolor('white'); fig.patch.set_facecolor('white')
        ax.grid(color='#D0D5DD', linewidth=0.5)
        ax.legend(fontsize=8, loc='upper right', bbox_to_anchor=(1.35, 1.15), frameon=False)
        plt.tight_layout(pad=0.4)
        buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig); buf.seek(0); return buf
    except Exception as e:
        log.warning(f"[cmp_pdf] chart_risk_radar error: {e}")
        return _blank_buf(5, 4)


def _chart_finsight_scores(m_a, m_b, tkr_a, tkr_b) -> io.BytesIO:
    """Barres horizontales : FinSight Score comparatif."""
    if not _MPL:
        return _blank_buf(7, 2.5)
    try:
        sa = float(m_a.get("finsight_score") or 0)
        sb = float(m_b.get("finsight_score") or 0)
        fig, ax = plt.subplots(figsize=(6, 1.8))
        bars = ax.barh([1, 0], [sa, sb], color=['#2E5FA3', '#2E8B57'], height=0.45, alpha=0.9)
        for bar, val, lbl in zip(bars, [sa, sb], [tkr_a, tkr_b]):
            ax.text(val + 0.5, bar.get_y() + bar.get_height()/2.,
                    f"{val:.0f}/100", va='center', fontsize=9, color='#333', fontweight='bold')
        ax.set_yticks([0, 1])
        ax.set_yticklabels([tkr_b, tkr_a], fontsize=10)
        ax.set_xlim(0, 110)
        ax.set_xlabel("FinSight Score (/100)", fontsize=9, color='#555')
        for sp in ['top', 'right']: ax.spines[sp].set_visible(False)
        ax.spines['left'].set_color('#D0D5DD'); ax.spines['bottom'].set_color('#D0D5DD')
        ax.set_facecolor('white'); fig.patch.set_facecolor('white')
        ax.xaxis.grid(True, alpha=0.3, color='#D0D5DD'); ax.set_axisbelow(True)
        plt.tight_layout(pad=0.5)
        buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig); buf.seek(0); return buf
    except Exception as e:
        log.warning(f"[cmp_pdf] chart_finsight error: {e}")
        return _blank_buf(7, 2.5)


# =============================================================================
# COVER PAGE (canvas onFirstPage) -- style pdf_writer.py societe
# =============================================================================
def _cover_page(canvas, doc, tkr_a, tkr_b, name_a, name_b,
                rec_a, rec_b, date_str, m_a, m_b, synthesis):
    W, H = A4
    cx = W / 2

    # Fond blanc
    canvas.setFillColor(WHITE)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)

    # Bande navy top 18mm
    canvas.setFillColor(NAVY)
    canvas.rect(0, H - 18*mm, W, 18*mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawCentredString(cx, H - 8*mm, "FinSight IA")
    canvas.setFillColor(colors.HexColor('#90B4E8'))
    canvas.setFont("Helvetica", 7.5)
    canvas.drawCentredString(cx, H - 14*mm,
        _enc("Analyse Comparative -- Rapport d'investissement"))

    # Ligne separatrice sous la bande
    canvas.setStrokeColor(GREY_RULE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_L, H - 20*mm, W - MARGIN_R, H - 20*mm)

    # Titre principal
    canvas.setFillColor(NAVY)
    canvas.setFont("Helvetica-Bold", 26)
    canvas.drawCentredString(cx, H * 0.855, _enc("Analyse Comparative"))
    canvas.setFillColor(GREY_TEXT)
    canvas.setFont("Helvetica", 14)
    canvas.drawCentredString(cx, H * 0.825,
        _enc(f"{tkr_a}   \u00b7   vs   \u00b7   {tkr_b}"))

    # Ligne separatrice
    canvas.setStrokeColor(GREY_RULE)
    canvas.setLineWidth(0.4)
    canvas.line(MARGIN_L + 20*mm, H * 0.810, W - MARGIN_R - 20*mm, H * 0.810)

    # ------------------------------------------------------------------
    # DEUX BOXES SOCIETES (gauche A, droite B)
    # ------------------------------------------------------------------
    box_top    = H * 0.800
    box_bottom = H * 0.620
    box_h      = box_top - box_bottom
    half_w     = (W - MARGIN_L - MARGIN_R) / 2 - 3*mm
    box_ax     = MARGIN_L
    box_bx     = MARGIN_L + half_w + 6*mm

    # Box A fond + bordure gauche
    canvas.setFillColor(COLOR_A_PAL)
    canvas.roundRect(box_ax, box_bottom, half_w, box_h, 3, fill=1, stroke=0)
    canvas.setStrokeColor(COLOR_A)
    canvas.setLineWidth(3)
    canvas.line(box_ax, box_bottom, box_ax, box_top)

    # Box B fond + bordure gauche
    canvas.setFillColor(COLOR_B_PAL)
    canvas.roundRect(box_bx, box_bottom, half_w, box_h, 3, fill=1, stroke=0)
    canvas.setStrokeColor(COLOR_B)
    canvas.setLineWidth(3)
    canvas.line(box_bx, box_bottom, box_bx, box_top)

    canvas.setLineWidth(0.5)

    def _draw_company_box(bx, bw, m, tkr, name, rec, color_main, color_pal):
        inner_x = bx + 5*mm
        cx_box   = bx + bw / 2

        # Nom societe (12pt navy bold)
        canvas.setFillColor(NAVY)
        canvas.setFont("Helvetica-Bold", 11)
        _nm = (name or tkr)[:32]
        canvas.drawString(inner_x, box_top - 8*mm, _enc(_nm))

        # Ticker + secteur (9pt gris)
        sec = m.get("sector_a") or m.get("sector_b") or m.get("sector") or ""
        canvas.setFillColor(GREY_TEXT)
        canvas.setFont("Helvetica", 8.5)
        canvas.drawString(inner_x, box_top - 13.5*mm,
            _enc(f"{tkr}  \u00b7  {sec[:28]}"))

        # Badge recommandation
        rec_col = _rec_color(rec)
        badge_w = 30*mm
        badge_h = 10*mm
        badge_x = inner_x
        badge_y = box_top - 24*mm
        canvas.setFillColor(rec_col)
        canvas.roundRect(badge_x, badge_y, badge_w, badge_h, 2, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 8.5)
        canvas.drawCentredString(badge_x + badge_w/2, badge_y + 3.2*mm,
            _enc(_rec_label(rec)))

        # Box cible navy
        tgt = m.get("target_price") or ""
        up  = m.get("upside_str") or ""
        cible_txt = f"Cible: {tgt}  ({up})" if tgt else "Cible: N/A"
        cible_w = bw - badge_w - 8*mm
        cible_x = badge_x + badge_w + 3*mm
        canvas.setFillColor(NAVY)
        canvas.roundRect(cible_x, badge_y, cible_w, badge_h, 2, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.drawCentredString(cible_x + cible_w/2, badge_y + 3.2*mm, _enc(cible_txt))

        # Cours + FinSight Score
        price_str = str(m.get("price_str") or "\u2014")
        fs_score  = str(m.get("finsight_score") or "\u2014")
        canvas.setFillColor(GREY_TEXT)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(inner_x, box_top - 36*mm,
            _enc(f"Cours : {price_str}   |   FinSight : {fs_score}/100"))

    _draw_company_box(box_ax, half_w, m_a, tkr_a, name_a, rec_a, COLOR_A, COLOR_A_PAL)
    _draw_company_box(box_bx, half_w, m_b, tkr_b, name_b, rec_b, COLOR_B, COLOR_B_PAL)

    # Ligne separatrice apres les boxes
    canvas.setStrokeColor(GREY_RULE)
    canvas.setLineWidth(0.4)
    canvas.line(MARGIN_L, H * 0.612, W - MARGIN_R, H * 0.612)

    # ------------------------------------------------------------------
    # BOX VERDICT (fond navy clair)
    # ------------------------------------------------------------------
    winner = m_a.get("winner") or tkr_a
    verdict_raw = synthesis.get("verdict_text") or ""
    verdict_excerpt = verdict_raw[:120]
    if len(verdict_raw) > 120:
        if ' ' in verdict_excerpt:
            verdict_excerpt = verdict_excerpt[:verdict_excerpt.rfind(' ')] + '...'
        else:
            verdict_excerpt += '...'

    verd_box_x = MARGIN_L
    verd_box_w = W - MARGIN_L - MARGIN_R
    verd_box_y = H * 0.550
    verd_box_h = 18*mm
    canvas.setFillColor(colors.HexColor('#EEF3FA'))
    canvas.roundRect(verd_box_x, verd_box_y, verd_box_w, verd_box_h, 3, fill=1, stroke=0)
    canvas.setStrokeColor(NAVY_LIGHT)
    canvas.setLineWidth(0.4)
    canvas.roundRect(verd_box_x, verd_box_y, verd_box_w, verd_box_h, 3, fill=0, stroke=1)

    canvas.setFillColor(NAVY)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawCentredString(cx, verd_box_y + verd_box_h - 6*mm,
        _enc(f"Choix prefere : {winner}"))
    canvas.setFillColor(GREY_TEXT)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawCentredString(cx, verd_box_y + 4.5*mm, _enc(verdict_excerpt))

    # Source / date
    canvas.setFillColor(GREY_TEXT)
    canvas.setFont("Helvetica", 7)
    canvas.drawCentredString(cx, H * 0.520,
        _enc(f"Donnees : yfinance  \u00b7  FMP  \u00b7  Finnhub   |   {date_str}   |   Horizon : 12 mois"))

    # ------------------------------------------------------------------
    # METRIQUES COMPARATIVES (2 rangees de 4 boites)
    # ------------------------------------------------------------------
    canvas.setStrokeColor(GREY_RULE)
    canvas.setLineWidth(0.4)
    canvas.line(MARGIN_L, H * 0.507, W - MARGIN_R, H * 0.507)

    canvas.setFillColor(NAVY)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(MARGIN_L, H * 0.497, _enc("Metriques comparatives cles"))

    box_w2 = (W - MARGIN_L - MARGIN_R - 3 * 2*mm) / 4
    box_h2 = 26*mm

    def _draw_metric_box(bx, by, label, va, vb, bw, bh):
        canvas.setFillColor(GREY_LIGHT)
        canvas.roundRect(bx, by, bw, bh, 2, fill=1, stroke=0)
        canvas.setStrokeColor(GREY_MED)
        canvas.setLineWidth(0.3)
        canvas.roundRect(bx, by, bw, bh, 2, fill=0, stroke=1)
        # Label
        canvas.setFillColor(GREY_TEXT)
        canvas.setFont("Helvetica", 6.5)
        canvas.drawCentredString(bx + bw / 2, by + bh - 4.5*mm, _enc(label))
        # Separator mini
        canvas.setStrokeColor(GREY_RULE)
        canvas.setLineWidth(0.3)
        canvas.line(bx + 2*mm, by + bh - 7*mm, bx + bw - 2*mm, by + bh - 7*mm)
        # Value A
        canvas.setFillColor(COLOR_A)
        canvas.setFont("Helvetica-Bold", 9.5)
        canvas.drawCentredString(bx + bw * 0.28, by + bh * 0.38, _enc(va))
        # vs
        canvas.setFillColor(GREY_TEXT)
        canvas.setFont("Helvetica", 7)
        canvas.drawCentredString(bx + bw * 0.50, by + bh * 0.38, "vs")
        # Value B
        canvas.setFillColor(COLOR_B)
        canvas.setFont("Helvetica-Bold", 9.5)
        canvas.drawCentredString(bx + bw * 0.72, by + bh * 0.38, _enc(vb))
        # Ticker labels
        canvas.setFillColor(GREY_TEXT)
        canvas.setFont("Helvetica", 5.5)
        canvas.drawCentredString(bx + bw * 0.28, by + 2.5*mm, _enc(tkr_a))
        canvas.drawCentredString(bx + bw * 0.72, by + 2.5*mm, _enc(tkr_b))

    # Row 1 : P/E, EV/EBITDA, Marge EBITDA, FinSight Score
    row1_top = H * 0.486
    row1_bottom = row1_top - box_h2
    metrics_row1 = [
        ("P/E (x)",      _frx(m_a.get("pe_ratio")),           _frx(m_b.get("pe_ratio"))),
        ("EV/EBITDA (x)",_frx(m_a.get("ev_ebitda")),          _frx(m_b.get("ev_ebitda"))),
        ("Marge EBITDA", _frpct(m_a.get("ebitda_margin_ltm")),_frpct(m_b.get("ebitda_margin_ltm"))),
        ("FinSight /100", str(m_a.get("finsight_score") or "\u2014") + "/100",
                          str(m_b.get("finsight_score") or "\u2014") + "/100"),
    ]
    for i, (lbl, va, vb) in enumerate(metrics_row1):
        bx = MARGIN_L + i * (box_w2 + 2*mm)
        _draw_metric_box(bx, row1_bottom, lbl, va, vb, box_w2, box_h2)

    # Row 2 : ROIC, Piotroski, ND/EBITDA, Beta
    row2_top = row1_bottom - 3*mm
    row2_bottom = row2_top - box_h2
    metrics_row2 = [
        ("ROIC (%)",      _frpct(m_a.get("roic")),            _frpct(m_b.get("roic"))),
        ("Piotroski /9",  str(m_a.get("piotroski_score") or "\u2014"),
                          str(m_b.get("piotroski_score") or "\u2014")),
        ("ND/EBITDA (x)", _frx(m_a.get("net_debt_ebitda")),   _frx(m_b.get("net_debt_ebitda"))),
        ("Beta",          _fr(m_a.get("beta"), 2),             _fr(m_b.get("beta"), 2)),
    ]
    for i, (lbl, va, vb) in enumerate(metrics_row2):
        bx = MARGIN_L + i * (box_w2 + 2*mm)
        _draw_metric_box(bx, row2_bottom, lbl, va, vb, box_w2, box_h2)

    # ------------------------------------------------------------------
    # BOX CONTEXTE (fond gris clair, texte synthese)
    # ------------------------------------------------------------------
    ctx_top = row2_bottom - 3*mm
    ctx_h   = 22*mm
    ctx_bottom = ctx_top - ctx_h
    canvas.setFillColor(GREY_LIGHT)
    canvas.roundRect(MARGIN_L, ctx_bottom, W - MARGIN_L - MARGIN_R, ctx_h, 2, fill=1, stroke=0)
    canvas.setStrokeColor(GREY_MED)
    canvas.setLineWidth(0.3)
    canvas.roundRect(MARGIN_L, ctx_bottom, W - MARGIN_L - MARGIN_R, ctx_h, 2, fill=0, stroke=1)

    # Accent bleu gauche
    canvas.setStrokeColor(NAVY_LIGHT)
    canvas.setLineWidth(2.5)
    canvas.line(MARGIN_L, ctx_bottom, MARGIN_L, ctx_top)

    canvas.setFillColor(NAVY)
    canvas.setFont("Helvetica-Bold", 7.5)
    canvas.drawString(MARGIN_L + 5*mm, ctx_top - 5*mm, _enc("Methodologie"))
    canvas.setFillColor(GREY_TEXT)
    canvas.setFont("Helvetica", 6.5)
    meth_text = (
        "Pipeline algorithmique : collecte de donnees (yfinance, Finnhub), valorisation "
        "quantitative (WACC, DCF, Piotroski, Beneish), synthese LLM (llama-3.3-70b), "
        "QA contradictoire. FinSight Score = agregat 0-100 couvrant rentabilite, "
        "valorisation, qualite bilancielle et momentum. Horizon d'analyse : 12 mois."
    )
    # Wrap manual en 2 lignes
    line1 = meth_text[:100]
    if ' ' in line1[80:]:
        cut = 80 + line1[80:].index(' ')
        line1 = meth_text[:cut]
        line2 = meth_text[cut+1:cut+1+105]
        line3 = meth_text[cut+1+105:cut+1+105+105]
    else:
        line2 = meth_text[100:205]
        line3 = meth_text[205:]
    canvas.drawString(MARGIN_L + 5*mm, ctx_top - 10*mm, _enc(line1))
    canvas.drawString(MARGIN_L + 5*mm, ctx_top - 14.5*mm, _enc(line2))
    if line3.strip():
        canvas.drawString(MARGIN_L + 5*mm, ctx_top - 19*mm, _enc(line3.strip()))

    # Ligne separatrice avant footer
    canvas.setStrokeColor(GREY_RULE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_L, 20*mm, W - MARGIN_R, 20*mm)

    # Footer navy bas 18mm
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, W, 18*mm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor('#90B4E8'))
    canvas.setFont("Helvetica", 6.5)
    canvas.drawCentredString(cx, 11*mm,
        _enc("CONFIDENTIEL \u2014 Usage restreint"))
    canvas.drawCentredString(cx, 6*mm,
        _enc("FinSight IA v1.2 \u2014 Ne constitue pas un conseil en investissement"))

    canvas.restoreState()


# =============================================================================
# HEADER / FOOTER PAGES DE CONTENU
# =============================================================================
def _header_footer(canvas, doc):
    W, H = A4
    canvas.saveState()
    # Header navy
    canvas.setFillColor(NAVY)
    canvas.rect(0, H - 12*mm, W, 12*mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(MARGIN_L, H - 8*mm,
        _enc(getattr(doc, '_cmp_header', 'FinSight IA')))
    canvas.setFont("Helvetica", 7.5)
    canvas.drawRightString(W - MARGIN_R, H - 8*mm,
        _enc(f"Confidentiel  \u00b7  Page {doc.page}"))
    # Footer
    canvas.setFillColor(GREY_RULE)
    canvas.rect(0, 0, W, 9*mm, fill=1, stroke=0)
    canvas.setFillColor(GREY_TEXT)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(MARGIN_L, 3.5*mm,
        _enc("FinSight IA  \u00b7  Analyse algorithmique, non contractuelle"))
    canvas.drawRightString(W - MARGIN_R, 3.5*mm,
        _enc(f"Page {doc.page}"))
    canvas.restoreState()


# =============================================================================
# HELPERS TABLEAU
# =============================================================================
def _make_tbl_3col(header, raw_rows, cw=None):
    """Construit un tableau 3 colonnes en filtrant les lignes '--'."""
    if cw is None:
        cw = [70*mm, 50*mm, 50*mm]
    filtered = [r for r in raw_rows if _row_has_data(r)]
    if not filtered:
        return None
    data = [header]
    for r in filtered:
        row = []
        for i, cell in enumerate(r):
            if isinstance(cell, Paragraph):
                row.append(cell)
            elif i == 0:
                row.append(Paragraph(_safe(str(cell)), S_TD_B))
            else:
                row.append(Paragraph(_safe(str(cell)), S_TD_C))
        data.append(row)
    return tbl(data, cw)


# =============================================================================
# SECTIONS PDF
# =============================================================================

def _section_exec_summary(story, m_a, m_b, synthesis, tkr_a, tkr_b):
    story += section_title("Executive Summary", "1")

    exec_text = synthesis.get("exec_summary") or ""
    if exec_text:
        story.append(Paragraph(_safe(_enc(exec_text)), S_BODY))
        story.append(Spacer(1, 4*mm))

    # Tableau KPIs cles cote a cote
    rec_a  = m_a.get("recommendation") or "HOLD"
    rec_b  = m_b.get("recommendation") or "HOLD"
    winner = m_a.get("winner") or tkr_a

    def _rec_par(rec):
        col = _rec_color(rec)
        return Paragraph(f"<b>{_safe(_enc(_rec_label(rec)))}</b>",
                         _s(f'rec{id(rec)}', size=8, leading=11, color=col, bold=True, align=TA_CENTER))

    header = [
        Paragraph("<b>Indicateur</b>", S_TH_L),
        Paragraph(f"<b>{_enc(tkr_a)}</b>", S_TH_C),
        Paragraph(f"<b>{_enc(tkr_b)}</b>", S_TH_C),
    ]
    raw_rows = [
        ["Cours",         str(m_a.get("price_str") or "\u2014"), str(m_b.get("price_str") or "\u2014")],
        ["Market Cap",    _frm(m_a.get("market_cap")),           _frm(m_b.get("market_cap"))],
        ["EV",            _frm(m_a.get("enterprise_value")),     _frm(m_b.get("enterprise_value"))],
        ["P/E (NTM)",     _frx(m_a.get("pe_ratio")),             _frx(m_b.get("pe_ratio"))],
        ["EV/EBITDA",     _frx(m_a.get("ev_ebitda")),            _frx(m_b.get("ev_ebitda"))],
        ["Marge EBITDA",  _frpct(m_a.get("ebitda_margin_ltm")),  _frpct(m_b.get("ebitda_margin_ltm"))],
        ["ROIC",          _frpct(m_a.get("roic")),               _frpct(m_b.get("roic"))],
        ["FinSight Score",str(m_a.get("finsight_score") or "\u2014") + "/100",
                          str(m_b.get("finsight_score") or "\u2014") + "/100"],
        ["Recommandation",_rec_par(rec_a),                       _rec_par(rec_b)],
    ]
    t = _make_tbl_3col(header, raw_rows)
    if t:
        story.append(t)

    story.append(Spacer(1, 4*mm))

    # Graphique FinSight Scores
    buf = _chart_finsight_scores(m_a, m_b, tkr_a, tkr_b)
    img = Image(buf, width=TABLE_W * 0.65, height=38*mm)
    story.append(img)
    story.append(Spacer(1, 3*mm))

    # Verdict excerpt
    wc_hex = _hex_str(BUY_GREEN if winner == tkr_a else COLOR_B)
    story.append(Paragraph(
        f"<b>Titre prefere : <font color='#{wc_hex}'>{_enc(winner)}</font></b>"
        f"  \u2014  {_safe(_enc((synthesis.get('verdict_text') or '')[:200]))}",
        _s('verd', size=9, leading=13, color=BLACK, sb=3, sa=2)
    ))
    story.append(Spacer(1, 3*mm))
    story.append(src("FinSight IA / yfinance / Finnhub"))


def _section_profil_pl(story, m_a, m_b, synthesis, tkr_a, tkr_b):
    story.append(PageBreak())
    story += section_title("Profil & Compte de Resultat", "2")

    # Texte computed Profil
    story.append(Paragraph(_safe(_enc(_profil_text(m_a, m_b, tkr_a, tkr_b))), S_BODY))
    story.append(Spacer(1, 3*mm))

    header = [
        Paragraph("<b>Profil</b>", S_TH_L),
        Paragraph(f"<b>{_enc(tkr_a)}</b>", S_TH_C),
        Paragraph(f"<b>{_enc(tkr_b)}</b>", S_TH_C),
    ]
    raw_rows = [
        ["Societe",    str(m_a.get("company_name_a") or tkr_a),  str(m_b.get("company_name_b") or tkr_b)],
        ["Secteur",    str(m_a.get("sector_a") or "\u2014"),      str(m_b.get("sector_b") or "\u2014")],
        ["Industrie",  str(m_a.get("industry_a") or "\u2014"),    str(m_b.get("industry_b") or "\u2014")],
        ["Pays",       str(m_a.get("country_a") or "\u2014"),     str(m_b.get("country_b") or "\u2014")],
        ["Devises",    str(m_a.get("currency_a") or "USD"),       str(m_b.get("currency_b") or "USD")],
        ["Employes",   _fr(m_a.get("employees_a"), 0),           _fr(m_b.get("employees_b"), 0)],
        ["Market Cap", _frm(m_a.get("market_cap")),              _frm(m_b.get("market_cap"))],
        ["Beta",       _fr(m_a.get("beta"), 2),                  _fr(m_b.get("beta"), 2)],
        ["Div. Yield", _frpct(m_a.get("dividend_yield")),        _frpct(m_b.get("dividend_yield"))],
    ]
    t = _make_tbl_3col(header, raw_rows)
    if t:
        story.append(t)
    story.append(Spacer(1, 4*mm))

    # P&L LTM
    if synthesis.get("financial_text"):
        story.append(Paragraph(_safe(_enc(synthesis["financial_text"])), S_BODY))
        story.append(Spacer(1, 3*mm))

    hdr_pl = [
        Paragraph("<b>P&amp;L LTM</b>", S_TH_L),
        Paragraph(f"<b>{_enc(tkr_a)}</b>", S_TH_C),
        Paragraph(f"<b>{_enc(tkr_b)}</b>", S_TH_C),
    ]
    raw_pl = [
        ["Chiffre d'affaires", _frm(m_a.get("revenue_ltm")),      _frm(m_b.get("revenue_ltm"))],
        ["EBITDA",             _frm(m_a.get("ebitda_ltm")),        _frm(m_b.get("ebitda_ltm"))],
        ["Marge EBITDA",       _frpct(m_a.get("ebitda_margin_ltm")), _frpct(m_b.get("ebitda_margin_ltm"))],
        ["EBIT",               _frm(m_a.get("ebit_ltm")),          _frm(m_b.get("ebit_ltm"))],
        ["Marge EBIT",         _frpct(m_a.get("ebit_margin")),     _frpct(m_b.get("ebit_margin"))],
        ["Resultat Net",       _frm(m_a.get("net_income_ltm")),    _frm(m_b.get("net_income_ltm"))],
        ["Marge Nette",        _frpct(m_a.get("net_margin_ltm")),  _frpct(m_b.get("net_margin_ltm"))],
        ["Rev. CAGR 3y",       _frpct(m_a.get("revenue_cagr_3y")), _frpct(m_b.get("revenue_cagr_3y"))],
        ["FCF",                _frm(m_a.get("free_cash_flow")),    _frm(m_b.get("free_cash_flow"))],
    ]
    t_pl = _make_tbl_3col(hdr_pl, raw_pl)
    if t_pl:
        story.append(t_pl)
    story.append(Spacer(1, 3*mm))

    # Graphique marges
    buf = _chart_margins(m_a, m_b, tkr_a, tkr_b)
    img = Image(buf, width=TABLE_W, height=65*mm)
    story.append(img)
    story.append(Spacer(1, 2*mm))
    story.append(src("FinSight IA / yfinance"))


def _section_rentabilite_bilan(story, m_a, m_b, tkr_a, tkr_b):
    story.append(PageBreak())
    story += section_title("Rentabilite & Bilan", "3")

    # Tableau rentabilite
    hdr_r = [
        Paragraph("<b>Rentabilite</b>", S_TH_L),
        Paragraph(f"<b>{_enc(tkr_a)}</b>", S_TH_C),
        Paragraph(f"<b>{_enc(tkr_b)}</b>", S_TH_C),
    ]
    raw_r = [
        ["ROIC",           _frpct(m_a.get("roic")),             _frpct(m_b.get("roic"))],
        ["ROE",            _frpct(m_a.get("roe")),              _frpct(m_b.get("roe"))],
        ["ROCE",           _frpct(m_a.get("roce")),             _frpct(m_b.get("roce"))],
        ["Rev. CAGR 3y",   _frpct(m_a.get("revenue_cagr_3y")), _frpct(m_b.get("revenue_cagr_3y"))],
        ["EBITDA CAGR 3y", _frpct(m_a.get("ebitda_cagr_3y")),  _frpct(m_b.get("ebitda_cagr_3y"))],
        ["FCF Yield",      _frpct(m_a.get("fcf_yield")),        _frpct(m_b.get("fcf_yield"))],
        ["EPS Croissance",  _frpct(m_a.get("eps_growth")),      _frpct(m_b.get("eps_growth"))],
    ]
    t_r = _make_tbl_3col(hdr_r, raw_r)
    if t_r:
        story.append(t_r)
    story.append(Spacer(1, 3*mm))

    buf = _chart_returns(m_a, m_b, tkr_a, tkr_b)
    img = Image(buf, width=TABLE_W, height=65*mm)
    story.append(img)
    story.append(Spacer(1, 3*mm))

    # Bilan (avec CondPageBreak)
    story.append(CondPageBreak(80*mm))
    story.append(Paragraph(_safe(_enc(_bilan_text(m_a, m_b, tkr_a, tkr_b))), S_BODY))
    story.append(Spacer(1, 3*mm))

    hdr_b = [
        Paragraph("<b>Bilan</b>", S_TH_L),
        Paragraph(f"<b>{_enc(tkr_a)}</b>", S_TH_C),
        Paragraph(f"<b>{_enc(tkr_b)}</b>", S_TH_C),
    ]
    raw_b = [
        ["Tresorerie",       _frm(m_a.get("cash")),              _frm(m_b.get("cash"))],
        ["Dette Totale",     _frm(m_a.get("total_debt")),        _frm(m_b.get("total_debt"))],
        ["Dette Nette",      _frm(m_a.get("net_debt")),          _frm(m_b.get("net_debt"))],
        ["ND / EBITDA",      _frx(m_a.get("net_debt_ebitda")),   _frx(m_b.get("net_debt_ebitda"))],
        ["Gearing",          _frx(m_a.get("gearing")),           _frx(m_b.get("gearing"))],
        ["Current Ratio",    _frx(m_a.get("current_ratio")),     _frx(m_b.get("current_ratio"))],
        ["Interest Coverage",_frx(m_a.get("interest_coverage")), _frx(m_b.get("interest_coverage"))],
        ["Fonds Propres",    _frm(m_a.get("equity")),            _frm(m_b.get("equity"))],
    ]
    t_b = _make_tbl_3col(hdr_b, raw_b)
    if t_b:
        story.append(t_b)
    story.append(Spacer(1, 2*mm))
    story.append(src("FinSight IA / yfinance"))


def _section_valorisation(story, m_a, m_b, synthesis, tkr_a, tkr_b):
    story.append(PageBreak())
    story += section_title("Valorisation", "4")

    if synthesis.get("valuation_text"):
        story.append(Paragraph(_safe(_enc(synthesis["valuation_text"])), S_BODY))
        story.append(Spacer(1, 3*mm))

    hdr_v = [
        Paragraph("<b>Multiple</b>", S_TH_L),
        Paragraph(f"<b>{_enc(tkr_a)}</b>", S_TH_C),
        Paragraph(f"<b>{_enc(tkr_b)}</b>", S_TH_C),
    ]
    raw_v = [
        ["P/E",       _frx(m_a.get("pe_ratio")),      _frx(m_b.get("pe_ratio"))],
        ["EV/EBITDA", _frx(m_a.get("ev_ebitda")),     _frx(m_b.get("ev_ebitda"))],
        ["EV/EBIT",   _frx(m_a.get("ev_ebit")),       _frx(m_b.get("ev_ebit"))],
        ["EV/Sales",  _frx(m_a.get("ev_sales")),      _frx(m_b.get("ev_sales"))],
        ["P/B",       _frx(m_a.get("price_to_book")), _frx(m_b.get("price_to_book"))],
        ["P/FCF",     _frx(m_a.get("p_fcf")),         _frx(m_b.get("p_fcf"))],
        ["Cible 12m", str(m_a.get("target_price") or "\u2014"), str(m_b.get("target_price") or "\u2014")],
        ["Upside",    str(m_a.get("upside_str") or "\u2014"),   str(m_b.get("upside_str") or "\u2014")],
    ]
    t_v = _make_tbl_3col(hdr_v, raw_v)
    if t_v:
        story.append(t_v)
    story.append(Spacer(1, 3*mm))

    buf = _chart_multiples(m_a, m_b, tkr_a, tkr_b)
    img = Image(buf, width=TABLE_W, height=70*mm)
    story.append(img)
    story.append(Spacer(1, 3*mm))

    # DCF (avec CondPageBreak)
    story.append(CondPageBreak(60*mm))
    story.append(Paragraph(_safe(_enc(_dcf_text(m_a, m_b, tkr_a, tkr_b))), S_BODY))
    story.append(Spacer(1, 3*mm))

    hdr_d = [
        Paragraph("<b>Hypothese DCF</b>", S_TH_L),
        Paragraph(f"<b>{_enc(tkr_a)}</b>", S_TH_C),
        Paragraph(f"<b>{_enc(tkr_b)}</b>", S_TH_C),
    ]
    raw_d = [
        ["WACC",                  _frpct(m_a.get("wacc")),          _frpct(m_b.get("wacc"))],
        ["Croissance LT",         _frpct(m_a.get("terminal_growth")), _frpct(m_b.get("terminal_growth"))],
        ["Valeur intr. Bear",     _fr(m_a.get("dcf_bear"), 1),      _fr(m_b.get("dcf_bear"), 1)],
        ["Valeur intr. Base",     _fr(m_a.get("dcf_base"), 1),      _fr(m_b.get("dcf_base"), 1)],
        ["Valeur intr. Bull",     _fr(m_a.get("dcf_bull"), 1),      _fr(m_b.get("dcf_bull"), 1)],
        ["Cours actuel",          str(m_a.get("price_str") or "\u2014"), str(m_b.get("price_str") or "\u2014")],
        ["Upside / Base",         str(m_a.get("upside_str") or "\u2014"), str(m_b.get("upside_str") or "\u2014")],
    ]
    t_d = _make_tbl_3col(hdr_d, raw_d, cw=[80*mm, 45*mm, 45*mm])
    if t_d:
        story.append(t_d)
    story.append(Spacer(1, 2*mm))
    story.append(src("FinSight IA / yfinance"))


def _section_qualite_risque(story, m_a, m_b, synthesis, tkr_a, tkr_b):
    story.append(PageBreak())
    story += section_title("Qualite & Risque", "5")

    if synthesis.get("quality_text"):
        story.append(Paragraph(_safe(_enc(synthesis["quality_text"])), S_BODY))
        story.append(Spacer(1, 3*mm))

    # Tableau qualite scores
    def _pio_style(v):
        if v is None: return S_TD_C
        try:
            fv = int(float(v))
            if fv >= 7: return S_TD_G
            if fv <= 3: return S_TD_R
            return S_TD_A
        except: return S_TD_C

    def _alt_style(v):
        if v is None: return S_TD_C
        try:
            fv = float(v)
            if fv > 3:    return S_TD_G
            if fv < 1.81: return S_TD_R
            return S_TD_A
        except: return S_TD_C

    pio_a = m_a.get("piotroski_score"); pio_b = m_b.get("piotroski_score")
    ben_a = m_a.get("beneish_score");   ben_b = m_b.get("beneish_score")
    alt_a = m_a.get("altman_z");        alt_b = m_b.get("altman_z")
    fs_a  = m_a.get("finsight_score");  fs_b  = m_b.get("finsight_score")

    hdr_q = [
        Paragraph("<b>Score Qualite</b>", S_TH_L),
        Paragraph(f"<b>{_enc(tkr_a)}</b>", S_TH_C),
        Paragraph(f"<b>{_enc(tkr_b)}</b>", S_TH_C),
    ]
    qual_rows = [
        [Paragraph("<b>Piotroski F-Score (/9)</b>", S_TD_B),
         Paragraph(_safe(_enc(str(pio_a or "\u2014"))), _pio_style(pio_a)),
         Paragraph(_safe(_enc(str(pio_b or "\u2014"))), _pio_style(pio_b))],
        [Paragraph("<b>Beneish M-Score</b>", S_TD_B),
         Paragraph(_safe(_enc(_fr(ben_a, 2))), S_TD_C),
         Paragraph(_safe(_enc(_fr(ben_b, 2))), S_TD_C)],
        [Paragraph("<b>Altman Z-Score</b>", S_TD_B),
         Paragraph(_safe(_enc(_fr(alt_a, 2))), _alt_style(alt_a)),
         Paragraph(_safe(_enc(_fr(alt_b, 2))), _alt_style(alt_b))],
        [Paragraph("<b>FinSight Score (/100)</b>", S_TD_B),
         Paragraph(_safe(_enc(str(fs_a or "\u2014"))), S_TD_BC),
         Paragraph(_safe(_enc(str(fs_b or "\u2014"))), S_TD_BC)],
    ]
    t_q = Table([hdr_q] + qual_rows, colWidths=[70*mm, 50*mm, 50*mm])
    t_q.setStyle(TableStyle([
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
    story.append(t_q)
    story.append(Spacer(1, 3*mm))

    # Barres FinSight Score
    buf = _chart_finsight_scores(m_a, m_b, tkr_a, tkr_b)
    img = Image(buf, width=TABLE_W * 0.65, height=38*mm)
    story.append(img)
    story.append(Spacer(1, 3*mm))

    # Profil de risque (CondPageBreak)
    story.append(CondPageBreak(100*mm))
    story.append(Paragraph(_safe(_enc(_risque_text(m_a, m_b, tkr_a, tkr_b))), S_BODY))
    story.append(Spacer(1, 3*mm))

    hdr_ri = [
        Paragraph("<b>Risque</b>", S_TH_L),
        Paragraph(f"<b>{_enc(tkr_a)}</b>", S_TH_C),
        Paragraph(f"<b>{_enc(tkr_b)}</b>", S_TH_C),
    ]
    raw_ri = [
        ["Beta",             _fr(m_a.get("beta"), 2),           _fr(m_b.get("beta"), 2)],
        ["Volatilite 52w",   _frpct(m_a.get("volatility_52w")), _frpct(m_b.get("volatility_52w"))],
        ["Perf. 1 mois",     _frpct(m_a.get("perf_1m"), True),  _frpct(m_b.get("perf_1m"), True)],
        ["Perf. 3 mois",     _frpct(m_a.get("perf_3m"), True),  _frpct(m_b.get("perf_3m"), True)],
        ["Perf. 12 mois",    _frpct(m_a.get("perf_12m"), True), _frpct(m_b.get("perf_12m"), True)],
        ["RSI (14j)",        _fr(m_a.get("rsi"), 1),            _fr(m_b.get("rsi"), 1)],
        ["ND / EBITDA",      _frx(m_a.get("net_debt_ebitda")),  _frx(m_b.get("net_debt_ebitda"))],
        ["Sentiment",        str(m_a.get("sentiment_label") or "\u2014"),
                             str(m_b.get("sentiment_label") or "\u2014")],
    ]
    t_ri = _make_tbl_3col(hdr_ri, raw_ri)
    if t_ri:
        story.append(t_ri)
    story.append(Spacer(1, 3*mm))

    # Radar chart
    buf_r = _chart_risk_radar(m_a, m_b, tkr_a, tkr_b)
    img_r = Image(buf_r, width=95*mm, height=80*mm)
    story.append(img_r)
    story.append(Spacer(1, 2*mm))
    story.append(src("FinSight IA / yfinance"))


def _section_verdict(story, m_a, m_b, synthesis, tkr_a, tkr_b):
    story.append(PageBreak())
    story += section_title("Verdict & Theses", "6")

    winner = m_a.get("winner") or tkr_a

    # Verdict LLM
    if synthesis.get("verdict_text"):
        story.append(Paragraph(
            f"<b>Verdict Analytique :</b>  {_safe(_enc(synthesis['verdict_text']))}",
            _s('verd2', size=9, leading=13, color=BLACK, sb=2, sa=4)
        ))
        story.append(Spacer(1, 3*mm))

    # Tableau theses bull/bear cote a cote
    story.append(Paragraph("<b>Theses d'investissement</b>", S_SUBSECTION))
    story.append(Spacer(1, 2*mm))

    def _thesis_cell(text, is_bull):
        col    = BUY_GREEN if is_bull else SELL_RED
        prefix = "\u25b2 " if is_bull else "\u25bc "
        _txt   = _safe(_enc(text or "\u2014"))
        return Paragraph(
            f"<font color='#{_hex_str(col)}'><b>{prefix}</b></font>{_txt}",
            _s(f'th{id(text)}', size=8, leading=12, color=BLACK, sb=2, sa=2)
        )

    hdr_th = [
        Paragraph(f"<b>{_enc(tkr_a)}</b>",
            _s('tha', size=8.5, leading=11, color=WHITE, bold=True, align=TA_CENTER)),
        Paragraph(f"<b>{_enc(tkr_b)}</b>",
            _s('thb', size=8.5, leading=11, color=WHITE, bold=True, align=TA_CENTER)),
    ]
    bull_row = [_thesis_cell(synthesis.get("bull_a"), True),  _thesis_cell(synthesis.get("bull_b"), True)]
    bear_row = [_thesis_cell(synthesis.get("bear_a"), False), _thesis_cell(synthesis.get("bear_b"), False)]

    t_th = Table([hdr_th, bull_row, bear_row], colWidths=[85*mm, 85*mm])
    t_th.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), NAVY),
        ('BACKGROUND',    (0, 1), (-1, 1), colors.HexColor('#EAF4EF')),
        ('BACKGROUND',    (0, 2), (-1, 2), colors.HexColor('#FAF0EF')),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('GRID',          (0, 0), (-1, -1), 0.3, GREY_MED),
        ('LINEBEFORE',    (1, 0), (1, -1),  0.8, GREY_RULE),
    ]))
    story.append(t_th)
    story.append(Spacer(1, 4*mm))

    # Scorecard comparative
    story.append(Paragraph("<b>Scorecard comparative</b>", S_SUBSECTION))
    story.append(Spacer(1, 2*mm))

    def _score_row(label, val_a, val_b, higher_better=True):
        fa = val_a if val_a is not None else 0
        fb = val_b if val_b is not None else 0
        try: fa = float(fa)
        except: fa = 0.0
        try: fb = float(fb)
        except: fb = 0.0
        if higher_better:
            col_a = BUY_GREEN if fa >= fb else GREY_TEXT
            col_b = BUY_GREEN if fb > fa  else GREY_TEXT
            bold_a = fa >= fb
            bold_b = fb > fa
        else:
            col_a = BUY_GREEN if fa <= fb else GREY_TEXT
            col_b = BUY_GREEN if fb < fa  else GREY_TEXT
            bold_a = fa <= fb
            bold_b = fb < fa
        s_a = _s(f'sca{id(label)}', size=8, leading=11, color=col_a, bold=bold_a, align=TA_CENTER)
        s_b = _s(f'scb{id(label)}', size=8, leading=11, color=col_b, bold=bold_b, align=TA_CENTER)
        return [
            Paragraph(_safe(_enc(label)), S_TD_B),
            Paragraph(_safe(_enc(str(round(fa, 2)) if fa else "\u2014")), s_a),
            Paragraph(_safe(_enc(str(round(fb, 2)) if fb else "\u2014")), s_b),
        ]

    sc_header = [
        Paragraph("<b>Critere</b>", S_TH_L),
        Paragraph(f"<b>{_enc(tkr_a)}</b>", S_TH_C),
        Paragraph(f"<b>{_enc(tkr_b)}</b>", S_TH_C),
    ]
    sc_rows = [
        _score_row("FinSight Score (/100)",  m_a.get("finsight_score"),    m_b.get("finsight_score")),
        _score_row("Piotroski F-Score (/9)", m_a.get("piotroski_score"),   m_b.get("piotroski_score")),
        _score_row("Marge EBITDA (%)",       m_a.get("ebitda_margin_ltm"), m_b.get("ebitda_margin_ltm")),
        _score_row("ROIC (%)",               m_a.get("roic"),               m_b.get("roic")),
        _score_row("ND/EBITDA (x)",          m_a.get("net_debt_ebitda"),    m_b.get("net_debt_ebitda"), higher_better=False),
        _score_row("P/E (x)",                m_a.get("pe_ratio"),           m_b.get("pe_ratio"), higher_better=False),
        _score_row("Beta",                   m_a.get("beta"),               m_b.get("beta"), higher_better=False),
    ]
    sc_t = Table([sc_header] + sc_rows, colWidths=[70*mm, 50*mm, 50*mm])
    sc_t.setStyle(TableStyle([
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
    story.append(sc_t)
    story.append(Spacer(1, 4*mm))

    # Disclaimer
    story.append(rule(sa=2))
    story.append(Paragraph(
        "Ce rapport est genere par un algorithme d'analyse financiere (FinSight IA). "
        "Il ne constitue pas un conseil en investissement. "
        "Les donnees sont issues de sources publiques (yfinance, Finnhub). "
        "L'analyse LLM est fournie a titre indicatif. "
        "Verifiez toujours les chiffres avant toute decision.",
        S_DISC
    ))


# =============================================================================
# WRITER PRINCIPAL
# =============================================================================
class ComparisonPDFWriter:
    """Genere un rapport PDF comparatif A4 entre deux entreprises."""

    def generate(self, state_a: dict, state_b: dict, output_path: str = None) -> str:
        buf = self.generate_bytes(state_a, state_b)
        if output_path is None:
            tkr_a = state_a.get("ticker", "A")
            tkr_b = state_b.get("ticker", "B")
            out_dir = Path("outputs/generated/cli_tests")
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(out_dir / f"{tkr_a}_vs_{tkr_b}_comparison.pdf")
        with open(output_path, "wb") as f:
            f.write(buf.getvalue())
        log.info(f"[cmp_pdf] genere -> {output_path}")
        return output_path

    def generate_bytes(self, state_a: dict, state_b: dict) -> io.BytesIO:
        from outputs.comparison_writer import extract_metrics, _fetch_supplements

        def _get_ticker(state, default="A"):
            snap = state.get("raw_data") or state.get("snapshot")
            if snap is not None and not isinstance(snap, (str, dict)):
                try:
                    return snap.ticker or default
                except Exception:
                    pass
            if isinstance(snap, dict):
                t = snap.get("ticker") or snap.get("company_info", {}).get("ticker")
                if t:
                    return t
            return state.get("ticker", default)

        tkr_a = _get_ticker(state_a, "A")
        tkr_b = _get_ticker(state_b, "B")

        log.info(f"[cmp_pdf] generation {tkr_a} vs {tkr_b}")
        supp_a = _fetch_supplements(tkr_a)
        supp_b = _fetch_supplements(tkr_b)
        m_a = extract_metrics(state_a, supp_a)
        m_b = extract_metrics(state_b, supp_b)

        # Winner
        fs_a = float(m_a.get("finsight_score") or 0)
        fs_b = float(m_b.get("finsight_score") or 0)
        winner = tkr_a if fs_a >= fs_b else tkr_b
        m_a["winner"] = m_b["winner"] = winner

        # Synthese LLM
        from outputs.comparison_pptx_writer import _generate_synthesis
        import re as _re_md
        log.info("[cmp_pdf] synthese LLM...")
        synthesis = _generate_synthesis(m_a, m_b)

        # Pre-strip markdown asterisks de tous les textes LLM
        def _strip_md(s):
            if not s: return s
            s = _re_md.sub(r'\*\*(.+?)\*\*', r'\1', str(s), flags=_re_md.DOTALL)
            s = _re_md.sub(r'\*(.+?)\*', r'\1', s, flags=_re_md.DOTALL)
            s = _re_md.sub(r'\*+', '', s)
            return s
        synthesis = {k: _strip_md(v) if isinstance(v, str) else v
                     for k, v in synthesis.items()}

        # Metadonnees
        name_a  = m_a.get("company_name_a") or tkr_a
        name_b  = m_b.get("company_name_b") or tkr_b
        rec_a   = m_a.get("recommendation") or "HOLD"
        rec_b   = m_b.get("recommendation") or "HOLD"
        today   = _date_cls.today()
        MONTHS  = ["janvier","fevrier","mars","avril","mai","juin",
                   "juillet","aout","septembre","octobre","novembre","decembre"]
        date_str = f"{today.day} {MONTHS[today.month-1]} {today.year}"

        # Document ReportLab
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=MARGIN_L, rightMargin=MARGIN_R,
            topMargin=MARGIN_T + 8*mm,
            bottomMargin=MARGIN_B + 6*mm,
        )
        doc._cmp_header = _enc(
            f"FinSight IA  \u00b7  {tkr_a} vs {tkr_b}  \u00b7  Rapport Comparatif"
        )

        story = []

        # Page 1 : Couverture (placeholder -- rendue via onFirstPage)
        story.append(Spacer(1, 0))

        # Page 2+ : Sections de contenu
        story.append(PageBreak())
        _section_exec_summary(story, m_a, m_b, synthesis, tkr_a, tkr_b)
        _section_profil_pl(story, m_a, m_b, synthesis, tkr_a, tkr_b)
        _section_rentabilite_bilan(story, m_a, m_b, tkr_a, tkr_b)
        _section_valorisation(story, m_a, m_b, synthesis, tkr_a, tkr_b)
        _section_qualite_risque(story, m_a, m_b, synthesis, tkr_a, tkr_b)
        _section_verdict(story, m_a, m_b, synthesis, tkr_a, tkr_b)

        # Build avec cover page et header/footer
        def _on_first(canvas, doc):
            canvas.saveState()
            _cover_page(canvas, doc, tkr_a, tkr_b, name_a, name_b,
                        rec_a, rec_b, date_str, m_a, m_b, synthesis)

        def _on_later(canvas, doc):
            canvas.saveState()
            _header_footer(canvas, doc)

        doc.build(story, onFirstPage=_on_first, onLaterPages=_on_later)
        buf.seek(0)
        log.info(f"[cmp_pdf] genere en memoire ({buf.getbuffer().nbytes} bytes)")
        return buf
