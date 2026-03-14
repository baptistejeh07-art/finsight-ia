# =============================================================================
# FinSight IA — PDF Writer
# outputs/pdf_writer.py
#
# PDFWriter.generate(state: FinSightState, output_path: str) -> str
# 6 pages : cover | sommaire | synthese | financiere | valorisation | risques
# Toutes les tables a exactement 170mm de large (AssertionError sinon)
# Police : Helvetica uniquement | Couleur accent : #1B3A6B
# =============================================================================

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constante largeur tables
# ---------------------------------------------------------------------------
try:
    from reportlab.lib.units import mm as _mm
    _TW = 170 * _mm   # 481.89 pt
except ImportError:
    _mm = 2.8346
    _TW = 170 * _mm


# ---------------------------------------------------------------------------
# Helpers lecture (dict OU objet)
# ---------------------------------------------------------------------------

def _g(obj, *keys, default=None):
    for k in keys:
        if obj is None:
            return default
        obj = obj.get(k) if isinstance(obj, dict) else getattr(obj, k, None)
    return obj if obj is not None else default


# ---------------------------------------------------------------------------
# Helpers formatage
# ---------------------------------------------------------------------------

def _v(val, fmt="{:.1f}", default="--"):
    if val is None:
        return default
    try:
        return fmt.format(float(val))
    except Exception:
        return default


def _pct(val, default="--"):
    if val is None:
        return default
    try:
        return f"{float(val) * 100:.1f} %"
    except Exception:
        return default


def _x(val, default="--"):
    if val is None:
        return default
    try:
        f = float(val)
        if f > 999 or f < -999:
            return "n.m."
        return f"{f:.1f}x"
    except Exception:
        return default


def _m(val, default="--"):
    if val is None:
        return default
    try:
        v = float(val)
        if abs(v) >= 1000:
            return f"{v / 1000:.1f}B"
        return f"{v:.0f}M"
    except Exception:
        return default


def _upside(target, current, default="--"):
    if target is None or current is None:
        return default
    try:
        c = float(current)
        if c == 0:
            return default
        return f"{(float(target) - c) / abs(c) * 100:+.1f} %"
    except Exception:
        return default


def _assert_tw(col_widths):
    total = sum(col_widths)
    assert abs(total - _TW) < 1.0, (
        f"Table width {total:.1f}pt != {_TW:.1f}pt (170mm). "
        f"Colonnes : {[round(c, 1) for c in col_widths]}"
    )


# ---------------------------------------------------------------------------
# Couleurs
# ---------------------------------------------------------------------------

def _C():
    from reportlab.lib import colors as C
    return {
        "navy":    C.HexColor("#1B3A6B"),
        "green":   C.HexColor("#1A7A4A"),
        "red":     C.HexColor("#A82020"),
        "amber":   C.HexColor("#B06000"),
        "grey":    C.HexColor("#555555"),
        "lgrey":   C.HexColor("#F5F5F5"),
        "blue_lt": C.HexColor("#EEF2F8"),
        "white":   C.white,
        "black":   C.black,
        "grid":    C.HexColor("#CCCCCC"),
    }


def _rec_color(rec: str):
    from reportlab.lib import colors as C
    r = (rec or "").upper()
    if r == "BUY":
        return C.HexColor("#1A7A4A")
    if r == "SELL":
        return C.HexColor("#A82020")
    return C.HexColor("#B06000")


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _styles():
    from reportlab.lib.styles import ParagraphStyle
    C = _C()
    return {
        "section":  ParagraphStyle("s_sec",   fontName="Helvetica-Bold", fontSize=9.5,
                                   textColor=C["white"], backColor=C["navy"],
                                   spaceBefore=10, spaceAfter=4,
                                   leftIndent=4, leading=15),
        "subsec":   ParagraphStyle("s_ssec",  fontName="Helvetica-Bold", fontSize=8.5,
                                   textColor=C["navy"], spaceBefore=8, spaceAfter=3, leading=12),
        "body":     ParagraphStyle("s_body",  fontName="Helvetica", fontSize=8,
                                   leading=12, spaceAfter=5),
        "small":    ParagraphStyle("s_small", fontName="Helvetica", fontSize=7,
                                   textColor=C["grey"], leading=10, spaceAfter=3),
        "bold":     ParagraphStyle("s_bold",  fontName="Helvetica-Bold", fontSize=8,
                                   leading=12, spaceAfter=4),
        "italic":   ParagraphStyle("s_ital",  fontName="Helvetica-Oblique", fontSize=7.5,
                                   textColor=C["grey"], leading=11, spaceAfter=3),
        "toc":      ParagraphStyle("s_toc",   fontName="Helvetica", fontSize=8.5,
                                   leading=14, leftIndent=12, spaceAfter=3),
    }


# ---------------------------------------------------------------------------
# Table style factory
# ---------------------------------------------------------------------------

def _ts(extra=None, first_col_navy=True, alt_rows=True):
    from reportlab.platypus import TableStyle
    C = _C()
    cmds = [
        ("BACKGROUND",    (0, 0), (-1,  0), C["navy"]),
        ("TEXTCOLOR",     (0, 0), (-1,  0), C["white"]),
        ("FONTNAME",      (0, 0), (-1,  0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1,  0), 7),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 7),
        ("GRID",          (0, 0), (-1, -1), 0.3, C["grid"]),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]
    if alt_rows:
        cmds.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [C["lgrey"], C["white"]]))
    if first_col_navy:
        cmds += [
            ("BACKGROUND", (0, 1), (0, -1), C["navy"]),
            ("TEXTCOLOR",  (0, 1), (0, -1), C["white"]),
            ("FONTNAME",   (0, 1), (0, -1), "Helvetica-Bold"),
        ]
    if extra:
        cmds += extra
    return TableStyle(cmds)


