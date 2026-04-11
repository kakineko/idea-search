from idea_search.providers.mock import MockProvider


def test_mock_generates_role_specific_ideas():
    p = MockProvider()
    ideas = p.generate_ideas(
        role="Contrarian",
        system_prompt="",
        problem="Save small bookstores",
        constraints=["no discounts"],
        context="",
        round_index=1,
        n=2,
    )
    assert len(ideas) >= 1
    assert all("title" in i and "statement" in i for i in ideas)
    assert any("Contrarian" in i["title"] for i in ideas)


def test_mock_evaluator_returns_score_rationale_suggestion():
    p = MockProvider()
    out = p.evaluate_axis(
        judge="NoveltyJudge",
        system_prompt="",
        problem="save small bookstores",
        idea_title="[Contrarian/against-consensus] some idea",
        idea_statement="statement",
    )
    assert "score" in out and 0 <= out["score"] <= 5
    assert out["rationale"]
    assert out["suggestion"]


def test_mock_scores_are_deterministic():
    p = MockProvider()
    kwargs = dict(
        judge="FeasibilityJudge", system_prompt="", problem="x",
        idea_title="[Proposer/direct-service] foo", idea_statement="bar",
    )
    a = p.evaluate_axis(**kwargs)
    b = p.evaluate_axis(**kwargs)
    assert a["score"] == b["score"]
