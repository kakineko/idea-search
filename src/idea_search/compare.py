"""Comparison runner: execute several pipeline variants on the same
problem and collect results into a single structured ModeResult list.
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from idea_search.baseline import (
    run_baseline_self_critique,
    run_baseline_single_shot,
)
from idea_search.charter import load_charter, merge_charter_into_config
from idea_search.clustering import cluster_ideas
from idea_search.controller import Controller
from idea_search.modes import Mode
from idea_search.pipeline.evaluator_pipeline import run_evaluator_round
from idea_search.pipeline.generator_pipeline import run_generator_round
from idea_search.providers.base import LLMProvider
from idea_search.schema import Evaluation, Idea, ProblemInput
from idea_search.similarity import jaccard


@dataclass(frozen=True)
class DiversityMetrics:
    """Machine diversity indicators for a mode's output."""
    n_ideas: int
    unique_tags: int
    avg_pairwise_similarity: float  # 0..1, lower = more diverse
    cluster_count_proxy: int        # clusters under a fixed threshold


@dataclass
class ModeResult:
    mode: Mode
    ideas: List[Idea]
    evaluations: Dict[str, Evaluation] = field(default_factory=dict)
    diversity: Optional[DiversityMetrics] = None
    cliche_count: int = 0

    def mode_name(self) -> str:
        return self.mode.value


# ----------------------------------------------------------------------
# Diversity metrics
# ----------------------------------------------------------------------

_DIVERSITY_CLUSTER_THRESHOLD = 0.40


def compute_diversity(ideas: List[Idea]) -> DiversityMetrics:
    if not ideas:
        return DiversityMetrics(
            n_ideas=0,
            unique_tags=0,
            avg_pairwise_similarity=0.0,
            cluster_count_proxy=0,
        )

    tag_set = {t for i in ideas for t in i.tags}

    if len(ideas) < 2:
        avg_sim = 0.0
    else:
        pairs: List[float] = []
        for i in range(len(ideas)):
            for j in range(i + 1, len(ideas)):
                pairs.append(jaccard(
                    ideas[i].title + " " + " ".join(ideas[i].tags),
                    ideas[j].title + " " + " ".join(ideas[j].tags),
                ))
        avg_sim = sum(pairs) / len(pairs) if pairs else 0.0

    clusters = cluster_ideas(ideas, threshold=_DIVERSITY_CLUSTER_THRESHOLD)

    return DiversityMetrics(
        n_ideas=len(ideas),
        unique_tags=len(tag_set),
        avg_pairwise_similarity=round(avg_sim, 3),
        cluster_count_proxy=len(clusters),
    )


# ----------------------------------------------------------------------
# Per-mode runners
# ----------------------------------------------------------------------

def _mode_config(base_config: Dict[str, Any], archive_path: Path) -> Dict[str, Any]:
    """Clone config with a mode-local archive path to prevent cross-mode pollution."""
    import copy
    cfg = copy.deepcopy(base_config)
    cfg.setdefault("archive", {})["path"] = str(archive_path)
    return cfg


def _run_generator_only(
    provider: LLMProvider,
    problem: ProblemInput,
    config: Dict[str, Any],
) -> List[Idea]:
    """6 generator roles, no evaluator, no archive, no cliché flag."""
    rounds = int(config.get("rounds", 1))
    previous: List[Tuple[Idea, Evaluation]] | None = None
    all_ideas: List[Idea] = []
    cfg_no_cliche = dict(config)
    cfg_no_cliche["cliche_patterns"] = []  # disable regex check
    for r in range(1, rounds + 1):
        ideas = run_generator_round(
            provider=provider,
            problem=problem,
            round_index=r,
            previous_evaluated=previous,
            archive_texts=[],  # no archive for this mode
            config=cfg_no_cliche,
        )
        all_ideas.extend(ideas)
        previous = None  # no evaluation to feed forward
    return all_ideas


def _run_gen_eval(
    provider: LLMProvider,
    problem: ProblemInput,
    config: Dict[str, Any],
) -> Tuple[List[Idea], Dict[str, Evaluation]]:
    """6 generator roles + 4 evaluators, no archive, no cliché, no cluster filter."""
    rounds = int(config.get("rounds", 1))
    previous: List[Tuple[Idea, Evaluation]] | None = None
    all_ideas: List[Idea] = []
    ev_map: Dict[str, Evaluation] = {}
    cfg_no_cliche = dict(config)
    cfg_no_cliche["cliche_patterns"] = []
    for r in range(1, rounds + 1):
        ideas = run_generator_round(
            provider=provider,
            problem=problem,
            round_index=r,
            previous_evaluated=previous,
            archive_texts=[],
            config=cfg_no_cliche,
        )
        evaluated = run_evaluator_round(provider, problem, ideas)
        all_ideas.extend(ideas)
        for idea, ev in evaluated:
            ev_map[idea.id] = ev
        previous = evaluated
    return all_ideas, ev_map


def _run_full(
    provider: LLMProvider,
    problem: ProblemInput,
    config: Dict[str, Any],
) -> Tuple[List[Idea], Dict[str, Evaluation]]:
    controller = Controller(provider, config)
    result = controller.run(problem)
    ideas = [p[0] for p in result["evaluated"]]
    ev_map = {i.id: ev for i, ev in result["evaluated"]}
    return ideas, ev_map


# ----------------------------------------------------------------------
# Top-level comparison orchestrator
# ----------------------------------------------------------------------

class CompareRunner:
    def __init__(self, provider: LLMProvider, base_config: Dict[str, Any]):
        self.provider = provider
        self.base_config = base_config
        self.charter = load_charter()
        merge_charter_into_config(self.charter, self.base_config)

    def run(
        self,
        problem: ProblemInput,
        modes: List[Mode],
        baseline_n: int = 3,
    ) -> List[ModeResult]:
        results: List[ModeResult] = []
        with tempfile.TemporaryDirectory(prefix="idea-search-compare-") as tmp:
            tmp_path = Path(tmp)
            for mode in modes:
                archive_path = tmp_path / f"{mode.value}.jsonl"
                cfg = _mode_config(self.base_config, archive_path)
                mr = self._run_one(mode, problem, cfg, baseline_n=baseline_n)
                mr.diversity = compute_diversity(mr.ideas)
                mr.cliche_count = sum(1 for i in mr.ideas if i.cliche_flag)
                results.append(mr)
        return results

    def _run_one(
        self,
        mode: Mode,
        problem: ProblemInput,
        config: Dict[str, Any],
        baseline_n: int,
    ) -> ModeResult:
        if mode is Mode.BASELINE_SINGLE:
            ideas = run_baseline_single_shot(self.provider, problem, n=baseline_n)
            return ModeResult(mode=mode, ideas=ideas)
        if mode is Mode.BASELINE_SELF_CRITIQUE:
            ideas = run_baseline_self_critique(self.provider, problem, n=baseline_n)
            return ModeResult(mode=mode, ideas=ideas)
        if mode is Mode.GENERATOR_ONLY:
            ideas = _run_generator_only(self.provider, problem, config)
            return ModeResult(mode=mode, ideas=ideas)
        if mode is Mode.GEN_EVAL:
            ideas, ev_map = _run_gen_eval(self.provider, problem, config)
            return ModeResult(mode=mode, ideas=ideas, evaluations=ev_map)
        if mode is Mode.FULL:
            ideas, ev_map = _run_full(self.provider, problem, config)
            return ModeResult(mode=mode, ideas=ideas, evaluations=ev_map)
        raise ValueError(f"Unhandled mode: {mode}")
