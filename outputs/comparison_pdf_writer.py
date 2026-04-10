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
COLOR_B     = colors.HexColor('#C9A227')   # Societe B -- or professionnel
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
COLOR_B_PAL = colors.HexColor('#FBF3DC')

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
S_NOTE      = _s('note',size=5.5, leading=8, color=GREY_TEXT)
S_DISC      = _s('disc',size=5.5, leading=8, color=GREY_TEXT, align=TA_JUSTIFY)

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

def _canvas_text(s):
    """Nettoie une chaine pour canvas.drawString : pas HTML, pas newlines, cp1252 safe.
    Contrairement a _safe(), ne cree pas d'entites HTML (&amp; etc.) qui seraient
    rendues litteralement sur le canvas."""
    if not s: return ""
    import re as _re2, html as _html2, unicodedata as _ud2
    s = str(s)
    s = _ud2.normalize('NFKC', s)
    s = _html2.unescape(s)           # decode &gt; &lt; etc.
    s = _re2.sub(r'\*\*(.+?)\*\*', r'\1', s)  # strip bold markdown
    s = _re2.sub(r'\*(.+?)\*', r'\1', s)      # strip italic markdown
    s = _re2.sub(r'\*+', '', s)               # remaining stars
    s = _re2.sub(r'\s+', ' ', s).strip()      # flatten newlines/whitespace
    return s.encode('cp1252', errors='replace').decode('cp1252')

def _safe(s):
    """Echappe &, <, > pour Paragraph ReportLab. Supprime le markdown LLM.
    Decode d'abord les entites HTML du LLM (&gt; → >) avant re-escaping."""
    if not s: return ""
    import re, html as _html
    s = str(s)
    s = _html.unescape(s)  # decode &gt; &lt; &amp; &nbsp; etc.
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
    """Format market cap / EV. Valeur stockee en MILLIARDS (comparison_writer.mc_bn).
    Gere aussi les formats alternatifs (millions, raw) pour robustesse."""
    if v is None: return "\u2014"
    try:
        v = float(v)
        # Detection robuste de l'echelle : si > 1e12 la valeur est en raw USD
        # (pipeline direct yfinance), si > 1e6 elle est en millions, sinon en milliards.
        if abs(v) > 1_000_000_000_000:
            v = v / 1_000_000_000  # raw -> milliards
        elif abs(v) > 1_000_000:
            v = v / 1_000          # millions -> milliards
        # Maintenant v est en milliards
        if cur == "EUR":
            sym_big, sym_small = "Md\u20ac", "M\u20ac"
        else:
            sym_big, sym_small = "Mds" + cur, "M" + cur
        if abs(v) >= 1:
            return _fr(v, 1) + " " + sym_big
        # Small caps : afficher en millions
        return _fr(v * 1000, 0) + " " + sym_small
    except: return "\u2014"


def _word_clip(s, n, ellipsis="\u2026"):
    """Clip une chaine a n chars en respectant la frontiere de mot.
    Retourne le texte integral si < n, sinon coupe au dernier espace et ajoute ellipsis."""
    if not s:
        return ""
    s = str(s).strip()
    if len(s) <= n:
        return s
    cut = s[:n]
    sp = cut.rfind(" ")
    if sp > n // 2:
        cut = cut[:sp]
    # Retirer ponctuation finale avant d'ajouter l'ellipsis
    cut = cut.rstrip(" ,;:-")
    return cut + ellipsis

_SENTIMENT_MAP = {
    "POSITIVE": "Positif", "BULLISH": "Positif", "TRES_POSITIF": "Tres positif",
    "NEGATIF": "Negatif", "NEGATIVE": "Negatif", "BEARISH": "Negatif",
    "NEUTRE": "Neutre", "NEUTRAL": "Neutre", "MIXED": "Mixte",
}

def _fmt_sentiment(v):
    if v is None: return "\u2014"
    return _SENTIMENT_MAP.get(str(v).upper().strip(), str(v).capitalize())


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


def _bilan_text_below(m_a, m_b, tkr_a, tkr_b):
    """Texte analytique sous le tableau Bilan (page 4) : lecture qualite bilancielle."""
    def _f(v):
        try: return float(v) if v is not None else None
        except: return None
    nd_a = _f(m_a.get("net_debt_ebitda"))
    nd_b = _f(m_b.get("net_debt_ebitda"))
    cr_a = _f(m_a.get("current_ratio"))
    cr_b = _f(m_b.get("current_ratio"))
    ic_a = _f(m_a.get("interest_coverage"))
    ic_b = _f(m_b.get("interest_coverage"))
    # Qualite levier
    def _lev_q(nd):
        if nd is None: return "indetermine"
        if nd < 0:   return "position de tresorerie nette (desendette)"
        if nd < 1.5: return "levier faible et confortable"
        if nd < 3.0: return "levier modere"
        return "levier eleve imposant vigilance"
    _lev_winner = None
    if nd_a is not None and nd_b is not None:
        _lev_winner = tkr_a if nd_a < nd_b else tkr_b
    # Liquidite
    def _liq_q(cr):
        if cr is None: return "non calculable"
        if cr >= 2.0: return "confortable"
        if cr >= 1.2: return "saine"
        if cr >= 1.0: return "tendue mais suffisante"
        return "sous tension"
    # Couverture interets
    def _cov_q(ic):
        if ic is None: return "non calculable"
        if ic >= 10: return "tres solide"
        if ic >= 5:  return "solide"
        if ic >= 2:  return "correcte"
        return "fragile"
    parts = []
    parts.append(
        f"Lecture de la structure bilancielle : {tkr_a} presente un ratio ND/EBITDA "
        f"{_lev_q(nd_a)} ({_frx(m_a.get('net_debt_ebitda'))}), tandis que {tkr_b} "
        f"affiche un profil {_lev_q(nd_b)} ({_frx(m_b.get('net_debt_ebitda'))})."
    )
    if _lev_winner:
        parts.append(
            f" Sur le critere du levier, {_lev_winner} dispose d'une flexibilite "
            f"superieure pour absorber un choc macro ou financer une operation de croissance externe."
        )
    parts.append(
        f" La liquidite courante est {_liq_q(cr_a)} pour {tkr_a} ({_frx(m_a.get('current_ratio'))}) "
        f"vs {_liq_q(cr_b)} pour {tkr_b} ({_frx(m_b.get('current_ratio'))}) -- "
        f"indicateur du coussin operationnel court terme avant recours a des lignes bancaires."
    )
    parts.append(
        f" La couverture des charges d'interets est {_cov_q(ic_a)} pour {tkr_a} "
        f"({_frx(m_a.get('interest_coverage'))}) et {_cov_q(ic_b)} pour {tkr_b} "
        f"({_frx(m_b.get('interest_coverage'))}) : une couverture inferieure a 3x signale "
        f"une sensibilite accrue a une remontee des taux directeurs."
    )
    parts.append(
        " Implication investisseur : la prime/decote de valorisation doit integrer le "
        "differentiel de qualite bilancielle, qui conditionne la soutenabilite du dividende "
        "et la capacite d'autofinancement en bas de cycle."
    )
    return "".join(parts)

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
        labels  = ["Marge EBITDA", "Marge EBIT", "Marge Nette"]
        vals_a  = [_pv(m_a.get("ebitda_margin_ltm")), _pv(m_a.get("ebit_margin")), _pv(m_a.get("net_margin_ltm"))]
        vals_b  = [_pv(m_b.get("ebitda_margin_ltm")), _pv(m_b.get("ebit_margin")), _pv(m_b.get("net_margin_ltm"))]
        x = np.arange(len(labels))
        width = 0.35
        fig, ax = plt.subplots(figsize=(8.5, 4.2))
        # Titre analytique : qui domine sur les marges
        try:
            _ebitda_a = vals_a[0]
            _ebitda_b = vals_b[0]
            _leader = tkr_a if _ebitda_a > _ebitda_b else tkr_b
            _title_chart = f"{_leader} domine les marges (EBITDA {max(_ebitda_a, _ebitda_b):.0f}% vs {min(_ebitda_a, _ebitda_b):.0f}%)"
        except Exception:
            _title_chart = "Marges comparees"
        ax.set_title(_title_chart, fontsize=14, fontweight='bold', color='#1B3A6B', pad=10)
        bars_a = ax.bar(x - width/2, vals_a, width, label=tkr_a, color='#1B3A6B', alpha=0.95)
        bars_b = ax.bar(x + width/2, vals_b, width, label=tkr_b, color='#C9A227', alpha=0.95)
        for bar in list(bars_a) + list(bars_b):
            h = bar.get_height()
            if h != 0:
                ax.text(bar.get_x() + bar.get_width()/2., h + 0.8,
                        f"{h:.1f}%", ha='center', va='bottom', fontsize=12, color='#333', fontweight='bold')
        # Note si toutes les valeurs sont proches de 0 (donnees manquantes)
        if all(abs(v) < 0.01 for v in vals_a + vals_b):
            ax.text(0.5, 0.5, "Donnees insuffisantes", ha='center', va='center',
                    transform=ax.transAxes, fontsize=13, color='#999', style='italic')
        else:
            # Forcer y_min à 0 pour éviter l'axe effondré + top avec marge
            ax.set_ylim(bottom=0, top=max(max(vals_a + vals_b) * 1.25, 5))
        ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=13)
        ax.set_ylabel("(%)", fontsize=12, color='#555')
        ax.legend(loc='upper right', fontsize=13, frameon=False)
        for sp in ['top', 'right']: ax.spines[sp].set_visible(False)
        ax.spines['left'].set_color('#D0D5DD'); ax.spines['bottom'].set_color('#D0D5DD')
        ax.tick_params(axis='y', labelsize=12)
        ax.set_facecolor('white'); fig.patch.set_facecolor('white')
        ax.yaxis.grid(True, alpha=0.3, color='#D0D5DD'); ax.set_axisbelow(True)
        plt.tight_layout(pad=0.8)
        buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=160, bbox_inches='tight')
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
        ax.bar(x + width/2, vals_b, width, label=tkr_b, color='#C9A227', alpha=0.9)
        if all(abs(v) < 0.01 for v in vals_a + vals_b):
            ax.text(0.5, 0.5, "Donnees insuffisantes", ha='center', va='center',
                    transform=ax.transAxes, fontsize=10, color='#999', style='italic')
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
        fig, ax = plt.subplots(figsize=(9.0, 2.8))
        ax.barh(y + height/2, vals_a, height, label=tkr_a, color='#2E5FA3', alpha=0.9)
        ax.barh(y - height/2, vals_b, height, label=tkr_b, color='#C9A227', alpha=0.9)
        ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=9)
        ax.set_xlabel("(x)", fontsize=9, color='#555')
        ax.legend(loc='lower right', fontsize=9, frameon=False)
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
        ax.plot(angles, vals_b, 's-', color='#C9A227', linewidth=1.8, label=tkr_b)
        ax.fill(angles, vals_b, alpha=0.12, color='#C9A227')
        ax.set_facecolor('white'); fig.patch.set_facecolor('white')
        ax.grid(color='#D0D5DD', linewidth=0.5)
        ax.set_title(f"Profil de Risque : {tkr_a} vs {tkr_b}",
                     fontsize=9, fontweight='bold', pad=14, color='#1A2E5A')
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
        bars = ax.barh([1, 0], [sa, sb], color=['#2E5FA3', '#C9A227'], height=0.45, alpha=0.9)
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


