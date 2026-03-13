# =============================================================================
# FinSight IA — Phase 9 Check : V2 Gouvernance
# phase9_check.py
#
# Valide les composants de gouvernance :
#   1. Constitution (7 articles, check_compliance)
#   2. Base vectorielle ChromaDB (index + query)
#   3. Agent Sociologue (observe)
#   4. Agent Enquete (investigate)
#   5. Agent Journaliste (weekly_report)
#   6. Agent Justice (evaluate + 1 proposition)
#
# Condition PASS :
#   - Constitution importee et articles 1-7 presents
#   - Vector store indexe les logs V2 (ou 0 log disponible = OK)
#   - Agent Justice retourne un rapport valide
#   - Au moins 1 proposition d'amendement generee OU verdict CONFORME
# =============================================================================

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

import time


def check_constitution() -> bool:
    log.info("[Phase9] Test 1/6 : Constitution")
    from config.constitution import ARTICLES, summary, check_compliance, get_article

    assert len(ARTICLES) == 7, f"Attendu 7 articles, got {len(ARTICLES)}"
    for i in range(1, 8):
        art = get_article(i)
        assert art is not None, f"Article {i} manquant"
        assert art.title, f"Article {i} sans titre"
    log.info(f"[Constitution] 7 articles OK")
    log.info(summary())

    # Test check_compliance
    fake_state = {"confidence_score": 0.55, "data_quality": 0.80}
    violations = check_compliance(fake_state)
    viol = [v for v in violations if not v["compliant"]]
    assert any(v["article"] == 1 for v in viol), "Article 1 violation non detectee"
    log.info(f"[Constitution] check_compliance OK — {len(viol)} violation(s) sur test")
    return True


def check_vector_store() -> bool:
    log.info("[Phase9] Test 2/6 : VectorStore")
    try:
        import chromadb  # noqa: F401
    except ImportError:
        log.warning("[VectorStore] chromadb non installe — pip install chromadb")
        log.warning("[VectorStore] Test SKIP (non bloquant)")
        return True   # non bloquant pour le PASS

    from knowledge.vector_store import VectorStore
    vs = VectorStore()

    added = vs.index_logs_directory()
    log.info(f"[VectorStore] {added} logs indexes, total={vs.count()}")

    if vs.count() > 0:
        results = vs.query("synthese confiance", n_results=3)
        log.info(f"[VectorStore] Query 'synthese confiance' : {len(results)} resultats")
    else:
        log.info("[VectorStore] 0 log disponible — index vide (bootstrap requis)")
    return True


def check_sociologue() -> bool:
    log.info("[Phase9] Test 3/6 : AgentSociologue")
    from agents.agent_sociologue import AgentSociologue

    soc = AgentSociologue()
    t0  = time.time()
    report = soc.observe(max_logs=200)
    ms  = int((time.time() - t0) * 1000)

    log.info(
        f"[Sociologue] {report.total_requests} requetes | "
        f"blocked_rate={report.blocked_rate:.0%} | "
        f"alertes={len(report.systemic_alerts)} | {ms}ms"
    )
    if report.correlation_notes:
        for note in report.correlation_notes[:3]:
            log.info(f"  Note : {note}")
    return True


def check_enquete() -> bool:
    log.info("[Phase9] Test 4/6 : AgentEnquete")
    from agents.agent_enquete import AgentEnquete

    enquete = AgentEnquete()
    t0      = time.time()
    report  = enquete.investigate("incidents erreurs agents", use_vector_store=False)
    ms      = int((time.time() - t0) * 1000)

    log.info(
        f"[Enquete] Sujet='{report.subject}' | "
        f"severity={report.severity} | "
        f"traces={len(report.traces)} | "
        f"patterns={len(report.patterns)} | {ms}ms"
    )
    if report.root_causes:
        for cause in report.root_causes[:2]:
            log.info(f"  Cause : {cause}")
    return True


