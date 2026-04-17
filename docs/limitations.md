# Known Limitations

This is a research-phase device. The list below is what the
maintainers know is wrong, missing, or weak today. Items marked as
*Planned* are intended directions, not commitments.

## 1. Diversity metric is lexical only

`compare.compute_diversity` measures `avg_pairwise_similarity` with
Jaccard over `title + tags`. This captures *vocabulary* overlap, not
*direction*.

Failure modes:

* Two ideas in the same direction phrased with different vocabulary
  look diverse.
* Two ideas in different directions that happen to reuse the same tag
  vocabulary look similar.

H1 is therefore tested against a proxy that may itself be wrong.

*Planned:* run an embedding-based similarity in parallel and report
both numbers side by side, so we can see when the two metrics
disagree.

## 2. Evaluator and generator share a model

In real-provider runs (`anthropic`, `claude-cli`, `openai`) the
generators and the 4-axis evaluators are typically the **same
underlying model**. This is a structural self-evaluation bias:
high evaluator scores may reflect prompt agreement rather than
candidate quality.

*Planned:* an ablation that uses **different providers** for generator
and evaluator (e.g. anthropic generators + openai evaluators) to
quantify the bias.

## 3. `baseline-self-critique` is intentionally weak

The current self-critique baseline does a single critique pass over a
single LLM's output. It is meant as a *lower bound* for H4 — "is role
separation just a fancy way of doing self-critique?" — and not as a
serious alternative pipeline.

*Planned:* a `baseline-strong` mode that combines multi-step CoT,
explicit diversity instructions, and a self-critique loop, so H1 is
tested against a baseline that does not concede the comparison.

## 4. Hierarchical search is 2-stage, not recursive

`HierarchicalController` decomposes a goal into branches and then runs
method search on each selected branch. Sub-branches of a branch are
**not** expanded. The "hierarchy" is fixed at depth 2.

A genuinely recursive structure (Goal → Branch → Sub-branch → ...
→ Method) is not implemented and is not on the near-term roadmap. The
2-stage version is sufficient for the current research questions.

## 5. Archive matching is also lexical

Cliché detection compares new idea text to past archive entries via
Jaccard at the token level. Same failure mode as §1: ideas that say
the same thing in different words slip through; ideas that share
boilerplate vocabulary get false-positive cliché flags.

*Planned:* embed new ideas and search the archive in embedding space
in addition to the lexical pass.

## 6. Evaluator pipeline is sequential

`pipeline/evaluator_pipeline.py` runs the 4 judges sequentially per
idea, and ideas sequentially per round. There is no concurrency. With
the `claude-cli` provider — where each call is a process spawn — this
is the dominant source of wall-clock cost on a real run.

*Planned:* batch evaluator calls per round behind an `asyncio.gather`
or thread pool, opt-in via config.

## 7. `claude-cli` `meta` is dropped on the floor

`ClaudeCLIProvider._complete_json` returns a `(parsed, meta)` tuple
where `meta` records `parsed_via_fallback`, `retry_used`, and a raw
excerpt of the response on failure. This information is **not**
propagated upward — by the time a `ModeResult` reaches the reporter,
there is no way to tell which calls were rescued by the regex
fallback or which calls needed a retry.

This makes after-the-fact reliability triage much harder than it
needs to be.

*Planned:* thread `meta` through the pipeline and surface a
"reliability summary" in the comparison report.

---

If you discover a limitation that is not in this list, file it before
fixing it — the value of the ablation rig depends on knowing which
parts of the result are trustworthy and which are not.
