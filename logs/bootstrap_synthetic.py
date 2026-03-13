# =============================================================================
# FinSight IA — Bootstrap 100 requetes synthetiques
# logs/bootstrap_synthetic.py
#
# Genere 100 logs V2 realistes sans appeler les APIs.
# Objectif : alimenter la chaine de Markov de l'Agent RH (Phase 7).
#
# Distributions calibrees sur les analyses reelles observees :
#   AgentData      : 2 000 - 6 000 ms
#   AgentSentiment : 300  - 1 500 ms
#   AgentQuant     : 50   - 200  ms
#   AgentSynthese  : 3 000- 8 000 ms  (LLM)
#   AgentQAPython  : 50   - 150  ms
#   AgentQAHaiku   : 2 000- 5 000 ms  (LLM)
#   AgentDevil     : 2 000- 6 000 ms  (LLM)
#
# Usage : python -m logs.bootstrap_synthetic
#         ou  : python logs/bootstrap_synthetic.py
# =============================================================================

from __future__ import annotations

import logging
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Ajout racine projet au path si execute directement
sys.path.insert(0, str(Path(__file__).parent.parent))

from logs.db_logger    import log_pipeline_v2
from logs.request_log  import AgentEntry, RequestLog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Univers de tickers — US + EU, secteurs varies
# ---------------------------------------------------------------------------

TICKERS = {
    # Technology
    "Technology": [
        "AAPL", "MSFT", "NVDA", "GOOG", "META", "ASML.AS", "SAP.DE",
        "STM.PA", "CAP.PA", "DASSAULT.PA",
    ],
    # Healthcare
    "Healthcare": [
        "JNJ", "UNH", "LLY", "PFE", "ABBV", "SAN.PA", "AIR.PA",
        "NOVO-B.CO", "ROG.SW", "NOVN.SW",
    ],
    # Financials
    "Financials": [
        "JPM", "BAC", "GS", "BNP.PA", "ACA.PA", "DBK.DE",
        "CS.SW", "ISP.MI", "HSBA.L", "LLOY.L",
    ],
    # Consumer
    "Consumer": [
        "AMZN", "TSLA", "NKE", "MCD", "MC.PA", "OR.PA",
        "KER.PA", "RI.PA", "CDI.PA", "BON.PA",
    ],
    # Energy
    "Energy": [
        "XOM", "CVX", "TTE.PA", "BP.L", "SHEL.L",
        "ENI.MI", "REP.MC", "ENGI.PA", "EDF.PA",
    ],
    # Industrials
    "Industrials": [
        "CAT", "HON", "GE", "AIR.PA", "DG.PA",
        "AF.PA", "MTX.DE", "SIE.DE", "ABB.ST",
    ],
    # Telecom
    "Telecom": [
        "VZ", "T", "ORA.PA", "DTE.DE", "TEF.MC",
        "TELIA.ST", "TIT.MI", "BT-A.L",
    ],
    # Real Estate
    "Real Estate": [
        "AMT", "PLD", "UNIBAIL.AS", "URW.AS", "CLT.PA",
    ],
}

# Aplatir en liste (ticker, sector)
_ALL_TICKERS: list[tuple[str, str]] = [
    (t, s) for s, tickers in TICKERS.items() for t in tickers
]

# ---------------------------------------------------------------------------
# Contextes de marche
# ---------------------------------------------------------------------------

MARKET_CONTEXTS = ["bull", "bear", "lateral"]

_CONTEXT_PARAMS = {
    "bull": {
        "price_factor":  (1.05, 1.40),   # cours en hausse
        "beta_range":    (0.8, 1.8),
        "rf_range":      (0.03, 0.05),
        "wacc_range":    (0.07, 0.10),
        "rec_weights":   {"BUY": 0.60, "HOLD": 0.30, "SELL": 0.10},
        "conf_range":    (0.70, 0.95),
    },
    "bear": {
        "price_factor":  (0.60, 0.95),
        "beta_range":    (1.0, 2.2),
        "rf_range":      (0.04, 0.06),
        "wacc_range":    (0.09, 0.14),
        "rec_weights":   {"BUY": 0.10, "HOLD": 0.35, "SELL": 0.55},
        "conf_range":    (0.55, 0.85),
    },
    "lateral": {
        "price_factor":  (0.95, 1.05),
        "beta_range":    (0.7, 1.3),
        "rf_range":      (0.035, 0.05),
        "wacc_range":    (0.07, 0.11),
        "rec_weights":   {"BUY": 0.30, "HOLD": 0.50, "SELL": 0.20},
        "conf_range":    (0.60, 0.85),
    },
}

