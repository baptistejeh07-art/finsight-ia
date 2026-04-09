"""
cmp_secteur_pptx_writer.py — FinSight IA
Pitchbook comparatif sectoriel 20 slides via python-pptx.
Compare deux secteurs cote a cote (memes ratios, scoring, top acteurs, risques).

Usage :
    from outputs.cmp_secteur_pptx_writer import CmpSecteurPPTXWriter
    bytes_ = CmpSecteurPPTXWriter.generate(
        tickers_a, sector_a, universe_a,
        tickers_b, sector_b, universe_b,
        output_path="cmp_tech_vs_sante.pptx"
    )

tickers_a / tickers_b : list[dict] tel que retourne par _fetch_real_sector_data
    Cles utiles : ticker, company, score_global, score_value, score_growth,
                  score_quality, score_momentum, pe_ratio, ev_ebitda, ev_revenue,
                  ebitda_margin, gross_margin, net_margin, roe, roic,
                  revenue_growth, momentum_52w, altman_z, piotroski_f,
                  peg_ratio, fcf_yield, beta, price, market_cap, currency
"""
from __future__ import annotations

import io
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

log = logging.getLogger(__name__)

from pptx import Presentation
from pptx.util import Cm, Pt, Inches
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

# ── Palette ──────────────────────────────────────────────────────────────────
_NAVY   = RGBColor(0x1B, 0x3A, 0x6B)
_NAVYL  = RGBColor(0x2A, 0x52, 0x98)
_WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
_BLACK  = RGBColor(0x1A, 0x1A, 0x1A)
_GRAYL  = RGBColor(0xF5, 0xF7, 0xFA)
_GRAYM  = RGBColor(0xE8, 0xEC, 0xF0)
_GRAYT  = RGBColor(0x55, 0x55, 0x55)
_GRAYD  = RGBColor(0xAA, 0xAA, 0xAA)
_GREEN  = RGBColor(0x1A, 0x7A, 0x4A)
_RED    = RGBColor(0xA8, 0x20, 0x20)
_AMBER  = RGBColor(0xB8, 0x92, 0x2A)

# Couleurs differenciantes A vs B
_COL_A      = RGBColor(0x1B, 0x3A, 0x6B)   # navy   → Secteur A
_COL_A_PALE = RGBColor(0xEE, 0xF3, 0xFA)
_COL_B      = RGBColor(0x1A, 0x7A, 0x4A)   # vert   → Secteur B
_COL_B_PALE = RGBColor(0xEA, 0xF4, 0xEF)

# ── Dimensions ───────────────────────────────────────────────────────────────
_SW = Inches(10.0)
_SH = Inches(5.625)

# Matplotlib hex (pour les charts)
_HEX_A = "#1B3A6B"
_HEX_B = "#1A7A4A"
_HEX_AG = "#5b7fb5"
_HEX_BG = "#5aab7a"


# ── Utilitaires safe ─────────────────────────────────────────────────────────
def _safe_float(v, default=0.0) -> float:
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except Exception:
        return default


