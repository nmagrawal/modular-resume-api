"""
Optional LLM-assisted bullet selection.

Some role presets suggest more candidate bullets than the fixed shape uses —
either because the primary list itself has 4 (e.g. "OG17·OG20·OG22·OG24")
or because a bonus is offered ("+OG9 if a fourth fits"). Until now the
assembler either trimmed those down by keyword/semantic relevance
(scoring.py) or, for a documented bonus, ignored it outright. This module
lets a local or hosted LLM make that specific pick instead, when you want a
model actually reading the JD and the candidate bullets side by side rather
than a relevance score.

Off by default — set LLM_BULLET_SELECTION=true (and configure an LLM via
llm_config.py: LLM_PROVIDER/LLM_MODEL, e.g. LLM_PROVIDER=ollama). The
deterministic /generate-resume endpoint makes zero network calls otherwise;
turning this on is an explicit choice, not a side effect of also having
LLM_PROVIDER set for the separate /generate-resume/ai summary layer.

Defense in depth, same principle as crew_agents.py's deterministic guard:
the LLM's pick is validated in code (right count, IDs actually in the
candidate pool) before it's trusted. Any failure — not configured, call
error, malformed/invalid response — returns None, and the caller falls back
to the existing relevance-score trim. This is never the sole decision-maker.
"""
from __future__ import annotations

import os

from pydantic import BaseModel

from app import llm_config


def is_enabled() -> bool:
    return os.getenv("LLM_BULLET_SELECTION", "").strip().lower() in ("1", "true", "yes")


class _BulletPick(BaseModel):
    bullet_ids: list[str]


def llm_select_bullets(
    jd_text: str,
    candidates: dict[str, str],
    target_count: int,
) -> list[str] | None:
    """Returns exactly `target_count` IDs chosen from `candidates` by an LLM,
    or None if unavailable/untrustworthy — callers must have a deterministic
    fallback ready and must not treat None as an error."""
    llm = llm_config.build_llm()
    if llm is None:
        return None

    listing = "\n".join(f"- {bid}: {text}" for bid, text in candidates.items())
    prompt = (
        f"Job description:\n{jd_text}\n\n"
        f"Candidate resume bullets (choose only from these IDs):\n{listing}\n\n"
        f"Pick exactly {target_count} of these bullet IDs — whichever are most "
        f"relevant to the job description above. Return only IDs that appear in "
        f"the list."
    )

    try:
        result = llm.call(prompt, response_model=_BulletPick)
    except Exception:
        return None

    seen: set[str] = set()
    valid_ordered = [
        bid for bid in result.bullet_ids
        if bid in candidates and not (bid in seen or seen.add(bid))
    ]
    if len(valid_ordered) < target_count:
        return None
    return valid_ordered[:target_count]
