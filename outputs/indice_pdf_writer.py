"""
indice_pdf_writer.py — FinSight IA
Generateur de rapport PDF d'analyse d'indice boursier.
Interface : IndicePDFWriter.generate(data, output_path) -> str
Double-passe SectionAnchor pour pagination dynamique.
"""

import io, tempfile, os, logging
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Image, KeepTogether
)
from reportlab.platypus.flowables import CondPageBreak
from reportlab.platypus.flowables import Flowable

from outputs.pdf_utils import safe_text as _safe


# ─── FORMAT FR CHIFFRES ──────────────────────────────────────────────────────
# Helpers typo FR : virgule décimale + espace avant « % » / « x » (convention
# FR = « 4,32 % » et « 13,4x »). Évite les `f"{v:.1f}%"` qui produisent du
# format US « 4.3% » non acceptable en rapport institutionnel FR.
def _frp(v, *, sign: bool = False, decimals: int = 1) -> str:
    """Pourcentage format FR : 33,9 % (ou +33,9 % si sign=True)."""
    if v is None:
        return "\u2014"
    fmt = f"{{:+.{decimals}f}}" if sign else f"{{:.{decimals}f}}"
    return fmt.format(v).replace(".", ",") + " %"


def _frx(v, *, decimals: int = 1) -> str:
    """Multiple format FR : 13,4x (pas d'espace avant x, convention FR financière)."""
    if v is None:
        return "\u2014"
    fmt = f"{{:.{decimals}f}}"
    return fmt.format(v).replace(".", ",") + "x"


def _frp_s(v, *, sign: bool = False, decimals: int = 1) -> str:
    """Version safe : accepte strings déjà formattées ou des non-numériques."""
    try:
        return _frp(float(v), sign=sign, decimals=decimals)
    except (TypeError, ValueError):
        return str(v) if v not in (None, "") else "\u2014"


# ─── PALETTE ──────────────────────────────────────────────────────────────────
NAVY       = colors.HexColor('#1B3A6B')
NAVY_LIGHT = colors.HexColor('#2A5298')
SURP_G     = colors.HexColor('#1A7A4A')
SOUS_R     = colors.HexColor('#A82020')
NEUTRE_A   = colors.HexColor('#B06000')
WHITE      = colors.white
BLACK      = colors.HexColor('#1A1A1A')
GREY_LIGHT = colors.HexColor('#F5F7FA')
GREY_MED   = colors.HexColor('#E8ECF0')
GREY_TEXT  = colors.HexColor('#555555')
GREY_RULE  = colors.HexColor('#D0D5DD')
ROW_ALT    = colors.HexColor('#F0F4F8')
ACCENT_BLU = colors.HexColor('#90B4E8')

PAGE_W, PAGE_H = A4
MARGIN_L = 17*mm; MARGIN_R = 17*mm
MARGIN_T = 22*mm; MARGIN_B = 18*mm
TABLE_W  = 170*mm

# ─── STYLES ───────────────────────────────────────────────────────────────────
def _style(name, font='Helvetica', size=9, color=BLACK, leading=13,
           align=TA_LEFT, bold=False, space_before=0, space_after=2):
    return ParagraphStyle(name, fontName='Helvetica-Bold' if bold else font,
        fontSize=size, textColor=color, leading=leading,
        alignment=align, spaceBefore=space_before, spaceAfter=space_after)

S_BODY       = _style('body',   size=8.5, leading=13, color=GREY_TEXT, align=TA_JUSTIFY)
S_SECTION    = _style('sec',    size=12,  leading=16, color=NAVY, bold=True, space_before=8, space_after=2)
S_SUBSECTION = _style('subsec', size=9,   leading=13, color=NAVY, bold=True, space_before=5, space_after=3)
S_DEBATE     = _style('debate', size=8.5, leading=12, color=NAVY_LIGHT, bold=True, space_before=3, space_after=5)
S_NOTE       = _style('note',   size=6.5, leading=9,  color=GREY_TEXT)
S_DISC       = _style('disc',   size=6.5, leading=9,  color=GREY_TEXT, align=TA_JUSTIFY)
S_TH_C  = _style('thc',  size=8, leading=11, color=WHITE, bold=True, align=TA_CENTER)
S_TH_L  = _style('thl',  size=8, leading=11, color=WHITE, bold=True, align=TA_LEFT)
S_TD_L  = _style('tdl',  size=8, leading=11, color=BLACK, align=TA_LEFT)
S_TD_C  = _style('tdc',  size=8, leading=11, color=BLACK, align=TA_CENTER)
S_TD_B  = _style('tdb',  size=8, leading=11, color=BLACK, bold=True, align=TA_LEFT)
S_TD_BC = _style('tdbc', size=8, leading=11, color=BLACK, bold=True, align=TA_CENTER)
S_TD_G  = _style('tdg',  size=8, leading=11, color=SURP_G,  bold=True, align=TA_CENTER)
S_TD_R  = _style('tdr',  size=8, leading=11, color=SOUS_R,  bold=True, align=TA_CENTER)
S_TD_A  = _style('tda',  size=8, leading=11, color=NEUTRE_A, bold=True, align=TA_CENTER)

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def rule(w=TABLE_W, thick=0.5, col=GREY_RULE, sb=4, sa=4):
    return HRFlowable(width=w, thickness=thick, color=col, spaceAfter=sa, spaceBefore=sb)

# ─── i18n helper indice PDF ───────────────────────────────────────────────
_INDICE_CURRENT_LANG: str = "fr"

_INDICE_PDF_LABELS: dict[str, dict[str, str]] = {
    "sommaire":          {"fr": "Sommaire", "en": "Table of contents",
                          "es": "Índice", "de": "Inhalt",
                          "it": "Sommario", "pt": "Sumário"},
    "synthese_macro":    {"fr": "Synthèse Macro & Signal Global",
                          "en": "Macro Synthesis & Global Signal",
                          "es": "Síntesis Macro y Señal Global",
                          "de": "Makro-Synthese & Globales Signal",
                          "it": "Sintesi Macro & Segnale Globale",
                          "pt": "Síntese Macro & Sinal Global"},
    "cartographie":      {"fr": "Cartographie des Secteurs",
                          "en": "Sector Mapping",
                          "es": "Cartografía Sectorial",
                          "de": "Sektor-Kartierung",
                          "it": "Cartografia dei Settori",
                          "pt": "Mapeamento Setorial"},
    "analyse_graphique": {"fr": "Analyse Graphique", "en": "Chart Analysis",
                          "es": "Análisis Gráfico", "de": "Chart-Analyse",
                          "it": "Analisi Grafica", "pt": "Análise Gráfica"},
    "rotation":          {"fr": "Rotation Sectorielle",
                          "en": "Sector Rotation",
                          "es": "Rotación Sectorial", "de": "Sektorrotation",
                          "it": "Rotazione Settoriale", "pt": "Rotação Setorial"},
    "allocation":        {"fr": "Allocation Optimale — Portefeuilles Mean-Variance",
                          "en": "Optimal Allocation — Mean-Variance Portfolios",
                          "es": "Asignación Óptima — Carteras Mean-Variance",
                          "de": "Optimale Allokation — Mean-Variance-Portfolios",
                          "it": "Allocazione Ottimale — Portafogli Mean-Variance",
                          "pt": "Alocação Ótima — Carteiras Mean-Variance"},
    "top3":              {"fr": "Top 3 Secteurs Recommandés",
                          "en": "Top 3 Recommended Sectors",
                          "es": "Top 3 Sectores Recomendados",
                          "de": "Top 3 Empfohlene Sektoren",
                          "it": "Top 3 Settori Raccomandati",
                          "pt": "Top 3 Setores Recomendados"},
    "risques_macro":     {"fr": "Risques Macro & Conditions d'Invalidation",
                          "en": "Macro Risks & Invalidation Conditions",
                          "es": "Riesgos Macro y Condiciones de Invalidación",
                          "de": "Makro-Risiken & Invalidierungsbedingungen",
                          "it": "Rischi Macro & Condizioni di Invalidazione",
                          "pt": "Riscos Macro & Condições de Invalidação"},
    "sentiment_method":  {"fr": "Sentiment Agrégé & Méthodologie",
                          "en": "Aggregated Sentiment & Methodology",
                          "es": "Sentimiento Agregado y Metodología",
                          "de": "Aggregierte Stimmung & Methodik",
                          "it": "Sentiment Aggregato & Metodologia",
                          "pt": "Sentimento Agregado & Metodologia"},
}


def _ilbl(key: str) -> str:
    spec = _INDICE_PDF_LABELS.get(key)
    if not spec:
        return key
    return spec.get(_INDICE_CURRENT_LANG) or spec.get("en") or spec.get("fr") or key


def section_title(text, num):
    return [rule(sb=10, sa=0), Paragraph(f"{num}. {text}", S_SECTION), rule(sb=2, sa=8)]

def debate_q(text): return Paragraph(f">  {text}", S_DEBATE)  # \u25b6 non rendu dans Helvetica
def src(text):      return Paragraph(f"Source : {text}", S_NOTE)


def tbl(data, cw, row_heights=None, compact=False):
    assert abs(sum(cw) - TABLE_W) < 0.5, (
        f"Somme colonnes = {sum(cw)/mm:.1f}mm != 170mm — {[c/mm for c in cw]}")
    pad = 3 if compact else 5
    t = Table(data, colWidths=cw, rowHeights=row_heights)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0),  NAVY),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [WHITE, ROW_ALT]),
        ('FONTNAME',      (0,0), (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,-1), 8),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0), (-1,-1), 3 if compact else 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3 if compact else 4),
        ('LEFTPADDING',   (0,0), (-1,-1), pad),
        ('RIGHTPADDING',  (0,0), (-1,-1), pad),
        ('LINEBELOW',     (0,0), (-1,0),  0.5, NAVY_LIGHT),
        ('LINEBELOW',     (0,-1),(-1,-1), 0.5, GREY_RULE),
        ('GRID',          (0,1), (-1,-1), 0.3, GREY_MED),
    ]))
    return t

def sig_s(signal):
    s = str(signal)
    return S_TD_G if "Surp" in s else (S_TD_R if "Sous" in s else S_TD_A)

def sig_hex(signal):
    s = str(signal)
    return '#1A7A4A' if "Surp" in s else ('#A82020' if "Sous" in s else '#B06000')


_log_fred = logging.getLogger(__name__)
log = _log_fred  # Alias pour compatibilité avec log.debug utilisé dans le module


def _build_fred_macro_table():
    """Construit un bloc ReportLab avec les indicateurs macroéconomiques FRED.

    Retourne une liste de flowables (Paragraph + Table + source),
    ou une liste vide si FRED est indisponible.
    """
    try:
        from data.sources.fred_source import fetch_macro_context
        macro = fetch_macro_context()
        if not macro:
            return []

        # ── Définition des lignes : (clé, label FR, format, interprétation) ──
        def _interp_fed(v):
            if v is None: return "—"
            if v >= 5.0:  return "Politique restrictive"
            if v >= 3.0:  return "Politique neutre-haute"
            if v >= 1.5:  return "Politique accommodante"
            return "Politique très accommodante"

        def _interp_10y(v):
            if v is None: return "—"
            if v >= 5.0:  return "Taux élevés — pression sur valorisations"
            if v >= 3.5:  return "Taux modérément élevés"
            if v >= 2.0:  return "Taux neutres"
            return "Taux bas — favorable aux actions"

        def _interp_curve(v):
            if v is None: return "—"
            if v < -0.5:  return "Courbe inversée — signal récessif"
            if v < 0:     return "Courbe plate à inversée — prudence"
            if v < 1.0:   return "Courbe légèrement positive"
            return "Courbe pentue — expansion"

        def _interp_cpi(v):
            if v is None: return "—"
            if v >= 5.0:  return "Inflation élevée"
            if v >= 3.0:  return "Inflation au-dessus de la cible"
            if v >= 1.5:  return "Inflation proche de la cible"
            return "Inflation faible — risque déflationniste"

        def _interp_unemp(v):
            if v is None: return "—"
            if v >= 6.0:  return "Marché de l'emploi dégradé"
            if v >= 4.5:  return "Emploi en ralentissement"
            if v >= 3.5:  return "Plein emploi"
            return "Marché de l'emploi très tendu"

        def _interp_vix(v):
            if v is None: return "—"
            if v >= 30:   return "Forte volatilité — stress de marché"
            if v >= 20:   return "Volatilité élevée — prudence"
            if v >= 15:   return "Volatilité normale"
            return "Complaisance — volatilité faible"

        def _interp_spread(v):
            if v is None: return "—"
            if v >= 3.0:  return "Stress crédit élevé"
            if v >= 2.0:  return "Spread tendu — vigilance"
            if v >= 1.0:  return "Spread normal"
            return "Spread comprimé — appétit pour le risque"

        rows_def = [
            ("fed_funds_rate",    "Fed Funds Rate",       "fed",    _interp_fed),
            ("treasury_10y",      "Treasury 10 ans",      "pct",    _interp_10y),
            ("yield_curve_spread","Yield Curve (10Y-2Y)",  "spread", _interp_curve),
            ("cpi_yoy",           "CPI YoY",              "pct",    _interp_cpi),
            ("unemployment",      "Chômage",              "pct",    _interp_unemp),
            ("vix",               "VIX",                  "num",    _interp_vix),
            ("credit_spread_baa", "Spread Crédit BAA",    "pct",    _interp_spread),
        ]

        # ── Construction des données du tableau ──
        header = [
            Paragraph("Indicateur", S_TH_L),
            Paragraph("Valeur", S_TH_C),
            Paragraph("Interprétation", S_TH_L),
        ]
        table_rows = []
        for key, label, fmt, interp_fn in rows_def:
            val = macro.get(key)
            if val is None:
                continue
            if fmt == "pct":
                val_str = f"{val:.2f} %"
            elif fmt == "spread":
                val_str = f"{val:+.2f} %"
            elif fmt == "fed":
                val_str = f"{val:.2f} %"
            elif fmt == "num":
                val_str = f"{val:.1f}"
            else:
                val_str = str(val)
            interp = interp_fn(val)
            table_rows.append([
                Paragraph(label, S_TD_B),
                Paragraph(val_str, S_TD_C),
                Paragraph(interp, S_TD_L),
            ])

        if not table_rows:
            return []

        elems = [
            Spacer(1, 3*mm),
            Paragraph("Indicateurs macroéconomiques — FRED", S_SUBSECTION),
            Spacer(1, 1*mm),
            tbl([header] + table_rows, cw=[42*mm, 30*mm, 98*mm], compact=True),
            src("Federal Reserve Economic Data (FRED) — St. Louis Fed. "
                "Dernières observations disponibles."),
            Spacer(1, 3*mm),
        ]
        return elems

    except Exception as e:
        _log_fred.warning(f"[fred] Table FRED indisponible dans le PDF indice: {e}")
        return []


