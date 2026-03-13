# =============================================================================
# FinSight IA — Rapport PDF Professionnel (IB Style)
# outputs/pdf_report.py
#
# 8 sections sur ~8 pages A4 :
#  1. Synthese Executive & Recommandation
#  2. Presentation de l'Entreprise
#  3. Analyse Financiere — Compte de Resultat & Bilan
#  4. Ratios Cles & Benchmark Sectoriel
#  5. Valorisation — DCF & Multiples
#  6. Scenarios de Valorisation
#  7. Sentiment de Marche & Avocat du Diable
#  8. Conditions d'Invalidation & Disclaimer
#
# Bookmarks PDF cliquables (panneau navigation Acrobat/Preview).
# Tables financieres avec ReportLab platypus Table draw-on-canvas.
#
# Usage :
#   path = generate_pdf(snapshot, ratios, synthesis, sentiment, qa_python, devil)
# =============================================================================

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_OUTPUT_DIR = Path(__file__).parent / "generated"

# ---------------------------------------------------------------------------
# Palette IB
# ---------------------------------------------------------------------------
_NAVY  = (0.106, 0.165, 0.290)   # #1B2A4A
_WHITE = (1.0,   1.0,   1.0)
_LIGHT = (0.980, 0.980, 0.980)   # #FAFAFA
_MID   = (0.941, 0.941, 0.941)   # #F0F0F0
_DARK  = (0.067, 0.067, 0.067)   # #111
_GREY  = (0.467, 0.467, 0.467)   # #777
_GREEN = (0.102, 0.478, 0.322)   # #1A7A52
_AMBER = (0.722, 0.573, 0.165)   # #B8922A
_RED   = (0.753, 0.224, 0.169)   # #C0392B


# ---------------------------------------------------------------------------
# Formatage
# ---------------------------------------------------------------------------
def _p(v) -> str:
    return f"{v*100:.1f}%" if v is not None else "N/A"

def _x(v) -> str:
    return f"{v:.2f}x" if v is not None else "N/A"

def _n(v, dp=2) -> str:
    return f"{v:.{dp}f}" if v is not None else "N/A"

def _f(v) -> str:
    return f"{v:,.0f}" if v is not None else "N/A"

def _safe(text, maxlen=None) -> str:
    if not text:
        return ""
    s = str(text)
    if maxlen:
        s = s[:maxlen]
    return s


# ---------------------------------------------------------------------------
# Helpers canvas
# ---------------------------------------------------------------------------

def _rgb(t):
    from reportlab.lib import colors
    return colors.Color(*t)

def _header_band(c, W, H, company: str, page_label: str, today: str):
    bh = 38
    c.setFillColor(_rgb(_NAVY))
    c.rect(0, H - bh, W, bh, fill=1, stroke=0)
    c.setFillColor(_rgb(_WHITE))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(26, H - 23, "FINSIGHT IA  —  ANALYSE FINANCIERE PROFESSIONNELLE")
    c.setFont("Helvetica", 7.5)
    c.drawRightString(W - 26, H - 23, f"{company}  |  {today}")
    c.setFont("Helvetica", 7)
    c.drawRightString(W - 26, H - 33, page_label)

def _footer(c, W, M, today: str, page: int, total: int = 8):
    c.setStrokeColor(_rgb(_MID))
    c.line(M, 22, W - M, 22)
    c.setFillColor(_rgb(_GREY))
    c.setFont("Helvetica", 6.5)
    c.drawString(M, 11,
        "FinSight IA — Outil d'aide a la decision uniquement. "
        "Ne constitue pas un conseil en investissement.")
    c.drawRightString(W - M, 11, f"{today}  |  Page {page}/{total}")

def _section_title(c, x, y, text: str, content_width: float, anchor: str = ""):
    """Titre de section avec ligne + bookmark PDF."""
    if anchor:
        c.bookmarkPage(anchor)
    c.setFillColor(_rgb(_NAVY))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x, y, text.upper())
    tw = c.stringWidth(text.upper(), "Helvetica-Bold", 8)
    c.setStrokeColor(_rgb(_MID))
    c.line(x + tw + 8, y + 3, x + content_width, y + 3)
    return y - 18

def _wrap(c, text: str, x, y, max_w: float,
          font="Helvetica", size=9, lh=13, color=None) -> float:
    """Wrap text. Returns final y."""
    if not text:
        return y
    c.setFont(font, size)
    c.setFillColor(_rgb(color or _DARK))
    for para in str(text).split("\n"):
        words = para.split()
        if not words:
            y -= lh * 0.5
            continue
        line = ""
        for w in words:
            test = (line + " " + w).strip()
            if c.stringWidth(test, font, size) > max_w:
                if line:
                    c.drawString(x, y, line)
                    y -= lh
                line = w
            else:
                line = test
        if line:
            c.drawString(x, y, line)
            y -= lh
    return y

def _draw_table(c, data, col_widths, style_cmds, x, y) -> float:
    """Dessine un platypus Table sur le canvas. Retourne le y apres le tableau."""
    try:
        from reportlab.platypus import Table, TableStyle
    except ImportError:
        return y
    tbl = Table(data, colWidths=col_widths)
    tbl.setStyle(TableStyle(style_cmds))
    _, th = tbl.wrapOn(c, sum(col_widths), 9999)
    tbl.drawOn(c, x, y - th)
    return y - th - 8

def _bullet(c, x, y, text: str, max_w: float, color=None, size=8.5, lh=12) -> float:
    c.setFont("Helvetica-Bold", size)
    c.setFillColor(_rgb(color or _DARK))
    c.drawString(x, y, "▸")
    c.setFont("Helvetica", size)
    c.setFillColor(_rgb(_DARK))
    return _wrap(c, text, x + 12, y, max_w - 14, size=size, lh=lh)


# ---------------------------------------------------------------------------
# TABLE DES MATIERES (Page 2)
# ---------------------------------------------------------------------------

_TOC_SECTIONS = [
    ("1",  "Synthese Executive & Recommandation",           "p.1",  "sec_cover"),
    ("2",  "Presentation de l'Entreprise",                  "p.2",  "sec_company"),
    ("3",  "Analyse Financiere — Compte de Resultat & Bilan","p.3", "sec_financials"),
    ("4",  "Ratios Cles & Benchmark Sectoriel",             "p.4",  "sec_ratios"),
    ("5",  "Valorisation — DCF & Multiples",                "p.5",  "sec_valuation"),
    ("6",  "Scenarios de Valorisation",                     "p.6",  "sec_scenarios"),
    ("7",  "Sentiment de Marche & Avocat du Diable",        "p.7",  "sec_sentiment"),
    ("8",  "Conditions d'Invalidation & Disclaimer",        "p.8",  "sec_disclaimer"),
]

def _add_toc_bookmarks(c):
    """Ajoute les entrees de sommaire dans le panneau de navigation PDF."""
    for num, title, _, anchor in _TOC_SECTIONS:
        c.addOutlineEntry(f"{num}. {title}", anchor, level=0, closed=False)


