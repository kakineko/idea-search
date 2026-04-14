"""Tests for AnthropicProvider.

All tests here avoid calling the real API. They cover:
- Module import safety (no SDK / no key required just to import)
- Clear error when API key is missing
- JSON extraction fallback logic
- Coercion helpers
- Prefill switch by expect type via monkeypatched _raw_complete
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import pytest

from idea_search.providers.anthropic_provider import (
    AnthropicProvider,
    AnthropicProviderError,
    _coerce_axis_eval,
    _coerce_branch_dict,
    _coerce_branch_eval,
    _coerce_idea_dict,
    _extract_first_json,
)


# ---- Error cases -----------------------------------------------------

def test_missing_api_key_raises_clear_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(AnthropicProviderError) as exc_info:
        AnthropicProvider()
    msg = str(exc_info.value)
    assert "ANTHROPIC_API_KEY" in msg
    assert "mock" in msg  # mentions the mock fallback


def test_explicit_api_key_bypasses_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Should not raise for missing key; will raise only if SDK not installed
    try:
        provider = AnthropicProvider(api_key="sk-ant-test")
        assert provider.name == "anthropic"
    except AnthropicProviderError as e:
        # Acceptable only if the SDK itself isn't installed
        assert "anthropic" in str(e).lower()


# ---- JSON extraction -------------------------------------------------

def test_extract_first_json_object():
    text = 'prefix {"a": 1, "b": [1, 2, 3]} suffix'
    assert _extract_first_json(text, "object") == {"a": 1, "b": [1, 2, 3]}


def test_extract_first_json_array():
    text = 'noise before [1, 2, {"k": "v"}] trailing'
    assert _extract_first_json(text, "array") == [1, 2, {"k": "v"}]


def test_extract_handles_nested_braces():
    text = 'x {"outer": {"inner": {"deep": true}}} y'
    assert _extract_first_json(text, "object") == {
        "outer": {"inner": {"deep": True}}
    }


def test_extract_handles_strings_with_braces():
    text = 'pre {"msg": "has } brace and [ bracket", "n": 1} post'
    assert _extract_first_json(text, "object") == {
        "msg": "has } brace and [ bracket",
        "n": 1,
    }


def test_extract_returns_none_when_no_json():
    assert _extract_first_json("hello world", "object") is None
    assert _extract_first_json("hello world", "array") is None


# ---- Coercion helpers ------------------------------------------------

def test_coerce_axis_eval_clamps_and_defaults():
    assert _coerce_axis_eval({"score": 10, "rationale": "r", "suggestion": "s"})["score"] == 5.0
    assert _coerce_axis_eval({"score": -1})["score"] == 0.0
    assert _coerce_axis_eval({"score": "bad"})["score"] == 3.0
    assert _coerce_axis_eval("not a dict")["score"] == 3.0


def test_coerce_idea_dict_preserves_fields():
    raw = {"title": "T", "statement": "S", "rationale": "R", "tags": ["a", "b"]}
    out = _coerce_idea_dict(raw, role="Proposer")
    assert out["title"] == "T"
    assert out["tags"] == ["a", "b"]


def test_coerce_idea_dict_handles_missing_fields():
    out = _coerce_idea_dict({}, role="Proposer")
    assert out["title"] == "(untitled)"
    assert out["tags"] == ["proposer"]


def test_coerce_branch_eval_fills_all_axes():
    out = _coerce_branch_eval({"upside": {"score": 4.0, "rationale": "r", "suggestion": "s"}})
    for axis in ("upside", "cost", "risk", "validation_speed", "personal_fit", "data_availability"):
        assert axis in out
        assert 0.0 <= out[axis]["score"] <= 5.0


def test_coerce_branch_dict_defaults():
    out = _coerce_branch_dict({"branch_name": "X"})
    assert out["branch_name"] == "X"
    assert out["required_capital"] == "unknown"
    assert out["assumptions"] == []


# ---- Prefill switch + flags behavior ---------------------------------

class _FakeProvider(AnthropicProvider):
    """Bypasses __init__ to avoid needing a real API key or SDK."""

    def __init__(self, responses: List[str]) -> None:
        # Skip parent __init__; set required internals manually
        self._api_key = "fake"
        self._model = "fake-model"
        self._client = None
        self._responses = list(responses)
        self._calls: List[Dict[str, Any]] = []

    def _raw_complete(self, system_prompt, user_prompt, prefill, max_tokens):
        self._calls.append({
            "system": system_prompt,
            "user": user_prompt,
            "prefill": prefill,
            "max_tokens": max_tokens,
        })
        return self._responses.pop(0)


def test_prefill_is_curly_for_object():
    p = _FakeProvider(['{"ok": 1}'])
    parsed, flags = p._complete_json("sys", "usr", expect="object")
    assert parsed == {"ok": 1}
    assert p._calls[0]["prefill"] == "{"
    assert flags == {"retry_used": False, "parsed_via_fallback": False}


def test_prefill_is_square_for_array():
    p = _FakeProvider(['[1, 2, 3]'])
    parsed, flags = p._complete_json("sys", "usr", expect="array")
    assert parsed == [1, 2, 3]
    assert p._calls[0]["prefill"] == "["
    assert flags == {"retry_used": False, "parsed_via_fallback": False}


def test_parsed_via_fallback_flag_when_regex_rescues():
    # Raw output has trailing garbage that breaks json.loads but
    # _extract_first_json can still recover the first balanced block
    p = _FakeProvider(['{"a": 1} EXTRA TEXT AFTER'])
    parsed, flags = p._complete_json("sys", "usr", expect="object")
    assert parsed == {"a": 1}
    assert flags["parsed_via_fallback"] is True
    assert flags["retry_used"] is False


def test_retry_used_flag_when_first_attempt_unparseable():
    # First response has no JSON at all; second response is clean
    p = _FakeProvider(["totally not json", '{"ok": true}'])
    parsed, flags = p._complete_json("sys", "usr", expect="object")
    assert parsed == {"ok": True}
    assert flags["retry_used"] is True
    assert flags["parsed_via_fallback"] is False
    assert len(p._calls) == 2


def test_fallback_returns_empty_after_both_attempts_fail(caplog):
    p = _FakeProvider(["junk1", "junk2"])
    with caplog.at_level("ERROR"):
        parsed, flags = p._complete_json("sys", "usr", expect="array")
    assert parsed == []
    assert flags["retry_used"] is True
    assert flags["parsed_via_fallback"] is True
    assert any("parsing failed" in r.message.lower() for r in caplog.records)


def test_warning_log_on_regex_fallback(caplog):
    p = _FakeProvider(['{"a": 1} trailing'])
    with caplog.at_level("WARNING"):
        p._complete_json("sys", "usr", expect="object")
    assert any("regex fallback" in r.message.lower() for r in caplog.records)
