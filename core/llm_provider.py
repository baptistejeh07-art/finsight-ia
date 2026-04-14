# =============================================================================
# FinSight IA — LLMProvider abstrait
# core/llm_provider.py
#
# CRITIQUE : construire avant tout le reste.
# Changer de fournisseur = 1 ligne de code.
# Providers : anthropic | groq | openai | mistral | cerebras | gemini | ollama
#
# ARCHITECTURE 2026-04-14 (refonte Baptiste)
# - Routing par phase du pipeline via llm_call(phase="...")
# - TPM counter glissant 60s par cle (evite 429)
# - Skip-forward fallback : pas de retour en arriere sur echec
# - Seuils par cle : TPD (journalier) + TPM (par minute)
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
# Rate limiter abstrait : TPD (journalier) + TPM (glissant 60s)
# ---------------------------------------------------------------------------

class _KeyRotator:
    """Base class pour rotation de cles multi-providers avec TPD + TPM tracking.

    Usage derive :
        class _GroqKeyRotator(_KeyRotator):
            _PREFIX = "GROQ_API_KEY"
            _DEFAULT_TPD = 80_000
            _DEFAULT_TPM = 12_000
    """

    _USAGE_FILE: Path    # a override
    _PREFIX: str = ""    # a override (ex: "GROQ_API_KEY")
    _DEFAULT_TPD: int = 50_000
    _DEFAULT_TPM: int = 10_000
    _ENV_LIMIT_TPD: str = ""  # optional override via env var

    def __init__(self):
        self._keys: list[str] = []
        self._limit_tpd: int = self._DEFAULT_TPD
        self._limit_tpm: int = self._DEFAULT_TPM
        self._usage: dict = {}          # persistance TPD
        # TPM : fenetre glissante 60s, liste [(ts, tokens)] par cle
        self._tpm_window: dict[int, list[tuple[float, int]]] = {}
        self._idx: int = 0
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        from dotenv import load_dotenv
        load_dotenv(override=True)
        i = 1
        while True:
            k = os.getenv(f"{self._PREFIX}_{i}", "").strip()
            if not k:
                break
            self._keys.append(k)
            i += 1
        # Fallback : ancienne variable sans suffixe
        if not self._keys:
            k = os.getenv(self._PREFIX, "").strip()
            if k:
                self._keys.append(k)
        # Limite TPD overridable par env var
        if self._ENV_LIMIT_TPD:
            self._limit_tpd = int(os.getenv(self._ENV_LIMIT_TPD, str(self._DEFAULT_TPD)))
        self._load_usage()
        self._loaded = True

    def _load_usage(self):
        today = str(date.today())
        try:
            raw = json.loads(self._USAGE_FILE.read_text(encoding="utf-8"))
            if raw.get("date") != today:
                raw = {"date": today, "keys": {}, "current": 0}
        except Exception:
            raw = {"date": today, "keys": {}, "current": 0}
        self._usage = raw
        self._idx = int(raw.get("current", 0))

    def _save_usage(self):
        try:
            self._USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._USAGE_FILE.write_text(
                json.dumps(self._usage, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _tokens_used_tpd(self, idx: int) -> int:
        return self._usage["keys"].get(str(idx), {}).get("tokens", 0)

    def _tokens_used_tpm(self, idx: int) -> int:
        """Somme des tokens consommes dans la fenetre glissante 60s."""
        now = time.time()
        window = self._tpm_window.get(idx, [])
        # Purge les entrees plus vieilles que 60s
        window = [(ts, tok) for ts, tok in window if now - ts < 60.0]
        self._tpm_window[idx] = window
        return sum(tok for _, tok in window)

    def _add_tokens(self, idx: int, tokens: int):
        k = str(idx)
        if k not in self._usage["keys"]:
            self._usage["keys"][k] = {"tokens": 0, "requests": 0}
        self._usage["keys"][k]["tokens"] += tokens
        self._usage["keys"][k]["requests"] += 1
        self._save_usage()
        # TPM tracking
        if idx not in self._tpm_window:
            self._tpm_window[idx] = []
        self._tpm_window[idx].append((time.time(), tokens))

    def _key_available(self, idx: int) -> bool:
        """True si la cle a du budget TPD ET TPM disponible."""
        if self._tokens_used_tpd(idx) >= self._limit_tpd:
            return False
        if self._tokens_used_tpm(idx) >= int(self._limit_tpm * 0.80):
            return False
        return True

    def get_key(self) -> str:
        self._load()
        if not self._keys:
            raise RuntimeError(
                f"[{self._PREFIX}Rotator] Aucune cle {self._PREFIX}_N trouvee dans .env")
        # Chercher une cle disponible (TPD + TPM OK)
        for _ in range(len(self._keys)):
            if self._key_available(self._idx):
                return self._keys[self._idx]
            _log.warning(
                f"[{self._PREFIX}Rotator] Cle {self._idx + 1} indisponible "
                f"(TPD {self._tokens_used_tpd(self._idx)}/{self._limit_tpd} "
                f"TPM {self._tokens_used_tpm(self._idx)}/{self._limit_tpm}) — rotation"
            )
            self._idx = (self._idx + 1) % len(self._keys)
            self._usage["current"] = self._idx
            self._save_usage()
        # Toutes les cles saturees : signaler au caller qu'il doit basculer provider
        raise _ProviderExhausted(
            f"[{self._PREFIX}Rotator] Toutes les cles saturees (TPD + TPM)")

    def record(self, tokens: int):
        self._load()
        self._add_tokens(self._idx, tokens)

    def is_exhausted(self) -> bool:
        self._load()
        return all(not self._key_available(i) for i in range(len(self._keys)))

    def has_keys(self) -> bool:
        self._load()
        return bool(self._keys)

    def status(self) -> str:
        self._load()
        parts = []
        for i, _ in enumerate(self._keys):
            tpd = self._tokens_used_tpd(i)
            tpm = self._tokens_used_tpm(i)
            active = " <-- actif" if i == self._idx else ""
            parts.append(f"  Cle {i+1}: TPD {tpd}/{self._limit_tpd}  "
                         f"TPM {tpm}/{self._limit_tpm}{active}")
        return "\n".join(parts)


class _ProviderExhausted(Exception):
    """Levee quand toutes les cles d'un provider sont saturees (skip-forward)."""
    pass


class _GroqKeyRotator(_KeyRotator):
    """Rotation cles Groq : 30 RPM, 12K TPM, 100K TPD (llama-3.3-70b free tier)."""
    _USAGE_FILE = Path(__file__).parent.parent / "logs" / "groq_usage.json"
    _PREFIX = "GROQ_API_KEY"
    _DEFAULT_TPD = 80_000   # 80% de 100K TPD
    _DEFAULT_TPM = 12_000
    _ENV_LIMIT_TPD = "GROQ_KEY_LIMIT"


class _OpenAIKeyRotator(_KeyRotator):
    """Rotation cles OpenAI : gpt-4o-mini (10K TPM, tier 1 pay-as-you-go).

    Tier 1 limits (default apres recharge 5$) : 200K TPD, 10K TPM.
    Budget conservateur pour eviter la surfacturation :
    - TPD : 150K tokens/jour/cle (~1-2$ max par jour par cle)
    - TPM : 8K tokens/minute
    """
    _USAGE_FILE = Path(__file__).parent.parent / "logs" / "openai_usage.json"
    _PREFIX = "OPENAI_API_KEY"
    _DEFAULT_TPD = 150_000
    _DEFAULT_TPM = 8_000
    _ENV_LIMIT_TPD = "OPENAI_KEY_LIMIT"


_rotator = _GroqKeyRotator()           # backwards compat pour code existant
_openai_rotator = _OpenAIKeyRotator()


# ---------------------------------------------------------------------------
# LLMProvider classique (backwards compatible)
# ---------------------------------------------------------------------------

class LLMProvider:
    """
    Abstraction LLM multi-fournisseurs.

    Usage classique (backwards compatible) :
        llm = LLMProvider(provider="groq")
        response = llm.generate("Analyse LVMH")

    Usage avec routing automatique par phase :
        from core.llm_provider import llm_call
        response = llm_call("Analyse LVMH", phase="long")
    """

    # Modeles par defaut par provider
    DEFAULTS: dict[str, str] = {
        "anthropic": "claude-haiku-4-5-20251001",
        "groq":      "llama-3.3-70b-versatile",
        "openai":    "gpt-4o-mini",                      # moins cher, 128K context
        "mistral":   "mistral-small-latest",
        "cerebras":  "qwen-3-235b-a22b-instruct-2507",
        "gemini":    "gemini-2.0-flash",
        "ollama":    "qwen3:14b",
    }

    SUPPORTED_PROVIDERS = set(DEFAULTS.keys())

    def __init__(self, provider: str = "groq", model: Optional[str] = None):
        _override = os.getenv("FINSIGHT_LLM_OVERRIDE", "").strip().lower()
        if _override and _override in self.SUPPORTED_PROVIDERS and provider == "groq":
            provider = _override
            model = None
        if provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Provider '{provider}' inconnu. "
                f"Valeurs acceptees : {sorted(self.SUPPORTED_PROVIDERS)}"
            )
        self.provider = provider
        self.model = model or self.DEFAULTS[provider]
        self._client = None

    def generate(self, prompt: str, system: Optional[str] = None,
                 max_tokens: int = 1024) -> str:
        if self.provider == "anthropic":
            return self._call_anthropic(prompt, system, max_tokens)
        elif self.provider == "groq":
            return self._call_groq(prompt, system, max_tokens)
        elif self.provider == "openai":
            return self._call_openai(prompt, system, max_tokens)
        elif self.provider == "mistral":
            return self._call_mistral(prompt, system, max_tokens)
        elif self.provider == "cerebras":
            return self._call_cerebras(prompt, system, max_tokens)
        elif self.provider == "gemini":
            return self._call_gemini(prompt, system, max_tokens)
        elif self.provider == "ollama":
            return self._call_ollama(prompt, system, max_tokens)
        raise ValueError(f"Provider inconnu : {self.provider}")

    async def generate_async(self, prompt: str, system: Optional[str] = None,
                             max_tokens: int = 1024) -> str:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.generate(prompt, system, max_tokens))

    # ------------------------------------------------------------------
    # Implementations par provider
    # ------------------------------------------------------------------

    def _call_anthropic(self, prompt, system, max_tokens):
        if self._client is None:
            import anthropic
            _key = _get_secret("ANTHROPIC_API_KEY")
            if not _key or _key.startswith("sk-ant-api03-...") or len(_key) < 20:
                raise ValueError(
                    "[Anthropic] ANTHROPIC_API_KEY non configuree.")
            self._client = anthropic.Anthropic(api_key=_key)
        kwargs = {
            "model": self.model, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        response = self._client.messages.create(**kwargs)
        return response.content[0].text

    def _call_groq(self, prompt, system, max_tokens):
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
                _key = _rotator.get_key()
                _client = Groq(api_key=_key)
                response = _client.chat.completions.create(
                    model=self.model, messages=messages, max_tokens=max_tokens)
                _total = getattr(getattr(response, "usage", None),
                                 "total_tokens", max_tokens)
                _rotator.record(_total)
                return response.choices[0].message.content
            except _ProviderExhausted:
                raise   # skip-forward : bubble up pour que llm_call change de provider
            except Exception as e:
                _code = getattr(e, "status_code", None) or getattr(
                    getattr(e, "response", None), "status_code", None)
                _msg = str(e)
                if _code in (429, 503) or "rate_limit" in _msg.lower() or "overloaded" in _msg.lower():
                    if _attempt < len(_delays):
                        continue
                raise
        raise RuntimeError("[Groq] Echec apres 4 tentatives")

    def _call_openai(self, prompt, system, max_tokens):
        """OpenAI GPT-4o-mini avec rotation de cles TPD+TPM.

        Supporte OPENAI_API_KEY_1 et OPENAI_API_KEY_2 (rotation automatique
        selon le budget restant). Fallback sur OPENAI_API_KEY si pas de suffixe.
        """
        from openai import OpenAI
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        _delays = [5, 15, 30]
        for _attempt, _wait in enumerate([0] + _delays):
            if _wait:
                _log.warning(f"[OpenAI] Tentative {_attempt + 1}/4 — attente {_wait}s")
                time.sleep(_wait)
            try:
                _key = _openai_rotator.get_key()
                _client = OpenAI(api_key=_key)
                response = _client.chat.completions.create(
                    model=self.model, messages=messages, max_tokens=max_tokens)
                _total = getattr(getattr(response, "usage", None),
                                 "total_tokens", max_tokens)
                _openai_rotator.record(_total)
                return response.choices[0].message.content
            except _ProviderExhausted:
                raise
            except Exception as e:
                _code = getattr(e, "status_code", None) or getattr(
                    getattr(e, "response", None), "status_code", None)
                _msg = str(e)
                if _code in (429, 503) or "rate_limit" in _msg.lower() or "overloaded" in _msg.lower():
                    if _attempt < len(_delays):
                        continue
                raise
        raise RuntimeError("[OpenAI] Echec apres 4 tentatives")

    def _call_mistral(self, prompt, system, max_tokens):
        from mistralai.client import Mistral
        _key = _get_secret("MISTRAL_API_KEY")
        if not _key or len(_key) < 16:
            raise ValueError("[Mistral] MISTRAL_API_KEY non configuree.")
        client = Mistral(api_key=_key)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        _delays = [5, 15, 30]
        for _attempt, _wait in enumerate([0] + _delays):
            if _wait:
                _log.warning(f"[Mistral] Tentative {_attempt + 1}/4 — attente {_wait}s")
                time.sleep(_wait)
            try:
                response = client.chat.complete(
                    model=self.model, messages=messages, max_tokens=max_tokens)
                return response.choices[0].message.content
            except Exception as e:
                _code = getattr(e, "status_code", None) or getattr(
                    getattr(e, "response", None), "status_code", None)
                _msg = str(e)
                if _code in (429, 503) or "rate" in _msg.lower() or "too many" in _msg.lower():
                    if _attempt < len(_delays):
                        continue
                raise
        raise RuntimeError("[Mistral] Echec apres 4 tentatives")

    def _call_cerebras(self, prompt, system, max_tokens):
        from cerebras.cloud.sdk import Cerebras
        _key = _get_secret("CEREBRAS_API_KEY")
        if not _key or len(_key) < 16:
            raise ValueError("[Cerebras] CEREBRAS_API_KEY non configuree.")
        client = Cerebras(api_key=_key)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        _delays = [5, 15, 30]
        for _attempt, _wait in enumerate([0] + _delays):
            if _wait:
                _log.warning(f"[Cerebras] Tentative {_attempt + 1}/4 — attente {_wait}s")
                time.sleep(_wait)
            try:
                response = client.chat.completions.create(
                    model=self.model, messages=messages, max_tokens=max_tokens)
                return response.choices[0].message.content
            except Exception as e:
                _code = getattr(e, "status_code", None) or getattr(
                    getattr(e, "response", None), "status_code", None)
                _msg = str(e)
                if _code in (429, 503) or "rate" in _msg.lower() or "too many" in _msg.lower():
                    if _attempt < len(_delays):
                        continue
                raise
        raise RuntimeError("[Cerebras] Echec apres 4 tentatives")

    def _call_gemini(self, prompt, system, max_tokens):
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=_get_secret("GEMINI_API_KEY"))
            self._client = genai
        model = self._client.GenerativeModel(
            self.model, generation_config={"max_output_tokens": max_tokens})
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        response = model.generate_content(full_prompt)
        return response.text

    def _call_ollama(self, prompt, system, max_tokens):
        import ollama
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = ollama.chat(model=self.model, messages=messages)
        return response["message"]["content"]

    def __repr__(self):
        return f"LLMProvider(provider='{self.provider}', model='{self.model}')"


