# =============================================================================
# FinSight IA — PDF Writer
# outputs/pdf_writer.py
#
# Basé sur le template visuel de référence (Goldman/MS style).
# PDFWriter.generate(state, output_path) -> str
# =============================================================================

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# PALETTE
# ═══════════════════════════════════════════════════════════════════
NAVY       = colors.HexColor("#1B3A6B")
NAVY_MID   = colors.HexColor("#2E5FA3")
NAVY_PALE  = colors.HexColor("#EEF3FA")
GREY_RULE  = colors.HexColor("#D0D0D0")
GREY_ROW   = colors.HexColor("#F7F8FA")
GREY_TEXT  = colors.HexColor("#555555")
GREY_LIGHT = colors.HexColor("#888888")
WHITE      = colors.white
BLACK      = colors.HexColor("#0D0D0D")
GREEN      = colors.HexColor("#1A7A4A")
GREEN_PALE = colors.HexColor("#EAF4EF")
RED        = colors.HexColor("#A82020")
RED_PALE   = colors.HexColor("#FAF0EF")
AMBER      = colors.HexColor("#B06000")
AMBER_PALE = colors.HexColor("#FDF6E8")

W, H = A4
CW   = 170   # largeur contenu mm

# ═══════════════════════════════════════════════════════════════════
# TYPOGRAPHIE
# ═══════════════════════════════════════════════════════════════════
def _build_styles():
    return {
        "body":      ParagraphStyle("body",    fontName="Helvetica",      fontSize=8.5, textColor=BLACK,      leading=14, spaceAfter=6,  alignment=TA_JUSTIFY),
        "body_sm":   ParagraphStyle("body_sm", fontName="Helvetica",      fontSize=7.5, textColor=GREY_TEXT,  leading=12, spaceAfter=4,  alignment=TA_JUSTIFY),
        "h1":        ParagraphStyle("h1",      fontName="Helvetica-Bold", fontSize=9,   textColor=NAVY,       leading=13, spaceBefore=0, spaceAfter=5),
        "h2":        ParagraphStyle("h2",      fontName="Helvetica-Bold", fontSize=8.5, textColor=NAVY_MID,   leading=13, spaceBefore=7, spaceAfter=3),
        "hdr_name":  ParagraphStyle("hn",      fontName="Helvetica-Bold", fontSize=12,  textColor=WHITE,      leading=16),
        "hdr_meta":  ParagraphStyle("hm",      fontName="Helvetica",      fontSize=7.5, textColor=colors.HexColor("#B8CCE4"), leading=11, alignment=TA_RIGHT),
        "th":        ParagraphStyle("th",      fontName="Helvetica-Bold", fontSize=7.5, textColor=WHITE,      leading=10, alignment=TA_CENTER),
        "th_left":   ParagraphStyle("thl",     fontName="Helvetica-Bold", fontSize=7.5, textColor=WHITE,      leading=10, alignment=TA_LEFT),
        "td":        ParagraphStyle("td",      fontName="Helvetica",      fontSize=8,   textColor=BLACK,      leading=11, alignment=TA_CENTER),
        "td_l":      ParagraphStyle("tdl",     fontName="Helvetica",      fontSize=8,   textColor=BLACK,      leading=11, alignment=TA_LEFT),
        "td_b":      ParagraphStyle("tdb",     fontName="Helvetica-Bold", fontSize=8,   textColor=BLACK,      leading=11, alignment=TA_CENTER),
        "td_sub":    ParagraphStyle("tds",     fontName="Helvetica-Oblique", fontSize=7.5, textColor=GREY_TEXT, leading=11, alignment=TA_LEFT),
        "td_sub_r":  ParagraphStyle("tdsr",    fontName="Helvetica-Oblique", fontSize=7.5, textColor=GREY_TEXT, leading=11, alignment=TA_CENTER),
        "caption":   ParagraphStyle("cap",     fontName="Helvetica-Oblique", fontSize=7, textColor=GREY_LIGHT, leading=10, spaceAfter=2, spaceBefore=1),
        "disclaimer":ParagraphStyle("dis",     fontName="Helvetica-Oblique", fontSize=6.5, textColor=GREY_LIGHT, leading=9.5, alignment=TA_JUSTIFY),
        "disc_h":    ParagraphStyle("dish",    fontName="Helvetica-Bold", fontSize=7,   textColor=GREY_TEXT,  spaceBefore=0, spaceAfter=2),
        "toc_item":  ParagraphStyle("toci",    fontName="Helvetica",      fontSize=9,   textColor=BLACK,      leading=14, alignment=TA_LEFT),
        "toc_num":   ParagraphStyle("tocn",    fontName="Helvetica-Bold", fontSize=9,   textColor=NAVY,       leading=14, alignment=TA_LEFT),
        "toc_pg":    ParagraphStyle("tocpg",   fontName="Helvetica",      fontSize=9,   textColor=GREY_LIGHT, leading=14, alignment=TA_RIGHT),
        "toc_title": ParagraphStyle("toct",    fontName="Helvetica-Bold", fontSize=14,  textColor=NAVY,       leading=18, alignment=TA_LEFT, spaceAfter=2),
        "toc_intro": ParagraphStyle("tocin",   fontName="Helvetica",      fontSize=8,   textColor=GREY_TEXT,  leading=13, alignment=TA_JUSTIFY),
    }

ST = _build_styles()

# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _enc(s: str) -> str:
    """Encode pour canvas.drawString (Helvetica latin-1)."""
    if not s: return ""
    try:    return s.encode("latin-1", errors="replace").decode("latin-1")
    except: return s

def p(text, s="body"):  return Paragraph(str(text), ST[s])
def sp(h=3):            return Spacer(1, h * mm)
def rule(c=GREY_RULE, t=0.4, b=2, a=4):
    return HRFlowable(width="100%", thickness=t, color=c, spaceBefore=b, spaceAfter=a)

def section(num, title):
    return [sp(5), rule(NAVY, 1.0, b=0, a=3), p(f"{num}.  {title.upper()}", "h1")]

def sub(text):  return p(text, "h2")

def tbl(rows, widths, extra=None):
    total = sum(widths)
    assert abs(total - CW) < 0.8, f"Colonnes = {total:.1f} mm != {CW} mm"
    cells = []
    for i, row in enumerate(rows):
        line = []
        for j, val in enumerate(row):
            if isinstance(val, Paragraph):
                line.append(val)
            elif i == 0:
                line.append(p(str(val), "th_left" if j == 0 else "th"))
            elif j == 0:
                line.append(p(str(val), "td_l"))
            else:
                line.append(p(str(val), "td"))
        cells.append(line)
    base = [
        ("BACKGROUND",    (0,0), (-1,0),  NAVY),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, GREY_ROW]),
        ("GRID",          (0,0), (-1,-1), 0.3, GREY_RULE),
        ("ALIGN",         (1,0), (-1,-1), "CENTER"),
        ("ALIGN",         (0,0), (0,-1),  "LEFT"),
        ("LEFTPADDING",   (0,0), (0,-1),  5),
        ("RIGHTPADDING",  (-1,0),(-1,-1), 4),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("FONTNAME",      (0,1), (0,-1),  "Helvetica-Bold"),
        ("LINEAFTER",     (0,0), (0,-1),  0.4, GREY_RULE),
    ]
    if extra:
        base += extra
    t = Table(cells, colWidths=[w * mm for w in widths], splitByRow=0)
    t.setStyle(TableStyle(base))
    return t

# Formatage nombres (style français : virgule décimale)
_MOIS_FR = {1:"janvier",2:"fevrier",3:"mars",4:"avril",5:"mai",6:"juin",
            7:"juillet",8:"aout",9:"septembre",10:"octobre",11:"novembre",12:"decembre"}