# ---------------------------------------------------------------------------
# Header / Footer (via canvas — pas sur page 1 cover)
# ---------------------------------------------------------------------------

def _header_footer(canvas, doc, company_name, ticker, gen_date, total_pages):
    if doc.page == 1:
        return
    from reportlab.lib.units import mm
    C = _C()
    w, h = doc.pagesize
    lm, rm = doc.leftMargin, doc.rightMargin
    bm = doc.bottomMargin

    canvas.saveState()
    # Header line
    canvas.setStrokeColor(C["navy"])
    canvas.setLineWidth(0.4)
    canvas.line(lm, h - 13 * mm, w - rm, h - 13 * mm)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(C["navy"])
    canvas.drawString(lm, h - 10.5 * mm, ticker)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(C["grey"])
    canvas.drawRightString(w - rm, h - 10.5 * mm, "FinSight IA -- Confidentiel")
    # Footer line
    canvas.setStrokeColor(C["navy"])
    canvas.line(lm, bm - 4 * mm, w - rm, bm - 4 * mm)
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(C["grey"])
    canvas.drawString(lm, bm - 7 * mm,
                      f"FinSight IA  |  {company_name} ({ticker})  |  {gen_date}  |  Usage confidentiel")
    canvas.drawRightString(w - rm, bm - 7 * mm,
                           f"{doc.page} / {total_pages[0]}")
    canvas.restoreState()


# ---------------------------------------------------------------------------
# PAGE 1 — Cover
# ---------------------------------------------------------------------------

def _page_cover(ticker, company_name, sector, exchange, gen_date, styles):
    from reportlab.platypus import PageBreak
    from reportlab.platypus.flowables import Flowable
    from reportlab.lib import colors as C
    from reportlab.lib.units import mm

    class CoverPage(Flowable):
        def __init__(self, ticker, company_name, sector, exchange, gen_date):
            Flowable.__init__(self)
            self.ticker = ticker
            self.company_name = company_name
            self.sector = sector
            self.exchange = exchange
            self.gen_date = gen_date

        def wrap(self, w, h):
            self._w = w
            self._h = h
            return w, h

        def draw(self):
            cv = self.canv
            W, H = self._w, self._h

            # Full-width navy band (top 42%)
            band_h = H * 0.42
            cv.setFillColor(C.HexColor("#1B3A6B"))
            cv.rect(0, H - band_h, W, band_h, fill=1, stroke=0)

            # "FinSight IA" small label
            cv.setFont("Helvetica", 7.5)
            cv.setFillColor(C.HexColor("#7B9ACB"))
            cv.drawString(0, H - 14 * mm, "FinSight IA")

            # Company name
            cv.setFont("Helvetica-Bold", 22)
            cv.setFillColor(C.white)
            name = self.company_name
            cv.drawString(0, H - 30 * mm, name)

            # "Rapport d'analyse"
            cv.setFont("Helvetica", 11)
            cv.setFillColor(C.HexColor("#AABBCC"))
            cv.drawString(0, H - 40 * mm, "Rapport d'analyse")

            # ticker . bourse . secteur
            cv.setFont("Helvetica", 9)
            cv.setFillColor(C.HexColor("#AABBCC"))
            parts = "  .  ".join(p for p in [self.ticker, self.exchange, self.sector] if p)
            cv.drawString(0, H - 50 * mm, parts)

            # Date bottom left of band
            cv.setFont("Helvetica", 7)
            cv.setFillColor(C.HexColor("#7B9ACB"))
            cv.drawString(0, H - band_h + 8 * mm, self.gen_date)
            cv.drawRightString(W, H - band_h + 8 * mm, "Rapport confidentiel")

    return [CoverPage(ticker, company_name, sector, exchange, gen_date), PageBreak()]


# ---------------------------------------------------------------------------
# PAGE 2 — Sommaire
# ---------------------------------------------------------------------------

def _page_sommaire(styles):
    from reportlab.platypus import Paragraph, Spacer, Table, PageBreak

    elems = [
        Paragraph("SOMMAIRE", styles["section"]),
        Spacer(1, 6),
        Paragraph(
            "Ce rapport presente une analyse financiere complete produite par FinSight IA. "
            "Les sections couvrent la synthese d'investissement, l'analyse des etats financiers, "
            "la valorisation multi-methodes ainsi que les risques et le sentiment de marche. "
            "Toutes les donnees sont issues de sources publiques.",
            styles["body"]),
        Spacer(1, 10),
    ]
    toc_rows = [
        ["", "Section", "Page"],
        ["1", "Synthese Executive & Recommandation", "3"],
        ["2", "Analyse Financiere", "4"],
        ["3", "Valorisation", "5"],
        ["4", "Risques & Sentiment de Marche", "6"],
    ]
    cw = [12 * _mm, 135 * _mm, 23 * _mm]
    _assert_tw(cw)
    t = Table(toc_rows, colWidths=cw)
    t.setStyle(_ts(first_col_navy=False))
    elems += [t, Spacer(1, 8), PageBreak()]
    return elems


# ---------------------------------------------------------------------------
# PAGE 3 — Synthese executive
# ---------------------------------------------------------------------------