def _chart_perf_bars(m_a, m_b, tkr_a, tkr_b) -> io.BytesIO:
    """Barres groupees : Performance 1m / 3m / 1 an."""
    if not _MPL:
        return _blank_buf(8, 3)
    try:
        def _pv(v):
            if v is None: return 0.0
            fv = float(v)
            return fv * 100 if abs(fv) <= 2.0 else fv
        labels  = ["1 mois", "3 mois", "1 an"]
        vals_a  = [_pv(m_a.get("perf_1m")), _pv(m_a.get("perf_3m")), _pv(m_a.get("perf_1y"))]
        vals_b  = [_pv(m_b.get("perf_1m")), _pv(m_b.get("perf_3m")), _pv(m_b.get("perf_1y"))]
        x = np.arange(len(labels)); width = 0.35
        _p1y_a = _pv(m_a.get("perf_1y"))
        _p1y_b = _pv(m_b.get("perf_1y"))
        _perf_leader = tkr_a if _p1y_a > _p1y_b else (tkr_b if _p1y_b > _p1y_a else None)
        _perf_title = (f"{_perf_leader} surperforme sur 1 an : {_p1y_a:+.1f}% vs {_p1y_b:+.1f}%"
                       if _perf_leader else f"Performance comparable : {_p1y_a:+.1f}% chacun sur 1 an")
        fig, ax = plt.subplots(figsize=(7, 3.2))
        ax.set_title(_perf_title, fontsize=9.5, fontweight='bold', color='#1B3A6B', pad=5)
        bars_a = ax.bar(x - width/2, vals_a, width, label=tkr_a, color='#2E5FA3', alpha=0.9)
        bars_b = ax.bar(x + width/2, vals_b, width, label=tkr_b, color='#C9A227', alpha=0.9)
        for bar in list(bars_a) + list(bars_b):
            h = bar.get_height()
            if abs(h) > 0.1:
                ax.text(bar.get_x() + bar.get_width()/2., h + (0.3 if h >= 0 else -1.2),
                        f"{h:+.1f}%", ha='center', va='bottom', fontsize=7.5, color='#333')
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
        log.warning(f"[cmp_pdf] chart_perf error: {e}")
        return _blank_buf(8, 3)


def _chart_fcf_capital(m_a, m_b, tkr_a, tkr_b) -> io.BytesIO:
    """Barres groupees : FCF Yield, Div Yield, P/FCF (normalise)."""
    if not _MPL:
        return _blank_buf(8, 3)
    try:
        def _pv(v):
            if v is None: return 0.0
            fv = float(v)
            return fv * 100 if abs(fv) <= 2.0 else fv
        labels = ["FCF Yield", "Div. Yield", "Capex/Rev."]
        vals_a = [_pv(m_a.get("fcf_yield")), _pv(m_a.get("dividend_yield")), _pv(m_a.get("capex_to_revenue"))]
        vals_b = [_pv(m_b.get("fcf_yield")), _pv(m_b.get("dividend_yield")), _pv(m_b.get("capex_to_revenue"))]
        x = np.arange(len(labels)); width = 0.35
        fig, ax = plt.subplots(figsize=(7, 3.2))
        ax.bar(x - width/2, vals_a, width, label=tkr_a, color='#2E5FA3', alpha=0.9)
        ax.bar(x + width/2, vals_b, width, label=tkr_b, color='#C9A227', alpha=0.9)
        if all(abs(v) < 0.01 for v in vals_a + vals_b):
            ax.text(0.5, 0.5, "Donnees insuffisantes", ha='center', va='center',
                    transform=ax.transAxes, fontsize=10, color='#999', style='italic')
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
        log.warning(f"[cmp_pdf] chart_fcf error: {e}")
        return _blank_buf(8, 3)


def _dcf_sensitivity_matrix(base_val, wacc, g_term):
    """
    Matrice 3x3 : WACC (lignes: -1%/base/+1%) x g_terminal (colonnes: -0.5%/base/+0.5%).
    Approximation Gordon Growth: V ~ base * (wacc-g) / (wacc+dw - g-dg).
    Retourne liste de listes de strings.
    """
    try:
        base_val = float(base_val or 0)
        wacc     = float(wacc or 0.10)
        g_term   = float(g_term or 0.03)
        if base_val <= 0 or (wacc - g_term) < 0.001:
            return None
        spread0 = wacc - g_term
        d_w = [-0.01, 0.0, 0.01]
        d_g = [-0.005, 0.0, 0.005]
        rows = []
        for dw in d_w:
            row = []
            for dg in d_g:
                new_spread = spread0 + dw - dg
                if new_spread > 0.001:
                    val = round(base_val * spread0 / new_spread, 0)
                    row.append(f"{val:,.0f}".replace(",", " "))
                else:
                    row.append("N/A")
            rows.append(row)
        return rows
    except Exception:
        return None


