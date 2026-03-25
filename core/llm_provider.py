# =============================================================================
# FinSight IA — LLMProvider abstrait
# core/llm_provider.py
#
# CRITIQUE : construire avant tout le reste.
# Changer de fournisseur = 1 ligne de code.
# Providers : anthropic | groq | gemini | ollama
# =============================================================================

from __future__ import annotations

import json
import logging
import os
import time
from datetime import date
from pathlib import Path
from typing import Optional

from core.secrets import get_secret as _get_secret

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gestionnaire de rotation des clés Groq
# ---------------------------------------------------------------------------

class _GroqKeyRotator:
    """
    Rotation automatique des clés Groq.
    - Lit GROQ_API_KEY_1, GROQ_API_KEY_2, ... depuis l'env
    - Suit les tokens consommés par clé dans logs/groq_usage.json
    - Bascule sur la clé suivante quand GROQ_KEY_LIMIT est atteint
    - Remet les compteurs à zéro chaque jour (UTC)
    """

    _USAGE_FILE = Path(__file__).parent.parent / "logs" / "groq_usage.json"

    def __init__(self):
        self._keys: list[str] = []
        self._limit: int = 50_000          # défaut conservateur
        self._usage: dict = {}
        self._idx: int = 0
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        # Charger les clés depuis l'env
        from dotenv import load_dotenv
        load_dotenv(override=True)
        i = 1
        while True:
            k = os.getenv(f"GROQ_API_KEY_{i}", "").strip()
            if not k:
                break
            self._keys.append(k)
            i += 1
        # Fallback : ancienne variable GROQ_API_KEY
        if not self._keys:
            k = os.getenv("GROQ_API_KEY", "").strip()
            if k:
                self._keys.append(k)
        self._limit = int(os.getenv("GROQ_KEY_LIMIT", "50000"))
        self._load_usage()
        self._loaded = True

    def _load_usage(self):
        today = str(date.today())
        try:
            raw = json.loads(self._USAGE_FILE.read_text(encoding="utf-8"))
            # Reset si nouveau jour
            if raw.get("date") != today:
                raw = {"date": today, "keys": {}, "current": 0}
        except Exception:
            raw = {"date": today, "keys": {}, "current": 0}
        self._usage = raw
        self._idx   = int(raw.get("current", 0))

    def _save_usage(self):
        try:
            self._USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._USAGE_FILE.write_text(json.dumps(self._usage, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _tokens_used(self, idx: int) -> int:
        return self._usage["keys"].get(str(idx), {}).get("tokens", 0)

    def _add_tokens(self, idx: int, tokens: int):
        k = str(idx)
        if k not in self._usage["keys"]:
            self._usage["keys"][k] = {"tokens": 0, "requests": 0}
        self._usage["keys"][k]["tokens"]   += tokens
        self._usage["keys"][k]["requests"] += 1
        self._save_usage()

    def get_key(self) -> str:
        self._load()
        if not self._keys:
            raise RuntimeError("[GroqRotator] Aucune cle GROQ_API_KEY_N trouvee dans .env")
        # Chercher une clé non épuisée à partir de l'index courant
        for _ in range(len(self._keys)):
            if self._tokens_used(self._idx) < self._limit:
                return self._keys[self._idx]
            _log.warning(
                f"[GroqRotator] Cle {self._idx + 1} epuisee "
                f"({self._tokens_used(self._idx)}/{self._limit} tokens) — rotation"
            )
            self._idx = (self._idx + 1) % len(self._keys)
            self._usage["current"] = self._idx
            self._save_usage()
        raise RuntimeError("[GroqRotator] Toutes les cles Groq sont epuisees pour aujourd'hui")

    def record(self, tokens: int):
        """Enregistre les tokens consommés par le dernier appel."""
        self._load()
        self._add_tokens(self._idx, tokens)
        used = self._tokens_used(self._idx)
        remaining = self._limit - used
        if remaining < 5000:
            _log.warning(f"[GroqRotator] Cle {self._idx + 1} : {remaining} tokens restants avant rotation")

    def status(self) -> str:
        self._load()
        parts = []
        for i, _ in enumerate(self._keys):
            used = self._tokens_used(i)
            active = " <-- actif" if i == self._idx else ""
            parts.append(f"  Cle {i+1}: {used}/{self._limit} tokens{active}")
        return "\n".join(parts)


_rotator = _GroqKeyRotator()


class LLMProvider:
    """
    Abstraction LLM multi-fournisseurs.

    Usage :
        llm = LLMProvider(provider="anthropic", model="claude-haiku-4-5-20251001")
        response = llm.generate("Analyse LVMH")

    Changer de provider sans toucher au reste du code :
        llm = LLMProvider(provider="groq")
        llm = LLMProvider(provider="ollama", model="qwen3:14b")
    """

    # Modèles par défaut par provider (brief technique §5)
    DEFAULTS: dict[str, str] = {
        "anthropic": "claude-haiku-4-5-20251001",       # tâches courantes — coût/qualité optimal
        "groq":      "llama-3.3-70b-versatile",         # principal — quasi gratuit, rapide
        "mistral":   "mistral-small-latest",             # fallback 1 — gratuit tier0
        "cerebras":  "qwen-3-235b-a22b-instruct-2507",     # fallback 2 — ultra rapide
        "gemini":    "gemini-2.0-flash",                 # fallback 3 — backup urgence
        "ollama":    "qwen3:14b",                        # tests locaux gratuits — développement
    }

    SUPPORTED_PROVIDERS = set(DEFAULTS.keys())

    def __init__(self, provider: str = "anthropic", model: Optional[str] = None):
        if provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Provider '{provider}' inconnu. "
                f"Valeurs acceptées : {sorted(self.SUPPORTED_PROVIDERS)}"
            )
        self.provider = provider
        self.model = model or self.DEFAULTS[provider]
        self._client = None  # lazy init — instancié au premier appel

    # ------------------------------------------------------------------
    # Interface publique principale
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        """
        Génère une réponse textuelle synchrone.

        Args:
            prompt:     Message utilisateur
            system:     Instruction système (optionnelle)
            max_tokens: Limite de tokens en sortie

        Returns:
            Texte généré par le modèle
        """
        if self.provider == "anthropic":
            return self._call_anthropic(prompt, system, max_tokens)
        elif self.provider == "groq":
            return self._call_groq(prompt, system, max_tokens)
        elif self.provider == "mistral":
            return self._call_mistral(prompt, system, max_tokens)
        elif self.provider == "cerebras":
            return self._call_cerebras(prompt, system, max_tokens)
        elif self.provider == "gemini":
            return self._call_gemini(prompt, system, max_tokens)
        elif self.provider == "ollama":
            return self._call_ollama(prompt, system, max_tokens)
        # Ne devrait jamais arriver (contrôlé dans __init__)
        raise ValueError(f"Provider inconnu : {self.provider}")

    async def generate_async(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        """
        Version async pour asyncio.gather() multi-agents.

        Exemple :
            results = await asyncio.gather(
                llm1.generate_async(prompt_a),
                llm2.generate_async(prompt_b),
            )
        """
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.generate(prompt, system, max_tokens)
        )

    # ------------------------------------------------------------------
    # Implémentations par provider (lazy client)
    # ------------------------------------------------------------------

    def _call_anthropic(self, prompt: str, system: Optional[str], max_tokens: int) -> str:
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(
                api_key=_get_secret("ANTHROPIC_API_KEY")
            )
        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        response = self._client.messages.create(**kwargs)
        return response.content[0].text

    def _call_groq(self, prompt: str, system: Optional[str], max_tokens: int) -> str:
        from groq import Groq
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        _delays = [5, 15, 30]
        for _attempt, _wait in enumerate([0] + _delays):
            if _wait:
                _log.warning(f"[Groq] Tentative {_attempt + 1}/4 — attente {_wait}s")
                time.sleep(_wait)
            try:
                # Obtenir la clé active (rotation automatique si limite atteinte)
                _key    = _rotator.get_key()
                _client = Groq(api_key=_key)
                response = _client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                )
                # Enregistrer les tokens consommés
                _total = getattr(getattr(response, "usage", None), "total_tokens", max_tokens)
                _rotator.record(_total)
                return response.choices[0].message.content
            except Exception as e:
                _code = getattr(e, "status_code", None) or getattr(
                    getattr(e, "response", None), "status_code", None
                )
                _msg = str(e)
                if _code in (429, 503) or "rate_limit" in _msg.lower() or "overloaded" in _msg.lower():
                    if _attempt < len(_delays):
                        continue
                raise
        raise RuntimeError("[Groq] Echec apres 4 tentatives")

    def _call_mistral(self, prompt: str, system: Optional[str], max_tokens: int) -> str:
        from mistralai.client import Mistral
        client = Mistral(api_key=_get_secret("MISTRAL_API_KEY"))
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.complete(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def _call_cerebras(self, prompt: str, system: Optional[str], max_tokens: int) -> str:
        from cerebras.cloud.sdk import Cerebras
        client = Cerebras(api_key=_get_secret("CEREBRAS_API_KEY"))
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def _call_gemini(self, prompt: str, system: Optional[str], max_tokens: int) -> str:
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=_get_secret("GEMINI_API_KEY"))
            self._client = genai
        model = self._client.GenerativeModel(
            self.model,
            generation_config={"max_output_tokens": max_tokens},
        )
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        response = model.generate_content(full_prompt)
        return response.text

    def _call_ollama(self, prompt: str, system: Optional[str], max_tokens: int) -> str:
        import ollama
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = ollama.chat(model=self.model, messages=messages)
        return response["message"]["content"]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"LLMProvider(provider='{self.provider}', model='{self.model}')"
