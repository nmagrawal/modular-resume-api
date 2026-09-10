# Modular Resume Bank — Format Rules

This is the spec the parser (`app/parser.py`) actually implements. Follow it
and the API works with **any** person's resume bank — nothing in the parser
is hardcoded to a specific name, company, or role.

A conforming bank file has five sections, in order, each starting with a
`#` or `##` heading matched **literally** (case-sensitive, exact text
before any trailing note):

```
## FACTS LEDGER
# LAYER 1 — SKILL MODULES
# LAYER 2 — EXPERIENCE & PROJECT BANK
# LAYER 3 — ROLE PRESETS
# LAYER 4 — RESUME ASSEMBLY RULES        (optional — human-readable only, not parsed)
```

Anything outside these five (a title, a `LAYER 5 — BUILD QUEUE`, an `OPEN`
section, prose asides) is ignored by the parser — put whatever you want
there.

---

## 1. `## FACTS LEDGER`

Two things are extracted from this section:

**a) A `| label | value |` table**, right after the heading:

```
| B.S. Computer Science | State University · 2016–2020 |
| TechCorp Inc. | Jan 2022 – Present · Senior Backend Engineer |
```

No header row is required. Each row becomes a `(label, value)` pair the
assembler can look up by substring (e.g. it finds your `M.S.` row for the
Education section, and an entity's row — matched against its `[Alias]`,
see §3 — for the "(dates · title)" suffix on each Experience heading).
Stop the table with a blank line before the next `**bold**` line.

**b) Two `**bold**`-labeled lists**, anywhere after the table, each a
`·`-separated line (may wrap across lines) ending in a blank line:

```
**Defensible numbers** — the only ones you ever use:
2M+ requests/day handled · 15 microservices owned · 40 engineers onboarded.

**Never appears, anywhere, again:**
"10x engineer" · "rockstar developer" · any invented percentage claims.
```

`defensible_numbers` and `banned_phrases` are parsed from these. The
assembler checks the final assembled markdown against `banned_phrases` and
adds a warning (never a silent failure) if one leaks through — it shouldn't,
since every bullet is pulled verbatim by ID, but it's a safety net.

---

## 2. `# LAYER 1 — SKILL MODULES`

**Module blocks**, one per module:

```
**M1 · Core Engineering**
Python · FastAPI · Docker · CI/CD · Git

**M2 · LLM & Agent Engineering** ← *deepest module*
LangGraph · MCP · Tool Calling · Structured Outputs
```

Rules:
- The ID must match `M\d+` (`M1`, `M2`, ... `M12`, ...).
- Everything after `**<ID> · <Name>**` on that same line (a `← *note*` or
  `*(note)*` aside) is captured as an optional note but otherwise ignored.
- Skills are `·`-separated and may wrap across multiple lines; they end at
  the next `**M<n> ·` block.

**Then, anywhere after the module blocks**, an (optional but recommended)
table wiring modules to your role presets — this is what lets the API
auto-classify a JD without you specifying a role every time:

```
### Module selection by role

| Role | Modules |
|---|---|
| Applied AI Engineer | M1 · M2 · M3 · M4 · M5 |
```

The `Role` column text must exactly match a role preset's name in LAYER 3
(see §4) — annotations like `*(new)*` or a trailing `← note` are stripped
automatically on both sides, so they don't need to match exactly.

---

## 3. `# LAYER 2 — EXPERIENCE & PROJECT BANK`

This section holds two kinds of subsections, told apart only by whether the
heading text contains the literal words `PROJECT BANK`.

### 3a. Experience bullet banks

**Every other `## ` heading in this section is treated as one experience
entity.** There's no fixed list of allowed entity names — add as many as you
want (jobs, advisory roles, teaching, freelance, whatever).

```
## TechCorp Inc. [TechCorp] — bullet bank (pick 3–4)
- **TC1** Led backend API development for a platform serving 2M+ requests/day...
- **TC2** Built event-driven data pipelines using message queues...
```

Rules:
- Heading format: `## <Display Name> [<Alias>] — <anything>`. The
  `[Alias]` is **required whenever the display name isn't itself the short
  name you'll reference in Role Presets** — e.g. display name "TechCorp Inc."
  but you'll write `**TechCorp**` in LAYER 3, so the heading needs
  `[TechCorp]`. If you omit the brackets, the alias defaults to the text
  before the first em-dash/en-dash/hyphen (`"StartupCo — bullet bank"` →
  alias `StartupCo`, no brackets needed there).
- Bullets are `- **ID** text...`, one per bullet, IDs unique across the
  *entire* bank (not just within one entity) — pick a short prefix per
  entity (`TC1`, `SC1`, `TC-PM1`, ...) and never reuse an ID. Bullet text may
  wrap across lines (joined with spaces); a line starting with a single `*`
  (an italic subheading like `*Ownership & scope*`) is skipped, not appended
  to the bullet.
- A bullet ID can physically live under a different entity's heading than
  the one that ultimately uses it — the parser resolves bullet IDs globally,
  so e.g. PM-flavored reframes of one job's bullets can sit under a
  different entity's section if that's how you organized it.

### 3b. Project bank

```
## PROJECT BANK — two bullets each, pick 4

**PR-API · Internal API Gateway** ← *flagship*
`Python · gRPC · Docker`
- Built an internal API gateway handling auth, rate limiting, and routing...
- Reduced cross-service latency by consolidating duplicate auth logic...
```

