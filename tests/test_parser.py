"""Parser tests, run against the shipped example bank and a tiny unrelated
fixture bank (the latter proves genericity — no hardcoded names)."""


def test_example_bank_structure(example_bank):
    assert set(example_bank.modules.keys()) == {"M1", "M2", "M3", "M4"}
    assert set(example_bank.role_presets.keys()) == {
        "Backend Engineer",
        "ML Engineer",
        "Engineering Manager",
    }
    assert {k: len(v) for k, v in example_bank.bullet_banks.items()} == {
        "TechCorp": 4,
        "StartupCo": 3,
    }
    assert len(example_bank.projects) == 5


def test_example_bank_facts_ledger(example_bank):
    assert len(example_bank.facts.defensible_numbers) == 4
    assert len(example_bank.facts.banned_phrases) == 4
    assert example_bank.facts.find_row("B.S.") is not None
    assert example_bank.facts.find_row("TechCorp") is not None


def test_entity_alias_bracket_convention(example_bank):
    # "TechCorp Inc. [TechCorp] — ..." -> alias "TechCorp", display "TechCorp Inc."
    assert example_bank.entity_display_names["TechCorp"] == "TechCorp Inc."
    assert example_bank.entity_display_names["StartupCo"] == "StartupCo, LLC"


def test_mini_bank_is_fully_independent(mini_bank):
    """A bank with none of example_bank's names/IDs/modules parses cleanly —
    proves the parser has no hardcoded content."""
    assert set(mini_bank.modules.keys()) == {"M1"}
    assert set(mini_bank.bullet_banks.keys()) == {"Acme", "Foo"}
    assert set(mini_bank.bullet_banks["Acme"].keys()) == {"AC1", "AC2"}
    assert set(mini_bank.projects.keys()) == {"PR-Q"}
    assert set(mini_bank.role_presets.keys()) == {"Backend Engineer"}
    assert mini_bank.facts.find_row("Acme") is not None
    assert mini_bank.facts.find_row("B.S.") is not None


def test_missing_bank_file_raises_clear_error(tmp_path):
    from app.parser import parse_bank

    missing = tmp_path / "does-not-exist.md"
    try:
        parse_bank(missing)
        assert False, "expected FileNotFoundError"
    except FileNotFoundError as e:
        assert "RESUME_BANK_PATH" in str(e)
