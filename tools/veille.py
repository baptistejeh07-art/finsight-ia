"""
tools/veille.py -- FinSight IA
Veille technologique institutionnelle : LLM finance, agents IA, fintech.

Architecture :
  1. Fetch RSS toutes sources (fenetre adaptee par source)
  2. Pre-filtrage negatif + nettoyage arXiv
  3. Un seul appel LLM : selection top 10 + resumes editoriaux + intro
  4. Bonus 5 articles via second appel LLM
  5. PDF institutionnel style FinSight

Usage:
  python tools/veille.py
  python tools/veille.py --days 14
"""
from __future__ import annotations

import html
import io
import json
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
# SOURCES  (fenetre par source : LLM/IA publient rarement, arXiv tous les jours)
# =============================================================================

SOURCES = [
    # -- LLM / IA (fenetre 30j — publient 1-2x/semaine) --
    {"name": "Anthropic Blog",      "url": "https://www.anthropic.com/rss.xml",                    "cat": "LLM",     "days": 30},
    {"name": "OpenAI Blog",         "url": "https://openai.com/blog/rss.xml",                      "cat": "LLM",     "days": 30},
    {"name": "Hugging Face Blog",   "url": "https://huggingface.co/blog/feed.xml",                 "cat": "LLM",     "days": 30},
    {"name": "Google DeepMind",     "url": "https://deepmind.google/blog/rss.xml",                 "cat": "LLM",     "days": 30},
    {"name": "Import AI",           "url": "https://importai.substack.com/feed",                   "cat": "LLM",     "days": 30},
    {"name": "The Batch (DL.AI)",   "url": "https://www.deeplearning.ai/the-batch/feed/",          "cat": "LLM",     "days": 14},
    {"name": "LangChain Blog",      "url": "https://blog.langchain.dev/rss/",                      "cat": "Agents",  "days": 14},
    {"name": "Mistral AI Blog",     "url": "https://mistral.ai/news/rss",                          "cat": "LLM",     "days": 30},
    # -- Fintech / Finance (fenetre 14j) --
    {"name": "Net Interest",        "url": "https://www.netinterest.co/feed",                      "cat": "Fintech", "days": 14},
    {"name": "Fintech Brainfood",   "url": "https://fintechbrainfood.substack.com/feed",           "cat": "Fintech", "days": 14},
    {"name": "Maddyness",           "url": "https://www.maddyness.com/feed/",                      "cat": "Fintech", "days": 7},
    {"name": "Finextra",            "url": "https://www.finextra.com/rss/headlines.aspx",          "cat": "Fintech", "days": 7},
    {"name": "AGEFI",               "url": "https://www.agefi.fr/rss/",                            "cat": "Finance", "days": 7},
    # -- Recherche arXiv (fenetre 5j — publient en masse) --
    {"name": "arXiv cs.LG",         "url": "http://export.arxiv.org/rss/cs.LG",                   "cat": "Recherche","days": 5},
    {"name": "arXiv q-fin",         "url": "http://export.arxiv.org/rss/q-fin",                   "cat": "Recherche","days": 5},
    {"name": "arXiv cs.AI",         "url": "http://export.arxiv.org/rss/cs.AI",                   "cat": "Recherche","days": 5},
    # -- Tech / VC --
    {"name": "VentureBeat AI",      "url": "https://venturebeat.com/category/ai/feed/",            "cat": "IA",      "days": 7},
    {"name": "MIT Tech Review",     "url": "https://www.technologyreview.com/feed/",               "cat": "IA",      "days": 14},
    {"name": "a16z Blog",           "url": "https://a16z.com/feed/",                               "cat": "VC",      "days": 30},
    {"name": "Sequoia Capital",     "url": "https://www.sequoiacap.com/feed/",                     "cat": "VC",      "days": 30},
    {"name": "The Information AI",  "url": "https://www.theinformation.com/feed",                  "cat": "Tech",    "days": 14},
    {"name": "Towards Data Science","url": "https://towardsdatascience.com/feed",                  "cat": "Data",    "days": 7},
]

# Mots-cles positifs (scoring)
KW_HIGH = [
    "llm", "large language model", "financial analysis", "finance", "trading",
    "investment", "agent", "rag", "retrieval augmented", "stock market",
    "portfolio", "valuation", "dcf", "earnings", "risk management",
    "quantitative", "alpha generation", "fintech", "banking", "asset management",
    "hedge fund", "earnings call", "transformer", "reasoning", "claude",
    "gpt-4", "gemini", "groq", "mistral", "anthropic", "openai", "llama",
    "agentic", "multi-agent", "tool use", "function calling",
    "sentiment analysis", "forecast", "financial data", "market intelligence",
    "robo-advisor", "algorithmic trading", "credit scoring", "fraud detection",
]
KW_MED = [
    "ai", "machine learning", "deep learning", "neural network", "model",
    "api", "fintech startup", "regulation", "compliance", "crypto", "defi",
    "prediction", "benchmark", "inference", "fine-tuning", "rlhf",
    "open source", "evaluation", "leaderboard", "capital markets",
]