# ---------------------------------------------------------------------------
# GENERATEUR PRINCIPAL
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
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
    except ImportError:
        raise RuntimeError("reportlab requis : pip install reportlab")

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today  = date.today().strftime("%d/%m/%Y")
    ticker = snapshot.ticker.replace(".", "_")

    if output_path is None:
        output_path = _OUTPUT_DIR / f"{ticker}_{date.today().isoformat()}_report.pdf"

    ci  = snapshot.company_info
    mkt = snapshot.market
    yr  = ratios.years.get(ratios.latest_year) if ratios else None
    latest = ratios.latest_year if ratios else ""

    W, H = A4
    M    = 28
    CW   = W - 2 * M

    c = canvas.Canvas(str(output_path), pagesize=A4)
    c.setTitle(f"FinSight IA — {ci.company_name} — {today}")
    c.setAuthor("FinSight IA v1.2")
    c.setSubject(f"Analyse financiere {ci.ticker}")

    # -----------------------------------------------------------------------
    # P1 — Synthese Executive & Recommandation
    # -----------------------------------------------------------------------
    c.bookmarkPage("sec_cover")
    _draw_page1(c, W, H, M, CW, ci, mkt, synthesis, yr, today)
    c.showPage()

    # -----------------------------------------------------------------------
    # P2 — Table des matieres + Presentation entreprise
    # -----------------------------------------------------------------------
    c.bookmarkPage("sec_company")
    _draw_page2(c, W, H, M, CW, ci, mkt, synthesis, today)
    c.showPage()

    # -----------------------------------------------------------------------
    # P3 — Analyse Financiere : IS + Bilan
    # -----------------------------------------------------------------------
    c.bookmarkPage("sec_financials")
    _draw_page3(c, W, H, M, CW, ci, snapshot, ratios, today)
    c.showPage()

    # -----------------------------------------------------------------------
    # P4 — Ratios cles & Benchmark
    # -----------------------------------------------------------------------
    c.bookmarkPage("sec_ratios")
    _draw_page4(c, W, H, M, CW, ci, yr, latest, today)
    c.showPage()

    # -----------------------------------------------------------------------
    # P5 — Valorisation DCF & Multiples
    # -----------------------------------------------------------------------
    c.bookmarkPage("sec_valuation")
    _draw_page5(c, W, H, M, CW, ci, mkt, yr, synthesis, today)
    c.showPage()

    # -----------------------------------------------------------------------
    # P6 — Scenarios
    # -----------------------------------------------------------------------
    c.bookmarkPage("sec_scenarios")
    _draw_page6(c, W, H, M, CW, ci, mkt, synthesis, today)
    c.showPage()

    # -----------------------------------------------------------------------
    # P7 — Sentiment + Devil's Advocate
    # -----------------------------------------------------------------------
    c.bookmarkPage("sec_sentiment")
    _draw_page7(c, W, H, M, CW, ci, sentiment, devil, qa_python, synthesis, today)
    c.showPage()

    # -----------------------------------------------------------------------
    # P8 — Invalidation + Disclaimer
    # -----------------------------------------------------------------------
    c.bookmarkPage("sec_disclaimer")
    _draw_page8(c, W, H, M, CW, ci, synthesis, today)
    c.showPage()

    # Bookmarks navigables dans Acrobat/Preview
    _add_toc_bookmarks(c)

    c.save()
    log.info(f"[PDFReport] {output_path.name} genere (8 pages)")
    return output_path


# ---------------------------------------------------------------------------
# PAGE 1 — Synthese Executive & Recommandation
# ---------------------------------------------------------------------------

def _draw_page1(c, W, H, M, CW, ci, mkt, synthesis, yr, today):
    _header_band(c, W, H, ci.company_name, "Page 1/8 — Synthese Executive", today)
    _footer(c, W, M, today, 1)

    y = H - 56

    # Identite societe
    c.setFont("Helvetica-Bold", 26)
    c.setFillColor(_rgb(_DARK))
    name = _safe(ci.company_name)
    # Tronquer si trop long
    while c.stringWidth(name, "Helvetica-Bold", 26) > CW and len(name) > 10:
        name = name[:-4] + "..."
    c.drawString(M, y, name)
    y -= 18

    meta = "  |  ".join(filter(None, [
        _safe(ci.ticker),
        _safe(ci.sector, 40) if ci.sector else "",
        f"Bourse : {_safe(ci.currency)}",
        f"Analyse : {today}",
        "FinSight IA v1.2",
    ]))
    c.setFont("Helvetica", 8)
    c.setFillColor(_rgb(_GREY))
    c.drawString(M, y, meta)
    y -= 16

    c.setStrokeColor(_rgb(_MID))
    c.line(M, y, W - M, y)
    y -= 22

    if not synthesis:
        c.setFont("Helvetica", 9)
        c.setFillColor(_rgb(_GREY))
        c.drawString(M, y, "Synthese non disponible.")
        return

    reco    = synthesis.recommendation
    reco_fr = {"BUY": "ACHETER", "SELL": "VENDRE", "HOLD": "CONSERVER"}.get(reco, reco)
    reco_col = {"BUY": _GREEN, "SELL": _RED}.get(reco, _AMBER)
    conv    = synthesis.conviction or 0

    # --- Zone recommandation (gauche) ---
    rec_x = M
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(_rgb(_GREY))
    c.drawString(rec_x, y, "RECOMMANDATION")
    y -= 6
    c.setFont("Helvetica-Bold", 40)
    c.setFillColor(_rgb(reco_col))
    c.drawString(rec_x, y - 34, reco_fr)

    bar_y = y - 52
    bar_w = 170
    c.setFillColor(_rgb(_MID))
    c.rect(rec_x, bar_y, bar_w, 5, fill=1, stroke=0)
    c.setFillColor(_rgb(reco_col))
    c.rect(rec_x, bar_y, int(bar_w * conv), 5, fill=1, stroke=0)
    c.setFont("Helvetica", 7.5)
    c.setFillColor(_rgb(_GREY))
    c.drawString(rec_x, bar_y - 12,
        f"Conviction IA : {conv:.0%}    |    Confiance modele : {synthesis.confidence_score:.0%}")

    # --- Box prix cibles (droite) ---
    box_x = M + 200
    box_y = y + 6
    box_w = CW - 200
    box_h = 108

    c.setFillColor(_rgb(_LIGHT))
    c.setStrokeColor(_rgb(_MID))
    c.roundRect(box_x, box_y - box_h, box_w, box_h, 3, fill=1, stroke=1)

    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(_rgb(_GREY))
    c.drawString(box_x + 10, box_y - 14, "PRIX CIBLES (12 MOIS)")

    cur = mkt.share_price if mkt else None
    cur_s = f"Cours actuel : {cur:,.2f} {ci.currency}" if cur else "Cours actuel : N/A"
    c.setFont("Helvetica", 6.5)
    c.setFillColor(_rgb(_GREY))
    c.drawString(box_x + 10, box_y - 24, cur_s)

    col3 = box_w / 3
    scenarios = [
        ("BEAR CASE", synthesis.target_bear, _RED,   "Scenario pessimiste"),
        ("BASE CASE", synthesis.target_base, _AMBER, "Scenario central"),
        ("BULL CASE", synthesis.target_bull, _GREEN, "Scenario optimiste"),
    ]
    for idx, (label, val, col, hint) in enumerate(scenarios):
        cx = box_x + 10 + idx * col3
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(_rgb(_GREY))
        c.drawString(cx, box_y - 36, label)
        c.setFont("Helvetica-Bold", 22)
        c.setFillColor(_rgb(col))
        val_s = f"{val:,.0f}" if val else "—"
        c.drawString(cx, box_y - 60, val_s)
        if val and cur:
            upside = (val - cur) / cur * 100
            arrow = "+" if upside >= 0 else ""
            u_col = _GREEN if upside >= 0 else _RED
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(_rgb(u_col))
            c.drawString(cx, box_y - 73, f"{arrow}{upside:.1f}%")
        c.setFont("Helvetica", 6.5)
        c.setFillColor(_rgb(_GREY))
        c.drawString(cx, box_y - 85, hint)

    y = box_y - box_h - 20

    c.setStrokeColor(_rgb(_MID))
    c.line(M, y, W - M, y)
    y -= 16

    # --- Tableau donnees de marche ---
    mkt_items = [
        ("Cours", f"{cur:,.2f} {ci.currency}" if cur else "N/A"),
        ("Beta", _n(mkt.beta_levered if mkt else None)),
        ("WACC", _p(mkt.wacc if mkt else None)),
        ("TG terminal", _p(mkt.terminal_growth if mkt else None)),
        ("P/E LTM", _x(yr.pe_ratio if yr else None)),
        ("EV/EBITDA", _x(yr.ev_ebitda if yr else None)),
    ]
    col_w = CW / len(mkt_items)
    for i, (lbl, val) in enumerate(mkt_items):
        cx = M + i * col_w
        c.setFont("Helvetica", 6.5)
        c.setFillColor(_rgb(_GREY))
        c.drawString(cx, y, lbl)
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(_rgb(_DARK))
        c.drawString(cx, y - 14, val)

    y -= 36
    c.setStrokeColor(_rgb(_MID))
    c.line(M, y, W - M, y)
    y -= 16

    # --- Resume executif ---
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(_rgb(_NAVY))
    c.drawString(M, y, "RESUME EXECUTIF")
    tw = c.stringWidth("RESUME EXECUTIF", "Helvetica-Bold", 8)
    c.setStrokeColor(_rgb(_MID))
    c.line(M + tw + 8, y + 3, W - M, y + 3)
    y -= 16

    summary_intro = _safe(synthesis.summary, 700)
    y = _wrap(c, summary_intro, M, y, CW, size=9, lh=14)


