"""
LAYER 3 rule: pick the role preset a JD best matches.

Score each preset by how many of its modules' skill phrases appear in the
JD text (its "Module selection by role" wiring from LAYER 1), plus any
explicit "Targets JDs naming: ..." hints called out in that preset's notes
in LAYER 3. Ties fall back to source order (Applied AI Engineer is listed
first and marked "default, highest volume").

The keyword score stays the primary signal on purpose — `matched_keywords`
is genuinely useful, human-inspectable output. When EMBEDDINGS_PROVIDER is
configured, a semantic similarity score (JD vs. that role's full skill list)
is added as a tie-breaking bonus, for JDs that paraphrase rather than name
your exact module vocabulary. It never overrides a clear keyword win.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app import semantic_search
from app.parser import ResumeBank
from app.scoring import normalize, phrase_hits

SEMANTIC_TIEBREAK_WEIGHT = 0.999  # keyword score always dominates; this only breaks ties


@dataclass
class RoleScore:
    role: str
    score: int
    matched_keywords: list[str]
    semantic_score: float = 0.0


def _role_keywords(bank: ResumeBank, role: str) -> list[str]:
    keywords: list[str] = [role]
    for mod_id in bank.modules_by_role.get(role, []):
        module = bank.modules.get(mod_id)
        if module:
            keywords.extend(module.skills)
    preset = bank.role_presets.get(role)
    if preset:
        hint_text = " ".join(preset.notes)
        m = re.search(r"Targets JDs naming:\s*(.+)", hint_text)
        if m:
            keywords.extend(p.strip(" .") for p in m.group(1).split(","))
    seen = set()
    deduped = []
    for k in keywords:
        kl = k.lower()
        if kl not in seen:
            seen.add(kl)
            deduped.append(k)
    return deduped


def score_roles(bank: ResumeBank, jd_text: str) -> list[RoleScore]:
    jd_lower = normalize(jd_text)
    semantic_on = semantic_search.embeddings_configured()
    results = []
    for role in bank.role_presets:
        keywords = _role_keywords(bank, role)
        matched = phrase_hits(keywords, jd_lower)
        semantic_bonus = 0.0
        if semantic_on:
            semantic_bonus = semantic_search.get_scorer().score(" ".join(keywords), jd_text)
        results.append(
            RoleScore(role=role, score=len(matched), matched_keywords=matched, semantic_score=semantic_bonus)
        )
    # Stable sort by (keyword score, semantic tiebreak) desc, then source order.
    order = {role: i for i, role in enumerate(bank.role_presets)}
    results.sort(key=lambda r: (-(r.score + r.semantic_score * SEMANTIC_TIEBREAK_WEIGHT), order[r.role]))
    return results


def resolve_role(bank: ResumeBank, jd_text: str, role_hint: str | None) -> tuple[str, list[RoleScore]]:
    scores = score_roles(bank, jd_text)
    if role_hint:
        hint_lower = role_hint.strip().lower()
        for role in bank.role_presets:
            if role.lower() == hint_lower:
                return role, scores
        for role in bank.role_presets:
            if hint_lower in role.lower():
                return role, scores
        raise ValueError(
            f"role_hint '{role_hint}' does not match any role preset: "
            f"{sorted(bank.role_presets.keys())}"
        )
    return scores[0].role, scores
