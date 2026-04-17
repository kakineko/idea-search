"""Unit tests for charter loading and config merge."""
from __future__ import annotations

import warnings
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from idea_search.charter import (
    Charter,
    load_charter,
    merge_charter_into_config,
)


# ---------------------------------------------------------------------------
# load_charter
# ---------------------------------------------------------------------------

def test_load_charter_returns_empty_when_file_missing(tmp_path: Path):
    missing = tmp_path / "nope.md"
    charter = load_charter(missing)
    assert isinstance(charter, Charter)
    assert charter.is_empty()
    assert charter.budget == {}
    assert charter.body_sections == {}


def test_load_charter_frontmatter_only(tmp_path: Path):
    p = tmp_path / "charter.md"
    p.write_text(
        "---\n"
        "charter_version: 2\n"
        "last_reviewed_on: 2026-04-17\n"
        "budget:\n"
        "  monthly_usd: 50\n"
        "  per_run_usd: null\n"
        "stop_conditions:\n"
        "  max_runs_per_day: 20\n"
        "review_cadence_days: 14\n"
        "---\n",
        encoding="utf-8",
    )
    c = load_charter(p)
    assert c.version == "2"
    assert c.last_reviewed_on == date(2026, 4, 17)
    assert c.budget == {"monthly_usd": 50.0, "per_run_usd": None}
    assert c.stop_conditions == {"max_runs_per_day": 20}
    assert c.review_cadence_days == 14
    assert c.body_sections == {}
    assert c.raw_body == ""


def test_load_charter_body_only_no_frontmatter(tmp_path: Path):
    p = tmp_path / "charter.md"
    p.write_text(
        "# Charter\n\n"
        "## Mission\n"
        "<!-- example placeholder -->\n"
        "Generate diverse hypotheses.\n\n"
        "## Risk Tolerance\n"
        "Take calculated bets.\n",
        encoding="utf-8",
    )
    c = load_charter(p)
    assert c.version is None
    assert c.budget == {}
    assert "mission" in c.body_sections
    assert "risk_tolerance" in c.body_sections
    # HTML comments are stripped
    assert "placeholder" not in c.body_sections["mission"]
    assert "Generate diverse hypotheses." in c.body_sections["mission"]
    assert c.body_sections["risk_tolerance"] == "Take calculated bets."


def test_load_charter_full_document(tmp_path: Path):
    p = tmp_path / "charter.md"
    p.write_text(
        "---\n"
        "charter_version: 1\n"
        "budget:\n"
        "  monthly_usd: 30\n"
        "risk:\n"
        "  irreversible_actions_allowed: false\n"
        "---\n"
        "# Charter\n\n"
        "## Mission\n"
        "<!-- 例: foo -->\n"
        "Be the front stage of verification.\n\n"
        "## Boundaries\n"
        "- no external writes\n",
        encoding="utf-8",
    )
    c = load_charter(p)
    assert c.version == "1"
    assert c.budget == {"monthly_usd": 30.0}
    assert c.risk == {"irreversible_actions_allowed": False}
    assert set(c.body_sections.keys()) == {"mission", "boundaries"}
    assert c.body_sections["mission"] == "Be the front stage of verification."
    assert "no external writes" in c.body_sections["boundaries"]