# =============================================================================
# COVER PAGE -- style secteur (Platypus story flowables)
# =============================================================================
def _build_cover_story(tkr_a, tkr_b, name_a, name_b,
                       rec_a, rec_b, date_str, m_a, m_b, synthesis):
    """Retourne la liste de flowables pour la page de garde.
    Le ruban navy de la marque est dessine via canvas dans _cover_header."""
    story = []

    # La banderole navy "FinSight IA / Plateforme d'Analyse..." est dessinee
    # par _header_footer (is_cover=True) sur la 1ere page en haut (18mm).
    # topMargin=30mm garantit l'espace libre sous le ruban.
    story.append(Spacer(1, 4 * mm))

    # Sous-titre
    story.append(Paragraph(
        _safe("Analyse Comparative de Societes"),
        _s('cv_sub', size=12, color=GREY_TEXT, align=TA_CENTER, sb=8, sa=4)
    ))

    # Titre principal
    story.append(Paragraph(
        _safe(f"{tkr_a}  vs  {tkr_b}"),
        _s('cv_main', size=28, color=NAVY, bold=True, align=TA_CENTER, leading=38, sb=4, sa=6)
    ))

    # Noms complets
    _na = (name_a or tkr_a)[:30]
    _nb = (name_b or tkr_b)[:30]
    story.append(Paragraph(
        _safe(f"{_na} ({tkr_a})   vs   {_nb} ({tkr_b})"),
        _s('cv_names', size=10, color=GREY_TEXT, align=TA_CENTER, sa=8)
    ))

    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width=TABLE_W, thickness=0.5, color=GREY_RULE,
                             spaceBefore=0, spaceAfter=6))

    # ---- Tableau KPI 2 colonnes (style secteur) ----
    def _kpi_p(txt, col=WHITE, bold=False, align=TA_CENTER, size=9):
        return Paragraph(_safe(txt), _s(f'kv{id(txt)}', size=size, color=col,
                                        bold=bold, align=align, leading=14))

    rec_lbl_a = _rec_label(rec_a)
    rec_lbl_b = _rec_label(rec_b)
    tgt_a  = str(m_a.get("target_price") or "N/A")
    tgt_b  = str(m_b.get("target_price") or "N/A")
    up_a   = str(m_a.get("upside_str") or "N/A")
    up_b   = str(m_b.get("upside_str") or "N/A")
    sc_a   = str(m_a.get("finsight_score") or "N/A")
    sc_b   = str(m_b.get("finsight_score") or "N/A")
    pe_a   = _frx(m_a.get("pe_ratio"));  pe_b  = _frx(m_b.get("pe_ratio"))
    ev_a   = _frx(m_a.get("ev_ebitda")); ev_b  = _frx(m_b.get("ev_ebitda"))
    mg_a   = _frpct(m_a.get("ebitda_margin_ltm"), False)
    mg_b   = _frpct(m_b.get("ebitda_margin_ltm"), False)

    kpi_data = [
        # Header (fond couleur)
        [_kpi_p(tkr_a, col=WHITE, bold=True, size=11),
         _kpi_p(tkr_b, col=WHITE, bold=True, size=11)],
        # Signal / recommandation
        [_kpi_p(f"Signal : {rec_lbl_a}", col=WHITE, size=9),
         _kpi_p(f"Signal : {rec_lbl_b}", col=WHITE, size=9)],
        # Cible + upside
        [_kpi_p(f"Cible 12m : {tgt_a}  ({up_a})", col=GREY_TEXT, size=9),
         _kpi_p(f"Cible 12m : {tgt_b}  ({up_b})", col=GREY_TEXT, size=9)],
        # Multiples
        [_kpi_p(f"P/E : {pe_a}  |  EV/EBITDA : {ev_a}", col=GREY_TEXT, size=8.5),
         _kpi_p(f"P/E : {pe_b}  |  EV/EBITDA : {ev_b}", col=GREY_TEXT, size=8.5)],
        # Marge EBITDA + Score
        [_kpi_p(f"Mg EBITDA : {mg_a}  |  Score : {sc_a}/100", col=GREY_TEXT, size=8.5),
         _kpi_p(f"Mg EBITDA : {mg_b}  |  Score : {sc_b}/100", col=GREY_TEXT, size=8.5)],
    ]

    col_w = TABLE_W / 2
    kpi_tbl = Table(kpi_data, colWidths=[col_w, col_w])
    kpi_tbl.setStyle(TableStyle([
        # En-tete (2 premieres lignes) fond couleur
        ('BACKGROUND',   (0, 0), (0, 1), COLOR_A),
        ('BACKGROUND',   (1, 0), (1, 1), COLOR_B),
        ('TOPPADDING',   (0, 0), (-1, 1), 8),
        ('BOTTOMPADDING',(0, 0), (-1, 1), 8),
        # Lignes de donnees
        ('TOPPADDING',   (0, 2), (-1, -1), 6),
        ('BOTTOMPADDING',(0, 2), (-1, -1), 6),
        ('ROWBACKGROUNDS',(0, 2), (-1, -1), [WHITE, GREY_LIGHT]),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEAFTER',    (0, 0), (0, -1), 0.5, GREY_RULE),
        ('GRID',         (0, 2), (-1, -1), 0.3, GREY_MED),
        ('LEFTPADDING',  (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 6*mm))

    # ---- Verdict box ----
    winner = m_a.get("winner") or tkr_a
    # Clip large (900 chars) pour accomoder le verdict complet "Choix/Pourquoi/Risque"
    verdict_raw = _safe(_word_clip(synthesis.get("verdict_text") or "", 900))

    verd_data = [[
        Paragraph(_safe(f"Choix prefere : {winner}"),
                  _s('verd_t', size=9.5, color=NAVY, bold=True, align=TA_CENTER, sa=3)),
        ],[
        Paragraph(verdict_raw,
                  _s('verd_b', size=8, color=GREY_TEXT, align=TA_CENTER, leading=12)),
    ]]
    verd_tbl = Table([[verd_data[0][0]], [verd_data[1][0]]], colWidths=[TABLE_W])
    verd_tbl.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), colors.HexColor('#EEF3FA')),
        ('BOX',          (0, 0), (-1, -1), 0.4, NAVY_LIGHT),
        ('TOPPADDING',   (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
        ('LEFTPADDING',  (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(verd_tbl)
    story.append(Spacer(1, 5*mm))

    # ---- Date / sources ----
    story.append(Paragraph(
        _safe(f"Donnees : yfinance  \u00b7  FMP  \u00b7  Finnhub   |   {date_str}   |   Horizon : 12 mois"),
        _s('cv_date', size=7.5, color=GREY_TEXT, align=TA_CENTER)
    ))

    story.append(PageBreak())
    return story


# =============================================================================
# HEADER / FOOTER PAGES DE CONTENU
# =============================================================================
def _header_footer(canvas, doc):
    W, H = A4
    canvas.saveState()
    is_cover = (doc.page == 1)
    if is_cover:
        # === Cover : gros ruban navy style societe (FinSight IA + plateforme) ===
        RIBBON_H = 18 * mm
        canvas.setFillColor(NAVY)
        canvas.rect(0, H - RIBBON_H, W, RIBBON_H, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 16)
        canvas.drawCentredString(W / 2, H - 10 * mm, _canvas_text("FinSight IA"))
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#BBCBDD"))
        canvas.drawCentredString(
            W / 2, H - 15 * mm,
            _canvas_text("Plateforme d'Analyse Financiere Institutionnelle")
        )
    else:
        # === Pages de contenu : ruban fin navy ===
        canvas.setFillColor(NAVY)
        canvas.rect(0, H - 12 * mm, W, 12 * mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(
            MARGIN_L, H - 8 * mm,
            _enc(getattr(doc, '_cmp_header', 'FinSight IA'))
        )
        canvas.setFont("Helvetica", 7.5)
        canvas.drawRightString(
            W - MARGIN_R, H - 8 * mm,
            _enc(f"Confidentiel  \u00b7  Page {doc.page}")
        )
    # Footer (toutes pages)
    canvas.setFillColor(GREY_RULE)
    canvas.rect(0, 0, W, 9 * mm, fill=1, stroke=0)
    canvas.setFillColor(GREY_TEXT)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(
        MARGIN_L, 3.5 * mm,
        _enc("FinSight IA  \u00b7  Analyse algorithmique, non contractuelle")
    )
    canvas.drawRightString(W - MARGIN_R, 3.5 * mm, _enc(f"Page {doc.page}"))
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
        story.append(Paragraph(_safe(_word_clip(exec_text, 700)), S_BODY))
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

    # Verdict excerpt — typographie harmonisee avec le corps de texte
    wc_hex = _hex_str(BUY_GREEN if winner == tkr_a else COLOR_B)
    _verdict_txt = _safe(_word_clip(synthesis.get('verdict_text') or "", 420))
    story.append(Paragraph(
        f"<b>Titre prefere : <font color='#{wc_hex}'>{_enc(winner)}</font></b>"
        f"  \u2014  {_verdict_txt}",
        _s('verd', size=8.5, leading=13, color=GREY_TEXT, align=TA_JUSTIFY, sb=3, sa=2)
    ))
    story.append(Spacer(1, 3*mm))

    # Synthese valorisation + qualite comparative
    pe_a   = _frx(m_a.get("pe_ratio"));    pe_b   = _frx(m_b.get("pe_ratio"))
    ev_a   = _frx(m_a.get("ev_ebitda"));   ev_b   = _frx(m_b.get("ev_ebitda"))
    roic_a = _frpct(m_a.get("roic"));      roic_b = _frpct(m_b.get("roic"))
    pio_a  = m_a.get("piotroski_score");    pio_b  = m_b.get("piotroski_score")
    pio_a_s = str(int(float(pio_a))) + "/9" if pio_a is not None else "\u2014"
    pio_b_s = str(int(float(pio_b))) + "/9" if pio_b is not None else "\u2014"
    up_a   = str(m_a.get("upside_str") or "\u2014")
    up_b   = str(m_b.get("upside_str") or "\u2014")
    valcomp_text = (
        f"Sur le plan de la valorisation, {tkr_a} s'echange a {pe_a}x les benefices "
        f"(EV/EBITDA {ev_a}x) contre {pe_b}x ({ev_b}x) pour {tkr_b}. "
        f"La qualite fondamentale (Piotroski F-Score : {pio_a_s} vs {pio_b_s}) "
        f"et la rentabilite operationnelle (ROIC {roic_a} vs {roic_b}) "
        f"permettent d'arbitrer entre un titre de croissance prime et un titre de valeur. "
        f"Le potentiel de hausse consensus ressort a {up_a} pour {tkr_a} et {up_b} pour {tkr_b}."
    )
    story.append(Paragraph(_safe(valcomp_text), S_BODY))
    story.append(Spacer(1, 3*mm))
    story.append(src("FinSight IA / yfinance / Finnhub"))


def _section_profil_pl(story, m_a, m_b, synthesis, tkr_a, tkr_b):
    story.append(PageBreak())
    story += section_title("Profil & Compte de Resultat", "2")

    # Texte computed Profil
    story.append(Paragraph(_safe(_profil_text(m_a, m_b, tkr_a, tkr_b)), S_BODY))
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
        story.append(Paragraph(_safe(synthesis["financial_text"]), S_BODY))
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
        ["EPS LTM",            _frx(m_a.get("trailing_eps")),      _frx(m_b.get("trailing_eps"))],
        ["EPS N+1E (consensus)", _frx(m_a.get("forward_eps")),     _frx(m_b.get("forward_eps"))],
        ["P/E Forward",        _frx(m_a.get("forward_pe")),        _frx(m_b.get("forward_pe"))],
        ["Rev. Growth YoY",    _frpct(m_a.get("revenue_growth_fwd"), True), _frpct(m_b.get("revenue_growth_fwd"), True)],
    ]
    t_pl = _make_tbl_3col(hdr_pl, raw_pl)
    if t_pl:
        story.append(t_pl)
    story.append(Spacer(1, 3*mm))

    # Graphique marges cote a cote avec commentaire analytique
    story.append(CondPageBreak(48*mm))
    buf = _chart_margins(m_a, m_b, tkr_a, tkr_b)
    img = Image(buf, width=105*mm, height=46*mm)
    _ebitda_a = _frpct(m_a.get('ebitda_margin_ltm'))
    _ebitda_b = _frpct(m_b.get('ebitda_margin_ltm'))
    _ebit_a   = _frpct(m_a.get('ebit_margin'))
    _ebit_b   = _frpct(m_b.get('ebit_margin'))
    _net_a    = _frpct(m_a.get('net_margin_ltm'))
    _net_b    = _frpct(m_b.get('net_margin_ltm'))
    try:
        _ebitda_a_f = float(str(m_a.get('ebitda_margin_ltm') or 0))
        _ebitda_b_f = float(str(m_b.get('ebitda_margin_ltm') or 0))
        _margin_leader = tkr_a if _ebitda_a_f >= _ebitda_b_f else tkr_b
        _margin_lagger = tkr_b if _margin_leader == tkr_a else tkr_a
        _margin_l_val  = _ebitda_a if _margin_leader == tkr_a else _ebitda_b
        _margin_lg_val = _ebitda_b if _margin_leader == tkr_a else _ebitda_a
        _margin_comment = (
            f"{_enc(_margin_leader)} domine sur les trois niveaux de marge "
            f"avec un EBITDA de {_margin_l_val} vs {_margin_lg_val} pour {_enc(_margin_lagger)}. "
        )
    except Exception:
        _margin_comment = ""
    _comment_text = (
        f"Comparaison des marges (EBITDA / EBIT / Nette) : "
        f"{_enc(tkr_a)} affiche {_ebitda_a} / {_ebit_a} / {_net_a} ; "
        f"{_enc(tkr_b)} affiche {_ebitda_b} / {_ebit_b} / {_net_b}. "
        f"{_margin_comment}"
        f"L'ecart de marge reflete des modeles economiques distincts — "
        f"structure des couts, mix produit/service, levier operationnel. "
        f"A analyser en complement des ratios de croissance et de qualite de bilan."
    )
    _S_SIDE_MARGIN = _s('side_margin', size=8.5, leading=13, color=GREY_TEXT, align=TA_LEFT)
    _comment_par = Paragraph(_safe(_comment_text), _S_SIDE_MARGIN)
    _note_par    = Paragraph("Source : FinSight IA / yfinance", S_NOTE)
    _right_cell  = Table(
        [[_comment_par], [_note_par]],
        colWidths=[60*mm],
    )
    _right_cell.setStyle(TableStyle([
        ('VALIGN',         (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',    (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',   (0, 0), (-1, -1), 0),
        ('TOPPADDING',     (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 0),
        ('NOSPLIT',        (0, 0), (-1, -1)),
    ]))
    side_margins = Table([[img, _right_cell]], colWidths=[105*mm, 65*mm])
    side_margins.setStyle(TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
    ]))
    story.append(side_margins)


def _section_rentabilite_bilan(story, m_a, m_b, tkr_a, tkr_b):
    story.append(PageBreak())
    story += section_title("Rentabilite & Bilan", "3")

    # Texte introductif rentabilite
    roic_a  = _frpct(m_a.get("roic"));      roic_b  = _frpct(m_b.get("roic"))
    roe_a   = _frpct(m_a.get("roe"));       roe_b   = _frpct(m_b.get("roe"))
    eps_g_a = _frpct(m_a.get("eps_growth")); eps_g_b = _frpct(m_b.get("eps_growth"))
    cagr_a  = _frpct(m_a.get("revenue_cagr_3y")); cagr_b = _frpct(m_b.get("revenue_cagr_3y"))
    fcfy_a  = _frpct(m_a.get("fcf_yield")); fcfy_b  = _frpct(m_b.get("fcf_yield"))
    try:
        _roic_a_f = float(str(m_a.get("roic") or 0))
        _roic_b_f = float(str(m_b.get("roic") or 0))
        _leader_r = tkr_a if _roic_a_f >= _roic_b_f else tkr_b
        _roic_comment = (
            f"{_enc(_leader_r)} affiche un ROIC superieur ({roic_a if _leader_r == tkr_a else roic_b}), "
            f"signe d'une meilleure allocation du capital investi. "
        )
    except Exception:
        _roic_comment = ""
    rent_text = (
        f"Analyse de la rentabilite : ROIC {roic_a} vs {roic_b}, ROE {roe_a} vs {roe_b}. "
        f"{_roic_comment}"
        f"La croissance des revenus sur 3 ans (CAGR {cagr_a} vs {cagr_b}) et "
        f"la progression du BPA ({eps_g_a} vs {eps_g_b}) "
        f"traduisent la capacite de chaque groupe a monetiser sa base d'actifs. "
        f"Le FCF yield ({fcfy_a} vs {fcfy_b}) complete la lecture en mesurant "
        f"la generation de cash disponible apres investissements."
    )
    story.append(Paragraph(_safe(rent_text), S_BODY))
    story.append(Spacer(1, 3*mm))

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

    # Bilan — regroupe dans un KeepTogether pour eviter qu'une partie orpheline
    # (source ou derniere ligne) se retrouve seule sur la page suivante.
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

    _bilan_block = [
        Paragraph(_safe(_bilan_text(m_a, m_b, tkr_a, tkr_b)), S_BODY),
        Spacer(1, 3*mm),
    ]
    if t_b:
        _bilan_block.append(t_b)
    _bilan_block.append(Spacer(1, 3*mm))
    _bilan_block.append(Paragraph(_safe(_bilan_text_below(m_a, m_b, tkr_a, tkr_b)), S_BODY))
    _bilan_block.append(Spacer(1, 2*mm))
    _bilan_block.append(src("FinSight IA / yfinance"))
    # CondPageBreak avant si < 110mm restants (bilan complet fait ~100mm)
    story.append(CondPageBreak(110*mm))
    story.append(KeepTogether(_bilan_block))


def _section_valorisation(story, m_a, m_b, synthesis, tkr_a, tkr_b):
    story.append(PageBreak())
    story += section_title("Valorisation", "5")

    if synthesis.get("valuation_text"):
        vt = _word_clip(synthesis["valuation_text"], 500)
        story.append(Paragraph(_safe(vt), S_BODY))
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
    # Mise en page cote-a-cote : texte analytique a gauche, tableau a droite
    pe_a  = _frx(m_a.get("pe_ratio"));     pe_b  = _frx(m_b.get("pe_ratio"))
    ev_a  = _frx(m_a.get("ev_ebitda"));    ev_b  = _frx(m_b.get("ev_ebitda"))
    pb_a  = _frx(m_a.get("price_to_book")); pb_b = _frx(m_b.get("price_to_book"))
    up_a  = str(m_a.get("upside_str") or "\u2014")
    up_b  = str(m_b.get("upside_str") or "\u2014")
    _mult_comment = (
        f"Lecture des multiples : Le P/E de {tkr_a} ({pe_a}x) "
        f"vs {tkr_b} ({pe_b}x) reflete les attentes de croissance respective. "
        f"L'EV/EBITDA ({ev_a}x vs {ev_b}x) donne une vue independante "
        f"de la structure financiere. Le P/B ({pb_a}x vs {pb_b}x) "
        f"mesure la prime payee sur les actifs nets. "
        f"Potentiel consensus : {up_a} pour {_enc(tkr_a)}, "
        f"{up_b} pour {_enc(tkr_b)}."
    )
    _S_MULT = _s('sidecom', size=8.5, leading=13, color=GREY_TEXT, align=TA_LEFT)
    t_v = _make_tbl_3col(hdr_v, raw_v, cw=[45*mm, 30*mm, 30*mm])
    side_left = Paragraph(_safe(_mult_comment), _S_MULT)
    if t_v:
        side_tbl = Table([[side_left, t_v]], colWidths=[65*mm, 105*mm])
        side_tbl.setStyle(TableStyle([
            ('VALIGN',  (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING',  (0, 0), (0, 0), 0),
            ('RIGHTPADDING', (0, 0), (0, 0), 4),
            ('LEFTPADDING',  (1, 0), (1, 0), 4),
            ('RIGHTPADDING', (1, 0), (1, 0), 0),
        ]))
        story.append(side_tbl)
    else:
        story.append(side_left)
    story.append(Spacer(1, 3*mm))

    buf = _chart_multiples(m_a, m_b, tkr_a, tkr_b)
    img = Image(buf, width=TABLE_W, height=55*mm)
    story.append(img)
    story.append(Spacer(1, 3*mm))

    # DCF (avec CondPageBreak)
    story.append(CondPageBreak(60*mm))
    story.append(Paragraph(_safe(_dcf_text(m_a, m_b, tkr_a, tkr_b)), S_BODY))
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
    story += section_title("Qualite & Risque", "7")

    if synthesis.get("quality_text"):
        story.append(Paragraph(_safe(synthesis["quality_text"]), S_BODY))
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
    ben_a = m_a.get("beneish_mscore");  ben_b = m_b.get("beneish_mscore")
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
    story.append(Paragraph(_safe(_risque_text(m_a, m_b, tkr_a, tkr_b)), S_BODY))
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
        ["Perf. 12 mois",    _frpct(m_a.get("perf_1y"), True),  _frpct(m_b.get("perf_1y"), True)],
        ["RSI (14j)",        _fr(m_a.get("rsi"), 1),            _fr(m_b.get("rsi"), 1)],
        ["ND / EBITDA",      _frx(m_a.get("net_debt_ebitda")),  _frx(m_b.get("net_debt_ebitda"))],
        ["Sentiment",        _fmt_sentiment(m_a.get("sentiment_label")),
                             _fmt_sentiment(m_b.get("sentiment_label"))],
    ]
    t_ri = _make_tbl_3col(hdr_ri, raw_ri)
    if t_ri:
        story.append(t_ri)
    story.append(Spacer(1, 3*mm))

    # Radar chart
    buf_r = _chart_risk_radar(m_a, m_b, tkr_a, tkr_b)
    img_r = Image(buf_r, width=95*mm, height=80*mm)
    story.append(KeepTogether([img_r, Spacer(1, 2*mm), src("FinSight IA / yfinance")]))

    # Interpretation textuelle du radar
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("<b>Interpretation du profil de risque</b>", S_SUBSECTION))
    story.append(Spacer(1, 2*mm))

    def _risk_level_txt(v, lo_good, hi_good, higher_is_better=True):
        if v is None: return ("N/A", "indetermine")
        try:
            fv = float(v)
            if higher_is_better:
                if fv >= hi_good: return ("Faible", "maitrise")
                if fv >= lo_good: return ("Modere", "surveiller")
                return ("Eleve", "significatif")
            else:
                if fv <= lo_good: return ("Faible", "maitrise")
                if fv <= hi_good: return ("Modere", "surveiller")
                return ("Eleve", "significatif")
        except: return ("N/A", "indetermine")

    axes_desc = [
        ("net_debt_ebitda", -0.5, 2.5, False,
         "Levier financier (ND/EBITDA)",
         "mesure le nombre d'annees necessaires pour rembourser la dette nette via l'EBITDA. "
         "En dessous de 2,5x, le levier est considere sain ; au-dela de 3,5x il devient contraignant."),
        ("perf_3m", 0.0, 0.10, True,
         "Momentum (performance 3 mois)",
         "capture la dynamique recente du titre. Un momentum positif traduit un flux acheteur "
         "soutenu et une perception favorable du marche a court terme."),
        ("piotroski_score", 4.0, 7.0, True,
         "Qualite comptable (Piotroski F-Score)",
         "evalue la solidite fondamentale sur 9 criteres binaires (rentabilite, levier, efficience). "
         "Un score superieur a 7 signale une entreprise financierement solide."),
        ("current_ratio", 1.0, 2.0, True,
         "Liquidite (Current Ratio)",
         "rapport actifs courants / passifs courants. Un ratio superieur a 1,5 indique une capacite "
         "confortable a honorer les obligations court terme sans stress de tresorerie."),
        ("revenue_cagr_3y", 0.03, 0.10, True,
         "Croissance (CAGR revenus 3 ans)",
         "mesure la croissance organique annualisee. Au-dela de 10 % par an, la societe fait partie "
         "des moteurs de croissance ; en dessous de 3 % elle evolue en territoire maturite."),
    ]

    for key, lo, hi, hib, axis_lbl, axis_desc in axes_desc:
        va = m_a.get(key); vb = m_b.get(key)
        la, _ = _risk_level_txt(va, lo, hi, hib)
        lb, _ = _risk_level_txt(vb, lo, hi, hib)
        val_a_str = _fr(va, 2) if va is not None else "\u2014"
        val_b_str = _fr(vb, 2) if vb is not None else "\u2014"
        color_map = {"Faible": "#1A7A4A", "Modere": "#B06000", "Eleve": "#A82020", "N/A": "#888888"}
        ca = color_map.get(la, "#888888"); cb = color_map.get(lb, "#888888")
        bullet = (
            f"<b>{_enc(axis_lbl)} :</b> {_enc(axis_desc)} "
            f"Pour {_enc(tkr_a)}, la valeur est <b>{_enc(val_a_str)}</b> "
            f"(<font color='{ca}'><b>{_enc(la)}</b></font>). "
            f"Pour {_enc(tkr_b)}, elle est <b>{_enc(val_b_str)}</b> "
            f"(<font color='{cb}'><b>{_enc(lb)}</b></font>)."
        )
        story.append(Paragraph(bullet, _s(f'ri_{key}', size=8, leading=12, color=BLACK, sb=0, sa=3)))

    # Conclusion comparative du profil de risque
    story.append(Spacer(1, 3*mm))
    pio_a = m_a.get("piotroski_score"); pio_b = m_b.get("piotroski_score")
    beta_a = m_a.get("beta"); beta_b = m_b.get("beta")
    nd_a = m_a.get("net_debt_ebitda"); nd_b = m_b.get("net_debt_ebitda")
    try:
        _pio_winner = tkr_a if (pio_a or 0) >= (pio_b or 0) else tkr_b
        _pio_loser  = tkr_b if _pio_winner == tkr_a else tkr_a
        _nd_a_f = float(nd_a) if nd_a is not None else 999
        _nd_b_f = float(nd_b) if nd_b is not None else 999
        _lev_winner = tkr_a if _nd_a_f <= _nd_b_f else tkr_b
        _beta_a_f = float(beta_a) if beta_a is not None else 1.0
        _beta_b_f = float(beta_b) if beta_b is not None else 1.0
        _vol_comment = (
            f"{tkr_a} affiche un beta de {_fr(beta_a,2)} vs {_fr(beta_b,2)} pour {tkr_b} "
            f"— {'expositions similaires au risque de marche' if abs(_beta_a_f - _beta_b_f) < 0.15 else f'{tkr_a if _beta_a_f < _beta_b_f else tkr_b} presente une sensibilite moindre aux variations du marche'}."
        )
        conclusion = (
            f"<b>Synthese comparative du profil de risque :</b> {_enc(_pio_winner)} domine sur la qualite "
            f"fondamentale (Piotroski {int(pio_a or 0) if _pio_winner == tkr_a else int(pio_b or 0)}/9) "
            f"tandis que {_enc(_lev_winner)} affiche le levier le plus maitrise. "
            f"{_enc(_vol_comment)} "
            f"En agregat, le profil de risque oriente la preference vers la valeur offrant la meilleure "
            f"combinaison qualite bilancielle / visibilite des flux — a croiser avec la valorisation relative."
        )
    except Exception:
        conclusion = (
            f"Le profil de risque comparatif de {_enc(tkr_a)} et {_enc(tkr_b)} doit etre "
            f"analyse en conjonction avec la valorisation et les perspectives de croissance "
            f"pour identifier la meilleure asymetrie risque/rendement."
        )
    story.append(Paragraph(conclusion.replace('&', '&amp;'), S_BODY))
    story.append(Spacer(1, 2*mm))
    story.append(src("FinSight IA / yfinance"))


def _section_verdict(story, m_a, m_b, synthesis, tkr_a, tkr_b):
    story.append(PageBreak())
    story += section_title("Verdict & Theses", "11")

    winner = m_a.get("winner") or tkr_a

    # Verdict LLM
    if synthesis.get("verdict_text"):
        story.append(Paragraph(
            f"<b>Verdict Analytique :</b>  {_safe(synthesis['verdict_text'])}",
            _s('verd2', size=9, leading=13, color=BLACK, sb=2, sa=4)
        ))
        story.append(Spacer(1, 3*mm))

    # Tableau theses bull/bear cote a cote
    story.append(Paragraph("<b>Theses d'investissement</b>", S_SUBSECTION))
    story.append(Spacer(1, 2*mm))

    def _thesis_cell(text, is_bull):
        col    = BUY_GREEN if is_bull else SELL_RED
        prefix = "\u25b2 " if is_bull else "\u25bc "
        _txt   = _safe(text or "\u2014")
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

    def _pct(v):
        """Convert decimal fraction to percentage value (0.348 -> 34.8)."""
        try:
            f = float(v)
            return round(f * 100, 1) if f is not None else None
        except Exception:
            return None

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
        _score_row("Marge EBITDA (%)",       _pct(m_a.get("ebitda_margin_ltm")), _pct(m_b.get("ebitda_margin_ltm"))),
        _score_row("ROIC (%)",               _pct(m_a.get("roic")),              _pct(m_b.get("roic"))),
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


def _section_fcf_capital(story, m_a, m_b, tkr_a, tkr_b):
    story.append(PageBreak())
    story += section_title("Free Cash Flow & Capital Allocation", "4")

    fcf_a  = _frm(m_a.get("free_cash_flow"))
    fcf_b  = _frm(m_b.get("free_cash_flow"))
    fy_a   = _frpct(m_a.get("fcf_yield"))
    fy_b   = _frpct(m_b.get("fcf_yield"))
    dy_a   = _frpct(m_a.get("dividend_yield"))
    dy_b   = _frpct(m_b.get("dividend_yield"))
    cx_a   = _frpct(m_a.get("capex_to_revenue"))
    cx_b   = _frpct(m_b.get("capex_to_revenue"))
    cc_a = _frpct(m_a.get("cash_conversion")); cc_b = _frpct(m_b.get("cash_conversion"))
    nd_a = _frm(m_a.get("net_debt"));         nd_b = _frm(m_b.get("net_debt"))
    nd_ev_a = _frx(m_a.get("net_debt_ebitda")); nd_ev_b = _frx(m_b.get("net_debt_ebitda"))
    text = (
        f"Analyse FCF : {tkr_a} genere {fcf_a} de FCF (rendement {fy_a}) vs {fcf_b} "
        f"({fy_b}) pour {tkr_b}. Capex/Revenus : {cx_a} vs {cx_b}, "
        f"refletant les intensites capitalistiques respectives. "
        f"Dividende {dy_a} vs {dy_b}. "
        f"Un FCF yield superieur signale une capacite accrue a financer la croissance, "
        f"racheter des actions et verser des dividendes sur horizon 12 mois. "
        f"Le taux de conversion cash (FCF/EBITDA) ressort a {cc_a} pour {tkr_a} vs {cc_b} "
        f"pour {tkr_b} : un ratio eleve indique que l'EBITDA se transforme efficacement "
        f"en cash disponible, limitant les besoins de financement externe. "
        f"Cote levier, la dette nette s'etablit a {nd_a} ({nd_ev_a}x EBITDA) pour {tkr_a} "
        f"et {nd_b} ({nd_ev_b}x EBITDA) pour {tkr_b} -- un indicateur cle "
        f"pour evaluer la capacite de remboursement et la flexibilite bilancielle."
    )
    story.append(Paragraph(_safe(text), S_BODY))
    story.append(Spacer(1, 3*mm))

    hdr = [
        Paragraph("<b>Cash-Flow</b>", S_TH_L),
        Paragraph(f"<b>{_enc(tkr_a)}</b>", S_TH_C),
        Paragraph(f"<b>{_enc(tkr_b)}</b>", S_TH_C),
    ]
    raw = [
        ["Free Cash-Flow",       _frm(m_a.get("free_cash_flow")),    _frm(m_b.get("free_cash_flow"))],
        ["FCF Yield",            _frpct(m_a.get("fcf_yield")),        _frpct(m_b.get("fcf_yield"))],
        ["P/FCF",                _frx(m_a.get("p_fcf")),              _frx(m_b.get("p_fcf"))],
        ["Capex / Rev.",         _frpct(m_a.get("capex_to_revenue")), _frpct(m_b.get("capex_to_revenue"))],
        ["Cash Conversion",      _frpct(m_a.get("cash_conversion")),  _frpct(m_b.get("cash_conversion"))],
        ["Dividende Yield",      _frpct(m_a.get("dividend_yield")),   _frpct(m_b.get("dividend_yield"))],
        ["Tresorerie",           _frm(m_a.get("cash")),               _frm(m_b.get("cash"))],
        ["Dette Nette",          _frm(m_a.get("net_debt")),           _frm(m_b.get("net_debt"))],
    ]
    t = _make_tbl_3col(hdr, raw)
    if t:
        story.append(t)
    story.append(Spacer(1, 4*mm))

    buf = _chart_fcf_capital(m_a, m_b, tkr_a, tkr_b)
    img = Image(buf, width=TABLE_W * 0.85, height=60*mm)
    story.append(KeepTogether([img, Spacer(1, 2*mm), src("FinSight IA / yfinance")]))


def _section_dcf_sensitivity(story, m_a, m_b, tkr_a, tkr_b):
    story.append(CondPageBreak(100*mm))
    story += section_title("Sensibilite Valorisation DCF", "6")

    wacc_a   = float(m_a.get("wacc") or 0.10)
    g_a      = float(m_a.get("terminal_growth") or 0.03)
    base_a   = float(m_a.get("dcf_base") or 0)
    wacc_b   = float(m_b.get("wacc") or 0.10)
    g_b      = float(m_b.get("terminal_growth") or 0.03)
    base_b   = float(m_b.get("dcf_base") or 0)

    text = (
        f"Analyse de sensibilite : variation de la valeur intrinseque selon le WACC et le "
        f"taux de croissance terminal (g). {tkr_a} : WACC base {_frpct(wacc_a)}, g {_frpct(g_a)}. "
        f"{tkr_b} : WACC base {_frpct(wacc_b)}, g {_frpct(g_b)}. "
        f"Les cases en ligne centrale (base) correspondent aux hypotheses du modele DCF. "
        f"Lecture : une hausse du WACC de 1 pt reduit mecaniquement la valeur intrinseque ; "
        f"une baisse du taux terminal penalise davantage les titres de croissance."
    )
    story.append(Paragraph(_safe(text), S_BODY))
    story.append(Spacer(1, 3*mm))

    g_labels = ["-0,5%", "Base", "+0,5%"]
    w_labels = ["WACC -1%", "WACC Base", "WACC +1%"]

    def _sensitivity_tbl(tkr, matrix, wacc, g):
        if not matrix:
            return None
        col_hdr = [
            Paragraph(f"<b>{_enc(tkr)} (g terminal)</b>", S_TH_L),
        ] + [Paragraph(f"<b>{g}</b>", S_TH_C) for g in g_labels]
        rows = [col_hdr]
        for i, w_lbl in enumerate(w_labels):
            is_base_row = (i == 1)
            row_cells = [Paragraph(f"<b>{_enc(w_lbl)}</b>", S_TD_B)]
            for j, val in enumerate(matrix[i]):
                is_base = is_base_row and (j == 1)
                style = _s(f'dcfs{i}{j}', size=8, leading=11,
                           color=NAVY if is_base else BLACK,
                           bold=is_base, align=TA_CENTER)
                row_cells.append(Paragraph(_safe(_enc(str(val))), style))
            rows.append(row_cells)
        t = Table(rows, colWidths=[35*mm, 25*mm, 25*mm, 25*mm])
        t.hAlign = 'LEFT'
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0), NAVY),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [WHITE, ROW_ALT]),
            ('BACKGROUND',    (1, 2), (3, 2), colors.HexColor('#EEF3FA')),
            ('FONTSIZE',      (0, 0), (-1, -1), 8),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING',   (0, 0), (-1, -1), 5),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 5),
            ('GRID',          (0, 0), (-1, -1), 0.3, GREY_MED),
            ('LINEBELOW',     (0, 0), (-1, 0),  0.5, NAVY_LIGHT),
        ]))
        return t

    mat_a = _dcf_sensitivity_matrix(base_a, wacc_a, g_a)
    mat_b = _dcf_sensitivity_matrix(base_b, wacc_b, g_b)

    if mat_a:
        story.append(Paragraph(f"<b>{_enc(tkr_a)}</b> — valeur intrinseque (\u20ac/$)", S_SUBSECTION))
        t_a = _sensitivity_tbl(tkr_a, mat_a, wacc_a, g_a)
        if t_a:
            story.append(t_a)
        story.append(Spacer(1, 4*mm))

    if mat_b:
        story.append(Paragraph(f"<b>{_enc(tkr_b)}</b> — valeur intrinseque (\u20ac/$)", S_SUBSECTION))
        t_b = _sensitivity_tbl(tkr_b, mat_b, wacc_b, g_b)
        if t_b:
            story.append(t_b)
        story.append(Spacer(1, 3*mm))

    story.append(Paragraph(
        "Hypothese : variation proportionnelle via Gordon Growth terminal. "
        "A utiliser en complement du modele DCF complet presente a la section precedente.",
        S_NOTE
    ))
    story.append(Spacer(1, 4*mm))

    # Analyse comparative interpretative
    story.append(Paragraph("<b>Analyse interpretative de la sensibilite</b>", S_SUBSECTION))
    story.append(Spacer(1, 2*mm))

    def _dcf_interp(tkr, wacc, g, base, mat):
        if not mat or base <= 0:
            return f"Les donnees DCF de {_enc(tkr)} sont insuffisantes pour une analyse de sensibilite complete."
        lo_val  = mat[2][0] if mat and len(mat) > 2 and len(mat[2]) > 0 else None
        hi_val  = mat[0][2] if mat and len(mat) > 0 and len(mat[0]) > 2 else None
        spread  = f"{_enc(str(lo_val))} a {_enc(str(hi_val))}" if lo_val and hi_val else "non disponible"
        wacc_s  = f"{wacc*100:.1f} %"
        g_s     = f"{g*100:.1f} %"
        return (
            f"{_enc(tkr)} : avec un WACC de base a {wacc_s} et un taux terminal de {g_s}, "
            f"la fourchette de valeur intrinseque s'etend de {spread}. "
            f"Une hausse de 1 point de WACC comprime significativement la valeur ; "
            f"une baisse du taux g expose davantage les flux distants. "
            f"La ligne centrale correspond aux hypotheses retenues dans le modele principal."
        )

    if mat_a:
        story.append(Paragraph(_dcf_interp(tkr_a, wacc_a, g_a, base_a, mat_a),
                                _s('dcfi_a', size=8.5, leading=13, color=BLACK, sb=0, sa=4)))
    if mat_b:
        story.append(Paragraph(_dcf_interp(tkr_b, wacc_b, g_b, base_b, mat_b),
                                _s('dcfi_b', size=8.5, leading=13, color=BLACK, sb=0, sa=4)))

    story.append(Paragraph(
        "Lecture transversale : comparer les fourchettes des deux societes permet d'identifier "
        "laquelle presente la valorisation la plus sensible aux chocs de taux. Un ecart de spread "
        "plus important signale un profil de flux futurs concentres sur le long terme, "
        "caracteristique des titres de croissance a duration elevee.",
        _s('dcfi_cross', size=8.5, leading=13, color=BLACK)
    ))
    story.append(Spacer(1, 2*mm))
    story.append(src("FinSight IA — calcul interne"))


