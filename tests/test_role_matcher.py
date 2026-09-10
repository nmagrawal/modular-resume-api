from app.role_matcher import resolve_role, score_roles


def test_classifies_kubernetes_jd_as_backend_engineer(example_bank):
    jd = (
        "We need a Backend Engineer to own our microservices and event-driven "
        "architecture, with Docker and Kubernetes deployment experience."
    )
    role, scores = resolve_role(example_bank, jd, role_hint=None)
    assert role == "Backend Engineer"
    assert scores[0].role == role
    assert "Kubernetes" in scores[0].matched_keywords


def test_role_hint_overrides_classification(example_bank):
    jd = "Anything at all, doesn't matter what's in here for this test."
    role, _ = resolve_role(example_bank, jd, role_hint="ML Engineer")
    assert role == "ML Engineer"


def test_role_hint_is_case_and_substring_tolerant(example_bank):
    role, _ = resolve_role(example_bank, "irrelevant jd text", role_hint="ml engineer")
    assert role == "ML Engineer"


def test_unknown_role_hint_raises(example_bank):
    try:
        resolve_role(example_bank, "irrelevant", role_hint="Nonexistent Role")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "Nonexistent Role" in str(e)


def test_score_roles_covers_every_preset(example_bank):
    scores = score_roles(example_bank, "generic job description")
    assert {s.role for s in scores} == set(example_bank.role_presets.keys())


def test_mini_bank_classification(mini_bank):
    role, scores = resolve_role(mini_bank, "Backend engineer role, Go and Kubernetes", None)
    assert role == "Backend Engineer"
