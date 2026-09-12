"""
Phase 3 scaffold — CrewAI orchestration + real LLM integration.

Everything that actually decides WHAT goes on the resume (role classification,
bullet/module/project selection, the swap/alt-set conditionals) already lives
in role_matcher.py and assembler.py as plain deterministic Python, and stays
the source of truth. That's on purpose — LAYER 4 is explicit that nothing on
the resume may be untraceable to a bullet ID in the bank, so an LLM should
never be the thing choosing or inventing bullet content.

What CrewAI is for here, once an API key is configured, is the thin layer on
top of that deterministic result:
  1. ResumeStrategist — explains, in plain language, why this role preset and
     these specific bullets were chosen for this JD (uses the already-computed
     scores/matched keywords, doesn't re-decide anything).
  2. ResumeWriter — writes the one piece the markdown bank *doesn't* contain:
     the 3-line professional summary. Grounded strictly in the Facts Ledger
     (defensible numbers + role/company facts) so it can't invent claims.
  3. QAReviewer — checks the final text against the Facts Ledger's banned-
     phrase list and confirms every claim traces back to a bullet ID.

This module is inert until an LLM is configured — any provider or a local
Ollama model, via llm_config.py (LLM_PROVIDER / LLM_MODEL, or just set
OPENAI_API_KEY / ANTHROPIC_API_KEY / etc. and it auto-detects). The
deterministic /generate-resume endpoint in main.py does not depend on this
file at all.
"""
from __future__ import annotations

import re

from app import llm_config
from app.assembler import AssembledResume, assemble
from app.parser import FactsLedger, ResumeBank, get_bank


def build_crew(bank: ResumeBank, jd_text: str, assembled: AssembledResume):
    """Constructs the CrewAI Crew. Imports crewai lazily so the rest of the
    API works even before `pip install crewai` / an LLM is set up."""
    from crewai import Agent, Crew, Process, Task
    from crewai.tools import tool

    facts = bank.facts
    llm = llm_config.build_llm()

    @tool("get_assembled_resume")
    def get_assembled_resume_tool() -> str:
        """Returns the deterministically-assembled resume markdown, the
        chosen role, and why it was chosen (matched keywords)."""
        top = assembled.role_scores[0]
        return (
            f"Role: {assembled.role}\n"
            f"Matched keywords: {', '.join(top.matched_keywords)}\n\n"
            f"Assembled markdown:\n{assembled.markdown}"
        )

    @tool("get_defensible_facts")
    def get_defensible_facts_tool() -> str:
        """Returns the ONLY numbers/facts allowed to appear in the summary —
        nothing outside this list may be used or invented."""
        return "Defensible numbers:\n" + "\n".join(f"- {n}" for n in facts.defensible_numbers)

    @tool("get_banned_phrases")
    def get_banned_phrases_tool() -> str:
        """Returns phrases that must never appear anywhere in the resume."""
        return "Banned phrases:\n" + "\n".join(f"- {p}" for p in facts.banned_phrases)

    strategist = Agent(
        role="Resume Strategist",
        goal="Explain why the chosen role preset and bullets fit this JD, without changing any selection.",
        backstory=(
            "You review a resume that was already assembled by deterministic rules "
            "(role classification + bullet selection) and articulate the reasoning "
            "in plain language for the candidate. You never add or remove content."
        ),
        tools=[get_assembled_resume_tool],
        llm=llm,
        verbose=True,
    )

    writer = Agent(
        role="Resume Writer",
        goal="Write a 3-line professional summary using ONLY facts from the Facts Ledger.",
        backstory=(
            "You write concise, punchy resume summaries. You are extremely strict about "
            "provenance: every number or claim must come from the Facts Ledger tool. If "
            "you are unsure whether a claim is supported, you leave it out."
        ),
        tools=[get_assembled_resume_tool, get_defensible_facts_tool],
        llm=llm,
        verbose=True,
    )

    reviewer = Agent(
        role="QA Reviewer",
        goal=(
            "Reject the summary if any banned phrase appears, OR if any number in it isn't "
            "backed by a bullet actually visible in the assembled resume — a real number "
            "from the wrong job is still a grounding failure, not just a fabricated one."
        ),
        backstory=(
            "You are the last gate before this resume goes out. A prior writer had this "
            "exact failure mode: it pulled a real, correct number from this candidate's "
            "career, but one that belonged to a job that isn't even on this particular "
            "resume — a real stat from an experience entry that was never selected showed "
            "up in the summary anyway. You check every number in the summary against the "
            "SPECIFIC bullets in get_assembled_resume, not just against 'is this number "
            "real somewhere.'"
        ),
        tools=[get_assembled_resume_tool, get_banned_phrases_tool],
        llm=llm,
        verbose=True,
    )

    task_explain = Task(
        description=(
            f"The JD is:\n{jd_text}\n\n"
            "Call get_assembled_resume and explain in 2-3 sentences why this role preset "
            "and its bullets were selected for this JD."
        ),
        expected_output="A short explanation of the role/bullet fit.",
        agent=strategist,
    )

    task_summary = Task(
        description=(
            f"The JD is:\n{jd_text}\n\n"
            "Using get_assembled_resume for context and get_defensible_facts for allowed "
            "numbers, write a 3-line professional summary to replace the "
            "'[[3-line summary ...]]' placeholder. Two hard rules: "
            "(1) any number you use must appear in get_defensible_facts, AND "
            "(2) it must also describe one of the specific experience entries or projects "
            "that get_assembled_resume actually shows — get_defensible_facts lists numbers "
            "from this person's ENTIRE career, most of which belong to experience NOT "
            "selected for this particular resume, so pulling in a real number that isn't "
            "backed by a bullet visible in get_assembled_resume is still a grounding failure. "
            "When in doubt, prefer plain role/skill framing over a number."
        ),
        expected_output="A 3-line professional summary, no more.",
        agent=writer,
        context=[task_explain],
    )

    task_review = Task(
        description=(
            "Take the summary from the previous task. Call get_banned_phrases and confirm "
            "none of those phrases appear. Then call get_assembled_resume and check every "
            "number in the summary: it must be traceable to a bullet actually shown there — "
            "not just be a real number from get_defensible_facts, since that list spans "
            "this person's entire career and most of it isn't on this particular resume. "
            "Output the final 3-line summary if it passes both checks, or a rejection naming "
            "the specific phrase or unsupported number."
        ),
        expected_output="Either the approved 3-line summary or a rejection reason.",
        agent=reviewer,
        context=[task_summary],
    )

    return Crew(
        agents=[strategist, writer, reviewer],
        tasks=[task_explain, task_summary, task_review],
        process=Process.sequential,
        verbose=True,
    )


