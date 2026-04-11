from pathlib import Path

from idea_search.archive import ArchiveStore
from idea_search.schema import Idea, Evaluation, AxisEvaluation


def _ax(score: float) -> AxisEvaluation:
    return AxisEvaluation(score=score, rationale="r", suggestion="s")


def test_archive_append_and_iterate(tmp_path: Path):
    store = ArchiveStore(tmp_path / "a.jsonl")
    idea = Idea(id="abc123", round=1, role="Proposer",
                title="t", statement="s", rationale="r")
    ev = Evaluation(
        idea_id="abc123",
        novelty=_ax(4), feasibility=_ax(3), value=_ax(4), risk=_ax(2),
    )
    store.append(idea, ev, session="sess1")
    store.append(idea, None, session="sess1")

    records = list(store.iter_records())
    assert len(records) == 2
    assert records[0]["idea"]["id"] == "abc123"
    assert records[0]["evaluation"] is not None
    assert records[1]["evaluation"] is None

    texts = list(store.iter_idea_texts())
    assert len(texts) == 2
    assert texts[0][0] == "abc123"
