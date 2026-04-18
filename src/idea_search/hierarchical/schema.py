"""Hierarchical schema: Goal, Branch, BranchEvaluation, MethodSearchInput.

Extends the existing idea_search.schema without modifying it.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Dict, List, Mapping, Optional

from pydantic import BaseModel, Field


class Goal(BaseModel):
    goal_id: str
    goal_statement: str
    constraints: List[str] = Field(default_factory=list)
    domain_context: List[str] = Field(default_factory=list)


class Branch(BaseModel):
    branch_id: str
    goal_id: str
    branch_name: str
    branch_description: str
    assumptions: List[str] = Field(default_factory=list)
    required_capital: str = "unknown"
    required_skill: str = "unknown"
    risk_level: str = "unknown"
    validation_speed: str = "unknown"
    personal_fit: str = "unknown"
    data_availability: str = "unknown"


class BranchAxisEvaluation(BaseModel):
    score: float  # 0-5
    rationale: str
    suggestion: str


# Default axis weights. Positive axes add, negative axes subtract.
# Exposed as a read-only view so callers cannot mutate global state by
# accident. To experiment with different weights, pass a fresh dict to
# ``BranchEvaluation.composite`` or ``select_top_k``.
_BRANCH_AXIS_WEIGHTS_RAW: Dict[str, float] = {
    "upside": 1.0,
    "cost": -1.0,
    "risk": -1.0,
    "validation_speed": 1.0,
    "personal_fit": 1.0,
    "data_availability": 1.0,
}
BRANCH_AXIS_WEIGHTS: Mapping[str, float] = MappingProxyType(_BRANCH_AXIS_WEIGHTS_RAW)


class BranchEvaluation(BaseModel):
    branch_id: str
    upside: BranchAxisEvaluation
    cost: BranchAxisEvaluation
    risk: BranchAxisEvaluation
    validation_speed: BranchAxisEvaluation
    personal_fit: BranchAxisEvaluation
    data_availability: BranchAxisEvaluation

    def composite(self, weights: Mapping[str, float] | None = None) -> float:
        """Weighted composite from evaluated scores only (no string attrs)."""
        w = weights or BRANCH_AXIS_WEIGHTS
        axes = {
            "upside": self.upside.score,
            "cost": self.cost.score,
            "risk": self.risk.score,
            "validation_speed": self.validation_speed.score,
            "personal_fit": self.personal_fit.score,
            "data_availability": self.data_availability.score,
        }
        return sum(axes[k] * w.get(k, 0.0) for k in axes)


class MethodSearchInput(BaseModel):
    """Everything the method-search engine needs from the hierarchical layer."""
    selected_branch: Branch
    inherited_goal: Goal
    inherited_constraints: List[str] = Field(default_factory=list)
    inherited_context: List[str] = Field(default_factory=list)
    selection_reason: str = ""
