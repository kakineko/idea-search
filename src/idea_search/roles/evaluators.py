"""Evaluator role wrappers. Each judge returns an AxisEvaluation with
score + short rationale + one improvement suggestion.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
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


_AXIS_JUDGE_PAIRS = [
    ("novelty", "NoveltyJudge"),
    ("feasibility", "FeasibilityJudge"),
    ("value", "ValueJudge"),
    ("risk", "RiskJudge"),
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
    """Evaluate an idea on 4 axes in parallel (novelty, feasibility, value, risk).

    Uses a ThreadPoolExecutor with max_workers=4 so that per-judge latency
    (e.g. subprocess calls in claude-cli) overlaps instead of serializing.
    If a single judge fails, its axis falls back to a default AxisEvaluation;
    if all 4 judges fail, the first exception is re-raised.
    """
    results: dict[str, AxisEvaluation] = {}
    errors: dict[str, BaseException] = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_axis = {
            executor.submit(_axis, provider, judge_name, problem, idea): axis_name
            for axis_name, judge_name in _AXIS_JUDGE_PAIRS
        }
        for future in as_completed(future_to_axis):
            axis_name = future_to_axis[future]
            try:
                results[axis_name] = future.result()
            except Exception as exc:
                errors[axis_name] = exc

    if len(errors) == 4:
        raise next(iter(errors.values()))

    default_eval = AxisEvaluation(
        score=0.0,
        rationale="(evaluation failed)",
        suggestion="",
    )
    for axis_name in errors:
        results[axis_name] = default_eval

    return Evaluation(
        idea_id=idea.id,
        novelty=results["novelty"],
        feasibility=results["feasibility"],
        value=results["value"],
        risk=results["risk"],
    )
