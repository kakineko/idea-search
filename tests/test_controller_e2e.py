from pathlib import Path

from idea_search.controller import Controller, _resolve_archive_path
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


def test_resolve_archive_path_explicit_wins():
    """An explicit path beats both shared mode and the session default."""
    p = _resolve_archive_path({"path": "custom/here.jsonl"}, "abcd1234")
    assert p == "custom/here.jsonl"
    p = _resolve_archive_path(
        {"path": "custom/here.jsonl", "shared": True}, "abcd1234"
    )
    assert p == "custom/here.jsonl"


def test_resolve_archive_path_shared_mode():
    """shared=true (no explicit path) returns the legacy shared file."""
    assert _resolve_archive_path({"shared": True}, "abcd1234") == "archive/ideas.jsonl"


def test_resolve_archive_path_default_is_session_scoped():
    """Empty archive config yields archive/session_<id>.jsonl."""
    assert (
        _resolve_archive_path({}, "deadbeef")
        == "archive/session_deadbeef.jsonl"
    )
    # shared=false explicit: same as default
    assert (
        _resolve_archive_path({"shared": False}, "deadbeef")
        == "archive/session_deadbeef.jsonl"
    )


def test_controller_default_uses_session_scoped_path(tmp_path: Path, monkeypatch):
    """With no archive config, Controller.archive.path includes the session_id."""
    monkeypatch.chdir(tmp_path)
    config = {"rounds": 1, "provider": "mock"}
    ctrl = Controller(MockProvider(), config)
    assert ctrl.session_id in str(ctrl.archive.path)
    assert str(ctrl.archive.path).startswith("archive/session_")
    assert ctrl._archive_shared is False


def test_controller_shared_mode_uses_legacy_file(tmp_path: Path, monkeypatch):
    """archive.shared=true points back at archive/ideas.jsonl."""
    monkeypatch.chdir(tmp_path)
    config = {"rounds": 1, "provider": "mock", "archive": {"shared": True}}
    ctrl = Controller(MockProvider(), config)
    assert str(ctrl.archive.path) == "archive/ideas.jsonl"
    assert ctrl._archive_shared is True


def test_controller_session_isolated_archive_reads(tmp_path: Path):
    """Two controllers writing to the same shared file see only own session
    when read back through the per-session helper."""
    shared = tmp_path / "shared.jsonl"
    cfg = lambda: {  # noqa: E731
        "rounds": 1, "provider": "mock",
        "archive": {"path": str(shared)},  # explicit path, shared=false implicit
        "generators": ["Proposer"], "evaluators": ["NoveltyJudge"],
        "synthesizer": {"high_novelty_top_k": 1, "high_feasibility_top_k": 1,
                        "include_critic_fragments": False},
        "similarity": {"jaccard_threshold": 0.55, "cliche_threshold": 0.70},
        "clustering": {"jaccard_cluster_threshold": 0.35},
        "report": {"per_cluster_top_k": 1, "max_clusters": 3},
        "cliche_patterns": [],
    }
    problem = ProblemInput(problem="p", constraints=[], context=None)

    c1 = Controller(MockProvider(), cfg())
    c1.run(problem)
    c2 = Controller(MockProvider(), cfg())
    # c2 must NOT see c1's records when reading through the session helper
    own = list(c2._read_archive_texts())
    assert own == []
    # But the underlying file does contain c1's writes
    all_records = list(c2.archive.iter_records())
    assert len(all_records) > 0
    assert all(r["session"] == c1.session_id for r in all_records)
