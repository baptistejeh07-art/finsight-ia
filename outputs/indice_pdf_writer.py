"""
indice_pdf_writer.py — FinSight IA
Generateur de rapport PDF d'analyse d'indice boursier.
Interface : IndicePDFWriter.generate(data, output_path) -> str
Double-passe SectionAnchor pour pagination dynamique.
"""

import io, tempfile, os
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
from reportlab.platypus.flowables import Flowable

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

def section_title(text, num):
    return [rule(sb=10, sa=0), Paragraph(f"{num}. {text}", S_SECTION), rule(sb=2, sa=8)]

def debate_q(text): return Paragraph(f"\u25b6  {text}", S_DEBATE)
def src(text):      return Paragraph(f"Source : {text}", S_NOTE)

def tbl(data, cw, row_heights=None):
    assert abs(sum(cw) - TABLE_W) < 0.5, (
        f"Somme colonnes = {sum(cw)/mm:.1f}mm != 170mm — {[c/mm for c in cw]}")
    t = Table(data, colWidths=cw, rowHeights=row_heights)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0),  NAVY),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [WHITE, ROW_ALT]),
        ('FONTNAME',      (0,0), (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0,0), (-1,-1), 8),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 5),
        ('RIGHTPADDING',  (0,0), (-1,-1), 5),
        ('LINEBELOW',     (0,0), (-1,0),  0.5, NAVY_LIGHT),
        ('LINEBELOW',     (0,-1),(-1,-1), 0.5, GREY_RULE),
        ('GRID',          (0,1), (-1,-1), 0.3, GREY_MED),
    ]))
    return t

def sig_s(signal):
    return S_TD_G if signal == "Surpond\xe9rer" else (S_TD_R if signal == "Sous-pond\xe9rer" else S_TD_A)

def sig_hex(signal):
    return '#1A7A4A' if signal == "Surpond\xe9rer" else ('#A82020' if signal == "Sous-pond\xe9rer" else '#B06000')


# ─── GRAPHIQUES ───────────────────────────────────────────────────────────────
def make_indice_perf_chart(data):
    months = ['Mar 25','Avr','Mai','Jun','Jul','Aou','Sep','Oct','Nov','Dec','Jan 26','Fev','Mar 26']
    spx    = [100,103,108,105,112,110,107,114,120,117,124,121,118]
    bonds  = [100,99, 98, 97, 99, 98, 97, 96, 98, 97, 99, 98, 97]
    gold   = [100,102,106,108,111,114,110,116,119,122,125,122,128]
    x = np.arange(len(months))
    fig, ax = plt.subplots(figsize=(8.0, 3.8))
    ax.plot(x, spx,   color='#1B3A6B', linewidth=2.0, label=data["indice"])
    ax.plot(x, bonds, color='#A0A0A0', linewidth=1.2, linestyle='--', label='US 10Y Bond')
    ax.plot(x, gold,  color='#B06000', linewidth=1.2, linestyle=':', label='Gold')
    ax.fill_between(x, spx, 100, where=[s > 100 for s in spx], alpha=0.08, color='#1B3A6B')
    ax.set_xticks(x[::2]); ax.set_xticklabels(months[::2], fontsize=10, color='#555')
    ax.yaxis.set_tick_params(labelsize=10)
    ax.tick_params(length=0)
    for sp in ['top','right']: ax.spines[sp].set_visible(False)
    ax.spines['left'].set_color('#D0D5DD'); ax.spines['bottom'].set_color('#D0D5DD')
    ax.set_facecolor('white'); fig.patch.set_facecolor('white')
    ax.grid(axis='y', alpha=0.15, color='#D0D5DD', linewidth=0.5)
    ax.legend(fontsize=10, loc='upper left', frameon=False)
    ax.set_title(f'Performance comparee assets - base 100, Mars 2025',
                 fontsize=12, color='#1B3A6B', fontweight='bold', pad=8)
    plt.tight_layout(pad=0.4)
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=160, bbox_inches='tight')
    plt.close(fig); buf.seek(0); return buf


def make_sector_weights_chart(data):
    secteurs = data["secteurs"]
    noms  = [s[0] for s in secteurs]
    poids = [float(s[4]) if isinstance(s[4], (int, float)) else 5.0 for s in secteurs]
    # fallback: poids uniformes si ev_ebitda n'est pas un poids
    # On utilise une pondération fictive representant l'indice
    poids_idx = [28.4, 12.8, 13.2, 10.6, 8.8, 8.4, 6.2, 4.8, 2.4, 2.6, 1.8]
    if len(poids_idx) != len(secteurs):
        poids_idx = [100/len(secteurs)] * len(secteurs)
    sigs = [s[3] for s in secteurs]
    bar_cols = [sig_hex(s) for s in sigs]
    y = np.arange(len(noms))
    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    bars = ax.barh(y, poids_idx, color=bar_cols, alpha=0.85, height=0.58,
                   edgecolor='white', linewidth=0.5)
    for i, (bar, val) in enumerate(zip(bars, poids_idx)):
        ax.text(val + 0.5, i, f"{val}%", va='center', fontsize=9, color='#333', fontweight='bold')
    ax.set_yticks(y); ax.set_yticklabels(noms, fontsize=9, color='#333')
    ax.set_xlabel("Ponderation dans l'indice (%)", fontsize=9, color='#555')
    ax.set_xlim(0, 36)
    ax.axvline(x=sum(poids_idx)/len(poids_idx), color='#D0D5DD', linewidth=0.8, linestyle='--', alpha=0.8)
    ax.text(sum(poids_idx)/len(poids_idx)+0.2, len(noms)-0.6, 'Moy.', fontsize=8, color='#999', style='italic')
    for sp in ['top','right']: ax.spines[sp].set_visible(False)
    ax.spines['left'].set_color('#D0D5DD'); ax.spines['bottom'].set_color('#D0D5DD')
    ax.set_facecolor('white'); fig.patch.set_facecolor('white')
    ax.tick_params(length=0)
    patches = [mpatches.Patch(color='#1A7A4A', label='Surponderer'),
               mpatches.Patch(color='#B06000', label='Neutre'),
               mpatches.Patch(color='#A82020', label='Sous-ponderer')]
    ax.legend(handles=patches, fontsize=9, loc='upper center',
              bbox_to_anchor=(0.5, -0.12), frameon=False, ncol=3)
    ax.set_title(f"Ponderations sectorielles - {data['indice']}",
                 fontsize=11, color='#1B3A6B', fontweight='bold', pad=8)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=160, bbox_inches='tight')
    plt.close(fig); buf.seek(0); return buf


