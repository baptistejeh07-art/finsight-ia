# =============================================================================
# FinSight IA — Agent Sentiment
# agents/agent_sentiment.py
#
# FinBERT local — zéro coût API, zéro LLM.
# Sources : Finnhub (ticker-spécifique) + feedparser RSS (filtrées)
# Score agrégé sur N articles : [-1 négatif → +1 positif]
#
# Constitution §1 : confidence_score + invalidation_conditions obligatoires.
# =============================================================================

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional

from data.sources import finnhub_source
from data.sources.news_source import fetch_rss
from nlp import finbert

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bug 4 — Filtre de pertinence
# ---------------------------------------------------------------------------

def _filter_relevant(articles: list, ticker: str, company_name: str) -> list:
    """
    Garde uniquement les articles qui mentionnent le ticker ou le nom société.
    Evite la pollution (ex: MC.PA → Moelis & Co sur Finnhub).
    """
    # Mots-clés de pertinence : ticker brut, ticker sans suffixe, mots du nom société
    keys = set()
    keys.add(ticker.lower())
    base = ticker.split(".")[0].lower()
    if len(base) >= 3:
        keys.add(base)
    if company_name:
        for word in company_name.lower().split():
            if len(word) >= 4 and word not in {"inc.", "corp", "ltd.", "s.a.", "group", "plc", "the"}:
                keys.add(word.rstrip(".,"))

    if not keys:
        return articles

    filtered = []
    for art in articles:
        text = (art.get("headline", "") + " " + art.get("summary", "")).lower()
        if any(k in text for k in keys):
            filtered.append(art)
    return filtered


# ---------------------------------------------------------------------------
# Modèle de résultat
# ---------------------------------------------------------------------------

