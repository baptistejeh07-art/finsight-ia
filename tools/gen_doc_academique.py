#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinSight IA -- Documentation Academique
Generateur PDF ReportLab
Baptiste Jehanno -- 2026
"""

import os, sys
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether, CondPageBreak
)
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

W, H = A4
ML, MR, MT, MB = 2.5*cm, 2.5*cm, 2.5*cm, 2.2*cm
TW = W - ML - MR

# ── Palette ──────────────────────────────────────────────────────────────────
NAVY  = colors.HexColor('#1B2A4A')
GREEN = colors.HexColor('#1A7A4A')
RED   = colors.HexColor('#A82020')
AMB   = colors.HexColor('#B06000')
LGREY = colors.HexColor('#F5F6F8')
MGREY = colors.HexColor('#D8DCE2')
DGREY = colors.HexColor('#555555')
BLACK = colors.HexColor('#111111')
W_    = colors.white

# ── Styles ───────────────────────────────────────────────────────────────────
def S():
    d = {}
    def ps(name, **kw):
        defaults = dict(fontName='Times-Roman', fontSize=10.5, leading=16,
                        textColor=BLACK, alignment=TA_JUSTIFY, spaceAfter=6)
        defaults.update(kw)
        d[name] = ParagraphStyle(name, **defaults)
    ps('body')
    ps('abstract', leftIndent=18, rightIndent=18, spaceAfter=8)
    ps('body_i', fontName='Times-Italic')
    ps('body_b', fontName='Times-Bold')
    ps('bullet', leftIndent=18, bulletIndent=4, spaceAfter=3)
    ps('quote', fontName='Times-Italic', fontSize=10, leading=15, textColor=DGREY,
       leftIndent=28, rightIndent=28, spaceAfter=2)
    ps('quote_attr', fontName='Times-Italic', fontSize=9, leading=13,
       textColor=DGREY, alignment=TA_RIGHT, rightIndent=28, spaceAfter=12)
    ps('h1', fontName='Helvetica-Bold', fontSize=13.5, leading=18, textColor=NAVY,
       spaceBefore=22, spaceAfter=8, alignment=TA_LEFT, keepWithNext=1)
    ps('h2', fontName='Helvetica-BoldOblique', fontSize=11, leading=16,
       textColor=NAVY, spaceBefore=14, spaceAfter=5, alignment=TA_LEFT, keepWithNext=1)
    ps('h3', fontName='Helvetica-Bold', fontSize=10, leading=14,
       textColor=GREEN, spaceBefore=9, spaceAfter=3, alignment=TA_LEFT, keepWithNext=1)
    ps('formula', fontName='Courier', fontSize=9.5, leading=15, textColor=BLACK,
       alignment=TA_CENTER, leftIndent=30, rightIndent=30, spaceBefore=5, spaceAfter=5,
       backColor=LGREY, borderPad=6)
    ps('caption', fontName='Helvetica', fontSize=8.5, leading=12, textColor=DGREY,
       alignment=TA_CENTER, spaceAfter=10, spaceBefore=3)
    ps('toc_h', fontName='Helvetica-Bold', fontSize=11, leading=16, textColor=NAVY,
       spaceAfter=3, alignment=TA_LEFT)
    ps('toc_s', fontName='Helvetica', fontSize=10, leading=15, textColor=BLACK,
       spaceAfter=2, leftIndent=16, alignment=TA_LEFT)
    ps('cover_title', fontName='Helvetica-Bold', fontSize=34, leading=42,
       textColor=NAVY, alignment=TA_CENTER, spaceAfter=8)
    ps('cover_sub', fontName='Helvetica', fontSize=13.5, leading=20,
       textColor=DGREY, alignment=TA_CENTER, spaceAfter=5)
    ps('cover_meta', fontName='Helvetica', fontSize=10, leading=15,
       textColor=DGREY, alignment=TA_CENTER, spaceAfter=4)
    ps('cover_author', fontName='Helvetica-Bold', fontSize=16, leading=22,
       textColor=NAVY, alignment=TA_CENTER, spaceAfter=3)
    ps('cover_stats', fontName='Helvetica', fontSize=9, leading=14,
       textColor=DGREY, alignment=TA_CENTER)
    ps('th', fontName='Helvetica-Bold', fontSize=8.5, leading=12, textColor=W_,
       alignment=TA_CENTER)
    ps('td', fontName='Helvetica', fontSize=8.5, leading=12, textColor=BLACK,
       alignment=TA_LEFT)
    ps('tdc', fontName='Helvetica', fontSize=8.5, leading=12, textColor=BLACK,
       alignment=TA_CENTER)
    ps('td_mono', fontName='Courier', fontSize=8, leading=11, textColor=NAVY,
       alignment=TA_LEFT)
    ps('label', fontName='Helvetica-Bold', fontSize=9, leading=13,
       textColor=NAVY, alignment=TA_LEFT, spaceAfter=2)
    return d

ST = S()

# ── Helpers ───────────────────────────────────────────────────────────────────
def sp(n=8): return Spacer(1, n)
def hr(c=NAVY, t=0.5, b=6, a=6): return HRFlowable(width='100%', thickness=t,
                                    color=c, spaceBefore=b, spaceAfter=a)
def P(txt, s='body'): return Paragraph(txt, ST[s])
def H1(t): return P(t, 'h1')
def H2(t): return P(t, 'h2')
def H3(t): return P(t, 'h3')
def B(t): return P(t, 'bullet')
def I(t): return P(t, 'body_i')
def bold(t): return P(t, 'body_b')
def Fm(t): return P(t, 'formula')
def Cap(t): return P(t, 'caption')

def TBL(rows, widths, striped=True, col_aligns=None):
    t = Table(rows, colWidths=widths)
    cmds = [
        ('BACKGROUND', (0,0), (-1,0), NAVY),
        ('TEXTCOLOR', (0,0), (-1,0), W_),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8.5),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 8.5),
        ('GRID', (0,0), (-1,-1), 0.3, MGREY),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]
    if striped:
        for i in range(1, len(rows)):
            bg = LGREY if i % 2 == 0 else W_
            cmds.append(('BACKGROUND', (0,i), (-1,i), bg))
    t.setStyle(TableStyle(cmds))
    return t

def quote_block(text, attr):
    return [P(u'\u00ab\u00a0' + text + u'\u00a0\u00bb', 'quote'),
            P(u'— ' + attr, 'quote_attr')]

# ── Page callbacks ─────────────────────────────────────────────────────────────
def cover_cb(c, doc):
    c.saveState()
    c.setFillColor(NAVY)
    c.rect(0, H-13*mm, W, 13*mm, fill=1, stroke=0)
    c.rect(0, 0, W, 9*mm, fill=1, stroke=0)
    c.setFillColor(GREEN)
    c.rect(0, H-15*mm, W, 2*mm, fill=1, stroke=0)
    c.rect(0, 9*mm, W, 1.5*mm, fill=1, stroke=0)
    c.restoreState()

def body_cb(c, doc):
    c.saveState()
    c.setStrokeColor(NAVY); c.setLineWidth(0.4)
    c.line(ML, H-MT+8, W-MR, H-MT+8)
    c.setFont('Helvetica', 7.5); c.setFillColor(NAVY)
    c.drawString(ML, H-MT+12, 'FinSight IA \u2014 Documentation Academique')
    c.drawRightString(W-MR, H-MT+12, 'Baptiste Jehanno \u2014 2026')
    c.line(ML, MB-8, W-MR, MB-8)
    c.setFont('Helvetica', 7.5); c.setFillColor(DGREY)
    c.drawCentredString(W/2, MB-18, str(doc.page))
    c.restoreState()

# ── BUILD DOCUMENT ─────────────────────────────────────────────────────────────
def build():
    out = os.path.join(os.path.dirname(__file__), '..', 'outputs',
                       'FINSIGHT_IA_Documentation_Academique.pdf')
    out = os.path.normpath(out)

    doc = SimpleDocTemplate(
        out, pagesize=A4,
        leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
        title='FinSight IA — Documentation Academique',
        author='Baptiste Jehanno'
    )

    story = []

    # ══════════════════════════════════════════════════════════════════════
    # COVER
    # ══════════════════════════════════════════════════════════════════════
    story += [
        sp(52),
        P('FinSight IA', 'cover_title'),
        sp(4),
        P("Plateforme d'Analyse Financi\u00e8re Institutionnelle", 'cover_sub'),
        P('par Intelligence Artificielle Multi-Agents', 'cover_sub'),
        sp(28),
        hr(NAVY, 0.4, 2, 2),
        sp(16),
        P('Pipeline LangGraph \u00b7 7 n\u0153uds \u00b7 33 ratios d\u00e9terministes \u00b7 Gouvernance constitutionnelle', 'cover_meta'),
        P('Livrables : Rapport PDF \u00b7 Pitchbook 20 slides \u00b7 Mod\u00e8le Excel formul\u00e9', 'cover_meta'),
        sp(52),
        hr(NAVY, 0.4, 2, 2),
        sp(18),
        P('Baptiste Jehanno', 'cover_author'),
        P('Concepteur et d\u00e9veloppeur principal', 'cover_meta'),
        sp(14),
        P('28 mars 2026', 'cover_meta'),
        sp(52),
        P('76 fichiers Python \u00a0\u00b7\u00a0 ~34\u202f000 lignes de code \u00a0\u00b7\u00a0 6 fournisseurs LLM '
          '\u00a0\u00b7\u00a0 Constitution \u00e0 7 articles', 'cover_stats'),
        PageBreak(),
    ]

    # ══════════════════════════════════════════════════════════════════════
    # RESUME
    # ══════════════════════════════════════════════════════════════════════
    story += [
        H1('R\u00e9sum\u00e9'),
        hr(NAVY, 0.4, 2, 8),
        P('<b>FinSight IA</b> est une plateforme automatis\u00e9e d\u2019analyse financi\u00e8re '
          'institutionnelle con\u00e7ue pour produire, en moins de 90 secondes, des documents '
          'de recherche comparables aux standards des grandes banques d\u2019investissement. '
          'Le syst\u00e8me orchestre un pipeline multi-agents \u00e0 sept n\u0153uds, gouvern\u00e9 '
          'par un graphe d\u2019\u00e9tats LangGraph, afin de collecter les donn\u00e9es financi\u00e8res '
          'sur cinq ann\u00e9es, calculer 33 ratios d\u00e9terministes, synth\u00e9tiser une th\u00e8se '
          'd\u2019investissement par mod\u00e8le de langage \u00e0 grande \u00e9chelle (LLM), la valider '
          'par double passage qualit\u00e9 \u2014 d\u00e9terministe et \u00e9ditorial \u2014, '
          'la confronter syst\u00e9matiquement \u00e0 un protocole d\u2019avocat du diable, '
          'puis g\u00e9n\u00e9rer trois livrables de qualit\u00e9 institutionnelle\u00a0: '
          'rapport PDF (9 pages), pitchbook PowerPoint (20 diapositives) et mod\u00e8le '
          'Excel formul\u00e9 (52 cellules prot\u00e9g\u00e9es).', 'abstract'),
        sp(4),
        P("L'ensemble du syst\u00e8me repose sur trois piliers\u00a0: "
          "(<b>i</b>) une <i>rigueur quantitative</i> assur\u00e9e par des calculs Python purs "
          "\u2014 Altman Z-Score, Beneish M-Score, WACC, DCF \u2014 sans intervention de LLM\u00a0; "
          "(<b>ii</b>) une <i>synth\u00e8se linguistique structur\u00e9e</i> par une cascade "
          "de cinq fournisseurs LLM avec rotation automatique des cl\u00e9s et repli "
          "hi\u00e9rarchique\u00a0; (<b>iii</b>) une <i>gouvernance constitutionnelle formelle</i> "
          "\u00e0 sept articles, imposant des seuils de confiance mesurables et un processus "
          "d\u2019amendement vers\u00e9.", 'abstract'),
        sp(4),
        P("Le projet est enti\u00e8rement d\u00e9ploy\u00e9 sur Streamlit Cloud et accessible "
          "publiquement. Son architecture, pr\u00e9sent\u00e9e dans ce document, illustre une "
          "approche \u00e9conomiquement frugale \u2014 aucun cloud priv\u00e9, aucun GPU \u2014 "
          "capable de rivaliser qualitativement avec des outils institutionnels dont le co\u00fbt "
          "d\u2019acc\u00e8s annuel d\u00e9passe plusieurs milliers d\u2019euros.", 'abstract'),
        PageBreak(),
    ]

    # ══════════════════════════════════════════════════════════════════════
    # TABLE DES MATIERES
    # ══════════════════════════════════════════════════════════════════════
    story += [
        H1('Table des mati\u00e8res'),
        hr(NAVY, 0.4, 2, 10),
    ]
    toc = [
        ('Introduction', None),
        ('Partie I', 'Architecture du pipeline multi-agents'),
        ('I.1', 'Vue d\u2019ensemble et principe directeur'),
        ('I.2', 'Le graphe LangGraph : 7 n\u0153uds et routage conditionnel'),
        ('I.3', 'AgentData : collecte multi-sources et scoring de couverture'),
        ('I.4', 'Orchestration parall\u00e8le et gestion de la latence'),
        ('Partie II', 'Rigueur quantitative : le mod\u00e8le financier'),
        ('II.1', 'Les 33 ratios d\u00e9terministes'),
        ('II.2', 'Mod\u00e8les de risque : Altman Z-Score et Beneish M-Score'),
        ('II.3', 'WACC et DCF : param\u00e9trage sectoriel'),
        ('II.4', 'Double validation QA : d\u00e9terministe et \u00e9ditoriale'),
        ('Partie III', 'Synth\u00e8se par intelligence artificielle'),
        ('III.1', 'Strat\u00e9gie multi-fournisseurs et r\u00e9silience LLM'),
        ('III.2', 'AgentSynth\u00e8se : ing\u00e9nierie du prompt et contraintes de sortie'),
        ('III.3', 'Le protocole de l\u2019Avocat du Diable'),
        ('Partie IV', 'Gouvernance constitutionnelle'),
        ('IV.1', 'La Constitution comme contrat formel'),
        ('IV.2', 'Les 7 articles et leurs seuils'),
        ('IV.3', 'Le processus d\u2019amendement'),
        ('Partie V', 'Livrables institutionnels'),
        ('V.1', 'Le rapport PDF (9 pages, ReportLab)'),
        ('V.2', 'Le pitchbook PowerPoint (20 diapositives)'),
        ('V.3', 'Le mod\u00e8le Excel (52 cellules prot\u00e9g\u00e9es)'),
        ('Partie VI', 'Interface et d\u00e9ploiement'),
        ('Partie VII', '\u00c9tat du projet et perspectives'),
        ('Conclusion', None),
    ]
    for num, title in toc:
        if title is None:
            story.append(P(f'<b>{num}</b>', 'toc_h'))
        elif num.startswith('I') and len(num) <= 3 and '.' not in num:
            story.append(P(f'<b>{num} \u2014 {title}</b>', 'toc_h'))
        else:
            story.append(P(f'<font color="#1B2A4A"><b>{num}</b></font>\u2003{title}', 'toc_s'))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════
    # INTRODUCTION
    # ══════════════════════════════════════════════════════════════════════
    story += [
        H1('Introduction'),
        hr(NAVY, 0.4, 2, 8),
    ]
    story += [
        P("L\u2019analyse financi\u00e8re institutionnelle est, dans sa forme classique, "
          "une activit\u00e9 \u00e0 haute intensit\u00e9 de travail qualifi\u00e9. Un analyste "
          "exp\u00e9riment\u00e9 consacre en moyenne 12 \u00e0 20 heures \u00e0 la production "
          "d\u2019un rapport initiation-de-couverture\u00a0: collecte des donn\u00e9es publiques, "
          "construction du mod\u00e8le Excel, r\u00e9daction de la th\u00e8se, mise en forme du "
          "pitchbook. Les cabinets de recherche facturent cet acc\u00e8s entre 5\u202f000 et "
          "50\u202f000\u00a0\u20ac par an selon la couverture. Seules les grandes institutions "
          "financ\u00e8res, fonds d\u2019investissement et family offices peuvent s\u2019y "
          "abonner."),
        P("<b>FinSight IA</b> pose une question radicalement diff\u00e9rente\u00a0: "
          "<i>est-il possible de r\u00e9pliquer la structure logique et la rigueur formelle "
          "de ce processus analytique, en le rendant accessible, v\u00e9rifiable et gratuit ?</i> "
          "La r\u00e9ponse apport\u00e9e n\u2019est pas de remplacer l\u2019analyste humain, "
          "mais de lui fournir \u2014 ou de fournir \u00e0 l\u2019investisseur autonome \u2014 "
          "une premi\u00e8re couche d\u2019analyse structur\u00e9e, quantitative, reproductible, "
          "en moins de 90 secondes, pour toute action cot\u00e9e dans le monde."),
        P("La singularit\u00e9 du projet tient \u00e0 trois partis pris architecturaux. "
          "Premi\u00e8rement, le principe dit \u00ab\u00a0Intel/Watt\u00a0\u00bb\u00a0: ne jamais "
          "soumettre \u00e0 un LLM ce qu\u2019un algorithme Python peut calculer de mani\u00e8re "
          "d\u00e9terministe. Deuxi\u00e8mement, une gouvernance constitutionnelle formelle\u00a0: "
          "sept articles aux seuils mesurables, applicables par code, avec processus "
          "d\u2019amendement vers\u00e9. Troisi\u00e8mement, une r\u00e9silience architecturale "
          "totale\u00a0: aucun fournisseur unique n\u2019est critique ; la cascade de cinq "
          "providers LLM garantit une disponibilit\u00e9 sup\u00e9rieure \u00e0 99\u202f%."),
        P("Ce document d\u00e9crit l\u2019\u00e9tat actuel de la plateforme, ses fondements "
          "techniques et quantitatifs, ses m\u00e9canismes de gouvernance, et la trajectoire "
          "des d\u00e9veloppements \u00e0 venir. Il s\u2019adresse aussi bien \u00e0 un jury "
          "acad\u00e9mique qu\u2019\u00e0 un interlocuteur professionnel souhaitant comprendre "
          "la rigueur sous-jacente \u00e0 un syst\u00e8me d\u2019IA financier d\u00e9ploy\u00e9."),
        PageBreak(),
    ]

    # ══════════════════════════════════════════════════════════════════════
    # PARTIE I — ARCHITECTURE
    # ══════════════════════════════════════════════════════════════════════
    story += [
        H1('Partie I \u2014 Architecture du pipeline multi-agents'),
        hr(NAVY, 0.4, 2, 8),
        H2('I.1 \u00a0 Vue d\u2019ensemble et principe directeur'),
        P("FinSight IA repose sur une architecture pipeline orchestr\u00e9e par "
          "<b>LangGraph</b> (Li et al., 2024), une biblioth\u00e8que de construction "
          "de graphes d\u2019\u00e9tats pour syst\u00e8mes multi-agents, d\u00e9velopp\u00e9e "
          "par LangChain Inc. dans le contexte des architectures LLM \u00e0 m\u00e9moire de "
          "travail partag\u00e9e. Le choix de LangGraph \u2014 plut\u00f4t qu\u2019une "
          "orchestration imp\u00e9rative classique \u2014 permet d\u2019exprimer explicitement "
          "les d\u00e9pendances entre agents, les conditions de bifurcation, et les boucles "
          "de reprise, sous forme d\u2019un graphe orient\u00e9 avec \u00e9tat typ\u00e9."),
        P("Le principe architectur\u00e9 directeur, not\u00e9 <b>\u00ab\u00a0Intel/Watt\u00a0\u00bb</b> "
          "dans la documentation interne, est le suivant\u00a0: <i>l\u2019intelligence artificielle "
          "g\u00e9n\u00e9rative est une ressource rare et co\u00fbteuse en tokens ; elle est "
          "r\u00e9serv\u00e9e aux t\u00e2ches cr\u00e9atives \u00e0 haute valeur ajout\u00e9e "
          "\u2014 synth\u00e8se, argumentation, narration \u2014 tandis que tout calcul "
          "d\u00e9terministe est pris en charge par des algorithmes Python purs</i>. "
          "Ce principe g\u00e9n\u00e8re un syst\u00e8me hybride o\u00f9 la rigueur quantitative "
          "n\u2019est pas d\u00e9l\u00e9gu\u00e9e au mod\u00e8le de langage \u2014 qui "
          "hallucinerait \u2014 mais garantie par le code."),
        H2('I.2 \u00a0 Le graphe LangGraph : 7 n\u0153uds et routage conditionnel'),
        P("L\u2019\u00e9tat du syst\u00e8me est un dictionnaire typ\u00e9 (<code>TypedDict</code>) "
          "transmis de n\u0153ud en n\u0153ud, accumul\u00e9 et jamais \u00e9cras\u00e9. "
          "Chaque n\u0153ud est une fonction Python asynchrone ou synchrone recevant "
          "l\u2019\u00e9tat complet et retournant une mise \u00e0 jour partielle. "
          "Le routage entre n\u0153uds est conditionnel\u00a0: deux variables d\u2019\u00e9tat "
          "pilotent les bifurcations \u2014 <code>data_quality</code> et "
          "<code>confidence_score</code>."),
    ]

    # Pipeline table
    pipe_data = [
        [P('N\u0153ud', 'th'), P('Agent', 'th'), P('R\u00f4le', 'th'), P('Sortie cl\u00e9', 'th')],
        [P('fetch_node', 'td_mono'), P('AgentData + AgentSentiment', 'td'),
         P('Collecte donn\u00e9es 5 ans, news, sentiment FinBERT', 'td'),
         P('FinancialSnapshot + data_quality', 'td')],
        [P('fallback_node', 'td_mono'), P('AgentData (retry)', 'td'),
         P('Enrichissement si data_quality < 0,70', 'td'),
         P('FinancialSnapshot am\u00e9lior\u00e9', 'td')],
        [P('quant_node', 'td_mono'), P('AgentQuant (Python pur)', 'td'),
         P('Calcul 33 ratios, Altman Z, Beneish M', 'td'),
         P('RatiosResult (aucun LLM)', 'td')],
        [P('synthesis_node', 'td_mono'), P('AgentSynth\u00e8se (LLM)', 'td'),
         P('G\u00e9n\u00e9ration th\u00e8se JSON structur\u00e9e, 70 champs', 'td'),
         P('SynthesisResult + confidence_score', 'td')],
        [P('qa_node', 'td_mono'), P('AgentQAPython + AgentQAHaiku', 'td'),
         P('Validation d\u00e9terministe + \u00e9ditoriale (parall\u00e8le)', 'td'),
         P('QAResult : flags, qa_score', 'td')],
        [P('devil_node', 'td_mono'), P('AgentDevil (LLM)', 'td'),
         P('Th\u00e8se inverse, conviction_delta', 'td'),
         P('DevilResult : counter_reco, delta', 'td')],
        [P('output_node', 'td_mono'), P('ExcelWriter + PDFWriter + PPTXWriter', 'td'),
         P('Rendu des trois livrables (parall\u00e8le)', 'td'),
         P('Binaires Excel, PDF, PPTX', 'td')],
    ]
    story += [
        sp(6),
        TBL(pipe_data, [2.8*cm, 3.8*cm, 5.8*cm, 3.6*cm]),
        Cap('Tableau 1 \u2014 Architecture du pipeline LangGraph : 7 n\u0153uds et leurs r\u00f4les'),
    ]

    story += [
        P("Le routage conditionnel suit la logique suivante. Apr\u00e8s "
          "<code>fetch_node</code>, si <code>data_quality < 0,70</code>, "
          "le graphe d\u00e9vise vers <code>fallback_node</code> avant de rejoindre "
          "<code>quant_node</code>. Apr\u00e8s <code>synthesis_node</code>, si "
          "<code>confidence_score < 0,45</code> (Article 1 de la Constitution), "
          "un n\u0153ud <code>blocked_node</code> est activ\u00e9 et le rapport est "
          "\u00e9mis avec une recommandation d\u00e9grad\u00e9e en HOLD. Enfin, "
          "si le passage QA \u00e9choue et que le compteur de reprises est inf\u00e9rieur "
          "\u00e0 1, le graphe boucle vers <code>synthesis_retry</code> avant "
          "de r\u00e9\u00e9valuer par QA."),
        H2('I.3 \u00a0 AgentData : collecte multi-sources et scoring de couverture'),
        P("L\u2019<b>AgentData</b> est le premier agent du pipeline. Il ne fait "
          "appel \u00e0 aucun mod\u00e8le de langage. Sa mission est exclusivement "
          "de collecter, normaliser et scorer les donn\u00e9es financi\u00e8res "
          "historiques d\u2019une entreprise sur cinq exercices fiscaux."),
        P("La strat\u00e9gie de collecte est hirarchis\u00e9e en trois niveaux, "
          "ex\u00e9cut\u00e9s en parall\u00e8le via <code>ThreadPoolExecutor</code>\u00a0:"),
        B("<b>yfinance</b> (niveau 1)\u00a0: source primaire. Acc\u00e8s gratuit, "
          "illimit\u00e9, couvrant la quasi-totalit\u00e9 des soci\u00e9t\u00e9s cot\u00e9es "
          "mondiales. Fournit le compte de r\u00e9sultat, le bilan, le tableau de flux "
          "de tr\u00e9sorerie sur 5 ans, ainsi que les prix boursiers mensuels."),
        B("<b>Financial Modeling Prep API</b> (niveau 2)\u00a0: fallback pour les donn\u00e9es "
          "non disponibles via yfinance, notamment les m\u00e9triques de valorisation "
          "fine et les soci\u00e9t\u00e9s europ\u00e9ennes. Plan gratuit limit\u00e9 "
          "\u00e0 250 requ\u00eates/jour."),
        B("<b>Finnhub API</b> (niveau 3)\u00a0: compl\u00e9ment pour les donn\u00e9es "
          "de march\u00e9 en temps r\u00e9el (cours actuel, b\u00eata lev\u00e9, flux "
          "d\u2019actualit\u00e9s sp\u00e9cifiques au ticker)."),
        sp(4),
        P("Le <b>score de couverture</b> de chaque ann\u00e9e est calcul\u00e9 "
          "selon la formule suivante, \u00e9valuant la compl\u00e9tude du mod\u00e8le "
          "financier\u00a0:"),
        Fm("coverage(ann\u00e9e) = | champs non-nuls | / | champs totaux de FinancialYear |"),
        Fm("data_quality = moyenne(coverage(ann\u00e9e)) sur toutes les ann\u00e9es disponibles"),
        Cap('Formule 1 \u2014 Calcul du score de couverture des donn\u00e9es financieres'),
        P("Le mod\u00e8le de donn\u00e9es <code>FinancialYear</code> comporte 39 champs "
          "r\u00e9partis en cinq cat\u00e9gories\u00a0: compte de r\u00e9sultat (9 champs), "
          "actif du bilan (7), passif du bilan (6), flux de tr\u00e9sorerie (10), "
          "agr\u00e9gats yfinance (7). Chaque champ manquant d\u00e9grade le score. "
          "Un score inf\u00e9rieur \u00e0 0,70 d\u00e9clenche le fallback et, si "
          "persistant, contraint la recommandation \u00e0 HOLD conform\u00e9ment "
          "\u00e0 l\u2019Article 2 de la Constitution."),
        H2('I.4 \u00a0 Orchestration parall\u00e8le et gestion de la latence'),
        P("Deux phases du pipeline font l\u2019objet d\u2019une ex\u00e9cution "
          "parall\u00e8le afin de minimiser la latence totale. Premi\u00e8rement, "
          "lors de <code>fetch_node</code>, la collecte des donn\u00e9es fondamentales "
          "(yfinance) et l\u2019analyse de sentiment (AgentSentiment via FinBERT + Finnhub) "
          "sont lanc\u00e9es simultan\u00e9ment dans deux threads s\u00e9par\u00e9s. "
          "Deuxi\u00e8mement, lors de <code>qa_node</code>, la validation d\u00e9terministe "
          "(AgentQAPython, ~100ms) et la validation \u00e9ditoriale LLM (AgentQAHaiku, "
          "~2s) s\u2019ex\u00e9cutent en parall\u00e8le via <code>concurrent.futures</code>."),
    ]
    lat_data = [
        [P('\u00c9tape', 'th'), P('Latence typ.', 'th'), P('D\u00e9tail', 'th')],
        [P('fetch_node', 'td'), P('1,5 \u2013 3 s', 'tdc'), P('yfinance + FinBERT en parall\u00e8le', 'td')],
        [P('quant_node', 'td'), P('< 200 ms', 'tdc'), P('Python pur, z\u00e9ro r\u00e9seau', 'td')],
        [P('synthesis_node', 'td'), P('8 \u2013 12 s', 'tdc'), P('LLM Groq ~4 000 tokens', 'td')],
        [P('qa_node', 'td'), P('2 \u2013 3 s', 'tdc'), P('D\u00e9terministe + LLM haiku (||)', 'td')],
        [P('devil_node', 'td'), P('5 \u2013 7 s', 'tdc'), P('LLM th\u00e8se inverse', 'td')],
        [P('output_node', 'td'), P('8 \u2013 15 s', 'tdc'), P('Excel + PDF + PPTX en parall\u00e8le', 'td')],
        [P('<b>Total (m\u00e9diane)</b>', 'td'), P('<b>~60 s</b>', 'tdc'), P('Sans reprise QA', 'td')],
    ]
    story += [
        sp(4),
        TBL(lat_data, [4*cm, 3*cm, 9*cm]),
        Cap('Tableau 2 \u2014 Latences par n\u0153ud du pipeline (valeurs typ. sur connexion standard)'),
        PageBreak(),
    ]

    # ══════════════════════════════════════════════════════════════════════
    # PARTIE II — RIGUEUR QUANTITATIVE
    # ══════════════════════════════════════════════════════════════════════
    story += [
        H1('Partie II \u2014 Rigueur quantitative : le mod\u00e8le financier'),
        hr(NAVY, 0.4, 2, 8),
        H2('II.1 \u00a0 Les 33 ratios d\u00e9terministes'),
        P("L\u2019<b>AgentQuant</b> calcule 33 ratios financiers r\u00e9partis en "
          "huit cat\u00e9gories analytiques, tous impl\u00e9ment\u00e9s en Python pur. "
          "Le principe de design est strict\u00a0: aucun ratio n\u2019est estim\u00e9 ou "
          "interp\u00e9t\u00e9 par un LLM. Tout repose sur les donn\u00e9es historiques "
          "collect\u00e9es par AgentData. Le calcul est reproductible, v\u00e9rifiable "
          "et stable."),
    ]
    ratio_data = [
        [P('Cat\u00e9gorie', 'th'), P('Ratios calcul\u00e9s', 'th'), P('N', 'th')],
        [P('Rentabilit\u00e9', 'td'),
         P('Gross margin, EBITDA margin, EBIT margin, Net margin, ROE, ROA, ROIC, FCF margin', 'td'),
         P('8', 'tdc')],
        [P('Croissance', 'td'),
         P('Revenue growth YoY, EBITDA growth, Gross profit growth, FCF growth', 'td'),
         P('4', 'tdc')],
        [P('Levier financier', 'td'),
         P('Debt/Equity, Net Debt/EBITDA, Interest coverage', 'td'),
         P('3', 'tdc')],
        [P('Liquidit\u00e9', 'td'),
         P('Current ratio, Quick ratio', 'td'),
         P('2', 'tdc')],
        [P('Efficience op.', 'td'),
         P('Asset turnover, DSO, DIO, DPO, Cash Conversion Cycle (CCC)', 'td'),
         P('5', 'tdc')],
        [P('Valorisation', 'td'),
         P('P/E, EV/EBITDA, EV/Revenue, P/B, FCF yield', 'td'),
         P('5', 'tdc')],
        [P('Allocation capital', 'td'),
         P('CapEx ratio, R&D ratio, Dividend payout', 'td'),
         P('3', 'tdc')],
        [P('Risque quantitatif', 'td'),
         P('Altman Z-Score, Beneish M-Score, Net Debt/EV', 'td'),
         P('3', 'tdc')],
        [P('<b>Total</b>', 'td'), P('', 'td'), P('<b>33</b>', 'tdc')],
    ]
    story += [
        sp(4),
        TBL(ratio_data, [3.5*cm, 11*cm, 1.5*cm]),
        Cap('Tableau 3 \u2014 Les 33 ratios d\u00e9terministes calcul\u00e9s par AgentQuant'),
        H2('II.2 \u00a0 Mod\u00e8les de risque\u00a0: Altman Z-Score et Beneish M-Score'),
        P("Le syst\u00e8me impl\u00e9mente deux mod\u00e8les de risque acad\u00e9miquement "
          "\u00e9tablis, tr\u00e8s utilis\u00e9s dans la pratique institutionnelle "
          "mais rarement automatis\u00e9s \u00e0 l\u2019\u00e9chelle."),
        H3("L\u2019Altman Z-Score (Altman, 1968)"),
        P("Le mod\u00e8le d\u2019<b>Edward Altman (1968)</b>, publi\u00e9 dans le "
          "<i>Journal of Finance</i>, est un score mul-tidiscriminant pr\u00e9dicteur "
          "de d\u00e9faillance d\u2019entreprise. Il combine cinq ratios financiers "
          "pond\u00e9r\u00e9s par r\u00e9gression discriminante lin\u00e9aire sur un "
          "\u00e9chantillon de 66 entreprises am\u00e9ricaines (33 d\u00e9faillantes, "
          "33 saines)\u00a0:"),
        Fm("Z = 1,2\u00d7X\u2081 + 1,4\u00d7X\u2082 + 3,3\u00d7X\u2083 + 0,6\u00d7X\u2084 + 1,0\u00d7X\u2085"),
        P("O\u00f9\u00a0: X\u2081 = Fonds de roulement / Total actif\u00a0; "
          "X\u2082 = B\u00e9n\u00e9fices non distribu\u00e9s / Total actif\u00a0; "
          "X\u2083 = EBIT / Total actif\u00a0; "
          "X\u2084 = Capitalisation boursi\u00e8re / Total passif\u00a0; "
          "X\u2085 = Chiffre d\u2019affaires / Total actif."),
        P("Les seuils de classification sont les suivants\u00a0: Z > 2,99 (zone s\u00fbre), "
          "1,81 \u2264 Z \u2264 2,99 (zone grise, surveillance renforc\u00e9e), "
          "Z < 1,81 (zone de d\u00e9tresse, risque de faillite 60\u201380\u202f% sur "
          "24 mois dans l\u2019\u00e9tude originale). Dans FinSight IA, un score "
          "Z < 1,81 g\u00e9n\u00e8re un flag <code>ERROR</code> dans AgentQAPython "
          "et d\u00e9grade le <code>qa_score</code> de 15\u202f%."),
        H3("Le Beneish M-Score (Beneish, 1999)"),
        P("<b>Messod Beneish (1999)</b>, dans \u00ab\u00a0The Detection of Earnings "
          "Manipulation\u00a0\u00bb publi\u00e9 dans le <i>Financial Analysts Journal</i>, "
          "propose un mod\u00e8le probabiliste de d\u00e9tection de manipulation comptable "
          "\u00e0 huit variables\u00a0:"),
        Fm("M = \u22124,84 + 0,920\u00d7DSRI + 0,528\u00d7GMI + 0,404\u00d7AQI + 0,892\u00d7SGI"),
        Fm("       + 0,115\u00d7DEPI \u2212 0,172\u00d7SGAI + 4,679\u00d7TATA \u2212 0,327\u00d7LVGI"),
        Cap("Formule 2 \u2014 Beneish M-Score (8 variables comptables)"),
        P("Les huit indices mesurent respectivement\u00a0: la d\u00e9rive du DSO "
          "(DSRI), la d\u00e9t\u00e9rioration des marges brutes (GMI), la qualit\u00e9 "
          "de l\u2019actif (AQI), la croissance des ventes (SGI), la d\u00e9pr\u00e9ciation "
          "(DEPI), les frais g\u00e9n\u00e9raux anormaux (SGAI), la qualit\u00e9 des "
          "accruals (TATA) et le levier financier (LVGI). Un score M > \u22122,22 "
          "est le seuil d\u2019alerte\u00a0; dans ce cas, FinSight IA \u00e9met un "
          "flag <code>WARNING</code> indiquant un risque de manipulation des r\u00e9sultats."),
        H2('II.3 \u00a0 WACC et DCF\u00a0: param\u00e9trage sectoriel'),
        P("Le co\u00fbt moyen pond\u00e9r\u00e9 du capital (<b>WACC</b>) est calcul\u00e9 "
          "selon la formule fondamentale de la th\u00e9orie financi\u00e8re "
          "(Modigliani & Miller, 1958\u00a0; Miles & Ezzell, 1980)\u00a0:"),
        Fm("WACC = (E/V \u00d7 Re) + (D/V \u00d7 Rd \u00d7 (1 \u2212 Tc))"),
        P("O\u00f9\u00a0: E = capitalisation boursi\u00e8re, D = dette totale, "
          "V = E + D, Re = co\u00fbt des fonds propres (CAPM), "
          "Rd = co\u00fbt de la dette (charges financi\u00e8res / dette totale), "
          "Tc = taux d\u2019imposition effectif ou sectoriel. "
          "Le co\u00fbt des fonds propres est d\u00e9riv\u00e9 du mod\u00e8le CAPM "
          "(Sharpe, 1964)\u00a0: Re = Rf + \u03b2 \u00d7 ERP. "
          "Le taux sans risque (Rf) est extrait en temps r\u00e9el depuis l\u2019instrument "
          "^TNX (obligation du Tr\u00e9sor am\u00e9ricain 10 ans) via yfinance. "
          "La prime de risque actions (ERP) est param\u00e9tr\u00e9e par secteur GICS\u00a0:"),
    ]
    sector_data = [
        [P('Secteur GICS', 'th'), P('ERP (%)', 'th'), P('Croiss. terminale (%)', 'th'),
         P('Cible marge EBITDA (%)', 'th')],
        [P('Technology', 'td'), P('5,5', 'tdc'), P('3,0', 'tdc'), P('26', 'tdc')],
        [P('Health Care', 'td'), P('5,5', 'tdc'), P('2,5', 'tdc'), P('23', 'tdc')],
        [P('Financials', 'td'), P('5,5', 'tdc'), P('2,5', 'tdc'), P('30', 'tdc')],
        [P('Energy', 'td'), P('6,0', 'tdc'), P('1,5', 'tdc'), P('20', 'tdc')],
        [P('Utilities', 'td'), P('5,0', 'tdc'), P('2,0', 'tdc'), P('28', 'tdc')],
        [P('Industrials', 'td'), P('5,5', 'tdc'), P('2,5', 'tdc'), P('18', 'tdc')],
        [P('Consumer Discretionary', 'td'), P('5,5', 'tdc'), P('2,5', 'tdc'), P('15', 'tdc')],
    ]
    story += [
        sp(4),
        TBL(sector_data, [5*cm, 2.5*cm, 3.5*cm, 4*cm]),
        Cap('Tableau 4 \u2014 Param\u00e8tres sectoriels utilis\u00e9s pour le calcul du WACC et du DCF (extrait)'),
        P("La valeur terminale est calcul\u00e9e selon le mod\u00e8le de Gordon "
          "(Gordon & Shapiro, 1956)\u00a0:"),
        Fm("TV = FCF\u209f \u00d7 (1 + g) / (WACC \u2212 g)"),
        Fm("VP(TV) = TV / (1 + WACC)\u207f"),
        Cap("Formule 3 \u2014 Valeur terminale (mod\u00e8le de Gordon) et sa valeur pr\u00e9sente"),
        P("O\u00f9 g est le taux de croissance terminal sectoriel et n est l\u2019horizon "
          "de projection explicite (2 ans dans le mod\u00e8le actuel\u00a0: N+1 et N+2). "
          "Les projections de flux de tr\u00e9sorerie disponibles sur l\u2019horizon "
          "explicite sont g\u00e9n\u00e9r\u00e9es par AgentSynth\u00e8se en lien avec "
          "les param\u00e8tres sectoriels ci-dessus, garantissant une coh\u00e9rence "
          "entre la th\u00e8se narrative et les hypoth\u00e8ses financi\u00e8res."),
        H2('II.4 \u00a0 Double validation QA\u00a0: d\u00e9terministe et \u00e9ditoriale'),
        P("La validation de la synth\u00e8se est assur\u00e9e par deux agents ind\u00e9pendants "
          "ex\u00e9cut\u00e9s en parall\u00e8le, conform\u00e9ment \u00e0 l\u2019Article 3 "
          "de la Constitution."),
        P("<b>AgentQAPython</b> impl\u00e9mente dix v\u00e9rifications d\u00e9terministes. "
          "Les plus critiques\u00a0: (i) <i>coh\u00e9rence des marges</i> \u2014 "
          "la marge nette doit \u00eatre inf\u00e9rieure \u00e0 la marge brute, l\u2019EBITDA "
          "inf\u00e9rieur au gross profit\u00a0; (ii) <i>plausibilit\u00e9 du prix cible</i> "
          "\u2014 le ratio prix cible / cours actuel doit \u00eatre compris dans [0,20\u00a0; "
          "5,0]\u00a0; (iii) <i>coh\u00e9rence recommandation / profil</i> \u2014 un BUY sur "
          "un Z-Score en zone de d\u00e9tresse g\u00e9n\u00e8re un flag ERROR. Chaque flag "
          "d\u00e9grade le <code>qa_score</code> de 0\u202f% (INFO), 5\u202f% (WARNING) "
          "ou 15\u202f% (ERROR)."),
        P("<b>AgentQAHaiku</b> (mod\u00e8le LLM l\u00e9ger, Claude Haiku ou Mistral) "
          "\u00e9value quatre dimensions qualitatives\u00a0: le professionnalisme du ton "
          "(standard IB), la coh\u00e9rence interne de la th\u00e8se, la pr\u00e9cision "
          "des formulations (chiffres cit\u00e9s, unit\u00e9s, horizons temporels), "
          "et la compl\u00e9tude du rapport (r\u00e9sum\u00e9, forces, risques, "
          "conditions d\u2019invalidation). En cas de d\u00e9faillance majeure, "
          "il g\u00e9n\u00e8re un r\u00e9sum\u00e9 am\u00e9lior\u00e9 qui est substitu\u00e9 "
          "\u00e0 l\u2019original."),
        PageBreak(),
    ]

    # ══════════════════════════════════════════════════════════════════════
    # PARTIE III — IA ET SYNTHESE
    # ══════════════════════════════════════════════════════════════════════
    story += [
        H1('Partie III \u2014 Synth\u00e8se par intelligence artificielle'),
        hr(NAVY, 0.4, 2, 8),
        H2('III.1 \u00a0 Strat\u00e9gie multi-fournisseurs et r\u00e9silience LLM'),
        P("L\u2019architecture LLM de FinSight IA repose sur un principe de "
          "<b>cascade de fournisseurs</b>\u00a0: aucun provider unique n\u2019est "
          "critique. La classe <code>LLMProvider</code> impl\u00e9mente une "
          "abstraction unifi\u00e9e sur six fournisseurs, interrog\u00e9s dans l\u2019ordre "
          "de pr\u00e9f\u00e9rence suivant\u00a0:"),
    ]
    llm_data = [
        [P('Priorit\u00e9', 'th'), P('Fournisseur', 'th'), P('Mod\u00e8le', 'th'),
         P('Caract\u00e9ristiques', 'th')],
        [P('1', 'tdc'), P('Groq', 'td'), P('llama-3.3-70b-versatile', 'td'),
         P('Gratuit, 70B param., ultra-rapide (~200 tok/s)', 'td')],
        [P('2', 'tdc'), P('Mistral AI', 'td'), P('mistral-small-latest', 'td'),
         P('Plan gratuit, fiable, fallback Europe', 'td')],
        [P('3', 'tdc'), P('Cerebras', 'td'), P('qwen-3-235b', 'td'),
         P('Inf\u00e9rence tr\u00e8s rapide, 235B param.', 'td')],
        [P('4', 'tdc'), P('Anthropic', 'td'), P('claude-haiku-4-5', 'td'),
         P('Fiable, qualit\u00e9 \u00e9ditoriale \u00e9lev\u00e9e', 'td')],
        [P('5', 'tdc'), P('Google Gemini', 'td'), P('gemini-2.0-flash', 'td'),
         P('Secours d\u2019urgence', 'td')],
        [P('6', 'tdc'), P('Ollama (local)', 'td'), P('qwen3:14b', 'td'),
         P('D\u00e9veloppement / tests hors ligne', 'td')],
    ]
    story += [
        sp(4),
        TBL(llm_data, [1.5*cm, 2.8*cm, 4.2*cm, 7.5*cm]),
        Cap('Tableau 5 \u2014 Cascade de fournisseurs LLM (ordre de pr\u00e9f\u00e9rence)'),
        P("Un m\u00e9canisme de <b>rotation des cl\u00e9s Groq</b> est impl\u00e9ment\u00e9 "
          "dans <code>core/llm_provider.py</code>\u00a0: le syst\u00e8me lit les variables "
          "<code>GROQ_API_KEY_1</code>, <code>GROQ_API_KEY_2</code>\u2026 depuis le "
          "fichier <code>.env</code>, suit la consommation de tokens par cl\u00e9 dans "
          "<code>logs/groq_usage.json</code>, et bascule automatiquement vers la cl\u00e9 "
          "suivante lorsque le seuil quotidien est atteint. Les compteurs sont r\u00e9initialis\u00e9s "
          "chaque jour \u00e0 minuit UTC. Cette approche garantit une disponibilit\u00e9 "
          "effective sup\u00e9rieure \u00e0 99\u202f% sans aucun co\u00fbt."),
        H2('III.2 \u00a0 AgentSynth\u00e8se\u00a0: ing\u00e9nierie du prompt et contraintes de sortie'),
        P("L\u2019<b>AgentSynth\u00e8se</b> est l\u2019agent central du syst\u00e8me. "
          "Il re\u00e7oit en entr\u00e9e l\u2019\u00e9tat complet du pipeline "
          "\u2014 donn\u00e9es historiques 5 ans, 33 ratios calcul\u00e9s, score "
          "de sentiment FinBERT, param\u00e8tres sectoriels \u2014 et doit produire "
          "un document JSON structur\u00e9 de 70 champs strictement d\u00e9finis."),
        P("Le prompt syst\u00e8me impose des contraintes formelles importantes\u00a0: "
          "sortie JSON uniquement (z\u00e9ro markdown)\u00a0; longueur prescrite pour chaque "
          "champ narratif (<code>company_description</code>\u00a0: 50\u201370 mots, "
          "<code>thesis</code>\u00a0: 3 phrases de 18\u201322 mots chacune)\u00a0; "
          "quantification obligatoire des catalyseurs (impact financier chiffr\u00e9)\u00a0; "
          "trois sc\u00e9narios de valorisation (Bull / Base / Bear) avec hypoth\u00e8ses "
          "explicites\u00a0; et cinq soci\u00e9t\u00e9s comparables avec leurs multiples."),
        P("Le <code>SynthesisResult</code> produit contient notamment\u00a0: "
          "<code>recommendation</code> (BUY / HOLD / SELL), <code>conviction</code> "
          "(0,0\u20131,0), <code>target_base</code> / <code>target_bull</code> / "
          "<code>target_bear</code> (prix en devise locale), les projections "
          "<code>is_projections</code> (N+1 et N+2 avec revenus, marges, b\u00e9n\u00e9fice "
          "net), le <code>football_field</code> (6 sc\u00e9narios de valorisation "
          "DCF + multiples), et les <code>invalidation_list</code> "
          "(d\u00e9clencheurs macro, sectoriels et sp\u00e9cifiques \u00e0 la soci\u00e9t\u00e9)."),
        H2('III.3 \u00a0 Le protocole de l\u2019Avocat du Diable'),
        P("Une singularit\u00e9 de FinSight IA est l\u2019int\u00e9gration syst\u00e9matique "
          "d\u2019un <b>protocole d\u2019inversion de th\u00e8se</b>, inspir\u00e9 des "
          "pratiques de <i>red teaming</i> en s\u00e9curit\u00e9 des syst\u00e8mes IA. "
          "L\u2019<b>AgentDevil</b> re\u00e7oit la synth\u00e8se valid\u00e9e et doit "
          "\u00e9laborer, sans aucune concession, la contre-th\u00e8se la plus solide "
          "possible."),
        P("Le prompt syst\u00e8me de l\u2019AgentDevil proscrit explicitement certains "
          "termes\u00a0: \u00ab\u00a0opportunit\u00e9\u00a0\u00bb, \u00ab\u00a0solide\u00a0\u00bb, "
          "\u00ab\u00a0r\u00e9silient\u00a0\u00bb, \u00ab\u00a0catalyseur positif\u00a0\u00bb. "
          "La sortie inclut trois contre-argumentations de 40\u201355 mots chacune, "
          "un <code>conviction_delta</code> compris dans [\u22121,0\u00a0; 0,0] "
          "mesurant la fragilit\u00e9 de la th\u00e8se principale, et une liste "
          "d\u2019hypoth\u00e8ses sous-jacentes consid\u00e9r\u00e9es comme "
          "\u00ab\u00a0fragiles\u00a0\u00bb."),
        P("Ce module am\u00e9liore la qualit\u00e9 d\u00e9cisionnelle du rapport en "
          "for\u00e7ant la confrontation \u00e0 la th\u00e8se adverse avant toute "
          "publication. Un <code>conviction_delta</code> de \u22120,3 indique que "
          "la th\u00e8se principale, bien que majoritaire, pr\u00e9sente des "
          "vuln\u00e9rabilit\u00e9s non n\u00e9gligeables ; "
          "\u22120,05 signale une th\u00e8se tr\u00e8s robuste \u00e0 l\u2019analyse "
          "adverse."),
        PageBreak(),
    ]

    # ══════════════════════════════════════════════════════════════════════
    # PARTIE IV — GOUVERNANCE
    # ══════════════════════════════════════════════════════════════════════
    story += [
        H1('Partie IV \u2014 Gouvernance constitutionnelle'),
        hr(NAVY, 0.4, 2, 8),
        H2('IV.1 \u00a0 La Constitution comme contrat formel'),
        P("La gouvernance de FinSight IA repose sur un m\u00e9canisme original\u00a0: "
          "une <b>Constitution formelle \u00e0 sept articles</b>, impl\u00e9ment\u00e9e "
          "dans <code>config/constitution.py</code> sous forme de dataclasses Python. "
          "Chaque article d\u00e9finit un seuil num\u00e9rique ou une r\u00e8gle "
          "proc\u00e9durale, appliqu\u00e9 par le graphe d\u2019\u00e9tats lors de "
          "l\u2019ex\u00e9cution."),
        P("Ce choix de design repr\u00e9sente une contribution int\u00e9ressante "
          "\u00e0 la r\u00e9flexion sur la gouvernance des syst\u00e8mes IA\u00a0: "
          "plut\u00f4t qu\u2019un ensemble de r\u00e8gles informelles ou de guidelines "
          "textuelles, la Constitution est ex\u00e9cutable, vers\u00e9e, et "
          "amendable via un processus formel. La fonction "
          "<code>check_compliance(state) \u2192 List[Violation]</code> parcourt "
          "chaque article et retourne les violations \u00e9ventuelles, permettant "
          "au pipeline d\u2019agir en cons\u00e9quence."),
        H2('IV.2 \u00a0 Les 7 articles et leurs seuils'),
    ]
    const_data = [
        [P('Art.', 'th'), P('Intitul\u00e9', 'th'), P('Seuil / R\u00e8gle', 'th'),
         P('Effet en cas de violation', 'th')],
        [P('1', 'tdc'), P('Confiance minimale', 'td'),
         P('confidence_score \u2265 0,45', 'td'),
         P('Activation blocked_node, recommandation HOLD forc\u00e9e', 'td')],
        [P('2', 'tdc'), P('Qualit\u00e9 des donn\u00e9es', 'td'),
         P('data_quality \u2265 0,70 apr\u00e8s fallback', 'td'),
         P('Output d\u00e9grad\u00e9, pas de prix cible, HOLD', 'td')],
        [P('3', 'tdc'), P('Politique de reprise QA', 'td'),
         P('qa_retries \u2264 1', 'td'),
         P('Au-del\u00e0 d\u2019une reprise, rapport \u00e9mis avec flags', 'td')],
        [P('4', 'tdc'), P('Int\u00e9grit\u00e9 Excel', 'td'),
         P('52 cellules formule prot\u00e9g\u00e9es', 'td'),
         P('Log ERROR, \u00e9criture bloqu\u00e9e silencieusement', 'td')],
        [P('5', 'tdc'), P('Droits des agents observateurs', 'td'),
         P('Lecture seule sur logs et m\u00e9triques RH', 'td'),
         P('Agents Sociologue / Enqu\u00eate / Journaliste non modifiables', 'td')],
        [P('6', 'tdc'), P('Pouvoirs de l\u2019AgentJustice', 'td'),
         P('Proc\u00e9dure formelle d\u2019amendement', 'td'),
         P('Proposition archive JSON, validation humaine requise', 'td')],
        [P('7', 'tdc'), P('Processus d\u2019amendement', 'td'),
         P('7 jours observation + approbation humaine', 'td'),
         P('Amendement vers\u00e9 dans knowledge/amendments/', 'td')],
    ]
    story += [
        sp(4),
        TBL(const_data, [1*cm, 3.5*cm, 4.5*cm, 7*cm]),
        Cap('Tableau 6 \u2014 Les 7 articles de la Constitution FinSight IA et leurs effets'),
        H2('IV.3 \u00a0 Le processus d\u2019amendement'),
        P("Le processus d\u2019amendement constitue un apport m\u00e9thodologique notable. "
          "L\u2019<b>AgentJustice</b> analyse p\u00e9riodiquement les logs du pipeline "
          "et peut proposer une modification constitutionnelle si le taux de violation "
          "d\u2019un article d\u00e9passe 20\u202f% sur la p\u00e9riode d\u2019observation. "
          "La proposition est arch\u00e9e au format JSON dans "
          "<code>knowledge/amendments/</code>, accompagn\u00e9e des preuves "
          "(\u00e9chantillon de logs concern\u00e9s), d\u2019une simulation de l\u2019impact "
          "du nouveau seuil, et d\u2019un identifiant unique. La validation finale "
          "requiert une action humaine explicite via la fonction "
          "<code>validate_amendment(id)</code>. Ce processus garantit qu\u2019aucune "
          "modification du cadre de gouvernance ne peut intervenir sans tra\u00e7abilit\u00e9 "
          "et approbation humaine."),
        PageBreak(),
    ]

    # ══════════════════════════════════════════════════════════════════════
    # PARTIE V — LIVRABLES
    # ══════════════════════════════════════════════════════════════════════
    story += [
        H1('Partie V \u2014 Livrables institutionnels'),
        hr(NAVY, 0.4, 2, 8),
        P("FinSight IA produit trois livrables de qualit\u00e9 institutionnelle, "
          "g\u00e9n\u00e9r\u00e9s en parall\u00e8le lors de <code>output_node</code>. "
          "Chacun est con\u00e7u pour \u00eatre directement utilisable sans retouche "
          "manuelle."),
        H2('V.1 \u00a0 Le rapport PDF\u00a0: ReportLab, 9 pages'),
        P("Le rapport PDF est g\u00e9n\u00e9r\u00e9 par ReportLab, biblioth\u00e8que "
          "Python de rendu vectoriel de qualit\u00e9 typographique. Il comporte "
          "9 pages organisatives\u00a0:"),
    ]
    pdf_data = [
        [P('Page', 'th'), P('Section', 'th'), P('Contenu', 'th')],
        [P('1', 'tdc'), P('Couverture', 'td'), P('Ticker, nom, recommandation color\u00e9e, prix cible, WACC', 'td')],
        [P('2', 'tdc'), P('Points cl\u00e9s', 'td'), P('KPIs\u00a0: cours, P/E, EV/EBITDA, capitalisation, dividende', 'td')],
        [P('3', 'tdc'), P('Synth\u00e8se', 'td'), P('Th\u00e8se (3 bullets), sc\u00e9narios, catalyseurs', 'td')],
        [P('4', 'tdc'), P('Financials', 'td'), P('Tableau 5 ans\u00a0: CA, EBITDA, marges, P/E', 'td')],
        [P('5', 'tdc'), P('Comparable peers', 'td'), P('5 pairs sectoriels avec multiples (EV/EBITDA, P/E)', 'td')],
        [P('6', 'tdc'), P('DCF', 'td'), P('3 sc\u00e9narios valorisation (Bear / Base / Bull)', 'td')],
        [P('7', 'tdc'), P('Football field', 'td'), P('Graphe matplotlib\u00a0: 6 plages de valorisation', 'td')],
        [P('8', 'tdc'), P('Avocat du diable', 'td'), P('Contre-th\u00e8se, conviction_delta, hypoth\u00e8ses fragiles', 'td')],
        [P('9', 'tdc'), P('Risques & suivi', 'td'), P('Catalyseurs, d\u00e9clencheurs de r\u00e9vision, date prochain suivi', 'td')],
    ]
    story += [
        sp(4),
        TBL(pdf_data, [1.5*cm, 3.5*cm, 11*cm]),
        Cap('Tableau 7 \u2014 Structure du rapport PDF (9 pages)'),
        H2('V.2 \u00a0 Le pitchbook PowerPoint (20 diapositives)'),
        P("Le pitchbook est g\u00e9n\u00e9r\u00e9 par <code>python-pptx</code>, "
          "une biblioth\u00e8que Python de manipulation du format Open XML. "
          "Les 20 diapositives suivent la structure standard d\u2019un pitchbook "
          "de banque d\u2019investissement, compos\u00e9 de cinq sections "
          "num\u00e9rot\u00e9es avec diapositives de s\u00e9paration\u00a0: "
          "synth\u00e8se macro et signal global (slides 1\u20137), cartographie "
          "des secteurs (8\u201311), Top 3 secteurs recommand\u00e9s (12\u201315), "
          "risques, rotation et sentiment (16\u201320). Chaque graphique "
          "\u2014 scatter plot EV/EBITDA vs croissance, distribution des valorisations, "
          "performance ETF 52 semaines, zone d\u2019entr\u00e9e optimale \u2014 "
          "est g\u00e9n\u00e9r\u00e9 dynamiquement par matplotlib et int\u00e9gr\u00e9 "
          "au format PNG embarqu\u00e9. La palette visuelle (bleu marine #1B2A4A, "
          "vert #1A7A4A) est conforme aux standards de la communication financi\u00e8re "
          "institutionnelle."),
        H2('V.3 \u00a0 Le mod\u00e8le Excel\u00a0: 52 cellules prot\u00e9g\u00e9es'),
        P("Le fichier Excel est inject\u00e9 dans un template pr\u00e9-formul\u00e9 via "
          "la biblioth\u00e8que <code>openpyxl</code>. Le template comporte sept "
          "feuilles\u00a0: INPUT (donn\u00e9es historiques injectes), RATIOS "
          "(32 ratios calcul\u00e9s par formules Excel natives), DCF, COMPARABLES, "
          "SCENARIOS, DASHBOARD et DASHBOARD 2."),
        P("La protection des cellules formule constitue un m\u00e9canisme de garde "
          "critique. 52 adresses de cellules sont list\u00e9es dans "
          "<code>FORMULA_CELLS</code> dans <code>config/excel_mapping.py</code>. "
          "Toute tentative d\u2019\u00e9criture est bloqu\u00e9e par une double v\u00e9rification "
          "dans <code>excel_writer.py</code>\u00a0: (i) v\u00e9rification statique contre "
          "la liste prot\u00e9g\u00e9e, (ii) v\u00e9rification dynamique par d\u00e9tection "
          "du caract\u00e8re \u00ab\u00a0=\u00a0\u00bb en d\u00e9but de valeur. "
          "Ce double garde garantit qu\u2019une injection de donn\u00e9es ne "
          "pourra jamais d\u00e9truire la logique de calcul du mod\u00e8le."),
        P("L\u2019alignement temporel des donn\u00e9es suit une convention stricte "
          "(alignement \u00e0 droite)\u00a0: la colonne H re\u00e7oit toujours l\u2019exercice "
          "le plus r\u00e9cent (LTM), G l\u2019ann\u00e9e N\u22121, F l\u2019ann\u00e9e "
          "N\u22122, etc. Si seulement 3 ann\u00e9es sont disponibles, les colonnes "
          "D et E restent vides. Cette convention garantit la coh\u00e9rence des "
          "formules de croissance inter-ann\u00e9e, ind\u00e9pendamment du nombre "
          "d\u2019ann\u00e9es disponibles."),
        sp(8),
    ]

    # ══════════════════════════════════════════════════════════════════════
    # PARTIE VI — INTERFACE ET DEPLOIEMENT
    # ══════════════════════════════════════════════════════════════════════
    story += [
        H1('Partie VI \u2014 Interface et d\u00e9ploiement'),
        hr(NAVY, 0.4, 2, 8),
        H2('VI.1 \u00a0 L\u2019interface Streamlit'),
        P("L\u2019interface utilisateur est d\u00e9velopp\u00e9e avec <b>Streamlit</b> "
          "(version 1.55+), un framework Python de prototypage d\u2019applications "
          "analytiques. Le fichier principal <code>app.py</code> comporte plus de "
          "2\u202f700 lignes de code et g\u00e8re trois \u00e9tats applicatifs\u00a0: "
          "accueil (formulaire de recherche, boutons de navigation rapide), "
          "analyse en cours (barre de progression), r\u00e9sultats (affichage "
          "interactif des livrables)."),
        P("La barre lat\u00e9rale fixe (330\u202fpx) propose\u00a0: le t\u00e9l\u00e9chargement "
          "des trois livrables (PDF, PPTX, Excel), les sources de donn\u00e9es actives "
          "(Yahoo Finance, FMP, Finnhub, EODHD), et une section \u00ab\u00a0Aper\u00e7u "
          "Claude\u00a0\u00bb permettant l\u2019inspection des outputs g\u00e9n\u00e9r\u00e9s "
          "avant validation vers la production. Cette fonctionnalit\u00e9 de preview "
          "int\u00e8gre un syst\u00e8me de validation humaine en deux \u00e9tapes "
          "(\u00ab\u00a0Valider tout\u00a0\u00bb / \u00ab\u00a0Rejeter\u00a0\u00bb) avec "
          "commit et push automatiques vers le d\u00e9p\u00f4t GitHub."),
        H2('VI.2 \u00a0 Trois modes d\u2019analyse'),
        P("La plateforme propose trois modes d\u2019analyse accessibles depuis "
          "l\u2019interface et la CLI\u00a0:"),
        B("<b>Mode Soci\u00e9t\u00e9</b>\u00a0: analyse individuelle d\u2019une action cot\u00e9e "
          "(AAPL, MC.PA, TSLA\u2026). Produit l\u2019ensemble des neuf livrables "
          "(PDF 9 pages, PPTX 20 slides, Excel 7 feuilles). Toutes soci\u00e9t\u00e9s "
          "cot\u00e9es mondiales compatibles yfinance."),
        B("<b>Mode Secteur</b>\u00a0: analyse d\u2019un secteur GICS au sein d\u2019un "
          "indice boursier (ex. Technology dans le S&P 500). Produit un rapport "
          "comparatif incluant cartographie des 8 \u00e0 12 acteurs repr\u00e9sentatifs, "
          "valorisation relative, scatter EV/EBITDA vs croissance, et top picks "
          "BUY / HOLD / SELL."),
        B("<b>Mode Indice</b>\u00a0: snapshot macro de l\u2019ensemble d\u2019un indice "
          "(S&P 500, CAC 40, DAX 40, FTSE 100, STOXX 50). Produit un rapport de "
          "12 pages (PDF) et 20 diapositives (PPTX) couvrant les 11 secteurs GICS, "
          "leurs scores FinSight, la rotation sectorielle recommand\u00e9e, "
          "le sentiment FinBERT agr\u00e9g\u00e9, et la performance ETF 52 semaines."),
        H2('VI.3 \u00a0 D\u00e9ploiement cloud et CI/CD'),
        P("La plateforme est d\u00e9ploy\u00e9e sur <b>Streamlit Community Cloud</b>, "
          "accessible publiquement. Le flux de d\u00e9ploiement continu est le suivant\u00a0: "
          "tout commit sur la branche <code>master</code> du d\u00e9p\u00f4t GitHub "
          "d\u00e9clenche automatiquement un red\u00e9ploiement de l\u2019application. "
          "Les cl\u00e9s API sont inject\u00e9es via le m\u00e9canisme de secrets "
          "Streamlit Cloud (<code>st.secrets</code>), jamais commit\u00e9es dans "
          "le code source. Le m\u00e9canisme de preview int\u00e9gr\u00e9 \u00e0 "
          "<code>app.py</code> permet d\u2019approuver ou rejeter les outputs "
          "g\u00e9n\u00e9r\u00e9s depuis l\u2019interface web, avec propagation "
          "automatique vers la production."),
        PageBreak(),
    ]

    # ══════════════════════════════════════════════════════════════════════
    # PARTIE VII — ETAT ET PERSPECTIVES
    # ══════════════════════════════════════════════════════════════════════
    story += [
        H1('Partie VII \u2014 \u00c9tat du projet et perspectives'),
        hr(NAVY, 0.4, 2, 8),
        H2('VII.1 \u00a0 Ce qui est op\u00e9rationnel (mars 2026)'),
        P("L\u2019ensemble du pipeline d\u00e9crit dans ce document est "
          "op\u00e9rationnel et d\u00e9ploy\u00e9 en production. "
          "Les capacit\u00e9s suivantes sont disponibles et valid\u00e9es\u00a0:"),
        B("Pipeline multi-agents complet\u00a0: collecte, quantification, synth\u00e8se, "
          "QA, avocat du diable, g\u00e9n\u00e9ration des livrables. Latence m\u00e9diane "
          "~60 secondes par analyse soci\u00e9t\u00e9."),
        B("Trois modes d\u2019analyse\u00a0: soci\u00e9t\u00e9, secteur (au sein d\u2019un "
          "indice), indice complet. 5 indices couverts (S&P 500, CAC 40, DAX 40, "
          "FTSE 100, STOXX 50)."),
        B("G\u00e9n\u00e9ration de livrables institutionnels\u00a0: PDF ReportLab, "
          "PPTX python-pptx (20 slides), Excel openpyxl (7 feuilles, 52 cellules "
          "prot\u00e9g\u00e9es)."),
        B("Gouvernance constitutionnelle\u00a0: 7 articles appliqu\u00e9s par code, "
          "processus d\u2019amendement vers\u00e9."),
        B("Cascade LLM 5 fournisseurs, rotation de cl\u00e9s Groq, disponibilit\u00e9 "
          "> 99\u202f%."),
        B("Interface Streamlit d\u00e9ploy\u00e9e, syst\u00e8me de preview avec "
          "validation humaine int\u00e9gr\u00e9e."),
        H2('VII.2 \u00a0 Travaux en cours'),
        P("Plusieurs axes d\u2019am\u00e9lioration sont en cours de d\u00e9veloppement\u00a0:"),
        B("<b>Ratios sectoriels sp\u00e9cialis\u00e9s</b>\u00a0: certains secteurs "
          "(banques, assurances, foncier cot\u00e9) requièrent des ratios "
          "sp\u00e9cifiques non couverts par les 33 ratios g\u00e9n\u00e9raux "
          "(NIM, Combined Ratio, NAV discount). Une biblioth\u00e8que de ratios "
          "sectoriels est en cours de formalisation."),
        B("<b>Enrichissement des donn\u00e9es europ\u00e9ennes</b>\u00a0: la couverture "
          "des soci\u00e9t\u00e9s europ\u00e9ennes par yfinance est parfois "
          "incompl\u00e8te sur les donn\u00e9es infra-annuelles. L\u2019int\u00e9gration "
          "de l\u2019API EODHD est \u00e9valu\u00e9e comme source compl\u00e9mentaire."),
        B("<b>Vectorisation de la base de connaissances</b>\u00a0: la biblioth\u00e8que "
          "ChromaDB est int\u00e9gr\u00e9e mais non encore activ\u00e9e en production. "
          "Elle permettra une recherche s\u00e9mantique sur l\u2019historique "
          "des analyses et des incidents du pipeline."),
        B("<b>Module de backtesting</b>\u00a0: un syst\u00e8me permettant de mesurer "
          "la performance des recommandations pass\u00e9es (BUY / HOLD / SELL) "
          "sur des horizons 3, 6 et 12 mois est en conception. Ce module est "
          "essentiel \u00e0 la cr\u00e9dibilit\u00e9 \u00e0 long terme du syst\u00e8me."),
        H2('VII.3 \u00a0 Vision \u00e0 12 mois'),
        P("La feuille de route \u00e0 12 mois s\u2019articule autour de trois "
          "chantiers structurants."),
        P("<b>1. Couverture universellee.</b> \u00c9tendre la couverture \u00e0 "
          "l\u2019ensemble des indices mondiaux (Nikkei, Hang Seng, MSCI EM), "
          "int\u00e9grer les obligations d\u2019entreprise et les ETF sectoriels "
          "comme classe d\u2019actifs additionnelle."),
        P("<b>2. FinSight Score.</b> D\u00e9velopper un score propri\u00e9taire "
          "comb-inant les 33 ratios quantitatifs, le sentiment FinBERT, "
          "les signaux de rotation sectorielle et les alertes constitutionnelles "
          "en un indice composite 0\u2013100 par action, backtest\u00e9 sur "
          "10 ans de donn\u00e9es historiques."),
        P("<b>3. API publique et B2B.</b> Exposer l\u2019ensemble du pipeline "
          "via une API REST (FastAPI), permettant \u00e0 des applications tierces "
          "\u2014 terminaux financiers, robo-advisors, applications mobiles \u2014 "
          "de consommer les analyses FinSight IA. Le mod\u00e8le \u00e9conomique "
          "envisag\u00e9 est un syst\u00e8me d\u2019abonnement \u00e0 l\u2019utilisation "
          "avec une strate gratuite (5 analyses/mois)."),
        sp(8),
    ]

    # ══════════════════════════════════════════════════════════════════════
    # CONCLUSION
    # ══════════════════════════════════════════════════════════════════════
    story += [
        H1('Conclusion'),
        hr(NAVY, 0.4, 2, 8),
        P("FinSight IA d\u00e9montre qu\u2019il est possible, avec des ressources "
          "limit\u00e9es et une architecture logicielle rigoureuse, de produire "
          "des analyses financi\u00e8res de qualit\u00e9 institutionnelle de mani\u00e8re "
          "enti\u00e8rement automatis\u00e9e. Le projet ne cherche pas \u00e0 "
          "\u00ab\u00a0remplacer\u00a0\u00bb l\u2019analyste humain, mais \u00e0 "
          "d\u00e9mocratiser l\u2019acc\u00e8s \u00e0 une premi\u00e8re couche "
          "analytique structur\u00e9e, reproductible et transparente."),
        P("Trois enseignements se d\u00e9gagent de ce projet. Le premier est "
          "architectural\u00a0: la s\u00e9paration stricte entre calcul "
          "d\u00e9terministe (Python) et synth\u00e8se g\u00e9n\u00e9rative (LLM) "
          "est une condition n\u00e9cessaire \u00e0 la fiabilit\u00e9 d\u2019un "
          "syst\u00e8me IA appliqu\u00e9 \u00e0 la finance\u00a0; le LLM "
          "hallucine des ratios, pas des algorithmes Python v\u00e9rifi\u00e9s. "
          "Le second est \u00e9conomique\u00a0: une cascade de six providers LLM, "
          "tous en acc\u00e8s gratuit ou quasi-gratuit, peut offrir une disponibilit\u00e9 "
          "comparable \u00e0 une infrastructure API payante\u00a0; la r\u00e9silience "
          "par diversification est moins co\u00fbteuse que la redondance par duplication. "
          "Le troisi\u00e8me est institutionnel\u00a0: la gouvernance constitutionnelle "
          "\u2014 th\u00e9oriquement emprunt\u00e9e au droit public, impl\u00e9ment\u00e9e "
          "en Python \u2014 offre un cadre de confiance mesurable pour des syst\u00e8mes "
          "IA \u00e0 fort impact d\u00e9cisionnel."),
        P("Le projet est \u00e0 la fois un prototype fonctionnel, un banc d\u2019essai "
          "m\u00e9thodologique, et une d\u00e9monstration de ce que l\u2019intelligence "
          "artificielle peut apporter \u00e0 la finance quantitative lorsqu\u2019elle "
          "est d\u00e9ploy\u00e9e avec rigueur, transparence et discernement."),
        sp(20),
        hr(NAVY, 0.4, 6, 6),
        P("<i>Ce document a \u00e9t\u00e9 r\u00e9dig\u00e9 et g\u00e9n\u00e9r\u00e9 "
          "en mars 2026. Le code source complet de FinSight IA est disponible "
          "sur GitHub. La plateforme est accessible publiquement via Streamlit Cloud. "
          "Toute correspondance peut \u00eatre adress\u00e9e \u00e0 Baptiste Jehanno.</i>",
          'caption'),
    ]

    # ── Build ─────────────────────────────────────────────────────────────
    def first_page(c, doc):
        cover_cb(c, doc)

    def later_pages(c, doc):
        body_cb(c, doc)

    doc.build(story,
              onFirstPage=first_page,
              onLaterPages=later_pages)
    print(f"PDF genere : {out}")
    return out

if __name__ == '__main__':
    build()
