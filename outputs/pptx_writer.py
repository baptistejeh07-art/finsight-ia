# =============================================================================
# FinSight IA — PPTX Writer (Pitchbook 20 slides)
# outputs/pptx_writer.py
#
# Genere un pitchbook IB professionnel en 20 slides via python-pptx.
# Utilise le FinSightState (dict) produit par le pipeline LangGraph.
#
# Usage :
#   writer = PPTXWriter()
#   path   = writer.generate(state, output_path)
# =============================================================================

from __future__ import annotations

import io
import logging
import math
import statistics
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Palette couleurs
# ---------------------------------------------------------------------------

NAVY       = "1B3A6B"
NAVY_MID   = "2E5FA3"
NAVY_PALE  = "EEF3FA"
GREEN      = "1A7A4A"
GREEN_PALE = "EAF4EF"
RED        = "A82020"
RED_PALE   = "FAF0EF"
AMBER      = "B06000"
AMBER_PALE = "FDF6E8"
WHITE      = "FFFFFF"
GREY_BG    = "F7F8FA"
GREY_TXT   = "555555"
GREY_LIGHT = "888888"
BLACK      = "0D0D0D"


# ---------------------------------------------------------------------------
# Imports pptx (lazy-guardés dans PPTXWriter.generate)
# ---------------------------------------------------------------------------

def _lazy_imports():
    from pptx import Presentation
    from pptx.util import Cm, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    return Presentation, Cm, Pt, Emu, RGBColor, PP_ALIGN


# ---------------------------------------------------------------------------
# Sanitisation XML — supprime les caractères interdits en XML 1.0
# Source courante : texte LLM ou API contenant des chars de contrôle
# ---------------------------------------------------------------------------

import re as _re

def _x(text) -> str:
    """Supprime les caractères invalides XML 1.0 (0x00-0x08, 0x0B-0x0C, 0x0E-0x1F, 0x7F)."""
    if text is None:
        return ""
    s = str(text)
    return _re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', s)


# ---------------------------------------------------------------------------
# Helpers couleur
# ---------------------------------------------------------------------------

def rgb(hex_str: str):
    from pptx.dml.color import RGBColor
    h = hex_str.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# ---------------------------------------------------------------------------
# Helpers mise en forme des nombres
# ---------------------------------------------------------------------------

def _fr(v, dp: int = 1, suffix: str = "") -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):,.{dp}f}".replace(",", " ").replace(".", ",") + suffix
    except Exception:
        return "—"


def _frm(v, cur_sym: str = "$") -> str:
    if v is None:
        return "—"
    try:
        v = float(v)
        # Guard : LLM peut envoyer des valeurs en EUR/USD absolus (ex: 195_000_000_000)
        # au lieu de millions (195_000). Si > 1e9, on normalise en millions.
        if abs(v) > 1_000_000_000:
            v = v / 1_000_000
        if cur_sym == "EUR":
            sym_big, sym_small = "Md\u20ac", "M\u20ac"
        else:
            sym_big, sym_small = "Mds" + cur_sym, "M" + cur_sym
        if abs(v) >= 1000:
            return _fr(v / 1000, 1) + " " + sym_big
        return _fr(v, 0) + " " + sym_small
    except Exception:
        return "—"


def _frn(v) -> str:
    """Formate un montant en millions -> toujours converti en Mds avec 1 décimale."""
    if v is None:
        return "—"
    try:
        v = float(v)
        if abs(v) > 1_000_000_000:  # guard LLM valeurs absolues
            v = v / 1_000_000
        return _fr(v / 1000, 1)
    except Exception:
        return "—"


def _frpct(v, signed: bool = False) -> str:
    if v is None:
        return "—"
    try:
        s = f"{float(v) * 100:+.1f}" if signed else f"{float(v) * 100:.1f}"
        return s.replace(".", ",") + " %"
    except Exception:
        return "—"


def _frpct_margin(v) -> str:
    """Like _frpct but guards against values already in percentage form (e.g. 65.0 vs 0.65).
    Used for gross_margin / ebitda_margin from inconsistent data sources."""
    if v is None:
        return "—"
    try:
        fv = float(v)
        # If |value| > 2.0 (i.e. > 200%), assume already-percentage form — divide by 100.
        # No real gross/EBITDA margin can exceed 200%, so threshold is safe.
        if abs(fv) > 2.0:
            fv = fv / 100.0
        s = f"{fv * 100:.1f}"
        return s.replace(".", ",") + " %"
    except Exception:
        return "—"


def _frx(v) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.1f}".replace(".", ",") + "x"
    except Exception:
        return "—"


def _upside(target, current) -> str:
    if not target or not current:
        return "—"
    try:
        return f"{(float(target) / float(current) - 1) * 100:+.1f}".replace(".", ",") + " %"
    except Exception:
        return "—"


