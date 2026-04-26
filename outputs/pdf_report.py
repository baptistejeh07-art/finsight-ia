# =============================================================================
# FinSight IA — Rapport PDF Professionnel v3
# outputs/pdf_report.py
#
# Template rigide 9 sections — ReportLab Platypus
# Palette : Helvetica | Navy #1B3A6B | Fond tableau #F5F5F5
# =============================================================================

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_OUTPUT_DIR = Path(__file__).parent / "generated"

# ---------------------------------------------------------------------------
# Helpers formatage
# ---------------------------------------------------------------------------

def _v(val, fmt="{:.1f}", default="N/A"):
    if val is None: return default
    try: return fmt.format(float(val))
    except Exception: return default


def _valid_hist_labels(snapshot) -> list:
    """Retourne les annees triees avec au moins une donnee reelle (exclut les annees all-None)."""
    if not (snapshot and snapshot.years):
        return []
    result = []
    for y, fy in snapshot.years.items():
        if fy is None:
            continue
        if any(getattr(fy, attr, None) is not None
               for attr in ("revenue", "cash", "da", "interest_expense")):
            result.append(y)
    return sorted(result, key=lambda y: int(y.split("_")[0]))

def _pct(val, default="N/A"):
    if val is None: return default
    try: return f"{float(val)*100:.1f}%"
    except Exception: return default

def _m(val, cur="", default="N/A"):
    if val is None: return default
    try:
        v = float(val)
        if abs(v) >= 1000: return f"{v/1000:.1f}B {cur}".strip()
        return f"{v:.0f}M {cur}".strip()
    except Exception: return default

def _x(val, default="N/A"):
    if val is None: return default
    try: return f"{float(val):.1f}x"
    except Exception: return default

def _upside(target, current, default="N/A"):
    if target is None or current is None or current == 0: return default
    try: return f"{(float(target)-float(current))/abs(float(current))*100:+.1f}%"
    except Exception: return default

# ---------------------------------------------------------------------------
# Benchmarks sectoriels
# ---------------------------------------------------------------------------

def _sector_benchmarks(sector: str) -> dict:
    s = (sector or "").lower()
    if "tech" in s or "software" in s or "semiconductor" in s:
        return dict(pe="20-35x", ev_ebitda="15-25x", ev_rev="5-12x",
                    gross_m="55-75%", ebitda_m="20-35%", roe="15-30%")
    if "health" in s or "pharma" in s or "biotech" in s:
        return dict(pe="18-30x", ev_ebitda="12-20x", ev_rev="3-8x",
                    gross_m="60-75%", ebitda_m="20-30%", roe="12-20%")
    if "financ" in s or "bank" in s or "insur" in s:
        return dict(pe="10-16x", ev_ebitda="8-12x", ev_rev="2-4x",
                    gross_m="50-65%", ebitda_m="30-45%", roe="10-18%")
    if "energy" in s or "oil" in s or "gas" in s:
        return dict(pe="10-18x", ev_ebitda="6-10x", ev_rev="1-3x",
                    gross_m="30-50%", ebitda_m="25-40%", roe="10-15%")
    if "consumer" in s or "retail" in s or "luxury" in s:
        return dict(pe="18-28x", ev_ebitda="10-18x", ev_rev="2-5x",
                    gross_m="40-60%", ebitda_m="15-25%", roe="12-22%")
    return dict(pe="15-22x", ev_ebitda="10-16x", ev_rev="2-5x",
                gross_m="35-55%", ebitda_m="15-25%", roe="10-18%")

def _signal(val, lo, hi, invert=False):
    """Retourne (couleur, label) selon seuils."""
    try:
        from reportlab.lib import colors as rl_colors
        v = float(val)
        if invert:
            ok  = v <= lo
            bad = v >= hi
        else:
            ok  = v >= hi
            bad = v <= lo
        if ok:  return rl_colors.HexColor("#1a7a52"), "OK"
        if bad: return rl_colors.HexColor("#c0392b"), "ELEVE"
        return rl_colors.HexColor("#b8922a"), "MOYEN"
    except Exception:
        from reportlab.lib import colors as rl_colors
        return rl_colors.HexColor("#666666"), "N/A"

# ---------------------------------------------------------------------------
# DCF sensitivity
# ---------------------------------------------------------------------------