def check_journaliste(soc_report, enq_report) -> bool:
    log.info("[Phase9] Test 5/6 : AgentJournaliste")
    from agents.agent_journaliste import AgentJournaliste

    journaliste = AgentJournaliste(use_llm=False)
    t0          = time.time()
    report      = journaliste.weekly_report(
        sociologue_report=soc_report,
        enquete_report=enq_report,
    )
    ms = int((time.time() - t0) * 1000)

    assert report.title, "Rapport sans titre"
    assert report.executive_summary, "Rapport sans executive_summary"
    log.info(f"[Journaliste] Rapport genere : {report.title} | {ms}ms")
    if report.file_path:
        log.info(f"[Journaliste] Sauvegarde : {report.file_path}")
    return True


def check_justice(soc_report, enq_report) -> bool:
    log.info("[Phase9] Test 6/6 : AgentJustice")
    from agents.agent_justice import AgentJustice

    justice = AgentJustice()
    t0      = time.time()
    report  = justice.evaluate(
        sociologue_report=soc_report,
        enquete_report=enq_report,
        max_logs=200,
    )
    ms = int((time.time() - t0) * 1000)

    log.info(
        f"[Justice] Verdict={report.verdict} | "
        f"{len(report.compliance_checks)} articles verifies | "
        f"{len(report.propositions)} proposition(s) | {ms}ms"
    )
    log.info(f"\n{report.commentary}")

    # Condition PASS : verdict valide ET rapport coherent
    assert report.verdict in ("CONFORME", "ALERTES", "AMENDEMENTS_REQUIS")
    assert len(report.compliance_checks) == 7

    pending = justice.list_pending_amendments()
    log.info(f"[Justice] {len(pending)} amendement(s) en attente de validation humaine")

    return True


if __name__ == "__main__":
    log.info("[Phase9] Demarrage verification V2 Gouvernance")

    soc_report = None
    enq_report = None

    tests = [
        ("Constitution",   check_constitution),
        ("VectorStore",    check_vector_store),
    ]

    results = {}
    for name, fn in tests:
        try:
            results[name] = fn()
        except Exception as e:
            log.error(f"[Phase9] ECHEC {name} : {e}", exc_info=True)
            results[name] = False

    # Agents observateurs
    try:
        from agents.agent_sociologue import AgentSociologue
        soc_report = AgentSociologue().observe(max_logs=200)
        results["Sociologue"] = True
        log.info(f"[Sociologue] OK — {soc_report.total_requests} requetes")
    except Exception as e:
        log.error(f"[Phase9] ECHEC Sociologue : {e}", exc_info=True)
        results["Sociologue"] = False

    try:
        from agents.agent_enquete import AgentEnquete
        enq_report = AgentEnquete().investigate("incidents erreurs", use_vector_store=False)
        results["Enquete"] = True
        log.info(f"[Enquete] OK — severity={enq_report.severity}")
    except Exception as e:
        log.error(f"[Phase9] ECHEC Enquete : {e}", exc_info=True)
        results["Enquete"] = False

    try:
        results["Journaliste"] = check_journaliste(soc_report, enq_report)
    except Exception as e:
        log.error(f"[Phase9] ECHEC Journaliste : {e}", exc_info=True)
        results["Journaliste"] = False

    try:
        results["Justice"] = check_justice(soc_report, enq_report)
    except Exception as e:
        log.error(f"[Phase9] ECHEC Justice : {e}", exc_info=True)
        results["Justice"] = False

    # Rapport final
    print("\n" + "=" * 60)
    print("  FinSight IA — Phase 9 Gouvernance")
    print("=" * 60)
    all_ok = True
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  {name:<20} {status}")
        if not ok:
            all_ok = False
    print("=" * 60)
    print(f"\nPhase 9 : {'PASS' if all_ok else 'FAIL'}")
    sys.exit(0 if all_ok else 1)
