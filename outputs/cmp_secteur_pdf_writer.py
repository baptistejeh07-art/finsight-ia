"""
cmp_secteur_pdf_writer.py — FinSight IA
Rapport PDF comparatif sectoriel via ReportLab.
~10 pages : cover, synthese, profil, valorisation, marges, croissance,
             top acteurs, risques/catalyseurs, recommandation, disclaimer.

Usage :
    from outputs.cmp_secteur_pdf_writer import generate_cmp_secteur_pdf
    generate_cmp_secteur_pdf(
        tickers_a, sector_a, universe_a,
        tickers_b, sector_b, universe_b,
        output_path="cmp_tech_vs_sante.pdf"
    )
"""
from __future__ import annotations

import io
import logging
import math
from datetime import date
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Image, KeepTogether,
)

# ── Palette ──────────────────────────────────────────────────────────────────
NAVY       = colors.HexColor("#1B3A6B")
NAVY_LIGHT = colors.HexColor("#2A5298")
GREEN      = colors.HexColor("#1A7A4A")
GREEN_L    = colors.HexColor("#EAF4EF")
RED        = colors.HexColor("#A82020")
AMBER      = colors.HexColor("#B8922A")
RED_L      = colors.HexColor("#FAEAEA")
WHITE      = colors.white
BLACK      = colors.HexColor("#1A1A1A")
GREY_LIGHT = colors.HexColor("#F5F7FA")
GREY_MED   = colors.HexColor("#E8ECF0")
GREY_TEXT  = colors.HexColor("#555555")
GREY_RULE  = colors.HexColor("#D0D5DD")
ROW_ALT    = colors.HexColor("#F0F4F8")
COL_A      = colors.HexColor("#1B3A6B")   # Secteur A — navy
COL_A_L    = colors.HexColor("#EEF3FA")
COL_B      = colors.HexColor("#1A7A4A")   # Secteur B — vert
COL_B_L    = colors.HexColor("#EAF4EF")

# Hex pour matplotlib
_HEX_A = "#1B3A6B"
_HEX_B = "#1A7A4A"

PAGE_W, PAGE_H = A4
MARGIN_L = 17 * mm
MARGIN_R = 17 * mm
MARGIN_T = 22 * mm
MARGIN_B = 18 * mm
TABLE_W  = PAGE_W - MARGIN_L - MARGIN_R   # ~176mm


# ── Styles ───────────────────────────────────────────────────────────────────
def _sty(name, font="Helvetica", size=9, color=BLACK, leading=13,
         align=TA_LEFT, bold=False, sb=0, sa=2):
    return ParagraphStyle(
        name,
        fontName="Helvetica-Bold" if bold else font,
        fontSize=size, textColor=color, leading=leading,
        alignment=align, spaceBefore=sb, spaceAfter=sa,
    )

S_BODY  = _sty("body",   size=8.5, leading=13, color=GREY_TEXT, align=TA_JUSTIFY)
S_BODY2 = _sty("body2",  size=8.5, leading=13, color=BLACK)
S_SEC   = _sty("sec",    size=12,  leading=16, color=NAVY, bold=True, sb=8, sa=2)
S_SSEC  = _sty("ssec",   size=9,   leading=13, color=NAVY, bold=True, sb=5, sa=3)
S_TH_C = _sty("thc",    size=8,   leading=11, color=WHITE, bold=True, align=TA_CENTER)
S_TH_L = _sty("thl",    size=8,   leading=11, color=WHITE, bold=True, align=TA_LEFT)
S_TD_L  = _sty("tdl",   size=8,   leading=11, color=BLACK, align=TA_LEFT)
S_TD_C  = _sty("tdc",   size=8,   leading=11, color=BLACK, align=TA_CENTER)
S_TD_B  = _sty("tdb",   size=8,   leading=11, color=BLACK, bold=True)
S_TD_A  = _sty("tda",   size=8,   leading=11, color=COL_A, bold=True, align=TA_CENTER)
S_TD_G  = _sty("tdg",   size=8,   leading=11, color=COL_B, bold=True, align=TA_CENTER)
S_NOTE  = _sty("note",  size=6.5, leading=9,  color=GREY_TEXT)
S_DISC  = _sty("disc",  size=6.5, leading=9,  color=GREY_TEXT, align=TA_JUSTIFY)
S_COVER = _sty("cov",   size=28,  leading=36, color=NAVY, bold=True, align=TA_CENTER)
S_SUB   = _sty("sub",   size=11,  leading=16, color=GREY_TEXT, align=TA_CENTER)
S_BADGE = _sty("bdg",   size=10,  leading=14, color=WHITE, bold=True, align=TA_CENTER)


# ── Helpers ───────────────────────────────────────────────────────────────────
def rule(w=TABLE_W, thick=0.5, col=GREY_RULE, sb=4, sa=4):
    return HRFlowable(width=w, thickness=thick, color=col, spaceAfter=sa, spaceBefore=sb)


def section(text, num):
    return [rule(sb=10, sa=0), Paragraph(f"{num}. {text}", S_SEC), rule(sb=2, sa=6)]


def _na(v, fmt=None, default="—"):
    if v is None:
        return default
    try:
        f = float(v)
        if not math.isfinite(f):
            return default
        return fmt(f) if fmt else f"{f:.1f}"
    except (TypeError, ValueError):
        return default


def _pct(v, sign=True, dp=1):
    if v is None:
        return "—"
    try:
        f = float(v)
        if not math.isfinite(f):
            return "—"
        prefix = "+" if sign and f >= 0 else ""
        return f"{prefix}{f:.{dp}f}%"
    except (TypeError, ValueError):
        return "—"


def _mult(v):
    if v is None:
        return "—"
    try:
        return f"{float(v):.1f}x"
    except (TypeError, ValueError):
        return "—"


