from idea_search.hierarchical.goal_decomposer import decompose_goal
from idea_search.hierarchical.schema import Goal
from idea_search.providers.mock import MockProvider


def _goal() -> Goal:
    return Goal(
        goal_id="g1",
        goal_statement="Find realistic ways for one person to make money",
        constraints=["low initial capital", "testable within 2 weeks"],
        domain_context=["AI systems", "Keirin prediction"],
    )


def test_decompose_returns_n_branches():
    branches = decompose_goal(MockProvider(), _goal(), n=5)
    assert len(branches) == 5
    assert all(b.goal_id == "g1" for b in branches)


def test_branches_have_diverse_attributes():
    branches = decompose_goal(MockProvider(), _goal(), n=5)
    capitals = {b.required_capital for b in branches}
    risks = {b.risk_level for b in branches}
    # Mock seeds intentionally vary these
    assert len(capitals) >= 2
    assert len(risks) >= 2


def test_each_branch_has_assumptions():
    branches = decompose_goal(MockProvider(), _goal(), n=3)
    assert all(len(b.assumptions) >= 1 for b in branches)


def test_branch_names_differ():
    branches = decompose_goal(MockProvider(), _goal(), n=5)
    names = [b.branch_name for b in branches]
    assert len(set(names)) == len(names)