def _page_synthese(snap, ratios, synthesis, styles):
    from reportlab.platypus import Paragraph, Spacer, Table, PageBreak
    from reportlab.platypus.flowables import Flowable
    from reportlab.lib import colors as C
    from reportlab.lib.units import mm

    ci    = snap.company_info
    mkt   = snap.market
    cur   = ci.currency or "USD"
    price = mkt.share_price
    rec   = _g(synthesis, "recommendation") or "N/A"
    conv  = _g(synthesis, "conviction")
    conf  = _g(synthesis, "confidence_score")
    tbase = _g(synthesis, "target_base")
    tbear = _g(synthesis, "target_bear")
    tbull = _g(synthesis, "target_bull")
    summary      = _g(synthesis, "summary") or ""
    strengths    = _g(synthesis, "strengths") or []
    risks_list   = _g(synthesis, "risks") or []
    val_comment  = _g(synthesis, "valuation_comment") or ""

    conv_s  = f"{float(conv) * 100:.0f} %" if conv is not None else "N/A"
    conf_s  = f"{float(conf) * 100:.0f} %" if conf is not None else "N/A"
    up_s    = _upside(tbase, price)
    tbase_s = f"{float(tbase):.0f} {cur}" if tbase else "N/A"
    price_s = f"{float(price):.2f} {cur}" if price else "N/A"

    rec_col = _rec_color(rec)

    class VerdictBanner(Flowable):
        def wrap(self, w, h):
            self._w = w
            return w, 13 * mm
        def draw(self):
            cv = self.canv
            cv.setFillColor(rec_col)
            cv.rect(0, 0, self._w, 13 * mm, fill=1, stroke=0)
            cv.setFont("Helvetica-Bold", 8.5)
            cv.setFillColor(C.white)
            line = (f"l {rec}     Cours : {price_s}  .  Cible base : {tbase_s}"
                    f"  .  Upside : {up_s}  .  Conviction : {conv_s}  .  Confiance IA : {conf_s}")
            cv.drawString(4 * mm, 4.5 * mm, line)

    elems = [
        Paragraph("1. SYNTHESE EXECUTIVE", styles["section"]),
        Spacer(1, 4),
        VerdictBanner(),
        Spacer(1, 8),
    ]

    # Description
    if summary:
        elems += [Paragraph(summary, styles["body"]), Spacer(1, 6)]

    # Scenarios table
    elems.append(Paragraph("Scenarios de valorisation", styles["subsec"]))

    def _hyp(scenario):
        if scenario == "Bear" and risks_list:
            s = risks_list[0]
        elif scenario == "Bull" and strengths:
            s = strengths[0]
        elif strengths:
            s = strengths[1] if len(strengths) > 1 else strengths[0]
        else:
            return "--"
        return (s[:68] + "...") if len(s) > 68 else s

    sdata = [
        ["",                    "Bear",                                    "Base",                                    "Bull"],
        ["Prix cible",          _v(tbear, "{:.0f}") + f" {cur}",          _v(tbase, "{:.0f}") + f" {cur}",          _v(tbull, "{:.0f}") + f" {cur}"],
        ["Upside/Downside",     _upside(tbear, price),                    _upside(tbase, price),                    _upside(tbull, price)],
        ["Probabilite estimee", "25 %",                                    "50 %",                                    "25 %"],
        ["Hypothese det.",      _hyp("Bear"),                             _hyp("Base"),                             _hyp("Bull")],
    ]
    cw = [38 * _mm, 44 * _mm, 44 * _mm, 44 * _mm]
    _assert_tw(cw)
    t = Table(sdata, colWidths=cw)
    t.setStyle(_ts(first_col_navy=True))
    elems += [t, Spacer(1, 8)]

    # These d'investissement
    if val_comment:
        elems.append(Paragraph("These d'investissement", styles["subsec"]))
        elems.append(Paragraph(val_comment, styles["body"]))

    elems.append(PageBreak())
    return elems


# ---------------------------------------------------------------------------
# Benchmarks sectoriels
# ---------------------------------------------------------------------------

def _benchmarks(sector: str) -> dict:
    s = (sector or "").lower()
    if "tech" in s or "software" in s or "semiconductor" in s:
        return dict(pe="20-35x", ev_ebitda="15-25x", ev_rev="5-12x",
                    gross_m="55-75 %", ebitda_m="20-35 %", roe="15-30 %")
    if "health" in s or "pharma" in s or "biotech" in s:
        return dict(pe="18-30x", ev_ebitda="12-20x", ev_rev="3-8x",
                    gross_m="60-75 %", ebitda_m="20-30 %", roe="12-20 %")
    if "financ" in s or "bank" in s or "insur" in s:
        return dict(pe="10-16x", ev_ebitda="8-12x", ev_rev="2-4x",
                    gross_m="50-65 %", ebitda_m="30-45 %", roe="10-18 %")
    if "energy" in s or "oil" in s or "gas" in s:
        return dict(pe="10-18x", ev_ebitda="6-10x", ev_rev="1-3x",
                    gross_m="30-50 %", ebitda_m="25-40 %", roe="10-15 %")
    if any(w in s for w in ("consumer", "retail", "luxury", "cyclical", "auto")):
        return dict(pe="8-15x", ev_ebitda="6-12x", ev_rev="0.4-1.2x",
                    gross_m="12-18 %", ebitda_m="8-14 %", roe="8-18 %")
    return dict(pe="15-22x", ev_ebitda="10-16x", ev_rev="2-5x",
                gross_m="35-55 %", ebitda_m="15-25 %", roe="10-18 %")


def _lecture_multiple(val, bm_str):
    try:
        v = float(val)
        parts = bm_str.replace("x", "").replace(" ", "").split("-")
        lo, hi = float(parts[0]), float(parts[1])
        if v > hi * 1.4:
            return "Prime technologique"
        if v > hi:
            return "Superieur"
        if v < lo * 0.8:
            return "Decote"
        return "Dans la norme"
    except Exception:
        return "--"


def _lecture_marge(val, bm_str):
    try:
        v = float(val) * 100
        parts = bm_str.replace("%", "").replace(" ", "").split("-")
        lo, hi = float(parts[0]), float(parts[1])
        if v > hi:
            return "Superieure"
        if v < lo:
            return "Inferieure"
        return "En ligne"
    except Exception:
        return "--"


