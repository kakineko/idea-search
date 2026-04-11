"""Deterministic mock provider for MVP verification."""
from __future__ import annotations

import hashlib
from typing import List, Dict, Any

from idea_search.providers.base import LLMProvider


# Role-specific idea seeds. Each seed is a (title_template, angle) pair.
# The mock builds title/statement/rationale from seeds + problem keywords
# so output is deterministic but role-diverse.
# Intentionally generic, cliché-ish ideas for the baseline naive path.
# These stay the same regardless of problem so the structural difference
# between "one LLM call" and "role-separated system" is visible in reports.
_BASELINE_SEEDS: List[Dict[str, str]] = [
    {
        "title": "Launch an AI-powered platform for the problem",
        "statement": "Build an AI-powered platform that connects stakeholders and disrupts the industry.",
        "rationale": "Generic tech-first framing, assumes software is the answer.",
        "tags": ["ai", "platform", "generic"],
    },
    {
        "title": "Start a loyalty / membership program",
        "statement": "Introduce a points-based loyalty program to increase repeat engagement.",
        "rationale": "Default retention playbook.",
        "tags": ["loyalty", "retention", "generic"],
    },
    {
        "title": "Host community events",
        "statement": "Run regular community events to build awareness and word of mouth.",
        "rationale": "Generic marketing playbook.",
        "tags": ["events", "community", "generic"],
    },
    {
        "title": "Partner with a big brand",
        "statement": "Form a strategic partnership with a well-known brand to borrow credibility.",
        "rationale": "Generic BD angle.",
        "tags": ["partnership", "generic"],
    },
    {
        "title": "Offer a premium subscription tier",
        "statement": "Monetize via a premium subscription that unlocks curated extras.",
        "rationale": "Default monetization answer.",
        "tags": ["subscription", "monetization", "generic"],
    },
]


_ROLE_SEEDS: Dict[str, List[Dict[str, str]]] = {
    "Proposer": [
        {"angle": "direct-service", "hook": "Offer a curated hands-on service around {keyword}"},
        {"angle": "membership", "hook": "Create a low-fee membership focused on {keyword} community rituals"},
    ],
    "Reframer": [
        {"angle": "inversion", "hook": "Reframe the problem as {keyword} being a gathering space, not a retail outlet"},
        {"angle": "job-to-be-done", "hook": "Treat {keyword} as an anxiety-relief product, not a product-sale business"},
    ],
    "Contrarian": [
        {"angle": "against-consensus", "hook": "Deliberately shrink inventory and raise prices around {keyword} to signal scarcity"},
        {"angle": "anti-scale", "hook": "Refuse online sales entirely and optimize for hyper-local {keyword} loyalty"},
    ],
    "AnalogyFinder": [
        {"angle": "cross-domain", "hook": "Borrow the wine-bar tasting model and apply it to {keyword}"},
        {"angle": "historical", "hook": "Use the 19th-century salon model to host recurring {keyword} evenings"},
    ],
    "ConstraintHacker": [
        {"angle": "constraint-flip", "hook": "Turn the no-discount constraint into a premium {keyword} experience"},
        {"angle": "budget-flip", "hook": "Use the 5000 USD cap to force a single, high-signal {keyword} ritual"},
    ],
    "Synthesizer": [
        {"angle": "merge", "hook": "Combine scarcity signaling and salon model into a recurring {keyword} event"},
        {"angle": "bridge", "hook": "Bridge membership and analogy angles into a subscription {keyword} club"},
    ],
}


_JUDGE_BIAS: Dict[str, Dict[str, float]] = {
    # (role, judge) -> score bias
    "NoveltyJudge": {
        "Proposer": 2.0, "Reframer": 4.0, "Contrarian": 4.5,
        "AnalogyFinder": 4.0, "ConstraintHacker": 3.5, "Synthesizer": 3.5,
    },
    "FeasibilityJudge": {
        "Proposer": 4.5, "Reframer": 3.5, "Contrarian": 2.5,
        "AnalogyFinder": 3.0, "ConstraintHacker": 4.0, "Synthesizer": 3.5,
    },
    "ValueJudge": {
        "Proposer": 3.5, "Reframer": 4.0, "Contrarian": 3.0,
        "AnalogyFinder": 3.5, "ConstraintHacker": 3.5, "Synthesizer": 4.0,
    },
    "RiskJudge": {
        "Proposer": 1.5, "Reframer": 2.0, "Contrarian": 3.5,
        "AnalogyFinder": 2.5, "ConstraintHacker": 2.0, "Synthesizer": 2.0,
    },
}


def _keywords(problem: str, top_k: int = 3) -> List[str]:
    stop = {"the", "a", "an", "and", "or", "to", "of", "for", "with",
            "without", "on", "in", "at", "by", "help", "must", "be"}
    tokens = [
        t.lower().strip(".,;:!?") for t in problem.split()
        if len(t) > 3 and t.lower() not in stop
    ]
    seen: List[str] = []
    for t in tokens:
        if t not in seen:
            seen.append(t)
        if len(seen) >= top_k:
            break
    return seen or ["idea"]


