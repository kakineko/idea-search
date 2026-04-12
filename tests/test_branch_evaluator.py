from idea_search.hierarchical.branch_evaluator import evaluate_branch, evaluate_branches
from idea_search.hierarchical.goal_decomposer import decompose_goal
from idea_search.hierarchical.schema import Goal
from idea_search.providers.mock import MockProvider

_AXES = ["upside", "cost", "risk", "validation_speed", "personal_fit", "data_availability"]


def _goal() -> Goal:
    return Goal(
        goal_id="g1",
        goal_statement="Find realistic ways to make money",
        constraints=["low capital"],
        domain_context=["AI systems"],
    )


def test_evaluate_branch_returns_all_axes():
    branches = decompose_goal(MockProvider(), _goal(), n=1)
    ev = evaluate_branch(MockProvider(), branches[0], _goal())
    for axis in _AXES:
        ax = getattr(ev, axis)
        assert 0 <= ax.score <= 5
        assert ax.rationale
        assert ax.suggestion


def test_evaluate_branches_returns_pairs():
    branches = decompose_goal(MockProvider(), _goal(), n=3)
    results = evaluate_branches(MockProvider(), branches, _goal())
    assert len(results) == 3
    for b, ev in results:
        assert ev.branch_id == b.branch_id


def test_scores_are_deterministic():
    branches = decompose_goal(MockProvider(), _goal(), n=2)
    ev1 = evaluate_branch(MockProvider(), branches[0], _goal())
    ev2 = evaluate_branch(MockProvider(), branches[0], _goal())
    assert ev1.upside.score == ev2.upside.score
