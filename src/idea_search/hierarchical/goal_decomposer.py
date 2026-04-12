"""Goal decomposition: broad goal → list of strategy branches."""
from __future__ import annotations

import uuid
from typing import List

from idea_search.providers.base import LLMProvider
from idea_search.hierarchical.schema import Goal, Branch


def decompose_goal(
    provider: LLMProvider,
    goal: Goal,
    n: int = 5,
) -> List[Branch]:
    raw_list = provider.decompose_goal(
        goal_statement=goal.goal_statement,
        constraints=goal.constraints,
        domain_context=goal.domain_context,
        n=n,
    )
    branches: List[Branch] = []
    for raw in raw_list:
        branches.append(Branch(
            branch_id=uuid.uuid4().hex[:10],
            goal_id=goal.goal_id,
            branch_name=raw.get("branch_name", "(unnamed)"),
            branch_description=raw.get("branch_description", ""),
            assumptions=raw.get("assumptions", []),
            required_capital=raw.get("required_capital", "unknown"),
            required_skill=raw.get("required_skill", "unknown"),
            risk_level=raw.get("risk_level", "unknown"),
            validation_speed=raw.get("validation_speed", "unknown"),
            personal_fit=raw.get("personal_fit", "unknown"),
            data_availability=raw.get("data_availability", "unknown"),
        ))
    return branches