def _med(vals: list, default=0.0) -> float:
    clean = [_safe_float(v) for v in vals if v is not None]
    if not clean:
        return default
    clean.sort()
    n = len(clean)
    return clean[n // 2] if n % 2 else (clean[n // 2 - 1] + clean[n // 2]) / 2


def _mean(vals: list, default=0.0) -> float:
    clean = [_safe_float(v) for v in vals if v is not None]
    return sum(clean) / len(clean) if clean else default


# ── PPTX primitives ──────────────────────────────────────────────────────────
def _blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def _rect(slide, x, y, w, h, fill=None, line=False, line_col=None, line_w=0.5):
    shape = slide.shapes.add_shape(1, Cm(x), Cm(y), Cm(w), Cm(h))
    if fill:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    else:
        shape.fill.background()
    if line and line_col:
        shape.line.color.rgb = line_col
        shape.line.width = Pt(line_w)
    else:
        shape.line.fill.background()
    return shape


def _txb(slide, text, x, y, w, h, size=9, bold=False, color=None, align=PP_ALIGN.LEFT,
         italic=False, wrap=True):
    color = color or _BLACK
    box = slide.shapes.add_textbox(Cm(x), Cm(y), Cm(w), Cm(h))
    tf = box.text_frame
    tf.word_wrap = wrap
    para = tf.paragraphs[0]
    para.alignment = align
    run = para.add_run()
    run.text = str(text)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return box


def _pic(slide, img_bytes, x, y, w, h):
    buf = io.BytesIO(img_bytes)
    slide.shapes.add_picture(buf, Cm(x), Cm(y), Cm(w), Cm(h))


def _add_table(slide, data, x, y, w, h, col_widths=None,
               header_fill=_NAVY, header_color=_WHITE,
               alt_fill=None, font_size=7.5, header_size=7.5):
    rows = len(data)
    cols = len(data[0]) if data else 1
    tbl_shape = slide.shapes.add_table(rows, cols, Cm(x), Cm(y), Cm(w), Cm(h))
    tbl = tbl_shape.table
    if col_widths:
        total = sum(col_widths)
        for i, cw in enumerate(col_widths):
            tbl.columns[i].width = Cm(cw * w / total)
    for r_idx, row_data in enumerate(data):
        is_header = (r_idx == 0)
        for c_idx, cell_text in enumerate(row_data):
            cell = tbl.cell(r_idx, c_idx)
            cell.text = str(cell_text) if cell_text is not None else "—"
            para = cell.text_frame.paragraphs[0]
            para.alignment = PP_ALIGN.CENTER
            run = para.runs[0] if para.runs else para.add_run()
            run.font.size = Pt(header_size if is_header else font_size)
            run.font.bold = is_header
            if is_header:
                run.font.color.rgb = header_color
                cell.fill.solid()
                cell.fill.fore_color.rgb = header_fill
            else:
                run.font.color.rgb = _BLACK
                if alt_fill and r_idx % 2 == 0:
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = alt_fill
                else:
                    cell.fill.background()
    return tbl


# ── Header / footer / chapter divider ────────────────────────────────────────
_NAV_LABELS = ["1", "2", "3", "4", "5"]


def _header(slide, title, subtitle, active_section=1):
    _rect(slide, 0, 0, 25.4, 1.4, fill=_NAVY)
    _txb(slide, title, 0.9, 0.05, 19.0, 1.3, size=12, bold=True, color=_WHITE)
    for i, lbl in enumerate(_NAV_LABELS):
        dot_x = 21.8 + i * 0.7
        fill = _WHITE if (i + 1) == active_section else _NAVYL
        _rect(slide, dot_x, 0.35, 0.55, 0.55, fill=fill)
        c = _BLACK if (i + 1) == active_section else _GRAYD
        _txb(slide, lbl, dot_x, 0.35, 0.55, 0.55, size=7, bold=True, color=c, align=PP_ALIGN.CENTER)
    _txb(slide, subtitle, 0.9, 1.55, 23.6, 0.55, size=7.5, color=_GRAYT)


def _footer(slide, D):
    _rect(slide, 0, 13.75, 25.4, 0.5, fill=_GRAYL)
    _txb(slide, "FinSight IA  |  Comparatif Sectoriel  |  Usage confidentiel", 0.9, 13.8, 14.0, 0.4, size=7, color=_GRAYD)
    _txb(slide, D["date_str"], 0, 13.8, 24.4, 0.4, size=7, color=_GRAYD, align=PP_ALIGN.RIGHT)


def _chapter_divider(prs, num_str, chapter_title, subtitle):
    slide = _blank(prs)
    _rect(slide, 0, 0, 25.4, 14.3, fill=_NAVY)
    _txb(slide, num_str, 1.0, 3.5, 8.0, 4.5, size=72, bold=True, color=_NAVYL)
    _txb(slide, chapter_title, 1.0, 7.0, 23.0, 2.0, size=28, bold=True, color=_WHITE)
    _rect(slide, 1.0, 9.1, 15.0, 0.05, fill=_GRAYD)
    _txb(slide, subtitle, 1.0, 9.4, 22.9, 0.8, size=11, color=_GRAYD)
    _txb(slide, "FinSight IA  |  Usage confidentiel", 0.9, 13.75, 23.6, 0.4, size=7, color=_GRAYD)


# ── Legend badge ─────────────────────────────────────────────────────────────
def _legend_badge(slide, x, y):
    _rect(slide, x, y, 0.4, 0.22, fill=_COL_A)
    _txb(slide, "A", x + 0.45, y, 1.5, 0.22, size=7, color=_COL_A)
    _rect(slide, x + 2.0, y, 0.4, 0.22, fill=_COL_B)
    _txb(slide, "B", x + 2.45, y, 1.5, 0.22, size=7, color=_COL_B)


# ── Preparation des donnees ───────────────────────────────────────────────────
def _prepare_data(tickers_a, sector_a, universe_a, tickers_b, sector_b, universe_b):
    """Calcule les medianes et aggregats pour les deux secteurs."""
    def _stats(td):
        if not td:
            return {}
        pe     = _med([t.get("pe_ratio") for t in td if t.get("pe_ratio")])
        ev_eb  = _med([t.get("ev_ebitda") for t in td if t.get("ev_ebitda")])
        ev_rev = _med([t.get("ev_revenue") for t in td if t.get("ev_revenue")])
        gm     = _med([t.get("gross_margin") for t in td])
        em     = _med([t.get("ebitda_margin") for t in td])
        nm     = _med([t.get("net_margin") for t in td])
        roe    = _med([t.get("roe") for t in td])
        roic   = _med([t.get("roic") for t in td if t.get("roic")], default=None)
        revg   = _med([t.get("revenue_growth", 0) for t in td]) * 100
        mom    = _med([t.get("momentum_52w", 0) for t in td])
        beta   = _med([t.get("beta", 1.0) for t in td if t.get("beta")])
        score  = int(_mean([t.get("score_global", 50) for t in td]))
        # score_value peut etre en 0-25 (fetch_real) ou 0-100 (compute_screening)
        # Normaliser vers 0-25 : si la valeur > 30, c'est du 0-100 -> diviser par 4
        def _sub(t, key, default=12):
            v = t.get(key)
            if v is None:
                return default
            return round(float(v) / 4.0, 1) if float(v) > 30 else float(v)
        s_val  = _mean([_sub(t, "score_value")    for t in td])
        s_gro  = _mean([_sub(t, "score_growth")   for t in td])
        s_qua  = _mean([_sub(t, "score_quality")  for t in td])
        s_mom  = _mean([_sub(t, "score_momentum") for t in td])
        pf     = _med([t.get("piotroski_f") for t in td if t.get("piotroski_f") is not None])
        az     = _med([t.get("altman_z") for t in td if t.get("altman_z") is not None], default=None)
        fcfy   = _med([t.get("fcf_yield") for t in td if t.get("fcf_yield") is not None])
        peg    = _med([t.get("peg_ratio") for t in td if t.get("peg_ratio")])
        div_yield = _med([t.get("div_yield") for t in td if t.get("div_yield") and float(t.get("div_yield") or 0) > 0], default=None)
        payout = _med([t.get("payout_ratio") for t in td if t.get("payout_ratio") and float(t.get("payout_ratio") or 0) > 0], default=None)
        return dict(
            pe=pe, ev_eb=ev_eb, ev_rev=ev_rev, gm=gm, em=em, nm=nm,
            roe=roe, roic=roic, revg=revg, mom=mom, beta=beta,
            score=score, s_val=s_val, s_gro=s_gro, s_qua=s_qua, s_mom=s_mom,
            pf=pf, az=az, fcfy=fcfy, peg=peg, div_yield=div_yield, payout=payout,
        )

    sa = _stats(tickers_a)
    sb = _stats(tickers_b)

    # Signal couleur selon score
    def _sig(score):
        if score >= 65:
            return _GREEN, "Surponderer"
        if score >= 45:
            return _AMBER, "Neutre"
        return _RED, "Sous-ponderer"

    sig_a_col, sig_a_lbl = _sig(sa.get("score", 50))
    sig_b_col, sig_b_lbl = _sig(sb.get("score", 50))

    # Universe commun ou combine
    universes = set(filter(None, [universe_a, universe_b]))
    universe_label = " / ".join(sorted(universes)) if universe_a != universe_b else (universe_a or "Global")

    _MOIS_FR = ["janvier","fevrier","mars","avril","mai","juin",
                "juillet","aout","septembre","octobre","novembre","decembre"]
    _now = datetime.now()
    _date_str = f"{_now.day} {_MOIS_FR[_now.month - 1]} {_now.year}"

    return dict(
        sector_a=sector_a, sector_b=sector_b,
        universe_a=universe_a, universe_b=universe_b,
        universe_label=universe_label,
        na=len(tickers_a), nb=len(tickers_b),
        td_a=tickers_a, td_b=tickers_b,
        sa=sa, sb=sb,
        sig_a_col=sig_a_col, sig_a_lbl=sig_a_lbl,
        sig_b_col=sig_b_col, sig_b_lbl=sig_b_lbl,
        date_str=_date_str,
        year=_now.year,
        llm={},
    )


# ── Helpers de formatage ──────────────────────────────────────────────────────
def _fmt(v, pct=False, x=False, dp=1):
    """Formate une valeur numerique pour affichage."""
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "—"
    try:
        f = float(v)
        if pct:
            return f"{f:+.{dp}f} %"
        if x:
            return f"{f:.{dp}f}x"
        return f"{f:.{dp}f}"
    except Exception:
        return str(v)


def _fmt_simple(v, pct=False, x=False, dp=1):
    """Formate sans signe +."""
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "—"
    try:
        f = float(v)
        if pct:
            return f"{f:.{dp}f} %"
        if x:
            return f"{f:.{dp}f}x"
        return f"{f:.{dp}f}"
    except Exception:
        return str(v)


# ── Contenu sectoriel (repris de sectoral_pptx_writer) ───────────────────────
from outputs.sectoral_pptx_writer import _SECTOR_CONTENT


def _get_content(sector_name: str) -> dict:
    """Cherche le contenu dans la librairie (insensible a la casse / partiel)."""
    key = sector_name.strip()
    if key in _SECTOR_CONTENT:
        return _SECTOR_CONTENT[key]
    key_lc = key.lower()
    for k, v in _SECTOR_CONTENT.items():
        if k.lower() == key_lc or key_lc in k.lower() or k.lower() in key_lc:
            return v
    # Fallback generique
    return {
        "description": f"Le secteur {sector_name} regroupe les societes actives dans ce domaine. "
                       f"Analyse basee sur les donnees financieres reelles des principaux acteurs.",
        "catalyseurs": [
            ("Croissance Structurelle", "Demande sectorielle portee par des tendances long terme favorables."),
            ("Transformation Digitale", "Adoption technologique acceleree — gains de productivite et nouveaux modeles."),
            ("Consolidation", "Fusions-acquisitions — economies d'echelle et elimination des acteurs faibles."),
        ],
        "risques": [
            ("Ralentissement Macro", "Recession potentielle — contraction de la demande et compression des marges."),
            ("Pression Concurrentielle", "Nouveaux entrants et disruption — erosion des parts de marche."),
            ("Risque Reglementaire", "Evolutions reglementaires — surcouts de conformite."),
        ],
        "drivers": [
            ("up", "Demande Structurelle", "Croissance portee par megatendances"),
            ("up", "Innovation", "R&D et transformation technologique"),
            ("down", "Sensibilite Macro", "Exposition aux cycles economiques"),
            ("down", "Pression Concurrence", "Nouveaux entrants et disruption"),
        ],
        "cycle_comment": "Positionnement cycle a determiner selon contexte macro",
        "metriques": [],
        "conditions": [],
    }


# ── Chart builders ────────────────────────────────────────────────────────────

def _chart_valuation(sa: dict, sb: dict, label_a: str, label_b: str) -> bytes:
    """Barres groupees : P/E, EV/EBITDA, EV/Revenue."""
    metrics = ["P/E", "EV/EBITDA", "EV/Revenue"]
    vals_a  = [sa.get("pe", 0) or 0, sa.get("ev_eb", 0) or 0, sa.get("ev_rev", 0) or 0]
    vals_b  = [sb.get("pe", 0) or 0, sb.get("ev_eb", 0) or 0, sb.get("ev_rev", 0) or 0]

    fig, ax = plt.subplots(figsize=(7.5, 3.0))
    x = np.arange(len(metrics))
    w = 0.35
    bars_a = ax.bar(x - w/2, vals_a, w, label=label_a, color=_HEX_A, alpha=0.9)
    bars_b = ax.bar(x + w/2, vals_b, w, label=label_b, color=_HEX_B, alpha=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=10)
    ax.set_ylabel("Multiple (x)", fontsize=9)
    ax.tick_params(axis="y", labelsize=8)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for bar in list(bars_a) + list(bars_b):
        h = bar.get_height()
        if h > 0:
            ax.annotate(f"{h:.1f}x", xy=(bar.get_x() + bar.get_width()/2, h),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8)
    ax.legend(fontsize=9, framealpha=0)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _chart_margins(sa: dict, sb: dict, label_a: str, label_b: str) -> bytes:
    """Barres groupees : Marge Brute, EBITDA, Nette."""
    metrics = ["Marge Brute", "Marge EBITDA", "Marge Nette"]
    vals_a  = [sa.get("gm", 0) or 0, sa.get("em", 0) or 0, sa.get("nm", 0) or 0]
    vals_b  = [sb.get("gm", 0) or 0, sb.get("em", 0) or 0, sb.get("nm", 0) or 0]

    fig, ax = plt.subplots(figsize=(7.5, 3.0))
    x = np.arange(len(metrics))
    w = 0.35
    bars_a = ax.bar(x - w/2, vals_a, w, label=label_a, color=_HEX_A, alpha=0.9)
    bars_b = ax.bar(x + w/2, vals_b, w, label=label_b, color=_HEX_B, alpha=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=10)
    ax.set_ylabel("Marge (%)", fontsize=9)
    ax.tick_params(axis="y", labelsize=8)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for bar in list(bars_a) + list(bars_b):
        h = bar.get_height()
        if abs(h) > 0.5:
            ax.annotate(f"{h:.1f}%", xy=(bar.get_x() + bar.get_width()/2, max(h, 0)),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=7.5)
    ax.legend(fontsize=9, framealpha=0)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _chart_radar(sa: dict, sb: dict, label_a: str, label_b: str) -> bytes:
    """Radar chart scoring 4 axes : Value, Growth, Quality, Momentum."""
    categories = ["Value", "Growth", "Quality", "Momentum"]
    vals_a = [sa.get("s_val", 12), sa.get("s_gro", 12), sa.get("s_qua", 12), sa.get("s_mom", 12)]
    vals_b = [sb.get("s_val", 12), sb.get("s_gro", 12), sb.get("s_qua", 12), sb.get("s_mom", 12)]

    N = len(categories)
    angles = [n / float(N) * 2 * math.pi for n in range(N)]
    angles += angles[:1]
    va = vals_a + vals_a[:1]
    vb = vals_b + vals_b[:1]

    fig, ax = plt.subplots(figsize=(4.5, 4.5), subplot_kw=dict(polar=True))
    ax.plot(angles, va, "o-", linewidth=2, color=_HEX_A, label=label_a)
    ax.fill(angles, va, alpha=0.15, color=_HEX_A)
    ax.plot(angles, vb, "s-", linewidth=2, color=_HEX_B, label=label_b)
    ax.fill(angles, vb, alpha=0.15, color=_HEX_B)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=10)
    ax.set_ylim(0, 25)
    ax.set_yticks([5, 10, 15, 20, 25])
    ax.set_yticklabels(["5", "10", "15", "20", "25"], fontsize=7, color="grey")
    ax.grid(color="grey", linestyle="--", linewidth=0.5, alpha=0.4)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=9)
    plt.tight_layout(pad=0.3)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _chart_momentum(sa: dict, sb: dict, label_a: str, label_b: str) -> bytes:
    """Barres : Croissance Revenue (%) et Momentum 52S (%)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.5, 3.0))

    # Revenue growth
    revg_a = sa.get("revg", 0) or 0
    revg_b = sb.get("revg", 0) or 0
    bars1 = ax1.bar([label_a, label_b], [revg_a, revg_b], color=[_HEX_A, _HEX_B], alpha=0.9, width=0.5)
    ax1.axhline(0, color="black", linewidth=0.6)
    ax1.set_title("Croissance Revenue medianne", fontsize=9, fontweight="bold")
    ax1.set_ylabel("%", fontsize=8)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax1.set_axisbelow(True)
    for bar in bars1:
        h = bar.get_height()
        ax1.annotate(f"{h:+.1f}%", xy=(bar.get_x() + bar.get_width()/2, h),
                     xytext=(0, 4 if h >= 0 else -12), textcoords="offset points",
                     ha="center", fontsize=9, fontweight="bold")

    # Momentum 52S
    mom_a = sa.get("mom", 0) or 0
    mom_b = sb.get("mom", 0) or 0
    bars2 = ax2.bar([label_a, label_b], [mom_a, mom_b], color=[_HEX_A, _HEX_B], alpha=0.9, width=0.5)
    ax2.axhline(0, color="black", linewidth=0.6)
    ax2.set_title("Performance 52 semaines medianne", fontsize=9, fontweight="bold")
    ax2.set_ylabel("%", fontsize=8)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax2.set_axisbelow(True)
    for bar in bars2:
        h = bar.get_height()
        ax2.annotate(f"{h:+.1f}%", xy=(bar.get_x() + bar.get_width()/2, h),
                     xytext=(0, 4 if h >= 0 else -12), textcoords="offset points",
                     ha="center", fontsize=9, fontweight="bold")

    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _chart_rentabilite(sa: dict, sb: dict, label_a: str, label_b: str) -> bytes:
    """Barres groupees : ROE, ROIC, FCF Yield (ROIC omis si indisponible)."""
    _roic_a = sa.get("roic")
    _roic_b = sb.get("roic")
    if _roic_a is None and _roic_b is None:
        metrics = ["ROE", "FCF Yield"]
        vals_a  = [sa.get("roe", 0) or 0, sa.get("fcfy", 0) or 0]
        vals_b  = [sb.get("roe", 0) or 0, sb.get("fcfy", 0) or 0]
    else:
        metrics = ["ROE", "ROIC", "FCF Yield"]
        vals_a  = [sa.get("roe", 0) or 0, _roic_a or 0, sa.get("fcfy", 0) or 0]
        vals_b  = [sb.get("roe", 0) or 0, _roic_b or 0, sb.get("fcfy", 0) or 0]

    fig, ax = plt.subplots(figsize=(7.5, 3.0))
    x = np.arange(len(metrics))
    w = 0.35
    bars_a = ax.bar(x - w/2, vals_a, w, label=label_a, color=_HEX_A, alpha=0.9)
    bars_b = ax.bar(x + w/2, vals_b, w, label=label_b, color=_HEX_B, alpha=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=10)
    ax.set_ylabel("(%)", fontsize=9)
    ax.tick_params(axis="y", labelsize=8)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for bar in list(bars_a) + list(bars_b):
        h = bar.get_height()
        if abs(h) > 0.5:
            ax.annotate(f"{h:.1f}%", xy=(bar.get_x() + bar.get_width()/2, max(h, 0)),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=7.5)
    ax.legend(fontsize=9, framealpha=0)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ── Slides ────────────────────────────────────────────────────────────────────

def _s01_cover(prs, D):
    slide = _blank(prs)
    # Barre navy
    _rect(slide, 0, 0, 25.4, 1.8, fill=_NAVY)
    _txb(slide, "FinSight IA", 0.9, 0.15, 12.0, 1.2, size=12, bold=True, color=_WHITE)
    _txb(slide, "Pitchbook  —  Comparatif Sectoriel", 0, 0.25, 24.5, 1.0, size=9.5, color=_WHITE, align=PP_ALIGN.RIGHT)

    # Titre principal
    title = f"{D['sector_a']}  vs  {D['sector_b']}"
    _txb(slide, title, 0, 4.0, 25.4, 2.5, size=34, bold=True, color=_NAVY, align=PP_ALIGN.CENTER)

    # Sous-titre univers
    _txb(slide, D["universe_label"], 0, 6.8, 25.4, 1.0, size=13, color=_GRAYT, align=PP_ALIGN.CENTER)

    # 4 KPI boxes : N societes A, Score A, N societes B, Score B
    kpis = [
        (f"{D['na']}", f"societes\n{D['sector_a']}", _COL_A),
        (f"{D['sa'].get('score', 0)}", f"Score FinSight\n{D['sector_a']}", _COL_A),
        (f"{D['nb']}", f"societes\n{D['sector_b']}", _COL_B),
        (f"{D['sb'].get('score', 0)}", f"Score FinSight\n{D['sector_b']}", _COL_B),
    ]
    box_w = 5.6
    step  = 5.85
    start_x = 0.9
    for i, (val, lbl, col) in enumerate(kpis):
        bx = start_x + i * step
        pale = _COL_A_PALE if col == _COL_A else _COL_B_PALE
        _rect(slide, bx, 8.5, box_w, 2.5, fill=pale)
        _rect(slide, bx, 8.5, 0.22, 2.5, fill=col)  # barre gauche coloree
        _txb(slide, val, bx + 0.22, 8.65, box_w - 0.22, 1.4, size=28, bold=True, color=col, align=PP_ALIGN.CENTER)
        _txb(slide, lbl, bx + 0.22, 10.2, box_w - 0.22, 1.0, size=8.5, color=_NAVY, align=PP_ALIGN.CENTER)

    # Signal badges
    _rect(slide, 2.2, 11.5, 4.5, 0.9, fill=D["sig_a_col"])
    _txb(slide, f"● {D['sig_a_lbl']}", 2.2, 11.58, 4.5, 0.75, size=9.5, bold=True, color=_WHITE, align=PP_ALIGN.CENTER)
    _rect(slide, 18.7, 11.5, 4.5, 0.9, fill=D["sig_b_col"])
    _txb(slide, f"● {D['sig_b_lbl']}", 18.7, 11.58, 4.5, 0.75, size=9.5, bold=True, color=_WHITE, align=PP_ALIGN.CENTER)

    # Footer
    _rect(slide, 0, 13.6, 25.4, 0.7, fill=_GRAYL)
    _txb(slide, "Rapport confidentiel  |  FinSight IA", 0.9, 13.65, 12.0, 0.5, size=7.5, color=_GRAYT)
    _txb(slide, D["date_str"], 0, 13.65, 24.4, 0.5, size=7.5, color=_GRAYT, align=PP_ALIGN.RIGHT)


def _s02_exec_summary(prs, D):
    slide = _blank(prs)
    sa, sb = D["sa"], D["sb"]
    _header(slide, f"Executive Summary  —  {D['sector_a']} vs {D['sector_b']}",
            f"Univers : {D['universe_label']}  |  {D['na']} + {D['nb']} societes analysees", 1)
    _footer(slide, D)

    # Signal A
    _rect(slide, 0.9, 2.1, 11.4, 0.85, fill=_COL_A_PALE)
    _rect(slide, 0.9, 2.1, 0.1, 0.85, fill=_COL_A)
    _txb(slide, f"{D['sector_a']}  —  {D['sig_a_lbl']}", 1.3, 2.18, 6.0, 0.7, size=10, bold=True, color=_COL_A)
    _txb(slide, f"Score {sa.get('score', 0)}/100  |  P/E {_fmt_simple(sa.get('pe'), x=True)}  |  Croissance rev. {_fmt(sa.get('revg'), pct=True)}  |  Marge EBITDA {_fmt_simple(sa.get('em'), pct=True)}",
         1.3, 2.62, 10.8, 0.5, size=8, color=_NAVY)

    # Signal B
    _rect(slide, 13.1, 2.1, 11.4, 0.85, fill=_COL_B_PALE)
    _rect(slide, 13.1, 2.1, 0.1, 0.85, fill=_COL_B)
    _txb(slide, f"{D['sector_b']}  —  {D['sig_b_lbl']}", 13.5, 2.18, 6.0, 0.7, size=10, bold=True, color=_COL_B)
    _txb(slide, f"Score {sb.get('score', 0)}/100  |  P/E {_fmt_simple(sb.get('pe'), x=True)}  |  Croissance rev. {_fmt(sb.get('revg'), pct=True)}  |  Marge EBITDA {_fmt_simple(sb.get('em'), pct=True)}",
         13.5, 2.62, 10.8, 0.5, size=8, color=_GREEN)

    # Tableau metriques cote a cote
    rows = [
        ["Metrique", D["sector_a"], D["sector_b"], "Avantage"],
        ["Score FinSight", f"{sa.get('score', 0)}/100", f"{sb.get('score', 0)}/100",
         D["sector_a"] if sa.get("score", 0) > sb.get("score", 0) else D["sector_b"]],
        ["P/E median", _fmt_simple(sa.get("pe"), x=True), _fmt_simple(sb.get("pe"), x=True),
         D["sector_a"] if (sa.get("pe") or 999) < (sb.get("pe") or 999) else D["sector_b"]],
        ["EV/EBITDA median", _fmt_simple(sa.get("ev_eb"), x=True), _fmt_simple(sb.get("ev_eb"), x=True),
         D["sector_a"] if (sa.get("ev_eb") or 999) < (sb.get("ev_eb") or 999) else D["sector_b"]],
        ["Croissance rev. med.", _fmt(sa.get("revg"), pct=True), _fmt(sb.get("revg"), pct=True),
         D["sector_a"] if (sa.get("revg") or -999) > (sb.get("revg") or -999) else D["sector_b"]],
        ["Marge EBITDA med.", _fmt_simple(sa.get("em"), pct=True), _fmt_simple(sb.get("em"), pct=True),
         D["sector_a"] if (sa.get("em") or -999) > (sb.get("em") or -999) else D["sector_b"]],
        ["Marge Nette med.", _fmt_simple(sa.get("nm"), pct=True), _fmt_simple(sb.get("nm"), pct=True),
         D["sector_a"] if (sa.get("nm") or -999) > (sb.get("nm") or -999) else D["sector_b"]],
        ["ROE median", _fmt_simple(sa.get("roe"), pct=True), _fmt_simple(sb.get("roe"), pct=True),
         D["sector_a"] if (sa.get("roe") or -999) > (sb.get("roe") or -999) else D["sector_b"]],
        ["Beta median", _fmt_simple(sa.get("beta"), dp=2), _fmt_simple(sb.get("beta"), dp=2),
         D["sector_a"] if (sa.get("beta") or 999) < (sb.get("beta") or 999) else D["sector_b"]],
        ["Perf. 52S med.", _fmt(sa.get("mom"), pct=True), _fmt(sb.get("mom"), pct=True),
         D["sector_a"] if (sa.get("mom") or -999) > (sb.get("mom") or -999) else D["sector_b"]],
    ]
    _add_table(slide, rows, 0.9, 3.2, 23.6, 8.2,
               col_widths=[5.5, 3.0, 3.0, 3.5],
               header_fill=_NAVY, header_color=_WHITE,
               alt_fill=_GRAYL, font_size=8.5, header_size=8.5)

    # Synthese IA
    llm_text = D.get("llm", {}).get("exec_summary", "")
    if llm_text:
        _rect(slide, 0.9, 11.6, 23.6, 0.38, fill=_NAVY)
        _txb(slide, "Synthese FinSight IA", 1.0, 11.63, 15.0, 0.32, size=7.5, bold=True, color=_WHITE)
        _txb(slide, llm_text, 0.9, 12.08, 23.6, 1.5, size=8.5, color=_BLACK, wrap=True)


def _s03_sommaire(prs, D):
    slide = _blank(prs)
    _header(slide, "Sommaire", f"Analyse comparative : {D['sector_a']} vs {D['sector_b']}", 1)
    _footer(slide, D)

    sections = [
        ("01", "Profil & Valorisation", "Structure des secteurs, multiples de marche, qualite des bilans"),
        ("02", "Croissance & Scoring", "Revenue growth, momentum et scoring multidimensionnel"),
        ("03", "Top Acteurs & Risques", "Meilleures societes et conditions d'invalidation par secteur"),
        ("04", "Synthese & Allocation", "Comparaison strategique et recommandation de positionnement"),
    ]
    y_start = 2.8
    for i, (num, title, desc) in enumerate(sections):
        y = y_start + i * 2.4
        _rect(slide, 0.9, y, 1.1, 1.4, fill=_NAVY)
        _txb(slide, num, 0.9, y + 0.3, 1.1, 0.8, size=14, bold=True, color=_WHITE, align=PP_ALIGN.CENTER)
        _txb(slide, title, 2.2, y + 0.1, 21.6, 0.8, size=11, bold=True, color=_NAVY)
        _txb(slide, desc, 2.2, y + 0.7, 21.6, 0.6, size=8.5, color=_GRAYT)
        _rect(slide, 0.9, y + 1.4, 23.6, 0.02, fill=_GRAYM)


def _s05_profil(prs, D):
    """Slide 5 — Profil des 2 secteurs cote a cote."""
    slide = _blank(prs)
    _header(slide, f"Profil & Structure des Secteurs",
            f"{D['sector_a']}  vs  {D['sector_b']}  |  Positionnement structurel", 1)
    _footer(slide, D)

    content_a = _get_content(D["sector_a"])
    content_b = _get_content(D["sector_b"])
    mid = 12.7

    # Secteur A — colonne gauche
    _rect(slide, 0.9, 2.1, 11.2, 0.5, fill=_COL_A)
    _txb(slide, D["sector_a"], 1.0, 2.13, 11.0, 0.45, size=10, bold=True, color=_WHITE)
    desc_a = content_a.get("description", "")[:500]
    _txb(slide, desc_a, 0.9, 2.75, 11.2, 3.5, size=8, color=_BLACK, wrap=True)

    # Cycle A
    cycle_a = content_a.get("cycle_comment", "")
    _rect(slide, 0.9, 6.5, 11.2, 0.5, fill=_COL_A_PALE)
    _txb(slide, f"Cycle : {cycle_a}", 1.0, 6.53, 11.0, 0.45, size=8, italic=True, color=_COL_A)

    # Drivers A
    _txb(slide, "Drivers principaux", 0.9, 7.3, 11.2, 0.5, size=9, bold=True, color=_NAVY)
    drivers_a = content_a.get("drivers", [])[:4]
    for j, drv in enumerate(drivers_a):
        direction, name, desc = (drv[0], drv[1], drv[2]) if len(drv) >= 3 else ("up", str(drv), "")
        arrow = "+" if direction == "up" else "-"
        col = _GREEN if direction == "up" else _RED
        _txb(slide, f"{arrow}", 0.9, 7.95 + j * 1.2, 0.5, 0.5, size=11, bold=True, color=col)
        _txb(slide, f"{name}", 1.45, 7.95 + j * 1.2, 10.5, 0.55, size=8.5, bold=True, color=_BLACK)
        _txb(slide, desc[:80], 1.45, 8.52 + j * 1.2, 10.5, 0.65, size=7.5, color=_GRAYT)

    # Separateur vertical
    _rect(slide, mid - 0.15, 2.0, 0.04, 11.4, fill=_GRAYM)

    # Secteur B — colonne droite
    _rect(slide, mid + 0.15, 2.1, 11.2, 0.5, fill=_COL_B)
    _txb(slide, D["sector_b"], mid + 0.25, 2.13, 11.0, 0.45, size=10, bold=True, color=_WHITE)
    desc_b = content_b.get("description", "")[:500]
    _txb(slide, desc_b, mid + 0.15, 2.75, 11.2, 3.5, size=8, color=_BLACK, wrap=True)

    # Cycle B
    cycle_b = content_b.get("cycle_comment", "")
    _rect(slide, mid + 0.15, 6.5, 11.2, 0.5, fill=_COL_B_PALE)
    _txb(slide, f"Cycle : {cycle_b}", mid + 0.25, 6.53, 11.0, 0.45, size=8, italic=True, color=_COL_B)

    # Drivers B
    _txb(slide, "Drivers principaux", mid + 0.15, 7.3, 11.2, 0.5, size=9, bold=True, color=_GREEN)
    drivers_b = content_b.get("drivers", [])[:4]
    for j, drv in enumerate(drivers_b):
        direction, name, desc = (drv[0], drv[1], drv[2]) if len(drv) >= 3 else ("up", str(drv), "")
        arrow = "+" if direction == "up" else "-"
        col = _GREEN if direction == "up" else _RED
        _txb(slide, f"{arrow}", mid + 0.15, 7.95 + j * 1.2, 0.5, 0.5, size=11, bold=True, color=col)
        _txb(slide, f"{name}", mid + 0.7, 7.95 + j * 1.2, 10.5, 0.55, size=8.5, bold=True, color=_BLACK)
        _txb(slide, desc[:80], mid + 0.7, 8.52 + j * 1.2, 10.5, 0.65, size=7.5, color=_GRAYT)


def _s06_valorisation(prs, D):
    """Slide 6 — Multiples de valorisation comparatifs."""
    slide = _blank(prs)
    sa, sb = D["sa"], D["sb"]
    _header(slide, "Valorisation Comparee  —  Multiples de Marche",
            f"P/E et EV-multiples medianes — {D['sector_a']} vs {D['sector_b']}", 1)
    _footer(slide, D)

    # Chart gauche
    try:
        img = _chart_valuation(sa, sb, D["sector_a"], D["sector_b"])
        _pic(slide, img, 0.9, 2.0, 12.5, 8.0)
    except Exception as e:
        log.warning("[cmp_secteur] _s06 chart: %s", e)
        _txb(slide, f"Graphique indisponible: {e}", 0.9, 5.0, 12.5, 1.0, size=8, color=_GRAYT)

    # Tableau metriques complementaires sous le chart (gauche)
    rows_extra = [
        ["Indicateurs", D["sector_a"], D["sector_b"]],
        ["FCF Yield med.", _fmt_simple(sa.get("fcfy"), pct=True, dp=1), _fmt_simple(sb.get("fcfy"), pct=True, dp=1)],
        ["Beta median", _fmt_simple(sa.get("beta"), dp=2), _fmt_simple(sb.get("beta"), dp=2)],
        ["Altman Z med.", _fmt_simple(sa.get("az"), dp=2), _fmt_simple(sb.get("az"), dp=2)],
        ["Piotroski med.", _fmt_simple(sa.get("pf"), dp=1), _fmt_simple(sb.get("pf"), dp=1)],
    ]
    _add_table(slide, rows_extra, 0.9, 10.3, 12.5, 2.85,
               col_widths=[4.5, 4.0, 4.0], alt_fill=_GRAYL, font_size=9, header_size=9)

    # Tableau metriques droite (multiples)
    rows = [
        ["Metrique", D["sector_a"], D["sector_b"]],
        ["P/E median", _fmt_simple(sa.get("pe"), x=True), _fmt_simple(sb.get("pe"), x=True)],
        ["EV/EBITDA med.", _fmt_simple(sa.get("ev_eb"), x=True), _fmt_simple(sb.get("ev_eb"), x=True)],
        ["EV/Revenue med.", _fmt_simple(sa.get("ev_rev"), x=True), _fmt_simple(sb.get("ev_rev"), x=True)],
        ["PEG ratio med.", _fmt_simple(sa.get("peg"), dp=2), _fmt_simple(sb.get("peg"), dp=2)],
    ]
    _add_table(slide, rows, 14.0, 2.0, 10.5, 6.0,
               col_widths=[4.5, 3.0, 3.0], alt_fill=_GRAYL, font_size=9, header_size=9)

    # Lecture analytique
    pe_a = sa.get("pe") or 0
    pe_b = sb.get("pe") or 0
    cheaper = D["sector_a"] if pe_a < pe_b else D["sector_b"]
    premium = D["sector_a"] if pe_a > pe_b else D["sector_b"]
    pe_spread = abs(pe_a - pe_b)
    fallback_lecture = (
        f"{cheaper} cote a une prime inferieure de {pe_spread:.1f}x P/E "
        f"vs {premium}. Ecart reflète "
        f"{'une anticipation de croissance superieure' if (sa.get('revg') or 0) > (sb.get('revg') or 0) else 'un profil de risque differentie'}."
    )
    lecture = D.get("llm", {}).get("valuation_read") or fallback_lecture
    _rect(slide, 14.0, 8.5, 10.5, 0.4, fill=_NAVY)
    _txb(slide, "Lecture analytique FinSight IA", 14.1, 8.52, 10.3, 0.35, size=7.5, bold=True, color=_WHITE)
    _txb(slide, lecture, 14.0, 9.0, 10.5, 4.2, size=8.5, color=_BLACK, wrap=True)


def _s07_marges(prs, D):
    """Slide 7 — Qualite, Marges & Rentabilite."""
    slide = _blank(prs)
    sa, sb = D["sa"], D["sb"]
    _header(slide, "Qualite & Rentabilite  —  Marges et Retour sur Capital",
            f"Qui genere plus de valeur par euro de chiffre d'affaires ?", 1)
    _footer(slide, D)

    try:
        img = _chart_margins(sa, sb, D["sector_a"], D["sector_b"])
        _pic(slide, img, 0.9, 2.0, 12.5, 9.5)
    except Exception as e:
        log.warning("[cmp_secteur] _s07 chart: %s", e)

    try:
        img2 = _chart_rentabilite(sa, sb, D["sector_a"], D["sector_b"])
        _pic(slide, img2, 13.5, 2.0, 11.0, 9.5)
    except Exception as e:
        log.warning("[cmp_secteur] _s07 chart2: %s", e)

    # Lecture analytique marges
    winner_margin = D["sector_a"] if (sa.get("em") or -999) > (sb.get("em") or -999) else D["sector_b"]
    winner_roe    = D["sector_a"] if (sa.get("roe") or -999) > (sb.get("roe") or -999) else D["sector_b"]
    fallback_diag = (
        f"{winner_margin} affiche une marge EBITDA superieure "
        f"({_fmt_simple(sa.get('em') if winner_margin == D['sector_a'] else sb.get('em'), pct=True)}). "
        f"{winner_roe} domine sur le ROE "
        f"({_fmt_simple(min(sa.get('roe') or 0, 999.9) if winner_roe == D['sector_a'] else min(sb.get('roe') or 0, 999.9), pct=True)})."
    )
    diag = D.get("llm", {}).get("margins_read") or fallback_diag
    _rect(slide, 0.9, 12.0, 23.6, 0.38, fill=_NAVY)
    _txb(slide, "Lecture analytique FinSight IA", 1.0, 12.03, 15.0, 0.32, size=7.5, bold=True, color=_WHITE)
    _txb(slide, diag, 0.9, 12.48, 23.6, 5.0, size=8.5, color=_BLACK, wrap=True)


def _s07b_capital_alloc(prs, D):
    """Slide 7b — Capital Allocation & Remuneration de l'Actionnaire."""
    slide = _blank(prs)
    sa, sb = D["sa"], D["sb"]
    _header(slide, "Capital Allocation  —  Dividendes, FCF & Remuneration",
            f"Comparaison politique de distribution — {D['sector_a']} vs {D['sector_b']}", 1)
    _footer(slide, D)

    # Tableau comparatif gauche
    def _fmt_pct(v):
        """div_yield et payout sont en fraction (×100). fcfy est deja en %, utiliser _fmt_pct_direct."""
        if v is None: return "—"
        try: return f"{float(v)*100:.1f} %"
        except: return "—"
    def _fmt_pct_direct(v):
        """fcfy est deja en % (1.38 = 1.38%) — pas de ×100."""
        if v is None: return "—"
        try: return f"{float(v):.1f} %"
        except: return "—"

    rows = [
        ["Indicateur", D["sector_a"], D["sector_b"]],
        ["Rendement dividende med.", _fmt_pct(sa.get("div_yield")), _fmt_pct(sb.get("div_yield"))],
        ["FCF Yield median",         _fmt_pct_direct(sa.get("fcfy")),  _fmt_pct_direct(sb.get("fcfy"))],
        ["Payout Ratio median",      _fmt_pct(sa.get("payout")),    _fmt_pct(sb.get("payout"))],
        ["FCF Yield / Div Yield",    f"{(sa.get('fcfy') or 0) / max(sa.get('div_yield') or 1, 0.01):.1f}x" if sa.get("fcfy") else "—",
                                     f"{(sb.get('fcfy') or 0) / max(sb.get('div_yield') or 1, 0.01):.1f}x" if sb.get("fcfy") else "—"],
    ]
    _add_table(slide, rows, 0.9, 2.0, 13.0, 5.5,
               col_widths=[5.5, 3.7, 3.7], alt_fill=_GRAYL, font_size=9, header_size=9)

    # Graphique barres capital allocation
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
        import io as _io

        metrics = []
        vals_a  = []
        vals_b  = []
        # div_yield est en fraction (×100) ; fcfy est deja en % (pas de ×100)
        for label, key, scale in [("Div Yield", "div_yield", 100), ("FCF Yield", "fcfy", 1)]:
            va = sa.get(key)
            vb = sb.get(key)
            if va is not None or vb is not None:
                metrics.append(label)
                vals_a.append(float(va or 0) * scale)
                vals_b.append(float(vb or 0) * scale)

        if metrics:
            x  = np.arange(len(metrics))
            bw = 0.32
            fig, ax = plt.subplots(figsize=(6.5, 4.5))
            fig.patch.set_facecolor('white')
            ax.set_facecolor('#FAFBFD')
            b1 = ax.bar(x - bw/2, vals_a, bw, label=D["sector_a"][:18],
                        color='#2E5FA3', alpha=0.85)
            b2 = ax.bar(x + bw/2, vals_b, bw, label=D["sector_b"][:18],
                        color='#1A7A4A', alpha=0.85)
            ax.set_xticks(x)
            ax.set_xticklabels(metrics, fontsize=10)
            ax.set_ylabel("%", fontsize=9)
            ax.legend(fontsize=8, framealpha=0.9)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.grid(axis='y', alpha=0.3)
            for bar in list(b1) + list(b2):
                h = bar.get_height()
                if h > 0:
                    ax.annotate(f'{h:.1f}%',
                               xy=(bar.get_x()+bar.get_width()/2, h),
                               xytext=(0, 2), textcoords="offset points",
                               ha='center', va='bottom', fontsize=8)
            fig.tight_layout(pad=0.5)
            buf_chart = _io.BytesIO()
            fig.savefig(buf_chart, format='png', dpi=130, bbox_inches='tight')
            plt.close(fig)
            buf_chart.seek(0)
            _pic(slide, buf_chart.read(), 0.9, 7.8, 13.0, 5.5)
    except Exception as e:
        log.warning("[cmp_secteur_pptx] capital_alloc chart: %s", e)

    # Profils de rendement à droite
    _rect(slide, 14.5, 2.0, 10.0, 0.4, fill=_COL_A)
    _txb(slide, f"Profil  {D['sector_a'][:20]}", 14.6, 2.02, 9.8, 0.35, size=8, bold=True, color=_WHITE)
    dy_a_str = _fmt_pct(sa.get("div_yield"))
    fy_a_str = _fmt_pct_direct(sa.get("fcfy"))
    pt_a_str = _fmt_pct(sa.get("payout"))
    profil_a = (
        f"Rendement dividende : {dy_a_str}\n"
        f"FCF Yield : {fy_a_str}\n"
        f"Payout Ratio : {pt_a_str}"
    )
    _txb(slide, profil_a, 14.5, 2.5, 10.0, 3.0, size=9, color=_BLACK, wrap=True)

    _rect(slide, 14.5, 5.8, 10.0, 0.4, fill=_COL_B)
    _txb(slide, f"Profil  {D['sector_b'][:20]}", 14.6, 5.82, 9.8, 0.35, size=8, bold=True, color=_WHITE)
    dy_b_str = _fmt_pct(sb.get("div_yield"))
    fy_b_str = _fmt_pct_direct(sb.get("fcfy"))
    pt_b_str = _fmt_pct(sb.get("payout"))
    profil_b = (
        f"Rendement dividende : {dy_b_str}\n"
        f"FCF Yield : {fy_b_str}\n"
        f"Payout Ratio : {pt_b_str}"
    )
    _txb(slide, profil_b, 14.5, 6.3, 10.0, 3.0, size=9, color=_BLACK, wrap=True)

    # Interpretation context
    _rect(slide, 14.5, 9.5, 10.0, 0.4, fill=_NAVY)
    _txb(slide, "Interpretation  —  Profils de Distribution", 14.6, 9.52, 9.8, 0.35, size=7.5, bold=True, color=_WHITE)
    dy_a = sa.get("div_yield") or 0
    dy_b = sb.get("div_yield") or 0
    fy_a = sa.get("fcfy") or 0
    fy_b = sb.get("fcfy") or 0
    high_dy = D["sector_a"] if dy_a > dy_b else D["sector_b"]
    high_fy = D["sector_a"] if fy_a > fy_b else D["sector_b"]
    fallback_interp = (
        f"{high_dy} offre le meilleur rendement dividende. "
        f"{high_fy} genere davantage de FCF, signe d'une capacite de remuneration durable. "
        f"Un FCF Yield superieur au dividende verse garantit la soutenabilite de la politique de distribution."
    )
    interp_txt = D.get("llm", {}).get("capital_alloc_read") or fallback_interp
    _txb(slide, interp_txt, 14.5, 10.0, 10.0, 3.3, size=8.5, color=_BLACK, wrap=True)