# ---------------------------------------------------------------------------
# PAGE 4 — Analyse financiere
# ---------------------------------------------------------------------------

def _page_financiere(snap, ratios, synthesis, styles):
    from reportlab.platypus import Paragraph, Spacer, Table, PageBreak
    from reportlab.lib import colors as C

    C_ = _C()
    ci    = snap.company_info
    cur   = ci.currency or "USD"
    units = ci.units or "M"

    elems = [Paragraph("2. ANALYSE FINANCIERE", styles["section"]), Spacer(1, 4)]
    elems.append(Paragraph(f"Compte de resultat consolide ({cur} {units})", styles["subsec"]))

    hist_labels = sorted(snap.years.keys(), key=lambda y: str(y).replace("_LTM", ""))
    display_labels = hist_labels[-4:] if hist_labels else []

    def _fy(lbl):
        return snap.years.get(lbl)

    def _ry(lbl):
        return ratios.years.get(lbl) if ratios else None

    col_names = [lbl.replace("_LTM", " LTM") for lbl in display_labels]
    n = len(display_labels)

    is_rows = [["Indicateur"] + col_names]

    # Revenue
    is_rows.append(["Chiffre d'affaires"] + [
        _m(getattr(_fy(l), "revenue", None) if _fy(l) else None)
        for l in display_labels
    ])
    # Croissance YoY
    grow = []
    prev = None
    for l in display_labels:
        fy = _fy(l)
        rev = fy.revenue if fy else None
        if prev and rev and prev != 0:
            grow.append(f"{(rev - prev) / abs(prev) * 100:+.1f} %")
        else:
            grow.append("--")
        prev = rev
    is_rows.append(["Croissance YoY"] + grow)
    # Marge brute
    is_rows.append(["Marge brute"] + [
        _pct(getattr(_ry(l), "gross_margin", None) if _ry(l) else None)
        for l in display_labels
    ])
    # EBITDA
    is_rows.append(["EBITDA"] + [
        _m(getattr(_ry(l), "ebitda", None) if _ry(l) else None)
        for l in display_labels
    ])
    # Marge EBITDA
    is_rows.append(["Marge EBITDA"] + [
        _pct(getattr(_ry(l), "ebitda_margin", None) if _ry(l) else None)
        for l in display_labels
    ])
    # Resultat net
    is_rows.append(["Resultat net"] + [
        _m(getattr(_ry(l), "net_income", None) if _ry(l) else None)
        for l in display_labels
    ])
    # Marge nette
    is_rows.append(["Marge nette"] + [
        _pct(getattr(_ry(l), "net_margin", None) if _ry(l) else None)
        for l in display_labels
    ])

    first_w = 44 * _mm
    rest_w  = (_TW - first_w) / max(n, 1)
    cw_is   = [first_w] + [rest_w] * n
    _assert_tw(cw_is)

    # Surligner derniere colonne (LTM)
    extra = []
    if n > 0:
        last_c = n  # 0-indexed last column index
        extra = [
            ("BACKGROUND", (last_c, 1), (last_c, -1), C.HexColor("#EEF2F8")),
            ("FONTNAME",   (last_c, 0), (last_c,  0), "Helvetica-Bold"),
            ("TEXTCOLOR",  (last_c, 0), (last_c,  0), C.white),
        ]

    t_is = Table(is_rows, colWidths=cw_is)
    t_is.setStyle(_ts(extra=extra, first_col_navy=True))
    elems += [t_is, Spacer(1, 4)]

    summary = _g(synthesis, "summary") or ""
    if summary:
        elems.append(Paragraph(summary[:500], styles["italic"]))
    elems.append(Spacer(1, 8))

    # --- Ratios vs benchmark ---
    elems.append(Paragraph("Positionnement relatif -- Ratios cles vs. pairs sectoriels", styles["subsec"]))

    sector    = ci.sector or ""
    bm        = _benchmarks(sector)
    latest_l  = hist_labels[-1] if hist_labels else None
    yr        = _ry(latest_l) if latest_l else None

    def _attr(a):
        return getattr(yr, a, None) if yr else None

    pe    = _attr("pe_ratio")
    ev_e  = _attr("ev_ebitda")
    ev_r  = _attr("ev_revenue")
    gm    = _attr("gross_margin")
    em    = _attr("ebitda_margin")
    roe   = _attr("roe")
    az    = _attr("altman_z")
    bm_sc = _attr("beneish_m")

    pe_s   = "n.m." if pe   and float(pe) > 999 else _x(pe)
    ev_e_s = "n.m." if ev_e and float(ev_e) > 999 else _x(ev_e)
    az_l   = ("Solide"    if az and float(az) > 2.99 else
              "Zone grise" if az and float(az) > 1.81 else
              "Detresse"   if az else "--")
    bm_l   = "Aucun signal" if bm_sc and float(bm_sc) < -2.22 else ("Risque manip." if bm_sc else "--")

    rdata = [["Indicateur", f"{ci.ticker} LTM", "Reference sectorielle", "Lecture"]]
    rdata += [
        ["P/E (x)",         pe_s,                bm["pe"],       _lecture_multiple(pe,   bm["pe"])],
        ["EV / EBITDA (x)", ev_e_s,              bm["ev_ebitda"],_lecture_multiple(ev_e, bm["ev_ebitda"])],
        ["EV / Revenue (x)",_x(ev_r),            bm["ev_rev"],   _lecture_multiple(ev_r, bm["ev_rev"])],
        ["Marge brute",     _pct(gm),            bm["gross_m"],  _lecture_marge(gm,  bm["gross_m"])],
        ["Marge EBITDA",    _pct(em),            bm["ebitda_m"], _lecture_marge(em,  bm["ebitda_m"])],
        ["Return on Equity",_pct(roe),           bm["roe"],      _lecture_marge(roe, bm["roe"])],
        ["Altman Z-Score",  _v(az, "{:.1f}"),    "> 2.99 = sain",az_l],
        ["Beneish M-Score", _v(bm_sc, "{:.2f}"), "< -2.22 = OK", bm_l],
    ]

    cw_r = [48 * _mm, 32 * _mm, 55 * _mm, 35 * _mm]
    _assert_tw(cw_r)
    t_r = Table(rdata, colWidths=cw_r)
    t_r.setStyle(_ts(first_col_navy=True))
    elems += [t_r, Spacer(1, 4)]

    ratio_comment = _g(synthesis, "valuation_comment") or ""
    if ratio_comment:
        elems.append(Paragraph(ratio_comment[:300], styles["italic"]))

    elems.append(PageBreak())
    return elems


