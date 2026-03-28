#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FinSight IA -- One-Pager Academique
Format A4 recto unique -- orientation Finance d'entreprise
Destine : jury L2 Gestion Sorbonne, clients, contacts
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
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

ML = MR = 1.5 * cm
MT   = 3.0 * cm
MB   = 1.2 * cm

TW   = W - ML - MR
GAP  = 0.5 * cm
COL  = (TW - GAP) / 2


def make_styles():
    d = {}
    def ps(name, **kw):
        defaults = dict(fontName='Times-Roman', fontSize=9.5, leading=13.5,
                        textColor=BLACK, alignment=TA_JUSTIFY, spaceAfter=6,
                        spaceBefore=0)
        defaults.update(kw)
        d[name] = ParagraphStyle(name, **defaults)

    ps('body')
    ps('intro', fontName='Times-Italic', fontSize=9.5, leading=14,
               spaceAfter=0, alignment=TA_JUSTIFY)
    ps('bul',  fontName='Times-Roman', fontSize=9.5, leading=13.5,
               leftIndent=10, spaceAfter=4, alignment=TA_LEFT)
    ps('sh',   fontName='Helvetica-Bold', fontSize=10, leading=13,
               textColor=NAVY, alignment=TA_LEFT, spaceAfter=4, spaceBefore=12)
    ps('sh0',  fontName='Helvetica-Bold', fontSize=10, leading=13,
               textColor=NAVY, alignment=TA_LEFT, spaceAfter=4, spaceBefore=0)
    ps('cap',  fontName='Times-Italic', fontSize=8.5, leading=11,
               textColor=DGREY, alignment=TA_CENTER, spaceAfter=4)
    return d


def header_cb(c, doc):
    # Navy header bar
    c.setFillColor(NAVY)
    c.rect(0, H - 52, W, 52, fill=1, stroke=0)

    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 18)
    c.drawString(ML, H - 30, 'FinSight IA')
    c.setFont('Helvetica', 8.5)
    c.drawString(ML, H - 45,
                 "Plateforme d'analyse financiere institutionnelle automatisee")

    c.setFont('Helvetica-Bold', 9)
    c.drawRightString(W - MR, H - 28, 'Baptiste Jehanno')
    c.setFont('Helvetica', 8)
    c.drawRightString(W - MR, H - 41, '28 mars 2026')

    # Green accent
    c.setFillColor(GREEN)
    c.rect(0, H - 55, W, 3, fill=1, stroke=0)

    # Footer
    c.setStrokeColor(MGREY)
    c.setLineWidth(0.4)
    c.line(ML, MB + 8, W - MR, MB + 8)
    c.setFillColor(DGREY)
    c.setFont('Helvetica-Oblique', 6.5)
    c.drawCentredString(
        W / 2, MB + 1,
        'FinSight IA  \u2014  Baptiste Jehanno  \u2014  mars 2026'
        '  \u2014  Deploye sur Streamlit Cloud  \u2014  finsight-ia.streamlit.app')


