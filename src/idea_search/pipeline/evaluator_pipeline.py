"""Evaluator pipeline: runs all 4 judges independently against each idea."""
from __future__ import annotations

from typing import List, Tuple

from idea_search.providers.base import LLMProvider
from idea_search.roles.evaluators import evaluate_idea
from idea_search.schema import Idea, Evaluation, ProblemInput


def run_evaluator_round(
    provider: LLMProvider,
    problem: ProblemInput,
    ideas: List[Idea],
) -> List[Tuple[Idea, Evaluation]]:
    results: List[Tuple[Idea, Evaluation]] = []
    for idea in ideas:
        ev = evaluate_idea(provider, problem, idea)
        results.append((idea, ev))
    return results