# ---------------------------------------------------------------------------
# PAGE 2 — Table des matieres + Presentation entreprise
# ---------------------------------------------------------------------------

def _draw_page2(c, W, H, M, CW, ci, mkt, synthesis, today):
    _header_band(c, W, H, ci.company_name, "Page 2/8 — Sommaire & Presentation", today)
    _footer(c, W, M, today, 2)

    y = H - 56

    # --- Sommaire ---
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(_rgb(_DARK))
    c.drawString(M, y, "TABLE DES MATIERES")
    y -= 8
    c.setStrokeColor(_rgb(_NAVY))
    c.setLineWidth(1.5)
    c.line(M, y, M + 180, y)
    c.setLineWidth(1)
    y -= 14

    for num, title, page_ref, anchor in _TOC_SECTIONS:
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(_rgb(_NAVY))
        c.drawString(M, y, f"{num}.")
        c.setFont("Helvetica", 8.5)
        c.setFillColor(_rgb(_DARK))
        c.drawString(M + 16, y, title)
        dots_x = M + 16 + c.stringWidth(title, "Helvetica", 8.5) + 4
        c.setFont("Helvetica", 8)
        c.setFillColor(_rgb(_GREY))
        # Ligne de points
        while dots_x < W - M - 30:
            c.drawString(dots_x, y, ".")
            dots_x += 4
        c.setFont("Helvetica", 8)
        c.setFillColor(_rgb(_GREY))
        c.drawRightString(W - M, y, page_ref)
        y -= 14

    y -= 20
    c.setStrokeColor(_rgb(_MID))
    c.line(M, y, W - M, y)
    y -= 20

    # --- Section 2 : Presentation entreprise ---
    y = _section_title(c, M, y, "2. Presentation de l'Entreprise", CW, "")
    y -= 2

    # Bloc d'identite
    sector_s = _safe(ci.sector or "N/A")
    ticker_s = _safe(ci.ticker)
    currency_s = _safe(ci.currency)

    # Sous-titre
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(_rgb(_GREY))
    c.drawString(M, y, f"{ticker_s}  —  {sector_s}  —  Devise : {currency_s}")
    y -= 14

    # Texte de presentation (genere a partir des donnees disponibles)
    company_desc = _build_company_description(ci, mkt, synthesis)
    y = _wrap(c, company_desc, M, y, CW, size=9, lh=14)
    y -= 16

    # Activites principales et positionnement
    if synthesis and synthesis.strengths:
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(_rgb(_GREY))
        c.drawString(M, y, "POINTS CLES DU MODELE D'AFFAIRES")
        y -= 16
        for s in synthesis.strengths[:3]:
            y = _bullet(c, M, y, _safe(s, 200), CW, color=_GREEN, size=8.5)
            y -= 3

    y -= 10

    # Positionnement concurrentiel
    if synthesis and synthesis.risks:
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(_rgb(_GREY))
        c.drawString(M, y, "FACTEURS DE RISQUE IDENTIFIES")
        y -= 16
        for r in synthesis.risks[:3]:
            y = _bullet(c, M, y, _safe(r, 200), CW, color=_RED, size=8.5)
            y -= 3


def _build_company_description(ci, mkt, synthesis) -> str:
    """Construit un texte de presentation a partir des donnees disponibles."""
    sector = ci.sector or "secteur non specifie"
    ticker = ci.ticker or ""
    currency = ci.currency or "USD"
    name = ci.company_name or ticker

    lines = []
    lines.append(
        f"{name} ({ticker}) est une societe cotee dans le secteur {sector}, "
        f"dont les comptes sont presentes en {currency}."
    )
    if mkt and mkt.share_price and mkt.shares_diluted:
        mktcap = mkt.share_price * mkt.shares_diluted / 1000
        lines.append(
            f"Sa capitalisation boursiere s'etablit a environ {mktcap:,.0f} Md {currency} "
            f"sur la base d'un cours de {mkt.share_price:,.2f} {currency} "
            f"et de {mkt.shares_diluted:,.0f} millions d'actions dilinees."
        )
    if synthesis and synthesis.summary:
        # Prendre les 300 premiers chars comme contexte business
        excerpt = _safe(synthesis.summary, 350)
        lines.append(excerpt)
    return " ".join(lines)


# ---------------------------------------------------------------------------
# PAGE 3 — Analyse Financiere : IS + Bilan
# ---------------------------------------------------------------------------