# ---------------------------------------------------------------------------
# llm_call(phase) : routing haut-niveau avec fallback skip-forward
# ---------------------------------------------------------------------------

# Chaines de providers par phase du pipeline (Baptiste 2026-04-14 : plan gratuit only)
#
# STRATEGIE : plan 100% gratuit tant que Baptiste n'a pas ajoute de budget OpenAI/
# Claude. Utilise Groq (rotation multi-cles a venir), Mistral (qualite FR top),
# Gemini (1M TPM gratuit), Cerebras (fallback), Anthropic (backup credits).
#
# OpenAI est code et fonctionnel mais retire des chaines par defaut : il se
# reactivera automatiquement si les cles OPENAI_API_KEY_1/_2 sont ajoutees
# dans .env ET qu'on remet "openai" dans la chaine.
_PHASE_CHAIN: dict[str, list[str]] = {
    # Petits prompts rapides : QA, devil advocate court, parsing, extraction
    # Groq primary (gratuit, rapide) -> Mistral -> Gemini -> Cerebras
    "short":    ["groq", "mistral", "gemini", "cerebras"],
    # Prompts longs analytiques : synthese, commentary, margin analysis, ratios
    # Mistral primary (qualite FR top, gratuit) -> Groq -> Gemini -> Cerebras
    "long":     ["mistral", "groq", "gemini", "cerebras"],
    # Prompts critiques finaux : these, conclusion, recommandation
    # Mistral primary (meilleur en FR) -> Gemini -> Groq -> Anthropic (backup)
    "critical": ["mistral", "gemini", "groq", "anthropic"],
    # Fallback par defaut (compat ancien code) : Groq -> Mistral -> Gemini -> etc.
    "default":  ["groq", "mistral", "gemini", "cerebras", "anthropic"],
}


