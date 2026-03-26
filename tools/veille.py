"""
tools/veille.py -- FinSight IA
Veille technologique : LLM finance, agents IA, fintech, recherche.

Usage:
  python tools/veille.py
  python tools/veille.py --days 14
"""
from __future__ import annotations

import html
import io
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

OUTPUT_DIR = ROOT / "outputs" / "veille"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# SOURCES RSS
# =============================================================================

SOURCES = [
    # -- LLM / IA --
    {"name": "Anthropic Blog",       "url": "https://www.anthropic.com/rss.xml",                      "cat": "LLM"},
    {"name": "OpenAI Blog",          "url": "https://openai.com/blog/rss.xml",                        "cat": "LLM"},
    {"name": "Hugging Face Blog",    "url": "https://huggingface.co/blog/feed.xml",                   "cat": "LLM"},
    {"name": "Import AI",            "url": "https://importai.substack.com/feed",                     "cat": "LLM"},
    {"name": "The Batch (DL.AI)",    "url": "https://www.deeplearning.ai/the-batch/feed/",            "cat": "LLM"},
    {"name": "LangChain Blog",       "url": "https://blog.langchain.dev/rss/",                        "cat": "Agents"},
    # -- Fintech / Finance --
    {"name": "Net Interest",         "url": "https://www.netinterest.co/feed",                        "cat": "Fintech"},
    {"name": "Fintech Brainfood",    "url": "https://fintechbrainfood.substack.com/feed",             "cat": "Fintech"},
    {"name": "Maddyness",            "url": "https://www.maddyness.com/feed/",                        "cat": "Fintech"},
    {"name": "Finextra",             "url": "https://www.finextra.com/rss/headlines.aspx",            "cat": "Fintech"},
    {"name": "AGEFI",                "url": "https://www.agefi.fr/rss/",                              "cat": "Finance"},
    # -- Recherche --
    {"name": "arXiv cs.LG",          "url": "http://export.arxiv.org/rss/cs.LG",                     "cat": "Recherche"},
    {"name": "arXiv q-fin",          "url": "http://export.arxiv.org/rss/q-fin",                     "cat": "Recherche"},
    {"name": "arXiv cs.AI",          "url": "http://export.arxiv.org/rss/cs.AI",                     "cat": "Recherche"},
    # -- Tech / VC --
    {"name": "VentureBeat AI",       "url": "https://venturebeat.com/category/ai/feed/",             "cat": "IA"},
    {"name": "MIT Tech Review",      "url": "https://www.technologyreview.com/feed/",                "cat": "IA"},
    {"name": "a16z Blog",            "url": "https://a16z.com/feed/",                                "cat": "VC"},
    {"name": "Sequoia Capital",      "url": "https://www.sequoiacap.com/feed/",                      "cat": "VC"},
    {"name": "The Information",      "url": "https://www.theinformation.com/feed",                   "cat": "Tech"},
]

# Mots-cles FinSight (scoring pertinence)
KW_HIGH = [
    "llm", "large language model", "financial", "finance", "trading", "investment",
    "agent", "rag", "retrieval", "stock", "portfolio", "valuation", "dcf",
    "earnings", "market", "risk", "quant", "alpha", "fintech", "banking",
    "credit", "fund", "hedge", "earnings call", "transformer", "reasoning",
    "claude", "gpt", "gemini", "groq", "mistral", "anthropic", "openai",
    "automation", "agentic", "multi-agent", "tool use", "function calling",
    "sentiment", "forecast", "analyse financiere", "analyse financière",
]
KW_MED = [
    "ai", "machine learning", "deep learning", "neural", "data", "model",
    "api", "startup", "regulation", "compliance", "crypto", "prediction",
    "benchmark", "open source", "inference", "fine-tuning", "rlhf",
    "python", "dataset", "evaluation", "leaderboard",
]


def _clean(text: str) -> str:
    """Nettoyage HTML basique."""
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_date(entry) -> datetime:
    """Parse la date d'une entree feedparser -> datetime UTC."""
    import email.utils
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    # Fallback : date courante
    return datetime.now(timezone.utc)