# ---------------------------------------------------------------------------
# PAGE 5 — Valorisation
# ---------------------------------------------------------------------------

def _page_valorisation(snap, ratios, synthesis, styles):
    from reportlab.platypus import Paragraph, Spacer, Table, PageBreak
    from reportlab.lib import colors as C

    C_  = _C()
    ci  = snap.company_info
    mkt = snap.market
    cur = ci.currency or "USD"

    price = mkt.share_price
    wacc  = mkt.wacc or 0.10
    tgr   = mkt.terminal_growth or 0.03
    tbase = _g(synthesis, "target_base")
    tbear = _g(synthesis, "target_bear")
    tbull = _g(synthesis, "target_bull")

    hist_labels = sorted(snap.years.keys(), key=lambda y: str(y).replace("_LTM", ""))
    latest_l    = hist_labels[-1] if hist_labels else None
    yr_latest   = ratios.years.get(latest_l) if ratios and latest_l else None

    elems = [Paragraph("3. VALORISATION", styles["section"]), Spacer(1, 4)]

    # --- DCF ---
    elems.append(Paragraph(
        f"Discounted Cash Flow -- Scenario base -- WACC {wacc * 100:.1f} %"
        f" -- Taux terminal {tgr * 100:.1f} % -- Horizon 5 ans",
        styles["subsec"]))

    dcf_txt = _g(synthesis, "valuation_comment") or (
        f"Le modele DCF retient un WACC de {wacc * 100:.1f} % et un taux terminal de "
        f"{tgr * 100:.1f} %. La valeur intrinseque ressort a "
        f"{_v(tbase, '{:.0f}')} {cur} dans le scenario base, soit un upside de "
        f"{_upside(tbase, price)} par rapport au cours actuel ({_v(price, '{:.2f}')} {cur})."
    )
    elems.append(Paragraph(dcf_txt, styles["body"]))
    elems.append(Spacer(1, 6))

    # --- Sensibilite 5x5 ---
    elems.append(Paragraph("Table de sensibilite -- Valeur intrinseque par action", styles["subsec"]))

    waccs = [wacc - 0.02, wacc - 0.01, wacc, wacc + 0.01, wacc + 0.02]
    tgrs  = [tgr - 0.010, tgr - 0.005, tgr, tgr + 0.005, tgr + 0.010]
    base_v      = float(tbase) if tbase else (float(price) if price else 100.0)
    denom_base  = wacc - tgr

    def _dcf(w, t):
        d = w - t
        if abs(d) < 1e-4 or abs(denom_base) < 1e-4:
            return "--"
        return f"{base_v * denom_base / d:.0f}"

    sens_data = [["WACC \\ TGR"] + [f"{t * 100:.1f} %" for t in tgrs]]
    for i, w in enumerate(waccs):
        sens_data.append([f"{w * 100:.1f} %"] + [_dcf(w, t) for t in tgrs])

    # 6 cols : label + 5 tgr values
    cw_s = [28 * _mm, 28.4 * _mm, 28.4 * _mm, 28.4 * _mm, 28.4 * _mm, 28.4 * _mm]
    _assert_tw(cw_s)

    extra_s = [
        ("BACKGROUND", (3, 3), (3, 3), C_["navy"]),
        ("TEXTCOLOR",  (3, 3), (3, 3), C_["white"]),
        ("FONTNAME",   (3, 3), (3, 3), "Helvetica-Bold"),
    ]
    t_s = Table(sens_data, colWidths=cw_s)
    t_s.setStyle(_ts(extra=extra_s, first_col_navy=True))
    elems += [t_s, Spacer(1, 3)]
    elems.append(Paragraph(
        "Ligne et colonne surlignees correspondent au scenario base. "
        "La cellule d'intersection materialise la valeur centrale du modele.",
        styles["small"]))
    elems.append(Spacer(1, 8))

    # --- Comparables peers ---
    elems.append(Paragraph("Analyse par multiples comparables -- Pairs sectoriels LTM", styles["subsec"]))

    peers = _g(synthesis, "comparable_peers")
    p_header = ["Societe", "EV/EBITDA", "EV/Revenue", "P/E", "Marge brute", "Marge EBITDA"]
    cw_p = [44 * _mm, 26 * _mm, 26 * _mm, 22 * _mm, 26 * _mm, 26 * _mm]
    _assert_tw(cw_p)

    pdata = [p_header, [
        f"{ci.ticker} (cible)",
        _x(getattr(yr_latest, "ev_ebitda",  None) if yr_latest else None),
        _x(getattr(yr_latest, "ev_revenue", None) if yr_latest else None),
        _x(getattr(yr_latest, "pe_ratio",   None) if yr_latest else None),
        _pct(getattr(yr_latest, "gross_margin",  None) if yr_latest else None),
        _pct(getattr(yr_latest, "ebitda_margin", None) if yr_latest else None),
    ]]

    if peers:
        for p in peers[:5]:
            nm  = _g(p, "name") or _g(p, "ticker") or "--"
            pdata.append([
                nm,
                _x(_g(p, "ev_ebitda")),
                _x(_g(p, "ev_revenue")),
                _x(_g(p, "pe")),
                _pct(_g(p, "gross_margin")),
                _pct(_g(p, "ebitda_margin")),
            ])

        def _median(attr):
            vals = []
            for p in peers[:5]:
                try:
                    v = float(_g(p, attr) or "nan")
                    if -999 < v < 999:
                        vals.append(v)
                except Exception:
                    pass
            if not vals:
                return "--"
            vals.sort()
            return f"{vals[len(vals) // 2]:.1f}x"

        def _median_pct(attr):
            vals = []
            for p in peers[:5]:
                try:
                    vals.append(float(_g(p, attr) or "nan"))
                except Exception:
                    pass
            if not vals:
                return "--"
            vals.sort()
            v = vals[len(vals) // 2]
            return f"{v * 100:.1f} %" if abs(v) < 10 else f"{v:.1f} %"

        pdata.append([
            "Mediane peers",
            _median("ev_ebitda"), _median("ev_revenue"), _median("pe"),
            _median_pct("gross_margin"), _median_pct("ebitda_margin"),
        ])
    else:
        pdata.append(["Donnees comparables non disponibles", "--", "--", "--", "--", "--"])

    extra_p = [
        ("FONTNAME",   (0, 1), (-1, 1),  "Helvetica-Bold"),
        ("FONTNAME",   (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), C.HexColor("#EEF2F8")),
    ]
    t_p = Table(pdata, colWidths=cw_p)
    t_p.setStyle(_ts(extra=extra_p, first_col_navy=True))
    elems += [t_p, Spacer(1, 8)]

    # --- Football Field ---
    elems.append(Paragraph("Football Field Chart -- Synthese des methodes de valorisation", styles["subsec"]))

    ff_src  = _g(synthesis, "football_field")
    ff_rows = []
    if ff_src:
        for m in ff_src:
            ff_rows.append({
                "label": _g(m, "label") or _g(m, "method") or "--",
                "low":   _g(m, "range_low")  or _g(m, "low"),
                "high":  _g(m, "range_high") or _g(m, "high"),
                "mid":   _g(m, "midpoint")   or _g(m, "mid"),
            })
    else:
        if tbear:
            ff_rows.append({"label": "DCF -- Bear", "low": tbear * 0.90, "high": tbear * 1.06, "mid": tbear})
        if tbase:
            ff_rows.append({"label": "DCF -- Base", "low": tbase * 0.94, "high": tbase * 1.06, "mid": tbase})
        if tbull:
            ff_rows.append({"label": "DCF -- Bull", "low": tbull * 0.92, "high": tbull * 1.10, "mid": tbull})
        if yr_latest and yr_latest.ev_ebitda and price:
            bm = _benchmarks(ci.sector or "")
            try:
                parts = bm["ev_ebitda"].replace("x","").replace(" ","").split("-")
                med = (float(parts[0]) + float(parts[1])) / 2
                impl = float(price) * med / float(yr_latest.ev_ebitda)
                ff_rows.append({"label": "EV/EBITDA -- Mediane peers",
                                 "low": impl * 0.90, "high": impl * 1.10, "mid": impl})
            except Exception:
                pass

    ff_tdata = [["Methode", "Fourchette basse", "Fourchette haute", "Point central"]]
    for r in ff_rows:
        ff_tdata.append([
            r["label"],
            _v(r["low"],  "{:.0f}") + f" {cur}",
            _v(r["high"], "{:.0f}") + f" {cur}",
            _v(r["mid"],  "{:.0f}") + f" {cur}",
        ])
    if price:
        ff_tdata.append([
            f"Cours actuel ({date.today().strftime('%d/%m/%Y')})",
            "--", "--", f"{float(price):.2f} {cur}"
        ])

    cw_ff = [72 * _mm, 33 * _mm, 33 * _mm, 32 * _mm]
    _assert_tw(cw_ff)
    t_ff = Table(ff_tdata, colWidths=cw_ff)
    t_ff.setStyle(_ts(first_col_navy=True))
    elems += [t_ff, Spacer(1, 4)]

    # Bar chart
    if ff_rows and price:
        elems.append(_football_chart(ff_rows, float(price), cur))

    elems.append(Paragraph(
        f"Le scenario DCF base ({_v(tbase, '{:.0f}')} {cur}) et le cours actuel "
        f"({_v(price, '{:.2f}')} {cur}) sont coherents avec une valorisation mixte.",
        styles["small"]))

    elems.append(PageBreak())
    return elems


def _football_chart(ff_rows, current_price, cur):
    from reportlab.platypus.flowables import Flowable
    from reportlab.lib import colors as C
    from reportlab.lib.units import mm

    COLORS = [
        C.HexColor("#A82020"),
        C.HexColor("#1B3A6B"),
        C.HexColor("#1A7A4A"),
        C.HexColor("#7B5EA7"),
        C.HexColor("#B06000"),
    ]

    class FFChart(Flowable):
        def wrap(self, w, h):
            self._w = w
            n = len(ff_rows)
            self._h = n * 9 * mm + 20 * mm
            return w, self._h

        def draw(self):
            cv  = self.canv
            W   = self._w
            H   = self._h
            n   = len(ff_rows)
            if n == 0:
                return

            ml = 38 * mm
            mr = 8 * mm
            mb = 12 * mm
            mt = 4 * mm
            chart_w = W - ml - mr
            bar_h   = 5 * mm
            row_h   = 9 * mm

            # Value range
            all_v = [current_price]
            for r in ff_rows:
                if r.get("low"):  all_v.append(float(r["low"]))
                if r.get("high"): all_v.append(float(r["high"]))
            vmin = min(all_v) * 0.88
            vmax = max(all_v) * 1.08
            vrange = vmax - vmin
            if vrange == 0:
                return

            def to_x(v):
                return ml + (float(v) - vmin) / vrange * chart_w

            for i, row in enumerate(ff_rows):
                y    = H - mt - (i + 1) * row_h + (row_h - bar_h) / 2
                low  = row.get("low")
                high = row.get("high")
                mid  = row.get("mid")
                lbl  = (row.get("label") or "")[:30]
                col  = COLORS[i % len(COLORS)]

                cv.setFont("Helvetica", 5.5)
                cv.setFillColor(C.HexColor("#333333"))
                cv.drawRightString(ml - 2 * mm, y + bar_h / 2 - 1.5, lbl)

                if low and high:
                    x1, x2 = to_x(low), to_x(high)
                    cv.setFillColor(col)
                    cv.setFillAlpha(0.22)
                    cv.rect(x1, y, x2 - x1, bar_h, fill=1, stroke=0)
                    cv.setFillAlpha(1.0)
                    cv.setStrokeColor(col)
                    cv.setLineWidth(0.7)
                    cv.rect(x1, y, x2 - x1, bar_h, fill=0, stroke=1)
                    if mid:
                        xm = to_x(mid)
                        cv.setFillColor(col)
                        cv.circle(xm, y + bar_h / 2, 1.8 * mm, fill=1, stroke=0)
                        cv.setFont("Helvetica-Bold", 5)
                        cv.setFillColor(C.HexColor("#111111"))
                        cv.drawCentredString(xm, y - 3.5, f"{float(mid):.0f}")

            # Current price line
            xp = to_x(current_price)
            cv.setStrokeColor(C.HexColor("#B06000"))
            cv.setLineWidth(1.0)
            cv.setDash(3, 2)
            cv.line(xp, mb, xp, H - mt)
            cv.setDash()
            cv.setFont("Helvetica-Bold", 5.5)
            cv.setFillColor(C.HexColor("#B06000"))
            cv.drawCentredString(xp, mb - 5, f"Cours {current_price:.0f} {cur}")

            # X-axis ticks
            cv.setFont("Helvetica", 5)
            cv.setFillColor(C.HexColor("#888888"))
            for tick in range(5):
                vt = vmin + tick * vrange / 4
                xt = to_x(vt)
                cv.drawCentredString(xt, mb - 5, f"{vt:.0f}")

    return FFChart()


# ---------------------------------------------------------------------------
# PAGE 6 — Risques & Sentiment
# ---------------------------------------------------------------------------

def _page_risques_sentiment(snap, synthesis, devil, sentiment, styles):
    from reportlab.platypus import Paragraph, Spacer, Table, HRFlowable
    from reportlab.lib import colors as C

    C_ = _C()
    ci  = snap.company_info

    elems = [Paragraph("4. ANALYSE DES RISQUES", styles["section"]), Spacer(1, 4)]

    # --- Avocat du diable ---
    elems.append(Paragraph(
        "These contraire -- Arguments en faveur d'une revision a la baisse",
        styles["subsec"]))

    counter_thesis = _g(devil, "counter_thesis") or ""
    counter_risks  = _g(devil, "counter_risks") or []
    risks_synth    = _g(synthesis, "risks") or []

    texts = []
    if counter_thesis:
        texts.append(counter_thesis)
    if counter_risks:
        texts += list(counter_risks[:3])
    if not texts:
        texts = risks_synth[:3]
    if not texts:
        texts = ["Analyse contradictoire non disponible."]

    for t in texts:
        if t:
            elems.append(Paragraph(str(t), styles["body"]))

    elems.append(Spacer(1, 8))

    # --- Conditions d'invalidation ---
    elems.append(Paragraph("Conditions d'invalidation de la these", styles["subsec"]))

    inv_synth = _g(synthesis, "invalidation_conditions") or ""
    inv_devil = _g(devil, "invalidation_conditions") or ""
    inv_list  = _g(synthesis, "invalidation_list")

    cdata = [["Axe", "Condition d'invalidation", "Horizon"]]
    if inv_list:
        for c in inv_list[:3]:
            cdata.append([
                _g(c, "axis") or "--",
                _g(c, "condition") or "--",
                _g(c, "horizon") or "--",
            ])
    else:
        if inv_synth:
            txt = (inv_synth[:100] + "...") if len(inv_synth) > 100 else inv_synth
            cdata.append(["Synthese IA", txt, "Court-moyen terme"])
        if inv_devil:
            txt = (inv_devil[:100] + "...") if len(inv_devil) > 100 else inv_devil
            cdata.append(["Avocat du diable", txt, "Court terme"])
        if len(cdata) == 1:
            cdata += [
                ["Macro",     "Taux 10 ans > 5,5 % deux trimestres consecutifs",          "6-12 mois"],
                ["Sectoriel", "Perte de part de marche significative vs. principaux pairs", "12-18 mois"],
                ["Societe",   "Marge brute sous plancher historique sur 2 trimestres",      "2-3 trim."],
            ]

    cw_c = [28 * _mm, 108 * _mm, 34 * _mm]
    _assert_tw(cw_c)
    t_c = Table(cdata, colWidths=cw_c)
    t_c.setStyle(_ts(first_col_navy=True))
    elems += [t_c, Spacer(1, 10)]

    # --- Sentiment ---
    elems.append(Paragraph("5. SENTIMENT DE MARCHE", styles["section"]))
    elems.append(Spacer(1, 4))

    if not sentiment:
        elems.append(Paragraph("Donnees de sentiment non disponibles.", styles["body"]))
    else:
        label     = _g(sentiment, "label") or "NEUTRAL"
        score     = float(_g(sentiment, "score") or 0.0)
        conf      = float(_g(sentiment, "confidence") or 0.0)
        n_art     = int(_g(sentiment, "articles_analyzed") or 0)
        breakdown = _g(sentiment, "breakdown") or {}
        samples   = _g(sentiment, "samples") or []
        engine    = (_g(sentiment, "meta", "engine") or "VADER").upper()

        elems.append(Paragraph(
            f"L'analyse semantique {engine} conduite sur un corpus de {n_art} articles publie"
            f"s au cours des sept derniers jours fait ressortir un sentiment globalement "
            f"{label.lower()} avec une inflexion (score agrege : {score:+.3f}). "
            f"Confiance : {conf * 100:.0f} %.",
            styles["body"]))
        elems.append(Spacer(1, 4))

        avg_pos = breakdown.get("avg_positive", 0)
        avg_neu = breakdown.get("avg_neutral",  0)
        avg_neg = breakdown.get("avg_negative", 0)
        n_pos = round(avg_pos * n_art) if n_art else 0
        n_neu = round(avg_neu * n_art) if n_art else 0
        n_neg = round(avg_neg * n_art) if n_art else 0

        def _themes(orient):
            ts = []
            for s in samples:
                lbl = (s.get("label") or "").upper()
                if ((orient == "Positif" and lbl == "POSITIVE") or
                        (orient == "Negatif" and lbl == "NEGATIVE") or
                        (orient == "Neutre"  and lbl == "NEUTRAL")):
                    h = s.get("headline", "")[:38]
                    if h:
                        ts.append(h)
            return ", ".join(ts[:2]) or "--"

        sdata = [["Orientation", "Articles", "Score moyen", "Themes principaux"]]
        sdata += [
            ["Positif", str(n_pos), f"{avg_pos:+.2f}", _themes("Positif")],
            ["Neutre",  str(n_neu), f"{avg_neu:+.2f}", _themes("Neutre")],
            ["Negatif", str(n_neg), f"{-avg_neg:+.2f}", _themes("Negatif")],
        ]
        cw_sent = [26 * _mm, 18 * _mm, 22 * _mm, 104 * _mm]
        _assert_tw(cw_sent)
        t_sent = Table(sdata, colWidths=cw_sent)
        t_sent.setStyle(_ts(first_col_navy=False, alt_rows=True))
        elems += [t_sent, Spacer(1, 8)]

    # --- Disclaimer ---
    elems.append(HRFlowable(width=_TW, thickness=0.5, color=C_["navy"]))
    elems.append(Spacer(1, 4))
    elems.append(Paragraph("Avertissement legal", styles["bold"]))
    elems.append(Paragraph(
        f"Ce rapport a ete genere par FinSight IA v1.0 le {date.today().strftime('%d %B %Y')}. "
        "Il est produit integralement par un systeme d'intelligence artificielle et ne constitue "
        "pas un conseil en investissement au sens de la directive europeenne MiFID II (2014/65/UE). "
        "FinSight IA ne saurait etre tenu responsable des decisions prises sur la base de ce document. "
        "Les donnees financieres sont issues de sources publiques (yfinance, Finnhub Financial, "
        "Financial Modeling Prep) et peuvent contenir des inexactitudes. Tout investisseur est invite "
        "a proceder a sa propre diligence et a consulter un professionnel qualifie avant toute decision. "
        "Document confidentiel -- diffusion restreinte.",
        styles["small"]))
    return elems


# ---------------------------------------------------------------------------
# PDFWriter — classe publique
# ---------------------------------------------------------------------------

class PDFWriter:
    """
    Generateur de rapport PDF FinSight IA.

    Usage :
        writer = PDFWriter()
        path   = writer.generate(state, "outputs/generated/report.pdf")
    """

    def generate(self, state: dict, output_path: str) -> str:
        """
        Genere le PDF complet depuis un FinSightState LangGraph.

        Args:
            state       : dict FinSightState (raw_data, ratios, synthesis, sentiment, devil)
            output_path : chemin absolu ou relatif du fichier PDF a creer

        Returns:
            str : chemin absolu du fichier cree
        """
        try:
            from reportlab.platypus import SimpleDocTemplate
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
        except ImportError:
            raise RuntimeError("reportlab requis : pip install reportlab")

        snap      = state.get("raw_data")
        ratios    = state.get("ratios")
        synthesis = state.get("synthesis")
        sentiment = state.get("sentiment")
        devil     = state.get("devil")

        if snap is None:
            raise ValueError("PDFWriter: state['raw_data'] (FinancialSnapshot) est requis")

        ci       = snap.company_info
        ticker   = ci.ticker or state.get("ticker", "UNKNOWN")
        co_name  = ci.company_name or ticker
        sector   = ci.sector or ""
        exchange = getattr(ci, "exchange", "") or ""
        gen_date = ci.analysis_date or date.today().strftime("%d %B %Y")

        out      = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        st = _styles()
        total_pages = [6]

        def _cb(canvas, doc):
            _header_footer(canvas, doc, co_name, ticker, gen_date, total_pages)

        doc = SimpleDocTemplate(
            str(out),
            pagesize=A4,
            leftMargin=18 * mm, rightMargin=18 * mm,
            topMargin=16 * mm,  bottomMargin=20 * mm,
            title=f"FinSight IA -- {co_name} ({ticker})",
            author="FinSight IA v1.0",
        )

        story = []
        story += _page_cover(ticker, co_name, sector, exchange, gen_date, st)
        story += _page_sommaire(st)
        story += _page_synthese(snap, ratios, synthesis, st)
        story += _page_financiere(snap, ratios, synthesis, st)
        story += _page_valorisation(snap, ratios, synthesis, st)
        story += _page_risques_sentiment(snap, synthesis, devil, sentiment, st)

        doc.build(story, onFirstPage=_cb, onLaterPages=_cb)
        log.info(f"[PDFWriter] {ticker} -> {out.name}")
        return str(out)