# ─── GRAPHIQUES ───────────────────────────────────────────────────────────────
def make_indice_perf_chart(data):
    ph = data.get("perf_history")
    if ph and ph.get("dates"):
        # Données réelles yfinance
        dates  = ph["dates"]
        i_perf = ph["indice"]
        bonds  = ph["bonds"]
        gold   = ph["gold"]
        # Afficher ~12 ticks répartis sur l'axe X
        n = len(dates)
        step = max(1, n // 12)
        x = np.arange(n)
        tick_idx = list(range(0, n, step))
        def _short_date(s):
            """Extrait YY/MM depuis une date ISO 'YYYY-MM-DD' — robuste aux formats alternatifs."""
            try:
                parts = str(s).split("-")
                if len(parts) >= 3:
                    return f"{parts[0][2:]}/{parts[1]}"
                return str(s)[:5]
            except Exception:
                return str(s)[:5]
        tick_lbl = [_short_date(dates[i]) for i in tick_idx]
        label_start = ph.get("label_start", str(dates[0])[:7])
        indice_name = ph.get("indice_name", data["indice"])
    else:
        # Fallback neutre (aucune donnée dispo) : droite à 100
        n = 13
        x = np.arange(n)
        i_perf = [100.0] * n
        bonds  = [100.0] * n
        gold   = [100.0] * n
        tick_idx = list(range(0, n, max(1, n // 6)))
        tick_lbl = [f"M{i+1}" for i in tick_idx]
        label_start = "N-12M"
        indice_name = data["indice"]

    # Tailles police agrandies (audit Baptiste S&P 500 p5 2026-04-14)
    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    ax.plot(x, i_perf, color='#1B3A6B', linewidth=2.4, label=indice_name)
    ax.plot(x, bonds,  color='#A0A0A0', linewidth=1.4, linestyle='--', label='US 10Y Bond')
    ax.plot(x, gold,   color='#B06000', linewidth=1.4, linestyle=':', label='Gold')
    ax.fill_between(x, i_perf, 100, where=[v > 100 for v in i_perf], alpha=0.08, color='#1B3A6B')
    ax.set_xticks([x[i] for i in tick_idx])
    ax.set_xticklabels(tick_lbl, fontsize=12, color='#555')
    ax.yaxis.set_tick_params(labelsize=13)
    ax.tick_params(length=0)
    for sp in ['top','right']: ax.spines[sp].set_visible(False)
    ax.spines['left'].set_color('#D0D5DD'); ax.spines['bottom'].set_color('#D0D5DD')
    ax.set_facecolor('white'); fig.patch.set_facecolor('white')
    ax.grid(axis='y', alpha=0.15, color='#D0D5DD', linewidth=0.5)
    ax.legend(fontsize=13, loc='upper left', frameon=False)
    ax.set_title(f'Performance comparée assets - base 100, {label_start}',
                 fontsize=16, color='#1B3A6B', fontweight='bold', pad=10)
    plt.tight_layout(pad=0.4)
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=160, bbox_inches='tight')
    plt.close(fig); buf.seek(0); return buf


def make_sector_weights_chart(data):
    secteurs = data["secteurs"]
    # Traduction FR systematique des noms secteurs pour les axes des charts
    noms  = [_abbrev_pdf(s[0]) for s in secteurs]
    # Poids proportionnels au nombre de sociétés par secteur
    total_nb = sum(s[1] for s in secteurs) or 1
    poids_idx = [round(100 * s[1] / total_nb, 1) for s in secteurs]
    sigs = [s[3] for s in secteurs]
    bar_cols = [sig_hex(s) for s in sigs]
    y = np.arange(len(noms))
    fig, ax = plt.subplots(figsize=(7.2, max(5.8, len(noms) * 0.52 + 2.2)))
    bars = ax.barh(y, poids_idx, color=bar_cols, alpha=0.85, height=0.62,
                   edgecolor='white', linewidth=0.6)
    x_max = max(poids_idx) * 1.35 if poids_idx else 30
    for i, (bar, val) in enumerate(zip(bars, poids_idx)):
        ax.text(val + x_max*0.015, i, f"{val}%", va='center', fontsize=13, color='#333', fontweight='bold')
    ax.set_yticks(y); ax.set_yticklabels(noms, fontsize=13, color='#333')
    ax.set_xlabel("Repartition par nombre de sociétés (%)", fontsize=13, color='#555', labelpad=8)
    ax.tick_params(axis='x', labelsize=12)
    ax.set_xlim(0, x_max)
    moy = sum(poids_idx)/len(poids_idx)
    ax.axvline(x=moy, color='#D0D5DD', linewidth=0.8, linestyle='--', alpha=0.8)
    ax.text(moy + x_max*0.01, len(noms)-0.6, 'Moy.', fontsize=11, color='#999', style='italic')
    for sp in ['top','right']: ax.spines[sp].set_visible(False)
    ax.spines['left'].set_color('#D0D5DD'); ax.spines['bottom'].set_color('#D0D5DD')
    ax.set_facecolor('white'); fig.patch.set_facecolor('white')
    ax.tick_params(length=0)
    patches = [mpatches.Patch(color='#1A7A4A', label='Surpond\u00e9rer'),
               mpatches.Patch(color='#B06000', label='Neutre'),
               mpatches.Patch(color='#A82020', label='Sous-pond\u00e9rer')]
    ax.legend(handles=patches, fontsize=14, loc='upper center',
              bbox_to_anchor=(0.5, -0.16), frameon=False, ncol=3)
    ax.set_title(f"Répartition sectorielle — {data['indice']} (nb sociétés)",
                 fontsize=17, color='#1B3A6B', fontweight='bold', pad=14)
    plt.tight_layout(pad=0.6)
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=160, bbox_inches='tight')
    plt.close(fig); buf.seek(0); return buf


def make_scatter_sectoriel(data):
    secteurs = data["secteurs"]
    if len(secteurs) <= 1:
        return None   # pas assez de points pour un scatter utile
    noms_abr = [_abbrev_pdf(s[0])[:14] for s in secteurs]
    def _safe_float(val, fallback=0.0):
        try:
            v = float(str(val).replace('x','').replace('*','').replace('%','').replace('+','').replace(',','.').replace('\u2014','').strip() or '0')
            return v
        except (ValueError, TypeError):
            return fallback

    ev_raw = [_safe_float(s[4]) for s in secteurs]
    crois  = [_safe_float(s[6]) for s in secteurs]
    sigs   = [s[3] for s in secteurs]
    cols   = [sig_hex(s) for s in sigs]

    # Fallback Mg.EBITDA quand EV/EBITDA absent (indices EU)
    use_mg = not any(v > 0 for v in ev_raw)
    if use_mg:
        mg_raw = [_safe_float(s[5]) for s in secteurs]
        if not any(v > 0 for v in mg_raw):
            return None  # aucune donnee disponible
        y_vals = mg_raw
        y_label = 'Marge EBITDA (%)'
        y_med_label = 'Med. Mg.EBITDA'
        chart_title = f"Mg. EBITDA vs Croissance BPA - Secteurs {data['indice']}"
    else:
        y_vals = ev_raw
        y_label = 'EV / EBITDA Médian (x)'
        y_med_label = 'Med. EV/EBITDA'
        chart_title = f"EV/EBITDA vs Croissance BPA - Secteurs {data['indice']}"

    fig, ax = plt.subplots(figsize=(9.0, 5.2))
    texts = []
    for nom, x, y, col in zip(noms_abr, crois, y_vals, cols):
        ax.scatter(x, y, color=col, s=180, zorder=4, alpha=0.88,
                   edgecolors='white', linewidth=0.8)
        texts.append(ax.text(x, y, nom, fontsize=8.5, color=col, fontweight='bold'))
    try:
        from adjustText import adjust_text
        adjust_text(texts, x=crois, y=y_vals, ax=ax,
                    arrowprops=dict(arrowstyle='-', color='#aaa', lw=0.5, alpha=0.6),
                    expand_points=(1.4, 1.4), force_text=(0.5, 0.8))
    except ImportError:
        pass
    med_y = float(np.median([v for v in y_vals if v > 0])) if any(v > 0 for v in y_vals) else 0
    med_cr = float(np.median(crois))
    ax.axhline(y=med_y, color='#D0D5DD', linewidth=0.9, linestyle='--', alpha=0.8)
    ax.axvline(x=med_cr, color='#D0D5DD', linewidth=0.9, linestyle='--', alpha=0.8)
    _x_ann = min(crois) + 0.2 if crois else 0
    _unit = '%' if use_mg else 'x'
    ax.text(_x_ann, med_y * 1.02 + 0.5,
            f'{y_med_label} ({med_y:.1f}{_unit})', fontsize=9, color='#999', style='italic')
    ax.set_xlabel('Croissance BPA médiane (%)', fontsize=11, color='#555')
    ax.set_ylabel(y_label, fontsize=11, color='#555')
    for sp in ['top','right']: ax.spines[sp].set_visible(False)
    ax.spines['left'].set_color('#D0D5DD'); ax.spines['bottom'].set_color('#D0D5DD')
    ax.set_facecolor('white'); fig.patch.set_facecolor('white')
    ax.tick_params(labelsize=10, length=0)
    ax.grid(alpha=0.12, color='#D0D5DD', linewidth=0.5)
    patches = [mpatches.Patch(color='#1A7A4A', label='Surpond\u00e9rer'),
               mpatches.Patch(color='#B06000', label='Neutre'),
               mpatches.Patch(color='#A82020', label='Sous-pond\u00e9rer')]
    ax.legend(handles=patches, fontsize=12, loc='upper center',
              bbox_to_anchor=(0.5, -0.13), frameon=False, ncol=3)
    ax.set_title(chart_title, fontsize=14, color='#1B3A6B', fontweight='bold', pad=12)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=160, bbox_inches='tight')
    plt.close(fig); buf.seek(0); return buf


def _abbrev_pdf(name: str) -> str:
    """Retourne l'abreviation FR courte du secteur (pour barres de scores PDF).

    Utilise core/sector_labels pour normaliser depuis n'importe quel format.
    """
    if not name:
        return ""
    try:
        from core.sector_labels import slug_from_any
    except ImportError:
        return str(name)
    slug = slug_from_any(name)
    if slug is None:
        return str(name)
    SHORT_FR_PDF = {
        "TECHNOLOGY":       "Technologie",
        "HEALTHCARE":       "Santé",
        "FINANCIALS":       "Finance",
        "CONSUMERCYCLICAL": "Conso. Cycl.",
        "CONSUMERDEFENSIVE":"Conso. Déf.",
        "ENERGY":           "Énergie",
        "INDUSTRIALS":      "Industrie",
        "MATERIALS":        "Matériaux",
        "REALESTATE":       "Immobilier",
        "UTILITIES":        "Serv. Publ.",
        "COMMUNICATION":    "Télécoms",
    }
    return SHORT_FR_PDF.get(slug, str(name))

def make_score_bars(data):
    secteurs = data["secteurs"]
    noms   = [s[0] for s in secteurs]
    scores = [float(s[2]) for s in secteurs]
    sigs   = [s[3] for s in secteurs]
    order  = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    noms_s   = [_abbrev_pdf(noms[i]) for i in order]
    scores_s = [scores[i] for i in order]
    cols_s   = [sig_hex(sigs[i]) for i in order]
    y = np.arange(len(noms_s))
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    bars = ax.barh(y, scores_s, color=cols_s, alpha=0.85, height=0.62,
                   edgecolor='white', linewidth=0.5)
    for i, (bar, val) in enumerate(zip(bars, scores_s)):
        ax.text(val + 0.8, i, str(int(val)), va='center',
                fontsize=10, color='#333', fontweight='bold')
    ax.axvline(x=50, color='#B06000', linewidth=1.2, linestyle='--', alpha=0.7, zorder=5)
    ax.text(51, len(noms_s)-0.4, 'Seuil Neutre (50)', fontsize=9, color='#B06000', style='italic')
    ax.set_yticks(y); ax.set_yticklabels(noms_s, fontsize=11, color='#333')
    ax.set_xlim(0, 118)
    ax.set_xlabel('Score composite (0-100)', fontsize=11, color='#555')
    ax.grid(axis='x', alpha=0.12, color='#D0D5DD', linewidth=0.5)
    for sp in ['top','right']: ax.spines[sp].set_visible(False)
    ax.spines['left'].set_color('#D0D5DD'); ax.spines['bottom'].set_color('#D0D5DD')
    ax.set_facecolor('white'); fig.patch.set_facecolor('white')
    ax.tick_params(labelsize=11, length=0)
    ax.set_title(f"Score composite - Secteurs {data['indice']} (tri\u00e9 par score d\u00e9croissant)",
                 fontsize=14, color='#1B3A6B', fontweight='bold', pad=10)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=160, bbox_inches='tight')
    plt.close(fig); buf.seek(0); return buf


def make_top3_donut(data):
    """Donut complet : tous les secteurs de l'indice avec leurs poids réels."""
    secteurs_all = data["secteurs"]
    total_nb = sum(s[1] for s in secteurs_all) or 1
    # Trier par poids décroissant
    sect_sorted = sorted(secteurs_all, key=lambda s: s[1], reverse=True)
    # Noms secteurs traduits en FR pour le donut et la legende
    noms = [_abbrev_pdf(s[0]) for s in sect_sorted]
    poids = [round(100.0 * s[1] / total_nb, 1) for s in sect_sorted]
    labels = [f"{n} ({p:.0f}%)" for n, p in zip(noms, poids)]
    # Palette étendue pour tous les secteurs
    _PALETTE = ['#1B3A6B', '#2A5298', '#5580B8', '#1A7A4A', '#C9A227',
                '#A82020', '#B06000', '#6B4C9A', '#2E8B57', '#CD853F',
                '#708090', '#BC8F8F', '#4682B4', '#D2691E', '#8FBC8F']
    palette = (_PALETTE * 3)[:len(noms)]
    explode = [0.03 if i < 3 else 0 for i in range(len(noms))]
    # Tailles agrandies (audit Baptiste S&P 500 p11 2026-04-14)
    fig, ax = plt.subplots(figsize=(7.2, 7.8))
    wedges, _ = ax.pie(poids, labels=None, autopct=None,
                       colors=palette, explode=explode,
                       startangle=90, wedgeprops=dict(linewidth=1.0, edgecolor='white'))
    centre = plt.Circle((0, 0), 0.35, color='white')
    ax.add_patch(centre)
    n_sect = len(noms)
    ax.text(0,  0.08, f"{n_sect}", ha='center', va='center', fontsize=22, fontweight='bold', color='#1B3A6B')
    ax.text(0, -0.12, "secteurs", ha='center', va='center', fontsize=12, color='#555555')
    ncol = 2 if n_sect <= 8 else 3
    ax.legend(wedges, labels, loc='lower center', bbox_to_anchor=(0.5, -0.30),
              ncol=ncol, fontsize=13, frameon=False, handlelength=1.6, columnspacing=1.4)
    ax.set_title("Répartition sectorielle de l'indice",
                 fontsize=16, color='#1B3A6B', fontweight='bold', pad=10)
    fig.patch.set_facecolor('white')
    plt.tight_layout(pad=0.6)
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=180, bbox_inches='tight')
    plt.close(fig); buf.seek(0); return buf


def make_allocation_chart(data):
    """Bar chart groupe : 3 portefeuilles optimaux (min-var, tangency, ERC) x 11 secteurs."""
    opt = data.get("optimal_portfolios", {})
    if not opt or not opt.get("sectors"):
        return None
    sectors = opt["sectors"]
    w_mv  = opt["min_var"]["weights"]
    w_tg  = opt["tangency"]["weights"]
    w_erc = opt["erc"]["weights"]
    n     = len(sectors)
    abbrevs = [_abbrev_pdf(s)[:12] for s in sectors]
    x     = np.arange(n)
    width = 0.25
    eq_w  = round(100 / n, 1)
    fig, ax = plt.subplots(figsize=(11.0, 5.4))
    ax.bar(x - width, w_mv,  width, label='Min-Variance', color='#1B3A6B', alpha=0.85, edgecolor='white')
    ax.bar(x,         w_tg,  width, label='Tangency (Max Sharpe)', color='#1A7A4A', alpha=0.85, edgecolor='white')
    ax.bar(x + width, w_erc, width, label='Equal Risk Contrib.', color='#B06000', alpha=0.85, edgecolor='white')
    ax.axhline(y=eq_w, color='#A82020', linewidth=1.0, linestyle='--', alpha=0.7, zorder=5)
    ax.text(n - 0.4, eq_w + 0.3, f'Egal ({_frp(eq_w)})', fontsize=10, color='#A82020', style='italic')
    ax.set_xticks(x)
    ax.set_xticklabels(abbrevs, rotation=30, ha='right', fontsize=11)
    ax.set_ylabel("Poids (%)", fontsize=12, color='#555', labelpad=8)
    ax.tick_params(axis='y', labelsize=11)
    ax.set_ylim(0, max(max(w_mv), max(w_tg), max(w_erc)) * 1.3)
    ax.legend(fontsize=12, loc='upper left', frameon=False, ncol=3)
    for sp in ['top','right']: ax.spines[sp].set_visible(False)
    ax.spines['left'].set_color('#D0D5DD'); ax.spines['bottom'].set_color('#D0D5DD')
    ax.set_facecolor('white'); fig.patch.set_facecolor('white')
    ax.tick_params(length=0)
    ax.grid(axis='y', alpha=0.10, color='#D0D5DD', linewidth=0.5)
    ax.set_title("Allocation optimale — Min-Variance, Tangency & Equal Risk Contribution",
                 fontsize=15, color='#1B3A6B', fontweight='bold', pad=12)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=160, bbox_inches='tight')
    plt.close(fig); buf.seek(0); return buf