def _section_momentum_marche(story, m_a, m_b, tkr_a, tkr_b):
    story.append(PageBreak())
    story += section_title("Momentum & Marche", "8")

    p1m_a  = _frpct(m_a.get("perf_1m"), True)
    p1m_b  = _frpct(m_b.get("perf_1m"), True)
    p1y_a  = _frpct(m_a.get("perf_1y"), True)
    p1y_b  = _frpct(m_b.get("perf_1y"), True)
    var_a  = _frpct(m_a.get("var_95_1m"))
    var_b  = _frpct(m_b.get("var_95_1m"))

    text = (
        f"Profil de momentum : {tkr_a} affiche {p1m_a} sur 1 mois et {p1y_a} sur 12 mois "
        f"vs {p1m_b} et {p1y_b} pour {tkr_b}. "
        f"La VaR 95 % mensuelle estimee est de {var_a} pour {tkr_a} vs {var_b} pour {tkr_b}. "
        f"Ces indicateurs refletent le sentiment court terme et la volatilite des actifs."
    )
    story.append(Paragraph(_safe(text), S_BODY))
    story.append(Spacer(1, 3*mm))

    hdr = [
        Paragraph("<b>Marche</b>", S_TH_L),
        Paragraph(f"<b>{_enc(tkr_a)}</b>", S_TH_C),
        Paragraph(f"<b>{_enc(tkr_b)}</b>", S_TH_C),
    ]
    raw = [
        ["Cours actuel",       str(m_a.get("price_str") or "\u2014"),  str(m_b.get("price_str") or "\u2014")],
        ["Plus haut 52 sem.",  _fr(m_a.get("week52_high"), 2),         _fr(m_b.get("week52_high"), 2)],
        ["Plus bas 52 sem.",   _fr(m_a.get("week52_low"), 2),          _fr(m_b.get("week52_low"), 2)],
        ["Perf. 1 mois",       _frpct(m_a.get("perf_1m"), True),       _frpct(m_b.get("perf_1m"), True)],
        ["Perf. 3 mois",       _frpct(m_a.get("perf_3m"), True),       _frpct(m_b.get("perf_3m"), True)],
        ["Perf. 12 mois",      _frpct(m_a.get("perf_1y"), True),       _frpct(m_b.get("perf_1y"), True)],
        ["VaR 95 % (1 mois)",  _frpct(m_a.get("var_95_1m")),           _frpct(m_b.get("var_95_1m"))],
        ["Vol. moyen 30j (M)", _fr(m_a.get("avg_volume_30d"), 1),      _fr(m_b.get("avg_volume_30d"), 1)],
        ["Prochains resultats",str(m_a.get("next_earnings_date") or "\u2014"),
                               str(m_b.get("next_earnings_date") or "\u2014")],
        ["Sentiment",          _fmt_sentiment(m_a.get("sentiment_label")),
                               _fmt_sentiment(m_b.get("sentiment_label"))],
    ]
    t = _make_tbl_3col(hdr, raw)
    if t:
        story.append(t)
    story.append(Spacer(1, 4*mm))

    buf = _chart_perf_bars(m_a, m_b, tkr_a, tkr_b)
    img = Image(buf, width=TABLE_W * 0.85, height=60*mm)
    story.append(KeepTogether([img, Spacer(1, 2*mm), src("FinSight IA / yfinance")]))
    story.append(Spacer(1, 3*mm))
    # Lecture analytique momentum
    p1y_a = _frpct(m_a.get("perf_1y"), True); p1y_b = _frpct(m_b.get("perf_1y"), True)
    p3m_a = _frpct(m_a.get("perf_3m"), True); p3m_b = _frpct(m_b.get("perf_3m"), True)
    var_a = _frpct(m_a.get("var_95_1m")); var_b = _frpct(m_b.get("var_95_1m"))
    vol_a = _frpct(m_a.get("volatility_52w")); vol_b = _frpct(m_b.get("volatility_52w"))
    rsi_a   = _fr(m_a.get("rsi"), 1);  rsi_b   = _fr(m_b.get("rsi"), 1)
    hi52_a  = _fr(m_a.get("week52_high"), 2); lo52_a = _fr(m_a.get("week52_low"), 2)
    hi52_b  = _fr(m_b.get("week52_high"), 2); lo52_b = _fr(m_b.get("week52_low"), 2)
    try:
        _p1y_a_f = float(str(m_a.get("perf_1y") or 0))
        _p1y_b_f = float(str(m_b.get("perf_1y") or 0))
        _p3m_a_f = float(str(m_a.get("perf_3m") or 0))
        _p3m_b_f = float(str(m_b.get("perf_3m") or 0))
        _leader = tkr_a if _p1y_a_f > _p1y_b_f else tkr_b
        _laggard = tkr_b if _leader == tkr_a else tkr_a
        _mom3m_leader = tkr_a if _p3m_a_f > _p3m_b_f else tkr_b
        _rsi_a_f = float(str(m_a.get("rsi") or 50))
        _rsi_b_f = float(str(m_b.get("rsi") or 50))
        def _rsi_comment(rsi_f, tkr):
            if rsi_f >= 70: return f"{_enc(tkr)} est en territoire de surachat (RSI {rsi_f:.0f})"
            if rsi_f <= 30: return f"{_enc(tkr)} est en zone de survente (RSI {rsi_f:.0f})"
            return f"{_enc(tkr)} affiche un RSI neutre ({rsi_f:.0f})"
        momentum_analysis = (
            f"<b>Lecture analytique :</b> Sur 12 mois, {_enc(_leader)} surperforme avec "
            f"{p1y_a if _leader == tkr_a else p1y_b} vs {p1y_b if _leader == tkr_a else p1y_a} "
            f"pour {_enc(_laggard)}. Sur 3 mois, c'est {_enc(_mom3m_leader)} qui prend la tete "
            f"({p3m_a if _mom3m_leader == tkr_a else p3m_b} vs "
            f"{p3m_b if _mom3m_leader == tkr_a else p3m_a}), "
            f"signalant un changement potentiel de dynamique. "
            f"Techniquement, {_rsi_comment(_rsi_a_f, tkr_a)} et "
            f"{_rsi_comment(_rsi_b_f, tkr_b)}. "
            f"La VaR 95 % mensuelle ({var_a} pour {_enc(tkr_a)} vs {var_b} pour {_enc(tkr_b)}) "
            f"et la volatilite annualisee ({vol_a} vs {vol_b}) permettent de calibrer "
            f"le dimensionnement de position : une VaR plus elevee impose une ponderation "
            f"reduite pour maintenir un budget risque equivalent en portefeuille. "
            f"Le sentiment de marche ressort {_fmt_sentiment(m_a.get('sentiment_label'))} "
            f"pour {_enc(tkr_a)} et {_fmt_sentiment(m_b.get('sentiment_label'))} pour {_enc(tkr_b)}."
        )
    except Exception:
        momentum_analysis = (
            f"L'analyse croisee des performances et de la volatilite de {_enc(tkr_a)} et "
            f"{_enc(tkr_b)} permet d'evaluer l'efficience risque/rendement de chaque titre "
            f"dans une optique de construction de portefeuille."
        )
    story.append(Paragraph(momentum_analysis.replace('&', '&amp;'), S_BODY))


