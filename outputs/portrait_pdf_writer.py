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


def _md_to_html(text: str) -> str:
    """Convertit le markdown LLM (**bold**, *italic*) en tags HTML ReportLab.

    Utile car certains LLM (Mistral notamment) génèrent du markdown malgré
    l'instruction de produire du texte plat.
    """
    import re
    if not text:
        return ""
    # Échappe les < et > qui ne sont pas des tags HTML autorisés
    # (ReportLab Paragraph supporte un sous-ensemble : <b>, <i>, <u>, <br/>,
    # <font>, <sub>, <sup>, <a>)
    safe = text.replace("&", "&amp;")
    # Restaure les & si déjà encodés (évite double-encode)
    safe = re.sub(r"&amp;(amp|lt|gt|quot|apos|#\d+);", r"&\1;", safe)
    # Markdown bold **text** ou __text__
    safe = re.sub(r"\*\*([^\*\n]+?)\*\*", r"<b>\1</b>", safe)
    safe = re.sub(r"__([^_\n]+?)__", r"<b>\1</b>", safe)
    # Markdown italic *text* ou _text_ (mais pas mid-word genre snake_case)
    safe = re.sub(r"(?<!\w)\*([^\*\n]+?)\*(?!\w)", r"<i>\1</i>", safe)
    safe = re.sub(r"(?<!\w)_([^_\n]+?)_(?!\w)", r"<i>\1</i>", safe)
    # Bullets markdown "- " ou "* " en début de ligne -> simple "·"
    safe = re.sub(r"^[\-\*]\s+", "· ", safe, flags=re.MULTILINE)
    # Headers markdown ## en gras (rares mais possibles)
    safe = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", safe, flags=re.MULTILINE)
    return safe


def _para_or_fallback(text: Optional[str], fallback: str = "Donnée non disponible."):
    """Retourne une liste de Paragraphs ou fallback si vide."""
    if not text or not text.strip():
        return [Paragraph(f"<i>{fallback}</i>", S_PARA)]
    cleaned = text.strip().replace("\r", "")
    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    return [Paragraph(_md_to_html(p), S_PARA) for p in paragraphs]


def _download_image(url: str, max_kb: int = 2500) -> Optional[bytes]:
    """Télécharge une image (Wikipedia/Wikimedia). Convertit en JPEG si exotique."""
    try:
        r = requests.get(
            url,
            timeout=12,
            headers={"User-Agent": "FinSight-IA/1.0 (contact: privacy@finsight-ia.com)"},
        )
        r.raise_for_status()
        if len(r.content) > max_kb * 1024:
            log.info(f"[portrait_pdf] image too big ({len(r.content)//1024} KB) for {url}")
            return None
        # Vérifie format : si SVG/WebP, on tente conversion JPEG via PIL
        ctype = (r.headers.get("content-type") or "").lower()
        content = r.content
        if "svg" in ctype:
            log.info(f"[portrait_pdf] SVG non supporté : {url}")
            return None
        # Si format raster non standard, convertir en JPEG via Pillow
        if not any(x in ctype for x in ("jpeg", "jpg", "png", "gif")):
            try:
                from PIL import Image as PILImage
                img = PILImage.open(io.BytesIO(content)).convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                content = buf.getvalue()
            except Exception as e:
                log.info(f"[portrait_pdf] PIL convert failed: {e}")
                return None
        return content
    except Exception as e:
        log.info(f"[portrait_pdf] image download FAIL {url}: {e}")
        return None


def _officer_photo_or_placeholder(officer) -> object:
    """Retourne une RLImage ou un placeholder Table avec initiales."""
    img_bytes = _download_image(officer.photo_url) if officer.photo_url else None
    if img_bytes:
        try:
            img = RLImage(io.BytesIO(img_bytes), width=3.2 * cm, height=3.2 * cm,
                          kind="proportional")
            img.hAlign = "LEFT"
            return img
        except Exception as e:
            log.info(f"[portrait_pdf] RLImage failed for {officer.name}: {e}")
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


def _section_block(title: str, body_text: Optional[str], story: list,
                   fallback: str = "Donnée non disponible pour cette section.",
                   force_page_break: bool = False):
    """Ajoute une section : titre + texte. Flow naturel (pas de PageBreak forcé).

    Le titre + la première moitié du contenu sont gardés ensemble (KeepTogether)
    pour éviter qu'un titre se retrouve seul en bas de page.
    """
    elements = _para_or_fallback(body_text, fallback)
    # Bloc titre + premier paragraphe = KeepTogether (anti-orphan)
    if elements:
        head = [Paragraph(title, S_SECTION), elements[0]]
        story.append(KeepTogether(head))
        for el in elements[1:]:
            story.append(el)
    else:
        story.append(Paragraph(title, S_SECTION))
    story.append(Spacer(1, 0.3 * cm))
    if force_page_break:
        story.append(PageBreak())


