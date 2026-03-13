# =============================================================================
# FinSight IA — Agent RH
# agents/agent_rh.py
#
# Monitoring des agents via chaine de Markov sur les logs V2.
# 3 etats par agent : Repos / Charge normale / Surcharge
# Sources : logs/local/v2_*.json
#
# Usage :
#   python -m agents.agent_rh
#   ou : from agents.agent_rh import AgentRH; rapport = AgentRH().analyze()
# =============================================================================

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

log = logging.getLogger(__name__)

_LOGS_DIR = Path(__file__).parent.parent / "logs" / "local"

# ---------------------------------------------------------------------------
# Etats Markov
# ---------------------------------------------------------------------------

STATES      = ["Repos", "Normal", "Surcharge"]
STATE_REPOS = 0
STATE_NORM  = 1
STATE_SURCH = 2

# Seuils de latence (ms) par agent — calibres sur observations reelles
# (lo, hi) : Repos < lo, Normal [lo, hi], Surcharge > hi
LATENCY_THRESHOLDS: dict[str, tuple[int, int]] = {
    "AgentData":      (2_000, 5_000),
    "AgentSentiment": (400,   1_200),
    "AgentQuant":     (80,    150),
    "AgentSynthese":  (3_500, 6_500),
    "AgentQAPython":  (70,    120),
    "AgentQAHaiku":   (2_500, 4_000),
    "AgentDevil":     (2_500, 5_000),
}

# Seuil d'alerte surcharge (distribution stationnaire)
SURCHARGE_ALERT_THRESHOLD = 0.25   # > 25% du temps en surcharge = alerte
REPOS_ALERT_THRESHOLD     = 0.65   # > 65% du temps en repos = sous-utilise


# ---------------------------------------------------------------------------
# Dataclasses resultats
# ---------------------------------------------------------------------------

@dataclass
class AgentMarkov:
    """Resultats Markov pour un agent."""
    agent:          str
    n_observations: int

    # Matrice de transition 3x3 (lignes = etat actuel, cols = etat suivant)
    transition_matrix: list[list[float]] = field(default_factory=list)

    # Distribution stationnaire (long terme)
    stationary: list[float] = field(default_factory=list)   # [P_Repos, P_Normal, P_Surcharge]

    # Taux bruts observes
    rate_repos:   float = 0.0
    rate_normal:  float = 0.0
    rate_surcharge: float = 0.0

    # Latences
    latency_mean: float = 0.0
    latency_p95:  float = 0.0
    latency_max:  float = 0.0

    # Flags
    surcharge_alert:     bool = False
    sous_utilise:        bool = False
    error_rate:          float = 0.0


@dataclass
class RHReport:
    """Rapport complet Agent RH."""
    n_logs:       int
    n_agents:     int
    agents:       dict[str, AgentMarkov] = field(default_factory=dict)
    alerts:       list[str]              = field(default_factory=list)
    recommandations: list[str]           = field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent RH
# ---------------------------------------------------------------------------

