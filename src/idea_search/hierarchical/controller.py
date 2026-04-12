"""Hierarchical controller: orchestrates Goal → Branch → Method search."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from idea_search.controller import Controller as MethodController
from idea_search.hierarchical.branch_evaluator import evaluate_branches
from idea_search.hierarchical.branch_selector import select_top_k
from idea_search.hierarchical.goal_decomposer import decompose_goal
from idea_search.hierarchical.method_adapter import (
    build_method_search_input,
    to_problem_input,
)
from idea_search.hierarchical.schema import (
    Branch,
    BranchEvaluation,
    Goal,
    MethodSearchInput,
)
from idea_search.providers.base import LLMProvider
from idea_search.reporter import build_report
from idea_search.schema import FinalReport


@dataclass
class GoalSearchResult:
    goal: Goal
    branches: List[Branch]
    evaluations: List[Tuple[Branch, BranchEvaluation]]
    selected: List[Tuple[Branch, BranchEvaluation, str]]


@dataclass
class HierarchicalResult:
    goal_search: GoalSearchResult
    method_results: List[Tuple[MethodSearchInput, FinalReport]] = field(
        default_factory=list,
    )


class HierarchicalController:
    def __init__(
        self,
        provider: LLMProvider,
        config: Dict[str, Any],
    ):
        self.provider = provider
        self.config = config

    def run_goal_search(
        self,
        goal: Goal,
        n_branches: int = 5,
    ) -> GoalSearchResult:
        branches = decompose_goal(self.provider, goal, n=n_branches)
        evaluated = evaluate_branches(self.provider, branches, goal)
        selected = select_top_k(evaluated, k=len(evaluated))
        return GoalSearchResult(
            goal=goal,
            branches=branches,
            evaluations=evaluated,
            selected=selected,
        )

    def run_hierarchical(
        self,
        goal: Goal,
        n_branches: int = 5,
        top_k: int = 1,
        weights: Dict[str, float] | None = None,
    ) -> HierarchicalResult:
        branches = decompose_goal(self.provider, goal, n=n_branches)
        evaluated = evaluate_branches(self.provider, branches, goal)
        selected = select_top_k(evaluated, k=top_k, weights=weights)

        goal_search = GoalSearchResult(
            goal=goal,
            branches=branches,
            evaluations=evaluated,
            selected=selected,
        )

        method_results: List[Tuple[MethodSearchInput, FinalReport]] = []
        for branch, ev, reason in selected:
            msi = build_method_search_input(branch, goal, reason)
            problem_input = to_problem_input(msi)

            method_ctrl = MethodController(self.provider, self.config)
            raw = method_ctrl.run(problem_input)
            report = build_report(
                problem=problem_input.problem,
                rounds=raw["rounds"],
                evaluated=raw["evaluated"],
                cliche_reasons=raw["cliche_reasons"],
                config=self.config,
            )
            method_results.append((msi, report))

        return HierarchicalResult(
            goal_search=goal_search,
            method_results=method_results,
        )