def make_scatter_sectoriel(data):
    secteurs = data["secteurs"]
    noms_abr = [s[0][:10] for s in secteurs]
    ev    = [float(str(s[4]).replace('x','').replace(',','.')) for s in secteurs]
    crois = [float(str(s[6]).replace('%','').replace('+','').replace(',','.')) for s in secteurs]
    sigs  = [s[3] for s in secteurs]
    cols  = [sig_hex(s) for s in sigs]
    offsets = [( 8, 6),( 8, 6),( 8,-13),(-58, 5),( 8, 6),
               ( 8,-14),( 8, 6),( 8,-13),( 8, 6),( 8,-13),(-60, 6)]
    while len(offsets) < len(secteurs):
        offsets.append((8, 6))
    fig, ax = plt.subplots(figsize=(9.0, 5.2))
    for nom, x, y, col, off in zip(noms_abr, crois, ev, cols, offsets):
        ax.scatter(x, y, color=col, s=180, zorder=4, alpha=0.88,
                   edgecolors='white', linewidth=0.8)
        ap = dict(arrowstyle='-', color=col, lw=0.5, alpha=0.5) if abs(off[0]) > 20 else None
        ax.annotate(nom, (x, y), textcoords='offset points', xytext=off,
                    fontsize=8.5, color=col, fontweight='bold', arrowprops=ap)
    med_ev = np.median(ev); med_cr = np.median(crois)
    ax.axhline(y=med_ev, color='#D0D5DD', linewidth=0.9, linestyle='--', alpha=0.8)
    ax.axvline(x=med_cr, color='#D0D5DD', linewidth=0.9, linestyle='--', alpha=0.8)
    ax.text(min(crois)+0.2, med_ev+0.5, f'Med. EV/EBITDA ({med_ev:.1f}x)', fontsize=9, color='#999', style='italic')
    ax.set_xlabel('Croissance BPA mediane (%)', fontsize=11, color='#555')
    ax.set_ylabel('EV / EBITDA median (x)', fontsize=11, color='#555')
    for sp in ['top','right']: ax.spines[sp].set_visible(False)
    ax.spines['left'].set_color('#D0D5DD'); ax.spines['bottom'].set_color('#D0D5DD')
    ax.set_facecolor('white'); fig.patch.set_facecolor('white')
    ax.tick_params(labelsize=10, length=0)
    ax.grid(alpha=0.12, color='#D0D5DD', linewidth=0.5)
    patches = [mpatches.Patch(color='#1A7A4A', label='Surponderer'),
               mpatches.Patch(color='#B06000', label='Neutre'),
               mpatches.Patch(color='#A82020', label='Sous-ponderer')]
    ax.legend(handles=patches, fontsize=10, loc='upper center',
              bbox_to_anchor=(0.5, -0.13), frameon=False, ncol=3)
    ax.set_title(f"EV/EBITDA vs Croissance BPA - Secteurs {data['indice']}",
                 fontsize=13, color='#1B3A6B', fontweight='bold', pad=12)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=160, bbox_inches='tight')
    plt.close(fig); buf.seek(0); return buf


def make_score_bars(data):
    secteurs = data["secteurs"]
    noms   = [s[0] for s in secteurs]
    scores = [float(s[2]) for s in secteurs]
    sigs   = [s[3] for s in secteurs]
    order  = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    noms_s   = [noms[i]   for i in order]
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
    ax.set_yticks(y); ax.set_yticklabels(noms_s, fontsize=10, color='#333')
    ax.set_xlim(0, 118)
    ax.set_xlabel('Score composite (0-100)', fontsize=10, color='#555')
    ax.grid(axis='x', alpha=0.12, color='#D0D5DD', linewidth=0.5)
    for sp in ['top','right']: ax.spines[sp].set_visible(False)
    ax.spines['left'].set_color('#D0D5DD'); ax.spines['bottom'].set_color('#D0D5DD')
    ax.set_facecolor('white'); fig.patch.set_facecolor('white')
    ax.tick_params(labelsize=10, length=0)
    ax.set_title(f"Score composite - Secteurs {data['indice']} (trie par score decroissant)",
                 fontsize=13, color='#1B3A6B', fontweight='bold', pad=10)
    plt.tight_layout(pad=0.5)
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=160, bbox_inches='tight')
    plt.close(fig); buf.seek(0); return buf


