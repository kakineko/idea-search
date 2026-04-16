"""Claude CLI provider — shells out to `claude -p` for each call.

Uses the user's Claude Code subscription (OAuth/keychain) instead of a
raw Anthropic API key. This means no direct API billing, but every call
is a subprocess invocation, so latency is higher and parallelism is
limited.

Design differences vs AnthropicProvider:
- No assistant prefill support (CLI has no such flag). JSON reliability
  comes from prompt-level instruction + markdown fence stripping + regex
  fallback.
- `--system-prompt` REPLACES the default Claude Code system prompt, so
  role prompts are delivered cleanly.
- Output is wrapped as `{"type":"result","result":"<text>", ...}`; the
  `result` field may be wrapped in ```json ... ``` fences which we strip.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from typing import Any, Dict, List, Literal, Tuple

from idea_search.hierarchical.prompts import (
    BRANCH_EVALUATOR_PROMPTS,
    GOAL_DECOMPOSER_PROMPT,
)
from idea_search.providers.anthropic_provider import (
    _coerce_axis_eval,
    _coerce_branch_dict,
    _coerce_branch_eval,
    _coerce_idea_dict,
    _extract_first_json,
)
from idea_search.providers.base import LLMProvider
from idea_search.roles.prompts import EVALUATOR_PROMPTS, GENERATOR_PROMPTS


log = logging.getLogger("idea_search.claude_cli")

_DEFAULT_MODEL = "sonnet"
_DEFAULT_TIMEOUT_SEC = 300
_RAW_EXCERPT_LEN = 400


class ClaudeCLIProviderError(RuntimeError):
    """Raised when the provider cannot operate (missing CLI, etc.)."""


_FENCE_RE = re.compile(
    r"^```(?:json|JSON)?\s*\n?(.*?)\n?```\s*$",
    re.DOTALL,
)


def _strip_code_fence(text: str) -> str:
    m = _FENCE_RE.match(text.strip())
    if m:
        return m.group(1).strip()
    return text.strip()


class ClaudeCLIProvider(LLMProvider):
    name = "claude-cli"

    def __init__(
        self,
        model: str | None = None,
        claude_binary: str | None = None,
        timeout_sec: int = _DEFAULT_TIMEOUT_SEC,
    ) -> None:
        # Explicit PATH check with an actionable error message.
        binary = claude_binary or shutil.which("claude")
        if not binary:
            raise ClaudeCLIProviderError(
                "ClaudeCLIProvider could not find the 'claude' command on PATH.\n"
                "  Install Claude Code first, then ensure `claude` is on your PATH.\n"
                "  See: https://docs.anthropic.com/claude/docs/claude-code\n"
                "  Alternative: use --provider mock (no setup) or --provider "
                "anthropic (with ANTHROPIC_API_KEY)."
            )
        self._binary = binary
        self._model = model or _DEFAULT_MODEL
        self._timeout_sec = timeout_sec

    # ------------------------------------------------------------------
    # Low-level subprocess + JSON completion helper
    # ------------------------------------------------------------------

    def _raw_complete(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Invoke `claude -p` once and return the inner `result` text
        (markdown code fences stripped if present).
        Raises CalledProcessError / TimeoutExpired on subprocess failure.
        """
        argv = [
            self._binary,
            "-p",
            "--model", self._model,
            "--system-prompt", system_prompt,
            "--output-format", "json",
            user_prompt,
        ]
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=self._timeout_sec,
        )
        if proc.returncode != 0:
            raise ClaudeCLIProviderError(
                f"claude CLI exited {proc.returncode}: "
                f"stderr={proc.stderr.strip()[:300]}"
            )
        try:
            envelope = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise ClaudeCLIProviderError(
                f"Failed to parse claude envelope JSON: {e}; "
                f"stdout head: {proc.stdout[:200]}"
            ) from e
        if envelope.get("is_error"):
            raise ClaudeCLIProviderError(
                f"claude CLI returned error envelope: "
                f"{envelope.get('result', '')[:200]}"
            )
        result_text = envelope.get("result", "")
        return _strip_code_fence(result_text)

    def _complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        expect: Literal["object", "array"],
    ) -> Tuple[Any, Dict[str, Any]]:
        """Return (parsed, meta) where meta captures reliability flags.

        meta = {
            "retry_used": bool,
            "parsed_via_fallback": bool,
            "raw_result_excerpt": str | None,  # only set when flags are True
        }
        """
        enforced_system = (
            system_prompt
            + "\n\nIMPORTANT: Respond with a single valid JSON "
            + ("object" if expect == "object" else "array")
            + ", and NOTHING else. No prose, no markdown fences, no commentary."
        )
        meta: Dict[str, Any] = {
            "retry_used": False,
            "parsed_via_fallback": False,
            "raw_result_excerpt": None,
        }

        raw = self._raw_complete(enforced_system, user_prompt)
        try:
            return json.loads(raw), meta
        except json.JSONDecodeError:
            extracted = _extract_first_json(raw, expect)
            if extracted is not None:
                meta["parsed_via_fallback"] = True
                meta["raw_result_excerpt"] = raw[:_RAW_EXCERPT_LEN]
                log.warning(
                    "claude-cli: regex fallback rescued parse (expect=%s). "
                    "raw excerpt: %s",
                    expect, meta["raw_result_excerpt"],
                )
                return extracted, meta

        # Retry once with stronger instruction
        meta["retry_used"] = True
        meta["raw_result_excerpt"] = raw[:_RAW_EXCERPT_LEN]
        log.warning(
            "claude-cli: initial parse failed; retrying once (expect=%s). "
            "raw excerpt: %s",
            expect, meta["raw_result_excerpt"],
        )
        stronger_system = (
            enforced_system
            + "\nYour previous response was not valid JSON. "
              "Return ONLY the JSON, no other characters."
        )
        raw2 = self._raw_complete(stronger_system, user_prompt)
        try:
            return json.loads(raw2), meta
        except json.JSONDecodeError:
            extracted = _extract_first_json(raw2, expect)
            if extracted is not None:
                meta["parsed_via_fallback"] = True
                meta["raw_result_excerpt"] = raw2[:_RAW_EXCERPT_LEN]
                log.warning(
                    "claude-cli: retry also needed regex fallback (expect=%s).",
                    expect,
                )
                return extracted, meta

        meta["parsed_via_fallback"] = True
        meta["raw_result_excerpt"] = raw2[:_RAW_EXCERPT_LEN]
        log.error(
            "claude-cli: parsing failed after retry (expect=%s). "
            "Returning empty default. raw excerpt: %s",
            expect, meta["raw_result_excerpt"],
        )
        return ({} if expect == "object" else []), meta

    # ------------------------------------------------------------------
    # LLMProvider interface: core role methods
    # ------------------------------------------------------------------

    def generate_ideas(
        self,
        role: str,
        system_prompt: str,
        problem: str,
        constraints: List[str],
        context: str,
        round_index: int,
        prior_fragments: List[Dict[str, Any]] | None = None,
        n: int = 2,
    ) -> List[Dict[str, Any]]:
        sys_prompt = system_prompt or GENERATOR_PROMPTS.get(role, "")
        user = _build_generator_user_prompt(
            role=role, problem=problem, constraints=constraints,
            context=context, round_index=round_index,
            prior_fragments=prior_fragments or [], n=n,
        )
        parsed, _meta = self._complete_json(sys_prompt, user, expect="array")
        if not isinstance(parsed, list):
            return []
        return [_coerce_idea_dict(x, role=role) for x in parsed if isinstance(x, dict)]

    def evaluate_axis(
        self,
        judge: str,
        system_prompt: str,
        problem: str,
        idea_title: str,
        idea_statement: str,
    ) -> Dict[str, Any]:
        sys_prompt = system_prompt or EVALUATOR_PROMPTS.get(judge, "")
        user = (
            f"Problem:\n{problem}\n\n"
            f"Idea title: {idea_title}\n"
            f"Idea statement: {idea_statement}\n\n"
            f"Return a JSON object with keys: score (0-5 number), "
            f"rationale (short string), suggestion (one-sentence string)."
        )
        parsed, _meta = self._complete_json(sys_prompt, user, expect="object")
        return _coerce_axis_eval(parsed)

    # ------------------------------------------------------------------
    # Baseline methods
    # ------------------------------------------------------------------

    def generate_baseline(
        self,
        problem: str,
        constraints: List[str],
        context: str,
        n: int = 3,
    ) -> List[Dict[str, Any]]:
        sys_prompt = (
            "You are a generic idea assistant. Produce a list of candidate "
            "ideas that address the problem. No role separation. Return a "
            "JSON array where each element has fields: title, statement, "
            "rationale, tags."
        )
        user = (
            f"Problem: {problem}\n"
            f"Constraints: {', '.join(constraints) if constraints else 'none'}\n"
            f"Context: {context or 'none'}\n\n"
            f"Return exactly {n} ideas as a JSON array."
        )
        parsed, _meta = self._complete_json(sys_prompt, user, expect="array")
        if not isinstance(parsed, list):
            return []
        return [_coerce_idea_dict(x, role="Baseline") for x in parsed if isinstance(x, dict)]

    def self_critique(
        self,
        problem: str,
        ideas: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not ideas:
            return ideas
        sys_prompt = (
            "You are the same model reviewing your own ideas. Critique each "
            "idea briefly, then return a revised version of the full list. "
            "Return a JSON array in the same format: title, statement, "
            "rationale, tags. Keep count equal."
        )
        user = (
            f"Problem: {problem}\n\n"
            f"Your previous ideas:\n{json.dumps(ideas, ensure_ascii=False, indent=2)}\n\n"
            f"Return the revised list as a JSON array of {len(ideas)} items."
        )
        parsed, _meta = self._complete_json(sys_prompt, user, expect="array")
        if not isinstance(parsed, list) or not parsed:
            return ideas
        return [_coerce_idea_dict(x, role="SelfCritique") for x in parsed if isinstance(x, dict)]

    # ------------------------------------------------------------------
    # Hierarchical methods
    # ------------------------------------------------------------------

    def decompose_goal(
        self,
        goal_statement: str,
        constraints: List[str],
        domain_context: List[str],
        n: int = 5,
    ) -> List[Dict[str, Any]]:
        user = (
            f"Goal: {goal_statement}\n"
            f"Constraints:\n"
            + "\n".join(f"- {c}" for c in constraints)
            + f"\n\nDomain context:\n"
            + "\n".join(f"- {c}" for c in domain_context)
            + f"\n\nReturn a JSON array of exactly {n} strategy branches. "
              "Each branch must be a JSON object with: branch_name, "
              "branch_description, assumptions (array of strings), "
              "required_capital, required_skill, risk_level, "
              "validation_speed, personal_fit, data_availability. "
              "String-attribute fields should use values like "
              "'low'/'medium'/'high' or 'days'/'weeks'/'months' as appropriate."
        )
        parsed, _meta = self._complete_json(
            GOAL_DECOMPOSER_PROMPT, user, expect="array",
        )
        if not isinstance(parsed, list):
            return []
        return [_coerce_branch_dict(x) for x in parsed if isinstance(x, dict)]

    def evaluate_branch(
        self,
        branch_name: str,
        branch_description: str,
        goal_statement: str,
        domain_context: List[str],
    ) -> Dict[str, Any]:
        sys_prompt = (
            "You are a multi-axis branch evaluator. Score the given branch "
            "on six axes and return a single JSON object.\n\n"
            "Axis rubrics:\n"
            + "\n".join(
                f"- {axis}: {prompt}"
                for axis, prompt in BRANCH_EVALUATOR_PROMPTS.items()
            )
            + "\n\nReturn a JSON object with keys: upside, cost, risk, "
              "validation_speed, personal_fit, data_availability. Each key "
              "maps to an object with {score (0-5), rationale, suggestion}."
        )
        user = (
            f"Goal: {goal_statement}\n"
            f"Domain context:\n"
            + "\n".join(f"- {c}" for c in domain_context)
            + f"\n\nBranch name: {branch_name}\n"
              f"Branch description: {branch_description}"
        )
        parsed, _meta = self._complete_json(sys_prompt, user, expect="object")
        return _coerce_branch_eval(parsed)


# ----------------------------------------------------------------------
# Module-level helpers
# ----------------------------------------------------------------------

def _build_generator_user_prompt(
    role: str,
    problem: str,
    constraints: List[str],
    context: str,
    round_index: int,
    prior_fragments: List[Dict[str, Any]],
    n: int,
) -> str:
    parts = [
        f"Role: {role}",
        f"Round: {round_index}",
        f"Problem:\n{problem}",
    ]
    if constraints:
        parts.append("Constraints:\n" + "\n".join(f"- {c}" for c in constraints))
    if context:
        parts.append(f"Context: {context}")
    if prior_fragments:
        parts.append("Prior fragments to build on:")
        for f in prior_fragments[:6]:
            parts.append(f"- [{f.get('reason', '')}] {f.get('title', '?')}")
    parts.append(
        f"\nReturn a JSON array of exactly {n} ideas. Each element must have: "
        "title (string), statement (2-4 sentences), rationale (1-2 sentences), "
        "tags (array of short strings)."
    )
    return "\n\n".join(parts)
