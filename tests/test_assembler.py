import pytest

from app.assembler import (
    EXPERIENCE_BULLETS_PER_ENTRY,
    PROJECT_BULLETS_PER_ENTRY,
    BulletExpr,
    assemble,
    parse_bullet_expr,
    parse_project_slot,
    select_bullets,
)

ALL_ROLES = ["Backend Engineer", "ML Engineer", "Engineering Manager"]


# --- conditional-expression grammar (synthetic, isolates the grammar itself) -

def test_parse_plain_list():
    expr = parse_bullet_expr("SC1·SC2·SC3")
    assert expr.primary_ids == ["SC1", "SC2", "SC3"]
    assert expr.swap is None
    assert expr.alt_set is None


def test_parse_swap_condition():
    expr = parse_bullet_expr("TC1·TC2·TC3 (swap TC4 in when Kubernetes appears in the JD)")
    assert expr.primary_ids == ["TC1", "TC2", "TC3"]
    assert expr.swap == ("Kubernetes", "TC4")


def test_parse_alt_set():
    expr = parse_bullet_expr("TC2·TC3·TC4 (or TC1·TC2·TC4, depending on the JD)")
    assert expr.alt_set == ["TC1", "TC2", "TC4"]


def test_parse_alt_single():
    expr = parse_bullet_expr("TC1·TC3·TC4 (or TC2)")
    assert expr.alt_single == "TC2"


def test_parse_bonus():
    expr = parse_bullet_expr("OG16·OG18·OG23 (+OG25 as a fourth)")
    assert expr.bonus_id == "OG25"


def test_bonus_candidate_is_actually_selectable_by_scoring():
    """A documented bonus must be a real candidate, not a note that gets
    parsed and then ignored — if it scores better than a primary bullet, it
    should win the trim, same as any other candidate."""
    expr = BulletExpr(primary_ids=["A", "B", "C"], bonus_id="D")
    texts = {
        "A": "totally unrelated filler content",
        "B": "totally unrelated filler content",
        "C": "kubernetes docker mildly related",
        "D": "kubernetes docker terraform extremely strongly related",
    }
    result = select_bullets(expr, target_count=3, bullet_texts=texts, jd_lower="kubernetes docker terraform")
    assert "D" in result
    assert len(result) == 3


def test_llm_selection_used_when_enabled(monkeypatch):
    """With LLM_BULLET_SELECTION on, a >target_count candidate pool should
    go through llm_selection rather than straight to scoring."""
    from app import llm_selection

    monkeypatch.setenv("LLM_BULLET_SELECTION", "true")
    monkeypatch.setattr(llm_selection, "llm_select_bullets", lambda jd, pool, n: ["A", "D"])

    expr = BulletExpr(primary_ids=["A", "B", "C"], bonus_id="D")
    texts = {"A": "x", "B": "x", "C": "x", "D": "x"}
    result = select_bullets(expr, target_count=2, bullet_texts=texts, jd_lower="jd", jd_text="JD")
    assert result == ["A", "D"]


def test_llm_selection_falls_back_to_scoring_when_untrustworthy(monkeypatch):
    """If the LLM path returns None (unconfigured, call failed, or its
    answer didn't validate), selection must fall back to scoring — never
    crash, never silently drop below target_count."""
    from app import llm_selection

    monkeypatch.setenv("LLM_BULLET_SELECTION", "true")
    monkeypatch.setattr(llm_selection, "llm_select_bullets", lambda jd, pool, n: None)

    expr = BulletExpr(primary_ids=["A", "B", "C"], bonus_id="D")
    texts = {
        "A": "kubernetes docker strongly related",
        "B": "unrelated", "C": "unrelated", "D": "unrelated",
    }
    result = select_bullets(expr, target_count=3, bullet_texts=texts, jd_lower="kubernetes docker", jd_text="JD")
    assert len(result) == 3
    assert "A" in result


def test_swap_forces_inclusion_even_if_low_scoring():
    """A forced swap must survive relevance-based trimming — it's a hard
    rule ("swap X in when Y appears"), not a vote among candidates."""
    expr = BulletExpr(primary_ids=["A", "B", "C", "D"], swap=("kubernetes", "E"))
    texts = {
        "A": "kubernetes kubernetes kubernetes kubernetes kubernetes",
        "B": "kubernetes kubernetes kubernetes kubernetes",
        "C": "kubernetes kubernetes kubernetes",
        "D": "kubernetes kubernetes",
        "E": "completely unrelated text with no matching tokens at all",
    }
    result = select_bullets(expr, target_count=3, bullet_texts=texts, jd_lower="kubernetes")
    assert "E" in result
    assert len(result) == 3


