import pytest

from idea_search.hierarchical.schema import (
    BRANCH_AXIS_WEIGHTS,
    Branch,
    BranchAxisEvaluation,
    BranchEvaluation,
    Goal,
    MethodSearchInput,
)


def _ax(score: float) -> BranchAxisEvaluation:
    return BranchAxisEvaluation(score=score, rationale="r", suggestion="s")


def _goal() -> Goal:
    return Goal(
        goal_id="g1",
        goal_statement="make money",
        constraints=["low capital"],
        domain_context=["AI systems"],
    )


def _branch() -> Branch:
    return Branch(
        branch_id="b1", goal_id="g1",
        branch_name="SaaS tool", branch_description="Build a SaaS",
        assumptions=["market exists"],
    )


def test_branch_evaluation_composite_default_weights():
    ev = BranchEvaluation(
        branch_id="b1",
        upside=_ax(4.0), cost=_ax(2.0), risk=_ax(1.0),
        validation_speed=_ax(4.0), personal_fit=_ax(5.0), data_availability=_ax(3.0),
    )
    # default: upside + speed + fit + data - cost - risk
    # = 4 + 4 + 5 + 3 - 2 - 1 = 13
    assert ev.composite() == 13.0


def test_branch_evaluation_composite_custom_weights():
    ev = BranchEvaluation(
        branch_id="b1",
        upside=_ax(4.0), cost=_ax(2.0), risk=_ax(1.0),
        validation_speed=_ax(4.0), personal_fit=_ax(5.0), data_availability=_ax(3.0),
    )
    custom = {"upside": 2.0, "cost": -0.5, "risk": -0.5, "validation_speed": 1.0,
              "personal_fit": 1.5, "data_availability": 0.5}
    result = ev.composite(custom)
    # = 4*2 + 4*1 + 5*1.5 + 3*0.5 - 2*0.5 - 1*0.5 = 8+4+7.5+1.5-1-0.5 = 19.5
    assert result == 19.5


def test_composite_uses_scores_not_string_attrs():
    ev = BranchEvaluation(
        branch_id="b1",
        upside=_ax(5.0), cost=_ax(5.0), risk=_ax(5.0),
        validation_speed=_ax(5.0), personal_fit=_ax(5.0), data_availability=_ax(5.0),
    )
    # All positive axes = 5*1 each (4 axes) = 20
    # All negative axes = 5*(-1) each (2 axes) = -10
    # Total = 10
    assert ev.composite() == 10.0


def test_branch_axis_weights_is_immutable():
    """Mutating BRANCH_AXIS_WEIGHTS must raise — it is a read-only view."""
    with pytest.raises(TypeError):
        BRANCH_AXIS_WEIGHTS["upside"] = 99.0
    with pytest.raises(TypeError):
        del BRANCH_AXIS_WEIGHTS["upside"]


def test_branch_axis_weights_supports_dict_reads():
    """Read-side API stays dict-like for callers that iterate or .get()."""
    assert BRANCH_AXIS_WEIGHTS["upside"] == 1.0
    assert BRANCH_AXIS_WEIGHTS.get("cost") == -1.0
    assert BRANCH_AXIS_WEIGHTS.get("missing", 0.0) == 0.0
    assert set(BRANCH_AXIS_WEIGHTS.keys()) == {
        "upside", "cost", "risk",
        "validation_speed", "personal_fit", "data_availability",
    }
    assert len(BRANCH_AXIS_WEIGHTS) == 6


def test_composite_with_explicit_dict_matches_default():
    """Passing a fresh dict with identical values yields the same composite."""
    ev = BranchEvaluation(
        branch_id="b1",
        upside=_ax(4.0), cost=_ax(2.0), risk=_ax(1.0),
        validation_speed=_ax(4.0), personal_fit=_ax(5.0), data_availability=_ax(3.0),
    )
    explicit = dict(BRANCH_AXIS_WEIGHTS)
    assert ev.composite(explicit) == ev.composite()


def test_branch_axis_weights_unchanged_after_failed_mutation():
    """A failed mutation attempt must leave the underlying values intact."""
    snapshot = dict(BRANCH_AXIS_WEIGHTS)
    with pytest.raises(TypeError):
        BRANCH_AXIS_WEIGHTS["upside"] = 99.0
    assert dict(BRANCH_AXIS_WEIGHTS) == snapshot


def test_method_search_input_holds_full_context():
    msi = MethodSearchInput(
        selected_branch=_branch(),
        inherited_goal=_goal(),
        inherited_constraints=["low capital"],
        inherited_context=["AI systems"],
        selection_reason="top composite",
    )
    assert msi.selected_branch.branch_name == "SaaS tool"
    assert msi.inherited_goal.goal_statement == "make money"
    assert msi.selection_reason == "top composite"
