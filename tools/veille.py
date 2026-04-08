"""
tools/veille.py -- FinSight IA
Veille : IA appliquee a la finance d'entreprise.
Format : article institutionnel style note de recherche.

Architecture :
  1. Fetch RSS (~24 sources) -- fenetre 7-30j selon source
  2. Scoring / filtrage / diversification (max 4 par source)
  3. Un appel LLM : redaction d'un article structure 900-1100 mots
  4. Build PDF article + retourne markdown pour rendu Streamlit inline

Usage:
  python tools/veille.py
  python tools/veille.py --days 14
"""
from __future__ import annotations

import html
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
# SOURCES -- IA x Finance d'entreprise (sujet central)
# =============================================================================

SOURCES = [
    # =========================================================
    # TIER 1 : IA x Finance d'entreprise (sujet principal)
    # =========================================================
    {"name": "Net Interest",          "url": "https://www.netinterest.co/feed",                                       "cat": "IA Finance", "days": 14},
    {"name": "Fintech Brainfood",     "url": "https://fintechbrainfood.substack.com/feed",                            "cat": "IA Finance", "days": 14},
    {"name": "CB Insights Research",  "url": "https://www.cbinsights.com/research-briefing/feed/",                    "cat": "IA Finance", "days": 14},
    {"name": "McKinsey QuantumBlack", "url": "https://www.mckinsey.com/capabilities/quantumblack/rss",                "cat": "IA Finance", "days": 30},
    {"name": "McKinsey Finance",      "url": "https://www.mckinsey.com/capabilities/strategy-and-corporate-finance/rss","cat": "IA Finance","days": 30},
    {"name": "CFA Institute Blog",    "url": "https://blogs.cfainstitute.org/feed/",                                  "cat": "Finance",    "days": 14},
    {"name": "Finextra",              "url": "https://www.finextra.com/rss/headlines.aspx",                           "cat": "Fintech",    "days": 7},
    {"name": "The Financial Brand",   "url": "https://thefinancialbrand.com/feed/",                                   "cat": "IA Finance", "days": 14},
    {"name": "American Banker AI",    "url": "https://www.americanbanker.com/tag/artificial-intelligence/feed",       "cat": "IA Finance", "days": 14},
    {"name": "AGEFI",                 "url": "https://www.agefi.fr/rss/",                                             "cat": "Finance",    "days": 7},
    {"name": "Maddyness",             "url": "https://www.maddyness.com/feed/",                                       "cat": "Fintech",    "days": 7},
    # =========================================================
    # TIER 2 : Recherche academique (q-fin prioritaire, cs.* filtre)
    # =========================================================
    {"name": "arXiv q-fin",           "url": "http://export.arxiv.org/rss/q-fin",                                    "cat": "Recherche",  "days": 7},
    {"name": "arXiv cs.CE",           "url": "http://export.arxiv.org/rss/cs.CE",                                    "cat": "Recherche",  "days": 7},
    {"name": "arXiv cs.AI",           "url": "http://export.arxiv.org/rss/cs.AI",                                    "cat": "Recherche",  "days": 5},
    # =========================================================
    # TIER 3 : Macro / Regulation (contexte institutionnel)
    # =========================================================
    {"name": "BIS Research Papers",   "url": "https://www.bis.org/rss/bis_papers.rss",                               "cat": "Macro",      "days": 14},
    {"name": "Banque de France Blog", "url": "https://blocnotesdeleco.banque-france.fr/rss.xml",                      "cat": "Macro",      "days": 14},
    {"name": "BCE Blog",              "url": "https://www.ecb.europa.eu/rss/publications.rss",                        "cat": "Macro",      "days": 14},
    {"name": "WEF Finance",           "url": "https://www.weforum.org/rss?category=financial-and-monetary-systems",   "cat": "Macro",      "days": 14},
    # =========================================================
    # TIER 4 : Tech IA (contexte technologique, fenetre courte)
    # =========================================================
    {"name": "LangChain Blog",        "url": "https://blog.langchain.dev/rss/",                                       "cat": "Agents",     "days": 14},
    {"name": "The Batch (DL.AI)",     "url": "https://www.deeplearning.ai/the-batch/feed/",                           "cat": "LLM",        "days": 14},
    {"name": "VentureBeat AI",        "url": "https://venturebeat.com/category/ai/feed/",                             "cat": "IA",         "days": 7},
    {"name": "MIT Tech Review",       "url": "https://www.technologyreview.com/feed/",                                "cat": "IA",         "days": 14},
    # =========================================================
    # TIER 5 : LLM / modeles (contexte tech, fenetre longue)
    # =========================================================
    {"name": "Anthropic Blog",        "url": "https://www.anthropic.com/rss.xml",                                     "cat": "LLM",        "days": 30},
    {"name": "OpenAI Blog",           "url": "https://openai.com/blog/rss.xml",                                       "cat": "LLM",        "days": 30},
    {"name": "Hugging Face Blog",     "url": "https://huggingface.co/blog/feed.xml",                                  "cat": "LLM",        "days": 30},
    {"name": "Mistral AI Blog",       "url": "https://mistral.ai/news/rss",                                           "cat": "LLM",        "days": 30},
    {"name": "Import AI",             "url": "https://importai.substack.com/feed",                                    "cat": "LLM",        "days": 30},
]