def _sensitivity_table(base_price, wacc_base, tgr_base):
    """3x3 grid : WACC -1%/0/+1% x TGR -0.5%/0/+0.5%"""
    rows = []
    waccs = [wacc_base - 0.01, wacc_base, wacc_base + 0.01]
    tgrs  = [tgr_base - 0.005, tgr_base, tgr_base + 0.005]
    for w in waccs:
        row = []
        for t in tgrs:
            denom = (w - t)
            denom_base = (wacc_base - tgr_base)
            if abs(denom) > 1e-4 and abs(denom_base) > 1e-4 and base_price:
                row.append(f"{base_price * denom_base / denom:.0f}")
            else:
                row.append("N/A")
        rows.append(row)
    return waccs, tgrs, rows

# ---------------------------------------------------------------------------
# PDF styles
# ---------------------------------------------------------------------------

def _build_styles():
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors as C
    NAVY  = C.HexColor("#1B3A6B")
    WHITE = C.white
    GREY  = C.HexColor("#555555")

    return {
        "title":      ParagraphStyle("t_title",    fontName="Helvetica-Bold", fontSize=15,
                                     textColor=NAVY, spaceAfter=2),
        "subtitle":   ParagraphStyle("t_sub",      fontName="Helvetica",      fontSize=8.5,
                                     textColor=GREY, spaceAfter=10),
        "section":    ParagraphStyle("t_sec",      fontName="Helvetica-Bold", fontSize=10.5,
                                     textColor=WHITE, backColor=NAVY,
                                     spaceBefore=14, spaceAfter=6,
                                     leftIndent=4, rightIndent=4, leading=16),
        "subsection": ParagraphStyle("t_ssec",     fontName="Helvetica-Bold", fontSize=9,
                                     textColor=NAVY, spaceBefore=8, spaceAfter=4),
        "body":       ParagraphStyle("t_body",     fontName="Helvetica",      fontSize=8.5,
                                     leading=13, spaceAfter=6),
        "bullet":     ParagraphStyle("t_bullet",   fontName="Helvetica",      fontSize=8.5,
                                     leading=13, leftIndent=14, firstLineIndent=-10, spaceAfter=3),
        "small":      ParagraphStyle("t_small",    fontName="Helvetica",      fontSize=7.5,
                                     textColor=GREY, spaceAfter=4),
        "bold":       ParagraphStyle("t_bold",     fontName="Helvetica-Bold", fontSize=8.5,
                                     leading=13, spaceAfter=4),
        "toc":        ParagraphStyle("t_toc",      fontName="Helvetica",      fontSize=8.5,
                                     leading=14, leftIndent=10, spaceAfter=2),
    }

# ---------------------------------------------------------------------------
# Table styles helpers
# ---------------------------------------------------------------------------