def _g(obj, attr, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _valid_years(snap) -> list:
    """Retourne les annees triees qui ont au moins une donnee reelle (exclut les annees all-None)."""
    if not (snap and snap.years):
        return []
    result = []
    for y, fy in snap.years.items():
        if fy is None:
            continue
        if any(getattr(fy, attr, None) is not None
               for attr in ("revenue", "cash", "da", "interest_expense")):
            result.append(y)
    return sorted(result, key=lambda y: str(y).replace("_LTM", ""))


# ---------------------------------------------------------------------------
# Helpers XML (transparence, fond slide)
# ---------------------------------------------------------------------------

def _set_slide_bg(slide, hex_color: str):
    """Definit le fond du slide via <p:bgPr> (approche native, comme la référence)."""
    from pptx.oxml.ns import qn
    from lxml import etree
    cSld = slide._element.find(qn('p:cSld'))
    if cSld is None:
        return
    existing = cSld.find(qn('p:bg'))
    if existing is not None:
        cSld.remove(existing)
    bg_xml = (
        '<p:bg xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
        ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<p:bgPr>'
        f'<a:solidFill><a:srgbClr val="{hex_color}"/></a:solidFill>'
        '<a:effectLst/>'
        '</p:bgPr>'
        '</p:bg>'
    )
    bg_elem = etree.fromstring(bg_xml)
    spTree = cSld.find(qn('p:spTree'))
    cSld.insert(list(cSld).index(spTree) if spTree is not None else 0, bg_elem)


def _add_text_alpha(slide, x, y, w, h, text, font_size,
                    color_hex="FFFFFF", alpha_val=15000, bold=False):
    """Ajoute un textbox avec couleur semi-transparente (alpha en millièmes, 15000=15%)."""
    from pptx.util import Cm, Pt
    from pptx.oxml.ns import qn
    from lxml import etree

    txBox = slide.shapes.add_textbox(Cm(x), Cm(y), Cm(w), Cm(h))
    tf = txBox.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = _x(text)
    run.font.name  = "Calibri"
    run.font.size  = Pt(font_size)
    run.font.bold  = bold

    # Injection XML directe (plus fiable que get_or_add_rPr + string parsing)
    r_elem = run._r                          # <a:r>
    rPr = r_elem.find(qn('a:rPr'))
    if rPr is None:
        rPr = etree.Element(qn('a:rPr'))
        r_elem.insert(0, rPr)

    # Supprimer toute couleur existante
    for tag in (qn('a:solidFill'), qn('a:gradFill'), qn('a:noFill'), qn('a:pattFill')):
        for child in list(rPr.findall(tag)):
            rPr.remove(child)

    # Construire solidFill > srgbClr > alpha via SubElement (évite les pb de namespace)
    solidFill  = etree.SubElement(rPr, qn('a:solidFill'))
    srgbClr    = etree.SubElement(solidFill, qn('a:srgbClr'))
    srgbClr.set('val', color_hex.upper())
    alpha_elem = etree.SubElement(srgbClr, qn('a:alpha'))
    alpha_elem.set('val', str(alpha_val))
    # Mettre solidFill en premier dans rPr
    rPr.remove(solidFill)
    rPr.insert(0, solidFill)

    return txBox


# ---------------------------------------------------------------------------
# Helpers formes pptx
# ---------------------------------------------------------------------------

def add_rect(slide, x, y, w, h, fill_hex, line_hex=None, line_width_pt=0):
    from pptx.util import Cm, Pt
    shape = slide.shapes.add_shape(1, Cm(x), Cm(y), Cm(w), Cm(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(fill_hex)
    if line_hex:
        shape.line.color.rgb = rgb(line_hex)
        shape.line.width = Pt(line_width_pt)
    else:
        shape.line.fill.background()
    return shape


def add_text_box(slide, x, y, w, h, text, font_size=10, color_hex=BLACK,
                 bold=False, italic=False, align=None,
                 font_name="Calibri", wrap=True):
    from pptx.util import Cm, Pt
    from pptx.enum.text import PP_ALIGN
    if align is None:
        align = PP_ALIGN.LEFT
    txBox = slide.shapes.add_textbox(Cm(x), Cm(y), Cm(w), Cm(h))
    tf = txBox.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = _x(text) if text is not None else "—"
    run.font.name = font_name
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = rgb(color_hex)
    return txBox


def add_multiline_text_box(slide, x, y, w, h, lines, font_size=8.5,
                           color_hex=BLACK, font_name="Calibri", wrap=True):
    """Text box avec plusieurs paragraphes (list of str)."""
    from pptx.util import Cm, Pt
    from pptx.enum.text import PP_ALIGN
    txBox = slide.shapes.add_textbox(Cm(x), Cm(y), Cm(w), Cm(h))
    tf = txBox.text_frame
    tf.word_wrap = wrap
    first = True
    for line in lines:
        if first:
            p = tf.paragraphs[0]
            first = False
        else:
            p = tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = _x(line) if line is not None else ""
        run.font.name = font_name
        run.font.size = Pt(font_size)
        run.font.color.rgb = rgb(color_hex)
    return txBox


def _set_cell(cell, text, font_size=8, bold=False, color_hex=BLACK,
              fill_hex=None, align=None, font_name="Calibri", italic=False):
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    if align is None:
        align = PP_ALIGN.CENTER
    if fill_hex:
        cell.fill.solid()
        cell.fill.fore_color.rgb = rgb(fill_hex)
    # Clear existing content then add styled run
    tf = cell.text_frame
    for para in tf.paragraphs:
        for run in list(para.runs):
            para._p.remove(run._r)
    para = tf.paragraphs[0]
    para.alignment = align
    run = para.add_run()
    run.text = _x(text) if text is not None else "\u2014"
    run.font.name = font_name
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = rgb(color_hex)


def _apply_cell_borders(tbl, total_rows, num_cols, hex_color="DDDDDD", width_pt=0.5):
    from pptx.oxml.ns import qn
    from lxml import etree
    w_emu = str(int(width_pt * 12700))
    ns = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
    ln_xml = (
        f'<a:ln {ns} w="{w_emu}">'
        f'<a:solidFill><a:srgbClr val="{hex_color}"/></a:solidFill>'
        f'</a:ln>'
    )
    for ri in range(total_rows):
        for ci in range(num_cols):
            tc = tbl.cell(ri, ci)._tc
            tcPr = tc.find(qn('a:tcPr'))
            if tcPr is None:
                tcPr = etree.SubElement(tc, qn('a:tcPr'))
            for tag in ('a:lnL', 'a:lnR', 'a:lnT', 'a:lnB'):
                old = tcPr.find(qn(tag))
                if old is not None:
                    tcPr.remove(old)
                ln = etree.fromstring(ln_xml)
                sub = etree.SubElement(tcPr, qn(tag))
                sub.append(ln[0])          # append <a:solidFill>
                sub.set('w', w_emu)


def add_table(slide, x, y, w, h, num_rows, num_cols, col_widths_pct=None,
              header_data=None, rows_data=None,
              header_fill=NAVY, row_fills=None, border_hex=None):
    """
    Ajoute un tableau python-pptx.
    header_data : list de strings (optionnel)
    rows_data   : list of list of strings
    col_widths_pct : list of floats (somme=1.0) — proportions colonnes
    row_fills   : list de fill_hex pour chaque ligne data (cycling)
    """
    from pptx.util import Cm, Pt, Emu
    from pptx.enum.text import PP_ALIGN

    total_rows = num_rows + (1 if header_data else 0)
    tbl = slide.shapes.add_table(
        total_rows, num_cols, Cm(x), Cm(y), Cm(w), Cm(h)
    ).table

    # Largeurs colonnes
    total_emu = int(Cm(w))
    if col_widths_pct:
        for ci, pct in enumerate(col_widths_pct):
            tbl.columns[ci].width = int(total_emu * pct)
    else:
        col_w = total_emu // num_cols
        for ci in range(num_cols):
            tbl.columns[ci].width = col_w

    row_offset = 0
    # Header
    if header_data:
        for ci, val in enumerate(header_data):
            cell = tbl.cell(0, ci)
            _set_cell(cell, val, font_size=8, bold=True,
                      color_hex=WHITE, fill_hex=header_fill,
                      align=PP_ALIGN.CENTER if ci > 0 else PP_ALIGN.LEFT)
        row_offset = 1

    # Data rows
    if rows_data:
        default_fills = [WHITE, GREY_BG]
        for ri, row in enumerate(rows_data):
            if row_fills and ri < len(row_fills):
                fill = row_fills[ri]
            else:
                fill = default_fills[ri % 2]
            for ci, val in enumerate(row):
                cell = tbl.cell(ri + row_offset, ci)
                align = PP_ALIGN.LEFT if ci == 0 else PP_ALIGN.CENTER
                _set_cell(cell, val, font_size=8, bold=False,
                          color_hex=BLACK, fill_hex=fill,
                          align=align)

    if border_hex:
        _apply_cell_borders(tbl, num_rows + (1 if header_data else 0), num_cols, border_hex)

    return tbl


# ---------------------------------------------------------------------------
# Elements communs des slides
# ---------------------------------------------------------------------------

def navy_bar(slide):
    add_rect(slide, 0, 0, 25.4, 1.65, NAVY)


def footer_bar(slide, ticker="", co_name=""):
    add_rect(slide, 0, 13.39, 25.4, 0.89, NAVY)
    add_text_box(slide, 1.02, 13.44, 23.37, 0.56,
                 "FinSight IA  \u00b7  Usage confidentiel", 7, WHITE)


def section_dots(slide, active: int):
    from pptx.enum.text import PP_ALIGN
    xs = [17.02, 17.65, 18.29, 18.92, 19.56]
    for i, x in enumerate(xs):
        num = i + 1
        fill = WHITE if num == active else NAVY_MID
        add_rect(slide, x, 0.33, 0.51, 0.51, fill)
        color = NAVY if num == active else WHITE
        add_text_box(slide, x + 0.02, 0.34, 0.47, 0.44,
                     str(num), 7, color, bold=True,
                     align=PP_ALIGN.CENTER)


def slide_title(slide, title: str, subtitle: str = ""):
    from pptx.enum.text import PP_ALIGN
    add_text_box(slide, 1.02, 0.33, 15.49, 0.97,
                 title, 13, WHITE, bold=True)
    if subtitle:
        add_text_box(slide, 1.02, 1.73, 23.37, 0.56,
                     subtitle, 9, NAVY_MID)


def kpi_box(slide, x, y, w, h, value, label, sub="",
            fill=NAVY_PALE, accent=NAVY_MID):
    from pptx.enum.text import PP_ALIGN
    add_rect(slide, x, y, w, h, fill)
    add_rect(slide, x, y, 0.13, h, accent)
    val_color = NAVY if fill != NAVY else WHITE
    lbl_color = GREY_TXT if fill != NAVY else WHITE
    sub_color = GREY_LIGHT if fill != NAVY else NAVY_PALE
    add_text_box(slide, x + 0.25, y + 0.15, w - 0.38, 1.1,
                 value, 19, val_color, bold=True)
    add_text_box(slide, x + 0.25, y + 1.25, w - 0.38, 0.57,
                 label, 8, lbl_color)
    if sub:
        add_text_box(slide, x + 0.25, y + 1.8, w - 0.38, 0.46,
                     sub, 7, sub_color)


def commentary_box(slide, x, y, w, h, text, accent=NAVY_MID):
    add_text_box(slide, x, y, w, h, text or "—", 8.5, GREY_TXT, wrap=True)


def divider_slide(prs, number_str: str, title: str, subtitle: str):
    from pptx.enum.text import PP_ALIGN
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    # Fond navy via <p:bgPr> (natif, comme la référence — pas de rectangle additionnel)
    _set_slide_bg(slide, NAVY)

    # Left accent bar
    add_rect(slide, 0, 0, 0.3, 14.29, NAVY_MID)

    # Numéro filigrane — blanc à 15 % d'opacité (comme la référence)
    _add_text_alpha(slide, 1.27, 4.06, 22.86, 4.57,
                    number_str, 80, "FFFFFF", 15000, bold=True)

    # Title
    add_text_box(slide, 1.27, 5.21, 21.59, 2.29,
                 title, 28, WHITE, bold=True)

    # Rule
    add_rect(slide, 1.27, 7.75, 7.62, 0.01, GREY_LIGHT)

    # Subtitle
    add_text_box(slide, 1.27, 8.08, 17.78, 0.89,
                 subtitle, 10, "AABBDD")

    # Footer (espaces autour du bullet comme la référence)
    add_text_box(slide, 1.02, 13.34, 23.37, 0.56,
                 "FinSight IA  \u00b7  Usage confidentiel", 7, "6677AA")

    return slide


# ---------------------------------------------------------------------------
# State data extraction helpers
# ---------------------------------------------------------------------------

def _extract_state(state: dict):
    snap      = state.get("raw_data")
    synthesis = state.get("synthesis")
    ratios    = state.get("ratios")
    devil     = state.get("devil")
    sentiment = state.get("sentiment")
    return snap, synthesis, ratios, devil, sentiment


def _ratio(ratios, attr):
    if not ratios:
        return None
    latest = getattr(ratios, "latest_year", None)
    if not latest:
        return None
    yrs = getattr(ratios, "years", {}) or {}
    yr = yrs.get(latest)
    val = getattr(yr, attr, None) if yr else None
    if val is not None:
        return val
    # Fallback: walk years in reverse order to find latest with data
    for y in sorted(yrs.keys(), key=lambda k: str(k).replace("_LTM", ""), reverse=True):
        yr2 = yrs.get(y)
        if yr2 is None:
            continue
        v2 = getattr(yr2, attr, None)
        if v2 is not None:
            return v2
    return None


def _fy(snap, year_key, attr):
    if not snap or not year_key:
        return None
    fy = snap.years.get(year_key) if snap.years else None
    return getattr(fy, attr, None) if fy else None


def _rec_colors(rec: str):
    rec = (rec or "HOLD").upper()
    if rec == "BUY":
        return GREEN_PALE, GREEN
    elif rec == "SELL":
        return RED_PALE, RED
    else:
        return AMBER_PALE, AMBER


def _sent_label_fr(label: str, score: float = 0.0) -> str:
    label = (label or "NEUTRAL").upper()
    if label in ("POSITIVE", "POSITIF"):
        return "Positif"
    elif label in ("NEGATIVE", "NEGATIF"):
        return "Négatif"
    else:
        return "Neutre +" if score > 0 else "Neutre"


def _safe_str(v, default="—") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _fr_date_long(d=None) -> str:
    """Converts a date to French long form: '14 mars 2026'."""
    from datetime import date as _date
    _MONTHS = ["janvier", "f\u00e9vrier", "mars", "avril", "mai", "juin",
               "juillet", "ao\u00fbt", "septembre", "octobre", "novembre", "d\u00e9cembre"]
    if d is None:
        d = _date.today()
    elif isinstance(d, str):
        try:
            d = _date.fromisoformat(str(d).split("T")[0][:10])
        except Exception:
            return str(d)
    try:
        return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"
    except Exception:
        return str(d)


_EXCHANGE_MAP = {
    "NMS": "NASDAQ", "NGM": "NASDAQ", "NCM": "NASDAQ", "NAS": "NASDAQ",
    "NYQ": "NYSE",   "NYA": "NYSE",
    "PCX": "NYSE Arca",
    "XPAR": "Euronext Paris", "PAR": "Euronext Paris", "ENX": "Euronext Paris",
    "XLON": "London SE",      "LSE": "London SE",       "IOB": "London SE",
    "XFRA": "Frankfurt",      "FRA": "Frankfurt",        "GER": "Frankfurt",
    "XAMS": "Euronext Amsterdam", "AMS": "Euronext Amsterdam",
    "XBRU": "Euronext Brussels",  "BRU": "Euronext Brussels",
    "XMIL": "Borsa Italiana",     "MIL": "Borsa Italiana",
    "XMAD": "BME",                "MCE": "BME",
    "TDM": "TSX",                 "TSX": "TSX",
}

def _normalize_exchange(ex: str) -> str:
    if not ex:
        return ""
    return _EXCHANGE_MAP.get(ex.upper().strip(), ex)


_TICKER_SUFFIX_MAP = {
    ".PA": "Euronext Paris",  ".L": "London SE",   ".DE": "Frankfurt",
    ".AS": "Euronext Amsterdam", ".BR": "Euronext Brussels",
    ".MI": "Borsa Italiana",  ".MC": "BME",         ".SW": "SIX Swiss",
    ".TO": "TSX",             ".HK": "HKEX",        ".T":  "Tokyo SE",
    ".AX": "ASX",             ".CO": "Nasdaq Copenhagen",
}

def _infer_exchange(ticker: str, exchange: str) -> str:
    """Retourne l'exchange normalisé, avec fallback sur le suffixe du ticker."""
    ex = _normalize_exchange(exchange)
    if ex:
        return ex
    for sfx, exch in _TICKER_SUFFIX_MAP.items():
        if ticker.upper().endswith(sfx.upper()):
            return exch
    return ""


import math as _math

def _cover_layout(co_name: str):
    """
    Calcule dynamiquement la taille de police et les positions y
    pour que le nom, la tagline et la boîte de recommandation
    ne se chevauchent jamais, quelle que soit la longueur du nom.
    """
    n = len(co_name)
    if n <= 15:   fs, cpl = 40, 22
    elif n <= 25: fs, cpl = 34, 28
    elif n <= 40: fs, cpl = 26, 35
    elif n <= 60: fs, cpl = 20, 44
    else:          fs, cpl = 16, 55
    n_lines   = max(1, min(_math.ceil(n / cpl), 5))
    line_h_cm = fs * 0.0353 * 1.35          # pt → cm, + interligne
    name_h    = max(n_lines * line_h_cm + 0.3, 1.4)
    name_y    = 4.06
    tagline_y = name_y + name_h + 0.25
    rec_y     = tagline_y + 0.76 + 0.28
    return fs, name_y, name_h, tagline_y, rec_y


def _truncate(s, n: int) -> str:
    s = _safe_str(s)
    if len(s) <= n:
        return s
    # Cut at last word boundary before n to avoid mid-word truncation
    cut = s[:n]
    last_space = cut.rfind(" ")
    if last_space > n // 2:
        cut = cut[:last_space]
    return cut + "…"


def _fit(s, n: int) -> str:
    """Coupe a n chars sans ajouter '...' — pour les zones ou le debordement est invisible."""
    s = _safe_str(s)
    if len(s) <= n:
        return s
    cut = s[:n]
    last_space = cut.rfind(" ")
    return cut[:last_space] if last_space > n // 2 else cut


def _peer_median(peers: list, attr: str):
    vals = []
    for p in (peers or []):
        v = _g(p, attr)
        if v is not None:
            try:
                vals.append(float(v))
            except Exception:
                pass
    if not vals:
        return None
    return statistics.median(vals)


# ---------------------------------------------------------------------------
# DCF sensitivity helper
# ---------------------------------------------------------------------------

def _dcf_value(tbase, wacc_base, tgr_base, w_delta, t_delta):
    """
    Approximation lineaire de la valeur DCF autour du point de base.
    En l'absence de FCF explicites, on scale le prix cible base
    par le ratio (wacc_ref / wacc_new) * (tgr_new / tgr_ref) simplifie.
    """
    if tbase is None:
        return "—"
    try:
        w = wacc_base + w_delta
        t = tgr_base + t_delta
        if w <= t or w <= 0:
            return "—"
        # Gordon Growth proxy: V ∝ 1 / (w - t)
        base_spread = wacc_base - tgr_base
        new_spread  = w - t
        if base_spread <= 0 or new_spread <= 0:
            return "—"
        val = float(tbase) * base_spread / new_spread
        return _fr(val, 0)
    except Exception:
        return "—"


# ---------------------------------------------------------------------------
# Slide 1 — Cover
# ---------------------------------------------------------------------------

def _slide_cover(prs, snap, synthesis, ratios, devil, sentiment):
    from pptx.enum.text import PP_ALIGN
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    ci       = snap.company_info if snap else None
    mkt      = snap.market if snap else None
    ticker   = _g(ci, "ticker", "—")
    co_name  = _g(ci, "company_name", "—")
    sector   = _g(ci, "sector", "") or ""
    exchange = _infer_exchange(ticker, getattr(ci, "exchange", "") or "" if ci else "")
    currency = _g(ci, "currency", "USD") or "USD"
    cur_sym  = "EUR" if currency == "EUR" else "$"
    gen_date = _fr_date_long(_g(ci, "analysis_date", None) or date.today())
    price    = _g(mkt, "share_price")

    rec      = _g(synthesis, "recommendation", "HOLD") or "HOLD"
    tbase    = _g(synthesis, "target_base")
    rec_fill, rec_accent = _rec_colors(rec)

    # Layout dynamique selon longueur du nom
    fs_name, name_y, name_h, tagline_y, rec_y = _cover_layout(co_name)

    # Top navy band
    add_rect(slide, 0, 0, 25.4, 3.81, NAVY)
    add_text_box(slide, 1.27, 0.46, 22.86, 0.71, "FinSight IA",
                 10, "8899BB", bold=False, align=PP_ALIGN.CENTER)
    add_rect(slide, 11.05, 1.32, 3.3, 0.05, WHITE)
    add_text_box(slide, 1.27, 1.52, 22.86, 0.81,
                 "Pitchbook  \u2014  Analyse d'investissement",
                 11, "CCDDEE", align=PP_ALIGN.CENTER)

    # Company name (taille dynamique, centré)
    add_text_box(slide, 1.27, name_y, 22.86, name_h,
                 co_name, fs_name, NAVY, bold=True, align=PP_ALIGN.CENTER)

    # Tagline ticker · exchange · secteur
    _tagline_parts = [p for p in [ticker, exchange, sector] if p and str(p).strip()]
    add_text_box(slide, 1.27, tagline_y, 22.86, 0.71,
                 "  \u00b7  ".join(_tagline_parts), 11, "888888",
                 align=PP_ALIGN.CENTER)

    # Recommendation box — rectangle solide centré ~40% largeur (gold standard)
    upside_str = _upside(tbase, price)
    rec_w = 10.0   # ~40% de 25.4cm
    rec_h = 1.20
    rec_x = (25.4 - rec_w) / 2
    add_rect(slide, rec_x, rec_y, rec_w, rec_h, rec_accent)
    add_text_box(
        slide, rec_x + 0.15, rec_y + 0.05, rec_w - 0.30, rec_h - 0.10,
        f"\u25cf {rec.upper()}  \u00b7  Prix cible base\u00a0: {_fr(tbase, 0)} {cur_sym}"
        f"  \u00b7  Upside\u00a0: {upside_str}",
        9, WHITE, bold=True, align=PP_ALIGN.CENTER
    )

    # Bottom rule + credits (8pt)
    add_rect(slide, 1.02, 12.4, 23.37, 0.03, "AAAAAA")
    add_text_box(slide, 1.02, 12.65, 11.43, 0.56,
                 "Rapport confidentiel", 8, GREY_TXT)
    add_text_box(slide, 12.95, 12.65, 11.43, 0.56,
                 gen_date, 8, GREY_TXT, align=PP_ALIGN.RIGHT)

    return slide


# ---------------------------------------------------------------------------
# Slide 2 — Executive Summary
# ---------------------------------------------------------------------------

def _slide_exec_summary(prs, snap, synthesis, ratios, devil, sentiment):
    from pptx.enum.text import PP_ALIGN
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    navy_bar(slide)
    footer_bar(slide)
    slide_title(slide, "Executive Summary")

    ci      = snap.company_info if snap else None
    mkt     = snap.market if snap else None
    currency = _g(ci, "currency", "USD") or "USD"
    cur_sym  = "EUR" if currency == "EUR" else "$"
    price    = _g(mkt, "share_price")

    rec      = _g(synthesis, "recommendation", "HOLD") or "HOLD"
    conv     = _g(synthesis, "conviction", 0.5) or 0.5
    conf     = _g(synthesis, "confidence_score", 0.5) or 0.5
    tbase    = _g(synthesis, "target_base")
    tbear    = _g(synthesis, "target_bear")
    tbull    = _g(synthesis, "target_bull")
    thesis   = _g(synthesis, "thesis", "") or ""
    strengths= _g(synthesis, "strengths", []) or []
    risks_s  = _g(synthesis, "risks", []) or []

    rec_fill, rec_accent = _rec_colors(rec)

    beta     = _g(mkt, "beta_levered")
    rfr      = _g(mkt, "risk_free_rate") or 0.041
    wacc_val = _g(mkt, "wacc") or 0.10

    sent_score  = _g(sentiment, "score", 0.0) or 0.0
    sent_label  = _g(sentiment, "label", "NEUTRAL") or "NEUTRAL"
    sent_articles = _g(sentiment, "articles_analyzed", 0) or 0
    sent_label_display = _sent_label_fr(sent_label, sent_score)
    _s2_is_llm  = _g(sentiment, "engine", "finbert") not in ("finbert", "finbert_fallback", None, "")

    # Rec band
    add_rect(slide, 1.02, 2.08, 23.37, 1.22, rec_fill)
    add_rect(slide, 1.02, 2.08, 0.13, 1.22, rec_accent)
    add_text_box(slide, 1.4, 2.13, 3.05, 1.12,
                 f"● {rec.upper()}", 11, rec_accent, bold=True)
    bull_str = (
        f"Bear : {_fr(tbear, 0)} {cur_sym} ({_upside(tbear, price)})  ·  "
        f"Bull : {_fr(tbull, 0)} {cur_sym} ({_upside(tbull, price)})"
    )
    add_text_box(
        slide, 4.7, 2.13, 19.3, 1.12,
        f"Prix cible base : {_fr(tbase, 0)} {cur_sym}  ·  Upside : {_upside(tbase, price)}  ·  {bull_str}",
        9, NAVY
    )

    # Thesis section header
    add_rect(slide, 1.02, 3.76, 11.56, 0.71, NAVY)
    add_text_box(slide, 1.02, 3.76, 11.56, 0.71,
                 "TH\u00c8SE D'INVESTISSEMENT", 9, WHITE, bold=True)

    # Thesis bullets — espacement dynamique avec corps de texte
    thesis_parts = _split_text(thesis, 3)
    pos_themes   = _g(synthesis, "positive_themes", []) or []
    strength_ys = [4.57, 6.10, 7.63]
    for i, sy in enumerate(strength_ys):
        label = strengths[i] if i < len(strengths) else (thesis_parts[i] if i < len(thesis_parts) else "")
        body  = thesis_parts[i] if i < len(thesis_parts) else ""
        # Fallback body : positive_themes si thesis_parts trop court
        if not body or body == label:
            body = pos_themes[i] if i < len(pos_themes) else ""
        add_rect(slide, 1.02, sy + 0.05, 0.15, 0.36, NAVY_MID)
        add_text_box(slide, 1.4, sy, 10.92, 0.51,
                     _truncate(label, 80), 8.5, NAVY, bold=True)
        add_text_box(slide, 1.4, sy + 0.47, 10.92, 1.05,
                     _fit(body, 480), 7.5, "333333", wrap=True)

    # Risks section header
    add_rect(slide, 13.08, 3.76, 11.3, 0.71, RED)
    add_text_box(slide, 13.08, 3.76, 11.3, 0.71,
                 "RISQUES PRINCIPAUX", 9, WHITE, bold=True)

    # Risques avec corps de texte
    counter_risks = _g(devil, "counter_risks", []) or []
    counter_thesis_txt = _g(devil, "counter_thesis", "") or ""
    risk_bodies  = _split_text(counter_thesis_txt, 3) if counter_thesis_txt else [""] * 3
    neg_themes   = _g(synthesis, "negative_themes", []) or []

    risk_ys = [4.57, 6.10, 7.63]
    for i, ry in enumerate(risk_ys):
        risk_text = (risks_s[i] if i < len(risks_s) else
                     (counter_risks[i] if i < len(counter_risks) else ""))
        # Cascade body : neg_themes → risk_bodies (counter_thesis) → counter_risks → fallback unique
        # Seuil abaissé à 15 chars : neg_themes peut être un court bullet point LLM
        body_r = (neg_themes[i] if i < len(neg_themes) and neg_themes[i] else "")
        if not body_r or len(body_r) < 15:
            rb = risk_bodies[i] if i < len(risk_bodies) else ""
            if rb and len(rb) >= 15:
                body_r = rb
        if not body_r or len(body_r) < 15:
            cr = counter_risks[i] if i < len(counter_risks) else ""
            if cr and len(cr) >= 15:
                body_r = cr
        if not body_r or len(body_r) < 15:
            # Fallback unique : intègre le label du risque pour différencier les 3 blocs
            _lbl = (risk_text.split(":", 1)[-1].strip() if ":" in risk_text
                    else risk_text)
            if _lbl and len(_lbl) >= 10:
                body_r = (f"{_lbl} — impact potentiel sur la valorisation et les marges, "
                          f"surveillance recommandée sur les 6-12 prochains mois.")
            else:
                body_r = ("Impact potentiel sur la thèse d'investissement — "
                          "surveillance recommandée sur les 6-12 prochains mois.")
        add_rect(slide, 13.08, ry + 0.05, 0.15, 0.36, RED)
        add_text_box(slide, 13.46, ry, 10.54, 0.51,
                     _truncate(risk_text, 80), 8.5, NAVY, bold=True)
        add_text_box(slide, 13.46, ry + 0.47, 10.54, 1.05,
                     _fit(body_r, 480), 7.5, "333333", wrap=True)

    # Vertical divider
    add_rect(slide, 12.57, 3.76, 0.03, 4.84, GREY_LIGHT)

    # Horizontal rule
    add_rect(slide, 1.02, 9.17, 23.37, 0.03, "AAAAAA")

    # -------------------------------------------------------------------------
    # Investment Case — Catalyseurs (left) + Valorisation Synthétique (right)
    # -------------------------------------------------------------------------
    catalysts   = _g(synthesis, "catalysts", []) or []
    peers       = _g(synthesis, "comparable_peers", []) or []
    ev_e        = _ratio(ratios, "ev_ebitda")
    pe_e        = _ratio(ratios, "pe_ratio")
    peer_median_ev_e = _peer_median(peers, "ev_ebitda")
    peer_median_pe   = _peer_median(peers, "pe")

    # --- Catalyseurs section (left) ---
    add_rect(slide, 1.02, 9.26, 11.14, 0.55, "1A7A4A")
    add_text_box(slide, 1.15, 9.26, 11.0, 0.55,
                 "CATALYSEURS \u00c0 SURVEILLER (12M)", 7.5, WHITE, bold=True)

    _cat_ys = [9.89, 10.44]
    for i, cy in enumerate(_cat_ys):
        if i < len(catalysts):
            _cat_name = _g(catalysts[i], "title") or _g(catalysts[i], "name") or ""
            _cat_body = _g(catalysts[i], "description") or _g(catalysts[i], "text") or ""
            _cat_txt  = _fit(f"{_cat_name[:25]}: {_cat_body}", 80) if _cat_body else _fit(_cat_name, 80)
        else:
            _cat_txt = "\u2014"
        add_rect(slide, 1.02, cy + 0.06, 0.12, 0.26, "1A7A4A")
        add_text_box(slide, 1.22, cy, 10.66, 0.48,
                     _cat_txt, 7.5, "333333", wrap=False)

    # --- Valorisation Synthétique section (right) ---
    add_rect(slide, 13.08, 9.26, 11.3, 0.55, NAVY)
    add_text_box(slide, 13.21, 9.26, 11.1, 0.55,
                 "VALORISATION SYNTH\u00c9TIQUE", 7.5, WHITE, bold=True)

    val_tbl = add_table(
        slide, 13.08, 9.89, 11.3, 1.1,
        num_rows=3, num_cols=3,
        col_widths_pct=[0.50, 0.25, 0.25],
        header_data=["Multiple", "Soci\u00e9t\u00e9", "M\u00e9diane pairs"],
        rows_data=[
            ["P/E NTM (x)", _frx(pe_e), _frx(peer_median_pe)],
            ["EV/EBITDA (x)", _frx(ev_e), _frx(peer_median_ev_e)],
            [f"Cible DCF ({cur_sym})",
             f"{_fr(tbase, 0)} {cur_sym}",
             f"Upside {_upside(tbase, price)}"],
        ],
    )

    # Vertical divider (lower section)
    add_rect(slide, 12.57, 9.17, 0.03, 2.0, GREY_LIGHT)

    # Horizontal rule (before KPI)
    add_rect(slide, 1.02, 11.23, 23.37, 0.03, "AAAAAA")

    # 4 KPI boxes (shifted down to accommodate investment case section)
    kpi_box(slide, 1.02, 11.34, 5.64, 1.96,
            _frx(ev_e), "EV/EBITDA",
            f"vs {_frx(peer_median_ev_e)} med. pairs")
    kpi_box(slide, 6.91, 11.34, 5.64, 1.96,
            _frpct(wacc_val), "WACC",
            f"Beta {_fr(beta, 2) if beta else '—'}  \u00b7  RFR {_frpct(rfr)}")
    kpi_box(slide, 12.80, 11.34, 5.64, 1.96,
            f"{_fr(tbase, 0)} {cur_sym}", "Valeur DCF base",
            f"Upside {_upside(tbase, price)} vs cours")
    kpi_box(slide, 18.69, 11.34, 5.64, 1.96,
            f"{sent_score:+.3f}".replace(".", ","),
            "Sentiment LLM" if _s2_is_llm else "Sentiment FinBERT",
            f"{sent_label_display}  \u00b7  {sent_articles} art.")

    return slide


# ---------------------------------------------------------------------------
# Slide 3 — Sommaire
# ---------------------------------------------------------------------------

def _slide_sommaire(prs, snap=None, synthesis=None):
    from pptx.enum.text import PP_ALIGN
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    navy_bar(slide)
    footer_bar(slide)
    slide_title(slide, "Sommaire")

    # Descriptions dynamiques basées sur les données de la société
    ci       = snap.company_info if snap else None
    co_name  = _g(ci, "company_name", "") or ""
    sector   = _g(ci, "sector", "") or ""
    strengths= _g(synthesis, "strengths", []) or []
    risks    = _g(synthesis, "risks", []) or []
    rec      = _g(synthesis, "recommendation", "") or ""

    def _s1(items, n=2):
        """2 premiers éléments d'une liste, jointure ' · '"""
        parts = [str(x)[:40] for x in items[:n] if x]
        return "  \u00b7  ".join(parts) if parts else ""

    co_desc  = f"{co_name}  \u00b7  {sector}" if co_name and sector else (co_name or "Presentation, mod\u00e8le \u00e9conomique")
    str_desc = _s1(strengths) or "Analyse strat\u00e9gique & positionnement"
    ris_desc = _s1(risks) or "Risques structurels & th\u00e8se contraire"

    sections = [
        ("01", "Company Overview",    _truncate(co_desc, 80),  "3\u20135"),
        ("02", "Analyse Financi\u00e8re",  "Compte de r\u00e9sultat, bilan & liquidit\u00e9, ratios",         "6\u20138"),
        ("03", "Valorisation",        "DCF, comparable peers, Football Field",                 "9\u201311"),
        ("04", "Risques & Strat\u00e9gie", _truncate(ris_desc, 80),  "12\u201313"),
        ("05", "Sentiment & Annexes", "FinBERT, actionnariat & historique de cours",           "14\u201315"),
    ]
    fills = [WHITE, GREY_BG, WHITE, GREY_BG, WHITE]
    ys    = [2.49, 4.42, 6.35, 8.28, 10.21]

    for i, (num, name, desc, pages) in enumerate(sections):
        y    = ys[i]
        fill = fills[i]
        add_rect(slide, 1.02, y, 23.37, 1.73, fill)
        add_rect(slide, 1.02, y, 0.13, 1.73, NAVY_MID)
        add_text_box(slide, 1.40, y + 0.15, 1.32, 1.43,
                     num, 17, GREY_LIGHT, bold=True)
        add_text_box(slide, 3.20, y + 0.20, 17.00, 0.71,
                     name, 13, NAVY, bold=True)
        add_text_box(slide, 3.20, y + 0.85, 17.00, 0.71,
                     desc, 8.5, GREY_TXT)
        add_text_box(slide, 20.57, y + 0.45, 3.82, 0.71,
                     pages, 9, NAVY_MID,
                     align=PP_ALIGN.RIGHT)

    return slide


# ---------------------------------------------------------------------------
# Slide 5 — Company Overview
# ---------------------------------------------------------------------------

def _slide_company_overview(prs, snap, synthesis, ratios):
    from pptx.enum.text import PP_ALIGN
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    navy_bar(slide)
    footer_bar(slide)
    section_dots(slide, 1)

    ci      = snap.company_info if snap else None
    mkt     = snap.market if snap else None
    ticker  = _g(ci, "ticker", "—")
    co_name = _g(ci, "company_name", "—")
    currency = _g(ci, "currency", "USD") or "USD"
    cur_sym  = "EUR" if currency == "EUR" else "$"
    price    = _g(mkt, "share_price")

    slide_title(slide, "Company Overview",
                f"{co_name}  ·  Présentation & Positionnement stratégique")

    desc     = _g(synthesis, "company_description", "") or ""
    segments = _g(synthesis, "segments", []) or []
    strengths= _g(synthesis, "strengths", []) or []

    # Nombre de segments pour la formulation dynamique
    n_seg = len(segments)
    _num_fr = {1:"un",2:"deux",3:"trois",4:"quatre",5:"cinq",6:"six"}
    seg_count_str = _num_fr.get(n_seg, str(n_seg)) if n_seg else ""

    # Description + phrase d'intro dans la même boîte
    if n_seg:
        intro_txt = (
            f" L'entreprise articule son activit\u00e9 autour de "
            f"{seg_count_str} segment{'s' if n_seg > 1 else ''} "
            f"strat\u00e9gique{'s' if n_seg > 1 else ''} :"
        )
        full_desc = _truncate(desc, 700) + intro_txt
    else:
        full_desc = _truncate(desc, 700)

    add_rect(slide, 1.02, 2.67, 13.72, 9.78, GREY_BG)
    add_rect(slide, 1.02, 2.67, 0.13, 9.78, NAVY_MID)
    add_text_box(slide, 1.40, 2.84, 12.95, 4.0,
                 full_desc, 8.5, BLACK, wrap=True)

    if n_seg:
        bullet_y = 7.10
        row_h = 1.95  # hauteur par segment (augmente pour eviter truncation "...")
        for i, seg in enumerate(segments[:4]):
            seg_name = _g(seg, "name", "") or str(seg)
            seg_desc = _g(seg, "description", "") or ""
            by = bullet_y + i * row_h
            add_rect(slide, 1.40, by + 0.12, 0.18, 0.18, NAVY_MID)
            add_text_box(slide, 1.72, by, 12.05, 0.46,
                         _truncate(seg_name, 80), 8.5, BLACK, bold=True)
            if seg_desc:
                add_text_box(slide, 1.72, by + 0.44, 12.05, 1.40,
                             _truncate(seg_desc, 520), 7.5, GREY_TXT, italic=True, wrap=True)
    else:
        # Fallback : liste des strengths si pas de segments
        bullet_y = 7.25
        add_text_box(slide, 1.40, 6.55, 12.95, 0.51,
                     "Positionnement strat\u00e9gique", 9, NAVY, bold=True)
        for i, strength in enumerate(strengths[:4]):
            add_rect(slide, 1.40, bullet_y + i * 0.72 + 0.18, 0.18, 0.18, NAVY_MID)
            add_text_box(slide, 1.72, bullet_y + i * 0.72, 12.05, 0.56,
                         _truncate(str(strength), 80), 8.5, BLACK)

    # 4 KPI boxes on right
    shares    = _g(mkt, "shares_diluted")
    mktcap    = (shares * price / 1000) if (shares and price) else None
    years_sorted = _valid_years(snap)
    latest_yr_key = years_sorted[-1] if years_sorted else None
    rev = _fy(snap, latest_yr_key, "revenue")

    kpi_ys = [2.67, 5.13, 7.59, 10.06]
    kpi_box(slide, 15.44, kpi_ys[0], 8.89, 2.29,
            _frm(mktcap * 1000 if mktcap else None, cur_sym) if mktcap else "—",
            "Capitalisation boursière",
            fill=NAVY, accent=WHITE)
    kpi_box(slide, 15.44, kpi_ys[1], 8.89, 2.29,
            _frm(rev, cur_sym),
            f"Chiffre d'affaires ({latest_yr_key or 'LTM'})")
    kpi_box(slide, 15.44, kpi_ys[2], 8.89, 2.29,
            f"{_fr(price, 2)} {cur_sym}" if price else "—",
            "Cours actuel")
    ev_e = _ratio(ratios, "ev_ebitda")
    pe   = _ratio(ratios, "pe_ratio")
    kpi_box(slide, 15.44, kpi_ys[3], 8.89, 2.29,
            _frx(ev_e),
            "EV/EBITDA (LTM)",
            f"P/E : {_frx(pe)}")

    return slide


# ---------------------------------------------------------------------------
# Slide 6 — Business Model (Segments)
# ---------------------------------------------------------------------------

def _slide_business_model(prs, snap, synthesis):
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    navy_bar(slide)
    footer_bar(slide)
    section_dots(slide, 1)
    slide_title(slide, "Mod\u00e8le \u00c9conomique",
                "Segments op\u00e9rationnels et moteurs de croissance")

    segments  = _g(synthesis, "segments", []) or []
    strengths = _g(synthesis, "strengths", []) or []

    # Fallback si pas de segments LLM : construire depuis strengths
    if not segments:
        _fallback_labels = ["Core Business", "Growth Driver", "International", "Innovation"]
        segments = [
            {"name": _fallback_labels[i], "description": strengths[i] if i < len(strengths) else "", "revenue_pct": None}
            for i in range(min(len(strengths), 4) or 3)
        ]

    # Limiter à 4 colonnes max pour la mise en page
    segs_to_show = segments[:4]
    n_cols = len(segs_to_show) or 1

    _palettes = [
        (NAVY_PALE,  NAVY_MID),
        (GREEN_PALE, GREEN),
        (GREY_BG,    GREY_LIGHT),
        (AMBER_PALE, AMBER),
    ]

    total_w = 23.36  # 25.4 - 1.02*2
    col_gap  = 0.30
    col_w    = (total_w - (n_cols - 1) * col_gap) / n_cols
    start_x  = 1.02
    col_h    = 9.78
    col_y    = 2.67

    for i, seg in enumerate(segs_to_show):
        fill, accent = _palettes[i % len(_palettes)]
        seg_name = _g(seg, "name", f"Segment {i+1}") or f"Segment {i+1}"
        seg_desc = _g(seg, "description", "") or ""
        rev_pct  = _g(seg, "revenue_pct")
        pct_str  = f"{float(rev_pct):.0f}%" if rev_pct is not None else "—"

        cx = start_x + i * (col_w + col_gap)
        add_rect(slide, cx, col_y, col_w, col_h, fill)
        add_rect(slide, cx, col_y, col_w, 0.15, accent)
        add_text_box(slide, cx + 0.25, col_y + 0.50, col_w - 0.50, 1.78,
                     pct_str, 22, accent, bold=True)
        add_text_box(slide, cx + 0.25, col_y + 2.29, col_w - 0.50, 0.30,
                     "du CA", 9, GREY_TXT)
        add_rect(slide, cx + 0.25, col_y + 2.79, col_w - 0.50, 0.05, GREY_LIGHT)
        add_text_box(slide, cx + 0.25, col_y + 3.05, col_w - 0.50, 0.71,
                     _truncate(seg_name, 60), 10, NAVY, bold=True, wrap=True)
        # Hauteur description etendue pour utiliser l'espace jusqu'au footer (13.39 - col_y - 3.81)
        desc_h = col_h - 3.81 - 0.30  # marge 0.30 cm avant le bas de la carte
        add_text_box(slide, cx + 0.25, col_y + 3.81, col_w - 0.50, max(desc_h, 5.0),
                     _truncate(seg_desc, 520), 8, GREY_TXT, wrap=True)

    return slide


# ---------------------------------------------------------------------------
# Slide 8 — Compte de Resultat
# ---------------------------------------------------------------------------

def _slide_is(prs, snap, synthesis, ratios):
    from pptx.enum.text import PP_ALIGN
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    navy_bar(slide)
    footer_bar(slide)
    section_dots(slide, 2)

    ci      = snap.company_info if snap else None
    currency= _g(ci, "currency", "USD") or "USD"
    cur_sym = "EUR" if currency == "EUR" else "$"

    years_sorted = _valid_years(snap)
    is_proj  = _g(synthesis, "is_projections", {}) or {}
    proj_keys = list(is_proj.keys())

    yr_range_start = years_sorted[0] if years_sorted else ""
    yr_range_end   = proj_keys[-1] if proj_keys else (years_sorted[-1] if years_sorted else "")

    slide_title(slide, "Analyse Financi\u00e8re \u2014 Compte de R\u00e9sultat",
                f"{currency} millions  \u00b7  {yr_range_start}\u2013{yr_range_end}")

    # Build display columns (up to 3 hist + 2 proj)
    hist_cols = years_sorted[-3:] if len(years_sorted) >= 3 else years_sorted
    proj_cols = proj_keys[:2]
    all_cols  = hist_cols + proj_cols

    header = ["Indicateur"] + [str(c) for c in all_cols]
    n_cols  = len(header)

    # IS rows
    rows_data = []
    for col_k in all_cols:
        pass  # computed below

    def _get_col(col_k):
        if col_k in proj_keys:
            pd = is_proj.get(col_k, {})
            return pd
        else:
            fy = snap.years.get(col_k) if (snap and snap.years) else None
            yr = ratios.years.get(col_k) if (ratios and ratios.years) else None
            return {"fy": fy, "yr": yr}

    row_labels = [
        "Chiffre d'affaires",
        "Croissance YoY",
        "Résultat brut",
        "Marge brute",
        "EBITDA",
        "Marge EBITDA",
        "Résultat net",
        "Marge nette",
    ]

    rows_data = []
    for rl in row_labels:
        row = [rl]
        for col_k in all_cols:
            d = _get_col(col_k)
            if col_k in proj_keys:
                rev   = _g(d, "revenue")
                grow  = _g(d, "revenue_growth")
                gm    = _g(d, "gross_margin")
                ebitda= _g(d, "ebitda")
                em    = _g(d, "ebitda_margin")
                ni    = _g(d, "net_income")
                nm    = _g(d, "net_margin")
            else:
                fy = d.get("fy")
                yr = d.get("yr")
                rev   = getattr(fy, "revenue", None) if fy else None
                grow  = getattr(yr, "revenue_growth", None) if yr else None
                gm    = getattr(yr, "gross_margin", None) if yr else None
                ebitda= getattr(yr, "ebitda", None) if yr else None
                em    = getattr(yr, "ebitda_margin", None) if yr else None
                ni    = getattr(yr, "net_income", None) if yr else None
                nm    = getattr(yr, "net_margin", None) if yr else None

            gp = (float(rev) * float(gm)) if (rev is not None and gm is not None) else None
            if rl == "Chiffre d'affaires":
                row.append(_frn(rev))
            elif rl == "Croissance YoY":
                row.append(_frpct(grow, signed=True))
            elif rl == "Résultat brut":
                row.append(_frn(gp))
            elif rl == "Marge brute":
                row.append(_frpct(gm))
            elif rl == "EBITDA":
                row.append(_frn(ebitda))
            elif rl == "Marge EBITDA":
                row.append(_frpct(em))
            elif rl == "Résultat net":
                row.append(_frn(ni))
            elif rl == "Marge nette":
                row.append(_frpct(nm))
            else:
                row.append("—")
        rows_data.append(row)

    col_w_total = 23.37
    first_col_pct = 0.28
    other_pct     = (1.0 - first_col_pct) / max(len(all_cols), 1)
    col_widths_pct = [first_col_pct] + [other_pct] * len(all_cols)

    tbl_h = min(1.0 + len(row_labels) * 0.71, 5.5)
    is_tbl = add_table(slide, 1.02, 2.54, col_w_total, tbl_h,
              len(row_labels), n_cols,
              col_widths_pct=col_widths_pct,
              header_data=header,
              rows_data=rows_data)

    # Post-process IS table:
    # 1. LTM column (last hist year): DDE8F5 on DATA rows only (header stays NAVY)
    # 2. Sub-metric rows: 7.5pt italic gray (Croissance, Marges)
    # 3. Valeur column: no special treatment needed
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN

    _SUBMAIN = {
        "Chiffre d'affaires", "Résultat brut", "EBITDA", "Résultat net"
    }
    _SUBSUB = {
        "Croissance YoY", "Marge brute", "Marge EBITDA", "Marge nette"
    }

    ltm_col_idx = len(hist_cols)  # table col index of last historical year

    for ri in range(1, len(row_labels) + 1):  # skip header row 0
        row_label = row_labels[ri - 1]
        is_sub = row_label in _SUBSUB

        for ci in range(n_cols):
            cell = is_tbl.cell(ri, ci)
            # LTM column highlight on data rows
            if ci == ltm_col_idx and ltm_col_idx >= 1:
                cell.fill.solid()
                cell.fill.fore_color.rgb = rgb("DDE8F5")
            # Sub-metric row styling
            try:
                p = cell.text_frame.paragraphs[0]
                for run in p.runs:
                    if is_sub:
                        run.font.size = Pt(7.5)
                        run.font.italic = True
                        run.font.color.rgb = rgb(GREY_TXT)
                    else:
                        run.font.size = Pt(8)
                        run.font.bold = True
                        if ci == ltm_col_idx:
                            run.font.color.rgb = rgb(NAVY)
            except Exception:
                pass

    # Commentary — utilise financial_commentary en priorite, puis fallback sur les autres champs
    fin_comment = _g(synthesis, "financial_commentary", "") or ""
    if not fin_comment.strip():
        # Fallback 1 : valuation_comment (souvent renseigne meme quand financial_commentary vide)
        fin_comment = _g(synthesis, "valuation_comment", "") or ""
    if not fin_comment.strip():
        # Fallback 2 : thesis (3 phrases separees par ' | ')
        thesis_raw = _g(synthesis, "thesis", "") or ""
        fin_comment = thesis_raw.replace(" | ", " ")
    if not fin_comment.strip():
        # Fallback 3 : summary general
        fin_comment = _g(synthesis, "summary", "") or ""
    if fin_comment.strip():
        commentary_box(slide, 1.02, 8.94, 23.37, 3.40, _truncate(fin_comment, 700))

    return slide


# ---------------------------------------------------------------------------
# Slide 9 — Bilan & Liquidite
# ---------------------------------------------------------------------------

def _slide_bilan(prs, snap, synthesis, ratios):
    from pptx.enum.text import PP_ALIGN
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    navy_bar(slide)
    footer_bar(slide)
    section_dots(slide, 2)

    ci      = snap.company_info if snap else None
    currency= _g(ci, "currency", "USD") or "USD"
    cur_sym = "EUR" if currency == "EUR" else "$"

    years_sorted  = _valid_years(snap)
    latest_yr_key = years_sorted[-1] if years_sorted else None
    latest_fy     = snap.years.get(latest_yr_key) if (snap and latest_yr_key) else None

    slide_title(slide, "Bilan & Liquidit\u00e9",
                f"Structure financi\u00e8re  \u00b7  {currency} millions  \u00b7  LTM {latest_yr_key or ''}")

    cash     = getattr(latest_fy, "cash", None) if latest_fy else None
    ltd      = getattr(latest_fy, "long_term_debt", None) if latest_fy else None
    std      = getattr(latest_fy, "short_term_debt", None) if latest_fy else None
    total_debt = ((_safe_float(ltd) or 0) + (_safe_float(std) or 0)) or None
    net_debt_val = ((_safe_float(total_debt) or 0) - (_safe_float(cash) or 0)) if (total_debt is not None or cash is not None) else None

    kpi_box(slide, 1.02, 2.67, 7.37, 2.29, _frm(cash, cur_sym), "Cash & equivalents")
    kpi_box(slide, 1.02, 5.28, 7.37, 2.29, _frm(ltd, cur_sym), "Dette long terme")
    kpi_box(slide, 1.02, 7.90, 7.37, 2.29, _frm(net_debt_val, cur_sym), "Dette nette",
            fill=NAVY, accent=WHITE)

    # Ratio table (7 rows × 4 cols with Signal column)
    cr  = _ratio(ratios, "current_ratio")
    qr  = _ratio(ratios, "quick_ratio")
    de  = _ratio(ratios, "debt_equity")
    ic  = _ratio(ratios, "interest_coverage")
    nde = _ratio(ratios, "net_debt_ebitda")
    az  = _ratio(ratios, "altman_z")
    bm  = _ratio(ratios, "beneish_m")

    def _sig(v, lo_good, hi_warn, reverse=False):
        if v is None: return "\u2014"
        try:
            vf = float(v)
            if not reverse:
                if vf >= lo_good: return "\u2705"
                if vf >= hi_warn: return "\u26a0\ufe0f"
                return "\u274c"
            else:
                if vf <= lo_good: return "\u2705"
                if vf <= hi_warn: return "\u26a0\ufe0f"
                return "\u274c"
        except: return "\u2014"

    az_sig = "\u2705" if (az and float(az) >= 2.99) else ("\u26a0\ufe0f" if (az and float(az) >= 1.81) else ("\u274c" if az else "\u2014"))
    bm_sig = "\u2705" if (bm and float(bm) <= -2.22) else ("\u274c" if bm else "\u2014")

    add_text_box(slide, 9.4, 2.34, 14.99, 0.46,
                 "Ratios de solvabilit\u00e9 & liquidit\u00e9", 9, NAVY, bold=True)

    ratio_rows = [
        ["Ratio liquidité courante", _fr(cr, 2),  "> 1,5",   _sig(cr, 1.5, 1.0)],
        ["Ratio rapide (quick)",     _fr(qr, 2),  "> 1,0",   _sig(qr, 1.0, 0.7)],
        ["D/E",                      _frx(de),    "< 2,0x",  _sig(de, 1.5, 3.0, reverse=True)],
        ["Couverture d'intérêts",    _frx(ic),    "> 3,0x",  _sig(ic, 3.0, 1.5)],
        ["Dette nette / EBITDA",     _frx(nde),   "< 2,0x",  _sig(nde, 2.0, 4.0, reverse=True)],
        ["Altman Z",                 _fr(az, 2),  "> 2,99",  az_sig],
        ["Beneish M",                _fr(bm, 2),  "< -2,22", bm_sig],
    ]
    ratio_tbl = add_table(slide, 9.4, 2.80, 14.99, 5.0,
              len(ratio_rows), 4,
              col_widths_pct=[0.44, 0.21, 0.21, 0.14],
              header_data=["Ratio", "Valeur", "R\u00e9f\u00e9rence", "Signal"],
              rows_data=ratio_rows)

    # Bold les noms d'indicateurs (colonne 0)
    from pptx.util import Pt
    for ri in range(1, len(ratio_rows) + 1):
        try:
            cell = ratio_tbl.cell(ri, 0)
            for run in cell.text_frame.paragraphs[0].runs:
                run.font.bold = True
                run.font.size = Pt(8)
        except Exception:
            pass

    fin_comment = _g(synthesis, "financial_commentary", "") or ""
    if fin_comment.strip():
        commentary_box(slide, 1.02, 11.30, 23.37, 1.30, fin_comment[:500])

    return slide


# ---------------------------------------------------------------------------
# Slide 10 — Ratios Cles
# ---------------------------------------------------------------------------

def _slide_ratios(prs, snap, synthesis, ratios):
    from pptx.enum.text import PP_ALIGN
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    navy_bar(slide)
    footer_bar(slide)
    section_dots(slide, 2)

    years_sorted  = _valid_years(snap)
    latest_yr_key = years_sorted[-1] if years_sorted else None

    slide_title(slide, "Ratios Cl\u00e9s vs. Benchmark Sectoriel",
                f"Positionnement relatif  \u00b7  LTM {latest_yr_key or ''}")

    pe   = _ratio(ratios, "pe_ratio")
    ev_e = _ratio(ratios, "ev_ebitda")
    ev_r = _ratio(ratios, "ev_revenue")
    gm   = _ratio(ratios, "gross_margin")
    em   = _ratio(ratios, "ebitda_margin")
    roe  = _ratio(ratios, "roe")
    az   = _ratio(ratios, "altman_z")
    bm   = _ratio(ratios, "beneish_m")
    roic = _ratio(ratios, "roic")
    capex_rev = _ratio(ratios, "capex_revenue")
    # Si capex_revenue absent des ratios, le calculer depuis snap
    if capex_rev is None and snap and latest_yr_key:
        capex_raw = _fy(snap, latest_yr_key, "capex")
        rev_raw   = _fy(snap, latest_yr_key, "revenue")
        if capex_raw is not None and rev_raw and float(rev_raw) > 0:
            capex_rev = abs(float(capex_raw)) / float(rev_raw)

    def _lecture_pe(v):
        if v is None: return "—"
        try:
            v = float(v)
            if v < 0:    return "Deficit"
            if v < 15:   return "Sous-value"
            if v < 25:   return "Correct"
            if v < 40:   return "Premium"
            return "Eleve"
        except: return "—"

    def _lecture_eve(v):
        if v is None: return "—"
        try:
            v = float(v)
            if v < 8:   return "Bas"
            if v < 14:  return "Correct"
            if v < 20:  return "Premium"
            return "Tr\u00e8s \u00e9lev\u00e9"
        except: return "—"

    def _lecture_z(v):
        if v is None: return "—"
        try:
            v = float(v)
            if v >= 2.99: return "Solide"
            if v >= 1.81: return "Zone grise"
            return "D\u00e9tresse"
        except: return "—"

    def _lecture_bm(v):
        if v is None: return "—"
        try:
            return "Risque manip." if float(v) > -2.22 else "Aucun signal"
        except: return "—"

    def _lecture_evr(v):
        if v is None: return "—"
        try:
            v = float(v)
            if v < 1:   return "Sous-value"
            if v < 5:   return "Correct"
            if v < 10:  return "Premium"
            return "Tr\u00e8s \u00e9lev\u00e9"
        except: return "—"

    def _lecture_gm(v):
        if v is None: return "—"
        try:
            v = float(v) * 100
            if v >= 60: return "Excellent"
            if v >= 40: return "Bon"
            if v >= 20: return "Correct"
            return "Bas"
        except: return "—"

    def _lecture_em(v):
        if v is None: return "—"
        try:
            v = float(v) * 100
            if v >= 30: return "Excellent"
            if v >= 20: return "Bon"
            if v >= 10: return "Correct"
            return "Bas"
        except: return "—"

    def _lecture_roe(v):
        if v is None: return "—"
        try:
            v = float(v) * 100
            if v >= 20: return "Excellent"
            if v >= 15: return "Bon"
            if v >= 5:  return "Correct"
            return "Bas"
        except: return "—"

    def _lecture_roic(v):
        if v is None: return "—"
        try:
            v = float(v) * 100
            if v >= 15: return "Excellent"
            if v >= 10: return "Bon"
            if v >= 5:  return "Correct"
            return "Bas"
        except: return "—"

    def _lecture_capex(v):
        if v is None: return "—"
        try:
            v = abs(float(v)) * 100
            if v < 5:   return "L\u00e9ger"
            if v < 15:  return "Mod\u00e9r\u00e9"
            return "Intensif"
        except: return "—"

    rows = [
        ["P/E",            _frx(pe),       "15\u201325x",  _lecture_pe(pe)],
        ["EV/EBITDA",      _frx(ev_e),     "8\u201314x",   _lecture_eve(ev_e)],
        ["EV/Revenue",     _frx(ev_r),     "1\u20135x",    _lecture_evr(ev_r)],
        ["Marge brute",    _frpct(gm),     "> 40 %",       _lecture_gm(gm)],
        ["Marge EBITDA",   _frpct(em),     "> 20 %",       _lecture_em(em)],
        ["ROE",            _frpct(roe),    "> 15 %",       _lecture_roe(roe)],
        ["ROIC",           _frpct(roic),   "> 10 %",       _lecture_roic(roic)],
        ["CapEx / Revenue",_frpct(capex_rev), "< 15 %",   _lecture_capex(capex_rev)],
        ["Altman Z",       _fr(az, 2),     "> 2,99",       _lecture_z(az)],
        ["Beneish M",      _fr(bm, 2),     "< -2,22",      _lecture_bm(bm)],
    ]

    ratio_tbl = add_table(slide, 1.02, 2.54, 23.37, 7.11,
              len(rows), 4,
              col_widths_pct=[0.25, 0.25, 0.25, 0.25],
              header_data=["Indicateur", "Valeur", "Benchmark", "Lecture"],
              rows_data=rows,
              border_hex="DDDDDD")

    # Per-cell coloring of Lecture column (col 3) + Valeur column navy bold (col 1)
    _GOOD_READS  = {"solide", "correct", "en ligne", "dans la norme", "sous-value", "aucun signal",
                    "bon", "excellent", "leger"}
    _WARN_READS  = {"élevé", "très élevé", "premium", "risque manip.", "détresse", "deficit",
                    "supérieur", "inférieure", "bas", "zone grise", "décote", "intensif"}
    _NEUT_READS  = {"en ligne", "prime technologique", "modéré"}  # amber category

    from pptx.util import Pt
    for ri in range(1, len(rows) + 1):
        # Valeur column (col 1): navy bold
        cell_v = ratio_tbl.cell(ri, 1)
        try:
            p = cell_v.text_frame.paragraphs[0]
            for run in p.runs:
                run.font.color.rgb = rgb(NAVY)
                run.font.bold = True
        except Exception: pass

        # Lecture column (col 3): colored fill + bold
        cell_l = ratio_tbl.cell(ri, 3)
        val_str = (rows[ri - 1][3] or "").strip().lower()
        if val_str in _GOOD_READS:
            cell_l.fill.solid()
            cell_l.fill.fore_color.rgb = rgb(GREEN_PALE)
            lec_tc = GREEN
        elif val_str in _NEUT_READS or val_str in {"supérieur", "supérieure"}:
            cell_l.fill.solid()
            cell_l.fill.fore_color.rgb = rgb(AMBER_PALE)
            lec_tc = AMBER
        elif val_str in _WARN_READS:
            cell_l.fill.solid()
            cell_l.fill.fore_color.rgb = rgb(RED_PALE)
            lec_tc = RED
        else:
            lec_tc = GREY_TXT
        try:
            p = cell_l.text_frame.paragraphs[0]
            for run in p.runs:
                run.font.color.rgb = rgb(lec_tc)
                run.font.bold = True
        except Exception: pass

    ratio_comment = _g(synthesis, "ratio_commentary", "") or ""
    if ratio_comment.strip():
        commentary_box(slide, 1.02, 10.08, 23.37, 2.29, ratio_comment)

    return slide


# ---------------------------------------------------------------------------
# Slide 12 — DCF & Scenarios
# ---------------------------------------------------------------------------

def _slide_dcf(prs, snap, synthesis, ratios):
    from pptx.enum.text import PP_ALIGN
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    navy_bar(slide)
    footer_bar(slide)
    section_dots(slide, 3)
    slide_title(slide, "Valorisation \u2014 DCF & Sc\u00e9narios")

    ci      = snap.company_info if snap else None
    mkt     = snap.market if snap else None
    currency= _g(ci, "currency", "USD") or "USD"
    cur_sym = "EUR" if currency == "EUR" else "$"
    price   = _g(mkt, "share_price")
    wacc    = _g(mkt, "wacc") or 0.10
    beta    = _g(mkt, "beta_levered")
    rfr     = _g(mkt, "risk_free_rate") or 0.041
    erp     = _g(mkt, "erp") or 0.055
    tgr     = _g(mkt, "terminal_growth") or 0.03

    tbase   = _g(synthesis, "target_base")
    tbear   = _g(synthesis, "target_bear")
    tbull   = _g(synthesis, "target_bull")

    # LEFT: DCF params table (simplified) + DDE8F5 highlight on valeur intrinseque
    upside_impl = _upside(tbase, price)
    param_rows = [
        ["WACC",                   _frpct(wacc)],
        ["TGR",                    _frpct(tgr)],
        ["Valeur intrins\u00e8que", f"{_fr(tbase, 0)} {cur_sym}" if tbase else "\u2014"],
        ["Cours actuel",           f"{_fr(price, 2)} {cur_sym}" if price else "\u2014"],
        ["Upside implicite",       upside_impl],
    ]
    param_tbl = add_table(slide, 1.02, 2.29, 11.18, 3.81,
              len(param_rows), 2,
              col_widths_pct=[0.55, 0.45],
              header_data=["Param\u00e8tre", "Valeur"],
              rows_data=param_rows,
              border_hex="DDDDDD")

    # Highlight "Valeur intrinsèque" row (row index 3 = data row 2 → tbl row 3)
    from pptx.util import Pt as _Pt_dcf
    try:
        for ci_p in range(2):
            c = param_tbl.cell(3, ci_p)
            c.fill.solid()
            c.fill.fore_color.rgb = rgb("DDE8F5")
            for run in c.text_frame.paragraphs[0].runs:
                run.font.color.rgb = rgb(NAVY)
                run.font.bold = True
    except Exception:
        pass

    # RIGHT: 3-column scenario table (matches reference exactly)
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN as _PA
    sc_tbl_obj = slide.shapes.add_table(4, 3, __import__('pptx.util', fromlist=['Cm']).Cm(12.45), __import__('pptx.util', fromlist=['Cm']).Cm(2.29), __import__('pptx.util', fromlist=['Cm']).Cm(11.94), __import__('pptx.util', fromlist=['Cm']).Cm(3.81)).table
    # Column widths equal
    from pptx.util import Cm as _Cm, Pt as _Pt
    col_w_emu = int(_Cm(11.94)) // 3
    for ci in range(3): sc_tbl_obj.columns[ci].width = col_w_emu

    sc_cfgs = [
        ("Bear",  tbear,  RED,   RED_PALE),
        ("Base",  tbase,  NAVY_MID, NAVY_PALE),
        ("Bull",  tbull,  GREEN, GREEN_PALE),
    ]
    for ci, (lbl, val, accent, pale) in enumerate(sc_cfgs):
        # Row 0: header label
        c = sc_tbl_obj.cell(0, ci)
        c.fill.solid(); c.fill.fore_color.rgb = rgb(accent)
        _set_cell(c, lbl, font_size=10, bold=True, color_hex=WHITE, align=_PA.CENTER)
        # Row 1: price value (large)
        c = sc_tbl_obj.cell(1, ci)
        c.fill.solid(); c.fill.fore_color.rgb = rgb(pale)
        price_str = f"{_fr(val, 0)} {cur_sym}" if val else "\u2014"
        _set_cell(c, price_str, font_size=20, bold=True, color_hex=accent, align=_PA.CENTER)
        # Row 2: upside
        c = sc_tbl_obj.cell(2, ci)
        c.fill.solid(); c.fill.fore_color.rgb = rgb(pale)
        _set_cell(c, _upside(val, price), font_size=12, bold=True, color_hex=accent, align=_PA.CENTER)
        # Row 3: footer label
        c = sc_tbl_obj.cell(3, ci)
        c.fill.solid(); c.fill.fore_color.rgb = rgb(pale)
        _set_cell(c, "Upside / Downside", font_size=7, bold=False, color_hex=GREY_LIGHT, align=_PA.CENTER)

    # Sensitivity table
    add_text_box(slide, 1.02, 6.65, 23.37, 0.56,
                 f"Table de sensibilité — Valeur intrinsèque ({cur_sym})",
                 9, NAVY, bold=True)

    w_deltas = [-0.02, -0.01, 0.00, 0.01, 0.02]
    t_deltas = [-0.01, -0.005, 0.00, 0.005, 0.01]

    header_s = ["WACC \\ TGR"] + [f"{(tgr + t) * 100:.1f}%".replace(".", ",") for t in t_deltas]
    sens_rows = []
    for w_d in w_deltas:
        w_val = wacc + w_d
        row   = [f"{w_val * 100:.1f}%".replace(".", ",")]
        for t_d in t_deltas:
            row.append(_dcf_value(tbase, wacc, tgr, w_d, t_d))
        sens_rows.append(row)

    sens_tbl = add_table(slide, 1.02, 7.37, 23.37, 3.10,
              len(sens_rows), len(header_s),
              header_data=header_s,
              rows_data=sens_rows,
              border_hex="DDDDDD")

    # Cross-highlight: WACC base row + TGR base column = DDE8F5; intersection = NAVY_MID/blanc
    try:
        base_ri = w_deltas.index(0.00) + 1   # +1 for header row
        base_ci = t_deltas.index(0.00) + 1   # +1 for label col
        n_rows_s = len(sens_rows) + 1
        n_cols_s = len(header_s)
        for ri in range(1, n_rows_s):
            for ci in range(1, n_cols_s):
                if ri == base_ri or ci == base_ci:
                    cell = sens_tbl.cell(ri, ci)
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = rgb("DDE8F5")
        # Highlight WACC label cell (col 0) at base row
        try:
            lbl_cell = sens_tbl.cell(base_ri, 0)
            lbl_cell.fill.solid()
            lbl_cell.fill.fore_color.rgb = rgb("DDE8F5")
            for run in lbl_cell.text_frame.paragraphs[0].runs:
                run.font.bold = True
                run.font.color.rgb = rgb(NAVY)
        except Exception:
            pass
        # Intersection: navy_mid + white bold
        base_cell = sens_tbl.cell(base_ri, base_ci)
        base_cell.fill.solid()
        base_cell.fill.fore_color.rgb = rgb(NAVY_MID)
        try:
            p = base_cell.text_frame.paragraphs[0]
            for run in p.runs:
                run.font.color.rgb = rgb(WHITE)
                run.font.bold = True
        except Exception:
            pass
    except Exception:
        pass

    dcf_comment = _g(synthesis, "dcf_commentary", "") or ""
    if dcf_comment.strip():
        commentary_box(slide, 1.02, 10.88, 23.37, 1.52, dcf_comment)

    return slide


# ---------------------------------------------------------------------------
# Slide 13 — Comparable Peers
# ---------------------------------------------------------------------------

def _slide_peers(prs, snap, synthesis, ratios):
    from pptx.enum.text import PP_ALIGN
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    navy_bar(slide)
    footer_bar(slide)
    section_dots(slide, 3)

    ci      = snap.company_info if snap else None
    mkt     = snap.market if snap else None
    currency= _g(ci, "currency", "USD") or "USD"
    cur_sym = "EUR" if currency == "EUR" else "$"
    ticker  = _g(ci, "ticker", "—")
    co_name = _g(ci, "company_name", "—")
    price   = _g(mkt, "share_price")
    shares  = _g(mkt, "shares_diluted")
    mktcap  = (shares * price / 1000) if (shares and price) else None

    slide_title(slide, "Comparable Peers",
                f"Analyse par multiples  \u00b7  LTM  \u00b7  Mkt Cap en Mds {currency}")

    ev_e = _ratio(ratios, "ev_ebitda")
    ev_r = _ratio(ratios, "ev_revenue")
    pe   = _ratio(ratios, "pe_ratio")
    gm   = _ratio(ratios, "gross_margin")
    em   = _ratio(ratios, "ebitda_margin")

    peers = _g(synthesis, "comparable_peers", []) or []

    header = ["Soci\u00e9t\u00e9", "Ticker", "Mkt Cap", "EV/EBITDA", "EV/Rev.", "P/E",
              "Mg Brute", "Mg EBITDA"]

    # Target company row — Mkt Cap en Mds (shares en millions * price / 1000 = Mds)
    mktcap_str = _fr(mktcap, 1) if mktcap else "—"
    target_row = [co_name, ticker, mktcap_str,
                  _frx(ev_e), _frx(ev_r), _frx(pe),
                  _frpct_margin(gm), _frpct_margin(em)]

    rows_data = [target_row]
    rows_fills = ["DDE8F5"]

    for peer in peers[:5]:
        pn   = _g(peer, "name", "—") or "—"
        pt   = _g(peer, "ticker", "—") or "—"
        # Ensure proper title case for company names
        pn = str(pn).strip()
        if pn and pn != "—" and pn == pn.lower():
            pn = pn.title()
        p_mc = _g(peer, "market_cap_mds")
        if p_mc is not None:
            try:
                p_mc_f = float(p_mc)
                # Si le LLM a retourné en millions au lieu de milliards (> 1000 Mds improbable)
                if p_mc_f > 10000:
                    p_mc_f = p_mc_f / 1000
                p_mktcap_str = _fr(p_mc_f, 1)
            except Exception:
                p_mktcap_str = "—"
        else:
            p_mktcap_str = "—"
        prow = [
            pn[:30], str(pt).upper() if pt != "—" else "—",
            p_mktcap_str,
            _frx(_g(peer, "ev_ebitda")),
            _frx(_g(peer, "ev_revenue")),
            _frx(_g(peer, "pe")),
            _frpct_margin(_g(peer, "gross_margin")),
            _frpct_margin(_g(peer, "ebitda_margin")),
        ]
        rows_data.append(prow)
        rows_fills.append(WHITE if len(rows_data) % 2 == 0 else GREY_BG)

    # Median row
    med_eve = _peer_median(peers, "ev_ebitda")
    med_evr = _peer_median(peers, "ev_revenue")
    med_pe  = _peer_median(peers, "pe")
    med_gm  = _peer_median(peers, "gross_margin")
    med_em  = _peer_median(peers, "ebitda_margin")
    median_row = ["Médiane peers", "—", "—",
                  _frx(med_eve), _frx(med_evr), _frx(med_pe),
                  _frpct_margin(med_gm), _frpct_margin(med_em)]
    rows_data.append(median_row)
    rows_fills.append(GREY_BG)

    tbl_h = min(1.0 + len(rows_data) * 0.71, 5.6)
    peers_tbl = add_table(slide, 1.02, 2.54, 23.37, tbl_h,
              len(rows_data), len(header),
              col_widths_pct=[0.20, 0.09, 0.13, 0.12, 0.12, 0.09, 0.13, 0.12],
              header_data=header,
              rows_data=rows_data,
              row_fills=rows_fills)

    # Post-process subject row (row 1): navy bold text
    for ci in range(len(header)):
        cell = peers_tbl.cell(1, ci)
        try:
            p = cell.text_frame.paragraphs[0]
            for run in p.runs:
                run.font.bold = True
                run.font.color.rgb = rgb(NAVY if ci != 1 else NAVY_MID)
                if ci == 1:  # Ticker col: small gray
                    run.font.size = __import__('pptx.util', fromlist=['Pt']).Pt(7.5)
        except Exception:
            pass

    # Post-process peer rows: ticker col (ci=1) small gray
    for ri in range(2, len(rows_data)):  # peer rows (not subject, not median)
        cell = peers_tbl.cell(ri, 1)
        try:
            p = cell.text_frame.paragraphs[0]
            for run in p.runs:
                from pptx.util import Pt as _Pt2
                run.font.size = _Pt2(7.5)
                run.font.color.rgb = rgb(GREY_TXT)
        except Exception:
            pass

    # Median row (last row): bold=True, NOT italic
    median_ri = len(rows_data)
    for ci in range(len(header)):
        cell = peers_tbl.cell(median_ri, ci)
        try:
            p = cell.text_frame.paragraphs[0]
            for run in p.runs:
                run.font.bold = True
                run.font.italic = False
        except Exception:
            pass

    peers_comment = _g(synthesis, "peers_commentary", "") or _g(synthesis, "ratio_commentary", "") or ""
    if peers_comment.strip():
        commentary_box(slide, 1.02, 8.69, 23.37, 3.43, peers_comment)

    return slide


# ---------------------------------------------------------------------------
# Slide 14 — Football Field
# ---------------------------------------------------------------------------

def _slide_football_field(prs, snap, synthesis, ratios):
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    navy_bar(slide)
    footer_bar(slide)
    section_dots(slide, 3)

    ci       = snap.company_info if snap else None
    mkt      = snap.market if snap else None
    currency = _g(ci, "currency", "USD") or "USD"
    cur_sym  = "EUR" if currency == "EUR" else "$"
    price    = _g(mkt, "share_price")

    slide_title(slide, "Football Field Chart",
                f"Synth\u00e8se des m\u00e9thodes de valorisation  \u00b7  {currency} par action")

    ff     = _g(synthesis, "football_field", []) or []

    # ── Matplotlib Football Field chart ──────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
        _mpl_ok = True
    except Exception:
        _mpl_ok = False

    COLOR_MAP = {
        "DCF - Bear":   "#A82020",
        "DCF - Base":   "#1B3A6B",
        "DCF - Bull":   "#1A7A4A",
        "Comparables":  "#2E5FA3",
        "DDM":          "#B06000",
    }
    DEFAULT_COLORS = ["#1B3A6B", "#2E5FA3", "#1A7A4A", "#A82020", "#B06000",
                      "#6E4FC2", "#888888"]

    ff_methods = []
    ff_lows    = []
    ff_highs   = []
    ff_colors  = []
    for i, item in enumerate(ff):
        label = str(_g(item, "label", "—"))
        low   = _g(item, "range_low")
        high  = _g(item, "range_high")
        if low is None or high is None:
            continue
        lo_f, hi_f = float(low), float(high)
        lo_f, hi_f = min(lo_f, hi_f), max(lo_f, hi_f)   # swap si LLM inverse lo/hi
        if hi_f <= lo_f:
            continue
        ff_methods.append(label)
        ff_lows.append(lo_f)
        ff_highs.append(hi_f)
        ff_colors.append(COLOR_MAP.get(label, DEFAULT_COLORS[i % len(DEFAULT_COLORS)]))

    def _make_ff_buf():
        n = len(ff_methods)
        # Hauteur cible en cm (zone disponible : y=2.54 à y=9.40 avant commentary)
        img_h_cm = min(max(3.8, n * 1.15), 6.8)
        # Dimensions figure proportionnelles à la zone pptx (23.37 x img_h_cm)
        fig_w_in = 12.0
        fig_h_in = img_h_cm * (fig_w_in / 23.37)
        fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))
        y = np.arange(n)
        all_v = ff_lows + ff_highs
        plage = (max(all_v) - min(all_v)) if len(all_v) > 1 else max(all_v)
        offset = max(plage * 0.04, 3.0)
        for i, (lo, hi, col) in enumerate(zip(ff_lows, ff_highs, ff_colors)):
            ax.barh(y[i], hi - lo, left=lo, height=0.52, color=col, alpha=0.87, zorder=3)
            ax.text((lo + hi) / 2, y[i], f"{int((lo + hi) / 2)}",
                    va='center', ha='center', fontsize=9, color='white',
                    fontweight='bold', zorder=4)
            ax.text(lo - offset, y[i], f"{int(lo)}", va='center', ha='right',
                    fontsize=8, color='#444', clip_on=False)
            ax.text(hi + offset, y[i], f"{int(hi)}", va='center', ha='left',
                    fontsize=8, color='#444', clip_on=False)
        if price and ff_lows:
            ax.axvline(x=price, color='#B06000', linewidth=2.0,
                       linestyle='--', zorder=5)
            price_lbl = f"{cur_sym}{price:.0f}"
            ax.text(price, n - 0.05, f"Cours : {price_lbl}",
                    fontsize=8, color='#B06000', fontweight='bold',
                    ha='center', va='top', clip_on=False,
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                              alpha=0.95, edgecolor='#B06000', linewidth=0.8))
        ax.set_yticks(y)
        ax.set_yticklabels(ff_methods, fontsize=9, color='#222')
        margin = max(25, plage * 0.20)
        ax.set_xlim(min(all_v) - margin, max(all_v) + margin)
        ax.set_xlabel(f"Valeur par action ({currency})", fontsize=9, color='#555')
        for sp in ['top', 'right']:
            ax.spines[sp].set_visible(False)
        ax.spines['left'].set_color('#D0D5DD')
        ax.spines['bottom'].set_color('#D0D5DD')
        ax.tick_params(axis='x', labelsize=8.5)
        ax.tick_params(axis='y', length=0)
        ax.set_facecolor('white')
        fig.patch.set_facecolor('white')
        ax.grid(axis='x', alpha=0.3, color='#D0D5DD', zorder=0)
        plt.tight_layout(pad=1.4)
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=180, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf

    if _mpl_ok and ff_methods:
        try:
            chart_buf = _make_ff_buf()
            n_ff = len(ff_methods)
            img_h_cm = min(max(3.8, n_ff * 1.15), 6.8)
            from pptx.util import Cm
            img_top  = Cm(2.54)
            img_left = Cm(1.02)
            img_w    = Cm(23.37)
            img_h    = Cm(img_h_cm)
            slide.shapes.add_picture(chart_buf, img_left, img_top, img_w, img_h)
            commentary_y = 2.54 + img_h_cm + 0.35
        except Exception as e:
            log.warning("FF chart embed failed: %s", e)
            _ff_fallback(slide, ff, price, cur_sym, currency)
            commentary_y = 9.80
    else:
        _ff_fallback(slide, ff, price, cur_sym, currency)
        commentary_y = 9.80

    dcf_comment = _g(synthesis, "dcf_commentary", "") or ""
    if dcf_comment.strip():
        commentary_box(slide, 1.02, commentary_y, 23.37, min(2.54, 19.05 - commentary_y - 0.8), dcf_comment)

    return slide


