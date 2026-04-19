"""Module d'extraction de données depuis documents uploadés par l'user.

Pipeline :
- détection de type (extension + signature + heuristiques)
- routing :
  - PDF/image → Gemini Vision (compte de résultat, bilan, contrat, autre)
  - XLSX → parser déterministe (cellules + labels) avec fallback Gemini
- output JSON structuré, validé par l'user avant utilisation dans le scoring.
"""

from core.documents.extractor import (
    DocumentType,
    ExtractionResult,
    detect_type,
    extract_document,
)

__all__ = ["DocumentType", "ExtractionResult", "detect_type", "extract_document"]