# ---------------------------------------------------------------------------
# Helpers de generation
# ---------------------------------------------------------------------------

def _ri(lo: int, hi: int) -> int:
    return random.randint(lo, hi)


def _rf(lo: float, hi: float, dp: int = 4) -> float:
    return round(random.uniform(lo, hi), dp)


def _choice_weighted(weights: dict) -> str:
    keys   = list(weights.keys())
    probs  = list(weights.values())
    return random.choices(keys, weights=probs, k=1)[0]


def _random_timestamp(days_back: int = 90) -> str:
    """Timestamp aleatoire dans les N derniers jours."""
    delta = timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(8, 18),
        minutes=random.randint(0, 59),
    )
    return (datetime.utcnow() - delta).isoformat()


# ---------------------------------------------------------------------------
# Generateur d'un log synthetique
# ---------------------------------------------------------------------------

def _generate_agent_entry(
    name: str,
    lat_lo: int,
    lat_hi: int,
    status_weights: dict | None = None,
    tokens: int = 0,
    extra_fn=None,
) -> AgentEntry:
    if status_weights is None:
        status_weights = {"ok": 0.92, "error": 0.05, "skip": 0.03}
    status  = _choice_weighted(status_weights)
    latency = _ri(lat_lo, lat_hi) if status != "error" else _ri(50, 300)
    extra   = extra_fn() if extra_fn and status == "ok" else {}
    return AgentEntry(
        agent=name,
        status=status,
        latency_ms=latency,
        tokens_used=tokens if status == "ok" else 0,
        extra=extra,
    )


