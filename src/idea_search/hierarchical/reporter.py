"""Hierarchical report renderer."""
from __future__ import annotations

from typing import List

from idea_search.hierarchical.controller import (
    GoalSearchResult,
    HierarchicalResult,
)
from idea_search.hierarchical.schema import Branch, BranchEvaluation
from idea_search.reporter import render_console as render_method_report


def _branch_table(
    evaluated: list[tuple[Branch, BranchEvaluation]],
    selected_ids: set[str],
) -> List[str]:
    lines: List[str] = []
    lines.append(
        "| # | Branch | Upside | Cost | Risk | Speed | Fit | Data | Composite | Selected |"
    )
    lines.append(
        "|--:|--------|-------:|-----:|-----:|------:|----:|-----:|----------:|:--------:|"
    )
    ranked = sorted(
        evaluated,
        key=lambda p: p[1].composite(),
        reverse=True,
    )
    for i, (b, ev) in enumerate(ranked, start=1):
        sel = "**YES**" if b.branch_id in selected_ids else ""
        lines.append(
            f"| {i} | {b.branch_name[:50]} "
            f"| {ev.upside.score:.1f} "
            f"| {ev.cost.score:.1f} "
            f"| {ev.risk.score:.1f} "
            f"| {ev.validation_speed.score:.1f} "
            f"| {ev.personal_fit.score:.1f} "
            f"| {ev.data_availability.score:.1f} "
            f"| {ev.composite():.2f} "
            f"| {sel} |"
        )
    return lines


def render_goal_search(result: GoalSearchResult) -> str:
    lines: List[str] = []
    lines.append("=" * 72)
    lines.append("GOAL SEARCH REPORT")
    lines.append("=" * 72)
    lines.append(f"Goal: {result.goal.goal_statement}")
    lines.append(f"Constraints: {', '.join(result.goal.constraints) or 'none'}")
    lines.append(f"Context: {', '.join(result.goal.domain_context) or 'none'}")
    lines.append(f"Branches generated: {len(result.branches)}")
    lines.append("")

    selected_ids = {b.branch_id for b, _, _ in result.selected}
    lines.extend(_branch_table(result.evaluations, selected_ids))
    lines.append("")

    for b, ev, reason in result.selected:
        lines.append(f"### Selected: {b.branch_name}")
        lines.append(f"  Reason: {reason}")
        lines.append(f"  Description: {b.branch_description}")
        lines.append(f"  Assumptions: {', '.join(b.assumptions)}")
        lines.append("  Judge details:")
        for axis_name in ("upside", "cost", "risk", "validation_speed", "personal_fit", "data_availability"):
            ax = getattr(ev, axis_name)
            lines.append(
                f"    - {axis_name}: {ax.score:.1f} — {ax.rationale} "
                f"→ {ax.suggestion}"
            )
        lines.append("")

    return "\n".join(lines)


def render_hierarchical(result: HierarchicalResult) -> str:
    parts: List[str] = []
    parts.append(render_goal_search(result.goal_search))

    for msi, report in result.method_results:
        branch = msi.selected_branch
        parts.append("")
        parts.append("=" * 72)
        parts.append(
            f"METHOD SEARCH — Branch: {branch.branch_name}"
        )
        parts.append("=" * 72)
        parts.append(f"Selection: {msi.selection_reason}")
        parts.append("")
        parts.append(render_method_report(report))
        parts.append("")

    return "\n".join(parts)