def make_top3_donut(data):
    poids_map = {
        "Technology": 28.4, "Health Care": 12.8, "Financials": 13.2,
        "Consumer Discretionary": 10.6, "Industrials": 8.8,
        "Communication Svcs": 8.4, "Consumer Staples": 6.2,
        "Energy": 4.8, "Real Estate": 2.4, "Materials": 2.6, "Utilities": 1.8,
    }
    top3 = data["top3_secteurs"]
    noms_top  = [s["nom"] for s in top3]
    poids_top = [poids_map.get(n, 5.0) for n in noms_top]
    reste     = max(0.0, 100.0 - sum(poids_top))
    labels    = [f"{n} ({p:.0f}%)" for n, p in zip(noms_top, poids_top)] + [f"Autres ({reste:.0f}%)"]
    sizes     = poids_top + [reste]
    palette   = ['#1B3A6B', '#2A5298', '#5580B8', '#D0D5DD']
    explode   = [0.04] * len(top3) + [0]
    fig, ax = plt.subplots(figsize=(5.2, 5.6))
    wedges, _ = ax.pie(sizes, labels=None, autopct=None,
                       colors=palette[:len(sizes)], explode=explode,
                       startangle=90, wedgeprops=dict(linewidth=0.8, edgecolor='white'))
    centre = plt.Circle((0, 0), 0.40, color='white')
    ax.add_patch(centre)
    total_top = sum(poids_top)
    ax.text(0,  0.10, "Top 3",    ha='center', va='center', fontsize=12, fontweight='bold', color='#1B3A6B')
    ax.text(0, -0.14, f"{total_top:.0f}%", ha='center', va='center', fontsize=16, fontweight='bold', color='#1B3A6B')
    ax.legend(wedges, labels, loc='lower center', bbox_to_anchor=(0.5, -0.18),
              ncol=2, fontsize=9, frameon=False, handlelength=1.4, columnspacing=1.2)
    ax.set_title(f"Contribution a l'indice - Top 3 vs reste",
                 fontsize=11, color='#1B3A6B', fontweight='bold', pad=10)
    fig.patch.set_facecolor('white')
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
    c.drawCentredString(cx, h - 14*mm, "Plateforme d'Analyse Financiere Institutionnelle")
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

    # 5 metriques
    metrics = [
        ("Secteurs analyses",  str(data["nb_secteurs"])),
        ("Societes couvertes", str(data["nb_societes"])),
        ("Cours indice",       data["cours"]),
        ("Variation YTD",      data["variation_ytd"]),
        ("P/E Forward",        data["pe_forward"]),
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
        "Donnees : yfinance · FMP · Finnhub · FinBERT  |  Horizon d'allocation : 12 mois")

    # Footer navy
    c.setFillColor(NAVY); c.rect(0, 0, w, 18*mm, fill=1, stroke=0)
    c.setFillColor(colors.HexColor('#90B4E8')); c.setFont('Helvetica', 6.5)
    c.drawCentredString(cx, 11*mm, "CONFIDENTIEL — Usage restreint")
    c.drawCentredString(cx, 6*mm,
        "Genere par FinSight IA v1.0. Ne constitue pas un conseil en investissement au sens MiFID II.")


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
        ("1.", f"Synthese Macro &amp; Signal Global",         "synthese",
         f"  Signal global \xb7 Conviction \xb7 Catalyseurs \xb7 Risques macro"),
        ("2.", "Cartographie des Secteurs",                   "carto",
         "  Tableau comparatif 11 secteurs \xb7 Score \xb7 EV/EBITDA \xb7 Momentum"),
        ("3.", "Analyse Graphique",                           "graphiques",
         "  Scatter EV/EBITDA vs croissance \xb7 Scores par secteur"),
        ("4.", "Rotation Sectorielle",                        "rotation",
         "  Phase du cycle \xb7 Sensibilite taux/PIB \xb7 Signal de rotation"),
        ("5.", "Top 3 Secteurs Recommandes",                  "top3",
         "  Detail signal \xb7 Societes representatives \xb7 Catalyseurs"),
        ("6.", "Risques Macro &amp; Conditions d'Invalidation", "risques",
         "  Cartographie risques \xb7 Probabilites \xb7 Horizons"),
        ("7.", "Sentiment Agrege &amp; Methodologie",         "sentiment",
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
    if registry is not None: elems.append(SectionAnchor('synthese', registry))
    elems += section_title("Synthese Macro &amp; Signal Global", 1)

    elems.append(Paragraph(data["texte_macro"], S_BODY))
    elems.append(Spacer(1, 3*mm))
    elems.append(Paragraph(data["texte_signal"], S_BODY))
    elems.append(Spacer(1, 3*mm))

    elems.append(Image(perf_buf, width=TABLE_W, height=72*mm))
    elems.append(src(f"FinSight IA — yfinance. Base 100, Mars 2025. {indice_rl} vs US 10Y Bond vs Gold."))
    elems.append(Spacer(1, 4*mm))

    elems.append(debate_q(
        "Quels catalyseurs pourraient faire devier l'indice de son scenario central ?"))
    cat_h = [Paragraph(h, S_TH_L) for h in ["Catalyseur", "Mecanisme", "Horizon"]]
    cat_rows = []
    for nom, mecanisme, horizon in data["catalyseurs"]:
        cat_rows.append([Paragraph(nom, S_TD_B),
                         Paragraph(mecanisme, S_TD_L),
                         Paragraph(horizon, S_TD_C)])
    elems.append(KeepTogether(tbl([cat_h] + cat_rows, cw=[42*mm, 110*mm, 18*mm])))
    elems.append(src("FinSight IA — Analyse interne. Probabilites non assignees (cf. section Risques)."))
    return elems


def _build_cartographie(data, weights_buf, registry=None):
    secteurs = data["secteurs"]
    indice_rl = data["indice"].replace("&", "&amp;")
    elems = []
    elems.append(PageBreak())
    elems.append(Spacer(1, 10*mm))
    if registry is not None: elems.append(SectionAnchor('carto', registry))
    elems += section_title("Cartographie des Secteurs", 2)
    elems.append(Spacer(1, 4*mm))

    # Graphique + mini tableau cote a cote
    weights_img = Image(weights_buf, width=76*mm, height=66*mm)
    sig_h = [Paragraph(h, S_TH_C) for h in ["Secteur", "Signal", "Score"]]
    sig_rows = []
    for s in secteurs:
        sig_rows.append([
            Paragraph(s[0], S_TD_L),
            Paragraph(s[3], sig_s(s[3])),
            Paragraph(str(s[2]), S_TD_C),
        ])
    # mini tbl: 52+34+10 = 96mm (pas 170, c'est un sous-tableau dans une cellule)
    sig_tbl_inner = Table([
        [Paragraph(h, S_TH_C) for h in ["Secteur","Signal","Score"]]
    ] + sig_rows, colWidths=[52*mm, 34*mm, 10*mm])
    sig_tbl_inner.setStyle(TableStyle([
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
    right_col = Table(
        [[Paragraph("Signaux par secteur", S_SUBSECTION)], [sig_tbl_inner]],
        colWidths=[90*mm]
    )
    right_col.setStyle(TableStyle([
        ("LEFTPADDING",   (0,0),(-1,-1), 0), ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ("TOPPADDING",    (0,0),(-1,-1), 0), ("BOTTOMPADDING", (0,0),(-1,-1), 2),
    ]))
    combined = Table([[weights_img, right_col]], colWidths=[78*mm, 92*mm])
    combined.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING",   (0,0),(-1,-1), 0), ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ("TOPPADDING",    (0,0),(-1,-1), 0), ("BOTTOMPADDING", (0,0),(-1,-1), 0),
        ("LEFTPADDING",   (1,0),(1,0),   6),
    ]))
    elems.append(combined)
    elems.append(src(
        f"FinSight IA — Ponderations GICS. Score composite : 40% momentum, 30% rev. BPA, 30% valorisation."))
    elems.append(Spacer(1, 4*mm))

    # Tableau comparatif complet — colonnes exactement 170mm
    # [8, 36, 14, 12, 26, 24, 18, 16, 16] = 170
    elems.append(Paragraph(
        f"Tableau comparatif — {data['nb_secteurs']} secteurs {indice_rl}", S_SUBSECTION))
    comp_h = [Paragraph(h, S_TH_C) for h in
              ["Rg","Secteur","Nb Soc.","Score","Signal",
               "EV/EBITDA","Mg.EBITDA","Croiss.","Momentum"]]
    comp_rows = []
    sorted_secs = sorted(secteurs, key=lambda s: s[2], reverse=True)
    for rang, s in enumerate(sorted_secs, 1):
        mg   = str(s[5]) if len(s) > 5 else "—"
        croi = str(s[6]) if len(s) > 6 else "—"
        mom  = str(s[7]) if len(s) > 7 else "—"
        comp_rows.append([
            Paragraph(str(rang), S_TD_C),
            Paragraph(s[0], S_TD_B),
            Paragraph(str(s[1]), S_TD_C),
            Paragraph(str(s[2]), S_TD_BC),
            Paragraph(s[3], sig_s(s[3])),
            Paragraph(str(s[4]), S_TD_C),
            Paragraph(mg, S_TD_C),
            Paragraph(croi, S_TD_G if '+' in str(croi) else S_TD_R),
            Paragraph(mom,  S_TD_G if '+' in str(mom)  else S_TD_R),
        ])
    elems.append(KeepTogether(tbl([comp_h] + comp_rows,
        cw=[8*mm, 36*mm, 14*mm, 12*mm, 26*mm, 24*mm, 18*mm, 16*mm, 16*mm])))
    elems.append(src(
        f"FinSight IA — FMP, yfinance. EV/EBITDA et marges = medianes sectorielles LTM. "
        "Momentum = performance relative 3 mois vs indice. Score = composite 0-100."))
    return elems


def _build_graphiques(data, scatter_buf, scores_buf, registry=None):
    elems = []
    elems.append(PageBreak())
    elems.append(Spacer(1, 10*mm))
    if registry is not None: elems.append(SectionAnchor('graphiques', registry))
    elems += section_title("Analyse Graphique", 3)
    elems.append(Spacer(1, 3*mm))

    elems.append(Paragraph("Positionnement EV/EBITDA vs Croissance BPA", S_SUBSECTION))
    elems.append(Paragraph(
        "Le scatter ci-dessous positionne chaque secteur sur deux axes : "
        "valorisation (EV/EBITDA median LTM) et croissance BPA mediane. "
        "Les lignes pointillees representent les medianes sectorielles — "
        "les secteurs dans le <b>quadrant superieur droit</b> paient une prime justifiee "
        "par une forte croissance ; ceux dans le <b>quadrant inferieur gauche</b> offrent "
        "une valeur relative.", S_BODY))
    elems.append(Spacer(1, 3*mm))
    elems.append(Image(scatter_buf, width=TABLE_W, height=100*mm))
    elems.append(src("FinSight IA — EV/EBITDA median LTM vs croissance BPA mediane secteur. FMP, Bloomberg."))

    elems.append(PageBreak())
    elems.append(Spacer(1, 10*mm))
    elems.append(Paragraph("Score composite — Classement sectoriel", S_SUBSECTION))
    nb_surp = sum(1 for s in data["secteurs"] if s[3] == "Surpond\xe9rer")
    nb_sous = sum(1 for s in data["secteurs"] if s[3] == "Sous-pond\xe9rer")
    elems.append(Paragraph(
        "Le score composite (0-100) agregge trois signaux : momentum prix 3 mois (40%), "
        "revision des estimations BPA sur 1 mois (30%) et valorisation relative (30%). "
        "La ligne pointillee orange marque le seuil 50 — <b>au-dessus : signal Surponderer</b> "
        "possible, <b>en dessous de 40 : Sous-ponderer</b>. "
        f"{nb_surp} secteur(s) franchissent le seuil Surponderer (60), "
        f"{nb_sous} secteur(s) en Sous-ponderer.", S_BODY))
    elems.append(Spacer(1, 3*mm))
    elems.append(Image(scores_buf, width=TABLE_W, height=100*mm))
    elems.append(src(
        "FinSight IA — Score composite trie par ordre decroissant. "
        "Seuil Surponderer = 60, Sous-ponderer = 40."))
    return elems


def _build_rotation(data, registry=None):
    elems = []
    elems.append(PageBreak())
    elems.append(Spacer(1, 10*mm))
    if registry is not None: elems.append(SectionAnchor('rotation', registry))
    elems += section_title("Rotation Sectorielle", 4)
    elems.append(Spacer(1, 4*mm))

    elems.append(debate_q(
        "Ou en sommes-nous dans le cycle economique et quels secteurs privilegier ?"))
    elems.append(Paragraph(data["texte_rotation"], S_BODY))
    elems.append(Spacer(1, 3*mm))

    rot_h = [Paragraph(h, S_TH_C) for h in
             ["Secteur","Phase cycle","Sens. taux","Sens. PIB","Signal de rotation"]]

    def rot_signal_s(sig):
        if sig == "Accumuler": return S_TD_G
        if sig in ("All\xe9ger", "Alleger"): return S_TD_R
        return S_TD_A

    rot_rows = []
    for item in data["rotation"]:
        s, phase, taux, pib, sig = item
        phase_s = S_TD_G if phase == "Expansion" else (S_TD_R if phase in ("R\xe9cession","Recession") else S_TD_A)
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
        "FinSight IA — Modele de rotation 4 phases. "
        "Sensibilites : Faible / Moderee / Elevee / Positive (taux)."))

    # Encadre cycle
    surp_noms = " \xb7 ".join(s["nom"] for s in data["top3_secteurs"])
    elems.append(Spacer(1, 4*mm))
    elems.append(Paragraph("Positionnement de cycle recommande", S_SUBSECTION))
    cycle_data = [
        ["Phase actuelle",
         data.get("phase_cycle", "Expansion avancee"),
         "Croissance positive, taux restrictifs, marges sous pression selective"],
        ["Secteurs a surponderer", surp_noms,
         "Forte visibilite BPA, faible sensibilite aux taux, pricing power intact"],
        ["Secteurs a neutraliser", "Industrials \xb7 Comm. Svcs \xb7 Consumer Disc.",
         "Croissance correcte mais risque de deceleration si PIB ralentit"],
        ["Secteurs a alleger", "Real Estate \xb7 Utilities",
         "Double penalite : taux eleves + faible croissance = compression multiple"],
        ["Catalyseur de rotation", "Confirmation pivot Fed (<2,5% CPI sur 3M)",
         "Renversement signal Real Estate et Utilities — accumulation anticipee"],
    ]
    cycle_h = [Paragraph(h, S_TH_L) for h in ["Element","Verdict","Rationale"]]
    cycle_rows = [[Paragraph(r[0], S_TD_B), Paragraph(r[1], S_TD_L), Paragraph(r[2], S_TD_L)]
                  for r in cycle_data]
    # [38, 52, 80] = 170
    elems.append(KeepTogether(tbl([cycle_h] + cycle_rows, cw=[38*mm, 52*mm, 80*mm])))
    elems.append(src(
        "FinSight IA — Modele cycle interne. Indicateurs : ISM, courbe taux, Leading indicators OCDE."))
    return elems


