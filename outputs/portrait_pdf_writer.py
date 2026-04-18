"""Writer PDF Portrait d'entreprise — ReportLab, 15 pages, style FinSight.

Cohérent avec cmp_societe_pdf_writer (couleurs NAVY, typo, footer).
Sections :
  1. Cover (full page)
  2. Snapshot exécutif
  3. Histoire & jalons
  4. Vision & ADN culturelle
  5. Modèle économique
  6. Segments d'activité
  7-9. Leadership (intro + 1-2 pages dirigeants avec photos)
  10. Marché & paysage concurrentiel
  11. Risques majeurs
  12. Stratégie 12-24 mois
  13. Devil's advocate
  14. Verdict + valorisation contextuelle
  15. Sources & disclaimer
"""
from __future__ import annotations
import io
import logging
from datetime import datetime
from typing import Optional

import requests
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Image as RLImage,
    Table,
    TableStyle,
    KeepTogether,
)

log = logging.getLogger(__name__)

# === Palette FinSight ===
NAVY = colors.HexColor("#1B3A6B")
NAVY_LIGHT = colors.HexColor("#2A5298")
INK_900 = colors.HexColor("#171717")
INK_600 = colors.HexColor("#525252")
INK_400 = colors.HexColor("#A3A3A3")
INK_200 = colors.HexColor("#E5E5E5")
INK_100 = colors.HexColor("#F5F5F5")
WHITE = colors.white

styles = getSampleStyleSheet()


def _s(name: str, size: int = 10, leading: Optional[int] = None,
       color=INK_900, bold: bool = False, align: int = TA_LEFT,
       sb: int = 0, sa: int = 0, italic: bool = False) -> ParagraphStyle:
    """Helper de création de style."""
    fontname = "Helvetica-Bold" if bold else ("Helvetica-Oblique" if italic else "Helvetica")
    return ParagraphStyle(
        name=name,
        fontName=fontname,
        fontSize=size,
        leading=leading or int(size * 1.35),
        textColor=color,
        alignment=align,
        spaceBefore=sb,
        spaceAfter=sa,
    )


# Styles de référence
S_COVER_BRAND = _s("cv_brand", size=12, color=NAVY_LIGHT, bold=True, align=TA_CENTER, sb=0, sa=4)
S_COVER_TITLE = _s("cv_title", size=30, color=NAVY, bold=True, align=TA_CENTER, leading=36, sb=8, sa=4)
S_COVER_TICKER = _s("cv_ticker", size=18, color=INK_900, align=TA_CENTER, sb=12, sa=8)
S_COVER_META = _s("cv_meta", size=9, color=INK_400, align=TA_CENTER, sb=4, sa=4)

S_SECTION = _s("sec", size=14, color=NAVY, bold=True, sb=10, sa=6)
S_SUBSECTION = _s("subsec", size=11, color=NAVY, bold=True, sb=8, sa=4)
S_PARA = _s("para", size=10, leading=15, align=TA_JUSTIFY, sa=8)
S_SMALL = _s("small", size=8, color=INK_600, leading=11, sa=4)
S_LABEL = _s("label", size=7, color=INK_400, sa=2)
S_FOOT = _s("foot", size=7, color=INK_400, align=TA_CENTER)

# === Fonctions utilitaires ===
def _page_footer(canvas, doc):
    """Footer de page avec n° page + pied de page."""
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(INK_400)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(2 * cm, 1 * cm,
                      f"FinSight IA — Portrait d'entreprise · {datetime.utcnow().strftime('%d/%m/%Y')}")
    canvas.drawRightString(w - 2 * cm, 1 * cm, f"Page {doc.page}")
    canvas.setStrokeColor(INK_200)
    canvas.setLineWidth(0.4)
    canvas.line(2 * cm, 1.3 * cm, w - 2 * cm, 1.3 * cm)
    canvas.restoreState()


