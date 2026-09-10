"""
JD relevance scoring — keyword overlap by default, semantic (embeddings) when
EMBEDDINGS_PROVIDER is configured. `relevance_score` is the single swap point:
role_matcher.py and assembler.py both call through it, so neither needed to
change when semantic search was added — see semantic_search.py.
"""
from __future__ import annotations

import re

from app import semantic_search

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "with", "on",
    "at", "by", "from", "into", "your", "you", "their", "its", "this",
    "that", "as", "is", "are", "be", "will", "we", "our", "who", "have",
    "has", "not", "but", "than", "then", "over", "per", "via", "using",
}


def normalize(text: str) -> str:
    return text.lower()


def significant_tokens(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9+\-/]*", text.lower())
    return [w for w in words if len(w) > 2 and w not in STOPWORDS]


def phrase_hits(phrases: list[str], jd_lower: str) -> list[str]:
    """Returns the subset of `phrases` that literally appear in the JD text."""
    return [p for p in phrases if p.lower() in jd_lower]


def _keyword_relevance_score(candidate_text: str, jd_lower: str) -> float:
    """0..1 fraction of the candidate's significant tokens that show up in the JD."""
    tokens = set(significant_tokens(candidate_text))
    if not tokens:
        return 0.0
    hits = sum(1 for t in tokens if t in jd_lower)
    return hits / len(tokens)


def relevance_score(candidate_text: str, jd_lower: str) -> float:
    if semantic_search.embeddings_configured():
        return semantic_search.get_scorer().score(candidate_text, jd_lower)
    return _keyword_relevance_score(candidate_text, jd_lower)


def score_many(candidate_texts: dict[str, str], jd_lower: str) -> dict[str, float]:
    return {cid: relevance_score(text, jd_lower) for cid, text in candidate_texts.items()}
