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


def _make_idea(idea_id: str) -> Idea:
    return Idea(id=idea_id, round=1, role="Proposer",
                title=f"t-{idea_id}", statement=f"s-{idea_id}", rationale="r")


def test_clear_empties_file(tmp_path: Path):
    store = ArchiveStore(tmp_path / "a.jsonl")
    store.append(_make_idea("x1"), None, session="s")
    store.append(_make_idea("x2"), None, session="s")
    assert len(list(store.iter_records())) == 2

    store.clear()
    assert list(store.iter_records()) == []
    assert store.path.exists()
    assert store.path.read_text(encoding="utf-8") == ""


def test_clear_creates_parent_dir(tmp_path: Path):
    nested = tmp_path / "deeply" / "nested" / "a.jsonl"
    store = ArchiveStore(nested)
    # Manually remove the directory created by __init__ to simulate fresh
    nested.parent.rmdir()
    assert not nested.parent.exists()

    store.clear()
    assert nested.exists()
    assert nested.read_text(encoding="utf-8") == ""


def test_iter_records_filters_by_session(tmp_path: Path):
    store = ArchiveStore(tmp_path / "a.jsonl")
    store.append(_make_idea("a"), None, session="alpha")
    store.append(_make_idea("b"), None, session="beta")
    store.append(_make_idea("c"), None, session="alpha")

    assert len(list(store.iter_records())) == 3
    alpha = list(store.iter_records(session="alpha"))
    assert [r["idea"]["id"] for r in alpha] == ["a", "c"]
    assert list(store.iter_records(session="beta"))[0]["idea"]["id"] == "b"
    assert list(store.iter_records(session="missing")) == []


def test_iter_idea_texts_filters_by_session(tmp_path: Path):
    store = ArchiveStore(tmp_path / "a.jsonl")
    store.append(_make_idea("a"), None, session="alpha")
    store.append(_make_idea("b"), None, session="beta")

    alpha_texts = list(store.iter_idea_texts(session="alpha"))
    assert [iid for iid, _ in alpha_texts] == ["a"]
    assert list(store.iter_idea_texts(session="beta"))[0][0] == "b"
    # No filter still yields all
    assert len(list(store.iter_idea_texts())) == 2