def _ff_fallback(slide, ff, price, cur_sym, currency):
    """Fallback table when matplotlib unavailable."""
    header = ["Méthode", "Fourchette basse", "Fourchette haute", "Point central"]
    row_fills_map = {
        "DCF - Bear": RED_PALE,
        "DCF - Base": NAVY_PALE,
        "DCF - Bull": GREEN_PALE,
    }
    rows_data  = []
    rows_fills = []
    for item in ff:
        label = str(_g(item, "label", "—"))
        low   = _g(item, "range_low")
        high  = _g(item, "range_high")
        mid   = _g(item, "midpoint")
        rows_data.append([label, _fr(low, 0), _fr(high, 0), _fr(mid, 0)])
        rows_fills.append(row_fills_map.get(label, GREY_BG))
    rows_data.append([f"Cours actuel ({_fr(price, 2)})", "—", "—", _fr(price, 2)])
    rows_fills.append(NAVY_PALE)
    if not rows_data:
        rows_data  = [["Aucune donnée disponible", "—", "—", "—"]]
        rows_fills = [GREY_BG]
    tbl_h = min(1.0 + len(rows_data) * 0.71, 6.0)
    add_table(slide, 1.02, 2.54, 23.37, tbl_h,
              len(rows_data), 4,
              col_widths_pct=[0.35, 0.20, 0.20, 0.25],
              header_data=header,
              rows_data=rows_data,
              row_fills=rows_fills)


