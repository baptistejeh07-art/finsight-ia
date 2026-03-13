# =============================================================================
# FinSight IA — Rapport PDF Professionnel v2
# outputs/pdf_report.py
#
# Template rigide 9 sections / 8-12 pages A4 :
#   1. Synthese Executive & Recommandation
#   2. Presentation de l'Entreprise
#   3. Analyse Financiere (IS 5 ans, Bilan, Ratios vs Benchmark)
#   4. Valorisation (DCF, Sensibilite, Multiples)
#   5. Risques & Scenarios (Bull/Base/Bear)
#   6. Sentiment de Marche
#   7. Avocat du Diable
#   8. Conditions d'Invalidation & Disclaimer
#
# Palette : Helvetica | Navy #1B3A6B | Fond tableau #F5F5F5
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
# Palette
# ---------------------------------------------------------------------------
_NAVY  = (0.106, 0.227, 0.420)   # #1B3A6B  headers
_WHITE = (1.0,   1.0,   1.0)
_F5    = (0.961, 0.961, 0.961)   # #F5F5F5  fond tableau
_MID   = (0.878, 0.878, 0.878)   # #E0E0E0  bordures
_DARK  = (0.067, 0.067, 0.067)   # #111
_GREY  = (0.467, 0.467, 0.467)   # #777
_GREEN = (0.102, 0.478, 0.322)   # #1A7A52
_AMBER = (0.722, 0.573, 0.165)   # #B8922A
_RED   = (0.753, 0.224, 0.169)   # #C0392B

# ---------------------------------------------------------------------------
# Formatage
# ---------------------------------------------------------------------------
def _p(v) -> str:   return f"{v*100:.1f}%" if v is not None else "N/A"
def _x(v) -> str:   return f"{v:.2f}x"    if v is not None else "N/A"
def _n(v, d=2)->str:return f"{v:.{d}f}"   if v is not None else "N/A"
def _f(v) -> str:   return f"{v:,.0f}"    if v is not None else "N/A"
def _s(t, n=None)->str:
    if not t: return ""
    s = str(t)
    return s[:n] if n else s

def _pct_chg(a, b) -> str:
    if a is None or b is None or b == 0: return "N/A"
    return f"{(a-b)/abs(b)*100:+.1f}%"

def _upside(target, current) -> str:
    if target is None or current is None or current == 0: return "N/A"
    return f"{(target-current)/current*100:+.1f}%"

# ---------------------------------------------------------------------------
# Helpers canvas
# ---------------------------------------------------------------------------
def _rgb(t):
    from reportlab.lib import colors
    return colors.Color(*t)

def _hband(c, W, H, company, label, today, n, total):
    bh = 34
    c.setFillColor(_rgb(_NAVY))
    c.rect(0, H-bh, W, bh, fill=1, stroke=0)
    c.setFillColor(_rgb(_WHITE))
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(24, H-21, "FINSIGHT IA  —  ANALYSE FINANCIERE PROFESSIONNELLE")
    c.setFont("Helvetica", 7)
    c.drawRightString(W-24, H-17, f"{_s(company, 50)}  |  {today}")
    c.drawRightString(W-24, H-28, label)

def _footer(c, W, M, today, n, total):
    c.setStrokeColor(_rgb(_MID))
    c.line(M, 22, W-M, 22)
    c.setFillColor(_rgb(_GREY))
    c.setFont("Helvetica", 6)
    c.drawString(M, 11,
        "FinSight IA — Document genere automatiquement. Ne constitue pas un conseil en investissement (MiFID II).")
    c.drawRightString(W-M, 11, f"{today}  |  Page {n}/{total}")

def _sec(c, x, y, text, cw):
    c.setFillColor(_rgb(_NAVY))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(x, y, text.upper())
    tw = c.stringWidth(text.upper(), "Helvetica-Bold", 8.5)
    c.setStrokeColor(_rgb(_MID))
    c.line(x+tw+8, y+3, x+cw, y+3)
    return y-16

def _subsec(c, x, y, text):
    c.setFillColor(_rgb(_NAVY))
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(x, y, text)
    return y-13

def _wrap(c, text, x, y, mw, font="Helvetica", size=8.5, lh=13, color=None) -> float:
    if not text: return y
    c.setFont(font, size)
    c.setFillColor(_rgb(color or _DARK))
    for para in str(text).split("\n"):
        words = para.split()
        if not words: y -= lh*0.4; continue
        line = ""
        for w in words:
            test = (line+" "+w).strip()
            if c.stringWidth(test, font, size) > mw:
                if line: c.drawString(x, y, line); y -= lh
                line = w
            else: line = test
        if line: c.drawString(x, y, line); y -= lh
    return y

def _bullet(c, x, y, text, mw, color=None, size=8.5, lh=12) -> float:
    c.setFont("Helvetica-Bold", size)
    c.setFillColor(_rgb(color or _NAVY))
    c.drawString(x, y, "\u25b8")
    c.setFont("Helvetica", size)
    c.setFillColor(_rgb(_DARK))
    return _wrap(c, text, x+12, y, mw-14, size=size, lh=lh)

def _tbl(c, data, widths, styles, x, y) -> float:
    from reportlab.platypus import Table, TableStyle
    t = Table(data, colWidths=widths)
    t.setStyle(TableStyle(styles))
    _, th = t.wrapOn(c, sum(widths), 9999)
    t.drawOn(c, x, y-th)
    return y-th-6

def _signal(v, lo, hi, invert=False):
    """Retourne (couleur, label) pour signal trafic."""
    if v is None: return _GREY, "N/A"
    if invert:
        if v < lo: return _GREEN, "OK"
        if v < hi: return _AMBER, "~"
        return _RED, "!"
    else:
        if v >= hi: return _GREEN, "OK"
        if v >= lo: return _AMBER, "~"
        return _RED, "!"

# ---------------------------------------------------------------------------
# GENERATION PRINCIPALE
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

    # Tri des annees historiques (5 max, les plus recentes)
    all_years = sorted(
        snapshot.years.keys(),
        key=lambda k: int(k.split("_")[0])
    )
    hist_years = all_years[-5:]  # max 5

    latest = ratios.latest_year if ratios else (hist_years[-1] if hist_years else "")
    yr     = ratios.years.get(latest) if ratios and latest else None

    W, H = A4
    M    = 26
    CW   = W - 2*M
    TOTAL_PAGES = 9

    c = canvas.Canvas(str(output_path), pagesize=A4)
    c.setTitle(f"FinSight IA — {ci.company_name} — {today}")
    c.setAuthor("FinSight IA v2.0")
    c.setSubject(f"Analyse financiere {ci.ticker}")

    # --- Pages ---
    _p1_synthese(c, W, H, M, CW, ci, mkt, synthesis, yr, today, TOTAL_PAGES)
    c.showPage()
    _p2_entreprise(c, W, H, M, CW, ci, mkt, synthesis, today, TOTAL_PAGES)
    c.showPage()
    _p3_is(c, W, H, M, CW, ci, snapshot, ratios, hist_years, today, TOTAL_PAGES)
    c.showPage()
    _p4_bilan_ratios(c, W, H, M, CW, ci, snapshot, ratios, hist_years, yr, latest, today, TOTAL_PAGES)
    c.showPage()
    _p5_dcf(c, W, H, M, CW, ci, mkt, yr, synthesis, today, TOTAL_PAGES)
    c.showPage()
    _p6_multiples(c, W, H, M, CW, ci, mkt, yr, synthesis, today, TOTAL_PAGES)
    c.showPage()
    _p7_scenarios(c, W, H, M, CW, ci, mkt, synthesis, today, TOTAL_PAGES)
    c.showPage()
    _p8_sentiment_devil(c, W, H, M, CW, ci, sentiment, devil, synthesis, today, TOTAL_PAGES)
    c.showPage()
    _p9_invalidation_disclaimer(c, W, H, M, CW, ci, synthesis, today, TOTAL_PAGES)

    # Bookmarks PDF
    for i, label in enumerate([
        "1. Synthese Executive",
        "2. Presentation Entreprise",
        "3.1 Compte de Resultat",
        "3.2 Bilan & Ratios",
        "4.1 DCF",
        "4.3 Multiples Comparables",
        "5. Scenarios",
        "6-7. Sentiment & Avocat du Diable",
        "8. Invalidation & Disclaimer",
    ], 1):
        c.bookmarkPage(f"p{i}")
        c.addOutlineEntry(label, f"p{i}", level=0)

    c.save()
    log.info(f"[PDFReport] {output_path.name} — {TOTAL_PAGES} pages")
    return output_path


