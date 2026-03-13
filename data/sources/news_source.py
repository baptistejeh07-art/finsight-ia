# =============================================================================
# FinSight IA — Source News : feedparser RSS
# data/sources/news_source.py
#
# Principe (brief §5) : "Filtrage avant FinBERT : Volume -99%"
# → On filtre par ticker/nom avant de passer à l'inference FinBERT.
#
# Sources :
#   - Finnhub : news ticker-spécifiques (déjà dans finnhub_source.py)
#   - RSS : Reuters, MarketWatch, Yahoo Finance, CNBC (news générales → filtrées)
# =============================================================================

from __future__ import annotations

import logging
from typing import Optional

import feedparser

log = logging.getLogger(__name__)

# Flux RSS fiables — ordre de priorité
RSS_FEEDS: dict[str, str] = {
    "reuters_biz":   "https://feeds.reuters.com/reuters/businessNews",
    "yahoo_finance": "https://finance.yahoo.com/rss/topstories",
    "marketwatch":   "http://feeds.marketwatch.com/marketwatch/topstories/",
    "cnbc_finance":  "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "seeking_alpha": "https://seekingalpha.com/market_currents.xml",
}

# Mapping ticker → mots-clés de recherche dans les flux généraux
# (Le ticker seul suffit rarement — ex. "aapl" n'apparaît pas dans les articles RSS)
_TICKER_KEYWORDS: dict[str, list[str]] = {
    # US
    "AAPL":  ["apple", "iphone", "tim cook", "aapl"],
    "TSLA":  ["tesla", "elon musk", "tsla"],
    "MSFT":  ["microsoft", "msft", "azure"],
    "NVDA":  ["nvidia", "nvda", "jensen huang"],
    "GOOGL": ["google", "alphabet", "googl"],
    "AMZN":  ["amazon", "amzn", "aws"],
    "META":  ["meta", "facebook", "zuckerberg"],
    "NFLX":  ["netflix", "nflx"],
    "JPM":   ["jpmorgan", "jp morgan", "jpm"],
    "BRK.B": ["berkshire", "warren buffett"],
    # EU
    "MC.PA":  ["lvmh", "louis vuitton", "moët", "mc.pa", "arnault"],
    "OR.PA":  ["l'oreal", "loreal", "or.pa"],
    "SAN.PA": ["sanofi", "san.pa"],
    "TTE.PA": ["totalenergies", "total", "tte.pa"],
    "BNP.PA": ["bnp paribas", "bnp.pa"],
    "AIR.PA": ["airbus", "air.pa"],
    "SU.PA":  ["schneider electric", "su.pa"],
    "SAP":    ["sap", "walldorf"],
}


def _keywords_for(ticker: str, company_name: str = "") -> list[str]:
    """Construit la liste des mots-clés de filtrage pour un ticker."""
    keys = set()

    # Ticker brut et base (sans extension)
    keys.add(ticker.lower())
    base = ticker.split(".")[0].lower()
    if len(base) >= 2:
        keys.add(base)

    # Mapping prédéfini
    if ticker in _TICKER_KEYWORDS:
        keys.update(_TICKER_KEYWORDS[ticker])

    # Nom de société (si fourni depuis CompanyInfo)
    if company_name:
        # Premier mot significatif du nom (ex. "Apple" de "Apple Inc.")
        first = company_name.split()[0].lower()
        if len(first) >= 4:
            keys.add(first)

    return list(keys)


def _is_relevant(title: str, summary: str, keywords: list[str]) -> bool:
    """Filtre un article : True si au moins un mot-clé présent."""
    text = f"{title} {summary}".lower()
    return any(kw in text for kw in keywords)


def fetch_rss(
    ticker: str,
    company_name: str = "",
    max_articles: int = 20,
) -> list[dict]:
    """
    Collecte news RSS filtrées par ticker/entreprise.

    Args:
        ticker:       ex. "AAPL", "MC.PA"
        company_name: ex. "Apple Inc." (optionnel, améliore le filtrage EU)
        max_articles: limite globale d'articles retournés

    Returns:
        Liste de dicts : [{"headline", "summary", "source", "url", "published"}, ...]
    """
    keywords = _keywords_for(ticker, company_name)
    results: list[dict] = []

    for source_name, url in RSS_FEEDS.items():
        if len(results) >= max_articles:
            break
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:30]:
                title   = entry.get("title", "")
                summary = entry.get("summary", "")

                if _is_relevant(title, summary, keywords):
                    results.append({
                        "headline":  title,
                        "summary":   summary[:300],
                        "source":    source_name,
                        "url":       entry.get("link", ""),
                        "published": entry.get("published", ""),
                    })
                    if len(results) >= max_articles:
                        break

        except Exception as e:
            log.warning(f"[RSS] {source_name} : {e}")

    log.info(f"[RSS] '{ticker}' : {len(results)} articles pertinents (keywords={keywords})")
    return results