def _draw_page3(c, W, H, M, CW, ci, snapshot, ratios, today):
    _header_band(c, W, H, ci.company_name, "Page 3/8 — Analyse Financiere", today)
    _footer(c, W, M, today, 3)

    y = H - 56

    y = _section_title(c, M, y, "3. Analyse Financiere — Compte de Resultat", CW, "")

    # --- Tableau IS ---
    year_labels = sorted(
        snapshot.years.keys(),
        key=lambda k: (int(k.split("_")[0]), 1 if "_LTM" in k else 0)
    )[:3]
    y_labels = [k.replace("_LTM", " (LTM)") for k in year_labels]

    unit = _safe(ci.units or "M")
    headers = [f"Metrique ({unit} {ci.currency})"] + y_labels

    def _fy_val(label, field):
        fy = snapshot.years.get(label)
        if fy is None:
            return "N/A"
        v = getattr(fy, field, None)
        if v is None:
            return "N/A"
        return f"{v:,.0f}"

    def _ryr_val(label, field):
        if not ratios:
            return "N/A"
        ry = ratios.years.get(label)
        if ry is None:
            return "N/A"
        v = getattr(ry, field, None)
        if v is None:
            return "N/A"
        return f"{v:,.0f}"

    def _ryr_pct(label, field):
        if not ratios:
            return "N/A"
        ry = ratios.years.get(label)
        if ry is None:
            return "N/A"
        v = getattr(ry, field, None)
        return _p(v)

    is_rows = [
        headers,
        ["Revenue"]          + [_fy_val(lbl, "revenue") for lbl in year_labels],
        ["Gross Profit"]     + [_ryr_val(lbl, "gross_profit") for lbl in year_labels],
        ["Marge Brute"]      + [_ryr_pct(lbl, "gross_margin") for lbl in year_labels],
        ["EBITDA"]           + [_ryr_val(lbl, "ebitda") for lbl in year_labels],
        ["Marge EBITDA"]     + [_ryr_pct(lbl, "ebitda_margin") for lbl in year_labels],
        ["Net Income"]       + [_ryr_val(lbl, "net_income") for lbl in year_labels],
        ["Marge Nette"]      + [_ryr_pct(lbl, "net_margin") for lbl in year_labels],
    ]

    ncols = 1 + len(year_labels)
    first_col_w = CW * 0.38
    other_col_w = (CW - first_col_w) / max(len(year_labels), 1)
    col_widths_is = [first_col_w] + [other_col_w] * len(year_labels)

    from reportlab.lib import colors as rlc
    _navy_rl  = rlc.Color(*_NAVY)
    _white_rl = rlc.Color(*_WHITE)
    _mid_rl   = rlc.Color(*_MID)
    _light_rl = rlc.Color(*_LIGHT)
    _grey_rl  = rlc.Color(*_GREY)
    _green_rl = rlc.Color(*_GREEN)
    _dark_rl  = rlc.Color(*_DARK)

    style_is = [
        ("BACKGROUND", (0,0), (-1,0), _navy_rl),
        ("TEXTCOLOR",  (0,0), (-1,0), _white_rl),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,0), 7.5),
        ("FONTSIZE",   (0,1), (-1,-1), 8),
        ("FONTNAME",   (0,1), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",   (1,1), (-1,-1), "Helvetica"),
        ("ALIGN",      (1,0), (-1,-1), "RIGHT"),
        ("ALIGN",      (0,0), (0,-1), "LEFT"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [_white_rl, _light_rl]),
        ("TEXTCOLOR",  (0,1), (0,-1), _grey_rl),
        ("TEXTCOLOR",  (1,1), (-1,-1), _dark_rl),
        ("GRID",       (0,0), (-1,-1), 0.25, _mid_rl),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (0,-1), 6),
        ("RIGHTPADDING",  (1,0), (-1,-1), 6),
    ]
    # Mettre les marges en vert/amber
    for row_idx, row in enumerate(is_rows):
        if row[0] in ("Marge Brute", "Marge EBITDA", "Marge Nette"):
            style_is.append(("TEXTCOLOR", (1, row_idx), (-1, row_idx), _green_rl))
            style_is.append(("FONTNAME",  (1, row_idx), (-1, row_idx), "Helvetica-Bold"))

    y = _draw_table(c, is_rows, col_widths_is, style_is, M, y)
    y -= 6

    # --- Commentaire IS ---
    if ratios and ratios.years:
        latest_ry = ratios.years.get(ratios.latest_year)
        if latest_ry:
            gm = latest_ry.gross_margin
            em = latest_ry.ebitda_margin
            rg = latest_ry.revenue_growth
            comment = (
                f"Sur l'exercice {ratios.latest_year.replace('_LTM', ' (LTM)')}, "
                f"la societe affiche une marge brute de {_p(gm)}, "
                f"une marge EBITDA de {_p(em)} "
                f"et une croissance du chiffre d'affaires de {_p(rg)} "
                f"par rapport a l'exercice precedent. "
            )
            if gm is not None and gm > 0.3:
                comment += f"La marge brute superieure a 30% temoigne d'un pricing power significatif. "
            elif gm is not None and gm < 0.15:
                comment += f"La marge brute inferieure a 15% reflete une structure de couts elevee typique du secteur. "
            y = _wrap(c, comment, M, y, CW, size=8.5, lh=13)
            y -= 12

    # --- Bilan synthetique ---
    y = _section_title(c, M, y, "3.2 Bilan & Solidite Financiere", CW, "")

    # Extraire donnees bilan du dernier exercice
    last_label = year_labels[-1] if year_labels else None
    last_fy = snapshot.years.get(last_label) if last_label else None

    if last_fy:
        cash = getattr(last_fy, "cash", None)
        ltd  = getattr(last_fy, "long_term_debt", None)
        std  = getattr(last_fy, "short_term_debt", None)
        eq   = getattr(last_fy, "total_equity_yf", None)
        ta   = getattr(last_fy, "total_assets_yf", None)

        total_debt = (ltd or 0) + (std or 0)
        net_debt = total_debt - (cash or 0) if (cash is not None) else None

        bs_items = [
            ["Postes Bilan cles", f"Dernier exercice : {last_label.replace('_LTM', ' (LTM)')}"],
            ["Tresorerie & equivalents", f"{ci.currency} {_f(cash)}M" if cash else "N/A"],
            ["Dette totale (LT + CT)", f"{ci.currency} {_f(total_debt)}M" if total_debt else "N/A"],
            ["Dette nette", f"{ci.currency} {_f(net_debt)}M" if net_debt is not None else "N/A"],
            ["Capitaux propres", f"{ci.currency} {_f(eq)}M" if eq else "N/A"],
            ["Total actif", f"{ci.currency} {_f(ta)}M" if ta else "N/A"],
        ]

        style_bs = [
            ("BACKGROUND", (0,0), (-1,0), _navy_rl),
            ("TEXTCOLOR",  (0,0), (-1,0), _white_rl),
            ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0), (-1,-1), 8),
            ("FONTNAME",   (0,1), (0,-1), "Helvetica"),
            ("FONTNAME",   (1,1), (-1,-1), "Helvetica-Bold"),
            ("ALIGN",      (1,0), (-1,-1), "RIGHT"),
            ("GRID",       (0,0), (-1,-1), 0.25, _mid_rl),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [_white_rl, _light_rl]),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (0,-1), 6),
            ("RIGHTPADDING",  (1,0), (-1,-1), 6),
        ]
        bs_col_widths = [CW * 0.55, CW * 0.45]
        y = _draw_table(c, bs_items, bs_col_widths, style_bs, M, y)
        y -= 6

        # Commentaire bilan
        if net_debt is not None and cash is not None:
            if net_debt < 0:
                bs_comment = (
                    f"La societe affiche une position de tresorerie nette positive "
                    f"(Cash {_f(cash)}M, Dette totale {_f(total_debt)}M), "
                    f"soit une dette nette de {_f(abs(net_debt))}M en faveur du cash. "
                    f"Cette solidite bilancielle constitue un facteur de resilience."
                )
            else:
                bs_comment = (
                    f"La dette nette s'etablit a {_f(net_debt)}M ({ci.currency}). "
                    f"La gestion de la structure financiere merite surveillance "
                    f"au regard des flux de tresorerie operationnels."
                )
            y = _wrap(c, bs_comment, M, y, CW, size=8.5, lh=13)


# ---------------------------------------------------------------------------
# PAGE 4 — Ratios cles & Benchmark
# ---------------------------------------------------------------------------

