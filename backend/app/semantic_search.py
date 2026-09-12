"""
Semantic search — the upgrade path for scoring.py's keyword-overlap scorer.

This is where LangChain earns its place in this project: its `Embeddings`
interface is the same three methods (`embed_query`, `embed_documents`) across
OpenAI, Ollama (local, no API key), HuggingFace (local, no API key/no
network), and dozens more — exactly the "any API key or a local Ollama
model" ask, for the one job (embeddings) that doesn't already have a clean
built-in answer elsewhere in this codebase. CrewAI's own LLM routing (see
llm_config.py) already covers provider-agnostic *chat* models; this module
covers embeddings, which is a separate concern.

Fully optional: with no EMBEDDINGS_PROVIDER set, scoring.py's keyword
overlap is used exactly as before — nothing about the deterministic pipeline
requires this module to do anything.

Env vars:
  EMBEDDINGS_PROVIDER   openai | ollama | huggingface
  EMBEDDINGS_MODEL      provider-specific model name (sane default per provider)
  EMBEDDINGS_BASE_URL   optional — self-hosted Ollama endpoint
"""
from __future__ import annotations

import math
import os
from functools import lru_cache

_DEFAULT_MODELS = {
    "openai": "text-embedding-3-small",
    "ollama": "nomic-embed-text",
    "huggingface": "sentence-transformers/all-MiniLM-L6-v2",
}


def embeddings_configured() -> bool:
    return bool(os.getenv("EMBEDDINGS_PROVIDER"))


@lru_cache(maxsize=1)
def _get_embeddings():
    provider = os.getenv("EMBEDDINGS_PROVIDER")
    if not provider:
        return None
    model = os.getenv("EMBEDDINGS_MODEL") or _DEFAULT_MODELS.get(provider)

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model=model)

    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings
        base_url = os.getenv("EMBEDDINGS_BASE_URL") or os.getenv("OLLAMA_HOST")
        kwargs = {"model": model}
        if base_url:
            kwargs["base_url"] = base_url
        return OllamaEmbeddings(**kwargs)

    if provider == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name=model)

    raise ValueError(
        f"Unknown EMBEDDINGS_PROVIDER '{provider}' — use openai, ollama, or huggingface."
    )


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticScorer:
    """Embeds candidate texts once and caches them (they're static across a
    process's lifetime — the bank doesn't change mid-run), so a request only
    pays for one fresh embedding call: the incoming JD."""

    def __init__(self):
        self._embeddings = _get_embeddings()
        self._doc_cache: dict[str, list[float]] = {}

    @property
    def active(self) -> bool:
        return self._embeddings is not None

    def _embed_document(self, text: str) -> list[float]:
        if text not in self._doc_cache:
            self._doc_cache[text] = self._embeddings.embed_query(text)
        return self._doc_cache[text]

    def score(self, candidate_text: str, jd_text: str) -> float:
        """0..1ish relevance score (clamped cosine similarity)."""
        if not candidate_text.strip():
            return 0.0
        candidate_vec = self._embed_document(candidate_text)
        jd_vec = self._embed_document(jd_text)
        return max(0.0, _cosine(candidate_vec, jd_vec))


@lru_cache(maxsize=1)
def get_scorer() -> SemanticScorer:
    return SemanticScorer()
