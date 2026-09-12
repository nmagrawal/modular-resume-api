# Modular Resume Chat (frontend)

A small Next.js chat interface for the [Modular Resume API](../README.md).
Paste a job description; the response comes back broken into Skills,
Experience, Projects, Education, and full-Markdown sections, each with its
own Copy button.

## Setup

```bash
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL, defaults to localhost:8000
npm run dev
```

Open http://localhost:3000. The backend (`../backend`) must be running —
see the [root README](../README.md#quick-start) for that.

## Structure

```
app/page.tsx              Chat page: message list + composer, ties everything together
components/
  ChatComposer.tsx         JD textarea, role-hint dropdown, AI-summary toggle, submit
  ResumeResult.tsx          Renders one response as Skills/Experience/Projects/Education/Markdown boxes
  SectionBox.tsx            Reusable titled box + Copy button
  CopyButton.tsx             Clipboard write with a "Copied" state, falls back to execCommand
lib/api.ts                 Typed client for the backend (keep in sync with backend/app/models.py)
```

## Notes

- The role dropdown and "AI-written summary" checkbox are optional. Without
  an LLM configured on the backend, leave the checkbox unchecked — the
  deterministic `/generate-resume` path always works.
- Checking "AI-written summary" calls both `/generate-resume` (for the
  structured sections) and `/generate-resume/ai` (for the summary text) and
  merges them; if the AI call fails (e.g. no LLM configured), the structured
  sections still render and a small inline notice explains why the summary
  didn't.
