"""Evaluator role wrappers. Each judge returns an AxisEvaluation with
score + short rationale + one improvement suggestion.
"""
from __future__ import annotations

from typing import List

from idea_search.providers.base import LLMProvider
from idea_search.roles.prompts import EVALUATOR_PROMPTS
from idea_search.schema import Idea, AxisEvaluation, Evaluation, ProblemInput


EVALUATOR_ROLES = [
    "NoveltyJudge",
    "FeasibilityJudge",
    "ValueJudge",
    "RiskJudge",
]


def _axis(provider: LLMProvider, judge: str, problem: ProblemInput, idea: Idea) -> AxisEvaluation:
    raw = provider.evaluate_axis(
        judge=judge,
        system_prompt=EVALUATOR_PROMPTS[judge],
        problem=problem.problem,
        idea_title=idea.title,
        idea_statement=idea.statement,
    )
    return AxisEvaluation(
        score=float(raw.get("score", 0.0)),
        rationale=str(raw.get("rationale", "")),
        suggestion=str(raw.get("suggestion", "")),
    )


def evaluate_idea(provider: LLMProvider, problem: ProblemInput, idea: Idea) -> Evaluation:
    return Evaluation(
        idea_id=idea.id,
        novelty=_axis(provider, "NoveltyJudge", problem, idea),
        feasibility=_axis(provider, "FeasibilityJudge", problem, idea),
        value=_axis(provider, "ValueJudge", problem, idea),
        risk=_axis(provider, "RiskJudge", problem, idea),
    )
