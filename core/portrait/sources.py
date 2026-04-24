"""Sources de données pour le Portrait d'entreprise.

Combine yfinance (officers, business summary) + Wikipedia (bio, photos)
+ Wikidata (image dirigeants).
"""
from __future__ import annotations
import logging
import re
from typing import Optional
from urllib.parse import quote
from dataclasses import dataclass, field

import requests

log = logging.getLogger(__name__)

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_FR_API = "https://fr.wikipedia.org/w/api.php"
TIMEOUT = 8


@dataclass
class Officer:
    name: str
    title: Optional[str] = None
    age: Optional[int] = None
    pay: Optional[float] = None
    bio: Optional[str] = None  # rempli par Wikipedia
    photo_url: Optional[str] = None  # rempli par Wikipedia/Wikimedia


@dataclass
class CompanyContext:
    ticker: str
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None
    employees: Optional[int] = None
    founded: Optional[int] = None
    long_business_summary: Optional[str] = None
    market_cap: Optional[float] = None
    currency: Optional[str] = None
    officers: list[Officer] = field(default_factory=list)
    wiki_history: Optional[str] = None  # extrait Wikipedia "History"
    wiki_intro: Optional[str] = None  # introduction Wikipedia


# ---------------------------------------------------------------------------
# yfinance
# ---------------------------------------------------------------------------
def fetch_yfinance_context(ticker: str) -> CompanyContext:
    """Récupère le contexte société depuis yfinance (cache 15 min via get_ticker)."""
    from core.yfinance_cache import get_ticker

    t = get_ticker(ticker)
    info = {}
    try:
        info = t.info or {}
    except Exception as e:
        log.warning(f"[portrait/sources] yfinance .info failed for {ticker}: {e}")

    officers_raw = info.get("companyOfficers", []) or []
    officers = []
    for o in officers_raw[:8]:  # max 8
        try:
            officers.append(
                Officer(
                    name=o.get("name", "").strip(),
                    title=o.get("title"),
                    age=o.get("age"),
                    pay=o.get("totalPay") or o.get("exercisedValue"),
                )
            )
        except Exception:
            continue

    return CompanyContext(
        ticker=ticker,
        name=info.get("longName") or info.get("shortName") or ticker,
        sector=info.get("sector"),
        industry=info.get("industry"),
        country=info.get("country"),
        website=info.get("website"),
        employees=info.get("fullTimeEmployees"),
        long_business_summary=info.get("longBusinessSummary"),
        market_cap=info.get("marketCap"),
        currency=info.get("financialCurrency") or info.get("currency"),
        officers=officers,
    )


# ---------------------------------------------------------------------------
# Wikipedia — intro + history
# ---------------------------------------------------------------------------
def _wiki_search_page(query: str, lang: str = "en") -> Optional[str]:
    """Cherche une page Wikipedia, retourne le titre du meilleur match."""
    api = WIKI_FR_API if lang == "fr" else WIKI_API
    try:
        r = requests.get(
            api,
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": 1,
            },
            timeout=TIMEOUT,
            headers={"User-Agent": "FinSight-IA/1.0"},
        )
        r.raise_for_status()
        results = r.json().get("query", {}).get("search", [])
        if results:
            return results[0].get("title")
    except Exception as e:
        log.debug(f"[portrait/sources] wiki search failed for {query}: {e}")
    return None


def _wiki_fetch_intro(title: str, lang: str = "en") -> Optional[str]:
    """Récupère le résumé (intro) Wikipedia d'une page."""
    api = WIKI_FR_API if lang == "fr" else WIKI_API
    try:
        r = requests.get(
            api,
            params={
                "action": "query",
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "titles": title,
                "format": "json",
                "redirects": 1,
            },
            timeout=TIMEOUT,
            headers={"User-Agent": "FinSight-IA/1.0"},
        )
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
        for p in pages.values():
            extract = p.get("extract")
            if extract:
                return extract.strip()
    except Exception as e:
        log.debug(f"[portrait/sources] wiki extract failed for {title}: {e}")
    return None


