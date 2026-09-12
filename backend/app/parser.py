"""
Parses a "modular resume bank" markdown file into structured data.

This parser is generic — it doesn't know your company names or role titles.
It only knows the structural conventions documented in BANK_FORMAT.md
(section headers, module blocks, `- **ID** text` bullets, the `[Alias]`
entity-heading convention, role-preset bold labels, and the facts-ledger
tables). Any bank file that follows that spec parses the same way.

Which file gets read is controlled by the RESUME_BANK_PATH environment
variable (see _resolve_bank_path below); it defaults to
2-FINAL-MODULAR-RESUME-BANK.md in the project root for this repo's own bank.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DEFAULT_BANK_FILENAME = "example-resume-bank.md"
DEFAULT_BANK_PATH = Path(__file__).resolve().parent.parent / DEFAULT_BANK_FILENAME

ENTITY_ID_PREFIXES = ("OG", "PP", "RP", "TE")


def resolve_bank_path() -> Path:
    """RESUME_BANK_PATH, if set, wins — this is how someone else's bank file
    gets used without touching any code."""
    env_path = os.getenv("RESUME_BANK_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return DEFAULT_BANK_PATH


@dataclass
class SkillModule:
    id: str
    name: str
    skills: list[str]
    note: str = ""


@dataclass
class Bullet:
    id: str
    text: str


@dataclass
class Project:
    id: str
    name: str
    tech: list[str]
    bullets: list[str]
    note: str = ""


@dataclass
class RolePreset:
    name: str
    raw: str
    modules: list[str]
    experience_entities: list[str]
    entity_bullet_expr: dict[str, str]  # entity name -> raw bullet expression (with conditionals)
    projects_expr: str  # raw "PR-A · PR-B · PR-C or PR-D" expression
    education_above_experience: bool
    notes: list[str] = field(default_factory=list)


@dataclass
class FactsLedger:
    defensible_numbers: list[str]
    banned_phrases: list[str]
    ledger_rows: list[tuple[str, str]] = field(default_factory=list)

    def find_row(self, label_substring: str) -> str | None:
        needle = label_substring.lower()
        for label, value in self.ledger_rows:
            if needle in label.lower():
                return value
        return None


@dataclass
class ResumeBank:
    modules: dict[str, SkillModule]
    modules_by_role: dict[str, list[str]]
    bullet_banks: dict[str, dict[str, Bullet]]  # alias -> {id: Bullet}
    entity_display_names: dict[str, str]  # alias -> full heading text, e.g. "TechCorp Inc."
    projects: dict[str, Project]
    role_presets: dict[str, RolePreset]
    facts: FactsLedger


def _get_section(text: str, header: str, next_headers: list[str]) -> str:
    start = text.index(header) + len(header)
    end = len(text)
    for h in next_headers:
        idx = text.find(h, start)
        if idx != -1:
            end = min(end, idx)
    return text[start:end]


def _split_top_sections(text: str) -> dict[str, str]:
    pattern = r"^#{1,2} (LAYER \d.*|FACTS LEDGER.*|OPEN.*)$"
    sections: dict[str, str] = {}
    matches = list(re.finditer(pattern, text, re.M))
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[name] = text[start:end]
    return sections


def _parse_modules(layer1_text: str) -> tuple[dict[str, SkillModule], dict[str, list[str]]]:
    if "### Module selection by role" in layer1_text:
        modules_part, table_part = layer1_text.split("### Module selection by role", 1)
    else:
        modules_part, table_part = layer1_text, ""

    modules: dict[str, SkillModule] = {}
    for m in re.finditer(
        r"\*\*(M\d+)\s*·\s*([^*]+?)\*\*([^\n]*)\n(.*?)(?=\n\*\*M\d+\s*·|\Z)",
        modules_part,
        re.S,
    ):
        mod_id, name, note_raw, body = m.groups()
        note = re.sub(r"[*()←]", "", note_raw).strip()
        skills_flat = re.sub(r"\s+", " ", body).strip()
        skills = [s.strip() for s in skills_flat.split("·") if s.strip()]
        modules[mod_id] = SkillModule(id=mod_id, name=name.strip(), skills=skills, note=note)

    modules_by_role: dict[str, list[str]] = {}
    for row in re.finditer(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$", table_part, re.M):
        role, mods = row.groups()
        if role.strip().lower() in ("role", "---") or set(role.strip()) <= {"-"}:
            continue
        mod_ids = re.findall(r"M\d+", mods)
        if mod_ids:
            modules_by_role[_normalize_role_name(role.strip())] = mod_ids

    return modules, modules_by_role


def _parse_bullet_block(text: str) -> dict[str, str]:
    """Parses '- **ID** text...' bullets, joining wrapped lines."""
    bullets: dict[str, list[str]] = {}
    current_id: str | None = None
    for line in text.splitlines():
        m = re.match(r"-\s+\*\*([A-Z][A-Z0-9\-]*)\*\*\s*(.*)", line)
        if m:
            current_id = m.group(1)
            bullets[current_id] = [m.group(2).strip()]
        elif current_id and line.strip() and not re.match(r"\s*\*[^*]", line):
            bullets[current_id].append(line.strip())
        elif not line.strip():
            continue
    return {k: " ".join(v).strip() for k, v in bullets.items()}


ENTITY_ALIAS_RE = re.compile(r"\[([^\]]+)\]")


def _entity_alias_and_display(heading_text: str) -> tuple[str, str]:
    """Per BANK_FORMAT.md: an entity heading may declare its canonical alias
    in [brackets] — this is the name used to reference it from Role Presets'
    bold labels. The display name (what actually renders on the resume) is
    everything before the alias brackets / before the first em-dash-en-dash-
    hyphen separator. Without brackets, alias == display name."""
    alias_m = ENTITY_ALIAS_RE.search(heading_text)
    if alias_m:
        display = heading_text[: alias_m.start()].strip()
        return alias_m.group(1).strip(), display
    display = re.split(r"\s+[—–-]\s+", heading_text)[0].strip()
    return display, display


def _parse_bullet_banks(
    layer2_text: str,
) -> tuple[dict[str, dict[str, Bullet]], dict[str, str]]:
    """Generic: any `## ` heading in LAYER 2 is an entity bullet bank EXCEPT
    the one whose text contains "PROJECT BANK" (that's parsed separately by
    _parse_projects). No company/role names are hardcoded here — anyone's
    bank works as long as headings follow the [Alias] convention."""
    headings = list(re.finditer(r"^## (.+)$", layer2_text, re.M))
    banks: dict[str, dict[str, Bullet]] = {}
    display_names: dict[str, str] = {}
    for i, m in enumerate(headings):
        heading_text = m.group(1).strip()
        if "PROJECT BANK" in heading_text.upper():
            continue
        alias, display = _entity_alias_and_display(heading_text)
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(layer2_text)
        section_text = layer2_text[start:end]
        raw_bullets = _parse_bullet_block(section_text)
        banks[alias] = {k: Bullet(id=k, text=v) for k, v in raw_bullets.items()}
        display_names[alias] = display
    return banks, display_names


def _parse_projects(layer2_text: str) -> dict[str, Project]:
    m = re.search(r"## PROJECT BANK.*?\n", layer2_text)
    if not m:
        return {}
    project_text = layer2_text[m.end():]
    next_layer = re.search(r"\n---\n", project_text)
    if next_layer:
        project_text = project_text[: next_layer.start()]

    projects: dict[str, Project] = {}
    blocks = re.split(r"\n(?=\*\*PR-)", project_text)
    for block in blocks:
        header_match = re.match(r"\*\*(PR-[A-Z]+)\s*·\s*(.+?)\*\*(.*)", block)
        if not header_match:
            continue
        pid, name, trailer = header_match.groups()
        tech_match = re.search(r"`([^`]+)`", block, re.S)
        tech = []
        if tech_match:
            tech_flat = re.sub(r"\s+", " ", tech_match.group(1))
            tech = [t.strip() for t in tech_flat.split("·") if t.strip()]

        bullet_lines = re.findall(
            r"^-\s+(.+(?:\n(?!\s*-\s|\*\*PR-)[^\n]+)*)", block, re.M
        )
        bullets = [re.sub(r"\s+", " ", b).strip() for b in bullet_lines]
        note = re.sub(r"[*()]", "", trailer.replace("←", "")).strip()
        projects[pid] = Project(id=pid, name=name.strip(), tech=tech, bullets=bullets, note=note)
    return projects


LABEL_RE = re.compile(r"\*\*([A-Za-z][A-Za-z /]{1,20}?)\*\*")


def _normalize_role_name(title_line: str) -> str:
    name = title_line.split("←")[0]
    name = re.sub(r"\*\([^)]*\)\*", "", name)
    return name.strip()


def _clean_entity_name(entity: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", entity).strip()


def _parse_role_presets(layer3_text: str) -> dict[str, RolePreset]:
    blocks = re.split(r"\n(?=### )", layer3_text)
    presets: dict[str, RolePreset] = {}
    for block in blocks:
        header_match = re.match(r"### (.+)", block)
        if not header_match:
            continue
        name = _normalize_role_name(header_match.group(1))

        body_end = len(block)
        for marker in ("\n### ", "\n---"):
            idx = block.find(marker, 1)
            if idx != -1:
                body_end = min(body_end, idx)
        body = block[header_match.end():body_end]

        notes = re.findall(r"^>\s*(.+)$", body, re.M)
        notes = [n.strip() for n in notes]

        education_above_experience = "Education above Experience" in body

        flat = re.sub(r"\n>.*", "", body)
        # Strip shared cross-preset asides that aren't part of this preset's fields.
        flat = re.sub(r"\*\*Large-company.*?instead\.", "", flat, flags=re.S)
        flat = re.sub(r"·?\s*Education above Experience\s*·?", " · ", flat)
        flat = re.sub(r"\s+", " ", flat).strip()

        label_matches = list(LABEL_RE.finditer(flat))
        fields: dict[str, str] = {}
        for i, lm in enumerate(label_matches):
            label = lm.group(1).strip()
            val_start = lm.end()
            val_end = label_matches[i + 1].start() if i + 1 < len(label_matches) else len(flat)
            value = flat[val_start:val_end].strip(" ·")
            fields[label] = value

        modules = [mid.strip() for mid in re.findall(r"M\d+", fields.get("Modules", ""))]
        experience_raw = fields.get("Experience", "")
        experience_entities = [
            _clean_entity_name(e) for e in re.split(r"\+", experience_raw) if e.strip()
        ]

        entity_bullet_expr: dict[str, str] = {}
        for entity in experience_entities:
            if entity in fields:
                entity_bullet_expr[entity] = fields[entity]

        projects_expr = fields.get("Projects", "")

        presets[name] = RolePreset(
            name=name,
            raw=body,
            modules=modules,
            experience_entities=experience_entities,
            entity_bullet_expr=entity_bullet_expr,
            projects_expr=projects_expr,
            education_above_experience=education_above_experience,
            notes=notes,
        )
    return presets


def _parse_facts(facts_text: str) -> FactsLedger:
    # Parse only the FIRST contiguous markdown table (a run of "| ... |"
    # lines with no blank line between them). A bank may have a second,
    # differently-shaped table further down (e.g. a "systems shipped"
    # table) — that's presentational content, not ledger rows, and this
    # boundary is generic rather than hunting for any particular bank's
    # own bold-header text.
    table_start = re.search(r"^\|", facts_text, re.M)
    if table_start:
        rest = facts_text[table_start.start():]
        blank_line = re.search(r"\n[ \t]*\n", rest)
        table_text = rest[: blank_line.start()] if blank_line else rest
    else:
        table_text = ""
    # Line-by-line, not one cross-line regex: a table header row with empty
    # cells ("| | |" — completely standard, valid markdown) has no non-
    # whitespace content for a capture group to grab on its own line, which
    # let `\s*` silently bridge into the next line and merge two rows into
    # one bogus row. Splitting each line on "|" avoids that entirely.
    ledger_rows: list[tuple[str, str]] = []
    for line in table_text.splitlines():
        line = line.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        label, value = cells[0], cells[1]
        if not label or not value:
            continue  # header row, e.g. "| | |"
        if re.fullmatch(r"[-:\s]+", label) or re.fullmatch(r"[-:\s]+", value):
            continue  # separator row, e.g. "|---|---|"
        ledger_rows.append((label, value))

    numbers_match = re.search(
        r"\*\*Defensible numbers\*\*.*?:\s*(.*?)\n\n", facts_text, re.S
    )
    defensible_numbers: list[str] = []
    if numbers_match:
        raw = re.sub(r"\s+", " ", numbers_match.group(1))
        defensible_numbers = [n.strip(" .") for n in raw.split("·") if n.strip(" .")]

    banned_match = re.search(
        r"\*\*Never appears, anywhere, again:?\*\*:?\s*(.*?)\n\n", facts_text, re.S
    )
    banned_phrases: list[str] = []
    if banned_match:
        raw = re.sub(r"\s+", " ", banned_match.group(1))
        banned_phrases = [
            p.strip(' ."') for p in raw.split("·") if p.strip(' ."')
        ]

    return FactsLedger(
        defensible_numbers=defensible_numbers,
        banned_phrases=banned_phrases,
        ledger_rows=ledger_rows,
    )


def parse_bank(path: Path | None = None) -> ResumeBank:
    path = path or resolve_bank_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Resume bank not found at {path}. Set RESUME_BANK_PATH to point at your "
            f"modular resume bank markdown file (see BANK_FORMAT.md)."
        )
    text = path.read_text(encoding="utf-8")
    sections = _split_top_sections(text)

    layer1 = sections.get("LAYER 1 — SKILL MODULES", "")
    layer2 = sections.get("LAYER 2 — EXPERIENCE & PROJECT BANK", "")
    layer3 = sections.get("LAYER 3 — ROLE PRESETS", "")
    facts_text = sections.get("FACTS LEDGER", "")

    modules, modules_by_role = _parse_modules(layer1)
    bullet_banks, entity_display_names = _parse_bullet_banks(layer2)
    projects = _parse_projects(layer2)
    role_presets = _parse_role_presets(layer3)
    facts = _parse_facts(facts_text)

    return ResumeBank(
        modules=modules,
        modules_by_role=modules_by_role,
        bullet_banks=bullet_banks,
        entity_display_names=entity_display_names,
        projects=projects,
        role_presets=role_presets,
        facts=facts,
    )


@lru_cache(maxsize=1)
def get_bank() -> ResumeBank:
    return parse_bank()
