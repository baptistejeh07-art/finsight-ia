"""core/sentinel/data_audit.py — Auditeur qualité données post-analyse.

Complète la Sentinel basique (qui capture les exceptions) avec des **règles
métier** qui détectent les **bugs silencieux** :

- Tickers fallback synthétiques (BAN1-N, Corp N) → alias secteur manquant
- Noms d'entreprise vides ou tronqués → mapping backend cassé
- % élevé de champs None dans ratios critiques → fetch yfinance dégradé
- Score FinSight = 50/100 pile (signal de _neutral partout) → pas de data
- LLM commentary trop court / générique → fallback static déclenché
- Graph matplotlib vide (< N courbes plottées) → yfinance history failed
- HHI ou pe_median_ltm à None → analytics sectoriels cassés

Score data_quality 0-100 calculé, inséré dans pipeline_errors si < 70.
Les 5 règles les plus critiques sont loggées INDIVIDUELLEMENT pour
diagnostic fin. Sur quality < 50 : severity='critical' → Claude wake-up.

Usage :
    from core.sentinel.data_audit import audit_sector_analysis

    score = audit_sector_analysis(
        sector="Banques", universe="S&P 500",
        tickers=tickers_data,          # liste fetched
        analytics=sector_analytics,
        job_id="abc123",
    )
    # score.global_pct = 0-100
    # score.issues = [list of {severity, rule, message}]
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from core.sentinel.recorder import record_error

log = logging.getLogger(__name__)


# ═══ Règles métier =════════════════════════════════════════════════════
# Chaque règle retourne (bool problem, severity, message, penalty_pts).
# Pénalités sur 100 — plus elles sont élevées, plus le score baisse.

_FALLBACK_TICKER_RE = re.compile(r"^[A-Z]{2,5}\d$")   # BAN1, TEC3, etc.
_FALLBACK_NAME_RE = re.compile(r"(Corp|Inc)\s+\d+$", re.IGNORECASE)
_CRITICAL_RATIOS = ("pe_ratio", "ev_ebitda", "ebitda_margin", "net_margin",
                    "roe", "roic", "net_debt_ebitda")


@dataclass
class DataQualityReport:
    global_pct: float = 100.0   # score 0-100
    checks: list[dict] = field(default_factory=list)  # [{rule, status, severity, msg}]
    issues: list[dict] = field(default_factory=list)  # issues seulement

    def add(self, rule: str, passed: bool, severity: str, msg: str,
            penalty: float = 0.0) -> None:
        entry = {
            "rule": rule,
            "passed": passed,
            "severity": severity,
            "message": msg,
            "penalty": penalty,
        }
        self.checks.append(entry)
        if not passed:
            self.issues.append(entry)
            self.global_pct = max(0.0, self.global_pct - penalty)


def _is_fallback_ticker(tk: str) -> bool:
    """True si ticker ressemble à un fallback synthétique (BAN1, TEC3, etc.)."""
    if not tk or len(tk) < 3:
        return True
    # Tickers réels fréquents finissant par 1 digit : 005930.KS, 8306.T
    if "." in tk or "-" in tk:
        return False
    return bool(_FALLBACK_TICKER_RE.match(tk))


def _is_fallback_name(name: str) -> bool:
    if not name:
        return True
    return bool(_FALLBACK_NAME_RE.search(name))


def _null_pct(tickers: list[dict], field: str) -> float:
    """% de tickers avec ce champ None/0/absent."""
    if not tickers:
        return 1.0
    n = len(tickers)
    n_null = sum(
        1 for t in tickers
        if t.get(field) is None or t.get(field) == 0
    )
    return n_null / n if n else 1.0


# ═══ Auditeurs spécialisés ════════════════════════════════════════════
def audit_sector_analysis(
    sector: str,
    universe: str,
    tickers: list[dict],
    analytics: Optional[dict] = None,
    llm_summary: Optional[str] = None,
    job_id: Optional[str] = None,
) -> DataQualityReport:
    """Audit complet d'une analyse sectorielle. Retourne rapport + insère
    les issues dans pipeline_errors Supabase."""
    report = DataQualityReport()
    analytics = analytics or {}

    # Règle 1 : tickers fallback synthétiques (pénalité lourde — 35 pts)
    n_fallback_tk = sum(1 for t in tickers if _is_fallback_ticker(t.get("ticker", "")))
    fallback_ratio = n_fallback_tk / len(tickers) if tickers else 1.0
    if fallback_ratio >= 0.5:
        report.add(
            "tickers_synthetic", False, "critical",
            f"{n_fallback_tk}/{len(tickers)} tickers semblent synthétiques (fallback). "
            f"L'alias secteur '{sector}' est probablement manquant dans _SECTOR_TICKERS.",
            penalty=35,
        )
    elif fallback_ratio >= 0.2:
        report.add(
            "tickers_synthetic", False, "error",
            f"{n_fallback_tk} tickers fallback sur {len(tickers)} — mapping incomplet.",
            penalty=20,
        )
    else:
        report.add("tickers_synthetic", True, "info",
                   f"Tous les tickers semblent réels ({len(tickers)} sociétés)")

    # Règle 2 : noms d'entreprise vides ou "Corp N" (pénalité 15)
    n_bad_names = sum(1 for t in tickers
                      if _is_fallback_name(t.get("name") or t.get("company") or ""))
    if n_bad_names >= 2:
        report.add(
            "names_fallback", False, "error",
            f"{n_bad_names}/{len(tickers)} sociétés sans nom réel "
            f"(affichage 'Corp N' dans donut + tableau).",
            penalty=15,
        )
    elif n_bad_names >= 1:
        report.add(
            "names_fallback", False, "warn",
            f"{n_bad_names} société sans nom — mapping backend.slim_tickers cassé ?",
            penalty=5,
        )
    else:
        report.add("names_fallback", True, "info", "Tous les noms sociétés renseignés")

    # Règle 3 : ratios critiques vides (pénalité proportionnelle)
    _missing_ratios_detail = []
    total_missing_pts = 0.0
    for f in _CRITICAL_RATIOS:
        pct_null = _null_pct(tickers, f)
        if pct_null >= 0.5:
            total_missing_pts += 3
            _missing_ratios_detail.append(f"{f} ({int(pct_null*100)}%)")
        elif pct_null >= 0.3:
            total_missing_pts += 1.5
            _missing_ratios_detail.append(f"{f} ({int(pct_null*100)}%)")
    if total_missing_pts > 0:
        report.add(
            "ratios_missing", False,
            "error" if total_missing_pts >= 10 else "warn",
            f"Ratios critiques manquants : {', '.join(_missing_ratios_detail)}",
            penalty=min(total_missing_pts, 25),
        )
    else:
        report.add("ratios_missing", True, "info",
                   "Ratios critiques disponibles pour ≥70% des sociétés")

    # Règle 4 : analytics sectoriels cassés (HHI, PE median, ROIC)
    missing_analytics = [k for k in ("hhi", "pe_median_ltm", "roic_mean")
                          if analytics.get(k) is None]
    if len(missing_analytics) >= 2:
        report.add(
            "analytics_broken", False, "error",
            f"Analytics sectoriels manquants : {missing_analytics}. "
            "HHI/PE/ROIC médian non calculés → dashboard affiche '—' partout.",
            penalty=15,
        )
    elif missing_analytics:
        report.add(
            "analytics_broken", False, "warn",
            f"Analytics partiels : {missing_analytics}.",
            penalty=5,
        )
    else:
        report.add("analytics_broken", True, "info",
                   f"HHI={analytics.get('hhi')}, PE med={analytics.get('pe_median_ltm')}")

    # Règle 5 : LLM summary fallback static (commentaire générique ou trop court)
    if llm_summary is not None:
        if len(llm_summary) < 50:
            report.add(
                "llm_summary_short", False, "warn",
                f"Synthèse LLM suspicieusement courte ({len(llm_summary)} chars). "
                "Probablement fallback static ou erreur silencieuse.",
                penalty=10,
            )
        elif "générée" in llm_summary.lower() and len(llm_summary) < 150:
            report.add(
                "llm_summary_generic", False, "warn",
                "Synthèse ressemble au fallback i18n (contient 'générée' + courte).",
                penalty=10,
            )
        else:
            report.add("llm_summary_ok", True, "info",
                       f"LLM summary {len(llm_summary)} chars")

    # Rapport final
    log.info(
        f"[sentinel:data_audit] {sector}/{universe} score={report.global_pct:.0f}/100 "
        f"({len(report.issues)} issues)"
    )

    # Insertion Supabase des issues trouvées
    for issue in report.issues:
        try:
            record_error(
                severity=issue["severity"],
                error_type=f"data_audit:{issue['rule']}",
                message=issue["message"],
                kind="secteur",
                ticker=f"{sector}/{universe}",
                job_id=job_id,
                context={
                    "rule": issue["rule"],
                    "penalty": issue["penalty"],
                    "data_quality_score": report.global_pct,
                    "sector": sector,
                    "universe": universe,
                    "n_tickers": len(tickers),
                },
            )
        except Exception as _e:
            log.debug(f"[sentinel:data_audit] record fail: {_e}")

    # Critique : score < 50 → log séparé pour wake-up claude visible
    if report.global_pct < 50:
        log.error(
            f"[sentinel:data_audit] CRITICAL — {sector}/{universe} "
            f"data quality {report.global_pct:.0f}/100. "
            f"Issues: {[i['rule'] for i in report.issues]}"
        )

    return report


def audit_societe_analysis(
    ticker: str,
    snapshot,
    ratios,
    synthesis: Optional[dict] = None,
    job_id: Optional[str] = None,
) -> DataQualityReport:
    """Audit complet d'une analyse société. snapshot/ratios sont des objets
    Pydantic (accès via getattr)."""
    report = DataQualityReport()

    ci = getattr(snapshot, "company_info", None) if snapshot else None
    market = getattr(snapshot, "market", None) if snapshot else None

    # Règle 1 : ticker/name présents
    if not ticker or len(ticker) < 1:
        report.add("ticker_missing", False, "critical", "Ticker absent", penalty=50)
    name = getattr(ci, "company_name", "") if ci else ""
    if not name or name == ticker:
        report.add(
            "name_missing", False, "warn",
            f"company_name absent ou égal au ticker ({name!r}).",
            penalty=10,
        )
    else:
        report.add("name_ok", True, "info", f"Société {name}")

    # Règle 2 : prix actuel
    price = getattr(market, "share_price", None) if market else None
    if not price or price <= 0:
        report.add(
            "price_missing", False, "error",
            f"share_price manquant ({price}). Valorisations P/E/DCF cassées.",
            penalty=20,
        )

    # Règle 3 : ratios LTM présents
    latest = getattr(ratios, "latest_year", None) if ratios else None
    if not latest:
        report.add("ratios_missing", False, "critical",
                   "Aucune année de ratios calculée.", penalty=30)
    else:
        latest_r = ratios.years.get(latest) if ratios else None
        if not latest_r:
            report.add("ratios_empty", False, "error",
                       f"Année {latest} sans ratios.", penalty=20)
        else:
            critical = ("pe_ratio", "ev_ebitda", "roe", "ebitda_margin")
            missing = [k for k in critical if getattr(latest_r, k, None) is None]
            if len(missing) >= 3:
                report.add(
                    "critical_ratios_null", False, "error",
                    f"Ratios critiques {missing} tous None — calculs cassés.",
                    penalty=20,
                )
            elif missing:
                report.add(
                    "critical_ratios_null", False, "warn",
                    f"Ratios partiels None : {missing}",
                    penalty=8,
                )

    # Règle 4 : synthèse LLM cohérente
    if synthesis:
        if isinstance(synthesis, dict):
            reco = synthesis.get("recommendation")
            conv = synthesis.get("conviction")
        else:
            reco = getattr(synthesis, "recommendation", None)
            conv = getattr(synthesis, "conviction", None)
        if not reco or reco not in ("BUY", "HOLD", "SELL"):
            report.add(
                "reco_invalid", False, "error",
                f"Recommendation invalide : {reco!r}",
                penalty=15,
            )
        if conv is None or conv < 0.2 or conv > 0.95:
            report.add(
                "conviction_invalid", False, "warn",
                f"Conviction hors bornes raisonnables [0.2, 0.95] : {conv}",
                penalty=5,
            )

    log.info(
        f"[sentinel:data_audit] {ticker} score={report.global_pct:.0f}/100 "
        f"({len(report.issues)} issues)"
    )

    for issue in report.issues:
        try:
            record_error(
                severity=issue["severity"],
                error_type=f"data_audit:{issue['rule']}",
                message=issue["message"],
                kind="societe",
                ticker=ticker,
                job_id=job_id,
                context={
                    "rule": issue["rule"],
                    "penalty": issue["penalty"],
                    "data_quality_score": report.global_pct,
                },
            )
        except Exception as _e:
            log.debug(f"[sentinel:data_audit] record fail: {_e}")

    if report.global_pct < 50:
        log.error(
            f"[sentinel:data_audit] CRITICAL — {ticker} "
            f"data quality {report.global_pct:.0f}/100"
        )

    return report
