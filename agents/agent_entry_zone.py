# =============================================================================
# FinSight IA — Agent Zone d'Entrée Optimale
# agents/agent_entry_zone.py
#
# Formalise mathématiquement les conditions d'achat optimales.
# Conditions (toutes satisfaites = signal d'entrée) :
#   (1) Cours actuel < DCF Base × 0.90   (marge de sécurité 10%)
#   (2) Momentum négatif court terme      (cours < MM50 = 50 jours ouvrés)
#   (3) Altman Z-Score > 2.99             (zone financièrement saine)
#   (4) Sentiment FinBERT > -0.1          (pas de panique)
#   (5) Sloan Accruals Ratio < 5%         (qualité bénéfices acceptable)
#
# Backtest : vérifie sur 5 ans yfinance le % de cas où toutes les
# conditions de prix (1 & 2) étaient réunies ET le rendement +12M était positif.
# Conditions 3/4/5 appliquées comme filtre binaire sur valeurs actuelles.
# Affiche "Backtest insuffisant (N < 5)" si trop peu d'occurrences.
# =============================================================================

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional
from core.yfinance_cache import get_ticker

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses résultat
# ---------------------------------------------------------------------------

@dataclass
class EntryCondition:
    code:      str
    label:     str
    satisfied: bool
    value_str: str    # valeur observée formatée
    threshold: str    # seuil à franchir