def _build_leadership_pages(state, story: list):
    """Section intro + cards dirigeants avec photo."""
    intro_elems = _para_or_fallback(state.leadership_intro,
                                    "Données dirigeants non disponibles.")
    head = [Paragraph("Leadership & gouvernance", S_SECTION), intro_elems[0]]
    story.append(KeepTogether(head))
    for el in intro_elems[1:]:
        story.append(el)
    story.append(Spacer(1, 0.4 * cm))

    # Officers cards
    officers = [o for o in state.context.officers if o.name][:4]
    if not officers:
        story.append(Paragraph("<i>Liste des dirigeants non disponible via yfinance.</i>", S_PARA))
    else:
        for o in officers:
            photo = _officer_photo_or_placeholder(o)
            bio_text = (o.bio or "").replace("\n", " ")[:500]
            bio_html = _md_to_html(bio_text) if bio_text else (
                f"<i>Bio Wikipedia non disponible pour {o.name}.</i>"
            )
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
            # Card complète gardée ensemble (photo + bio ne se séparent pas)
            story.append(KeepTogether(card))
            story.append(Spacer(1, 0.3 * cm))
    story.append(Spacer(1, 0.4 * cm))


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
_PORTRAIT_LABELS: dict[str, dict[str, str]] = {
    "snapshot":     {"fr": "Snapshot exécutif", "en": "Executive Snapshot",
                     "es": "Snapshot Ejecutivo", "de": "Executive Snapshot",
                     "it": "Snapshot Esecutivo", "pt": "Snapshot Executivo"},
    "histoire":     {"fr": "Histoire & jalons", "en": "History & Milestones",
                     "es": "Historia y Hitos", "de": "Geschichte & Meilensteine",
                     "it": "Storia & Traguardi", "pt": "História & Marcos"},
    "vision":       {"fr": "Vision & ADN", "en": "Vision & DNA",
                     "es": "Visión y ADN", "de": "Vision & DNA",
                     "it": "Visione & DNA", "pt": "Visão & ADN"},
    "business":     {"fr": "Modèle économique", "en": "Business Model",
                     "es": "Modelo de Negocio", "de": "Geschäftsmodell",
                     "it": "Modello di Business", "pt": "Modelo de Negócio"},
    "segments":     {"fr": "Segments d'activité", "en": "Business Segments",
                     "es": "Segmentos de Negocio", "de": "Geschäftssegmente",
                     "it": "Segmenti di Attività", "pt": "Segmentos de Actividade"},
    "market":       {"fr": "Marché & paysage concurrentiel",
                     "en": "Market & Competitive Landscape",
                     "es": "Mercado y Panorama Competitivo",
                     "de": "Markt & Wettbewerbslandschaft",
                     "it": "Mercato & Panorama Competitivo",
                     "pt": "Mercado & Panorama Competitivo"},
    "risks":        {"fr": "Risques majeurs", "en": "Major Risks",
                     "es": "Riesgos Principales", "de": "Hauptrisiken",
                     "it": "Rischi Principali", "pt": "Principais Riscos"},
    "strategy":     {"fr": "Stratégie 12-24 mois", "en": "12-24 Month Strategy",
                     "es": "Estrategia 12-24 Meses", "de": "12-24-Monats-Strategie",
                     "it": "Strategia 12-24 Mesi", "pt": "Estratégia 12-24 Meses"},
    "devil":        {"fr": "Devil's advocate — la thèse inverse",
                     "en": "Devil's Advocate — Contrary Thesis",
                     "es": "Abogado del Diablo — Tesis Contraria",
                     "de": "Advocatus Diaboli — Gegenteilige These",
                     "it": "Avvocato del Diavolo — Tesi Contraria",
                     "pt": "Advogado do Diabo — Tese Contrária"},
    "verdict":      {"fr": "Verdict & profil d'investisseur",
                     "en": "Verdict & Investor Profile",
                     "es": "Veredicto y Perfil del Inversor",
                     "de": "Urteil & Anlegerprofil",
                     "it": "Verdetto & Profilo Investitore",
                     "pt": "Veredicto & Perfil do Investidor"},
}


def _port_lbl(key: str, lang: str) -> str:
    spec = _PORTRAIT_LABELS.get(key)
    if not spec:
        return key
    lang = (lang or "fr").lower()[:2]
    return spec.get(lang) or spec.get("en") or spec.get("fr") or key


def write_portrait_pdf(state, output_path: str, language: str = "fr", currency: str = "EUR") -> str:
    """Génère le PDF Portrait depuis un PortraitState.

    Returns: chemin du PDF généré.
    """
    # i18n : stocker sur l'état pour les helpers internes
    try:
        state.language = language
        state.currency = currency
    except Exception:
        pass
    _L = language or "fr"
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

    # 1. Cover (page entière, suivie d'un PageBreak)
    _build_cover(state, story)

    # === Bloc 1 : ADN société (snapshot, histoire, vision) ===
    _section_block(_port_lbl("snapshot", _L), state.snapshot, story)
    _section_block(_port_lbl("histoire", _L), state.history, story)
    _section_block(_port_lbl("vision", _L), state.vision, story, force_page_break=True)

    # === Bloc 2 : Modèle & segments ===
    _section_block(_port_lbl("business", _L), state.business_model, story)
    _section_block(_port_lbl("segments", _L), state.segments, story, force_page_break=True)

    # === Bloc 3 : Leadership (page dédiée pour les cards photos) ===
    _build_leadership_pages(state, story)
    story.append(PageBreak())

    # === Bloc 4 : Marché, risques, stratégie ===
    _section_block(_port_lbl("market", _L), state.market, story)
    _section_block(_port_lbl("risks", _L), state.risks, story)
    _section_block(_port_lbl("strategy", _L), state.strategy, story, force_page_break=True)

    # === Bloc 5 : Conclusion (devil + verdict) ===
    _section_block(_port_lbl("devil", _L), state.devil_advocate, story)
    _section_block(_port_lbl("verdict", _L), state.verdict, story, force_page_break=True)

    # === Bloc 6 : Sources & disclaimer ===
    _build_sources_page(state, story)

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return output_path
