"""Baseline idea generation runners.

Used to compare against the role-separated generator/evaluator system.
Two modes:
    - single_shot: one provider call, no critique, no evaluation
    - self_critique: single model generates, then critiques and revises
      its own output (single-model loop, not role-separated)
"""
from __future__ import annotations

import uuid
from typing import List

from idea_search.providers.base import LLMProvider
from idea_search.schema import Idea, ProblemInput


def _to_idea(raw: dict, role: str) -> Idea:
    return Idea(
        id=uuid.uuid4().hex[:10],
        round=0,
        role=role,
        title=str(raw.get("title", "(untitled)")),
        statement=str(raw.get("statement", "")),
        rationale=str(raw.get("rationale", "")),
        tags=list(raw.get("tags", [])),
    )


def run_baseline_single_shot(
    provider: LLMProvider,
    problem: ProblemInput,
    n: int = 3,
) -> List[Idea]:
    """One provider call, N generic ideas. No evaluation, no archive."""
    raw_list = provider.generate_baseline(
        problem=problem.problem,
        constraints=problem.constraints,
        context=problem.context or "",
        n=n,
    )
    return [_to_idea(r, role="BaselineSingle") for r in raw_list]


def run_baseline_self_critique(
    provider: LLMProvider,
    problem: ProblemInput,
    n: int = 3,
) -> List[Idea]:
    """Single model generates, then critiques itself, then revises.
    No role separation, no external evaluator.
    """
    raw_list = provider.generate_baseline(
        problem=problem.problem,
        constraints=problem.constraints,
        context=problem.context or "",
        n=n,
    )
    revised = provider.self_critique(problem=problem.problem, ideas=raw_list)
    return [_to_idea(r, role="BaselineSelfCritique") for r in revised]