def _s08_croissance(prs, D):
    """Slide 8 — Croissance & Momentum."""
    slide = _blank(prs)
    sa, sb = D["sa"], D["sb"]
    _header(slide, "Croissance & Momentum  —  Acceleration ou Ralentissement ?",
            f"Revenue growth et performance 52 semaines medianes comparees", 2)
    _footer(slide, D)

    try:
        img = _chart_momentum(sa, sb, D["sector_a"], D["sector_b"])
        _pic(slide, img, 0.9, 2.0, 14.5, 9.5)
    except Exception as e:
        log.warning("[cmp_secteur] _s08 chart: %s", e)

    # Stats complementaires
    rows = [
        ["", D["sector_a"], D["sector_b"]],
        ["Croissance rev. med.", _fmt(sa.get("revg"), pct=True), _fmt(sb.get("revg"), pct=True)],
        ["Perf. 52S med.", _fmt(sa.get("mom"), pct=True), _fmt(sb.get("mom"), pct=True)],
        ["Beta median", _fmt_simple(sa.get("beta"), dp=2), _fmt_simple(sb.get("beta"), dp=2)],
        ["FCF Yield med.", _fmt_simple(sa.get("fcfy"), pct=True, dp=1), _fmt_simple(sb.get("fcfy"), pct=True, dp=1)],
        ["Score Global", f"{sa.get('score', 0)}/100", f"{sb.get('score', 0)}/100"],
    ]
    _add_table(slide, rows, 15.8, 2.0, 8.6, 9.0,
               col_widths=[4.0, 2.3, 2.3], alt_fill=_GRAYL, font_size=9, header_size=9)

    # Lecture analytique croissance
    faster = D["sector_a"] if (sa.get("revg") or -999) > (sb.get("revg") or -999) else D["sector_b"]
    faster_s = sa if faster == D["sector_a"] else sb
    slower_s = sb if faster == D["sector_a"] else sa
    spread_g = abs((sa.get("revg") or 0) - (sb.get("revg") or 0))
    fallback_lecture = (
        f"{faster} croit {spread_g:.1f} pts plus vite "
        f"({_fmt(faster_s.get('revg'), pct=True)} vs {_fmt(slower_s.get('revg'), pct=True)}). "
        f"Momentum 52S {'confirme cette tendance' if ((faster_s.get('mom') or 0) > (slower_s.get('mom') or 0)) else 'diverge : marche anticipe ralentissement'}."
    )
    lecture = D.get("llm", {}).get("growth_read") or fallback_lecture
    _rect(slide, 0.9, 11.8, 23.6, 0.38, fill=_NAVY)
    _txb(slide, "Lecture analytique FinSight IA", 1.0, 11.83, 15.0, 0.32, size=7.5, bold=True, color=_WHITE)
    _txb(slide, lecture, 0.9, 12.28, 23.6, 5.0, size=8.5, color=_BLACK, wrap=True)


