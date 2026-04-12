"""Branch selection: pick top-k branches by composite score."""
from __future__ import annotations

from typing import Dict, List, Tuple

from idea_search.hierarchical.schema import Branch, BranchEvaluation


def select_top_k(
    evaluated: List[Tuple[Branch, BranchEvaluation]],
    k: int = 1,
    weights: Dict[str, float] | None = None,
) -> List[Tuple[Branch, BranchEvaluation, str]]:
    """Return top-k (branch, evaluation, selection_reason) sorted by composite.

    The default k=1 keeps v1 output concise. Callers can pass higher k
    for broader exploration in future versions.
    """
    ranked = sorted(
        evaluated,
        key=lambda p: p[1].composite(weights),
        reverse=True,
    )
    results: List[Tuple[Branch, BranchEvaluation, str]] = []
    for branch, ev in ranked[:k]:
        score = ev.composite(weights)
        reason = (
            f"Ranked #{len(results) + 1} with composite={score:.2f} "
            f"(upside={ev.upside.score}, cost={ev.cost.score}, "
            f"risk={ev.risk.score}, speed={ev.validation_speed.score}, "
            f"fit={ev.personal_fit.score}, data={ev.data_availability.score})"
        )
        results.append((branch, ev, reason))
    return results
