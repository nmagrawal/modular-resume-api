# Architecture

## Pipeline

```
JD text
  │
  ▼
role_matcher.py   — scores the JD against each role preset's keywords,
  │                  picks the best-fit preset (or honors an explicit hint)
  ▼
assembler.py      — pulls that preset's modules/experience/projects from
  │                  the bank, resolves conditional picks ("swap X in when
  │                  Y appears in the JD", "X or Y depending on the JD"),
  │                  reorders skills to mirror the JD's vocabulary, and
  │                  renders the fixed resume shape
  ▼
resume markdown + structured JSON (role, matched keywords, warnings)
```

`parser.py` does the one-time work of turning the bank markdown into
structured data; `role_matcher.py` and `assembler.py` are where LAYER 3 and
LAYER 4 of the bank's own rules become executable code instead of prose.

**This is generic** — the parser has no hardcoded company names, role
titles, or bullet IDs. Anyone can point it at their own bank file (see
[../BANK_FORMAT.md](../BANK_FORMAT.md)) and it works the same way.

## Where this stands

- ✅ **Deterministic core** — keyword-based JD→role classification, rule-based
  bullet/module/project selection. No AI, no network calls, no API key. This
  is the whole `POST /generate-resume` path.
- ✅ **Semantic search** (optional) — set `EMBEDDINGS_PROVIDER` and bullet/
  project relevance scoring switches from keyword overlap to embedding
  similarity via LangChain, so a paraphrased JD that shares zero literal
  keywords with a bullet still matches it correctly. Falls back to keyword
  overlap with nothing configured.
- ✅ **AI summary layer** (optional) — `POST /generate-resume/ai` runs a
  3-agent CrewAI crew (Strategist → Writer → Reviewer) on top of the
  deterministic result, to write the one thing the bank doesn't contain: the
  3-line professional summary. Works with any provider CrewAI's LiteLLM
  backend supports, including a fully local Ollama model.
- ✅ **LLM-assisted bullet selection** (optional) — when a role preset offers
  more candidates than the fixed shape uses, `LLM_BULLET_SELECTION=true`
  hands that specific pick to the configured chat model instead of the
  relevance scorer.
- ✅ **Frontend** — a small Next.js chat interface (`frontend/`) that calls
  the API and renders each resume section in its own copyable box.

## Two different multi-provider layers, on purpose

This project uses **CrewAI's own LiteLLM-backed `LLM` class** for the chat
model (`llm_config.py`) and **LangChain's `Embeddings` interface** for
semantic search (`semantic_search.py`) — not LangChain for both. That's a
deliberate choice, not an oversight: CrewAI's `Agent(llm=...)` doesn't
actually call a LangChain chat model's `.invoke()` if you hand it one — it
reads a couple of attributes off the object and rebuilds its own LiteLLM
call from them, so wiring a LangChain chat model into CrewAI is fragile and
buys nothing. LiteLLM already speaks Ollama/OpenAI/Anthropic/Groq/etc.
natively via a model-string, which is what `llm_config.py` builds. LangChain
earns its place instead on the embeddings side, where its `Embeddings`
interface (`embed_query`/`embed_documents`) is genuinely the same three
lines across OpenAI, Ollama, and fully-local HuggingFace models — and
CrewAI doesn't touch that code path at all.

## Provider setup

### Chat model (`POST /generate-resume/ai`, and `LLM_BULLET_SELECTION`)

