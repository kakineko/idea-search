# idea-search

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)

> **A multi-stage search device that turns an ambiguous question into a
> diverse set of directional hypothesis candidates.**

## Purpose

* Front stage of a larger pipeline: produce **structured candidates** that
  feed an automated downstream verification pipeline (not yet built).
* Helping a human pick a winner is a **secondary** goal, only relevant
  while the downstream verifier is absent.
* Built as an **experimental rig**: different generation strategies are
  available as separate modes so their individual contribution can be
  isolated by ablation.

## Two Modes of Operation

**Method Search** — given a concrete *problem*, run 6 generator roles +
4-axis evaluators + archive feedback over multiple rounds and return
clustered candidates.

```bash
idea-search run --input examples/sample_input.json
```

**Hierarchical Search** — given an abstract *goal*, decompose it into
3–5 strategy branches, evaluate them on 6 axes, then run method search
on the selected top branch(es).

```bash
idea-search hierarchical-full --input examples/goal_input.json --branches 5 --top-k 1
```

There are also two intermediate entrypoints: `idea-search compare` for
ablation across modes, and `idea-search goal-search` for the
decomposition stage only.

## Main Hypotheses

* **H1 (main)** — Role-separated generators + archive feedback yield
  significantly higher *directional diversity* than a single LLM call on
  the same prompt.
* The five comparison modes (`baseline-single`, `baseline-self-critique`,
  `generator-only`, `gen-eval`, `full`) form an ablation ladder that
  isolates the contribution of role separation, evaluation, and archive.

See [docs/hypothesis.md](docs/hypothesis.md) for the full hypothesis
table and which mode tests which sub-hypothesis.

## Quick Start

```bash
git clone https://github.com/kakineko/idea-search.git
cd idea-search
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Requires Python 3.11+. Core deps: `pydantic>=2.5`, `pyyaml>=6.0`.

For contributors running analysis scripts in `scripts/` (embedding
similarity, etc.), install the optional `[analysis]` extras inside the
same venv to avoid conflicts with system-wide Python packages:

```bash
pip install -e ".[analysis]"
```

Mock provider (no API key, deterministic):

```bash
# Method search
python -m idea_search run --input examples/sample_input.json

# Hierarchical search
python -m idea_search hierarchical-full \
  --input examples/goal_input.json --branches 5 --top-k 1

# Ablation across all 5 modes
python -m idea_search compare \
  --input examples/sample_input.json \
  --modes baseline-single,baseline-self-critique,generator-only,gen-eval,full
```

Switch provider with `--provider {mock,anthropic,claude-cli}`. See
[docs/providers.md](docs/providers.md) for tradeoffs and credentials.

## Known Limitations

* Diversity metric is **lexical only** (Jaccard on title + tags); semantic
  diversity is not captured yet.
* Generator and evaluator typically share the **same underlying model**,
  so evaluator scores carry a self-congratulation risk.
* `baseline-self-critique` is **deliberately weak** and exists as a
  comparison floor; a stronger baseline is planned.
* Hierarchical search is **2-stage** (Goal → Branch → Method). Recursive
  sub-branch expansion is not implemented.

Full list with planned mitigations: [docs/limitations.md](docs/limitations.md).

## Project Status

Experimental / research-phase. The CLI surface, JSON schemas, and config
keys are **unstable** and may change without notice. Pin to a specific
commit if depending on it.

## Documentation

* [docs/hypothesis.md](docs/hypothesis.md) — H1–H4, mode ↔ ablation table,
  definition of "good output".
* [docs/architecture.md](docs/architecture.md) — Layer diagram, data flow
  for both modes, synthesizer and archive roles.
* [docs/providers.md](docs/providers.md) — mock / anthropic / claude-cli
  comparison and JSON-reliability strategy.
* [docs/limitations.md](docs/limitations.md) — Current shortcomings and
  planned work.
* `charter.md` — President-level constraints (budget, stop conditions,
  tone). Loaded by every controller.
* `README_ja.md` — Japanese version (may lag behind).