def _section_52w_price(story, m_a, m_b, tkr_a, tkr_b, synthesis=None):
    """Section : graphique de cours 52 semaines normalise + texte analytique."""
    story.append(CondPageBreak(80*mm))
    story += section_title("Evolution Boursiere 52 Semaines", "9")

    # Texte introductif
    p1m_a  = _frpct(m_a.get("perf_1m"), True)
    p3m_a  = _frpct(m_a.get("perf_3m"), True)
    p1y_a  = _frpct(m_a.get("perf_1y"), True)
    p1m_b  = _frpct(m_b.get("perf_1m"), True)
    p3m_b  = _frpct(m_b.get("perf_3m"), True)
    p1y_b  = _frpct(m_b.get("perf_1y"), True)
    hi_a   = _fr(m_a.get("week52_high"), 2)
    lo_a   = _fr(m_a.get("week52_low"), 2)
    hi_b   = _fr(m_b.get("week52_high"), 2)
    lo_b   = _fr(m_b.get("week52_low"), 2)
    vol_a  = _frpct(m_a.get("volatility_52w"))
    vol_b  = _frpct(m_b.get("volatility_52w"))

    intro = (
        f"Le graphique ci-dessous presente l'evolution des cours de {_enc(tkr_a)} et {_enc(tkr_b)} "
        f"sur les 52 dernieres semaines, normalises en base 100. Cette representation permet "
        f"de comparer directement la dynamique relative des deux titres independamment de leur "
        f"niveau de prix absolu."
    )
    story.append(Paragraph(_safe(intro), S_BODY))
    story.append(Spacer(1, 3*mm))

    # Graphique 52W normalise
    if _MPL:
        try:
            import yfinance as yf
            import matplotlib.dates as mdates
            from datetime import datetime, timedelta

            end = datetime.today()
            start = end - timedelta(days=370)
            df_a = yf.download(tkr_a, start=start, end=end, progress=False, auto_adjust=True)
            df_b = yf.download(tkr_b, start=start, end=end, progress=False, auto_adjust=True)

            if not (df_a.empty and df_b.empty):
                fig, ax = plt.subplots(figsize=(10, 4))
                fig.patch.set_facecolor('white')
                ax.set_facecolor('#FAFAFA')
                ca = '#2E5FA3'; cb = '#C9A227'
                if not df_a.empty:
                    close_a = df_a['Close'].squeeze()
                    base_a = close_a.iloc[0]
                    if base_a and base_a > 0:
                        ax.plot(close_a.index, close_a / base_a * 100,
                                color=ca, linewidth=1.8, label=tkr_a)
                if not df_b.empty:
                    close_b = df_b['Close'].squeeze()
                    base_b = close_b.iloc[0]
                    if base_b and base_b > 0:
                        ax.plot(close_b.index, close_b / base_b * 100,
                                color=cb, linewidth=1.8, label=tkr_b)
                ax.axhline(y=100, color='#BBBBBB', linestyle='--', linewidth=0.9, alpha=0.7)
                try:
                    _p52_a = ((close_a.iloc[-1] / close_a.iloc[0]) - 1) * 100 if not df_a.empty else None
                    _p52_b = ((close_b.iloc[-1] / close_b.iloc[0]) - 1) * 100 if not df_b.empty else None
                    if _p52_a is not None and _p52_b is not None:
                        _52_ldr = tkr_a if _p52_a > _p52_b else tkr_b
                        _52_t = f"52 semaines : {tkr_a} {_p52_a:+.1f}% vs {tkr_b} {_p52_b:+.1f}% — {_52_ldr} surperforme"
                    else:
                        _52_t = f'Performance Relative 52 Semaines — {tkr_a} vs {tkr_b} (base 100)'
                except Exception:
                    _52_t = f'Performance Relative 52 Semaines — {tkr_a} vs {tkr_b} (base 100)'
                ax.set_title(_52_t, fontsize=10, fontweight='bold', color='#1B3A6B', pad=5)
                ax.set_ylabel('Base 100', fontsize=8)
                ax.legend(fontsize=9, frameon=False)
                ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
                ax.tick_params(labelsize=8)
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))
                ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
                plt.xticks(rotation=25, ha='right')
                fig.tight_layout(pad=1.0)
                buf = io.BytesIO()
                fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
                plt.close(fig); buf.seek(0)
                img = Image(buf, width=TABLE_W, height=70*mm)
                story.append(KeepTogether([img, Spacer(1, 2*mm), src("FinSight IA / yfinance")]))
                story.append(Spacer(1, 4*mm))
        except Exception as e:
            log.warning(f"[cmp_pdf] 52w chart error: {e}")
            story.append(Spacer(1, 3*mm))

    # Tendance globale et points cles
    story.append(Paragraph("<b>Tendance et dynamique de marche</b>", S_SUBSECTION))
    story.append(Spacer(1, 2*mm))

    def _trend_txt(tkr, m):
        """Generate trend analysis text for one ticker."""
        p1y = m.get("perf_1y")
        price = m.get("share_price")
        hi = m.get("week52_high")
        lo = m.get("week52_low")
        parts = []
        # Overall trend
        if p1y is not None:
            try:
                fp = float(p1y)
                if fp > 0.15:
                    parts.append(f"{_enc(tkr)} affiche une tendance haussiere marquee sur 12 mois ({_frpct(p1y, True)})")
                elif fp > 0.03:
                    parts.append(f"{_enc(tkr)} evolue en tendance haussiere moderee ({_frpct(p1y, True)})")
                elif fp > -0.03:
                    parts.append(f"{_enc(tkr)} est en phase laterale ({_frpct(p1y, True)})")
                elif fp > -0.15:
                    parts.append(f"{_enc(tkr)} evolue en tendance baissiere moderee ({_frpct(p1y, True)})")
                else:
                    parts.append(f"{_enc(tkr)} subit une tendance baissiere prononcee ({_frpct(p1y, True)})")
            except Exception:
                pass
        # Drawdown from 52W high
        if price and hi:
            try:
                dd = (float(price) - float(hi)) / float(hi)
                if dd < -0.05:
                    parts.append(f"en retrait de {abs(dd)*100:.1f} % par rapport au plus haut 52 semaines ({_fr(hi, 2)})".replace(".", ","))
                else:
                    parts.append(f"proche de son plus haut 52 semaines ({_fr(hi, 2)})")
            except Exception:
                pass
        # Recovery from 52W low
        if price and lo:
            try:
                rec = (float(price) - float(lo)) / float(lo)
                if rec > 0.20:
                    parts.append(f"en hausse de {rec*100:.1f} % depuis le plus bas 52 semaines ({_fr(lo, 2)})".replace(".", ","))
            except Exception:
                pass
        if parts:
            return ". ".join(parts) + "."
        return f"{_enc(tkr)} : donnees de tendance indisponibles."

    trend_a = _trend_txt(tkr_a, m_a)
    trend_b = _trend_txt(tkr_b, m_b)
    story.append(Paragraph(_safe(trend_a),
                            _s('trend_a', size=8.5, leading=13, color=BLACK, sb=0, sa=3)))
    story.append(Paragraph(_safe(trend_b),
                            _s('trend_b', size=8.5, leading=13, color=BLACK, sb=0, sa=3)))
    story.append(Spacer(1, 2*mm))

    # Contexte macro et interpretation fondamentale
    _sec_a = m_a.get("sector_a") or m_a.get("sector") or ""
    _sec_b = m_b.get("sector_b") or m_b.get("sector") or ""
    _pe_a  = m_a.get("pe_ratio") or m_a.get("pe_trailing")
    _pe_b  = m_b.get("pe_ratio") or m_b.get("pe_trailing")
    _eg_a  = m_a.get("earnings_growth")
    _eg_b  = m_b.get("earnings_growth")
    _beta_a = m_a.get("beta")
    _beta_b = m_b.get("beta")

    _macro_parts = []
    # Contexte taux / cycle
    _macro_parts.append(
        "Dans un environnement de taux directeurs normalises et d'inflation moderee, "
        "les marches actions discriminent davantage entre les profils de croissance et "
        "la qualite des fondamentaux."
    )
    # Lecture sectorielle
    if _sec_a and _sec_b:
        if _sec_a == _sec_b:
            _macro_parts.append(
                f"Les deux valeurs evoluent dans le meme secteur ({_sec_a}), "
                f"la divergence de trajectoire reflete donc des dynamiques propres "
                f"(mix produits, geographies, execution) plutot qu'une rotation sectorielle."
            )
        else:
            _macro_parts.append(
                f"La difference sectorielle ({_sec_a} vs {_sec_b}) implique des sensibilites "
                f"macro distinctes — les flux de rotation sectorielle expliquent une partie "
                f"de la divergence observee."
            )
    # Lecture valorisation
    if _pe_a and _pe_b:
        try:
            _pa, _pb = float(_pe_a), float(_pe_b)
            if _pa > 0 and _pb > 0:
                _leader_pe = tkr_a if _pa < _pb else tkr_b
                _macro_parts.append(
                    f"{_enc(_leader_pe)} offre un profil de valorisation plus attractif "
                    f"(P/E {min(_pa,_pb):.1f}x vs {max(_pa,_pb):.1f}x), suggerant une asymetrie "
                    f"risque/rendement favorable si la croissance des resultats se maintient."
                )
        except (ValueError, TypeError):
            pass
    # Beta / sensibilite
    if _beta_a and _beta_b:
        try:
            _ba, _bb = float(_beta_a), float(_beta_b)
            _defensif = tkr_a if _ba < _bb else tkr_b
            _cyclique = tkr_b if _ba < _bb else tkr_a
            _macro_parts.append(
                f"En termes de profil de risque, {_enc(_defensif)} (beta {min(_ba,_bb):.2f}) "
                f"offre un caractere plus defensif tandis que {_enc(_cyclique)} (beta {max(_ba,_bb):.2f}) "
                f"amplifie les mouvements de marche — un parametre cle pour le sizing de position."
            )
        except (ValueError, TypeError):
            pass

    # Narratif LLM si disponible (contexte macro reel), sinon fallback template
    _llm_narrative = (synthesis or {}).get("price_narrative", "")
    if _llm_narrative and len(_llm_narrative) > 30:
        story.append(Paragraph(
            f"<b>Contexte macro et dynamique de marche.</b> {_safe(_llm_narrative)}",
            _s('macro_ctx', size=8.5, leading=13, color=BLACK, sb=0, sa=4)))
    elif _macro_parts:
        _macro_text = " ".join(_macro_parts)
        story.append(Paragraph(
            f"<b>Contexte macro et lecture fondamentale.</b> {_safe(_macro_text)}",
            _s('macro_ctx', size=8.5, leading=13, color=BLACK, sb=0, sa=4)))
    story.append(Spacer(1, 3*mm))

    # Analyse chiffree des deux titres
    story.append(Paragraph("<b>Lecture analytique</b>", S_SUBSECTION))
    story.append(Spacer(1, 2*mm))

    ana_a = (
        f"<b>{_enc(tkr_a)}</b> : Le titre a evolue entre {lo_a} et {hi_a} sur 52 semaines, "
        f"affichant une performance de {p1m_a} sur 1 mois, {p3m_a} sur 3 mois et {p1y_a} sur "
        f"12 mois. La volatilite annualisee ressort a {vol_a}, reflectant "
        + ("un titre relativement stable adapte aux profils prudents."
           if m_a.get("volatility_52w") is not None and float(m_a.get("volatility_52w") or 0.3) < 0.25
           else "un niveau de risque de prix notable qu'il convient d'integrer dans le dimensionnement de position.")
    )
    ana_b = (
        f"<b>{_enc(tkr_b)}</b> : Le titre a evolue entre {lo_b} et {hi_b} sur 52 semaines, "
        f"avec des performances de {p1m_b} sur 1 mois, {p3m_b} sur 3 mois et {p1y_b} sur "
        f"12 mois. La volatilite annualisee de {vol_b} "
        + ("indique un comportement de cours contenu, favorable aux strategies de portage."
           if m_b.get("volatility_52w") is not None and float(m_b.get("volatility_52w") or 0.3) < 0.25
           else "signale une amplitude de prix elevee, coherente avec un profil de croissance ou de retournement.")
    )
    story.append(Paragraph(_enc(ana_a),
                            _s('52w_a', size=8.5, leading=13, color=BLACK, sb=0, sa=4)))
    story.append(Paragraph(_enc(ana_b),
                            _s('52w_b', size=8.5, leading=13, color=BLACK, sb=0, sa=4)))

    # Comparaison relative
    def _better_perf(v_a, v_b):
        try:
            fa = float(v_a or 0); fb = float(v_b or 0)
            if fa > fb: return tkr_a
            if fb > fa: return tkr_b
            return None
        except: return None

    leader_1y = _better_perf(m_a.get("perf_1y"), m_b.get("perf_1y"))
    leader_3m = _better_perf(m_a.get("perf_3m"), m_b.get("perf_3m"))
    if leader_1y or leader_3m:
        comp_parts = []
        if leader_1y:
            comp_parts.append(
                f"{_enc(leader_1y)} surperforme sur 12 mois ({p1y_a if leader_1y == tkr_a else p1y_b})"
            )
        if leader_3m:
            comp_parts.append(
                f"{_enc(leader_3m)} affiche le meilleur momentum recent sur 3 mois "
                f"({p3m_a if leader_3m == tkr_a else p3m_b})"
            )
        cross = "Sur la periode consideree : " + " ; ".join(comp_parts) + "."
        story.append(Paragraph(_safe(cross),
                                _s('52w_cross', size=8.5, leading=13, color=BLACK)))
    story.append(Spacer(1, 2*mm))


