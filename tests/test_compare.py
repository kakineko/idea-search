from pathlib import Path

from idea_search.compare import CompareRunner, compute_diversity
from idea_search.compare_report import render_comparison
from idea_search.modes import Mode
from idea_search.providers.mock import MockProvider
from idea_search.schema import Idea, ProblemInput


def _config() -> dict:
    return {
        "rounds": 1,
        "provider": "mock",
        "generators": [
            "Proposer", "Reframer", "Contrarian",
            "AnalogyFinder", "ConstraintHacker", "Synthesizer",
        ],
        "evaluators": ["NoveltyJudge", "FeasibilityJudge", "ValueJudge", "RiskJudge"],
        "synthesizer": {
            "high_novelty_top_k": 2,
            "high_feasibility_top_k": 2,
            "include_critic_fragments": True,
        },
        "similarity": {"jaccard_threshold": 0.55, "cliche_threshold": 0.70},
        "clustering": {"jaccard_cluster_threshold": 0.35},
        "report": {"per_cluster_top_k": 2, "max_clusters": 5},
        "archive": {"path": "archive/ideas.jsonl"},
        "cliche_patterns": [],
    }


def _problem() -> ProblemInput:
    return ProblemInput(
        problem="Help small bookstores survive without discounts.",
        constraints=["no discounts"],
        context="Urban stores.",
    )


def _make(i: int, title: str, tags: list[str]) -> Idea:
    return Idea(
        id=f"id{i}", round=0, role="X",
        title=title, statement="s", rationale="r", tags=tags,
    )


def test_diversity_metrics_on_distinct_ideas():
    ideas = [
        _make(1, "alpha salon model", ["salon", "membership"]),
        _make(2, "beta bicycle repair", ["bicycle", "service"]),
        _make(3, "gamma craft ritual", ["ritual", "craft"]),
    ]
    d = compute_diversity(ideas)
    assert d.n_ideas == 3
    assert d.unique_tags == 6
    assert d.avg_pairwise_similarity < 0.3
    assert d.cluster_count_proxy == 3


def test_diversity_metrics_on_similar_ideas():
    ideas = [
        _make(1, "bookstore club one", ["bookstore", "club"]),
        _make(2, "bookstore club two", ["bookstore", "club"]),
        _make(3, "bookstore club three", ["bookstore", "club"]),
    ]
    d = compute_diversity(ideas)
    assert d.avg_pairwise_similarity > 0.5
    assert d.cluster_count_proxy == 1
    assert d.unique_tags == 2


def test_diversity_empty_and_single():
    assert compute_diversity([]).n_ideas == 0
    single = compute_diversity([_make(1, "solo", ["x"])])
    assert single.n_ideas == 1
    assert single.avg_pairwise_similarity == 0.0


def test_compare_runner_runs_all_modes():
    runner = CompareRunner(MockProvider(), _config())
    modes = [
        Mode.BASELINE_SINGLE,
        Mode.BASELINE_SELF_CRITIQUE,
        Mode.GENERATOR_ONLY,
        Mode.GEN_EVAL,
        Mode.FULL,
    ]
    results = runner.run(_problem(), modes, baseline_n=3)
    assert len(results) == 5
    for r in results:
        assert r.diversity is not None
        assert r.diversity.n_ideas == len(r.ideas)

    # baselines should be smaller than generator-based modes
    n_baseline = results[0].diversity.n_ideas
    n_full = results[4].diversity.n_ideas
    assert n_full > n_baseline

    # gen-eval and full have evaluator scores; baselines do not
    assert len(results[3].evaluations) == len(results[3].ideas)
    assert len(results[4].evaluations) == len(results[4].ideas)
    assert results[0].evaluations == {}
    assert results[1].evaluations == {}


def test_baseline_less_diverse_than_full():
    runner = CompareRunner(MockProvider(), _config())
    results = runner.run(_problem(), [Mode.BASELINE_SINGLE, Mode.FULL])
    bl, full = results
    # Full should produce more distinct clusters than the naive baseline
    assert full.diversity.cluster_count_proxy >= bl.diversity.cluster_count_proxy
    # Full should produce more unique tags
    assert full.diversity.unique_tags > bl.diversity.unique_tags


def test_render_comparison_markdown():
    runner = CompareRunner(MockProvider(), _config())
    results = runner.run(
        _problem(),
        [Mode.BASELINE_SINGLE, Mode.GENERATOR_ONLY, Mode.FULL],
    )
    md = render_comparison(_problem().problem, results)
    assert "# Idea Search — Mode Comparison" in md
    assert "## Summary" in md
    assert "baseline-single" in md
    assert "generator-only" in md
    assert "full" in md
    # Human scoring cells must exist
    assert "[  ]" in md
    # Summary must include machine diversity columns
    assert "AvgPairwiseSim" in md
    assert "ClusterProxy" in md