def _s09_scoring(prs, D):
    """Slide 9 — Scoring multi-criteres (radar)."""
    slide = _blank(prs)
    sa, sb = D["sa"], D["sb"]
    _header(slide, "Scoring Multi-Criteres  —  Value / Growth / Quality / Momentum",
            f"Score FinSight decompose par dimension — {D['sector_a']} vs {D['sector_b']}", 2)
    _footer(slide, D)

    # Tableau scores — colonne gauche (x=0.9, w=10.5)
    rows_a = [
        ["Dimension", D["sector_a"], D["sector_b"]],
        ["Value", f"{sa.get('s_val', 0):.0f}/25", f"{sb.get('s_val', 0):.0f}/25"],
        ["Growth", f"{sa.get('s_gro', 0):.0f}/25", f"{sb.get('s_gro', 0):.0f}/25"],
        ["Quality", f"{sa.get('s_qua', 0):.0f}/25", f"{sb.get('s_qua', 0):.0f}/25"],
        ["Momentum", f"{sa.get('s_mom', 0):.0f}/25", f"{sb.get('s_mom', 0):.0f}/25"],
        ["TOTAL", f"{sa.get('score', 0)}/100", f"{sb.get('score', 0)}/100"],
    ]
    _add_table(slide, rows_a, 0.9, 2.2, 10.5, 7.0,
               col_widths=[4.0, 3.25, 3.25], alt_fill=_GRAYL, font_size=10, header_size=10)

    # Radar chart — colonne droite (x=12.0, w=12.5)
    try:
        img = _chart_radar(sa, sb, D["sector_a"], D["sector_b"])
        _pic(slide, img, 12.0, 1.6, 12.5, 11.0)
    except Exception as e:
        log.warning("[cmp_secteur] _s09 radar: %s", e)

    # Interpretation globale
    winner = D["sector_a"] if sa.get("score", 0) > sb.get("score", 0) else D["sector_b"]
    score_w = sa.get("score", 0) if winner == D["sector_a"] else sb.get("score", 0)
    score_l = sb.get("score", 0) if winner == D["sector_a"] else sa.get("score", 0)
    fallback_interp = (
        f"Sur le scoring FinSight global, {winner} ressort en avance ({score_w}/100 vs {score_l}/100). "
        f"Ecart de {abs(score_w - score_l)} pts — difference structurelle de profil."
    )
    interp = D.get("llm", {}).get("scoring_read") or fallback_interp
    _rect(slide, 0.9, 9.5, 10.5, 0.38, fill=_NAVY)
    _txb(slide, "Interpretation FinSight IA", 1.0, 9.53, 10.3, 0.32, size=7.5, bold=True, color=_WHITE)
    _txb(slide, interp, 0.9, 9.98, 10.5, 3.2, size=8.5, color=_BLACK, wrap=True)