@dataclass
class SentimentResult:
    """
    Résultat Agent Sentiment pour un ticker.
    Constitution §1 : confidence_score + invalidation_conditions dans meta.
    """
    ticker:             str
    timestamp:          str
    score:              float   # [-1, 1] — négatif → positif
    score_normalized:   float   # [ 0, 1] — pour affichage UI
    label:              str     # "POSITIVE" | "NEGATIVE" | "NEUTRAL"
    confidence:         float   # probabilité du label dominant [0, 1]
    articles_analyzed:  int
    articles_total:     int
    breakdown:          dict    # avg_positive / avg_negative / avg_neutral
    sources:            list
    samples:            list    # 3 exemples avec score individuel
    meta:               dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class AgentSentiment:
    """
    Agent Sentiment — FinBERT local, zéro LLM, zéro coût API.

    Usage :
        agent = AgentSentiment()
        result = agent.analyze("AAPL")
        print(result.label, result.score)
    """

    def analyze(
        self,
        ticker: str,
        company_name: str = "",
        news_days: int = 7,
    ) -> SentimentResult:
        """
        Analyse le sentiment pour un ticker.

        Returns:
            SentimentResult (label NEUTRAL + confidence=0 si aucune news)
        """
        request_id = str(uuid.uuid4())
        t_start    = time.time()

        log.info(f"[AgentSentiment] Analyse '{ticker}' — {request_id[:8]}")

        # ------------------------------------------------------------------
        # 1. Collecte news : Finnhub (spécifique) + RSS (filtrée)
        # ------------------------------------------------------------------
        finnhub_news = finnhub_source.fetch_news(ticker, days=news_days)
        rss_news     = fetch_rss(ticker, company_name=company_name)

        # Bug 4 fix — filtre de pertinence sur les articles Finnhub
        # Pour les tickers avec suffixe (.PA, .L, etc.) ou ambigus, Finnhub peut
        # retourner des articles d'une autre société (ex: MC → Moelis & Co).
        # On filtre en vérifiant que l'article mentionne le ticker OU le nom société.
        if company_name or "." in ticker:
            finnhub_news = _filter_relevant(finnhub_news, ticker, company_name)
            log.info(
                f"[AgentSentiment] '{ticker}' — Finnhub apres filtrage pertinence : "
                f"{len(finnhub_news)} articles"
            )

        all_news   = finnhub_news + rss_news
        total_news = len(all_news)

        log.info(
            f"[AgentSentiment] '{ticker}' — "
            f"{len(finnhub_news)} Finnhub + {len(rss_news)} RSS = {total_news} articles"
        )

        # ------------------------------------------------------------------
        # 2. Cas aucune news
        # ------------------------------------------------------------------
        if total_news == 0:
            log.warning(f"[AgentSentiment] '{ticker}' : aucune news disponible")
            return self._empty_result(ticker, request_id, t_start)

        # ------------------------------------------------------------------
        # 3. Préparation textes : headline + summary (brief : "filtrer d'abord")
        # ------------------------------------------------------------------
        texts = [
            (n.get("headline", "") + " " + n.get("summary", "")).strip()
            for n in all_news
            if n.get("headline", "").strip()
        ]

        # ------------------------------------------------------------------
        # 4. Sentiment inference (FinBERT ou VADER fallback)
        # ------------------------------------------------------------------
        raw_scores, engine_used = finbert.analyze(texts)

        if not raw_scores:
            log.error(f"[AgentSentiment] FinBERT n'a retourné aucun score pour '{ticker}'")
            return self._empty_result(ticker, request_id, t_start)

        # ------------------------------------------------------------------
        # 5. Agrégation
        # ------------------------------------------------------------------
        agg = finbert.aggregate(raw_scores)

        # ------------------------------------------------------------------
        # 6. Samples — 3 articles représentatifs avec score individuel
        # ------------------------------------------------------------------
        samples = []
        for article, score_dict in list(zip(all_news, raw_scores))[:3]:
            raw_s = score_dict["positive"] - score_dict["negative"]
            samples.append({
                "headline": article.get("headline", "")[:120],
                "source":   article.get("source", ""),
                "score":    round(raw_s, 4),
                "label":    (
                    "POSITIVE" if raw_s > 0.1 else
                    "NEGATIVE" if raw_s < -0.1 else
                    "NEUTRAL"
                ),
            })

        # ------------------------------------------------------------------
        # 7. Métadonnées (constitution §1)
        # ------------------------------------------------------------------
        latency_ms  = int((time.time() - t_start) * 1000)
        sources_set = list({n.get("source", "unknown") for n in all_news})

        result = SentimentResult(
            ticker            = ticker.upper(),
            timestamp         = datetime.utcnow().isoformat(),
            score             = agg["score"],
            score_normalized  = agg["score_normalized"],
            label             = agg["label"],
            confidence        = agg["confidence"],
            articles_analyzed = len(raw_scores),
            articles_total    = total_news,
            breakdown         = agg.get("breakdown", {}),
            sources           = sources_set,
            samples           = samples,
            meta = {
                "request_id":   request_id,
                "latency_ms":   latency_ms,
                "confidence_score": agg["confidence"],
                "invalidation_conditions": (
                    "Score invalide si : "
                    "(1) moins de 3 articles analysés (bruit statistique), "
                    "(2) news > 7 jours (information périmée), "
                    "(3) ticker ambigu (mêmes lettres = autre société), "
                    "(4) événement exceptionnel concentre la publication (biais de volume)"
                ),
                "engine":       engine_used,   # "finbert" ou "vader"
                "tokens_used": 0,  # inference locale — zéro token API
            },
        )

        log.info(
            f"[AgentSentiment] '{ticker}' OK — "
            f"{agg['label']} score={agg['score']:+.3f} "
            f"conf={agg['confidence']:.0%} "
            f"({len(raw_scores)}/{total_news} articles, {latency_ms}ms)"
        )

        return result

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _empty_result(
        self, ticker: str, request_id: str, t_start: float
    ) -> SentimentResult:
        """Résultat neutre quand aucune news n'est disponible."""
        return SentimentResult(
            ticker            = ticker.upper(),
            timestamp         = datetime.utcnow().isoformat(),
            score             = 0.0,
            score_normalized  = 0.5,
            label             = "NEUTRAL",
            confidence        = 0.0,
            articles_analyzed = 0,
            articles_total    = 0,
            breakdown         = {},
            sources           = [],
            samples           = [],
            meta = {
                "request_id":   request_id,
                "latency_ms":   int((time.time() - t_start) * 1000),
                "confidence_score": 0.0,
                "invalidation_conditions": "Aucune news disponible pour cette période.",
                "tokens_used": 0,
            },
        )