ARXIV_MAX_PER_FEED = 8

# -- Mots-cles positifs (scoring) --
# Tier A (+15) : combinaisons IA + finance d'entreprise directes
KW_HIGH_A = [
    "corporate finance", "due diligence", "financial modeling", "fp&a",
    "credit scoring", "fraud detection", "audit ai", "ai audit",
    "capital allocation", "debt financing", "credit analysis",
    "mergers acquisitions", "m&a ai", "cfo ai", "ai cfo",
    "financial analysis ai", "ai financial", "earnings forecast",
    "financial reporting automation", "ai valuation", "dcf ai",
]
# Tier B (+10) : finance + tech generalement pertinents
KW_HIGH = [
    "llm", "large language model", "financial analysis", "finance", "trading",
    "investment", "agent", "rag", "retrieval augmented", "portfolio",
    "valuation", "dcf", "earnings", "risk management", "quantitative",
    "alpha generation", "fintech", "banking", "asset management",
    "hedge fund", "earnings call", "agentic", "multi-agent",
    "sentiment analysis", "forecast", "financial data", "market intelligence",
    "credit risk", "financial ai", "ai finance", "robo-advisor",
    "algorithmic trading", "compliance ai", "regulatory ai",
]
KW_MED = [
    "ai", "machine learning", "neural network", "model", "automation",
    "fintech startup", "regulation", "compliance", "prediction",
    "open source", "capital markets", "reporting", "digitalization",
    "enterprise", "productivity", "efficiency", "cost reduction",
]

# -- Mots-cles negatifs (articles clairement hors-sujet) --
KW_NEG = [
    "warehouse", "robotic path", "robot navigation", "care home",
    "hospital", "medical imaging", "protein folding", "drug discovery",
    "poker", "chess", "game theory board", "autonomous driving",
    "image generation", "text-to-image", "diffusion model art", "video generation",
    "climate model", "weather prediction", "seismic", "geology",
    "social media bot", "misinformation detection",
    # Hors-sujet finance d'entreprise : modeles generaux sans application finance
    "fuel prices", "plastic", "cognitive framework", "agi framework",
    "manipulation detection", "harmful content", "safety bug bounty",
    "cyberwar scaling", "computer vision harder", "llms training other",
    "measuring progress toward agi", "protecting people from harmful",
]


# =============================================================================
# NETTOYAGE / SCORING
# =============================================================================

def _clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
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
    for kw in KW_HIGH_A:
        if kw in text:
            score += 15
    for kw in KW_HIGH:
        if kw in text:
            score += 10
    for kw in KW_MED:
        if kw in text:
            score += 3
    return min(score, 100)


