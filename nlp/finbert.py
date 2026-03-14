# =============================================================================
# FinSight IA — FinBERT local
# nlp/finbert.py
#
# Modèle : ProsusAI/finbert — pré-entraîné sur 4.9B tokens finance
# Zéro coût API. Tourne en CPU (~1–3s pour 10 articles).
# Labels : positive | negative | neutral
#
# Principe Intel/Watt (brief §5) : FinBERT ≠ LLM — 0 token API consommé.
# =============================================================================

from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)

# Lazy init — chargé au premier appel (modèle ~440 MB, téléchargé une fois)
_pipeline = None
_vader    = None   # Fallback léger si torch/transformers absent (SCC free tier)


def _get_pipeline():
    """Retourne le pipeline FinBERT, ou None si torch indisponible."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    try:
        import warnings, os
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        offline = os.getenv("TRANSFORMERS_OFFLINE", "0")
        if offline == "1":
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
        warnings.filterwarnings("ignore", category=UserWarning)
        from transformers import pipeline as hf_pipeline
        import transformers
        transformers.logging.set_verbosity_error()
        log.info("[FinBERT] Chargement ProsusAI/finbert...")
        _pipeline = hf_pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            tokenizer="ProsusAI/finbert",
            device=-1,
            top_k=None,
        )
        log.info("[FinBERT] Modele charge.")
    except Exception as e:
        log.warning(f"[FinBERT] Indisponible ({e}) — fallback VADER actif")
        return None
    return _pipeline


def _get_vader():
    """Retourne le SentimentIntensityAnalyzer VADER (fallback léger, ~100KB)."""
    global _vader
    if _vader is not None:
        return _vader
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        _vader = SentimentIntensityAnalyzer()
        log.info("[Sentiment] VADER charge (fallback FinBERT).")
    except Exception as e:
        log.error(f"[Sentiment] VADER indisponible : {e}")
        return None
    return _vader


def _vader_scores(texts: list[str]) -> list[dict]:
    """Analyse via VADER — même interface que FinBERT."""
    vader = _get_vader()
    if vader is None:
        return []
    results = []
    for text in texts:
        s = vader.polarity_scores(text[:512])
        # VADER: neg/neu/pos/compound → convertir en format FinBERT
        results.append({
            "positive": round(s["pos"], 4),
            "negative": round(s["neg"], 4),
            "neutral":  round(s["neu"], 4),
        })
    return results


def analyze(texts: list[str], batch_size: int = 16, _use_vader: bool = False) -> list[dict]:
    """
    Analyse sentiment de N textes en batch via FinBERT.

    Args:
        texts:      liste de textes (headlines ou headline+summary tronqués)
        batch_size: taille des batchs pour inference

    Returns:
        list de dicts : [{"positive": 0.8, "negative": 0.1, "neutral": 0.1}, ...]
        Liste vide si erreur ou modèle indisponible.
    """
    clean = [t[:512] for t in texts if t and t.strip()]
    if not clean:
        return []

    # Essaie FinBERT en premier, sinon VADER
    pipe = _get_pipeline()
    if pipe is None:
        log.info(f"[Sentiment] Analyse {len(clean)} textes via VADER")
        return _vader_scores(clean)

    results: list[dict] = []
    try:
        log.info(f"[Sentiment] Analyse {len(clean)} textes via FinBERT")
        raw_outputs = pipe(clean, batch_size=batch_size, truncation=True, max_length=512)
        for item_scores in raw_outputs:
            scores = {s["label"].lower(): round(s["score"], 4) for s in item_scores}
            results.append({
                "positive": scores.get("positive", 0.0),
                "negative": scores.get("negative", 0.0),
                "neutral":  scores.get("neutral",  0.0),
            })
    except Exception as e:
        log.error(f"[FinBERT] Erreur inference : {e} — fallback VADER")
        results = _vader_scores(clean)

    return results


def aggregate(scores: list[dict]) -> dict:
    """
    Agrège N scores FinBERT en un score composite.

    score_composite = moyenne(positive − negative)  ∈ [-1, 1]
    score_normalized = (score + 1) / 2              ∈ [ 0, 1]

    Returns:
        {score, score_normalized, label, confidence, n, breakdown}
    """
    if not scores:
        return {
            "score": 0.0, "score_normalized": 0.5,
            "label": "NEUTRAL", "confidence": 0.0,
            "n": 0, "breakdown": {},
        }

    raw = [s["positive"] - s["negative"] for s in scores]
    avg_score = sum(raw) / len(raw)

    avg_pos = sum(s["positive"] for s in scores) / len(scores)
    avg_neg = sum(s["negative"] for s in scores) / len(scores)
    avg_neu = sum(s["neutral"]  for s in scores) / len(scores)

    if avg_pos >= avg_neg and avg_pos >= avg_neu:
        label, confidence = "POSITIVE", avg_pos
    elif avg_neg >= avg_pos and avg_neg >= avg_neu:
        label, confidence = "NEGATIVE", avg_neg
    else:
        label, confidence = "NEUTRAL", avg_neu

    return {
        "score":            round(avg_score, 4),
        "score_normalized": round((avg_score + 1) / 2, 4),
        "label":            label,
        "confidence":       round(confidence, 4),
        "n":                len(scores),
        "breakdown": {
            "avg_positive": round(avg_pos, 4),
            "avg_negative": round(avg_neg, 4),
            "avg_neutral":  round(avg_neu, 4),
        },
    }


def score_single(text: str) -> dict:
    """Analyse un seul texte. Utile pour debug et tests unitaires."""
    results = analyze([text])
    if not results:
        return {"positive": 0.0, "negative": 0.0, "neutral": 1.0}
    return results[0]