def llm_call(prompt: str, phase: str = "default",
             system: Optional[str] = None, max_tokens: int = 1024,
             model: Optional[str] = None) -> str:
    """Appel LLM haut-niveau avec routing automatique par phase + fallback.

    Args:
        prompt : prompt utilisateur
        phase  : "short" | "long" | "critical" | "default"
                 Selection la chaine de providers la plus adaptee.
        system : message systeme optionnel
        max_tokens : budget tokens sortie
        model : override le modele par defaut du provider

    Returns:
        Texte genere

    Raises:
        RuntimeError si tous les providers de la chaine ont echoue.
    """
    chain = _PHASE_CHAIN.get(phase) or _PHASE_CHAIN["default"]
    errors = []
    for _provider in chain:
        try:
            _llm = LLMProvider(provider=_provider, model=model)
            return _llm.generate(prompt, system=system, max_tokens=max_tokens)
        except _ProviderExhausted as e:
            # Budget sature (TPD/TPM) — skip forward sans retry
            _log.warning(f"[llm_call:{phase}] {_provider} sature, skip: {e}")
            errors.append(f"{_provider}:exhausted")
            continue
        except Exception as e:
            _code = getattr(e, "status_code", None)
            _msg = str(e)[:150]
            _log.warning(f"[llm_call:{phase}] {_provider} echec ({_code}): {_msg}")
            errors.append(f"{_provider}:{_code or 'err'}")
            continue
    raise RuntimeError(
        f"[llm_call:{phase}] Tous les providers ont echoue : {', '.join(errors)}")


def llm_status() -> str:
    """Retourne un status resume des rotators pour diagnostic."""
    lines = ["=== LLM Provider Status ==="]
    lines.append("Groq :")
    try:
        lines.append(_rotator.status())
    except Exception as e:
        lines.append(f"  erreur : {e}")
    lines.append("OpenAI :")
    try:
        lines.append(_openai_rotator.status())
    except Exception as e:
        lines.append(f"  erreur : {e}")
    return "\n".join(lines)