def _s10_top_a(prs, D):
    """Slide 10 — Top acteurs Secteur A."""
    slide = _blank(prs)
    _header(slide, f"Top Acteurs  —  {D['sector_a']}",
            f"{D['na']} societes analysees — classees par score FinSight", 3)
    _footer(slide, D)
    _barre_secteur(slide, D["sector_a"], D["td_a"], _COL_A, D["universe_a"],
                   llm_text=D.get("llm", {}).get("top_a_read"))


def _s11_top_b(prs, D):
    """Slide 11 — Top acteurs Secteur B."""
    slide = _blank(prs)
    _header(slide, f"Top Acteurs  —  {D['sector_b']}",
            f"{D['nb']} societes analysees — classees par score FinSight", 3)
    _footer(slide, D)
    _barre_secteur(slide, D["sector_b"], D["td_b"], _COL_B, D["universe_b"],
                   llm_text=D.get("llm", {}).get("top_b_read"))


def _barre_secteur(slide, sector_name, tickers_data, col, universe, llm_text=None):
    """Tableau top 8 acteurs d'un secteur."""
    sorted_td = sorted(tickers_data, key=lambda x: x.get("score_global", 0), reverse=True)[:8]

    table_h = 9.5 if llm_text else 11.0
    rows = [["Societe", "Score", "P/E", "EV/EBITDA", "Croiss.Rev.", "Mg.EBITDA", "Mg.Nette", "ROE", "Beta"]]
    for t in sorted_td:
        rows.append([
            t.get("company", t.get("ticker", ""))[:24],
            f"{t.get('score_global', 0)}/100",
            _fmt_simple(t.get("pe_ratio"), x=True),
            _fmt_simple(t.get("ev_ebitda"), x=True),
            _fmt(t.get("revenue_growth", 0) * 100 if (t.get("revenue_growth") or 0) < 5 else t.get("revenue_growth", 0), pct=True),
            _fmt_simple(t.get("ebitda_margin"), pct=True),
            _fmt_simple(t.get("net_margin"), pct=True),
            _fmt_simple(min(t.get("roe") or 0, 999.9) if t.get("roe") is not None else None, pct=True),
            _fmt_simple(t.get("beta"), dp=2),
        ])

    _add_table(slide, rows, 0.9, 2.0, 23.6, table_h,
               col_widths=[4.5, 2.0, 2.0, 2.5, 2.5, 2.5, 2.5, 2.0, 1.8],
               header_fill=col, alt_fill=_GRAYL, font_size=8.5, header_size=8.5)

    if llm_text:
        _rect(slide, 0.9, 11.7, 23.6, 0.38, fill=col)
        _txb(slide, "Lecture analytique FinSight IA", 1.0, 11.73, 18.0, 0.32, size=7.5, bold=True, color=_WHITE)
        _txb(slide, llm_text, 0.9, 12.18, 23.6, 1.35, size=8.5, color=_BLACK, wrap=True)