def _wiki_fetch_section(title: str, section_name: str, lang: str = "en") -> Optional[str]:
    """Récupère le contenu textuel d'une section précise (ex: 'History')."""
    api = WIKI_FR_API if lang == "fr" else WIKI_API
    try:
        # Récupère la liste des sections
        r = requests.get(
            api,
            params={
                "action": "parse",
                "page": title,
                "prop": "sections",
                "format": "json",
                "redirects": 1,
            },
            timeout=TIMEOUT,
            headers={"User-Agent": "FinSight-IA/1.0"},
        )
        r.raise_for_status()
        sections = r.json().get("parse", {}).get("sections", [])
        target_idx = None
        for s in sections:
            if section_name.lower() in (s.get("line", "").lower()):
                target_idx = s.get("index")
                break
        if target_idx is None:
            return None
        # Récupère le contenu
        r2 = requests.get(
            api,
            params={
                "action": "parse",
                "page": title,
                "section": target_idx,
                "prop": "wikitext",
                "format": "json",
                "redirects": 1,
            },
            timeout=TIMEOUT,
            headers={"User-Agent": "FinSight-IA/1.0"},
        )
        r2.raise_for_status()
        wikitext = r2.json().get("parse", {}).get("wikitext", {}).get("*", "")
        # Cleanup wikitext basique : retire références, templates, liens
        text = re.sub(r"\{\{[^{}]*\}\}", "", wikitext)
        text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
        text = re.sub(r"'''(.*?)'''", r"\1", text)
        text = re.sub(r"''(.*?)''", r"\1", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()[:6000]  # cap
    except Exception as e:
        log.debug(f"[portrait/sources] wiki section failed for {title}/{section_name}: {e}")
    return None


def enrich_with_wikipedia(ctx: CompanyContext) -> CompanyContext:
    """Ajoute intro + history Wikipedia à la société."""
    page = _wiki_search_page(ctx.name, lang="en")
    if page:
        ctx.wiki_intro = _wiki_fetch_intro(page, lang="en")
        ctx.wiki_history = _wiki_fetch_section(page, "History", lang="en")
    return ctx


# ---------------------------------------------------------------------------
# Photos dirigeants — Wikipedia pageimage
# ---------------------------------------------------------------------------
def fetch_officer_photo(name: str) -> Optional[str]:
    """Cherche une photo Wikipedia/Wikimedia d'une personne."""
    page = _wiki_search_page(name, lang="en")
    if not page:
        return None
    try:
        r = requests.get(
            WIKI_API,
            params={
                "action": "query",
                "prop": "pageimages",
                "piprop": "original",
                "pithumbsize": 400,
                "titles": page,
                "format": "json",
                "redirects": 1,
            },
            timeout=TIMEOUT,
            headers={"User-Agent": "FinSight-IA/1.0"},
        )
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
        for p in pages.values():
            orig = p.get("original") or p.get("thumbnail")
            if orig and orig.get("source"):
                return orig["source"]
    except Exception as e:
        log.debug(f"[portrait/sources] photo fetch failed for {name}: {e}")
    return None


def _is_valid_person_bio(name: str, page_title: str, intro: str) -> bool:
    """Vérifie que la page Wikipedia renvoyée concerne bien la PERSONNE cherchée.

    Sans cette validation, une recherche « Timothy D. Cook CEO & Director »
    peut renvoyer la page Steve Jobs (qui contient tous ces mots) et sa bio
    serait affichée comme celle de Cook (bug observé sur AAPL portrait 2026).
    Pareil, « Deirdre O'Brien » peut renvoyer une page « 2013 Birthday
    Honours » qui mentionne son nom en passant.

    Heuristiques :
      - Le dernier token du nom (souvent le nom de famille) doit apparaître
        dans les 300 premiers caractères de l'intro.
      - Le titre de la page Wikipedia ne doit pas ressembler à un article
        d'événement/catégorie (contient « Birthday », « List of »,
        « Honours », « Awards », « ceremony »...).
      - Le titre ne doit pas être un nom complètement différent (ex: Cook
        recherché mais page = « Steven Paul Jobs ») : on exige que AU MOINS
        un token de 3+ caractères du nom cherché apparaisse dans le titre.
    """
    if not name or not page_title or not intro:
        return False
    lower_title = page_title.lower()
    # Rejette les pages d'événements/catégories qui peuvent contenir le nom
    # en tant que citation (liste de récipiendaires, hommages collectifs...).
    _blacklist = ("birthday honours", "list of", "honours", "awards",
                  "ceremony", "new year honour", "members of",
                  "recipients of", "winners of")
    if any(b in lower_title for b in _blacklist):
        return False
    # Au moins un token significatif du nom doit être dans le titre.
    name_tokens = [t for t in name.replace(".", " ").split() if len(t) >= 3]
    if name_tokens:
        title_norm = lower_title
        if not any(t.lower() in title_norm for t in name_tokens):
            return False
    # Le nom de famille (dernier token alphabétique ≥ 3 chars) doit apparaître
    # dans les 300 premiers caractères de l'intro pour confirmer qu'elle
    # commence bien par parler de la bonne personne.
    surname_candidates = [t for t in name.replace(".", " ").split() if len(t) >= 3]
    if surname_candidates:
        surname = surname_candidates[-1].lower()
        if surname not in intro[:300].lower():
            return False
    return True


def _llm_generate_officer_bio(name: str, title: str, company: str) -> Optional[str]:
    """Fallback bio via LLM quand Wikipedia ne retourne rien (ou rejetée par
    la validation). Garde le ton factuel du reste du portrait."""
    try:
        from core.llm_provider import LLMProvider
        prompt = (
            f"Rédige une bio courte et factuelle (3 phrases max, 60 à 80 mots) "
            f"sur {name}, {title} chez {company}. Donne uniquement des faits "
            f"publics (parcours, années clés, formation si publique). "
            f"Commence directement par le nom. Pas de spéculation, pas "
            f"d'emoji, français avec accents. Si tu n'as aucune info fiable "
            f"sur cette personne, réponds exactement : INCONNU."
        )
        for prov, model in [("groq", "llama-3.3-70b-versatile"),
                             ("mistral", None),
                             ("anthropic", None)]:
            try:
                llm = LLMProvider(provider=prov, model=model)
                ans = llm.generate(prompt, system="Tu es analyste sobre, factuel.",
                                     max_tokens=180)
                if ans and "INCONNU" not in ans.upper() and len(ans.strip()) > 40:
                    return ans.strip()[:600]
            except Exception as e:
                log.debug(f"[portrait/sources] LLM bio {prov} fail: {e}")
                continue
    except Exception as e:
        log.debug(f"[portrait/sources] LLM bio init fail: {e}")
    return None


def fetch_officer_bio(name: str, role_hint: Optional[str] = None,
                       company_name: Optional[str] = None) -> Optional[str]:
    """Récupère la bio Wikipedia d'un dirigeant (premier paragraphe).

    Étapes :
      1. Recherche Wikipedia par nom seul (le role_hint polluait la query
         et faisait ressortir des pages d'entreprise ou du CEO fondateur).
      2. Validation : la page trouvée concerne-t-elle bien la bonne personne ?
         Sinon on rejette (évite Tim Cook → bio Steve Jobs).
      3. Fallback LLM si Wikipedia ne donne rien d'utilisable et qu'on a
         `company_name` pour contextualiser.
    """
    if not name:
        return None
    # 1. Recherche Wikipedia par nom seul (NE PAS ajouter le role_hint, il
    # polluait la query et ressortait des pages « CEO » / pages entreprise).
    page = _wiki_search_page(name, lang="en")
    if page:
        intro = _wiki_fetch_intro(page, lang="en")
        if intro and _is_valid_person_bio(name, page, intro):
            return intro[:600].strip()
        else:
            log.info(f"[portrait/sources] wiki page '{page}' rejected for '{name}' "
                      f"(validation échouée)")
    # 2. Fallback LLM si on a le nom de la société
    if company_name:
        bio = _llm_generate_officer_bio(name, role_hint or "dirigeant", company_name)
        if bio:
            return bio
    return None
    return None


def enrich_officers_with_wikipedia(officers: list[Officer], company_name: str) -> list[Officer]:
    """Enrichit chaque officer avec photo + bio Wikipedia (best effort),
    fallback LLM pour la bio si Wikipedia ne trouve rien de pertinent."""
    for o in officers[:5]:  # cap : top 5 dirigeants
        if not o.name:
            continue
        try:
            o.photo_url = fetch_officer_photo(o.name)
            # company_name passé au fetch pour activer le fallback LLM
            # quand Wikipedia rejette la page (bio mismatch) ou ne trouve
            # rien (dirigeant récent sans page dédiée).
            o.bio = fetch_officer_bio(o.name, o.title, company_name=company_name)
        except Exception as e:
            log.debug(f"[portrait/sources] enrich {o.name} failed: {e}")
    return officers
