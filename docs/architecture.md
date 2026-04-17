# Architecture

## Layers

```
┌─────────────────────────────────────────────────────────────┐
│ Reporting       reporter.py, compare_report.py,             │
│                 hierarchical/reporter.py                    │
├─────────────────────────────────────────────────────────────┤
│ Controller      controller.Controller,                      │
│                 hierarchical.HierarchicalController,        │
│                 compare.CompareRunner                       │
├─────────────────────────────────────────────────────────────┤
│ Pipeline        pipeline/generator_pipeline.py,             │
│                 pipeline/evaluator_pipeline.py,             │
│                 hierarchical/method_adapter.py              │
├─────────────────────────────────────────────────────────────┤
│ Roles           roles/generators.py, roles/evaluators.py,   │
│                 roles/prompts.py, hierarchical/prompts.py   │
├─────────────────────────────────────────────────────────────┤
│ Providers       providers/{mock,anthropic,                  │
│                 claude_cli,openai}_provider.py              │
└─────────────────────────────────────────────────────────────┘
                Cross-cutting:
                  schema.py, similarity.py, clustering.py,
                  archive/ (jsonl store), charter.py
```

Higher layers depend on lower layers; lower layers do not import
upward. The CLI (`cli.py`) wires a `Controller` (or sibling) for the
chosen subcommand and prints the chosen reporter's output.

## Method search — data flow

Triggered by `idea-search run` (and by `--modes full` of `compare`).

```
ProblemInput
    │
    ▼
For each round (1..N):
    Controller
       │
       ├─► generator_pipeline.run_generator_round
       │     ├─ 6 roles: Proposer, Reframer, Contrarian,
       │     │           AnalogyFinder, ConstraintHacker,
       │     │           Synthesizer
       │     └─ Synthesizer reads:
       │          round 1     → other generators' raw ideas
       │          round 2..N  → high-novelty top-K
       │                       + high-feasibility top-K
       │                       + critic-broken fragments
       │
       ├─► cliche detection (regex from config + similarity to archive)
       │
       ├─► evaluator_pipeline.run_evaluator_round
       │     └─ 4 judges: NoveltyJudge, FeasibilityJudge,
       │                  ValueJudge, RiskJudge
       │
       └─► archive.append(idea, eval, session)
              (refresh archive snapshot for next round)
    │
    ▼
clustering.cluster_ideas (Jaccard)
    │
    ▼
reporter.build_report → FinalReport
```

## Hierarchical search — data flow

Triggered by `idea-search hierarchical-full` (and `goal-search` for the
decomposition stage in isolation).

```
Goal
 │
 ▼
hierarchical.goal_decomposer.decompose_goal(provider, goal, n=N)
 │   → N strategy branches
 ▼
hierarchical.branch_evaluator.evaluate_branches
 │   → 6 axes per branch:
 │     upside, cost, risk, validation_speed,
 │     personal_fit, data_availability
 ▼
hierarchical.branch_selector.select_top_k(weights=...)
 │   → top-K branches
 ▼
For each selected branch:
    hierarchical.method_adapter.build_method_search_input
        → ProblemInput (branch becomes problem statement)
    Controller.run(problem)   ← reuses the method-search pipeline
 │
 ▼
hierarchical.reporter.render_hierarchical
```

`HierarchicalController` is a thin orchestrator: decomposition and
evaluation happen at this layer, but per-branch *method search* is
delegated to the regular `Controller`. The hierarchy is therefore
2-stage (Goal → Branch → Method) and not recursive — see
[limitations.md](limitations.md), §4.

## Synthesizer — two-stage input

The Synthesizer role is special: it does not generate from the prompt
alone but composes from other roles' output.

| Round | Synthesizer reads |
|-------|-------------------|
| 1     | Raw ideas produced by the other 5 generators in this round. |
| 2..N  | Top-K ideas by novelty score, plus top-K by feasibility score, plus "critic-broken" fragments (low composite score or high risk) from the previous round's evaluations. |

Configured under `synthesizer:` in `config/default.yaml`
(`high_novelty_top_k`, `high_feasibility_top_k`,
`include_critic_fragments`). Implemented in
`pipeline/generator_pipeline.py`.

## Archive — what it is for

`ArchiveStore` (`src/idea_search/archive/`) is a JSONL append-only log
of every `(idea, evaluation, session_id)` triple. It plays three roles:

1. **Search history.** Persistent record across runs and sessions.
2. **Cliché detection input.** New ideas are compared against archive
   texts via Jaccard; high-similarity hits are flagged on the
   `cliche_flag` / `cliche_reason` fields of the new `Idea`.
3. **Soft constraint feedback.** Archive texts are passed into the next
   generator round so the generators can see what has already been
   said and avoid repeating it.

Only `full` mode uses the archive; the comparison modes
(`generator-only`, `gen-eval`) deliberately disable it — see
`compare._mode_config`, which redirects each mode to a temporary
isolated archive path so cross-mode pollution is impossible.

## Cross-cutting: charter

`charter.py` loads `charter.md` (project root) into a `Charter` model
and merges its machine-readable section (`budget`, `stop_conditions`,
`risk`, `escalation`, `review_cadence_days`) into the runtime config
**with charter taking precedence**. Both `Controller` and
`CompareRunner` perform this merge in `__init__`. Empty charter = no-op.
Prompt-level injection of charter prose is not implemented yet.
