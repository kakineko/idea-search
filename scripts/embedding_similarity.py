"""Embedding-based similarity analysis on existing archive.

Encodes every idea with sentence-transformers/all-MiniLM-L6-v2 and
reports pairwise cosine similarity, alongside the lexical Jaccard
score from idea_search.similarity for the same pairs.

Requires the [analysis] extras. Run inside a virtual environment:
    pip install -e ".[analysis]"
    python scripts/embedding_similarity.py <archive_path>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

from idea_search.similarity import jaccard


_MODEL_NAME = "all-MiniLM-L6-v2"
_THRESHOLDS = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90)


def load_records(path: Path) -> List[dict]:
    out: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def idea_text(rec: dict) -> Tuple[str, str, int, str]:
    """Return (id, role, round, title+statement)."""
    idea = rec.get("idea") or {}
    iid = idea.get("id", "?")
    role = idea.get("role", "?")
    rnd = idea.get("round", 0)
    title = idea.get("title", "")
    statement = idea.get("statement", "")
    return iid, role, rnd, f"{title}. {statement}"


def cos(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <archive_path>", file=sys.stderr)
        return 2

    path = Path(argv[1])
    records = load_records(path)
    print(f"Loaded {len(records)} records from {path.name}")

    rows = [idea_text(r) for r in records]
    texts = [r[3] for r in rows]

    print(f"Encoding {len(texts)} ideas with {_MODEL_NAME}...")
    model = SentenceTransformer(_MODEL_NAME)
    embeddings = model.encode(texts, show_progress_bar=False)
    print(f"Embedding shape: {embeddings.shape}")

    # Pairwise cosine + matched Jaccard
    pairs: List[Tuple[float, float, str, str, str, str]] = []
    for i in range(len(rows)):
        id_i, role_i, _, text_i = rows[i]
        for j in range(i + 1, len(rows)):
            id_j, role_j, _, text_j = rows[j]
            emb_sim = cos(embeddings[i], embeddings[j])
            jac_sim = jaccard(text_i, text_j)
            pairs.append((emb_sim, jac_sim, id_i, role_i, id_j, role_j))

    pairs.sort(reverse=True)
    n_pairs = len(pairs)
    embs = [p[0] for p in pairs]
    jacs = [p[1] for p in pairs]

    print()
    print(f"Total pairs: {n_pairs}")
    print(f"{'metric':<10} {'max':>7} {'mean':>7} {'median':>7} {'min':>7}")
    print("-" * 42)
    print(
        f"{'embedding':<10} "
        f"{max(embs):>7.3f} {sum(embs)/n_pairs:>7.3f} "
        f"{sorted(embs)[n_pairs // 2]:>7.3f} {min(embs):>7.3f}"
    )
    print(
        f"{'jaccard':<10} "
        f"{max(jacs):>7.3f} {sum(jacs)/n_pairs:>7.3f} "
        f"{sorted(jacs)[n_pairs // 2]:>7.3f} {min(jacs):>7.3f}"
    )
    print()

    print(f"{'threshold':>10}  {'pairs ≥ thresh':>16}  {'pct of total':>14}")
    print("-" * 46)
    for t in _THRESHOLDS:
        count = sum(1 for s in embs if s >= t)
        pct = (count / n_pairs * 100.0) if n_pairs else 0.0
        print(f"{t:>10.2f}  {count:>16d}  {pct:>13.1f}%")

    print()
    print("Top 10 most similar pairs (embedding):")
    print(
        f"  {'emb':>5}  {'jac':>5}  "
        f"{'id_a':<10} {'role_a':<16}    "
        f"{'id_b':<10} {'role_b':<16}"
    )
    for emb_sim, jac_sim, id_i, role_i, id_j, role_j in pairs[:10]:
        print(
            f"  {emb_sim:.3f}  {jac_sim:.3f}  "
            f"{id_i:<10} {role_i:<16}  ↔ "
            f"{id_j:<10} {role_j:<16}"
        )

    print()
    print("Same pairs ranked by Jaccard (top 5) for comparison:")
    by_jaccard = sorted(pairs, key=lambda p: p[1], reverse=True)[:5]
    print(
        f"  {'jac':>5}  {'emb':>5}  "
        f"{'id_a':<10} {'role_a':<16}    "
        f"{'id_b':<10} {'role_b':<16}"
    )
    for emb_sim, jac_sim, id_i, role_i, id_j, role_j in by_jaccard:
        print(
            f"  {jac_sim:.3f}  {emb_sim:.3f}  "
            f"{id_i:<10} {role_i:<16}  ↔ "
            f"{id_j:<10} {role_j:<16}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
