"""Generator pipeline: runs each generator role and tags cliché candidates.

Synthesizer input rules:
    Round 1: receives all ideas produced by the other generators in this round.
    Round 2+: receives curated fragments:
        - top-N high novelty from previous round
        - top-N high feasibility from previous round
        - fragments from critic-broken ideas (low-score or high-risk)
"""
from __future__ import annotations

import re
from typing import List, Dict, Any, Tuple

from idea_search.providers.base import LLMProvider
from idea_search.roles.generators import run_generator
from idea_search.schema import Idea, Evaluation, ProblemInput
from idea_search.similarity import (
    jaccard, matches_cliche_pattern, compile_cliche_patterns,
)


def _fragment_from_idea(idea: Idea, reason: str) -> Dict[str, Any]:
    return {
        "id": idea.id,
        "title": idea.title,
        "statement": idea.statement,
        "reason": reason,
    }


def select_synthesizer_inputs(
    round_index: int,
    current_round_ideas: List[Idea],
    previous_evaluated: List[Tuple[Idea, Evaluation]] | None,
    *,
    high_novelty_top_k: int = 3,
    high_feasibility_top_k: int = 3,
    include_critic_fragments: bool = True,
) -> List[Dict[str, Any]]:
    """Return the fragment list the Synthesizer should consume this round."""
    if round_index == 1 or not previous_evaluated:
        # Round 1: feed raw ideas from generators (excluding Synthesizer itself).
        return [
            _fragment_from_idea(i, reason="round1-generator")
            for i in current_round_ideas
            if i.role != "Synthesizer"
        ]

    # Round 2+: curated fragments from the previous round.
    by_novelty = sorted(
        previous_evaluated, key=lambda p: p[1].novelty.score, reverse=True,
    )[:high_novelty_top_k]
    by_feasibility = sorted(
        previous_evaluated, key=lambda p: p[1].feasibility.score, reverse=True,
    )[:high_feasibility_top_k]

    fragments: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    for idea, _ in by_novelty:
        if idea.id not in seen_ids:
            fragments.append(_fragment_from_idea(idea, reason="high-novelty"))
            seen_ids.add(idea.id)
    for idea, _ in by_feasibility:
        if idea.id not in seen_ids:
            fragments.append(_fragment_from_idea(idea, reason="high-feasibility"))
            seen_ids.add(idea.id)

    if include_critic_fragments:
        # "critic-broken": low composite OR high risk with low feasibility
        for idea, ev in previous_evaluated:
            broken = (ev.composite() < 6.0) or (
                ev.risk.score >= 3.5 and ev.feasibility.score < 3.0
            )
            if broken and idea.id not in seen_ids:
                fragments.append(_fragment_from_idea(
                    idea,
                    reason=f"critic-broken ({ev.risk.suggestion})",
                ))
                seen_ids.add(idea.id)
    return fragments


def flag_cliches(
    ideas: List[Idea],
    archive_texts: List[tuple[str, str]],
    cliche_patterns: List[str],
    *,
    similarity_threshold: float = 0.55,
    cliche_threshold: float = 0.70,
) -> List[Idea]:
    """Mutates cliche_flag / similar_to on each idea and returns the list."""
    compiled = compile_cliche_patterns(cliche_patterns)
    for idea in ideas:
        text = idea.to_text()

        pattern_hits = matches_cliche_pattern(text, compiled)
        reasons: List[str] = []
        if pattern_hits:
            reasons.append(f"matches cliche pattern(s): {', '.join(pattern_hits)}")

        similar = []
        for aid, atext in archive_texts:
            score = jaccard(text, atext)
            if score >= similarity_threshold:
                similar.append((aid, score))
        similar.sort(key=lambda p: p[1], reverse=True)
        idea.similar_to = [aid for aid, _ in similar[:3]]

        if similar and similar[0][1] >= cliche_threshold:
            reasons.append(
                f"very similar to archive id {similar[0][0]} "
                f"(jaccard={similar[0][1]:.2f})"
            )

        if reasons:
            idea.cliche_flag = True
            idea.cliche_reason = "; ".join(reasons)
    return ideas


def run_generator_round(
    provider: LLMProvider,
    problem: ProblemInput,
    round_index: int,
    previous_evaluated: List[Tuple[Idea, Evaluation]] | None,
    archive_texts: List[tuple[str, str]],
    config: Dict[str, Any],
) -> List[Idea]:
    """Run one round of generation. Synthesizer runs last with curated input."""
    generator_roles = config.get("generators", [])
    non_synth = [r for r in generator_roles if r != "Synthesizer"]

    ideas: List[Idea] = []
    for role in non_synth:
        ideas.extend(run_generator(provider, role, problem, round_index))

    if "Synthesizer" in generator_roles:
        synth_conf = config.get("synthesizer", {})
        fragments = select_synthesizer_inputs(
            round_index=round_index,
            current_round_ideas=ideas,
            previous_evaluated=previous_evaluated,
            high_novelty_top_k=synth_conf.get("high_novelty_top_k", 3),
            high_feasibility_top_k=synth_conf.get("high_feasibility_top_k", 3),
            include_critic_fragments=synth_conf.get("include_critic_fragments", True),
        )
        ideas.extend(run_generator(
            provider, "Synthesizer", problem, round_index,
            prior_fragments=fragments,
        ))

    sim_conf = config.get("similarity", {})
    flag_cliches(
        ideas,
        archive_texts=archive_texts,
        cliche_patterns=config.get("cliche_patterns", []),
        similarity_threshold=sim_conf.get("jaccard_threshold", 0.55),
        cliche_threshold=sim_conf.get("cliche_threshold", 0.70),
    )
    return ideas