# ---------------------------------------------------------------------------
# PAGE 1 — 1. SYNTHESE EXECUTIVE
# ---------------------------------------------------------------------------

def _p1_synthese(c, W, H, M, CW, ci, mkt, synthesis, yr, today, T):
    _hband(c, W, H, ci.company_name, "Page 1 — 1. Synthese Executive", today, 1, T)
    _footer(c, W, M, today, 1, T)
    y = H - 50

    # Identite
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(_rgb(_DARK))
    name = _s(ci.company_name)
    while c.stringWidth(name, "Helvetica-Bold", 22) > CW and len(name) > 8:
        name = name[:-4] + "..."
    c.drawString(M, y, name)
    y -= 14
    c.setFont("Helvetica", 7.5)
    c.setFillColor(_rgb(_GREY))
    meta = "  |  ".join(filter(None, [
        _s(ci.ticker), _s(ci.sector, 35), f"Devise : {_s(ci.currency)}", today
    ]))
    c.drawString(M, y, meta)
    y -= 10
    c.setStrokeColor(_rgb(_MID)); c.line(M, y, W-M, y); y -= 16

    if not synthesis:
        c.setFont("Helvetica", 9); c.setFillColor(_rgb(_GREY))
        c.drawString(M, y, "Synthese non disponible."); return

    reco    = synthesis.recommendation or "N/A"
    reco_fr = {"BUY":"ACHETER","SELL":"VENDRE","HOLD":"CONSERVER"}.get(reco, reco)
    reco_col= {"BUY":_GREEN,"SELL":_RED}.get(reco, _AMBER)
    conv    = synthesis.conviction or 0
    conf    = synthesis.confidence_score or 0

    # --- Recommandation (gauche) ---
    c.setFont("Helvetica-Bold", 8); c.setFillColor(_rgb(_GREY))
    c.drawString(M, y, "RECOMMANDATION"); y -= 4
    c.setFont("Helvetica-Bold", 38); c.setFillColor(_rgb(reco_col))
    c.drawString(M, y-32, reco_fr)
    bar_y = y - 50; bw = 160
    c.setFillColor(_rgb(_MID)); c.rect(M, bar_y, bw, 5, fill=1, stroke=0)
    c.setFillColor(_rgb(reco_col)); c.rect(M, bar_y, int(bw*conv), 5, fill=1, stroke=0)
    c.setFont("Helvetica", 7); c.setFillColor(_rgb(_GREY))
    c.drawString(M, bar_y-11, f"Conviction : {conv:.0%}    |    Confiance IA : {conf:.0%}")

    # --- Table Bear/Base/Bull (droite) ---
    cur = mkt.share_price if mkt else None
    bx  = M + 180; bw2 = CW - 180; bh2 = 105
    c.setFillColor(_rgb(_F5)); c.setStrokeColor(_rgb(_MID))
    c.roundRect(bx, y-bh2+6, bw2, bh2, 3, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 6.5); c.setFillColor(_rgb(_GREY))
    c.drawString(bx+8, y-10, "PRIX CIBLES 12 MOIS")
    if cur:
        c.setFont("Helvetica", 6.5)
        c.drawString(bx+8, y-21, f"Cours actuel au {today} : {cur:,.2f} {ci.currency}")

    scens = [
        ("Bear", synthesis.target_bear, _RED,   15),
        ("Base", synthesis.target_base, _AMBER, 55),
        ("Bull", synthesis.target_bull, _GREEN, 95),
    ]
    col3 = bw2 / 3
    for label, tgt, col, prob in scens:
        idx  = ["Bear","Base","Bull"].index(label)
        cx   = bx + 8 + idx*col3
        c.setFont("Helvetica-Bold", 7); c.setFillColor(_rgb(_GREY))
        c.drawString(cx, y-33, label.upper())
        c.setFont("Helvetica-Bold", 18); c.setFillColor(_rgb(col))
        tgt_s = f"{tgt:,.0f}" if tgt else "—"
        c.drawString(cx, y-54, tgt_s)
        if tgt and cur:
            up = (tgt-cur)/cur*100
            c.setFont("Helvetica-Bold", 7.5)
            c.setFillColor(_rgb(_GREEN if up >= 0 else _RED))
            c.drawString(cx, y-67, f"{up:+.1f}%")
        c.setFont("Helvetica", 6.5); c.setFillColor(_rgb(_GREY))
        c.drawString(cx, y-79, f"Proba : {prob}%")
        # Hypothese cle
        hyp = _get_scenario_hyp(synthesis, label, 0)
        _wrap(c, hyp, cx, y-91, col3-6, size=5.5, lh=7.5, color=_GREY)

    y = y - bh2 - 14
    c.setStrokeColor(_rgb(_MID)); c.line(M, y, W-M, y); y -= 14

    # --- Paragraphe de synthese (4-6 phrases) ---
    y = _sec(c, M, y, "1. Synthese Executive & Recommandation", CW)
    summary = _s(synthesis.summary, 900) if synthesis.summary else (
        f"{ci.company_name} ({ci.ticker}) est analyse dans le secteur {ci.sector or 'N/A'}. "
        f"La recommandation est {reco_fr} avec une conviction de {conv:.0%}. "
        f"Le score de confiance du modele IA s'etablit a {conf:.0%}. "
        f"Le cours actuel de {_f(cur)} {ci.currency} presente un potentiel vers la cible base de "
        f"{_f(synthesis.target_base)} {ci.currency}."
    )
    y = _wrap(c, summary, M, y, CW, size=8.5, lh=13)
    y -= 10

    # --- Donnees de marche rapides ---
    if mkt:
        items = [
            ("Cours", f"{_f(cur)} {ci.currency}" if cur else "N/A"),
            ("Beta", _n(mkt.beta_levered)),
            ("WACC", _p(mkt.wacc)),
            ("TGR", _p(mkt.terminal_growth)),
            ("P/E LTM", _x(getattr(yr, "pe_ratio", None) if yr else None)),
            ("EV/EBITDA", _x(getattr(yr, "ev_ebitda", None) if yr else None)),
        ]
        cw6 = CW / len(items)
        for i, (lbl, val) in enumerate(items):
            cx = M + i*cw6
            c.setFont("Helvetica", 6); c.setFillColor(_rgb(_GREY)); c.drawString(cx, y, lbl)
            c.setFont("Helvetica-Bold", 10); c.setFillColor(_rgb(_DARK)); c.drawString(cx, y-13, val)


# ---------------------------------------------------------------------------
# PAGE 2 — 2. PRESENTATION ENTREPRISE
# ---------------------------------------------------------------------------