def make_attribution_chart(data):
    """Bar chart horizontal : contribution sectorielle au return indice 12 mois."""
    contrib = data.get("sector_contribution", [])
    if not contrib:
        return None
    # Traduction FR des noms secteurs (audit Baptiste S&P 500 p6 2026-04-14)
    noms = [_abbrev_pdf(c[0]) for c in contrib]
    vals = [c[1] for c in contrib]   # contribution en points de %
    rets = [c[2] for c in contrib]   # return 1Y brut
    cols = ['#1A7A4A' if v >= 0 else '#A82020' for v in vals]
    fig, ax = plt.subplots(figsize=(9.0, 5.2))
    y = np.arange(len(noms))
    ax.barh(y, vals, color=cols, alpha=0.85, height=0.60,
            edgecolor='white', linewidth=0.5)
    x_range = max(abs(min(vals)), abs(max(vals))) * 1.0 if vals else 1.0
    x_pad   = x_range * 0.08
    for i, (val, ret) in enumerate(zip(vals, rets)):
        label = f"{val:+.1f}pp  ({_frp(ret, sign=True)})".replace(".", ",", 1)
        ax.text(val + x_pad if val >= 0 else val - x_pad, i,
                label, va='center', fontsize=10, color='#333',
                fontweight='bold', ha='left' if val >= 0 else 'right')
    ax.axvline(x=0, color='#888', linewidth=0.8, linestyle='-')
    ax.set_yticks(y); ax.set_yticklabels(noms, fontsize=11, color='#333')
    ax.set_xlabel("Contribution au return indice (points de %)", fontsize=11, color='#555')
    x_abs = x_range + 3 * x_pad
    ax.set_xlim(-x_abs, x_abs)
    for sp in ['top','right']: ax.spines[sp].set_visible(False)
    ax.spines['left'].set_color('#D0D5DD'); ax.spines['bottom'].set_color('#D0D5DD')
    ax.set_facecolor('white'); fig.patch.set_facecolor('white')
    ax.tick_params(length=0)
    ax.grid(axis='x', alpha=0.10, color='#D0D5DD', linewidth=0.5)
    ax.set_title("Attribution sectorielle — Contribution au return indice 12 mois",
                 fontsize=16, color='#1B3A6B', fontweight='bold', pad=10)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=160, bbox_inches='tight')
    plt.close(fig); buf.seek(0); return buf


def make_correlation_heatmap(data):
    """Heatmap 11x11 des correlations sectorielle (rendements journaliers 52S)."""
    corr_data = data.get("correlation_matrix", {})
    if not corr_data or not corr_data.get("sectors"):
        return None
    sectors = corr_data["sectors"]
    matrix  = np.array(corr_data["matrix"], dtype=float)
    n = len(sectors)
    if n < 3:
        return None
    abbrevs = [_abbrev_pdf(s)[:13] for s in sectors]
    # Colormap divergente : rouge (-1) → blanc (0) → navy (+1)
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list(
        'fs_corr', ['#A82020', '#F5F7FA', '#1B3A6B'], N=256)
    fig, ax = plt.subplots(figsize=(9.0, 7.2))
    im = ax.imshow(matrix, cmap=cmap, vmin=-1, vmax=1, aspect='auto')
    fsize = 7.0 if n > 8 else 8.5
    for i in range(n):
        for j in range(n):
            val  = matrix[i, j]
            tcol = 'white' if abs(val) > 0.65 else '#333'
            ax.text(j, i, f"{val:.2f}", ha='center', va='center',
                    fontsize=fsize, color=tcol)
    ax.set_xticks(range(n)); ax.set_xticklabels(abbrevs, rotation=35,
                                                 ha='right', fontsize=8)
    ax.set_yticks(range(n)); ax.set_yticklabels(abbrevs, fontsize=8)
    ax.tick_params(length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.03)
    cb.ax.tick_params(labelsize=7.5)
    cb.set_label("Coefficient de correlation", fontsize=8, color='#555')
    ax.set_title(
        "Matrice de correlation sectorielle — Rendements journaliers 52 semaines",
        fontsize=11, color='#1B3A6B', fontweight='bold', pad=10)
    ax.set_facecolor('white'); fig.patch.set_facecolor('white')
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=160, bbox_inches='tight')
    plt.close(fig); buf.seek(0); return buf


# ─── CANVAS ───────────────────────────────────────────────────────────────────
def _cover_page(c, doc, data):
    w, h = A4; cx = w / 2
    c.setFillColor(WHITE); c.rect(0, 0, w, h, fill=1, stroke=0)

    # Bande navy top
    c.setFillColor(NAVY); c.rect(0, h - 18*mm, w, 18*mm, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont('Helvetica-Bold', 13)
    c.drawCentredString(cx, h - 8*mm, "FinSight IA")
    c.setFillColor(colors.HexColor('#90B4E8')); c.setFont('Helvetica', 7.5)
    c.drawCentredString(cx, h - 14*mm, "Plateforme d'Analyse Financi\u00e8re Institutionnelle")
    c.setStrokeColor(GREY_RULE); c.setLineWidth(0.5)
    c.line(MARGIN_L, h - 20*mm, w - MARGIN_R, h - 20*mm)

    # Surtitre + titre
    c.setFillColor(GREY_TEXT); c.setFont('Helvetica', 8.5)
    c.drawCentredString(cx, h * 0.810, "ANALYSE D'INDICE")
    c.setFillColor(NAVY); c.setFont('Helvetica-Bold', 30)
    c.drawCentredString(cx, h * 0.768, data["indice"])
    c.setFillColor(GREY_TEXT); c.setFont('Helvetica', 10)
    c.drawCentredString(cx, h * 0.735, "Allocation sectorielle — Vue macro institutionnelle")
    c.setStrokeColor(GREY_RULE); c.setLineWidth(0.4)
    c.line(MARGIN_L + 20*mm, h * 0.720, w - MARGIN_R - 20*mm, h * 0.720)

    # Signal global
    sig     = data["signal_global"]
    sig_col = colors.HexColor(sig_hex(sig))
    box_w, box_h_b = 80*mm, 14*mm
    bx = cx - box_w / 2; by = h * 0.666
    c.setFillColor(sig_col)
    c.roundRect(bx, by, box_w, box_h_b, 2, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(cx, by + box_h_b / 2 + 1.5*mm, f"Signal global : {sig}")
    c.setFont('Helvetica', 8)
    c.drawCentredString(cx, by + box_h_b / 2 - 3*mm, f"Conviction {data['conviction_pct']} %")

    # 5 metriques — tolère les deux conventions de nommage
    _nb_soc = data.get("nb_societes") or data.get("nb_societes", "\u2014")
    metrics = [
        ("Secteurs analys\u00e9s",  str(data.get("nb_secteurs", "\u2014"))),
        ("Soci\u00e9t\u00e9s couvertes", str(_nb_soc)),
        ("Cours indice",       data.get("cours", "\u2014")),
        ("Variation YTD",      data.get("variation_ytd", "\u2014")),
        ("P/E Forward",        data.get("pe_forward", "\u2014")),
    ]
    col_span = (w - MARGIN_L - MARGIN_R) / 5
    my_lbl = h * 0.618; my_val = h * 0.600
    for i, (lbl, val) in enumerate(metrics):
        mx = MARGIN_L + col_span * i + col_span / 2
        c.setFillColor(GREY_TEXT); c.setFont('Helvetica', 7)
        c.drawCentredString(mx, my_lbl, lbl)
        c.setFillColor(NAVY); c.setFont('Helvetica-Bold', 9)
        c.drawCentredString(mx, my_val, val)

    c.setStrokeColor(GREY_RULE); c.setLineWidth(0.4)
    c.line(MARGIN_L, h * 0.585, w - MARGIN_R, h * 0.585)

    # Tagline
    c.setFillColor(GREY_TEXT); c.setFont('Helvetica', 7.5)
    c.drawCentredString(cx, h * 0.558, f"Rapport d'analyse confidentiel — {data['date_analyse']}")
    c.setFont('Helvetica', 7)
    c.drawCentredString(cx, h * 0.539,
        "Donn\u00e9es : yfinance \u00b7 FMP \u00b7 Finnhub \u00b7 FinBERT  |  Horizon d'allocation : 12 mois")

    # Footer navy
    c.setFillColor(NAVY); c.rect(0, 0, w, 18*mm, fill=1, stroke=0)
    c.setFillColor(colors.HexColor('#90B4E8')); c.setFont('Helvetica', 6.5)
    c.drawCentredString(cx, 11*mm, "CONFIDENTIEL — Usage restreint")
    c.drawCentredString(cx, 6*mm,
        "G\u00e9n\u00e9r\u00e9 par FinSight IA v1.0. Ne constitue pas un conseil en investissement au sens MiFID II.")


def _content_header(c, doc, data):
    w, h = A4
    c.setFillColor(NAVY); c.rect(0, h - 14*mm, w, 14*mm, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont('Helvetica-Bold', 8)
    c.drawString(MARGIN_L, h - 9*mm,
                 f"FinSight IA  \xb7  {data['indice']} ({data['code']})  \xb7  Analyse d'Indice")
    c.setFont('Helvetica', 7.5)
    c.drawRightString(w - MARGIN_R, h - 9*mm,
                      f"{data['date_analyse']}  \xb7  Confidentiel  \xb7  Page {doc.page}")
    c.setStrokeColor(colors.HexColor('#E8ECF0')); c.setLineWidth(0.15)
    c.line(MARGIN_L, MARGIN_B - 2*mm, w - MARGIN_R, MARGIN_B - 2*mm)
    c.setFillColor(GREY_TEXT); c.setFont('Helvetica', 6.5)
    c.drawString(MARGIN_L, MARGIN_B - 7*mm,
                 "FinSight IA v1.0 — Ne constitue pas un conseil en investissement.")
    c.drawRightString(w - MARGIN_R, MARGIN_B - 7*mm,
                      "Sources : yfinance \xb7 FMP \xb7 Finnhub \xb7 FinBERT")


# ─── PAGINATION DYNAMIQUE ─────────────────────────────────────────────────────
class SectionAnchor(Flowable):
    def __init__(self, key, registry):
        super().__init__()
        self.key = key; self.registry = registry
        self.width = 0; self.height = 0

    def draw(self):
        self.registry[self.key] = self.canv.getPageNumber()

    def wrap(self, aw, ah): return 0, 0


# ─── SECTIONS ─────────────────────────────────────────────────────────────────
def _build_sommaire(data, page_nums=None):
    if page_nums is None: page_nums = {}
    S_SUB = _style("subgrey", size=7, leading=10, color=GREY_TEXT)
    def pnum(k): return Paragraph(str(page_nums.get(k, "—")), S_TD_C)

    indice_rl = data["indice"].replace("&", "&amp;")
    sections = [
        ("1.", f"Synth\u00e8se Macro &amp; Signal Global",    "Synthèse",
         f"  Signal global \xb7 Conviction \xb7 Catalyseurs \xb7 Risques macro"),
        ("2.", "Cartographie des Secteurs",                   "carto",
         f"  Tableau comparatif {data.get('nb_secteurs','?')} secteur(s) \xb7 Score \xb7 EV/EBITDA \xb7 Attribution \xb7 Breadth"),
        ("3.", "Analyse Graphique",                           "graphiques",
         "  Scatter EV/EBITDA vs croissance \xb7 Scores par secteur \xb7 Matrice de correlation"),
        ("4.", "Rotation Sectorielle",                        "rotation",
         "  Phase du cycle \xb7 Sensibilit\u00e9 taux/PIB \xb7 Signal de rotation"),
        ("5.", "Allocation Optimale",                         "allocation",
         "  Min-Variance \xb7 Tangency (Max Sharpe) \xb7 Equal Risk Contribution \xb7 Poids cibles"),
        ("6.", "Top 3 Secteurs Recommand\u00e9s",             "top3",
         "  D\u00e9tail signal \xb7 Soci\u00e9t\u00e9s représentatives \xb7 Catalyseurs"),
        ("7.", "Risques Macro &amp; Conditions d'Invalidation", "risques",
         "  Cartographie risques \xb7 Probabilit\u00e9s \xb7 Horizons"),
        ("8.", "Sentiment Agr\u00e9g\u00e9 &amp; M\u00e9thodologie", "sentiment",
         "  FinBERT indice \xb7 Distribution par secteur \xb7 Sources"),
    ]
    rows = []
    for num, titre, key, sub in sections:
        rows.append([Paragraph(num, S_TD_BC), Paragraph(titre, S_TD_B), pnum(key)])
        rows.append([Paragraph("", S_TD_C), Paragraph(sub, S_SUB), Paragraph("", S_TD_C)])

    header = [Paragraph("N\xb0", S_TH_C), Paragraph("Section", S_TH_L), Paragraph("Page", S_TH_C)]
    t = tbl([header] + rows, cw=[12*mm, 142*mm, 16*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 2),  (2, 2),  colors.HexColor("#F8F9FB")),
        ("BACKGROUND", (0, 4),  (2, 4),  colors.HexColor("#F8F9FB")),
        ("BACKGROUND", (0, 6),  (2, 6),  colors.HexColor("#F8F9FB")),
        ("BACKGROUND", (0, 8),  (2, 8),  colors.HexColor("#F8F9FB")),
        ("BACKGROUND", (0, 10), (2, 10), colors.HexColor("#F8F9FB")),
        ("BACKGROUND", (0, 12), (2, 12), colors.HexColor("#F8F9FB")),
        ("BACKGROUND", (0, 14), (2, 14), colors.HexColor("#F8F9FB")),
        ("TOPPADDING",    (0, 2), (2, 15), 1),
        ("BOTTOMPADDING", (0, 2), (2, 15), 1),
    ]))
    return t