def _is_relevant(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    for kw in KW_NEG:
        if kw in text:
            return False
    return True


# =============================================================================
# FETCH RSS
# =============================================================================

def fetch_articles(days_override: int | None = None) -> list[dict]:
    try:
        import feedparser
    except ImportError:
        print("[VEILLE] pip install feedparser requis")
        sys.exit(1)

    now = datetime.now(timezone.utc)
    raw: list[dict] = []
    arxiv_counts: dict[str, int] = {}

    for src in SOURCES:
        src_days = days_override or src.get("days", 7)
        cutoff   = now - timedelta(days=src_days)
        is_arxiv = "arxiv" in src["name"].lower()

        try:
            feed = feedparser.parse(src["url"])
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
                if not _is_relevant(title, summary):
                    continue
                raw.append({
                    "source":  src["name"],
                    "cat":     src["cat"],
                    "title":   title[:220],
                    "summary": summary[:500],
                    "link":    link,
                    "date":    pub,
                    "score":   _score(title, summary),
                })
                if is_arxiv:
                    arxiv_counts[src["name"]] = arxiv_counts.get(src["name"], 0) + 1
        except Exception as e:
            print(f"[VEILLE] {src['name']} : {e}")

    # Tri score + diversification (max 4 par source)
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
# LLM : REDACTION DE L'ARTICLE INSTITUTIONNEL
# =============================================================================

def _build_prompt(candidates: list[dict], date_fr: str) -> str:
    # Pre-filtre : ecarte les articles dont le titre est clairement hors-sujet finance d'entreprise
    _TITLE_NEG = [
        "cyberwar", "bug bounty", "voice agent", "audio ai", "agi framework",
        "cognitive framework", "harmful manipulation", "plastic could",
        "fuel prices", "online seller", "product discovery in chat",
        "evaluating voice", "llms training other",
        "political superintelligence", "robot drummer", "society of minds",
        "scaling laws for cyber", "distributed training run", "image generation",
        "text-to-image", "protein folding", "drug discovery", "medical imaging",
    ]
    filtered = [
        a for a in candidates
        if not any(kw in (a.get("title","") + " " + a.get("summary","")).lower() for kw in _TITLE_NEG)
    ]
    # Garder au moins 15 si le filtre est trop agressif
    if len(filtered) < 15:
        filtered = candidates
    top20 = filtered[:15]  # 15 au lieu de 20 pour reduire la taille du prompt
    art_list = ""
    for i, a in enumerate(top20):
        d = a["date"].strftime("%d/%m/%Y") if hasattr(a.get("date"), "strftime") else str(a.get("date",""))[:10]
        art_list += (
            f"\n[{i}] {a['source']} | {d}\n"
            f"TITRE: {a['title']}\nEXTRAIT: {a['summary'][:250]}\nLIEN: {a['link']}\n"
        )

    return f"""Tu es analyste senior dans une division recherche institutionnelle specialisee en IA appliquee a la finance d\'entreprise.
Audience : directeurs financiers (CFO), analystes M&A, responsables corporate finance, investisseurs institutionnels.

MODELE DE STYLE : Notes de recherche JP Morgan / Goldman Sachs Macro Research.
Regles absolues de style :
1. Titres de sections DECLARATIFS : ils enoncent une conclusion. Ex : "Les agents IA compriment le cycle de cloture comptable" et non "IA et comptabilite".
2. "En bref" : liste de 4-5 bullets. Chaque bullet = un fait ou conclusion, verbe d\'action en debut.
3. Phrases courtes. Maximum 25 mots. Pas de subordonnees enchassees.
4. Zero jargon creux : "game-changer", "paradigm shift", "revolutionner", "transformer profondement" INTERDITS.
5. Pas de hedging ("il semble que", "peut-etre", "pourrait potentiellement").

SUJET CENTRAL : Comment l\'IA (LLM, agents, GenAI, ML) transforme la FINANCE D\'ENTREPRISE.
Sujets prioritaires : valorisation automatisee, analyse financiere, due diligence, credit scoring,
FP&A predictif, reporting automatise, detection de fraude, gestion des risques, M&A assistee par IA,
modeles de prevision, copilotes financiers, agents d\'analyse.
Marches financiers : contexte uniquement, pas sujet principal.

ANGLE GLOBAL OBLIGATOIRE : Chaque section doit ouvrir sur les implications macro : economie,
societe, secteurs (banque, assurance, conseil), regulation (DORA, AI Act, Bale IV, MiFID),
politique industrielle. Pas de section separee pour ca : c\'est tisse dans chaque paragraphe.

EXPERTS A CONVOQUER DANS LE CORPS DU TEXTE :
Integre leurs positions la ou leur point de vue enrichit ou contredit l\'argument. Pas de section dedidee.
Profils selon pertinence : regulateurs (CE, BCE, AMF), juristes/avocats (droit IA, responsabilite),
forces armees/securite nationale, ingenieurs/chercheurs, economistes, grands dirigeants/CEO, ecologistes/ESG.
Regles :
- Position issue d\'une source collectee : integre le nom de la source naturellement dans la phrase.
- Position publique connue : indique "(position connue)" apres la citation.
- Contradictions entre experts : dans le meme paragraphe, c\'est la tension qui apporte la valeur.
- Minimum 3 profils d\'experts differents repartis dans l\'article.

CITATIONS -- STYLE JOURNAL, PAS ANNEXE :
N\'utilise JAMAIS les numeros [1], [2], [3] etc. qui renvoient a une liste en fin d\'article.
Integre la source directement dans la phrase, de facon naturelle :
  "Selon Finextra, SIX a integre Snowflake pour..."
  "D\'apres un rapport de McKinsey QuantumBlack, les equipes FP&A..."
  "Comme l\'a indique Jamie Dimon (JP Morgan) lors de la conference annuelle..."
  "MIT Technology Review rapporte que..."
  "Une etude publiee sur arXiv (q-fin) montre que..."
Ne cite une source que pour des faits specifiques. Les connaissances generales n\'ont pas besoin de citation.
INTERDIT d\'inventer des chiffres. Si la source ne les donne pas, formule qualitativement.
EXPERTS REELS UNIQUEMENT : Tirole, Stiglitz, Blanchard, Lagarde, Gensler, Altman, Amodei, Dimon, Fink, Bengio, LeCun, Ng.
N\'invente jamais un nom d\'expert ni une citation.

ARTICLES DISPONIBLES ({len(top20)} sources collectees) :
{art_list}

MISSION : Redige un article de revue institutionnelle EN FRANCAIS de 1800-2200 mots.
C\'est un article long, riche, developpe. 4 a 5 pages. Developpe chaque argument en profondeur.
Un article court (< 1400 mots) est un echec.

STRUCTURE EXACTE :

## [Titre declaratif max 12 mots]
*[Sous-titre : une phrase de contexte factuel]*
**FinSight IA · Veille IA & Finance d\'Entreprise · {date_fr}**

### En bref
- [Fait ou conclusion 1 -- verbe d\'action]
- [Fait ou conclusion 2]
- [Fait ou conclusion 3]
- [Fait ou conclusion 4]
- [Fait ou conclusion 5]

### [Titre section 1 DECLARATIF]
[350-450 mots. Prose analytique. Sources citees inline naturellement. Experts integres la ou ils enrichissent.
Impacts sur les metiers de la finance d\'entreprise. Vue macro en fin de section.]

### [Titre section 2 DECLARATIF]
[300-380 mots. Meme exigences. Perspectives contradictoires si pertinent.]

### [Titre section 3 DECLARATIF -- obligatoire, ne pas fusionner]
[250-320 mots. Peut couvrir regulation, geopolitique IA, ou troisieme tendance cle.]

### Implications globales
[200-260 mots. Economie, societe, secteurs, indices, regulation europeenne, politique industrielle.
Cite les positions de regulateurs ou decideurs si pertinent.]

### Points de vigilance
- [Risque ou limite precis -- pas de generalites]
- [Risque 2]
- [Risque 3]
- [Risque 4 optionnel]

### Conclusion
[80-100 mots. Synthese et projection 6-12 mois. Terminer sur un fait ou un enjeu concret, pas une banalite.]

---

### Regard FinSight
[180-220 mots. UNIQUEMENT ICI : impact sur FinSight IA. Specifique : agents (AgentQuant, AgentSynthese,
AgentData), fonctionnalites (valorisation, scoring, comparatif).

**(A) Impact sur FinSight** : 2-3 points concrets.

**(B) Theses d\'application** *(seulement si l\'analyse fait emerger des idees originales)* :
1-3 hypotheses inedites sur un usage de l\'IA en finance d\'entreprise. Inattendues, pas des reformulations.]

### Pour aller plus loin
[Liste des articles les plus pertinents utilises. Format :
- [Titre de l\'article](URL) -- *Nom de la source* -- Date
Seulement les sources reellement utiles pour approfondir. 5 a 10 liens maximum.]

REGLES ABSOLUES :
- TOUT en francais
- Citations inline naturelles, JAMAIS de numeros [n] renvoyant a une annexe
- Titres DECLARATIFS obligatoires
- Finance d\'entreprise = priorite. Marches = contexte
- Experts integres dans la prose, jamais en section separee
- Regard FinSight UNIQUEMENT apres Conclusion
- INTERDIT d\'inventer des chiffres ou des noms d\'experts

Reponds UNIQUEMENT en JSON valide sans markdown autour :
{{{{
  "title": "Titre",
  "subtitle": "Sous-titre",
  "article_md": "contenu complet en markdown (de ### En bref jusqu a ### Pour aller plus loin inclus)"
}}}}"""



def llm_write_article(candidates: list[dict], date_fr: str) -> dict:
    """Appelle le LLM pour rediger l'article institutionnel. Retourne {"title","subtitle","article_md","sources"}."""
    prompt = _build_prompt(candidates, date_fr)

    def _parse(raw: str) -> dict | None:
        raw = re.sub(r"^```(?:json)?", "", raw.strip()).strip()
        raw = re.sub(r"```$", "", raw).strip()
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if not m:
            return None
        candidate = m.group()
        # Tentative 1 : JSON direct
        try:
            parsed = json.loads(candidate)
            if parsed.get("article_md"):
                return parsed
        except Exception:
            pass
        # Tentative 2 : extraire les champs manuellement (LLM met des vraies newlines dans article_md)
        try:
            title    = re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', candidate)
            subtitle = re.search(r'"subtitle"\s*:\s*"((?:[^"\\]|\\.)*)"', candidate)
            # article_md : entre "article_md": " et la fin du JSON ("}") — sans "sources" requis
            art_m = re.search(r'"article_md"\s*:\s*"(.*?)"\s*(?:,\s*"[a-z]|\})', candidate, re.DOTALL)
            if not (title and art_m):
                return None
            article_md = art_m.group(1)
            article_md = article_md.replace("\\n", "\n").replace('\\"', '"')
            if not article_md.strip():
                return None
            return {
                "title":      title.group(1).replace('\\"', '"') if title else "",
                "subtitle":   subtitle.group(1).replace('\\"', '"') if subtitle else "",
                "article_md": article_md,
                "sources":    [],
            }
        except Exception:
            return None

    # 1. Groq
    groq_keys = [k for k in [
        os.getenv("GROQ_API_KEY_1"),
        os.getenv("GROQ_API_KEY_2"),
        os.getenv("GROQ_API_KEY"),
    ] if k]
    for gk in groq_keys:
        for model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
            try:
                from groq import Groq
                resp = Groq(api_key=gk).chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=4000,
                    temperature=0.35,
                )
                result = _parse(resp.choices[0].message.content.strip())
                if result:
                    print(f"[VEILLE] LLM OK : {model} (key ...{gk[-6:]})")
                    return result
            except Exception as e:
                print(f"[VEILLE] Groq {model} ...{gk[-6:]} : {e}")

    # 2. Mistral fallback
    mk = os.getenv("MISTRAL_API_KEY")
    if mk:
        try:
            from mistralai.client import Mistral
            resp = Mistral(api_key=mk).chat.complete(
                model="mistral-small-latest",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2800,
                temperature=0.35,
            )
            result = _parse(resp.choices[0].message.content.strip())
            if result:
                print("[VEILLE] LLM OK : Mistral small (fallback)")
                return result
        except Exception as e:
            print(f"[VEILLE] Mistral : {e}")

    # 3. Anthropic fallback
    ak = os.getenv("ANTHROPIC_API_KEY")
    if ak:
        try:
            import anthropic as _ant
            resp = _ant.Anthropic(api_key=ak).messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2800,
                messages=[{"role": "user", "content": prompt}],
            )
            result = _parse(resp.content[0].text.strip())
            if result:
                print("[VEILLE] LLM OK : Anthropic haiku (fallback)")
                return result
        except Exception as e:
            print(f"[VEILLE] Anthropic : {e}")

    # 4. Fallback basique sans LLM
    print("[VEILLE] Tous LLM epuises — fallback basique")
    return _fallback_article(candidates, date_fr)