def _draw_page4(c, W, H, M, CW, ci, yr, latest, today):
    _header_band(c, W, H, ci.company_name, "Page 4/8 — Ratios & Benchmark Sectoriel", today)
    _footer(c, W, M, today, 4)

    y = H - 56
    y = _section_title(c, M, y, "4. Ratios Cles & Benchmark Sectoriel", CW, "")

    if yr is None:
        c.setFont("Helvetica", 9)
        c.setFillColor(_rgb(_GREY))
        c.drawString(M, y, "Ratios non disponibles.")
        return

    from reportlab.lib import colors as rlc
    _navy_rl  = rlc.Color(*_NAVY)
    _white_rl = rlc.Color(*_WHITE)
    _mid_rl   = rlc.Color(*_MID)
    _light_rl = rlc.Color(*_LIGHT)
    _grey_rl  = rlc.Color(*_GREY)
    _green_rl = rlc.Color(*_GREEN)
    _amber_rl = rlc.Color(*_AMBER)
    _red_rl   = rlc.Color(*_RED)
    _dark_rl  = rlc.Color(*_DARK)

    def _interp_margin(v, good, warn):
        if v is None: return "N/A", _grey_rl
        if v >= good: return "Fort", _green_rl
        if v >= warn: return "Acceptable", _amber_rl
        return "Sous la norme", _red_rl

    def _interp_ratio_low_good(v, good, bad):
        if v is None: return "N/A", _grey_rl
        if v <= good: return "Attractif", _green_rl
        if v <= bad:  return "Moyen", _amber_rl
        return "Eleve", _red_rl

    rows_data = [
        ["Ratio", f"Valeur ({latest.replace('_LTM','')} LTM)", "Benchmark Sectoriel", "Interpretation"],
        ["P/E Ratio",      _x(yr.pe_ratio),      "15-25x (mediane)",    *_interp_ratio_low_good(yr.pe_ratio,    18, 30)[:1]],
        ["EV/EBITDA",      _x(yr.ev_ebitda),     "6-12x (secteur)",     *_interp_ratio_low_good(yr.ev_ebitda,   10, 20)[:1]],
        ["Marge Brute",    _p(yr.gross_margin),  "> 30%",               *_interp_margin(yr.gross_margin, 0.30, 0.15)[:1]],
        ["Marge EBITDA",   _p(yr.ebitda_margin), "> 15%",               *_interp_margin(yr.ebitda_margin, 0.15, 0.08)[:1]],
        ["Marge Nette",    _p(yr.net_margin),    "> 8%",                *_interp_margin(yr.net_margin, 0.08, 0.03)[:1]],
        ["ROE",            _p(yr.roe),           "> 12%",               *_interp_margin(yr.roe, 0.12, 0.05)[:1]],
        ["ROIC",           _p(yr.roic),          "> 10%",               *_interp_margin(yr.roic, 0.10, 0.04)[:1]],
        ["FCF Yield",      _p(yr.fcf_yield),     "> 4%",                *_interp_margin(yr.fcf_yield, 0.04, 0.01)[:1]],
        ["Dette N./EBITDA",_x(yr.net_debt_ebitda),"< 2.5x sain",        *_interp_ratio_low_good(yr.net_debt_ebitda, 2.0, 4.0)[:1]],
        ["Current Ratio",  _n(yr.current_ratio), "> 1.5",               "Fort" if (yr.current_ratio or 0) >= 1.5 else ("Acceptable" if (yr.current_ratio or 0) >= 1.0 else "Insuffisant")],
        ["Croissance CA",  _p(yr.revenue_growth),"Secteur spec.",       "Elevee" if (yr.revenue_growth or 0) > 0.10 else ("Moderee" if (yr.revenue_growth or 0) > 0.03 else "Faible")],
        ["DSO (jours)",    _n(yr.dso, 0),        "< 60j",               "Sain" if yr.dso and yr.dso < 60 else ("Correct" if yr.dso and yr.dso < 90 else "A surveiller")],
    ]

    cw1 = CW * 0.22
    cw2 = CW * 0.22
    cw3 = CW * 0.26
    cw4 = CW * 0.30
    col_widths_r = [cw1, cw2, cw3, cw4]

    style_r = [
        ("BACKGROUND", (0,0), (-1,0), _navy_rl),
        ("TEXTCOLOR",  (0,0), (-1,0), _white_rl),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 8),
        ("FONTNAME",   (0,1), (0,-1), "Helvetica"),
        ("FONTNAME",   (1,1), (1,-1), "Helvetica-Bold"),
        ("ALIGN",      (1,0), (2,-1), "CENTER"),
        ("ALIGN",      (3,0), (3,-1), "LEFT"),
        ("ALIGN",      (0,0), (0,-1), "LEFT"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [_white_rl, _light_rl]),
        ("GRID",       (0,0), (-1,-1), 0.25, _mid_rl),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (0,-1), 6),
    ]

    # Coloration colonne "Interpretation" par texte
    interp_colors = {
        "Fort": _green_rl, "Attractif": _green_rl, "Elevee": _green_rl, "Sain": _green_rl,
        "Acceptable": _amber_rl, "Moyen": _amber_rl, "Moderee": _amber_rl, "Correct": _amber_rl,
        "Sous la norme": _red_rl, "Eleve": _red_rl, "Faible": _red_rl, "Insuffisant": _red_rl,
        "A surveiller": _amber_rl,
    }
    for i, row in enumerate(rows_data[1:], 1):
        interp_val = row[3] if len(row) > 3 else ""
        col_r = interp_colors.get(interp_val, _dark_rl)
        style_r.append(("TEXTCOLOR", (3, i), (3, i), col_r))
        style_r.append(("FONTNAME",  (3, i), (3, i), "Helvetica-Bold"))

    y = _draw_table(c, rows_data, col_widths_r, style_r, M, y)
    y -= 16

    # Indicateurs de risque (Altman Z + Beneish M)
    y = _section_title(c, M, y, "4.2 Indicateurs de Risque Comptable", CW, "")

    if yr.altman_z is not None:
        z = yr.altman_z
        z_col = _GREEN if z >= 2.99 else (_RED if z < 1.81 else _AMBER)
        z_lbl = "SAIN (Z > 2.99)" if z >= 2.99 else ("ZONE GRISE (1.81 < Z < 2.99)" if z >= 1.81 else "DETRESSE (Z < 1.81)")
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(_rgb(_GREY))
        c.drawString(M, y, "Altman Z-Score :")
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(_rgb(z_col))
        c.drawString(M + 110, y, f"{z:.2f}")
        c.setFont("Helvetica", 8.5)
        c.setFillColor(_rgb(z_col))
        c.drawString(M + 145, y, f"→  {z_lbl}")
        y -= 18

    if yr.beneish_m is not None:
        m = yr.beneish_m
        m_col = _RED if m > -2.22 else _GREEN
        m_lbl = "RISQUE DE MANIPULATION COMPTABLE DETECTE" if m > -2.22 else "Aucun signal de manipulation"
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(_rgb(_GREY))
        c.drawString(M, y, "Beneish M-Score :")
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(_rgb(m_col))
        c.drawString(M + 110, y, f"{m:.3f}")
        c.setFont("Helvetica", 8.5)
        c.setFillColor(_rgb(m_col))
        c.drawString(M + 145, y, f"→  {m_lbl}")
        y -= 18


# ---------------------------------------------------------------------------
# PAGE 5 — Valorisation DCF & Multiples
# ---------------------------------------------------------------------------

