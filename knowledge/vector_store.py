# =============================================================================
# FinSight IA — Base Vectorielle
# knowledge/vector_store.py
#
# Indexation des logs V2 dans une base vectorielle locale (ChromaDB).
# Permet aux agents observateurs de faire des requetes semantiques.
#
# Collections :
#   - "pipeline_logs"    : chaque log V2 complet (text = summary)
#   - "agent_incidents"  : incidents / erreurs extraits des logs
#   - "amendments"       : propositions d'amendement
#
# Usage :
#   vs = VectorStore()
#   vs.index_logs_directory()               # indexe logs/local/v2_*.json
#   results = vs.query("erreur synthese")   # top-5 logs similaires
# =============================================================================

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

# Repertoire de persistance Chroma
_CHROMA_DIR = Path(__file__).parent / "chroma_db"
_LOGS_DIR   = Path(__file__).parent.parent / "logs" / "local"


# ---------------------------------------------------------------------------
# Helpers de conversion log → texte indexable
# ---------------------------------------------------------------------------

def _log_to_text(record: dict) -> str:
    """
    Convertit un log V2 en texte plat pour l'indexation semantique.
    Inclut ticker, recommendation, confidence, agents, erreurs.
    """
    parts = []
    parts.append(f"ticker={record.get('ticker', 'UNKNOWN')}")
    parts.append(f"recommendation={record.get('recommendation', 'N/A')}")
    conf = record.get("confidence_score")
    if conf is not None:
        parts.append(f"confidence={conf:.2f}")
    rec  = record.get("recommendation", "")
    if rec:
        parts.append(f"recommendation={rec}")

    agents = record.get("agents_called") or []
    statuses = [f"{a.get('agent','?')}:{a.get('status','?')}" for a in agents]
    if statuses:
        parts.append("agents=" + " ".join(statuses))

    output = record.get("output") or {}
    summary = output.get("summary", "")
    if summary:
        parts.append(summary[:300])

    inv = record.get("invalidation_conditions", "")
    if inv:
        parts.append(f"invalidation={inv[:200]}")

    ctx = record.get("market_context") or {}
    price = ctx.get("share_price")
    if price:
        parts.append(f"price={price}")

    return " | ".join(parts)


