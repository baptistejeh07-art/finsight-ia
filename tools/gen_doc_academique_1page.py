#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinSight IA -- One-Pager Academique
Format A4 recto unique, destine aux jurys d'admission
76 fichiers Python · ~34 000 lignes · 6 fournisseurs LLM
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

W, H = A4
NAVY  = colors.HexColor('#1B2A4A')
GREEN = colors.HexColor('#1A7A4A')
LGREY = colors.HexColor('#F0F2F5')
MGREY = colors.HexColor('#D0D4DC')
DGREY = colors.HexColor('#555555')
BLACK = colors.HexColor('#111111')
WHITE = colors.white

ML = MR = 1.4 * cm
MT   = 2.85 * cm   # below header + stats + rule
MB   = 1.1 * cm

TW   = W - ML - MR
GAP  = 0.45 * cm
COL  = (TW - GAP) / 2   # ~247 pt per column

FB   = 8.8    # body font
FSH  = 9.5    # section header
FFM  = 7.5    # formula/code


def make_styles():
    d = {}
    def ps(name, **kw):
        defaults = dict(fontName='Times-Roman', fontSize=FB, leading=FB * 1.4,
                        textColor=BLACK, alignment=TA_JUSTIFY, spaceAfter=5,
                        spaceBefore=0)
        defaults.update(kw)
        d[name] = ParagraphStyle(name, **defaults)

    ps('body')
    ps('intro', fontName='Times-Italic', fontSize=FB - 0.3, leading=(FB-0.3)*1.4,
               spaceAfter=0, alignment=TA_JUSTIFY)
    ps('bul',  alignment=TA_LEFT, leftIndent=9, spaceAfter=2.5)
    ps('fm',   fontName='Courier', fontSize=FFM, leading=FFM * 1.45,
               leftIndent=5, spaceAfter=3, alignment=TA_LEFT,
               backColor=LGREY, textColor=colors.HexColor('#1a1a1a'))
    ps('sh',   fontName='Helvetica-Bold', fontSize=FSH, leading=FSH + 2,
               textColor=NAVY, alignment=TA_LEFT, spaceAfter=3, spaceBefore=9)
    ps('sh0',  fontName='Helvetica-Bold', fontSize=FSH, leading=FSH + 2,
               textColor=NAVY, alignment=TA_LEFT, spaceAfter=3, spaceBefore=0)
    return d


def header_cb(c, doc):
    # Navy header bar
    c.setFillColor(NAVY)
    c.rect(0, H - 48, W, 48, fill=1, stroke=0)

    # Title + subtitle
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 16)
    c.drawString(ML, H - 27, 'FinSight IA')
    c.setFont('Helvetica', 8)
    c.drawString(ML, H - 41,
                 "Plateforme d'Analyse Financiere Institutionnelle par IA Multi-Agents")

    # Author block
    c.setFont('Helvetica-Bold', 8.5)
    c.drawRightString(W - MR, H - 25, 'Baptiste Jehanno')
    c.setFont('Helvetica', 7.5)
    c.drawRightString(W - MR, H - 38, '28 mars 2026')

    # Green accent bar
    c.setFillColor(GREEN)
    c.rect(0, H - 51, W, 3, fill=1, stroke=0)

    # Stats line
    c.setFillColor(DGREY)
    c.setFont('Helvetica', 6.8)
    c.drawCentredString(
        W / 2, H - 62,
        '76 fichiers Python  \u00b7  ~34 000 lignes de code  \u00b7  '
        '6 fournisseurs LLM  \u00b7  Constitution 7 articles  \u00b7  '
        'Streamlit Cloud')

    # Rule below stats
    c.setStrokeColor(MGREY)
    c.setLineWidth(0.4)
    c.line(ML, H - 68, W - MR, H - 68)

    # Footer rule + colophon
    c.line(ML, MB + 8, W - MR, MB + 8)
    c.setFillColor(DGREY)
    c.setFont('Helvetica-Oblique', 6.2)
    c.drawCentredString(
        W / 2, MB + 1,
        'FinSight IA \u2014 Baptiste Jehanno \u2014 mars 2026  '
        '\u2014  Code source : GitHub  \u2014  Demo : finsight-ia.streamlit.app')