def _build_synthese(data, perf_buf, registry=None):
    indice_rl = data["indice"].replace("&", "&amp;")
    elems = []
    if registry is not None: elems.append(SectionAnchor('Synthèse', registry))
    elems += section_title(_ilbl("synthese_macro"), 1)

    # ── KPI macro header : PE / 10Y / ERP ─────────────────────────────────────
    _erp    = data.get("erp", "—")
    _rf     = data.get("rf_rate", "—")
    _pe     = data.get("pe_forward", "—")
    _ytd    = data.get("variation_ytd", "—")
    _esig   = data.get("erp_signal", "—")
    _cours  = data.get("cours", "—")
    _esig_s = S_TD_G if _esig == "Favorable" else (S_TD_R if _esig == "Tendu" else S_TD_A)
    _ytd_s  = S_TD_G if "+" in str(_ytd) else S_TD_R
    kpi_h   = [Paragraph(h, S_TH_C) for h in
               ["Cours indice", "Perf. YTD", "P/E Forward", "10Y Yield", "ERP", "Signal ERP"]]
    kpi_row = [
        Paragraph(str(_cours),   S_TD_BC),
        Paragraph(str(_ytd),     _ytd_s),
        Paragraph(str(_pe),      S_TD_BC),
        Paragraph(str(_rf),      S_TD_BC),
        Paragraph(str(_erp),     S_TD_BC),
        Paragraph(str(_esig),    _esig_s),
    ]
    # [28, 22, 24, 24, 22, 50] = 170mm
    elems.append(KeepTogether(tbl([kpi_h, kpi_row], cw=[28*mm,22*mm,24*mm,24*mm,22*mm,50*mm])))
    # Interprétation ERP
    _erp_interp = {
        "Tendu":    ("<b>ERP sous 2%</b> \u2014 prime actions insuffisanté par rapport au taux sans risque. "
                     "Chaque BUY doit \u00eatre justifi\u00e9 par une croissance visible et un pricing power d\u00e9montr\u00e9."),
        "Favorable":("<b>ERP au-dessus de 4%</b> \u2014 le march\u00e9 actions offre une prime attractive "
                     "vs les taux. Le contexte macro justifié une surpond\u00e9ration actions. "
                     "Les signaux Surpond\u00e9rer ont une base macro solide."),
        "Neutre":   ("<b>ERP entre 2% et 4%</b> \u2014 valorisation raisonnable. "
                     "La s\u00e9lection sectorielle prime sur l'exposition beta. "
                     "Privil\u00e9gier les secteurs avec visibilit\u00e9 BPA \u00e9lev\u00e9e."),
    }
    _interp_txt = _erp_interp.get(_esig, "ERP non calcule \u2014 lancer une analyse indice compl\u00e8te.")
    elems.append(Paragraph(_interp_txt, S_BODY))
    elems.append(src(
        f"FinSight IA — ERP = Earnings Yield (1/PE forward) - Taux 10Y US (^TNX). "
        f"Seuils : Tendu <2%, Neutre 2-4%, Favorable >4%."))
    elems.append(Spacer(1, 3*mm))

    # ── Positionnement P/E vs historique 10 ans ──────────────────────────────
    _indice_name = data.get("indice", "")
    # Fourchettes historiques P/E forward 10 ans par indice (conservatrices)
    _PE_HIST = {
        "S&P 500":   (13.0, 24.0),
        "NASDAQ":    (18.0, 38.0),
        "NASDAQ 100":(18.0, 38.0),
        "CAC 40":    (11.0, 20.0),
        "DAX":       (10.0, 19.0),
        "Eurostoxx": (10.0, 18.0),
        "FTSE 100":  (10.0, 17.0),
        "Nikkei":    (13.0, 22.0),
        "Hang Seng": ( 8.0, 16.0),
        "Russell 2000": (15.0, 30.0),
    }
    # Recherche par correspondance partielle
    _pe_range = None
    for k, v in _PE_HIST.items():
        if k.lower() in _indice_name.lower() or _indice_name.lower() in k.lower():
            _pe_range = v
            break
    if _pe_range is None:
        _pe_range = (11.0, 22.0)  # fourchette generique

    try:
        _pe_val = float(str(_pe).replace("x", "").replace(",", ".").strip())
    except Exception:
        _pe_val = None

    if _pe_val is not None:
        _pe_min, _pe_max = _pe_range
        _pe_pct = max(0, min(100, round((_pe_val - _pe_min) / max(_pe_max - _pe_min, 1) * 100)))
        if _pe_pct >= 75:
            _pe_pos, _pe_pos_s = "Cherte élevée", S_TD_R
            _pe_interp = (f"Le P/E forward de {_frx(_pe_val)} se situe dans le <b>quartile supérieur</b> "
                          f"de sa fourchette historique 10 ans ({_pe_min:.0f}x\u2013{_pe_max:.0f}x). "
                          f"La valorisation intègre une croissance des benefices soutenue ; "
                          f"tout choc sur les marges ou la guidance pourrait triggerer une recompression multiple.")
        elif _pe_pct >= 50:
            _pe_pos, _pe_pos_s = "Valorisation élevée", S_TD_A
            _pe_interp = (f"Le P/E forward de {_frx(_pe_val)} s'inscrit <b>au-dessus de la médiane historique</b> "
                          f"({_pe_min:.0f}x\u2013{_pe_max:.0f}x). La prime de valorisation est justifiable "
                          f"si la visibilité BPA reste intacte. Surveiller les révisions d'analystes.")
        elif _pe_pct >= 25:
            _pe_pos, _pe_pos_s = "Valorisation raisonnable", S_TD_G
            _pe_interp = (f"Le P/E forward de {_frx(_pe_val)} s'inscrit <b>dans la moitié inférieure</b> "
                          f"de la fourchette historique ({_pe_min:.0f}x\u2013{_pe_max:.0f}x). "
                          f"La valorisation offre un coussin par rapport aux niveaux de stress.")
        else:
            _pe_pos, _pe_pos_s = "Sous-valorisation", S_TD_G
            _pe_interp = (f"Le P/E forward de {_frx(_pe_val)} se situe dans le <b>quartile inférieur</b> "
                          f"de sa fourchette historique ({_pe_min:.0f}x\u2013{_pe_max:.0f}x). "
                          f"Les niveaux actuels peuvent offrir une opportunité d'entrée si les fondamentaux se stabilisent.")

        pe_h = [Paragraph(h, S_TH_C) for h in
                ["P/E Forward actuel", "Fourchette 10 ans", "Percentile hist.", "Positionnement"]]
        pe_row = [
            Paragraph(_frx(_pe_val),                        S_TD_BC),
            Paragraph(f"{_pe_min:.0f}x \u2014 {_pe_max:.0f}x", S_TD_C),
            Paragraph(f"{_pe_pct}e percentile",              _pe_pos_s),
            Paragraph(f"<b>{_pe_pos}</b>",                   _pe_pos_s),
        ]
        elems.append(KeepTogether([
            Paragraph("Positionnement P/E Forward vs historique 10 ans", S_SUBSECTION),
            Spacer(1, 2*mm),
            tbl([pe_h, pe_row], cw=[38*mm, 38*mm, 40*mm, 54*mm]),
            Spacer(1, 2*mm),
            Paragraph(_pe_interp, S_BODY),
            Spacer(1, 1*mm),
            src(f"FinSight IA — Fourchettes P/E historiques estimees sur 10 ans. "
                f"Percentile = (PE actuel - PE min) / (PE max - PE min). Source : consensus analystes."),
            Spacer(1, 3*mm),
        ]))

    # ── Régime de Marché + Probabilite de récession ──────────────────────────
    _macro = data.get("macro") or {}
    _regime  = _macro.get("régime")
    _vix     = _macro.get("vix")
    _spread  = _macro.get("yield_spread_10y_3m")
    _sp_ma   = _macro.get("sp500_vs_ma200")
    _rec_6m  = _macro.get("recession_prob_6m")
    _rec_12m = _macro.get("recession_prob_12m")
    _rec_lvl = _macro.get("recession_level", "Inconnu")
    _drivers = _macro.get("recession_drivers", [])

    if _regime and _regime != "Inconnu":
        elems.append(Paragraph("Environnement macro — Régime de Marché", S_SUBSECTION))
        elems.append(Spacer(1, 2*mm))
        _vix_str    = f"{_vix:.0f}" if _vix    is not None else "indetermine"
        _spread_str = f"{_spread:+.1f}%" if _spread is not None else "non disponible"
        _sp_ma_str  = f"{_sp_ma:+.1f}%" if _sp_ma  is not None else "non disponible"
        _sp_trend   = _macro.get("sp500_trend", "indeterminee")
        _regime_labels = {
            "Bull": "haussier", "Bear": "baissier",
            "Volatile": "volatile", "Transition": "de transition",
        }
        _regime_lbl = _regime_labels.get(_regime, _regime.lower())
        elems.append(Paragraph(
            f"<b>Régime de Marché : {_regime}.</b> L'environnement macro est actuellement "
            f"{_regime_lbl}, avec un VIX a {_vix_str}, un spread 10Y-3M de {_spread_str} "
            f"et le S&P 500 a {_sp_ma_str} de sa moyenne mobile 200 jours. "
            f"La tendance de fond reste {_sp_trend.lower()}.", S_BODY))
        elems.append(Spacer(1, 2*mm))
        if _rec_6m is not None:
            _drivers_str = " et ".join(_drivers[:2]) if _drivers else "aucun signal recessif dominant"
            _rec_qualif  = ("élevée" if _rec_lvl == "Élevée" else
                            ("modérée" if _rec_lvl == "Modérée" else "faible"))
            elems.append(Paragraph(
                f"<b>Risque de récession.</b> La probabilité de récession sur 6 mois est Estimée "
                f"a <b>{_rec_6m}%</b> (niveau {_rec_qualif}), contre {_rec_12m}% sur 12 mois. "
                f"Les principaux signaux d'alerte incluent {_drivers_str}. "
                "Cette évaluation est indicative et fondee sur des indicateurs de Marché "
                "(VIX, courbe des taux, momentum) Plutôt que sur un modèle econometrique.", S_BODY))
            elems.append(src(
                "Indicateur de Marché (non econometrique) : VIX + spread 10Y-3M + "
                "position S&P 500 vs MA200 + momentum 6M. Source : FinSight IA / yfinance."))
        elems.append(Spacer(1, 4*mm))
    else:
        elems.append(Spacer(1, 4*mm))

    # ── Indicateurs macroéconomiques FRED (si disponibles) ───────────────────
    _fred_elems = _build_fred_macro_table()
    if _fred_elems:
        elems.extend(_fred_elems)

    elems.append(Paragraph("Contexte macro\u00e9conomique et positionnément", S_SUBSECTION))
    elems.append(Spacer(1, 1*mm))
    elems.append(Paragraph(data["texte_macro"], S_BODY))
    elems.append(Spacer(1, 3*mm))
    elems.append(Paragraph("Signal global et conviction d'allocation", S_SUBSECTION))
    elems.append(Spacer(1, 1*mm))
    elems.append(Paragraph(data["texte_signal"], S_BODY))
    elems.append(Spacer(1, 3*mm))

    elems.append(Image(perf_buf, width=TABLE_W, height=72*mm))
    _ph = data.get("perf_history")
    _base_lbl = _ph["label_start"] if _ph else data.get("date_analyse","")
    elems.append(src(f"FinSight IA — yfinance. Base 100, {_base_lbl}. {indice_rl} vs US 10Y Bond vs Gold."))
    elems.append(Spacer(1, 4*mm))

    elems.append(debate_q(
        "Quels catalyseurs pourraient faire devier l'indice de son scénario central ?"))
    def _xml_esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    cat_h = [Paragraph(h, S_TH_L) for h in ["Catalyseur", "Mecanisme", "Horizon"]]
    cat_rows = []
    for nom, mecanisme, horizon in data["catalyseurs"]:
        cat_rows.append([Paragraph(_xml_esc(nom), S_TD_B),
                         Paragraph(_xml_esc(mecanisme), S_TD_L),
                         Paragraph(_xml_esc(horizon), S_TD_C)])
    elems.append(KeepTogether(tbl([cat_h] + cat_rows, cw=[42*mm, 110*mm, 18*mm])))
    elems.append(src("FinSight IA — Analyse interne. Probabilités non assignees (cf. section Risques)."))

    # Bloc Synthèse signal — fill empty space page 3
    secteurs = data["secteurs"]
    nb_surp  = sum(1 for s in secteurs if len(s) > 3 and "Surp" in str(s[3]))
    nb_sous  = sum(1 for s in secteurs if len(s) > 3 and "Sous" in str(s[3]))
    nb_neut  = len(secteurs) - nb_surp - nb_sous
    top_s    = sorted(secteurs, key=lambda s: float(str(s[2]).replace(',','.') or 0), reverse=True)
    top3_nms = ", ".join(s[0] for s in top_s[:3]) if top_s else "—"
    conviction = data.get("conviction_pct", "—")
    elems.append(Spacer(1, 5*mm))
    syn_h = [Paragraph(h, S_TH_C) for h in ["Signal", "Nb secteurs", "Implication allocation"]]
    _surp_impl = ("Surpond\xe9ration active \u2014 renforcer l\u2019exposition"
                  if nb_surp > 0
                  else "Aucun secteur en signal Surpond\xe9rer \u2014 maintenir pond\xe9ration neutre")
    syn_rows = [
        [Paragraph("Surpond\xe9rer", S_TD_G), Paragraph(str(nb_surp), S_TD_C),
         Paragraph(_surp_impl, S_TD_L)],
        [Paragraph("Neutre",       S_TD_A), Paragraph(str(nb_neut), S_TD_C),
         Paragraph("Pond\xe9ration indice \u2014 maintenir", S_TD_L)],
        [Paragraph("Sous-pond\xe9rer", S_TD_R), Paragraph(str(nb_sous), S_TD_C),
         Paragraph("R\xe9duire l\u2019exposition en dessous de l\u2019indice", S_TD_L)],
    ]
    _conv_para = Paragraph(
        f"Conviction globale {conviction} % — les {nb_surp} secteur(s) Surpond\xe9rer "
        f"({top3_nms}) concentrent les opportunit\xe9s d\u2019alpha. Toute d\xe9t\xe9rioration "
        "du signal doit declencher une revue de positionnément dans les 5 jours ouvrables.", S_BODY)
    elems.append(KeepTogether([
        debate_q("Quelle est la distribution actuelle des signaux sectoriels ?"),
        tbl([syn_h] + syn_rows, cw=[36*mm, 28*mm, 106*mm]),
        Spacer(1, 2*mm),
        _conv_para,
    ]))
    return elems