Rules:
- The heading must contain `PROJECT BANK`.
- Each project starts with `**<PR-ID> · <Name>**`, ID matching `PR-[A-Z]+`.
  A trailing `← *note*` or `(...)` after the name is kept as a display note.
- One optional backtick-fenced tech-tag line, `·`-separated.
- Then plain `- ` bullets (no `**ID**` prefix needed — the project ID is
  the addressable unit, not each bullet) until the next `**PR-` block.

---

## 4. `# LAYER 3 — ROLE PRESETS`

One block per role, in this exact bold-label sequence:

```
### Backend Engineer ← default, highest volume
**Modules** M1·M2 · **Experience** TechCorp + StartupCo ·
**TechCorp** TC1·TC2·TC3 (swap TC4 in when Kubernetes appears in the JD) ·
**StartupCo** SC1·SC2·SC3 · **Projects** PR-API · PR-CHAT · PR-INFRA · PR-ML or PR-DASH
```

Rules:
- `### <Role Name>` — a trailing `← note` is stripped for matching purposes;
  this exact name (minus the note) is the `role_hint` value the API accepts
  and the key used everywhere in responses.
- `**Modules**` — a `·`-separated list of module IDs from LAYER 1.
- `**Experience**` — entity aliases (matching §3a's `[Alias]`) joined with
  `+`, e.g. `TechCorp + StartupCo`.
- One `**<Alias>**` field per entity named in Experience, giving that
  entity's bullet-ID expression. Supported conditional grammar (all
  optional, evaluated against the incoming JD text):
  - `ID1·ID2·ID3` — plain pick, used as-is.
  - `ID1·ID2·ID3 (swap ID4 in when <keyword> appears in the JD)` — forces
    `ID4` into the final pick, replacing the weakest-scoring of the primary
    IDs, whenever `<keyword>` (case-insensitive substring) appears in the JD.
  - `ID1·ID2·ID3 (or ID4·ID5·ID6, depending on the JD)` — two full
    alternative sets; whichever set's bullets have higher aggregate
    relevance to the JD is used.
  - `ID1·ID2·ID3 (or ID4)` — a single alternative for the last slot; swapped
    in only if it scores higher against the JD than the slot it'd replace.
  - `ID1·ID2·ID3 (+ID4 as a fourth)` / `(+ID4 if a fourth fits)` — `ID4`
    joins the primary IDs as a real, selectable candidate (the experience
    shape stays a fixed 3 bullets, per §5 — this doesn't add a 4th slot, it
    adds a 4th *option* for the existing 3 slots). Which of the 4 candidates
    fills the 3 slots is decided the same way any other over-sized candidate
    pool is: by relevance score, or — if `LLM_BULLET_SELECTION=true` — by
    the configured chat model reading the JD and the candidate bullets
    directly. See the README's "LLM-assisted bullet selection."
  - If an entity is named in `**Experience**` but has no matching
    `**<Alias>**` field at all, the API doesn't fail — it falls back to that
    entity's most JD-relevant bullets and adds a warning to the response
    (useful for catching a documentation gap, which is exactly what this
    caught in the original bank).
- `**Projects**` — a `·`-separated list of project-slot expressions.
  Each slot is one `PR-ID`, optionally with `<note in parens>`, optionally
  `PR-IDA or PR-IDB` for a JD-scored choice between two projects.
- Any `> blockquote` lines in the block are captured as free-text `notes`
  (surfaced via `GET /roles`) — use them for your own "honest read" caveats;
  they aren't otherwise interpreted.
- The literal phrase `Education above Experience` anywhere in the block
  flips that preset's layout to put Education before Experience in the
  rendered resume (LAYER 4's documented exception for evaluation-flavored
  presets). Everything else renders Education last.

---

## 5. `# LAYER 4 — RESUME ASSEMBLY RULES`

This section is **not parsed** — it's a human-readable description of the
fixed shape, and the assembler (`app/assembler.py`) hardcodes that shape as
two constants:

```python
EXPERIENCE_BULLETS_PER_ENTRY = 3
PROJECT_BULLETS_PER_ENTRY = 2
```

If your bank uses a different shape (say, 4 bullets per job), change those
two constants — there's no markdown syntax for it, on purpose, since it's a
layout decision rather than content.

---

## Checklist before you point `RESUME_BANK_PATH` at a new file

- [ ] `## FACTS LEDGER` uses `##`, not `#` (the parser accepts either, but
      be consistent — LAYER 1-4 headers use `#`).
- [ ] Every module note uses `← *text*` or `*(text)*` — either works, but
      the closing marker must actually close (a bare `← note` with no `*`
      around it is fine too, it just won't be split out as a separate note).
- [ ] Every experience heading's alias (bracketed or default) matches
      *exactly* the bold label you use for it in every Role Preset that
      references it.
- [ ] Bullet IDs are unique across the whole file, not just within one
      entity's section.
- [ ] Role names in the "Module selection by role" table match Role Preset
      `###` headings (modulo trailing notes/annotations).
- [ ] `**Never appears, anywhere, again:**` — colon can go inside or outside
      the closing `**`, both parse.

Run `GET /bank-info` after pointing at a new file — it reports module/bullet/
project/preset counts so you can sanity-check the parse before generating a
real resume.