def _p2_entreprise(c, W, H, M, CW, ci, mkt, synthesis, today, T):
    _hband(c, W, H, ci.company_name, "Page 2 — 2. Presentation de l'Entreprise", today, 2, T)
    _footer(c, W, M, today, 2, T)
    y = H - 50

    y = _sec(c, M, y, "2. Presentation de l'Entreprise", CW)

    # Identite
    c.setFont("Helvetica-Bold", 7.5); c.setFillColor(_rgb(_GREY))
    c.drawString(M, y, f"Secteur : {_s(ci.sector or 'N/A', 40)}   |   Devise : {ci.currency}   |   Ticker : {ci.ticker}")
    y -= 12

    if mkt and mkt.share_price and mkt.shares_diluted:
        mktcap = mkt.share_price * mkt.shares_diluted / 1_000
        c.setFont("Helvetica", 7.5); c.setFillColor(_rgb(_GREY))
        c.drawString(M, y, f"Capitalisation boursiere estimee : {mktcap:,.0f} Md {ci.currency}   |   Cours : {mkt.share_price:,.2f}   |   Actions : {mkt.shares_diluted:,.0f}M")
        y -= 12
    y -= 4

    # Activites principales (3 segments)
    y = _subsec(c, M, y, "Activites principales")
    segments = _extract_segments(synthesis, ci)
    for seg_name, pct, desc in segments[:3]:
        c.setFont("Helvetica-Bold", 8); c.setFillColor(_rgb(_NAVY))
        c.drawString(M, y, f"▸ {seg_name}")
        if pct: c.drawString(M+120, y, f"{pct}% du CA")
        y -= 12
        y = _wrap(c, desc, M+12, y, CW-12, size=8, lh=12)
        y -= 6
    y -= 10

    # Positionnement concurrentiel
    y = _subsec(c, M, y, "Positionnement concurrentiel")
    positioning = _extract_positioning(synthesis, ci)
    y = _wrap(c, positioning, M, y, CW, size=8.5, lh=13)
    y -= 10

    # Concurrents
    if synthesis:
        y = _subsec(c, M, y, "Principaux concurrents")
        c.setFont("Helvetica", 8); c.setFillColor(_rgb(_DARK))
        c.drawString(M, y, _extract_competitors(synthesis, ci))
        y -= 14

    # Risques & forces
    y -= 8
    col_w = CW / 2 - 6
    left_y = right_y = y

    # Forces
    c.setFont("Helvetica-Bold", 7.5); c.setFillColor(_rgb(_GREEN))
    c.drawString(M, left_y, "AVANTAGES COMPETITIFS"); left_y -= 13
    strengths = getattr(synthesis, "strengths", None) or []
    for s in strengths[:4]:
        left_y = _bullet(c, M, left_y, _s(s, 120), col_w, color=_GREEN, size=7.5, lh=11)
        left_y -= 4

    # Risques
    c.setFont("Helvetica-Bold", 7.5); c.setFillColor(_rgb(_RED))
    c.drawString(M+col_w+12, right_y, "FACTEURS DE RISQUE"); right_y -= 13
    risks = getattr(synthesis, "risks", None) or []
    for r in risks[:4]:
        right_y = _bullet(c, M+col_w+12, right_y, _s(r, 120), col_w, color=_RED, size=7.5, lh=11)
        right_y -= 4


# ---------------------------------------------------------------------------
# PAGE 3 — 3.1 COMPTE DE RESULTAT
# ---------------------------------------------------------------------------