# ---------------------------------------------------------------------------
# Slide 16 — Risques & Conditions d'Invalidation
# ---------------------------------------------------------------------------

def _slide_risques(prs, snap, synthesis, devil, extra_scores: dict = None):
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    navy_bar(slide)
    footer_bar(slide)
    section_dots(slide, 4)
    slide_title(slide, "Risques & Conditions d'Invalidation",
                "Analyse des risques structurels  \u00b7  Th\u00e8se contraire")

    counter_thesis = _g(devil, "counter_thesis", "") or ""
    counter_risks  = _g(devil, "counter_risks", []) or []
    risks_s        = _g(synthesis, "risks", []) or []
    invalidation   = _g(synthesis, "invalidation_list", []) or []

    risk_sources  = counter_risks if counter_risks else risks_s
    ct_parts      = _split_text(counter_thesis, 3)
    neg_themes_s  = _g(synthesis, "negative_themes", []) or []

    card_configs = [
        (RED_PALE,   RED,        "Risque 1"),
        (NAVY_PALE,  NAVY_MID,   "Risque 2"),
        (AMBER_PALE, AMBER,      "Risque 3"),
    ]
    card_w = 7.62
    card_h = 5.33
    card_y = 2.67
    gaps   = [1.02, 8.97, 16.92]

    for i, (fill, accent, label) in enumerate(card_configs):
        cx    = gaps[i]
        risk  = str(risk_sources[i]) if i < len(risk_sources) else label
        body  = ct_parts[i] if i < len(ct_parts) else ""
        # Fallback 1 : negative_themes du synthesis
        if not body.strip():
            body = str(neg_themes_s[i]) if i < len(neg_themes_s) else ""
        # Fallback 2 : utiliser le texte du risque lui-meme comme corps de carte
        # (le titre affiche le debut, le corps affiche l'integralite — plus de carte vide)
        if not body.strip() and risk and risk != label:
            body = risk
        # Fallback 3 : synthesis.risks complet si counter_risks ne fournit que des titres courts
        if not body.strip() and i < len(risks_s):
            body = str(risks_s[i])
        # Fallback ultime : message generique localise
        if not body.strip():
            _generic = [
                "Risque macro-économique : remontée des taux ou ralentissement de la demande mondiale.",
                "Risque sectoriel : intensification de la concurrence ou disruption technologique.",
                "Risque spécifique : détérioration des marges ou exécution stratégique.",
            ]
            body = _generic[i] if i < len(_generic) else "Analyse en cours."
        add_rect(slide, cx, card_y, card_w, card_h, fill)
        add_rect(slide, cx, card_y, card_w, 0.15, accent)
        add_text_box(slide, cx + 0.30, card_y + 0.30, card_w - 0.60, 1.10,
                     _truncate(risk, 220), 9, accent, bold=True, wrap=True)
        add_text_box(slide, cx + 0.30, card_y + 1.60, card_w - 0.60, 3.50,
                     _fit(body, 400), 8, GREY_TXT, wrap=True)

    # Invalidation table
    add_rect(slide, 1.02, 8.33, 23.37, 0.03, "AAAAAA")
    add_text_box(slide, 1.02, 8.53, 23.37, 0.46,
                 "Conditions d'invalidation de la thèse", 9, NAVY, bold=True)

    if not invalidation:
        inv_rows = [
            ["Macro",     "Remontée des taux directeurs > 200bps",              "6-12 mois"],
            ["Sectoriel", "Rupture technologique remettant en cause le modèle", "12-18 mois"],
            ["Société",   "Détérioration matérielle des marges opérationnelles","2-3 trim."],
        ]
    else:
        _AXIS_NORM = {"Societe": "Société", "societe": "Société", "société": "Société",
                      "Sectoriel": "Sectoriel", "Macro": "Macro"}
        inv_rows = []
        for item in invalidation[:3]:
            axis  = str(_g(item, "axis",      "—"))
            axis  = _AXIS_NORM.get(axis, axis)
            cond  = str(_g(item, "condition", "—"))
            horiz = str(_g(item, "horizon",   "—"))
            inv_rows.append([axis, cond, horiz])

    inv_tbl = add_table(slide, 1.02, 9.19, 23.37, 3.05,
              len(inv_rows), 3,
              col_widths_pct=[0.15, 0.65, 0.20],
              header_data=["Axe", "Condition d'invalidation", "Horizon"],
              rows_data=inv_rows)

    # Bold Axe column (col 0)
    for ri in range(1, len(inv_rows) + 1):
        cell = inv_tbl.cell(ri, 0)
        try:
            p = cell.text_frame.paragraphs[0]
            for run in p.runs:
                run.font.bold = True
                run.font.color.rgb = rgb(NAVY)
        except Exception:
            pass

    # --- Bande scores compact : 2 lignes (12.30 → 13.33) ----------------------
    # Ligne 1 : Detresse · M&A · Regime macroeconomique
    # Ligne 2 : Qualite Earnings · Structure Capital · Soutenabilite Dividende
    # Zone disponible : 12.24 (fin table) → 13.39 (footer) = 1.15cm
    if extra_scores:
        _dist  = extra_scores.get('composite_distress') or {}
        _ma    = extra_scores.get('ma_score')           or {}
        _macro = extra_scores.get('macro')              or {}
        _eq    = extra_scores.get('earnings_quality')   or {}
        _cs    = extra_scores.get('capital_structure')  or {}
        _ds    = extra_scores.get('dividend_sustainability') or {}

        _CMAP = {
            'Sain': "1A7A4A", 'Saine': "1A7A4A",
            'Modere': AMBER, 'Moderé': AMBER, 'Moderee': AMBER,
            'Vigilance': AMBER, 'Critique': RED,
            'Tres attractive': "1A7A4A", 'Attractive': "1A7A4A",
            'Moderate': AMBER, 'Peu attractive': RED,
            'Bull': "1A7A4A", 'Bear': RED,
            'Volatile': AMBER, 'Transition': AMBER,
            'Excellente': "1A7A4A", 'Correcte': "1B3A6B",
            'Faible': RED, 'N/D': "B0B0B0",
            'Tres soutenable': "1A7A4A", 'Soutenable': "1A7A4A",
            'Tendu': AMBER, 'Insoutenable': RED,
        }

        strip_h = 0.50
        gap     = 0.03
        bx_w    = 7.79
        bx_x    = [1.02, 9.01, 17.01]

        # --- Ligne 1 : Distress / M&A / Regime ---
        row1_y  = 12.30
        row1_items = []
        if _dist.get('score') is not None:
            d_lbl = _dist.get('label', '—')
            row1_items.append((f"Détresse : {_dist['score']}/100  {d_lbl}",
                               _CMAP.get(d_lbl, NAVY)))
        if _ma.get('score') is not None:
            m_lbl = _ma.get('label', '—')
            row1_items.append((f"M&A : {_ma['score']}/100  {m_lbl}",
                               _CMAP.get(m_lbl, NAVY)))
        regime = _macro.get('regime', '')
        rec_6m = _macro.get('recession_prob_6m')
        if regime and regime != 'Inconnu':
            rec_part = f"  Rec.6M:{rec_6m}%" if rec_6m is not None else ''
            row1_items.append((f"Régime : {regime}{rec_part}", _CMAP.get(regime, NAVY)))

        for i, (txt, col) in enumerate(row1_items[:3]):
            x = bx_x[i]
            add_rect(slide, x, row1_y, bx_w, strip_h, "F0F4F8")
            add_rect(slide, x, row1_y, 0.12, strip_h, col)
            add_text_box(slide, x + 0.22, row1_y + 0.03, bx_w - 0.30, strip_h - 0.06,
                         txt, 7.0, NAVY, bold=False)

        # --- Ligne 2 : Earnings Quality / Structure Capital / Dividende ---
        row2_y = row1_y + strip_h + gap
        row2_items = []

        eq_lbl = _eq.get('label')
        if eq_lbl and eq_lbl != 'N/D':
            cc = _eq.get('cash_conversion')
            cc_str = f" ({cc:.2f}x)" if cc is not None else ''
            row2_items.append((f"Earnings Qualité : {eq_lbl}{cc_str}",
                               _CMAP.get(eq_lbl, NAVY)))

        cs_lbl = _cs.get('label')
        if cs_lbl and cs_lbl != 'N/D':
            ratio = _cs.get('short_term_ratio')
            r_str = f" ({ratio*100:.0f}% CT)" if ratio is not None else ''
            row2_items.append((f"Struct. Capital : {cs_lbl}{r_str}",
                               _CMAP.get(cs_lbl, NAVY)))

        ds_lbl = _ds.get('label')
        if ds_lbl and ds_lbl not in ('N/D', 'Sans dividende'):
            cov = _ds.get('fcf_coverage')
            c_str = f" ({cov:.1f}x)" if cov is not None else ''
            row2_items.append((f"Dividende : {ds_lbl}{c_str}",
                               _CMAP.get(ds_lbl, NAVY)))
        elif not row2_items:
            row2_items = []  # no items → skip row 2

        for i, (txt, col) in enumerate(row2_items[:3]):
            x = bx_x[i]
            add_rect(slide, x, row2_y, bx_w, strip_h, "EBF0F7")
            add_rect(slide, x, row2_y, 0.12, strip_h, col)
            add_text_box(slide, x + 0.22, row2_y + 0.03, bx_w - 0.30, strip_h - 0.06,
                         txt, 7.0, NAVY, bold=False)

    return slide