def _build_cartographie(data, weights_buf, attribution_buf=None, registry=None):
    secteurs = data["secteurs"]
    indice_rl = data["indice"].replace("&", "&amp;")
    elems = []
    elems.append(CondPageBreak(120*mm))
    elems.append(Spacer(1, 6*mm))
    if registry is not None: elems.append(SectionAnchor('carto', registry))
    elems += section_title(_ilbl("cartographie"), 2)
    elems.append(Spacer(1, 4*mm))

    # Graphique + mini tableau côte à côte
    # combined: [80, 90] = 170mm. Image 80mm, right_col 90mm.
    weights_img = Image(weights_buf, width=80*mm, height=68*mm)
    sig_rows = []
    for s in secteurs:
        sig_rows.append([
            Paragraph(_abbrev_pdf(s[0]), S_TD_L),
            Paragraph(s[3], sig_s(s[3])),
            Paragraph(str(s[2]), S_TD_C),
        ])
    # mini tbl: [46, 28, 16] = 90mm — Score 16mm donne 10mm texte avec pad 3mm
    sig_tbl_inner = Table([
        [Paragraph(h, S_TH_C) for h in ["Secteur","Signal","Score"]]
    ] + sig_rows, colWidths=[46*mm, 28*mm, 16*mm])
    sig_tbl_inner.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,0),  NAVY),
        ('ROWBACKGROUNDS',(0,1),(-1,-1), [WHITE, ROW_ALT]),
        ('FONTNAME',      (0,0),(-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0),(-1,-1), 8),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0),(-1,-1), 3),
        ('BOTTOMPADDING', (0,0),(-1,-1), 3),
        ('LEFTPADDING',   (0,0),(-1,-1), 3),
        ('RIGHTPADDING',  (0,0),(-1,-1), 3),
        ('GRID',          (0,1),(-1,-1), 0.3, GREY_MED),
    ]))
    right_col = Table(
        [[Paragraph("Signaux par secteur", S_SUBSECTION)], [sig_tbl_inner]],
        colWidths=[90*mm]
    )
    right_col.setStyle(TableStyle([
        ("LEFTPADDING",   (0,0),(-1,-1), 0), ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ("TOPPADDING",    (0,0),(-1,-1), 0), ("BOTTOMPADDING", (0,0),(-1,-1), 2),
    ]))
    combined = Table([[weights_img, right_col]], colWidths=[80*mm, 90*mm])
    combined.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING",   (0,0),(-1,-1), 0), ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ("TOPPADDING",    (0,0),(-1,-1), 0), ("BOTTOMPADDING", (0,0),(-1,-1), 0),
        ("LEFTPADDING",   (1,0),(1,0),   6),
    ]))
    elems.append(combined)
    elems.append(src(
        f"FinSight IA — Pondérations GICS. Score composite : 40% momentum, 30% rév. BPA, 30% valorisation."))
    elems.append(Spacer(1, 4*mm))

    # Tableau comparatif complet — colonnes exactement 170mm
    # [8, 36, 14, 16, 22, 24, 18, 16, 16] = 170 — compact pad 3mm
    comp_h = [Paragraph(h, S_TH_C) for h in
              ["Rg","Secteur","Nb","Score","Signal",
               "EV/EBITDA","Mg.EBIT.","Croiss.","Mom."]]
    comp_rows = []
    sorted_secs = sorted(secteurs, key=lambda s: s[2], reverse=True)
    for rang, s in enumerate(sorted_secs, 1):
        mg_raw = s[5] if len(s) > 5 else None
        mg   = f"{mg_raw:.1f}%" if isinstance(mg_raw, (int, float)) and mg_raw != 0.0 else "\u2014"
        croi = str(s[6]) if len(s) > 6 else "\u2014"
        mom  = str(s[7]) if len(s) > 7 else "\u2014"
        # EV/EBITDA : afficher N/A* pour immobilier (REITs) si Donnée absente
        _ev_raw = s[4] if len(s) > 4 else "\u2014"
        _sec_low = str(s[0]).lower()
        _is_reit = any(k in _sec_low for k in ("real estate", "immobilier", "reit", "foncier"))
        if _is_reit and str(_ev_raw) in ("\u2014", "—", "", "None"):
            _ev_str = "N/A*"
        else:
            _ev_str = str(_ev_raw)
        comp_rows.append([
            Paragraph(str(rang), S_TD_C),
            Paragraph(_abbrev_pdf(s[0]), S_TD_B),
            Paragraph(str(s[1]), S_TD_C),
            Paragraph(str(s[2]), S_TD_BC),
            Paragraph(s[3], sig_s(s[3])),
            Paragraph(_ev_str, S_TD_C),
            Paragraph(mg, S_TD_C),
            Paragraph(croi, S_TD_G if '+' in str(croi) else S_TD_R),
            Paragraph(mom,  S_TD_G if '+' in str(mom)  else S_TD_R),
        ])
    # [8, 33, 10, 14, 30, 22, 18, 17, 18] = 170mm — Signal 30mm ok pour "Sous-pondérer"
    comp_tbl = tbl([comp_h] + comp_rows,
        cw=[8*mm, 33*mm, 10*mm, 14*mm, 30*mm, 22*mm, 18*mm, 17*mm, 18*mm],
        compact=True)
    elems.append(KeepTogether([
        Paragraph(f"Tableau comparatif — {data['nb_secteurs']} {'secteur' if data['nb_secteurs'] == 1 else 'secteurs'} {indice_rl}", S_SUBSECTION),
        Spacer(1, 2*mm),
        comp_tbl,
    ]))
    elems.append(src(
        f"FinSight IA — FMP, yfinance. EV/EBITDA et marges = m\u00e9dianes sectorielles LTM. "
        "Momentum = performance relative 3 mois vs indice. Score = composite 0-100. "
        "(*) EV/EBITDA non standard pour l\u2019immobilier cot\u00e9 (REITs) : privil\u00e9gier P/NAV ou Price/FFO."))

    # ── Table valorisation etendue : P/B, Div Yield, ERP sectoriel ───────────
    pb_map  = data.get("pb_by_sector", {})
    dy_map  = data.get("dy_by_sector", {})
    erp_map = data.get("erp_by_sector", {})
    if pb_map or dy_map:
        elems.append(Spacer(1, 5*mm))
        elems.append(Paragraph("Valorisation \u00c9tendue &amp; Rendement Sectoriel", S_SUBSECTION))
        elems.append(Paragraph(
            "Ce tableau compl\u00e8te le comparatif EV/EBITDA avec trois dimensions "
            "additionnelles : <b>Price/Book</b> (positionnément valeur vs croissance), "
            "<b>Dividend Yield</b> (rendement courant), et <b>ERP sectoriel implicite</b> "
            "(Div. Yield + croissance LT - taux sans risque) qui estime la prime de risque "
            "propre \u00e0 chaque secteur.", S_BODY))
        elems.append(Spacer(1, 2*mm))
        val_h = [Paragraph(h, S_TH_C) for h in
                 ["Secteur", "P/Book", "Div. Yield", "ERP Sectoriel", "Lecture"]]
        # Alias ETF → nom secteur local (ex: yfinance/CAC40 vs SPDR ETF names)
        _SECTOR_ALIAS = {
            "Financial Services": "Financials",
            "Healthcare": "Health Care",
            "Basic Materials": "Materials",
            "Consumer Défensive": "Consumer Staples",
            "Consumer Cyclical": "Consumer Discretionary",
        }
        val_rows = []
        for s in sorted_secs:
            nom = s[0]
            _alias = _SECTOR_ALIAS.get(nom, nom)
            _pb  = pb_map.get(nom)  if pb_map.get(nom)  is not None else pb_map.get(_alias)
            _dy  = dy_map.get(nom)  if dy_map.get(nom)  is not None else dy_map.get(_alias)
            _erp = erp_map.get(nom) if erp_map.get(nom) is not None else erp_map.get(_alias)
            _pb_s  = _frx(_pb)  if _pb  else "\u2014"
            _dy_s  = _frp(_dy)  if _dy  else "\u2014"
            _erp_s = _frp(_erp, sign=True) if _erp is not None else "\u2014"
            _erp_style = S_TD_G if (_erp or 0) > 4 else (S_TD_R if (_erp or 0) < 1 else S_TD_A)
            # Lecture qualitative
            if _erp is None:
                _lecture = "\u2014"
            elif _erp > 4:
                _lecture = "Prime \u00e9lev\u00e9e — secteur attractif vs taux"
            elif _erp < 1:
                _lecture = "Prime faible — valoris\u00e9 serr\u00e9 vs taux"
            else:
                _lecture = "Prime mod\u00e9r\u00e9e — valorisation raisonnable"
            # Affichage du nom de secteur en francais
            try:
                from core.sector_labels import fr_label as _fr_lbl
                _nom_fr = _fr_lbl(nom)
            except Exception:
                _nom_fr = nom
            val_rows.append([
                Paragraph(_nom_fr, S_TD_B),
                Paragraph(_pb_s, S_TD_C),
                Paragraph(_dy_s, S_TD_G if (_dy or 0) > 2.5 else S_TD_C),
                Paragraph(_erp_s, _erp_style),
                Paragraph(_lecture, S_TD_L),
            ])
        # [42, 20, 22, 26, 60] = 170mm
        elems.append(KeepTogether(tbl([val_h] + val_rows,
                                      cw=[42*mm, 20*mm, 22*mm, 26*mm, 60*mm])))
        elems.append(src(
            f"FinSight IA — P/Book et Div.Yield : ETF SPDR yfinance ou valeurs sectorielles "
            f"Médianes S&amp;P 500. ERP sectoriel = Div.Yield + croissance LT Normalisée - "
            f"{data.get('rf_rate','4.50%')} (10Y US)."))

    # ── Attribution sectorielle ────────────────────────────────────────────────
    if attribution_buf is not None:
        elems.append(Spacer(1, 5*mm))
        elems.append(Paragraph("Attribution sectorielle au return indice", S_SUBSECTION))
        elems.append(Paragraph(
            "Le graphique ci-dessous Décompose le return total de l'indice en contributions "
            "sectorielles : <b>contribution = poids sectoriel \xd7 return 1 an</b>. "
            "Cette lecture permet d'identifier quels secteurs ont tire ou freine la "
            "performance de l'indice, et d'évaluer la concentration du return.", S_BODY))
        elems.append(Spacer(1, 2*mm))
        elems.append(Image(attribution_buf, width=TABLE_W, height=88*mm))
        elems.append(src(
            "FinSight IA — ETF SPDR sectoriels, yfinance. "
            "Poids = nb sociétés par secteur / total indice. Contribution = poids x return 12 mois."))

    # ── Factor tilts & Breadth ─────────────────────────────────────────────────
    analytics = data.get("indice_analytics", {})
    if analytics:
        elems.append(Spacer(1, 5*mm))
        elems.append(Paragraph("Biais Factoriels &amp; Santé du March\u00e9", S_SUBSECTION))
        _tilt    = analytics.get("tilt", "—")
        _spread  = analytics.get("tilt_spread", 0)
        _cyc     = analytics.get("cyclical_return", 0)
        _def     = analytics.get("defensive_return", 0)
        _breadth = analytics.get("breadth_pct", 0)
        _br_nb   = analytics.get("breadth_nb", 0)
        _br_tot  = analytics.get("nb_total", 0)
        _tilt_s  = S_TD_G if _tilt == "Cyclique" else (S_TD_R if _tilt == "Défensif" else S_TD_A)
        _br_s    = S_TD_G if _breadth >= 70 else (S_TD_R if _breadth < 40 else S_TD_A)
        ftbl_h = [Paragraph(h, S_TH_C) for h in
                  ["Indicateur", "Valeur", "Detail", "Interprétation"]]
        ftbl_rows = [
            [Paragraph("Biais sectoriel", S_TD_B),
             Paragraph(_tilt, _tilt_s),
             Paragraph(f"Cyclique {_cyc:+.1f}% vs D\u00e9fensif {_def:+.1f}% (\u00c9cart {_spread:.1f}pp)", S_TD_L),
             Paragraph(
                 "Cyclique = Technologie, Conso. Cycl., T\u00e9l\u00e9coms, Finance, "
                 "Industrie, \u00c9nergie, Mat\u00e9riaux | "
                 "D\u00e9fensif = Conso. D\u00e9f., Sant\u00e9, Serv. Publ., Immobilier", S_TD_L)],
            [Paragraph("Breadth sectorielle", S_TD_B),
             Paragraph(f"{_breadth}%", _br_s),
             Paragraph(f"{_br_nb}/{_br_tot} secteurs en momentum positif (return 12M > 0)", S_TD_L),
             Paragraph(
                 ">70% : March\u00e9 porteur, beta recommand\u00e9 | "
                 "<40% : March\u00e9 fragile, stock-picking d\u00e9fensif", S_TD_L)],
        ]
        # [40, 22, 62, 46] = 170
        elems.append(KeepTogether(tbl([ftbl_h] + ftbl_rows,
                                      cw=[40*mm, 22*mm, 62*mm, 46*mm])))
        elems.append(src(
            "FinSight IA — ETF SPDR, yfinance. "
            "Biais = écart de return annualise cyclique/défensif. "
            "Breadth = % secteurs return 12M > 0."))
    return elems


def _build_graphiques(data, scatter_buf, scores_buf, corr_buf=None, registry=None):
    elems = []
    elems.append(CondPageBreak(120*mm))
    elems.append(Spacer(1, 6*mm))
    if registry is not None: elems.append(SectionAnchor('graphiques', registry))
    elems += section_title(_ilbl("analyse_graphique"), 3)
    elems.append(Spacer(1, 3*mm))

    elems.append(Paragraph("Positionnement EV/EBITDA vs Croissance BPA", S_SUBSECTION))
    if scatter_buf is not None:
        elems.append(Paragraph(
            "Le scatter ci-dessous positionné chaque secteur sur deux axes : "
            "valorisation (EV/EBITDA m\u00e9dian LTM) et croissance BPA m\u00e9diane. "
            "Les lignes pointill\u00e9es repr\u00e9sentent les m\u00e9dianes sectorielles — "
            "les secteurs dans le <b>quadrant sup\u00e9rieur droit</b> paient une prime justifi\u00e9e "
            "par une forte croissance ; ceux dans le <b>quadrant inf\u00e9rieur gauche</b> offrent "
            "une valeur relative.", S_BODY))
        elems.append(Spacer(1, 3*mm))
        elems.append(Image(scatter_buf, width=TABLE_W, height=95*mm))
        elems.append(src("FinSight IA — EV/EBITDA médian LTM vs croissance BPA Médiane secteur. FMP, Bloomberg."))
        # Interprétation enrichie via LLM (audit Baptiste S&P 500 p7 2026-04-14)
        _secteurs = data["secteurs"]
        # Noms secteurs en francais pour affichage ET pour injection dans prompt LLM
        _surp = [_abbrev_pdf(s[0]) for s in _secteurs if "Surp" in str(s[3])]
        _sous = [_abbrev_pdf(s[0]) for s in _secteurs if "Sous" in str(s[3])]
        _neut = [_abbrev_pdf(s[0]) for s in _secteurs if "Neutre" in str(s[3])
                 or (s[3] not in ("Surp", "Sous") and "Surp" not in str(s[3]) and "Sous" not in str(s[3]))]
        _surp_str = ", ".join(_surp) if _surp else "aucun"
        _sous_str = ", ".join(_sous) if _sous else "aucun"

        # Top/bottom EV/EBITDA pour alimenter le prompt
        _ev_pairs = []
        for s in _secteurs:
            try:
                _ev = float(str(s[4]).replace('x','').replace(',','.').strip() or 0)
                if _ev > 0:
                    _ev_pairs.append((_abbrev_pdf(s[0]), _ev, str(s[6])))
            except Exception as _e:
                log.debug(f"[indice_pdf_writer:_build_graphiques] exception skipped: {_e}")
        _ev_pairs.sort(key=lambda x: x[1])
        _cheap_str  = ", ".join(f"{n} {v:.1f}x" for n, v, _ in _ev_pairs[:3]) or "n.d."
        _exp_str    = ", ".join(f"{n} {v:.1f}x" for n, v, _ in _ev_pairs[-3:]) or "n.d."

        _llm_text = ""
        try:
            from core.llm_provider import llm_call
            _indice_name = data.get("indice", "l'indice")
            # LLM-A compressed
            _prompt_p7 = (
                f"Analyste buy-side senior. Analyse 320-380 mots du positionnement "
                f"EV/EBITDA vs croissance BPA pour {_indice_name}.\n"
                f"Surpondérer : {_surp_str}\nSous-ponderer : {_sous_str}\n"
                f"Decotes : {_cheap_str}\nPrimes : {_exp_str}\n\n"
                f"3 paragraphes separes par ligne vide (~110 mots chacun) avec ces "
                f"titres EXACTS en MAJUSCULES au debut de chaque paragraphe suivi de ' : ' :\n"
                f"1. DÉCOTE : lecture du quadrant inferieur gauche, risques value trap, "
                f"conditions de re-rating.\n"
                f"2. PRIME : justification du quadrant superieur droit, Sensibilité "
                f"révisions BPA, risques spécifiques.\n"
                f"3. IMPLICATIONS : ou renforcer, ou alléger, catalyseurs et signaux "
                f"macro a cross-checker.\n\n"
                f"IMPORTANT : commence CHAQUE paragraphe par son titre MAJUSCULE + ' : '.\n"
                f"Francais avec accents. Noms secteurs en francais. Pas de markdown/emojis/bullets."
            )
            _llm_text = llm_call(_prompt_p7, phase="long", max_tokens=1000) or ""
            try:
                from core.llm_guardrails import audit_llm_output as _audit
                _audit(_llm_text, index_name=_indice_name,
                        context_label=f"indice_pdf p7 {_indice_name}")
            except Exception:
                pass
        except Exception as _e:
            log.warning("[indice_pdf] scatter p7 LLM echoue: %s", _e)
        elems.append(Spacer(1, 4*mm))
        if _llm_text.strip():
            # NIGHT-4 : helper sous-titres bleus propage depuis pdf_writer
            try:
                from outputs.pdf_writer import _render_llm_structured as _rls
                _rls(elems, _llm_text, section_map={
                    "DÉCOTE":        "D\u00e9côté \u2014 quadrant inf\u00e9rieur gauche",
                    "DÉCOTE":        "D\u00e9côté \u2014 quadrant inf\u00e9rieur gauche",
                    "PRIME":         "Prime \u2014 quadrant sup\u00e9rieur droit",
                    "IMPLICATIONS":  "Implications d'allocation",
                })
            except Exception:
                for _para in _llm_text.strip().split("\n\n"):
                    _clean = _para.strip().replace("\n", " ")
                    if _clean:
                        elems.append(Paragraph(_clean, S_BODY))
                        elems.append(Spacer(1, 2*mm))
        else:
            # Fallback texte déterministe si LLM echoue
            elems.append(Paragraph(
                "<b>Lecture du positionnement.</b> "
                "Les secteurs dans le <b>quadrant inf\xe9rieur gauche</b> (faible EV/EBITDA, "
                "faible croissance BPA) offrent une d\xe9côté relative \u2014 opportunit\xe9 "
                "si les fondamentaux se stabilisent. Ceux dans le <b>quadrant sup\xe9rieur "
                "droit</b> paient une prime justifi\xe9e par leur croissance visible. "
                f"Secteurs signal <b>Surpond\xe9rer</b> : {_surp_str}. "
                f"Secteurs signal <b>Sous-pond\xe9rer</b> : {_sous_str}. "
                f"Les secteurs en d\xe9côté EV/EBITDA ({_cheap_str}) meritent une analyse "
                f"fondamentale approfondie pour distinguer opportunite structurelle et "
                f"value trap cyclique. \xc0 l'inverse, les secteurs en prime ({_exp_str}) "
                f"exigent une croissance BPA durable sur 18-24 mois pour justifier leur "
                f"valorisation.", S_BODY))
    else:
        elems.append(Paragraph(
            "L'analyse comparative EV/EBITDA vs croissance BPA n\u00e9cessite au moins deux secteurs. "
            "Pour un univers mono-sectoriel, consulter le tableau comparatif (section 2) "
            "qui donne les m\u00e9dianes LTM par soci\u00e9t\u00e9 représentative.", S_BODY))
        elems.append(src("FinSight IA — Graphique non disponible pour univers mono-sectoriel."))

    elems.append(CondPageBreak(120*mm))
    elems.append(Spacer(1, 6*mm))
    elems.append(Paragraph("Score composite — Classement sectoriel", S_SUBSECTION))
    nb_surp = sum(1 for s in data["secteurs"] if "Surp" in str(s[3]))
    nb_sous = sum(1 for s in data["secteurs"] if "Sous" in str(s[3]))
    elems.append(Paragraph(
        "Le score composite (0-100) agr\u00e8ge trois signaux : momentum prix 3 mois (40%), "
        "révision des estimations BPA sur 1 mois (30%) et valorisation relative (30%). "
        "La ligne pointill\u00e9e orange marque le seuil 50 — <b>au-dessus : signal Surpond\u00e9rer</b> "
        "possible, <b>en dessous de 40 : Sous-pond\u00e9rer</b>. "
        f"{nb_surp} {'secteur franchit' if nb_surp == 1 else 'secteurs franchissent'} le seuil Surpond\u00e9rer (60), "
        f"{nb_sous} {'en' if nb_sous == 0 else 'secteur en' if nb_sous == 1 else 'secteurs en'} Sous-pond\u00e9rer.", S_BODY))
    elems.append(Spacer(1, 3*mm))
    elems.append(Image(scores_buf, width=TABLE_W, height=95*mm))
    elems.append(src(
        "FinSight IA — Score composite tri\u00e9 par ordre d\u00e9croissant. "
        "Seuil Surpond\u00e9rer = 60, Sous-pond\u00e9rer = 40."))

    # Top 3 / Bottom 3 secteurs par score
    _sect_sorted = sorted(data["secteurs"],
                          key=lambda s: float(str(s[2]).replace(',','.') or 0), reverse=True)
    elems.append(Spacer(1, 5*mm))
    elems.append(Paragraph("Top 3 &amp; Bottom 3 secteurs par score composite", S_SUBSECTION))
    _tb_h = [Paragraph(h, S_TH_C) for h in ["Rang", "Secteur", "Score", "Signal", "Implication"]]
    _tb_rows = []
    def _impl(sig):
        _s = str(sig)
        _txt = ("Surpond\xe9rer \u2014 renforcer" if "Surp" in _s
                else "Sous-pond\xe9rer \u2014 all\xe9ger" if "Sous" in _s
                else "Pond\xe9ration indice \u2014 maintenir")
        return Paragraph(_txt, sig_s(sig))
    for _i, _s in enumerate(_sect_sorted[:3]):
        _tb_rows.append([
            Paragraph(f"#{_i+1}", S_TD_C),
            Paragraph(_s[0], S_TD_L),
            Paragraph(str(_s[2]), S_TD_C),
            Paragraph(_s[3], sig_s(_s[3])),
            _impl(_s[3]),
        ])
    for _i, _s in enumerate(_sect_sorted[-3:]):
        _rank = len(_sect_sorted) - 2 + _i
        _tb_rows.append([
            Paragraph(f"#{_rank}", S_TD_C),
            Paragraph(_s[0], S_TD_L),
            Paragraph(str(_s[2]), S_TD_C),
            Paragraph(_s[3], sig_s(_s[3])),
            _impl(_s[3]),
        ])
    elems.append(KeepTogether(tbl([_tb_h] + _tb_rows, cw=[12*mm, 52*mm, 16*mm, 32*mm, 58*mm])))
    elems.append(src("FinSight IA — Scores FinSight. Score composite 0-100."))

    # ── Matrice de correlation ─────────────────────────────────────────────────
    if corr_buf is not None:
        elems.append(CondPageBreak(120*mm))
        elems.append(Spacer(1, 6*mm))
        elems.append(Paragraph("Matrice de Correlation Sectorielle", S_SUBSECTION))
        elems.append(Paragraph(
            "La matrice ci-dessous mesure la <b>correlation des rendements journaliers</b> "
            "entre les 11 secteurs GICS sur les 52 derni\u00e8res semaines. "
            "Une correlation \u00e9lev\u00e9e (proche de +1, navy) indique que les deux secteurs "
            "bougent ensemble \u2014 la diversification inter-sectorielle est limit\u00e9e. "
            "Une correlation faible ou n\u00e9gative (rouge) offre un b\u00e9n\u00e9fice "
            "de diversification r\u00e9el en portefeuille.", S_BODY))
        elems.append(Spacer(1, 3*mm))
        elems.append(Image(corr_buf, width=TABLE_W, height=120*mm))
        elems.append(src(
            "FinSight IA — Correlations calculées sur rendements journaliers 52S "
            "des ETF SPDR sectoriels (XLK, XLV, XLF...). yfinance."))
        # Interprétation quantitative
        corr_d = data.get("correlation_matrix", {})
        if corr_d and corr_d.get("matrix"):
            mat = corr_d["matrix"]
            secs = corr_d.get("sectors", [])
            n_c = len(secs)
            off_diag = [(mat[i][j], secs[i], secs[j])
                        for i in range(n_c) for j in range(i+1, n_c)]
            if off_diag:
                min_c = min(off_diag, key=lambda x: x[0])
                max_c = max(off_diag, key=lambda x: x[0])
                med_c = round(float(__import__('statistics').median([v[0] for v in off_diag])), 2)
                elems.append(Spacer(1, 3*mm))
                corr_interp = [
                    ["Corrélation médiane", f"{med_c:.2f}",
                     "Niveau de dépendance systemique moyen entre secteurs"],
                    ["Paire la moins correlee",
                     f"{_abbrev_pdf(min_c[1])} / {_abbrev_pdf(min_c[2])}  ({min_c[0]:.2f})",
                     "Meilleur bénéfice de diversification inter-sectoriel disponible"],
                    ["Paire la plus correlee",
                     f"{_abbrev_pdf(max_c[1])} / {_abbrev_pdf(max_c[2])}  ({max_c[0]:.2f})",
                     "Secteurs a ne pas sur-pondérér simultanement — beta commun élevé"],
                ]
                corr_h = [Paragraph(h, S_TH_L) for h in ["Indicateur", "Valeur", "Interprétation"]]
                corr_rows = [[Paragraph(r[0], S_TD_B), Paragraph(r[1], S_TD_C),
                              Paragraph(r[2], S_TD_L)] for r in corr_interp]
                elems.append(KeepTogether(tbl([corr_h] + corr_rows,
                                              cw=[46*mm, 64*mm, 60*mm])))
                elems.append(src("FinSight IA — calcul interne sur Données ETF SPDR."))
    return elems