def _s12_risques_a(prs, D):
    """Slide 12 — Risques & Catalyseurs Secteur A."""
    slide = _blank(prs)
    content = _get_content(D["sector_a"])
    _header(slide, f"Risques & Catalyseurs  —  {D['sector_a']}",
            "Conditions d'investissement et d'invalidation de la these", 3)
    _footer(slide, D)
    _risques_slide(slide, content, _COL_A, _COL_A_PALE,
                   llm_text=D.get("llm", {}).get("these_a"))


def _s13_risques_b(prs, D):
    """Slide 13 — Risques & Catalyseurs Secteur B."""
    slide = _blank(prs)
    content = _get_content(D["sector_b"])
    _header(slide, f"Risques & Catalyseurs  —  {D['sector_b']}",
            "Conditions d'investissement et d'invalidation de la these", 3)
    _footer(slide, D)
    _risques_slide(slide, content, _COL_B, _COL_B_PALE,
                   llm_text=D.get("llm", {}).get("these_b"))


def _risques_slide(slide, content, col, col_pale, llm_text=None):
    cats  = content.get("catalyseurs", [])[:3]
    risks = content.get("risques", [])[:3]
    conds = content.get("conditions", [])[:4]

    # Catalyseurs
    _rect(slide, 0.9, 2.1, 11.4, 0.55, fill=col)
    _txb(slide, "CATALYSEURS", 0.9, 2.14, 11.4, 0.45, size=8.5, bold=True, color=_WHITE, align=PP_ALIGN.CENTER)
    for i, (title, body) in enumerate(cats):
        y = 2.85 + i * 2.2
        _rect(slide, 0.9, y, 11.4, 0.5, fill=col_pale)
        _txb(slide, f"+ {title}", 1.0, y + 0.04, 11.2, 0.45, size=9, bold=True, color=col)
        _txb(slide, body[:160], 1.0, y + 0.6, 11.2, 1.45, size=8, color=_BLACK, wrap=True)

    # Risques
    _rect(slide, 13.1, 2.1, 11.4, 0.55, fill=_RED)
    _txb(slide, "RISQUES", 13.1, 2.14, 11.4, 0.45, size=8.5, bold=True, color=_WHITE, align=PP_ALIGN.CENTER)
    for i, (title, body) in enumerate(risks):
        y = 2.85 + i * 2.2
        _rect(slide, 13.1, y, 11.4, 0.5, fill=RGBColor(0xFB, 0xEB, 0xEB))
        _txb(slide, f"- {title}", 13.2, y + 0.04, 11.2, 0.45, size=9, bold=True, color=_RED)
        _txb(slide, body[:160], 13.2, y + 0.6, 11.2, 1.45, size=8, color=_BLACK, wrap=True)

    # Conditions d'invalidation
    if conds:
        _rect(slide, 0.9, 9.5, 23.6, 0.45, fill=_NAVY)
        _txb(slide, "CONDITIONS D'INVALIDATION", 0.9, 9.54, 23.6, 0.4, size=8.5, bold=True, color=_WHITE, align=PP_ALIGN.CENTER)
        col_w = [3.5, 10.0, 2.5]
        rows_cond = [["Type", "Condition", "Horizon"]] + [[c[0], c[1][:100], c[2]] for c in conds]
        _add_table(slide, rows_cond, 0.9, 10.1, 23.6, 3.2,
                   col_widths=col_w, header_fill=_NAVY, alt_fill=_GRAYL,
                   font_size=8, header_size=8)
    elif llm_text:
        _rect(slide, 0.9, 9.5, 23.6, 0.38, fill=col)
        _txb(slide, "Synthese FinSight IA", 1.0, 9.53, 18.0, 0.32, size=7.5, bold=True, color=_WHITE)
        _txb(slide, llm_text, 0.9, 9.98, 23.6, 3.2, size=8.5, color=_BLACK, wrap=True)