def _incident_to_text(record: dict) -> str:
    """Cree un texte d'incident a partir d'un log avec erreurs ou agents en echec."""
    ticker = record.get("ticker", "UNKNOWN")
    ts     = record.get("timestamp", "")
    agents = record.get("agents_called") or []
    errors = [a for a in agents if a.get("status") == "error"]
    lines  = [f"INCIDENT ticker={ticker} ts={ts}"]
    for e in errors:
        lines.append(f"  agent={e.get('agent')} latency={e.get('latency_ms')}ms")
    conf = record.get("confidence_score")
    if conf is not None and conf < 0.65:
        lines.append(f"  confidence_trop_faible={conf:.2f}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# VectorStore
# ---------------------------------------------------------------------------

class VectorStore:
    """
    Base vectorielle ChromaDB locale pour FinSight IA.
    Lazy-init : Chroma est instancie seulement a la premiere utilisation.
    """

    def __init__(self, persist_dir: Optional[Path] = None):
        self._dir    = persist_dir or _CHROMA_DIR
        self._client = None
        self._colls  = {}   # cache des collections

    # ------------------------------------------------------------------
    # Init ChromaDB
    # ------------------------------------------------------------------

    def _get_client(self):
        if self._client is None:
            try:
                import chromadb
                self._dir.mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(path=str(self._dir))
                log.info(f"[VectorStore] ChromaDB initialise : {self._dir}")
            except ImportError:
                raise RuntimeError(
                    "chromadb requis : pip install chromadb"
                )
        return self._client

    def _get_collection(self, name: str):
        if name not in self._colls:
            client = self._get_client()
            self._colls[name] = client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._colls[name]

    # ------------------------------------------------------------------
    # Indexation des logs V2
    # ------------------------------------------------------------------

    def index_logs_directory(self, logs_dir: Optional[Path] = None) -> int:
        """
        Scanne logs/local/ pour les fichiers v2_*.json et les indexe.
        Retourne le nombre de documents ajoutes (skip si deja presents).
        """
        src = logs_dir or _LOGS_DIR
        files = list(src.glob("v2_*.json"))
        if not files:
            log.warning(f"[VectorStore] Aucun log V2 trouve dans {src}")
            return 0

        coll_logs  = self._get_collection("pipeline_logs")
        coll_inc   = self._get_collection("agent_incidents")

        added = 0
        for fp in files:
            try:
                record = json.loads(fp.read_text(encoding="utf-8"))
                rid    = record.get("request_id") or fp.stem

                # Log principal
                existing = coll_logs.get(ids=[rid])
                if existing["ids"]:
                    continue   # deja indexe

                text = _log_to_text(record)
                meta = {
                    "ticker":          record.get("ticker", ""),
                    "recommendation":  record.get("recommendation") or "",
                    "confidence":      float(record.get("confidence_score") or 0),
                    "latency_ms":      int(record.get("latency_ms") or 0),
                    "timestamp":       record.get("timestamp", ""),
                    "file":            fp.name,
                }
                coll_logs.add(documents=[text], metadatas=[meta], ids=[rid])
                added += 1

                # Incidents
                agents = record.get("agents_called") or []
                has_errors = any(a.get("status") == "error" for a in agents)
                conf = record.get("confidence_score")
                if has_errors or (conf is not None and float(conf) < 0.65):
                    inc_text = _incident_to_text(record)
                    inc_id   = f"inc_{rid[:16]}"
                    coll_inc.add(
                        documents=[inc_text],
                        metadatas=[{**meta, "incident_type": "error_or_low_conf"}],
                        ids=[inc_id],
                    )

            except Exception as e:
                log.warning(f"[VectorStore] Erreur indexation {fp.name}: {e}")

        log.info(f"[VectorStore] {added} nouveaux logs indexes (sur {len(files)} fichiers)")
        return added

    # ------------------------------------------------------------------
    # Requetes
    # ------------------------------------------------------------------

    def query(
        self,
        text: str,
        collection: str = "pipeline_logs",
        n_results: int = 5,
    ) -> list[dict]:
        """
        Requete semantique dans une collection.
        Retourne une liste de resultats {id, text, metadata, distance}.
        """
        coll = self._get_collection(collection)
        n_total = coll.count()
        if n_total == 0:
            return []
        n = min(n_results, n_total)
        results = coll.query(query_texts=[text], n_results=n)
        out = []
        for i, doc_id in enumerate(results["ids"][0]):
            out.append({
                "id":       doc_id,
                "text":     results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })
        return out

    def query_incidents(self, text: str, n_results: int = 5) -> list[dict]:
        """Requete dans la collection des incidents."""
        return self.query(text, collection="agent_incidents", n_results=n_results)

    def count(self, collection: str = "pipeline_logs") -> int:
        """Nombre de documents dans une collection."""
        return self._get_collection(collection).count()

    # ------------------------------------------------------------------
    # Indexation des amendements
    # ------------------------------------------------------------------

    def index_amendment(self, amendment: dict) -> None:
        """Indexe une proposition d'amendement."""
        coll  = self._get_collection("amendments")
        aid   = amendment.get("amendment_id", f"amend_{datetime.utcnow().isoformat()}")
        text  = (
            f"Article {amendment.get('article_number')} "
            f"Titre: {amendment.get('title', '')} "
            f"Justification: {amendment.get('justification', '')} "
            f"Proposition: {amendment.get('proposed_text', '')}"
        )
        meta = {
            "article_number": int(amendment.get("article_number", 0)),
            "proposed_by":    amendment.get("proposed_by", "AgentJustice"),
            "date":           amendment.get("date", datetime.utcnow().isoformat()),
            "validated":      str(amendment.get("validated", False)),
        }
        coll.add(documents=[text], metadatas=[meta], ids=[aid])
        log.info(f"[VectorStore] Amendement {aid} indexe")

    def get_amendments(self, validated_only: bool = False) -> list[dict]:
        """Retourne tous les amendements, optionnellement filtres par validation."""
        coll = self._get_collection("amendments")
        if coll.count() == 0:
            return []
        where = {"validated": "True"} if validated_only else None
        res   = coll.get(where=where, include=["documents", "metadatas"])
        out   = []
        for i, doc_id in enumerate(res["ids"]):
            out.append({
                "id":       doc_id,
                "text":     res["documents"][i],
                "metadata": res["metadatas"][i],
            })
        return out
