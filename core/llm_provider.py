# =============================================================================
# FinSight IA — LLMProvider abstrait
# core/llm_provider.py
#
# CRITIQUE : construire avant tout le reste.
# Changer de fournisseur = 1 ligne de code.
# Providers : anthropic | groq | gemini | ollama
# =============================================================================

from __future__ import annotations

import os
from typing import Optional


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
        "anthropic": "claude-haiku-4-5-20251001",   # tâches courantes — coût/qualité optimal
        "groq":      "llama-3.3-70b-versatile",     # tâches simples répétitives — quasi gratuit
        "gemini":    "gemini-2.0-flash",             # backup urgence uniquement
        "ollama":    "qwen3:14b",                    # tests locaux gratuits — développement
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
                api_key=os.getenv("ANTHROPIC_API_KEY")
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
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def _call_gemini(self, prompt: str, system: Optional[str], max_tokens: int) -> str:
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
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