def _draw_page5(c, W, H, M, CW, ci, mkt, yr, synthesis, today):
    _header_band(c, W, H, ci.company_name, "Page 5/8 — Valorisation DCF & Multiples", today)
    _footer(c, W, M, today, 5)

    y = H - 56
    y = _section_title(c, M, y, "5. Valorisation — DCF & Hypotheses", CW, "")

    from reportlab.lib import colors as rlc
    _navy_rl  = rlc.Color(*_NAVY)
    _white_rl = rlc.Color(*_WHITE)
    _mid_rl   = rlc.Color(*_MID)
    _light_rl = rlc.Color(*_LIGHT)
    _grey_rl  = rlc.Color(*_GREY)
    _dark_rl  = rlc.Color(*_DARK)

    # Tableau hypotheses DCF
    cur  = mkt.share_price if mkt else None
    wacc = mkt.wacc if mkt else None
    tg   = mkt.terminal_growth if mkt else None
    beta = mkt.beta_levered if mkt else None
    rf   = mkt.risk_free_rate if mkt else None
    erp  = mkt.erp if mkt else None
    ke   = (rf + beta * erp) if (rf and beta and erp) else None
    kd   = mkt.cost_of_debt_pretax if mkt else None
    we   = mkt.weight_equity if mkt else None
    wd   = mkt.weight_debt if mkt else None
    tax  = mkt.tax_rate if mkt else None

    dcf_rows = [
        ["Parametre DCF",          "Valeur",           "Commentaire"],
        ["Cours actuel",           f"{cur:,.2f} {ci.currency}" if cur else "N/A", "Reference marche"],
        ["WACC",                   _p(wacc),            "Cout moyen pondere du capital"],
        ["Taux de croissance terminal", _p(tg),         "Croissance perpetuellement durable"],
        ["Horizon de projection",  "5 ans",             "Standard IB"],
        ["Beta (leve)",            _n(beta),            "Sensibilite marche (risque systemique)"],
        ["Taux sans risque (Rf)",  _p(rf),              "OAT 10 ans / UST 10 ans"],
        ["Prime de risque (ERP)",  _p(erp),             "Damodaran 2025"],
        ["Cout des fonds propres (Ke)", _p(ke),         "CAPM : Rf + Beta x ERP"],
        ["Cout de la dette (Kd)",  _p(kd),              "Avant impot"],
        ["Taux d'imposition",      _p(tax),             "Taux effectif"],
        ["Ponderation FP / Dette", f"{_p(we)} / {_p(wd)}", "Structure de capital observee"],
    ]

    cw_d = [CW * 0.35, CW * 0.20, CW * 0.45]
    style_dcf = [
        ("BACKGROUND", (0,0), (-1,0), _navy_rl),
        ("TEXTCOLOR",  (0,0), (-1,0), _white_rl),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 8),
        ("FONTNAME",   (0,1), (0,-1), "Helvetica"),
        ("FONTNAME",   (1,1), (1,-1), "Helvetica-Bold"),
        ("ALIGN",      (1,0), (1,-1), "CENTER"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [_white_rl, _light_rl]),
        ("GRID",       (0,0), (-1,-1), 0.25, _mid_rl),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (0,-1), 6),
        ("TEXTCOLOR",  (2,1), (2,-1), _grey_rl),
    ]
    y = _draw_table(c, dcf_rows, cw_d, style_dcf, M, y)
    y -= 8

    # Formule WACC explicite
    if ke and kd and we and wd and tax:
        c.setFillColor(_rgb(_LIGHT))
        c.setStrokeColor(_rgb(_MID))
        formula_h = 32
        c.roundRect(M, y - formula_h, CW, formula_h, 3, fill=1, stroke=1)
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(_rgb(_GREY))
        c.drawString(M + 8, y - 11, "FORMULE WACC  (CAPM)")
        c.setFont("Helvetica", 8)
        c.setFillColor(_rgb(_DARK))
        ke_formula = (f"Ke = {_p(rf)} + {_n(beta)} x {_p(erp)} = {_p(ke)}  |  "
                      f"WACC = {_p(we)} x {_p(ke)} + {_p(wd)} x {_p(kd)} x (1 - {_p(tax)}) = {_p(wacc)}")
        c.drawString(M + 8, y - 24, ke_formula[:100])
        y -= formula_h + 12

    # Analyse par multiples
    y = _section_title(c, M, y, "5.2 Analyse par Multiples Comparables", CW, "")

    multiples_text = (
        f"En appliquant les multiples medians du secteur {_safe(ci.sector or 'comparable')}, "
    )
    if yr and yr.ev_ebitda:
        if yr.ev_ebitda > 20:
            multiples_text += (
                f"l'EV/EBITDA de {_x(yr.ev_ebitda)} est significativement superieur a la mediane sectorielle "
                f"(generalement 8-15x pour ce secteur). "
                f"Cette prime de valorisation integre les perspectives de croissance future "
                f"et la qualite du modele d'affaires. "
            )
        else:
            multiples_text += (
                f"l'EV/EBITDA de {_x(yr.ev_ebitda)} est cohérent avec la norme sectorielle. "
                f"Le titre semble correctement valorise sur une base de multiples comparables. "
            )
    if yr and yr.pe_ratio and yr.pe_ratio > 0:
        multiples_text += (
            f"Le P/E de {_x(yr.pe_ratio)} reflete les attentes du marche "
            f"{'sur la croissance beneficiaire.' if yr.pe_ratio > 25 else 'et reste dans la norme historique.'}"
        )

    y = _wrap(c, multiples_text, M, y, CW, size=9, lh=14)


# ---------------------------------------------------------------------------
# PAGE 6 — Scenarios de Valorisation
# ---------------------------------------------------------------------------