def _build_rotation(data, registry=None):
    elems = []
    elems.append(CondPageBreak(120*mm))
    elems.append(Spacer(1, 6*mm))
    if registry is not None: elems.append(SectionAnchor('rotation', registry))
    elems += section_title(_ilbl("rotation"), 4)
    elems.append(Spacer(1, 4*mm))

    elems.append(debate_q(
        "O\u00f9 en sommes-nous dans le cycle \u00e9conomique et quels secteurs privil\u00e9gier ?"))
    elems.append(Paragraph("Analyse du positionnément cyclique et recommandation de rotation", S_SUBSECTION))
    elems.append(Spacer(1, 1*mm))
    elems.append(Paragraph(data["texte_rotation"], S_BODY))
    elems.append(Spacer(1, 3*mm))

    rot_h = [Paragraph(h, S_TH_C) for h in
             ["Secteur","Phase cycle","Sens. taux","Sens. PIB","Signal de rotation"]]

    def rot_signal_s(sig):
        if sig == "Accumuler": return S_TD_G
        if sig in ("All\xe9ger", "Alléger"): return S_TD_R
        return S_TD_A

    rot_rows = []
    for item in data["rotation"]:
        s, phase, taux, pib, sig = item
        phase_s = S_TD_G if phase == "Expansion" else (S_TD_R if phase in ("R\xe9cession","Récession") else S_TD_A)
        rot_rows.append([
            Paragraph(s, S_TD_B),
            Paragraph(phase, phase_s),
            Paragraph(taux, S_TD_C),
            Paragraph(pib,  S_TD_C),
            Paragraph(sig,  rot_signal_s(sig)),
        ])
    # [44, 32, 26, 26, 42] = 170
    elems.append(KeepTogether(tbl([rot_h] + rot_rows,
        cw=[44*mm, 32*mm, 26*mm, 26*mm, 42*mm])))
    elems.append(src(
        "FinSight IA — Modèle de rotation 4 phases. "
        "Sensibilités : Faible / Modérée / Élevée / Positive (taux)."))

    # Encadre cycle — dynamique depuis les Données réelles
    _surp_noms_rot = data.get("surp_noms") or " \xb7 ".join(
        s["nom"] for s in data["top3_secteurs"] if "Surp" in str(s.get("signal",""))) or "—"
    _sous_noms_rot = data.get("sous_noms") or " \xb7 ".join(
        s[0] for s in data["secteurs"] if "Sous" in str(s[3])) or "aucun"
    _neutre_parts = [s[0] for s in data["secteurs"] if "Surp" not in str(s[3]) and "Sous" not in str(s[3])]
    if len(_neutre_parts) > 5:
        _neutre_noms = " \xb7 ".join(_neutre_parts[:5]) + f" (et {len(_neutre_parts)-5} autres)"
    else:
        _neutre_noms = " \xb7 ".join(_neutre_parts) or "\u2014"
    elems.append(Spacer(1, 4*mm))
    elems.append(Paragraph("Positionnement de cycle recommande", S_SUBSECTION))
    cycle_data = [
        ["Phase actuelle",
         data.get("phase_cycle", "Expansion avancee"),
         "Croissance positive, taux restrictifs, marges sous pression sélective"],
        ["Secteurs a Surpondérer", _surp_noms_rot.replace("/", "\xb7"),
         "Forte visibilité BPA, faible Sensibilité aux taux, pricing power intact"],
        ["Secteurs a neutraliser", _neutre_noms,
         "Croissance correcte mais risque de décélération si PIB ralentit"],
        ["Secteurs a alléger", _sous_noms_rot.replace("/", "\xb7"),
         "Signal de vente relatif — compression de multiple anticipee"],
        ["Catalyseur de rotation", "Confirmation pivot Fed (<2,5% CPI sur 3M)",
         "R\u00e9\u00e9valuer les signaux en Sous-pond\u00e9rer en premier si pivot se confirme"],
    ]
    cycle_h = [Paragraph(h, S_TH_L) for h in ["Element","Verdict","Rationale"]]
    cycle_rows = [[Paragraph(r[0], S_TD_B), Paragraph(r[1], S_TD_L), Paragraph(r[2], S_TD_L)]
                  for r in cycle_data]
    # [38, 52, 80] = 170
    elems.append(KeepTogether(tbl([cycle_h] + cycle_rows, cw=[38*mm, 52*mm, 80*mm])))
    elems.append(src(
        "FinSight IA — Modèle cycle interne. Indicateurs : ISM, courbe taux, Leading indicators OCDE."))
    return elems


def _build_allocation(data, allocation_buf=None, registry=None):
    """Section 5 — Allocation Optimale : Min-Variance, Tangency, ERC."""
    elems = []
    elems.append(CondPageBreak(120*mm))
    elems.append(Spacer(1, 6*mm))
    if registry is not None: elems.append(SectionAnchor('allocation', registry))
    elems += section_title(_ilbl("allocation"), 5)
    elems.append(Spacer(1, 3*mm))

    opt = data.get("optimal_portfolios", {})
    _erp    = data.get("erp", "—")
    _esig   = data.get("erp_signal", "—")
    _rf     = data.get("rf_rate", "4.50%")

    elems.append(Paragraph(
        "A partir de la matrice de correlation sectorielle (rendements journaliers 52S) "
        "et des volatilités annualisées, trois portefeuilles optimaux sont construits "
        "selon la th\u00e9orie moderne du portefeuille (Markowitz, 1952). "
        "Chaque portefeuille r\u00e9pond \u00e0 un objectif distinct : "
        "<b>minimisation du risque</b> (Min-Variance), "
        "<b>maximisation du ratio risque/rendement</b> (Tangency / Max Sharpe), "
        "et <b>\u00e9galit\u00e9 de la contribution au risque</b> par secteur (Equal Risk Contribution). "
        f"Taux sans risque : {_rf} (10Y US Treasury). "
        f"Contexte ERP : {_erp} ({_esig}).", S_BODY))
    elems.append(Spacer(1, 3*mm))

    if not opt or not opt.get("sectors"):
        elems.append(Paragraph(
            "Optimisation non disponible pour cet indice — les portefeuilles Mean-Variance "
            "reposent sur les ETF SPDR sectoriels (XLK, XLV, XLF…) dont les donn\u00e9es "
            "de rendement journalier sont propres au march\u00e9 US. "
            "Pour le S&amp;P 500, cette section affiche les trois portefeuilles optimaux "
            "avec poids cibles et ratios de Sharpe.", S_BODY))
        return elems

    sectors = opt["sectors"]
    w_mv    = opt["min_var"]["weights"]
    w_tg    = opt["tangency"]["weights"]
    w_erc   = opt["erc"]["weights"]
    eq_w    = round(100 / len(sectors), 1)
    n_s     = len(sectors)

    # Chart allocation
    if allocation_buf is not None:
        # Source adaptatif : ETF SPDR pour S&P 500, synthetic sector
        # returns pour les autres indices (DAX/CAC/FTSE/etc.)
        _univ = data.get("indice", "") or data.get("universe", "")
        if "S&P 500" in _univ or "SP 500" in _univ:
            _source_base = "ETF SPDR S&amp;P 500"
        else:
            _source_base = f"returns sectoriels synthétiques ({_univ})"
        elems.append(Image(allocation_buf, width=TABLE_W, height=82*mm))
        elems.append(src(
            f"FinSight IA — Optimisation Markowitz sur {_source_base}. "
            "Rendements historiques 52S. Contrainte max 40% par secteur. "
            f"Ligne rouge pointillee = poids egal ({_frp(eq_w)})."))
        elems.append(Spacer(1, 4*mm))

    # Tableau des poids
    elems.append(Paragraph("Poids cibles par secteur (%)", S_SUBSECTION))
    alloc_h = [Paragraph(h, S_TH_C) for h in
               ["Secteur", "Min-Variance", "Tangency", "ERC", "Signal FinSight"]]
    alloc_rows = []
    for i, nom in enumerate(sectors):
        _w_mv  = w_mv[i]  if i < len(w_mv)  else 0
        _w_tg  = w_tg[i]  if i < len(w_tg)  else 0
        _w_erc = w_erc[i] if i < len(w_erc) else 0
        # Signal de surponderabilite : si 2/3 portfolios > egal
        _votes = sum([1 for w in [_w_mv, _w_tg, _w_erc] if w > eq_w * 0.9])
        _sig_a = (S_TD_G if _votes >= 2 else (S_TD_R if _votes == 0 else S_TD_A))
        _sig_t = ("Surpondérer" if _votes >= 2 else ("Sous-pondérer" if _votes == 0 else "Neutre"))
        def _w(v): return Paragraph(_frp(v), S_TD_G if v > eq_w else (S_TD_R if v < eq_w*0.6 else S_TD_A))
        alloc_rows.append([
            Paragraph(nom, S_TD_B),
            _w(_w_mv), _w(_w_tg), _w(_w_erc),
            Paragraph(_sig_t, _sig_a),
        ])
    # [46, 28, 28, 28, 40] = 170mm
    elems.append(KeepTogether(tbl([alloc_h] + alloc_rows, cw=[46*mm,28*mm,28*mm,28*mm,40*mm])))
    elems.append(Spacer(1, 4*mm))

    # Metriques des 3 portefeuilles
    elems.append(Paragraph("Performances attendues (historiques 52S)", S_SUBSECTION))
    met_h = [Paragraph(h, S_TH_C) for h in
             ["Portefeuille", "Objectif", "Return attendu", "Volatilite", "Ratio de Sharpe"]]
    def _sr(sh):
        try:
            sh = float(sh)
            return S_TD_G if sh >= 0.8 else (S_TD_R if sh < 0.4 else S_TD_A)
        except Exception: return S_TD_C

    def _opt_get(key, field, fmt="{:+.1f}%", default="\u2014"):
        try:
            v = opt.get(key, {}).get(field)
            if v is None:
                return default
            return fmt.format(float(v))
        except Exception: return default

    met_rows = [
        [Paragraph("Min-Variance", S_TD_B),
         Paragraph("Minimiser le risque — profil conservateur", S_TD_L),
         Paragraph(_opt_get('min_var', 'return'), S_TD_C),
         Paragraph(_opt_get('min_var', 'vol', "{:.1f}%"), S_TD_C),
         Paragraph(_opt_get('min_var', 'sharpe', "{:.2f}"), _sr(opt.get('min_var', {}).get('sharpe', 0)))],
        [Paragraph("Tangency", S_TD_B),
         Paragraph("Maximiser le Sharpe — optimum risque/rendement", S_TD_L),
         Paragraph(_opt_get('tangency', 'return'), S_TD_C),
         Paragraph(_opt_get('tangency', 'vol', "{:.1f}%"), S_TD_C),
         Paragraph(_opt_get('tangency', 'sharpe', "{:.2f}"), _sr(opt.get('tangency', {}).get('sharpe', 0)))],
        [Paragraph("Equal Risk Contribution", S_TD_B),
         Paragraph("Contribution egale au risque — profil diversifié", S_TD_L),
         Paragraph(_opt_get('erc', 'return'), S_TD_C),
         Paragraph(_opt_get('erc', 'vol', "{:.1f}%"), S_TD_C),
         Paragraph(_opt_get('erc', 'sharpe', "{:.2f}"), _sr(opt.get('erc', {}).get('sharpe', 0)))],
    ]
    # [38, 68, 20, 20, 24] = 170mm
    elems.append(KeepTogether(tbl([met_h] + met_rows, cw=[38*mm,68*mm,20*mm,20*mm,24*mm])))
    elems.append(Paragraph(
        f"<i>Note : performances et Sharpe calculés sur rendements historiques 52 semaines. "
        f"Ils ne constituent pas une prévision. Dans un contexte ERP {_esig} ({_erp}), "
        + ("le Tangency portfolio est particulièrement pertinent — la prime actions justifié "
           "une exposition optimisee." if _esig == "Favorable"
           else "le Min-Variance est recommande — proteger le capital prime sur le rendement." if _esig == "Tendu"
           else "les trois profils sont valides selon l'horizon et le profil de risque.")
        + "</i>", S_NOTE))
    elems.append(src(
        "FinSight IA — Markowitz (1952). Optimisation scipy SLSQP. "
        "Contraintes : poids 0-40% par secteur, somme = 100%."))
    return elems


