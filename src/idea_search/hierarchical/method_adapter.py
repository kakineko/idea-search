"""Adapter: convert a selected Branch into a ProblemInput for the existing
method-search engine, preserving rich hierarchical context.
"""
from __future__ import annotations

from idea_search.hierarchical.schema import Branch, Goal, MethodSearchInput
from idea_search.schema import ProblemInput


def build_method_search_input(
    branch: Branch,
    goal: Goal,
    selection_reason: str,
) -> MethodSearchInput:
    return MethodSearchInput(
        selected_branch=branch,
        inherited_goal=goal,
        inherited_constraints=list(goal.constraints),
        inherited_context=list(goal.domain_context),
        selection_reason=selection_reason,
    )


def to_problem_input(msi: MethodSearchInput) -> ProblemInput:
    """Flatten MethodSearchInput into the existing ProblemInput schema,
    embedding branch context so the method-search engine operates with
    full awareness of the branch it's exploring.
    """
    branch = msi.selected_branch

    problem = (
        f"Within the strategy branch '{branch.branch_name}': "
        f"{branch.branch_description}\n\n"
        f"Broader goal: {msi.inherited_goal.goal_statement}\n\n"
        f"Branch assumptions:\n"
        + "\n".join(f"- {a}" for a in branch.assumptions)
        + "\n\n"
        f"Selection reason: {msi.selection_reason}"
    )

    constraints = list(msi.inherited_constraints)
    if branch.required_capital != "unknown":
        constraints.append(f"Required capital: {branch.required_capital}")
    if branch.required_skill != "unknown":
        constraints.append(f"Required skill: {branch.required_skill}")
    if branch.risk_level != "unknown":
        constraints.append(f"Risk tolerance: {branch.risk_level}")

    context_parts = list(msi.inherited_context)
    if branch.validation_speed != "unknown":
        context_parts.append(f"Target validation speed: {branch.validation_speed}")
    if branch.personal_fit != "unknown":
        context_parts.append(f"Personal fit level: {branch.personal_fit}")
    if branch.data_availability != "unknown":
        context_parts.append(f"Data availability: {branch.data_availability}")

    context = "; ".join(context_parts) if context_parts else None

    return ProblemInput(
        problem=problem,
        constraints=constraints,
        context=context,
    )