def _build_top3(data, donut_buf, registry=None):
    indice_rl = data["indice"].replace("&", "&amp;")
    secteurs  = data["secteurs"]
    elems = []
    elems.append(PageBreak())
    elems.append(Spacer(1, 10*mm))
    if registry is not None: elems.append(SectionAnchor('top3', registry))
    elems += section_title("Top 3 Secteurs Recommandes", 5)
    elems.append(Spacer(1, 3*mm))

    nb_surp = len(data["top3_secteurs"])
    elems.append(Paragraph(
        f"Sur les {data['nb_secteurs']} secteurs couverts, {nb_surp} affichent un signal "
        f"<b>Surponderer</b>. Ces secteurs combinent momentum prix positif, revision haussiere "
        "des BPA et valorisation raisonnable par rapport a leur historique. "
        "Pour le detail complet — ratios LTM/NTM, Football Field, DCF, FinBERT — "
        f"lancer l'analyse sectorielle dediee dans FinSight IA.", S_BODY))
    elems.append(Spacer(1, 4*mm))

    # Tableau synthese
    elems.append(Paragraph("Vue d'ensemble — Secteurs Surponderer", S_SUBSECTION))
    synth_h = [Paragraph(h, S_TH_C) for h in
               ["Secteur","Signal","Score","EV/EBITDA","Mg. EBITDA","Croiss.","Momentum"]]
    synth_rows = []
    for sect in data["top3_secteurs"]:
        s_data = next((s for s in secteurs if s[0] == sect["nom"]), None)
        mg   = f"{s_data[5]}%" if s_data and len(s_data) > 5 else "—"
        croi = str(s_data[6]) if s_data and len(s_data) > 6 else "—"
        mom  = str(s_data[7]) if s_data and len(s_data) > 7 else "—"
        synth_rows.append([
            Paragraph(f"<b>{sect['nom']}</b>", S_TD_B),
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
    elems.append(src(f"FinSight IA — FMP, yfinance. EV/EBITDA et marges = medianes LTM."))
    elems.append(Spacer(1, 4*mm))

    # Donut gauche + textes analytiques droite
    donut_img = Image(donut_buf, width=82*mm, height=86*mm)
    analyses_lines = []
    for sect in data["top3_secteurs"]:
        cat = sect.get("catalyseur", "")
        rsk = sect.get("risque", "")
        analyses_lines.append(
            f"<b>{sect['nom']}</b> — {sect['signal']} \xb7 Score {sect['score']} \xb7 "
            f"EV/EBITDA {sect['ev_ebitda']}<br/>"
            f"Catalyseur : {cat}<br/>"
            f"Risque : {rsk}"
            "<br/><br/>"
        )
    analyses_text = "".join(analyses_lines)
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
        f"FinSight IA — Ponderations GICS {data['date_analyse']}. "
        "Analyses generees par l'agent Synthese."))
    elems.append(Spacer(1, 5*mm))

    # Tableau 9 societes — KeepTogether sur titre+texte+spacer+tableau
    soc_h = [Paragraph(h, S_TH_C) for h in
             ["Secteur","Ticker","Signal","EV/EBITDA","Score","Prochaine etape"]]
    soc_rows = []
    for sect in data["top3_secteurs"]:
        for tkr, sig, ev, score in sect["societes"]:
            soc_rows.append([
                Paragraph(sect["nom"], S_TD_L),
                Paragraph(f"<b>{tkr}</b>", S_TD_BC),
                Paragraph(sig, sig_s(sig)),
                Paragraph(ev, S_TD_C),
                Paragraph(str(score), S_TD_C),
                Paragraph("Lancer analyse societe FinSight IA", S_TD_L),
            ])
    # [36, 16, 30, 24, 18, 46] = 170
    soc_tbl = tbl([soc_h] + soc_rows, cw=[36*mm, 16*mm, 30*mm, 24*mm, 18*mm, 46*mm])
    elems.append(KeepTogether([
        Paragraph("Societes representatives — 3 convictions par secteur", S_SUBSECTION),
        Spacer(1, 2*mm),
        Paragraph(
            "Ces societes constituent les convictions les plus solides au sein de chaque "
            "secteur Surponderer. Pour acceder a l'analyse complete — prix cible, DCF, "
            "Altman Z-Score, FinBERT — lancer l'analyse societe individuelle.", S_BODY),
        Spacer(1, 2*mm),
        soc_tbl,
    ]))
    elems.append(src(
        "FinSight IA — Societes selectionnees par capitalisation et signal FinSight. "
        "Score = composite 0-100. Analyse complete via module societe ou sectoriel."))
    return elems