def _date_fr(d=None):
    d = d or date.today()
    return f"{d.day} {_MOIS_FR[d.month]} {d.year}"

def _fr(v, dp=1, suffix=""):
    if v is None: return "—"
    try:
        s = f"{float(v):.{dp}f}".replace(".", ",")
        return s + suffix
    except: return "—"

def _frpct(v, dp=1):
    if v is None: return "—"
    try:    return _fr(float(v) * 100, dp, "\u00a0%")
    except: return "—"

def _frx(v):
    if v is None: return "—"
    try:
        f = float(v)
        return "n.m." if abs(f) > 999 else _fr(f, 1, "x")
    except: return "—"

def _frm(v):
    if v is None: return "—"
    try:
        f = float(v)
        return _fr(f/1000, 1, "B") if abs(f) >= 1000 else _fr(f, 1)
    except: return "—"

def _upside(target, current):
    if target is None or current is None: return "—"
    try:
        c = float(current)
        if c == 0: return "—"
        u = (float(target) - c) / abs(c) * 100
        return f"{u:+.0f}\u00a0%".replace(".", ",")
    except: return "—"

def _g(obj, *keys, default=None):
    for k in keys:
        if obj is None: return default
        obj = obj.get(k) if isinstance(obj, dict) else getattr(obj, k, None)
    return obj if obj is not None else default

def _rec_color(rec):
    r = (rec or "").upper()
    if r == "BUY":  return GREEN
    if r == "SELL": return RED
    return AMBER

def _rec_pale(rec):
    r = (rec or "").upper()
    if r == "BUY":  return GREEN_PALE
    if r == "SELL": return RED_PALE
    return AMBER_PALE

def _lecture(val, bm_str, pct=False):
    import re as _re
    try:
        v = float(val) * (100 if pct else 1)
        nums = _re.findall(r'\d+(?:[,.]\d+)?', bm_str.replace(",", "."))
        if len(nums) < 2: return "\u2014"
        lo, hi = float(nums[0].replace(",",".")), float(nums[1].replace(",","."))
        if not pct and v > hi * 1.4: return "Prime technologique"
        if v > hi: return "Sup\u00e9rieure" if pct else "Sup\u00e9rieur"
        if v < lo: return "Inf\u00e9rieure" if pct else "D\u00e9cote"
        return "En ligne" if pct else "Dans la norme"
    except: return "\u2014"

def _benchmarks(sector):
    s = (sector or "").lower()
    if any(w in s for w in ("tech","software","semiconductor","information")):
        return dict(pe="15\u2013\u202035x", ev_e="12\u2013\u202025x", ev_r="3\u2013\u202012x",
                    gm="55\u2013\u202075\u00a0%", em="20\u2013\u202035\u00a0%", roe="15\u2013\u202030\u00a0%")
    if any(w in s for w in ("health","pharma","biotech")):
        return dict(pe="18\u2013\u202030x", ev_e="12\u2013\u202020x", ev_r="3\u2013\u20208x",
                    gm="60\u2013\u202075\u00a0%", em="20\u2013\u202030\u00a0%", roe="12\u2013\u202020\u00a0%")
    if any(w in s for w in ("financ","bank","insur")):
        return dict(pe="10\u2013\u202016x", ev_e="8\u2013\u202012x", ev_r="2\u2013\u20204x",
                    gm="50\u2013\u202065\u00a0%", em="30\u2013\u202045\u00a0%", roe="10\u2013\u202018\u00a0%")
    if any(w in s for w in ("energy","oil","gas")):
        return dict(pe="10\u2013\u202018x", ev_e="6\u2013\u202010x", ev_r="1\u2013\u20203x",
                    gm="30\u2013\u202050\u00a0%", em="25\u2013\u202040\u00a0%", roe="10\u2013\u202015\u00a0%")
    if any(w in s for w in ("consumer","retail","luxury","auto","cyclical")):
        return dict(pe="8\u2013\u202015x", ev_e="6\u2013\u202012x", ev_r="0,4\u2013\u20201,2x",
                    gm="12\u2013\u202018\u00a0%", em="8\u2013\u202014\u00a0%", roe="8\u2013\u202018\u00a0%")
    return dict(pe="15\u2013\u202022x", ev_e="10\u2013\u202016x", ev_r="2\u2013\u20205x",
                gm="35\u2013\u202055\u00a0%", em="15\u2013\u202025\u00a0%", roe="10\u2013\u202018\u00a0%")


# ═══════════════════════════════════════════════════════════════════
# FOOTER / HEADER — pages 2-6 uniquement
# ═══════════════════════════════════════════════════════════════════

def _make_footer(company_name, ticker):
    def footer(canvas, doc):
        canvas.saveState()
        y = 11 * mm
        canvas.setStrokeColor(GREY_RULE)
        canvas.setLineWidth(0.3)
        canvas.line(20*mm, y+3*mm, W-20*mm, y+3*mm)
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(GREY_LIGHT)
        canvas.drawString(20*mm, y,
            _enc(f"FinSight IA  \u00b7  {company_name} ({ticker})  \u00b7  Usage confidentiel"))
        # Page numero : on affiche doc.page - 1 car page 1 = cover
        canvas.drawRightString(W-20*mm, y, f"{doc.page - 1}")
        # En-tete discret
        yh = H - 9*mm
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(GREY_LIGHT)
        canvas.drawString(20*mm, yh, _enc(f"{company_name}  ({ticker})"))
        canvas.drawRightString(W-20*mm, yh, "FinSight IA  \u2014  Confidentiel")
        canvas.setLineWidth(0.3)
        canvas.setStrokeColor(GREY_RULE)
        canvas.line(20*mm, yh-2*mm, W-20*mm, yh-2*mm)
        canvas.restoreState()
    return footer


# ═══════════════════════════════════════════════════════════════════
# COVER — page 1, canvas seulement, aucun header/footer
# ═══════════════════════════════════════════════════════════════════