def _build_top3(data, donut_buf, registry=None):
    indice_rl = data["indice"].replace("&", "&amp;")
    secteurs  = data["secteurs"]
    elems = []
    elems.append(CondPageBreak(120*mm))
    elems.append(Spacer(1, 6*mm))
    if registry is not None: elems.append(SectionAnchor('top3', registry))
    elems += section_title(_ilbl("top3"), 6)
    elems.append(Spacer(1, 3*mm))

    _surp_list = [s for s in data["secteurs"] if s[3] in ("Surpondérer", "Surpond\xe9rer")]
    nb_surp_reel = len(_surp_list)
    _surp_label = (f"{nb_surp_reel} secteur(s) affichent un signal <b>Surpond\u00e9rer</b>"
                   if nb_surp_reel > 0
                   else "aucun secteur ne franchit le seuil Surpond\u00e9rer")
    _n_comp = len(data["top3_secteurs"]) - nb_surp_reel
    if _n_comp > 0:
        _comp_s = ("secteur Neutre est présente en complément"
                   if _n_comp == 1
                   else f"{_n_comp} secteurs Neutrès sont présentés en complément")
        _complement = f" Le {_comp_s}."
    else:
        _complement = ""
    _nb_s_tot = data['nb_secteurs']
    _s_tot_lbl = "secteur couvert" if _nb_s_tot == 1 else "secteurs couverts"
    elems.append(Paragraph(
        f"Sur {_nb_s_tot} {_s_tot_lbl}, {_surp_label}.{_complement} "
        "Ces secteurs combinent momentum prix positif, révision haussière des BPA et "
        "valorisation raisonnable par rapport \u00e0 leur historique. "
        "Pour le d\u00e9tail complet — ratios LTM/NTM, Football Field, DCF, FinBERT — "
        "lancer l'analyse sectorielle d\u00e9di\u00e9e dans FinSight IA.", S_BODY))
    elems.append(Spacer(1, 4*mm))

    # Tableau Synthèse
    _titre_synth = ("Vue d'ensemble — Secteurs Surpond\u00e9rer" if nb_surp_reel > 0
                    else "Vue d'ensemble — Meilleurs secteurs de l'univers")
    elems.append(Paragraph(_titre_synth, S_SUBSECTION))
    synth_h = [Paragraph(h, S_TH_C) for h in
               ["Secteur","Signal","Score","EV/EBITDA","Mg. EBITDA","Croiss.","Momentum"]]
    synth_rows = []
    for sect in data["top3_secteurs"]:
        s_data = next((s for s in secteurs if s[0] == sect["nom"]), None)
        mg_raw = s_data[5] if s_data and len(s_data) > 5 else None
        mg   = f"{mg_raw:.1f}%" if isinstance(mg_raw, (int, float)) and mg_raw != 0.0 else "\u2014"
        croi = str(s_data[6]) if s_data and len(s_data) > 6 else "\u2014"
        mom  = str(s_data[7]) if s_data and len(s_data) > 7 else "\u2014"
        synth_rows.append([
            Paragraph(f"<b>{_abbrev_pdf(sect['nom'])}</b>", S_TD_B),
            Paragraph(sect["signal"], sig_s(sect["signal"])),
            Paragraph(str(sect["score"]), S_TD_BC),
            Paragraph(sect["ev_ebitda"], S_TD_C),
            Paragraph(mg, S_TD_C),
            Paragraph(croi, S_TD_G if '+' in str(croi) else S_TD_R),
            Paragraph(mom,  S_TD_G if '+' in str(mom)  else S_TD_R),
        ])
    # [40, 28, 14, 22, 22, 22, 22] = 170
    elems.append(KeepTogether(tbl([synth_h] + synth_rows,
        cw=[40*mm, 28*mm, 14*mm, 22*mm, 22*mm, 22*mm, 22*mm])))
    _has_proxy_pdf = data.get("etf_proxy_ev_ebitda") is not None
    _src_note = ("FinSight IA — FMP, yfinance. EV/EBITDA et marges = m\u00e9dianes LTM."
                 + (" * = EV/EBITDA via ETF proxy (indice)." if _has_proxy_pdf else ""))
    elems.append(src(_src_note))
    elems.append(Spacer(1, 4*mm))

    # Donut gauche + textes analytiques LLM droite
    donut_img = Image(donut_buf, width=82*mm, height=86*mm)

    # Génération LLM du texte analytique pour les secteurs recommandés
    _top3_llm_text = ""
    try:
        from core.llm_provider import LLMProvider
        import json as _json, re as _re
        _llm = LLMProvider(provider="groq", model="llama-3.3-70b-versatile")
        _sect_desc = "\n".join(
            f"- {s['nom']} : score {s['score']}/100, signal {s['signal']}, "
            f"EV/EBITDA {s['ev_ebitda']}, catalyseur={s.get('catalyseur','')}, risque={s.get('risque','')}"
            for s in data["top3_secteurs"]
        )
        _top3_prompt = (
            f"Tu es un analyste sell-side senior. Rédige une analyse concise (250 mots) des "
            f"secteurs recommandés de l'indice {data.get('indice', '')} :\n{_sect_desc}\n\n"
            f"RÈGLES : français correct avec accents, prose technique, cite les chiffres. "
            f"Pas de markdown **, pas d'emojis. Structure en 3 paragraphes courts "
            f"(un par secteur) avec drivers, risques et conviction."
        )
        _top3_llm_text = _llm.generate(_top3_prompt, max_tokens=600) or ""
        # Strip markdown ** et * que certains LLM insèrent malgré la consigne
        _top3_llm_text = _re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', _top3_llm_text)
        # Italiques *mot* -> <i>mot</i> (garder single * comme markdown minimal)
        _top3_llm_text = _re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<i>\1</i>', _top3_llm_text)
        _top3_llm_text = _top3_llm_text.replace('**', '').replace('##', '').replace('###', '')
    except Exception as _llm_err:
        import logging as _log_m
        _log_m.getLogger(__name__).warning("[indice_pdf] top3 LLM: %s", _llm_err)

    if not _top3_llm_text.strip():
        # Fallback : texte structuré depuis les données
        analyses_lines = []
        for sect in data["top3_secteurs"]:
            cat = sect.get("catalyseur", "")
            rsk = sect.get("risque", "")
            analyses_lines.append(
                f"<b>{sect['nom']}</b> — {sect['signal']} \xb7 Score {sect['score']} \xb7 "
                f"EV/EBITDA {sect['ev_ebitda']}<br/>"
                f"Catalyseur : {cat}<br/>"
                f"Risque : {rsk}<br/><br/>"
            )
        _top3_llm_text = "".join(analyses_lines)

    analyses_text = _top3_llm_text
    donut_row = Table([[donut_img, Paragraph(analyses_text, S_BODY)]],
                      colWidths=[82*mm, 88*mm])
    donut_row.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING",   (0,0),(-1,-1), 0), ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ("TOPPADDING",    (0,0),(-1,-1), 0), ("BOTTOMPADDING", (0,0),(-1,-1), 0),
        ("LEFTPADDING",   (1,0),(1,0),   6),
    ]))
    elems.append(donut_row)
    elems.append(src(
        f"FinSight IA — Pond\u00e9rations GICS {data['date_analyse']}. "
        "Analyses g\u00e9n\u00e9r\u00e9es par l'agent Synth\u00e8se."))
    elems.append(Spacer(1, 5*mm))

    # Tableau 9 sociétés — colonne EV/EBITDA ou Mg.EBITDA selon dispo
    _all_ev_missing = all(
        str(s.get("ev_ebitda","—")) in ("—","\u2014","","None")
        for s in data.get("top3_secteurs",[])
    )
    _ev_col_lbl = "Mg.EBITDA" if _all_ev_missing else "EV/EBITDA"
    soc_h = [Paragraph(h, S_TH_C) for h in
             ["Secteur","Ticker","Signal", _ev_col_lbl,"Score"]]
    soc_rows = []
    for sect in data["top3_secteurs"]:
        _mg      = sect.get("mg_ebitda", 0) or 0
        _sect_ev = str(sect.get("ev_ebitda", "\u2014"))
        _sect_ev_ok = _sect_ev not in ("\u2014", "—", "", "None")
        _ev_sect = (f"{_mg:.1f}%" if _all_ev_missing and _mg else "\u2014")
        for tkr, sig, ev, score in (sect.get("societes") or sect.get("societes") or []):
            if _all_ev_missing:
                _val_disp = _ev_sect
            elif str(ev) in ("\u2014", "—", "", "None") and _sect_ev_ok:
                # Fallback : EV/EBITDA secteur comme proxy si le ticker n'a pas de valeur
                _val_disp = f"~{_sect_ev}"
            else:
                _val_disp = ev
            soc_rows.append([
                Paragraph(_abbrev_pdf(sect["nom"]), S_TD_L),
                Paragraph(f"<b>{tkr}</b>", S_TD_BC),
                Paragraph(sig, sig_s(sig)),
                Paragraph(_val_disp, S_TD_C),
                Paragraph(str(score), S_TD_C),
            ])
    # [52, 20, 36, 28, 34] = 170
    soc_tbl = tbl([soc_h] + soc_rows, cw=[52*mm, 20*mm, 36*mm, 28*mm, 34*mm])
    elems.append(KeepTogether([
        Paragraph("Soci\u00e9t\u00e9s représentatives — 3 convictions par secteur *", S_SUBSECTION),
        Spacer(1, 2*mm),
        Paragraph(
            "Ces sociétés constituent les convictions les plus solides au sein de chaque "
            "secteur Surpond\u00e9rer. Le score FinSight int\u00e8gre momentum, r\u00e9visions BPA et "
            "valorisation relative.", S_BODY),
        Spacer(1, 2*mm),
        soc_tbl,
    ]))
    elems.append(src(
        "FinSight IA — Sociétés sélectionnées par capitalisation et signal FinSight. "
        "Score = composite 0-100. Analyse complète via module société ou sectoriel."))
    elems.append(Paragraph(
        "* Pour une analyse approfondie et rigoureuse (Football Field, DCF complet, Altman Z-Score, "
        "FinBERT news) — lancer l'analyse soci\u00e9t\u00e9 individuelle dans FinSight IA.",
        S_NOTE))
    return elems


def _build_risques(data, registry=None):
    indice_rl = data["indice"].replace("&", "&amp;")
    elems = []
    elems.append(CondPageBreak(120*mm))
    elems.append(Spacer(1, 6*mm))
    if registry is not None: elems.append(SectionAnchor('risques', registry))
    elems += section_title(_ilbl("risques_macro"), 7)

    sig_central = data["signal_global"]
    elems.append(Paragraph(
        f"L'analyse adversariale identifie trois axes de risque susceptibles d'invalider "
        f"le scénario central <b>{sig_central}</b> sur le {indice_rl}. Notre approche ne traite "
        "pas ces risques comme des probabilités faibles a ignorer, mais comme des "
        "<b>conditions de surveillance active</b> qui doivent modifier le positionnément "
        "si elles se materialisent. Chaque risque est évalue sur sa probabilité estimée "
        "a 12 mois, son mecanisme de transmission et son impact potentiel sur les niveaux "
        "de l'indice et les multiples.", S_BODY))
    elems.append(Spacer(1, 2*mm))

    for nom, mec, prob, impact in data["risques"]:
        # Fix 2026-04-15 : regex robuste pour tous formats LLM
        import re as _re_ird
        _m_ird = _re_ird.search(r'(\d+)', str(prob).replace('%','').replace('pct',''))
        p_int = int(_m_ird.group(1)) if _m_ird else 30
        _prob_qualif = ("élevée" if p_int >= 40 else ("modérée" if p_int >= 25 else "faible"))
        elems.append(Paragraph(
            f"<b>{nom} ({prob}, impact {impact.lower()}).</b> {mec} "
            f"La probabilité de materialisation sur 12 mois est jugee {_prob_qualif}.", S_BODY))
        elems.append(Spacer(1, 2*mm))
    elems.append(src(
        f"FinSight IA — Analyse adversariale. Probabilités estimées au {data['date_analyse']}."))
    elems.append(Spacer(1, 4*mm))

    elems.append(debate_q(
        f"Quelles conditions invalideraient le signal {sig_central} et vers quel scénario ?"))
    inv_h = [Paragraph(h, S_TH_L) for h in
             ["Sc\u00e9nario","Condition d\u00e9clencheur","Signal r\u00e9sultant","Horizon"]]
    inv_data = [[s[0], s[1], s[2], s[3]] for s in (data.get("scenarios") or [
        ("Bull case", "Score > 60 + BPA NTM > +8% YoY", "Surpond\u00e9rer", "3-6 mois"),
        ("Bear case", "Score < 40 via r\u00e9cession ou choc g\u00e9opolitique", "Sous-pond\u00e9rer", "6-12 mois"),
        ("Stagflation", "CPI > 3,5% + PIB < 1%", "Sous-pond\u00e9rer s\u00e9lectif", "6-9 mois"),
    ])]

    def inv_signal_s(v):
        if "Surpond" in v: return S_TD_G
        if "Sous-pond" in v: return S_TD_R
        return S_TD_A

    inv_rows = [[Paragraph(r[0], S_TD_B), Paragraph(r[1], S_TD_L),
                 Paragraph(r[2], inv_signal_s(r[2])), Paragraph(r[3], S_TD_C)]
                for r in inv_data]
    # [24, 82, 40, 24] = 170 — compact pad 3mm, Horizon 24mm = 18mm texte
    elems.append(KeepTogether(tbl([inv_h] + inv_rows,
        cw=[24*mm, 82*mm, 40*mm, 24*mm], compact=True)))
    elems.append(src(
        "FinSight IA — Sc\u00e9narios alternatifs. Conditions \u00e0 r\u00e9\u00e9valuer \u00e0 chaque rapport mensuel."))
    elems.append(Spacer(1, 4*mm))
    elems.append(Paragraph("Gestion du risque portefeuille", S_SUBSECTION))
    # Texte LLM dynamique basé sur le contexte concret de l'indice — remplace
    # le fallback hardcoded generique signale par Baptiste
    _risk_text = data.get("texte_gestion_risque", "")
    if not _risk_text.strip():
        try:
            import sys as _sys, os as _os
            _sys.path.insert(0, _os.path.dirname(_os.path.dirname(__file__)))
            from core.llm_provider import LLMProvider
            _llm_r = LLMProvider(provider="groq", model="llama-3.3-70b-versatile")
            # Contexte chiffre : signal central, nb secteurs, surponderes, phase cycle
            _sec_surp = [s[0] for s in data.get("secteurs", [])
                         if len(s) > 3 and "Surp" in str(s[3])]
            _sec_sous = [s[0] for s in data.get("secteurs", [])
                         if len(s) > 3 and "Sous" in str(s[3])]
            _phase = data.get("phase_cycle", "n/d")
            _nb_surp = len(_sec_surp)
            _nb_sous = len(_sec_sous)
            _surp_str = ", ".join(_sec_surp[:3]) if _sec_surp else "aucun"
            _sous_str = ", ".join(_sec_sous[:3]) if _sec_sous else "aucun"
            _prompt_r = (
                f"Tu es un g\u00e9rant buy-side senior. R\u00e9dige un commentaire "
                f"(200-240 mots) de gestion de risque portefeuille pour le {indice_rl} "
                f"dans le sc\u00e9nario central {sig_central}.\n\n"
                f"Contexte : phase de cycle {_phase}, {_nb_surp} secteurs en Surpond\u00e9rer "
                f"({_surp_str}), {_nb_sous} en Sous-pond\u00e9rer ({_sous_str}).\n\n"
                f"Structure en 2 paragraphes :\n"
                f"1. Positionnement recommand\u00e9 (sur/sous-pond\u00e9rations sectorielles, "
                f"niveau de beta portefeuille, couvertures d\u00e9fensives)\n"
                f"2. Triggers de r\u00e9vision de l'allocation (niveaux de risque macro a "
                f"surveiller, conditions qui feraient basculer vers un profil plus "
                f"d\u00e9fensif ou offensif)\n\n"
                f"Francais correct avec accents. Pas de markdown. Pas d'emojis. "
                f"Cite les secteurs par leur nom francais, pas l'anglais."
            )
            _risk_text = _llm_r.generate(_prompt_r, max_tokens=600) or ""
        except Exception as _e:
            log.debug(f"[indice_pdf_writer:inv_signal_s] exception skipped: {_e}")
    if not _risk_text.strip():
        _risk_text = (
            f"Dans le sc\u00e9nario central, le {indice_rl} \u00e9volue dans une fourchette "
            f"cible sur 12 mois. Le portefeuille mod\u00e8le recommande une surexposition "
            f"s\u00e9lective sur les secteurs identifi\u00e9s comme Surpond\u00e9rer, une "
            f"couverture partielle via les secteurs d\u00e9fensifs en cas de choc, et une "
            f"r\u00e9duction tactique du beta si les conditions macro se d\u00e9t\u00e9riorent. "
            f"La prochaine revue est programmee dans 30 jours."
        )
    elems.append(Paragraph(_risk_text, S_BODY))
    return elems