def test_alt_set_picks_higher_scoring_set():
    expr = BulletExpr(primary_ids=["A"], alt_set=["B"])
    texts = {"A": "totally unrelated filler", "B": "kubernetes docker terraform"}
    result = select_bullets(expr, target_count=1, bullet_texts=texts, jd_lower="kubernetes docker")
    assert result == ["B"]


def test_parse_project_slot_with_or():
    ids, note = parse_project_slot("PR-ML or PR-DASH")
    assert ids == ["PR-ML", "PR-DASH"]
    assert note is None


def test_parse_project_slot_with_note():
    ids, note = parse_project_slot('PR-API (framed as "the gateway I proposed and scoped")')
    assert ids == ["PR-API"]
    assert "framed as" in note


# --- full assembly, against the shipped example bank ------------------------

@pytest.mark.parametrize("role", ALL_ROLES)
def test_every_preset_assembles_to_fixed_shape(example_bank, role):
    jd = f"Generic job description mentioning {role} and some unrelated keywords."
    result = assemble(example_bank, jd, role_hint=role)
    assert result.role == role
    assert len(result.experience) == 2
    for entry in result.experience:
        assert len(entry.bullets) == EXPERIENCE_BULLETS_PER_ENTRY
    assert len(result.projects) == 4
    for entry in result.projects:
        assert len(entry.project.bullets) == PROJECT_BULLETS_PER_ENTRY


def test_kubernetes_swap_actually_swaps_in_tc4(example_bank):
    jd = "Backend Engineer role requiring deep Kubernetes experience."
    result = assemble(example_bank, jd, role_hint="Backend Engineer")
    techcorp_ids = [b.id for e in result.experience if e.entity == "TechCorp" for b in e.bullets]
    assert "TC4" in techcorp_ids


def test_alt_set_swaps_when_jd_favors_it(example_bank):
    # TC1 ("Python and Go microservices API") scores higher than TC3 ("service
    # mesh migration, mentoring") against this JD, so the alt set TC1·TC2·TC4
    # should out-score the primary TC2·TC3·TC4 and get selected instead.
    jd = "ML Engineer role requiring strong Python and Go microservices API development, plus Kubernetes and CI/CD."
    result = assemble(example_bank, jd, role_hint="ML Engineer")
    techcorp_ids = [b.id for e in result.experience if e.entity == "TechCorp" for b in e.bullets]
    assert "TC1" in techcorp_ids
    assert "TC3" not in techcorp_ids


def test_education_above_experience_flag(example_bank):
    result = assemble(example_bank, "Engineering Manager role", role_hint="Engineering Manager")
    assert result.education_above_experience is True
    assert result.markdown.index("## Education") < result.markdown.index("## Experience")


def test_banned_phrase_guard_flags_leakage(example_bank):
    from app import assembler

    original = assembler.render_markdown
    try:
        assembler.render_markdown = lambda *a, **kw: original(*a, **kw) + "\nrockstar developer"
        result = assemble(example_bank, "Backend Engineer, Kubernetes")
        assert any("Banned phrase" in w for w in result.warnings)
    finally:
        assembler.render_markdown = original


def test_contact_placeholders_when_unconfigured(monkeypatch, example_bank):
    for var in ("RESUME_CONTACT_NAME", "RESUME_CONTACT_EMAIL", "RESUME_CONTACT_LINKEDIN"):
        monkeypatch.delenv(var, raising=False)
    result = assemble(example_bank, "Backend Engineer, Kubernetes")
    assert "[[" in result.contact.name
    assert "[[" in result.contact.email


def test_contact_overrides_take_precedence(example_bank):
    result = assemble(
        example_bank, "Backend Engineer, Kubernetes",
        contact_overrides={"name": "Jane Doe", "email": "jane@example.com"},
    )
    assert result.contact.name == "Jane Doe"
    assert result.contact.email == "jane@example.com"


def test_missing_entity_bullet_list_falls_back_with_warning(mini_bank):
    """Backend Engineer's Experience field lists 'Acme + Foo', but the preset
    has no explicit '**Foo**' bullet expression — a real gap this exact
    parser found in a real bank. Must degrade gracefully, not crash."""
    result = assemble(mini_bank, "backend engineer, go, kubernetes")
    foo_entry = next(e for e in result.experience if e.entity == "Foo")
    assert len(foo_entry.bullets) >= 1
    assert any("source gap" in w for w in result.warnings)


def test_education_generic_across_banks(mini_bank):
    result = assemble(mini_bank, "Backend engineer, Go, Kubernetes")
    assert "B.S. Computer Science" in result.markdown
    assert "Jordan Rivera" not in result.markdown
