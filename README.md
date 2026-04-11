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

Requires Python 3.11+. Dependencies: `pydantic`, `pyyaml`, `pytest`.

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
- `OpenAIProvider` / `AnthropicProvider` — stubs raising `NotImplementedError`

To plug in a real LLM, implement `generate_ideas` and `evaluate_axis` in a new
provider class and register it in `providers/__init__.py`.

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