def build():
    OUT = 'outputs/FINSIGHT_IA_One_Pager.pdf'
    doc = SimpleDocTemplate(
        OUT, pagesize=A4,
        leftMargin=ML, rightMargin=MR,
        topMargin=MT, bottomMargin=MB + 14,
    )

    st = make_styles()
    P  = lambda t, s='body': Paragraph(t, st[s])
    SH = lambda t: Paragraph(t, st['sh'])
    S0 = lambda t: Paragraph(t, st['sh0'])
    BU = lambda t: Paragraph('\u2022\u00a0 ' + t, st['bul'])
    sp = lambda n=4: Spacer(1, n)

    # ── Intro pleine largeur ──────────────────────────────────────────────────
    intro_txt = (
        "FinSight IA est une plateforme que j\u2019ai con\u00e7ue et d\u00e9velopp\u00e9e "
        "seul pour automatiser la production de recherche financi\u00e8re de qualit\u00e9 "
        "institutionnelle. En moins de 90 secondes, le syst\u00e8me collecte cinq ann\u00e9es "
        "de donn\u00e9es financi\u00e8res, calcule les principaux indicateurs utilis\u00e9s "
        "par les analystes sell-side \u2014 rentabilit\u00e9, valorisation, structure du "
        "capital, liquidit\u00e9, croissance \u2014 synth\u00e9tise une th\u00e8se "
        "d\u2019investissement structur\u00e9e, et g\u00e9n\u00e8re trois livrables "
        "pr\u00eats \u00e0 l\u2019usage\u00a0: un rapport de recherche, un pitchbook "
        "de pr\u00e9sentation, et un mod\u00e8le Excel financier. "
        "Le tout accessible gratuitement, sans abonnement Bloomberg ni FactSet."
    )
    intro_tbl = Table(
        [[Paragraph(intro_txt, st['intro'])]],
        colWidths=[TW],
    )
    intro_tbl.setStyle(TableStyle([
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LINEBELOW',     (0, 0), (-1, -1), 0.5, MGREY),
    ]))

    # ── Colonne gauche ────────────────────────────────────────────────────────
    left = [
        S0('CE QUE PRODUIT FINSIGHT IA'),
        P("Chaque analyse g\u00e9n\u00e8re trois livrables simultan\u00e9ment, "
          "comparables au travail d\u2019un analyste junior en banque "
          "d\u2019investissement\u00a0:"),
        BU("<b>Rapport de recherche PDF</b> (9 pages)\u00a0: "
           "synth\u00e8se de la th\u00e8se d\u2019investissement, "
           "analyse sectorielle, valorisation, scénarios bull/base/bear, "
           "points cl\u00e9s et recommandation."),
        BU("<b>Pitchbook PowerPoint</b> (20 diapositives)\u00a0: "
           "pr\u00e9sentation au format banque d\u2019investissement, "
           "graphiques historiques, comparables sectoriels, "
           "th\u00e8se et contre-th\u00e8se."),
        BU("<b>Mod\u00e8le Excel financier</b> (7 feuilles)\u00a0: "
           "compte de r\u00e9sultat, bilan, flux de tr\u00e9sorerie "
           "sur 5 ans, ratios calcul\u00e9s, DCF, sc\u00e9narios."),

        SH("L'ANALYSE FINANCI\u00c8RE COUVERTE"),
        P("Le syst\u00e8me analyse quatre dimensions fondamentales de la sant\u00e9 "
          "financi\u00e8re d\u2019une entreprise\u00a0:"),
        BU("<b>Rentabilit\u00e9</b>\u00a0: ROE, ROA, ROIC, marge EBITDA, "
           "marge nette, rendement du free cash flow."),
        BU("<b>Valorisation</b>\u00a0: PER, EV/EBITDA, Price-to-Book, "
           "Price-to-Sales \u2014 compar\u00e9s aux pairs sectoriels."),
        BU("<b>Structure du capital</b>\u00a0: ratio dette nette sur EBITDA, "
           "levier financier, couverture des int\u00e9r\u00eats."),
        BU("<b>Croissance</b>\u00a0: TCAM du chiffre d\u2019affaires sur "
           "3 et 5 ans, croissance du B\u00e9n\u00e9fice par Action, "
           "dynamique de la marge op\u00e9rationnelle."),

        SH('TROIS MODES D\u2019ANALYSE'),
        BU("<b>Soci\u00e9t\u00e9</b>\u00a0: analyse individuelle d\u2019une action cot\u00e9e "
           "mondiale (AAPL, LVMH, TotalEnergies\u2026). "
           "Produit les neuf livrables complets."),
        BU("<b>Secteur</b>\u00a0: vue comparative d\u2019un secteur GICS au sein "
           "d\u2019un indice. Cartographie des acteurs, valorisation relative, "
           "top picks BUY / HOLD / SELL."),
        BU("<b>Indice</b>\u00a0: snapshot macro d\u2019un march\u00e9 entier "
           "(S&P\u00a0500, CAC\u00a040, DAX\u2026). Rotation sectorielle "
           "recommand\u00e9e, sentiment agr\u00e9g\u00e9, performance ETF."),
    ]

    # ── Colonne droite ────────────────────────────────────────────────────────
    right = [
        S0('COMMENT LE SYST\u00c8ME FONCTIONNE'),
        P("Le pipeline suit la m\u00eame logique qu\u2019un analyste "
          "sell-side\u00a0: <b>collecter</b> les donn\u00e9es financi\u00e8res "
          "historiques (cinq exercices), <b>calculer</b> les ratios de mani\u00e8re "
          "d\u00e9terministe et v\u00e9rifiable, <b>synth\u00e9tiser</b> une th\u00e8se "
          "via un mod\u00e8le de langage, puis <b>valider</b> la coh\u00e9rence "
          "avant de g\u00e9n\u00e9rer les livrables."),
        P("Les donn\u00e9es proviennent de Yahoo Finance (cinq ans d\u2019historique "
          "couvrant la quasi-totalit\u00e9 des soci\u00e9t\u00e9s cot\u00e9es mondiales), "
          "compl\u00e9t\u00e9es par des sources sp\u00e9cialis\u00e9es pour les "
          "entreprises europ\u00e9ennes et les actualit\u00e9s r\u00e9centes. "
          "Le syst\u00e8me fonctionne sans abonnement payant."),

        SH('RIGUEUR ET CONTR\u00d4LE QUALIT\u00c9'),
        P("Deux niveaux de validation sont appliqu\u00e9s \u00e0 chaque analyse. "
          "Le premier est <b>d\u00e9terministe</b>\u00a0: le syst\u00e8me v\u00e9rifie "
          "la coh\u00e9rence interne des ratios, d\u00e9tecte les anomalies "
          "comptables et contr\u00f4le la qualit\u00e9 des donn\u00e9es collect\u00e9es. "
          "Le second est <b>\u00e9ditorial</b>\u00a0: une validation "
          "ind\u00e9pendante \u00e9value la clart\u00e9, le niveau de rigueur "
          "et la conformit\u00e9 aux standards de la recherche financi\u00e8re."),
        P("Un <b>protocole d\u2019avocat du diable</b> syst\u00e9matique "
          "g\u00e9n\u00e8re la contre-th\u00e8se \u00e0 chaque analyse\u00a0: "
          "quels \u00e9l\u00e9ments invalideraient la recommandation\u00a0? "
          "Quels risques l\u2019analyste aurait pu sous-estimer\u00a0? "
          "Cette discipline intellectuelle, emprunt\u00e9e aux meilleures "
          "pratiques des comit\u00e9s d\u2019investissement, est int\u00e9gr\u00e9e "
          "directement dans le rapport livr\u00e9."),

        SH('\u00c9TAT EN MARS 2026'),
        P("La plateforme est d\u00e9ploy\u00e9e en production sur Streamlit "
          "Community Cloud et accessible librement. Elle couvre l\u2019ensemble "
          "des soci\u00e9t\u00e9s cot\u00e9es sur les grandes places boursi\u00e8res "
          "mondiales. Les analyses ont \u00e9t\u00e9 valid\u00e9es sur des "
          "titres aussi divers qu\u2019Apple, LVMH, TotalEnergies, SAP ou Nvidia."),
        P("Ce projet illustre une conviction\u00a0: les outils de la finance "
          "institutionnelle \u2014 aujourd\u2019hui r\u00e9serv\u00e9s aux grandes "
          "structures par leur co\u00fbt \u2014 peuvent \u00eatre "
          "d\u00e9mocratis\u00e9s sans sacrifier la rigueur analytique."),
    ]

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

    doc.build(
        [intro_tbl, sp(8), tbl],
        onFirstPage=header_cb,
        onLaterPages=header_cb,
    )
    print(f'PDF genere : {os.path.abspath(OUT)}')


build()