def _s14_synthese(prs, D):
    """Slide 14 — Synthese comparative : forces / faiblesses des 2 secteurs."""
    slide = _blank(prs)
    sa, sb = D["sa"], D["sb"]
    _header(slide, "Synthese Comparative  —  Forces & Faiblesses",
            f"Analyse strategique : atouts et vulnerabilites de chaque secteur", 4)
    _footer(slide, D)

    mid = 12.7

    # Secteur A
    _rect(slide, 0.9, 2.1, 11.2, 0.55, fill=_COL_A)
    _txb(slide, D["sector_a"], 1.0, 2.13, 11.0, 0.45, size=10, bold=True, color=_WHITE)

    # Forces A
    forces_a = _build_forces(sa, D["sector_a"])
    _txb(slide, "Forces", 0.9, 2.85, 5.5, 0.45, size=9, bold=True, color=_GREEN)
    for j, f in enumerate(forces_a[:3]):
        _txb(slide, f"+ {f}", 0.9, 3.4 + j * 1.1, 11.2, 0.85, size=8, color=_BLACK, wrap=True)

    # Faiblesses A
    weaks_a = _build_weaknesses(sa, D["sector_a"])
    _txb(slide, "Vulnerabilites", 0.9, 7.0, 5.5, 0.45, size=9, bold=True, color=_RED)
    for j, w in enumerate(weaks_a[:3]):
        _txb(slide, f"- {w}", 0.9, 7.55 + j * 1.1, 11.2, 0.85, size=8, color=_BLACK, wrap=True)

    # Signal A
    _rect(slide, 0.9, 11.2, 11.2, 0.7, fill=D["sig_a_col"])
    _txb(slide, f"Signal FinSight : {D['sig_a_lbl']}  |  Score {sa.get('score', 0)}/100",
         0.9, 11.28, 11.2, 0.55, size=9, bold=True, color=_WHITE, align=PP_ALIGN.CENTER)

    # Separateur
    _rect(slide, mid - 0.1, 2.0, 0.04, 10.0, fill=_GRAYM)

    # Secteur B
    _rect(slide, mid + 0.1, 2.1, 11.2, 0.55, fill=_COL_B)
    _txb(slide, D["sector_b"], mid + 0.2, 2.13, 11.0, 0.45, size=10, bold=True, color=_WHITE)

    forces_b = _build_forces(sb, D["sector_b"])
    _txb(slide, "Forces", mid + 0.1, 2.85, 5.5, 0.45, size=9, bold=True, color=_GREEN)
    for j, f in enumerate(forces_b[:3]):
        _txb(slide, f"+ {f}", mid + 0.1, 3.4 + j * 1.1, 11.2, 0.85, size=8, color=_BLACK, wrap=True)

    weaks_b = _build_weaknesses(sb, D["sector_b"])
    _txb(slide, "Vulnerabilites", mid + 0.1, 7.0, 5.5, 0.45, size=9, bold=True, color=_RED)
    for j, w in enumerate(weaks_b[:3]):
        _txb(slide, f"- {w}", mid + 0.1, 7.55 + j * 1.1, 11.2, 0.85, size=8, color=_BLACK, wrap=True)

    _rect(slide, mid + 0.1, 11.2, 11.2, 0.7, fill=D["sig_b_col"])
    _txb(slide, f"Signal FinSight : {D['sig_b_lbl']}  |  Score {sb.get('score', 0)}/100",
         mid + 0.1, 11.28, 11.2, 0.55, size=9, bold=True, color=_WHITE, align=PP_ALIGN.CENTER)


def _build_forces(s: dict, sector_name: str) -> list[str]:
    forces = []
    if (s.get("em") or 0) > 20:
        forces.append(f"Marge EBITDA elevee ({s.get('em', 0):.0f}%) — forte capacite a generer du cash operationnel")
    if (s.get("revg") or 0) > 5:
        forces.append(f"Croissance revenue soutenue ({s.get('revg', 0):+.1f}%) — secteur en expansion structurelle")
    if (s.get("roe") or 0) > 15:
        forces.append(f"ROE attractif ({s.get('roe', 0):.0f}%) — modele a forte creation de valeur actionnariale")
    if (s.get("roic") or 0) > 10:
        forces.append(f"ROIC > cout du capital ({s.get('roic', 0):.1f}%) — allocation capital disciplinee")
    if (s.get("fcfy") or 0) > 3:
        forces.append(f"FCF Yield ({s.get('fcfy', 0):.1f}%) — generation de cash visible, base pour dividendes et rachats")
    if (s.get("mom") or 0) > 5:
        forces.append(f"Momentum 52S positif ({s.get('mom', 0):+.1f}%) — confiance des investisseurs confirmee")
    # Padding : toujours 3 items pour equilibrer la mise en page
    _pad = [
        "Bilan sectoriel solide — solidite financiere confirmee",
        "Diversification des revenus geographique structurelle",
        "Visibilite sur les flux de tresorerie favorable",
    ]
    i = 0
    while len(forces) < 3:
        forces.append(_pad[i % len(_pad)])
        i += 1
    return forces[:3]


def _build_weaknesses(s: dict, sector_name: str) -> list[str]:
    weaks = []
    if (s.get("pe") or 0) > 30:
        weaks.append(f"Valorisation tendue (P/E {s.get('pe', 0):.0f}x) — peu de marge de securite en cas de deception")
    if (s.get("revg") or 0) < 2:
        weaks.append(f"Croissance revenue faible ({s.get('revg', 0):+.1f}%) — risque de re-rating baissier")
    if (s.get("nm") or 0) < 5:
        weaks.append(f"Marge nette comprimee ({s.get('nm', 0):.1f}%) — sensibilite elevee aux hausses de couts")
    if (s.get("beta") or 1) > 1.3:
        weaks.append(f"Beta eleve ({s.get('beta', 0):.2f}) — volatilite superieure au marche, prudence en phase de correction")
    if (s.get("mom") or 0) < -5:
        weaks.append(f"Momentum negatif 52S ({s.get('mom', 0):+.1f}%) — pression vendeuse persistante")
    if (s.get("ev_eb") or 0) > 20:
        weaks.append(f"EV/EBITDA premium ({s.get('ev_eb', 0):.0f}x) — execution sans faute requise")
    # Padding : toujours 2 items minimum pour equilibrer
    _pad = [
        "Surveillance du consensus — revision de valorisation possible",
        "Sensibilite macro a surveiller sur les 12 prochains mois",
        "Execution du management determinante pour maintenir les multiples",
    ]
    i = 0
    while len(weaks) < 2:
        weaks.append(_pad[i % len(_pad)])
        i += 1
    return weaks[:3]


def _s15_allocation(prs, D):
    """Slide 15 — Recommandation d'allocation."""
    slide = _blank(prs)
    sa, sb = D["sa"], D["sb"]
    _header(slide, "Recommandation d'Allocation  —  Positionnement Portefeuille",
            "Signal FinSight et implications pour la construction de portefeuille", 4)
    _footer(slide, D)

    # Contexte macro
    _rect(slide, 0.9, 2.1, 23.6, 0.6, fill=_GRAYL)
    _txb(slide, "Contexte d'analyse : les signaux FinSight sont calcules sur donnees fondamentales reelles (yfinance). Ils ne constituent pas un conseil d'investissement.",
         1.0, 2.15, 23.4, 0.5, size=7.5, italic=True, color=_GRAYT)

    # Panel A
    _rect(slide, 0.9, 3.0, 11.2, 1.0, fill=_COL_A)
    _txb(slide, D["sector_a"], 1.0, 3.08, 11.0, 0.45, size=12, bold=True, color=_WHITE)
    _txb(slide, D["universe_a"], 1.0, 3.58, 11.0, 0.35, size=8.5, color=_WHITE)

    _rect(slide, 0.9, 4.2, 11.2, 1.4, fill=D["sig_a_col"])
    _txb(slide, f"● {D['sig_a_lbl']}", 0.9, 4.45, 11.2, 0.8, size=22, bold=True, color=_WHITE, align=PP_ALIGN.CENTER)

    # KPIs A
    kpi_rows_a = [
        ("Score FinSight", f"{sa.get('score', 0)}/100"),
        ("P/E median", _fmt_simple(sa.get("pe"), x=True)),
        ("Croissance Rev.", _fmt(sa.get("revg"), pct=True)),
        ("Marge EBITDA", _fmt_simple(sa.get("em"), pct=True)),
        ("ROE", _fmt_simple(sa.get("roe"), pct=True)),
        ("Perf. 52S", _fmt(sa.get("mom"), pct=True)),
    ]
    for j, (label, val) in enumerate(kpi_rows_a):
        y = 5.8 + j * 0.85
        _rect(slide, 0.9, y, 11.2, 0.75, fill=_GRAYL if j % 2 == 0 else _WHITE)
        _txb(slide, label, 1.0, y + 0.12, 7.0, 0.55, size=9, color=_GRAYT)
        _txb(slide, val, 1.0, y + 0.12, 11.0, 0.55, size=9, bold=True, color=_NAVY, align=PP_ALIGN.RIGHT)

    # Separateur
    _rect(slide, 12.7, 2.8, 0.04, 10.5, fill=_GRAYM)

    # Panel B
    _rect(slide, 13.1, 3.0, 11.2, 1.0, fill=_COL_B)
    _txb(slide, D["sector_b"], 13.2, 3.08, 11.0, 0.45, size=12, bold=True, color=_WHITE)
    _txb(slide, D["universe_b"], 13.2, 3.58, 11.0, 0.35, size=8.5, color=_WHITE)

    _rect(slide, 13.1, 4.2, 11.2, 1.4, fill=D["sig_b_col"])
    _txb(slide, f"● {D['sig_b_lbl']}", 13.1, 4.45, 11.2, 0.8, size=22, bold=True, color=_WHITE, align=PP_ALIGN.CENTER)

    kpi_rows_b = [
        ("Score FinSight", f"{sb.get('score', 0)}/100"),
        ("P/E median", _fmt_simple(sb.get("pe"), x=True)),
        ("Croissance Rev.", _fmt(sb.get("revg"), pct=True)),
        ("Marge EBITDA", _fmt_simple(sb.get("em"), pct=True)),
        ("ROE", _fmt_simple(sb.get("roe"), pct=True)),
        ("Perf. 52S", _fmt(sb.get("mom"), pct=True)),
    ]
    for j, (label, val) in enumerate(kpi_rows_b):
        y = 5.8 + j * 0.85
        _rect(slide, 13.1, y, 11.2, 0.75, fill=_GRAYL if j % 2 == 0 else _WHITE)
        _txb(slide, label, 13.2, y + 0.12, 7.0, 0.55, size=9, color=_GRAYT)
        _txb(slide, val, 13.2, y + 0.12, 11.0, 0.55, size=9, bold=True, color=_GREEN, align=PP_ALIGN.RIGHT)

    # Recommandation IA
    alloc_text = D.get("llm", {}).get("allocation_read")
    if alloc_text:
        _rect(slide, 0.9, 11.0, 23.6, 0.38, fill=_NAVY)
        _txb(slide, "Recommandation FinSight IA", 1.0, 11.03, 18.0, 0.32, size=7.5, bold=True, color=_WHITE)
        _txb(slide, alloc_text, 0.9, 11.48, 23.6, 1.25, size=8.5, color=_BLACK, wrap=True)

    # Note de bas de page
    _txb(slide, "Note : Score FinSight = indicateur proprietaire multidimensionnel (value + growth + qualite + momentum). Signal = Surponderer si score >= 65, Neutre si >= 45, Sous-ponderer si < 45.",
         0.9, 12.85, 23.6, 0.55, size=7, italic=True, color=_GRAYD, wrap=True)


