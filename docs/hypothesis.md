# Hypotheses

`idea-search` is an experimental rig. The point of having five comparison
modes is not to find a "best" mode but to test specific claims about
*why* role separation, evaluation, and archive feedback matter — or
whether they matter at all.

## Main hypothesis

**H1.** A pipeline that combines **role-separated generators** with
**archive feedback** produces *significantly* higher *directional
diversity* than a single LLM call asked the same question with the same
constraints.

"Directional diversity" is approximated today by `unique_tags`,
`avg_pairwise_similarity` (Jaccard, lower = more diverse), and
`cluster_count_proxy` from `compare.compute_diversity`. The metric is
known to be lexical-only (see [limitations.md](limitations.md)).

## Sub-hypotheses

* **H2 — Role separation alone helps.** Even without an evaluator and
  without archive feedback, the 6 generator roles produce more
  directionally distinct candidates than a single LLM call. Tested by
  comparing `generator-only` against the baselines.
* **H3 — Archive feedback adds on top of role separation.** Adding the
  archive (cliché regex + similarity check against past ideas)
  suppresses repeated directions across rounds beyond what role
  separation alone achieves. Tested by comparing `full` against
  `gen-eval` (which has evaluators but no archive).
* **H4 — Single-model self-critique is not a substitute for role
  separation.** A baseline that asks the same model to critique its own
  ideas adds polish but does not increase the number of directions
  represented. Tested by comparing `baseline-self-critique` against
  `baseline-single`; both should sit below `generator-only` on diversity
  metrics.

## Mode ↔ ablation table

| Mode | What it ablates / isolates | Hypothesis it speaks to |
|------|----------------------------|--------------------------|
| `baseline-single`        | Reference floor — single shot, N ideas in one call. No roles, no eval, no archive. | H1 baseline, H4 baseline |
| `baseline-self-critique` | Adds a single self-critique pass over the baseline. **Intentionally weak.** | H4 |
| `generator-only`         | Role separation **on**, evaluator **off**, archive **off**, cliché filter **off**. | H1, H2 |
| `gen-eval`               | Role separation **on**, evaluator **on**, archive **off**, cliché filter **off**. | H2 → H3 stepping stone |
| `full`                   | Role separation **on**, evaluator **on**, archive **on**, cliché filter **on**, cluster filter **on**. | H1, H3 |

Modes are defined in `src/idea_search/modes.py` and dispatched by
`CompareRunner._run_one` in `src/idea_search/compare.py`.

## What "good output" means here

Priority order, from primary to secondary:

1. **Structured candidates the downstream verifier can consume.** Each
   `Idea` (`src/idea_search/schema.py`) carries `title`, `statement`,
   `rationale`, `tags`, optional `parent_ids`, and an optional
   four-axis `Evaluation`. Schema stability matters more than prose
   quality.
2. **Directional diversity preserved.** Multiple distinct directions
   survive the pipeline rather than collapsing onto one cluster. This is
   what H1 actually claims and what the diversity metrics track.
3. **Help a human pick a winner.** Real, but secondary. Once the
   downstream verifier exists, this should not be load-bearing.

A run that produces a single very polished idea is *not* a good run.
A run that produces many distinct, structured, mediocre ideas is a
better one for this device's purpose.

## What this rig deliberately does *not* prove

* That `full` produces "better" ideas in any human-judgment sense — only
  that it covers more directions under the chosen metric.
* That the metric itself is a faithful proxy for direction. Today it is
  lexical and can be fooled in either direction (see
  [limitations.md](limitations.md), §1).
* That the underlying model's capabilities are constant across modes.
  Anthropic / OpenAI providers are non-deterministic by default; the
  mock provider is deterministic and is the recommended floor for
  ablation comparisons during development.
