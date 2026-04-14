# idea-search

Multi-role idea search system. Instead of asking a single LLM to produce one
"best" idea, this MVP separates **generators** (each with a different role and
bias) from **evaluators** (each scoring a different axis), runs multiple
rounds, flags clichés, clusters candidates by direction, and returns several
top ideas from different clusters so a human can pick.

## Why

Single-pass LLM idea generation tends to collapse onto generic, safe,
cliché-sounding answers. This system:

- uses 6 generator roles with distinct biases (Proposer, Reframer, Contrarian,
  AnalogyFinder, ConstraintHacker, Synthesizer)
- scores each idea independently on **novelty / feasibility / value / risk**,
  each judge returning a score, short rationale, and one improvement suggestion
- detects clichés two ways: regex against known patterns, and Jaccard
  similarity against a local archive
- keeps multiple directions (clusters) instead of compressing to a single
  "winner"

## Install

```bash
cd /Users/idey/work/idea-search
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Requires Python 3.11+. Core dependencies: `pydantic`, `pyyaml`, `pytest`.

Optional: install the Anthropic provider to run against a real LLM:
```bash
pip install -e ".[anthropic]"
export ANTHROPIC_API_KEY=sk-ant-...
```

## Run (mock provider, no API key)

```bash
python -m idea_search run --input examples/sample_input.json
```

Or with overrides:

```bash
python -m idea_search run \
  --input examples/sample_input.json \
  --rounds 2 \
  --provider mock \
  --out report.json
```

`--json` emits the full report to stdout as JSON.

## Compare pipeline variants (baseline vs full system)

Runs several pipeline configurations on the same problem so you can tell
how much of the result quality comes from the role-separated architecture
versus a naive single-shot call. The report is Markdown with blank score
columns for human grading.

```bash
python -m idea_search compare \
  --input examples/sample_input.json \
  --rounds 1 \
  --out comparison.md
```

Modes (comma-separated via `--modes`, all 5 by default):

| Mode                      | What it does                                    |
|---------------------------|-------------------------------------------------|
| `baseline-single`         | One provider call, N generic ideas, no critique |
| `baseline-self-critique`  | Single model generates + critiques itself       |
| `generator-only`          | 6 generator roles, no evaluator/archive/cliché  |
| `gen-eval`                | Generators + 4-axis evaluators                  |
| `full`                    | Full Controller pipeline                        |

The report includes **machine diversity metrics** for each mode (unique
tags, average pairwise Jaccard similarity, greedy cluster count) plus
**blank score cells** for human-graded **novelty / feasibility /
actionability** per idea and **variety** per mode.

## Input format

A JSON file with:

```json
{
  "problem": "Help small independent bookstores survive...",
  "constraints": ["no discounts", "budget under 5000 USD"],
  "context": "Urban bookstores in Japan and US"
}
```

Only `problem` is required.

## Architecture

```
              ┌──────────────────────────────────────────┐
              │              Controller                  │
              │      (rounds, state, archive)            │
              └──────┬──────────────────────┬────────────┘
                     │                      │
          ┌──────────▼───────────┐ ┌────────▼──────────┐
          │  Generator Pipeline  │ │ Evaluator Pipeline│
          │  Proposer            │ │  NoveltyJudge     │
          │  Reframer            │ │  FeasibilityJudge │
          │  Contrarian          │ │  ValueJudge       │
          │  AnalogyFinder       │ │  RiskJudge        │
          │  ConstraintHacker    │ └───────────────────┘
          │  Synthesizer*        │
          └──────────┬───────────┘
                     │
          ┌──────────▼───────────┐
          │ similarity + clichés │  (Jaccard + regex patterns)
          └──────────┬───────────┘
                     │
          ┌──────────▼───────────┐
          │ clustering + report  │
          └──────────┬───────────┘
                     │
              archive/ideas.jsonl
```

### Synthesizer input rules

- **Round 1**: receives all ideas from the other generators in this round
- **Round 2+**: receives curated fragments:
  - top-N highest **novelty** from previous round
  - top-N highest **feasibility** from previous round
  - fragments from critic-broken ideas (low composite or high risk + low feasibility)

### Cliché detection

Two independent checks, either one triggers a flag:

1. Regex match against `cliche_patterns` in config (`ai-powered platform`,
   `Uber for X`, `disrupt the industry`, …)
2. Jaccard similarity against prior ideas in the archive exceeding the
   configured threshold

## Provider abstraction

`providers/base.py` defines `LLMProvider`. V1 ships:

- `MockProvider` — deterministic, no API key, used by default
- `AnthropicProvider` — real Claude API; requires `ANTHROPIC_API_KEY`
- `OpenAIProvider` — still a stub raising `NotImplementedError`

### Using the Anthropic provider

Install the optional dependency and set the key:
```bash
pip install -e ".[anthropic]"
export ANTHROPIC_API_KEY=sk-ant-...
# Optional: override the model (default: claude-sonnet-4-6)
export ANTHROPIC_MODEL=claude-haiku-4-5-20251001
```

Then add `--provider anthropic` to any subcommand:
```bash
# Flat idea search
python -m idea_search run --input examples/sample_input.json --provider anthropic

# Goal decomposition only
python -m idea_search goal-search --input examples/goal_input.json --provider anthropic

# End-to-end hierarchical search
python -m idea_search hierarchical-full \
  --input examples/goal_input.json \
  --provider anthropic \
  --rounds 1
```

Switching back to mock is just `--provider mock` (default). The provider is
chosen fresh per invocation, so you can diff mock vs anthropic runs on the
same input.

If `ANTHROPIC_API_KEY` is unset, `--provider anthropic` raises a clear
runtime error; mock-based commands keep working regardless.

### Mock vs Anthropic — what to look for

The mock provider verifies the pipeline structure but cannot produce
meaningful semantic output. Its limits:

- Keyword extraction is literal (`for one person to make money` →
  keywords `find`, `realistic`, `ways`)
- Branch / idea seeds are templated; they don't reflect domain context
- Scores are keyword-mapped, not content-aware

Switching to the Anthropic provider lets you verify:

1. **Branch decomposition quality** — do branches become domain-specific
   and genuinely distinct paths (e.g. `AI-augmented Keirin analytics` vs
   `Prompt-engineering consulting`), instead of generic templates?
2. **Branch ranking** — does the ordering shift in ways that make sense
   given the constraints (e.g. does `validation_speed` actually drop for
   capital-heavy branches)?
3. **Method-search specificity** — does each generator role produce
   ideas that build on the selected branch's assumptions, rather than
   reusing the same "membership / salon / scarcity" templates?

### Adding another real provider

Implement `LLMProvider` (see `anthropic_provider.py` as a reference) and
register it in `providers/__init__.py::get_provider`.

## Tests

```bash
pytest
```

Covers similarity, clustering, archive, mock provider, and a full E2E
controller run.

## Configuration

`config/default.yaml` controls rounds, thresholds, cliché patterns, and
clustering. Override via `--config path/to/your.yaml`.

## Not in this MVP

- Web search
- Real LLM integrations (OpenAI / Anthropic beyond stubs)
- GUI
- Distributed execution
- Embedding-based similarity

## Extension points

- Add a new generator role: drop a system prompt in `roles/prompts.py`, add
  the role to `generators` in the config, teach the mock provider a seed
  (optional).
- Add a new evaluator axis: extend the schema, evaluator pipeline, and the
  composite formula in `schema.Evaluation.composite`.
- Swap similarity for embeddings: implement a new `similarity.py` function
  matching the Jaccard signature.
- Real LLM provider: implement `LLMProvider` and register in `get_provider`.