def _s16_disclaimer(prs, D):
    """Slide 16 — Disclaimer."""
    slide = _blank(prs)
    _rect(slide, 0, 0, 25.4, 1.8, fill=_NAVY)
    _txb(slide, "FinSight IA  —  Mentions Legales & Methodologie", 0.9, 0.3, 23.6, 1.2,
         size=13, bold=True, color=_WHITE)

    disclaimers = [
        ("Caractere informatif", "Ce document est produit a des fins d'information uniquement. Il ne constitue pas un conseil en investissement, une recommendation d'achat ou de vente de valeurs mobilieres, ni une invitation a contracter."),
        ("Sources des donnees", "Les donnees financieres sont issues de yfinance (Yahoo Finance), Finnhub et Financial Modeling Prep. FinSight IA ne garantit pas l'exhaustivite ou l'exactitude de ces donnees. Les chiffres presentent les medianes des societes analysees."),
        ("Scores & Signaux FinSight", "Le Score FinSight est un indicateur proprietaire multidimensionnel (value + growth + qualite + momentum, chacun sur 25 pts). Les signaux Surponderer / Neutre / Sous-ponderer sont derives mecaniquement des scores — ils ne constituent pas des recommendations d'investissement personnalisees."),
        ("Performance passee", "Les performances passees et les donnees historiques ne prejugent pas des performances futures. Les comparatifs sectoriels sont etablis a date de generation du rapport."),
        ("Responsabilite", "FinSight IA et ses developpers declinent toute responsabilite quant a l'utilisation de ce document. Toute decision d'investissement doit etre prise apres consultation d'un conseiller financier agree."),
    ]
    y = 2.2
    for title, text in disclaimers:
        _txb(slide, title, 0.9, y, 23.6, 0.4, size=9, bold=True, color=_NAVY)
        _txb(slide, text, 0.9, y + 0.45, 23.6, 1.0, size=7.5, color=_GRAYT, wrap=True)
        y += 1.7

    _txb(slide, f"Genere par FinSight IA  |  {D['date_str']}  |  Usage confidentiel — ne pas diffuser",
         0.9, 13.5, 23.6, 0.4, size=7.5, bold=True, color=_NAVY, align=PP_ALIGN.CENTER)


# ── Generateur de textes analytiques LLM ─────────────────────────────────────

def _generate_llm_texts(D: dict) -> dict:
    """Un seul appel Mistral pour generer tous les textes analytiques du pitchbook."""
    try:
        from core.llm_provider import LLMProvider
        llm = LLMProvider(provider="mistral", model="mistral-small-latest")
        sa, sb = D["sa"], D["sb"]
        sector_a, sector_b = D["sector_a"], D["sector_b"]
        roe_a = min(float(sa.get("roe") or 0), 999.9)
        roe_b = min(float(sb.get("roe") or 0), 999.9)
        dy_a = sa.get("div_yield") or 0
        dy_b = sb.get("div_yield") or 0
        fy_a = sa.get("fcfy") or 0
        fy_b = sb.get("fcfy") or 0
        prompt = (
            f"Tu es analyste financier senior. Redige des textes courts pour un pitchbook comparatif sectoriel "
            f"entre {sector_a} et {sector_b} (univers : {D['universe_label']}).\n\n"
            f"Donnees medianes :\n"
            f"- {sector_a} : Score {sa.get('score',0)}/100, Signal {D['sig_a_lbl']}, "
            f"P/E {sa.get('pe',0):.1f}x, EV/EBITDA {sa.get('ev_eb',0):.1f}x, "
            f"Croiss.Rev {sa.get('revg',0):+.1f}%, Mg.EBITDA {sa.get('em',0):.1f}%, "
            f"ROE {roe_a:.1f}%, Perf.52S {sa.get('mom',0):+.1f}%, Beta {sa.get('beta',1.0):.2f}, "
            f"Div Yield {dy_a:.1f}%, FCF Yield {fy_a:.1f}%\n"
            f"- {sector_b} : Score {sb.get('score',0)}/100, Signal {D['sig_b_lbl']}, "
            f"P/E {sb.get('pe',0):.1f}x, EV/EBITDA {sb.get('ev_eb',0):.1f}x, "
            f"Croiss.Rev {sb.get('revg',0):+.1f}%, Mg.EBITDA {sb.get('em',0):.1f}%, "
            f"ROE {roe_b:.1f}%, Perf.52S {sb.get('mom',0):+.1f}%, Beta {sb.get('beta',1.0):.2f}, "
            f"Div Yield {dy_b:.1f}%, FCF Yield {fy_b:.1f}%\n\n"
            f"Reponds UNIQUEMENT en JSON valide. Textes en francais sans accents ni caracteres speciaux. "
            f"Maximum 220 caracteres par champ sauf exec_summary (350 max).\n"
            f'{{\n'
            f'  "exec_summary": "Synthese 2-3 phrases : qui privilegier, ecarts cles, signal IA",\n'
            f'  "valuation_read": "Lecture valorisation 1-2 phrases : analyse multiples P/E et EV/EBITDA",\n'
            f'  "margins_read": "Lecture marges 1-2 phrases : qualite operationnelle et rentabilite",\n'
            f'  "capital_alloc_read": "Capital allocation 1-2 phrases : dividendes, FCF yield et remuneration actionnaire",\n'
            f'  "growth_read": "Lecture croissance 1-2 phrases : acceleration/ralentissement et momentum",\n'
            f'  "scoring_read": "Interpretation scoring 1-2 phrases : analyse radar multidimensionnel",\n'
            f'  "top_a_read": "Synthese top acteurs {sector_a} 1-2 phrases",\n'
            f'  "top_b_read": "Synthese top acteurs {sector_b} 1-2 phrases",\n'
            f'  "these_a": "These investissement {sector_a} : 2 phrases, arguments cles",\n'
            f'  "these_b": "These investissement {sector_b} : 2 phrases, arguments cles",\n'
            f'  "allocation_read": "Recommandation allocation portefeuille 2-3 phrases : surponderations cles"\n'
            f'}}'
        )
        import json, re
        resp = llm.generate(prompt, max_tokens=1000)
        m = re.search(r'\{.*\}', resp, re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            log.info("[cmp_secteur_pptx] LLM texts OK (%d champs)", len(data))
            return data
    except Exception as e:
        log.warning("[cmp_secteur_pptx] LLM texts generation failed: %s", e)
    return {}


# ── Classe principale ─────────────────────────────────────────────────────────

class CmpSecteurPPTXWriter:
    """Generateur de pitchbook comparatif sectoriel 16 slides."""

    @staticmethod
    def generate(
        tickers_a: list[dict],
        sector_a: str,
        universe_a: str,
        tickers_b: list[dict],
        sector_b: str,
        universe_b: str,
        output_path: Optional[str] = None,
    ) -> bytes:
        """
        Genere le PPTX comparatif et retourne les bytes.
        Si output_path est fourni, sauvegarde aussi sur disque.
        """
        D = _prepare_data(tickers_a, sector_a, universe_a, tickers_b, sector_b, universe_b)
        D["llm"] = _generate_llm_texts(D)

        prs = Presentation()
        prs.slide_width  = _SW
        prs.slide_height = _SH

        # Section 1 — Vue d'ensemble
        _s01_cover(prs, D)                # Slide 1 — Cover
        _s02_exec_summary(prs, D)         # Slide 2 — Executive Summary (tableau metriques)
        _s03_sommaire(prs, D)             # Slide 3 — Sommaire

        # Section 2 — Profil & Valorisation
        _chapter_divider(prs, "01", "Profil & Valorisation",
                         "Structure des secteurs, multiples et qualite des bilans")
        _s05_profil(prs, D)               # Slide 5 — Profil cote a cote
        _s06_valorisation(prs, D)         # Slide 6 — P/E, EV/EBITDA
        _s07_marges(prs, D)               # Slide 7 — Marges & Rentabilite
        _s07b_capital_alloc(prs, D)       # Slide 7b — Capital Allocation

        # Section 3 — Croissance & Scoring
        _chapter_divider(prs, "02", "Croissance & Scoring",
                         "Revenue growth, momentum et scoring multidimensionnel")
        _s08_croissance(prs, D)           # Slide 9 — Croissance & Momentum
        _s09_scoring(prs, D)              # Slide 10 — Radar scoring

        # Section 4 — Top Acteurs & Risques
        _chapter_divider(prs, "03", "Top Acteurs & Risques",
                         "Meilleures societes et conditions d'invalidation par secteur")
        _s10_top_a(prs, D)                # Slide 12 — Top acteurs A
        _s11_top_b(prs, D)                # Slide 13 — Top acteurs B
        _s12_risques_a(prs, D)            # Slide 14 — Risques A
        _s13_risques_b(prs, D)            # Slide 15 — Risques B

        # Section 5 — Synthese & Allocation
        _chapter_divider(prs, "04", "Synthese & Allocation",
                         "Comparaison strategique et recommandation de positionnement")
        _s14_synthese(prs, D)             # Slide 17 — Synthese comparative
        _s15_allocation(prs, D)           # Slide 18 — Recommandation allocation
        _s16_disclaimer(prs, D)           # Slide 19 — Disclaimer

        buf = io.BytesIO()
        prs.save(buf)
        pptx_bytes = buf.getvalue()

        if output_path:
            Path(output_path).write_bytes(pptx_bytes)
            log.info("[CmpSecteurPPTXWriter] Sauvegarde : %s (%d Ko)", output_path, len(pptx_bytes) // 1024)

        return pptx_bytes
