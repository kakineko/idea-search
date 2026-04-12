from idea_search.hierarchical.method_adapter import (
    build_method_search_input,
    to_problem_input,
)
from idea_search.hierarchical.schema import Branch, Goal


def _goal() -> Goal:
    return Goal(
        goal_id="g1",
        goal_statement="Make money as one person",
        constraints=["low capital", "testable in 2 weeks"],
        domain_context=["AI systems", "Keirin prediction"],
    )


def _branch() -> Branch:
    return Branch(
        branch_id="b1", goal_id="g1",
        branch_name="Data product for Keirin",
        branch_description="Package Keirin prediction data as a subscription service",
        assumptions=["Race data is accessible", "Paying audience exists"],
        required_capital="low",
        required_skill="data science",
        risk_level="medium",
        validation_speed="weeks",
        personal_fit="high",
        data_availability="partial",
    )


def test_method_search_input_preserves_all_context():
    msi = build_method_search_input(_branch(), _goal(), "top composite score")
    assert msi.selected_branch.branch_name == "Data product for Keirin"
    assert msi.inherited_goal.goal_statement == "Make money as one person"
    assert "low capital" in msi.inherited_constraints
    assert "AI systems" in msi.inherited_context
    assert msi.selection_reason == "top composite score"


def test_to_problem_input_embeds_branch_deeply():
    msi = build_method_search_input(_branch(), _goal(), "best branch")
    pi = to_problem_input(msi)

    # Problem text must include branch name, description, goal, assumptions, reason
    assert "Data product for Keirin" in pi.problem
    assert "Package Keirin prediction data" in pi.problem
    assert "Make money as one person" in pi.problem
    assert "Race data is accessible" in pi.problem
    assert "best branch" in pi.problem

    # Constraints include inherited + branch attributes
    assert "low capital" in pi.constraints
    assert any("Required capital: low" in c for c in pi.constraints)
    assert any("Required skill: data science" in c for c in pi.constraints)

    # Context includes domain + branch attributes
    assert "AI systems" in pi.context
    assert "validation speed: weeks" in pi.context.lower()
    assert "personal fit" in pi.context.lower()
    assert "data availability" in pi.context.lower()
