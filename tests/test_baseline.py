from idea_search.baseline import (
    run_baseline_self_critique,
    run_baseline_single_shot,
)
from idea_search.providers.mock import MockProvider
from idea_search.schema import ProblemInput


def _problem() -> ProblemInput:
    return ProblemInput(
        problem="Help small bookstores survive without discounting.",
        constraints=["no discounts"],
        context="Urban independent stores.",
    )


def test_single_shot_returns_n_ideas():
    ideas = run_baseline_single_shot(MockProvider(), _problem(), n=3)
    assert len(ideas) == 3
    assert all(i.role == "BaselineSingle" for i in ideas)
    assert all(i.round == 0 for i in ideas)


def test_single_shot_marks_generic_tag():
    ideas = run_baseline_single_shot(MockProvider(), _problem(), n=5)
    # The baseline seeds are intentionally generic
    assert any("generic" in i.tags for i in ideas)


def test_self_critique_revises_first_generic():
    ideas = run_baseline_self_critique(MockProvider(), _problem(), n=3)
    assert len(ideas) == 3
    assert all(i.role == "BaselineSelfCritique" for i in ideas)
    # The first idea should be revised (tag changes)
    assert "self-critique" in ideas[0].tags
    assert "generic" not in ideas[0].tags


def test_self_critique_differs_from_single_shot():
    single = run_baseline_single_shot(MockProvider(), _problem(), n=3)
    critiqued = run_baseline_self_critique(MockProvider(), _problem(), n=3)
    # At minimum the first idea's title should differ
    assert single[0].title != critiqued[0].title
