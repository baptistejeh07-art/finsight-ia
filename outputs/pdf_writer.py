# =============================================================================
# FinSight IA -- PDF Writer
# outputs/pdf_writer.py
#
# PDFWriter.generate(state: FinSightState, output_path: str) -> str
#
# 6 pages :
#   1. Page de garde  (bande navy, nom societe, ticker, date)
#   2. Sommaire       (4 sections, numeros de page, intro)
#   3. Synthese       (header societe + verdict, description, scenarios, these)
#                     + 2. ANALYSE FINANCIERE (IS table + commentaire)
#   4. Ratios table   + 3. VALORISATION (DCF + sensibilite + comparables)
#   5. Football field + 4. ANALYSE DES RISQUES (3 para + invalidation)
#                     + 5. SENTIMENT DE MARCHE (intro + table header)
#   6. Sentiment data rows + Disclaimer
#
# Toutes les tables exactement 170mm (AssertionError sinon)
# Police : Helvetica | Couleur accent : #1B3A6B
# Footer : FinSight IA - {societe} ({ticker}) - Usage confidentiel {N}
# =============================================================================

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

try:
    from reportlab.lib.units import mm as _mm
except ImportError:
    _mm = 2.8346

_TW = 170 * _mm   # 481.89 pt -- contrainte stricte


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
        if abs(f) > 999:
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
        return f"{v:.1f}"
    except Exception:
        return default


def _upside(target, current, default="--"):
    if target is None or current is None:
        return default
    try:
        c = float(current)
        if c == 0:
            return default
        u = (float(target) - c) / abs(c) * 100
        return f"{u:+.0f} %"
    except Exception:
        return default


def _assert_tw(col_widths):
    total = sum(col_widths)
    assert abs(total - _TW) < 1.0, (
        f"Table width {total:.1f}pt != {_TW:.1f}pt (170mm). "
        f"Cols: {[round(c / _mm, 1) for c in col_widths]}mm"
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
                                   textColor=C["navy"], spaceBefore=6, spaceAfter=3, leading=12),
        "body":     ParagraphStyle("s_body",  fontName="Helvetica", fontSize=8,
                                   leading=12, spaceAfter=5),
        "small":    ParagraphStyle("s_small", fontName="Helvetica", fontSize=7,
                                   textColor=C["grey"], leading=10, spaceAfter=3),
        "bold":     ParagraphStyle("s_bold",  fontName="Helvetica-Bold", fontSize=8,
                                   leading=12, spaceAfter=2),
        "italic":   ParagraphStyle("s_ital",  fontName="Helvetica-Oblique", fontSize=7.5,
                                   textColor=C["grey"], leading=11, spaceAfter=4),
        "toc":      ParagraphStyle("s_toc",   fontName="Helvetica", fontSize=8.5,
                                   leading=14, leftIndent=12, spaceAfter=3),
        "devil_t":  ParagraphStyle("s_devt",  fontName="Helvetica-Bold", fontSize=8,
                                   leading=12, spaceAfter=1),
    }


# ---------------------------------------------------------------------------
# Table style
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
# Footer (toutes les pages)
# ---------------------------------------------------------------------------

def _footer_cb(company_name, ticker, total_pages):
    def _cb(canvas, doc):
        from reportlab.lib.units import mm
        C = _C()
        w, _ = doc.pagesize
        lm, bm = doc.leftMargin, doc.bottomMargin
        rm = doc.rightMargin
        canvas.saveState()
        canvas.setStrokeColor(C["navy"])
        canvas.setLineWidth(0.4)
        canvas.line(lm, bm - 4 * mm, w - rm, bm - 4 * mm)
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(C["grey"])
        canvas.drawString(lm, bm - 7 * mm,
                          f"FinSight IA  -  {company_name} ({ticker})  -  Usage confidentiel")
        canvas.drawRightString(w - rm, bm - 7 * mm,
                               f"{doc.page} / {total_pages[0]}")
        canvas.restoreState()
    return _cb


# ---------------------------------------------------------------------------
# PAGE 1 -- Page de garde
# ---------------------------------------------------------------------------

def _page_cover(ticker, company_name, sector, exchange, gen_date):
    from reportlab.platypus import PageBreak
    from reportlab.platypus.flowables import Flowable
    from reportlab.lib import colors as C
    from reportlab.lib.units import mm

    class Cover(Flowable):
        def wrap(self, w, h):
            self._w, self._h = w, h
            return w, h

        def draw(self):
            cv = self.canv
            W, H = self._w, self._h
            band_h = H * 0.42

            # Bande navy pleine largeur
            cv.setFillColor(C.HexColor("#1B3A6B"))
            cv.rect(0, H - band_h, W, band_h, fill=1, stroke=0)

            # "FinSight IA" discret
            cv.setFont("Helvetica", 7.5)
            cv.setFillColor(C.HexColor("#7B9ACB"))
            cv.drawString(0, H - 14 * mm, "FinSight IA")

            # Nom societe
            # Truncate if too long
            name = company_name
            cv.setFont("Helvetica-Bold", 22)
            cv.setFillColor(C.white)
            cv.drawString(0, H - 30 * mm, name)

            # "Rapport d'analyse"
            cv.setFont("Helvetica", 11)
            cv.setFillColor(C.HexColor("#AABBCC"))
            cv.drawString(0, H - 40 * mm, "Rapport d'analyse")

            # ticker . bourse . secteur
            cv.setFont("Helvetica", 9)
            cv.setFillColor(C.HexColor("#AABBCC"))
            parts = "  .  ".join(p for p in [ticker, exchange, sector] if p)
            cv.drawString(0, H - 50 * mm, parts)

            # Date + confidentiel en bas de bande
            cv.setFont("Helvetica", 7)
            cv.setFillColor(C.HexColor("#7B9ACB"))
            cv.drawString(0, H - band_h + 8 * mm, gen_date)
            cv.drawRightString(W, H - band_h + 8 * mm, "Rapport confidentiel")

    return [Cover(), PageBreak()]


