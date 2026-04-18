# Jaccard Threshold Sensitivity Analysis

Date: 2026-04-18
Source: archive/session_8f5a463a.jsonl (24 ideas, rounds=2 experiment)
Script: scripts/jaccard_sensitivity.py

## Background

The first real provider runs (results/2026-04-18_first_real_runs.md)
found that cliche detection produced 0 hits across 24 ideas, despite
diversity collapse being visible in clustering. Hypothesis H5 suggests
the Jaccard threshold (0.55) may be too strict for same-domain ideas.

## Method

Computed pairwise Jaccard similarity on tokenized (title + statement)
text for all 24 ideas in session 8f5a463a. Tokenization reuses
`idea_search.similarity.tokenize` (regex `[a-zA-Z0-9]+`, lowercased,
length > 2, with a small built-in stop-word set). Counted how many
of the 276 unordered pairs would be flagged at each threshold.

## Results

```
Total pairs: 276
max sim:     0.171
mean sim:    0.059
median sim:  0.054
```

| Threshold | Pairs ≥ thresh | % of total | Note |
|----------:|---------------:|-----------:|------|
| 0.25 | 0 | 0.0 % | |
| 0.30 | 0 | 0.0 % | |
| 0.35 | 0 | 0.0 % | |
| 0.40 | 0 | 0.0 % | |
| 0.45 | 0 | 0.0 % | |
| 0.50 | 0 | 0.0 % | |
| 0.55 | 0 | 0.0 % | current similarity default |
| 0.60 | 0 | 0.0 % | |
| 0.70 | 0 | 0.0 % | current cliche threshold |

### Top 10 most similar pairs

```
0.171  971af61cad [Reframer        ] ↔ d32586e5ec [Reframer        ]
0.170  c8ac12f8b2 [AnalogyFinder   ] ↔ e0a4c9ff07 [AnalogyFinder   ]
0.151  3c673ba36c [Reframer        ] ↔ e0a4c9ff07 [AnalogyFinder   ]
0.135  8ad0e4d254 [Proposer        ] ↔ 3ae0a87d45 [Proposer        ]
0.133  8ad0e4d254 [Proposer        ] ↔ b78add4ca0 [ConstraintHacker]
0.132  971af61cad [Reframer        ] ↔ 70c130dd3f [ConstraintHacker]
0.126  e837163daa [Proposer        ] ↔ 23075786f3 [Proposer        ]
0.126  971af61cad [Reframer        ] ↔ 5955bd86d1 [ConstraintHacker]
0.124  8ad0e4d254 [Proposer        ] ↔ 70c130dd3f [ConstraintHacker]
0.123  3247c54dae [Synthesizer     ] ↔ 843707bea8 [Synthesizer     ]
```

## Findings

**Threshold tuning cannot save Jaccard here.** The maximum pairwise
similarity across all 276 pairs is **0.171** — below even the
lowest swept threshold (0.25). The mean (0.059) and median (0.054)
are an order of magnitude below the current default (0.55).

H5 ("Jaccard threshold is domain-sensitive") is *not* the right
framing. The correct hypothesis is stronger:

> **H5′. Lexical Jaccard on long, content-rich statements
> systematically under-estimates direction-level similarity when the
> generator produces detailed, varied prose around the same idea.**

Two ideas can be in the same strategic direction (e.g. both are
"recurring subscription with human curation") yet share so few
*specific* content words — because each elaborates with different
concrete numbers, partner types, channels, and metaphors — that
Jaccard collapses to a near-zero score.

The same-role pairs at the top of the list confirm this:
the two highest pairs are Reframer↔Reframer and
AnalogyFinder↔AnalogyFinder — yet still only 0.17.

## Implications

1. **The current Jaccard-based cliché check is a no-op for
   claude-cli output in this domain.** Setting `cliche_threshold`
   to 0.7 (or 0.55, or 0.25) is operationally equivalent: zero
   detections.
2. **Lowering the threshold further (e.g. 0.10–0.15) would start
   producing detections, but the signal-to-noise is unclear.**
   At 0.15 we would flag pairs that share only generic vocabulary
   (e.g. "subscription", "curation"); the rate of *useful* flags
   vs. spurious ones is unknown.
3. **Embedding-based similarity is now the obvious next move.**
   The clustering report already shows directional collapse
   (`curation/low-tech` had 3 ideas) that lexical Jaccard cannot
   see. An embedding score on the same 276 pairs would either
   confirm the collapse quantitatively or force us to reconsider
   what "directional collapse" means.

## Suggested actions

- **Do not** simply lower the default threshold globally — it would
  silently change comparison results across all domains without
  evidence the new value is better than 0.55.
- **Add embedding similarity** as a second metric, reported
  alongside Jaccard in compare-mode output. Only act on the
  threshold question once we can see both signals side by side.
- **Optionally**: add a `--similarity-threshold` CLI flag to make
  per-run experimentation cheaper than editing config.

## Next

See results/2026-04-18_first_real_runs.md for related next steps.
This sensitivity analysis advances next-step #1 and reframes the
problem for next-step #4 (embedding-based diversity metric).