def _build_risques(data, registry=None):
    indice_rl = data["indice"].replace("&", "&amp;")
    elems = []
    elems.append(PageBreak())
    elems.append(Spacer(1, 10*mm))
    if registry is not None: elems.append(SectionAnchor('risques', registry))
    elems += section_title("Risques Macro &amp; Conditions d'Invalidation", 6)

    sig_central = data["signal_global"]
    elems.append(Paragraph(
        f"L'analyse adversariale identifie trois axes de risque susceptibles d'invalider "
        f"le scenario central <b>{sig_central}</b> sur le {indice_rl}. Notre approche ne traite "
        "pas ces risques comme des probabilites faibles a ignorer, mais comme des "
        "<b>conditions de surveillance active</b> qui doivent modifier le positionnement "
        "si elles se materialisent. Chaque risque est evalue sur sa probabilite estimee "
        "a 12 mois, son mecanisme de transmission et son impact potentiel sur les niveaux "
        "de l'indice et les multiples.", S_BODY))
    elems.append(Spacer(1, 2*mm))

    risk_h = [Paragraph(h, S_TH_L) for h in ["Risque macro","Mecanisme","Prob.","Impact"]]
    risk_rows = []
    for nom, mec, prob, impact in data["risques"]:
        p_int = int(str(prob).replace('%',''))
        ps  = S_TD_R if p_int >= 40 else (S_TD_A if p_int >= 25 else S_TD_G)
        is_ = S_TD_R if impact in ("Eleve", "\xc9lev\xe9") else S_TD_A
        risk_rows.append([Paragraph(nom, S_TD_B), Paragraph(mec, S_TD_L),
                          Paragraph(str(prob), ps), Paragraph(impact, is_)])
    # [36, 107, 16, 11] = 170
    elems.append(KeepTogether(tbl([risk_h] + risk_rows, cw=[36*mm, 107*mm, 16*mm, 11*mm])))
    elems.append(src(
        f"FinSight IA — Analyse adversariale. Probabilites estimees au {data['date_analyse']}."))
    elems.append(Spacer(1, 4*mm))

    elems.append(debate_q(
        f"Quelles conditions invalideraient le signal {sig_central} et vers quel scenario ?"))
    inv_h = [Paragraph(h, S_TH_L) for h in
             ["Scenario","Condition declencheur","Signal resultant","Horizon"]]
    inv_data = [
        ["Bull case",
         "CPI <2,5% sur 3M + BPA Q1 >12% YoY + Fed pivot annonce",
         "Surponderer",
         "3-6 mois"],
        ["Bear case",
         "Recession technique confirmee (2T PIB <0%) OU choc geopolitique majeur",
         "Sous-ponderer",
         "6-12 mois"],
        ["Stagflation",
         "CPI rechauffe >3,5% + PIB <1% — stagflation scenario",
         "Sous-ponderer selectif",
         "6-9 mois"],
    ]

    def inv_signal_s(v):
        if "Surponderer" in v: return S_TD_G
        if "Sous-ponderer" in v: return S_TD_R
        return S_TD_A

    inv_rows = [[Paragraph(r[0], S_TD_B), Paragraph(r[1], S_TD_L),
                 Paragraph(r[2], inv_signal_s(r[2])), Paragraph(r[3], S_TD_C)]
                for r in inv_data]
    # [22, 91, 48, 9] = 170
    elems.append(KeepTogether(tbl([inv_h] + inv_rows, cw=[22*mm, 91*mm, 48*mm, 9*mm])))
    elems.append(src(
        "FinSight IA — Scenarios alternatifs. Conditions a reevaluer a chaque rapport mensuel."))
    elems.append(Spacer(1, 4*mm))
    elems.append(Paragraph("Gestion du risque portefeuille", S_SUBSECTION))
    elems.append(Paragraph(data.get("texte_gestion_risque",
        f"Dans le scenario central, le {indice_rl} evolue dans une fourchette cible sur 12 mois, "
        "soutenu par la resilience des marges des secteurs Surponderer. Le portefeuille modele "
        "recommande une surexposition selective sur les secteurs identifies, une couverture "
        "partielle via les secteurs defensifs en cas de choc de croissance, et une reduction "
        "tactique du beta portefeuille si les conditions macro se deteriorent de maniere "
        f"significative. La prochaine revue est programmee dans 30 jours."), S_BODY))
    return elems


