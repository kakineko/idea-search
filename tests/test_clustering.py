from idea_search.clustering import cluster_ideas, label_cluster
from idea_search.schema import Idea


def _make(i: int, title: str, statement: str, tags=None) -> Idea:
    return Idea(
        id=f"id{i}", round=1, role="Proposer",
        title=title, statement=statement, rationale="r",
        tags=tags or [],
    )


def test_cluster_similar_ideas_merge():
    ideas = [
        _make(1, "bookstore membership club", "weekly bookstore membership event"),
        _make(2, "bookstore membership", "weekly bookstore club for members"),
        _make(3, "bicycle repair service", "mobile bicycle repair for commuters"),
    ]
    groups = cluster_ideas(ideas, threshold=0.30)
    sizes = sorted(len(g) for g in groups)
    assert sizes == [1, 2]


def test_cluster_all_unique_when_threshold_high():
    ideas = [
        _make(1, "alpha idea one", "statement alpha"),
        _make(2, "beta idea two", "statement beta"),
        _make(3, "gamma idea three", "statement gamma"),
    ]
    groups = cluster_ideas(ideas, threshold=0.90)
    assert len(groups) == 3


def test_label_cluster_uses_tags():
    ideas = [
        _make(1, "a", "a", tags=["contrarian", "salon"]),
        _make(2, "b", "b", tags=["contrarian", "ritual"]),
    ]
    label = label_cluster(ideas, ["id1", "id2"])
    assert "contrarian" in label