def _validate_ai_summary(summary: str, facts: FactsLedger) -> list[str]:
    """Deterministic defense-in-depth, run after the Reviewer agent, not
    instead of it.

    In testing (see README's "Provider setup"), the Reviewer agent — even
    with the right tools and an explicit instruction to cross-check numbers
    — confidently APPROVED a summary containing fabricated percentages,
    asserting they were "tied to visible bullets" when they were not
    anywhere in the bank. An LLM's self-report that it checked something is
    not the same as it actually being true. This function re-checks the one
    highest-risk, cheapest-to-verify pattern in code: this bank's own Facts
    Ledger explicitly bans invented percentage claims (see the "Never
    appears, anywhere, again" list), so ANY percentage in the AI summary
    that isn't verbatim in defensible_numbers is treated as fabricated.
    """
    violations = []
    ledger_text = " ".join(facts.defensible_numbers).lower()
    for pct in re.findall(r"\d+(?:\.\d+)?%", summary):
        if pct.lower() not in ledger_text:
            violations.append(f"percentage claim '{pct}' not found in defensible numbers")
    for phrase in facts.banned_phrases:
        if phrase.lower() in summary.lower():
            violations.append(f"banned phrase '{phrase}' found")
    return violations


def run_crew(jd_text: str, role_hint: str | None = None) -> dict:
    """Runs the full deterministic assembly, then hands it to the CrewAI crew
    to produce a grounded summary. Raises RuntimeError with a clear message
    if no LLM API key is configured yet — this is expected until Phase 3 is
    wired up."""
    if not llm_config.is_llm_configured():
        raise RuntimeError(
            "No LLM configured. Set LLM_PROVIDER + LLM_MODEL (any LiteLLM-supported "
            "provider, including a local Ollama model), or just set OPENAI_API_KEY / "
            "ANTHROPIC_API_KEY / GROQ_API_KEY / etc. and it auto-detects. See README.md. "
            "The deterministic /generate-resume endpoint works without any of this."
        )

    bank = get_bank()
    assembled = assemble(bank, jd_text=jd_text, role_hint=role_hint)
    crew = build_crew(bank, jd_text, assembled)
    result = crew.kickoff()
    raw_summary = str(result)

    violations = _validate_ai_summary(raw_summary, bank.facts)
    ai_summary = (
        f"[REJECTED by deterministic guard, not the Reviewer agent] {'; '.join(violations)}"
        if violations
        else raw_summary
    )

    return {
        "role": assembled.role,
        "resume_markdown": assembled.markdown,
        "ai_summary": ai_summary,
        "ai_summary_raw": raw_summary,
        "warnings": assembled.warnings,
    }