def _fallback_article(candidates: list[dict], date_fr: str) -> dict:
    """Fallback si aucun LLM disponible : article minimal a partir des titres."""
    items = candidates[:10]
    lines = [
        "### En bref",
        f"Voici une selection de {len(items)} articles sur l'IA appliquee a la finance d'entreprise "
        f"collectes cette semaine. Les resumes IA sont indisponibles (quota LLM depasse).",
        "",
        "### Articles de la semaine",
    ]
    for i, a in enumerate(items, 1):
        d = a["date"].strftime("%d/%m/%Y") if hasattr(a.get("date"), "strftime") else ""
        lines.append(f"**{i}. {a['title']}**")
        lines.append(f"*{a['source']} — {d}*")
        lines.append(a["summary"][:200] + "...")
        lines.append(f"[Source]({a['link']})")
        lines.append("")
    lines += [
        "---",
        "### Regard FinSight",
        "Synthese indisponible — relancer la veille avec quota LLM disponible.",
        "### Sources",
    ]
    for i, a in enumerate(items, 1):
        d = a["date"].strftime("%d/%m/%Y") if hasattr(a.get("date"), "strftime") else ""
        lines.append(f"[{i}] {a['title']} — *{a['source']}* — {d} — {a['link']}")
    return {
        "title":      "Veille IA & Finance d'Entreprise",
        "subtitle":   f"Edition du {date_fr} — synthese indisponible",
        "article_md": "\n".join(lines),
        "sources":    [{"n": i+1, "title": a["title"], "source": a["source"],
                        "date": a["date"].strftime("%d/%m/%Y") if hasattr(a.get("date"), "strftime") else "",
                        "url": a["link"]} for i, a in enumerate(items)],
    }


