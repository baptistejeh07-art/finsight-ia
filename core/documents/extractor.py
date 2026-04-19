"""Pipeline d'extraction de documents → JSON structuré.

Routing :
  - PDF/image → Gemini 2.0 Flash Vision (extraction LLM)
  - XLSX/XLS → parser cellules + fallback Gemini si non reconnu
  - TXT/CSV → texte brut + résumé LLM

Étape 1 : détection rapide du type via Gemini sur 1ère page (compte_resultat / bilan / contrat / autre)
Étape 2 : extraction structurée selon le type, schema JSON strict

Le résultat est un dict JSON normalisé, prêt à être validé par l'user puis intégré
dans le scoring (s'il s'agit de comptes) ou comme contexte enrichissant (contrat, autre).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from core.documents.prompts import (
    PROMPT_AUTRE,
    PROMPT_BILAN,
    PROMPT_COMPTE_RESULTAT,
    PROMPT_CONTRAT,
    PROMPT_DETECTION,
    SCHEMA_AUTRE,
    SCHEMA_BILAN,
    SCHEMA_COMPTE_RESULTAT,
    SCHEMA_CONTRAT,
)

log = logging.getLogger(__name__)


class DocumentType(str, Enum):
    COMPTE_RESULTAT = "compte_resultat"
    BILAN = "bilan"
    CONTRAT = "contrat"
    AUTRE = "autre"


@dataclass
class ExtractionResult:
    type_detected: DocumentType
    data: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    error: str | None = None
    source: str = "gemini"  # "gemini" | "xlsx_parser" | "fallback"
    pages_processed: int = 0


# ==============================================================================
# Détection type par extension (pré-filtre rapide)
# ==============================================================================

_PDF_EXTS = {".pdf"}
_IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_XLSX_EXTS = {".xlsx", ".xls", ".xlsm"}
_TEXT_EXTS = {".txt", ".csv"}


def _file_kind(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in _PDF_EXTS:
        return "pdf"
    if ext in _IMG_EXTS:
        return "image"
    if ext in _XLSX_EXTS:
        return "xlsx"
    if ext in _TEXT_EXTS:
        return "text"
    return "unknown"


def file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# ==============================================================================
# Gemini Vision API (HTTP direct, pas de SDK)
# ==============================================================================

_GEMINI_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-2.0-flash")
_GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _gemini_call(
    prompt: str,
    file_bytes: bytes,
    mime_type: str,
    response_schema: dict | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    """Appel Gemini Vision avec structured output."""
    import requests

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY absente — impossible d'extraire via LLM")

    url = f"{_GEMINI_API_BASE}/models/{_GEMINI_MODEL}:generateContent?key={api_key}"

    parts: list[dict] = [
        {"text": prompt},
        {
            "inline_data": {
                "mime_type": mime_type,
                "data": base64.b64encode(file_bytes).decode("ascii"),
            }
        },
    ]

    body: dict[str, Any] = {
        "contents": [{"parts": parts}],
        "generation_config": {
            "temperature": 0.0,
            "max_output_tokens": 4096,
            "response_mime_type": "application/json",
        },
    }
    if response_schema is not None:
        body["generation_config"]["response_schema"] = response_schema

    r = requests.post(url, json=body, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"Gemini HTTP {r.status_code} : {r.text[:300]}")

    payload = r.json()
    candidates = payload.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini : pas de candidats dans la réponse")
    text = (
        candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    ).strip()
    if not text:
        raise RuntimeError("Gemini : réponse vide")

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # Tente de récupérer un JSON même si entouré de texte parasite
        first = text.find("{")
        last = text.rfind("}")
        if first >= 0 and last > first:
            try:
                return json.loads(text[first : last + 1])
            except json.JSONDecodeError:
                pass
        raise RuntimeError(f"Gemini : JSON invalide ({e}) — extrait : {text[:200]}")


# ==============================================================================
# Détection type via Gemini (1 appel rapide, schema léger)
# ==============================================================================

_DETECT_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": [t.value for t in DocumentType]},
        "confiance": {"type": "number"},
        "annee": {"type": "integer"},
    },
    "required": ["type", "confiance"],
}


def detect_type(file_bytes: bytes, mime_type: str) -> tuple[DocumentType, float]:
    """Détection rapide via Gemini : compte_resultat / bilan / contrat / autre."""
    try:
        out = _gemini_call(PROMPT_DETECTION, file_bytes, mime_type, _DETECT_SCHEMA)
        t = out.get("type", "autre")
        conf = float(out.get("confiance", 0.5))
        try:
            return DocumentType(t), conf
        except ValueError:
            return DocumentType.AUTRE, conf
    except Exception as e:
        log.warning(f"[detect_type] échec : {e}")
        return DocumentType.AUTRE, 0.0


# ==============================================================================
# Extraction par type
# ==============================================================================

_EXTRACT_CONFIG = {
    DocumentType.COMPTE_RESULTAT: (PROMPT_COMPTE_RESULTAT, SCHEMA_COMPTE_RESULTAT),
    DocumentType.BILAN: (PROMPT_BILAN, SCHEMA_BILAN),
    DocumentType.CONTRAT: (PROMPT_CONTRAT, SCHEMA_CONTRAT),
    DocumentType.AUTRE: (PROMPT_AUTRE, SCHEMA_AUTRE),
}


def _extract_by_type(
    doc_type: DocumentType, file_bytes: bytes, mime_type: str
) -> dict[str, Any]:
    prompt, schema = _EXTRACT_CONFIG[doc_type]
    return _gemini_call(prompt, file_bytes, mime_type, schema)


# ==============================================================================
# Pipeline principal
# ==============================================================================

def extract_document(
    file_bytes: bytes,
    filename: str,
    mime_type: str | None = None,
) -> ExtractionResult:
    """Extrait un document → JSON structuré.

    Args:
        file_bytes : contenu brut du fichier
        filename : nom du fichier (utilisé pour détection type extension)
        mime_type : MIME type explicite (si None, déduit de l'extension)

    Returns:
        ExtractionResult avec type, data JSON, confidence, erreurs éventuelles.
    """
    kind = _file_kind(filename)
    if mime_type is None:
        mime_type = _guess_mime(filename)

    # XLSX → parser déterministe direct (pas de Gemini par défaut)
    if kind == "xlsx":
        try:
            from core.documents.xlsx_parser import parse_xlsx_document

            data = parse_xlsx_document(file_bytes)
            doc_type = DocumentType(data.get("type", "autre"))
            return ExtractionResult(
                type_detected=doc_type,
                data=data,
                confidence=data.pop("_confidence", 0.85),
                source="xlsx_parser",
            )
        except Exception as e:
            log.warning(f"[extract] XLSX parser échec, fallback Gemini : {e}")
            # tombe dans le pipeline Gemini ci-dessous (avec mime XLSX)

    # PDF / image / fallback XLSX → Gemini
    if kind in {"pdf", "image", "xlsx", "text"}:
        try:
            doc_type, conf = detect_type(file_bytes, mime_type)
            data = _extract_by_type(doc_type, file_bytes, mime_type)
            return ExtractionResult(
                type_detected=doc_type,
                data=data,
                confidence=conf,
                source="gemini",
            )
        except Exception as e:
            log.error(f"[extract] Gemini extraction échec : {e}")
            return ExtractionResult(
                type_detected=DocumentType.AUTRE,
                data={},
                confidence=0.0,
                error=str(e),
                source="gemini",
            )

    return ExtractionResult(
        type_detected=DocumentType.AUTRE,
        data={},
        error=f"Type de fichier non supporté : {kind}",
        source="fallback",
    )


def _guess_mime(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".txt": "text/plain",
        ".csv": "text/csv",
    }.get(ext, "application/octet-stream")
