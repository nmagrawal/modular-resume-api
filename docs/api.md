# API Reference

Base URL: `http://localhost:8000` by default (see backend `.env.example`).

## `GET /health`
Liveness check.

## `GET /bank-info`
Confirms which bank file is loaded and gives a structural summary — the fast
way to verify `RESUME_BANK_PATH` picked up the right file.

```bash
curl http://127.0.0.1:8000/bank-info
```

## `GET /roles`
Lists every role preset the bank defines, with its modules, experience
entities, and any free-text notes.

## `POST /generate-resume`
The main endpoint. Deterministic, no AI required.

**Request:**
```json
{
  "jd": "We need a Backend Engineer to own our microservices, with Docker and Kubernetes deployment experience...",
  "role_hint": null,
  "contact": { "email": "you@example.com" },
  "save_to_file": true
}
```

- `jd` (required) — the job description text.
- `role_hint` (optional) — force a specific role preset by name instead of
  auto-classifying.
- `contact` (optional) — override any of `name`, `location`, `email`,
  `phone`, `linkedin`, `github`, `site`. Anything not overridden falls back
  to a `[[PLACEHOLDER]]` (the bank has no phone/email/GitHub of its own).
- `save_to_file` (optional, default `false`) — also writes the assembled
  markdown to `backend/app/output/`.

**Response:**
```json
{
  "role": "Backend Engineer",
  "role_scores": [
    { "role": "Backend Engineer", "score": 3, "matched_keywords": ["Kubernetes", "Docker", "..."], "semantic_score": 0.0 },
    { "role": "ML Engineer", "score": 1, "matched_keywords": ["..."], "semantic_score": 0.0 }
  ],
  "modules": [ { "id": "M1", "name": "Core Engineering", "skills": ["..."] } ],
  "experience": [ { "entity": "TechCorp", "display_title": "TechCorp Inc.", "ledger_line": "...", "bullets": [ { "id": "TC4", "text": "..." } ] } ],
  "projects": [ { "id": "PR-API", "name": "Internal API Gateway", "note": null, "tech": ["..."], "bullets": ["..."] } ],
  "education": ["B.S. Computer Science — State University · 2016–2020"],
  "education_above_experience": false,
  "resume_markdown": "# [[NAME — set RESUME_CONTACT_NAME or pass `contact.name`]]\n...",
  "warnings": [],
  "saved_path": "backend/app/output/20260910-024726_backend-engineer.md"
}
```

`role_scores` and `warnings` are there on purpose — every decision the API
makes is inspectable: which roles it considered, which keywords matched, and
any gap in the bank it had to fall back around (never a silent failure). A
`role_scores[0].score == 0` with `semantic_score == 0` and no `role_hint`
given means the JD matched nothing — `warnings` will say so explicitly
rather than letting the forced first-listed-role pick look like a real
match.

## `POST /generate-resume/ai`
Same input shape. Runs the deterministic pipeline above, then hands it to a
CrewAI crew (Strategist explains the fit → Writer drafts a grounded 3-line
summary → Reviewer cross-checks it against the assembled resume and the
Facts Ledger's banned-phrase list) that writes the professional summary.
Returns `503` until a chat model is configured — see
[architecture.md's Provider setup](architecture.md#provider-setup).

```json
{
  "role": "Backend Engineer",
  "resume_markdown": "# [[NAME — set RESUME_CONTACT_NAME or pass `contact.name`]]\n...",
  "ai_summary": "Backend Engineer with expertise in...",
  "ai_summary_raw": "Backend Engineer with expertise in...",
  "warnings": []
}
```

If the Reviewer rejects the Writer's draft, `ai_summary` is the rejection
reason (naming the specific violation) instead of a summary — that's by
design, not a bug: a rejected summary means the gate worked.

Note this endpoint does **not** return the structured `modules` /
`experience` / `projects` / `education` breakdown that `/generate-resume`
does — the bundled frontend calls both endpoints and merges them (the
deterministic call for structured sections, this one just for the summary
text).
