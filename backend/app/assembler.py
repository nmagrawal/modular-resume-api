"""
LAYER 4 rule: assemble a resume from a chosen role preset + the bank,
tailored to a JD. Encodes:

  - LAYER 1 instruction: "reorder within a module to mirror the JD's exact
    vocabulary"
  - LAYER 2/3 conditional bullet picks ("swap X in when Y appears in the
    JD", "X or Y, depending on the JD", "+X as a fourth")
  - LAYER 4 fixed shape: Header / Title / Summary / Skills / Experience
    (2x3) / Projects (4x2) / Education (last, or above Experience for the
    Evaluation-flavored preset)
  - Facts Ledger guard: every bullet is pulled verbatim by ID from the
    vetted bank, and the final text is checked against the "never appears
    again" banned-phrase list as a safety net.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from app import llm_selection
from app.parser import Bullet, Project, ResumeBank
from app.role_matcher import RoleScore, resolve_role
from app.scoring import relevance_score

EXPERIENCE_BULLETS_PER_ENTRY = 3
PROJECT_BULLETS_PER_ENTRY = 2



@dataclass
class BulletExpr:
    primary_ids: list[str]
    swap: tuple[str, str] | None = None       # (trigger_keyword, swap_in_id)
    alt_set: list[str] | None = None          # full alternate list, "or X·Y·Z, depending on..."
    alt_single: str | None = None             # single alt for the last primary slot, "(or X)"
    bonus_id: str | None = None               # "(+X as a fourth)" — noted, not used (fixed 3-bullet shape)


def parse_bullet_expr(expr: str) -> BulletExpr:
    m = re.match(r"^\s*([^(]+?)\s*(?:\((.+)\))?\s*$", expr.strip())
    primary_part = m.group(1) if m else expr
    paren = m.group(2) if m and m.group(2) else ""

    primary_ids = [x.strip() for x in primary_part.split("·") if x.strip()]

    swap = None
    swap_m = re.search(r"swap\s+([A-Z0-9\-]+)\s+in\s+when\s+(.+?)\s+appears in the JD", paren)
    if swap_m:
        swap = (swap_m.group(2).strip(), swap_m.group(1).strip())

    alt_set = None
    alt_set_m = re.search(r"\bor\s+([A-Z0-9\-·]+)\s*,\s*depending on", paren)
    if alt_set_m:
        alt_set = [x.strip() for x in alt_set_m.group(1).split("·") if x.strip()]

    alt_single = None
    if alt_set is None:
        alt_single_m = re.match(r"^or\s+([A-Z0-9\-]+)$", paren.strip())
        if alt_single_m:
            alt_single = alt_single_m.group(1).strip()

    bonus_id = None
    bonus_m = re.search(r"\+\s*([A-Z0-9\-]+)\s+(?:as a fourth|if a fourth fits)", paren)
    if bonus_m:
        bonus_id = bonus_m.group(1).strip()

    return BulletExpr(
        primary_ids=primary_ids, swap=swap, alt_set=alt_set,
        alt_single=alt_single, bonus_id=bonus_id,
    )


def select_bullets(
    expr: BulletExpr,
    target_count: int,
    bullet_texts: dict[str, str],
    jd_lower: str,
    jd_text: str | None = None,
) -> list[str]:
    def score(bid: str) -> float:
        return relevance_score(bullet_texts.get(bid, ""), jd_lower)

    candidates = list(expr.primary_ids)

    if expr.alt_set:
        primary_score = sum(score(i) for i in expr.primary_ids)
        alt_score = sum(score(i) for i in expr.alt_set)
        candidates = list(expr.alt_set if alt_score > primary_score else expr.primary_ids)

    if expr.alt_single and candidates:
        last_id = candidates[-1]
        if score(expr.alt_single) > score(last_id):
            candidates[-1] = expr.alt_single

    # A documented bonus ("+X as a fourth" / "+X if a fourth fits") is a real
    # candidate, not just a note — put it in the pool so it can actually be
    # picked, instead of being parsed and then silently ignored.
    if expr.bonus_id and expr.bonus_id not in candidates:
        candidates.append(expr.bonus_id)

    # Size to target_count BEFORE applying the forced swap below, so the
    # swap-in bullet can't be scored back out — "swap X in when Y appears in
    # the JD" is a hard rule, not a vote among candidates.
    if len(candidates) > target_count:
        llm_pick = None
        if llm_selection.is_enabled():
            pool = {bid: bullet_texts[bid] for bid in candidates if bid in bullet_texts}
            llm_pick = llm_selection.llm_select_bullets(jd_text or jd_lower, pool, target_count)
        if llm_pick is not None:
            candidates = llm_pick
        else:
            candidates.sort(key=lambda bid: -score(bid))
            candidates = candidates[:target_count]
    elif len(candidates) < target_count:
        remaining = [bid for bid in bullet_texts if bid not in candidates]
        remaining.sort(key=lambda bid: -score(bid))
        candidates.extend(remaining[: target_count - len(candidates)])

    if expr.swap:
        trigger, swap_id = expr.swap
        if trigger.lower() in jd_lower and swap_id not in candidates:
            if candidates:
                weakest = min(candidates, key=score)
                candidates[candidates.index(weakest)] = swap_id
            else:
                candidates.append(swap_id)

    return candidates


def parse_project_slot(raw: str) -> tuple[list[str], str | None]:
    raw = raw.strip()
    note = None
    note_m = re.search(r"\(([^)]+)\)", raw)
    if note_m:
        note = note_m.group(1)
        raw = (raw[: note_m.start()] + raw[note_m.end():]).strip()
    if " or " in raw:
        ids = [x.strip() for x in raw.split(" or ") if x.strip()]
    else:
        ids = [raw] if raw else []
    return ids, note


@dataclass
class AssembledExperienceEntry:
    entity: str
    display_title: str
    ledger_line: str | None
    bullets: list[Bullet]


@dataclass
class AssembledProjectEntry:
    project: Project
    note: str | None


@dataclass
class AssembledModule:
    id: str
    name: str
    skills: list[str]


def _contact_default(env_var: str, placeholder: str) -> str:
    """Contact info isn't resume-bank content (it's per-deployer config), so
    it comes from environment variables, not hardcoded source — that's what
    keeps this generic across anyone's deployment. Falls back to a visible
    placeholder rather than silently guessing."""
    return os.getenv(env_var, placeholder)


@dataclass
class ContactInfo:
    name: str = field(default_factory=lambda: _contact_default("RESUME_CONTACT_NAME", "[[NAME — set RESUME_CONTACT_NAME or pass `contact.name`]]"))
    location: str = field(default_factory=lambda: _contact_default("RESUME_CONTACT_LOCATION", "[[LOCATION]]"))
    email: str = field(default_factory=lambda: _contact_default("RESUME_CONTACT_EMAIL", "[[EMAIL]]"))
    phone: str = field(default_factory=lambda: _contact_default("RESUME_CONTACT_PHONE", "[[PHONE]]"))
    linkedin: str = field(default_factory=lambda: _contact_default("RESUME_CONTACT_LINKEDIN", "[[LINKEDIN]]"))
    github: str = field(default_factory=lambda: _contact_default("RESUME_CONTACT_GITHUB", "[[GITHUB]]"))
    site: str = field(default_factory=lambda: _contact_default("RESUME_CONTACT_SITE", "[[SITE]]"))


@dataclass
class AssembledResume:
    role: str
    role_scores: list[RoleScore]
    modules: list[AssembledModule]
    experience: list[AssembledExperienceEntry]
    projects: list[AssembledProjectEntry]
    education: list[str]
    education_above_experience: bool
    contact: ContactInfo
    warnings: list[str] = field(default_factory=list)
    markdown: str = ""


def reorder_skills_for_jd(skills: list[str], jd_lower: str) -> list[str]:
    return sorted(skills, key=lambda s: 0 if s.lower() in jd_lower else 1)


# Degree rows are detected generically (no hardcoded degree names) so this
# works for anyone's Facts Ledger, not just this bank's M.S./B.E. — see
# BANK_FORMAT.md's "Education" note.
DEGREE_KEYWORDS = (
    "m.s.", "m.a.", "b.s.", "b.a.", "b.e.", "ph.d.", "mba", "m.eng", "b.eng",
    "bachelor", "master", "doctorate", "associate degree",
)


def _education_rows(bank: ResumeBank) -> list[str]:
    rows = [
        f"{label} — {value}"
        for label, value in bank.facts.ledger_rows
        if any(kw in label.lower() for kw in DEGREE_KEYWORDS)
    ]
    if not rows:
        return ["[[No degree row detected in the FACTS LEDGER table — add one, e.g. `| M.S. Foo | University · Years |`]]"]
    return rows


def assemble(
    bank: ResumeBank,
    jd_text: str,
    role_hint: str | None = None,
    contact_overrides: dict | None = None,
) -> AssembledResume:
    role, role_scores = resolve_role(bank, jd_text, role_hint)
    preset = bank.role_presets[role]
    jd_lower = jd_text.lower()
    warnings: list[str] = []

    top = role_scores[0]
    if role_hint is None and top.score == 0 and top.semantic_score == 0:
        warnings.append(
            f"No keyword or semantic match found for any role preset — defaulted to "
            f"'{role}' (the first-listed preset) with zero confidence, not a real match. "
            f"This JD may be outside the bank's domain; consider passing an explicit "
            f"role_hint instead of trusting this pick."
        )

    modules_out: list[AssembledModule] = []
    for mid in preset.modules:
        mod = bank.modules.get(mid)
        if not mod:
            warnings.append(f"Module {mid} referenced by preset '{role}' but not found in bank.")
            continue
        modules_out.append(
            AssembledModule(id=mid, name=mod.name, skills=reorder_skills_for_jd(mod.skills, jd_lower))
        )

    # Bullet IDs have globally unique prefixes (OG, OG-PM, PP, RP, RP-PM, TE), but
    # a preset can reference an ID that's physically filed under a different
    # entity's section in the source bank (bullets reframing one job's work for
    # a different preset are sometimes filed under the OTHER job's heading).
    # Look bullet text up globally so an explicit pick always resolves.
    all_bullet_texts = {
        bid: b.text for bank_bullets in bank.bullet_banks.values() for bid, b in bank_bullets.items()
    }

    experience_out: list[AssembledExperienceEntry] = []
    for entity in preset.experience_entities:
        bullet_bank = bank.bullet_banks.get(entity)
        if bullet_bank is None:
            warnings.append(f"No bullet bank found for entity '{entity}' (role '{role}').")
            continue
        own_bullet_texts = {bid: b.text for bid, b in bullet_bank.items()}
        expr_raw = preset.entity_bullet_expr.get(entity)
        if expr_raw:
            expr = parse_bullet_expr(expr_raw)
            bullet_texts = all_bullet_texts
        else:
            warnings.append(
                f"Preset '{role}' names '{entity}' as an experience entity but the bank has no "
                f"explicit bullet list for it (source gap) — falling back to the {EXPERIENCE_BULLETS_PER_ENTRY} "
                f"most JD-relevant bullets from its bank."
            )
            expr = BulletExpr(primary_ids=[])
            bullet_texts = own_bullet_texts
        chosen_ids = select_bullets(expr, EXPERIENCE_BULLETS_PER_ENTRY, bullet_texts, jd_lower, jd_text)
        bullets = [Bullet(id=bid, text=bullet_texts[bid]) for bid in chosen_ids if bid in bullet_texts]
        experience_out.append(
            AssembledExperienceEntry(
                entity=entity,
                display_title=bank.entity_display_names.get(entity, entity),
                ledger_line=bank.facts.find_row(entity),
                bullets=bullets,
            )
        )

    project_slots = [s for s in preset.projects_expr.split("·") if s.strip()]
    projects_out: list[AssembledProjectEntry] = []
    for slot in project_slots:
        ids, note = parse_project_slot(slot)
        if not ids:
            continue
        if len(ids) > 1:
            def proj_score(pid: str) -> float:
                proj = bank.projects.get(pid)
                if not proj:
                    return 0.0
                return sum(relevance_score(b, jd_lower) for b in proj.bullets)
            ids.sort(key=lambda pid: -proj_score(pid))
        pid = ids[0]
        proj = bank.projects.get(pid)
        if not proj:
            warnings.append(f"Project {pid} referenced by preset '{role}' but not found in bank.")
            continue
        projects_out.append(AssembledProjectEntry(project=proj, note=note))

    contact = ContactInfo(**{**{}, **(contact_overrides or {})})
    education = _education_rows(bank)

    markdown = render_markdown(role, modules_out, experience_out, projects_out,
                                education, preset.education_above_experience, contact)

    banned_hits = [p for p in bank.facts.banned_phrases if p.lower() in markdown.lower()]
    if banned_hits:
        warnings.append(f"Banned phrase(s) from the Facts Ledger leaked into output: {banned_hits}")

    return AssembledResume(
        role=role,
        role_scores=role_scores,
        modules=modules_out,
        experience=experience_out,
        projects=projects_out,
        education=education,
        education_above_experience=preset.education_above_experience,
        contact=contact,
        warnings=warnings,
        markdown=markdown,
    )


def render_markdown(
    role: str,
    modules: list[AssembledModule],
    experience: list[AssembledExperienceEntry],
    projects: list[AssembledProjectEntry],
    education: list[str],
    education_above_experience: bool,
    contact: ContactInfo,
) -> str:
    lines: list[str] = []
    lines.append(f"# {contact.name}")
    lines.append(
        f"{contact.location} · {contact.email} · {contact.phone} · "
        f"{contact.linkedin} · {contact.github} · {contact.site}"
    )
    lines.append("")
    lines.append(f"## {role}")
    lines.append("")
    lines.append("[[3-line summary — pull from FINAL-PROFILE.md §2; not present in this bank]]")
    lines.append("")

    lines.append("## Skills")
    for mod in modules:
        lines.append(f"**{mod.name}**: {' · '.join(mod.skills)}")
    lines.append("")

    def experience_section() -> list[str]:
        out = ["## Experience"]
        for entry in experience:
            header = entry.display_title
            if entry.ledger_line:
                header += f" ({entry.ledger_line})"
            out.append(f"### {header}")
            for b in entry.bullets:
                out.append(f"- {b.text}")
            out.append("")
        return out

    def education_section() -> list[str]:
        return ["## Education", *(f"- {r}" for r in education), ""]

    if education_above_experience:
        lines.extend(education_section())
        lines.extend(experience_section())
    else:
        lines.extend(experience_section())

    lines.append("## Projects")
    for entry in projects:
        title = entry.project.name
        if entry.note:
            title += f" ({entry.note})"
        lines.append(f"### {title}")
        if entry.project.tech:
            lines.append(f"`{' · '.join(entry.project.tech)}`")
        for b in entry.project.bullets:
            lines.append(f"- {b}")
        lines.append("")

    if not education_above_experience:
        lines.extend(education_section())

    return "\n".join(lines).strip() + "\n"
