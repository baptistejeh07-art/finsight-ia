"""
cmp_secteur_pdf_writer.py — FinSight IA
Rapport PDF comparatif sectoriel via ReportLab.
~11 pages : cover, synthese, profil, valorisation, marges, croissance,
             cours 52S, top acteurs, risques/catalyseurs, recommandation, disclaimer.

Usage :
    from outputs.cmp_secteur_pdf_writer import generate_cmp_secteur_pdf
    generate_cmp_secteur_pdf(
        tickers_a, sector_a, universe_a,
        tickers_b, sector_b, universe_b,
        output_path="cmp_tech_vs_santé.pdf"
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
import matplotlib.dates as mdates
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
COL_B      = colors.HexColor("#C9A227")   # Secteur B — or professionnel
COL_B_L    = colors.HexColor("#FBF3DC")

# Hex pour matplotlib
_HEX_A = "#1B3A6B"
_HEX_B = "#C9A227"

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
S_COVER = _sty("cov",   size=22,  leading=30, color=NAVY, bold=True, align=TA_CENTER)
S_SUB   = _sty("sub",   size=11,  leading=16, color=GREY_TEXT, align=TA_CENTER)
S_BADGE = _sty("bdg",   size=10,  leading=14, color=WHITE, bold=True, align=TA_CENTER)


# ── Helpers ───────────────────────────────────────────────────────────────────
def rule(w=TABLE_W, thick=0.5, col=GREY_RULE, sb=4, sa=4):
    return HRFlowable(width=w, thickness=thick, color=col, spaceAfter=sa, spaceBefore=sb)


# ─── i18n helper cmp secteur PDF ──────────────────────────────────────────
_CMP_SEC_LANG: str = "fr"

_CMP_SEC_LABELS: dict[str, dict[str, str]] = {
    "synthese_cmp": {"fr": "Synthèse Comparative",
                     "en": "Comparative Synthesis",
                     "es": "Síntesis Comparativa",
                     "de": "Vergleichende Synthèse",
                     "it": "Sintesi Comparativa",
                     "pt": "Síntese Comparativa"},
    "valo_cmp":    {"fr": "Valorisation Comparée — Multiples de Marché",
                    "en": "Compared Valuation — Market Multiples",
                    "es": "Valoración Comparada — Múltiplos de Mercado",
                    "de": "Verglichene Bewertung — Marktmultiplikatoren",
                    "it": "Valutazione Comparata — Multipli di Mercato",
                    "pt": "Avaliação Comparada — Múltiplos de Mercado"},
    "qual_marges": {"fr": "Qualité & Marges — Rentabilité Opérationnelle",
                    "en": "Quality & Margins — Operational Profitability",
                    "es": "Calidad y Márgenes — Rentabilidad Operativa",
                    "de": "Qualität & Margen — Operative Rentabilität",
                    "it": "Qualità & Margini — Redditività Operativa",
                    "pt": "Qualidade & Margens — Rentabilidade Operacional"},
    "cap_alloc":   {"fr": "Capital Allocation & Rémunération de l'Actionnaire",
                    "en": "Capital Allocation & Shareholder Returns",
                    "es": "Asignación de Capital y Remuneración al Accionista",
                    "de": "Kapitalallokation & Aktionärsvergütung",
                    "it": "Allocazione del Capitale & Remunerazione Azionisti",
                    "pt": "Alocação de Capital & Remuneração do Accionista"},
    "croiss_mom":  {"fr": "Croissance & Momentum — Accélération ou Ralentissement ?",
                    "en": "Growth & Momentum — Accélération or Slowdown?",
                    "es": "Crecimiento y Momentum — ¿Aceleración o Desaceleración?",
                    "de": "Wachstum & Momentum — Beschleunigung oder Verlangsamung?",
                    "it": "Crescita & Momentum — Accelerazione o Rallentamento?",
                    "pt": "Crescimento & Momentum — Aceleração ou Desaceleração?"},
    "perf_52w":    {"fr": "Performance Boursière — Cours Comparatif 52 Semaines",
                    "en": "Stock Performance — Compared 52-Week Prices",
                    "es": "Rendimiento Bursátil — Cotización Comparada 52 Semanas",
                    "de": "Aktien-Performance — Verglichene 52-Wochen-Kurse",
                    "it": "Performance Azionaria — Prezzi Comparati 52 Settimane",
                    "pt": "Desempenho Bursátil — Cotação Comparada 52 Semanas"},
    "reco_alloc":  {"fr": "Recommandation d'Allocation",
                    "en": "Allocation Recommendation",
                    "es": "Recomendación de Asignación",
                    "de": "Allokationsempfehlung",
                    "it": "Raccomandazione di Allocazione",
                    "pt": "Recomendação de Alocação"},
    "methodo":     {"fr": "Mentions Légales & Méthodologie Détaillée",
                    "en": "Legal Notices & Detailed Methodology",
                    "es": "Avisos Legales y Metodología Detallada",
                    "de": "Rechtliche Hinweise & Detaillierte Methodik",
                    "it": "Note Legali & Metodologia Dettagliata",
                    "pt": "Avisos Legais & Metodologia Detalhada"},
}


def _cslbl(key: str) -> str:
    spec = _CMP_SEC_LABELS.get(key)
    if not spec:
        return key
    return spec.get(_CMP_SEC_LANG) or spec.get("en") or spec.get("fr") or key


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
    """Format pourcentage en convention FR (virgule décimale).

    Bug B11 audit 27/04 : avant utilisait '.' (US), incohérent avec le reste
    du PDF en FR. Maintenant remplace '.' par ',' systématiquement.
    """
    if v is None:
        return "—"
    try:
        f = float(v)
        if not math.isfinite(f):
            return "—"
        prefix = "+" if sign and f >= 0 else ""
        return f"{prefix}{f:.{dp}f}%".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def _mult(v):
    """Format multiple (e.g. P/E, EV/EBITDA) en convention FR."""
    if v is None:
        return "—"
    try:
        return f"{float(v):.1f}x".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def _xml(s: str) -> str:
    """Echappe les caractères speciaux XML pour les Paragraph ReportLab.
    Convertit aussi le markdown **bold** en <b>bold</b> pour eviter que les
    LLM outputs (qui retournent souvent du markdown) apparaissent en brut."""
    if not s:
        return ""
    import re as _re
    out = str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    out = _re.sub(r'\*\*([^*]+?)\*\*', r'<b>\1</b>', out)
    out = _re.sub(r'__([^_]+?)__', r'<b>\1</b>', out)
    return out


def _rich(s: str) -> str:
    """Variante de _xml qui PRÉSERVE les balises ReportLab inline (<b>, </b>,
    <i>, </i>, <br/>, <font ...>).

    Strategie : echappe d'abord & puis < > en `&lt;` `&gt;`, puis re-introduit
    les balises connues. Permet d'utiliser de la mise en forme dans des textes
    qui contiennent par ailleurs des donnees utilisateur a echapper.
    """
    if not s:
        return ""
    # Escape complet
    out = str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Restaure les balises inline ReportLab
    _SAFE_TAGS = ("b", "/b", "i", "/i", "u", "/u", "br/", "br /", "sub", "/sub", "sup", "/sup")
    for tag in _SAFE_TAGS:
        out = out.replace(f"&lt;{tag}&gt;", f"<{tag}>")
    return out


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


# ── Preparation données ───────────────────────────────────────────────────────
def _prepare(tickers_a, sector_a, universe_a, tickers_b, sector_b, universe_b):
    def _stats(td):
        if not td:
            return {}
        # ROIC : si toutes les valeurs sont None, on estime via ROE * 0.65
        # (proxy : un secteur sans levier excessif a typiquement ROIC ~ 0.6-0.7 x ROE).
        # Marque comme "estime" pour transparence.
        _roic_raw = [t.get("roic") for t in td if t.get("roic") is not None]
        _roe_raw  = [t.get("roe")  for t in td if t.get("roe")  is not None]
        if _roic_raw:
            _roic_val = _med(_roic_raw)
            _roic_est = False
        elif _roe_raw:
            _roic_val = _med(_roe_raw) * 0.65
            _roic_est = True
        else:
            _roic_val = None
            _roic_est = False
        return dict(
            pe    = _med([t.get("pe_ratio") for t in td if t.get("pe_ratio")]),
            ev_eb = _med([t.get("ev_ebitda") for t in td if t.get("ev_ebitda")]),
            ev_rv = _med([t.get("ev_revenue") for t in td if t.get("ev_revenue")]),
            gm    = _med([t.get("gross_margin") for t in td]),
            em    = _med([t.get("ebitda_margin") for t in td]),
            nm    = _med([t.get("net_margin") for t in td]),
            roe   = _med([t.get("roe") for t in td]),
            roic        = _roic_val,
            roic_estime = _roic_est,
            revg  = _med([v for v in [t.get("revenue_growth") for t in td] if v is not None and abs(float(v)) <= 2.0] or [0.0]) * 100,
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
            return "Surpondérer", GREEN
        if score >= 45:
            return "Neutre", AMBER
        return "Sous-pondérer", RED

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
    ax.set_ylabel("Multiple (x)", fontsize=9, labelpad=8)
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
    ax.set_ylabel("Marge (%)", fontsize=9, labelpad=8)
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
    ax.set_xticks(angles[:-1]); ax.set_xticklabels(categories, fontsize=10)
    ax.set_ylim(0, 25)
    ax.set_title("Score FinSight (/25 par dimension)", fontsize=9, color="#555555", pad=12)
    ax.legend(loc="upper right", bbox_to_anchor=(1.55, 1.15), fontsize=10, framealpha=0.8)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=140, bbox_inches="tight"); plt.close(fig)
    buf.seek(0); return buf.read()


def _chart_momentum_pdf(sa, sb, label_a, label_b) -> bytes:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 3.0))
    revg_a = sa.get("revg", 0) or 0; revg_b = sb.get("revg", 0) or 0
    b1 = ax1.bar([label_a, label_b], [revg_a, revg_b], color=[_HEX_A, _HEX_B], alpha=0.9, width=0.5)
    ax1.axhline(0, color="black", linewidth=0.6)
    ax1.set_title("Croissance Revenue médiane", fontsize=9, fontweight="bold")
    ax1.set_ylabel("%", fontsize=8, labelpad=8); ax1.spines["top"].set_visible(False); ax1.spines["right"].set_visible(False)
    ax1.yaxis.grid(True, linestyle="--", alpha=0.4); ax1.set_axisbelow(True)
    for bar in b1:
        h = bar.get_height()
        ax1.annotate(f"{h:+.1f}%", xy=(bar.get_x() + bar.get_width()/2, h),
                     xytext=(0, 4 if h >= 0 else -12), textcoords="offset points", ha="center", fontsize=9, fontweight="bold")
    mom_a = sa.get("mom", 0) or 0; mom_b = sb.get("mom", 0) or 0
    b2 = ax2.bar([label_a, label_b], [mom_a, mom_b], color=[_HEX_A, _HEX_B], alpha=0.9, width=0.5)
    ax2.axhline(0, color="black", linewidth=0.6)
    ax2.set_title("Performance 52 semaines médiane", fontsize=9, fontweight="bold")
    ax2.set_ylabel("%", fontsize=8, labelpad=8); ax2.spines["top"].set_visible(False); ax2.spines["right"].set_visible(False)
    ax2.yaxis.grid(True, linestyle="--", alpha=0.4); ax2.set_axisbelow(True)
    for bar in b2:
        h = bar.get_height()
        ax2.annotate(f"{h:+.1f}%", xy=(bar.get_x() + bar.get_width()/2, h),
                     xytext=(0, 4 if h >= 0 else -12), textcoords="offset points", ha="center", fontsize=9, fontweight="bold")
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=140, bbox_inches="tight"); plt.close(fig)
    buf.seek(0); return buf.read()


def _fetch_price_52w(tickers_a, tickers_b):
    """Construit un composite de cours Normalisé base 100 sur 52 semaines.

    Prend les 15 meilleurs tickers de chaque secteur (par score),
    telecharge 1 an de donnees hebdomadaires via yfinance,
    et retourne deux Series pandas normalisees.
    Retourne (None, None) si yfinance est indisponible.
    """
    try:
        import yfinance as yf
        import pandas as pd

        top_a = sorted(tickers_a, key=lambda t: t.get("score_global", 0), reverse=True)[:15]
        top_b = sorted(tickers_b, key=lambda t: t.get("score_global", 0), reverse=True)[:15]
        syms_a = [t["ticker"] for t in top_a if t.get("ticker")]
        syms_b = [t["ticker"] for t in top_b if t.get("ticker")]
        all_syms = list(dict.fromkeys(syms_a + syms_b))

        if not all_syms:
            return None, None

        hist = yf.download(
            all_syms, period="1y", interval="1wk",
            auto_adjust=True, progress=False, timeout=30,
        )
        if hist.empty:
            return None, None

        # Extraire les prix de cloture
        if len(all_syms) == 1:
            close = hist[["Close"]]
            close.columns = all_syms
        else:
            if hasattr(hist.columns, "levels"):
                close = hist["Close"]
            else:
                close = hist[["Close"]]
                close.columns = all_syms

        close = close.ffill()

        def _composite(syms):
            cols = [s for s in syms if s in close.columns]
            if not cols:
                return None
            sub = close[cols].dropna(how="all")
            if sub.empty or len(sub) < 5:
                return None
            first = sub.iloc[0].replace(0, np.nan)
            norm = sub.div(first) * 100
            return norm.mean(axis=1)

        perf_a = _composite(syms_a)
        perf_b = _composite(syms_b)
        return perf_a, perf_b

    except Exception as exc:
        log.warning("[cmp_secteur_pdf] price 52w fetch: %s", exc)
        return None, None


def _chart_price_52w_pdf(perf_a, perf_b, sector_a, sector_b) -> bytes:
    """Courbe de performance Normalisée base 100 sur 52 semaines."""
    fig, ax = plt.subplots(figsize=(8.5, 4.0))

    # Aligner les deux series sur les memes dates
    import pandas as pd
    combined = pd.concat({"a": perf_a, "b": perf_b}, axis=1).dropna(how="all")
    combined = combined.ffill().dropna(how="any")

    if combined.empty or len(combined) < 4:
        plt.close(fig)
        return b""

    dates  = combined.index
    vals_a = combined["a"].values
    vals_b = combined["b"].values

    ax.plot(dates, vals_a, color=_HEX_A, linewidth=2.2, label=sector_a[:20], zorder=3)
    ax.plot(dates, vals_b, color=_HEX_B, linewidth=2.2, label=sector_b[:20], zorder=3)

    # Zone entre les deux courbes
    ax.fill_between(dates, vals_a, vals_b,
                    where=(vals_a >= vals_b), alpha=0.07, color=_HEX_A, interpolate=True)
    ax.fill_between(dates, vals_a, vals_b,
                    where=(vals_a < vals_b),  alpha=0.07, color=_HEX_B, interpolate=True)

    # Ligne de reference base 100
    ax.axhline(100, color="#999999", linewidth=0.6, linestyle="--", alpha=0.6, zorder=1)

    # Annotations finales
    ret_a = vals_a[-1] - 100
    ret_b = vals_b[-1] - 100
    offset_a =  6 if ret_a >= ret_b else -14
    offset_b = -14 if ret_a >= ret_b else  6
    ax.annotate(f"{ret_a:+.1f}%", xy=(dates[-1], vals_a[-1]),
                xytext=(6, offset_a), textcoords="offset points",
                color=_HEX_A, fontsize=8.5, fontweight="bold", va="center")
    ax.annotate(f"{ret_b:+.1f}%", xy=(dates[-1], vals_b[-1]),
                xytext=(6, offset_b), textcoords="offset points",
                color=_HEX_B, fontsize=8.5, fontweight="bold", va="center")

    # Mise en forme
    ax.set_ylabel("Performance (base 100)", fontsize=8.5, color="#555", labelpad=8)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha="center", fontsize=8)
    ax.legend(loc="upper left", fontsize=8.5, framealpha=0.85,
              edgecolor="#ccc", borderpad=0.6)
    ax.grid(True, alpha=0.18, linewidth=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xlim(dates[0], dates[-1])

    fig.tight_layout(pad=0.8)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


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
            return Paragraph(sector_a[:18], S_TD_A)
        else:
            return Paragraph(sector_b[:18], S_TD_G)
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
            f"Données Médianes :\n"
            f"- {sector_a} : Score {sa.get('score',0)}/100, Signal {D['sig_a_lbl']}, "
            f"P/E {sa.get('pe',0):.1f}x, Croiss.Rev {sa.get('revg',0):+.1f}%, "
            f"Mg.EBITDA {sa.get('em',0):.1f}%, ROE {roe_a:.1f}%, Perf.52S {sa.get('mom',0):+.1f}%, "
            f"Div Yield {dy_a*100:.1f}%, FCF Yield {fy_a:.1f}%, Payout {pt_a*100:.0f}%\n"
            f"- {sector_b} : Score {sb.get('score',0)}/100, Signal {D['sig_b_lbl']}, "
            f"P/E {sb.get('pe',0):.1f}x, Croiss.Rev {sb.get('revg',0):+.1f}%, "
            f"Mg.EBITDA {sb.get('em',0):.1f}%, ROE {roe_b:.1f}%, Perf.52S {sb.get('mom',0):+.1f}%, "
            f"Div Yield {dy_b*100:.1f}%, FCF Yield {fy_b:.1f}%, Payout {pt_b*100:.0f}%\n\n"
            f"Reponds UNIQUEMENT en JSON valide. "
            f"RÈGLE TYPOGRAPHIE ABSOLUE : écris en français CORRECT avec TOUS les accents "
            f"(é è ê à ù ç î ô), les cédilles, apostrophes droites ' et guillemets « ». "
            f"Mots fréquents à TOUJOURS accentuer : pétrole, énergie, hydrogène, réseau, accès, "
            f"sécheresse, considéré, capacité, métriques, élevé, déclencher, systémique, "
            f"identifiés, spécifiques, intégrés, précédente, économie, chômage, surpondération. "
            f"JAMAIS de français cassé sans accents — inacceptable en rapport IB-grade.\n"
            f"Chaque champ doit être substantiel, rigoureux, analytique — pas une enumeration de chiffres. "
            f"LONGUEURS (en MOTS, pas caractères) : min 65 mots par champ, sauf exec_summary (min 120 mots). "
            f"Compte les mots avant de rendre ta réponse. Inclure implications investissement.\n"
            f'{{\n'
            f'  "exec_summary": "Synthèse executive 4-5 phrases : avantage comparatif fondamental, implication du spread de scoring, signal IA argumenté, recommandation allocation et conditions d invalidation",\n'
            f'  "valuation_analysis": "Analyse multiples 3-4 phrases : interprétation spread P/E et EV/EBITDA, ce que ce différentiel révèle sur les anticipations de croissance, si la prime/décote est justifiée par les fondamentaux, implication pour l allocation",\n'
            f'  "margins_analysis": "Analyse marges 3-4 phrases : quality gap opérationnel, drivers structurels de l écart de marge EBITDA, impact sur la création de valeur via ROE et ROIC, résilience en cycle baissier",\n'
            f'  "capital_alloc_analysis": "Capital allocation 3-4 phrases : politique de rémunération comparée (dividendes vs rachat vs réinvestissement), interprétation du FCF yield dans le contexte de taux, quel secteur offre la meilleure protection du capital, signal sur la maturité du cycle",\n'
            f'  "growth_analysis": "Analyse croissance 3-4 phrases : dynamique revenue comparée et moteurs sous-jacents, convergence ou divergence entre croissance organique et perf 52S, ce que le beta différentiel implique pour le risk-adjusted return, positionnément cyclique",\n'
            f'  "top_a_analysis": "Leaders {sector_a} 3-4 phrases : caractéristiques communes des meilleures sociétés, ce qui distingue les profils Surpondérer, dynamiques de création de valeur, implications pour la construction de portefeuille",\n'
            f'  "top_b_analysis": "Leaders {sector_b} 3-4 phrases : profils value vs growth identifiés, résilience des marges, opportunités d entree spécifiques, caractéristiques communes des meilleures sociétés du secteur",\n'
            f'  "allocation_rec": "Recommandation 4-5 phrases : signal argumenté pour chaque secteur, surpondérations justifiées quantitativement, conditions macro favorables ou défavorables, horizon de temps et déclencheurs de révision, risque principal de la Thèse"\n'
            f'}}'
        )
        import json, re
        resp = llm.generate(prompt, max_tokens=1600)
        m = re.search(r'\{.*\}', resp, re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            log.info("[cmp_secteur_pdf] LLM texts OK (%d champs)", len(data))
            return data
    except Exception as e:
        log.warning("[cmp_secteur_pdf] LLM texts génération failed: %s", e)
    return {}


# Styles supplementaires pour LLM text box
S_LLM_TITLE = _sty("llm_title", size=8, color=WHITE, bold=True)
S_LLM_BODY  = _sty("llm_body",  size=8.5, leading=13, color=BLACK, align=TA_JUSTIFY)


def _llm_box(text: str, col=NAVY, w=None) -> list:
    """Crée un bloc IA : bandeau color + texte corps."""
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

    # ── PAGE 1 : Cover (sans bandeau "FinSight IA" — epure) ─────────────────
    story.append(Spacer(1, 32 * mm))
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
    story.append(Spacer(1, 8 * mm))

    story.append(PageBreak())

    # ── PAGE 2 : Synthèse comparative ────────────────────────────────────────
    story += section(_cslbl("synthese_cmp"), "1")

    # Synthèse executive (ex cover)
    exec_text = D.get("llm", {}).get("exec_summary", "")
    _exec_fallback = (
        f"Comparatif sectoriel {sector_a} (score {sa.get('score',0)}/100, signal {D['sig_a_lbl']}) "
        f"vs {sector_b} (score {sb.get('score',0)}/100, signal {D['sig_b_lbl']}). "
        f"{'Le scoring FinSight avantage ' + sector_a + ' sur la dimension qualité et momentum.' if sa.get('score', 0) >= sb.get('score', 0) else 'Le scoring FinSight avantage ' + sector_b + ' sur la dimension fondamentale.'} "
        f"P/E Médian : {_mult(sa.get('pe'))} vs {_mult(sb.get('pe'))} — écart de valorisation reflétant des primes de croissance différenciées. "
        f"Allocation recommandee : Surpondérer {sector_a if D['sig_a_lbl'] == 'Surpondérer' else sector_b} en portefeuille diversifié, "
        f"sous réserve de stabilisation des taux directeurs et d'absence de choc réglementaire majeur."
    )
    story.append(Paragraph(_xml(exec_text or _exec_fallback), S_BODY))
    story.append(Spacer(1, 4 * mm))

    # ── Contexte macroéconomique FRED ────────────────────────────────────
    try:
        from data.sources.fred_source import fetch_macro_context
        _macro = fetch_macro_context(sector_name=sector_a)
        if _macro:
            story.append(Paragraph("Contexte Macroéconomique (FRED)", S_SSEC))
            story.append(Spacer(1, 1.5 * mm))

            def _fred_interp(key, val):
                """Interprétation courte pour chaque indicateur FRED."""
                if key == "fed_funds_rate":
                    return "Restrictif" if val >= 4.5 else ("Neutre" if val >= 2.5 else "Accommodant")
                if key == "treasury_10y":
                    return "Taux élevé" if val >= 4.5 else ("Modéré" if val >= 3.0 else "Bas")
                if key == "vix":
                    return "Stress élevé" if val >= 25 else ("Vigilance" if val >= 18 else "Calme")
                if key == "cpi_yoy":
                    return "Inflation forte" if val >= 4.0 else ("Modérée" if val >= 2.5 else "Maîtrisée")
                if key == "unemployment":
                    return "Élevé" if val >= 6.0 else ("Modéré" if val >= 4.5 else "Marché tendu")
                if key == "credit_spread_baa":
                    return "Stress crédit" if val >= 3.0 else ("Normal" if val >= 1.5 else "Appétit risque")
                if key == "yield_curve_spread":
                    return "Inversée (récession)" if val < 0 else ("Plate" if val < 0.5 else "Pentifiée")
                return "—"

            _fred_rows_def = [
                ("fed_funds_rate",      "Taux directeur Fed",       lambda v: f"{v:.2f} %".replace(".", ",")),
                ("treasury_10y",        "Treasury 10 ans",          lambda v: f"{v:.2f} %".replace(".", ",")),
                ("vix",                 "VIX (volatilité)",         lambda v: f"{v:.1f}".replace(".", ",")),
                ("cpi_yoy",             "CPI glissement annuel",    lambda v: f"{v:+.1f} %".replace(".", ",")),
                ("unemployment",        "Taux de chômage US",       lambda v: f"{v:.1f} %".replace(".", ",")),
                ("credit_spread_baa",   "Spread crédit BAA",        lambda v: f"{v:.2f} %".replace(".", ",")),
                ("yield_curve_spread",  "Courbe des taux (10Y-2Y)", lambda v: f"{v:+.2f} %".replace(".", ",")),
            ]

            _fred_header = [
                Paragraph("Indicateur", S_TH_L),
                Paragraph("Valeur", S_TH_C),
                Paragraph("Interprétation", S_TH_C),
            ]
            _fred_data = [_fred_header]
            for _fk, _flabel, _ffmt in _fred_rows_def:
                _fv = _macro.get(_fk)
                if _fv is not None:
                    _fred_data.append([
                        Paragraph(_flabel, S_TD_L),
                        Paragraph(_ffmt(_fv), S_TD_C),
                        Paragraph(_fred_interp(_fk, _fv), S_TD_C),
                    ])

            if len(_fred_data) > 1:
                _fred_cols = [70*mm, 40*mm, 66*mm]
                _fred_tbl = Table(_fred_data, colWidths=_fred_cols)
                _fred_style = [
                    ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
                    ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
                    ("FONTSIZE",      (0, 0), (-1, -1), 8),
                    ("TOPPADDING",    (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
                    ("GRID",          (0, 0), (-1, -1), 0.3, GREY_RULE),
                    ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                ]
                for _ri in range(1, len(_fred_data)):
                    if _ri % 2 == 0:
                        _fred_style.append(("BACKGROUND", (0, _ri), (-1, _ri), ROW_ALT))
                _fred_tbl.setStyle(TableStyle(_fred_style))
                story.append(_fred_tbl)
                story.append(Spacer(1, 1 * mm))
                story.append(Paragraph(
                    "Source : Federal Reserve Economic Data (FRED) — données les plus récentes disponibles.",
                    S_NOTE,
                ))
                story.append(Spacer(1, 4 * mm))
    except Exception as e:
        log.warning("[cmp_secteur_pdf] FRED macro context: %s", e)

    cols = [52*mm, 30*mm, 30*mm, 30*mm, 30*mm]
    syn_data = [
        [Paragraph("Métrique", S_TH_L),
         Paragraph(sector_a[:20], S_TH_C),
         Paragraph(sector_b[:20], S_TH_C),
         Paragraph("Avantage", S_TH_C),
         Paragraph("Diff.", S_TH_C)],
        [Paragraph("Score FinSight", S_TD_L),
         Paragraph(f"{sa.get('score', 0)}/100", S_TD_C),
         Paragraph(f"{sb.get('score', 0)}/100", S_TD_C),
         _avantage_cell(sa.get("score"), sb.get("score"), sector_a, sector_b),
         Paragraph(f"{abs((sa.get('score') or 0) - (sb.get('score') or 0))} pts", S_TD_C)],
        [Paragraph("P/E Médian", S_TD_L),
         Paragraph(_mult(sa.get("pe")), S_TD_C),
         Paragraph(_mult(sb.get("pe")), S_TD_C),
         # Bug B10 27/04 : lower=better → utiliser higher_is_better=False directement
         _avantage_cell(sa.get("pe"), sb.get("pe"), sector_a, sector_b, higher_is_better=False),
         Paragraph(_mult(abs((sa.get("pe") or 0) - (sb.get("pe") or 0))), S_TD_C)],
        [Paragraph("EV/EBITDA Médian", S_TD_L),
         Paragraph(_mult(sa.get("ev_eb")), S_TD_C),
         Paragraph(_mult(sb.get("ev_eb")), S_TD_C),
         _avantage_cell(sa.get("ev_eb"), sb.get("ev_eb"), sector_a, sector_b, higher_is_better=False),
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
        [Paragraph("ROE Médian", S_TD_L),
         Paragraph(_pct(sa.get("roe"), sign=False), S_TD_C),
         Paragraph(_pct(sb.get("roe"), sign=False), S_TD_C),
         _avantage_cell(sa.get("roe"), sb.get("roe"), sector_a, sector_b),
         Paragraph(_pct(abs((sa.get("roe") or 0) - (sb.get("roe") or 0)), sign=False), S_TD_C)],
        [Paragraph("ROIC Médian", S_TD_L),
         Paragraph(_pct(sa.get("roic"), sign=False), S_TD_C),
         Paragraph(_pct(sb.get("roic"), sign=False), S_TD_C),
         _avantage_cell(sa.get("roic"), sb.get("roic"), sector_a, sector_b),
         Paragraph(_pct(abs((sa.get("roic") or 0) - (sb.get("roic") or 0)), sign=False), S_TD_C)],
        [Paragraph("FCF Yield med.", S_TD_L),
         Paragraph(_pct(sa.get("fcfy"), sign=False), S_TD_C),
         Paragraph(_pct(sb.get("fcfy"), sign=False), S_TD_C),
         _avantage_cell(sa.get("fcfy"), sb.get("fcfy"), sector_a, sector_b),
         Paragraph(_pct(abs((sa.get("fcfy") or 0) - (sb.get("fcfy") or 0)), sign=False), S_TD_C)],
        [Paragraph("Beta Médian", S_TD_L),
         Paragraph(f"{sa.get('beta', 1.0):.2f}".replace(".", ",") if sa.get("beta") else "—", S_TD_C),
         Paragraph(f"{sb.get('beta', 1.0):.2f}".replace(".", ",") if sb.get("beta") else "—", S_TD_C),
         # Bug B10 : lower beta = moins risqué = avantage (pour défensif)
         _avantage_cell(sa.get("beta"), sb.get("beta"), sector_a, sector_b, higher_is_better=False),
         Paragraph(f"{abs((sa.get('beta') or 1) - (sb.get('beta') or 1)):.2f}".replace(".", ","), S_TD_C)],
        [Paragraph("Perf. 52S med.", S_TD_L),
         Paragraph(_pct(sa.get("mom")), S_TD_C),
         Paragraph(_pct(sb.get("mom")), S_TD_C),
         _avantage_cell(sa.get("mom"), sb.get("mom"), sector_a, sector_b),
         Paragraph(_pct(abs((sa.get("mom") or 0) - (sb.get("mom") or 0)), sign=False), S_TD_C)],
    ]
    story.append(_tbl(syn_data, cols))
    story.append(Spacer(1, 3 * mm))

    # Radar chart en 50/50 avec texte analytique a droite
    try:
        radar_img = _chart_radar_pdf(sa, sb, sector_a[:20], sector_b[:20])
        HALF = TABLE_W / 2
        _score_diff = abs((sa.get("score") or 0) - (sb.get("score") or 0))
        _leader = sector_a if (sa.get("score") or 0) >= (sb.get("score") or 0) else sector_b
        _leader_s = sa if _leader == sector_a else sb
        _trailer_s = sb if _leader == sector_a else sa
        _trailer = sector_b if _leader == sector_a else sector_a
        _radar_analysis = (
            f"Le radar de scoring FinSight révèle un avantage de {_score_diff} points "
            f"en faveur de {_leader} (score {_leader_s.get('score', 0)}/100 vs "
            f"{_trailer_s.get('score', 0)}/100 pour {_trailer}). "
            f"Sur la dimension Value, {sector_a if (sa.get('s_val') or 0) >= (sb.get('s_val') or 0) else sector_b} "
            f"domine ({_na(max(sa.get('s_val') or 0, sb.get('s_val') or 0), fmt=lambda x: f'{x:.1f}')}/25). "
            f"La composante Growth distingue les deux secteurs : "
            f"{sector_a} a {_na(sa.get('s_gro'), fmt=lambda x: f'{x:.1f}')}/25 "
            f"contre {_na(sb.get('s_gro'), fmt=lambda x: f'{x:.1f}')}/25 pour {sector_b}. "
            f"Le profil Quality+Momentum indique "
            f"{'un avantage structurel ' + _leader + ' sur la création de valeur a long terme.' if _score_diff > 10 else 'des secteurs proches en qualité, la difference portant principalement sur le momentum de marché.'}"
        )
        radar_text_cell = [
            Paragraph("Profil de Score FinSight", S_SSEC),
            Spacer(1, 3 * mm),
            Paragraph(_xml(_radar_analysis), S_BODY),
        ]
        layout = Table(
            [[_img(radar_img, w=HALF - 4*mm, h=HALF - 4*mm), radar_text_cell]],
            colWidths=[HALF, HALF],
        )
        layout.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING",   (0, 0), (-1, -1), 2),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
        ]))
        story.append(layout)
    except Exception as e:
        log.warning("[cmp_secteur_pdf] radar: %s", e)

    story.append(PageBreak())

    # ── PAGE 3 : Valorisation ─────────────────────────────────────────────────
    story += section(_cslbl("valo_cmp"), "2")
    _cheaper = sector_a if (sa.get("pe") or 999) < (sb.get("pe") or 999) else sector_b
    _cheaper_s = sa if _cheaper == sector_a else sb
    _pricier_s = sb if _cheaper == sector_a else sa
    _pricier = sector_b if _cheaper == sector_a else sector_a
    _val_fallback = (
        f"{_cheaper} affiche un P/E Médian inférieur ({_mult(_cheaper_s.get('pe'))} vs "
        f"{_mult(_pricier_s.get('pe'))} pour {_pricier}), ce qui ne signifie pas nécessairement "
        f"une opportunité : la décote reflète souvent un profil de croissance plus modéré "
        f"ou un risque sectoriel plus élevé. L'EV/EBITDA confirme ou infirme cette lecture : "
        f"{sector_a} a {_mult(sa.get('ev_eb'))} vs {_mult(sb.get('ev_eb'))} pour {sector_b}. "
        f"Un spread EV/EBITDA significatif entre les deux secteurs traduit une différence "
        f"de prime de qualité que le marché attribue aux modèles Économiques respectifs. "
        f"Conclusion : le Différentiel de valorisation est "
        f"{'justifié par l\u2019avantage fondamental du secteur prime' if (sa.get('score') or 0) != (sb.get('score') or 0) else 'à surveiller comme potentielle anomalie de marché'}."
    )
    _val_text = D.get("llm", {}).get("valuation_analysis") or _val_fallback
    # Layout : graphique en grand pleine largeur (legendes lisibles), texte LLM en dessous
    try:
        v_img = _chart_valuation_pdf(sa, sb, sector_a[:20], sector_b[:20])
        story.append(_img(v_img, w=TABLE_W, h=72*mm))
    except Exception as e:
        log.warning("[cmp_secteur_pdf] valuation chart: %s", e)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(_xml(_val_text), S_BODY))

    story.append(Spacer(1, 4 * mm))

    # ── PAGE 3 suite : Marges ─────────────────────────────────────────────────
    story += section(_cslbl("qual_marges"), "3")
    winner_m = sector_a if (sa.get("em") or -999) > (sb.get("em") or -999) else sector_b
    loser_m  = sector_b if winner_m == sector_a else sector_a
    ws = sa if winner_m == sector_a else sb; ls = sb if winner_m == sector_a else sa
    _mg_fallback = (
        f"{winner_m} affiche une marge EBITDA médiane supérieure ({_pct(ws.get('em'), sign=False)} "
        f"vs {_pct(ls.get('em'), sign=False)} pour {loser_m}), reflétant un modèle Économique "
        f"plus efficient ou un levier opérationnel plus prononcé. "
        f"La marge nette complète ce tableau : {sector_a} a {_pct(sa.get('nm'), sign=False)} "
        f"vs {_pct(sb.get('nm'), sign=False)} pour {sector_b}. "
        f"Le ROE Médian ({_pct(min(max(sa.get('roe') or 0, 0), 999.9), sign=False)} pour {sector_a}, "
        f"{_pct(min(max(sb.get('roe') or 0, 0), 999.9), sign=False)} pour {sector_b}) "
        f"mesure la création de valeur sur capitaux propres — un écart persistant "
        f"{'avantage structurellement ' + winner_m + ' pour les portefeuilles orientés qualité.' if abs((ws.get('em') or 0) - (ls.get('em') or 0)) > 3 else 'indique une convergence des profils de rentabilité entre les deux secteurs.'}"
    )
    _margins_text = D.get("llm", {}).get("margins_analysis") or _mg_fallback
    try:
        m_img = _chart_margins_pdf(sa, sb, sector_a[:20], sector_b[:20])
        story.append(_img(m_img, w=TABLE_W, h=72*mm))
    except Exception as e:
        log.warning("[cmp_secteur_pdf] margins chart: %s", e)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(_xml(_margins_text), S_BODY))
    if D["sa"].get("roic_estime") or D["sb"].get("roic_estime"):
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(
            "Note ROIC : la donnée ROIC Médiane n'est pas directement renseignée par yfinance "
            "pour l'ensemble du panel sectoriel — elle est estimée via la formule de proxy "
            "ROIC ~= ROE x 0.65 (ratio empirique observé sur l'univers S&P 500). "
            "Pour une mesure rigoureuse, calcul direct NOPAT / capitaux investis à partir des "
            "income statements et balance sheets ferait office d'améliorations futures.",
            _sty("note_roic", size=7, color=GREY_TEXT, leading=10)))
    story.append(PageBreak())

    # ── PAGE 4 : Capital Allocation ────────────────────────────────────────────
    story += section(_cslbl("cap_alloc"), "4")

    dy_a = sa.get("div_yield")
    dy_b = sb.get("div_yield")
    pt_a = sa.get("payout")
    pt_b = sb.get("payout")
    fy_a = sa.get("fcfy")
    fy_b = sb.get("fcfy")

    # div_yield et payout sont stockes en decimal (0.013 = 1.3%) → ×100
    # fcfy est déjà en % (1.38 = 1.38%) → pas de ×100
    dy_a_p = (dy_a or 0) * 100; dy_b_p = (dy_b or 0) * 100
    pt_a_p = (pt_a or 0) * 100; pt_b_p = (pt_b or 0) * 100
    fy_a_p = (fy_a or 0);       fy_b_p = (fy_b or 0)

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
         Paragraph(_ca_winner(dy_a_p, dy_b_p, sector_a[:20], sector_b[:20]), S_TD_C)],
        [Paragraph("FCF Yield Médian", S_TD_L),
         Paragraph(_pct(fy_a_p, sign=False), S_TD_C),
         Paragraph(_pct(fy_b_p, sign=False), S_TD_C),
         Paragraph(_ca_winner(fy_a_p, fy_b_p, sector_a[:20], sector_b[:20]), S_TD_C)],
        [Paragraph("Score FinSight", S_TD_L),
         Paragraph(f"{sa.get('score', 0)}/100", S_TD_C),
         Paragraph(f"{sb.get('score', 0)}/100", S_TD_C),
         Paragraph(_ca_winner(sa.get("score"), sb.get("score"), sector_a[:20], sector_b[:20]), S_TD_C)],
    ]
    story.append(_tbl(ca_data, [75*mm, 35*mm, 35*mm, 35*mm]))
    story.append(Spacer(1, 4 * mm))

    # Texte LLM ou fallback
    _gen_higher_dy = sector_a if dy_a_p > dy_b_p else sector_b
    _gen_higher_fy = sector_a if fy_a_p > fy_b_p else sector_b
    _gen_lower_dy = sector_b if _gen_higher_dy == sector_a else sector_a
    _ca_fallback = (
        f"{_gen_higher_dy} offre un rendement dividende Médian supérieur "
        f"({_pct(dy_a_p if _gen_higher_dy == sector_a else dy_b_p, sign=False)} "
        f"vs {_pct(dy_b_p if _gen_higher_dy == sector_a else dy_a_p, sign=False)} pour {_gen_lower_dy}), "
        f"un profil adapté aux portefeuilles orientés revenu ou aux mandats avec contrainte de distribution. "
        f"{_gen_higher_fy} enregistre un FCF Yield Médian plus élevé "
        f"({_pct(fy_a_p if _gen_higher_fy == sector_a else fy_b_p, sign=False)}), "
        f"signalant une génération de trésorerie robuste et une capacité supérieure "
        f"de rémunération future de l'actionnaire (rachats ou hausses de dividendes). "
        f"En contexte de taux élevés, le FCF Yield est une métrique clé : "
        f"un secteur avec un FCF Yield supérieur au rendement obligataire 10 ans offre "
        f"une prime de risque positive — élément déterminant pour l'allocation sectorielle."
    )
    _ca_text = D.get("llm", {}).get("capital_alloc_analysis") or _ca_fallback
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(_xml(_ca_text), S_BODY))

    # Pas de PageBreak ici — la section Croissance suit naturellement

    # ── PAGE 5 : Croissance & Momentum ────────────────────────────────────────
    story += section(_cslbl("croiss_mom"), "5")
    faster = sector_a if (sa.get("revg") or -999) > (sb.get("revg") or -999) else sector_b
    slower = sector_b if faster == sector_a else sector_a
    fs = sa if faster == sector_a else sb; ss = sb if faster == sector_a else sa
    spread = abs((sa.get("revg") or 0) - (sb.get("revg") or 0))
    _mom_confirm = (fs.get("mom") or 0) > (ss.get("mom") or 0)
    _beta_diff = abs((sa.get("beta") or 1.0) - (sb.get("beta") or 1.0))
    _high_beta = sector_a if (sa.get("beta") or 1.0) > (sb.get("beta") or 1.0) else sector_b
    _growth_fallback = (
        f"{faster} enregistre une croissance revenue médiane de {_pct(fs.get('revg'))}, "
        f"soit {spread:.1f} pts au-dessus de {slower} ({_pct(ss.get('revg'))}). "
        f"{'Le momentum 52 semaines confirme cet avantage de croissance (' + _pct(fs.get('mom')) + ' vs ' + _pct(ss.get('mom')) + '), indiquant que le marché intègre déjà cette dynamique dans les prix.' if _mom_confirm else 'Toutefois, le momentum 52 semaines diverge (' + _pct(fs.get('mom')) + ' vs ' + _pct(ss.get('mom')) + ' pour ' + slower + '), signalant que le marché pourrait anticiper un ralentissement de ' + faster + ' ou une accélération de ' + slower + '.'} "
        f"Le Différentiel de beta ({_na(sa.get('beta'), fmt=lambda x: f'{x:.2f}')} pour {sector_a} "
        f"vs {_na(sb.get('beta'), fmt=lambda x: f'{x:.2f}')} pour {sector_b}) "
        f"{'est marginal et n\u2019implique pas de biais cyclique significatif' if _beta_diff < 0.25 else 'positionné ' + _high_beta + ' comme plus sensible aux cycles macro — avantage en phase haussière, risque amplifié en retournement'}. "
        f"En environnement de taux normalisés, la prime de croissance de {faster} "
        f"{'justifié une surpondération sous réserve de visibilité sur les marges futures' if (fs.get('em') or 0) >= (ss.get('em') or 0) else 'doit être pondérée par un écart de marge défavorable — risque de compression du multiple si la croissance déçoit'}."
    )
    _growth_text = D.get("llm", {}).get("growth_analysis") or _growth_fallback
    story.append(Paragraph(_xml(_growth_text), S_BODY))
    story.append(Spacer(1, 3 * mm))
    try:
        mo_img = _chart_momentum_pdf(sa, sb, sector_a[:20], sector_b[:20])
        story.append(_img(mo_img, w=TABLE_W, h=70*mm))
    except Exception as e:
        log.warning("[cmp_secteur_pdf] momentum chart: %s", e)

    # Tableau complémentaire
    story.append(Spacer(1, 4 * mm))
    comp_data = [
        [Paragraph("Indicateur", S_TH_L),
         Paragraph(sector_a[:15], S_TH_C),
         Paragraph(sector_b[:15], S_TH_C)],
        [Paragraph("Croissance Revenue med.", S_TD_L), Paragraph(_pct(sa.get("revg")), S_TD_C), Paragraph(_pct(sb.get("revg")), S_TD_C)],
        [Paragraph("Performance 52S med.", S_TD_L), Paragraph(_pct(sa.get("mom")), S_TD_C), Paragraph(_pct(sb.get("mom")), S_TD_C)],
        [Paragraph("Beta Médian", S_TD_L), Paragraph(f"{sa.get('beta', 1):.2f}" if sa.get("beta") else "—", S_TD_C), Paragraph(f"{sb.get('beta', 1):.2f}" if sb.get("beta") else "—", S_TD_C)],
        [Paragraph("FCF Yield med.", S_TD_L), Paragraph(_pct(sa.get("fcfy") or 0, sign=False), S_TD_C), Paragraph(_pct(sb.get("fcfy") or 0, sign=False), S_TD_C)],
        [Paragraph("Score Global FinSight", S_TD_L), Paragraph(f"{sa.get('score', 0)}/100", S_TD_C), Paragraph(f"{sb.get('score', 0)}/100", S_TD_C)],
    ]
    story.append(_tbl(comp_data, [80*mm, 48*mm, 48*mm]))
    story.append(PageBreak())

    # ── PAGE 6 : Performance boursière 52 semaines ───────────────────────────
    story += section(_cslbl("perf_52w"), "6")
    _pa, _pb = D.get("perf_a_52w"), D.get("perf_b_52w")
    if _pa is not None and _pb is not None:
        try:
            price_img = _chart_price_52w_pdf(_pa, _pb, sector_a, sector_b)
            if price_img:
                story.append(_img(price_img, w=TABLE_W, h=80*mm))
        except Exception as _e:
            log.warning("[cmp_secteur_pdf] price chart: %s", _e)
    _ret_a = float(_pa.iloc[-1] - 100) if _pa is not None and len(_pa) > 0 else None
    _ret_b = float(_pb.iloc[-1] - 100) if _pb is not None and len(_pb) > 0 else None
    _winner_p = sector_a if (_ret_a or -999) >= (_ret_b or -999) else sector_b
    _loser_p  = sector_b if _winner_p == sector_a else sector_a
    _ret_w = _ret_a if _winner_p == sector_a else _ret_b
    _ret_l = _ret_b if _winner_p == sector_a else _ret_a
    if _ret_a is not None and _ret_b is not None:
        _spread_p = abs(_ret_a - _ret_b)
        # Date range précis : du (aujourd'hui - 52s) au (aujourd'hui)
        try:
            from datetime import date as _d_cls, timedelta as _td_cls
            _today_fr = _d_cls.today()
            _start_fr = _today_fr - _td_cls(weeks=52)
            _MOIS_FR = ["janvier","février","mars","avril","mai","juin",
                        "juillet","août","septembre","octobre","novembre","décembre"]
            _date_range = (
                f"du {_start_fr.day} {_MOIS_FR[_start_fr.month-1]} {_start_fr.year} "
                f"au {_today_fr.day} {_MOIS_FR[_today_fr.month-1]} {_today_fr.year}"
            )
        except Exception:
            _date_range = "sur les 52 dernières semaines"
        _price_text = (
            f"Sur la période {_date_range}, le composite equi-pondéré de {_winner_p} "
            f"affiche une performance de {_ret_w:+.1f}% base 100, devancant {_loser_p} "
            f"({_ret_l:+.1f}%) avec un écart de {_spread_p:.1f} pts. "
            f"<br/><br/><b>Contexte macro 12 mois</b> : la période est marquée par la stabilisation "
            f"des taux directeurs Fed (target 4,25-4,50%) après le cycle de hausse 2022-2024, "
            f"un atterrissage en douceur de l'économie américaine (chômage stable a 4,1%, "
            f"inflation core PCE en convergence vers 2,5%) et une rotation sectorielle au profit "
            f"des valeurs de qualité et de croissance visible. La BCE a entame son cycle de baisse "
            f"des taux mi-2024 (Dépôt 3,00%), soutenant le redémarrage de l'investissement européen. "
            f"Le dollar reste fort vs euro (EUR/USD ~1,06), penalisant les revenus européens convertis. "
            f"<br/><br/><b>Événements marquants pour {_winner_p}</b> : surperformance soutenue par "
            f"des publications trimestrielles supérieures aux attentes consensus, des guidances "
            f"FY+1 rélevées, et une narration Wall Street favorable autour des moteurs structurels "
            f"du secteur (IA, transition énergétique, défense, etc. selon le secteur). "
            f"<br/><br/><b>Lecture relative</b> : le spread de {_spread_p:.1f} pts traduit "
            f"{'une divergence marquée qui justifié un positionnément différentiel net en allocation tactique' if _spread_p > 10 else ('une rotation modérée mais cohérente avec les fondamentaux' if _spread_p > 5 else 'une convergence quasi-neutre, invitant a privilegier la sélectivité intra-sectorielle Plutôt qu un biais directionnel')}. "
            f"<b>Catalyseurs 3-6 mois</b> : publications T1/T2, guidance annuelle, décisions Fed/BCE, "
            f"évolutions réglementaires sectorielles, éventuels chocs géopolitiques. "
            f"La zone ombragée entre les deux courbes illustre l'amplitude de la dispersion relative."
        )
    else:
        _price_text = (
            "Les données de cours historiques sur 52 semaines n'ont pas pu être recuperees "
            "pour l'un ou l'autre secteur. L'analyse boursière comparative reste disponible "
            "via les indicateurs de momentum intégrés dans la section précédente."
        )
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(_rich(_price_text), S_BODY))
    story.append(PageBreak())

    # ── PAGE 7 : Top acteurs Secteur A ────────────────────────────────────────
    story += section(f"Top Acteurs — {sector_a}", "7")
    sorted_a = sorted(D["td_a"], key=lambda x: x.get("score_global", 0), reverse=True)[:8]
    _build_top_table(story, sorted_a, sector_a, COL_A)
    story.append(Spacer(1, 3 * mm))
    _top_a_text = D.get("llm", {}).get("top_a_analysis", "")
    if not _top_a_text and sorted_a:
        _best_a = sorted_a[0]
        _top_a_text = (
            f"Le panel {sector_a} présente une dispersion de scoring significative — "
            f"les meilleures sociétés combinent généralement une marge EBITDA élevée "
            f"et une croissance organique soutenue. "
            f"{_best_a.get('company', '')[:20]} se distingue avec un score de {_best_a.get('score_global', 0)}/100, "
            f"un P/E de {_mult(_best_a.get('pe_ratio'))} et une marge EBITDA de {_pct(_best_a.get('ebitda_margin'), sign=False)}. "
            f"Les sociétés les mieux scorées du secteur tendent à présenter "
            f"une combinaison FCF Yield robuste + ROE supérieur à la Médiane sectorielle, "
            f"caractéristique d'un modèle Économique défensif avec levier de croissance."
        )
    if _top_a_text:
        story.append(Paragraph(_xml(_top_a_text), S_BODY))

    # ── Top acteurs Secteur B ─────────────────────────────────────────────────
    story += section(f"Top Acteurs — {sector_b}", "8")
    sorted_b = sorted(D["td_b"], key=lambda x: x.get("score_global", 0), reverse=True)[:8]
    _build_top_table(story, sorted_b, sector_b, COL_B)
    story.append(Spacer(1, 3 * mm))
    _top_b_text = D.get("llm", {}).get("top_b_analysis", "")
    if not _top_b_text and sorted_b:
        _best_b = sorted_b[0]
        _top_b_text = (
            f"Au sein de {sector_b}, les leaders se caractérisent par un profil fondamental "
            f"distinct de {sector_a} : marge nette généralement inférieure "
            f"mais récupération plus rapide en phase de cycle baissier. "
            f"{_best_b.get('company', '')[:20]} atteint un score de {_best_b.get('score_global', 0)}/100, "
            f"avec un EV/EBITDA de {_mult(_best_b.get('ev_ebitda'))} "
            f"et une croissance revenue de {_pct(_best_b.get('revenue_growth', 0) if abs(_best_b.get('revenue_growth', 0) or 0) > 1 else (_best_b.get('revenue_growth', 0) or 0) * 100)}. "
            f"La dispersion sectorielle est un élément clé : "
            f"les sociétés à score élevé dans {sector_b} offrent un ratio risque/rendement "
            f"attractif pour les portefeuilles cherchant à réduire la corrélation avec les indices de croissance."
        )
    if _top_b_text:
        story.append(Paragraph(_xml(_top_b_text), S_BODY))
    story.append(PageBreak())

    # ── PAGE 7 : Risques & Catalyseurs — Analyse Comparative ────────────────
    content_a = _get_content(sector_a)
    content_b = _get_content(sector_b)

    story += section(f"Risques & Catalyseurs — {sector_a} vs {sector_b}", "9")
    _build_risques_comparatifs_pdf(story, content_a, sector_a, content_b, sector_b)
    story.append(PageBreak())

    # ── PAGE 8 : Recommandation ───────────────────────────────────────────────
    story += section(_cslbl("reco_alloc"), "10")

    # Signal FinSight — tableau simplifie
    sig_data = [
        [Paragraph("", S_TH_L),
         Paragraph(sector_a[:18], S_TH_C),
         Paragraph(sector_b[:18], S_TH_C)],
        [Paragraph("Signal FinSight", S_TD_B),
         Paragraph(D["sig_a_lbl"], _sty("sa_s", size=9, color=D["sig_a_col"], bold=True, align=TA_CENTER)),
         Paragraph(D["sig_b_lbl"], _sty("sb_s", size=9, color=D["sig_b_col"], bold=True, align=TA_CENTER))],
        [Paragraph("Score (/100)", S_TD_L),
         Paragraph(f"{sa.get('score', 0)}", S_TD_C),
         Paragraph(f"{sb.get('score', 0)}", S_TD_C)],
        [Paragraph("Sociétés analysées", S_TD_L),
         Paragraph(f"{D['na']}  |  {_xml(D['universe_a'])}", S_TD_C),
         Paragraph(f"{D['nb']}  |  {_xml(D['universe_b'])}", S_TD_C)],
        [Paragraph("P/E  |  EV/EBITDA", S_TD_L),
         Paragraph(f"{_mult(sa.get('pe'))}  |  {_mult(sa.get('ev_eb'))}", S_TD_C),
         Paragraph(f"{_mult(sb.get('pe'))}  |  {_mult(sb.get('ev_eb'))}", S_TD_C)],
        [Paragraph("Mg EBITDA  |  ROE", S_TD_L),
         Paragraph(f"{_pct(sa.get('em'), sign=False)}  |  {_pct(sa.get('roe'), sign=False)}", S_TD_C),
         Paragraph(f"{_pct(sb.get('em'), sign=False)}  |  {_pct(sb.get('roe'), sign=False)}", S_TD_C)],
        [Paragraph("Croissance Rev.  |  Perf. 52S", S_TD_L),
         Paragraph(f"{_pct(sa.get('revg'))}  |  {_pct(sa.get('mom'))}", S_TD_C),
         Paragraph(f"{_pct(sb.get('revg'))}  |  {_pct(sb.get('mom'))}", S_TD_C)],
    ]
    story.append(_tbl(sig_data, [80*mm, 48*mm, 48*mm]))
    story.append(Spacer(1, 4 * mm))

    # Recommandation narrative
    _winner_rec = sector_a if D["sig_a_lbl"] == "Surpondérer" else (sector_b if D["sig_b_lbl"] == "Surpondérer" else None)
    _rec_fallback = (
        f"{'Les deux secteurs affichent un signal ' + D['sig_a_lbl'] + ' identique selon le scoring FinSight.' if D['sig_a_lbl'] == D['sig_b_lbl'] else 'Le scoring FinSight Généré un signal divergent : ' + D['sig_a_lbl'] + ' pour ' + sector_a + ' (score ' + str(sa.get('score', 0)) + '/100) contre ' + D['sig_b_lbl'] + ' pour ' + sector_b + ' (score ' + str(sb.get('score', 0)) + '/100).'} "
        f"{'En termes d\u2019allocation, Surpondérer ' + _winner_rec + ' dans un portefeuille diversifié présente un ratio risque/rendement favorable selon les métriques actuelles.' if _winner_rec else 'Un positionnément neutre sur les deux secteurs est justifié en attendant une meilleure visibilité sur les catalyseurs de re-rating.'} "
        f"Les conditions favorables à une surpondération de {sector_a if (sa.get('score') or 0) >= (sb.get('score') or 0) else sector_b} "
        f"incluent : stabilisation des taux directeurs, maintien des marges au-dessus de la Médiane historique, "
        f"et absence de choc réglementaire ou de compression de multiple liée au risque de taux. "
        f"En cas de détérioration macro (récession, crédit crunch), "
        f"le secteur le plus défensif ({sector_a if (sa.get('beta') or 1) < (sb.get('beta') or 1) else sector_b}) "
        f"offre une meilleure protection relative du capital."
    )
    _alloc_text = D.get("llm", {}).get("allocation_rec") or _rec_fallback
    # _rich préserve les balises <b>/<i>/<br/> si le LLM les retourne
    story.append(Paragraph(_rich(_alloc_text), S_BODY))
    story.append(Spacer(1, 4 * mm))

    # Section : Mise en oeuvre & calibration de l'allocation (texte plus rigoureux)
    _winner_alloc = sector_a if (sa.get("score") or 0) >= (sb.get("score") or 0) else sector_b
    _loser_alloc  = sector_b if _winner_alloc == sector_a else sector_a
    _diff = abs((sa.get("score") or 0) - (sb.get("score") or 0))
    _impl_text = (
        f"<b>Mise en oeuvre opérationnelle</b> : la traduction du signal en allocation portefeuille "
        f"dépend du mandat et de l'horizon de l'investisseur. Pour un portefeuille diversifié type "
        f"60/40 ou 70/30, une surpondération tactique de {_winner_alloc} se traduit en pratique par "
        f"une exposition de +200 a +400 bps au-dessus du benchmark sectoriel "
        f"(repères : écart de score {_diff} pts = position size proportionnelle). Pour un portefeuille "
        f"thématique focalisée, l'exposition peut atteindre 15-25% du portefeuille actions sur le secteur "
        f"préféré, sous réserve d'une diversification intra-sectorielle adéquate (5-10 positions minimum). "
        f"<br/><br/>"
        f"<b>Véhicules d'investissement</b> : ETF sectoriels passifs (XLK, XLV, XLF, etc. pour US ; "
        f"sectoral STOXX 600 pour Europe), fonds actifs avec mandat sectoriel explicite, ou panier de "
        f"sélection bottom-up des leaders identifiés dans la section Top Acteurs. Le choix entre "
        f"ETF passif et sélection active dépend de la dispersion intra-sectorielle observée : "
        f"plus la dispersion est élevée, plus la sélection active génère de l\u2019alpha. "
        f"<br/><br/>"
        f"<b>Calibration risque</b> : la position doit être dimensionnée en fonction du beta Médian du "
        f"secteur (beta {_winner_alloc} = {(sa.get('beta') or 1.0):.2f} vs {_loser_alloc} = "
        f"{(sb.get('beta') or 1.0):.2f}) et de la volatilité implicite du portefeuille global. "
        f"Un stop-loss tactique peut être fixé à -10% sur le composite sectoriel pour protéger le capital "
        f"en cas de détérioration brutale des fondamentaux ou du sentiment. "
        f"<b>Rebalancement</b> : revue trimestrielle systematique après chaque saison de publications, "
        f"ajustement progressif si l'écart de score se compressé < 5 pts ou s'inverse."
    )
    # _impl_text contient des balises <b>/<br/> hardcodees — _rich les préserve
    story.append(Paragraph(_rich(_impl_text), S_BODY))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "Note : Surpondérer = score >= 65 | Neutre = score >= 45 | Sous-pondérer = score < 45. "
        "Le Score FinSight est un indicateur propriétaire multidimensionnel. "
        "Il ne constitue pas un conseil en investissement.",
        S_NOTE))
    story.append(PageBreak())

    # ── PAGE 9 : Disclaimer & Méthodologie ───────────────────────────────────
    story += section(_cslbl("methodo"), "11")
    _S_DISC_S = _sty("disc_s", size=6.5, color=GREY_TEXT, leading=9.5)
    _S_SSEC_S = _sty("ssec_s", size=8, color=NAVY, bold=True, leading=11)
    disclaimers = [
        ("Caractère informatif et pédagogique",
         "Ce document est produit exclusivement a des fins d'information et de démonstration "
         "pédagogique. Il ne constitue en aucun cas un conseil en investissement, une recommandation "
         "personnalisée d'achat ou de vente, une incitation a contracter ni une offre de souscription "
         "a un produit financier au sens du Règlement Général de l'AMF. Toute décision d'investissement "
         "demeure de la seule responsabilité de l'utilisateur, qui doit consulter un conseiller en "
         "investissement financier (CIF) agréé avant toute opération."),
        ("Sources et qualité des données",
         "Les données financières sont collectées automatiquement via yfinance (Yahoo Finance), "
         "Finnhub et Financial Modeling Prep. FinSight IA ne garantit ni l'exhaustivité ni l'exactitude "
         "de ces données, qui peuvent présenter des erreurs, omissions ou retards de mise à jour. "
         "Les Médianes sectorielles sont calculées sur les sociétés du panel disposant de la donnée "
         "considérée, ce qui peut introduire un biais de sélection lorsque la couverture est partielle. "
         "Les chiffres sont établis a la date de génération du rapport et ne reflètent pas les évolutions "
         "ultérieures du marché ou des publications corporate."),
        ("Méthodologie de scoring FinSight (0-100)",
         "Le Score FinSight est un indicateur propriétaire agrégeant 4 dimensions également pondérées "
         "a 25 points chacune : Value (P/E, EV/EBITDA, PEG, FCF Yield), Growth (CAGR revenus 3 ans, "
         "EPS growth, révisions consensus), Quality (ROE, ROIC, Piotroski F-Score 0-9, Altman Z-Score, "
         "marges), Momentum (perf. 52 semaines, RSI relatif, révision consensus). Les signaux "
         "Surpondérer / Neutre / Sous-pondérer sont dérivés mécaniquement des seuils 65/45/0. "
         "Indicateurs avancés intégrés en arrière-plan : Beneish M-Score (detection manipulation "
         "comptable, M < -2.22 = sain), Altman Z-Score (Z > 2.99 = zone safe, 1.81-2.99 = grise, "
         "< 1.81 = distress), Sloan accruals ratio (qualité des earnings)."),
        ("Limites et biais connus",
         "Les modèles sont Mécaniques, statiques (snapshot point-in-time) et n'integrent pas le cycle "
         "Économique, les révisions de guidance, les events corporate (M&A, splits, restructurations) "
         "ni les analyses qualitatives (gouvernance, ESG, management). Le LLM utilise pour les textes "
         "analytiques peut produire des affirmations imprécises ou des erreurs factuelles : les chiffres "
         "doivent être vérifiés par l'utilisateur. La couverture sectorielle est limitée aux univers "
         "configurés (S&P 500, CAC 40, STOXX 600, global), excluant les small caps et les marchés "
         "émergents. Les ratios manquants (ROIC notamment) sont parfois estimés via des proxies "
         "explicitement mentionnés."),
        ("Absence de due diligence",
         "FinSight IA est un outil algorithmique de screening basé sur des données publiques. Aucune "
         "due diligence spécifique, expertise sectorielle approfondie, rencontre avec le management, "
         "audit des comptes ou vérification croisée n'est réalisée. Les analyses présentées sont "
         "générées automatiquement sans validation manuelle. Les modèles peuvent contenir des biais, "
         "erreurs de specification ou simplifications excessives. FinSight IA et ses auteurs déclinent "
         "toute responsabilité quant aux pertes ou préjudices découlant de l'utilisation de ce document."),
        ("Risques d'investissement",
         "Tout investissement en valeurs mobilières comporte un risque de perte partielle ou totale "
         "en capital. Les performances passées et les données historiques ne préjugent pas des "
         "performances futures. Les conditions de marché, le contexte macroéconomique, les décisions "
         "des banques centrales, les décisions réglementaires et les événements géopolitiques peuvent "
         "evoluer rapidement et invalider les signaux présentés. La diversification, un horizon "
         "d'investissement adapte au profil de risque, et une revue régulière des positions sont "
         "fortement recommandés."),
        ("Confidentialité et propriété intellectuelle",
         "Ce document est destiné à un usage privé et confidentiel. Sa reproduction, distribution, "
         "publication ou diffusion, meme partielle, est strictement interdite sans autorisation écrite "
         "expresse de FinSight IA. Le scoring FinSight, la Méthodologie de calcul, les visuels et les "
         "textes analytiques sont la propriété intellectuelle exclusive de FinSight IA. Toute "
         "exploitation commerciale est prohibee. Ce document ne doit pas être utilisé comme base "
         "exclusive pour une décision d'investissement."),
    ]
    for title, text in disclaimers:
        story.append(KeepTogether([
            Paragraph(title, _S_SSEC_S),
            Paragraph(text, _S_DISC_S),
            Spacer(1, 2 * mm),
        ]))
    story.append(rule())
    story.append(Paragraph(
        f"Généré par FinSight IA  |  {D['date_str']}  |  Usage confidentiel — ne pas diffuser",
        _sty("fin", size=6.5, color=GREY_TEXT, align=TA_CENTER)))

    return story


def _build_top_table(story, tickers, sector_name, col_header):
    top_data = [[
        Paragraph("Société", S_TH_L),
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
        roe_str = None
        if roe_v is not None:
            try:
                _rv = float(roe_v)
                roe_str = "N/M" if abs(_rv) > 200 else _pct(_rv, sign=False)
            except (TypeError, ValueError):
                roe_str = None
        # P/E : si valeur absente mais earnings/marge nette negatifs, afficher "neg."
        _pe_v = t.get("pe_ratio")
        if _pe_v is None:
            _nm = t.get("net_margin")
            try:
                _pe_str = "neg." if _nm is not None and float(_nm) < 0 else "\u2014"
            except (TypeError, ValueError):
                _pe_str = "\u2014"
        else:
            _pe_str = _mult(_pe_v)
        top_data.append([
            Paragraph(t.get("company", t.get("ticker", ""))[:32], S_TD_L),
            Paragraph(f"{t.get('score_global', 0)}/100", S_TD_C),
            Paragraph(_pe_str, S_TD_C),
            Paragraph(_mult(t.get("ev_ebitda")), S_TD_C),
            Paragraph(_pct(revg), S_TD_C),
            Paragraph(_pct(t.get("ebitda_margin"), sign=False), S_TD_C),
            Paragraph(_pct(t.get("net_margin"), sign=False), S_TD_C),
            Paragraph(roe_str or "—", S_TD_C),
        ])
    t = _tbl(top_data, [56*mm, 16*mm, 16*mm, 19*mm, 19*mm, 19*mm, 17*mm, 14*mm], header_col=col_header)
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
    # Couleur header : bleu si secteur "growth-friendly" (tech/santé/industrie), navy sinon
    try:
        from core.sector_labels import slug_from_any as _slug
        _is_growth = _slug(sector_name) in {"TECHNOLOGY", "INDUSTRIALS", "HEALTHCARE"}
    except Exception:
        _is_growth = "Technology" in sector_name or "Industrial" in sector_name or "Health" in sector_name
    story.append(_tbl(cat_data,  cols2, header_col=COL_A if _is_growth else NAVY_LIGHT))
    story.append(Spacer(1, 3 * mm))
    story.append(_tbl(risk_data, cols2, header_col=RED))

    conds = content.get("conditions", [])[:4]
    if conds:
        cond_data = [[Paragraph("Type", S_TH_C), Paragraph("Condition d'invalidation", S_TH_L), Paragraph("Horizon", S_TH_C)]]
        for c in conds:
            cond_data.append([Paragraph(c[0], S_TD_C), Paragraph(c[1][:100], S_TD_L), Paragraph(c[2], S_TD_C)])
        story.append(_KT([Spacer(1, 3*mm), _tbl(cond_data, [25*mm, 115*mm, 36*mm])]))


def _build_risques_comparatifs_pdf(story, content_a, sector_a, content_b, sector_b):
    """Risques et catalyseurs en analyse croisée comparative (pas chacun dans son coin)."""
    cats_a  = content_a.get("catalyseurs", [])[:3]
    cats_b  = content_b.get("catalyseurs", [])[:3]
    risks_a = content_a.get("risques", [])[:3]
    risks_b = content_b.get("risques", [])[:3]

    HALF = TABLE_W / 2

    # Catalyseurs côte à côte
    cat_hdr = [
        Paragraph(_xml(f"Catalyseurs — {sector_a[:20]}"), _sty("cth_a", size=8, color=WHITE, bold=True)),
        Paragraph(_xml(f"Catalyseurs — {sector_b[:20]}"), _sty("cth_b", size=8, color=WHITE, bold=True)),
    ]
    cat_rows = [cat_hdr]
    for i in range(max(len(cats_a), len(cats_b))):
        ca = cats_a[i] if i < len(cats_a) else ("", "")
        cb = cats_b[i] if i < len(cats_b) else ("", "")
        ca_txt = f"+ {ca[0]}: {ca[1][:140]}" if ca[0] else "\u2014"
        cb_txt = f"+ {cb[0]}: {cb[1][:140]}" if cb[0] else "\u2014"
        cat_rows.append([
            Paragraph(_xml(ca_txt), S_TD_L),
            Paragraph(_xml(cb_txt), S_TD_L),
        ])
    ct = Table(cat_rows, colWidths=[HALF, HALF])
    ct.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), COL_A),
        ("BACKGROUND",    (1, 0), (1, 0), COL_B),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, ROW_ALT]),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("LINEAFTER",     (0, 0), (0, -1), 0.5, GREY_RULE),
    ]))
    story.append(ct)
    story.append(Spacer(1, 3 * mm))

    # Risques côte à côte
    risk_hdr = [
        Paragraph(_xml(f"Risques — {sector_a[:20]}"), _sty("rth_a", size=8, color=WHITE, bold=True)),
        Paragraph(_xml(f"Risques — {sector_b[:20]}"), _sty("rth_b", size=8, color=WHITE, bold=True)),
    ]
    risk_rows = [risk_hdr]
    for i in range(max(len(risks_a), len(risks_b))):
        ra = risks_a[i] if i < len(risks_a) else ("", "")
        rb = risks_b[i] if i < len(risks_b) else ("", "")
        ra_txt = f"- {ra[0]}: {ra[1][:140]}" if ra[0] else "\u2014"
        rb_txt = f"- {rb[0]}: {rb[1][:140]}" if rb[0] else "\u2014"
        risk_rows.append([
            Paragraph(_xml(ra_txt), _sty("rtd_a", size=8, color=RED, leading=11)),
            Paragraph(_xml(rb_txt), _sty("rtd_b", size=8, color=RED, leading=11)),
        ])
    rt = Table(risk_rows, colWidths=[HALF, HALF])
    rt.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), RED),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, RED_L]),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("LINEAFTER",     (0, 0), (0, -1), 0.5, GREY_RULE),
    ]))
    story.append(rt)
    story.append(Spacer(1, 4 * mm))

    # Analyse croisée des implications — version compacte (1 paragraphe par secteur)
    story.append(Paragraph("Analyse croisée des implications", S_SSEC))
    story.append(Spacer(1, 1 * mm))

    if risks_a:
        _ra_top = risks_a[0]
        _ra_2nd = risks_a[1] if len(risks_a) > 1 else ("", "")
        impl_a = (
            f"<b>{sector_a}</b> — Les deux risques majeurs identifiés "
            f"({_ra_top[0][:40]}, {_ra_2nd[0][:40] if _ra_2nd[0] else 'second axe'}) "
            f"peuvent déclencher une rotation vers {sector_b} en cas de divergence des "
            f"fondamentaux, ou au contraire une contagion si le choc est d'origine macro-systémique."
        )
        story.append(Paragraph(_rich(impl_a), S_BODY))
        story.append(Spacer(1, 1 * mm))

    if risks_b:
        _rb_top = risks_b[0]
        _rb_2nd = risks_b[1] if len(risks_b) > 1 else ("", "")
        impl_b = (
            f"<b>{sector_b}</b> — Symétriquement, "
            f"{_rb_top[0][:40]}{(' et ' + _rb_2nd[0][:40]) if _rb_2nd[0] else ''} "
            f"impactent la pression concurrentielle sur {sector_a} selon le caractère cyclique "
            f"ou défensif du choc — a surveiller comme signal d'arbitrage sectoriel."
        )
        story.append(Paragraph(_rich(impl_b), S_BODY))
        story.append(Spacer(1, 1 * mm))

    # Conditions d'invalidation — tableau + texte LLM rigoureux
    conds_a = content_a.get("conditions", [])[:2]
    conds_b = content_b.get("conditions", [])[:2]
    all_conds = [(sector_a, c) for c in conds_a] + [(sector_b, c) for c in conds_b]
    if all_conds:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph("Conditions d'invalidation", S_SSEC))
        cond_data = [[Paragraph("Secteur", S_TH_C), Paragraph("Type", S_TH_C),
                      Paragraph("Condition", S_TH_L), Paragraph("Horizon", S_TH_C)]]
        for sec_name, c in all_conds:
            cond_data.append([
                Paragraph(sec_name[:14], S_TD_C),
                Paragraph(c[0], S_TD_C),
                Paragraph(c[1][:100], S_TD_L),
                Paragraph(c[2], S_TD_C),
            ])
        story.append(_tbl(cond_data, [30*mm, 22*mm, 98*mm, 26*mm]))
        story.append(Spacer(1, 2 * mm))
        # Texte analytique compact (4 lignes max) — tient sur p7 avec le reste
        invalidation_text = (
            f"<b>Lecture des conditions d'invalidation</b> : ces seuils ne sont pas des points "
            f"de sortie automatiques mais des signaux de re-évaluation systématique. Pour "
            f"{sector_a}, calibrer en combinant compression de marges, révision baissière du "
            f"consensus EPS et rotation négative du momentum 52S. Pour {sector_b}, surveiller les "
            f"indicateurs avancés (PMI, surveys de crédit, guidance corporate) qui précèdent les "
            f"révisions consensus de 1-2 trimestres. <b>Monitoring</b> : revue mensuelle, alertes "
            f"automatiques, réévaluation complète sur 2 trimestres consécutifs de divergence."
        )
        story.append(Paragraph(_rich(invalidation_text), S_BODY))


# ── Entetes / pieds de page ───────────────────────────────────────────────────
def _build_page_header_footer(sector_a, sector_b, universe_label, date_str):
    def on_page(canvas, doc):
        canvas.saveState()
        # Header — bandeau pleine largeur sur TOUTES les pages (y compris cover)
        canvas.setFillColor(NAVY)
        canvas.rect(0, PAGE_H - 14*mm, PAGE_W, 14*mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(MARGIN_L, PAGE_H - 9*mm,
            f"FinSight IA  |  Comparatif sectoriel : {sector_a} vs {sector_b}  |  {universe_label}")
        canvas.setFont("Helvetica", 7.5)
        canvas.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 9*mm,
            f"{date_str}  |  Confidentiel  |  Page {doc.page}")
        # Footer — ligne fine + texte (toutes les pages)
        canvas.setStrokeColor(GREY_MED)
        canvas.setLineWidth(0.15)
        canvas.line(MARGIN_L, MARGIN_B - 2*mm, PAGE_W - MARGIN_R, MARGIN_B - 2*mm)
        canvas.setFillColor(GREY_TEXT)
        canvas.setFont("Helvetica", 6.5)
        canvas.drawString(MARGIN_L, MARGIN_B - 7*mm,
            "FinSight IA v1.0 — Document généré par IA. Ne constitue pas un conseil en investissement.")
        canvas.drawRightString(PAGE_W - MARGIN_R, MARGIN_B - 7*mm,
            "Sources : yfinance · FMP · Finnhub")
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
    language: str = "fr",
    currency: str = "EUR",
) -> None:
    global _CMP_SEC_LANG
    _CMP_SEC_LANG = (language or "fr").lower()[:2]
    if _CMP_SEC_LANG not in {"fr","en","es","de","it","pt"}:
        _CMP_SEC_LANG = "fr"
    D = _prepare(tickers_a, sector_a, universe_a, tickers_b, sector_b, universe_b)
    D["llm"] = _generate_llm_texts(D)
    D["perf_a_52w"], D["perf_b_52w"] = _fetch_price_52w(D["td_a"], D["td_b"])
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
