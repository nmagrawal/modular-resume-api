"""
Tests for the deterministic guard in crew_agents.py — not for the CrewAI
agents themselves (those need a real LLM and are exercised manually, see
README's "Provider setup"). This guard exists specifically because, in
manual testing, a Reviewer agent confidently approved a summary with
fabricated percentages, asserting (falsely) that they were grounded. These
tests pin that exact failure mode so it can't silently regress.
"""
from app.crew_agents import _validate_ai_summary


def test_fabricated_percentage_is_flagged(example_bank):
    summary = "Reduced inference latency by 28% and boosted accuracy by 19%."
    violations = _validate_ai_summary(summary, example_bank.facts)
    assert any("28%" in v for v in violations)
    assert any("19%" in v for v in violations)


def test_clean_summary_has_no_violations(example_bank):
    summary = (
        "Backend Engineer with expertise in microservices and Kubernetes, "
        "handling 2M+ requests/day across 15 microservices."
    )
    assert _validate_ai_summary(summary, example_bank.facts) == []


def test_banned_phrase_is_flagged(example_bank):
    summary = "A true rockstar developer who ships fast."
    violations = _validate_ai_summary(summary, example_bank.facts)
    assert any("rockstar developer" in v for v in violations)


def test_percentage_actually_in_ledger_is_not_flagged(mini_bank):
    # mini_bank's defensible numbers don't include a percentage — this just
    # confirms the check is case-insensitive and substring-based, not that
    # any specific percentage is allowed (there isn't one in this fixture).
    from dataclasses import replace

    facts_with_pct = replace(mini_bank.facts, defensible_numbers=["50% test coverage"])
    assert _validate_ai_summary("We hit 50% test coverage.", facts_with_pct) == []