def _section_piotroski_detail(story, m_a, m_b, tkr_a, tkr_b):
    story.append(CondPageBreak(100*mm))
    story += section_title("Analyse Piotroski F-Score", "10")

    pio_a = m_a.get("piotroski_score")
    pio_b = m_b.get("piotroski_score")
    pio_a_str = str(int(float(pio_a))) if pio_a is not None else "\u2014"
    pio_b_str = str(int(float(pio_b))) if pio_b is not None else "\u2014"

    def _pio_level(s):
        if s is None: return "indetermine"
        try:
            iv = int(float(s))
            if iv >= 7: return "solide (>= 7)"
            if iv >= 5: return "correct (5-6)"
            if iv >= 4: return "limite (4)"
            return "fragile (<= 3)"
        except: return "indetermine"

    text = (
        f"Le Piotroski F-Score evalue la solidite financiere d'une entreprise sur "
        f"9 criteres binaires repartis en 3 categories. "
        f"{tkr_a} obtient {pio_a_str}/9 ({_pio_level(pio_a)}) | "
        f"{tkr_b} obtient {pio_b_str}/9 ({_pio_level(pio_b)}). "
        f"-- Rentabilite (4 criteres) : ROA positif (generation de profit sur actifs), "
        f"CFO positif (cash operationnel reel), amelioration du ROA vs N-1, "
        f"et accruals < 0 (qualite des benefices : le cash prime sur le resultat comptable). "
        f"-- Levier & Liquidite (3 criteres) : reduction du ratio d'endettement, "
        f"amelioration du ratio de liquidite courante, et absence de dilution actionnariale. "
        f"Ces criteres signalent la robustesse bilancielle et la discipline financiere. "
        f"-- Efficacite operationnelle (2 criteres) : amelioration de la marge brute "
        f"et de la rotation des actifs, traduisant une meilleure productivite industrielle. "
        f"Un score >= 7 distingue les entreprises financierement saines des cas a risque (<= 3)."
    )
    def _pio_cell(v):
        if v is None:
            return Paragraph("\u2014", S_TD_C)
        try:
            iv = int(float(v))
            if iv == 1:
                return Paragraph(
                    "<font color='#1A7A4A'><b>\u2713 1</b></font>",
                    _s('piog', size=8, leading=11, color=BUY_GREEN, bold=True, align=TA_CENTER)
                )
            else:
                return Paragraph(
                    "<font color='#A82020'><b>\u2717 0</b></font>",
                    _s('pior', size=8, leading=11, color=SELL_RED, bold=True, align=TA_CENTER)
                )
        except:
            return Paragraph("\u2014", S_TD_C)

    criteria = [
        ("Rentabilite", None, None),
        ("ROA positif",            m_a.get("pio_roa_positive"),         m_b.get("pio_roa_positive")),
        ("CFO positif",            m_a.get("pio_cfo_positive"),         m_b.get("pio_cfo_positive")),
        ("Delta ROA (amelioration)",m_a.get("pio_delta_roa"),           m_b.get("pio_delta_roa")),
        ("Accruals (CFO > NI)",    m_a.get("pio_accruals"),             m_b.get("pio_accruals")),
        ("Levier / Liquidite", None, None),
        ("Delta Levier (reduction)",m_a.get("pio_delta_leverage"),      m_b.get("pio_delta_leverage")),
        ("Delta Liquidite (hausse)",m_a.get("pio_delta_liquidity"),     m_b.get("pio_delta_liquidity")),
        ("Pas de dilution",        m_a.get("pio_no_dilution"),          m_b.get("pio_no_dilution")),
        ("Efficacite Operationnelle", None, None),
        ("Delta Marge Brute",      m_a.get("pio_delta_gross_margin"),   m_b.get("pio_delta_gross_margin")),
        ("Delta Rotation Actif",   m_a.get("pio_delta_asset_turnover"), m_b.get("pio_delta_asset_turnover")),
    ]

    S_CAT = _s('pioc', size=8, leading=11, color=WHITE, bold=True, align=TA_LEFT)
    hdr_pio = [
        Paragraph("<b>Critere Piotroski</b>", S_TH_L),
        Paragraph(f"<b>{_enc(tkr_a)}</b>", S_TH_C),
        Paragraph(f"<b>{_enc(tkr_b)}</b>", S_TH_C),
    ]
    rows_pio = [hdr_pio]
    for label, va, vb in criteria:
        if va is None and vb is None:
            # sous-titre categorie
            rows_pio.append([
                Paragraph(f"<b>{_safe(_enc(label))}</b>", S_CAT),
                Paragraph("", S_CAT),
                Paragraph("", S_CAT),
            ])
        else:
            rows_pio.append([
                Paragraph(_safe(_enc(label)), S_TD_B),
                _pio_cell(va),
                _pio_cell(vb),
            ])

    t_pio = Table(rows_pio, colWidths=[90*mm, 40*mm, 40*mm])
    # Build style dynamically
    ts = [
        ('BACKGROUND',    (0, 0), (-1, 0), NAVY),
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
    ]
    # Colorier les sous-titres catégorie en navy
    for i, (label, va, vb) in enumerate(criteria, start=1):
        if va is None and vb is None:
            ts.append(('BACKGROUND', (0, i), (-1, i), NAVY_LIGHT))
    t_pio.setStyle(TableStyle(ts))
    story.append(t_pio)
    story.append(Spacer(1, 3*mm))

    # Texte analytique sous le tableau
    story.append(Paragraph(_safe(text), S_BODY))
    story.append(Spacer(1, 3*mm))

    # Barre score total
    score_text = (
        f"Score total : {tkr_a} {pio_a_str}/9 vs {tkr_b} {pio_b_str}/9. "
        f"Un score >= 7 indique une amelioration de la sante financiere. "
        f"Sources : etats financiers yfinance (exercice le plus recent disponible)."
    )
    story.append(Paragraph(_safe(score_text), S_NOTE))
    story.append(Spacer(1, 2*mm))
    story.append(src("FinSight IA / yfinance"))


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

        # Page 1 : Couverture (flowables, style secteur)
        story += _build_cover_story(tkr_a, tkr_b, name_a, name_b,
                                    rec_a, rec_b, date_str, m_a, m_b, synthesis)

        # Pages suivantes : Sections de contenu
        _section_exec_summary(story, m_a, m_b, synthesis, tkr_a, tkr_b)       # 1
        _section_profil_pl(story, m_a, m_b, synthesis, tkr_a, tkr_b)          # 2
        _section_rentabilite_bilan(story, m_a, m_b, tkr_a, tkr_b)             # 3
        _section_fcf_capital(story, m_a, m_b, tkr_a, tkr_b)                   # 4
        _section_valorisation(story, m_a, m_b, synthesis, tkr_a, tkr_b)       # 5
        _section_dcf_sensitivity(story, m_a, m_b, tkr_a, tkr_b)               # 6
        _section_qualite_risque(story, m_a, m_b, synthesis, tkr_a, tkr_b)     # 7
        _section_momentum_marche(story, m_a, m_b, tkr_a, tkr_b)               # 8
        _section_52w_price(story, m_a, m_b, tkr_a, tkr_b, synthesis)          # 9
        _section_piotroski_detail(story, m_a, m_b, tkr_a, tkr_b)             # 10
        _section_verdict(story, m_a, m_b, synthesis, tkr_a, tkr_b)           # 11

        # Build : header/footer sur toutes les pages (y compris cover)
        def _on_later(canvas, doc):
            canvas.saveState()
            _header_footer(canvas, doc)

        doc.build(story, onFirstPage=_on_later, onLaterPages=_on_later)
        buf.seek(0)
        log.info(f"[cmp_pdf] genere en memoire ({buf.getbuffer().nbytes} bytes)")
        return buf
