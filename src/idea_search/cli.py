"""CLI entrypoint for idea-search."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

import yaml

import uuid

from idea_search.compare import CompareRunner
from idea_search.compare_report import render_comparison
from idea_search.controller import Controller
from idea_search.hierarchical.controller import HierarchicalController
from idea_search.hierarchical.reporter import (
    render_goal_search,
    render_hierarchical,
)
from idea_search.hierarchical.schema import Goal
from idea_search.modes import Mode
from idea_search.providers import get_provider
from idea_search.reporter import build_report, render_console
from idea_search.schema import ProblemInput


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "default.yaml"


def load_config(path: Path | None) -> Dict[str, Any]:
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_problem(path: Path) -> ProblemInput:
    with Path(path).open("r", encoding="utf-8") as f:
        data = json.load(f)
    return ProblemInput(**data)


def _cmd_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.rounds is not None:
        config["rounds"] = args.rounds
    if args.provider:
        config["provider"] = args.provider

    problem = load_problem(args.input)
    provider = get_provider(config.get("provider", "mock"))
    controller = Controller(provider, config)

    result = controller.run(problem)
    report = build_report(
        problem=problem.problem,
        rounds=result["rounds"],
        evaluated=result["evaluated"],
        cliche_reasons=result["cliche_reasons"],
        config=config,
    )

    if args.json:
        print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))
    else:
        print(render_console(report))

    if args.out:
        Path(args.out).write_text(
            json.dumps(report.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return 0


_DEFAULT_COMPARE_MODES = (
    "baseline-single,baseline-self-critique,generator-only,gen-eval,full"
)


def _cmd_compare(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.rounds is not None:
        config["rounds"] = args.rounds
    if args.provider:
        config["provider"] = args.provider

    problem = load_problem(args.input)
    provider = get_provider(config.get("provider", "mock"))

    modes = Mode.parse_list(args.modes or _DEFAULT_COMPARE_MODES)

    runner = CompareRunner(provider, config)
    results = runner.run(problem, modes, baseline_n=args.baseline_n)

    md = render_comparison(problem.problem, results)
    print(md)

    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
    return 0


def _load_goal(path: Path) -> Goal:
    with Path(path).open("r", encoding="utf-8") as f:
        data = json.load(f)
    return Goal(
        goal_id=data.get("goal_id", uuid.uuid4().hex[:10]),
        goal_statement=data["goal_statement"],
        constraints=data.get("constraints", []),
        domain_context=data.get("domain_context", []),
    )


def _cmd_goal_search(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.provider:
        config["provider"] = args.provider

    goal = _load_goal(args.input)
    provider = get_provider(config.get("provider", "mock"))
    ctrl = HierarchicalController(provider, config)
    result = ctrl.run_goal_search(goal, n_branches=args.branches)

    print(render_goal_search(result))
    return 0


def _cmd_hierarchical_full(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.rounds is not None:
        config["rounds"] = args.rounds
    if args.provider:
        config["provider"] = args.provider

    goal = _load_goal(args.input)
    provider = get_provider(config.get("provider", "mock"))
    ctrl = HierarchicalController(provider, config)
    result = ctrl.run_hierarchical(
        goal,
        n_branches=args.branches,
        top_k=args.top_k,
    )

    print(render_hierarchical(result))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="idea-search")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run an idea search session")
    run.add_argument("--input", "-i", type=Path, required=True,
                     help="Path to problem input JSON")
    run.add_argument("--config", "-c", type=Path, default=None,
                     help="Path to config YAML (defaults to built-in)")
    run.add_argument("--rounds", type=int, default=None,
                     help="Override rounds from config")
    run.add_argument("--provider", choices=["mock", "openai", "anthropic"],
                     default=None, help="Override provider")
    run.add_argument("--json", action="store_true",
                     help="Emit full report as JSON to stdout")
    run.add_argument("--out", type=Path, default=None,
                     help="Write JSON report to this path")
    run.set_defaults(func=_cmd_run)

    cmp = sub.add_parser(
        "compare", help="Compare pipeline variants on the same problem",
    )
    cmp.add_argument("--input", "-i", type=Path, required=True,
                     help="Path to problem input JSON")
    cmp.add_argument("--config", "-c", type=Path, default=None,
                     help="Path to config YAML (defaults to built-in)")
    cmp.add_argument("--modes", type=str, default=None,
                     help=("Comma-separated list of modes to run. "
                           f"Default: {_DEFAULT_COMPARE_MODES}"))
    cmp.add_argument("--rounds", type=int, default=None,
                     help="Override rounds (applies to non-baseline modes)")
    cmp.add_argument("--provider", choices=["mock", "openai", "anthropic"],
                     default=None, help="Override provider")
    cmp.add_argument("--baseline-n", type=int, default=3,
                     help="Number of ideas per baseline mode")
    cmp.add_argument("--out", type=Path, default=None,
                     help="Write markdown comparison report to this path")
    cmp.set_defaults(func=_cmd_compare)

    # -- Hierarchical commands -------------------------------------------
    gs = sub.add_parser(
        "goal-search",
        help="Decompose a broad goal into branches and evaluate them",
    )
    gs.add_argument("--input", "-i", type=Path, required=True,
                    help="Path to goal input JSON")
    gs.add_argument("--config", "-c", type=Path, default=None)
    gs.add_argument("--provider", choices=["mock", "openai", "anthropic"],
                    default=None)
    gs.add_argument("--branches", type=int, default=5,
                    help="Number of branches to generate")
    gs.set_defaults(func=_cmd_goal_search)

    hf = sub.add_parser(
        "hierarchical-full",
        help="Goal → Branch → Method search end-to-end",
    )
    hf.add_argument("--input", "-i", type=Path, required=True,
                    help="Path to goal input JSON")
    hf.add_argument("--config", "-c", type=Path, default=None)
    hf.add_argument("--rounds", type=int, default=None,
                    help="Override rounds for the method-search stage")
    hf.add_argument("--provider", choices=["mock", "openai", "anthropic"],
                    default=None)
    hf.add_argument("--branches", type=int, default=5,
                    help="Number of branches to generate")
    hf.add_argument("--top-k", type=int, default=1,
                    help="Number of top branches to explore with method search")
    hf.set_defaults(func=_cmd_hierarchical_full)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