def _score(role: str, judge: str, seed: str) -> float:
    base = _JUDGE_BIAS.get(judge, {}).get(role, 3.0)
    jitter = int(hashlib.sha256((role + judge + seed).encode()).hexdigest(), 16) % 7
    val = base + (jitter - 3) * 0.2
    return round(max(0.0, min(5.0, val)), 2)


class MockProvider(LLMProvider):
    name = "mock"

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
        seeds = _ROLE_SEEDS.get(role, _ROLE_SEEDS["Proposer"])
        kws = _keywords(problem)
        ideas: List[Dict[str, Any]] = []
        for i, seed in enumerate(seeds[:n]):
            kw = kws[i % len(kws)]
            hook = seed["hook"].format(keyword=kw)
            parent_refs = ""
            if prior_fragments:
                parent_refs = " Built on: " + ", ".join(
                    f.get("title", "?") for f in prior_fragments[:3]
                )
            ideas.append({
                "title": f"[{role}/{seed['angle']}] {hook[:60]}",
                "statement": (
                    f"{hook}. In round {round_index}, the {role} angle "
                    f"focuses on '{kw}' under constraints: "
                    f"{'; '.join(constraints) if constraints else 'none'}."
                    f"{parent_refs}"
                ),
                "rationale": (
                    f"{role} chose the '{seed['angle']}' angle because it "
                    f"pushes against the obvious path for '{kw}' and exposes "
                    f"an under-explored direction."
                ),
                "tags": [role.lower(), seed["angle"], kw],
            })
        return ideas

    def evaluate_axis(
        self,
        judge: str,
        system_prompt: str,
        problem: str,
        idea_title: str,
        idea_statement: str,
    ) -> Dict[str, Any]:
        # Detect originating role from the title prefix "[Role/angle]"
        role = "Proposer"
        if idea_title.startswith("["):
            try:
                role = idea_title[1:].split("/", 1)[0]
            except Exception:
                pass
        score = _score(role, judge, idea_title)
        axis_comments = {
            "NoveltyJudge": (
                f"Novelty driven by the {role} framing",
                "Push one step further by removing the most generic element.",
            ),
            "FeasibilityJudge": (
                f"Feasibility within stated constraints looks workable",
                "Pilot with a single store before generalizing.",
            ),
            "ValueJudge": (
                f"Value is tied to how loyal the target audience is",
                "Quantify the value in terms of repeat visits per month.",
            ),
            "RiskJudge": (
                f"Main risk is misreading audience appetite",
                "Pre-commit a stop-loss: cancel if week-4 retention < 30%.",
            ),
        }
        rationale, suggestion = axis_comments.get(
            judge, ("Generic comment", "Generic improvement"),
        )
        return {
            "score": score,
            "rationale": rationale,
            "suggestion": suggestion,
        }

    def generate_baseline(
        self,
        problem: str,
        constraints: List[str],
        context: str,
        n: int = 3,
    ) -> List[Dict[str, Any]]:
        """Return generic, templated ideas regardless of problem specifics.
        Mimics what a naive single LLM call often produces: safe,
        cliché-sounding answers with little variety.
        """
        seeds = _BASELINE_SEEDS[:max(1, n)]
        kws = _keywords(problem)
        results: List[Dict[str, Any]] = []
        for i, seed in enumerate(seeds):
            kw = kws[i % len(kws)] if kws else "this problem"
            results.append({
                "title": seed["title"],
                "statement": seed["statement"] + f" (target: {kw})",
                "rationale": seed["rationale"],
                "tags": list(seed["tags"]),
            })
        return results

    def self_critique(
        self,
        problem: str,
        ideas: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Simulate a single model critiquing and revising its own output.
        Rewrites the most generic-sounding idea with a slightly more
        specific variant but keeps the overall structure (no role split).
        """
        if not ideas:
            return ideas
        revised: List[Dict[str, Any]] = []
        kws = _keywords(problem)
        kw = kws[0] if kws else "this problem"
        for i, idea in enumerate(ideas):
            # Rewrite the first "generic"-tagged idea more concretely
            if "generic" in idea.get("tags", []) and i == 0:
                revised.append({
                    "title": f"Revised: narrow down '{idea['title']}' to one concrete pilot",
                    "statement": (
                        f"After self-critique, pick one specific, testable version: "
                        f"run a 4-week pilot of the previous idea focused strictly on '{kw}' "
                        f"with one measurable success metric."
                    ),
                    "rationale": (
                        "Self-critique: the original was too generic. Added a concrete "
                        "timebox and a single metric, but still framed by the same model."
                    ),
                    "tags": ["self-critique", "pilot", "narrowed"],
                })
            else:
                revised.append(idea)
        return revised
