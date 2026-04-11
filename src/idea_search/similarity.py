"""Similarity + cliche detection (Jaccard + fixed regex patterns)."""
from __future__ import annotations

import re
from typing import Iterable, List, Tuple, Set


_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")
_STOP = {
    "the", "a", "an", "and", "or", "to", "of", "for", "with", "without",
    "on", "in", "at", "by", "is", "are", "be", "as", "this", "that",
    "it", "its", "from", "but", "not", "into", "their", "they", "we",
    "you", "your", "our", "one", "two", "new", "use", "using",
}


def tokenize(text: str) -> Set[str]:
    return {
        t.lower() for t in _TOKEN_RE.findall(text or "")
        if len(t) > 2 and t.lower() not in _STOP
    }


def jaccard(a: str, b: str) -> float:
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    union = ta | tb
    return len(inter) / len(union)


def most_similar(
    text: str, candidates: Iterable[Tuple[str, str]], top_k: int = 3,
) -> List[Tuple[str, float]]:
    """candidates: iterable of (id, text). Returns [(id, score), ...]."""
    scored = [(cid, jaccard(text, ctext)) for cid, ctext in candidates]
    scored.sort(key=lambda p: p[1], reverse=True)
    return scored[:top_k]


def compile_cliche_patterns(patterns: List[str]) -> List[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def matches_cliche_pattern(text: str, compiled: List[re.Pattern]) -> List[str]:
    """Return a list of pattern sources that match the text."""
    return [p.pattern for p in compiled if p.search(text or "")]