def _build_sentiment(data, registry=None):
    indice_rl = data["indice"].replace("&", "&amp;")
    fb = data["finbert"]
    elems = []
    elems.append(CondPageBreak(120*mm))
    elems.append(Spacer(1, 6*mm))
    if registry is not None: elems.append(SectionAnchor('sentiment', registry))
    elems += section_title(_ilbl("sentiment_method"), 8)

    if fb["nb_articles"] == 0:
        elems.append(Paragraph(
            "L'analyse de sentiment FinBERT n'est pas disponible dans le cadre du screening "
            "d'indice. Le modèle FinBERT est active lors des analyses sectorielles ou "
            "société individuelles, ou il traite les flux RSS et Finnhub propres a chaque "
            "valeur. Pour acceder au sentiment sectoriel detaille, lancer l'analyse "
            "sectorielle dediee depuis FinSight IA.", S_BODY))
        elems.append(Spacer(1, 4*mm))
    else:
        elems.append(Paragraph(
            f"L'analyse FinBERT conduite sur <b>{fb['nb_articles']} articles</b> des sept derniers "
            f"jours produit un sentiment agrege de <b>{fb['score_agrege']}</b> sur l'ensemble du "
            f"{indice_rl}. Les publications favorables portent sur : {fb['positif']['themes']}. "
            f"Les signaux négatifs se concentrent sur : {fb['négatif']['themes']}.", S_BODY))
        elems.append(Spacer(1, 3*mm))

        # Distribution globale — [24, 20, 26, 100] = 170
        sent_h = [Paragraph(h, S_TH_C) for h in
                  ["Orientation","Articles","Score moyen","Thèmes dominants"]]
        sent_rows = [
            [Paragraph("Positif",  S_TD_G),
             Paragraph(str(fb["positif"]["nb"]),  S_TD_C),
             Paragraph(fb["positif"]["score"],    S_TD_G),
             Paragraph(fb["positif"]["themes"],   S_TD_L)],
            [Paragraph("Neutre",   S_TD_A),
             Paragraph(str(fb["neutre"]["nb"]),   S_TD_C),
             Paragraph(fb["neutre"]["score"],     S_TD_C),
             Paragraph(fb["neutre"]["themes"],    S_TD_L)],
            [Paragraph("Négatif",  S_TD_R),
             Paragraph(str(fb["négatif"]["nb"]),  S_TD_C),
             Paragraph(fb["négatif"]["score"],    S_TD_R),
             Paragraph(fb["négatif"]["themes"],   S_TD_L)],
        ]
        elems.append(KeepTogether(tbl([sent_h] + sent_rows, cw=[24*mm, 20*mm, 26*mm, 100*mm])))
        elems.append(src(
            f"FinBERT — Corpus presse financière anglophone. {fb['nb_articles']} articles, 7 jours."))
        elems.append(Spacer(1, 4*mm))

        # Sentiment par secteur — deux colonnes côte à côte
        elems.append(Paragraph("Sentiment FinBERT — Distribution par secteur", S_SUBSECTION))
        ps_h = [Paragraph(h, S_TH_C) for h in ["Secteur","Score moyen","Orientation"]]
        ps_rows = []
        for sect, score, orient in fb["par_secteur"]:
            os_ = S_TD_G if orient == "Positif" else (S_TD_R if orient in ("Négatif","N\xe9gatif") else S_TD_C)
            try:
                sc_s = S_TD_G if float(score) > 0 else (S_TD_R if float(score) < -0.10 else S_TD_C)
            except ValueError:
                sc_s = S_TD_C
            ps_rows.append([Paragraph(sect, S_TD_B), Paragraph(score, sc_s), Paragraph(orient, os_)])

        mid = len(ps_rows) // 2
        left_rows  = ps_rows[:mid + 1]
        right_rows = ps_rows[mid + 1:]
        while len(right_rows) < len(left_rows):
            right_rows.append([Paragraph("", S_TD_C)] * 3)

        # Sous-tableaux : [45, 20, 20] = 85mm chacun
        def _mini_tbl(hdr, rows, cw):
            t = Table([hdr] + rows, colWidths=cw)
            t.setStyle(TableStyle([
                ('BACKGROUND',    (0,0),(-1,0),  NAVY),
                ('ROWBACKGROUNDS',(0,1),(-1,-1), [WHITE, ROW_ALT]),
                ('FONTNAME',      (0,0),(-1,0),  'Helvetica-Bold'),
                ('FONTSIZE',      (0,0),(-1,-1), 8),
                ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
                ('TOPPADDING',    (0,0),(-1,-1), 3),
                ('BOTTOMPADDING', (0,0),(-1,-1), 3),
                ('LEFTPADDING',   (0,0),(-1,-1), 5),
                ('RIGHTPADDING',  (0,0),(-1,-1), 5),
                ('GRID',          (0,1),(-1,-1), 0.3, GREY_MED),
            ]))
            return t

        left_tbl  = _mini_tbl(ps_h, left_rows,  [45*mm, 20*mm, 20*mm])
        right_tbl = _mini_tbl(ps_h, right_rows, [45*mm, 20*mm, 20*mm])
        # [85, 85] = 170
        two_col = Table([[left_tbl, right_tbl]], colWidths=[85*mm, 85*mm])
        two_col.setStyle(TableStyle([
            ("VALIGN",        (0,0),(-1,-1), "TOP"),
            ("LEFTPADDING",   (0,0),(-1,-1), 0), ("RIGHTPADDING",  (0,0),(-1,-1), 0),
            ("TOPPADDING",    (0,0),(-1,-1), 0), ("BOTTOMPADDING", (0,0),(-1,-1), 0),
            ("LEFTPADDING",   (1,0),(1,0),   6),
        ]))
        elems.append(two_col)
        elems.append(src(
            "FinBERT — Score par secteur = moyenne pondérée des articles mentionnant le secteur."))
        elems.append(Spacer(1, 4*mm))

    # Méthodologie — [40, 130] = 170
    elems.append(Paragraph("Sources &amp; M\u00e9thodologie", S_SUBSECTION))
    meth_h = [Paragraph(h, S_TH_L) for h in ["Composante","M\u00e9thodologie"]]
    meth_rows = [[Paragraph(k, S_TD_B), Paragraph(v, S_TD_L)]
                 for k, v in (data.get("Méthodologie") or data.get("Méthodologie") or [])]
    elems.append(KeepTogether(tbl([meth_h] + meth_rows, cw=[40*mm, 130*mm])))
    elems.append(src(
        f"FinSight IA v1.0 — Mise \u00e0 jour quotidienne. Donn\u00e9es au {data['date_analyse']}."))
    return elems


def _build_disclaimer(data):
    elems = []
    elems.append(CondPageBreak(120*mm))
    elems.append(Spacer(1, 6*mm))
    elems.append(rule())
    S_DISC_TITLE = _style('disc_title', size=6.5, leading=9, color=GREY_TEXT, bold=True)
    elems.append(Paragraph(
        "INFORMATIONS RÉGLEMENTAIRES ET AVERTISSEMENTS IMPORTANTS", S_DISC_TITLE))
    elems.append(Spacer(1, 1.5*mm))
    elems.append(Paragraph(
        f"<b>Nature du document.</b> Ce rapport a été Généré automatiquement par FinSight IA v1.0 "
        f"le {data['date_analyse']}. Il est produit intégralement par un systeme d'intelligence "
        "artificielle et <b>ne constitue pas un conseil en investissement</b> au sens de la "
        "directive européenne MiFID II (2014/65/UE) ni au sens de toute autre réglementation "
        "applicable. FinSight IA n'est pas un prestataire de services d'investissement agréé. "
        "Ce document est fourni a titre informatif uniquement et ne saurait être interprète "
        "comme une recommandation personnalisee d'achat, de vente ou de conservation de tout "
        "instrument financier.", S_DISC))
    elems.append(Spacer(1, 1.5*mm))
    elems.append(Paragraph(
        "<b>Conflits d'intérêt.</b> FinSight IA est un outil d'analyse automatise sans position "
        "proprietaire dans les titrès ou indices couverts. Aucune rémunération n'est percue de "
        "la part des Émetteurs analyses. Nonobstant, le lecteur est invite a considerer que tout "
        "modèle analytique comporte des biais inherents a ses hypotheses de construction.", S_DISC))
    elems.append(Spacer(1, 1.5*mm))
    elems.append(Paragraph(
        "<b>Fiabilite des Données.</b> Les Données financières sont issues de sources publiques "
        "(yfinance, Financial Modeling Prep, Finnhub) et de modèles internes. Malgre les "
        "contrôles appliques, ces Données peuvent contenir des inexactitudes, des délais ou "
        "des erreurs. Les projections et estimations présentées reposent sur des hypotheses "
        "qui peuvent ne pas se réaliser. Les performances passees ne prejudgent pas des "
        "performances futures.", S_DISC))
    elems.append(Spacer(1, 1.5*mm))
    elems.append(Paragraph(
        "<b>Restrictions de diffusion.</b> Ce document est strictement confidentiel et destine "
        "exclusivement a son destinataire. Il ne peut être reproduit, distribue ou communique "
        "a des tiers sans autorisation expresse. Sa diffusion peut être soumise a des "
        "restrictions legales dans certaines juridictions. FinSight IA décline toute "
        "responsabilité pour les Décisions prises sur la base de ce document. Tout investisseur "
        "est invite a proceder a sa propre analyse et a consulter un conseiller financier "
        "qualifie avant toute Décision d'investissement. — <b>Document confidentiel.</b>", S_DISC))
    return elems


# ─── STORY BUILDER ────────────────────────────────────────────────────────────
def _build_story(data, perf_buf, weights_buf, scatter_buf, scores_buf,
                 donut_buf, attribution_buf, corr_buf, allocation_buf, page_nums, registry):
    indice_rl = data["indice"].replace("&", "&amp;")
    story = []

    # Page 1 : cover (canvas pur)
    story.append(Spacer(1, 1))
    story.append(PageBreak())

    # Page 2 : sommaire
    story.append(Paragraph(
        f"{indice_rl} ({data['code']}) — Analyse d'Indice FinSight IA",
        _style('rt', size=13, bold=True, color=NAVY, leading=18, space_after=2)))
    story.append(Paragraph(
        f"Rapport confidentiel \xb7 {data['date_analyse']}",
        _style('rs', size=8, color=GREY_TEXT, leading=11, space_after=6)))
    story.append(rule())
    story.append(Paragraph(_ilbl("sommaire"), S_SECTION))
    story.append(_build_sommaire(data, page_nums))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("A propos de cette analyse", S_SUBSECTION))
    _nb_soc_intro = data.get("nb_societes") or data.get("nb_societes", "\u2014")
    _nb_sec_intro = data.get("nb_secteurs", "\u2014")
    story.append(Paragraph(
        f"Cette analyse d'indice couvre l'ensemble des {_nb_sec_intro} secteurs GICS du "
        f"{indice_rl} ({_nb_soc_intro} soci\u00e9t\u00e9s). Elle produit un signal global "
        "d'allocation sectorielle (Surpond\u00e9rer / Neutre / Sous-pond\u00e9rer) et un score composite "
        "par secteur. Les donn\u00e9es sont issues de yfinance, FMP et Finnhub. Le sentiment est "
        "analys\u00e9 par FinBERT sur 7 jours glissants. La m\u00e9thodologie compl\u00e8te est d\u00e9taill\u00e9e "
        "en section 7.", S_BODY))
    story.append(PageBreak())

    story += _build_synthese(data, perf_buf, registry)
    story += _build_cartographie(data, weights_buf, attribution_buf, registry)
    story += _build_graphiques(data, scatter_buf, scores_buf, corr_buf, registry)
    story += _build_rotation(data, registry)
    story += _build_allocation(data, allocation_buf, registry)
    story += _build_top3(data, donut_buf, registry)
    story += _build_risques(data, registry)
    story += _build_sentiment(data, registry)
    story += _build_disclaimer(data)
    return story


# ─── CLASSE PRINCIPALE ────────────────────────────────────────────────────────
class IndicePDFWriter:

    @staticmethod
    def generate(data: dict, output_path: str, language: str = "fr", currency: str = "EUR") -> str:
        """
        Genere le rapport PDF d'analyse d'indice FinSight IA.
        Retourne output_path. Double-passe pour pagination dynamique.
        """
        # i18n : stocker dans data + activer module-level
        data.setdefault("_language", language)
        data.setdefault("_currency", currency)
        global _INDICE_CURRENT_LANG
        _INDICE_CURRENT_LANG = (language or "fr").lower()[:2]
        if _INDICE_CURRENT_LANG not in {"fr","en","es","de","it","pt"}:
            _INDICE_CURRENT_LANG = "fr"
        # Macro regime_v + récession (si pas déjà calculé par app.py)
        if not data.get("macro"):
            try:
                import sys as _sys, os as _os
                _sys.path.insert(0, _os.path.dirname(_os.path.dirname(__file__)))
                from agents.agent_macro import AgentMacro
                data["macro"] = AgentMacro().analyze()
            except Exception as _me:
                import logging as _log
                _log.getLogger(__name__).warning("[IndicePDFWriter] AgentMacro: %s", _me)
                data.setdefault("macro", {})

        # Buffers graphiques (Générés une seule fois, rewound avant chaque passe)
        perf_buf        = make_indice_perf_chart(data)
        weights_buf     = make_sector_weights_chart(data)
        scatter_buf     = make_scatter_sectoriel(data)
        scores_buf      = make_score_bars(data)
        donut_buf       = make_top3_donut(data)
        attribution_buf = make_attribution_chart(data)
        corr_buf        = make_correlation_heatmap(data)
        allocation_buf  = make_allocation_chart(data)

        doc_kwargs = dict(
            pagesize=A4,
            leftMargin=MARGIN_L,
            rightMargin=MARGIN_R,
            topMargin=MARGIN_T + 6*mm,
            bottomMargin=MARGIN_B + 8*mm,
            title=f"FinSight IA — {data['indice']} Analyse d'Indice",
            author="FinSight IA v1.0",
        )

        def make_on_page(d):
            def on_page(c, doc):
                if doc.page == 1:
                    _cover_page(c, doc, d)
                else:
                    _content_header(c, doc, d)
            return on_page

        def _rewind(*bufs):
            for b in bufs:
                if b is not None:
                    b.seek(0)

        _all_bufs = (perf_buf, weights_buf, scatter_buf, scores_buf,
                     donut_buf, attribution_buf, corr_buf, allocation_buf)

        # Passe 1 — collecter numeros de page réels
        registry = {}
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp_path = tmp.name
        doc1 = SimpleDocTemplate(tmp_path, **doc_kwargs)
        _rewind(*_all_bufs)
        story1 = _build_story(data, perf_buf, weights_buf, scatter_buf, scores_buf,
                               donut_buf, attribution_buf, corr_buf, allocation_buf, {}, registry)
        doc1.build(story1, onFirstPage=make_on_page(data), onLaterPages=make_on_page(data))
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

        # Passe 2 — build final avec vrais numeros
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        doc2 = SimpleDocTemplate(output_path, **doc_kwargs)
        _rewind(*_all_bufs)
        story2 = _build_story(data, perf_buf, weights_buf, scatter_buf, scores_buf,
                               donut_buf, attribution_buf, corr_buf, allocation_buf, dict(registry), {})
        doc2.build(story2, onFirstPage=make_on_page(data), onLaterPages=make_on_page(data))

        print(f"Rapport indice Généré : {output_path}  |  Sections : {registry}")
        return output_path
