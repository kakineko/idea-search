# Providers

Four providers are wired into `providers.get_provider`. The CLI exposes
three through the `--provider` flag (`mock`, `anthropic`, `claude-cli`);
`openai` is registered but treated as secondary and is not advertised on
the CLI surface.

## Comparison

| Provider     | Auth                          | Cost                 | Parallelism                       | Use case                                    |
|--------------|-------------------------------|----------------------|-----------------------------------|---------------------------------------------|
| `mock`       | none                          | 0                    | high (in-process)                 | Development, CI, deterministic ablation     |
| `anthropic`  | `ANTHROPIC_API_KEY`           | per-token billing    | high (HTTP, async-friendly)       | Production experiments                      |
| `claude-cli` | Claude Code OAuth (keychain)  | inside subscription  | low (one subprocess per call)     | Use existing Claude Code subscription       |

`mock` is the floor for ablation work because it is deterministic; tests
and the comparison runner default to it.

## Switching provider

Either at the CLI:

```bash
idea-search run --input examples/sample_input.json --provider anthropic
idea-search compare --input examples/sample_input.json --provider claude-cli
```

…or in `config/default.yaml` via the top-level `provider:` field. The
CLI flag wins when both are present (see `_cmd_run` / `_cmd_compare` in
`cli.py`).

## `claude-cli` notes

* Requires the `claude` binary on `PATH`. The provider raises
  `ClaudeCLIProviderError` at construction time if it is missing.
* Each call is a `subprocess` invocation (`claude -p ...`). Latency is
  dominated by process startup, so this provider is the slowest of the
  three on multi-round runs.
* JSON parsing uses a **3-stage fallback**:
  1. Direct `json.loads` of the CLI's `result` field (after stripping
     ```` ```json ... ``` ```` fences).
  2. Regex extraction of the first balanced JSON object/array via
     `_extract_first_json` (imported from the Anthropic provider).
  3. One retry with a stricter "JSON only, no prose" instruction; on
     repeated failure, an empty object/list is returned and the failure
     is recorded in a `meta` dict.
* Field shape is normalized by `_coerce_idea_dict`,
  `_coerce_axis_eval`, `_coerce_branch_dict`, and `_coerce_branch_eval`
  (re-exported from the Anthropic provider). Missing fields get safe
  defaults rather than raising.
* `--system-prompt` **replaces** the default Claude Code system prompt,
  so role / judge prompts are delivered cleanly without inheriting the
  default Claude Code persona.

## JSON reliability — shared behavior

All three real providers (anthropic, claude-cli, openai) share the
post-processing primitives defined in `providers/anthropic_provider.py`:

* `_coerce_idea_dict(raw, role, round_index)` — fills in `id`, `round`,
  `role`, and ensures `tags` / `parent_ids` are lists; missing
  `title` / `statement` / `rationale` become empty strings rather than
  raising.
* `_coerce_axis_eval(raw)` — coerces `score` to `float`, defaults to
  `3.0` on failure, and ensures `rationale` and `suggestion` are
  strings.
* `_coerce_branch_dict` / `_coerce_branch_eval` — same idea for the
  hierarchical layer's `Branch` and `BranchEvaluation` types.

Net effect: a partial or slightly malformed model response is degraded
into a usable record rather than crashing the round. Loud failures only
happen when the response is unrecoverable JSON or transport fails.

## What the providers do *not* do today

* No request batching. Each idea / axis evaluation is its own call.
* No automatic model fallback (e.g. retry on a different model on
  rate-limit). Failures bubble up to the controller.
* No cost accounting. The `meta` dict that `claude-cli`'s
  `_complete_json` returns includes reliability flags (whether the
  fallback parser was used, whether a retry was issued, raw excerpt on
  failure) but is **not** propagated up to the controller layer today —
  see [limitations.md](limitations.md), §7.

When choosing a provider for a real ablation run: prefer `anthropic` for
throughput and timing comparability, prefer `claude-cli` only when the
subscription cost model matters more than wall-clock time.