def _draw_cover(canvas, doc, ticker, company_name, sector, exchange, gen_date):
    canvas.saveState()
    cx = W / 2

    # Bande navy pleine en haut (12mm)
    canvas.setFillColor(NAVY)
    canvas.rect(0, H-12*mm, W, 12*mm, fill=1, stroke=0)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(WHITE)
    canvas.drawCentredString(cx, H-8*mm, "FinSight IA")

    # Zone centrale — légèrement au-dessus du milieu
    mid_y = H * 0.52

    # Ligne décorative courte au-dessus du titre
    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(1.0)
    canvas.line(cx-25*mm, mid_y+14*mm, cx+25*mm, mid_y+14*mm)

    # Sous-titre
    canvas.setFont("Helvetica", 11)
    canvas.setFillColor(colors.HexColor("#555555"))
    canvas.drawCentredString(cx, mid_y+6*mm, _enc("Rapport d'analyse"))

    # Nom société (grand, navy bold) — retour à la ligne si trop long
    canvas.setFont("Helvetica-Bold", 26)
    canvas.setFillColor(NAVY)
    words = company_name.split()
    if len(company_name) <= 28 or not words:
        lines = [company_name]
    else:
        # Découpe au mot le plus proche du milieu
        mid = len(company_name) // 2
        best, best_pos = 0, 0
        pos = 0
        for i, w in enumerate(words):
            pos += len(w) + (1 if i > 0 else 0)
            if abs(pos - mid) < abs(best_pos - mid):
                best, best_pos = i + 1, pos
        lines = [" ".join(words[:best]), " ".join(words[best:])]
        lines = [l for l in lines if l]

    line_h = 10 * mm
    start_y = mid_y - 8*mm if len(lines) == 1 else mid_y + (line_h * (len(lines)-1)) / 2 - 8*mm
    for i, ln in enumerate(lines):
        canvas.drawCentredString(cx, start_y - i * line_h, _enc(ln))

    # Ticker · Exchange · Secteur
    parts = "  \u00b7  ".join(x for x in [ticker, exchange, sector] if x)
    canvas.setFont("Helvetica", 10)
    canvas.setFillColor(colors.HexColor("#888888"))
    ticker_y = start_y - len(lines) * line_h - 2*mm
    canvas.drawCentredString(cx, ticker_y, _enc(parts))

    # Bas de page — ligne + "Rapport confidentiel" + date
    fy = 18*mm
    canvas.setStrokeColor(colors.HexColor("#CCCCCC"))
    canvas.setLineWidth(0.5)
    canvas.line(20*mm, fy+5*mm, W-20*mm, fy+5*mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawString(20*mm, fy, "Rapport confidentiel")
    canvas.drawRightString(W-20*mm, fy, _enc(gen_date))

    canvas.restoreState()


# ═══════════════════════════════════════════════════════════════════
# PAGE SOMMAIRE
# ═══════════════════════════════════════════════════════════════════

def _page_toc(story, gen_date, snap=None, synthesis=None):
    story.append(sp(10))
    story.append(Paragraph("Sommaire", ST["toc_title"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=NAVY, spaceBefore=2, spaceAfter=10))

    toc_items = [
        ("1.", "Synth\u00e8se Ex\u00e9cutive",       "2"),
        ("2.", "Analyse Financi\u00e8re",            "3"),
        ("3.", "Valorisation",                   "4"),
        ("4.", "Analyse des Risques & Sentiment","5"),
    ]
    for num, title, pg in toc_items:
        row = Table([[
            Paragraph(num, ST["toc_num"]),
            Paragraph(title, ST["toc_item"]),
            Paragraph(pg, ST["toc_pg"]),
        ]], colWidths=[10*mm, 145*mm, 15*mm])
        row.setStyle(TableStyle([
            ("TOPPADDING",    (0,0),(-1,-1), 6),
            ("BOTTOMPADDING", (0,0),(-1,-1), 6),
            ("LEFTPADDING",   (0,0),(-1,-1), 0),
            ("RIGHTPADDING",  (0,0),(-1,-1), 0),
            ("LINEBELOW",     (0,0),(-1,-1), 0.3, GREY_RULE),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ]))
        story.append(row)

    # Donnees cles — liste propre sans tableau
    if snap and synthesis:
        story.append(sp(12))
        story.append(HRFlowable(width="100%", thickness=0.4, color=GREY_RULE, spaceBefore=0, spaceAfter=6))
        story.append(Paragraph("Donn\u00e9es cl\u00e9s", ST["h1"]))
        story.append(sp(2))
        ci  = snap.company_info
        mkt = snap.market
        cur = ci.currency or "USD"
        rec  = (_g(synthesis,"recommendation") or "HOLD").upper()
        conv = _g(synthesis,"conviction")
        tbase = _g(synthesis,"target_base")
        price = mkt.share_price

        lbl_st  = ParagraphStyle("kfl", fontName="Helvetica",     fontSize=7.5, textColor=GREY_TEXT, leading=12)
        val_st  = ParagraphStyle("kfv", fontName="Helvetica-Bold", fontSize=8.5, textColor=NAVY,      leading=12)

        kf_rows = [
            [("Ticker",            ci.ticker or "\u2014"),
             ("Recommandation",    rec)],
            [("Soci\u00e9t\u00e9", ci.company_name or "\u2014"),
             ("Conviction",        _frpct(conv) if conv else "\u2014")],
            [("Secteur",           ci.sector or "\u2014"),
             ("Cours",             f"{_fr(price,2)}\u00a0{cur}" if price else "\u2014")],
            [("Devise",            cur),
             ("Cible base",        f"{_fr(tbase,0)}\u00a0{cur}" if tbase else "\u2014")],
            [("Date d'analyse",    gen_date),
             ("",                  "")],
        ]
        kf_data = []
        for (l1,v1),(l2,v2) in kf_rows:
            kf_data.append([
                Paragraph(l1, lbl_st), Paragraph(v1, val_st),
                Paragraph(l2, lbl_st), Paragraph(v2, val_st),
            ])
        kf_tbl = Table(kf_data, colWidths=[28*mm, 52*mm, 38*mm, 52*mm], splitByRow=0)
        kf_tbl.setStyle(TableStyle([
            ("TOPPADDING",    (0,0),(-1,-1), 5),
            ("BOTTOMPADDING", (0,0),(-1,-1), 5),
            ("LEFTPADDING",   (0,0),(-1,-1), 0),
            ("RIGHTPADDING",  (0,0),(-1,-1), 4),
            ("LINEAFTER",     (1,0),(1,-1),  0.8,  GREY_RULE),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ]))
        story.append(kf_tbl)

    # À propos de cette analyse
    story.append(sp(10))
    story.append(HRFlowable(width="100%", thickness=0.4, color=GREY_RULE, spaceBefore=0, spaceAfter=6))
    story.append(Paragraph("\u00c0 propos de cette analyse", ST["h1"]))
    story.append(sp(3))
    story.append(Paragraph(
        "L'analyse fondamentale repose sur les donn\u00e9es financi\u00e8res historiques issues de sources "
        "publiques (yfinance, Finnhub Financial, Financial Modeling Prep). La valorisation DCF "
        "est calcul\u00e9e sur un horizon de cinq ans avec sensibilit\u00e9 au WACC et au taux de croissance "
        "terminal. L'analyse de sentiment est conduite par FinBERT, mod\u00e8le de traitement du "
        "langage naturel sp\u00e9cialis\u00e9 en finance, sur un corpus d'articles des sept derniers jours.",
        ST["toc_intro"]))
    story.append(sp(4))
    story.append(Paragraph(
        "La th\u00e8se d'investissement est soumise \u00e0 un protocole de contradiction syst\u00e9matique "
        "(avocat du diable) visant \u00e0 identifier les hypoth\u00e8ses les plus fragiles et les "
        "sc\u00e9narios de baisse. Les conditions d'invalidation sont explicitement formul\u00e9es "
        "pour chaque axe de risque\u00a0: macro\u00e9conomique, sectoriel et sp\u00e9cifique \u00e0 la soci\u00e9t\u00e9.",
        ST["toc_intro"]))
    story.append(PageBreak())


# ═══════════════════════════════════════════════════════════════════
# PAGE 1 — SYNTHESE EXECUTIVE
# ═══════════════════════════════════════════════════════════════════

def _page_synthese(story, snap, synthesis):
    ci    = snap.company_info
    mkt   = snap.market
    cur   = ci.currency or "USD"
    price = mkt.share_price

    rec   = (_g(synthesis,"recommendation") or "HOLD").upper()
    conv  = _g(synthesis,"conviction")
    conf  = _g(synthesis,"confidence_score")
    tbase = _g(synthesis,"target_base")
    tbear = _g(synthesis,"target_bear")
    tbull = _g(synthesis,"target_bull")
    desc  = _g(synthesis,"company_description") or _g(synthesis,"summary") or ""
    thesis= _g(synthesis,"thesis") or ""
    stren = _g(synthesis,"strengths") or []
    risks = _g(synthesis,"risks") or []

    exchange  = getattr(ci,"exchange","") or ""
    sector    = ci.sector or ""
    price_s   = _fr(price, 2, f"\u00a0{cur}")
    tbase_s   = _fr(tbase, 0, f"\u00a0{cur}") if tbase else "N/A"
    conv_s    = _frpct(conv) if conv is not None else "N/A"
    conf_s    = _frpct(conf) if conf is not None else "N/A"
    up_s      = _upside(tbase, price)

    # Header navbar
    hdr = Table([[
        p(ci.company_name or ci.ticker, "hdr_name"),
        p(f"{ci.ticker}  \u00b7  {exchange}  \u00b7  {sector}  \u00b7  {_date_fr()}", "hdr_meta"),
    ]], colWidths=[80*mm, 90*mm])
    hdr.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), NAVY),
        ("TOPPADDING",    (0,0),(-1,-1), int(4.5*mm)),
        ("BOTTOMPADDING", (0,0),(-1,-1), int(4.5*mm)),
        ("LEFTPADDING",   (0,0),(0,-1),  int(7*mm)),
        ("RIGHTPADDING",  (-1,0),(-1,-1),int(7*mm)),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ]))
    story.append(hdr)

    # Bande recommandation
    rec_col  = _rec_color(rec)
    rec_pale = _rec_pale(rec)
    rec_style = ParagraphStyle("rc", fontName="Helvetica-Bold", fontSize=9.5,
                               textColor=rec_col, leading=13)
    line_style = ParagraphStyle("rl", fontName="Helvetica", fontSize=8,
                                textColor=NAVY, leading=12, alignment=TA_RIGHT)
    rec_band = Table([[
        Paragraph(f"&#9679;  {rec}", rec_style),
        Paragraph(
            f"Cours\u00a0: {price_s}  \u00b7  Cible base\u00a0: {tbase_s}  \u00b7  "
            f"Upside\u00a0: {up_s}  \u00b7  Conviction\u00a0: {conv_s}  \u00b7  "
            f"Confiance IA\u00a0: {conf_s}", line_style),
    ]], colWidths=[30*mm, 140*mm])
    rec_band.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), rec_pale),
        ("TOPPADDING",    (0,0),(-1,-1), int(2.5*mm)),
        ("BOTTOMPADDING", (0,0),(-1,-1), int(2.5*mm)),
        ("LEFTPADDING",   (0,0),(0,-1),  int(7*mm)),
        ("RIGHTPADDING",  (-1,0),(-1,-1),int(7*mm)),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ]))
    story.append(rec_band)
    story.append(sp(5))

    # Description
    if desc:
        story.append(p(desc))
        story.append(sp(4))

    # Scenarios
    story.append(sub("Scenarios de valorisation"))

    def _hyp(s_list, idx=0):
        if not s_list or idx >= len(s_list): return "—"
        s = s_list[idx]
        return s if len(s) <= 80 else s[:78]+"…"

    scen = [
        ["", "Bear", "Base", "Bull"],
        [f"Prix cible ({cur})", _fr(tbear,0), _fr(tbase,0), _fr(tbull,0)],
        ["Upside\u00a0/\u00a0Downside", _upside(tbear,price), _upside(tbase,price), _upside(tbull,price)],
        ["Probabilite estimee", "25\u00a0%", "50\u00a0%", "25\u00a0%"],
        ["Hypothese determinante", _hyp(risks,0), _hyp(stren,0) if stren else "—", _hyp(stren,1) if len(stren)>1 else "—"],
    ]
    story.append(tbl(scen, [46, 38, 46, 40], extra=[
        ("BACKGROUND", (1,1),(1,-1), RED_PALE),
        ("BACKGROUND", (2,1),(2,-1), NAVY_PALE),
        ("BACKGROUND", (3,1),(3,-1), GREEN_PALE),
        ("TEXTCOLOR",  (1,2),(1,2),  RED),
        ("TEXTCOLOR",  (3,2),(3,2),  GREEN),
        ("FONTNAME",   (1,2),(3,2),  "Helvetica-Bold"),
        ("FONTSIZE",   (0,4),(-1,4), 7.5),
        ("TOPPADDING", (0,4),(-1,4), 4),
        ("BOTTOMPADDING",(0,4),(-1,4),4),
    ]))
    story.append(sp(4))

    # These
    if thesis:
        story.append(p(thesis))