def _score(title: str, summary: str) -> int:
    text = (title + " " + summary).lower()
    score = 0
    for kw in KW_HIGH:
        if kw in text:
            score += 8
    for kw in KW_MED:
        if kw in text:
            score += 3
    return min(score, 100)


# =============================================================================
# FETCH RSS
# =============================================================================

def fetch_articles(days: int = 7) -> list[dict]:
    """Fetche tous les flux RSS, filtre par date, retourne liste de dicts."""
    try:
        import feedparser
    except ImportError:
        print("[VEILLE] feedparser non installe — pip install feedparser")
        sys.exit(1)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    articles = []

    for src in SOURCES:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:20]:
                pub = _parse_date(entry)
                if pub < cutoff:
                    continue
                title   = _clean(getattr(entry, "title",   "") or "")
                summary = _clean(getattr(entry, "summary", "") or getattr(entry, "description", "") or "")
                link    = getattr(entry, "link", "") or ""
                if not title or not link:
                    continue
                score = _score(title, summary)
                articles.append({
                    "source":  src["name"],
                    "cat":     src["cat"],
                    "title":   title[:200],
                    "summary": summary[:800],
                    "link":    link,
                    "date":    pub,
                    "score":   score,
                })
        except Exception as e:
            print(f"[VEILLE] {src['name']} : {e}")

    # Trier par score desc puis date desc
    articles.sort(key=lambda a: (a["score"], a["date"]), reverse=True)
    print(f"[VEILLE] {len(articles)} articles collectes (fenetre {days}j)")
    return articles


# =============================================================================
# SUMMARIZE VIA LLM
# =============================================================================

def summarize_articles(articles: list[dict]) -> list[dict]:
    """
    Enrichit chaque article avec :
      - resume_fr   : 3 phrases en francais
      - pertinence  : 1 phrase sur l'apport pour FinSight
    """
    # Rotation cles GROQ_API_KEY_1, _2, ... puis fallback GROQ_API_KEY
    groq_key = os.getenv("GROQ_API_KEY_1") or os.getenv("GROQ_API_KEY_2") or os.getenv("GROQ_API_KEY")
    if not groq_key:
        print("[VEILLE] Aucune cle Groq trouvee — resumes depuis description brute")
        for a in articles:
            a["resume_fr"]  = a["summary"][:300]
            a["pertinence"] = "Impact direct sur les pipelines LLM financiers."
        return articles

    try:
        from groq import Groq
        client = Groq(api_key=groq_key)
    except Exception as e:
        print(f"[VEILLE] Groq init error: {e}")
        for a in articles:
            a["resume_fr"]  = a["summary"][:300]
            a["pertinence"] = "Impact potentiel sur FinSight."
        return articles

    for i, art in enumerate(articles):
        try:
            prompt = (
                f"Tu es analyste FinTech. Lis ce contenu et reponds en JSON strict.\n"
                f"Titre: {art['title']}\n"
                f"Source: {art['source']}\n"
                f"Contenu: {art['summary'][:600]}\n\n"
                f"Reponds UNIQUEMENT avec ce JSON (aucun markdown, aucun texte autour):\n"
                f'{{"resume":"<3 phrases concises en francais>","pertinence":"<1 phrase sur l apport pour FinSight IA — plateforme analyse financiere multi-agents>"}}'
            )
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=250,
                temperature=0.3,
            )
            raw = resp.choices[0].message.content.strip()
            # Extraire JSON meme si entouré de backticks
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                import json
                parsed = json.loads(m.group())
                art["resume_fr"]  = parsed.get("resume",     art["summary"][:300])
                art["pertinence"] = parsed.get("pertinence", "Impact direct sur FinSight.")
            else:
                art["resume_fr"]  = art["summary"][:300]
                art["pertinence"] = "Impact direct sur FinSight."
            time.sleep(0.3)   # eviter rate-limit
        except Exception as e:
            print(f"[VEILLE] LLM {i}: {e}")
            art["resume_fr"]  = art["summary"][:300]
            art["pertinence"] = "Impact direct sur FinSight."

    return articles


# =============================================================================
# BONUS : 5 articles supplementaires proposes par le LLM
# =============================================================================

