# First Real Provider Runs

Date: 2026-04-18
Provider: claude-cli (sonnet)
Session IDs: 57d3a7ab (rounds=1), 8f5a463a (rounds=2)

## Experiment 1: Run with rounds=1

- Wall time: 17m57s
- Total ideas: 12 (6 roles × 2 each)
- Clusters: 5
- Cliche flagged: 0
- Archive size: 12 records

### Findings

- Role differentiation observed: Contrarian → military concepts,
  AnalogyFinder → biology, ConstraintHacker → B2B reversal
- Collapse observed: community/low-tech cluster had 2 ideas
  (2 of 6 roles converged to "subscription + curation")
- No cliche detected: regex patterns did not match
- JSON reliability: 0 retries, 0 fallbacks for 35+ subprocess calls

### Top ideas (composite)

| Cluster | Title | Composite | Role |
|---|---|---|---|
| asymmetric-advantage/human-intelligence | The Human Algorithm | 10.0 | Contrarian |
| biology/community-embedding | The Literary Root Network | 9.0 | AnalogyFinder |
| b2b/curation | Curated Outpost Network | 9.0 | ConstraintHacker |
| Japan-US/anti-Amazon | The Becoming Box | 9.0 | (role unclear) |
| community/low-tech | The Human Oracle Subscription | 8.0 | (community) |

## Experiment 2: Run with rounds=2

- Wall time: 34m53s
- Total ideas: 24 (12 per round)
- Clusters (final): 5
- Cliche flagged: 0 (both rounds)
- Archive size: 24 records

### Findings (UNEXPECTED)

#### Archive feedback did not prevent collapse

- curation/low-tech cluster grew to 3 ideas (worse than rounds=1's 2)
- similar_to = 0 across all rounds
- Jaccard threshold (0.55) may be too strict for same-domain ideas
- Model received archive_texts in prompt but did not strongly
  optimize for diversity

#### Quality improved with rounds, even if diversity did not

- Round 2 top-3 (composite 9.5-9.7) all from Round 2
- This suggests archive feedback helps quality refinement,
  not diversity expansion
- Opposite of H3 hypothesis

#### Evaluator may be too lenient

- All round 1 scores ≥ 7.5
- Zero critic-broken fragments for Synthesizer
- Synthesizer operated on top-3 novelty + top-3 feasibility only

#### Multiplicative diversity partially observed

- Same role produced different angles across rounds:
  - Round 1 AnalogyFinder: Mycorrhizal
  - Round 2 AnalogyFinder: US Special Forces + mycorrhizal hybrid
- This is encouraging but did not translate to cluster diversity

### Session-scoped archive worked

- Experiment 1 archive (session 57d3a7ab) completely isolated from
  Experiment 2 (session 8f5a463a)
- New feature from this morning's commit a1075fa validated

## Revised Hypotheses

| ID | Original | Revised | Status |
|---|---|---|---|
| H1 | Role separation creates diversity | Confirmed at round 1 | Weakly supported |
| H2 | Archive feedback prevents cliche | Disproven in this setting | Rejected |
| H3 | Round iteration increases diversity | Quality yes, diversity no | Needs refinement |
| H4 (new) | Evaluator is too lenient | Suggested | To verify |
| H5 (new) | Jaccard threshold is domain-sensitive | Suggested | To verify |

## Next Experiments (not run today)

1. Sensitivity analysis: re-evaluate session 8f5a463a with
   Jaccard thresholds 0.35, 0.40, 0.45, 0.50
2. Strengthen evaluator prompts to produce more critic-broken cases
3. Rewrite archive feedback prompt to explicitly demand divergence
4. Add embedding-based diversity metric alongside Jaccard
5. Run compare mode (all 5 modes) for H1 direct comparison

## Cost Note

- Subscription via claude-cli (no API billing)
- rounds=1: ~18 min / 35 subprocess calls
- rounds=2: ~35 min / 70 subprocess calls
- Linear scaling confirmed