# ---------------------------------------------------------------------------
# Slide 18 — Sentiment FinBERT
# ---------------------------------------------------------------------------

def _slide_sentiment(prs, snap, synthesis, sentiment):
    from pptx.enum.text import PP_ALIGN
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    navy_bar(slide)
    footer_bar(slide)
    section_dots(slide, 5)

    sent_score    = _g(sentiment, "score", 0.0) or 0.0
    sent_label    = _g(sentiment, "label", "NEUTRAL") or "NEUTRAL"
    sent_articles = _g(sentiment, "articles_analyzed", 0) or 0
    sent_conf     = _g(sentiment, "confidence", 0.0) or 0.0
    sent_breakdown= _g(sentiment, "breakdown", {}) or {}

    sent_label_display = _sent_label_fr(sent_label, sent_score)
    rec = _g(synthesis, "recommendation", "HOLD") or "HOLD"
    sent_meta   = _g(sentiment, "meta", {}) or {}
    engine_used = sent_meta.get("engine", "finbert")
    _is_llm     = engine_used == "llm_groq"
    engine_lbl  = "Modèle LLM Groq" if _is_llm else "FinBERT (fallback)"

    _all_neutral = (sent_articles > 0 and
                    (_g(sent_breakdown, "neutral_count", 0) or 0) >= sent_articles * 0.9)
    _warn_finbert = _all_neutral and not _is_llm

    slide_title(
        slide,
        "Sentiment de March\u00e9 \u2014 " + ("LLM Groq" if _is_llm else "FinBERT"),
        f"Analyse s\u00e9mantique  \u00b7  {sent_articles} articles  \u00b7  7 derniers jours"
        + ("  \u00b7  Classification LLM" if _is_llm else "  \u00b7  English-only fallback"),
    )

    # 4 KPI cards
    kpi_box(slide, 1.02,  2.67, 7.11, 2.79,
            sent_label_display, "Orientation globale",
            f"Score agr\u00e9g\u00e9 : {sent_score:+.3f}".replace(".", ","))
    kpi_box(slide, 8.64,  2.67, 5.08, 2.79,
            str(sent_articles), "Articles analys\u00e9s", "Fen\u00eatre : 7 jours")
    kpi_box(slide, 14.22, 2.67, 4.57, 2.79,
            _frpct(sent_conf), "Confiance IA", engine_lbl)
    _, rec_accent = _rec_colors(rec)
    kpi_box(slide, 19.30, 2.67, 4.83, 2.79,
            rec.upper(), "Coh\u00e9rence", "Align\u00e9 avec la th\u00e8se")

    # Breakdown table
    add_text_box(slide, 1.02, 5.79, 23.37, 0.46,
                 "D\u00e9tail par orientation", 9, NAVY_MID, bold=True)

    pos_val  = _g(sent_breakdown, "avg_positive",  None)
    neg_val  = _g(sent_breakdown, "avg_negative",  None)
    neut_val = _g(sent_breakdown, "avg_neutral",   None)
    pos_cnt  = _g(sent_breakdown, "positive_count", None)
    neg_cnt  = _g(sent_breakdown, "negative_count", None)
    neu_cnt  = _g(sent_breakdown, "neutral_count",  None)

    def _fmt_score(v):
        if v is None: return "\u2014"
        try:    return f"{float(v):+.3f}".replace(".", ",")
        except: return str(v)

    def _cnt(v):
        if v is None: return "\u2014"
        return str(int(v))

    pos_themes  = _g(synthesis, "positive_themes", []) or []
    neg_themes  = _g(synthesis, "negative_themes", []) or []
    # Limiter à 1 thème par ligne pour éviter l'explosion de hauteur du tableau
    pos_theme_str  = _truncate(str(pos_themes[0]), 240) if pos_themes else "Catalyseurs, croissance, r\u00e9sultats"
    neg_theme_str  = _truncate(str(neg_themes[0]), 240) if neg_themes else "Risques macro, concurrence, dette"

    neut_theme_str = ("Actualit\u00e9 sectorielle g\u00e9n\u00e9rale"
                      if _is_llm else "Articles non-anglais \u2014 LLM indisponible ce run"
                      if _all_neutral else "Actualit\u00e9 sectorielle g\u00e9n\u00e9rale")

    # Si count = 0 → score et thème non significatifs, on les masque
    break_rows = [
        ["Positif",
         _cnt(pos_cnt),
         _fmt_score(pos_val) if (pos_cnt or 0) > 0 else "\u2014",
         pos_theme_str       if (pos_cnt or 0) > 0 else "Aucun article class\u00e9 positif"],
        ["Neutre",
         _cnt(neu_cnt),
         _fmt_score(neut_val) if (neu_cnt or 0) > 0 else "\u2014",
         neut_theme_str],
        ["N\u00e9gatif",
         _cnt(neg_cnt),
         _fmt_score(neg_val) if (neg_cnt or 0) > 0 else "\u2014",
         neg_theme_str       if (neg_cnt or 0) > 0 else "Aucun article class\u00e9 n\u00e9gatif"],
    ]
    sent_row_fills = [GREEN_PALE, WHITE, RED_PALE]
    tbl_y    = 6.48
    tbl_h_s  = 3.20
    sent_tbl = add_table(slide, 1.02, tbl_y, 23.37, tbl_h_s,
              3, 4,
              col_widths_pct=[0.15, 0.15, 0.20, 0.50],
              header_data=["Orientation", "Articles", "Score moyen", "Th\u00e8mes principaux"],
              rows_data=break_rows,
              row_fills=sent_row_fills)

    # Bold + colored text per sentiment row
    _sent_colors = [GREEN, GREY_TXT, RED]
    from pptx.util import Pt as _Pt3
    for ri in range(1, 4):
        tc_color = _sent_colors[ri - 1]
        for ci in range(2):  # bold color only on first 2 cols
            cell = sent_tbl.cell(ri, ci)
            try:
                p = cell.text_frame.paragraphs[0]
                for run in p.runs:
                    run.font.bold = True
                    run.font.color.rgb = rgb(tc_color)
            except Exception:
                pass

    # Bannière avertissement si FinBERT fallback + tous neutres
    if _warn_finbert:
        add_rect(slide, 1.02, tbl_y + tbl_h_s + 0.25, 23.37, 0.72, "FFF3CD")
        add_rect(slide, 1.02, tbl_y + tbl_h_s + 0.25, 0.13,  0.72, "E6A817")
        add_text_box(
            slide, 1.35, tbl_y + tbl_h_s + 0.30, 23.0, 0.62,
            "\u26a0  Classification LLM indisponible ce run \u2014 FinBERT English-only class\u00e9 tous les articles FR en neutre. "
            "Les scores ci-dessus ne sont pas significatifs. "
            "Relancer l\u2019analyse lorsque Groq est disponible.",
            7.5, "7D5A00", wrap=True
        )
        # Titres des articles bruts (jusqu'à 8) pour context
        samples = _g(sentiment, "samples", []) or []
        all_news_titles = [s.get("headline", "") for s in samples if s.get("headline")]
        if not all_news_titles:
            # Fallback: reconstruire depuis breakdown si disponible
            all_news_titles = []
        if all_news_titles:
            add_text_box(slide, 1.02, tbl_y + tbl_h_s + 1.15, 23.37, 0.40,
                         "Titres des articles analys\u00e9s (bruts, non class\u00e9s) :",
                         8, NAVY_MID, bold=True)
            art_txt = "\n".join(f"\u2022 {h[:110]}" for h in all_news_titles[:6])
            add_text_box(slide, 1.02, tbl_y + tbl_h_s + 1.60, 23.37, 1.80,
                         art_txt, 7.5, "333333", wrap=True)
        comment_y = tbl_y + tbl_h_s + (3.65 if all_news_titles else 1.20)
    else:
        comment_y = max(tbl_y + tbl_h_s + 0.50, 11.5)

    # Commentaire sentiment — LLM Groq en priorité, fallback agrégé
    val_comment = _g(sentiment, "llm_commentary", "") or ""
    if not val_comment.strip():
        lbl_fr = _sent_label_fr(sent_label, sent_score)
        if _warn_finbert:
            val_comment = (
                f"Analyse de sentiment indisponible ce run : le mod\u00e8le LLM Groq n\u2019a pas pu classifier "
                f"les {sent_articles} articles. FinBERT \u00e9tant English-only, tous les titres "
                f"fran\u00e7ais ont \u00e9t\u00e9 class\u00e9s neutres par d\u00e9faut. "
                f"Relancer l\u2019analyse avec Groq actif pour obtenir un score exploitable."
            )
        else:
            val_comment = (
                f"Le sentiment {lbl_fr.lower()} (score {sent_score:+.3f}) est bas\u00e9 sur "
                f"{sent_articles} articles analys\u00e9s sur 7 jours. "
                f"Confiance IA\u00a0: {sent_conf:.0%}. "
                f"Coh\u00e9rence avec la recommandation {rec}\u00a0: "
                + ("valid\u00e9e." if (sent_score > 0.05 and rec == "BUY") or
                                      (sent_score < -0.05 and rec == "SELL") or
                                      (abs(sent_score) <= 0.05 and rec == "HOLD")
                   else "surveiller.")
            )
    comment_y = min(comment_y, 12.8)
    add_text_box(slide, 1.02, comment_y, 23.37, 2.0,
                 val_comment, 8.5, "333333", wrap=True)

    return slide


