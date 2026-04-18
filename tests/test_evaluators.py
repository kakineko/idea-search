"""Tests for evaluator role wrapper parallelization."""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from idea_search.providers.base import LLMProvider
from idea_search.providers.mock import MockProvider
from idea_search.roles.evaluators import evaluate_idea
from idea_search.schema import Idea, ProblemInput


def _make_idea() -> Idea:
    return Idea(
        id="idea-1",
        round=1,
        role="Proposer",
        title="[Proposer/direct-service] Offer a curated hands-on service",
        statement="Test statement for parallel evaluator.",
        rationale="Test rationale.",
        tags=["proposer", "direct-service", "test"],
    )


def _make_problem() -> ProblemInput:
    return ProblemInput(problem="How to help a local shop", constraints=[], context=None)


class _SequentialReference:
    """Reference sequential implementation used in the equivalence test.

    Mirrors the original pre-parallelization logic so we can assert that
    the parallel version in evaluate_idea produces identical results when
    the provider is deterministic.
    """

    @staticmethod
    def run(provider: LLMProvider, problem: ProblemInput, idea: Idea):
        from idea_search.roles.evaluators import _axis
        from idea_search.schema import Evaluation

        return Evaluation(
            idea_id=idea.id,
            novelty=_axis(provider, "NoveltyJudge", problem, idea),
            feasibility=_axis(provider, "FeasibilityJudge", problem, idea),
            value=_axis(provider, "ValueJudge", problem, idea),
            risk=_axis(provider, "RiskJudge", problem, idea),
        )


class _FailingProvider(LLMProvider):
    """Mock provider that raises on selected judges but delegates the rest
    to MockProvider for deterministic output.
    """

    name = "failing"

    def __init__(self, failing_judges: set[str]) -> None:
        self._failing = failing_judges
        self._inner = MockProvider()

    def generate_ideas(self, *args, **kwargs) -> List[Dict[str, Any]]:
        return self._inner.generate_ideas(*args, **kwargs)

    def evaluate_axis(
        self,
        judge: str,
        system_prompt: str,
        problem: str,
        idea_title: str,
        idea_statement: str,
    ) -> Dict[str, Any]:
        if judge in self._failing:
            raise RuntimeError(f"{judge} simulated failure")
        return self._inner.evaluate_axis(
            judge=judge,
            system_prompt=system_prompt,
            problem=problem,
            idea_title=idea_title,
            idea_statement=idea_statement,
        )


def test_evaluate_idea_parallel_returns_same_as_sequential() -> None:
    provider = MockProvider()
    problem = _make_problem()
    idea = _make_idea()

    parallel = evaluate_idea(provider, problem, idea)
    sequential = _SequentialReference.run(provider, problem, idea)

    assert parallel.idea_id == sequential.idea_id
    assert parallel.novelty == sequential.novelty
    assert parallel.feasibility == sequential.feasibility
    assert parallel.value == sequential.value
    assert parallel.risk == sequential.risk


def test_evaluate_idea_one_judge_fails() -> None:
    provider = _FailingProvider(failing_judges={"NoveltyJudge"})
    problem = _make_problem()
    idea = _make_idea()

    result = evaluate_idea(provider, problem, idea)

    assert result.idea_id == idea.id
    assert result.novelty.score == 0.0
    assert result.novelty.rationale == "(evaluation failed)"
    assert result.novelty.suggestion == ""
    # Other judges should succeed with non-default values
    assert result.feasibility.rationale != "(evaluation failed)"
    assert result.value.rationale != "(evaluation failed)"
    assert result.risk.rationale != "(evaluation failed)"


def test_evaluate_idea_all_judges_fail() -> None:
    provider = _FailingProvider(
        failing_judges={
            "NoveltyJudge",
            "FeasibilityJudge",
            "ValueJudge",
            "RiskJudge",
        }
    )
    problem = _make_problem()
    idea = _make_idea()

    with pytest.raises(RuntimeError, match="simulated failure"):
        evaluate_idea(provider, problem, idea)