def _draw_page6(c, W, H, M, CW, ci, mkt, synthesis, today):
    _header_band(c, W, H, ci.company_name, "Page 6/8 — Scenarios de Valorisation", today)
    _footer(c, W, M, today, 6)

    y = H - 56
    y = _section_title(c, M, y, "6. Scenarios de Valorisation — Distribution Triangulaire", CW, "")

    cur = mkt.share_price if mkt else None
    reco_fr = "N/A"
    if synthesis:
        reco_fr = {"BUY": "ACHETER", "SELL": "VENDRE", "HOLD": "CONSERVER"}.get(
            synthesis.recommendation, synthesis.recommendation or "N/A")

    scenarios = []
    if synthesis:
        scenarios = [
            ("BULL CASE",  synthesis.target_bull, _GREEN,
             "Acceleration de la croissance, expansion des marges, "
             "catalyseurs sectoriels positifs se materialisant. "
             "Execution parfaite du plan strategique. Multiples en re-rating."),
            ("BASE CASE",  synthesis.target_base, _AMBER,
             "Croissance moderee en ligne avec les previsions consensus. "
             "Marges stables ou en legere amelioration. "
             "Valorisation actuelle proche de la juste valeur intrinsèque."),
            ("BEAR CASE",  synthesis.target_bear, _RED,
             "Intensification de la concurrence, compression des marges, "
             "deterioration du contexte macro. "
             "La valorisation actuelle ne price pas ce scenario."),
        ]

    scen_w = (CW - 16) / 3

    for idx, (label, val, col, narrative) in enumerate(scenarios):
        sx = M + idx * (scen_w + 8)
        sy = y
        box_h = 220

        # Boite scenario
        c.setFillColor(_rgb(_LIGHT))
        c.setStrokeColor(_rgb(col))
        c.setLineWidth(1.5)
        c.roundRect(sx, sy - box_h, scen_w, box_h, 3, fill=1, stroke=1)
        c.setLineWidth(1)

        # Header bande coloree
        c.setFillColor(_rgb(col))
        c.roundRect(sx, sy - 28, scen_w, 28, 3, fill=1, stroke=0)

        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(_rgb(_WHITE))
        c.drawCentredString(sx + scen_w / 2, sy - 17, label)

        # Prix cible
        val_s = f"{val:,.0f}" if val else "—"
        c.setFont("Helvetica-Bold", 28)
        c.setFillColor(_rgb(col))
        c.drawCentredString(sx + scen_w / 2, sy - 66, val_s)

        c.setFont("Helvetica", 8)
        c.setFillColor(_rgb(_GREY))
        c.drawCentredString(sx + scen_w / 2, sy - 78, ci.currency)

        # Upside/downside
        if val and cur:
            upside = (val - cur) / cur * 100
            arrow  = "+" if upside >= 0 else ""
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(_rgb(_GREEN if upside >= 0 else _RED))
            c.drawCentredString(sx + scen_w / 2, sy - 95, f"{arrow}{upside:.1f}%")
            c.setFont("Helvetica", 7)
            c.setFillColor(_rgb(_GREY))
            c.drawCentredString(sx + scen_w / 2, sy - 107, f"vs cours actuel {cur:,.2f}")

        # Narratif
        _wrap(c, narrative, sx + 8, sy - 125, scen_w - 16, size=7.5, lh=12)

        # Barre probabilite
        probs = [0.25, 0.55, 0.20]
        prob_w = int((scen_w - 16) * probs[idx])
        c.setFillColor(_rgb(_MID))
        c.rect(sx + 8, sy - box_h + 16, scen_w - 16, 4, fill=1, stroke=0)
        c.setFillColor(_rgb(col))
        c.rect(sx + 8, sy - box_h + 16, prob_w, 4, fill=1, stroke=0)
        c.setFont("Helvetica", 6.5)
        c.setFillColor(_rgb(_GREY))
        c.drawCentredString(sx + scen_w / 2, sy - box_h + 8, f"Prob. estimee : {int(probs[idx]*100)}%")

    y -= 240

    # Recommandation finale
    c.setStrokeColor(_rgb(_MID))
    c.line(M, y, W - M, y)
    y -= 20

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(_rgb(_GREY))
    c.drawString(M, y, "RECOMMANDATION FINALE :")
    reco_col_map = {"ACHETER": _GREEN, "VENDRE": _RED}
    reco_col = reco_col_map.get(reco_fr, _AMBER)
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(_rgb(reco_col))
    reco_x = M + c.stringWidth("RECOMMANDATION FINALE :  ", "Helvetica-Bold", 9)
    c.drawString(reco_x, y - 2, reco_fr)
    y -= 22

    if synthesis and synthesis.summary:
        # 2eme moitie du summary comme conclusion
        summary = _safe(synthesis.summary, 600)
        midpoint = len(summary) // 2
        conclusion = summary[midpoint:].strip()
        if conclusion:
            y = _wrap(c, conclusion, M, y, CW, size=9, lh=14)


# ---------------------------------------------------------------------------
# PAGE 7 — Sentiment de marche & Avocat du Diable
# ---------------------------------------------------------------------------

def _draw_page7(c, W, H, M, CW, ci, sentiment, devil, qa_python, synthesis, today):
    _header_band(c, W, H, ci.company_name,
                 "Page 7/8 — Sentiment & Avocat du Diable", today)
    _footer(c, W, M, today, 7)

    y = H - 56
    half = (CW - 14) / 2

    # --- Colonne gauche : Sentiment ---
    col_l = M
    col_r = M + half + 14

    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(_rgb(_NAVY))
    c.drawString(col_l, y, "7. SENTIMENT DE MARCHE (FinBERT)")
    tw = c.stringWidth("7. SENTIMENT DE MARCHE (FinBERT)", "Helvetica-Bold", 8)
    c.setStrokeColor(_rgb(_MID))
    c.line(col_l + tw + 6, y + 3, col_l + half, y + 3)
    y -= 18

    y_l = y

    if sentiment:
        sent_col = _GREEN if sentiment.score > 0.1 else (_RED if sentiment.score < -0.1 else _AMBER)
        c.setFont("Helvetica-Bold", 22)
        c.setFillColor(_rgb(sent_col))
        c.drawString(col_l, y_l, _safe(sentiment.label).upper())
        y_l -= 18

        c.setFont("Helvetica", 8)
        c.setFillColor(_rgb(_GREY))
        score_line = (f"Score : {sentiment.score:+.3f}  |  "
                      f"Confiance : {sentiment.confidence:.0%}  |  "
                      f"{sentiment.articles_analyzed} articles analyses")
        c.drawString(col_l, y_l, score_line)
        y_l -= 16

        # Barre sentiment
        bar_w = half - 10
        mid_x = col_l + bar_w / 2
        c.setFillColor(_rgb(_MID))
        c.rect(col_l, y_l, bar_w, 5, fill=1, stroke=0)
        # Position score (-1 a +1) -> largeur
        score_pos = (sentiment.score + 1) / 2  # 0 a 1
        c.setFillColor(_rgb(sent_col))
        c.rect(col_l, y_l, int(bar_w * score_pos), 5, fill=1, stroke=0)
        c.setFillColor(_rgb(_GREY))
        c.setFont("Helvetica", 6)
        c.drawString(col_l, y_l - 8, "Tres negatif")
        c.drawRightString(col_l + bar_w, y_l - 8, "Tres positif")
        y_l -= 22

        if hasattr(sentiment, "summary") and sentiment.summary:
            y_l = _wrap(c, _safe(sentiment.summary, 350), col_l, y_l, half, size=8.5, lh=13)
    else:
        c.setFont("Helvetica", 9)
        c.setFillColor(_rgb(_GREY))
        c.drawString(col_l, y_l, "Sentiment non disponible.")
        y_l -= 14

    y_l -= 16

    # QA
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(_rgb(_NAVY))
    c.drawString(col_l, y_l, "VALIDATION QA — PIPELINE FINSIGHT IA")
    tw2 = c.stringWidth("VALIDATION QA — PIPELINE FINSIGHT IA", "Helvetica-Bold", 8)
    c.setStrokeColor(_rgb(_MID))
    c.line(col_l + tw2 + 6, y_l + 3, col_l + half, y_l + 3)
    y_l -= 18

    if qa_python:
        status_col = _GREEN if qa_python.passed else _RED
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(_rgb(status_col))
        c.drawString(col_l, y_l,
            f"{'VALIDE' if qa_python.passed else 'ECHEC'}  —  Score : {qa_python.qa_score:.0%}")
        y_l -= 16
        for fl in qa_python.flags[:5]:
            sym_col = _RED if fl.level == "ERROR" else (_AMBER if fl.level == "WARNING" else _GREEN)
            sym = "ERREUR" if fl.level == "ERROR" else ("AVERT." if fl.level == "WARNING" else "OK")
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(_rgb(sym_col))
            c.drawString(col_l, y_l, f"[{sym}]")
            c.setFont("Helvetica", 7.5)
            c.setFillColor(_rgb(_DARK))
            y_l = _wrap(c, _safe(fl.message, 100), col_l + 50, y_l, half - 52,
                       size=7.5, lh=11) - 2

    # --- Colonne droite : Avocat du Diable ---
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(_rgb(_NAVY))
    c.drawString(col_r, y, "8. AVOCAT DU DIABLE — THESE INVERSE")
    tw3 = c.stringWidth("8. AVOCAT DU DIABLE — THESE INVERSE", "Helvetica-Bold", 8)
    c.setStrokeColor(_rgb(_MID))
    c.line(col_r + tw3 + 6, y + 3, col_r + half, y + 3)
    y_r = y - 18

    if devil:
        delta = devil.conviction_delta
        delta_col = _RED if delta < -0.2 else (_GREEN if delta > 0.2 else _AMBER)
        solid = ("These fragile — arguments contra solides" if delta < -0.2
                 else ("These robuste malgre la these inverse" if delta > 0.2
                       else "These moderement solide"))

        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(_rgb(_GREY))
        c.drawString(col_r, y_r, f"These principale : {_safe(devil.original_reco, 20)}")
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(_rgb(delta_col))
        c.drawString(col_r + half - c.stringWidth(
            f"These inverse : {_safe(devil.counter_reco, 20)}", "Helvetica-Bold", 9),
            y_r, f"These inverse : {_safe(devil.counter_reco, 20)}")
        y_r -= 14

        # Delta conviction
        c.setFillColor(_rgb(_LIGHT))
        c.setStrokeColor(_rgb(_MID))
        c.roundRect(col_r, y_r - 22, half, 22, 2, fill=1, stroke=1)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(_rgb(delta_col))
        c.drawString(col_r + 8, y_r - 14,
            f"Delta conviction : {delta:+.2f}  —  {solid}")
        y_r -= 30

        if devil.counter_thesis:
            c.setFont("Helvetica-Bold", 7.5)
            c.setFillColor(_rgb(_GREY))
            c.drawString(col_r, y_r, "THESE INVERSE :")
            y_r -= 13
            y_r = _wrap(c, _safe(devil.counter_thesis, 500), col_r, y_r, half,
                       size=8.5, lh=13)
            y_r -= 12

        if devil.key_assumptions:
            c.setFont("Helvetica-Bold", 7.5)
            c.setFillColor(_rgb(_AMBER))
            c.drawString(col_r, y_r, "HYPOTHESES FRAGILES IDENTIFIEES :")
            y_r -= 13
            for a in devil.key_assumptions[:3]:
                c.setFont("Helvetica-Bold", 8.5)
                c.setFillColor(_rgb(_AMBER))
                c.drawString(col_r, y_r, "?")
                c.setFont("Helvetica", 8.5)
                c.setFillColor(_rgb(_DARK))
                y_r = _wrap(c, _safe(a, 200), col_r + 12, y_r, half - 14,
                           size=8.5, lh=12) - 4
    else:
        c.setFont("Helvetica", 9)
        c.setFillColor(_rgb(_GREY))
        c.drawString(col_r, y_r, "Analyse contradictoire non disponible.")