class AgentRH:
    """
    Lit les logs V2, construit les chaines de Markov par agent,
    calcule la distribution stationnaire, et produit un rapport.
    """

    def analyze(self, logs_dir: Optional[Path] = None) -> RHReport:
        logs_dir = logs_dir or _LOGS_DIR

        # 1. Charger les logs V2
        records = self._load_logs(logs_dir)
        log.info(f"[AgentRH] {len(records)} logs V2 charges")

        if not records:
            log.warning("[AgentRH] Aucun log V2 trouve dans %s", logs_dir)
            return RHReport(n_logs=0, n_agents=0)

        # 2. Extraire les observations par agent
        obs_by_agent = self._extract_observations(records)

        # 3. Construire les chaines de Markov
        report = RHReport(n_logs=len(records), n_agents=len(obs_by_agent))
        for agent_name, obs in obs_by_agent.items():
            am = self._build_markov(agent_name, obs)
            report.agents[agent_name] = am

        # 4. Generer alertes + recommandations
        self._generate_alerts(report)

        return report

    # ------------------------------------------------------------------
    # Chargement
    # ------------------------------------------------------------------

    def _load_logs(self, logs_dir: Path) -> list[dict]:
        records = []
        for f in sorted(logs_dir.glob("v2_*.json")):
            try:
                with open(f, encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict) and data.get("version") == "v2":
                    records.append(data)
            except Exception as e:
                log.warning(f"[AgentRH] Erreur lecture {f.name}: {e}")
        # Trier par timestamp
        records.sort(key=lambda r: r.get("timestamp", ""))
        return records

    # ------------------------------------------------------------------
    # Extraction des observations
    # ------------------------------------------------------------------

    def _extract_observations(self, records: list[dict]) -> dict[str, list[dict]]:
        """
        Retourne un dict agent_name -> liste d'observations
        {"latency_ms": int, "status": str, "timestamp": str}
        triees par timestamp.
        """
        obs: dict[str, list[dict]] = {}
        for rec in records:
            for entry in rec.get("agents_called", []):
                agent = entry.get("agent", "?")
                if agent not in obs:
                    obs[agent] = []
                obs[agent].append({
                    "latency_ms": entry.get("latency_ms", 0),
                    "status":     entry.get("status", "ok"),
                    "timestamp":  rec.get("timestamp", ""),
                })
        return obs

    # ------------------------------------------------------------------
    # Construction Markov
    # ------------------------------------------------------------------

    def _classify(self, agent: str, latency_ms: int) -> int:
        lo, hi = LATENCY_THRESHOLDS.get(agent, (500, 2000))
        if latency_ms < lo:
            return STATE_REPOS
        elif latency_ms <= hi:
            return STATE_NORM
        else:
            return STATE_SURCH

    def _build_markov(self, agent: str, obs: list[dict]) -> AgentMarkov:
        n = len(obs)

        # Classificiation des etats
        states_seq = [
            self._classify(agent, o["latency_ms"])
            for o in obs
        ]
        latencies = [o["latency_ms"] for o in obs]
        errors    = sum(1 for o in obs if o["status"] == "error")

        # Taux bruts
        rate_r = states_seq.count(STATE_REPOS)   / n
        rate_n = states_seq.count(STATE_NORM)    / n
        rate_s = states_seq.count(STATE_SURCH)   / n

        # Matrice de comptage des transitions
        counts = np.zeros((3, 3), dtype=float)
        for i in range(len(states_seq) - 1):
            counts[states_seq[i], states_seq[i + 1]] += 1

        # Normalisation par ligne (avec gestion ligne vide)
        P = np.zeros((3, 3), dtype=float)
        for i in range(3):
            row_sum = counts[i].sum()
            if row_sum > 0:
                P[i] = counts[i] / row_sum
            else:
                # Pas de transition depuis cet etat : auto-boucle
                P[i, i] = 1.0

        # Distribution stationnaire via vecteur propre gauche (eigenvalue = 1)
        stationary = self._stationary_distribution(P)

        # Latences
        lat_arr  = np.array(latencies, dtype=float)
        lat_mean = float(lat_arr.mean())
        lat_p95  = float(np.percentile(lat_arr, 95))
        lat_max  = float(lat_arr.max())

        am = AgentMarkov(
            agent=agent,
            n_observations=n,
            transition_matrix=P.tolist(),
            stationary=stationary,
            rate_repos=rate_r,
            rate_normal=rate_n,
            rate_surcharge=rate_s,
            latency_mean=lat_mean,
            latency_p95=lat_p95,
            latency_max=lat_max,
            surcharge_alert=stationary[STATE_SURCH] > SURCHARGE_ALERT_THRESHOLD,
            sous_utilise=stationary[STATE_REPOS]   > REPOS_ALERT_THRESHOLD,
            error_rate=errors / n,
        )
        return am

    def _stationary_distribution(self, P: np.ndarray) -> list[float]:
        """
        Distribution stationnaire par iteration de puissance.
        Convergence en <500 iterations pour matrices 3x3.
        """
        pi = np.ones(3) / 3.0
        for _ in range(1000):
            pi_new = pi @ P
            if np.allclose(pi_new, pi, atol=1e-10):
                break
            pi = pi_new
        # Normalisation defensive
        s = pi.sum()
        if s > 0:
            pi /= s
        return pi.tolist()

    # ------------------------------------------------------------------
    # Alertes et recommandations
    # ------------------------------------------------------------------

    def _generate_alerts(self, report: RHReport) -> None:
        alerts = []
        recs   = []

        for name, am in report.agents.items():
            pi_s = am.stationary[STATE_SURCH] if am.stationary else 0
            pi_r = am.stationary[STATE_REPOS] if am.stationary else 0

            if am.surcharge_alert:
                alerts.append(
                    f"SURCHARGE — {name} : {pi_s:.0%} du temps en surcharge "
                    f"(p95={am.latency_p95:.0f}ms, max={am.latency_max:.0f}ms)"
                )
                recs.append(
                    f"{name} : envisager mise en cache ou parallelisation "
                    f"(latence p95={am.latency_p95:.0f}ms > seuil)"
                )

            if am.sous_utilise:
                alerts.append(
                    f"SOUS-UTILISATION — {name} : {pi_r:.0%} du temps en repos"
                )
                recs.append(
                    f"{name} : agent sous-utilise — verifier si les seuils "
                    f"de latence sont bien calibres"
                )

            if am.error_rate > 0.08:
                alerts.append(
                    f"TAUX ERREUR — {name} : {am.error_rate:.0%} d'erreurs"
                )
                recs.append(
                    f"{name} : taux d'erreur eleve ({am.error_rate:.0%}) — "
                    f"verifier la stabilite de la source de donnees"
                )

        if not alerts:
            alerts.append("Tous les agents opèrent dans des plages normales.")

        report.alerts          = alerts
        report.recommandations = recs


