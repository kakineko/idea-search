from idea_search.hierarchical.branch_evaluator import evaluate_branches
from idea_search.hierarchical.branch_selector import select_top_k
from idea_search.hierarchical.goal_decomposer import decompose_goal
from idea_search.hierarchical.schema import Goal
from idea_search.providers.mock import MockProvider


def _goal() -> Goal:
    return Goal(
        goal_id="g1",
        goal_statement="Find realistic ways to make money",
        constraints=["low capital"],
        domain_context=["AI systems"],
    )


def _evaluated():
    branches = decompose_goal(MockProvider(), _goal(), n=5)
    return evaluate_branches(MockProvider(), branches, _goal())


def test_select_top_1():
    evaluated = _evaluated()
    selected = select_top_k(evaluated, k=1)
    assert len(selected) == 1
    _, ev, reason = selected[0]
    assert "Ranked #1" in reason
    assert "composite=" in reason


def test_select_top_3():
    evaluated = _evaluated()
    selected = select_top_k(evaluated, k=3)
    assert len(selected) == 3
    composites = [ev.composite() for _, ev, _ in selected]
    # Descending order
    assert composites == sorted(composites, reverse=True)


def test_selection_reason_includes_axis_scores():
    evaluated = _evaluated()
    selected = select_top_k(evaluated, k=1)
    _, _, reason = selected[0]
    assert "upside=" in reason
    assert "cost=" in reason
    assert "risk=" in reason
