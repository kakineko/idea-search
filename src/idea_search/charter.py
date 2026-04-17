"""Charter loader.

The charter (``charter.md`` at the project root) is the single input from
the President (社長) to the harness. This module only handles *reading*
the file and merging its machine-readable section into a runtime config.

Out of scope here (deferred to a later task):

* Injecting charter prose into LLM prompts.
* Detecting boundary violations or budget overruns.
* Triggering escalation / runtime stops.
"""
from __future__ import annotations

import re
import warnings
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class Charter(BaseModel):
    """Parsed charter document.

    All fields are optional / default-empty so an absent or partially-filled
    charter file still produces a valid object.
    """

    version: Optional[str] = None
    last_reviewed_on: Optional[date] = None  # accepts YAML bare date or ISO string
    budget: Dict[str, Optional[float]] = Field(default_factory=dict)
    stop_conditions: Dict[str, Any] = Field(default_factory=dict)
    risk: Dict[str, Any] = Field(default_factory=dict)
    escalation: Dict[str, Any] = Field(default_factory=dict)
    # Note: YAML floats (e.g. 14.5) are silently truncated by int(); write integers.
    review_cadence_days: Optional[int] = None
    body_sections: Dict[str, str] = Field(default_factory=dict)
    raw_body: str = ""

    @field_validator("last_reviewed_on", mode="before")
    @classmethod
    def _coerce_last_reviewed(cls, v):
        if v is None or isinstance(v, date):
            return v
        if isinstance(v, str):
            try:
                return date.fromisoformat(v)
            except ValueError as e:
                raise ValueError(
                    f"last_reviewed_on must be ISO date string (YYYY-MM-DD), "
                    f"got: {v!r}"
                ) from e
        raise ValueError(
            f"last_reviewed_on must be date or ISO string, "
            f"got {type(v).__name__}"
        )

    def is_empty(self) -> bool:
        """True when no *configuration* field carries information.

        Meta-only fields (``version``, ``last_reviewed_on``) are intentionally
        ignored: a charter that records its own version but specifies nothing
        actionable still merges as a no-op.
        """
        return (
            all(v is None for v in self.budget.values())
            and not self.stop_conditions
            and not self.risk
            and not self.escalation
            and self.review_cadence_days is None
            and not self.body_sections
        )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HEADER_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _default_charter_path() -> Path:
    """Project-root ``charter.md`` (mirrors ``cli.DEFAULT_CONFIG_PATH``)."""
    return Path(__file__).resolve().parents[2] / "charter.md"


def _to_snake(name: str) -> str:
    """``"Risk Tolerance"`` → ``"risk_tolerance"``."""
    cleaned = re.sub(r"[^\w\s]", "", name).strip().lower()
    return re.sub(r"\s+", "_", cleaned)


def _split_sections(body: str) -> Dict[str, str]:
    """Split markdown body by level-2 headers, strip ``<!-- ... -->`` comments."""
    sections: Dict[str, str] = {}
    matches = list(_HEADER_RE.finditer(body))
    for i, m in enumerate(matches):
        key = _to_snake(m.group(1))
        if not key:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        content = _COMMENT_RE.sub("", body[start:end]).strip()
        sections[key] = content
    return sections


def _parse_frontmatter(text: str) -> tuple[Dict[str, Any], str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_text, body = m.group(1), m.group(2)
    try:
        loaded = yaml.safe_load(fm_text)
    except yaml.YAMLError as e:
        warnings.warn(
            f"charter.md frontmatter is invalid YAML; ignoring: {e}",
            stacklevel=2,
        )
        return {}, body
    if loaded is None:
        return {}, body
    if not isinstance(loaded, dict):
        warnings.warn(
            f"charter.md frontmatter must be a mapping; got "
            f"{type(loaded).__name__}; ignoring.",
            stacklevel=2,
        )
        return {}, body
    return loaded, body


def _coerce_dict(value: Any, field_name: str) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    warnings.warn(
        f"charter.md field '{field_name}' must be a mapping; ignoring.",
        stacklevel=2,
    )
    return {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_charter(path: Path | None = None) -> Charter:
    """Load the charter file. Returns an empty ``Charter`` when absent.

    A missing file is the normal initial state and never raises.
    Invalid YAML in the frontmatter is degraded to an empty frontmatter
    with a ``UserWarning``.
    """
    target = Path(path) if path is not None else _default_charter_path()
    if not target.exists():
        return Charter()

    text = target.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    sections = _split_sections(body)

    version_val = fm.get("version", fm.get("charter_version"))
    if version_val is not None:
        version_val = str(version_val)

    review = fm.get("review_cadence_days")
    if review is not None:
        try:
            review = int(review)
        except (TypeError, ValueError):
            warnings.warn(
                f"charter.md review_cadence_days must be int; got {review!r}; "
                "ignoring.",
                stacklevel=2,
            )
            review = None

    return Charter(
        version=version_val,
        last_reviewed_on=fm.get("last_reviewed_on"),
        budget=_coerce_dict(fm.get("budget"), "budget"),
        stop_conditions=_coerce_dict(fm.get("stop_conditions"), "stop_conditions"),
        risk=_coerce_dict(fm.get("risk"), "risk"),
        escalation=_coerce_dict(fm.get("escalation"), "escalation"),
        review_cadence_days=review,
        body_sections=sections,
        raw_body=body.strip(),
    )


_MERGE_KEYS = ("budget", "stop_conditions", "risk", "escalation")


def merge_charter_into_config(
    charter: Charter, config: Dict[str, Any]
) -> Dict[str, Any]:
    """Mutate ``config`` in place so charter values take precedence.

    Rules:

    * ``None`` values in the charter are treated as "unspecified" and
      never overwrite an existing config value.
    * For dict subtrees (``budget``, ``stop_conditions``, ``risk``,
      ``escalation``) we shallow-merge: only keys with non-``None``
      charter values are written.
    * If the charter is empty, this is a complete no-op.
    """
    if charter.is_empty():
        return config

    for key in _MERGE_KEYS:
        section = getattr(charter, key)
        if not section:
            continue
        target = config.get(key)
        if not isinstance(target, dict):
            target = {}
            config[key] = target
        for k, v in section.items():
            if v is None:
                continue
            target[k] = v

    if charter.review_cadence_days is not None:
        config["review_cadence_days"] = charter.review_cadence_days

    return config