def test_load_charter_invalid_yaml_warns_and_degrades(tmp_path: Path):
    p = tmp_path / "charter.md"
    p.write_text(
        "---\n"
        "budget: {monthly_usd: 30\n"  # broken: missing closing brace
        "  this is: not yaml: at all:\n"
        "---\n"
        "## Mission\nhello\n",
        encoding="utf-8",
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        c = load_charter(p)
    messages = [str(w.message) for w in caught]
    assert any("invalid YAML" in m for m in messages)
    # Frontmatter is dropped, but body still parses.
    assert c.budget == {}
    assert c.body_sections.get("mission") == "hello"


def test_load_charter_section_split_normalizes_headers(tmp_path: Path):
    p = tmp_path / "charter.md"
    p.write_text(
        "## Tone & Style\n"
        "Be terse.\n\n"
        "## Emergency Stop Conditions\n"
        "Halt on cap.\n\n"
        "## Change Log\n"
        "- v0 init\n",
        encoding="utf-8",
    )
    c = load_charter(p)
    assert set(c.body_sections.keys()) == {
        "tone_style",
        "emergency_stop_conditions",
        "change_log",
    }
    assert c.body_sections["change_log"] == "- v0 init"


def test_load_charter_empty_file(tmp_path: Path):
    p = tmp_path / "charter.md"
    p.write_text("", encoding="utf-8")
    c = load_charter(p)
    assert c.is_empty()


def test_load_charter_frontmatter_non_mapping_warns(tmp_path: Path):
    p = tmp_path / "charter.md"
    p.write_text(
        "---\n"
        "- just\n"
        "- a\n"
        "- list\n"
        "---\n",
        encoding="utf-8",
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        c = load_charter(p)
    assert any("must be a mapping" in str(w.message) for w in caught)
    assert c.is_empty()


# ---------------------------------------------------------------------------
# last_reviewed_on date coercion
# ---------------------------------------------------------------------------

def test_last_reviewed_on_iso_string(tmp_path: Path):
    """Quoted ISO string is parsed into a date."""
    p = tmp_path / "charter.md"
    p.write_text(
        "---\n"
        'last_reviewed_on: "2026-04-17"\n'
        "---\n",
        encoding="utf-8",
    )
    c = load_charter(p)
    assert c.last_reviewed_on == date(2026, 4, 17)


def test_last_reviewed_on_invalid_string(tmp_path: Path):
    """A non-ISO string is rejected with ValidationError."""
    p = tmp_path / "charter.md"
    p.write_text(
        "---\n"
        'last_reviewed_on: "not-a-date"\n'
        "---\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_charter(p)


def test_last_reviewed_on_none(tmp_path: Path):
    """Explicit null in YAML stays None on the model."""
    p = tmp_path / "charter.md"
    p.write_text(
        "---\n"
        "last_reviewed_on: null\n"
        "---\n",
        encoding="utf-8",
    )
    c = load_charter(p)
    assert c.last_reviewed_on is None


# ---------------------------------------------------------------------------
# is_empty semantics
# ---------------------------------------------------------------------------

def test_is_empty_ignores_meta_fields(tmp_path: Path):
    """A charter with only version + last_reviewed_on counts as empty."""
    p = tmp_path / "charter.md"
    p.write_text(
        "---\n"
        "charter_version: 3\n"
        "last_reviewed_on: 2026-04-17\n"
        "---\n",
        encoding="utf-8",
    )
    c = load_charter(p)
    assert c.version == "3"
    assert c.last_reviewed_on == date(2026, 4, 17)
    assert c.is_empty()


def test_is_empty_false_with_actual_content(tmp_path: Path):
    """Any real configuration value flips is_empty to False."""
    p = tmp_path / "charter.md"
    p.write_text(
        "---\n"
        "budget:\n"
        "  monthly_usd: 30\n"
        "---\n",
        encoding="utf-8",
    )
    c = load_charter(p)
    assert not c.is_empty()


def test_is_empty_with_only_null_budget_values(tmp_path: Path):
    """Budget keys present but all-null still counts as empty."""
    p = tmp_path / "charter.md"
    p.write_text(
        "---\n"
        "budget:\n"
        "  monthly_usd: null\n"
        "  per_run_usd: null\n"
        "---\n",
        encoding="utf-8",
    )
    c = load_charter(p)
    assert c.is_empty()


# ---------------------------------------------------------------------------
# merge_charter_into_config
# ---------------------------------------------------------------------------

def test_merge_empty_charter_is_noop():
    config = {"rounds": 2, "provider": "mock"}
    snapshot = dict(config)
    merge_charter_into_config(Charter(), config)
    assert config == snapshot


def test_merge_skips_none_values():
    config = {"budget": {"monthly_usd": 100.0}}
    charter = Charter(budget={"monthly_usd": None, "per_run_usd": 0.5})
    merge_charter_into_config(charter, config)
    # None did not clobber the existing value
    assert config["budget"]["monthly_usd"] == 100.0
    # New non-None key was added
    assert config["budget"]["per_run_usd"] == 0.5


def test_merge_charter_overrides_existing_config_value():
    config = {"budget": {"monthly_usd": 100.0}}
    charter = Charter(budget={"monthly_usd": 30.0})
    merge_charter_into_config(charter, config)
    assert config["budget"]["monthly_usd"] == 30.0


def test_merge_creates_missing_top_level_keys():
    config = {"rounds": 1}
    charter = Charter(
        risk={"irreversible_actions_allowed": False},
        review_cadence_days=14,
    )
    merge_charter_into_config(charter, config)
    assert config["risk"] == {"irreversible_actions_allowed": False}
    assert config["review_cadence_days"] == 14


def test_merge_replaces_non_dict_existing_subtree():
    config = {"budget": "not a dict"}
    charter = Charter(budget={"monthly_usd": 30.0})
    merge_charter_into_config(charter, config)
    assert config["budget"] == {"monthly_usd": 30.0}


# ---------------------------------------------------------------------------
# Integration: real project charter.md does not break Controller construction
# ---------------------------------------------------------------------------

def test_load_real_project_charter_does_not_raise():
    """The repo's own charter.md (mostly nulls) must load cleanly."""
    c = load_charter()  # default path
    # Whether or not the file exists, this must succeed.
    assert isinstance(c, Charter)