def _para_or_fallback(text: Optional[str], fallback: str = "Donnée non disponible.") -> Paragraph:
    """Crée un paragraphe ou renvoie un fallback si le contenu est vide."""
    if not text or not text.strip():
        return Paragraph(f"<i>{fallback}</i>", S_PARA)
    # Convertit les sauts de ligne doubles en break paragraph
    cleaned = text.strip().replace("\r", "")
    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    return [Paragraph(p, S_PARA) for p in paragraphs]


def _download_image(url: str, max_kb: int = 500) -> Optional[bytes]:
    """Télécharge une image et la retourne en bytes (None si échec)."""
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "FinSight-IA/1.0"})
        r.raise_for_status()
        if len(r.content) > max_kb * 1024:
            return None  # trop lourd, skip
        return r.content
    except Exception as e:
        log.debug(f"[portrait_pdf] image download failed for {url}: {e}")
        return None


def _officer_photo_or_placeholder(officer) -> object:
    """Retourne une RLImage ou un placeholder Table avec initiales."""
    img_bytes = _download_image(officer.photo_url) if officer.photo_url else None
    if img_bytes:
        try:
            img = RLImage(io.BytesIO(img_bytes), width=3.2 * cm, height=3.2 * cm)
            img.hAlign = "LEFT"
            return img
        except Exception:
            pass
    # Placeholder : carré navy avec initiales
    initials = "".join([w[0] for w in (officer.name or "??").split()[:2]]).upper()[:2]
    placeholder = Table(
        [[Paragraph(f'<font color="white" size="20"><b>{initials}</b></font>',
                    _s("ph", size=20, color=WHITE, bold=True, align=TA_CENTER, leading=24))]],
        colWidths=[3.2 * cm],
        rowHeights=[3.2 * cm],
    )
    placeholder.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    return placeholder


# === Construction des pages ===
def _build_cover(state, story: list):
    """Page de couverture style FinSight."""
    story.append(Spacer(1, 6 * cm))
    story.append(Paragraph("FINSIGHT IA · PORTRAIT D&apos;ENTREPRISE", S_COVER_BRAND))
    story.append(Spacer(1, 1.2 * cm))
    story.append(Paragraph(state.context.name or state.ticker, S_COVER_TITLE))
    story.append(Paragraph(state.ticker, S_COVER_TICKER))
    if state.context.sector:
        story.append(Paragraph(f"{state.context.sector} · {state.context.industry or '—'}", S_COVER_META))
    story.append(Spacer(1, 1 * cm))
    if state.context.market_cap and state.context.currency:
        story.append(
            Paragraph(
                f"Capitalisation boursière : {state.context.market_cap/1e9:.1f} Mds {state.context.currency}",
                S_COVER_META,
            )
        )
    if state.context.country:
        story.append(Paragraph(f"Siège : {state.context.country}", S_COVER_META))
    if state.context.employees:
        story.append(Paragraph(
            f"Effectif : {state.context.employees:,} salariés".replace(",", " "),
            S_COVER_META,
        ))
    story.append(Spacer(1, 4 * cm))
    today = datetime.utcnow().strftime("%d %B %Y")
    story.append(Paragraph(f"Édition du {today}", S_COVER_META))
    story.append(Paragraph(
        "<i>Rapport qualitatif généré par le pipeline FinSight IA — données yfinance, "
        "Wikipedia, intelligence artificielle.</i>",
        S_COVER_META,
    ))
    story.append(PageBreak())


def _section_page(title: str, body_text: Optional[str], story: list,
                  fallback: str = "Donnée non disponible pour cette section."):
    """Ajoute une page section : titre + texte généré par LLM."""
    story.append(Paragraph(title, S_SECTION))
    elements = _para_or_fallback(body_text, fallback)
    if isinstance(elements, list):
        story.extend(elements)
    else:
        story.append(elements)
    story.append(PageBreak())