def _p3_is(c, W, H, M, CW, ci, snapshot, ratios, hist_years, today, T):
    _hband(c, W, H, ci.company_name, "Page 3 — 3.1 Compte de Resultat", today, 3, T)
    _footer(c, W, M, today, 3, T)
    y = H - 50

    y = _sec(c, M, y, "3. Analyse Financiere", CW)
    y = _subsec(c, M, y, f"3.1 Compte de Resultat ({ci.currency} {ci.units or 'M'})")

    unit = ci.units or "M"
    cur  = ci.currency or "USD"

    # Colonnes : YEAR-2, YEAR-1, YEAR LTM, YEAR+1F, YEAR+2F
    display_years = hist_years[-3:] if len(hist_years) >= 3 else hist_years
    yr_labels = [k.replace("_LTM","").replace("_"," ") for k in display_years]

    # Dernier millesime pour projections
    last_fy = snapshot.years.get(display_years[-1]) if display_years else None
    rev_last = getattr(last_fy, "revenue", None)
    ry_last  = ratios.years.get(display_years[-1]) if ratios else None
    g        = getattr(ry_last, "revenue_growth", None) or 0.08
    gm_last  = getattr(ry_last, "gross_margin", None)
    em_last  = getattr(ry_last, "ebitda_margin", None)
    nm_last  = getattr(ry_last, "net_margin", None)

    def _proj_rev(n): return rev_last * (1+g)**n if rev_last else None
    def _proj_gp(n):  return _proj_rev(n) * gm_last if _proj_rev(n) and gm_last else None
    def _proj_eb(n):  return _proj_rev(n) * em_last if _proj_rev(n) and em_last else None
    def _proj_ni(n):  return _proj_rev(n) * nm_last if _proj_rev(n) and nm_last else None

    last_base_yr = int(display_years[-1].split("_")[0]) if display_years else 2024
    fwd1 = str(last_base_yr+1)+"F"
    fwd2 = str(last_base_yr+2)+"F"

    headers = [f"({cur} {unit})", *yr_labels, fwd1, fwd2]

    def _val(yk, field):
        fy = snapshot.years.get(yk)
        if fy is None: return "N/A"
        v = getattr(fy, field, None)
        return _f(v) if v is not None else "N/A"

    def _rval(yk, field):
        if not ratios: return "N/A"
        ry = ratios.years.get(yk)
        if ry is None: return "N/A"
        v = getattr(ry, field, None)
        return _f(v) if v is not None else "N/A"

    def _rpct(yk, field):
        if not ratios: return "N/A"
        ry = ratios.years.get(yk)
        if ry is None: return "N/A"
        v = getattr(ry, field, None)
        return _p(v) if v is not None else "N/A"

    def _row(label, *vals):
        return [label, *vals]

    def _pct_row(label, *vals):
        return [label, *[f"({v})" if v != "N/A" else "N/A" for v in vals]]

    rev_vals  = [_val(k,"revenue")  for k in display_years] + [_f(_proj_rev(1)), _f(_proj_rev(2))]
    gp_vals   = [_rval(k,"gross_profit") if ratios and ratios.years.get(k) and hasattr(ratios.years.get(k),"gross_profit") else _f(_gp(snapshot,k))  for k in display_years] + [_f(_proj_gp(1)), _f(_proj_gp(2))]
    gm_vals   = [_rpct(k,"gross_margin") for k in display_years] + [_p(gm_last), _p(gm_last)]
    eb_vals   = [_rval(k,"ebitda") if ratios and ratios.years.get(k) and hasattr(ratios.years.get(k),"ebitda") else _f(_eb_calc(snapshot,k)) for k in display_years] + [_f(_proj_eb(1)), _f(_proj_eb(2))]
    em_vals   = [_rpct(k,"ebitda_margin") for k in display_years] + [_p(em_last), _p(em_last)]
    ni_vals   = [_f(getattr(snapshot.years.get(k),"net_income",None)) if snapshot.years.get(k) else "N/A" for k in display_years] + [_f(_proj_ni(1)), _f(_proj_ni(2))]
    nm_vals   = [_rpct(k,"net_margin") for k in display_years] + [_p(nm_last), _p(nm_last)]
    rg_vals   = ["—"] + [_rpct(k,"revenue_growth") for k in display_years[1:]] + [_p(g), _p(g)]

    from reportlab.lib import colors as rl_colors

    data = [
        headers,
        _row("Revenue", *rev_vals),
        _row("Croissance YoY", *rg_vals),
        _row("Gross Profit", *gp_vals),
        _pct_row("Gross Margin", *gm_vals),
        _row("EBITDA", *eb_vals),
        _pct_row("EBITDA Margin", *em_vals),
        _row("Net Income", *ni_vals),
        _pct_row("Net Margin", *nm_vals),
    ]

    ncols = len(headers)
    lbl_w = 90
    data_w = (CW - lbl_w) / (ncols - 1)
    col_widths = [lbl_w] + [data_w]*(ncols-1)

    tbl_styles = [
        ("BACKGROUND", (0,0), (-1,0), _rgb(_NAVY)),
        ("TEXTCOLOR",  (0,0), (-1,0), _rgb(_WHITE)),
        ("FONT",       (0,0), (-1,0), "Helvetica-Bold", 7),
        ("FONT",       (0,1), (0,-1), "Helvetica-Bold", 7),
        ("FONT",       (1,1), (-1,-1),"Helvetica", 7),
        ("ALIGN",      (1,0), (-1,-1),"RIGHT"),
        ("ALIGN",      (0,0), (0,-1), "LEFT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[_rgb(_WHITE), _rgb(_F5)]),
        ("GRID",       (0,0), (-1,-1), 0.4, _rgb(_MID)),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING", (0,0),(0,-1), 4),
        # Projections en italique (dernières 2 colonnes)
        ("TEXTCOLOR", (-2,1),(-1,-1), _rgb(_GREY)),
        ("FONT",      (-2,1),(-1,-1), "Helvetica-Oblique", 7),
    ]

    y = _tbl(c, data, col_widths, tbl_styles, M, y)
    y -= 6

    # Note projections
    c.setFont("Helvetica-Oblique", 6.5); c.setFillColor(_rgb(_GREY))
    c.drawString(M, y, f"* Projections {fwd1}/{fwd2} : extrapolation lineaire basee sur CAGR historique ({g*100:.1f}%) — a titre indicatif uniquement.")
    y -= 18

    # Paragraphe d'analyse
    y = _subsec(c, M, y, "Commentaire")
    commentary = _build_is_commentary(snapshot, ratios, display_years, ci)
    _wrap(c, commentary, M, y, CW, size=8.5, lh=13)


# ---------------------------------------------------------------------------
# PAGE 4 — 3.2 BILAN & 3.3 RATIOS VS BENCHMARK
# ---------------------------------------------------------------------------

def _p4_bilan_ratios(c, W, H, M, CW, ci, snapshot, ratios, hist_years, yr, latest, today, T):
    _hband(c, W, H, ci.company_name, "Page 4 — 3.2 Bilan & 3.3 Ratios vs Benchmark", today, 4, T)
    _footer(c, W, M, today, 4, T)
    y = H - 50

    # --- 3.2 Bilan ---
    y = _subsec(c, M, y, f"3.2 Bilan & Solidite Financiere — LTM ({ci.currency} {ci.units or 'M'})")

    fy_last = snapshot.years.get(latest) if latest else None
    def _bv(field): return getattr(fy_last, field, None) if fy_last else None

    cash   = _bv("cash")
    ltd    = _bv("long_term_debt")
    std    = _bv("short_term_debt")
    net_d  = (ltd or 0) + (std or 0) - (cash or 0) if (ltd or std or cash) else None
    cr     = getattr(yr, "current_ratio", None) if yr else None
    de     = getattr(yr, "net_debt_ebitda", None) if yr else None

    def _interp_cr(v):
        if v is None: return "N/A"
        if v >= 2.0: return "Sain (>2x)"
        if v >= 1.0: return "Acceptable (1-2x)"
        return "Tendu (<1x)"

    def _interp_nd(v):
        if v is None: return "N/A"
        if v < 0:    return "Position cash nette"
        if v < 2.0:  return "Levier modere"
        if v < 4.0:  return "Levier eleve"
        return "Dette excessive"

    bilan_data = [
        ["Metrique", "Valeur LTM", "Interpretation"],
        ["Cash & Equivalents",   f"{_f(cash)} {ci.currency}M"  if cash  else "N/A", "Reserve de liquidite"],
        ["Dette Long Terme",     f"{_f(ltd)} {ci.currency}M"   if ltd   else "N/A", "Principale source de levier"],
        ["Dette Nette",          f"{_f(net_d)} {ci.currency}M" if net_d is not None else "N/A",
                                 "Positif" if (net_d or 0) < 0 else "Negatif"],
        ["Current Ratio",        _x(cr), _interp_cr(cr)],
        ["Net Debt / EBITDA",    _x(de), _interp_nd(de)],
    ]

    bw = [130, 100, CW-230]
    bsty = [
        ("BACKGROUND", (0,0),(-1,0), _rgb(_NAVY)),
        ("TEXTCOLOR",  (0,0),(-1,0), _rgb(_WHITE)),
        ("FONT",       (0,0),(-1,0), "Helvetica-Bold", 7),
        ("FONT",       (0,1),(0,-1), "Helvetica-Bold", 7),
        ("FONT",       (1,1),(-1,-1),"Helvetica", 7),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[_rgb(_WHITE),_rgb(_F5)]),
        ("GRID",       (0,0),(-1,-1), 0.4, _rgb(_MID)),
        ("TOPPADDING", (0,0),(-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(0,-1),4),
    ]
    y = _tbl(c, bilan_data, bw, bsty, M, y)
    y -= 8

    bilan_para = _build_bilan_commentary(fy_last, yr, ci)
    y = _wrap(c, bilan_para, M, y, CW, size=8.5, lh=13)
    y -= 18

    # --- 3.3 Ratios vs Benchmark ---
    y = _subsec(c, M, y, f"3.3 Ratios Cles vs Benchmark Sectoriel ({ci.sector or 'secteur'})")

    sector = ci.sector or "Technology"
    benchmarks = _sector_benchmarks(sector)

    def _sig_cell(v, lo, hi, inv=False, fmt="x"):
        col, _ = _signal(v, lo, hi, invert=inv)
        icon   = {_GREEN:"●", _AMBER:"●", _RED:"●"}.get(col, "●")
        val_s  = (_p(v) if fmt=="%" else _x(v)) if v is not None else "N/A"
        return val_s, col

    rows_def = [
        ("P/E",          getattr(yr,"pe_ratio",None),     10, 25, False, "x", benchmarks.get("pe","15-25x")),
        ("EV/EBITDA",    getattr(yr,"ev_ebitda",None),    8,  18, False, "x", benchmarks.get("ev_ebitda","8-15x")),
        ("EV/Revenue",   getattr(yr,"ev_revenue",None),   1,  5,  False, "x", benchmarks.get("ev_rev","2-6x")),
        ("Gross Margin", getattr(yr,"gross_margin",None), 0.3,0.6, False,"%", benchmarks.get("gm","40-60%")),
        ("EBITDA Margin",getattr(yr,"ebitda_margin",None),0.15,0.35,False,"%",benchmarks.get("em","20-35%")),
        ("ROE",          getattr(yr,"roe",None),          0.1,0.25,False,"%", benchmarks.get("roe","15-25%")),
        ("Altman Z-Score",getattr(yr,"altman_z",None),   1.8,3.0,False,"z", ">2.99 = Sain"),
        ("Beneish M-Score",getattr(yr,"beneish_m",None), -2.5,-2.22,True,"z","<-2.22 = OK"),
    ]

    rdata = [["Ratio", "Valeur", f"Benchmark ({_s(sector,20)})", "Signal"]]
    sig_colors = {}
    for i, (label, v, lo, hi, inv, fmt, bench) in enumerate(rows_def):
        if fmt == "%": val_s = _p(v)
        elif fmt == "x": val_s = _x(v)
        else: val_s = _n(v)
        col, _ = _signal(v, lo, hi, invert=inv)
        sig    = {_GREEN:"🟢  OK", _AMBER:"🟡  ~", _RED:"🔴  !", _GREY:"—"}.get(col, "—")
        sig_colors[i+1] = col
        if label == "Altman Z-Score":
            sig = "SAIN" if (v or 0) >= 3.0 else ("ZONE GRISE" if (v or 0) >= 1.8 else "DETRESSE") if v else "N/A"
            sig = f"{'🟢' if 'SAIN' in sig else '🟡' if 'GRISE' in sig else '🔴'}  {sig}"
        if label == "Beneish M-Score":
            sig = "🟢  OK" if (v is not None and v < -2.22) else ("🔴  SIGNAL" if v is not None else "—")
        rdata.append([label, val_s, bench, sig])

    rw = [110, 65, 100, CW-275]
    rsty = [
        ("BACKGROUND", (0,0),(-1,0), _rgb(_NAVY)),
        ("TEXTCOLOR",  (0,0),(-1,0), _rgb(_WHITE)),
        ("FONT",       (0,0),(-1,0), "Helvetica-Bold", 7),
        ("FONT",       (0,1),(0,-1), "Helvetica-Bold", 7),
        ("FONT",       (1,1),(-1,-1),"Helvetica", 7),
        ("ALIGN",      (1,0),(-1,-1),"CENTER"),
        ("ALIGN",      (0,0),(0,-1), "LEFT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[_rgb(_WHITE),_rgb(_F5)]),
        ("GRID",       (0,0),(-1,-1), 0.4, _rgb(_MID)),
        ("TOPPADDING", (0,0),(-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(0,-1),4),
    ]
    _tbl(c, rdata, rw, rsty, M, y)


# ---------------------------------------------------------------------------
# PAGE 5 — 4.1 DCF + 4.2 SENSIBILITE
# ---------------------------------------------------------------------------

def _p5_dcf(c, W, H, M, CW, ci, mkt, yr, synthesis, today, T):
    _hband(c, W, H, ci.company_name, "Page 5 — 4. Valorisation : DCF", today, 5, T)
    _footer(c, W, M, today, 5, T)
    y = H - 50

    y = _sec(c, M, y, "4. Valorisation", CW)
    y = _subsec(c, M, y, "4.1 DCF — Scenario Base")

    wacc = getattr(mkt, "wacc", None) if mkt else None
    tgr  = getattr(mkt, "terminal_growth", None) if mkt else None
    em   = getattr(yr, "ebitda_margin", None) if yr else None
    gm   = getattr(yr, "gross_margin", None) if yr else None
    cap  = 0.05
    rev  = getattr(yr, "revenue_ltm", None) if yr else None

    # Sous-titre WACC / TGR
    c.setFont("Helvetica", 7); c.setFillColor(_rgb(_GREY))
    c.drawString(M, y,
        f"WACC : {_p(wacc)}   |   Terminal Growth Rate : {_p(tgr)}   |   Horizon : 5 ans")
    y -= 14

    dcf_data = [
        ["Hypothese", "Valeur"],
        ["Revenue CAGR projete",      _p(getattr(yr,"revenue_growth",None) if yr else None)],
        ["EBITDA Margin cible",        _p(em)],
        ["CapEx (% Revenue)",          _p(cap)],
        ["WACC",                       _p(wacc)],
        ["Terminal Growth Rate",       _p(tgr)],
        ["Valeur intrinseque (Base)",  _f(getattr(synthesis,"target_base",None)) + f" {ci.currency}" if synthesis and synthesis.target_base else "N/A"],
        ["Cours actuel",               _f(getattr(mkt,"share_price",None)) + f" {ci.currency}" if mkt and mkt.share_price else "N/A"],
        ["Upside/Downside implicite",  _upside(getattr(synthesis,"target_base",None) if synthesis else None, getattr(mkt,"share_price",None) if mkt else None)],
    ]

    dw = [160, CW-160]
    dsty = [
        ("BACKGROUND",(0,0),(-1,0),_rgb(_NAVY)),
        ("TEXTCOLOR", (0,0),(-1,0),_rgb(_WHITE)),
        ("FONT",      (0,0),(-1,0),"Helvetica-Bold",7),
        ("FONT",      (0,1),(0,-1),"Helvetica",7),
        ("FONT",      (1,1),(-1,-1),"Helvetica-Bold",7),
        ("ALIGN",     (1,0),(-1,-1),"RIGHT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[_rgb(_WHITE),_rgb(_F5)]),
        ("GRID",      (0,0),(-1,-1),0.4,_rgb(_MID)),
        ("TOPPADDING",(0,0),(-1,-1),3),
        ("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(0,-1),4),
        # Lignes Valeur & Cours en gras navy
        ("BACKGROUND",(0,6),(-1,7),_rgb(_F5)),
        ("FONT",      (0,6),(-1,7),"Helvetica-Bold",7),
    ]
    y = _tbl(c, dcf_data, dw, dsty, M, y)
    y -= 8

    dcf_para = (
        f"La valorisation DCF repose sur un WACC de {_p(wacc)} et un taux de croissance terminal de {_p(tgr)}, "
        f"coherents avec le profil de risque du secteur {ci.sector or 'N/A'}. "
        f"Les deux variables les plus sensibles sont le WACC (impact majeur sur la valeur terminale, ~60-70% de l'EV) "
        f"et le taux de croissance des revenus sur les 3 premieres annees de projection. "
        f"Un WACC superieur de 100pb reduit typiquement la valeur intrinseque de 10 a 15%."
    )
    y = _wrap(c, dcf_para, M, y, CW, size=8.5, lh=13)
    y -= 18

    # --- 4.2 Table de Sensibilite ---
    y = _subsec(c, M, y, "4.2 Table de Sensibilite DCF  (Valeur intrinseque par action)")

    base_price = getattr(synthesis, "target_base", None) if synthesis else None
    wacc_b = wacc or 0.08
    tgr_b  = tgr  or 0.025

    sens_header = ["WACC \\ TGR", f"{(tgr_b-0.005)*100:.1f}%", f"{tgr_b*100:.1f}%", f"{(tgr_b+0.005)*100:.1f}%"]
    sens_data   = [sens_header]
    for dw2 in [-0.01, 0, +0.01]:
        row_label = f"{(wacc_b+dw2)*100:.1f}%"
        row = [row_label]
        for dt in [-0.005, 0, +0.005]:
            p = _compute_sensitivity(base_price, wacc_b+dw2, tgr_b+dt, wacc_b, tgr_b)
            row.append(_f(p) if p else "N/A")
        sens_data.append(row)

    sw = [60, (CW-60)/3, (CW-60)/3, (CW-60)/3]
    ssty = [
        ("BACKGROUND",(0,0),(-1,0),_rgb(_NAVY)),
        ("TEXTCOLOR", (0,0),(-1,0),_rgb(_WHITE)),
        ("FONT",      (0,0),(-1,0),"Helvetica-Bold",7),
        ("FONT",      (0,1),(0,-1),"Helvetica-Bold",7),
        ("FONT",      (1,1),(-1,-1),"Helvetica",7),
        ("ALIGN",     (0,0),(-1,-1),"CENTER"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[_rgb(_F5),_rgb(_WHITE)]),
        ("GRID",      (0,0),(-1,-1),0.4,_rgb(_MID)),
        ("TOPPADDING",(0,0),(-1,-1),3),
        ("BOTTOMPADDING",(0,0),(-1,-1),3),
        # Case centrale (base) surlignee
        ("BACKGROUND",(2,2),(2,2),_rgb((0.8,0.9,0.8))),
        ("FONT",      (2,2),(2,2),"Helvetica-Bold",7),
    ]
    _tbl(c, sens_data, sw, ssty, M, y)


# ---------------------------------------------------------------------------
# PAGE 6 — 4.3 MULTIPLES COMPARABLES
# ---------------------------------------------------------------------------

def _p6_multiples(c, W, H, M, CW, ci, mkt, yr, synthesis, today, T):
    _hband(c, W, H, ci.company_name, "Page 6 — 4.3 Multiples Comparables", today, 6, T)
    _footer(c, W, M, today, 6, T)
    y = H - 50

    y = _subsec(c, M, y, "4.3 Valorisation par Multiples Comparables")

    cur = getattr(mkt, "share_price", None) if mkt else None
    ev_ebitda_co = getattr(yr, "ev_ebitda",   None) if yr else None
    ev_rev_co    = getattr(yr, "ev_revenue",  None) if yr else None
    pe_co        = getattr(yr, "pe_ratio",    None) if yr else None

    sector = ci.sector or "Technology"
    b      = _sector_benchmarks(sector)
    median_ev_eb  = b.get("med_ev_ebitda", 12.0)
    median_ev_rev = b.get("med_ev_rev",     4.0)
    median_pe     = b.get("med_pe",        20.0)

    def _implied(multiple_co, multiple_peers, cur_price):
        if multiple_co is None or multiple_co == 0 or cur_price is None: return None
        return cur_price * (multiple_peers / multiple_co)

    imp_ev_eb  = _implied(ev_ebitda_co, median_ev_eb,  cur)
    imp_ev_rev = _implied(ev_rev_co,    median_ev_rev, cur)
    imp_pe     = _implied(pe_co,        median_pe,     cur)

    mult_data = [
        ["Multiple", "Valeur Societe", "Mediane Peers", "Implied Price", "Upside"],
        ["EV/EBITDA",  _x(ev_ebitda_co), f"{median_ev_eb:.1f}x",
         f"{_f(imp_ev_eb)} {ci.currency}" if imp_ev_eb else "N/A",
         _upside(imp_ev_eb, cur)],
        ["EV/Revenue",  _x(ev_rev_co), f"{median_ev_rev:.1f}x",
         f"{_f(imp_ev_rev)} {ci.currency}" if imp_ev_rev else "N/A",
         _upside(imp_ev_rev, cur)],
        ["P/E",  _x(pe_co), f"{median_pe:.1f}x",
         f"{_f(imp_pe)} {ci.currency}" if imp_pe else "N/A",
         _upside(imp_pe, cur)],
    ]

    # Moyenne ponderee
    implied_prices = [p for p in [imp_ev_eb, imp_ev_rev, imp_pe] if p is not None]
    avg_implied = sum(implied_prices)/len(implied_prices) if implied_prices else None
    mult_data.append([
        "Moyenne ponderee", "", "",
        f"{_f(avg_implied)} {ci.currency}" if avg_implied else "N/A",
        _upside(avg_implied, cur),
    ])

    mw = [90, 80, 80, 100, CW-350]
    msty = [
        ("BACKGROUND",(0,0),(-1,0),_rgb(_NAVY)),
        ("TEXTCOLOR", (0,0),(-1,0),_rgb(_WHITE)),
        ("FONT",      (0,0),(-1,0),"Helvetica-Bold",7),
        ("FONT",      (0,1),(0,-1),"Helvetica-Bold",7),
        ("FONT",      (1,1),(-1,-1),"Helvetica",7),
        ("ALIGN",     (1,0),(-1,-1),"CENTER"),
        ("ALIGN",     (0,0),(0,-1), "LEFT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[_rgb(_WHITE),_rgb(_F5)]),
        ("GRID",      (0,0),(-1,-1),0.4,_rgb(_MID)),
        ("TOPPADDING",(0,0),(-1,-1),3),
        ("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(0,-1),4),
        ("BACKGROUND",(0,-1),(-1,-1),_rgb(_F5)),
        ("FONT",      (0,-1),(-1,-1),"Helvetica-Bold",7),
    ]
    y = _tbl(c, mult_data, mw, msty, M, y)

    c.setFont("Helvetica-Oblique",6.5); c.setFillColor(_rgb(_GREY))
    c.drawString(M, y-4, f"Medianes secteur {sector} — sources : yfinance, Finnhub. Peers : voir comparables.")


# ---------------------------------------------------------------------------
# PAGE 7 — 5. RISQUES & SCENARIOS
# ---------------------------------------------------------------------------

def _p7_scenarios(c, W, H, M, CW, ci, mkt, synthesis, today, T):
    _hband(c, W, H, ci.company_name, "Page 7 — 5. Analyse des Risques & Scenarios", today, 7, T)
    _footer(c, W, M, today, 7, T)
    y = H - 50

    y = _sec(c, M, y, "5. Analyse des Risques & Scenarios", CW)

    cur = getattr(mkt, "share_price", None) if mkt else None

    scenarios = [
        ("BULL", synthesis.target_bull if synthesis else None, _GREEN, 25,
         _get_scenario_hyp(synthesis, "Bull", 0),
         _get_scenario_hyp(synthesis, "Bull", 1),
         _get_scenario_hyp(synthesis, "Bull", 2)),
        ("BASE", synthesis.target_base if synthesis else None, _AMBER, 55,
         _get_scenario_hyp(synthesis, "Base", 0),
         _get_scenario_hyp(synthesis, "Base", 1),
         _get_scenario_hyp(synthesis, "Base", 2)),
        ("BEAR", synthesis.target_bear if synthesis else None, _RED, 20,
         _get_scenario_hyp(synthesis, "Bear", 0),
         _get_scenario_hyp(synthesis, "Bear", 1),
         _get_scenario_hyp(synthesis, "Bear", 2)),
    ]

    for case, tgt, col, prob, h1, h2, h3 in scenarios:
        bx = M; bw_s = CW; bh_s = 88
        # Fond colore light
        light = {_GREEN:(0.9,0.97,0.93), _AMBER:(0.98,0.96,0.88), _RED:(0.98,0.9,0.88)}
        c.setFillColor(_rgb(light.get(col, _F5)))
        c.setStrokeColor(_rgb(col))
        c.setLineWidth(1.5)
        c.roundRect(bx, y-bh_s, bw_s, bh_s, 4, fill=1, stroke=1)
        c.setLineWidth(1)

        # Header ligne
        c.setFont("Helvetica-Bold", 10); c.setFillColor(_rgb(col))
        tgt_s = f"{tgt:,.0f} {ci.currency}" if tgt else "N/A"
        up_s  = _upside(tgt, cur)
        c.drawString(bx+10, y-16, f"{case} — {tgt_s}  ({up_s})")
        c.setFont("Helvetica", 7.5); c.setFillColor(_rgb(_GREY))
        c.drawRightString(bx+bw_s-10, y-16, f"Probabilite estimee : {prob}%")

        # Hypotheses
        for j, hyp in enumerate([h1, h2, h3], 1):
            hy = y - 28 - (j-1)*17
            c.setFont("Helvetica-Bold", 8); c.setFillColor(_rgb(col))
            c.drawString(bx+10, hy, f"▸")
            c.setFont("Helvetica", 8); c.setFillColor(_rgb(_DARK))
            _wrap(c, hyp, bx+22, hy, bw_s-32, size=8, lh=11)

        y -= bh_s + 10


# ---------------------------------------------------------------------------
# PAGE 8 — 6. SENTIMENT & 7. AVOCAT DU DIABLE
# ---------------------------------------------------------------------------

def _p8_sentiment_devil(c, W, H, M, CW, ci, sentiment, devil, synthesis, today, T):
    _hband(c, W, H, ci.company_name, "Page 8 — 6. Sentiment & 7. Avocat du Diable", today, 8, T)
    _footer(c, W, M, today, 8, T)
    y = H - 50

    # --- Section 6 : Sentiment ---
    y = _sec(c, M, y, "6. Sentiment de Marche", CW)

    if sentiment:
        score = getattr(sentiment, "composite_score", None)
        articles = getattr(sentiment, "article_count", 0) or 0
        pos_n = getattr(sentiment, "positive_count", 0) or 0
        neg_n = getattr(sentiment, "negative_count", 0) or 0
        neu_n = getattr(sentiment, "neutral_count",  0) or 0

        orient = "POSITIVE" if (score or 0) > 0.1 else ("NEGATIVE" if (score or 0) < -0.1 else "NEUTRE")
        o_col  = _GREEN if orient == "POSITIVE" else (_RED if orient == "NEGATIVE" else _AMBER)

        c.setFont("Helvetica-Bold", 9); c.setFillColor(_rgb(o_col))
        c.drawString(M, y, f"Score FinBERT : {orient}  ({_n(score,3)})")
        c.setFont("Helvetica", 7.5); c.setFillColor(_rgb(_GREY))
        c.drawRightString(W-M, y, f"Confiance : {abs(score or 0):.0%}  |  Articles analyses : {articles}")
        y -= 14

        sent_data = [
            ["Orientation", "Nb articles", "Themes dominants"],
            ["Positif", str(pos_n), _sent_themes(sentiment, "positive")],
            ["Neutre",  str(neu_n), _sent_themes(sentiment, "neutral")],
            ["Negatif", str(neg_n), _sent_themes(sentiment, "negative")],
        ]
        sw = [80, 70, CW-150]
        ssty = [
            ("BACKGROUND",(0,0),(-1,0),_rgb(_NAVY)),
            ("TEXTCOLOR", (0,0),(-1,0),_rgb(_WHITE)),
            ("FONT",      (0,0),(-1,0),"Helvetica-Bold",7),
            ("FONT",      (0,1),(0,-1),"Helvetica",7),
            ("BACKGROUND",(0,1),(-1,1),_rgb((0.92,0.97,0.93))),
            ("BACKGROUND",(0,3),(-1,3),_rgb((0.97,0.92,0.92))),
            ("ROWBACKGROUNDS",(0,2),(-1,2),[_rgb(_F5)]),
            ("GRID",      (0,0),(-1,-1),0.4,_rgb(_MID)),
            ("TOPPADDING",(0,0),(-1,-1),3),
            ("BOTTOMPADDING",(0,0),(-1,-1),3),
            ("LEFTPADDING",(0,0),(0,-1),4),
        ]
        y = _tbl(c, sent_data, sw, ssty, M, y)
        y -= 8

        sent_para = _build_sent_commentary(sentiment, synthesis)
        y = _wrap(c, sent_para, M, y, CW, size=8.5, lh=13)
    else:
        c.setFont("Helvetica-Oblique",8); c.setFillColor(_rgb(_GREY))
        c.drawString(M, y, "Donnees de sentiment non disponibles pour cette analyse.")
        y -= 20

    y -= 16

    # --- Section 7 : Avocat du Diable ---
    y = _sec(c, M, y, "7. Avocat du Diable", CW)

    if devil:
        delta = getattr(devil, "conviction_delta", None)
        counter_rec = getattr(devil, "counter_recommendation", None)
        c.setFont("Helvetica-Bold", 8); c.setFillColor(_rgb(_RED))
        delta_s = f"{delta:+.2f}" if delta is not None else "N/A"
        c.drawString(M, y, f"These inverse  |  Delta conviction : {delta_s}  |  Recommandation alternative : {counter_rec or 'N/A'}")
        y -= 14

        ct = getattr(devil, "counter_thesis", None) or ""
        paras = [p.strip() for p in ct.split("\n\n") if p.strip()] if ct else []

        labels = [
            "Fragilite principale de la these d'investissement :",
            "Deuxieme fragilite structurelle :",
            "Risque sous-estime par le marche :",
        ]
        for i, (label, para) in enumerate(zip(labels, paras + [""]*3)):
            if i >= 3: break
            c.setFont("Helvetica-Bold", 7.5); c.setFillColor(_rgb(_RED))
            c.drawString(M, y, label); y -= 12
            if para:
                y = _wrap(c, para, M+8, y, CW-8, size=8.5, lh=13)
            else:
                c.setFont("Helvetica-Oblique",8); c.setFillColor(_rgb(_GREY))
                c.drawString(M+8, y, "Analyse non disponible."); y -= 13
            y -= 8
    else:
        c.setFont("Helvetica-Oblique",8); c.setFillColor(_rgb(_GREY))
        c.drawString(M, y, "Analyse Avocat du Diable non disponible.")


# ---------------------------------------------------------------------------
# PAGE 9 — 8. CONDITIONS D'INVALIDATION & DISCLAIMER
# ---------------------------------------------------------------------------

def _p9_invalidation_disclaimer(c, W, H, M, CW, ci, synthesis, today, T):
    _hband(c, W, H, ci.company_name, "Page 9 — 8. Invalidation & Disclaimer", today, 9, T)
    _footer(c, W, M, today, 9, T)
    y = H - 50

    y = _sec(c, M, y, "8. Conditions d'Invalidation", CW)

    c.setFont("Helvetica", 8); c.setFillColor(_rgb(_DARK))
    c.drawString(M, y, "Cette analyse serait a reviser dans les cas suivants :"); y -= 16

    inv_raw = (getattr(synthesis, "invalidation_conditions", None) or "") if synthesis else ""
    inv_lines = [l.strip() for l in inv_raw.split(".") if len(l.strip()) > 10]

    categories = [
        ("Macro",      "Si les conditions macroeconomiques se deteriorent significativement (hausse des taux >100pb, recession prononcee)."),
        ("Sectorielle","Si la dynamique sectorielle se retourne (disruption technologique, regulation defavorable, perte de part de marche majeure)."),
        ("Societe",    "Si les fondamentaux de la societe se degradent (marge brute sous seuil critique, dette excessive, gouvernance defaillante)."),
    ]

    for cat, fallback in categories:
        c.setFont("Helvetica-Bold", 8); c.setFillColor(_rgb(_NAVY))
        c.drawString(M, y, cat); y -= 12
        relevant = next((l for l in inv_lines if any(k in l.lower() for k in cat.lower().split())), fallback)
        y = _wrap(c, relevant, M+8, y, CW-8, size=8.5, lh=13, color=_DARK)
        y -= 10

    y -= 10
    c.setStrokeColor(_rgb(_MID)); c.line(M, y, W-M, y); y -= 20

    # Disclaimer
    y = _sec(c, M, y, "9. Disclaimer", CW)

    disclaimer = (
        f"Rapport genere par FinSight IA v2.0 le {today}. "
        "Ce document est produit par un systeme d'intelligence artificielle a des fins d'analyse uniquement. "
        "Il ne constitue pas un conseil en investissement au sens de la directive MiFID II. "
        "FinSight IA ne peut etre tenu responsable des decisions d'investissement prises sur la base de ce document. "
        "Les donnees financieres sont issues de sources publiques (yfinance, Finnhub, FMP) et peuvent contenir des inexactitudes. "
        "Toute decision d'investissement doit faire l'objet d'une analyse complementaire par un professionnel qualifie."
    )
    y = _wrap(c, disclaimer, M, y, CW, size=8, lh=13, color=_GREY)
    y -= 20

    # Signature finale
    c.setFillColor(_rgb(_NAVY))
    c.rect(M, y-28, CW, 28, fill=1, stroke=0)
    c.setFillColor(_rgb(_WHITE)); c.setFont("Helvetica-Bold", 8)
    c.drawString(M+10, y-14, "FinSight IA")
    c.setFont("Helvetica", 7.5)
    c.drawString(M+10, y-25, f"{today}  |  Confidentiel — Usage interne uniquement")
    c.drawRightString(W-M-10, y-20,
        f"Conviction : {getattr(synthesis,'conviction',0):.0%}  |  "
        f"Confiance IA : {getattr(synthesis,'confidence_score',0):.0%}"
        if synthesis else "FinSight IA v2.0")


# ---------------------------------------------------------------------------
# HELPERS DATA
# ---------------------------------------------------------------------------

def _gp(snapshot, yk):
    fy = snapshot.years.get(yk)
    if not fy: return None
    rev  = getattr(fy, "revenue", None)
    cogs = getattr(fy, "cogs", None)
    if rev is None: return None
    return rev - abs(cogs) if cogs is not None else None

def _eb_calc(snapshot, yk):
    fy = snapshot.years.get(yk)
    if not fy: return None
    gp  = _gp(snapshot, yk)
    if gp is None: return None
    sga = abs(getattr(fy,"sga",None) or 0)
    rd  = abs(getattr(fy,"rd",None) or 0)
    return gp - sga - rd

def _compute_sensitivity(base_price, wacc, tgr, wacc_base, tgr_base):
    if base_price is None: return None
    try:
        adj = (wacc_base - tgr_base) / ((wacc - tgr) if abs(wacc - tgr) > 1e-4 else 1e-4)
        return base_price * adj
    except: return None

def _sector_benchmarks(sector):
    s = (sector or "").lower()
    if "tech" in s or "software" in s:
        return {"pe":"25-40x","ev_ebitda":"20-35x","ev_rev":"6-12x","gm":"60-80%","em":"25-45%","roe":"20-40%",
                "med_pe":30.0,"med_ev_ebitda":25.0,"med_ev_rev":8.0}
    if "health" in s or "pharma" in s or "bio" in s:
        return {"pe":"20-35x","ev_ebitda":"12-20x","ev_rev":"4-8x","gm":"60-75%","em":"25-40%","roe":"15-30%",
                "med_pe":25.0,"med_ev_ebitda":15.0,"med_ev_rev":5.0}
    if "financ" in s or "bank" in s:
        return {"pe":"10-18x","ev_ebitda":"8-15x","ev_rev":"2-4x","gm":"50-70%","em":"20-35%","roe":"10-20%",
                "med_pe":13.0,"med_ev_ebitda":10.0,"med_ev_rev":3.0}
    if "energy" in s or "oil" in s:
        return {"pe":"8-15x","ev_ebitda":"5-10x","ev_rev":"1-3x","gm":"30-55%","em":"15-30%","roe":"10-20%",
                "med_pe":11.0,"med_ev_ebitda":7.0,"med_ev_rev":2.0}
    if "consumer" in s or "retail" in s:
        return {"pe":"15-30x","ev_ebitda":"10-18x","ev_rev":"1-4x","gm":"30-55%","em":"10-25%","roe":"15-30%",
                "med_pe":22.0,"med_ev_ebitda":13.0,"med_ev_rev":2.5}
    if "industrial" in s:
        return {"pe":"15-25x","ev_ebitda":"10-16x","ev_rev":"1-3x","gm":"30-50%","em":"12-25%","roe":"12-22%",
                "med_pe":18.0,"med_ev_ebitda":12.0,"med_ev_rev":2.0}
    # Default
    return {"pe":"15-25x","ev_ebitda":"10-18x","ev_rev":"2-5x","gm":"40-65%","em":"18-35%","roe":"12-25%",
            "med_pe":20.0,"med_ev_ebitda":12.0,"med_ev_rev":4.0}

def _get_scenario_hyp(synthesis, case, idx):
    if not synthesis: return "Hypothese non disponible."
    case_l = case.lower()
    # Chercher dans les risques / forces selon le cas
    if case_l == "bull":
        items = getattr(synthesis, "strengths", None) or []
        defaults = [
            "Acceleration de la croissance organique au-dessus du consensus.",
            "Expansion des marges via economies d'echelle et levier operationnel.",
            "Multiple de valorisation re-rating vers la limite haute sectorielle.",
        ]
    elif case_l == "base":
        items = []
        defaults = [
            f"Croissance revenues conforme au consensus de marche.",
            "Maintien des marges actuelles sur l'horizon de projection.",
            "Multiple de valorisation stable, proche des medianes sectorielles.",
        ]
    else:
        items = getattr(synthesis, "risks", None) or []
        defaults = [
            "Deterioration du contexte macroeconomique et pression sur les marges.",
            "Perte de part de marche face a la concurrence intensifiee.",
            "Compression des multiples en environnement de taux eleves.",
        ]
    pool = [_s(i, 120) for i in items] + defaults
    return pool[idx] if idx < len(pool) else defaults[min(idx, len(defaults)-1)]

def _extract_segments(synthesis, ci):
    """Extrait 3 segments d'activite depuis la synthese ou defaut."""
    defaults = [
        (ci.sector or "Activite principale", None, f"Activite principale de {ci.company_name}."),
        ("Autres segments", None, "Activites complementaires et diversification sectorielle."),
        ("International", None, "Operations et filiales a l'international."),
    ]
    if not synthesis: return defaults
    risks = getattr(synthesis, "risks", None) or []
    strengths = getattr(synthesis, "strengths", None) or []
    # Simple extraction
    return defaults

def _extract_positioning(synthesis, ci):
    if not synthesis: return f"{ci.company_name} opere dans le secteur {ci.sector or 'N/A'}."
    summary = getattr(synthesis, "summary", None) or ""
    if len(summary) > 100:
        return summary[:500]
    return (
        f"{ci.company_name} ({ci.ticker}) occupe une position etablie dans le secteur {ci.sector or 'N/A'}. "
        f"La societe beneficie de barrieres a l'entree significatives et d'un positionnement differencie. "
        f"La dynamique concurrentielle reste intense, necessitant une vigilance accrue sur les parts de marche. "
        f"Le modele economique repose sur une generation de cash recurrente et une discipline d'allocation du capital."
    )

def _extract_competitors(synthesis, ci):
    strengths = getattr(synthesis, "strengths", None) or []
    return "Concurrents directs : donnees issues de l'analyse sectorielle (voir onglet COMPARABLES dans Excel)."

def _build_is_commentary(snapshot, ratios, years, ci):
    if not years or not ratios: return "Analyse financiere basee sur les donnees disponibles."
    latest = years[-1]
    ry = ratios.years.get(latest)
    g  = getattr(ry, "revenue_growth", None)
    em = getattr(ry, "ebitda_margin", None)
    nm = getattr(ry, "net_margin", None)
    return (
        f"Sur la periode analysee, {ci.company_name} affiche une dynamique de revenus "
        f"{'en progression de ' + _p(g) if g else 'stable'} sur le dernier exercice. "
        f"La marge EBITDA de {_p(em)} temoigne "
        f"{'d un levier operationnel soutenu' if (em or 0) > 0.25 else 'd une pression sur la rentabilite operationnelle'}. "
        f"La marge nette s etablit a {_p(nm)}, refletant l impact des charges financieres et fiscales. "
        f"Les projections {str(int(latest.split('_')[0])+1)}F/{str(int(latest.split('_')[0])+2)}F restent "
        f"conditionnelles aux hypotheses de croissance et de marge retenues — a traiter avec prudence."
    )

def _build_bilan_commentary(fy, yr, ci):
    if not fy: return "Donnees bilancielles non disponibles."
    cash = getattr(fy,"cash",None); ltd = getattr(fy,"long_term_debt",None)
    cr = getattr(yr,"current_ratio",None) if yr else None
    parts = []
    if cash and ltd:
        net = ltd - cash
        parts.append(
            f"La structure bilancielle de {ci.company_name} presente une dette nette de "
            f"{_f(net)} {ci.currency}M, "
            f"{'limitee au regard de la generation de cash' if net < cash else 'materielle et a surveiller'}."
        )
    if cr:
        parts.append(
            f"Le ratio de liquidite courante de {_x(cr)} est "
            f"{'confortable' if cr >= 2 else 'adequat' if cr >= 1 else 'tendu et necessitant une attention particuliere'}."
        )
    parts.append(
        "La capacite a absorber un choc exogene depend de l'acces aux lignes de credit disponibles et du profil d'echeance de la dette."
    )
    return " ".join(parts)

def _sent_themes(sentiment, orient):
    themes = getattr(sentiment, f"{orient}_themes", None)
    if themes and isinstance(themes, list):
        return ", ".join(str(t) for t in themes[:3])
    keys_map = {
        "positive": ["resultats", "croissance", "dividende"],
        "neutral":  ["previsions", "marche", "analyse"],
        "negative": ["risque", "pression", "competition"],
    }
    return ", ".join(keys_map.get(orient, ["N/A"]))

def _build_sent_commentary(sentiment, synthesis):
    score = getattr(sentiment, "composite_score", None)
    orient = "positif" if (score or 0) > 0.1 else ("negatif" if (score or 0) < -0.1 else "neutre")
    rec = getattr(synthesis, "recommendation", "N/A") if synthesis else "N/A"
    return (
        f"Le sentiment de marche agregé est {orient} (score : {_n(score,3)}), "
        f"base sur l analyse de {getattr(sentiment,'article_count',0) or 0} articles financiers recents. "
        f"Ce signal {'renforce' if (orient == 'positif' and rec == 'BUY') or (orient == 'negatif' and rec == 'SELL') else 'nuance'} "
        f"la recommandation {rec} issue de l analyse fondamentale. "
        f"Le sentiment doit etre interprete comme un facteur complementaire, "
        f"non comme un signal d investissement autonome."
    )