def _xml(s: str) -> str:
    """Echappe les caracteres speciaux XML pour les Paragraph ReportLab."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _safe_float(v, default=0.0):
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except Exception:
        return default


def _med(vals, default=0.0):
    clean = [_safe_float(v) for v in vals if v is not None]
    if not clean:
        return default
    clean.sort()
    n = len(clean)
    return clean[n // 2] if n % 2 else (clean[n // 2 - 1] + clean[n // 2]) / 2


def _mean(vals, default=0.0):
    clean = [_safe_float(v) for v in vals if v is not None]
    return sum(clean) / len(clean) if clean else default


# ── Preparation donnees ───────────────────────────────────────────────────────
def _prepare(tickers_a, sector_a, universe_a, tickers_b, sector_b, universe_b):
    def _stats(td):
        if not td:
            return {}
        return dict(
            pe    = _med([t.get("pe_ratio") for t in td if t.get("pe_ratio")]),
            ev_eb = _med([t.get("ev_ebitda") for t in td if t.get("ev_ebitda")]),
            ev_rv = _med([t.get("ev_revenue") for t in td if t.get("ev_revenue")]),
            gm    = _med([t.get("gross_margin") for t in td]),
            em    = _med([t.get("ebitda_margin") for t in td]),
            nm    = _med([t.get("net_margin") for t in td]),
            roe   = _med([t.get("roe") for t in td]),
            roic  = _med([t.get("roic") for t in td if t.get("roic") is not None], default=None),
            revg  = _med([t.get("revenue_growth", 0) for t in td]) * 100,
            mom   = _med([t.get("momentum_52w", 0) for t in td]),
            beta  = _med([t.get("beta", 1.0) for t in td if t.get("beta")]),
            fcfy  = _med([t.get("fcf_yield") for t in td if t.get("fcf_yield")]),
            peg   = _med([t.get("peg_ratio") for t in td if t.get("peg_ratio")]),
            pf    = _med([t.get("piotroski_f") for t in td if t.get("piotroski_f") is not None]),
            div_yield = _med([t.get("div_yield") for t in td if t.get("div_yield") and float(t.get("div_yield") or 0) > 0], default=None),
            payout = _med([t.get("payout_ratio") for t in td if t.get("payout_ratio") and float(t.get("payout_ratio") or 0) > 0], default=None),
            score = int(_mean([t.get("score_global", 50) for t in td])),
            s_val = _mean([round(float(t.get("score_value") or 12) / 4.0, 1) if (t.get("score_value") or 0) > 30 else float(t.get("score_value") or 12) for t in td]),
            s_gro = _mean([round(float(t.get("score_growth") or 12) / 4.0, 1) if (t.get("score_growth") or 0) > 30 else float(t.get("score_growth") or 12) for t in td]),
            s_qua = _mean([round(float(t.get("score_quality") or 12) / 4.0, 1) if (t.get("score_quality") or 0) > 30 else float(t.get("score_quality") or 12) for t in td]),
            s_mom = _mean([round(float(t.get("score_momentum") or 12) / 4.0, 1) if (t.get("score_momentum") or 0) > 30 else float(t.get("score_momentum") or 12) for t in td]),
        )

    sa = _stats(tickers_a)
    sb = _stats(tickers_b)

    def _sig(score):
        if score >= 65:
            return "Surponderer", GREEN
        if score >= 45:
            return "Neutre", AMBER
        return "Sous-ponderer", RED

    sig_a_lbl, sig_a_col = _sig(sa.get("score", 50))
    sig_b_lbl, sig_b_col = _sig(sb.get("score", 50))

    universes = set(filter(None, [universe_a, universe_b]))
    universe_label = " / ".join(sorted(universes)) if universe_a != universe_b else (universe_a or "Global")

    return dict(
        sector_a=sector_a, sector_b=sector_b,
        universe_a=universe_a, universe_b=universe_b,
        universe_label=universe_label,
        na=len(tickers_a), nb=len(tickers_b),
        td_a=tickers_a, td_b=tickers_b,
        sa=sa, sb=sb,
        sig_a_lbl=sig_a_lbl, sig_a_col=sig_a_col,
        sig_b_lbl=sig_b_lbl, sig_b_col=sig_b_col,
        date_str=(lambda d: f"{d.day} {['janvier','fevrier','mars','avril','mai','juin','juillet','aout','septembre','octobre','novembre','decembre'][d.month-1]} {d.year}")(date.today()),
    )


# ── Contenus sectoriels ───────────────────────────────────────────────────────
from outputs.cmp_secteur_pptx_writer import _get_content


# ── Chart builders ────────────────────────────────────────────────────────────
def _chart_valuation_pdf(sa, sb, label_a, label_b) -> bytes:
    metrics = ["P/E", "EV/EBITDA", "EV/Revenue"]
    vals_a  = [sa.get("pe", 0) or 0, sa.get("ev_eb", 0) or 0, sa.get("ev_rv", 0) or 0]
    vals_b  = [sb.get("pe", 0) or 0, sb.get("ev_eb", 0) or 0, sb.get("ev_rv", 0) or 0]
    fig, ax = plt.subplots(figsize=(8, 3.0))
    x = np.arange(len(metrics))
    w = 0.35
    bars_a = ax.bar(x - w/2, vals_a, w, label=label_a, color=_HEX_A, alpha=0.9)
    bars_b = ax.bar(x + w/2, vals_b, w, label=label_b, color=_HEX_B, alpha=0.9)
    ax.set_xticks(x); ax.set_xticklabels(metrics, fontsize=10)
    ax.set_ylabel("Multiple (x)", fontsize=9)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4); ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    for bar in list(bars_a) + list(bars_b):
        h = bar.get_height()
        if h > 0:
            ax.annotate(f"{h:.1f}x", xy=(bar.get_x() + bar.get_width()/2, h),
                        xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8)
    ax.legend(fontsize=9, framealpha=0)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=140, bbox_inches="tight"); plt.close(fig)
    buf.seek(0); return buf.read()


def _chart_margins_pdf(sa, sb, label_a, label_b) -> bytes:
    metrics = ["Brute", "EBITDA", "Nette"]
    vals_a  = [sa.get("gm", 0) or 0, sa.get("em", 0) or 0, sa.get("nm", 0) or 0]
    vals_b  = [sb.get("gm", 0) or 0, sb.get("em", 0) or 0, sb.get("nm", 0) or 0]
    fig, ax = plt.subplots(figsize=(8, 3.0))
    x = np.arange(len(metrics)); w = 0.35
    bars_a = ax.bar(x - w/2, vals_a, w, label=label_a, color=_HEX_A, alpha=0.9)
    bars_b = ax.bar(x + w/2, vals_b, w, label=label_b, color=_HEX_B, alpha=0.9)
    ax.set_xticks(x); ax.set_xticklabels([f"Marge {m}" for m in metrics], fontsize=10)
    ax.set_ylabel("Marge (%)", fontsize=9)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4); ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    for bar in list(bars_a) + list(bars_b):
        h = bar.get_height()
        if abs(h) > 0.5:
            ax.annotate(f"{h:.1f}%", xy=(bar.get_x() + bar.get_width()/2, max(h, 0)),
                        xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=7.5)
    ax.legend(fontsize=9, framealpha=0)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=140, bbox_inches="tight"); plt.close(fig)
    buf.seek(0); return buf.read()


def _chart_radar_pdf(sa, sb, label_a, label_b) -> bytes:
    categories = ["Value", "Growth", "Quality", "Momentum"]
    vals_a = [sa.get("s_val", 12), sa.get("s_gro", 12), sa.get("s_qua", 12), sa.get("s_mom", 12)]
    vals_b = [sb.get("s_val", 12), sb.get("s_gro", 12), sb.get("s_qua", 12), sb.get("s_mom", 12)]
    N = len(categories)
    angles = [n / float(N) * 2 * math.pi for n in range(N)]
    angles += angles[:1]
    va = vals_a + vals_a[:1]; vb = vals_b + vals_b[:1]
    fig, ax = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))
    ax.plot(angles, va, "o-", linewidth=2, color=_HEX_A, label=label_a)
    ax.fill(angles, va, alpha=0.15, color=_HEX_A)
    ax.plot(angles, vb, "s-", linewidth=2, color=_HEX_B, label=label_b)
    ax.fill(angles, vb, alpha=0.15, color=_HEX_B)
    ax.set_xticks(angles[:-1]); ax.set_xticklabels(categories, fontsize=9)
    ax.set_ylim(0, 25)
    ax.legend(loc="upper right", bbox_to_anchor=(1.4, 1.1), fontsize=9)
    plt.tight_layout(pad=0.3)
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=140, bbox_inches="tight"); plt.close(fig)
    buf.seek(0); return buf.read()


def _chart_momentum_pdf(sa, sb, label_a, label_b) -> bytes:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 3.0))
    revg_a = sa.get("revg", 0) or 0; revg_b = sb.get("revg", 0) or 0
    b1 = ax1.bar([label_a, label_b], [revg_a, revg_b], color=[_HEX_A, _HEX_B], alpha=0.9, width=0.5)
    ax1.axhline(0, color="black", linewidth=0.6)
    ax1.set_title("Croissance Revenue medianne", fontsize=9, fontweight="bold")
    ax1.set_ylabel("%", fontsize=8); ax1.spines["top"].set_visible(False); ax1.spines["right"].set_visible(False)
    ax1.yaxis.grid(True, linestyle="--", alpha=0.4); ax1.set_axisbelow(True)
    for bar in b1:
        h = bar.get_height()
        ax1.annotate(f"{h:+.1f}%", xy=(bar.get_x() + bar.get_width()/2, h),
                     xytext=(0, 4 if h >= 0 else -12), textcoords="offset points", ha="center", fontsize=9, fontweight="bold")
    mom_a = sa.get("mom", 0) or 0; mom_b = sb.get("mom", 0) or 0
    b2 = ax2.bar([label_a, label_b], [mom_a, mom_b], color=[_HEX_A, _HEX_B], alpha=0.9, width=0.5)
    ax2.axhline(0, color="black", linewidth=0.6)
    ax2.set_title("Performance 52 semaines medianne", fontsize=9, fontweight="bold")
    ax2.set_ylabel("%", fontsize=8); ax2.spines["top"].set_visible(False); ax2.spines["right"].set_visible(False)
    ax2.yaxis.grid(True, linestyle="--", alpha=0.4); ax2.set_axisbelow(True)
    for bar in b2:
        h = bar.get_height()
        ax2.annotate(f"{h:+.1f}%", xy=(bar.get_x() + bar.get_width()/2, h),
                     xytext=(0, 4 if h >= 0 else -12), textcoords="offset points", ha="center", fontsize=9, fontweight="bold")
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=140, bbox_inches="tight"); plt.close(fig)
    buf.seek(0); return buf.read()


def _img(img_bytes, w=TABLE_W, h=None):
    buf = io.BytesIO(img_bytes)
    if h:
        return Image(buf, width=w, height=h)
    return Image(buf, width=w)


# ── Helpers de table ──────────────────────────────────────────────────────────
def _tbl(data, cw, header_col=NAVY):
    t = Table(data, colWidths=cw)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  header_col),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, ROW_ALT]),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("LINEBELOW",     (0, 0), (-1, 0),  0.5, NAVY_LIGHT),
        ("LINEBELOW",     (0, -1),(-1, -1), 0.5, GREY_RULE),
        ("GRID",          (0, 1), (-1, -1), 0.3, GREY_MED),
    ]))
    return t


def _avantage_cell(val_a, val_b, sector_a, sector_b, higher_is_better=True):
    """Renvoie (texte, style) pour la colonne Avantage."""
    try:
        fa, fb = float(val_a or 0), float(val_b or 0)
        if fa == fb:
            return Paragraph("Egal", S_TD_C)
        if (fa > fb) == higher_is_better:
            return Paragraph(sector_a[:10], S_TD_A)
        else:
            return Paragraph(sector_b[:10], S_TD_G)
    except Exception:
        return Paragraph("—", S_TD_C)


# ── Generateur de textes analytiques LLM ─────────────────────────────────────

def _generate_llm_texts(D: dict) -> dict:
    """Un seul appel Mistral pour les textes analytiques du PDF comparatif."""
    try:
        from core.llm_provider import LLMProvider
        llm = LLMProvider(provider="mistral", model="mistral-small-latest")
        sa, sb = D["sa"], D["sb"]
        sector_a, sector_b = D["sector_a"], D["sector_b"]
        roe_a = min(float(sa.get("roe") or 0), 999.9)
        roe_b = min(float(sb.get("roe") or 0), 999.9)
        dy_a = sa.get("div_yield") or 0
        dy_b = sb.get("div_yield") or 0
        pt_a = sa.get("payout") or 0
        pt_b = sb.get("payout") or 0
        fy_a = sa.get("fcfy") or 0
        fy_b = sb.get("fcfy") or 0
        prompt = (
            f"Tu es analyste financier senior. Redige des textes analytiques pour un rapport PDF comparatif sectoriel "
            f"entre {sector_a} et {sector_b} (univers : {D['universe_label']}).\n\n"
            f"Donnees medianes :\n"
            f"- {sector_a} : Score {sa.get('score',0)}/100, Signal {D['sig_a_lbl']}, "
            f"P/E {sa.get('pe',0):.1f}x, Croiss.Rev {sa.get('revg',0):+.1f}%, "
            f"Mg.EBITDA {sa.get('em',0):.1f}%, ROE {roe_a:.1f}%, Perf.52S {sa.get('mom',0):+.1f}%, "
            f"Div Yield {dy_a*100:.1f}%, FCF Yield {fy_a*100:.1f}%, Payout {pt_a*100:.0f}%\n"
            f"- {sector_b} : Score {sb.get('score',0)}/100, Signal {D['sig_b_lbl']}, "
            f"P/E {sb.get('pe',0):.1f}x, Croiss.Rev {sb.get('revg',0):+.1f}%, "
            f"Mg.EBITDA {sb.get('em',0):.1f}%, ROE {roe_b:.1f}%, Perf.52S {sb.get('mom',0):+.1f}%, "
            f"Div Yield {dy_b*100:.1f}%, FCF Yield {fy_b*100:.1f}%, Payout {pt_b*100:.0f}%\n\n"
            f"Reponds UNIQUEMENT en JSON valide. Textes en francais sans accents ni caracteres speciaux. "
            f"Max 300 caracteres par champ sauf exec_summary (500 max).\n"
            f'{{\n'
            f'  "exec_summary": "Synthese 3 phrases : comparatif cle, signal IA et recommandation",\n'
            f'  "valuation_analysis": "Analyse valorisation 2 phrases : interpretation multiples P/E et EV/EBITDA",\n'
            f'  "margins_analysis": "Analyse marges 2 phrases : qualite operationnelle, ROE et creation de valeur",\n'
            f'  "capital_alloc_analysis": "Capital allocation 2 phrases : dividendes, FCF yield et politique de remuneration actionnaire",\n'
            f'  "growth_analysis": "Analyse croissance 2 phrases : dynamique revenue, momentum 52S et beta",\n'
            f'  "top_a_analysis": "Synthese top acteurs {sector_a} 2 phrases : meilleurs profils et caracteristiques",\n'
            f'  "top_b_analysis": "Synthese top acteurs {sector_b} 2 phrases : meilleurs profils et caracteristiques",\n'
            f'  "allocation_rec": "Recommandation allocation 3 phrases : signal, surponderations, conditions"\n'
            f'}}'
        )
        import json, re
        resp = llm.generate(prompt, max_tokens=800)
        m = re.search(r'\{.*\}', resp, re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            log.info("[cmp_secteur_pdf] LLM texts OK (%d champs)", len(data))
            return data
    except Exception as e:
        log.warning("[cmp_secteur_pdf] LLM texts generation failed: %s", e)
    return {}


# Styles supplementaires pour LLM text box
S_LLM_TITLE = _sty("llm_title", size=8, color=WHITE, bold=True)
S_LLM_BODY  = _sty("llm_body",  size=8.5, leading=13, color=BLACK, align=TA_JUSTIFY)


def _llm_box(text: str, col=NAVY, w=None) -> list:
    """Cree un bloc IA : bandeau color + texte corps."""
    if not text:
        return []
    bw = w or TABLE_W
    title_tbl = Table(
        [[Paragraph("Analyse FinSight IA", S_LLM_TITLE)]],
        colWidths=[bw],
    )
    title_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), col),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
    ]))
    body_tbl = Table(
        [[Paragraph(_xml(text), S_LLM_BODY)]],
        colWidths=[bw],
    )
    body_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), GREY_LIGHT),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("LINEBELOW",    (0,-1), (-1,-1), 0.5, GREY_RULE),
    ]))
    return [KeepTogether([title_tbl, body_tbl]), Spacer(1, 3*mm)]


# ── Generateur de contenu ─────────────────────────────────────────────────────
def _build_story(D: dict) -> list:
    sa, sb = D["sa"], D["sb"]
    sector_a, sector_b = D["sector_a"], D["sector_b"]
    story = []

    # ── PAGE 1 : Cover ────────────────────────────────────────────────────────
    story.append(Spacer(1, 40 * mm))
    story.append(Paragraph("FinSight IA", _sty("brand", size=12, color=NAVY_LIGHT, bold=True)))
    story.append(Spacer(1, 4 * mm))
    story.append(rule(thick=2, col=NAVY, sb=0, sa=0))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(f"Comparatif Sectoriel", _sty("ct", size=14, color=GREY_TEXT, align=TA_CENTER)))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"{sector_a}  vs  {sector_b}", S_COVER))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(_xml(D["universe_label"]), S_SUB))
    story.append(Spacer(1, 10 * mm))
    story.append(rule(thick=0.5, col=GREY_RULE, sb=0, sa=0))
    story.append(Spacer(1, 8 * mm))

    # KPI snapshot (2 colonnes)
    kpi_data = [
        [Paragraph(sector_a, _sty("ka", size=10, color=WHITE, bold=True, align=TA_CENTER)),
         Paragraph(sector_b, _sty("kb", size=10, color=WHITE, bold=True, align=TA_CENTER))],
        [Paragraph(f"Score FinSight : {sa.get('score', 0)}/100\nSignal : {D['sig_a_lbl']}", _sty("ks", size=9, color=WHITE, align=TA_CENTER, leading=14)),
         Paragraph(f"Score FinSight : {sb.get('score', 0)}/100\nSignal : {D['sig_b_lbl']}", _sty("ks2", size=9, color=WHITE, align=TA_CENTER, leading=14))],
        [Paragraph(f"P/E med. : {_mult(sa.get('pe'))}  |  Croiss. : {_pct(sa.get('revg'))}  |  Mg EBITDA : {_pct(sa.get('em'), sign=False)}",
                   _sty("kd", size=8, color=GREY_TEXT, align=TA_CENTER)),
         Paragraph(f"P/E med. : {_mult(sb.get('pe'))}  |  Croiss. : {_pct(sb.get('revg'))}  |  Mg EBITDA : {_pct(sb.get('em'), sign=False)}",
                   _sty("kd2", size=8, color=GREY_TEXT, align=TA_CENTER))],
    ]
    kpi_t = Table(kpi_data, colWidths=[TABLE_W / 2, TABLE_W / 2])
    kpi_t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (0, 1), COL_A),
        ("BACKGROUND",   (1, 0), (1, 1), COL_B),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("LINEAFTER",    (0, 0), (0, -1), 0.5, WHITE),
    ]))
    story.append(kpi_t)
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(D["date_str"], _sty("dt", size=8, color=GREY_TEXT, align=TA_CENTER)))
    story.append(Spacer(1, 5 * mm))

    # ── Synthese IA sur la cover ──────────────────────────────────────────────
    exec_text = D.get("llm", {}).get("exec_summary", "")
    if exec_text:
        story += _llm_box(exec_text)

    story.append(PageBreak())

    # ── PAGE 2 : Synthese comparative ────────────────────────────────────────
    story += section("Synthese Comparative", "1")
    cols = [52*mm, 30*mm, 30*mm, 30*mm, 30*mm]
    syn_data = [
        [Paragraph("Metrique", S_TH_L),
         Paragraph(sector_a[:14], S_TH_C),
         Paragraph(sector_b[:14], S_TH_C),
         Paragraph("Avantage", S_TH_C),
         Paragraph("Diff.", S_TH_C)],
        [Paragraph("Score FinSight", S_TD_L),
         Paragraph(f"{sa.get('score', 0)}/100", S_TD_C),
         Paragraph(f"{sb.get('score', 0)}/100", S_TD_C),
         _avantage_cell(sa.get("score"), sb.get("score"), sector_a, sector_b),
         Paragraph(f"{abs((sa.get('score') or 0) - (sb.get('score') or 0))} pts", S_TD_C)],
        [Paragraph("P/E median", S_TD_L),
         Paragraph(_mult(sa.get("pe")), S_TD_C),
         Paragraph(_mult(sb.get("pe")), S_TD_C),
         _avantage_cell(sb.get("pe"), sa.get("pe"), sector_b, sector_a),   # lower is better
         Paragraph(_mult(abs((sa.get("pe") or 0) - (sb.get("pe") or 0))), S_TD_C)],
        [Paragraph("EV/EBITDA median", S_TD_L),
         Paragraph(_mult(sa.get("ev_eb")), S_TD_C),
         Paragraph(_mult(sb.get("ev_eb")), S_TD_C),
         _avantage_cell(sb.get("ev_eb"), sa.get("ev_eb"), sector_b, sector_a),
         Paragraph(_mult(abs((sa.get("ev_eb") or 0) - (sb.get("ev_eb") or 0))), S_TD_C)],
        [Paragraph("Croissance Rev. med.", S_TD_L),
         Paragraph(_pct(sa.get("revg")), S_TD_C),
         Paragraph(_pct(sb.get("revg")), S_TD_C),
         _avantage_cell(sa.get("revg"), sb.get("revg"), sector_a, sector_b),
         Paragraph(_pct(abs((sa.get("revg") or 0) - (sb.get("revg") or 0)), sign=False), S_TD_C)],
        [Paragraph("Marge EBITDA med.", S_TD_L),
         Paragraph(_pct(sa.get("em"), sign=False), S_TD_C),
         Paragraph(_pct(sb.get("em"), sign=False), S_TD_C),
         _avantage_cell(sa.get("em"), sb.get("em"), sector_a, sector_b),
         Paragraph(_pct(abs((sa.get("em") or 0) - (sb.get("em") or 0)), sign=False), S_TD_C)],
        [Paragraph("Marge Nette med.", S_TD_L),
         Paragraph(_pct(sa.get("nm"), sign=False), S_TD_C),
         Paragraph(_pct(sb.get("nm"), sign=False), S_TD_C),
         _avantage_cell(sa.get("nm"), sb.get("nm"), sector_a, sector_b),
         Paragraph(_pct(abs((sa.get("nm") or 0) - (sb.get("nm") or 0)), sign=False), S_TD_C)],
        [Paragraph("ROE median", S_TD_L),
         Paragraph(_pct(sa.get("roe"), sign=False), S_TD_C),
         Paragraph(_pct(sb.get("roe"), sign=False), S_TD_C),
         _avantage_cell(sa.get("roe"), sb.get("roe"), sector_a, sector_b),
         Paragraph(_pct(abs((sa.get("roe") or 0) - (sb.get("roe") or 0)), sign=False), S_TD_C)],
        [Paragraph("ROIC median", S_TD_L),
         Paragraph(_pct(sa.get("roic"), sign=False), S_TD_C),
         Paragraph(_pct(sb.get("roic"), sign=False), S_TD_C),
         _avantage_cell(sa.get("roic"), sb.get("roic"), sector_a, sector_b),
         Paragraph(_pct(abs((sa.get("roic") or 0) - (sb.get("roic") or 0)), sign=False), S_TD_C)],
        [Paragraph("FCF Yield med.", S_TD_L),
         Paragraph(_pct(sa.get("fcfy"), sign=False), S_TD_C),
         Paragraph(_pct(sb.get("fcfy"), sign=False), S_TD_C),
         _avantage_cell(sa.get("fcfy"), sb.get("fcfy"), sector_a, sector_b),
         Paragraph(_pct(abs((sa.get("fcfy") or 0) - (sb.get("fcfy") or 0)), sign=False), S_TD_C)],
        [Paragraph("Beta median", S_TD_L),
         Paragraph(f"{sa.get('beta', 1.0):.2f}" if sa.get("beta") else "—", S_TD_C),
         Paragraph(f"{sb.get('beta', 1.0):.2f}" if sb.get("beta") else "—", S_TD_C),
         _avantage_cell(sb.get("beta"), sa.get("beta"), sector_b, sector_a),
         Paragraph(f"{abs((sa.get('beta') or 1) - (sb.get('beta') or 1)):.2f}", S_TD_C)],
        [Paragraph("Perf. 52S med.", S_TD_L),
         Paragraph(_pct(sa.get("mom")), S_TD_C),
         Paragraph(_pct(sb.get("mom")), S_TD_C),
         _avantage_cell(sa.get("mom"), sb.get("mom"), sector_a, sector_b),
         Paragraph(_pct(abs((sa.get("mom") or 0) - (sb.get("mom") or 0)), sign=False), S_TD_C)],
    ]
    story.append(_tbl(syn_data, cols))
    story.append(Spacer(1, 3 * mm))

    # Radar chart (reduit pour equilibrer la page)
    try:
        radar_img = _chart_radar_pdf(sa, sb, sector_a[:12], sector_b[:12])
        story.append(KeepTogether([
            _img(radar_img, w=90*mm, h=70*mm),
        ]))
    except Exception as e:
        log.warning("[cmp_secteur_pdf] radar: %s", e)

    story.append(PageBreak())

    # ── PAGE 3 : Valorisation ─────────────────────────────────────────────────
    story += section("Valorisation Comparee — Multiples de Marche", "2")
    _val_text = D.get("llm", {}).get("valuation_analysis") or (
        f"Analyse des multiples medianes — {sector_a} vs {sector_b}. "
        f"{'Le secteur le moins valorise est ' + (sector_a if (sa.get('pe') or 999) < (sb.get('pe') or 999) else sector_b) + ' (P/E ' + _mult((sa if (sa.get('pe') or 999) < (sb.get('pe') or 999) else sb).get('pe')) + ' vs ' + _mult((sb if (sa.get('pe') or 999) < (sb.get('pe') or 999) else sa).get('pe')) + ').'} "
        "Un multiple inferieur n'implique pas une opportunite — verifier la coherence avec les fondamentaux."
    )
    story.append(Paragraph(_xml(_val_text), S_BODY))
    story.append(Spacer(1, 3 * mm))
    try:
        v_img = _chart_valuation_pdf(sa, sb, sector_a[:12], sector_b[:12])
        story.append(_img(v_img, w=TABLE_W, h=70*mm))
    except Exception as e:
        log.warning("[cmp_secteur_pdf] valuation chart: %s", e)

    story.append(Spacer(1, 3 * mm))

    # ── PAGE 3 suite : Marges ─────────────────────────────────────────────────
    story += section("Qualite & Marges — Rentabilite Operationnelle", "3")
    winner_m = sector_a if (sa.get("em") or -999) > (sb.get("em") or -999) else sector_b
    _margins_text = D.get("llm", {}).get("margins_analysis") or (
        f"{winner_m} affiche une marge EBITDA superieure ({_pct((sa if winner_m == sector_a else sb).get('em'), sign=False)}). "
        f"La marge nette reflete la qualite du modele economique. "
        f"ROE median le plus eleve : {_pct(min(max(sa.get('roe') or 0, sb.get('roe') or 0), 999.9), sign=False)}."
    )
    story.append(Paragraph(_xml(_margins_text), S_BODY))
    story.append(Spacer(1, 3 * mm))
    try:
        m_img = _chart_margins_pdf(sa, sb, sector_a[:12], sector_b[:12])
        story.append(_img(m_img, w=TABLE_W, h=70*mm))
    except Exception as e:
        log.warning("[cmp_secteur_pdf] margins chart: %s", e)
    story.append(PageBreak())

    # ── PAGE 4 : Capital Allocation ────────────────────────────────────────────
    story += section("Capital Allocation & Remuneration de l'Actionnaire", "4")

    dy_a = sa.get("div_yield")
    dy_b = sb.get("div_yield")
    pt_a = sa.get("payout")
    pt_b = sb.get("payout")
    fy_a = sa.get("fcfy")
    fy_b = sb.get("fcfy")

    # div_yield / payout / fcfy sont stockes en decimal (0.013 = 1.3%) → ×100 pour affichage
    dy_a_p = (dy_a or 0) * 100; dy_b_p = (dy_b or 0) * 100
    pt_a_p = (pt_a or 0) * 100; pt_b_p = (pt_b or 0) * 100
    fy_a_p = (fy_a or 0) * 100; fy_b_p = (fy_b or 0) * 100

    def _ca_winner(va, vb, sa_name, sb_name, higher=True):
        """Retourne le nom du secteur gagnant ou 'Egalite'."""
        try:
            fa, fb = float(va or 0), float(vb or 0)
            if abs(fa - fb) < 0.3:  # seuil en % apres multiplication
                return "Egalite"
            return sa_name if (fa > fb) == higher else sb_name
        except Exception:
            return "—"

    ca_data = [
        [Paragraph("Indicateur", S_TH_L),
         Paragraph(sector_a[:18], S_TH_C),
         Paragraph(sector_b[:18], S_TH_C),
         Paragraph("Avantage", S_TH_C)],
        [Paragraph("Rendement dividende med.", S_TD_L),
         Paragraph(_pct(dy_a_p, sign=False), S_TD_C),
         Paragraph(_pct(dy_b_p, sign=False), S_TD_C),
         Paragraph(_ca_winner(dy_a_p, dy_b_p, sector_a[:14], sector_b[:14]), S_TD_C)],
        [Paragraph("FCF Yield median", S_TD_L),
         Paragraph(_pct(fy_a_p, sign=False), S_TD_C),
         Paragraph(_pct(fy_b_p, sign=False), S_TD_C),
         Paragraph(_ca_winner(fy_a_p, fy_b_p, sector_a[:14], sector_b[:14]), S_TD_C)],
        [Paragraph("Payout Ratio median", S_TD_L),
         Paragraph(_pct(pt_a_p, sign=False), S_TD_C),
         Paragraph(_pct(pt_b_p, sign=False), S_TD_C),
         Paragraph("—", S_TD_C)],
        [Paragraph("Score FinSight", S_TD_L),
         Paragraph(f"{sa.get('score', 0)}/100", S_TD_C),
         Paragraph(f"{sb.get('score', 0)}/100", S_TD_C),
         Paragraph(_ca_winner(sa.get("score"), sb.get("score"), sector_a[:14], sector_b[:14]), S_TD_C)],
    ]
    story.append(_tbl(ca_data, [75*mm, 35*mm, 35*mm, 35*mm]))
    story.append(Spacer(1, 4 * mm))

    # Texte LLM ou fallback
    _gen_higher_dy = sector_a if dy_a_p > dy_b_p else sector_b
    _gen_higher_fy = sector_a if fy_a_p > fy_b_p else sector_b
    _ca_fallback = (
        f"{_gen_higher_dy} offre un rendement dividende superieur ({_pct(dy_a_p if _gen_higher_dy == sector_a else dy_b_p, sign=False)}), "
        f"convenant aux portefeuilles de type 'revenu'. "
        f"{_gen_higher_fy} presente un FCF Yield plus eleve ({_pct(fy_a_p if _gen_higher_fy == sector_a else fy_b_p, sign=False)}), "
        f"signal d'une generation de cash robuste et d'une meilleure capacite de remuneration future de l'actionnaire."
    )
    _ca_text = D.get("llm", {}).get("capital_alloc_analysis") or _ca_fallback
    story += _llm_box(_ca_text)

    # Pas de PageBreak ici — la section Croissance suit naturellement

    # ── PAGE 5 : Croissance & Momentum ────────────────────────────────────────
    story += section("Croissance & Momentum — Acceleration ou Ralentissement ?", "5")
    faster = sector_a if (sa.get("revg") or -999) > (sb.get("revg") or -999) else sector_b
    slower = sector_b if faster == sector_a else sector_a
    fs = sa if faster == sector_a else sb; ss = sb if faster == sector_a else sa
    spread = abs((sa.get("revg") or 0) - (sb.get("revg") or 0))
    _growth_text = D.get("llm", {}).get("growth_analysis") or (
        f"{faster} enregistre une croissance revenue medianne superieure de {spread:.1f} pts "
        f"({_pct(fs.get('revg'))} vs {_pct(ss.get('revg'))}). "
        f"Le momentum 52S {'confirme cette tendance' if ((fs.get('mom') or 0) > (ss.get('mom') or 0)) else 'diverge — le marche anticipe un ralentissement'} "
        f"pour {faster}."
    )
    story.append(Paragraph(_xml(_growth_text), S_BODY))
    story.append(Spacer(1, 3 * mm))
    try:
        mo_img = _chart_momentum_pdf(sa, sb, sector_a[:12], sector_b[:12])
        story.append(_img(mo_img, w=TABLE_W, h=70*mm))
    except Exception as e:
        log.warning("[cmp_secteur_pdf] momentum chart: %s", e)

    # Tableau complementaire
    story.append(Spacer(1, 4 * mm))
    comp_data = [
        [Paragraph("Indicateur", S_TH_L),
         Paragraph(sector_a[:15], S_TH_C),
         Paragraph(sector_b[:15], S_TH_C)],
        [Paragraph("Croissance Revenue med.", S_TD_L), Paragraph(_pct(sa.get("revg")), S_TD_C), Paragraph(_pct(sb.get("revg")), S_TD_C)],
        [Paragraph("Performance 52S med.", S_TD_L), Paragraph(_pct(sa.get("mom")), S_TD_C), Paragraph(_pct(sb.get("mom")), S_TD_C)],
        [Paragraph("Beta median", S_TD_L), Paragraph(f"{sa.get('beta', 1):.2f}" if sa.get("beta") else "—", S_TD_C), Paragraph(f"{sb.get('beta', 1):.2f}" if sb.get("beta") else "—", S_TD_C)],
        [Paragraph("FCF Yield med.", S_TD_L), Paragraph(_pct((sa.get("fcfy") or 0)*100, sign=False), S_TD_C), Paragraph(_pct((sb.get("fcfy") or 0)*100, sign=False), S_TD_C)],
        [Paragraph("Piotroski F-Score med.", S_TD_L), Paragraph(f"{sa.get('pf', 0):.1f}/9" if sa.get("pf") else "—", S_TD_C), Paragraph(f"{sb.get('pf', 0):.1f}/9" if sb.get("pf") else "—", S_TD_C)],
        [Paragraph("Score Global FinSight", S_TD_L), Paragraph(f"{sa.get('score', 0)}/100", S_TD_C), Paragraph(f"{sb.get('score', 0)}/100", S_TD_C)],
    ]
    story.append(_tbl(comp_data, [80*mm, 48*mm, 48*mm]))
    story.append(PageBreak())

    # ── PAGE 6 : Top acteurs Secteur A ────────────────────────────────────────
    story += section(f"Top Acteurs — {sector_a}", "6")
    sorted_a = sorted(D["td_a"], key=lambda x: x.get("score_global", 0), reverse=True)[:8]
    _build_top_table(story, sorted_a, sector_a, COL_A)
    story.append(Spacer(1, 3 * mm))
    story += _llm_box(D.get("llm", {}).get("top_a_analysis", ""), col=COL_A)

    # ── Top acteurs Secteur B ─────────────────────────────────────────────────
    story += section(f"Top Acteurs — {sector_b}", "7")
    sorted_b = sorted(D["td_b"], key=lambda x: x.get("score_global", 0), reverse=True)[:8]
    _build_top_table(story, sorted_b, sector_b, COL_B)
    story.append(Spacer(1, 3 * mm))
    story += _llm_box(D.get("llm", {}).get("top_b_analysis", ""), col=COL_B)
    story.append(PageBreak())

    # ── PAGE 7 : Risques & Catalyseurs ───────────────────────────────────────
    content_a = _get_content(sector_a)
    content_b = _get_content(sector_b)

    story += section(f"Risques & Catalyseurs — {sector_a}", "8")
    _build_risques_pdf(story, content_a, sector_a)
    story.append(PageBreak())

    story += section(f"Risques & Catalyseurs — {sector_b}", "9")
    _build_risques_pdf(story, content_b, sector_b)
    story.append(PageBreak())

    # ── PAGE 8 : Recommandation ───────────────────────────────────────────────
    story += section("Recommandation d'Allocation", "10")
    story.append(Paragraph(
        "Positionnement FinSight derive du scoring multidimensionnel (Value + Growth + Quality + Momentum). "
        "Ce signal est indicatif — toute decision d'investissement requiert une analyse complementaire.",
        S_BODY))
    story.append(Spacer(1, 4 * mm))

    rec_data = [
        [Paragraph("", S_TH_L),
         Paragraph(sector_a[:18], S_TH_C),
         Paragraph(sector_b[:18], S_TH_C)],
        [Paragraph("Signal FinSight", S_TD_B),
         Paragraph(D["sig_a_lbl"], _sty("sa_s", size=9, color=D["sig_a_col"], bold=True, align=TA_CENTER)),
         Paragraph(D["sig_b_lbl"], _sty("sb_s", size=9, color=D["sig_b_col"], bold=True, align=TA_CENTER))],
        [Paragraph("Score (/100)", S_TD_L), Paragraph(f"{sa.get('score', 0)}", S_TD_C), Paragraph(f"{sb.get('score', 0)}", S_TD_C)],
        [Paragraph("Universe", S_TD_L), Paragraph(_xml(D["universe_a"]), S_TD_C), Paragraph(_xml(D["universe_b"]), S_TD_C)],
        [Paragraph("Nb societes analysees", S_TD_L), Paragraph(f"{D['na']}", S_TD_C), Paragraph(f"{D['nb']}", S_TD_C)],
        [Paragraph("P/E median", S_TD_L), Paragraph(_mult(sa.get("pe")), S_TD_C), Paragraph(_mult(sb.get("pe")), S_TD_C)],
        [Paragraph("EV/EBITDA median", S_TD_L), Paragraph(_mult(sa.get("ev_eb")), S_TD_C), Paragraph(_mult(sb.get("ev_eb")), S_TD_C)],
        [Paragraph("Marge EBITDA med.", S_TD_L), Paragraph(_pct(sa.get("em"), sign=False), S_TD_C), Paragraph(_pct(sb.get("em"), sign=False), S_TD_C)],
        [Paragraph("ROE median", S_TD_L), Paragraph(_pct(sa.get("roe"), sign=False), S_TD_C), Paragraph(_pct(sb.get("roe"), sign=False), S_TD_C)],
        [Paragraph("Croissance Rev. med.", S_TD_L), Paragraph(_pct(sa.get("revg")), S_TD_C), Paragraph(_pct(sb.get("revg")), S_TD_C)],
        [Paragraph("Perf. 52S med.", S_TD_L), Paragraph(_pct(sa.get("mom")), S_TD_C), Paragraph(_pct(sb.get("mom")), S_TD_C)],
    ]
    story.append(_tbl(rec_data, [80*mm, 48*mm, 48*mm]))
    story.append(Spacer(1, 4 * mm))
    story += _llm_box(D.get("llm", {}).get("allocation_rec", ""))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "Note : Surponderer = score >= 65 | Neutre = score >= 45 | Sous-ponderer = score < 45. "
        "Le Score FinSight est un indicateur proprietaire multidimensionnel. "
        "Il ne constitue pas un conseil en investissement.",
        S_NOTE))
    story.append(PageBreak())

    # ── PAGE 9 : Disclaimer ───────────────────────────────────────────────────
    story += section("Mentions Legales & Methodologie", "11")
    disclaimers = [
        ("Sources de donnees", "Les donnees financieres sont issues de yfinance (Yahoo Finance), Finnhub et Financial Modeling Prep. FinSight IA ne garantit pas l'exhaustivite ou l'exactitude de ces donnees. Les chiffres presentent les medianes des societes analysees a la date de generation."),
        ("Caractere informatif", "Ce document est produit a des fins d'information uniquement. Il ne constitue pas un conseil en investissement, une recommendation d'achat ou de vente de valeurs mobilieres, ni une invitation a contracter."),
        ("Scores & Signaux", "Le Score FinSight est un indicateur proprietaire multidimensionnel (value + growth + qualite + momentum, chacun sur 25 pts). Les signaux Surponderer / Neutre / Sous-ponderer sont derives mecaniquement des scores — ils ne constituent pas des recommendations d'investissement personnalisees."),
        ("Responsabilite", "FinSight IA et ses developpers declinent toute responsabilite quant a l'utilisation de ce document. Toute decision d'investissement doit etre prise apres consultation d'un conseiller financier agree."),
        ("Performance passee", "Les performances passees et les donnees historiques ne prejugent pas des performances futures. Les comparatifs sont etablis a date de generation du rapport."),
    ]
    for title, text in disclaimers:
        story.append(KeepTogether([
            Paragraph(title, S_SSEC),
            Paragraph(text, S_DISC),
            Spacer(1, 3 * mm),
        ]))
    story.append(rule())
    story.append(Paragraph(
        f"Genere par FinSight IA  |  {D['date_str']}  |  Usage confidentiel — ne pas diffuser",
        _sty("fin", size=7, color=GREY_TEXT, align=TA_CENTER)))

    return story


def _build_top_table(story, tickers, sector_name, col_header):
    top_data = [[
        Paragraph("Societe", S_TH_L),
        Paragraph("Score", S_TH_C),
        Paragraph("P/E", S_TH_C),
        Paragraph("EV/EBITDA", S_TH_C),
        Paragraph("Croiss.Rev.", S_TH_C),
        Paragraph("Mg.EBITDA", S_TH_C),
        Paragraph("Mg.Nette", S_TH_C),
        Paragraph("ROE", S_TH_C),
    ]]
    for t in tickers:
        revg = t.get("revenue_growth", 0)
        if revg and abs(revg) < 5:  # yfinance donne en decimale (0.08 = 8%)
            revg = revg * 100
        roe_v = t.get("roe")
        if roe_v is not None:
            try:
                roe_v = min(float(roe_v), 999.9)
            except (TypeError, ValueError):
                roe_v = None
        top_data.append([
            Paragraph(t.get("company", t.get("ticker", ""))[:22], S_TD_L),
            Paragraph(f"{t.get('score_global', 0)}/100", S_TD_C),
            Paragraph(_mult(t.get("pe_ratio")), S_TD_C),
            Paragraph(_mult(t.get("ev_ebitda")), S_TD_C),
            Paragraph(_pct(revg), S_TD_C),
            Paragraph(_pct(t.get("ebitda_margin"), sign=False), S_TD_C),
            Paragraph(_pct(t.get("net_margin"), sign=False), S_TD_C),
            Paragraph(_pct(roe_v, sign=False), S_TD_C),
        ])
    t = _tbl(top_data, [46*mm, 18*mm, 18*mm, 20*mm, 20*mm, 20*mm, 18*mm, 16*mm], header_col=col_header)
    story.append(t)


def _build_risques_pdf(story, content, sector_name):
    from reportlab.platypus import KeepTogether as _KT
    cats  = content.get("catalyseurs", [])[:3]
    risks = content.get("risques", [])[:3]

    cat_data  = [[Paragraph("Catalyseur", S_TH_L), Paragraph("Description", S_TH_L)]]
    risk_data = [[Paragraph("Risque", S_TH_L), Paragraph("Description", S_TH_L)]]
    for title, body in cats:
        cat_data.append([Paragraph(f"+ {title}", S_TD_B), Paragraph(body[:200], S_TD_L)])
    for title, body in risks:
        risk_data.append([Paragraph(f"- {title}", _sty("rb", size=8, color=RED, bold=True)), Paragraph(body[:200], S_TD_L)])

    cols2 = [55*mm, 121*mm]
    story.append(_tbl(cat_data,  cols2, header_col=COL_A if "Technology" in sector_name or "Industrial" in sector_name or "Health" in sector_name else NAVY_LIGHT))
    story.append(Spacer(1, 3 * mm))
    story.append(_tbl(risk_data, cols2, header_col=RED))

    conds = content.get("conditions", [])[:4]
    if conds:
        cond_data = [[Paragraph("Type", S_TH_C), Paragraph("Condition d'invalidation", S_TH_L), Paragraph("Horizon", S_TH_C)]]
        for c in conds:
            cond_data.append([Paragraph(c[0], S_TD_C), Paragraph(c[1][:100], S_TD_L), Paragraph(c[2], S_TD_C)])
        story.append(_KT([Spacer(1, 3*mm), _tbl(cond_data, [25*mm, 115*mm, 36*mm])]))


# ── Entetes / pieds de page ───────────────────────────────────────────────────
def _build_page_header_footer(sector_a, sector_b, universe_label, date_str):
    def on_page(canvas, doc):
        canvas.saveState()
        # Header
        canvas.setFillColor(NAVY)
        canvas.rect(MARGIN_L, PAGE_H - 14*mm, PAGE_W - MARGIN_L - MARGIN_R, 8*mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(MARGIN_L + 3*mm, PAGE_H - 9*mm, f"FinSight IA  |  Comparatif : {sector_a} vs {sector_b}  |  {universe_label}")
        canvas.setFont("Helvetica", 7.5)
        canvas.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 9*mm, date_str)
        # Footer
        canvas.setFillColor(GREY_LIGHT)
        canvas.rect(MARGIN_L, MARGIN_B - 5*mm, PAGE_W - MARGIN_L - MARGIN_R, 5*mm, fill=1, stroke=0)
        canvas.setFillColor(GREY_TEXT)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(MARGIN_L + 3*mm, MARGIN_B - 3*mm, "Usage confidentiel  |  FinSight IA")
        canvas.drawRightString(PAGE_W - MARGIN_R, MARGIN_B - 3*mm, f"Page {doc.page}")
        canvas.restoreState()
    return on_page


# ── Point d'entree ────────────────────────────────────────────────────────────
def generate_cmp_secteur_pdf(
    tickers_a: list[dict],
    sector_a: str,
    universe_a: str,
    tickers_b: list[dict],
    sector_b: str,
    universe_b: str,
    output_path: str,
) -> None:
    D = _prepare(tickers_a, sector_a, universe_a, tickers_b, sector_b, universe_b)
    D["llm"] = _generate_llm_texts(D)
    story = _build_story(D)

    on_page = _build_page_header_footer(sector_a, sector_b, D["universe_label"], D["date_str"])

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T + 6*mm,
        bottomMargin=MARGIN_B + 3*mm,
        title=f"Comparatif Sectoriel {sector_a} vs {sector_b}",
    )
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    size_ko = Path(output_path).stat().st_size // 1024
    log.info("[CmpSecteurPDF] Sauvegarde : %s (%d Ko)", output_path, size_ko)