# =============================================================================
# PDF INSTITUTIONNEL -- FORMAT ARTICLE
# =============================================================================

C_NAVY      = "#1B3A6B"
C_NAVY2     = "#2A5298"
C_GREEN     = "#1A7A4A"
C_GREY_BG   = "#F7F9FC"
C_GREY_MED  = "#E4E9F0"
C_GREY_DARK = "#8898AA"
C_BLACK     = "#1A1A1A"
C_WHITE     = "#FFFFFF"
C_AMBER     = "#B06000"


def _h(hex_str: str):
    from reportlab.lib import colors
    return colors.HexColor(hex_str)


def _enc(s: str) -> str:
    return (s or "").encode("cp1252", errors="replace").decode("cp1252")


def _md_to_rl(text: str) -> str:
    """Markdown inline basique -> ReportLab Paragraph XML, cp1252 safe."""
    import html as _h2
    text = str(text or "")
    # Echapper d'abord les entites HTML
    text = _h2.escape(text, quote=False)
    # Bold **...**
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Italic *...*  (pas double)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    # [n] numeriques isoles (ancienne syntaxe) -> supprimes (on n'utilise plus de numerotation)
    text = re.sub(r'\s*\[\d+\]', '', text)
    # Markdown links [texte](url) -> lien cliquable
    def _link(m):
        txt = m.group(1)
        url = m.group(2)
        url_esc = _h2.escape(url, quote=True)
        return f'<link href="{url_esc}" color="{C_NAVY2}"><u>{txt}</u></link>'
    text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', _link, text)
    return _enc(text)


