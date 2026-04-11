from pathlib import Path

from idea_search.controller import Controller
from idea_search.providers.mock import MockProvider
from idea_search.reporter import build_report
from idea_search.schema import ProblemInput


def _config(tmp_path: Path) -> dict:
    return {
        "rounds": 2,
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
        "cliche_patterns": [r"ai[- ]?powered?\s+platform", r"uber for"],
    }


def test_controller_end_to_end(tmp_path: Path):
    problem = ProblemInput(
        problem="Help small independent bookstores survive without discounts.",
        constraints=["no discounts", "budget under 5000 USD"],
        context="Urban bookstores in Japan and US.",
    )
    controller = Controller(MockProvider(), _config(tmp_path))
    result = controller.run(problem)

    assert result["rounds"] == 2
    assert len(result["evaluated"]) > 0
    # Each evaluated idea has 4-axis evaluation with score+rationale+suggestion
    for idea, ev in result["evaluated"]:
        for axis in (ev.novelty, ev.feasibility, ev.value, ev.risk):
            assert 0 <= axis.score <= 5
            assert axis.rationale
            assert axis.suggestion

    # Synthesizer should appear in both rounds
    synth_rounds = {i.round for i, _ in result["evaluated"] if i.role == "Synthesizer"}
    assert synth_rounds == {1, 2}

    report = build_report(
        problem=problem.problem,
        rounds=result["rounds"],
        evaluated=result["evaluated"],
        cliche_reasons=result["cliche_reasons"],
        config=_config(tmp_path),
    )
    # We expect multiple clusters so the user can compare directions
    assert len(report.clusters) >= 2
    assert len(report.top_per_cluster) >= 2
