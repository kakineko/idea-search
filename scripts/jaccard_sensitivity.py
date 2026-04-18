"""Jaccard threshold sensitivity analysis on an existing archive.

Sweeps a range of similarity thresholds over the (title + statement)
tokens of every idea in a session JSONL file, reporting how many idea
pairs would be flagged as similar at each threshold.

Usage:
    python scripts/jaccard_sensitivity.py <archive_path>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Tuple

from idea_search.similarity import jaccard, tokenize


THRESHOLDS = (0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70)


def load_records(path: Path) -> List[dict]:
    out: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def idea_text(rec: dict) -> Tuple[str, str, str]:
    """Return (id, role, title+statement) for one archive record."""
    idea = rec.get("idea") or {}
    iid = idea.get("id", "?")
    role = idea.get("role", "?")
    title = idea.get("title", "")
    statement = idea.get("statement", "")
    return iid, role, f"{title}. {statement}"


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <archive_path>", file=sys.stderr)
        return 2

    path = Path(argv[1])
    records = load_records(path)
    print(f"Loaded {len(records)} records from {path.name}")

    rows = [idea_text(r) for r in records]

    # Pairwise Jaccard over (title + statement)
    pairs: List[Tuple[float, str, str, str, str]] = []
    for i in range(len(rows)):
        id_i, role_i, text_i = rows[i]
        for j in range(i + 1, len(rows)):
            id_j, role_j, text_j = rows[j]
            sim = jaccard(text_i, text_j)
            pairs.append((sim, id_i, role_i, id_j, role_j))

    pairs.sort(reverse=True)
    n_pairs = len(pairs)
    max_sim = pairs[0][0] if pairs else 0.0
    median_sim = pairs[n_pairs // 2][0] if pairs else 0.0
    mean_sim = sum(p[0] for p in pairs) / n_pairs if n_pairs else 0.0

    print()
    print(f"Total pairs: {n_pairs}")
    print(f"max sim:     {max_sim:.3f}")
    print(f"mean sim:    {mean_sim:.3f}")
    print(f"median sim:  {median_sim:.3f}")
    print()

    print(f"{'threshold':>10}  {'pairs ≥ thresh':>16}  {'pct of total':>14}")
    print("-" * 46)
    for t in THRESHOLDS:
        count = sum(1 for p in pairs if p[0] >= t)
        pct = (count / n_pairs * 100.0) if n_pairs else 0.0
        marker = ""
        if t == 0.55:
            marker = "  <-- current default"
        if t == 0.70:
            marker = "  <-- current cliche threshold"
        print(f"{t:>10.2f}  {count:>16d}  {pct:>13.1f}%{marker}")

    print()
    print("Top 10 most similar pairs (id [role] ↔ id [role]):")
    for sim, id_i, role_i, id_j, role_j in pairs[:10]:
        print(f"  {sim:.3f}  {id_i} [{role_i:<16}] ↔ {id_j} [{role_j:<16}]")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
