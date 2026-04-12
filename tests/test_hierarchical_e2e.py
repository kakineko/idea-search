from pathlib import Path

from idea_search.hierarchical.controller import HierarchicalController
from idea_search.hierarchical.reporter import render_goal_search, render_hierarchical
from idea_search.hierarchical.schema import Goal
from idea_search.providers.mock import MockProvider


def _goal() -> Goal:
    return Goal(
        goal_id="g1",
        goal_statement="Find realistic ways for one person to make money",
        constraints=["low initial capital", "testable within 2 weeks"],
        domain_context=["AI systems", "Keirin prediction"],
    )


def _config(tmp_path: Path) -> dict:
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
        "archive": {"path": str(tmp_path / "archive.jsonl")},
        "cliche_patterns": [],
    }


def test_goal_search_produces_branches_and_evaluations(tmp_path: Path):
    ctrl = HierarchicalController(MockProvider(), _config(tmp_path))
    result = ctrl.run_goal_search(_goal(), n_branches=5)

    assert len(result.branches) == 5
    assert len(result.evaluations) == 5
    assert len(result.selected) == 5  # goal-search returns all ranked
    for b, ev in result.evaluations:
        assert ev.branch_id == b.branch_id
        assert 0 <= ev.upside.score <= 5


def test_hierarchical_full_runs_method_search(tmp_path: Path):
    ctrl = HierarchicalController(MockProvider(), _config(tmp_path))
    result = ctrl.run_hierarchical(_goal(), n_branches=5, top_k=1)

    assert len(result.goal_search.branches) == 5
    assert len(result.method_results) == 1  # top_k=1

    msi, report = result.method_results[0]
    assert msi.selected_branch.branch_name
    assert msi.inherited_goal.goal_id == "g1"
    assert report.total_ideas > 0
    assert len(report.clusters) >= 1


def test_hierarchical_full_top_k_2(tmp_path: Path):
    ctrl = HierarchicalController(MockProvider(), _config(tmp_path))
    result = ctrl.run_hierarchical(_goal(), n_branches=5, top_k=2)

    assert len(result.method_results) == 2
    # Different branches
    branch_names = {msi.selected_branch.branch_name for msi, _ in result.method_results}
    assert len(branch_names) == 2


def test_render_goal_search_output(tmp_path: Path):
    ctrl = HierarchicalController(MockProvider(), _config(tmp_path))
    result = ctrl.run_goal_search(_goal())
    text = render_goal_search(result)
    assert "GOAL SEARCH REPORT" in text
    assert "Upside" in text
    assert "Selected:" in text


def test_render_hierarchical_output(tmp_path: Path):
    ctrl = HierarchicalController(MockProvider(), _config(tmp_path))
    result = ctrl.run_hierarchical(_goal(), top_k=1)
    text = render_hierarchical(result)
    assert "GOAL SEARCH REPORT" in text
    assert "METHOD SEARCH" in text
    assert "Branch:" in text