# ═══════════════════════════════════════════════════════════════════
# PAGE 2 — ANALYSE FINANCIERE
# ═══════════════════════════════════════════════════════════════════

def _is_widths(n_data):
    """Calcule les largeurs de colonnes pour le tableau IS."""
    label = 54.0
    per   = (CW - label) / n_data
    cols  = [label] + [per] * n_data
    diff  = CW - sum(cols)
    cols[-1] = round(cols[-1] + diff, 2)
    return cols

def _page_financiere(story, snap, ratios, synthesis):
    story += section("2", "Analyse Financi\u00e8re")

    ci    = snap.company_info
    cur   = ci.currency or "USD"
    units = ci.units or "M"

    # Préparation années
    hist_labels = sorted(snap.years.keys(), key=lambda y: str(y).replace("_LTM",""))
    hist_3 = hist_labels[-3:] if len(hist_labels) >= 3 else hist_labels

    col_names = []
    for i, l in enumerate(hist_3):
        base = str(l).replace("_LTM","")
        col_names.append(base + " LTM" if i == len(hist_3)-1 else base)

    # Projections depuis synthesis.is_projections
    is_proj_raw = _g(synthesis,"is_projections") or {}
    last_yr_key = str(hist_3[-1]).replace("_LTM","") if hist_3 else str(date.today().year-1)
    try:
        ny1 = str(int(last_yr_key)+1) + "F"
        ny2 = str(int(last_yr_key)+2) + "F"
    except Exception:
        ny1, ny2 = "2025F", "2026F"

    def _pvalid(d):
        return isinstance(d, dict) and d.get("revenue") is not None

    def _extrapolate():
        hd = []
        for l in hist_3[-2:]:
            fy = snap.years.get(l)
            ry = ratios.years.get(l) if ratios else None
            if fy and ry: hd.append((fy, ry))
        if not hd: return {}
        last_fy, last_ry = hd[-1]
        growth = 0.07
        if len(hd) >= 2:
            prev_fy = hd[-2][0]
            if prev_fy.revenue and last_fy.revenue and prev_fy.revenue != 0:
                g = (last_fy.revenue - prev_fy.revenue) / abs(prev_fy.revenue)
                growth = max(min(g, 0.60), -0.15)
        result = {}
        prev_rev = last_fy.revenue
        for i, lbl in enumerate([ny1, ny2]):
            g_yr = growth * (0.80 ** i)
            rev  = (prev_rev * (1+g_yr)) if prev_rev else None
            gm   = getattr(last_ry, "gross_margin",  None)
            em   = getattr(last_ry, "ebitda_margin", None)
            nm   = getattr(last_ry, "net_margin",    None)
            result[lbl] = {
                "revenue": rev, "revenue_growth": g_yr,
                "gross_margin": gm,
                "ebitda": (rev*em) if rev and em else None, "ebitda_margin": em,
                "net_income": (rev*nm) if rev and nm else None, "net_margin": nm,
            }
            prev_rev = rev
        return result

    extrap = _extrapolate()   # toujours calculé en fallback
    is_proj = {}
    for lbl in [ny1, ny2]:
        raw_entry = is_proj_raw.get(lbl)
        # Essayer aussi les variantes de clés LLM ("2026", "FY2026")
        if raw_entry is None:
            alt = lbl.replace("F","")
            raw_entry = is_proj_raw.get(alt) or is_proj_raw.get("FY"+alt)
        if _pvalid(raw_entry):
            # Fusionner avec extrap pour combler les champs null
            merged = dict(extrap.get(lbl, {}))
            merged.update({k: v for k, v in raw_entry.items() if v is not None})
            is_proj[lbl] = merged
        elif lbl in extrap:
            is_proj[lbl] = extrap[lbl]

    proj_labels = []
    for lbl in [ny1, ny2]:
        if lbl in is_proj:
            proj_labels.append(lbl)
            col_names.append(lbl)

    all_labels = list(hist_3) + proj_labels

    def _fy(l): return snap.years.get(l)
    def _ry(l): return ratios.years.get(l) if ratios else None
    def _pv(l, k):
        p_ = is_proj.get(l)
        return p_.get(k) if isinstance(p_, dict) else None

    story.append(sub(f"Compte de r\u00e9sultat consolid\u00e9  ({cur} {units})"))

    # Colonnes : header
    hdr_row = ["Indicateur"] + col_names

    # Revenue
    rev_row = ["Chiffre d'affaires"]
    for l in all_labels:
        fy = _fy(l)
        v  = _pv(l,"revenue") if l in proj_labels else (fy.revenue if fy else None)
        rev_row.append(_frm(v))

    # Croissance
    grow_row = [""]  # label sub-style
    prev_rev = None
    grow_vals = []
    for l in all_labels:
        if l in proj_labels:
            g = _pv(l,"revenue_growth")
            grow_vals.append(_frpct(g) if g is not None else "—")
            prev_rev = _pv(l,"revenue")
        else:
            fy = _fy(l); rev = fy.revenue if fy else None
            if prev_rev and rev and prev_rev != 0:
                grow_vals.append(f"{(rev-prev_rev)/abs(prev_rev)*100:+.1f}\u00a0%".replace(".",","))
            else:
                grow_vals.append("—")
            prev_rev = rev

    # Marge brute
    gm_row = ["Marge brute"]
    for l in all_labels:
        yr = _ry(l)
        v  = _pv(l,"gross_margin") if l in proj_labels else (yr.gross_margin if yr else None)
        gm_row.append(_frpct(v))

    # EBITDA
    ebitda_row = ["EBITDA"]
    for l in all_labels:
        yr = _ry(l)
        v  = _pv(l,"ebitda") if l in proj_labels else (yr.ebitda if yr else None)
        ebitda_row.append(_frm(v))

    # Marge EBITDA
    em_row = [""]
    em_vals = []
    for l in all_labels:
        yr = _ry(l)
        v  = _pv(l,"ebitda_margin") if l in proj_labels else (yr.ebitda_margin if yr else None)
        em_vals.append(_frpct(v))

    # Resultat net
    ni_row = ["Resultat net"]
    for l in all_labels:
        yr = _ry(l)
        v  = _pv(l,"net_income") if l in proj_labels else (yr.net_income if yr else None)
        ni_row.append(_frm(v))

    # Marge nette
    nm_row = [""]
    nm_vals = []
    for l in all_labels:
        yr = _ry(l)
        v  = _pv(l,"net_margin") if l in proj_labels else (yr.net_margin if yr else None)
        nm_vals.append(_frpct(v))

    n_data = len(all_labels)
    widths = _is_widths(n_data)
    ltm_col = len(hist_3)  # index (1-based) de la colonne LTM

    # Construction des lignes avec sous-lignes en italique
    is_rows = [hdr_row, rev_row]

    # Sous-ligne Croissance YoY
    g_sub = [p("    Croissance YoY", "td_sub")] + [p(v, "td_sub_r") for v in grow_vals]
    is_rows.append(g_sub)

    is_rows.append(gm_row)
    is_rows.append(ebitda_row)

    # Sous-ligne Marge EBITDA
    em_sub = [p("    Marge EBITDA", "td_sub")] + [p(v, "td_sub_r") for v in em_vals]
    is_rows.append(em_sub)

    is_rows.append(ni_row)

    # Sous-ligne Marge nette
    nm_sub = [p("    Marge nette", "td_sub")] + [p(v, "td_sub_r") for v in nm_vals]
    is_rows.append(nm_sub)

    story.append(tbl(is_rows, widths, extra=[
        ("BACKGROUND", (ltm_col, 1), (ltm_col, -1), NAVY_PALE),
        ("LINEBELOW",  (0,1), (-1,1), 0.5, GREY_RULE),
        ("LINEBELOW",  (0,3), (-1,3), 0.5, GREY_RULE),
        ("LINEBELOW",  (0,5), (-1,5), 0.5, GREY_RULE),
    ]))

    fin_comment = _g(synthesis,"financial_commentary") or _g(synthesis,"summary") or ""
    if fin_comment:
        story.append(sp(3))
        story.append(p(fin_comment))

    # Ratios
    story.append(sp(3))
    story.append(sub("Positionnement relatif \u2014 Ratios cl\u00e9s vs. pairs sectoriels"))

    hist_labels_all = sorted(snap.years.keys(), key=lambda y: str(y).replace("_LTM",""))
    latest_l = hist_labels_all[-1] if hist_labels_all else None
    yr       = ratios.years.get(latest_l) if ratios and latest_l else None
    def _a(attr): return getattr(yr, attr, None) if yr else None

    pe   = _a("pe_ratio"); ev_e = _a("ev_ebitda"); ev_r = _a("ev_revenue")
    gm   = _a("gross_margin"); em = _a("ebitda_margin"); roe = _a("roe")
    az   = _a("altman_z"); bm_sc = _a("beneish_m")
    bm   = _benchmarks(ci.sector or "")

    az_lbl  = ("Solide" if az and float(az)>2.99 else "Zone grise" if az and float(az)>1.81 else "D\u00e9tresse") if az else "\u2014"
    bm_lbl  = "Aucun signal" if bm_sc and float(bm_sc)<-2.22 else ("Risque manip." if bm_sc else "\u2014")

    # Couleurs colonne Lecture
    def _lect_color(lbl):
        if lbl in ("Prime technologique","Sup\u00e9rieur","Sup\u00e9rieure","Solide","Aucun signal","En ligne","Dans la norme"):
            return GREEN if lbl in ("Solide","Aucun signal") else (AMBER if lbl in ("En ligne","Dans la norme") else RED)
        if lbl in ("D\u00e9cote","Inf\u00e9rieure","D\u00e9tresse","Risque manip.","Zone grise"): return RED
        return AMBER

    def _lect_pale(lbl):
        c = _lect_color(lbl)
        if c == GREEN: return GREEN_PALE
        if c == RED:   return RED_PALE
        return AMBER_PALE

    def _lect_p(lbl):
        st_ = ParagraphStyle("lp", fontName="Helvetica-Bold", fontSize=7.5,
                             textColor=_lect_color(lbl), leading=10, alignment=TA_CENTER)
        return Paragraph(lbl, st_)

    lect_pe   = _lecture(pe,  bm["pe"])
    lect_eve  = _lecture(ev_e,bm["ev_e"])
    lect_evr  = _lecture(ev_r,bm["ev_r"])
    lect_gm   = _lecture(gm,  bm["gm"],  pct=True)
    lect_em   = _lecture(em,  bm["em"],  pct=True)
    lect_roe  = _lecture(roe, bm["roe"], pct=True)

    rat_rows = [
        ["Indicateur", f"{ci.ticker}  LTM", "Reference sectorielle", "Lecture"],
        ["P/E (x)",           _frx(pe),   bm["pe"],    _lect_p(lect_pe)],
        ["EV / EBITDA (x)",   _frx(ev_e), bm["ev_e"],  _lect_p(lect_eve)],
        ["EV / Revenue (x)",  _frx(ev_r), bm["ev_r"],  _lect_p(lect_evr)],
        ["Marge brute",       _frpct(gm), bm["gm"],    _lect_p(lect_gm)],
        ["Marge EBITDA",      _frpct(em), bm["em"],    _lect_p(lect_em)],
        ["Return on Equity",  _frpct(roe),bm["roe"],   _lect_p(lect_roe)],
        ["Altman Z-Score",    _fr(az,1),  "> 2,99 = sain", _lect_p(az_lbl)],
        ["Beneish M-Score",   _fr(bm_sc,2),"< \u20132,22 = OK", _lect_p(bm_lbl)],
    ]

    # Fond coloré par ligne sur la colonne Lecture
    extra_r = []
    for ri, lbl in [(1,lect_pe),(2,lect_eve),(3,lect_evr),(4,lect_gm),(5,lect_em),
                    (6,lect_roe),(7,az_lbl),(8,bm_lbl)]:
        extra_r.append(("BACKGROUND", (3,ri),(3,ri), _lect_pale(lbl)))

    story.append(tbl(rat_rows, [54, 34, 50, 32], extra=extra_r))

    rc = _g(synthesis,"ratio_commentary") or ""
    if rc:
        story.append(sp(3))
        story.append(p(rc))