Any [LiteLLM-supported provider](https://docs.litellm.ai/docs/providers)
works. Set `LLM_PROVIDER` + `LLM_MODEL`, or just set the provider's usual API
key env var and a sensible default model is picked automatically:

```bash
# Local, free, no API key — needs `ollama pull llama3.1` (or another
# tool-calling-capable model) and `ollama serve` running.
export LLM_PROVIDER=ollama
export LLM_MODEL=llama3.1

# OpenAI
export OPENAI_API_KEY=sk-...          # LLM_PROVIDER auto-detected as openai

# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...   # LLM_PROVIDER auto-detected as anthropic

# Self-hosted / OpenAI-compatible endpoint
export LLM_PROVIDER=openai
export LLM_MODEL=your-model-name
export LLM_BASE_URL=https://your-endpoint/v1
```

**A note on model quality for the QA gate, from actually testing this**:
the Reviewer agent's whole job is catching the Writer agent's mistakes — and
in testing, smaller local models genuinely do make mistakes worth catching,
and the Reviewer itself isn't fully reliable either. A 3B model (`llama3.2`)
sometimes emitted raw tool-call JSON as its final answer instead of real
prose. An 8B model (`qwen3:8b`) wrote a fluent summary that quietly pulled in
a real, correct number from a *different job* than the one on this resume (a
real stat from an experience entity that wasn't even selected for this
particular preset) — the Reviewer caught that one and rejected it correctly.
But on another run, the same model's Writer fabricated two percentages
outright, and the Reviewer **approved them anyway**, asserting in its own
final answer that they were "explicitly tied to visible bullets" — which was
simply false. An LLM reporting that it verified something is not the same as
it having verified it. Because of that, `run_crew()` in `crew_agents.py` runs
one deterministic, non-LLM check after the crew finishes: any percentage in
the final summary that isn't verbatim in the Facts Ledger's defensible
numbers gets the whole summary rejected in code, regardless of what the
Reviewer agent said. Treat the Reviewer agent as a useful first pass, not a
guarantee — the deterministic guard is what actually holds the line.
`ai_summary_raw` in the response always carries the crew's unedited output
too, so a rejection is inspectable rather than opaque.

### Embeddings (semantic search)

```bash
# Local, free, no API key
export EMBEDDINGS_PROVIDER=huggingface   # needs: pip install langchain-huggingface sentence-transformers
export EMBEDDINGS_MODEL=sentence-transformers/all-MiniLM-L6-v2   # default if unset

# Local via Ollama (needs an embedding-capable model pulled, and the server
# started with embeddings support — `ollama pull nomic-embed-text`)
export EMBEDDINGS_PROVIDER=ollama
export EMBEDDINGS_MODEL=nomic-embed-text

# OpenAI
export EMBEDDINGS_PROVIDER=openai
export OPENAI_API_KEY=sk-...
```

Verified: a JD phrase with **zero literal keyword overlap** with a bullet
("stood up statistically rigorous offline testing for retrieval quality")
scored 0.40 semantic similarity against a bullet using different wording for
the same idea (LangGraph/MCP/human-in-the-loop), correctly well above an
unrelated bullet's 0.16 — the case keyword-overlap scoring structurally
can't handle.

### LLM-assisted bullet selection

Some role presets offer more candidate bullets than the fixed shape uses —
either because a primary list already has 4, or because BANK_FORMAT.md's
`(+X as a fourth)` / `(+X if a fourth fits)` bonus grammar names an explicit
extra option. **Until this was added, that bonus was parsed and then
silently ignored** — the assembler always fell back to trimming by
relevance score among the base candidates, never actually considering the
bonus. Two fixes landed together:

1. The bonus candidate is now always a real part of the pool (works with
   plain keyword/semantic scoring — no LLM required).
2. Optionally, set `LLM_BULLET_SELECTION=true` to have the `LLM_PROVIDER`
   chat model do that specific pick instead of the relevance scorer, when
   there's an actual choice to make (i.e. more candidates than slots).

```bash
export LLM_PROVIDER=ollama
export LLM_MODEL=qwen3:8b
export LLM_BULLET_SELECTION=true
```

This uses `crewai.LLM.call(..., response_model=...)` for structured output
(a Pydantic model, not free text) — verified to return clean, parseable
picks even from a local 3B model, unlike the free-text summary layer. The
result is still validated in code before being trusted (right count, IDs
actually in the candidate pool); an untrustworthy or failed call falls back
to relevance scoring, the same defense-in-depth pattern as the summary
layer's fact-checking guard.

**Verified against a real bonus case**: a preset offering `OG20·OG22·OG21`
plus a documented bonus `OG9`, against a JD emphasizing exactly what `OG9`
covers (golden datasets, hard negatives, abstention, prompt-injection
resistance) that the primary three don't. Relevance scoring alone already
correctly swapped `OG9` in for `OG20` once the bonus was in the pool; with
`LLM_BULLET_SELECTION=true` on `qwen3:8b`, the model also picked `OG9`,
landing on a slightly different (still defensible) second choice than the
scorer for the remaining slot — the kind of judgment call where reasonable
scoring methods can differ.

**Note**: `/generate-resume` makes zero network calls unless
`LLM_BULLET_SELECTION=true` is explicitly set — just having `LLM_PROVIDER`
configured for the separate `/generate-resume/ai` summary layer does not
turn this on.

## Testing

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/ -v
```

The suite runs the parser/assembler/role-matcher against both this repo's
real bank and a small, deliberately unrelated fixture bank
(`tests/fixtures/mini-bank.md`) — the latter exists specifically to catch
any hardcoded assumption about company names, module names, or bullet ID
prefixes creeping back in.
