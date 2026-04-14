"""Anthropic provider.

Wraps the Anthropic Messages API so the idea-search pipelines can run
against a real LLM. The provider is loaded lazily: importing this module
does NOT require the `anthropic` SDK or an API key. Those are only
required when the provider is actually instantiated.

Structured output strategy:
    - The system prompt is taken verbatim from existing role prompts.
    - The user prompt contains structured context (problem, idea, etc.).
    - We use assistant prefill ("{" for object, "[" for array) to force
      the model to start emitting JSON immediately.
    - On parse failure we retry once, then fall back to a safe default
      (empty list / mid-scale axis score) and surface warnings.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Literal, Tuple

from idea_search.hierarchical.prompts import (
    BRANCH_EVALUATOR_PROMPTS,
    GOAL_DECOMPOSER_PROMPT,
)
from idea_search.providers.base import LLMProvider
from idea_search.roles.prompts import EVALUATOR_PROMPTS, GENERATOR_PROMPTS


log = logging.getLogger("idea_search.anthropic")

_DEFAULT_MODEL = "claude-sonnet-4-6"
_DEFAULT_MAX_TOKENS = 2048
_ENV_API_KEY = "ANTHROPIC_API_KEY"
_ENV_MODEL = "ANTHROPIC_MODEL"


class AnthropicProviderError(RuntimeError):
    """Raised when the provider cannot operate (missing SDK, missing key)."""


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get(_ENV_API_KEY)
        if not self._api_key:
            raise AnthropicProviderError(
                f"AnthropicProvider requires the {_ENV_API_KEY} environment "
                f"variable.\n"
                f"  Set it with: export {_ENV_API_KEY}=sk-ant-...\n"
                f"  Or pass api_key= when constructing the provider.\n"
                f"  The mock provider remains available via --provider mock."
            )

        try:
            import anthropic  # noqa: F401  (lazy import; re-imported in _client)
        except ImportError as e:
            raise AnthropicProviderError(
                "The 'anthropic' package is not installed.\n"
                "  Install the optional dependency: "
                "pip install -e '.[anthropic]'\n"
                "  Or: pip install anthropic"
            ) from e

        self._model = model or os.environ.get(_ENV_MODEL) or _DEFAULT_MODEL
        self._client = None  # built lazily on first call

    # ------------------------------------------------------------------
    # Low-level JSON completion helper
    # ------------------------------------------------------------------

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def _raw_complete(
        self,
        system_prompt: str,
        user_prompt: str,
        prefill: str,
        max_tokens: int,
    ) -> str:
        client = self._get_client()
        response = client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": prefill},
            ],
        )
        text_parts = [
            block.text for block in response.content
            if getattr(block, "type", None) == "text"
        ]
        return prefill + "".join(text_parts)

    def _complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        expect: Literal["object", "array"],
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> Tuple[Any, Dict[str, bool]]:
        """Return (parsed_json, flags) where flags indicate retry / fallback use.

        flags = {
            "retry_used": bool,        # a second API call was needed
            "parsed_via_fallback": bool,  # regex-extraction salvaged the output
        }
        """
        prefill = "{" if expect == "object" else "["
        enforced_system = (
            system_prompt
            + "\n\nIMPORTANT: Respond with a single valid JSON "
            + ("object" if expect == "object" else "array")
            + ", and NOTHING else. No prose, no markdown fences, no commentary."
        )

        flags = {"retry_used": False, "parsed_via_fallback": False}

        raw = self._raw_complete(enforced_system, user_prompt, prefill, max_tokens)
        try:
            return json.loads(raw), flags
        except json.JSONDecodeError:
            extracted = _extract_first_json(raw, expect)
            if extracted is not None:
                flags["parsed_via_fallback"] = True
                log.warning(
                    "Anthropic JSON parse required regex fallback (expect=%s).",
                    expect,
                )
                return extracted, flags

        # Retry once with stronger instruction + more tokens
        flags["retry_used"] = True
        log.warning("Anthropic JSON parse failed; retrying once (expect=%s).", expect)
        stronger_system = (
            enforced_system
            + "\nYour previous response was not valid JSON. "
              "Return ONLY the JSON, no other characters."
        )
        raw2 = self._raw_complete(
            stronger_system, user_prompt, prefill, max_tokens + 512,
        )
        try:
            return json.loads(raw2), flags
        except json.JSONDecodeError:
            extracted = _extract_first_json(raw2, expect)
            if extracted is not None:
                flags["parsed_via_fallback"] = True
                log.warning(
                    "Anthropic JSON retry also needed regex fallback (expect=%s).",
                    expect,
                )
                return extracted, flags

        flags["parsed_via_fallback"] = True
        log.error(
            "Anthropic JSON parsing failed after retry; returning empty %s.",
            expect,
        )
        return ({} if expect == "object" else []), flags

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
            role=role,
            problem=problem,
            constraints=constraints,
            context=context,
            round_index=round_index,
            prior_fragments=prior_fragments or [],
            n=n,
        )
        parsed, _flags = self._complete_json(sys_prompt, user, expect="array")
        if not isinstance(parsed, list):
            return []
        return [_coerce_idea_dict(item, role=role) for item in parsed if isinstance(item, dict)]

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
        parsed, _flags = self._complete_json(sys_prompt, user, expect="object")
        return _coerce_axis_eval(parsed)

    # ------------------------------------------------------------------
    # LLMProvider interface: baseline methods
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
            "ideas that address the problem. No role separation, no critique, "
            "no special framing. Return a JSON array where each element has "
            "fields: title, statement, rationale, tags."
        )
        user = (
            f"Problem: {problem}\n"
            f"Constraints: {', '.join(constraints) if constraints else 'none'}\n"
            f"Context: {context or 'none'}\n\n"
            f"Return exactly {n} ideas as a JSON array."
        )
        parsed, _flags = self._complete_json(sys_prompt, user, expect="array")
        if not isinstance(parsed, list):
            return []
        return [_coerce_idea_dict(item, role="Baseline") for item in parsed if isinstance(item, dict)]

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
        parsed, _flags = self._complete_json(sys_prompt, user, expect="array")
        if not isinstance(parsed, list) or not parsed:
            return ideas
        return [_coerce_idea_dict(item, role="SelfCritique") for item in parsed if isinstance(item, dict)]

    # ------------------------------------------------------------------
    # LLMProvider interface: hierarchical methods
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
              "The string-attribute fields should be one of: "
              "'low'/'medium'/'high' or 'days'/'weeks'/'months' etc."
        )
        parsed, _flags = self._complete_json(
            GOAL_DECOMPOSER_PROMPT, user, expect="array",
        )
        if not isinstance(parsed, list):
            return []
        return [_coerce_branch_dict(item) for item in parsed if isinstance(item, dict)]

    def evaluate_branch(
        self,
        branch_name: str,
        branch_description: str,
        goal_statement: str,
        domain_context: List[str],
    ) -> Dict[str, Any]:
        # Combine all 6 branch axis prompts into one system message and
        # ask the model for all six in one call (one API round trip).
        sys_prompt = (
            "You are a multi-axis branch evaluator. Score the given branch "
            "on six axes and return a single JSON object.\n\n"
            "Axis rubrics:\n"
            + "\n".join(
                f"- {axis}: {prompt}"
                for axis, prompt in BRANCH_EVALUATOR_PROMPTS.items()
            )
            + "\n\nReturn JSON object with keys: upside, cost, risk, "
              "validation_speed, personal_fit, data_availability. Each key "
              "maps to {score (0-5), rationale, suggestion}."
        )
        user = (
            f"Goal: {goal_statement}\n"
            f"Domain context:\n"
            + "\n".join(f"- {c}" for c in domain_context)
            + f"\n\nBranch name: {branch_name}\n"
              f"Branch description: {branch_description}"
        )
        parsed, _flags = self._complete_json(sys_prompt, user, expect="object")
        return _coerce_branch_eval(parsed)


# ----------------------------------------------------------------------
# Module-level helpers (also used by unit tests)
# ----------------------------------------------------------------------

def _extract_first_json(text: str, expect: Literal["object", "array"]) -> Any | None:
    """Extract the first balanced JSON object or array from text."""
    opener, closer = ("{", "}") if expect == "object" else ("[", "]")
    start = text.find(opener)
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                snippet = text[start:i + 1]
                try:
                    return json.loads(snippet)
                except json.JSONDecodeError:
                    return None
    return None


def _coerce_idea_dict(raw: Dict[str, Any], role: str) -> Dict[str, Any]:
    return {
        "title": str(raw.get("title", "(untitled)")),
        "statement": str(raw.get("statement", "")),
        "rationale": str(raw.get("rationale", "")),
        "tags": _as_string_list(raw.get("tags", [role.lower()])),
    }


def _coerce_axis_eval(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {"score": 3.0, "rationale": "fallback", "suggestion": "n/a"}
    try:
        score = float(raw.get("score", 3.0))
    except (TypeError, ValueError):
        score = 3.0
    score = max(0.0, min(5.0, score))
    return {
        "score": score,
        "rationale": str(raw.get("rationale", "")),
        "suggestion": str(raw.get("suggestion", "")),
    }


def _coerce_branch_dict(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "branch_name": str(raw.get("branch_name", "(unnamed)")),
        "branch_description": str(raw.get("branch_description", "")),
        "assumptions": _as_string_list(raw.get("assumptions", [])),
        "required_capital": str(raw.get("required_capital", "unknown")),
        "required_skill": str(raw.get("required_skill", "unknown")),
        "risk_level": str(raw.get("risk_level", "unknown")),
        "validation_speed": str(raw.get("validation_speed", "unknown")),
        "personal_fit": str(raw.get("personal_fit", "unknown")),
        "data_availability": str(raw.get("data_availability", "unknown")),
    }


def _coerce_branch_eval(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    axes = ["upside", "cost", "risk", "validation_speed", "personal_fit", "data_availability"]
    return {axis: _coerce_axis_eval(raw.get(axis, {})) for axis in axes}


def _as_string_list(x: Any) -> List[str]:
    if isinstance(x, list):
        return [str(item) for item in x]
    if isinstance(x, str):
        return [x]
    return []


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
            title = f.get("title", "?")
            reason = f.get("reason", "")
            parts.append(f"- [{reason}] {title}")
    parts.append(
        f"\nReturn a JSON array of exactly {n} ideas. Each element must have: "
        "title (string), statement (2-4 sentences), rationale (1-2 sentences), "
        "tags (array of short strings)."
    )
    return "\n\n".join(parts)
