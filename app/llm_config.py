"""
Provider-agnostic LLM configuration for the CrewAI summary-writing layer
(app/crew_agents.py).

CrewAI's own `Agent(llm=...)` is backed by LiteLLM under the hood — it does
NOT actually call a LangChain chat model's `.invoke()` if you hand it one;
it just reads a couple of attributes off the object and rebuilds its own
`crewai.LLM` from them. So the reliable way to get "any provider or a local
Ollama model" into CrewAI is LiteLLM's own model-string convention, not a
LangChain object. (LangChain is used instead in semantic_search.py, where
it's a genuine unique fit — see that module's docstring.)

Env vars:
  LLM_PROVIDER   openai | anthropic | ollama | groq | together | mistral | ...
                 (any LiteLLM-supported provider; see docs.litellm.ai/docs/providers)
  LLM_MODEL      bare model name, e.g. "gpt-4o-mini", "claude-3-5-sonnet-20241022",
                 "llama3.1"
  LLM_BASE_URL   optional — self-hosted Ollama / OpenAI-compatible endpoint
  LLM_API_KEY    optional — generic override; providers otherwise read their
                 usual env var (OPENAI_API_KEY, ANTHROPIC_API_KEY, ...)

If LLM_PROVIDER/LLM_MODEL aren't set, we auto-detect from whichever
provider-specific API key is already present, so "just set OPENAI_API_KEY"
keeps working without extra config.
"""
from __future__ import annotations

import os

# provider -> (litellm prefix or None if bare model name is enough, default model)
_PROVIDER_DEFAULTS: dict[str, tuple[str | None, str]] = {
    "openai": (None, "gpt-4o-mini"),
    "anthropic": ("anthropic", "claude-3-5-sonnet-20241022"),
    "ollama": ("ollama_chat", "llama3.1"),
    "groq": ("groq", "llama-3.1-70b-versatile"),
    "together": ("together_ai", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
    "mistral": ("mistral", "mistral-large-latest"),
}

_AUTO_DETECT_ENV_KEYS = {
    "OPENAI_API_KEY": "openai",
    "ANTHROPIC_API_KEY": "anthropic",
    "GROQ_API_KEY": "groq",
    "TOGETHER_API_KEY": "together",
    "MISTRAL_API_KEY": "mistral",
}


def _detect_provider() -> str | None:
    for env_key, provider in _AUTO_DETECT_ENV_KEYS.items():
        if os.getenv(env_key):
            return provider
    if os.getenv("LLM_BASE_URL") or os.getenv("OLLAMA_HOST"):
        return "ollama"
    return None


def resolve_model_string() -> str | None:
    """Returns a LiteLLM-format model string (e.g. "ollama_chat/llama3.1",
    "anthropic/claude-3-5-sonnet-20241022", "gpt-4o-mini"), or None if
    nothing is configured."""
    provider = os.getenv("LLM_PROVIDER") or _detect_provider()
    if not provider:
        return None

    prefix, default_model = _PROVIDER_DEFAULTS.get(provider, (provider, ""))
    model = os.getenv("LLM_MODEL") or default_model
    if not model:
        return None
    return f"{prefix}/{model}" if prefix else model


def is_llm_configured() -> bool:
    return resolve_model_string() is not None


def build_llm():
    """Returns a configured crewai.LLM, or None if nothing is set up."""
    model_string = resolve_model_string()
    if not model_string:
        return None

    from crewai import LLM

    kwargs: dict[str, str] = {"model": model_string}
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OLLAMA_HOST")
    if base_url:
        kwargs["base_url"] = base_url
    api_key = os.getenv("LLM_API_KEY")
    if api_key:
        kwargs["api_key"] = api_key
    return LLM(**kwargs)