# ---------------------------------------------------------------------------
# Slide 19 — Actionnariat
# ---------------------------------------------------------------------------

def _slide_actionnariat(prs, snap, synthesis):
    from pptx.enum.text import PP_ALIGN
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    navy_bar(slide)
    footer_bar(slide)
    section_dots(slide, 5)

    ci       = snap.company_info if snap else None
    gen_date = _fr_date_long(_g(ci, "analysis_date", None) or date.today())

    slide_title(slide, "Actionnariat & Structure du Capital",
                f"R\u00e9partition de l'actionnariat  \u00b7  Au {gen_date}")

    # ----------------------------------------------------------------
    # Données actionnaires depuis snap.institutional_holders (yfinance)
    # ----------------------------------------------------------------
    holders = (getattr(snap, "institutional_holders", None) or []) if snap else []

    # Fallback si aucune donnée réelle
    if not holders:
        holders = [
            {"name": "Institutionnels passifs",  "type": "Institutionnel", "pct": 24.0, "style": "Passif"},
            {"name": "Institutionnels actifs",   "type": "Institutionnel", "pct": 12.0, "style": "Actif"},
            {"name": "Insiders & dirigeants",    "type": "Insiders",       "pct": 8.0,  "style": "Insider"},
            {"name": "Autres (Retail)",          "type": "Retail & autres","pct": 56.0, "style": "\u2014"},
        ]

    # ----------------------------------------------------------------
    # Tableau gauche : Top actionnaires (Actionnaire | Type | % | Style)
    # ----------------------------------------------------------------
    holder_rows = []
    for h in holders:
        pct_val = h.get("pct")
        pct_str = f"{float(pct_val):,.1f}\u00a0%".replace(",", "\u00a0") if pct_val is not None else "\u2014"
        holder_rows.append([
            str(h.get("name", "\u2014"))[:35],
            str(h.get("type", "\u2014")),
            pct_str,
            str(h.get("style", "\u2014")),
        ])

    n_rows      = len(holder_rows)
    tbl_h       = min(0.71 + n_rows * 0.61, 7.0)

    add_text_box(slide, 1.02, 2.08, 13.97, 0.56,
                 "Top actionnaires", 9, NAVY_MID, bold=True)
    holders_tbl = add_table(slide, 1.02, 2.69, 14.73, tbl_h,
              n_rows, 4,
              col_widths_pct=[0.38, 0.26, 0.20, 0.16],
              header_data=["Actionnaire", "Type", "D\u00e9tention\u00a0%", "Style"],
              rows_data=holder_rows,
              border_hex="DDDDDD")

    # Bold + couleur sur la colonne Style
    from pptx.util import Pt as _Pt_h
    _style_colors = {"Passif": "2E5FA3", "Actif": "1A7A4A", "Insider": "B06000"}
    for ri in range(1, n_rows + 1):
        try:
            cell = holders_tbl.cell(ri, 3)
            for run in cell.text_frame.paragraphs[0].runs:
                style_val = holder_rows[ri - 1][3]
                col = _style_colors.get(style_val, GREY_TXT)
                run.font.color.rgb = rgb(col)
                run.font.bold = True
                run.font.size = _Pt_h(7.5)
        except Exception:
            pass

    # ----------------------------------------------------------------
    # Tableau droit : Répartition par type (dynamique depuis les données)
    # ----------------------------------------------------------------
    pct_passif  = sum(h.get("pct") or 0 for h in holders if h.get("style") == "Passif")
    pct_actif   = sum(h.get("pct") or 0 for h in holders if h.get("style") == "Actif")
    pct_insider = sum(h.get("pct") or 0 for h in holders if h.get("style") == "Insider")
    pct_retail  = sum(h.get("pct") or 0 for h in holders if h.get("style") == "\u2014")

    def _pct_str(v):
        return f"{v:.1f}\u00a0%" if v > 0 else "\u2014"

    type_rows = []
    if pct_passif  > 0: type_rows.append(["Institutionnel passif",  _pct_str(pct_passif)])
    if pct_actif   > 0: type_rows.append(["Institutionnel actif",   _pct_str(pct_actif)])
    if pct_insider > 0: type_rows.append(["Insider",                _pct_str(pct_insider)])
    if pct_retail  > 0: type_rows.append(["Retail & autres",        _pct_str(pct_retail)])
    if not type_rows:
        type_rows = [["Donn\u00e9es indisponibles", "\u2014"]]

    type_tbl_h = min(0.71 + len(type_rows) * 0.61, tbl_h)

    add_text_box(slide, 16.00, 2.08, 8.38, 0.56,
                 "R\u00e9partition par type", 9, NAVY_MID, bold=True)
    add_table(slide, 16.00, 2.69, 8.38, type_tbl_h,
              len(type_rows), 2,
              col_widths_pct=[0.60, 0.40],
              header_data=["Type d'actionnaire", "Part estim\u00e9e"],
              rows_data=type_rows,
              border_hex="DDDDDD")

    # ----------------------------------------------------------------
    # Commentaire
    # ----------------------------------------------------------------
    commentary_y = 2.69 + tbl_h + 0.35
    valuation_comment = _g(synthesis, "valuation_comment", "") or ""
    thesis_s          = _g(synthesis, "thesis", "") or ""
    comment_txt = valuation_comment or thesis_s
    if comment_txt.strip():
        commentary_box(slide, 1.02, commentary_y, 23.37, min(2.79, 14.0 - commentary_y), comment_txt[:400])

    return slide