def generate_synthetic_request(idx: int) -> RequestLog:
    """Genere un RequestLog synthetique complet."""
    ticker, sector = random.choice(_ALL_TICKERS)
    context        = random.choice(MARKET_CONTEXTS)
    p              = _CONTEXT_PARAMS[context]

    # Cours de reference fictif selon secteur
    base_prices = {
        "Technology": 200, "Healthcare": 150, "Financials": 80,
        "Consumer": 120, "Energy": 60, "Industrials": 100,
        "Telecom": 20, "Real Estate": 90,
    }
    base   = base_prices.get(sector, 100)
    factor = _rf(*p["price_factor"])
    price  = round(base * factor, 2)

    beta  = _rf(*p["beta_range"])
    rf    = _rf(*p["rf_range"])
    wacc  = _rf(*p["wacc_range"])
    rec   = _choice_weighted(p["rec_weights"])
    conf  = _rf(*p["conf_range"])
    conv  = _rf(0.40, 0.85) if rec in ("BUY", "SELL") else _rf(0.30, 0.60)

    # Annees disponibles (3 ou 4 selon disponibilite simulee)
    n_years  = random.choices([3, 4, 5], weights=[0.10, 0.60, 0.30])[0]
    base_yr  = 2025
    years    = [str(base_yr - (n_years - 1 - i)) for i in range(n_years)]

    # Timestamp aleatoire dans les 90 derniers jours
    ts = _random_timestamp(days_back=90)

    req = RequestLog(
        ticker=ticker,
        request_id=str(uuid.uuid4()),
        timestamp=ts,
    )

    # --- AgentData ---
    req.add(AgentEntry(
        agent="AgentData",
        status=_choice_weighted({"ok": 0.94, "error": 0.06}),
        latency_ms=_ri(1800, 6200),
        extra={
            "source":          random.choices(["yfinance", "fmp"], weights=[0.90, 0.10])[0],
            "confidence":      _rf(0.75, 0.95),
            "years_available": n_years,
            "market_context":  context,
        },
    ))

    # --- AgentSentiment ---
    n_articles = _ri(0, 15)
    req.add(AgentEntry(
        agent="AgentSentiment",
        status=_choice_weighted({"ok": 0.88, "skip": 0.10, "error": 0.02}),
        latency_ms=_ri(280, 1600),
        extra={
            "articles": n_articles,
            "score":    _rf(-0.3, 0.6) if n_articles > 0 else None,
        },
    ))

    # --- AgentQuant ---
    req.add(AgentEntry(
        agent="AgentQuant",
        status="ok",
        latency_ms=_ri(40, 220),
        extra={"ratios_count": random.choices([28, 30, 33], weights=[0.15, 0.25, 0.60])[0]},
    ))

    # --- AgentSynthese (LLM) ---
    tok_synth = _ri(1200, 2800)
    req.add(AgentEntry(
        agent="AgentSynthese",
        status=_choice_weighted({"ok": 0.96, "error": 0.04}),
        latency_ms=_ri(2800, 8500),
        tokens_used=tok_synth,
        extra={"recommendation": rec, "conviction": conv},
    ))

    # --- AgentQAPython ---
    n_warnings = random.choices([0, 1, 2, 3], weights=[0.40, 0.35, 0.18, 0.07])[0]
    req.add(AgentEntry(
        agent="AgentQAPython",
        status="ok",
        latency_ms=_ri(45, 160),
        extra={"warnings": n_warnings},
    ))

    # --- AgentQAHaiku (LLM, parallele avec AgentDevil) ---
    tok_qah = _ri(600, 1400)
    req.add(AgentEntry(
        agent="AgentQAHaiku",
        status=_choice_weighted({"ok": 0.95, "error": 0.05}),
        latency_ms=_ri(1800, 5200),
        tokens_used=tok_qah,
        extra={"readability": _rf(0.55, 0.95)},
    ))

    # --- AgentDevil (LLM, parallele avec AgentQAHaiku) ---
    tok_dev = _ri(800, 1800)
    req.add(AgentEntry(
        agent="AgentDevil",
        status=_choice_weighted({"ok": 0.95, "error": 0.05}),
        latency_ms=_ri(1800, 6000),
        tokens_used=tok_dev,
        extra={"conviction_delta": _rf(-0.35, 0.05)},
    ))

    # Finalize
    total_ms = sum(a.latency_ms for a in req.agents)

    req.market_context = {
        "share_price":    price,
        "beta_levered":   beta,
        "risk_free_rate": rf,
        "wacc":           wacc,
        "market_context": context,
    }
    req.input_data = {
        "sector":          sector,
        "currency":        "EUR" if any(x in ticker for x in [".PA", ".DE", ".AS", ".SW", ".MI", ".L", ".MC", ".ST", ".CO"]) else "USD",
        "years_available": years,
        "base_year":       int(years[-1]) if years else 2025,
    }
    req.output = {
        "recommendation":          rec,
        "conviction":              conv,
        "confidence_score":        conf,
        "target_base":             round(price * _rf(0.95, 1.25), 2),
        "target_bull":             round(price * _rf(1.10, 1.50), 2),
        "target_bear":             round(price * _rf(0.65, 0.95), 2),
        "summary":                 f"[SYNTHETIC] Analyse {ticker} — contexte {context}. Recommandation {rec} avec conviction {conv:.0%}.",
        "invalidation_conditions": f"[SYNTHETIC] Invalidation si : changement secteur, restatement, ou volatilite > 40%.",
    }
    req.confidence_score        = conf
    req.recommendation          = rec
    req.conviction              = conv
    req.invalidation_conditions = req.output["invalidation_conditions"]
    req.total_latency_ms        = total_ms

    return req


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def run_bootstrap(n: int = 100) -> None:
    log.info(f"[Bootstrap] Debut generation {n} requetes synthetiques...")

    counts   = {"ok": 0, "error": 0}
    sectors  = {}
    contexts = {"bull": 0, "bear": 0, "lateral": 0}
    recs     = {"BUY": 0, "HOLD": 0, "SELL": 0}

    for i in range(1, n + 1):
        req = generate_synthetic_request(i)
        try:
            log_pipeline_v2(req)
            counts["ok"] += 1
            # Stats
            ctx = (req.market_context or {}).get("market_context", "?")
            if ctx in contexts:
                contexts[ctx] += 1
            sec = (req.input_data or {}).get("sector", "?")
            sectors[sec] = sectors.get(sec, 0) + 1
            rec = req.recommendation or "?"
            if rec in recs:
                recs[rec] += 1
        except Exception as e:
            log.error(f"[Bootstrap] Erreur requete {i} ({req.ticker}): {e}")
            counts["error"] += 1

        if i % 10 == 0:
            log.info(f"[Bootstrap] {i}/{n} generes...")

    log.info(f"\n[Bootstrap] Termine : {counts['ok']} OK / {counts['error']} erreurs")
    log.info(f"  Contextes : {contexts}")
    log.info(f"  Recs      : {recs}")
    log.info(f"  Secteurs  : {dict(sorted(sectors.items(), key=lambda x: -x[1]))}")
    log.info(f"  Fichiers  : logs/local/v2_*.json")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    run_bootstrap(n)