# ═══════════════════════════════════════════════════════════════════
# PAGE 3 — VALORISATION
# ═══════════════════════════════════════════════════════════════════

def _page_valorisation(story, snap, ratios, synthesis):
    story += section("3", "Valorisation")

    ci    = snap.company_info
    mkt   = snap.market
    cur   = ci.currency or "USD"
    price = mkt.share_price
    wacc  = mkt.wacc  or 0.10
    tgr   = mkt.terminal_growth or 0.03
    tbase = _g(synthesis,"target_base")
    tbear = _g(synthesis,"target_bear")
    tbull = _g(synthesis,"target_bull")

    beta    = mkt.beta_levered
    rfr     = mkt.risk_free_rate or 0.041
    erp     = mkt.erp  or 0.055
    ke      = rfr + erp * (beta or 1.0)
    kd_pre  = mkt.cost_of_debt_pretax or 0.04
    tax     = mkt.tax_rate or 0.25
    kd_post = kd_pre * (1 - tax)

    # DCF
    story.append(sub(
        f"Discounted Cash Flow  \u2014  Scenario base  \u00b7  "
        f"WACC {_fr(wacc*100,1)}\u00a0%  \u00b7  Taux terminal {_fr(tgr*100,1)}\u00a0%  \u00b7  Horizon 5 ans"
    ))

    dcf_commentary = _g(synthesis,"dcf_commentary") or ""
    dcf_base = (
        f"Le modele DCF est calibre sur un horizon de cinq ans, avec un WACC de {_fr(wacc*100,1)}\u00a0% "
        f"decompose en un cout des fonds propres de {_fr(ke*100,1)}\u00a0% "
        f"(Beta {_fr(beta,2) if beta else 'N/A'}  \u2014  RFR {_fr(rfr*100,1)}\u00a0%  \u2014  "
        f"prime de risque marche {_fr(erp*100,1)}\u00a0%) "
        f"et un cout de la dette apres impot de {_fr(kd_post*100,1)}\u00a0%. "
        f"La valeur intrinseque ressort a <b>{_fr(tbase,0)}\u00a0{cur}</b> par action "
        f"dans le scenario base, soit un upside de {_upside(tbase,price)} par rapport au cours actuel."
    )
    story.append(p(dcf_commentary or dcf_base))
    story.append(sp(2))
    story.append(p(f"Table de sensibilit\u00e9 \u2014 Valeur intrins\u00e8que par action ({cur})", "caption"))

    # Sensibilite
    waccs = [wacc-0.02, wacc-0.01, wacc, wacc+0.01, wacc+0.02]
    tgrs  = [tgr-0.01,  tgr-0.005, tgr, tgr+0.005, tgr+0.01]
    bv    = float(tbase) if tbase else (float(price) if price else 100.0)
    db    = wacc - tgr

    def _dcf(w, t):
        d = w - t
        if abs(d) < 1e-4 or abs(db) < 1e-4: return "—"
        return _fr(bv * db / d, 0)

    sens = [["WACC  \u2193  /  TGR  \u2192"] + [_fr(t*100,1,"\u00a0%") for t in tgrs]]
    for i, w in enumerate(waccs):
        row = [_fr(w*100,1,"\u00a0%")]
        for j, t in enumerate(tgrs):
            if i == 2 and j == 2:
                row.append(p(_dcf(w,t), "td_b"))
            else:
                row.append(_dcf(w,t))
        sens.append(row)

    SENS_HL = colors.HexColor("#EEF2F8")
    story.append(tbl(sens, [34, 27.2, 27.2, 27.2, 27.2, 27.2], extra=[
        ("BACKGROUND", (0,3),(-1,3),  SENS_HL),
        ("BACKGROUND", (3,1),(3,-1),  SENS_HL),
        ("BACKGROUND", (3,3),(3,3),   NAVY_PALE),
        ("TEXTCOLOR",  (3,3),(3,3),   NAVY),
        ("FONTNAME",   (0,3),(-1,3),  "Helvetica-Bold"),
        ("FONTNAME",   (3,3),(3,3),   "Helvetica-Bold"),
    ]))
    story.append(p(
        f"Ligne et colonne surlignees correspondent au scenario base. "
        f"La cellule d'intersection materialise la valeur centrale du modele ({_fr(tbase,0)}\u00a0{cur}).",
        "caption"))

    # Comparables
    story.append(sp(3))
    story.append(sub("Analyse par multiples comparables \u2014 Pairs sectoriels LTM"))

    hist_labels = sorted(snap.years.keys(), key=lambda y: str(y).replace("_LTM",""))
    latest_l    = hist_labels[-1] if hist_labels else None
    yr = ratios.years.get(latest_l) if ratios and latest_l else None
    def _a(attr): return getattr(yr, attr, None) if yr else None

    pe   = _a("pe_ratio"); ev_e = _a("ev_ebitda"); ev_r = _a("ev_revenue")
    gm   = _a("gross_margin"); em = _a("ebitda_margin")
    peers = _g(synthesis,"comparable_peers") or []

    comp_hdr = ["Soci\u00e9t\u00e9", "EV/EBITDA", "EV/Revenue", "P/E", "Marge brute", "Marge EBITDA"]
    comp = [comp_hdr, [
        p(f"{ci.ticker}  (cible)", "td_l"),
        _frx(ev_e), _frx(ev_r), _frx(pe), _frpct(gm), _frpct(em),
    ]]

    if peers:
        for peer in peers[:5]:
            comp.append([
                _g(peer,"name") or _g(peer,"ticker") or "—",
                _frx(_g(peer,"ev_ebitda")), _frx(_g(peer,"ev_revenue")),
                _frx(_g(peer,"pe")),
                _frpct(_g(peer,"gross_margin")), _frpct(_g(peer,"ebitda_margin")),
            ])

        def _med(attr):
            vals = []
            for peer in peers[:5]:
                try:
                    v = float(_g(peer,attr) or "nan")
                    if abs(v) < 999: vals.append(v)
                except: pass
            if not vals: return "—"
            vals.sort()
            return vals[len(vals)//2]

        def _medpct(attr):
            vals = []
            for peer in peers[:5]:
                try:
                    v = float(_g(peer,attr) or "nan")
                    if abs(v) < 10: vals.append(v)
                except: pass
            if not vals: return "—"
            vals.sort()
            return vals[len(vals)//2]

        med_ev  = _med("ev_ebitda")
        med_evr = _med("ev_revenue")
        med_pe  = _med("pe")
        med_gm  = _medpct("gross_margin")
        med_em  = _medpct("ebitda_margin")
        comp.append([
            p("M\u00e9diane peers", "td_l"),
            p(_frx(med_ev),"td_b"), p(_frx(med_evr),"td_b"),
            p(_frx(med_pe),"td_b"),
            p(_frpct(med_gm),"td_b"), p(_frpct(med_em),"td_b"),
        ])

        # Commentaire
        if isinstance(med_ev, float) and ev_e and float(ev_e) > 0:
            try:
                prime = (float(ev_e)/med_ev - 1)*100
                impl  = float(price)*med_ev/float(ev_e) if price and ev_e else None
                story.append(tbl(comp, [42, 28, 28, 26, 24, 22], extra=[
                    ("BACKGROUND", (0,1),(-1,1),  NAVY_PALE),
                    ("LINEABOVE",  (0,-1),(-1,-1), 0.8, NAVY),
                    ("BACKGROUND", (0,-1),(-1,-1), GREY_ROW),
                ]))
                story.append(sp(3))
                story.append(p(
                    f"La mediane des pairs sur l'EV/EBITDA ressort a {_frx(med_ev)}, contre "
                    f"{_frx(ev_e)} pour {ci.ticker}, confirmant une prime de {_fr(prime,0)}\u00a0% "
                    f"que le marche justifie par le potentiel strategique. "
                    f"En appliquant la mediane sectorielle, la valeur implicite ressortirait a "
                    f"environ {_fr(impl,0) if impl else 'N/A'}\u00a0{cur}."
                ))
            except Exception:
                story.append(tbl(comp, [42, 28, 28, 26, 24, 22], extra=[
                    ("BACKGROUND", (0,1),(-1,1),  NAVY_PALE),
                    ("LINEABOVE",  (0,-1),(-1,-1), 0.8, NAVY),
                    ("BACKGROUND", (0,-1),(-1,-1), GREY_ROW),
                ]))
        else:
            story.append(tbl(comp, [42, 28, 28, 26, 24, 22], extra=[
                ("BACKGROUND", (0,1),(-1,1),  NAVY_PALE),
                ("LINEABOVE",  (0,-1),(-1,-1), 0.8, NAVY),
                ("BACKGROUND", (0,-1),(-1,-1), GREY_ROW),
            ]))
    else:
        # Fallback propre sans peers
        story.append(tbl(comp, [42, 28, 28, 26, 24, 22], extra=[
            ("BACKGROUND", (0,1),(-1,1), NAVY_PALE),
        ]))
        story.append(p("Donnees comparables non disponibles pour ce ticker.", "caption"))

    # Football Field
    story.append(PageBreak())
    story.append(sub("Football Field Chart \u2014 Synth\u00e8se des m\u00e9thodes de valorisation"))

    ff_src = _g(synthesis,"football_field") or []
    ff_rows_data = []
    if ff_src:
        for m in ff_src:
            ff_rows_data.append({
                "label": _g(m,"label") or "—",
                "low":   _g(m,"range_low"), "high": _g(m,"range_high"), "mid": _g(m,"midpoint"),
            })
    else:
        if tbear: ff_rows_data.append({"label":"DCF \u2014 Bear","low":float(tbear)*0.90,"high":float(tbear)*1.05,"mid":tbear})
        if tbase: ff_rows_data.append({"label":"DCF \u2014 Base","low":float(tbase)*0.94,"high":float(tbase)*1.06,"mid":tbase})
        if tbull: ff_rows_data.append({"label":"DCF \u2014 Bull","low":float(tbull)*0.92,"high":float(tbull)*1.10,"mid":tbull})
        bm_s = _benchmarks(ci.sector or "")
        if yr and yr.ev_ebitda and price:
            try:
                parts = bm_s["ev_e"].replace("x","").replace("\u00a0","").split("\u2013")
                med = (float(parts[0])+float(parts[1]))/2
                impl = float(price)*med/float(yr.ev_ebitda)
                ff_rows_data.append({"label":"EV/EBITDA \u2014 Mediane peers","low":impl*0.90,"high":impl*1.10,"mid":impl})
                impl2 = impl*1.5
                ff_rows_data.append({"label":"EV/EBITDA \u2014 Prime tech +50\u00a0%","low":impl2*0.90,"high":impl2*1.10,"mid":impl2})
            except: pass
        if yr and yr.ev_revenue and price:
            try:
                bm_r = bm_s["ev_r"].replace("x","").replace("\u00a0","").replace(",",".").split("\u2013")
                med_r = (float(bm_r[0])+float(bm_r[1]))/2
                impl_r = float(price)*med_r/float(yr.ev_revenue)
                ff_rows_data.append({"label":"EV/Revenue \u2014 Mediane peers","low":impl_r*0.90,"high":impl_r*1.10,"mid":impl_r})
            except: pass

    ff_tbl = [["M\u00e9thode", f"Fourchette basse ({cur})", f"Fourchette haute ({cur})", f"Point central ({cur})"]]
    for r in ff_rows_data:
        ff_tbl.append([r["label"], _fr(r["low"],0), _fr(r["high"],0), _fr(r["mid"],0)])
    if price:
        ff_tbl.append([f"Cours actuel ({_date_fr()})", "\u2014", "\u2014", _fr(price,2)])

    story.append(tbl(ff_tbl, [70, 33, 33, 34]))

    if tbase and price:
        story.append(sp(3))
        story.append(p(
            f"Le scenario DCF base ({_fr(tbase,0)}\u00a0{cur}) et le cours actuel "
            f"({_fr(price,2)}\u00a0{cur}) sont coherents avec une valorisation mixte "
            "DCF / multiples ajustes. L'application stricte des multiples medians pairs "
            "illustre l'ampleur de la prime integree, et le risque de correction si les "
            "hypotheses structurelles ne se materialisent pas dans les delais anticipes."
        ))


# ═══════════════════════════════════════════════════════════════════
# PAGE 4 — ANALYSE DES RISQUES & SENTIMENT
# ═══════════════════════════════════════════════════════════════════

_POSITIVE_FILTER = {
    "base solide", "solide", "resilient", "resiliente", "opportunite", "opportunites",
    "potentiel positif", "favorable", "robuste", "croissance acceleree",
    "catalyseur positif", "offrent", "offre une", "suggerent une capacite",
    "nouvelle opportunit", "investir dans de nouvelles",
}

def _strip_positive_sentences(text: str) -> str:
    """Supprime les phrases contenant des mots positifs interdits (Bug 3)."""
    if not text:
        return text
    sentences = [s.strip() for s in text.replace(". ", ".|").replace(".\n", "|\n").split("|") if s.strip()]
    clean = []
    for s in sentences:
        s_low = s.lower()
        if not any(w in s_low for w in _POSITIVE_FILTER):
            clean.append(s)
    result = " ".join(clean)
    return result if result.strip() else text  # fallback si tout filtré


def _page_risques_sentiment(story, snap, synthesis, devil, sentiment):
    story += section("4", "Analyse des Risques & Sentiment")

    ci = snap.company_info

    story.append(sub("These contraire  \u2014  Arguments en faveur d'une revision a la baisse"))

    counter_thesis = _g(devil,"counter_thesis") or ""
    counter_risks  = _g(devil,"counter_risks") or []
    risks_synth    = _g(synthesis,"risks") or []

    # Construction des 3 paragraphes Avocat du Diable
    # counter_thesis format : "argument1 | argument2 | argument3"
    paragraphs = []
    if counter_thesis:
        # Split par ' | ' en priorité (format agent_devil), fallback phrases
        if " | " in counter_thesis:
            ct_parts = [s.strip() for s in counter_thesis.split(" | ") if s.strip()]
        else:
            sents = [s.strip() for s in counter_thesis.replace(". ", ".|").split("|") if s.strip()]
            chunk = max(1, len(sents) // 3)
            ct_parts = [
                ". ".join(sents[i*chunk:(i+1)*chunk]).strip()
                for i in range(3)
            ]
        # Associer chaque partie à un titre de risque (ou titre générique)
        titles = list(counter_risks[:3]) if counter_risks else [f"Risque {i+1}" for i in range(3)]
        for i in range(3):
            title = titles[i] if i < len(titles) else f"Risque {i+1}"
            body  = ct_parts[i] if i < len(ct_parts) else ""
            if body and not body.endswith("."): body += "."
            # Ne jamais mettre le titre comme corps de texte
            paragraphs.append((title, body if body and body.strip() != title.strip() else ""))
    elif risks_synth:
        for r in risks_synth[:3]:
            paragraphs.append(("", str(r)))
    else:
        paragraphs = [("Analyse contradictoire non disponible.", "")]

    for title, body in paragraphs:
        if title:
            t = title if title.endswith(".") else title + "."
            story.append(p(f"<b>{t}</b>", "body"))
        if body:
            story.append(p(_strip_positive_sentences(body), "body_sm"))
        story.append(sp(2))

    # Conditions d'invalidation
    story.append(sp(2))
    story.append(sub("Conditions d'invalidation de la these"))

    inv_list = _g(synthesis,"invalidation_list") or []
    inv_str  = _g(synthesis,"invalidation_conditions") or ""

    inv_data = [["Axe", "Condition d'invalidation", "Horizon"]]
    if inv_list:
        for c in inv_list[:3]:
            inv_data.append([_g(c,"axis") or "—", _g(c,"condition") or "—", _g(c,"horizon") or "—"])
    else:
        if inv_str:
            inv_data.append(["Synthese IA", inv_str[:120]+("…" if len(inv_str)>120 else ""), "Court-moyen"])
        inv_data += [
            ["Macro",    "Taux souverains 10 ans > 5,5\u00a0% sur deux trimestres consecutifs", "6\u201312 mois"],
            ["Sectoriel","Perte de part de marche significative vs. principaux pairs",           "12\u201318 mois"],
            ["Societe",  "Marge brute sous plancher historique sur deux trimestres",             "2\u20133 trim."],
        ]
        inv_data = inv_data[:4]

    story.append(tbl(inv_data, [28, 110, 32]))

    # Sentiment
    story.append(sp(5))
    story.append(rule(NAVY, 1.0, b=0, a=3))
    story.append(p("5.  SENTIMENT DE MARCHE", "h1"))

    if not sentiment:
        story.append(p("Donnees de sentiment non disponibles.", "body_sm"))
        return

    label     = (_g(sentiment,"label") or "NEUTRAL").lower()
    score     = float(_g(sentiment,"score") or 0.0)
    n_art     = int(_g(sentiment,"articles_analyzed") or 0)
    breakdown = _g(sentiment,"breakdown") or {}
    samples   = _g(sentiment,"samples") or []
    engine    = (_g(sentiment,"meta","engine") or "VADER").upper()
    rec       = (_g(synthesis,"recommendation") or "").upper()

    avg_pos = float(breakdown.get("avg_positive", 0))
    avg_neu = float(breakdown.get("avg_neutral",  0))
    avg_neg = float(breakdown.get("avg_negative", 0))

    def _themes(orient):
        ts = []
        for s in samples:
            lbl = (s.get("label") or "").upper()
            if ((orient=="pos" and lbl=="POSITIVE") or
                    (orient=="neg" and lbl=="NEGATIVE") or
                    (orient=="neu" and lbl=="NEUTRAL")):
                h = s.get("headline","")[:45]
                if h: ts.append(h)
        return ", ".join(ts[:2]) or "—"

    direction = "positive moderee" if score > 0.05 else ("negative moderee" if score < -0.05 else "neutre")
    rec_comment = (f" Ce sentiment est coherent avec la recommandation {rec} fondee sur "
                   "les fondamentaux." if rec else "")

    story.append(p(
        f"L'analyse semantique {engine} conduite sur un corpus de {n_art} articles "
        f"publie{'s' if n_art>1 else ''} au cours des sept derniers jours fait ressortir "
        f"un sentiment globalement {label} avec une inflexion {direction} "
        f"(score agrege : {_fr(score,3)}). "
        f"Les publications favorables sont portees par {_themes('pos')}. "
        f"Les publications defavorables se concentrent sur {_themes('neg')}."
        + rec_comment
    ))
    story.append(sp(3))

    n_pos = round(avg_pos * n_art) if n_art else 0
    n_neu = round(avg_neu * n_art) if n_art else 0
    n_neg = round(avg_neg * n_art) if n_art else 0

    sent_rows = [
        ["Orientation", "Articles", "Score moyen", "Themes principaux"],
        ["Positif", str(n_pos), _fr(avg_pos,2), _themes("pos")],
        ["Neutre",  str(n_neu), _fr(avg_neu,2), _themes("neu")],
        ["Negatif", str(n_neg), _fr(-avg_neg,2), _themes("neg")],
    ]
    story.append(tbl(sent_rows, [28, 18, 24, 100]))


# ═══════════════════════════════════════════════════════════════════
# PAGE 5 (6) — DISCLAIMER
# ═══════════════════════════════════════════════════════════════════

def _page_disclaimer(story, snap, gen_date):
    story.append(sp(12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=NAVY, spaceBefore=0, spaceAfter=5))
    story.append(p("Avertissement legal", "disc_h"))
    story.append(p(
        f"Ce rapport a ete genere par FinSight IA v1.0 le {gen_date}. "
        "Il est produit integralement par un systeme d'intelligence artificielle "
        "et ne constitue pas un conseil en investissement au sens de la directive "
        "europeenne MiFID II (2014/65/UE). FinSight IA ne saurait etre tenu "
        "responsable des decisions prises sur la base de ce document. "
        "Les donnees financieres sont issues de sources publiques (yfinance, Finnhub, FMP) "
        "et peuvent contenir des inexactitudes. "
        "Tout investisseur est invite a proceder a sa propre diligence et a consulter "
        "un professionnel qualifie avant toute decision. "
        "Document confidentiel — diffusion restreinte.",
        "disclaimer"
    ))


# ═══════════════════════════════════════════════════════════════════
# PDFWriter
# ═══════════════════════════════════════════════════════════════════

class PDFWriter:
    def generate(self, state: dict, output_path: str) -> str:
        snap      = state.get("raw_data")
        ratios    = state.get("ratios")
        synthesis = state.get("synthesis")
        sentiment = state.get("sentiment")
        devil     = state.get("devil")

        if snap is None:
            raise ValueError("PDFWriter: state['raw_data'] requis")

        ci       = snap.company_info
        ticker   = ci.ticker or state.get("ticker", "UNKNOWN")

        # Résolution du nom complet si company_name == ticker
        co_name = ci.company_name or ""
        if not co_name or co_name.upper() == ticker.upper():
            try:
                import yfinance as yf
                info = yf.Ticker(ticker).info
                co_name = info.get("longName") or info.get("shortName") or ticker
            except Exception:
                co_name = ticker

        sector   = ci.sector or ""
        exchange = getattr(ci, "exchange", "") or ""
        gen_date = _date_fr()

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        cover_cb  = lambda c, d: _draw_cover(c, d, ticker, co_name, sector, exchange, gen_date)
        footer_cb = _make_footer(co_name, ticker)

        doc = SimpleDocTemplate(
            str(out),
            pagesize=A4,
            leftMargin=20*mm, rightMargin=20*mm,
            topMargin=12*mm,  bottomMargin=18*mm,
            title=f"FinSight IA — {co_name} ({ticker})",
            author="FinSight IA v1.0",
        )

        # Page 1 = cover (canvas only), page 2 = sommaire, pages 3+ = contenu (flux naturel)
        story = [PageBreak()]                                    # consomme page 1 pour la cover
        _page_toc(story, gen_date, snap=snap, synthesis=synthesis)  # page 2 — sommaire
        _page_synthese(story, snap, synthesis)
        _page_financiere(story, snap, ratios, synthesis)
        _page_valorisation(story, snap, ratios, synthesis)
        _page_risques_sentiment(story, snap, synthesis, devil, sentiment)
        _page_disclaimer(story, snap, gen_date)

        doc.build(story, onFirstPage=cover_cb, onLaterPages=footer_cb)
        log.info(f"[PDFWriter] {ticker} -> {out.name}")
        return str(out)