@dataclass
class EntryZoneResult:
    ticker:             str
    conditions:         list = field(default_factory=list)  # List[EntryCondition]
    satisfied_count:    int  = 0
    all_satisfied:      bool = False
    backtest_n:         int  = 0
    backtest_pct_pos:   Optional[float] = None   # [0,1]
    backtest_label:     str  = ""
    mm50:               Optional[float] = None
    current_price:      Optional[float] = None
    dcf_proxy:          Optional[float] = None
    latency_ms:         int  = 0

    def to_dict(self) -> dict:
        return {
            "ticker":          self.ticker,
            "satisfied_count": self.satisfied_count,
            "all_satisfied":   self.all_satisfied,
            "backtest_n":      self.backtest_n,
            "backtest_pct_pos": self.backtest_pct_pos,
            "backtest_label":  self.backtest_label,
            "mm50":            self.mm50,
            "current_price":   self.current_price,
            "dcf_proxy":       self.dcf_proxy,
            "conditions": [
                {
                    "code":      c.code,
                    "label":     c.label,
                    "satisfied": c.satisfied,
                    "value":     c.value_str,
                    "threshold": c.threshold,
                }
                for c in self.conditions
            ],
        }


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class AgentEntryZone:
    """
    Calcule les 5 conditions d'entrée optimale et le backtest 5 ans.
    Aucun LLM. Python + yfinance.
    """

    def compute(
        self,
        snapshot,
        ratios,
        synthesis,
        qa_python,
        sentiment=None,
    ) -> EntryZoneResult:
        t0 = time.time()
        ticker = snapshot.ticker
        log.info(f"[AgentEntryZone] '{ticker}' — calcul zone d'entree")

        conditions: list[EntryCondition] = []

        mkt         = snapshot.market
        price       = mkt.share_price
        latest      = ratios.latest_year
        yr          = ratios.years.get(latest)

        # --- DCF proxy : synthesis.target_base si disponible (avant MC) ---
        dcf_proxy: Optional[float] = None
        if synthesis and synthesis.target_base and synthesis.target_base > 0:
            dcf_proxy = float(synthesis.target_base)
        # Chantier 1 override : si MC disponible dans ratios.meta
        mc_p50 = ratios.meta.get("dcf_mc_p50") if ratios.meta else None
        if mc_p50 and mc_p50 > 0:
            dcf_proxy = float(mc_p50)

        # --- MM50 (50 jours ouvrés) ---
        mm50 = self._compute_mm50(ticker)

        # --- Sloan Accruals depuis qa_python.meta ---
        sloan_ratio: Optional[float] = None
        if qa_python and hasattr(qa_python, "meta"):
            sloan_ratio = qa_python.meta.get("sloan_ratio")

        # --- Sentiment FinBERT ---
        sentiment_score: Optional[float] = None
        if sentiment is not None:
            sentiment_score = getattr(sentiment, "score", None)

        # --- Altman Z ---
        altman_z: Optional[float] = yr.altman_z if yr else None

        # =================================================================
        # Condition 1 — Cours < DCF × 0.90
        # =================================================================
        if price and dcf_proxy:
            seuil = dcf_proxy * 0.90
            sat   = price < seuil
            conditions.append(EntryCondition(
                code      = "MARGIN_OF_SAFETY",
                label     = "Marge de securite 10%",
                satisfied = sat,
                value_str = f"Cours={price:.2f} / DCF={dcf_proxy:.2f}",
                threshold = f"Cours < DCF x 0.90 ({seuil:.2f})",
            ))
        else:
            conditions.append(EntryCondition(
                code="MARGIN_OF_SAFETY", label="Marge de securite 10%",
                satisfied=False, value_str="N/A", threshold="Cours < DCF x 0.90",
            ))

        # =================================================================
        # Condition 2 — Cours < MM50
        # =================================================================
        if price and mm50:
            sat = price < mm50
            conditions.append(EntryCondition(
                code      = "MOMENTUM_NEGATIF",
                label     = "Momentum negatif (cours < MM50)",
                satisfied = sat,
                value_str = f"Cours={price:.2f} / MM50={mm50:.2f}",
                threshold = f"Cours < MM50 ({mm50:.2f})",
            ))
        else:
            conditions.append(EntryCondition(
                code="MOMENTUM_NEGATIF", label="Momentum negatif (cours < MM50)",
                satisfied=False, value_str="N/A", threshold="Cours < MM50",
            ))

        # =================================================================
        # Condition 3 — Altman Z > 2.99
        # =================================================================
        if altman_z is not None:
            sat = altman_z > 2.99
            conditions.append(EntryCondition(
                code      = "ALTMAN_SAFE",
                label     = "Sante financiere (Altman Z > 2.99)",
                satisfied = sat,
                value_str = f"Z={altman_z:.2f}",
                threshold = "Z > 2.99",
            ))
        else:
            conditions.append(EntryCondition(
                code="ALTMAN_SAFE", label="Sante financiere (Altman Z > 2.99)",
                satisfied=False, value_str="N/A", threshold="Z > 2.99",
            ))

        # =================================================================
        # Condition 4 — Sentiment FinBERT > -0.1
        # =================================================================
        if sentiment_score is not None:
            sat = sentiment_score > -0.1
            conditions.append(EntryCondition(
                code      = "SENTIMENT_OK",
                label     = "Sentiment FinBERT > -0.1",
                satisfied = sat,
                value_str = f"Score={sentiment_score:.3f}",
                threshold = "Score > -0.1",
            ))
        else:
            conditions.append(EntryCondition(
                code="SENTIMENT_OK", label="Sentiment FinBERT > -0.1",
                satisfied=True,   # bénéfice du doute si non disponible
                value_str="N/A", threshold="Score > -0.1",
            ))

        # =================================================================
        # Condition 5 — Sloan Accruals < 5%
        # =================================================================
        if sloan_ratio is not None:
            sat = abs(sloan_ratio) < 0.05
            conditions.append(EntryCondition(
                code      = "SLOAN_OK",
                label     = "Qualite benefices (Sloan < 5%)",
                satisfied = sat,
                value_str = f"Sloan={sloan_ratio:.1%}",
                threshold = "|Sloan| < 5%",
            ))
        else:
            conditions.append(EntryCondition(
                code="SLOAN_OK", label="Qualite benefices (Sloan < 5%)",
                satisfied=True,   # bénéfice du doute si non calculable
                value_str="N/A", threshold="|Sloan| < 5%",
            ))

        # --- Résumé conditions ---
        sat_count   = sum(1 for c in conditions if c.satisfied)
        all_sat     = sat_count == len(conditions)

        # =================================================================
        # Backtest 5 ans (conditions de prix uniquement)
        # =================================================================
        bt = self._backtest(ticker, dcf_proxy, mm50, altman_z, sloan_ratio, sentiment_score)

        ms = int((time.time() - t0) * 1000)
        log.info(
            f"[AgentEntryZone] '{ticker}' — {sat_count}/{len(conditions)} conditions "
            f"all={all_sat} bt_n={bt['n']} ({ms}ms)"
        )

        return EntryZoneResult(
            ticker          = ticker,
            conditions      = conditions,
            satisfied_count = sat_count,
            all_satisfied   = all_sat,
            backtest_n      = bt["n"],
            backtest_pct_pos= bt.get("pct_pos"),
            backtest_label  = bt["label"],
            mm50            = mm50,
            current_price   = price,
            dcf_proxy       = dcf_proxy,
            latency_ms      = ms,
        )

    # ------------------------------------------------------------------
    # MM50 : moyenne mobile 50 jours ouvrés
    # ------------------------------------------------------------------

    def _compute_mm50(self, ticker: str) -> Optional[float]:
        try:
            import yfinance as yf
            hist = get_ticker(ticker).history(period="4mo", interval="1d")
            if hist.empty or len(hist) < 10:
                return None
            close = hist["Close"].dropna()
            if len(close) < 50:
                # Moins de 50 points : MM sur données disponibles
                return round(float(close.mean()), 4)
            mm50 = close.rolling(50).mean().iloc[-1]
            return round(float(mm50), 4) if mm50 else None
        except Exception as e:
            log.debug(f"[AgentEntryZone] MM50 erreur : {e}")
            return None

    # ------------------------------------------------------------------
    # Backtest 5 ans — conditions de prix (1 & 2) sur données mensuelles
    # Conditions 3/4/5 : filtre binaire basé sur valeurs actuelles.
    # ------------------------------------------------------------------

    def _backtest(
        self,
        ticker: str,
        dcf_proxy: Optional[float],
        mm50_current: Optional[float],
        altman_z: Optional[float],
        sloan_ratio: Optional[float],
        sentiment_score: Optional[float],
    ) -> dict:

        # --- Filtre binaire conditions fondamentales (actuelles) ---
        funda_ok = True
        if altman_z is not None and altman_z <= 2.99:
            funda_ok = False
        if sloan_ratio is not None and abs(sloan_ratio) >= 0.05:
            funda_ok = False
        if sentiment_score is not None and sentiment_score <= -0.1:
            funda_ok = False

        if not funda_ok:
            return {
                "n": 0,
                "pct_pos": None,
                "label": "Backtest non applicable — conditions fondamentales actuelles non satisfaites",
            }

        if not dcf_proxy or dcf_proxy <= 0:
            return {
                "n": 0,
                "pct_pos": None,
                "label": "Backtest insuffisant — DCF proxy indisponible",
            }

        try:
            import yfinance as yf
            import numpy as np

            # Données mensuelles 5 ans (pour le backtest des rendements)
            hist = get_ticker(ticker).history(period="5y", interval="1mo")
            if hist.empty or len(hist) < 13:
                return {"n": 0, "pct_pos": None,
                        "label": "Backtest insuffisant (N < 5 occurrences)"}

            close = hist["Close"].dropna().values
            n_months = len(close)

            # MM50 proxy mensuel : rolling 3 mois (≈ 60 jours ouvrés) sur données mensuel
            # Note : en données mensuelles, MM50j ≈ MM3 mois. Approximation défendable.
            mm_roll = np.convolve(close, np.ones(3) / 3, mode="valid")
            # Aligner : mm_roll[i] correspond à close[i+2]
            offset = 2

            occurrences = 0
            positives   = 0

            for i in range(offset, n_months - 12):
                p = close[i]
                mm_est = mm_roll[i - offset]

                # Condition 1 : cours < DCF × 0.90
                cond1 = p < dcf_proxy * 0.90
                # Condition 2 : cours < MM50 proxy
                cond2 = p < mm_est

                if cond1 and cond2:
                    occurrences += 1
                    fwd_ret = close[i + 12] / p - 1
                    if fwd_ret > 0:
                        positives += 1

            if occurrences < 5:
                return {
                    "n": occurrences,
                    "pct_pos": None,
                    "label": f"Backtest insuffisant (N < 5 occurrences — N={occurrences})",
                }

            pct = round(positives / occurrences, 3)
            return {
                "n": occurrences,
                "pct_pos": pct,
                "label": (
                    f"Backtest 5 ans : {occurrences} occurrences — "
                    f"rendement +12M positif dans {pct:.0%} des cas"
                ),
            }

        except Exception as e:
            log.debug(f"[AgentEntryZone] backtest erreur : {e}")
            return {"n": 0, "pct_pos": None,
                    "label": "Backtest non disponible (erreur donnees)"}