def _ts_base(nav_rows=None):
    """TableStyle de base avec headers navy."""
    from reportlab.platypus import TableStyle
    from reportlab.lib import colors as C
    NAVY = C.HexColor("#1B3A6B")
    F5   = C.HexColor("#F5F5F5")
    cmds = [
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), C.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 7.5),
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 1), (-1, -1), 7.5),
        ("BACKGROUND",  (0, 1), (-1, -1), F5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [F5, C.white]),
        ("GRID",        (0, 0), (-1, -1), 0.3, C.HexColor("#CCCCCC")),
        ("TOPPADDING",  (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
    ]
    if nav_rows:
        for r in nav_rows:
            cmds.append(("BACKGROUND",  (0, r), (-1, r), NAVY))
            cmds.append(("TEXTCOLOR",   (0, r), (-1, r), C.white))
            cmds.append(("FONTNAME",    (0, r), (-1, r), "Helvetica-Bold"))
    return TableStyle(cmds)

# ---------------------------------------------------------------------------
# Header/Footer
# ---------------------------------------------------------------------------

def _header_footer(canvas, doc, company_name, ticker, gen_date):
    from reportlab.lib import colors as C
    from reportlab.lib.units import mm
    NAVY = C.HexColor("#1B3A6B")
    w, h = doc.pagesize
    # Footer line
    canvas.saveState()
    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, doc.bottomMargin - 5*mm, w - doc.rightMargin, doc.bottomMargin - 5*mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(C.HexColor("#555555"))
    canvas.drawString(doc.leftMargin, doc.bottomMargin - 9*mm,
                      f"FinSight IA | {company_name} ({ticker}) | {gen_date} | Confidentiel")
    canvas.drawRightString(w - doc.rightMargin, doc.bottomMargin - 9*mm,
                           f"Page {doc.page}")
    canvas.restoreState()

# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _sec_header(text, styles):
    from reportlab.platypus import Paragraph
    return Paragraph(text, styles["section"])

def _body(text, styles):
    from reportlab.platypus import Paragraph
    if not text: return None
    return Paragraph(str(text), styles["body"])

def _build_toc(styles):
    from reportlab.platypus import Paragraph, Spacer
    items = [
        "1. Synthèse Exécutive & Recommandation",
        "2. Présentation de l'Entreprise",
        "3. Analyse Financière",
        "4. Valorisation",
        "5. Analyse des Risques & Scénarios",
        "6. Sentiment de Marché",
        "7. Avocat du Diable",
        "8. Conditions d'Invalidation",
        "9. Disclaimer",
    ]
    elems = [Paragraph("TABLE DES MATIÈRES", styles["subsection"])]
    for item in items:
        elems.append(Paragraph(item, styles["toc"]))
    elems.append(Spacer(1, 10))
    return elems

def _sec1_synthese(snapshot, ratios, synthesis, styles):
    from reportlab.platypus import Paragraph, Spacer, Table, PageBreak
    from reportlab.lib import colors as C
    from reportlab.lib.units import mm

    elems = [_sec_header("1.  SYNTHÈSE EXÉCUTIVE", styles)]

    mkt   = snapshot.market
    ci    = snapshot.company_info
    cur   = ci.currency or "USD"
    price = mkt.share_price
    rec   = "N/A"
    conv  = "N/A"
    conf  = "N/A"

    if synthesis:
        rec  = getattr(synthesis, "recommendation", "N/A") or "N/A"
        conv = f"{getattr(synthesis, 'conviction', 0)*100:.0f}%"
        conf = f"{getattr(synthesis, 'confidence_score', 0)*100:.0f}%"

    elems.append(Paragraph(
        f"<b>RECOMMANDATION : {rec}</b>  |  Conviction : {conv}  |  Confiance IA : {conf}",
        styles["bold"]))

    # Bear / Base / Bull table
    tb = getattr(synthesis, "target_bear", None) if synthesis else None
    tbase = getattr(synthesis, "target_base", None) if synthesis else None
    tbull = getattr(synthesis, "target_bull", None) if synthesis else None

    data = [
        ["", "Bear", "Base", "Bull"],
        ["Prix Cible",
         f"{_v(tb, '{:.0f}')} {cur}" if tb else "N/A",
         f"{_v(tbase, '{:.0f}')} {cur}" if tbase else "N/A",
         f"{_v(tbull, '{:.0f}')} {cur}" if tbull else "N/A"],
        ["Upside/Downside",
         _upside(tb, price),
         _upside(tbase, price),
         _upside(tbull, price)],
        ["Probabilité", "25%", "50%", "25%"],
    ]
    t = Table(data, colWidths=[90, 120, 120, 120])
    t.setStyle(_ts_base())
    elems += [t, Spacer(1, 6)]

    elems.append(Paragraph(
        f"Cours actuel au {date.today().strftime('%d/%m/%Y')} : "
        f"{_v(price, '{:.2f}')} {cur}",
        styles["small"]))

    if synthesis and getattr(synthesis, "summary", ""):
        elems.append(Paragraph(synthesis.summary, styles["body"]))

    return elems


def _sec2_entreprise(snapshot, synthesis, styles):
    from reportlab.platypus import Paragraph, Spacer, Table

    elems = [_sec_header("2.  PRÉSENTATION DE L'ENTREPRISE", styles)]
    ci = snapshot.company_info
    cur = ci.currency or "USD"

    elems.append(Paragraph(
        f"Ticker : <b>{ci.ticker}</b>  |  Secteur : <b>{ci.sector or 'N/A'}</b>  |  "
        f"Devise : <b>{cur}</b>  |  Unités : <b>{ci.units or 'M'}</b>",
        styles["small"]))
    elems.append(Spacer(1, 6))

    elems.append(Paragraph("<b>Positionnement concurrentiel</b>", styles["subsection"]))
    if synthesis and getattr(synthesis, "valuation_comment", ""):
        elems.append(Paragraph(synthesis.valuation_comment, styles["body"]))
    else:
        elems.append(Paragraph("Données de positionnément non disponibles.", styles["body"]))

    if synthesis and getattr(synthesis, "strengths", []):
        elems.append(Paragraph("<b>Points forts</b>", styles["subsection"]))
        for s in synthesis.strengths[:3]:
            elems.append(Paragraph(f"• {s}", styles["bullet"]))

    return elems


def _sec3_financiere(snapshot, ratios, styles):
    from reportlab.platypus import Paragraph, Spacer, Table
    from reportlab.lib import colors as C

    elems = [_sec_header("3.  ANALYSE FINANCIÈRE", styles)]
    ci  = snapshot.company_info
    cur = ci.currency or "USD"
    units = ci.units or "M"

    # -- 3.1 Compte de Résultat --
    elems.append(Paragraph(f"3.1  Compte de Résultat ({cur} {units})", styles["subsection"]))

    # Colonnes : 3 historiques + 2 projections
    hist_labels = _valid_hist_labels(snapshot)[-3:]
    proj_labels = ["2025F", "2026F"]
    all_labels  = hist_labels + proj_labels

    def _fy(label):
        if label in snapshot.years:
            return snapshot.years[label]
        if ratios and label in ratios.projections:
            return ratios.projections[label]
        return None

    def _ry(label):
        return ratios.years.get(label) if ratios else None

    header = ["Métrique"] + all_labels
    rows = [header]

    def _row(name, vals):
        return [name] + [v if v else "N/A" for v in vals]

    rows.append(_row("Revenue",
        [_m(getattr(_fy(l), "revenue", None)) for l in all_labels]))

    rev_prev = None
    grow_vals = []
    for l in all_labels:
        fy = _fy(l)
        rev = getattr(fy, "revenue", None) if fy else None
        if rev_prev and rev and rev_prev != 0:
            grow_vals.append(f"{(rev - rev_prev)/abs(rev_prev)*100:+.1f}%")
        else:
            grow_vals.append("—")
        rev_prev = rev
    rows.append(_row("Croissance YoY", grow_vals))

    rows.append(_row("Gross Profit",
        [_m((_ry(l).gross_profit if _ry(l) else None) or
             getattr(_fy(l), "gross_profit_yf", None)) for l in all_labels]))
    rows.append(_row("Gross Margin",
        [_pct(_ry(l).gross_margin if _ry(l) else None) for l in all_labels]))
    rows.append(_row("EBITDA",
        [_m(_ry(l).ebitda if _ry(l) else None) for l in all_labels]))
    rows.append(_row("EBITDA Margin",
        [_pct(_ry(l).ebitda_margin if _ry(l) else None) for l in all_labels]))
    rows.append(_row("Net Income",
        [_m(_ry(l).net_income if _ry(l) else None) for l in all_labels]))
    rows.append(_row("Net Margin",
        [_pct(_ry(l).net_margin if _ry(l) else None) for l in all_labels]))

    col_w = [90] + [65] * len(all_labels)
    t = Table(rows, colWidths=col_w)
    t.setStyle(_ts_base())
    elems += [t, Spacer(1, 6)]
    elems.append(Paragraph(
        "Analyse des tendances financières sur les exercices disponibles. "
        "Les colonnes F correspondent aux projections sectorielles FinSight IA.",
        styles["small"]))

    # -- 3.2 Bilan --
    elems.append(Paragraph("3.2  Bilan & Solidité Financière", styles["subsection"]))
    latest = hist_labels[-1] if hist_labels else None
    yr = _ry(latest) if latest else None
    fy = _fy(latest) if latest else None

    if yr and fy:
        bdata = [["Métrique", f"Valeur LTM ({cur}M)", "Interprétation"]]
        cash = getattr(fy, "cash", None)
        ltd  = getattr(fy, "long_term_debt", None)
        nd   = yr.net_debt
        cr   = yr.current_ratio
        de   = yr.debt_equity

        def _interp_nd(v):
            if v is None: return "N/A"
            return "Trésorerie nette positive" if float(v) < 0 else "Endetté net"

        def _interp_cr(v):
            if v is None: return "N/A"
            f = float(v)
            if f > 2: return "Sain"
            if f > 1: return "Correct"
            return "Tendu"

        bdata += [
            ["Cash & Équivalents",   _m(cash),  "Liquidité disponible"],
            ["Dette Long Terme",     _m(ltd),   "Financement LT"],
            ["Dette Nette",          _m(nd),    _interp_nd(nd)],
            ["Current Ratio",        _x(cr),    _interp_cr(cr)],
            ["Debt / Equity",        _x(de),    "N/A" if de is None else ("Solide" if float(de) < 1 else "Levier élevé")],
        ]
        bt = Table(bdata, colWidths=[130, 110, 210])
        bt.setStyle(_ts_base())
        elems += [bt, Spacer(1, 6)]

    # -- 3.3 Ratios vs Benchmark --
    elems.append(Paragraph("3.3  Ratios Clés vs Benchmark Sectoriel", styles["subsection"]))
    sector = snapshot.company_info.sector or ""
    bm = _sector_benchmarks(sector)

    if yr:
        from reportlab.lib import colors as C
        rdata = [["Ratio", "Valeur", f"Benchmark {sector[:15] or 'Secteur'}", "Signal"]]

        def _sig_row(label, val, bm_str, lo_pct=None, hi_pct=None, invert=False):
            col, lbl = _signal(val, lo_pct or 0, hi_pct or 99, invert=invert)
            return [label, val or "N/A", bm_str, lbl]

        rdata += [
            _sig_row("P/E",           _x(yr.pe_ratio),      bm["pe"]),
            _sig_row("EV/EBITDA",     _x(yr.ev_ebitda),     bm["ev_ebitda"]),
            _sig_row("EV/Revenue",    _x(yr.ev_revenue),    bm["ev_rev"]),
            _sig_row("Gross Margin",  _pct(yr.gross_margin), bm["gross_m"]),
            _sig_row("EBITDA Margin", _pct(yr.ebitda_margin), bm["ebitda_m"]),
            _sig_row("ROE",           _pct(yr.roe),         bm["roe"]),
        ]
        # Altman
        az = yr.altman_z
        az_lbl = "SAIN" if (az and float(az) > 2.99) else ("ZONE GRISE" if (az and float(az) > 1.81) else ("DETRESSE" if az else "N/A"))
        rdata.append(["Altman Z-Score", _v(az, "{:.2f}"), "> 2.99 = Sain", az_lbl])
        # Beneish
        bm_score = yr.beneish_m
        bm_lbl = "OK" if (bm_score and float(bm_score) < -2.22) else ("SIGNAL" if bm_score else "N/A")
        rdata.append(["Beneish M-Score", _v(bm_score, "{:.3f}"), "< -2.22 = OK", bm_lbl])

        rt = Table(rdata, colWidths=[110, 80, 120, 140])
        rt.setStyle(_ts_base())
        elems += [rt, Spacer(1, 4)]

    return elems


def _sec4_valorisation(snapshot, ratios, synthesis, styles):
    from reportlab.platypus import Paragraph, Spacer, Table
    from reportlab.lib import colors as C

    elems = [_sec_header("4.  VALORISATION", styles)]
    mkt = snapshot.market
    ci  = snapshot.company_info
    cur = ci.currency or "USD"

    wacc = getattr(mkt, "wacc", None) or 0.10
    tgr  = getattr(mkt, "terminal_growth", None) or 0.025
    price = mkt.share_price

    # -- 4.1 DCF --
    elems.append(Paragraph("4.1  DCF — Scénario Base", styles["subsection"]))
    elems.append(Paragraph(
        f"WACC : {wacc*100:.1f}%  |  Terminal Growth Rate : {tgr*100:.1f}%  |  Horizon : 5 ans",
        styles["small"]))

    tbase = getattr(synthesis, "target_base", None) if synthesis else None
    upside = _upside(tbase, price)

    # Projections
    hist_labels = _valid_hist_labels(snapshot)
    latest_fy   = snapshot.years.get(hist_labels[-1]) if hist_labels else None
    rev_cagr = "N/A"
    if ratios and len(hist_labels) >= 2:
        r0 = getattr(snapshot.years.get(hist_labels[0]), "revenue", None)
        r1 = getattr(latest_fy, "revenue", None)
        if r0 and r1 and r0 > 0 and len(hist_labels) > 1:
            n = len(hist_labels) - 1
            try: rev_cagr = f"{((r1/r0)**(1/n)-1)*100:.1f}%"
            except Exception: pass

    latest_yr = ratios.years.get(hist_labels[-1]) if ratios and hist_labels else None
    ebitda_m  = _pct(latest_yr.ebitda_margin if latest_yr else None)

    dcf_data = [
        ["Hypothèse", "Valeur"],
        ["Revenue CAGR projeté (historique)", rev_cagr],
        ["EBITDA Margin cible (LTM)", ebitda_m],
        ["WACC", f"{wacc*100:.1f}%"],
        ["Terminal Growth Rate", f"{tgr*100:.1f}%"],
        ["Valeur intrinsèque (Base)", f"{_v(tbase, '{:.0f}')} {cur}" if tbase else "N/A"],
        ["Cours actuel", f"{_v(price, '{:.2f}')} {cur}"],
        ["Upside / Downside implicite", upside],
    ]
    dt = Table(dcf_data, colWidths=[250, 200])
    dt.setStyle(_ts_base())
    elems += [dt, Spacer(1, 6)]

    if synthesis and getattr(synthesis, "valuation_comment", ""):
        elems.append(Paragraph(synthesis.valuation_comment, styles["small"]))

    # -- 4.2 Sensibilité --
    elems.append(Paragraph("4.2  Table de Sensibilité DCF (Prix Implicite)", styles["subsection"]))
    waccs, tgrs, sens_rows = _sensitivity_table(tbase or price, wacc, tgr)
    tgr_labels  = [f"TGR {t*100:.1f}%" for t in tgrs]
    wacc_labels = [f"WACC {w*100:.1f}%" for w in waccs]
    sens_data = [["WACC \\ TGR"] + tgr_labels]
    for i, row in enumerate(sens_rows):
        sens_data.append([wacc_labels[i]] + row)
    st_t = Table(sens_data, colWidths=[100, 120, 120, 120])
    # Highlight center (base case)
    from reportlab.platypus import TableStyle as TS
    from reportlab.lib import colors as C
    style = _ts_base()
    style.add("BACKGROUND", (2, 2), (2, 2), C.HexColor("#1B3A6B"))
    style.add("TEXTCOLOR",  (2, 2), (2, 2), C.white)
    style.add("FONTNAME",   (2, 2), (2, 2), "Helvetica-Bold")
    st_t.setStyle(style)
    elems += [st_t, Spacer(1, 6)]

    # -- 4.3 Multiples --
    elems.append(Paragraph("4.3  Valorisation par Multiples Comparables", styles["subsection"]))
    sector = ci.sector or ""
    bm = _sector_benchmarks(sector)

    def _mid_bm(s):
        """Extrait la valeur médiane d'une chaine comme '10-18x'."""
        try:
            parts = s.replace("x","").replace("%","").split("-")
            return (float(parts[0]) + float(parts[1])) / 2
        except Exception: return None

    # Récupérer médiane peers et implied price
    mult_data = [["Multiple", f"Valeur {ci.ticker}", "Médiane Peers", "Implied Price", "Upside"]]
    if latest_yr and price:
        def _implied(company_mult, peer_mult, cur_price):
            try:
                if company_mult and peer_mult and float(company_mult) > 0:
                    return f"{cur_price * float(peer_mult) / float(company_mult):.0f}"
            except Exception: pass
            return "N/A"

        ev_ebitda_comp  = latest_yr.ev_ebitda
        ev_rev_comp     = latest_yr.ev_revenue
        pe_comp         = latest_yr.pe_ratio
        med_ev_ebitda   = _mid_bm(bm["ev_ebitda"])
        med_ev_rev      = _mid_bm(bm["ev_rev"])
        med_pe          = _mid_bm(bm["pe"])

        impl_ev_ebitda = _implied(ev_ebitda_comp, med_ev_ebitda, price)
        impl_ev_rev    = _implied(ev_rev_comp, med_ev_rev, price)
        impl_pe        = _implied(pe_comp, med_pe, price)

        # Pondération simple
        imp_prices = []
        for ip in [impl_ev_ebitda, impl_ev_rev, impl_pe]:
            try: imp_prices.append(float(ip))
            except Exception: pass
        avg_imp = f"{sum(imp_prices)/len(imp_prices):.0f} {cur}" if imp_prices else "N/A"

        mult_data += [
            ["EV/EBITDA", _x(ev_ebitda_comp), f"{med_ev_ebitda:.1f}x" if med_ev_ebitda else "N/A",
             f"{impl_ev_ebitda} {cur}", _upside(impl_ev_ebitda, price)],
            ["EV/Revenue", _x(ev_rev_comp), f"{med_ev_rev:.1f}x" if med_ev_rev else "N/A",
             f"{impl_ev_rev} {cur}", _upside(impl_ev_rev, price)],
            ["P/E", _x(pe_comp), f"{med_pe:.1f}x" if med_pe else "N/A",
             f"{impl_pe} {cur}", _upside(impl_pe, price)],
            ["Moyenne pondérée", "—", "—", avg_imp, _upside(avg_imp.split()[0] if imp_prices else None, price)],
        ]
    else:
        mult_data.append(["Données insuffisantés", "—", "—", "—", "—"])

    mt = Table(mult_data, colWidths=[80, 80, 90, 100, 100])
    mt.setStyle(_ts_base())
    elems += [mt]
    return elems


def _sec5_risques(snapshot, synthesis, styles):
    from reportlab.platypus import Paragraph, Spacer, Table
    from reportlab.lib import colors as C

    elems = [_sec_header("5.  ANALYSE DES RISQUES & SCÉNARIOS", styles)]
    ci  = snapshot.company_info
    cur = ci.currency or "USD"
    price = snapshot.market.share_price

    strengths = (getattr(synthesis, "strengths", []) if synthesis else []) or []
    risks     = (getattr(synthesis, "risks", []) if synthesis else []) or []
    tb  = getattr(synthesis, "target_bear", None) if synthesis else None
    tba = getattr(synthesis, "target_base", None) if synthesis else None
    tbu = getattr(synthesis, "target_bull", None) if synthesis else None

    def _scenario_block(label, target, bullets, prob, color_hex):
        from reportlab.lib import colors as C
        col = C.HexColor(color_hex)
        items = []
        title = (f"{label} — {_v(target, '{:.0f}')} {cur} ({_upside(target, price)})  "
                 f"| Probabilité estimée : {prob}")
        items.append(Paragraph(f"<b>{title}</b>", styles["bold"]))
        for b in bullets[:3]:
            if b: items.append(Paragraph(f"• {b}", styles["bullet"]))
        items.append(Spacer(1, 6))
        return items

    elems += _scenario_block("Bull", tbu, strengths, "25%", "#1a7a52")
    elems += _scenario_block("Base", tba,
                             [s for s in (strengths + risks)][:3] if (strengths or risks) else [],
                             "50%", "#1B3A6B")
    elems += _scenario_block("Bear", tb, risks, "25%", "#c0392b")
    return elems


def _sec6_sentiment(sentiment, styles):
    from reportlab.platypus import Paragraph, Spacer, Table

    elems = [_sec_header("6.  SENTIMENT DE MARCHÉ", styles)]

    if not sentiment:
        elems.append(Paragraph("Données de sentiment non disponibles (FinBERT désactivé en cloud).", styles["body"]))
        return elems

    label  = getattr(sentiment, "label",             "NEUTRAL")
    score  = getattr(sentiment, "score",             0.0)
    conf   = getattr(sentiment, "confidence",        0.0)
    n_art  = getattr(sentiment, "articles_analyzed", 0)
    breakdown = getattr(sentiment, "breakdown", {}) or {}

    elems.append(Paragraph(
        f"Score FinBERT : <b>{label}</b> ({score:+.3f})  |  "
        f"Confiance : {conf*100:.0f}%  |  Articles analysés : {n_art}",
        styles["bold"]))
    elems.append(Spacer(1, 6))

    n_pos = round(breakdown.get("avg_positive", 0) * n_art) if n_art else 0
    n_neu = round(breakdown.get("avg_neutral",  0) * n_art) if n_art else 0
    n_neg = round(breakdown.get("avg_negative", 0) * n_art) if n_art else 0

    sdata = [["Orientation", "Nb articles", "Score moyen"],
             ["Positif",  str(n_pos), f"{breakdown.get('avg_positive', 0)*100:.0f}%"],
             ["Neutre",   str(n_neu), f"{breakdown.get('avg_neutral',  0)*100:.0f}%"],
             ["Négatif",  str(n_neg), f"{breakdown.get('avg_negative', 0)*100:.0f}%"]]
    st = Table(sdata, colWidths=[130, 120, 200])
    st.setStyle(_ts_base())
    elems += [st, Spacer(1, 6)]

    elems.append(Paragraph(
        f"Le sentiment de marché est {label.lower()} avec un score de {score:+.3f}. "
        "Cette analyse est basée sur les actualités récentes collectées via Finnhub et RSS. "
        "Le sentiment doit être interprété en complément de l'analyse fondamentale.",
        styles["body"]))
    return elems


def _sec7_devil(devil, synthesis, styles):
    from reportlab.platypus import Paragraph, Spacer

    elems = [_sec_header("7.  AVOCAT DU DIABLE", styles)]

    if not devil:
        elems.append(Paragraph("Analyse contradictoire non disponible.", styles["body"]))
        return elems

    delta   = getattr(devil, "conviction_delta", 0.0)
    rec_orig = getattr(synthesis, "recommendation", "N/A") if synthesis else "N/A"
    alt_map  = {"BUY": "HOLD/SELL", "HOLD": "SELL", "SELL": "BUY"}
    alt_rec  = alt_map.get(rec_orig, "HOLD")

    elems.append(Paragraph(
        f"<b>Thèse inverse</b>  |  Delta conviction : {delta:+.2f}  |  "
        f"Recommandation alternative : {alt_rec}",
        styles["bold"]))
    elems.append(Spacer(1, 6))

    counter = getattr(devil, "counter_thesis", "") or ""
    elems.append(Paragraph(counter, styles["body"]))

    counter_risks = getattr(devil, "counter_risks", []) or []
    for i, risk in enumerate(counter_risks[:3]):
        if risk:
            elems.append(Paragraph(f"<b>Fragilité {i+1} :</b> {risk}", styles["bullet"]))
    return elems


def _sec8_invalidation(synthesis, devil, styles):
    from reportlab.platypus import Paragraph, Spacer

    elems = [_sec_header("8.  CONDITIONS D'INVALIDATION", styles)]
    elems.append(Paragraph(
        "Cette analyse serait à réviser dans les cas suivants :", styles["body"]))

    conditions = []
    if synthesis and getattr(synthesis, "invalidation_conditions", ""):
        conditions.append(("Synthèse IA", synthesis.invalidation_conditions))
    if devil and getattr(devil, "invalidation_conditions", ""):
        conditions.append(("Avocat du Diable", devil.invalidation_conditions))

    if not conditions:
        elems.append(Paragraph("• Révision des hypothèses macro ou sectorielles significatives.", styles["bullet"]))
        elems.append(Paragraph("• Restatement comptable ou changement de direction.", styles["bullet"]))
        elems.append(Paragraph("• Évolution réglementaire majeure impactant le modèle d'affaires.", styles["bullet"]))
    else:
        for source, cond in conditions:
            elems.append(Paragraph(f"<b>{source} :</b> {cond}", styles["bullet"]))

    return elems


def _sec9_disclaimer(gen_date, styles):
    from reportlab.platypus import Paragraph, Spacer, HRFlowable
    from reportlab.lib import colors as C

    elems = [_sec_header("9.  DISCLAIMER", styles)]
    elems.append(Paragraph(
        f"Rapport généré par FinSight IA v1.0 le {gen_date}. "
        "Ce document est produit par un système d'intelligence artificielle à des fins d'analyse uniquement. "
        "Il ne constitue pas un conseil en investissement au sens de la directive MiFID II. "
        "FinSight IA ne peut être tenu responsable des décisions d'investissement prises sur la base de ce document. "
        "Les données financières sont issues de sources publiques (yfinance, Finnhub, FMP) "
        "et peuvent contenir des inexactitudes. "
        "Toute décision d'investissement doit faire l'objet d'une analyse complémentaire "
        "par un professionnel qualifié.",
        styles["body"]))
    elems.append(Spacer(1, 10))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=C.HexColor("#1B3A6B")))
    elems.append(Spacer(1, 4))
    elems.append(Paragraph(
        f"FinSight IA  |  {gen_date}  |  Confidentiel — Usage interne uniquement",
        styles["small"]))
    return elems