def _build_leadership_pages(state, story: list):
    """Page intro + cards dirigeants avec photo."""
    story.append(Paragraph("Leadership & gouvernance", S_SECTION))
    intro_elems = _para_or_fallback(state.leadership_intro,
                                    "Données dirigeants non disponibles.")
    if isinstance(intro_elems, list):
        story.extend(intro_elems)
    else:
        story.append(intro_elems)
    story.append(Spacer(1, 0.4 * cm))

    # Officers cards
    officers = [o for o in state.context.officers if o.name][:4]
    if not officers:
        story.append(Paragraph("<i>Liste des dirigeants non disponible via yfinance.</i>", S_PARA))
    else:
        for o in officers:
            photo = _officer_photo_or_placeholder(o)
            bio_html = (o.bio or "").replace("\n", " ")[:500]
            if not bio_html:
                bio_html = f"<i>Bio Wikipedia non disponible pour {o.name}.</i>"
            info_para = Paragraph(
                f"<b>{o.name}</b><br/>"
                f"<font color='#525252' size='8'>{o.title or '—'}</font><br/><br/>"
                f"<font size='8'>{bio_html}</font>",
                _s("offinfo", size=9, leading=12),
            )
            card = Table(
                [[photo, info_para]],
                colWidths=[3.6 * cm, 12.5 * cm],
            )
            card.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, INK_200),
            ]))
            story.append(card)
            story.append(Spacer(1, 0.3 * cm))
    story.append(PageBreak())


def _build_sources_page(state, story: list):
    """Page finale : sources + disclaimer."""
    story.append(Paragraph("Sources et avertissement", S_SECTION))
    story.append(Paragraph(
        "Ce portrait a été assemblé automatiquement par le pipeline FinSight IA à partir "
        "des sources publiques suivantes :",
        S_PARA,
    ))
    sources = [
        f"• <b>yfinance</b> — données de marché, profil société, dirigeants : {state.ticker}",
        f"• <b>Wikipedia</b> — intro et historique de la société, biographies des dirigeants",
        "• <b>Wikimedia Commons</b> — photographies officielles libres de droits",
        "• <b>Pipeline LLM FinSight</b> — Groq llama-3.3-70b · Mistral Large · Anthropic Haiku 4.5",
    ]
    for s in sources:
        story.append(Paragraph(s, S_SMALL))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Avertissement", S_SUBSECTION))
    story.append(Paragraph(
        "Ce document est un rapport d&apos;information qualitative. Il ne constitue pas un "
        "conseil en investissement personnalisé au sens de l&apos;article L.321-1 du code "
        "monétaire et financier. Aucun chiffre figurant dans ce portrait ne doit être "
        "considéré comme un engagement de FinSight IA quant à son exactitude. "
        "L&apos;utilisateur reste seul juge de ses décisions d&apos;investissement.",
        S_SMALL,
    ))
    if state.warnings:
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph("Limites de cette édition", S_SUBSECTION))
        for w in state.warnings[:8]:
            story.append(Paragraph(f"• {w}", S_SMALL))


# === Entrée principale ===
def write_portrait_pdf(state, output_path: str) -> str:
    """Génère le PDF Portrait depuis un PortraitState.

    Returns: chemin du PDF généré.
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=1.8 * cm,
        title=f"Portrait FinSight — {state.context.name or state.ticker}",
        author="FinSight IA",
    )
    story: list = []

    # 1. Cover
    _build_cover(state, story)
    # 2. Snapshot
    _section_page("Snapshot exécutif", state.snapshot, story)
    # 3. Histoire
    _section_page("Histoire & jalons", state.history, story)
    # 4. Vision
    _section_page("Vision & ADN", state.vision, story)
    # 5. Modèle éco
    _section_page("Modèle économique", state.business_model, story)
    # 6. Segments
    _section_page("Segments d'activité", state.segments, story)
    # 7-9. Leadership
    _build_leadership_pages(state, story)
    # 10. Marché
    _section_page("Marché & paysage concurrentiel", state.market, story)
    # 11. Risques
    _section_page("Risques majeurs", state.risks, story)
    # 12. Stratégie
    _section_page("Stratégie 12-24 mois", state.strategy, story)
    # 13. Devil
    _section_page("Devil's advocate — la thèse inverse", state.devil_advocate, story)
    # 14. Verdict
    _section_page("Verdict & profil d'investisseur", state.verdict, story)
    # 15. Sources
    _build_sources_page(state, story)

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return output_path