# ---------------------------------------------------------------------------
# Slide 20 — Historique de Cours
# ---------------------------------------------------------------------------

def _slide_historique(prs, snap, synthesis):
    from pptx.enum.text import PP_ALIGN
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    navy_bar(slide)
    footer_bar(slide)
    section_dots(slide, 5)

    ci       = snap.company_info if snap else None
    mkt      = snap.market if snap else None
    ticker   = _g(ci, "ticker", "—")
    currency = _g(ci, "currency", "USD") or "USD"
    cur_sym  = "EUR" if currency == "EUR" else "$"
    exchange = getattr(ci, "exchange", "") or "" if ci else ""
    gen_date = _fr_date_long(_g(ci, "analysis_date", None) or date.today())
    price    = _g(mkt, "share_price")

    _exch_part = f"  \u00b7  {exchange}" if exchange else ""
    slide_title(slide, f"Historique de Cours \u2014 52 Semaines",
                f"{ticker}{_exch_part}  \u00b7  {currency}  \u00b7  Au {gen_date}")

    history = snap.stock_history if (snap and snap.stock_history) else []
    prices  = []
    for pt in history:
        p = _g(pt, "price")
        if p is not None:
            try:
                prices.append(float(p))
            except Exception:
                pass

    p_high = max(prices) if prices else price
    p_low  = min(prices) if prices else price
    p_first = prices[0] if prices else price
    p_last  = prices[-1] if prices else price
    perf_52w = ((p_last / p_first) - 1) if (p_first and p_last and p_first != 0) else None

    # 4 KPI boxes
    kpi_box(slide, 1.02,  2.67, 5.33, 2.08,
            f"{_fr(price, 2)} {cur_sym}", "Cours actuel")
    kpi_box(slide, 6.73,  2.67, 5.33, 2.08,
            f"{_fr(p_high, 2)} {cur_sym}", "Plus haut 52 sem.")
    kpi_box(slide, 12.45, 2.67, 5.33, 2.08,
            f"{_fr(p_low, 2)} {cur_sym}", "Plus bas 52 sem.")
    kpi_box(slide, 18.16, 2.67, 6.10, 2.08,
            _frpct(perf_52w, signed=True),
            "Performance 52 sem.")

    # Titre analytique basé sur la performance
    _perf_label = _frpct(perf_52w, signed=True) if perf_52w is not None else ""
    _trend_txt = ("en hausse" if perf_52w and perf_52w > 0.05
                  else ("en repli" if perf_52w and perf_52w < -0.05 else "stable"))
    _hist_subtitle = (f"Cours {_trend_txt} de {_perf_label} sur 12 mois"
                      if _perf_label else "Evolution du cours — 12 derniers mois")
    add_text_box(slide, 1.02, 5.13, 23.37, 0.46,
                 _hist_subtitle, 9, NAVY, bold=True)

    # Graphique line chart matplotlib (standard sell-side — prix = ligne, pas barres)
    chart_x = 1.02
    chart_y = 5.84
    chart_w = 23.37
    chart_h = 5.08

    _chart_inserted = False
    if prices and len(prices) >= 2:
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import io as _io

            months_lbl = [_g(pt, "month", "") or "" for pt in history[-len(prices):]]

            fig_w_in = 12.0
            fig_h_in = chart_h * (fig_w_in / chart_w)
            fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))
            fig.patch.set_facecolor('#F5F7FA')
            ax.set_facecolor('#F5F7FA')

            x_idx = list(range(len(prices)))
            ax.plot(x_idx, prices, color='#2E5FA3', linewidth=2.2, zorder=3)
            ax.fill_between(x_idx, prices, min(prices) * 0.98,
                            color='#2E5FA3', alpha=0.08)

            # Marqueur dernier cours
            ax.scatter([x_idx[-1]], [prices[-1]], color='#2E5FA3', s=40, zorder=4)
            ax.annotate(f"{prices[-1]:.0f} {currency}",
                        xy=(x_idx[-1], prices[-1]),
                        xytext=(-10, 6), textcoords='offset points',
                        fontsize=8, color='#1B3A6B', fontweight='bold')

            # Plus haut / plus bas
            idx_hi = prices.index(p_high)
            idx_lo = prices.index(p_low)
            ax.annotate(f"H: {p_high:.0f}", xy=(idx_hi, p_high),
                        xytext=(0, 8), textcoords='offset points',
                        fontsize=7, color='#1B5E20',
                        arrowprops=dict(arrowstyle='-', color='#1B5E20', lw=0.7))
            ax.annotate(f"B: {p_low:.0f}", xy=(idx_lo, p_low),
                        xytext=(0, -14), textcoords='offset points',
                        fontsize=7, color='#B71C1C',
                        arrowprops=dict(arrowstyle='-', color='#B71C1C', lw=0.7))

            ax.set_xticks(x_idx)
            ax.set_xticklabels(months_lbl, fontsize=7.5, color='#555', rotation=20, ha='right')
            ax.tick_params(axis='y', labelsize=8, labelcolor='#555')
            ax.set_ylabel(currency, fontsize=8, color='#555')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('#D0D5DD')
            ax.spines['bottom'].set_color('#D0D5DD')
            ax.grid(axis='y', alpha=0.3, color='#D0D5DD', linewidth=0.5)

            plt.tight_layout(pad=0.5)
            _buf = _io.BytesIO()
            fig.savefig(_buf, format='png', dpi=150, bbox_inches='tight')
            plt.close(fig)
            _buf.seek(0)

            from pptx.util import Cm as _Cm
            slide.shapes.add_picture(_buf, _Cm(chart_x), _Cm(chart_y), _Cm(chart_w), _Cm(chart_h))
            _chart_inserted = True
        except Exception as _e:
            log.warning(f"[pptx] historique line chart error: {_e}")

    if not _chart_inserted:
        add_rect(slide, chart_x, chart_y, chart_w, chart_h, GREY_BG,
                 line_hex="D0D0D0", line_width_pt=0.5)
        add_text_box(slide, chart_x + 8.0, chart_y + 2.0, 7.37, 1.0,
                     "Historique de cours non disponible", 10, GREY_TXT)

    # Commentary (plain text) — 400 chars pour eviter troncature visible
    thesis_s = _g(synthesis, "summary", "") or _g(synthesis, "thesis", "") or ""
    if thesis_s.strip():
        add_text_box(slide, 1.02, 11.48, 23.37, 1.91,
                     thesis_s[:400], 8.5, GREY_TXT, wrap=True)

    return slide