# Mots-cles negatifs (articles hors-sujet a exclure)
KW_NEG = [
    "warehouse", "robotic path", "robot navigation", "care home", "smart speaker",
    "hospital", "medical imaging", "protein folding", "drug discovery",
    "poker", "chess", "game theory board", "autonomous driving", "self-driving",
    "image generation", "text-to-image", "diffusion model art", "video generation",
    "climate model", "weather prediction", "seismic", "geology",
    "social media bot", "misinformation detection",
]

# Limite arXiv par sous-feed pour eviter de tout inonder
ARXIV_MAX_PER_FEED = 8


def _clean_text(text: str) -> str:
    """Nettoyage HTML + suppression prefixes arXiv bruts."""
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    # Supprimer le prefixe arXiv "arXiv:XXXX Announce Type: new Abstract:"
    text = re.sub(r"arXiv:\S+\s+Announce\s+Type:\s*\w+\s+Abstract:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_date(entry) -> datetime:
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def _score(title: str, summary: str) -> int:
    text = (title + " " + summary).lower()
    score = 0
    for kw in KW_HIGH:
        if kw in text:
            score += 10
    for kw in KW_MED:
        if kw in text:
            score += 3
    return min(score, 100)


def _is_relevant(title: str, summary: str) -> bool:
    """Filtre negatif — elimine les articles clairement hors-sujet."""
    text = (title + " " + summary).lower()
    for kw in KW_NEG:
        if kw in text:
            return False
    return True


# =============================================================================
# FETCH
# =============================================================================

def fetch_articles(days_override: int | None = None) -> list[dict]:
    try:
        import feedparser
    except ImportError:
        print("[VEILLE] pip install feedparser requis")
        sys.exit(1)

    now     = datetime.now(timezone.utc)
    raw     = []
    arxiv_counts: dict[str, int] = {}

    for src in SOURCES:
        src_days = days_override or src.get("days", 7)
        cutoff   = now - timedelta(days=src_days)
        is_arxiv = "arxiv" in src["name"].lower()

        try:
            feed = feedparser.parse(src["url"])
            count = 0
            for entry in feed.entries:
                if is_arxiv and arxiv_counts.get(src["name"], 0) >= ARXIV_MAX_PER_FEED:
                    break
                pub = _parse_date(entry)
                if pub < cutoff:
                    continue
                title   = _clean_text(getattr(entry, "title",   "") or "")
                summary = _clean_text(getattr(entry, "summary", "") or getattr(entry, "description", "") or "")
                link    = getattr(entry, "link", "") or ""
                if not title or not link:
                    continue
                # Filtre negatif
                if not _is_relevant(title, summary):
                    continue
                score = _score(title, summary)
                raw.append({
                    "source":  src["name"],
                    "cat":     src["cat"],
                    "title":   title[:220],
                    "summary": summary[:600],
                    "link":    link,
                    "date":    pub,
                    "score":   score,
                    "idx":     len(raw),
                })
                if is_arxiv:
                    arxiv_counts[src["name"]] = arxiv_counts.get(src["name"], 0) + 1
                count += 1
        except Exception as e:
            print(f"[VEILLE] {src['name']} : {e}")

    # Diversifier : max 4 articles par source dans le top 30
    raw.sort(key=lambda a: (a["score"], a["date"]), reverse=True)
    seen_src: dict[str, int] = {}
    balanced = []
    for a in raw:
        n = seen_src.get(a["source"], 0)
        if n < 4:
            balanced.append(a)
            seen_src[a["source"]] = n + 1

    print(f"[VEILLE] {len(raw)} articles bruts -> {len(balanced)} apres filtrage/diversification")
    return balanced


# =============================================================================
# LLM : SELECTION + RESUMES EDITORIAUX (UN SEUL APPEL)
# =============================================================================

def llm_select_and_summarize(candidates: list[dict]) -> dict:
    """
    Un seul appel Groq :
    - Selectionne les 10 articles les plus pertinents
    - Pour chaque article : passage cite, these, contre-these, application FinSight rigoureuse
    - Intro editoriale 120-150 mots
    Retourne {editorial, articles:[{...}]}
    """
    groq_key = os.getenv("GROQ_API_KEY_1") or os.getenv("GROQ_API_KEY_2") or os.getenv("GROQ_API_KEY")
    if not groq_key:
        print("[VEILLE] Aucune cle Groq — resumes basiques")
        return _fallback_selection(candidates)

    # Preparer la liste des candidats pour le prompt
    top30 = candidates[:30]
    art_list = ""
    for i, a in enumerate(top30):
        art_list += f"\n[{i}] SOURCE={a['source']} | CAT={a['cat']} | DATE={a['date'].strftime('%d/%m/%Y')}\nTITRE: {a['title']}\nCONTENU: {a['summary'][:400]}\n"

    prompt = f"""Tu es analyste senior de FinSight IA, plateforme d'analyse financiere multi-agents LLM.
Audience : directeurs d'investissement, analystes sell-side/buy-side, quants, DG fintech.

MISSION :
1. Selectionner les 10 articles les PLUS PERTINENTS parmi les {len(top30)} candidats.
   Criteres : LLM en finance, agents IA pour investissement, donnees financieres, automatisation analyse, fintech.
   EXCLURE : recherches trop academiques sans application finance, articles non-financiers.

2. Pour chaque article, produire une analyse structuree RIGOUREUSE en francais :

   passage_cle : Extraire ou reformuler une CITATION representative de l article entre guillemets.
                 Doit refleter le point central du texte. 15-30 mots maximum.

   these : 2 phrases argumentant POUR la pertinence de cet article.
           Arguments concrets, chiffres si disponibles, pourquoi c est significatif.

   contre_these : 1-2 phrases de CRITIQUE ou LIMITES objectives.
                  Biais methodologique, conditions d application, limitations.

   application_finsight : 3-4 phrases structurees sur l application concrete a FinSight IA.
                          Mentionner : (1) le module concerne (AgentSentiment, AgentQuant, AgentSynthese, etc.),
                          (2) le mecanisme d integration specifique,
                          (3) l impact mesurable attendu sur la qualite des analyses,
                          (4) la priorite d implementation.

   priorite : HAUTE | MOYENNE | FAIBLE selon l urgence pour FinSight.

3. Rediger une INTRODUCTION EDITORIALE de 120-150 mots sur les themes dominants.
   Style : direct, analytique, sans jargon creux.

ARTICLES CANDIDATS :
{art_list}

Reponds UNIQUEMENT en JSON valide sans markdown ni texte autour :
{{
  "editorial": "<120-150 mots introduction editoriale>",
  "selection": [
    {{
      "idx": <entier — index original de l article>,
      "passage_cle": "<citation ou formulation representative entre guillemets>",
      "these": "<2 phrases argumentant pour la pertinence>",
      "contre_these": "<1-2 phrases de critique ou limites>",
      "application_finsight": "<3-4 phrases application concrete a FinSight>",
      "priorite": "<HAUTE|MOYENNE|FAIBLE>"
    }}
  ]
}}"""

    try:
        from groq import Groq
        client = Groq(api_key=groq_key)
        resp   = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4500,
            temperature=0.3,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
        m   = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            parsed = json.loads(m.group())
            enriched = []
            for sel in parsed.get("selection", [])[:10]:
                idx = sel.get("idx")
                if idx is not None and 0 <= idx < len(top30):
                    art = dict(top30[idx])
                    art["passage_cle"]        = sel.get("passage_cle",        "")
                    art["these"]              = sel.get("these",              art["summary"][:200])
                    art["contre_these"]       = sel.get("contre_these",       "")
                    art["application_finsight"] = sel.get("application_finsight", "Impact sur les pipelines FinSight.")
                    art["priorite"]           = sel.get("priorite",           "MOYENNE")
                    # Compat backward : resume_fr = these pour sections qui l utiliseraient
                    art["resume_fr"]          = art["these"]
                    art["implication"]        = art["application_finsight"]
                    enriched.append(art)
            return {
                "editorial": parsed.get("editorial", ""),
                "articles":  enriched,
            }
    except Exception as e:
        print(f"[VEILLE] LLM select error : {e}")

    return _fallback_selection(candidates)


def _fallback_selection(candidates: list[dict]) -> dict:
    """Fallback sans LLM : top 10 par score avec resume brut."""
    arts = []
    for a in candidates[:10]:
        a = dict(a)
        a["passage_cle"]         = ""
        a["these"]               = a["summary"][:250]
        a["contre_these"]        = ""
        a["application_finsight"] = "Pertinent pour les pipelines FinSight."
        a["priorite"]            = "MOYENNE"
        a["resume_fr"]           = a["these"]
        a["implication"]         = a["application_finsight"]
        arts.append(a)
    return {"editorial": "", "articles": arts}


# =============================================================================
# BONUS 5 ARTICLES
# =============================================================================

def suggest_bonus(top10: list[dict]) -> list[dict]:
    groq_key = os.getenv("GROQ_API_KEY_1") or os.getenv("GROQ_API_KEY_2") or os.getenv("GROQ_API_KEY")
    if not groq_key:
        return []
    try:
        from groq import Groq
        client = Groq(api_key=groq_key)
        themes = ", ".join(sorted({a.get("cat","") for a in top10[:5]}))
        titles = "; ".join([a["title"][:80] for a in top10[:5]])
        prompt = (
            f"Tu es veilleur technologique expert en LLM et finance quantitative.\n"
            f"Cette semaine dans la veille FinSight : {themes}.\n"
            f"Articles principaux : {titles}.\n\n"
            f"Propose 5 ressources COMPLEMENTAIRES et specifiques (GitHub repos, papiers arXiv recents, "
            f"posts de blog techniques, datasets financiers, outils open-source) "
            f"utiles pour une plateforme d'analyse financiere multi-agents.\n"
            f"Sois tres specifique (vrais noms, vrais liens si tu les connais).\n\n"
            f"JSON UNIQUEMENT (array de 5 objets, aucun markdown) :\n"
            f'[{{"title":"...","source":"...","link":"...","cat":"...","these":"<2 phrases pertinence>","contre_these":"<1 phrase limite>","application_finsight":"<3-4 phrases module+integration+impact+priorite>","priorite":"HAUTE|MOYENNE|FAIBLE"}}]'
        )
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1400,
            temperature=0.55,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
        m   = re.search(r'\[.*\]', raw, re.DOTALL)
        if m:
            bonus = json.loads(m.group())
            out   = []
            for b in bonus:
                b.setdefault("title",       "Article bonus")
                b.setdefault("source",      "IA suggestion")
                b.setdefault("link",        "")
                b.setdefault("cat",         "IA")
                b.setdefault("resume_fr",   "Contenu pertinent pour FinSight.")
                b.setdefault("implication", "A explorer pour les pipelines FinSight.")
                b["date"] = datetime.now(timezone.utc)
                b["score"] = 50
                if b["title"] != "Article bonus":
                    out.append(b)
            return out[:5]
    except Exception as e:
        print(f"[VEILLE] Bonus LLM : {e}")
    return []


# =============================================================================
# PDF INSTITUTIONNEL
# =============================================================================

# Palette
C_NAVY      = "#1B3A6B"
C_NAVY2     = "#2A5298"
C_GREEN     = "#1A7A4A"
C_ORANGE    = "#C05000"
C_PURPLE    = "#5B2D8E"
C_AMBER     = "#B06000"
C_WHITE     = "#FFFFFF"
C_GREY_BG   = "#F7F9FC"
C_GREY_MED  = "#E4E9F0"
C_GREY_DARK = "#8898AA"
C_BLACK     = "#1A1A1A"

# Couleur par categorie
CAT_COLORS = {
    "LLM":      C_NAVY2,
    "Agents":   C_NAVY2,
    "Fintech":  C_GREEN,
    "Finance":  C_GREEN,
    "Recherche":C_ORANGE,
    "IA":       C_PURPLE,
    "VC":       C_AMBER,
    "Tech":     C_AMBER,
    "Data":     C_PURPLE,
}


def _h(hex_str: str):
    from reportlab.lib import colors
    return colors.HexColor(hex_str)


def _enc(s: str) -> str:
    """Encode cp1252 — evite les erreurs ReportLab Windows."""
    return (s or "").encode("cp1252", errors="replace").decode("cp1252")


def build_pdf(result: dict, bonus5: list[dict], output_path: Path) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak, KeepTogether
    )
    from reportlab.lib import colors

    W, H = A4
    ML = MR = 18 * mm
    MT = 24 * mm
    MB = 16 * mm

    _MOIS_FR = ["janvier","fevrier","mars","avril","mai","juin",
                "juillet","aout","septembre","octobre","novembre","decembre"]
    today    = datetime.now()
    date_fr  = f"{today.day} {_MOIS_FR[today.month-1]} {today.year}"
    edition  = f"Edition du {date_fr}"

    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
        title=f"FinSight IA — Veille Technologique — {date_fr}",
        author="FinSight IA",
    )

    # -- Styles -----------------------------------------------------------------
    def _s(name, **kw):
        base = dict(fontName="Helvetica", fontSize=10, leading=14,
                    textColor=_h(C_BLACK), spaceAfter=0)
        base.update(kw)
        return ParagraphStyle(name, **base)

    S_MAIN_TITLE = _s("mt", fontName="Helvetica-Bold", fontSize=26,
                       textColor=_h(C_NAVY), leading=30, spaceAfter=2)
    S_MAIN_DATE  = _s("md", fontName="Helvetica", fontSize=11,
                       textColor=_h(C_GREY_DARK), spaceAfter=0)
    S_TAGS_LINE  = _s("tl", fontName="Helvetica", fontSize=9,
                       textColor=_h(C_GREY_DARK), spaceAfter=0)
    S_EDITO      = _s("ed", fontName="Helvetica", fontSize=9.5, leading=14.5,
                       textColor=_h(C_BLACK), spaceAfter=0, alignment=TA_JUSTIFY)
    S_SEC_TITLE  = _s("st", fontName="Helvetica-Bold", fontSize=10,
                       textColor=_h(C_NAVY), leading=13, spaceAfter=0,
                       textTransform="uppercase", letterSpacing=0.8)
    S_ART_NUM    = _s("an", fontName="Helvetica-Bold", fontSize=22,
                       textColor=_h(C_GREY_MED), leading=24, spaceAfter=0)
    S_ART_TITLE  = _s("at", fontName="Helvetica-Bold", fontSize=10.5,
                       textColor=_h(C_NAVY), leading=14, spaceAfter=3)
    S_META       = _s("am", fontName="Helvetica", fontSize=8,
                       textColor=_h(C_GREY_DARK), leading=11, spaceAfter=4)
    S_RESUME     = _s("ar", fontName="Helvetica", fontSize=9.5, leading=14,
                       textColor=_h(C_BLACK), spaceAfter=4, alignment=TA_JUSTIFY)
    S_IMPL       = _s("ai", fontName="Helvetica-Bold", fontSize=9,
                       textColor=_h(C_GREEN), leading=13, spaceAfter=0)
    S_LINK       = _s("al", fontName="Helvetica", fontSize=8,
                       textColor=_h(C_NAVY2), leading=11, spaceAfter=0)
    S_QUOTE      = _s("aq", fontName="Helvetica-Oblique", fontSize=9,
                       textColor=_h("#333333"), leading=13, spaceAfter=0, alignment=TA_JUSTIFY)
    S_THESE_LBL  = _s("tl2", fontName="Helvetica-Bold", fontSize=7.5,
                       textColor=_h(C_GREEN), leading=11, spaceAfter=0,
                       textTransform="uppercase", letterSpacing=0.5)
    S_THESE_TXT  = _s("tt", fontName="Helvetica", fontSize=9,
                       textColor=_h(C_BLACK), leading=13, spaceAfter=0, alignment=TA_JUSTIFY)
    S_CONTRA_LBL = _s("cl", fontName="Helvetica-Bold", fontSize=7.5,
                       textColor=_h(C_ORANGE), leading=11, spaceAfter=0,
                       textTransform="uppercase", letterSpacing=0.5)
    S_CONTRA_TXT = _s("ct", fontName="Helvetica", fontSize=9,
                       textColor=_h(C_BLACK), leading=13, spaceAfter=0, alignment=TA_JUSTIFY)
    S_APP_LBL    = _s("apl", fontName="Helvetica-Bold", fontSize=7.5,
                       textColor=_h(C_WHITE), leading=11, spaceAfter=0,
                       textTransform="uppercase", letterSpacing=0.5)
    S_APP_TXT    = _s("apt", fontName="Helvetica", fontSize=9,
                       textColor=_h(C_WHITE), leading=13, spaceAfter=0, alignment=TA_JUSTIFY)
    S_PRIO       = _s("pr", fontName="Helvetica-Bold", fontSize=8,
                       textColor=_h(C_WHITE), leading=11, spaceAfter=0)
    S_BONUS_T    = _s("bt", fontName="Helvetica-Bold", fontSize=10,
                       textColor=_h(C_AMBER), leading=14, spaceAfter=3)
    S_SEC_BONUS  = _s("sb", fontName="Helvetica-Bold", fontSize=10,
                       textColor=_h(C_AMBER), leading=13, spaceAfter=0,
                       textTransform="uppercase", letterSpacing=0.8)
    S_FOOTER     = _s("ft", fontName="Helvetica", fontSize=7.5,
                       textColor=_h(C_GREY_DARK), leading=10, alignment=TA_CENTER)

    articles = result.get("articles", [])
    editorial = result.get("editorial", "")
    content_w = W - ML - MR

    elems = []

    # ==========================================================================
    # PAGE DE GARDE INTEGREE (pas de page separee — debut du flux)
    # ==========================================================================

    elems.append(Spacer(1, 6 * mm))

    # Titre principal
    elems.append(Paragraph(_enc("FinSight IA"), S_MAIN_TITLE))
    elems.append(Paragraph(_enc("Veille Technologique"), _s("vt",
        fontName="Helvetica", fontSize=15, textColor=_h(C_NAVY2), leading=18, spaceAfter=2)))
    elems.append(Paragraph(_enc(edition), S_MAIN_DATE))

    # Ligne de tags thematiques
    cats = sorted({a.get("cat","") for a in articles if a.get("cat")})
    tags = "  ·  ".join(cats) if cats else "LLM  ·  Finance  ·  Agents  ·  Recherche"
    elems.append(Spacer(1, 2 * mm))
    elems.append(Paragraph(_enc(tags), S_TAGS_LINE))
    elems.append(Spacer(1, 3 * mm))

    # Ligne de separation epaisse
    elems.append(HRFlowable(width="100%", thickness=2, color=_h(C_NAVY), spaceAfter=8))

    # -- Editorial intro --------------------------------------------------------
    if editorial:
        edito_table = Table(
            [[Paragraph(_enc(editorial), S_EDITO)]],
            colWidths=[content_w],
        )
        edito_table.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (-1,-1), _h(C_GREY_BG)),
            ("BOX",         (0,0), (-1,-1), 0.5, _h(C_GREY_MED)),
            ("LEFTPADDING",  (0,0), (-1,-1), 10),
            ("RIGHTPADDING", (0,0), (-1,-1), 10),
            ("TOPPADDING",   (0,0), (-1,-1), 8),
            ("BOTTOMPADDING",(0,0), (-1,-1), 8),
        ]))
        elems.append(edito_table)
        elems.append(Spacer(1, 6 * mm))

    # ==========================================================================
    # SECTION TOP 10
    # ==========================================================================

    # En-tete de section
    sec_row = Table(
        [[Paragraph(_enc("Selection FinSight — Top 10 articles"), S_SEC_TITLE),
          Paragraph(_enc(f"{len(articles)} articles  |  {len(set(a.get('source','') for a in articles))} sources"), S_META)]],
        colWidths=[content_w * 0.72, content_w * 0.28],
    )
    sec_row.setStyle(TableStyle([
        ("ALIGN",       (1,0), (1,0), "RIGHT"),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING",   (0,0), (-1,-1), 0),
        ("BOTTOMPADDING",(0,0), (-1,-1), 6),
    ]))
    elems.append(sec_row)
    elems.append(HRFlowable(width="100%", thickness=0.5, color=_h(C_GREY_MED), spaceAfter=6))

    # Couleurs priorite
    PRIO_COLORS = {"HAUTE": "#B22222", "MOYENNE": "#1B3A6B", "FAIBLE": "#5B7A9B"}

    # -- Articles ---------------------------------------------------------------
    for i, art in enumerate(articles):
        date_label = art["date"].strftime("%d/%m/%Y") if hasattr(art.get("date"), "strftime") else str(art.get("date",""))[:10]
        cat        = art.get("cat", "IA")
        cat_color  = CAT_COLORS.get(cat, C_NAVY2)
        source     = art.get("source", "?")
        link       = art.get("link",   "")
        link_short = re.sub(r"^https?://(?:www\.)?", "", link)[:90]
        passage    = art.get("passage_cle", "")
        these      = art.get("these", art.get("resume_fr", art.get("summary",""))[:250])
        contre     = art.get("contre_these", "")
        appli      = art.get("application_finsight", art.get("implication",""))
        priorite   = art.get("priorite", "MOYENNE").upper()
        prio_color = PRIO_COLORS.get(priorite, C_NAVY)

        # Badge categorie + meta
        cat_badge = (
            f'<font color="{cat_color}"><b>[{_enc(cat.upper())}]</b></font>'
            f'  <font color="{C_GREY_DARK}">{_enc(source)}  ·  {date_label}</font>'
        )

        card_content = [
            Paragraph(_enc(f"{i+1:02d}. {art['title']}"), S_ART_TITLE),
            Paragraph(cat_badge, S_META),
            Spacer(1, 3),
        ]

        # Citation / passage cle
        if passage:
            quote_table = Table(
                [[Paragraph(_enc(passage), S_QUOTE)]],
                colWidths=[content_w - 28],
            )
            quote_table.setStyle(TableStyle([
                ("BACKGROUND",   (0,0), (-1,-1), _h("#F0F4F8")),
                ("LINEBEFORE",   (0,0), (0,-1), 3, _h(C_GREY_DARK)),
                ("LEFTPADDING",  (0,0), (-1,-1), 8),
                ("RIGHTPADDING", (0,0), (-1,-1), 8),
                ("TOPPADDING",   (0,0), (-1,-1), 5),
                ("BOTTOMPADDING",(0,0), (-1,-1), 5),
            ]))
            card_content.append(quote_table)
            card_content.append(Spacer(1, 5))

        # These + Contre-these cote a cote si les deux existent, sinon empiles
        if these or contre:
            col_w = (content_w - 28) / 2 - 3
            these_block = [
                Paragraph(_enc("These"), S_THESE_LBL),
                Spacer(1, 2),
                Paragraph(_enc(these), S_THESE_TXT),
            ]
            contra_block = [
                Paragraph(_enc("Contre-these"), S_CONTRA_LBL),
                Spacer(1, 2),
                Paragraph(_enc(contre if contre else "—"), S_CONTRA_TXT),
            ]
            tc_table = Table(
                [[these_block, contra_block]],
                colWidths=[col_w, col_w],
                hAlign="LEFT",
            )
            tc_table.setStyle(TableStyle([
                ("VALIGN",       (0,0), (-1,-1), "TOP"),
                ("LEFTPADDING",  (0,0), (-1,-1), 0),
                ("RIGHTPADDING", (0,0), (-1,-1), 0),
                ("TOPPADDING",   (0,0), (-1,-1), 0),
                ("BOTTOMPADDING",(0,0), (-1,-1), 0),
            ]))
            card_content.append(tc_table)
            card_content.append(Spacer(1, 5))

        # Application FinSight
        if appli:
            prio_label = f"Application FinSight  —  Priorite {priorite}"
            app_table = Table(
                [[Paragraph(_enc(prio_label), S_APP_LBL)],
                 [Paragraph(_enc(appli), S_APP_TXT)]],
                colWidths=[content_w - 28],
            )
            app_table.setStyle(TableStyle([
                ("BACKGROUND",   (0,0), (-1,-1), _h(prio_color)),
                ("LEFTPADDING",  (0,0), (-1,-1), 8),
                ("RIGHTPADDING", (0,0), (-1,-1), 8),
                ("TOPPADDING",   (0,0), (-1,-1), 5),
                ("BOTTOMPADDING",(0,0), (-1,-1), 5),
            ]))
            card_content.append(app_table)
            card_content.append(Spacer(1, 3))

        if link:
            card_content.append(Paragraph(_enc(f"  {link_short}"), S_LINK))

        # Carte avec fond alternant
        bg_color = C_GREY_BG if i % 2 == 0 else C_WHITE
        card = Table([[card_content]], colWidths=[content_w])
        card.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,-1), _h(bg_color)),
            ("LEFTPADDING",  (0,0), (-1,-1), 8),
            ("RIGHTPADDING", (0,0), (-1,-1), 8),
            ("TOPPADDING",   (0,0), (-1,-1), 8),
            ("BOTTOMPADDING",(0,0), (-1,-1), 8),
        ]))
        elems.append(KeepTogether([card, Spacer(1, 2)]))

    elems.append(Spacer(1, 4 * mm))

    # ==========================================================================
    # SECTION BONUS
    # ==========================================================================

    if bonus5:
        elems.append(HRFlowable(width="100%", thickness=1, color=_h(C_GREY_MED), spaceAfter=8))
        bonus_hdr = Table(
            [[Paragraph(_enc("Bonus — 5 ressources complementaires selectionnees par l'IA"), S_SEC_BONUS),
              Paragraph(_enc("Suggestions editoriales"), S_META)]],
            colWidths=[content_w * 0.75, content_w * 0.25],
        )
        bonus_hdr.setStyle(TableStyle([
            ("ALIGN",       (1,0), (1,0), "RIGHT"),
            ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING",  (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
            ("TOPPADDING",   (0,0), (-1,-1), 0),
            ("BOTTOMPADDING",(0,0), (-1,-1), 6),
        ]))
        elems.append(bonus_hdr)
        elems.append(HRFlowable(width="100%", thickness=0.5, color=_h(C_GREY_MED), spaceAfter=6))

        for i, art in enumerate(bonus5):
            date_label = str(art.get("date",""))[:10]
            cat        = art.get("cat","IA")
            source     = art.get("source","?")
            link       = art.get("link","")
            link_short = re.sub(r"^https?://(?:www\.)?", "", link)[:90]
            these      = art.get("these", art.get("resume_fr", art.get("summary",""))[:200])
            contre     = art.get("contre_these","")
            appli      = art.get("application_finsight", art.get("implication",""))
            priorite   = art.get("priorite","MOYENNE").upper()
            prio_color = PRIO_COLORS.get(priorite, C_NAVY)

            cat_badge = (
                f'<font color="{C_AMBER}"><b>[BONUS {i+1}]</b></font>'
                f'  <font color="{C_GREY_DARK}">{_enc(source)}  ·  {_enc(cat)}</font>'
            )
            bonus_card_content = [
                Paragraph(_enc(art.get("title","")), S_BONUS_T),
                Paragraph(cat_badge, S_META),
                Spacer(1, 3),
            ]
            if these:
                col_w = (content_w - 28) / 2 - 3
                these_b = [Paragraph(_enc("These"), S_THESE_LBL), Spacer(1,2), Paragraph(_enc(these), S_THESE_TXT)]
                contra_b = [Paragraph(_enc("Contre-these"), S_CONTRA_LBL), Spacer(1,2), Paragraph(_enc(contre if contre else "—"), S_CONTRA_TXT)]
                tc2 = Table([[these_b, contra_b]], colWidths=[col_w, col_w], hAlign="LEFT")
                tc2.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
                bonus_card_content.append(tc2)
                bonus_card_content.append(Spacer(1,5))
            if appli:
                app2 = Table([[Paragraph(_enc(f"Application FinSight — Priorite {priorite}"), S_APP_LBL)],[Paragraph(_enc(appli), S_APP_TXT)]], colWidths=[content_w - 28])
                app2.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),_h(prio_color)),("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
                bonus_card_content.append(app2)
                bonus_card_content.append(Spacer(1,3))
            if link:
                bonus_card_content.append(Paragraph(_enc(f"  {link_short}"), S_LINK))

            bonus_card = Table([[bonus_card_content]], colWidths=[content_w])
            bonus_card.setStyle(TableStyle([
                ("BACKGROUND",   (0,0), (-1,-1), _h("#FEFAF3")),
                ("LINEBEFORE",   (0,0), (0,-1), 2.5, _h(C_AMBER)),
                ("LEFTPADDING",  (0,0), (-1,-1), 10),
                ("RIGHTPADDING", (0,0), (-1,-1), 8),
                ("TOPPADDING",   (0,0), (-1,-1), 7),
                ("BOTTOMPADDING",(0,0), (-1,-1), 7),
            ]))
            elems.append(KeepTogether([bonus_card, Spacer(1, 3)]))

    # ==========================================================================
    # FOOTER
    # ==========================================================================

    elems.append(Spacer(1, 6 * mm))
    elems.append(HRFlowable(width="100%", thickness=1, color=_h(C_NAVY), spaceAfter=5))
    n_src = len(set(a.get("source","") for a in articles))
    elems.append(Paragraph(
        _enc(f"FinSight IA v1.0  —  Veille generee le {date_fr}  —  "
             f"{n_src} sources actives  —  Groq llama-3.3-70b  —  RSS / feedparser"),
        S_FOOTER
    ))
    elems.append(Paragraph(
        _enc("Document genere automatiquement. Les resumes sont produits par IA et peuvent contenir des approximations."
             " Ne constitue pas un conseil en investissement."),
        S_FOOTER
    ))

    # -- Header/footer sur chaque page ------------------------------------------
    def _on_page(canvas, doc_obj):
        canvas.saveState()
        # Bande navy en haut
        canvas.setFillColor(_h(C_NAVY))
        canvas.rect(0, H - 9 * mm, W, 9 * mm, fill=1, stroke=0)
        canvas.setFillColor(_h(C_WHITE))
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(ML, H - 6 * mm, "FinSight IA  ·  Veille Technologique")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(W - MR, H - 6 * mm,
                               f"{date_fr}  ·  Page {doc_obj.page}")
        canvas.restoreState()

    doc.build(elems, onFirstPage=_on_page, onLaterPages=_on_page)
    return output_path


# =============================================================================
# POINT D'ENTREE
# =============================================================================

def run_veille(days: int | None = None) -> Path:
    print(f"\n{'='*55}")
    print("  FINSIGHT IA -- Veille Technologique")
    print(f"{'='*55}\n")

    # 1. Fetch + filtrage
    candidates = fetch_articles(days_override=days)
    if not candidates:
        print("[VEILLE] Aucun article — essayez --days 30")
        sys.exit(1)

    # 2. Selection LLM + resumes editoriaux (un seul appel)
    print(f"[VEILLE] Selection et resumes editoriaux (LLM)...")
    result = llm_select_and_summarize(candidates)
    print(f"[VEILLE] {len(result.get('articles',[]))} articles selectionnes")

    # 3. Bonus
    print("[VEILLE] Suggestions bonus (LLM)...")
    bonus5 = suggest_bonus(result.get("articles", []))
    print(f"[VEILLE] {len(bonus5)} articles bonus")

    # 4. PDF
    _MOIS_FR = ["janvier","fevrier","mars","avril","mai","juin",
                "juillet","aout","septembre","octobre","novembre","decembre"]
    d = datetime.now()
    date_tag  = d.strftime("%Y%m%d")
    # Numero sequentiel sur la date : veille_20260326_1.pdf, _2.pdf, ...
    seq = 1
    while (OUTPUT_DIR / f"veille_{date_tag}_{seq}.pdf").exists():
        seq += 1
    out_path  = OUTPUT_DIR / f"veille_{date_tag}_{seq}.pdf"
    print(f"[VEILLE] Generation PDF -> {out_path.name}")
    build_pdf(result, bonus5, out_path)

    print(f"\n[VEILLE] Termine : {out_path}")
    print(f"{'='*55}\n")
    return out_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=None,
                        help="Fenetre temporelle globale (ecrase les fenetres par source)")
    args = parser.parse_args()

    pdf_path = run_veille(days=args.days)
    try:
        os.startfile(str(pdf_path))
    except Exception as e:
        print(f"[VEILLE] Ouverture PDF : {e}\n -> {pdf_path}")
