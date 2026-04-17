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
from core.llm_provider import LLMProvider

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
    llm_commentary:     str  = ""   # commentaire généré par LLM (fallback langue)
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
        # 4b. LLM Groq — classification forcée + commentaire (tous tickers)
        #     FinBERT est English-only → articles FR/DE/ES mal classés.
        #     On passe TOUJOURS par le LLM pour classification + commentaire.
        # ------------------------------------------------------------------
        neu_ratio = sum(1 for s in raw_scores
                        if s["neutral"] >= s["positive"] and s["neutral"] >= s["negative"]
                        ) / len(raw_scores)

        llm_commentary = ""
        if len(texts) >= 1:
            raw_scores, engine_used, llm_commentary = self._llm_classify(
                ticker, texts, raw_scores, company_name
            )

        # ------------------------------------------------------------------
        # 5. Agrégation
        # ------------------------------------------------------------------
        agg = finbert.aggregate(raw_scores)

        # ------------------------------------------------------------------
        # 6. Samples — 1 représentatif par catégorie (POSITIVE / NEGATIVE / NEUTRAL)
        # ------------------------------------------------------------------
        _s_pos, _s_neg, _s_neu = [], [], []
        for article, score_dict in zip(all_news, raw_scores):
            raw_s = score_dict["positive"] - score_dict["negative"]
            lbl = "POSITIVE" if raw_s > 0.1 else "NEGATIVE" if raw_s < -0.1 else "NEUTRAL"
            entry = {
                "headline": article.get("headline", "")[:120],
                "source":   article.get("source", ""),
                "score":    round(raw_s, 4),
                "label":    lbl,
            }
            if lbl == "POSITIVE" and len(_s_pos) < 2:
                _s_pos.append(entry)
            elif lbl == "NEGATIVE" and len(_s_neg) < 2:
                _s_neg.append(entry)
            elif lbl == "NEUTRAL" and len(_s_neu) < 2:
                _s_neu.append(entry)
            if len(_s_pos) + len(_s_neg) + len(_s_neu) >= 6:
                break
        samples = _s_pos + _s_neg + _s_neu

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
            llm_commentary    = llm_commentary,
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
    # LLM classification fallback (articles non-anglais)
    # ------------------------------------------------------------------

    def _llm_classify(
        self,
        ticker: str,
        texts: list[str],
        fallback: list[dict],
        company_name: str = "",
    ) -> tuple[list[dict], str, str]:
        """
        Classification forcée via Groq + génération commentaire 2 phrases.
        Retourne (scores, engine_name, commentary).
        """
        ctx = f" ({company_name})" if company_name else ""
        headlines = "\n".join(f"{i+1}. {t[:150]}" for i, t in enumerate(texts[:20]))

        from core.prompt_standards import RULE_FRENCH_ACCENTS
        prompt = (
            f"TÂCHE 1 — CLASSIFICATION OBLIGATOIRE\n"
            f"Tu analyses l'actualité financière de l'action {ticker}{ctx}.\n"
            f"Pour chaque titre ci-dessous, tu DOIS décider : POSITIF, NÉGATIF ou NEUTRE.\n"
            f"Règles strictes :\n"
            f"- POSITIF : résultats solides, partenariat, croissance, note relevée, acquisition favorable\n"
            f"- NÉGATIF : déception résultats, litige, perte de marché, abaissement note, risque majeur\n"
            f"- NEUTRE : information vraiment sans impact clair sur le cours (MAX 25% des titres)\n"
            f"INTERDIT : mettre NEUTRE par défaut ou par flemme. Force-toi à trancher.\n"
            f"Format exact (une ligne par titre) : numero|POSITIF ou numero|NÉGATIF ou numero|NEUTRE\n\n"
            f"TÂCHE 2 — COMMENTAIRE (après la liste)\n"
            f"Écris 35-55 mots (2 phrases denses) en français qui résument le "
            f"sentiment global de la presse financière sur {ticker}{ctx} cette "
            f"semaine. Mentionne le ton dominant (euphorie, prudence, pessimisme) "
            f"et le thème récurrent (résultats, M&A, guidance, régulation).\n"
            f"Format : COMMENTAIRE: <tes 2 phrases ici>\n\n"
            f"Titres à analyser :\n{headlines}"
        )
        system = (
            "Tu es analyste financier senior sell-side sur la presse financière. "
            "Tu réponds d'abord avec la classification ligne par ligne (numero|label), "
            "puis avec le commentaire préfixé 'COMMENTAIRE:'. Pas d'explication "
            "supplémentaire, pas de markdown.\n"
            f"{RULE_FRENCH_ACCENTS}"
        )

        try:
            llm = LLMProvider(provider="mistral", model="mistral-small-latest")
            raw = llm.generate(prompt=prompt, system=system, max_tokens=700)
            if not raw:
                log.warning(f"[AgentSentiment] '{ticker}' LLM vide — fallback FinBERT")
                return fallback, "finbert", ""

            scores = list(fallback)
            commentary = ""

            for line in raw.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                # Commentaire
                low = line.lower()
                if low.startswith("commentaire:") or low.startswith("commentaire :"):
                    sep = line.find(":")
                    commentary = line[sep + 1:].strip()
                    continue
                # Classification
                if "|" not in line:
                    continue
                parts = line.split("|", 1)
                if len(parts) < 2:
                    continue
                try:
                    idx = int(parts[0].strip()) - 1
                    label = parts[1].strip().upper()
                    if 0 <= idx < len(scores):
                        if label == "POSITIF":
                            scores[idx] = {"positive": 0.80, "negative": 0.05, "neutral": 0.15}
                        elif label == "NEGATIF":
                            scores[idx] = {"positive": 0.05, "negative": 0.80, "neutral": 0.15}
                        else:
                            scores[idx] = {"positive": 0.15, "negative": 0.10, "neutral": 0.75}
                except (ValueError, IndexError):
                    continue

            pos_n = sum(1 for s in scores if s["positive"] > s["negative"] and s["positive"] > s["neutral"])
            neg_n = sum(1 for s in scores if s["negative"] > s["positive"] and s["negative"] > s["neutral"])
            log.info(
                f"[AgentSentiment] '{ticker}' LLM Groq OK — "
                f"pos={pos_n} neg={neg_n} commentary={len(commentary)}c"
            )
            return scores, "llm_groq", commentary

        except Exception as e:
            log.warning(f"[AgentSentiment] LLM classify echoue: {e}")
            return fallback, "finbert", ""

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