# ---------------------------------------------------------------------------
# Rapport texte
# ---------------------------------------------------------------------------

def format_report(report: RHReport) -> str:
    lines = [
        "=" * 68,
        "  AGENT RH — RAPPORT MONITORING MARKOV",
        f"  Logs analyses : {report.n_logs} | Agents surveilles : {report.n_agents}",
        "=" * 68,
    ]

    # Tableau par agent
    lines.append("")
    lines.append(f"{'Agent':<18} {'N':>4}  {'Repos':>7} {'Normal':>7} {'Surch.':>7}  "
                 f"{'pi_R':>6} {'pi_N':>6} {'pi_S':>6}  "
                 f"{'Moy':>6} {'p95':>6}  {'Err':>5}  Flag")
    lines.append("-" * 100)

    agent_order = [
        "AgentData", "AgentSentiment", "AgentQuant", "AgentSynthese",
        "AgentQAPython", "AgentQAHaiku", "AgentDevil",
    ]
    for name in agent_order:
        am = report.agents.get(name)
        if not am:
            continue
        pi = am.stationary
        flag = ""
        if am.surcharge_alert:
            flag += "[SURCH] "
        if am.sous_utilise:
            flag += "[SOUS-UTIL] "
        if am.error_rate > 0.08:
            flag += "[ERR] "
        lines.append(
            f"{name:<18} {am.n_observations:>4}  "
            f"{am.rate_repos:>6.0%} {am.rate_normal:>7.0%} {am.rate_surcharge:>7.0%}  "
            f"{pi[0]:>6.1%} {pi[1]:>6.1%} {pi[2]:>6.1%}  "
            f"{am.latency_mean:>6.0f} {am.latency_p95:>6.0f}  "
            f"{am.error_rate:>4.0%}  {flag}"
        )

    # Matrices de transition
    lines.append("")
    lines.append("MATRICES DE TRANSITION (lignes = etat actuel, cols = etat suivant)")
    lines.append("                  -> Repos    Normal  Surcharge")
    for name in agent_order:
        am = report.agents.get(name)
        if not am or not am.transition_matrix:
            continue
        P = am.transition_matrix
        lines.append(f"  {name:<16}")
        for i, state in enumerate(STATES):
            row = P[i] if i < len(P) else [0, 0, 0]
            lines.append(f"    {state:<12}  {row[0]:>6.1%}  {row[1]:>6.1%}  {row[2]:>8.1%}")

    # Alertes
    lines.append("")
    lines.append("ALERTES")
    lines.append("-" * 40)
    for a in report.alerts:
        lines.append(f"  ! {a}")

    # Recommandations
    if report.recommandations:
        lines.append("")
        lines.append("RECOMMANDATIONS")
        lines.append("-" * 40)
        for r in report.recommandations:
            lines.append(f"  > {r}")

    lines.append("")
    lines.append("=" * 68)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )
    rh     = AgentRH()
    report = rh.analyze()
    print(format_report(report))