def suggest_bonus(top_articles: list[dict]) -> list[dict]:
    """
    Demande au LLM de proposer 5 articles complementaires
    en dehors des sources deja selectionnees.
    """
    groq_key = os.getenv("GROQ_API_KEY_1") or os.getenv("GROQ_API_KEY_2") or os.getenv("GROQ_API_KEY")
    if not groq_key:
        return []

    try:
        from groq import Groq
        import json
        client = Groq(api_key=groq_key)
        themes = ", ".join({a["cat"] for a in top_articles[:5]})
        prompt = (
            f"Tu es un veilleur technologique specialise en LLM, fintech et finance quantitative.\n"
            f"Themes couverts ce jour : {themes}.\n"
            f"Propose 5 articles/ressources supplementaires EN LIEN avec ces themes "
            f"issus de sources variees (GitHub, ArXiv, blogs specialises, newsletters...). "
            f"Choisis des articles que tu juges particulierement utiles pour une plateforme "
            f"d'analyse financiere multi-agents.\n\n"
            f"Reponds UNIQUEMENT avec ce JSON (array de 5 objets, aucun markdown):\n"
            f'[{{"title":"...","source":"...","link":"...","date":"...","cat":"...","resume_fr":"<3 phrases>","pertinence":"<1 phrase FinSight>"}}]'
        )
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.6,
        )
        raw = resp.choices[0].message.content.strip()
        # Nettoyage robuste : extraire le tableau JSON
        raw_clean = re.sub(r'```(?:json)?', '', raw).strip()
        m = re.search(r'\[.*\]', raw_clean, re.DOTALL)
        if m:
            bonus = json.loads(m.group())
            for b in bonus:
                b["score"] = 50
                if not b.get("date"):
                    b["date"] = datetime.now(timezone.utc)
                # Assurer que les champs requis existent
                b.setdefault("title", "Article bonus")
                b.setdefault("source", "IA suggestion")
                b.setdefault("link", "")
                b.setdefault("cat", "IA")
                b.setdefault("resume_fr", "Contenu non disponible.")
                b.setdefault("pertinence", "Pertinent pour les pipelines FinSight.")
            return [b for b in bonus if b.get("title")][:5]
    except Exception as e:
        print(f"[VEILLE] Bonus LLM: {e}")
    return []


# =============================================================================
# PDF GENERATION
# =============================================================================

NAVY       = "#1B3A6B"
NAVY_LIGHT = "#2A5298"
GREEN      = "#1A7A4A"
WHITE      = "#FFFFFF"
GREY_BG    = "#F5F7FA"
GREY_MED   = "#E8ECF0"
GREY_TEXT  = "#555555"
BLACK      = "#1A1A1A"


def _hex(h):
    from reportlab.lib import colors
    return colors.HexColor(h)