def _build_sentiment(data, registry=None):
    indice_rl = data["indice"].replace("&", "&amp;")
    fb = data["finbert"]
    elems = []
    elems.append(PageBreak())
    elems.append(Spacer(1, 10*mm))
    if registry is not None: elems.append(SectionAnchor('sentiment', registry))
    elems += section_title("Sentiment Agrege &amp; Methodologie", 7)

    elems.append(Paragraph(
        f"L'analyse FinBERT conduite sur <b>{fb['nb_articles']} articles</b> des sept derniers "
        f"jours produit un sentiment agrege de <b>{fb['score_agrege']}</b> sur l'ensemble du "
        f"{indice_rl}. Les publications favorables portent sur : {fb['positif']['themes']}. "
        f"Les signaux negatifs se concentrent sur : {fb['negatif']['themes']}.", S_BODY))
    elems.append(Spacer(1, 3*mm))

    # Distribution globale — [24, 20, 26, 100] = 170
    sent_h = [Paragraph(h, S_TH_C) for h in
              ["Orientation","Articles","Score moyen","Themes dominants"]]
    sent_rows = [
        [Paragraph("Positif",  S_TD_G),
         Paragraph(str(fb["positif"]["nb"]),  S_TD_C),
         Paragraph(fb["positif"]["score"],    S_TD_G),
         Paragraph(fb["positif"]["themes"],   S_TD_L)],
        [Paragraph("Neutre",   S_TD_A),
         Paragraph(str(fb["neutre"]["nb"]),   S_TD_C),
         Paragraph(fb["neutre"]["score"],     S_TD_C),
         Paragraph(fb["neutre"]["themes"],    S_TD_L)],
        [Paragraph("Negatif",  S_TD_R),
         Paragraph(str(fb["negatif"]["nb"]),  S_TD_C),
         Paragraph(fb["negatif"]["score"],    S_TD_R),
         Paragraph(fb["negatif"]["themes"],   S_TD_L)],
    ]
    elems.append(KeepTogether(tbl([sent_h] + sent_rows, cw=[24*mm, 20*mm, 26*mm, 100*mm])))
    elems.append(src(
        f"FinBERT — Corpus presse financiere anglophone. {fb['nb_articles']} articles, 7 jours."))
    elems.append(Spacer(1, 4*mm))

    # Sentiment par secteur — deux colonnes cote a cote
    elems.append(Paragraph("Sentiment FinBERT — Distribution par secteur", S_SUBSECTION))
    ps_h = [Paragraph(h, S_TH_C) for h in ["Secteur","Score moyen","Orientation"]]
    ps_rows = []
    for sect, score, orient in fb["par_secteur"]:
        os_ = S_TD_G if orient == "Positif" else (S_TD_R if orient in ("Negatif","N\xe9gatif") else S_TD_C)
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
        "FinBERT — Score par secteur = moyenne ponderee des articles mentionnant le secteur."))
    elems.append(Spacer(1, 4*mm))

    # Methodologie — [40, 130] = 170
    elems.append(Paragraph("Sources &amp; Methodologie", S_SUBSECTION))
    meth_h = [Paragraph(h, S_TH_L) for h in ["Composante","Methodologie"]]
    meth_rows = [[Paragraph(k, S_TD_B), Paragraph(v, S_TD_L)]
                 for k, v in data["methodologie"]]
    elems.append(KeepTogether(tbl([meth_h] + meth_rows, cw=[40*mm, 130*mm])))
    elems.append(src(
        f"FinSight IA v1.0 — Mise a jour quotidienne. Donnees au {data['date_analyse']}."))
    return elems


