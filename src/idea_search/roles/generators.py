"""Generator role wrappers."""
from __future__ import annotations

import uuid
from typing import List, Dict, Any

from idea_search.providers.base import LLMProvider
from idea_search.roles.prompts import GENERATOR_PROMPTS
from idea_search.schema import Idea, ProblemInput


GENERATOR_ROLES = [
    "Proposer",
    "Reframer",
    "Contrarian",
    "AnalogyFinder",
    "ConstraintHacker",
    "Synthesizer",
]


def run_generator(
    provider: LLMProvider,
    role: str,
    problem: ProblemInput,
    round_index: int,
    prior_fragments: List[Dict[str, Any]] | None = None,
) -> List[Idea]:
    system_prompt = GENERATOR_PROMPTS[role]
    raw = provider.generate_ideas(
        role=role,
        system_prompt=system_prompt,
        problem=problem.problem,
        constraints=problem.constraints,
        context=problem.context or "",
        round_index=round_index,
        prior_fragments=prior_fragments or [],
        n=2,
    )
    ideas: List[Idea] = []
    for item in raw:
        idea = Idea(
            id=uuid.uuid4().hex[:10],
            round=round_index,
            role=role,
            title=item.get("title", "(untitled)"),
            statement=item.get("statement", ""),
            rationale=item.get("rationale", ""),
            tags=item.get("tags", []),
            parent_ids=[f["id"] for f in (prior_fragments or []) if "id" in f],
        )
        ideas.append(idea)
    return ideas
