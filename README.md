# Modular Resume API

An API (plus a small chat-style frontend) that takes a job description and
returns a tailored resume, assembled from a "modular resume bank" — a
markdown file holding your vetted skill modules, experience bullets,
projects, and role presets. Nothing on the output resume is generated or
invented; every line is pulled verbatim, by ID, from bullets you've already
written and approved.

```
resume-agent/
├── backend/     FastAPI app — parses your bank, classifies the JD, assembles the resume
├── frontend/    Next.js chat UI — paste a JD, get sections back with copy buttons
├── docs/        architecture.md (how it works, provider setup) · api.md (endpoint reference)
├── BANK_FORMAT.md   the format spec for anyone's modular resume bank
└── LICENSE
```

See [docs/architecture.md](docs/architecture.md) for how the pipeline works,
the provider-setup details (Ollama/OpenAI/Anthropic/etc. for both the AI
summary layer and semantic search), and [docs/api.md](docs/api.md) for the
full endpoint reference. **This is generic** — the parser has no hardcoded
company names, role titles, or bullet IDs; anyone can point it at their own
bank file (see [BANK_FORMAT.md](BANK_FORMAT.md)).

## Quick start

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt          # core — deterministic path only
pip install -r requirements-ai.txt       # + CrewAI summary layer + semantic search

uvicorn app.main:app --reload --port 8000
```

Interactive docs: http://127.0.0.1:8000/docs

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL, defaults to localhost:8000
npm run dev
```

Open http://localhost:3000. Paste a JD, hit Generate (or ⌘/Ctrl+Enter) — the
response comes back as Skills / Experience / Projects / Education / full
Markdown, each in its own box with a Copy button. The role dropdown and
"AI-written summary" checkbox are optional; without an LLM configured on the
backend, leave the checkbox off and everything still works.

If the frontend can't reach the backend, check `CORS_ORIGINS` on the backend
(defaults to `http://localhost:3000`) and `NEXT_PUBLIC_API_URL` on the
frontend.

## Configuration

| Env var (backend) | Purpose | Default |
|---|---|---|
| `RESUME_BANK_PATH` | Path to your modular resume bank markdown file | `backend/example-resume-bank.md` — a fictional worked example, not a real resume |
| `RESUME_CONTACT_NAME`, `_LOCATION`, `_EMAIL`, `_PHONE`, `_LINKEDIN`, `_GITHUB`, `_SITE` | Header contact line — not bank *content* (see BANK_FORMAT.md), it's per-deployer config | `[[PLACEHOLDER]]`; override per-request via `contact` instead if you'd rather not set env vars |
| `CORS_ORIGINS` | Comma-separated origins allowed to call the API | `http://localhost:3000,http://127.0.0.1:3000` |
| `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY` | Chat model for `/generate-resume/ai` and (if enabled) `LLM_BULLET_SELECTION` | auto-detected from `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / etc.; otherwise unconfigured (503) |
| `EMBEDDINGS_PROVIDER`, `EMBEDDINGS_MODEL`, `EMBEDDINGS_BASE_URL` | Enables semantic search for bullet/project relevance | unset — keyword overlap is used |
| `LLM_BULLET_SELECTION` | Uses the chat model to pick bullets when a preset offers more candidates than slots | unset/`false` — `/generate-resume` makes zero network calls otherwise |

Put these in `backend/.env` (see `backend/.env.example`). Full details and
`ollama`/`openai`/`anthropic` examples for each in
[docs/architecture.md](docs/architecture.md).

| Env var (frontend) | Purpose | Default |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Backend base URL | `http://localhost:8000` |

Put this in `frontend/.env.local` (see `frontend/.env.local.example`).

Bringing your own bank? Read [BANK_FORMAT.md](BANK_FORMAT.md), then:

```bash
export RESUME_BANK_PATH=/path/to/your-resume-bank.md
```

## Testing

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/ -v
```

```bash
cd frontend
npm run lint
npm run build
```

See [docs/architecture.md#testing](docs/architecture.md#testing) for what
the backend suite actually covers (real bank + a deliberately unrelated
fixture bank, to catch hardcoded assumptions creeping back in).

## Project structure

```
backend/
  app/
    parser.py           Markdown → structured data (modules, bullets, projects, presets, facts)
    scoring.py          JD relevance scoring — keyword overlap, or semantic when configured
    semantic_search.py  LangChain embeddings (OpenAI/Ollama/HuggingFace) behind scoring.py
    role_matcher.py     JD → best-fit role preset
    assembler.py        Role preset + bank + JD → assembled resume (LAYER 3/4 rules as code)
    llm_config.py       Provider-agnostic chat model config for crew_agents.py (LiteLLM-backed)
    llm_selection.py    Optional LLM-assisted bullet selection (see docs/architecture.md)
    crew_agents.py      CrewAI: Strategist → Writer → Reviewer, grounded in the Facts Ledger
    models.py           Request/response schemas
    storage.py          Optional save-to-file
    main.py             FastAPI app + CORS
    output/             Saved resumes (created on first save)
  tests/                pytest suite (parser, assembler, role_matcher; real bank + fixture bank)
  example-resume-bank.md   Fictional worked example (Jordan Rivera / TechCorp / StartupCo)
  requirements.txt        Core deps (deterministic path only)
  requirements-ai.txt     + CrewAI + LangChain (summary layer + semantic search)
  requirements-dev.txt    + pytest
  Dockerfile
frontend/
  app/page.tsx          Chat UI: message list + composer
  components/           ChatComposer, ResumeResult, SectionBox, CopyButton
  lib/api.ts            Typed client for the backend API
docs/
  architecture.md       Pipeline, provider setup, design rationale
  api.md                Endpoint reference
BANK_FORMAT.md           The format spec for anyone's modular resume bank
```