def build_pdf(article_data: dict, output_path: Path) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable, PageBreak
    )

    W, H = A4
    ML = MR = 20 * mm
    MT = 26 * mm
    MB = 18 * mm

    _MOIS_FR = ["janvier","fevrier","mars","avril","mai","juin",
                "juillet","aout","septembre","octobre","novembre","decembre"]
    today   = datetime.now()
    date_fr = f"{today.day} {_MOIS_FR[today.month-1]} {today.year}"

    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
        title=f"FinSight IA — Veille IA & Finance — {date_fr}",
        author="FinSight IA",
    )

    def _s(name, **kw):
        base = dict(fontName="Helvetica", fontSize=10, leading=14,
                    textColor=_h(C_BLACK), spaceAfter=0)
        base.update(kw)
        return ParagraphStyle(name, **base)

    S_COVER_TITLE  = _s("ct",  fontName="Helvetica-Bold", fontSize=24, textColor=_h(C_NAVY), leading=28, spaceAfter=2)
    S_COVER_SUB    = _s("cs",  fontName="Helvetica",      fontSize=12, textColor=_h(C_NAVY2), leading=16, spaceAfter=2)
    S_COVER_DATE   = _s("cd",  fontName="Helvetica",      fontSize=9.5, textColor=_h(C_GREY_DARK), spaceAfter=0)
    S_SECTION      = _s("sh",  fontName="Helvetica-Bold", fontSize=11, textColor=_h(C_NAVY), leading=15, spaceAfter=4, spaceBefore=8)
    S_LEAD         = _s("ld",  fontName="Helvetica",      fontSize=10.5, leading=15, textColor=_h(C_BLACK), spaceAfter=4, alignment=TA_JUSTIFY)
    S_BODY         = _s("bd",  fontName="Helvetica",      fontSize=9.5, leading=14, textColor=_h(C_BLACK), spaceAfter=3, alignment=TA_JUSTIFY)
    S_BULLET       = _s("bu",  fontName="Helvetica",      fontSize=9.5, leading=14, textColor=_h(C_BLACK), spaceAfter=1,
                               leftIndent=10, firstLineIndent=0)
    S_BULLET_FS    = _s("bfs", fontName="Helvetica",      fontSize=9.5, leading=14, textColor=_h(C_BLACK), spaceAfter=1,
                               leftIndent=10, firstLineIndent=0)
    S_NUMLIST      = _s("nl",  fontName="Helvetica",      fontSize=9.5, leading=14, textColor=_h(C_BLACK), spaceAfter=2,
                               leftIndent=14, firstLineIndent=0)
    S_FINSIGHT     = _s("fs",  fontName="Helvetica",      fontSize=9.5, leading=14, textColor=_h(C_BLACK), spaceAfter=3, alignment=TA_JUSTIFY)
    S_SOURCE_ITEM  = _s("si",  fontName="Helvetica",      fontSize=8.5, leading=12, textColor=_h(C_GREY_DARK), spaceAfter=2)
    S_FOOTER       = _s("ft",  fontName="Helvetica",      fontSize=7.5, textColor=_h(C_GREY_DARK), leading=10, alignment=TA_CENTER)
    S_BOLD_LABEL   = _s("bl",  fontName="Helvetica-Bold", fontSize=9,   textColor=_h(C_NAVY2), leading=13, spaceAfter=2)

    title    = article_data.get("title",    "Veille IA & Finance d'Entreprise")
    subtitle = article_data.get("subtitle", "")
    art_md   = article_data.get("article_md", "")
    sources  = article_data.get("sources",  [])

    elems = []

    # ------------------------------------------------------------------
    # EN-TETE
    # ------------------------------------------------------------------
    elems.append(Spacer(1, 4 * mm))
    elems.append(Paragraph(_enc(title), S_COVER_TITLE))
    if subtitle:
        elems.append(Paragraph(_enc(subtitle), S_COVER_SUB))
    elems.append(Paragraph(_enc(f"FinSight IA  ·  Veille IA & Finance d'Entreprise  ·  {date_fr}"), S_COVER_DATE))
    elems.append(Spacer(1, 3 * mm))
    elems.append(HRFlowable(width="100%", thickness=2, color=_h(C_NAVY), spaceAfter=6))

    # ------------------------------------------------------------------
    # CORPS DE L'ARTICLE (parsing markdown minimal)
    # ------------------------------------------------------------------
    in_sources = False
    in_finsight = False
    pending_section = None  # titre de section en attente
    para_buffer: list[str] = []

    def _flush_buffer():
        if para_buffer:
            text = " ".join(para_buffer).strip()
            if text:
                style = S_FINSIGHT if in_finsight else (S_LEAD if pending_section == "En bref" else S_BODY)
                elems.append(Paragraph(_md_to_rl(text), style))
                elems.append(Spacer(1, 1.5 * mm))
            para_buffer.clear()

    for line in art_md.split("\n"):
        stripped = line.strip()

        # Ligne vide -> flush paragraphe courant
        if not stripped:
            _flush_buffer()
            continue

        # Separateur ---
        if re.match(r'^-{3,}$', stripped):
            _flush_buffer()
            elems.append(Spacer(1, 3 * mm))
            elems.append(HRFlowable(width="100%", thickness=0.5, color=_h(C_GREY_MED), spaceAfter=4))
            continue

        # Titre h2 (## ...) -> titre principal (pas re-affiche, deja dans l'entete)
        if stripped.startswith("## "):
            continue

        # Sous-titre *...* au debut
        if stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**"):
            continue  # deja dans l'entete

        # Ligne **FinSight IA · ...** -> skip (deja dans entete)
        if stripped.startswith("**FinSight IA"):
            continue

        # Titre h3 (### ...) -> section
        if stripped.startswith("### "):
            _flush_buffer()
            sec_name = stripped[4:].strip()
            in_sources  = "sources" in sec_name.lower() or "pour aller" in sec_name.lower()
            in_finsight = "finsight" in sec_name.lower() or "regard" in sec_name.lower()
            pending_section = sec_name

            if in_sources:
                elems.append(Spacer(1, 3 * mm))
                elems.append(HRFlowable(width="100%", thickness=1, color=_h(C_GREY_MED), spaceAfter=4))
                elems.append(Paragraph(_enc("Pour aller plus loin"), S_SECTION))
            elif in_finsight:
                elems.append(Spacer(1, 3 * mm))
                elems.append(HRFlowable(width="100%", thickness=1.5, color=_h(C_NAVY2), spaceAfter=6))
                from reportlab.platypus import Table, TableStyle
                fs_header = Table(
                    [[Paragraph(_enc("Regard FinSight"), _s("fsh", fontName="Helvetica-Bold", fontSize=11,
                        textColor=_h(C_WHITE), leading=14, spaceAfter=0))]],
                    colWidths=[W - ML - MR],
                )
                fs_header.setStyle(TableStyle([
                    ("BACKGROUND",  (0,0),(-1,-1), _h(C_NAVY)),
                    ("LEFTPADDING", (0,0),(-1,-1), 8),
                    ("TOPPADDING",  (0,0),(-1,-1), 6),
                    ("BOTTOMPADDING",(0,0),(-1,-1), 6),
                ]))
                elems.append(fs_header)
                elems.append(Spacer(1, 3 * mm))
            else:
                elems.append(Paragraph(_enc(sec_name), S_SECTION))
                elems.append(HRFlowable(width="100%", thickness=0.5, color=_h(C_GREY_MED), spaceAfter=4))
            continue

        # Lignes "Pour aller plus loin" -- format : - [Titre](url) -- *Source* -- Date
        if in_sources:
            _flush_buffer()
            import html as _ht
            # Bullet avec lien markdown : - [titre](url) -- *source* -- date
            m_blink = re.match(r'^[-*]\s+\[(.+?)\]\((https?://[^\)]+)\)(.*)', stripped)
            if m_blink:
                title_txt = m_blink.group(1)
                url       = m_blink.group(2).rstrip('.,)')
                rest_txt  = m_blink.group(3).strip(' --')
                url_esc   = _ht.escape(url, quote=True)
                rl_line = (
                    f'\u2022 <link href="{url_esc}" color="{C_NAVY2}"><u>{_enc(title_txt)}</u></link>'
                    + (f' <i>{_enc(rest_txt)}</i>' if rest_txt else '')
                )
                elems.append(Paragraph(rl_line, S_SOURCE_ITEM))
                elems.append(Spacer(1, 1 * mm))
            else:
                # Fallback : rendre tel quel avec liens cliquables si presents
                elems.append(Paragraph(_md_to_rl(stripped), S_SOURCE_ITEM))
                elems.append(Spacer(1, 1 * mm))
            continue

        # Bullets markdown (- texte) -> chaque bullet sur sa propre ligne
        if re.match(r'^[-*]\s+', stripped):
            _flush_buffer()
            bullet_text = re.sub(r'^[-*]\s+', '', stripped)
            bstyle = S_BULLET_FS if in_finsight else S_BULLET
            elems.append(Paragraph(_enc("\u2022 ") + _md_to_rl(bullet_text), bstyle))
            continue

        # Listes numerotees (1. texte) -> chaque item sur sa propre ligne
        m_num = re.match(r'^(\d+)\.\s+(.+)$', stripped)
        if m_num:
            _flush_buffer()
            num_text = m_num.group(1) + ". " + m_num.group(2)
            elems.append(Paragraph(_md_to_rl(num_text), S_NUMLIST))
            continue

        # Lignes normales -> accumule dans le buffer paragraphe
        # Gere les lignes bold isolees (ex: **Titre de sous-section**)
        if stripped.startswith("**") and stripped.endswith("**") and stripped.count("**") == 2:
            _flush_buffer()
            elems.append(Paragraph(_md_to_rl(stripped), S_BOLD_LABEL))
            continue

        para_buffer.append(stripped)

    _flush_buffer()  # flush final

    # ------------------------------------------------------------------
    # FOOTER
    # ------------------------------------------------------------------
    elems.append(Spacer(1, 6 * mm))
    elems.append(HRFlowable(width="100%", thickness=1, color=_h(C_NAVY), spaceAfter=4))
    # Compte les liens "Pour aller plus loin" depuis article_md
    n_sources = len(re.findall(r'\bhttps?://', art_md))
    elems.append(Paragraph(
        _enc(f"FinSight IA v1.2  —  Veille generee le {date_fr}  —  {n_sources} sources referencees"),
        S_FOOTER,
    ))
    elems.append(Paragraph(
        _enc("Document genere par IA. Ne constitue pas un conseil en investissement. Sources verifiees au moment de la collecte."),
        S_FOOTER,
    ))

    def _on_page(canvas, doc_obj):
        canvas.saveState()
        canvas.setFillColor(_h(C_NAVY))
        canvas.rect(0, H - 9 * mm, W, 9 * mm, fill=1, stroke=0)
        canvas.setFillColor(_h(C_WHITE))
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(ML, H - 6 * mm, "FinSight IA  ·  Veille IA & Finance d'Entreprise")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(W - MR, H - 6 * mm, f"{date_fr}  ·  Page {doc_obj.page}")
        canvas.restoreState()

    doc.build(elems, onFirstPage=_on_page, onLaterPages=_on_page)
    return output_path


