"""Round controller: orchestrates generate -> evaluate -> archive -> next round."""
from __future__ import annotations

import uuid
from typing import List, Tuple, Dict, Any

from idea_search.archive import ArchiveStore
from idea_search.charter import load_charter, merge_charter_into_config
from idea_search.pipeline.generator_pipeline import run_generator_round
from idea_search.pipeline.evaluator_pipeline import run_evaluator_round
from idea_search.providers.base import LLMProvider
from idea_search.schema import Idea, Evaluation, ProblemInput


def _resolve_archive_path(archive_cfg: Dict[str, Any], session_id: str) -> str:
    """Pick the archive path with this priority:

    1. explicit ``archive.path`` from config — used as given;
    2. ``archive.shared: true`` (no explicit path) — fixed legacy file
       ``archive/ideas.jsonl`` so multiple runs accumulate;
    3. otherwise — ``archive/session_<session_id>.jsonl`` so consecutive
       runs do not pollute each other.
    """
    explicit = archive_cfg.get("path")
    if explicit:
        return str(explicit)
    if archive_cfg.get("shared", False):
        return "archive/ideas.jsonl"
    return f"archive/session_{session_id}.jsonl"


class Controller:
    def __init__(self, provider: LLMProvider, config: Dict[str, Any]):
        self.provider = provider
        self.config = config
        self.charter = load_charter()
        merge_charter_into_config(self.charter, self.config)
        self.session_id = uuid.uuid4().hex[:8]
        archive_cfg = config.get("archive") or {}
        archive_path = _resolve_archive_path(archive_cfg, self.session_id)
        self.archive = ArchiveStore(archive_path)
        self._archive_shared = bool(archive_cfg.get("shared", False))

    def run(self, problem: ProblemInput) -> Dict[str, Any]:
        rounds = int(self.config.get("rounds", 2))
        previous_evaluated: List[Tuple[Idea, Evaluation]] | None = None
        all_evaluated: List[Tuple[Idea, Evaluation]] = []
        all_cliche_patterns: set[str] = set()

        archive_texts = list(self._read_archive_texts())

        for round_index in range(1, rounds + 1):
            ideas = run_generator_round(
                provider=self.provider,
                problem=problem,
                round_index=round_index,
                previous_evaluated=previous_evaluated,
                archive_texts=archive_texts,
                config=self.config,
            )

            for idea in ideas:
                if idea.cliche_reason:
                    all_cliche_patterns.add(idea.cliche_reason)

            evaluated = run_evaluator_round(self.provider, problem, ideas)

            for idea, ev in evaluated:
                self.archive.append(idea, ev, session=self.session_id)

            # Refresh archive snapshot so later rounds see this round's ideas
            archive_texts = list(self._read_archive_texts())

            all_evaluated.extend(evaluated)
            previous_evaluated = evaluated

        return {
            "session_id": self.session_id,
            "rounds": rounds,
            "evaluated": all_evaluated,
            "cliche_reasons": sorted(all_cliche_patterns),
        }

    def _read_archive_texts(self):
        """Load archive texts; restrict to current session unless shared."""
        if self._archive_shared:
            return self.archive.iter_idea_texts()
        return self.archive.iter_idea_texts(session=self.session_id)