# ---------------------------------------------------------------------------
# Slide 21 — Conviction Tracker & Investment Thesis Summary
# ---------------------------------------------------------------------------

def _slide_conviction_tracker(prs, snap, synthesis, ratios, devil, sentiment):
    """Slide 21 : Conviction Tracker JPM-style — visualisation de la these d investissement."""
    from pptx.enum.text import PP_ALIGN
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    navy_bar(slide)
    footer_bar(slide)
    section_dots(slide, 5)

    ci       = snap.company_info if snap else None
    ticker   = _g(ci, "ticker", "—")
    rec      = (_g(synthesis, "recommendation") or "HOLD").upper()
    conv_raw = _g(synthesis, "conviction") or 0.5
    try: conv = float(conv_raw)
    except: conv = 0.5
    conv_pct = int(conv * 100)
    gen_date = _fr_date_long(_g(ci, "analysis_date", None) or date.today())

    slide_title(slide, "Conviction & Th\u00e8se d\u2019Investissement",
                f"{ticker}  \u00b7  FinSight IA  \u00b7  Rapport {gen_date}")

    # ── Bloc recommandation central ─────────────────────────────────────────
    _REC_COL = {"BUY": ("1A7A4A", "E8F5E9"), "SELL": ("A82020", "FFEBEE")}.get(rec, ("B06000", "FFF8E1"))
    add_rect(slide, 0.90, 2.30, 7.50, 3.50, _REC_COL[1], line_hex=_REC_COL[0], line_width_pt=2)
    add_text_box(slide, 0.90, 2.40, 7.50, 1.10, rec, 36, _REC_COL[0], bold=True, align=PP_ALIGN.CENTER)
    add_text_box(slide, 0.90, 3.55, 7.50, 0.55, f"Conviction : {conv_pct}%", 11, GREY_TXT, align=PP_ALIGN.CENTER)
    add_text_box(slide, 0.90, 4.15, 7.50, 0.55, gen_date, 8.5, GREY_TXT, align=PP_ALIGN.CENTER)

    # ── Conviction meter (barre horizontale) ────────────────────────────────
    bar_x, bar_y, bar_w, bar_h = 0.90, 6.10, 7.50, 0.55
    add_rect(slide, bar_x, bar_y, bar_w, bar_h, "E8ECF0")
    add_rect(slide, bar_x, bar_y, bar_w * conv, bar_h, _REC_COL[0])
    add_text_box(slide, bar_x, bar_y - 0.40, bar_w, 0.38, "NIVEAU DE CONVICTION", 7, NAVY, bold=True)
    add_text_box(slide, bar_x + bar_w + 0.1, bar_y, 1.2, bar_h, f"{conv_pct}%", 10, NAVY, bold=True)

    # ── Devil's Advocate delta ───────────────────────────────────────────────
    devil_conv = _g(devil, "devil_conviction") or 0.5
    delta = conv - (float(devil_conv) if devil_conv else 0.5)
    delta_lbl = f"+{delta*100:.0f}% vs Avocat du Diable" if delta >= 0 else f"{delta*100:.0f}% vs Avocat du Diable"
    delta_col = "1A7A4A" if delta >= 0 else "A82020"
    add_rect(slide, 0.90, 7.00, 7.50, 0.75, "F5F7FA")
    add_text_box(slide, 1.00, 7.05, 7.30, 0.65, f"Delta conviction : {delta_lbl}", 8.5, delta_col, bold=True)

    # ── Thesis Summary ───────────────────────────────────────────────────────
    thesis_raw = _g(synthesis, "thesis", "") or ""
    thesis_parts = [p.strip() for p in thesis_raw.split(" | ") if p.strip()] if thesis_raw else []
    add_rect(slide, 9.20, 2.30, 15.20, 0.55, NAVY)
    add_text_box(slide, 9.35, 2.35, 15.0, 0.45, "TH\u00c8SE D\u2019INVESTISSEMENT", 8, WHITE, bold=True)
    y_th = 2.95
    for i, part in enumerate(thesis_parts[:3]):
        add_rect(slide, 9.20, y_th, 0.10, 0.80, _REC_COL[0])
        add_text_box(slide, 9.45, y_th + 0.05, 14.85, 0.75, part[:220], 8.5, GREY_TXT, wrap=True)
        y_th += 0.95

    # ── Catalyseurs / Risques ────────────────────────────────────────────────
    pos_themes = _g(synthesis, "positive_themes") or []
    neg_themes = _g(synthesis, "negative_themes") or []
    y_mid = max(y_th + 0.30, 5.95)

    add_rect(slide, 9.20, y_mid, 7.40, 0.50, "1A7A4A")
    add_text_box(slide, 9.35, y_mid + 0.05, 7.2, 0.40, "CATALYSEURS BULLS", 7.5, WHITE, bold=True)
    y_c = y_mid + 0.60
    for th in (pos_themes[:2] if pos_themes else ["N/D"]):
        _c_txt = _fit(str(th), 68)
        add_text_box(slide, 9.45, y_c, 7.10, 0.45, f"\u2022 {_c_txt}", 7, GREY_TXT, wrap=False)
        y_c += 0.52

    add_rect(slide, 17.00, y_mid, 6.80, 0.50, "A82020")
    add_text_box(slide, 17.10, y_mid + 0.05, 6.6, 0.40, "RISQUES BEARS", 7.5, WHITE, bold=True)
    y_r = y_mid + 0.60
    for th in (neg_themes[:2] if neg_themes else ["N/D"]):
        _r_txt = _fit(str(th), 68)
        add_text_box(slide, 17.10, y_r, 6.6, 0.45, f"\u2022 {_r_txt}", 7, GREY_TXT, wrap=False)
        y_r += 0.52

    # ── Invalidation conditions ──────────────────────────────────────────────
    inv_list = _g(synthesis, "invalidation_list") or []
    if inv_list:
        y_inv = max(y_c, y_r) + 0.40
        if y_inv < 11.5:
            add_rect(slide, 9.20, y_inv, 15.20, 0.45, "FFF3CD")
            add_rect(slide, 9.20, y_inv, 0.10, 0.45, "B06000")
            inv_str = "  \u00b7  ".join(
                f"{_g(it,'axis','?')}: {str(_g(it,'condition',''))[:60]}" for it in inv_list[:2])
            add_text_box(slide, 9.45, y_inv + 0.04, 14.85, 0.38,
                         f"\u26a0 Conditions d\u2019invalidation : {inv_str}", 7.5, "7A5000")

    # ── Note methodologique ──────────────────────────────────────────────────
    add_text_box(slide, 0.90, 13.20, 23.60, 0.45,
                 "FinSight IA genere cette analyse a un instant T. Pour le suivi dans le temps, "
                 "comparer les rapports successifs. La conviction reflete les donnees disponibles a la date d'analyse.",
                 7, GREY_TXT, wrap=True)

    return slide


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _split_text(text: str, n: int) -> list:
    """Divise un texte en n parties. Priorité au séparateur ' | ' (format LLM devil)."""
    if not text:
        return [""] * n
    text = text.strip()
    # Format explicite avec ' | ' (agent_devil)
    if " | " in text:
        parts = [p.strip() for p in text.split(" | ") if p.strip()]
        # Compléter si moins de n parties
        while len(parts) < n:
            parts.append("")
        return parts[:n]
    # Sinon découpage par phrases
    for sep in (". ", "! ", "? "):
        text = text.replace(sep, ".|")
    parts = [p.strip() for p in text.split("|") if p.strip()]
    if not parts:
        return [text[:len(text) // n] for _ in range(n)]
    chunk = max(1, len(parts) // n)
    result = []
    for i in range(n):
        start = i * chunk
        end   = start + chunk if i < n - 1 else len(parts)
        result.append(". ".join(parts[start:end]))
    return result


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# PPTXWriter — classe principale
# ---------------------------------------------------------------------------

class PPTXWriter:
    """
    Genere un pitchbook IB en 20 slides a partir du FinSightState (dict).
    """

    def generate(self, state: dict, output_path: str) -> str:
        try:
            from pptx import Presentation
            from pptx.util import Cm, Emu
        except ImportError:
            raise RuntimeError("python-pptx requis : pip install python-pptx")

        snap, synthesis, ratios, devil, sentiment = _extract_state(state)

        # Scores additionnels (Composite Distress, M&A, Macro)
        _ticker_for_scores = (snap.company_info.ticker if snap and snap.company_info else None) or state.get('ticker', '')
        _yr_for_scores = None
        if snap and ratios and ratios.years:
            _latest_lbl = sorted(ratios.years.keys())[-1] if ratios.years else None
            _yr_for_scores = ratios.years.get(_latest_lbl)
        _extra_scores = {}
        try:
            from agents.agent_quant import (compute_composite_distress, compute_ma_score,
                                            compute_earnings_quality, compute_capital_structure,
                                            compute_dividend_sustainability)
            if _yr_for_scores is not None:
                _extra_scores['composite_distress']      = compute_composite_distress(_yr_for_scores)
                _extra_scores['ma_score']                = compute_ma_score(_yr_for_scores)
                _extra_scores['earnings_quality']        = compute_earnings_quality(_yr_for_scores)
                _extra_scores['capital_structure']       = compute_capital_structure(_yr_for_scores)
                _extra_scores['dividend_sustainability'] = compute_dividend_sustainability(_yr_for_scores)
        except Exception as _ese:
            log.warning("[PPTXWriter] distress/ma_score: %s", _ese)
        try:
            from agents.agent_macro import AgentMacro
            _extra_scores['macro'] = AgentMacro().analyze()
        except Exception as _ese:
            log.warning("[PPTXWriter] macro: %s", _ese)

        # Fallback minimal si snap absent
        if snap is None:
            log.warning("PPTXWriter: raw_data absent dans le state — fallback vide")
            from data.models import FinancialSnapshot, CompanyInfo, MarketData
            snap = FinancialSnapshot(
                ticker="N/A",
                company_info=CompanyInfo(company_name="N/A", ticker="N/A"),
                years={},
                market=MarketData(),
                stock_history=[],
            )

        prs = Presentation()
        prs.slide_width  = Cm(25.4)
        prs.slide_height = Cm(14.29)

        # --- Slide 1: Cover ---
        _slide_cover(prs, snap, synthesis, ratios, devil, sentiment)

        # --- Slide 2: Executive Summary ---
        _slide_exec_summary(prs, snap, synthesis, ratios, devil, sentiment)

        # --- Slide 3: Sommaire ---
        _slide_sommaire(prs, snap, synthesis)

        # --- Slide 4: Divider Company Overview ---
        divider_slide(prs, "01", "Company Overview",
                      "Pr\u00e9sentation, mod\u00e8le \u00e9conomique & donn\u00e9es de march\u00e9")

        # --- Slide 5: Company Overview ---
        _slide_company_overview(prs, snap, synthesis, ratios)

        # --- Slide 6: Business Model ---
        _slide_business_model(prs, snap, synthesis)

        # --- Slide 7: Divider Analyse Financiere ---
        divider_slide(prs, "02", "Analyse Financi\u00e8re",
                      "Compte de r\u00e9sultat, bilan, liquidit\u00e9 & ratios")

        # --- Slide 8: Compte de Resultat ---
        _slide_is(prs, snap, synthesis, ratios)

        # --- Slide 9: Bilan & Liquidite ---
        _slide_bilan(prs, snap, synthesis, ratios)

        # --- Slide 10: Ratios Cles ---
        _slide_ratios(prs, snap, synthesis, ratios)

        # --- Slide 11: Divider Valorisation ---
        divider_slide(prs, "03", "Valorisation",
                      "DCF, comparable peers & Football Field Chart")

        # --- Slide 12: DCF & Scenarios ---
        _slide_dcf(prs, snap, synthesis, ratios)

        # --- Slide 13: Comparable Peers ---
        _slide_peers(prs, snap, synthesis, ratios)

        # --- Slide 14: Football Field ---
        _slide_football_field(prs, snap, synthesis, ratios)

        # --- Slide 15: Divider Risques ---
        divider_slide(prs, "04", "Risques & Strat\u00e9gie",
                      "Avocat du diable & conditions d'invalidation")

        # --- Slide 16: Risques ---
        _slide_risques(prs, snap, synthesis, devil, extra_scores=_extra_scores)

        # --- Slide 17: Divider Sentiment ---
        divider_slide(prs, "05", "Sentiment & Annexes",
                      "FinBERT, actionnariat & historique de cours")

        # --- Slide 18: Sentiment ---
        _slide_sentiment(prs, snap, synthesis, sentiment)

        # --- Slide 19: Actionnariat ---
        _slide_actionnariat(prs, snap, synthesis)

        # --- Slide 20: Historique de Cours ---
        _slide_historique(prs, snap, synthesis)

        # --- Slide 21: Conviction Tracker ---
        _slide_conviction_tracker(prs, snap, synthesis, ratios, devil, sentiment)

        # Save
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(out_path))
        log.info("PPTXWriter: pitchbook sauvegarde -> %s", out_path)
        return str(out_path)