# =============================================================================
# POINT D'ENTREE
# =============================================================================

def run_veille(days: int | None = None) -> dict:
    """
    Lance la veille complete.
    Retourne {"pdf_path": Path, "article_md": str, "title": str, "subtitle": str, "date_fr": str}
    """
    print(f"\n{'='*55}")
    print("  FINSIGHT IA -- Veille IA & Finance d'Entreprise")
    print(f"{'='*55}\n")

    _MOIS_FR = ["janvier","fevrier","mars","avril","mai","juin",
                "juillet","aout","septembre","octobre","novembre","decembre"]
    today   = datetime.now()
    date_fr = f"{today.day} {_MOIS_FR[today.month-1]} {today.year}"

    # 1. Fetch
    candidates = fetch_articles(days_override=days)
    if not candidates:
        print("[VEILLE] Aucun article -- essayez --days 30")
        # Renvoie un resultat vide plutot que sys.exit (pour app.py)
        return {"pdf_path": None, "article_md": "Aucun article collecte.", "title": "Veille vide", "subtitle": "", "date_fr": date_fr}

    # 2. Redaction LLM
    print(f"[VEILLE] Redaction article LLM ({len(candidates)} candidats)...")
    article_data = llm_write_article(candidates, date_fr)
    print(f"[VEILLE] Article genere ({len(article_data.get('article_md',''))} chars)")

    # 3. PDF
    date_tag = today.strftime("%Y%m%d")
    seq = 1
    while (OUTPUT_DIR / f"veille_{date_tag}_{seq}.pdf").exists():
        seq += 1
    out_path = OUTPUT_DIR / f"veille_{date_tag}_{seq}.pdf"
    print(f"[VEILLE] Generation PDF -> {out_path.name}")
    build_pdf(article_data, out_path)

    print(f"\n[VEILLE] Termine : {out_path}")
    print(f"{'='*55}\n")

    return {
        "pdf_path":   out_path,
        "article_md": article_data.get("article_md", ""),
        "title":      article_data.get("title", "Veille IA & Finance d'Entreprise"),
        "subtitle":   article_data.get("subtitle", ""),
        "date_fr":    date_fr,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=None)
    args = parser.parse_args()

    result = run_veille(days=args.days)
    if result["pdf_path"]:
        try:
            os.startfile(str(result["pdf_path"]))
        except Exception:
            pass