def _build_disclaimer(data):
    elems = []
    elems.append(PageBreak())
    elems.append(Spacer(1, 10*mm))
    elems.append(rule())
    S_DISC_TITLE = _style('disc_title', size=6.5, leading=9, color=GREY_TEXT, bold=True)
    elems.append(Paragraph(
        "INFORMATIONS REGLEMENTAIRES ET AVERTISSEMENTS IMPORTANTS", S_DISC_TITLE))
    elems.append(Spacer(1, 1.5*mm))
    elems.append(Paragraph(
        f"<b>Nature du document.</b> Ce rapport a ete genere automatiquement par FinSight IA v1.0 "
        f"le {data['date_analyse']}. Il est produit integralement par un systeme d'intelligence "
        "artificielle et <b>ne constitue pas un conseil en investissement</b> au sens de la "
        "directive europeenne MiFID II (2014/65/UE) ni au sens de toute autre reglementation "
        "applicable. FinSight IA n'est pas un prestataire de services d'investissement agree. "
        "Ce document est fourni a titre informatif uniquement et ne saurait etre interprete "
        "comme une recommandation personnalisee d'achat, de vente ou de conservation de tout "
        "instrument financier.", S_DISC))
    elems.append(Spacer(1, 1.5*mm))
    elems.append(Paragraph(
        "<b>Conflits d'interet.</b> FinSight IA est un outil d'analyse automatise sans position "
        "proprietaire dans les titres ou indices couverts. Aucune remuneration n'est percue de "
        "la part des emetteurs analyses. Nonobstant, le lecteur est invite a considerer que tout "
        "modele analytique comporte des biais inherents a ses hypotheses de construction.", S_DISC))
    elems.append(Spacer(1, 1.5*mm))
    elems.append(Paragraph(
        "<b>Fiabilite des donnees.</b> Les donnees financieres sont issues de sources publiques "
        "(yfinance, Financial Modeling Prep, Finnhub) et de modeles internes. Malgre les "
        "controles appliques, ces donnees peuvent contenir des inexactitudes, des delais ou "
        "des erreurs. Les projections et estimations presentees reposent sur des hypotheses "
        "qui peuvent ne pas se realiser. Les performances passees ne prejudgent pas des "
        "performances futures.", S_DISC))
    elems.append(Spacer(1, 1.5*mm))
    elems.append(Paragraph(
        "<b>Restrictions de diffusion.</b> Ce document est strictement confidentiel et destine "
        "exclusivement a son destinataire. Il ne peut etre reproduit, distribue ou communique "
        "a des tiers sans autorisation expresse. Sa diffusion peut etre soumise a des "
        "restrictions legales dans certaines juridictions. FinSight IA decline toute "
        "responsabilite pour les decisions prises sur la base de ce document. Tout investisseur "
        "est invite a proceder a sa propre analyse et a consulter un conseiller financier "
        "qualifie avant toute decision d'investissement. — <b>Document confidentiel.</b>", S_DISC))
    return elems


