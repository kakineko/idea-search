"""Markdown comparison report. Designed for human scoring:
blank score columns for novelty / feasibility / actionability per idea,
and a mode-level variety column in the summary table.
"""
from __future__ import annotations

from typing import List

from idea_search.compare import ModeResult
from idea_search.schema import Evaluation


def _avg_machine_novelty(ideas_ids: List[str], evaluations: dict) -> str:
    scores = [evaluations[i].novelty.score for i in ideas_ids if i in evaluations]
    if not scores:
        return "n/a"
    return f"{sum(scores) / len(scores):.2f}"


def _avg_machine_composite(ideas_ids: List[str], evaluations: dict) -> str:
    scores = [evaluations[i].composite() for i in ideas_ids if i in evaluations]
    if not scores:
        return "n/a"
    return f"{sum(scores) / len(scores):.2f}"


def _excerpt(text: str, limit: int = 90) -> str:
    text = (text or "").replace("\n", " ").replace("|", "/")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def render_comparison(
    problem: str,
    results: List[ModeResult],
) -> str:
    lines: List[str] = []
    lines.append("# Idea Search — Mode Comparison")
    lines.append("")
    lines.append(f"**Problem**: {problem}")
    lines.append("")
    lines.append(
        "Diversity metrics are machine-computed. Per-idea scores "
        "(novelty / feasibility / actionability) are **for human scoring** — "
        "fill the blank cells with 0–5."
    )
    lines.append("")

    # -------- Summary table --------
    lines.append("## Summary")
    lines.append("")
    lines.append(
        "| Mode | #Ideas | #Tags(uniq) | AvgPairwiseSim↓ | ClusterProxy↑ | Cliché | MachineN | MachineComposite | HumanVariety |"
    )
    lines.append(
        "|------|-------:|------------:|----------------:|--------------:|-------:|---------:|-----------------:|:------------:|"
    )
    for r in results:
        d = r.diversity
        n_ideas = d.n_ideas if d else 0
        unique_tags = d.unique_tags if d else 0
        avg_sim = f"{d.avg_pairwise_similarity:.3f}" if d else "n/a"
        clusters = d.cluster_count_proxy if d else 0
        idea_ids = [i.id for i in r.ideas]
        avg_n = _avg_machine_novelty(idea_ids, r.evaluations)
        avg_c = _avg_machine_composite(idea_ids, r.evaluations)
        lines.append(
            f"| {r.mode_name()} | {n_ideas} | {unique_tags} | {avg_sim} | "
            f"{clusters} | {r.cliche_count} | {avg_n} | {avg_c} | [  ] |"
        )
    lines.append("")
    lines.append(
        "- **AvgPairwiseSim**: mean Jaccard between all idea pairs "
        "(lower = more diverse).\n"
        "- **ClusterProxy**: greedy clusters at Jaccard threshold 0.40 "
        "(higher = more distinct directions).\n"
        "- **HumanVariety**: fill manually — how many *directions* feel "
        "genuinely different to you."
    )
    lines.append("")

    # -------- Per-mode idea tables --------
    for r in results:
        lines.append(f"## Mode: {r.mode_name()}")
        lines.append("")
        lines.append(
            f"- Ideas: {len(r.ideas)} | "
            f"Unique tags: {r.diversity.unique_tags if r.diversity else 0} | "
            f"AvgPairwiseSim: "
            f"{r.diversity.avg_pairwise_similarity if r.diversity else 'n/a'} | "
            f"ClusterProxy: "
            f"{r.diversity.cluster_count_proxy if r.diversity else 0} | "
            f"Cliché flagged: {r.cliche_count}"
        )
        lines.append("")
        lines.append(
            "| # | Role | Title | Statement (excerpt) | Novelty | Feasibility | Actionability | MachineN | MachineF |"
        )
        lines.append(
            "|--:|------|-------|---------------------|:-------:|:-----------:|:-------------:|:--------:|:--------:|"
        )
        for idx, idea in enumerate(r.ideas, start=1):
            ev: Evaluation | None = r.evaluations.get(idea.id)
            mn = f"{ev.novelty.score:.1f}" if ev else "—"
            mf = f"{ev.feasibility.score:.1f}" if ev else "—"
            title = _excerpt(idea.title, 60)
            stmt = _excerpt(idea.statement, 100)
            lines.append(
                f"| {idx} | {idea.role} | {title} | {stmt} "
                f"| [  ] | [  ] | [  ] | {mn} | {mf} |"
            )
        lines.append("")

    lines.append("---")
    lines.append(
        "Scoring guide: 0 = absent, 1 = weak, 3 = acceptable, 5 = outstanding. "
        "`MachineN` / `MachineF` are machine evaluator scores shown for "
        "reference only — do not copy them into your human columns."
    )
    lines.append("")
    return "\n".join(lines)
