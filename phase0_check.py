#!/usr/bin/env python3
# =============================================================================
# FinSight IA — Phase 0 : Vérification des clés API + LLMProvider
# Usage : python phase0_check.py
# Condition de passage Phase 0 → Phase 1 :
#   - Toutes les clés obligatoires lisibles
#   - LLMProvider instanciable pour les 4 providers
# =============================================================================

import os
import sys
from pathlib import Path

# Charger le .env du projet
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")


# --- Clés requises V1 (obligatoires) ---
REQUIRED = {
    "ANTHROPIC_API_KEY":     "Claude Haiku/Sonnet — LLM principal",
    "GROQ_API_KEY":          "Groq / Llama 3 — tâches légères répétitives",
    "FINNHUB_API_KEY":       "Finnhub — news, sentiment, macro, earnings",
    "POLYGON_API_KEY":       "Polygon.io — temps réel, WebSocket",
    "SUPABASE_URL":          "Supabase — archive PostgreSQL",
    "SUPABASE_SECRET_KEY":   "Supabase — clé secrète",
    "ALPHAVANTAGE_API_KEY":  "Alpha Vantage — fallback données",
    "EODHD_API_KEY":         "EODHD — fallback dernier recours",
    "FMP_API_KEY":           "Financial Modeling Prep — fondamentaux européens",
}

# --- Clés optionnelles V1 ---
OPTIONAL = {
    "GEMINI_API_KEY":           "Gemini Flash — backup urgence uniquement",
    "SUPABASE_PUBLISHABLE_KEY": "Supabase — clé publique (frontend)",
}


def _mask(value: str) -> str:
    if len(value) <= 12:
        return value[:4] + "..." + value[-2:]
    return value[:8] + "..." + value[-4:]


def check_keys() -> bool:
    print("=" * 68)
    print("  FinSight IA — Phase 0 : Vérification des clés API")
    print("=" * 68)

    all_ok = True

    print("\n  [OBLIGATOIRES]")
    for key, description in REQUIRED.items():
        value = os.getenv(key, "").strip()
        if value:
            status = f"OK  {_mask(value)}"
            mark = "[OK]"
        else:
            status = "MANQUANTE"
            mark = "[!!]"
            all_ok = False
        print(f"  {mark}  {key:<28} {status:<20}  {description}")

    print("\n  [OPTIONNELLES]")
    for key, description in OPTIONAL.items():
        value = os.getenv(key, "").strip()
        status = f"OK  {_mask(value)}" if value else "non definie"
        print(f"  [ ·]  {key:<28} {status:<20}  {description}")

    print()
    return all_ok


def check_llm_provider() -> bool:
    print("=" * 68)
    print("  LLMProvider — instanciation des 4 providers")
    print("=" * 68)

    sys.path.insert(0, str(Path(__file__).parent))
    from core.llm_provider import LLMProvider

    providers = [
        ("anthropic", None),
        ("groq",      None),
        ("gemini",    None),
        ("ollama",    "qwen3:14b"),
    ]

    all_ok = True
    for provider, model in providers:
        try:
            kwargs = {"provider": provider}
            if model:
                kwargs["model"] = model
            llm = LLMProvider(**kwargs)
            print(f"  [OK]  {repr(llm)}")
        except Exception as e:
            print(f"  [!!]  LLMProvider(provider='{provider}') -- ERREUR : {e}")
            all_ok = False

    print()
    return all_ok


def main():
    keys_ok = check_keys()
    llm_ok  = check_llm_provider()

    print("=" * 68)
    if keys_ok and llm_ok:
        print("  PHASE 0 VALIDEE -- Pret pour Phase 1 (Agent Data)")
    else:
        if not keys_ok:
            print("  [!!] Des cles sont manquantes -- completer le .env")
        if not llm_ok:
            print("  [!!] LLMProvider en erreur -- verifier les imports")
        sys.exit(1)
    print("=" * 68)


if __name__ == "__main__":
    main()
