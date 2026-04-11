"""Greedy Jaccard-distance clustering. Simple and dependency-free."""
from __future__ import annotations

from typing import List, Dict
from idea_search.schema import Idea
from idea_search.similarity import jaccard


def _cluster_signal(idea: Idea) -> str:
    """Short, distinctive text for clustering.
    Uses title + tags so that boilerplate in statements does not collapse
    every idea into one cluster.
    """
    return idea.title + " " + " ".join(idea.tags)


def cluster_ideas(ideas: List[Idea], threshold: float = 0.40) -> List[List[str]]:
    """Return groups of idea ids. Two ideas go in the same cluster if
    their Jaccard similarity >= threshold. Greedy single-link.
    """
    clusters: List[List[str]] = []
    cluster_texts: List[List[str]] = []

    for idea in ideas:
        signal = _cluster_signal(idea)
        placed = False
        for cid, members in enumerate(clusters):
            for t in cluster_texts[cid]:
                if jaccard(signal, t) >= threshold:
                    members.append(idea.id)
                    cluster_texts[cid].append(signal)
                    placed = True
                    break
            if placed:
                break
        if not placed:
            clusters.append([idea.id])
            cluster_texts.append([signal])
    return clusters


def label_cluster(ideas: List[Idea], member_ids: List[str]) -> str:
    """Pick a short label from member tags (most frequent)."""
    counts: Dict[str, int] = {}
    for idea in ideas:
        if idea.id not in member_ids:
            continue
        for tag in idea.tags:
            counts[tag] = counts.get(tag, 0) + 1
    if not counts:
        return "untagged"
    sorted_tags = sorted(counts.items(), key=lambda p: (-p[1], p[0]))
    return "/".join(t for t, _ in sorted_tags[:2])