def build_pdf(top10: list[dict], bonus5: list[dict], output_path: Path) -> Path:
    """Genere le PDF de veille style FinSight."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak
    )
    from reportlab.lib import colors

    w, h = A4
    ML, MR = 18 * mm, 18 * mm
    MT, MB = 20 * mm, 18 * mm

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=ML, rightMargin=MR,
        topMargin=MT, bottomMargin=MB,
        title="FinSight IA — Veille Technologique",
        author="FinSight IA",
    )

    # -- Styles --
    def _style(name, **kw):
        base = dict(fontName="Helvetica", fontSize=10, leading=14,
                    textColor=_hex(BLACK), spaceAfter=2)
        base.update(kw)
        return ParagraphStyle(name, **base)

    S_TITLE   = _style("title",   fontName="Helvetica-Bold", fontSize=22,
                        textColor=_hex(NAVY), spaceAfter=4)
    S_SUB     = _style("sub",     fontName="Helvetica",      fontSize=12,
                        textColor=_hex(GREY_TEXT), spaceAfter=12)
    S_SEC     = _style("sec",     fontName="Helvetica-Bold", fontSize=13,
                        textColor=_hex(NAVY_LIGHT), spaceAfter=6, spaceBefore=14)
    S_ART_T   = _style("art_t",   fontName="Helvetica-Bold", fontSize=10,
                        textColor=_hex(NAVY), spaceAfter=2)
    S_META    = _style("meta",    fontName="Helvetica",      fontSize=8.5,
                        textColor=_hex(GREY_TEXT), spaceAfter=4)
    S_BODY    = _style("body",    fontName="Helvetica",      fontSize=9,
                        textColor=_hex(BLACK), leading=13, spaceAfter=3)
    S_PERT    = _style("pert",    fontName="Helvetica-Oblique", fontSize=9,
                        textColor=_hex(GREEN), spaceAfter=6)
    S_LINK    = _style("link",    fontName="Helvetica",      fontSize=8,
                        textColor=_hex(NAVY_LIGHT), spaceAfter=8)
    S_BONUS_T = _style("bonus_t", fontName="Helvetica-Bold", fontSize=10,
                        textColor=colors.HexColor("#B06000"), spaceAfter=2)
    S_FOOTER  = _style("footer",  fontName="Helvetica",      fontSize=7.5,
                        textColor=_hex(GREY_TEXT), alignment=TA_CENTER)

    def _enc(s: str) -> str:
        """Encode les caracteres speciaux pour ReportLab."""
        return (s or "").encode("cp1252", errors="replace").decode("cp1252")

    _MOIS = ["janvier","fevrier","mars","avril","mai","juin",
             "juillet","aout","septembre","octobre","novembre","decembre"]
    today    = datetime.now()
    date_str = f"{today.day} {_MOIS[today.month-1]} {today.year}"
    elems     = []

    # ---- HEADER -----------------------------------------------------------
    elems.append(Spacer(1, 4 * mm))
    elems.append(Paragraph(_enc("FinSight IA — Veille Technologique"), S_TITLE))
    elems.append(Paragraph(_enc(f"{date_str}  •  LLM, Agents IA, Fintech, Recherche"), S_SUB))
    elems.append(HRFlowable(width="100%", thickness=1.5, color=_hex(NAVY), spaceAfter=10))

    # Bandeau resume
    n_total = len(top10) + len(bonus5)
    sources_used = sorted({a.get("source","?") for a in top10})
    intro = (
        f"{n_total} articles selectionnes parmi les sources suivantes : "
        + ", ".join(sources_used[:8])
        + (f" et {len(sources_used)-8} autres" if len(sources_used) > 8 else "")
        + "."
    )
    intro_style = _style("intro", fontName="Helvetica", fontSize=9,
                          textColor=_hex(GREY_TEXT), spaceAfter=14,
                          backColor=_hex(GREY_BG))
    elems.append(Paragraph(_enc(intro), intro_style))

    # ---- TOP 10 -----------------------------------------------------------
    elems.append(Paragraph(_enc("Selection FinSight — Top 10 articles"), S_SEC))
    elems.append(HRFlowable(width="100%", thickness=0.5, color=_hex(GREY_MED), spaceAfter=6))

    for i, art in enumerate(top10, 1):
        date_label = art["date"].strftime("%d/%m/%Y") if hasattr(art.get("date"), "strftime") else str(art.get("date",""))[:10]
        score      = art.get("score", 0)
        score_bar  = (">" * min(int(score / 20), 5)).ljust(5, "-")

        # Titre numerote
        elems.append(Paragraph(
            _enc(f"{i:02d}. {art['title']}"),
            S_ART_T
        ))
        # Meta : source | date | cat | score
        elems.append(Paragraph(
            _enc(f"{art.get('source','?')}  |  {date_label}  |  {art.get('cat','?')}  |  Pertinence : {score}/100  [{score_bar}]"),
            S_META
        ))
        # Resume
        resume = art.get("resume_fr") or art.get("summary","")
        elems.append(Paragraph(_enc(resume[:400]), S_BODY))
        # Pertinence FinSight
        pert = art.get("pertinence","")
        if pert:
            elems.append(Paragraph(_enc(f"FinSight : {pert}"), S_PERT))
        # Lien
        link = art.get("link","")
        if link:
            elems.append(Paragraph(_enc(f"Lien : {link[:120]}"), S_LINK))

        # Separateur leger entre articles
        if i < len(top10):
            elems.append(HRFlowable(width="100%", thickness=0.3,
                                    color=_hex(GREY_MED), spaceAfter=4))

    # ---- BONUS 5 ----------------------------------------------------------
    if bonus5:
        elems.append(PageBreak())
        elems.append(Paragraph(_enc("Bonus — 5 articles complementaires selectionnes par l'IA"), S_SEC))
        elems.append(HRFlowable(width="100%", thickness=0.5, color=_hex(GREY_MED), spaceAfter=6))

        for i, art in enumerate(bonus5, 1):
            date_label = str(art.get("date",""))[:10]
            elems.append(Paragraph(_enc(f"B{i}. {art.get('title','')}"), S_BONUS_T))
            elems.append(Paragraph(
                _enc(f"{art.get('source','?')}  |  {date_label}  |  {art.get('cat','?')}"),
                S_META
            ))
            resume = art.get("resume_fr") or art.get("summary","")
            elems.append(Paragraph(_enc(resume[:400]), S_BODY))
            pert = art.get("pertinence","")
            if pert:
                elems.append(Paragraph(_enc(f"FinSight : {pert}"), S_PERT))
            link = art.get("link","")
            if link:
                elems.append(Paragraph(_enc(f"Lien : {link[:120]}"), S_LINK))
            if i < len(bonus5):
                elems.append(HRFlowable(width="100%", thickness=0.3,
                                        color=_hex(GREY_MED), spaceAfter=4))

    # ---- FOOTER -----------------------------------------------------------
    elems.append(Spacer(1, 8 * mm))
    elems.append(HRFlowable(width="100%", thickness=0.8, color=_hex(NAVY), spaceAfter=6))
    elems.append(Paragraph(
        _enc(f"FinSight IA v1.0 — Veille generee le {date_str} — Sources : RSS / feedparser / Groq llama-3.3-70b"),
        S_FOOTER
    ))
    elems.append(Paragraph(
        _enc("Ce document est produit automatiquement. Les resumes sont generes par IA et peuvent contenir des inexactitudes."),
        S_FOOTER
    ))

    # -- Build ---
    def _header_footer(canvas, doc):
        canvas.saveState()
        # Header bande navy
        canvas.setFillColor(_hex(NAVY))
        canvas.rect(0, h - 10 * mm, w, 10 * mm, fill=1, stroke=0)
        canvas.setFillColor(_hex(WHITE))
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(ML, h - 6.5 * mm, "FinSight IA  ·  Veille Technologique")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(w - MR, h - 6.5 * mm, f"{date_str}  ·  Page {doc.page}")
        canvas.restoreState()

    doc.build(elems, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return output_path


# =============================================================================
# POINT D'ENTREE
# =============================================================================

def run_veille(days: int = 7) -> Path:
    print(f"\n{'='*55}")
    print("  FINSIGHT IA -- Veille Technologique")
    print(f"{'='*55}\n")

    # 1. Fetch
    articles = fetch_articles(days=days)

    if not articles:
        print("[VEILLE] Aucun article trouve — essayez --days 30")
        sys.exit(1)

    # 2. Top 10 (deja tries par score)
    top10 = articles[:10]
    print(f"[VEILLE] Top 10 selectionnes — generation des resumes...")

    # 3. Summarize
    top10 = summarize_articles(top10)

    # 4. Bonus 5
    print("[VEILLE] Bonus 5 articles (suggestion LLM)...")
    bonus5 = suggest_bonus(top10)

    # 5. PDF
    date_tag  = datetime.now().strftime("%Y%m%d_%H%M")
    out_path  = OUTPUT_DIR / f"veille_{date_tag}.pdf"
    print(f"[VEILLE] Generation PDF -> {out_path.name}")
    build_pdf(top10, bonus5, out_path)

    print(f"\n[VEILLE] Termine : {out_path}")
    print(f"{'='*55}\n")
    return out_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="FinSight IA -- Veille Technologique")
    parser.add_argument("--days", type=int, default=7, help="Fenetre temporelle en jours (defaut: 7)")
    args = parser.parse_args()

    pdf_path = run_veille(days=args.days)

    # Ouvrir automatiquement le PDF (Windows)
    try:
        os.startfile(str(pdf_path))
    except Exception as e:
        print(f"[VEILLE] Impossible d'ouvrir le PDF : {e}")
        print(f"[VEILLE] Chemin : {pdf_path}")