# ---------------------------------------------------------------------------
# PAGE 2 -- Sommaire
# ---------------------------------------------------------------------------

def _page_sommaire(st):
    from reportlab.platypus import Paragraph, Spacer, Table, PageBreak

    elems = [
        Paragraph("SOMMAIRE", st["section"]),
        Spacer(1, 6),
        Paragraph(
            "Ce rapport presente une analyse financiere complete produite par FinSight IA. "
            "Les sections couvrent la synthese d'investissement, l'analyse des etats financiers, "
            "la valorisation multi-methodes ainsi que les risques et le sentiment de marche. "
            "Toutes les donnees sont issues de sources publiques.",
            st["body"]),
        Spacer(1, 10),
    ]
    rows = [
        ["", "Section", "Page"],
        ["1", "Synthese Executive & Recommandation", "3"],
        ["2", "Analyse Financiere", "3"],
        ["3", "Valorisation", "4"],
        ["4", "Risques & Sentiment de Marche", "5"],
    ]
    cw = [12 * _mm, 135 * _mm, 23 * _mm]
    _assert_tw(cw)
    t = Table(rows, colWidths=cw)
    t.setStyle(_ts(first_col_navy=False))
    elems += [t, Spacer(1, 8), PageBreak()]
    return elems


# ---------------------------------------------------------------------------
# PAGE 3 -- Synthese + Analyse financiere
# ---------------------------------------------------------------------------

