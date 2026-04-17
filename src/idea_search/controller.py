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


class Controller:
    def __init__(self, provider: LLMProvider, config: Dict[str, Any]):
        self.provider = provider
        self.config = config
        self.charter = load_charter()
        merge_charter_into_config(self.charter, self.config)
        archive_path = config.get("archive", {}).get("path", "archive/ideas.jsonl")
        self.archive = ArchiveStore(archive_path)
        self.session_id = uuid.uuid4().hex[:8]

    def run(self, problem: ProblemInput) -> Dict[str, Any]:
        rounds = int(self.config.get("rounds", 2))
        previous_evaluated: List[Tuple[Idea, Evaluation]] | None = None
        all_evaluated: List[Tuple[Idea, Evaluation]] = []
        all_cliche_patterns: set[str] = set()

        archive_texts = list(self.archive.iter_idea_texts())

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
            archive_texts = list(self.archive.iter_idea_texts())

            all_evaluated.extend(evaluated)
            previous_evaluated = evaluated

        return {
            "session_id": self.session_id,
            "rounds": rounds,
            "evaluated": all_evaluated,
            "cliche_reasons": sorted(all_cliche_patterns),
        }