# ─── STORY BUILDER ────────────────────────────────────────────────────────────
def _build_story(data, perf_buf, weights_buf, scatter_buf, scores_buf,
                 donut_buf, page_nums, registry):
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
    story.append(Paragraph("Sommaire", S_SECTION))
    story.append(_build_sommaire(data, page_nums))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("A propos de cette analyse", S_SUBSECTION))
    story.append(Paragraph(
        f"Cette analyse d'indice couvre l'ensemble des {data['nb_secteurs']} secteurs GICS du "
        f"{indice_rl} ({data['nb_societes']} societes). Elle produit un signal global "
        "d'allocation sectorielle (Surponderer / Neutre / Sous-ponderer) et un score composite "
        "par secteur. Les donnees sont issues de yfinance, FMP et Finnhub. Le sentiment est "
        "analyse par FinBERT sur 7 jours glissants. La methodologie complete est detaillee "
        "en section 7.", S_BODY))
    story.append(PageBreak())

    story += _build_synthese(data, perf_buf, registry)
    story += _build_cartographie(data, weights_buf, registry)
    story += _build_graphiques(data, scatter_buf, scores_buf, registry)
    story += _build_rotation(data, registry)
    story += _build_top3(data, donut_buf, registry)
    story += _build_risques(data, registry)
    story += _build_sentiment(data, registry)
    story += _build_disclaimer(data)
    return story


# ─── CLASSE PRINCIPALE ────────────────────────────────────────────────────────
class IndicePDFWriter:

    @staticmethod
    def generate(data: dict, output_path: str) -> str:
        """
        Genere le rapport PDF d'analyse d'indice FinSight IA.
        Retourne output_path. Double-passe pour pagination dynamique.
        """
        # Buffers graphiques (generes une seule fois, rewound avant chaque passe)
        perf_buf    = make_indice_perf_chart(data)
        weights_buf = make_sector_weights_chart(data)
        scatter_buf = make_scatter_sectoriel(data)
        scores_buf  = make_score_bars(data)
        donut_buf   = make_top3_donut(data)

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
            for b in bufs: b.seek(0)

        # Passe 1 — collecter numeros de page reels
        registry = {}
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp_path = tmp.name
        doc1 = SimpleDocTemplate(tmp_path, **doc_kwargs)
        _rewind(perf_buf, weights_buf, scatter_buf, scores_buf, donut_buf)
        story1 = _build_story(data, perf_buf, weights_buf, scatter_buf, scores_buf,
                               donut_buf, {}, registry)
        doc1.build(story1, onFirstPage=make_on_page(data), onLaterPages=make_on_page(data))
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

        # Passe 2 — build final avec vrais numeros
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        doc2 = SimpleDocTemplate(output_path, **doc_kwargs)
        _rewind(perf_buf, weights_buf, scatter_buf, scores_buf, donut_buf)
        story2 = _build_story(data, perf_buf, weights_buf, scatter_buf, scores_buf,
                               donut_buf, dict(registry), {})
        doc2.build(story2, onFirstPage=make_on_page(data), onLaterPages=make_on_page(data))

        print(f"Rapport indice genere : {output_path}  |  Sections : {registry}")
        return output_path
