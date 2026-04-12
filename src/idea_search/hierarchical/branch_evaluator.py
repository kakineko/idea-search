"""Branch evaluation: score each branch on 6 axes independently."""
from __future__ import annotations

from typing import List, Tuple

from idea_search.providers.base import LLMProvider
from idea_search.hierarchical.schema import (
    Branch,
    BranchAxisEvaluation,
    BranchEvaluation,
    Goal,
)

_AXES = ["upside", "cost", "risk", "validation_speed", "personal_fit", "data_availability"]


def evaluate_branch(
    provider: LLMProvider,
    branch: Branch,
    goal: Goal,
) -> BranchEvaluation:
    raw = provider.evaluate_branch(
        branch_name=branch.branch_name,
        branch_description=branch.branch_description,
        goal_statement=goal.goal_statement,
        domain_context=goal.domain_context,
    )
    axis_evals = {}
    for axis in _AXES:
        data = raw.get(axis, {"score": 3.0, "rationale": "", "suggestion": ""})
        axis_evals[axis] = BranchAxisEvaluation(
            score=float(data.get("score", 3.0)),
            rationale=str(data.get("rationale", "")),
            suggestion=str(data.get("suggestion", "")),
        )
    return BranchEvaluation(branch_id=branch.branch_id, **axis_evals)


def evaluate_branches(
    provider: LLMProvider,
    branches: List[Branch],
    goal: Goal,
) -> List[Tuple[Branch, BranchEvaluation]]:
    return [(b, evaluate_branch(provider, b, goal)) for b in branches]