def _page_synthese_et_financiere(snap, ratios, synthesis, st):
    from reportlab.platypus import Paragraph, Spacer, Table, PageBreak
    from reportlab.platypus.flowables import Flowable
    from reportlab.lib import colors as C
    from reportlab.lib.units import mm

    ci    = snap.company_info
    mkt   = snap.market
    cur   = ci.currency or "USD"
    units = ci.units or "M"
    price = mkt.share_price

    rec   = (_g(synthesis, "recommendation") or "N/A").upper()
    conv  = _g(synthesis, "conviction")
    conf  = _g(synthesis, "confidence_score")
    tbase = _g(synthesis, "target_base")
    tbear = _g(synthesis, "target_bear")
    tbull = _g(synthesis, "target_bull")
    summary    = _g(synthesis, "summary") or ""
    strengths  = _g(synthesis, "strengths") or []
    risks_list = _g(synthesis, "risks") or []
    val_comment = _g(synthesis, "valuation_comment") or ""

    conv_s  = f"{float(conv) * 100:.0f} %" if conv is not None else "N/A"
    conf_s  = f"{float(conf) * 100:.0f} %" if conf is not None else "N/A"
    up_s    = _upside(tbase, price)
    tbase_s = f"{float(tbase):.0f} $" if tbase else "N/A"
    price_s = f"{float(price):.2f} $" if price else "N/A"

    # ------------------------------------------------------------------
    # Bloc header societe + verdict (2 lignes, table pleine largeur)
    # ------------------------------------------------------------------
    exchange = getattr(ci, "exchange", "") or ""
    sector   = ci.sector or ""
    gen_date = ci.analysis_date or date.today().strftime("%d %B %Y")

    header_line  = "  -  ".join(p for p in [ci.company_name, ci.ticker, exchange, sector, gen_date] if p)
    verdict_line = (f"l {rec}  Cours : {price_s}  -  Cible base : {tbase_s}"
                    f"  -  Upside : {up_s}  -  Conviction : {conv_s}  -  Confiance IA : {conf_s}")

    from reportlab.platypus import TableStyle as TS
    rec_col = _rec_color(rec)
    C_ = _C()

    hdr_data = [[header_line], [verdict_line]]
    hdr_cw   = [_TW]
    _assert_tw(hdr_cw)
    hdr_t = Table(hdr_data, colWidths=hdr_cw)
    hdr_t.setStyle(TS([
        ("BACKGROUND",    (0, 0), (-1, 0), C_["navy"]),
        ("TEXTCOLOR",     (0, 0), (-1, 0), C_["white"]),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 8),
        ("BACKGROUND",    (0, 1), (-1, 1), rec_col),
        ("TEXTCOLOR",     (0, 1), (-1, 1), C_["white"]),
        ("FONTNAME",      (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 1), (-1, 1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))

    elems = [hdr_t, Spacer(1, 6)]

    # Description societe
    if summary:
        elems.append(Paragraph(summary, st["body"]))
        elems.append(Spacer(1, 6))

    # Scenarios de valorisation
    elems.append(Paragraph("Scenarios de valorisation", st["subsec"]))

    def _hyp(scenario):
        if scenario == "Bear" and risks_list:
            s = risks_list[0]
        elif scenario == "Bull" and strengths:
            s = strengths[0]
        elif strengths:
            s = strengths[1] if len(strengths) > 1 else strengths[0]
        else:
            return "--"
        return (s[:70] + "...") if len(s) > 70 else s

    sc_data = [
        ["",                    "Bear",                              "Base",                              "Bull"],
        ["Prix cible (" + cur + ")",
         _v(tbear, "{:.0f}"),   _v(tbase, "{:.0f}"),   _v(tbull, "{:.0f}")],
        ["Upside / Downside",   _upside(tbear, price), _upside(tbase, price), _upside(tbull, price)],
        ["Probabilite estimee", "25 %",                "50 %",                "25 %"],
        ["Hypothese determinante", _hyp("Bear"),       _hyp("Base"),          _hyp("Bull")],
    ]
    cw_sc = [42 * _mm, 43 * _mm, 43 * _mm, 42 * _mm]
    _assert_tw(cw_sc)
    t_sc = Table(sc_data, colWidths=cw_sc)
    t_sc.setStyle(_ts(first_col_navy=True))
    elems += [t_sc, Spacer(1, 8)]

    # These d'investissement
    if val_comment:
        elems.append(Paragraph(val_comment, st["body"]))
        elems.append(Spacer(1, 8))

    # ------------------------------------------------------------------
    # 2. ANALYSE FINANCIERE
    # ------------------------------------------------------------------
    elems.append(Paragraph("2. ANALYSE FINANCIERE", st["section"]))
    elems.append(Spacer(1, 4))

    hist_labels = sorted(snap.years.keys(), key=lambda y: str(y).replace("_LTM", ""))
    # Garde max 3 annees historiques
    hist_3 = hist_labels[-3:] if len(hist_labels) >= 3 else hist_labels
    # Derniere annee labellee "YYYY LTM"
    col_names = []
    for i, l in enumerate(hist_3):
        base = str(l).replace("_LTM", "")
        if i == len(hist_3) - 1:
            col_names.append(base + " LTM")
        else:
            col_names.append(base)
    # Colonnes projections
    next_yr  = str(int(str(hist_3[-1]).replace("_LTM", "")) + 1) if hist_3 else "2025"
    next_yr2 = str(int(next_yr) + 1)
    col_names += [next_yr + "F", next_yr2 + "F"]
    all_labels = hist_3 + [next_yr + "F", next_yr2 + "F"]

    def _fy(lbl):
        return snap.years.get(lbl)

    def _ry(lbl):
        return ratios.years.get(lbl) if ratios else None

    elems.append(Paragraph(
        f"Compte de resultat consolide ({cur} {units})", st["subsec"]))

    is_hdr  = ["Indicateur"] + col_names
    is_rows = [is_hdr]

    # Revenue
    rev_row = ["Chiffre d'affaires"]
    for l in all_labels:
        fy = _fy(l)
        rev_row.append(_m(fy.revenue if fy else None))
    is_rows.append(rev_row)

    # Croissance YoY
    grow_row = ["Croissance YoY"]
    prev = None
    for l in all_labels:
        fy = _fy(l)
        rev = fy.revenue if fy else None
        if prev and rev and prev != 0:
            grow_row.append(f"{(rev - prev) / abs(prev) * 100:+.1f} %")
        else:
            grow_row.append("--")
        prev = rev
    is_rows.append(grow_row)

    # Marge brute
    gm_row = ["Marge brute"]
    for l in all_labels:
        yr = _ry(l)
        gm_row.append(_pct(yr.gross_margin if yr else None))
    is_rows.append(gm_row)

    # EBITDA
    ebitda_row = ["EBITDA"]
    for l in all_labels:
        yr = _ry(l)
        ebitda_row.append(_m(yr.ebitda if yr else None))
    is_rows.append(ebitda_row)

    # Marge EBITDA
    em_row = ["Marge EBITDA"]
    for l in all_labels:
        yr = _ry(l)
        em_row.append(_pct(yr.ebitda_margin if yr else None))
    is_rows.append(em_row)

    # Resultat net
    ni_row = ["Resultat net"]
    for l in all_labels:
        yr = _ry(l)
        ni_row.append(_m(yr.net_income if yr else None))
    is_rows.append(ni_row)

    # Marge nette
    nm_row = ["Marge nette"]
    for l in all_labels:
        yr = _ry(l)
        nm_row.append(_pct(yr.net_margin if yr else None))
    is_rows.append(nm_row)

    n_data  = len(all_labels)
    first_w = 38 * _mm
    rest_w  = (_TW - first_w) / n_data
    cw_is   = [first_w] + [rest_w] * n_data
    _assert_tw(cw_is)

    # Derniere colonne historique surlignee bleu pale
    last_hist_col = len(hist_3)  # 1-indexed position of last hist col
    extra_is = [
        ("BACKGROUND", (last_hist_col, 1), (last_hist_col, -1), C.HexColor("#EEF2F8")),
        ("FONTNAME",   (last_hist_col, 0), (last_hist_col,  0), "Helvetica-Bold"),
    ]
    t_is = Table(is_rows, colWidths=cw_is)
    t_is.setStyle(_ts(extra=extra_is, first_col_navy=True))
    elems += [t_is, Spacer(1, 4)]

    # Commentaire IS -- depuis synthesis.summary ou genere
    fin_comment = (_g(synthesis, "summary") or "")
    if fin_comment:
        elems.append(Paragraph(fin_comment[:450], st["italic"]))

    elems.append(PageBreak())
    return elems


# ---------------------------------------------------------------------------
# PAGE 4 -- Ratios + Valorisation
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


def _lecture(val, bm_str, pct_mode=False):
    try:
        v = float(val) * (100 if pct_mode else 1)
        parts = bm_str.replace("x", "").replace("%", "").replace(" ", "").split("-")
        lo, hi = float(parts[0]), float(parts[1])
        if not pct_mode and v > hi * 1.4:
            return "Prime technologique"
        if v > hi:
            return "Superieure" if pct_mode else "Superieur"
        if v < lo:
            return "Inferieure" if pct_mode else "Decote"
        return "En ligne" if pct_mode else "Dans la norme"
    except Exception:
        return "--"


def _page_ratios_et_valorisation(snap, ratios, synthesis, st):
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

    def _ry(lbl):
        return ratios.years.get(lbl) if ratios else None

    yr = _ry(latest_l) if latest_l else None

    def _a(attr):
        return getattr(yr, attr, None) if yr else None

    bm      = _benchmarks(ci.sector or "")
    pe      = _a("pe_ratio")
    ev_e    = _a("ev_ebitda")
    ev_r    = _a("ev_revenue")
    gm      = _a("gross_margin")
    em      = _a("ebitda_margin")
    roe     = _a("roe")
    az      = _a("altman_z")
    bm_sc   = _a("beneish_m")

    az_lbl  = ("Solide"    if az   and float(az)   > 2.99 else
               "Zone grise" if az  and float(az)   > 1.81 else
               "Detresse"   if az  else "--")
    bm_lbl  = "Aucun signal" if bm_sc and float(bm_sc) < -2.22 else ("Risque manip." if bm_sc else "--")

    # ------------------------------------------------------------------
    # Ratios table (exactement comme reference: 9 lignes, 4 colonnes)
    # ------------------------------------------------------------------
    elems = []
    elems.append(Paragraph(
        "Positionnement relatif  -  Ratios cles vs. pairs sectoriels",
        st["subsec"]))

    rdata = [["Indicateur", f"{ci.ticker} LTM", "Reference sectorielle", "Lecture"]]
    rdata += [
        ["P/E (x)",          "n.m." if pe  and float(pe)  > 999 else _x(pe),   bm["pe"],       _lecture(pe,    bm["pe"])],
        ["EV / EBITDA (x)",  "n.m." if ev_e and float(ev_e) > 999 else _x(ev_e), bm["ev_ebitda"], _lecture(ev_e,  bm["ev_ebitda"])],
        ["EV / Revenue (x)", _x(ev_r),    bm["ev_rev"],    _lecture(ev_r,  bm["ev_rev"])],
        ["Marge brute",      _pct(gm),    bm["gross_m"],   _lecture(gm,    bm["gross_m"],  pct_mode=True)],
        ["Marge EBITDA",     _pct(em),    bm["ebitda_m"],  _lecture(em,    bm["ebitda_m"], pct_mode=True)],
        ["Return on Equity", _pct(roe),   bm["roe"],       _lecture(roe,   bm["roe"],      pct_mode=True)],
        ["Altman Z-Score",   _v(az,  "{:.1f}"),  "> 2.99 = sain",  az_lbl],
        ["Beneish M-Score",  _v(bm_sc, "{:.2f}"), "< -2.22 = OK", bm_lbl],
    ]
    cw_r = [50 * _mm, 32 * _mm, 55 * _mm, 33 * _mm]
    _assert_tw(cw_r)

    # Code couleur signal sur colonne Lecture
    extra_r = []
    signal_rows = {
        1: pe,   2: ev_e,  3: ev_r,
        4: gm,   5: em,    6: roe,
        7: az,   8: bm_sc,
    }
    for row_idx, val in signal_rows.items():
        lbl = rdata[row_idx][3]
        if lbl in ("Prime technologique", "Superieur", "Superieure", "En ligne", "Solide", "Aucun signal"):
            color = C.HexColor("#1A7A4A")
        elif lbl in ("Decote", "Inferieure", "Detresse", "Risque manip."):
            color = C.HexColor("#A82020")
        else:
            color = C.HexColor("#B06000")
        extra_r.append(("TEXTCOLOR", (3, row_idx), (3, row_idx), color))
        extra_r.append(("FONTNAME",  (3, row_idx), (3, row_idx), "Helvetica-Bold"))

    t_r = Table(rdata, colWidths=cw_r)
    t_r.setStyle(_ts(extra=extra_r, first_col_navy=True))
    elems += [t_r, Spacer(1, 4)]

    val_comment = _g(synthesis, "valuation_comment") or ""
    if val_comment:
        elems.append(Paragraph(val_comment, st["italic"]))
    elems.append(Spacer(1, 8))

    # ------------------------------------------------------------------
    # 3. VALORISATION
    # ------------------------------------------------------------------
    elems.append(Paragraph("3. VALORISATION", st["section"]))
    elems.append(Spacer(1, 4))

    beta  = mkt.beta_levered
    rfr   = mkt.risk_free_rate
    erp   = mkt.erp

    elems.append(Paragraph(
        f"Discounted Cash Flow  -  Scenario base  -  WACC {wacc * 100:.1f} %"
        f"  -  Taux terminal {tgr * 100:.1f} %  -  Horizon 5 ans",
        st["subsec"]))

    # DCF commentary
    ke_str   = f"{(rfr or 0.041) * 100 + (erp or 0.055) * (beta or 1.0) * 100:.1f} %" if beta else "N/A"
    kd_str   = f"{((mkt.cost_of_debt_pretax or 0.04) * (1 - (mkt.tax_rate or 0.25))) * 100:.1f} %"
    beta_str = f"{float(beta):.2f}" if beta else "N/A"
    rfr_str  = f"{float(rfr) * 100:.1f} %" if rfr else "N/A"
    erp_str  = f"{float(erp) * 100:.1f} %" if erp else "N/A"

    dcf_para = (
        f"Le modele DCF est calibre sur un horizon de cinq ans, avec un WACC de {wacc * 100:.1f} % "
        f"decompose en un cout des fonds propres de {ke_str} "
        f"(Beta {beta_str}  -  RFR {rfr_str}  -  prime de risque marche {erp_str}) "
        f"et un cout de la dette apres impot de {kd_str}. "
        f"La valeur intrinseque ressort a {_v(tbase, '{:.0f}')} {cur} par action dans le scenario base, "
        f"soit un upside de {_upside(tbase, price)} par rapport au cours actuel. "
        f"Les deux variables les plus sensibles sont le taux de croissance du chiffre "
        f"d'affaires en annees 3-5 et la marge EBITDA terminale."
    )
    elems.append(Paragraph(dcf_para, st["body"]))
    elems.append(Spacer(1, 6))

    # Table de sensibilite 5x5
    elems.append(Paragraph(
        f"Table de sensibilite  -  Valeur intrinseque par action ({cur})",
        st["subsec"]))

    waccs = [wacc - 0.01*2, wacc - 0.01, wacc, wacc + 0.01, wacc + 0.01*2]
    tgrs  = [tgr - 0.005*2, tgr - 0.005, tgr, tgr + 0.005, tgr + 0.005*2]
    base_v     = float(tbase) if tbase else (float(price) if price else 100.0)
    denom_base = wacc - tgr

    def _dcf(w, t):
        d = w - t
        if abs(d) < 1e-4 or abs(denom_base) < 1e-4:
            return "--"
        return f"{base_v * denom_base / d:.0f}"

    tgr_hdrs  = [f"{t * 100:.1f} %" for t in tgrs]
    wacc_hdrs = [f"{w * 100:.1f} %" for w in waccs]
    sens = [["WACC  /  TGR"] + tgr_hdrs]
    for i, w in enumerate(waccs):
        sens.append([wacc_hdrs[i]] + [_dcf(w, t) for t in tgrs])

    cw_s = [28 * _mm, 28.4 * _mm, 28.4 * _mm, 28.4 * _mm, 28.4 * _mm, 28.4 * _mm]
    _assert_tw(cw_s)

    extra_s = [
        ("BACKGROUND", (3, 3), (3, 3), C_["navy"]),
        ("TEXTCOLOR",  (3, 3), (3, 3), C_["white"]),
        ("FONTNAME",   (3, 3), (3, 3), "Helvetica-Bold"),
    ]
    t_s = Table(sens, colWidths=cw_s)
    t_s.setStyle(_ts(extra=extra_s, first_col_navy=True))
    elems += [t_s, Spacer(1, 3)]
    elems.append(Paragraph(
        "Ligne et colonne surlignees correspondent au scenario base. "
        "La cellule d'intersection materialise la valeur centrale du modele.",
        st["small"]))
    elems.append(Spacer(1, 8))

    # Comparables peers
    elems.append(Paragraph(
        "Analyse par multiples comparables  -  Pairs sectoriels LTM",
        st["subsec"]))

    peers   = _g(synthesis, "comparable_peers")
    p_hdr   = ["Societe", "EV/EBITDA", "EV/Revenue", "P/E", "Marge brute", "Marge\nEBITDA"]
    cw_p    = [44 * _mm, 26 * _mm, 26 * _mm, 22 * _mm, 26 * _mm, 26 * _mm]
    _assert_tw(cw_p)

    pdata = [p_hdr, [
        f"{ci.ticker} (cible)",
        _x(ev_e), _x(ev_r), _x(pe), _pct(gm), _pct(em),
    ]]

    if peers:
        for p in peers[:5]:
            pdata.append([
                _g(p, "name") or _g(p, "ticker") or "--",
                _x(_g(p, "ev_ebitda")),  _x(_g(p, "ev_revenue")),
                _x(_g(p, "pe")),
                _pct(_g(p, "gross_margin")), _pct(_g(p, "ebitda_margin")),
            ])

        def _med(attr, items, is_pct=False):
            vals = []
            for p in items:
                try:
                    v = float(_g(p, attr) or "nan")
                    if abs(v) < (10 if is_pct else 999):
                        vals.append(v)
                except Exception:
                    pass
            if not vals:
                return "--"
            vals.sort()
            v = vals[len(vals) // 2]
            return f"{v * 100:.1f} %" if is_pct else f"{v:.1f}x"

        pdata.append([
            "Mediane peers",
            _med("ev_ebitda", peers[:5]),   _med("ev_revenue", peers[:5]),
            _med("pe", peers[:5]),
            _med("gross_margin", peers[:5], is_pct=True),
            _med("ebitda_margin", peers[:5], is_pct=True),
        ])
    else:
        pdata.append(["Donnees comparables non disponibles", "--", "--", "--", "--", "--"])

    extra_p = [
        ("FONTNAME",   (0,  1), (-1,  1), "Helvetica-Bold"),
        ("FONTNAME",   (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), C.HexColor("#EEF2F8")),
    ]
    t_p = Table(pdata, colWidths=cw_p)
    t_p.setStyle(_ts(extra=extra_p, first_col_navy=True))
    elems += [t_p, Spacer(1, 5)]

    # Commentaire peers
    med_ev = None
    if peers:
        try:
            vals = [float(_g(p, "ev_ebitda")) for p in peers[:5] if _g(p, "ev_ebitda")]
            vals = [v for v in vals if 0 < v < 999]
            if vals:
                vals.sort()
                med_ev = vals[len(vals) // 2]
        except Exception:
            pass

    peers_comment = ""
    if med_ev and ev_e:
        try:
            impl = float(price) * med_ev / float(ev_e) if ev_e and price else None
            prime = (float(ev_e) / med_ev - 1) * 100 if ev_e else 0
            peers_comment = (
                f"La mediane des pairs sur l'EV/EBITDA ressort a {med_ev:.1f}x, "
                f"contre {_x(ev_e)} pour {ci.ticker}, confirmant une prime de {prime:.0f} % "
                f"que le marche justifie par le potentiel strategique. "
                f"En appliquant la mediane sectorielle, la valeur implicite ressortirait a "
                f"environ {_v(impl, '{:.0f}')} {cur}."
            )
        except Exception:
            pass

    if peers_comment:
        elems.append(Paragraph(peers_comment, st["italic"]))

    elems.append(PageBreak())
    return elems


# ---------------------------------------------------------------------------
# PAGE 5 -- Football field + Risques + Sentiment header
# ---------------------------------------------------------------------------

def _page_ff_risques_sentiment(snap, ratios, synthesis, devil, sentiment, st):
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
    yr = ratios.years.get(latest_l) if ratios and latest_l else None

    # ------------------------------------------------------------------
    # Football field table
    # ------------------------------------------------------------------
    ff_src  = _g(synthesis, "football_field")
    ff_rows = []
    if ff_src:
        for m in ff_src:
            ff_rows.append({
                "label": _g(m, "label") or _g(m, "method") or "--",
                "low":   _g(m, "range_low") or _g(m, "low"),
                "high":  _g(m, "range_high") or _g(m, "high"),
                "mid":   _g(m, "midpoint") or _g(m, "mid"),
            })
    else:
        if tbear:
            lo, hi = float(tbear) * 0.90, float(tbear) * 1.05
            ff_rows.append({"label": "DCF  -  Bear", "low": lo, "high": hi, "mid": tbear})
        if tbase:
            lo, hi = float(tbase) * 0.94, float(tbase) * 1.06
            ff_rows.append({"label": "DCF  -  Base", "low": lo, "high": hi, "mid": tbase})
        if tbull:
            lo, hi = float(tbull) * 0.92, float(tbull) * 1.10
            ff_rows.append({"label": "DCF  -  Bull", "low": lo, "high": hi, "mid": tbull})
        # EV/EBITDA mediane peers
        if yr and yr.ev_ebitda and price:
            bm = _benchmarks(ci.sector or "")
            try:
                parts = bm["ev_ebitda"].replace("x", "").replace(" ", "").split("-")
                med = (float(parts[0]) + float(parts[1])) / 2
                impl = float(price) * med / float(yr.ev_ebitda)
                ff_rows.append({
                    "label": "EV/EBITDA  -  Mediane peers",
                    "low": impl * 0.90, "high": impl * 1.10, "mid": impl
                })
                impl2 = impl * 1.5
                ff_rows.append({
                    "label": "EV/EBITDA  -  Prime tech +50 %",
                    "low": impl2 * 0.90, "high": impl2 * 1.10, "mid": impl2
                })
            except Exception:
                pass
        # EV/Revenue mediane peers
        if yr and yr.ev_revenue and price:
            bm = _benchmarks(ci.sector or "")
            try:
                parts = bm["ev_rev"].replace("x", "").replace(" ", "").split("-")
                med = (float(parts[0]) + float(parts[1])) / 2
                impl = float(price) * med / float(yr.ev_revenue)
                ff_rows.append({
                    "label": "EV/Revenue  -  Mediane peers",
                    "low": impl * 0.90, "high": impl * 1.10, "mid": impl
                })
            except Exception:
                pass

    ff_hdr  = [
        "Methode",
        f"Fourchette basse ({cur})",
        f"Fourchette haute ({cur})",
        f"Point central ({cur})"
    ]
    cw_ff = [72 * _mm, 33 * _mm, 33 * _mm, 32 * _mm]
    _assert_tw(cw_ff)

    ff_tdata = [ff_hdr]
    for r in ff_rows:
        ff_tdata.append([
            r["label"],
            _v(r["low"],  "{:.0f}"),
            _v(r["high"], "{:.0f}"),
            _v(r["mid"],  "{:.0f}"),
        ])
    if price:
        today_str = date.today().strftime("%d/%m/%Y")
        ff_tdata.append([f"Cours actuel ({today_str})", "--", "--", f"{float(price):.2f} {cur}"])

    t_ff = Table(ff_tdata, colWidths=cw_ff)
    t_ff.setStyle(_ts(first_col_navy=True))
    elems = [t_ff, Spacer(1, 5)]

    # Commentaire football field
    if tbase and price:
        ff_comment = (
            f"Le scenario DCF base ({_v(tbase, '{:.0f}')} {cur}) et le cours actuel "
            f"({_v(price, '{:.2f}')} {cur}) sont coherents avec une valorisation mixte "
            f"DCF / multiples ajustes. L'application stricte des multiples medians pairs "
            f"illustre l'ampleur de la prime integree, et le risque de correction si les "
            f"hypotheses structurelles ne se materialisent pas dans les delais anticipes."
        )
        elems.append(Paragraph(ff_comment, st["italic"]))
    elems.append(Spacer(1, 8))

    # ------------------------------------------------------------------
    # 4. ANALYSE DES RISQUES
    # ------------------------------------------------------------------
    elems.append(Paragraph("4. ANALYSE DES RISQUES", st["section"]))
    elems.append(Spacer(1, 4))
    elems.append(Paragraph(
        "These contraire  -  Arguments en faveur d'une revision a la baisse",
        st["subsec"]))

    counter_risks = _g(devil, "counter_risks") or []
    counter_thesis = _g(devil, "counter_thesis") or ""
    risks_synth    = _g(synthesis, "risks") or []

    # 3 paragraphes avocat du diable (titre gras + corps)
    paragraphs = []
    if counter_risks and counter_thesis:
        # Distribuer le texte en 3 sections
        parts = counter_thesis.split(". ")
        chunk = max(1, len(parts) // 3)
        for i, title in enumerate(counter_risks[:3]):
            body = ". ".join(parts[i * chunk:(i + 1) * chunk]).strip()
            if not body.endswith("."):
                body += "."
            paragraphs.append((title, body))
    elif counter_thesis:
        sentences = [s.strip() for s in counter_thesis.split(". ") if s.strip()]
        chunk = max(1, len(sentences) // 3)
        for i in range(3):
            body = ". ".join(sentences[i * chunk:(i + 1) * chunk]).strip()
            if body and not body.endswith("."):
                body += "."
            title = f"Risque {i + 1}"
            paragraphs.append((title, body or "--"))
    elif risks_synth:
        for r in risks_synth[:3]:
            paragraphs.append(("", r))
    else:
        paragraphs = [("Analyse contradictoire non disponible.", "")]

    for title, body in paragraphs:
        if title:
            elems.append(Paragraph(title + ("." if not title.endswith(".") else ""), st["devil_t"]))
        if body:
            elems.append(Paragraph(body, st["body"]))
        elems.append(Spacer(1, 4))

    # Conditions d'invalidation
    elems.append(Paragraph("Conditions d'invalidation de la these", st["subsec"]))

    inv_str  = _g(synthesis, "invalidation_conditions") or ""
    inv_list = _g(synthesis, "invalidation_list")

    cdata = [["Axe", "Condition d'invalidation", "Horizon"]]
    if inv_list:
        for c in inv_list[:3]:
            cdata.append([_g(c, "axis") or "--", _g(c, "condition") or "--", _g(c, "horizon") or "--"])
    else:
        if inv_str:
            cdata.append(["Synthese IA", inv_str[:120] + ("..." if len(inv_str) > 120 else ""), "Court-moyen terme"])
        if len(cdata) < 4:
            cdata += [
                ["Macro",     "Taux souverains 10 ans > 5,5 % sur deux trimestres consecutifs", "6-12 mois"],
                ["Sectoriel", "Perte de part de marche significative vs. principaux pairs",      "12-18 mois"],
                ["Societe",   "Marge brute sous plancher historique sur deux trimestres",         "2-3 trim."],
            ]
            cdata = cdata[:4]  # header + 3 rows

    cw_c = [28 * _mm, 110 * _mm, 32 * _mm]
    _assert_tw(cw_c)
    t_c = Table(cdata, colWidths=cw_c)
    t_c.setStyle(_ts(first_col_navy=True))
    elems += [t_c, Spacer(1, 10)]

    # ------------------------------------------------------------------
    # 5. SENTIMENT DE MARCHE (intro + header de table)
    # ------------------------------------------------------------------
    elems.append(Paragraph("5. SENTIMENT DE MARCHE", st["section"]))
    elems.append(Spacer(1, 4))

    if not sentiment:
        elems.append(Paragraph("Donnees de sentiment non disponibles.", st["body"]))
    else:
        label     = (_g(sentiment, "label") or "NEUTRAL").lower()
        score     = float(_g(sentiment, "score") or 0.0)
        n_art     = int(_g(sentiment, "articles_analyzed") or 0)
        conf      = float(_g(sentiment, "confidence") or 0.0)
        breakdown = _g(sentiment, "breakdown") or {}
        samples   = _g(sentiment, "samples") or []
        engine    = (_g(sentiment, "meta", "engine") or "VADER").upper()
        rec       = (_g(synthesis, "recommendation") or "").upper()

        avg_pos = breakdown.get("avg_positive", 0)
        avg_neu = breakdown.get("avg_neutral",  0)
        avg_neg = breakdown.get("avg_negative", 0)

        def _themes(orient):
            ts = []
            for s in samples:
                lbl = (s.get("label") or "").upper()
                if ((orient == "pos" and lbl == "POSITIVE") or
                        (orient == "neg" and lbl == "NEGATIVE") or
                        (orient == "neu" and lbl == "NEUTRAL")):
                    h = s.get("headline", "")[:40]
                    if h:
                        ts.append(h)
            return ", ".join(ts[:3]) or "--"

        direction = "positive moderee" if score > 0.05 else ("negative moderee" if score < -0.05 else "neutre")
        pos_themes = _themes("pos") or "annonces de livraisons, perspectives sectorielles"
        neg_themes = _themes("neg") or "incertitudes macro, concurrence"
        rec_comment = (f"Ce sentiment est coherent avec la recommandation {rec} fondee sur les "
                       f"fondamentaux -- il confirme l'absence de newsflow structurellement "
                       f"defavorable a court terme." if rec else "")

        sent_intro = (
            f"L'analyse semantique {engine} conduite sur un corpus de {n_art} articles "
            f"publie{'s' if n_art > 1 else ''} au cours des sept derniers jours fait "
            f"ressortir un sentiment globalement {label} avec une inflexion {direction} "
            f"(score agrege : {score:+.3f}). "
            f"Les publications favorables sont portees par {pos_themes}. "
            f"Les publications defavorables se concentrent sur {neg_themes}. "
            + rec_comment
        )
        elems.append(Paragraph(sent_intro, st["body"]))
        elems.append(Spacer(1, 6))

        # Header de table (les lignes de donnees continuent sur page 6)
        sent_hdr = [["Orientation", "Articles", "Score moyen", "Themes principaux"]]
        cw_sent  = [28 * _mm, 18 * _mm, 24 * _mm, 100 * _mm]
        _assert_tw(cw_sent)

        n_pos = round(avg_pos * n_art) if n_art else 0
        n_neu = round(avg_neu * n_art) if n_art else 0
        n_neg = round(avg_neg * n_art) if n_art else 0

        sent_rows = sent_hdr + [
            ["Positif", str(n_pos), f"{avg_pos:+.2f}", _themes("pos")],
            ["Neutre",  str(n_neu), f"{avg_neu:+.2f}", _themes("neu")],
            ["Negatif", str(n_neg), f"{-avg_neg:+.2f}", _themes("neg")],
        ]
        t_sent = Table(sent_rows, colWidths=cw_sent)
        t_sent.setStyle(_ts(first_col_navy=False, alt_rows=True))
        elems.append(t_sent)

    elems.append(PageBreak())
    return elems


# ---------------------------------------------------------------------------
# PAGE 6 -- Disclaimer
# ---------------------------------------------------------------------------

def _page_disclaimer(snap, st):
    from reportlab.platypus import Paragraph, Spacer, HRFlowable
    from reportlab.lib import colors as C

    C_  = _C()
    ci  = snap.company_info
    gen_date = ci.analysis_date or date.today().strftime("%d %B %Y")

    elems = [
        Spacer(1, 12),
        HRFlowable(width=_TW, thickness=0.5, color=C_["navy"]),
        Spacer(1, 5),
        Paragraph("Avertissement legal", st["bold"]),
        Paragraph(
            f"Ce rapport a ete genere par FinSight IA v1.0 le {gen_date}. "
            "Il est produit integralement par un systeme d'intelligence artificielle "
            "et ne constitue pas un conseil en investissement au sens de la directive "
            "europeenne MiFID II (2014/65/UE). FinSight IA ne saurait etre tenu "
            "responsable des decisions prises sur la base de ce document. "
            "Les donnees financieres sont issues de sources publiques (yfinance, "
            "Finnhub Financial, Financial Modeling Prep) et peuvent contenir des "
            "inexactitudes. Tout investisseur est invite a proceder a sa propre "
            "diligence et a consulter un professionnel qualifie avant toute decision. "
            "Document confidentiel -- diffusion restreinte.",
            st["small"]),
    ]
    return elems


# ---------------------------------------------------------------------------
# PDFWriter -- classe publique
# ---------------------------------------------------------------------------

class PDFWriter:
    """
    Generateur de rapport PDF FinSight IA — 6 pages.

    Usage :
        writer = PDFWriter()
        path   = writer.generate(state, "outputs/generated/report.pdf")
    """

    def generate(self, state: dict, output_path: str) -> str:
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
            raise ValueError("PDFWriter: state['raw_data'] requis")

        ci       = snap.company_info
        ticker   = ci.ticker or state.get("ticker", "UNKNOWN")
        co_name  = ci.company_name or ticker
        sector   = ci.sector or ""
        exchange = getattr(ci, "exchange", "") or ""
        gen_date = ci.analysis_date or date.today().strftime("%d %B %Y")

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        st           = _styles()
        total_pages  = [6]

        def _cb(canvas, doc):
            _footer_cb(co_name, ticker, total_pages)(canvas, doc)

        doc = SimpleDocTemplate(
            str(out),
            pagesize=A4,
            leftMargin=18 * mm, rightMargin=18 * mm,
            topMargin=16 * mm,  bottomMargin=20 * mm,
            title=f"FinSight IA -- {co_name} ({ticker})",
            author="FinSight IA v1.0",
        )

        story = []
        story += _page_cover(ticker, co_name, sector, exchange, gen_date)
        story += _page_sommaire(st)
        story += _page_synthese_et_financiere(snap, ratios, synthesis, st)
        story += _page_ratios_et_valorisation(snap, ratios, synthesis, st)
        story += _page_ff_risques_sentiment(snap, ratios, synthesis, devil, sentiment, st)
        story += _page_disclaimer(snap, st)

        doc.build(story, onFirstPage=_cb, onLaterPages=_cb)
        log.info(f"[PDFWriter] {ticker} -> {out.name}")
        return str(out)
