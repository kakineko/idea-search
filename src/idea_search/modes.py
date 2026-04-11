"""Pipeline variant modes used by the comparison runner."""
from __future__ import annotations

from enum import Enum
from typing import List


class Mode(str, Enum):
    BASELINE_SINGLE = "baseline-single"
    BASELINE_SELF_CRITIQUE = "baseline-self-critique"
    GENERATOR_ONLY = "generator-only"
    GEN_EVAL = "gen-eval"
    FULL = "full"

    @classmethod
    def parse_list(cls, spec: str) -> List["Mode"]:
        """Parse a comma-separated list of mode names into Mode values."""
        out: List[Mode] = []
        for part in spec.split(","):
            name = part.strip()
            if not name:
                continue
            try:
                out.append(cls(name))
            except ValueError as e:
                valid = ", ".join(m.value for m in cls)
                raise ValueError(
                    f"Unknown mode '{name}'. Valid: {valid}"
                ) from e
        return out

    @classmethod
    def all(cls) -> List["Mode"]:
        return list(cls)