# ---------------------------------------------------------------------------
# Point d'entrée public
# ---------------------------------------------------------------------------

def generate_pdf(
    snapshot,
    ratios,
    synthesis=None,
    sentiment=None,
    qa_python=None,
    devil=None,
    output_path: Optional[Path] = None,
) -> Path:
    try:
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable
        )
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors as C
    except ImportError:
        raise RuntimeError("reportlab requis : pip install reportlab")

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    gen_date = date.today().strftime("%d/%m/%Y")
    ci       = snapshot.company_info
    ticker   = snapshot.ticker.replace(".", "_")

    if output_path is None:
        output_path = _OUTPUT_DIR / f"{ticker}_{date.today().isoformat()}_report.pdf"

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=18*mm,  bottomMargin=22*mm,
        title=f"FinSight IA — {ci.company_name} ({ci.ticker})",
        author="FinSight IA v1.0",
    )

    NAVY = C.HexColor("#1B3A6B")
    styles = _build_styles()

    def _on_page(canvas, doc_obj):
        _header_footer(canvas, doc_obj, ci.company_name, ci.ticker, gen_date)

    # --- Build story ---
    story = []

    # Cover / Header block
    story.append(Paragraph("FINSIGHT IA — RAPPORT D'ANALYSE FINANCIÈRE", styles["title"]))
    story.append(Paragraph(
        f"{ci.company_name} ({ci.ticker})  |  Secteur : {ci.sector or 'N/A'}  |  "
        f"Devise : {ci.currency or 'USD'}",
        styles["subtitle"]))
    story.append(Paragraph(
        f"Date : {gen_date}  |  Analyste : FinSight IA v1.0  |  Confidentiel",
        styles["small"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=NAVY, spaceAfter=8))

    # TOC
    story += _build_toc(styles)
    story.append(PageBreak())

    # Sections
    story += _sec1_synthese(snapshot, ratios, synthesis, styles)
    story.append(Spacer(1, 8))
    story += _sec2_entreprise(snapshot, synthesis, styles)
    story.append(PageBreak())

    story += _sec3_financiere(snapshot, ratios, styles)
    story.append(PageBreak())

    story += _sec4_valorisation(snapshot, ratios, synthesis, styles)
    story.append(PageBreak())

    story += _sec5_risques(snapshot, synthesis, styles)
    story.append(Spacer(1, 8))
    story += _sec6_sentiment(sentiment, styles)
    story.append(PageBreak())

    story += _sec7_devil(devil, synthesis, styles)
    story.append(Spacer(1, 8))
    story += _sec8_invalidation(synthesis, devil, styles)
    story.append(Spacer(1, 8))
    story += _sec9_disclaimer(gen_date, styles)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    log.info(f"[PDFReport] {ticker} → {output_path.name}")
    return output_path