def build():
    OUT = 'outputs/FINSIGHT_IA_One_Pager.pdf'
    doc = SimpleDocTemplate(
        OUT, pagesize=A4,
        leftMargin=ML, rightMargin=MR,
        topMargin=MT, bottomMargin=MB + 12,
    )

    st = make_styles()
    P  = lambda t, s='body': Paragraph(t, st[s])
    SH = lambda t: Paragraph(t, st['sh'])
    S0 = lambda t: Paragraph(t, st['sh0'])
    BU = lambda t: Paragraph('\u2022\u00a0 ' + t, st['bul'])
    FM = lambda t: Paragraph(t, st['fm'])
    sp = lambda n=3: Spacer(1, n)

    # ── LEFT COLUMN ──────────────────────────────────────────────────────────
    left = [
        S0('ARCHITECTURE DU PIPELINE'),
        P("FinSight IA orchestre <b>7 agents</b> via un graphe d'\u00e9tats "
          "<b>LangGraph</b> (TypedDict, routage conditionnel). Principe "
          "fondateur\u00a0: le calcul d\u00e9terministe est exclusivement "
          "Python \u2014 aucun LLM ne produit de ratio."),
        P("Flux\u00a0: <i>fetch</i> (AgentData + FinBERT) \u2192 "
          "<i>fallback</i> (coverage\u00a0<\u00a00,70) \u2192 "
          "<i>quant</i> (33 ratios, 0 r\u00e9seau) \u2192 "
          "<i>synthesis</i> (LLM, JSON 70 champs) \u2192 "
          "<i>qa</i> (d\u00e9terministe \u2225 \u00e9ditorial) \u2192 "
          "<i>devil</i> (th\u00e8se inverse) \u2192 "
          "<i>output</i> (PDF \u2225 PPTX \u2225 Excel)."),
        P("Collecte multi-sources\u00a0: yfinance (primaire, 5 ans), "
          "FMP API (fallback EU), Finnhub (news + \u03b2). "
          "Score de couverture\u00a0:"),
        FM("coverage = |champs non-nuls| / |champs FinancialYear (39)|"),
        P("Si coverage\u00a0<\u00a00,70 \u2192 fallback automatique. "
          "Latence m\u00e9diane totale\u00a0: <b>~60 secondes</b>."),

        SH('IA & SYNTH\u00c8SE \u2014 CASCADE 6 LLM'),
        P("R\u00e9silience par diversification\u00a0: Groq (llama-3.3-70b) "
          "\u2192 Mistral \u2192 Cerebras \u2192 Anthropic Haiku "
          "\u2192 Gemini \u2192 Ollama. Rotation automatique des cl\u00e9s. "
          "Disponibilit\u00e9\u00a0>\u00a099\u202f%."),
        P("<b>AgentSynth\u00e8se</b>\u00a0: JSON 70 champs (th\u00e8se, "
          "recommandation, sc\u00e9narios, catalyseurs, risques) via prompt "
          "Jinja inject\u00e9 des 5 ann\u00e9es de ratios calcul\u00e9s."),
        P("<b>Double QA parall\u00e8le</b>\u00a0: AgentQAPython "
          "(10 checks d\u00e9terministes, flags INFO/WARNING/ERROR, "
          "d\u00e9gradation <i>qa_score</i>) + AgentQAHaiku (\u00e9ditorial). "
          "<b>AgentDevil</b>\u00a0: <i>conviction_delta</i> \u2208 [\u22121,\u00a00]."),

        SH('LIVRABLES INSTITUTIONNELS'),
        BU("<b>Rapport PDF 9 pages</b>\u00a0: ReportLab, "
           "canvas callbacks, graphiques matplotlib."),
        BU("<b>Pitchbook PPTX 20 slides</b>\u00a0: python-pptx, "
           "palette navy/blanc, layouts banque d\u2019investissement."),
        BU("<b>Mod\u00e8le Excel 7 feuilles</b>\u00a0: 52 cellules "
           "prot\u00e9g\u00e9es (liste statique + "
           "d\u00e9tection <i>startswith('=')</i>), "
           "5 ans align\u00e9s droite (H\u00a0=\u00a0LTM)."),
    ]

    # ── RIGHT COLUMN ─────────────────────────────────────────────────────────
    right = [
        S0('RIGUEUR QUANTITATIVE \u2014 33 RATIOS PYTHON PUR'),
        P("Rentabilit\u00e9 (ROE, ROA, ROIC, EBITDA margin, FCF yield) "
          "\u00b7 Valorisation (P/E, EV/EBITDA, P/B, P/S) "
          "\u00b7 Levier (D/E, Net debt/EBITDA) "
          "\u00b7 Liquidit\u00e9 (Current, Quick ratio) "
          "\u00b7 Efficacit\u00e9 (Asset turnover, DSO) "
          "\u00b7 Croissance (CAGR 3/5 ans, EPS growth). "
          "Z\u00e9ro appel LLM dans AgentQuant."),
        P("<b>Altman Z-Score</b> (1968)\u00a0:"),
        FM("Z = 1,2\u00d7X\u2081 + 1,4\u00d7X\u2082 + 3,3\u00d7X\u2083 "
           "+ 0,6\u00d7X\u2084 + 1,0\u00d7X\u2085"),
        P("Z\u00a0<\u00a01,81 \u2192 d\u00e9tresse. "
          "<b>Beneish M-Score</b> (1999)\u00a0: 8 variables "
          "comptables, M\u00a0>\u00a0\u22122,22 \u2192 manipulation potentielle."),
        P("<b>WACC</b> (Modigliani & Miller, 1958\u00a0; Sharpe, 1964)\u00a0:"),
        FM("WACC = (E/V \u00d7 Re) + (D/V \u00d7 Rd \u00d7 (1 \u2212 Tc))"),
        P("Re\u00a0= Rf\u00a0+\u00a0\u03b2\u00d7ERP (CAPM). "
          "Rf extrait de ^TNX (yfinance), "
          "ERP param\u00e9tr\u00e9 par secteur GICS (5,0\u00a0\u2013\u00a06,0\u202f%). "
          "DCF\u00a0: 5 ans explicites + valeur terminale\u00a0:"),
        FM("TV = FCF\u209c \u00d7 (1+g) / (WACC\u2212g)   "
           "[Gordon & Shapiro, 1956]"),

        SH('GOUVERNANCE CONSTITUTIONNELLE'),
        P("La <b>Constitution</b> encode 7 articles en dataclasses Python, "
          "appliqu\u00e9s \u00e0 chaque ex\u00e9cution par "
          "<code>check_compliance(state)</code>. "
          "Amendements via <code>validate_amendment(id)</code> "
          "(validation humaine explicite, archiv\u00e9e)."),
        BU("Art.\u00a01\u00a0: <i>confidence_score</i> \u2265 0,45 "
           "\u2014 HOLD si inf\u00e9rieur."),
        BU("Art.\u00a02\u00a0: <i>data_quality</i> \u2265 0,70 "
           "\u2014 fallback + HOLD."),
        BU("Art.\u00a03\u00a0: <i>qa_score</i> \u2265 0,60 avant output."),
        BU("Art.\u00a04\u00a0: AgentDevil syst\u00e9matique (th\u00e8se inverse)."),
        BU("Art.\u00a06\u00a0: SELL uniquement si "
           "<i>conviction_delta</i> < \u22120,50."),
        P("AgentJustice surveille le taux de violation\u00a0; "
          ">\u00a020\u202f% \u2192 proposition d'amendement."),

        SH('\u00c9TAT \u2014 MARS 2026 & ROADMAP'),
        P("Production d\u00e9ploy\u00e9e (<b>Streamlit Community Cloud</b>). "
          "3 modes\u00a0: <i>Soci\u00e9t\u00e9</i> (action cot\u00e9e mondiale) "
          "\u00b7 <i>Secteur</i> (GICS / indice) "
          "\u00b7 <i>Indice</i> (snapshot macro, 12\u202fp. PDF, 20 slides)."),
        P("<b>En cours</b>\u00a0: ratios banques/utilities/REIT, "
          "EODHD (source EU), ChromaDB (m\u00e9moire s\u00e9mantique). "
          "<b>Vision 12 mois</b>\u00a0: FinSight Score 0\u2013100 "
          "(backtest 10 ans), couverture Nikkei/Hang\u00a0Seng, "
          "API REST B2B (FastAPI, freemium)."),
    ]

    # ── Full-width intro ─────────────────────────────────────────────────────
    intro_txt = (
        "FinSight IA est une plateforme automatis\u00e9e d\u2019analyse financi\u00e8re "
        "institutionnelle con\u00e7ue pour produire, en moins de 90 secondes, des documents "
        "de recherche comparables aux standards des grandes banques d\u2019investissement. "
        "Le syst\u00e8me repose sur trois piliers\u00a0: <b>rigueur quantitative</b> "
        "(33 ratios d\u00e9terministes calcul\u00e9s exclusivement en Python\u00a0; "
        "aucun LLM ne produit de ratio), <b>synth\u00e8se linguistique structur\u00e9e</b> "
        "(cascade de 6 fournisseurs LLM avec rotation automatique des cl\u00e9s), et "
        "<b>gouvernance constitutionnelle formelle</b> "
        "(7 articles encod\u00e9s en Python, seuils de confiance mesurables, "
        "processus d\u2019amendement vers\u00e9). "
        "Enti\u00e8rement d\u00e9ploy\u00e9 sur Streamlit Cloud, "
        "sans cloud priv\u00e9 ni GPU, il rivalise qualitativement avec des outils "
        "institutionnels dont le co\u00fbt d\u2019acc\u00e8s d\u00e9passe 20\u202f000\u202f\u20ac/an."
    )
    intro_tbl = Table(
        [[Paragraph(intro_txt, st['intro'])]],
        colWidths=[TW],
    )
    intro_tbl.setStyle(TableStyle([
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LINEBELOW',     (0,0), (-1,-1), 0.4, MGREY),
    ]))

    # ── Two-column table ──────────────────────────────────────────────────────
    tbl = Table(
        [[left, right]],
        colWidths=[COL, COL],
    )
    tbl.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',   (0, 0), (0, 0),   0),
        ('RIGHTPADDING',  (0, 0), (0, 0),   GAP / 2),
        ('LEFTPADDING',   (1, 0), (1, 0),   GAP / 2),
        ('RIGHTPADDING',  (1, 0), (1, 0),   0),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LINEAFTER',     (0, 0), (0, -1),  0.4, MGREY),
    ]))

    doc.build([intro_tbl, Spacer(1, 6), tbl], onFirstPage=header_cb, onLaterPages=header_cb)
    print(f'PDF genere : {os.path.abspath(OUT)}')


build()