# ---------------------------------------------------------------------------
# PAGE 8 — Conditions d'Invalidation & Disclaimer
# ---------------------------------------------------------------------------

def _draw_page8(c, W, H, M, CW, ci, synthesis, today):
    _header_band(c, W, H, ci.company_name,
                 "Page 8/8 — Invalidation & Disclaimer", today)
    _footer(c, W, M, today, 8)

    y = H - 56
    y = _section_title(c, M, y, "9. Conditions d'Invalidation de la These", CW, "")

    if synthesis and synthesis.invalidation_conditions:
        conds_text = _safe(synthesis.invalidation_conditions, 800)
        # Split par points comme liste si possible
        if ". " in conds_text:
            items = [s.strip() for s in conds_text.split(". ") if s.strip()]
            for item in items[:6]:
                y = _bullet(c, M, y, item + ".", CW, color=_AMBER, size=9, lh=14) - 4
        else:
            y = _wrap(c, conds_text, M, y, CW, size=9, lh=14)
    else:
        generic_conds = [
            ("Revision a la baisse des resultats operationnels superieure a 15% "
             "sur 2 trimestres consecutifs."),
            ("Degradation significative du bilan : dette nette/EBITDA depassant 4x "
             "sans plan de desendettement credible."),
            ("Perte de pricing power confirmee : contraction des marges brutes "
             "superieure a 5 points sur 12 mois."),
            ("Changement reglementaire majeur impactant le coeur de metier "
             "(fiscalite, regulation sectorielle, sanctions)."),
            ("Annonce de catalyseurs positifs majeurs non integres dans le scenario "
             "Bull Case : revision a la hausse requise."),
        ]
        for cond in generic_conds:
            y = _bullet(c, M, y, cond, CW, color=_AMBER, size=9, lh=14) - 4

    y -= 20

    # Methodologie
    y = _section_title(c, M, y, "Methodologie & Sources", CW, "")

    meth = (
        "Cette analyse est produite par FinSight IA, un pipeline multi-agents "
        "basé sur Claude (Anthropic). "
        "Données financieres : Yahoo Finance (source principale), "
        "Financial Modeling Prep, Finnhub. "
        "Calcul des ratios selon les normes IFRS/US GAAP. "
        "Valorisation : DCF (WACC CAPM + taux de croissance terminal) "
        "et multiples sectoriels (EV/EBITDA, P/E, P/S). "
        "Sentiment de marche : FinBERT (ProsusAI, modele NLP entraine sur corpus financier). "
        "Validation QA en deux passes : verifications deterministes (Python) "
        "et editoriales (LLM Haiku). "
        "La procedure Avocat du Diable génère systematiquement une these inverse "
        "pour challenger la recommandation principale et identifier les hypotheses fragiles."
    )
    y = _wrap(c, meth, M, y, CW, size=8.5, lh=13)
    y -= 24

    # Disclaimer box
    y = _section_title(c, M, y, "Avertissement Legal (Important)", CW, "")

    disc_h = 130
    c.setFillColor(_rgb(_LIGHT))
    c.setStrokeColor(_rgb((0.8, 0.8, 0.8)))
    c.roundRect(M, y - disc_h, CW, disc_h, 4, fill=1, stroke=1)

    disclaimer = (
        "IMPORTANT — Ce rapport est produit a titre informatif uniquement "
        "et ne constitue en aucun cas un conseil en investissement, "
        "une recommandation d'achat ou de vente de valeurs mobilieres, "
        "ni une offre ou solicitation d'offre pour l'achat ou la vente "
        "de tout instrument financier. "
        "Les informations sont issues de sources jugees fiables "
        "mais leur exactitude et exhaustivite ne sont pas garanties. "
        "Les performances passees ne prejudgent pas des performances futures. "
        "L'investissement en bourse comporte des risques de perte en capital. "
        "Tout investisseur doit effectuer sa propre analyse et consulter "
        "un conseiller financier agree avant toute decision d'investissement. "
        "FinSight IA decline toute responsabilite quant aux decisions "
        "prises sur la base de ce document."
    )
    _wrap(c, disclaimer, M + 10, y - 14, CW - 20,
          font="Helvetica", size=7.5, lh=12, color=_GREY)

    y -= disc_h + 18

    # Signature finale
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(_rgb(_NAVY))
    c.drawString(M, y, "FINSIGHT IA")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(_rgb(_GREY))
    c.drawString(M + 72, y,
        f"Rapport genere le {today}  |  Confidentiel  |  Usage interne uniquement")


# ---------------------------------------------------------------------------
# Alias public
# ---------------------------------------------------------------------------

def save_pdf(snapshot, ratios, synthesis, sentiment, qa_python, devil) -> Path:
    return generate_pdf(snapshot, ratios, synthesis, sentiment, qa_python, devil)
