from idea_search.similarity import (
    jaccard, tokenize, matches_cliche_pattern, compile_cliche_patterns,
)


def test_jaccard_identical():
    assert jaccard("alpha beta gamma", "alpha beta gamma") == 1.0


def test_jaccard_disjoint():
    assert jaccard("alpha beta", "gamma delta") == 0.0


def test_jaccard_partial_overlap():
    score = jaccard("bookstore membership community", "bookstore community lounge")
    assert 0.0 < score < 1.0


def test_tokenize_removes_stopwords():
    tokens = tokenize("This is a book about bookstores")
    assert "book" in tokens
    assert "bookstores" in tokens
    assert "this" not in tokens
    assert "is" not in tokens


def test_cliche_pattern_match():
    compiled = compile_cliche_patterns([r"ai[- ]?powered?\s+platform", r"uber for"])
    assert matches_cliche_pattern("an AI-powered platform for bookstores", compiled)
    assert matches_cliche_pattern("Uber for dog walkers", compiled)
    assert not matches_cliche_pattern("a quiet salon model", compiled)
