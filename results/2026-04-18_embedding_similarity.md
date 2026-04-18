# Embedding Similarity Analysis

Date: 2026-04-18
Source: archive/session_8f5a463a.jsonl (24 ideas, rounds=2 experiment)
Script: scripts/embedding_similarity.py
Model: sentence-transformers/all-MiniLM-L6-v2 (384-dim)

## Background

results/2026-04-18_jaccard_sensitivity.md showed Jaccard similarity
maxes out at **0.171** for claude-cli long-form ideas, rendering
threshold tuning ineffective. This analysis tests whether semantic
embedding similarity can detect the directional collapse that Jaccard
missed entirely.

## Method

Encoded all 24 idea texts (`title + ". " + statement`) with
sentence-transformers/all-MiniLM-L6-v2. Computed cosine similarity
for all 276 unordered pairs. The same script also recomputes the
Jaccard score on the same pair set so the two metrics can be compared
on identical units.

Run inside the venv created via the new `[analysis]` extras:

```
python -m venv .venv && source .venv/bin/activate
pip install -e ".[analysis]"
python scripts/embedding_similarity.py archive/session_8f5a463a.jsonl
```

## Results

### Distribution

| Metric    |   Max |  Mean | Median |   Min |
|-----------|------:|------:|-------:|------:|
| Embedding | 0.880 | 0.484 |  0.484 | 0.158 |
| Jaccard   | 0.171 | 0.059 |  0.055 | 0.000 |

### Embedding threshold sweep (276 pairs)

| Threshold | Pairs ≥ thresh | % of total |
|----------:|---------------:|-----------:|
| 0.50      | 122 | 44.2 % |
| 0.55      |  80 | 29.0 % |
| 0.60      |  50 | 18.1 % |
| 0.65      |  28 | 10.1 % |
| 0.70      |  11 |  4.0 % |
| 0.75      |   3 |  1.1 % |
| 0.80      |   1 |  0.4 % |
| 0.85      |   1 |  0.4 % |
| 0.90      |   0 |  0.0 % |

Compare to Jaccard at the same thresholds: **all zero**.
The lexical metric never produces a single hit at *any* threshold
≥ 0.25 on this data; the embedding metric produces 122 hits at 0.50
and a still-meaningful 11 hits at 0.70.

### Top 10 pairs by embedding (with matched Jaccard)

| Embedding | Jaccard | Pair |
|----------:|--------:|------|
| **0.880** | 0.126 | Proposer ↔ Proposer |
| 0.794 | 0.114 | Reframer ↔ Synthesizer |
| 0.755 | 0.062 | Reframer ↔ Synthesizer |
| 0.747 | 0.075 | ConstraintHacker ↔ Reframer |
| 0.729 | 0.101 | Reframer ↔ Synthesizer |
| 0.728 | 0.106 | Contrarian ↔ Synthesizer |
| 0.727 | 0.111 | Synthesizer ↔ Synthesizer |
| 0.718 | 0.067 | Reframer ↔ Contrarian |
| 0.709 | 0.170 | AnalogyFinder ↔ AnalogyFinder |
| 0.704 | 0.092 | Synthesizer ↔ ConstraintHacker |

### Top 5 Jaccard pairs (the only pairs lexical caught at all)

| Jaccard | Embedding | Pair |
|--------:|----------:|------|
| 0.171 | 0.657 | Reframer ↔ Reframer |
| 0.170 | 0.709 | AnalogyFinder ↔ AnalogyFinder |
| 0.151 | 0.654 | Reframer ↔ AnalogyFinder |
| 0.135 | 0.605 | Proposer ↔ Proposer |
| 0.133 | 0.697 | Proposer ↔ ConstraintHacker |

All five top-Jaccard pairs sit comfortably at embedding ≥ 0.60 —
the embedding metric **agrees with Jaccard whenever Jaccard fires**,
and additionally surfaces 117 more pairs at 0.50 that Jaccard never
sees.

## Findings

1. **The collapse is real, not a clustering artifact.** Embedding
   similarity exposes the same directional convergence that the
   `curation/low-tech (3 ideas)` cluster hinted at. The single
   highest-similarity pair (0.880, two Proposers) is a textbook
   "different prose, same idea" case that lexical Jaccard cannot
   see (0.126).
2. **Synthesizer collapses toward the rest.** Six of the top-10
   embedding pairs involve a Synthesizer. The Synthesizer is *built*
   from other roles' ideas, so directional overlap is somewhat
   expected — but it confirms that the Synthesizer is not adding
   genuinely new directions, only recombinations.
3. **Threshold ~0.70 looks usable.** It flags 11 pairs (4 % of
   total) — small enough to be a useful signal, large enough not to
   be noise from the model. A loose 0.60 threshold would flag 18 %
   of pairs and may be too permissive.
4. **Embedding is a strict superset of Jaccard's signal here.**
   Every top-Jaccard pair is also high on embedding (≥ 0.60), so
   replacing Jaccard with embedding would not lose any of the
   signal Jaccard *did* produce.

## Implications

- **Replace Jaccard with embedding similarity in cliché detection.**
  At default `cliche_threshold: 0.70` semantics, embedding correctly
  surfaces 11 pair-overlaps that the current implementation reports
  as zero.
- **Suggested defaults for runtime integration**:
  - `similarity_threshold: 0.60` (was 0.55 on Jaccard scale)
  - `cliche_threshold: 0.75` (was 0.70 on Jaccard scale)
  - At these thresholds, ~50 pairs are "similar" (18 %) and 3 are
    "cliché" (1 %) on this dataset — both seem reasonable.
- **Keep both metrics during transition.** Reporting both in
  comparison mode lets us track whether model behaviour changes
  the calibration over time.

## Cost

- Model download: ~80 MB (one-time, cached under `.venv` /
  `~/.cache/huggingface/hub/`)
- Encoding 24 ideas: < 1 s on CPU
- Pairwise cosine for 276 pairs: negligible
- No API calls, fully offline after first model fetch

## Next

This analysis advances next-step #4 from
results/2026-04-18_first_real_runs.md (embedding-based diversity
metric) and supersedes hypothesis H5 / H5′ from
results/2026-04-18_jaccard_sensitivity.md.

The follow-up integration task (not run today): fold an embedding
score into `idea_search.similarity` behind a config switch, plumb it
through `Controller` so the cliché feedback loop has real signal,
and re-run the rounds=2 experiment to see whether the Synthesizer
collapse can actually be suppressed when the model receives accurate
"this is too close to what we already said" feedback.
