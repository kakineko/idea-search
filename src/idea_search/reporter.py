"""Final report builder: cluster ideas, pick top-K per cluster, render."""
from __future__ import annotations

from typing import List, Tuple, Dict, Any

from idea_search.clustering import cluster_ideas, label_cluster
from idea_search.schema import Idea, Evaluation, Cluster, FinalReport


def build_report(
    problem: str,
    rounds: int,
    evaluated: List[Tuple[Idea, Evaluation]],
    cliche_reasons: List[str],
    config: Dict[str, Any],
) -> FinalReport:
    ideas = [p[0] for p in evaluated]
    ev_map: Dict[str, Evaluation] = {i.id: e for i, e in evaluated}

    non_cliche = [i for i in ideas if not i.cliche_flag] or ideas
    threshold = config.get("clustering", {}).get("jaccard_cluster_threshold", 0.40)
    groups = cluster_ideas(non_cliche, threshold=threshold)

    # sort clusters by their best composite score
    def cluster_best(member_ids: List[str]) -> float:
        return max(
            (ev_map[mid].composite() for mid in member_ids if mid in ev_map),
            default=0.0,
        )

    groups.sort(key=cluster_best, reverse=True)
    max_clusters = config.get("report", {}).get("max_clusters", 5)
    per_cluster_top_k = config.get("report", {}).get("per_cluster_top_k", 2)
    groups = groups[:max_clusters]

    clusters: List[Cluster] = []
    top_per_cluster: List[Dict[str, Any]] = []

    for group in groups:
        label = label_cluster(ideas, group)
        clusters.append(Cluster(label=label, member_ids=group))

        ranked = sorted(
            (ev_map[mid] for mid in group if mid in ev_map),
            key=lambda e: e.composite(),
            reverse=True,
        )[:per_cluster_top_k]

        idea_lookup = {i.id: i for i in ideas}
        for ev in ranked:
            idea = idea_lookup[ev.idea_id]
            top_per_cluster.append({
                "cluster_label": label,
                "idea": idea.model_dump(),
                "evaluation": ev.model_dump(),
                "composite_score": round(ev.composite(), 2),
            })

    summary = (
        f"Generated {len(ideas)} ideas across {rounds} rounds, "
        f"{len(ideas) - len(non_cliche)} flagged as cliché, "
        f"clustered into {len(clusters)} directions."
    )

    return FinalReport(
        problem=problem,
        rounds=rounds,
        total_ideas=len(ideas),
        clusters=clusters,
        top_per_cluster=top_per_cluster,
        cliche_patterns_detected=cliche_reasons,
        summary=summary,
    )


def render_console(report: FinalReport) -> str:
    lines: List[str] = []
    lines.append("=" * 72)
    lines.append("IDEA SEARCH — FINAL REPORT")
    lines.append("=" * 72)
    lines.append(f"Problem: {report.problem}")
    lines.append(f"Rounds : {report.rounds}")
    lines.append(f"Summary: {report.summary}")
    lines.append("")
    lines.append(f"Clusters ({len(report.clusters)}):")
    for c in report.clusters:
        lines.append(f"  - [{c.label}] ({len(c.member_ids)} ideas)")
    lines.append("")
    lines.append("TOP IDEAS PER CLUSTER")
    lines.append("-" * 72)
    for entry in report.top_per_cluster:
        idea = entry["idea"]
        ev = entry["evaluation"]
        lines.append(f"[{entry['cluster_label']}] {idea['title']}")
        lines.append(f"  composite={entry['composite_score']}  "
                     f"N={ev['novelty']['score']}  "
                     f"F={ev['feasibility']['score']}  "
                     f"V={ev['value']['score']}  "
                     f"R={ev['risk']['score']}")
        lines.append(f"  statement: {idea['statement']}")
        lines.append(f"  rationale: {idea['rationale']}")
        lines.append("  Judge comments:")
        for axis in ("novelty", "feasibility", "value", "risk"):
            ax = ev[axis]
            lines.append(
                f"    - {axis}: {ax['rationale']} -> suggestion: {ax['suggestion']}"
            )
        if idea.get("cliche_flag"):
            lines.append(f"  [CLICHE] {idea.get('cliche_reason')}")
        lines.append("")
    if report.cliche_patterns_detected:
        lines.append("Cliché patterns / reasons detected:")
        for r in report.cliche_patterns_detected:
            lines.append(f"  - {r}")
    return "\n".join(lines)
