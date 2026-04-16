"""Tests for ClaudeCLIProvider. All tests are offline (no subprocess calls)."""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from idea_search.providers.claude_cli_provider import (
    ClaudeCLIProvider,
    ClaudeCLIProviderError,
    _strip_code_fence,
)


# ---- PATH check ------------------------------------------------------

def test_missing_claude_binary_raises(monkeypatch):
    """PATH check should fire with a clear message when `claude` isn't found."""
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(ClaudeCLIProviderError) as exc:
        ClaudeCLIProvider()
    msg = str(exc.value)
    assert "claude" in msg
    assert "PATH" in msg
    assert "mock" in msg  # mentions the mock fallback


def test_explicit_binary_bypasses_which(monkeypatch):
    """Passing claude_binary= should skip PATH lookup."""
    monkeypatch.setattr("shutil.which", lambda name: None)
    p = ClaudeCLIProvider(claude_binary="/fake/claude")
    assert p._binary == "/fake/claude"
    assert p._model == "sonnet"


# ---- Code fence stripping --------------------------------------------

def test_strip_fence_removes_json_fence():
    text = '```json\n{"a": 1}\n```'
    assert _strip_code_fence(text) == '{"a": 1}'


def test_strip_fence_removes_plain_fence():
    text = "```\n[1, 2, 3]\n```"
    assert _strip_code_fence(text) == "[1, 2, 3]"


def test_strip_fence_noop_when_no_fence():
    text = '{"already": "clean"}'
    assert _strip_code_fence(text) == '{"already": "clean"}'


# ---- Parse / retry / fallback flags ---------------------------------

class _FakeCliProvider(ClaudeCLIProvider):
    """Bypasses PATH check and stubs _raw_complete with canned responses."""

    def __init__(self, responses: List[str]) -> None:
        self._binary = "/fake/claude"
        self._model = "sonnet"
        self._timeout_sec = 120
        self._responses = list(responses)
        self._calls: List[Dict[str, Any]] = []

    def _raw_complete(self, system_prompt, user_prompt):
        self._calls.append({"system": system_prompt, "user": user_prompt})
        return self._responses.pop(0)


def test_happy_path_no_retry_no_fallback():
    p = _FakeCliProvider(['{"ok": true}'])
    parsed, meta = p._complete_json("sys", "usr", expect="object")
    assert parsed == {"ok": True}
    assert meta["retry_used"] is False
    assert meta["parsed_via_fallback"] is False
    assert meta["raw_result_excerpt"] is None


def test_regex_fallback_when_extra_text():
    p = _FakeCliProvider(['{"a": 1} extra trailing garbage'])
    parsed, meta = p._complete_json("sys", "usr", expect="object")
    assert parsed == {"a": 1}
    assert meta["retry_used"] is False
    assert meta["parsed_via_fallback"] is True
    assert meta["raw_result_excerpt"] is not None
    assert "extra trailing garbage" in meta["raw_result_excerpt"]


def test_retry_used_when_first_unparseable():
    p = _FakeCliProvider(["totally not json", '[1, 2, 3]'])
    parsed, meta = p._complete_json("sys", "usr", expect="array")
    assert parsed == [1, 2, 3]
    assert meta["retry_used"] is True
    assert meta["parsed_via_fallback"] is False
    assert meta["raw_result_excerpt"] is not None
    assert len(p._calls) == 2


def test_fallback_returns_empty_after_both_attempts_fail(caplog):
    p = _FakeCliProvider(["junk1", "junk2"])
    with caplog.at_level("ERROR"):
        parsed, meta = p._complete_json("sys", "usr", expect="array")
    assert parsed == []
    assert meta["retry_used"] is True
    assert meta["parsed_via_fallback"] is True
    assert meta["raw_result_excerpt"] is not None
    assert any("parsing failed" in r.message.lower() for r in caplog.records)


def test_warning_logged_on_regex_rescue(caplog):
    p = _FakeCliProvider(['{"a": 1} trailing'])
    with caplog.at_level("WARNING"):
        p._complete_json("sys", "usr", expect="object")
    assert any("regex fallback" in r.message.lower() for r in caplog.records)
