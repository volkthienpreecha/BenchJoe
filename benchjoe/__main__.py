"""
benchjoe — CLI entry point.

Usage:
    benchjoe run <task_id> [options]
    benchjoe run --all-samples  [options]
    benchjoe report

Examples:
    benchjoe run arvo:10400 --cybergym-data ~/cybergym_data --server http://localhost:8666
    benchjoe run --all-samples --cybergym-data ~/cybergym_data --server http://localhost:8666
    benchjoe run arvo:10400 --workspace ./my_workspace   # skip gen_task, use existing dir
    benchjoe report
"""

import argparse
import json
import sys
from pathlib import Path

from benchjoe import SAMPLE_TASKS
from benchjoe.fetcher import fetch_task, workspace_ready, read_description, read_error_output
from benchjoe.prompt import build_prompt
from benchjoe.runner import run_task
from benchjoe.logger import parse_trajectory, save_trajectory
from benchjoe.validator import validate
from benchjoe.classifier import classify
from benchjoe.reporter import TaskResult, save_result, load_results, build_report


BASE_DIR = Path.cwd()
WORKSPACES_DIR = BASE_DIR / "workspaces"
RESULTS_DIR = BASE_DIR / "results"


def cmd_run(args: argparse.Namespace) -> None:
    task_ids = SAMPLE_TASKS if args.all_samples else [args.task_id]

    for task_id in task_ids:
        print(f"\n{'=' * 60}")
        print(f"  Task: {task_id}")
        print(f"{'=' * 60}")

        # --- Step 1: set up workspace ---
        if args.workspace:
            workspace = Path(args.workspace)
            print(f"  Using existing workspace: {workspace}")
        else:
            if not args.cybergym_data or not args.server:
                print("  ERROR: --cybergym-data and --server are required unless --workspace is given", file=sys.stderr)
                sys.exit(1)
            print(f"  Setting up workspace via CyberGym gen_task...")
            workspace = fetch_task(
                task_id,
                cybergym_data_dir=Path(args.cybergym_data),
                server=args.server,
                workspaces_dir=WORKSPACES_DIR,
                mask_map=args.mask_map,
            )

        if not workspace_ready(workspace):
            print(f"  ERROR: workspace at {workspace} is missing expected files", file=sys.stderr)
            continue

        # --- Step 2: build prompt ---
        description = read_description(workspace)
        error_output = read_error_output(workspace)
        prompt = build_prompt(description, error_output)

        print(f"  Prompt built ({len(prompt)} chars)")
        print(f"  Running Claude Code — no Docker, no proxy, full internet...")

        # --- Step 3: run Claude Code ---
        events, duration = run_task(
            prompt,
            workspace,
            model=args.model,
            timeout=args.timeout,
        )
        print(f"  Session complete ({duration}s, {len(events)} events)")

        # --- Step 4: parse trajectory ---
        trajectory = parse_trajectory(events)
        traj_path = RESULTS_DIR / task_id.replace(":", "_") / "trajectory.jsonl"
        save_trajectory(trajectory, traj_path)
        print(f"  Trajectory saved: {len(trajectory)} events → {traj_path}")

        # --- Step 5: validate PoC ---
        print(f"  Validating PoC...")
        validation = validate(workspace, timeout=60)
        print(f"  Validation: {'✅ SUCCESS' if validation.success else '❌ FAILED'}")
        if validation.error:
            print(f"    Error: {validation.error}")

        # --- Step 6: classify ---
        classification = classify(trajectory, validation)
        print(f"  Classification: {classification.label} ({classification.confidence})")
        print(f"    {classification.reason}")

        # --- Step 7: save result ---
        result = TaskResult(
            task_id=task_id,
            benchjoe_success=validation.success,
            classification_label=classification.label,
            classification_reason=classification.reason,
            duration_seconds=duration,
            web_fetch_count=classification.web_fetch_count,
            external_fetch_count=classification.external_fetch_count,
        )
        save_result(result, RESULTS_DIR)
        print(f"  Result saved.")


def cmd_report(args: argparse.Namespace) -> None:
    results = load_results(RESULTS_DIR)
    if not results:
        print("No results found. Run some tasks first with: benchjoe run --all-samples ...")
        return

    report_path = RESULTS_DIR / "comparison.md"
    md = build_report(results, report_path)
    print(md)
    print(f"\nReport saved to {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="benchjoe",
        description="CyberGym tasks run like an average Claude Code user — no isolation, no proxy",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- run command ---
    run_parser = subparsers.add_parser("run", help="Run one or more tasks")
    run_parser.add_argument("task_id", nargs="?", help="CyberGym task ID, e.g. arvo:10400")
    run_parser.add_argument("--all-samples", action="store_true", help="Run all 10 sample tasks")
    run_parser.add_argument("--workspace", help="Path to existing task workspace (skips gen_task)")
    run_parser.add_argument("--cybergym-data", help="Path to cybergym_data directory")
    run_parser.add_argument("--server", default="http://localhost:8666", help="CyberGym server URL")
    run_parser.add_argument("--mask-map", default=None, help="Path to mask_map.json")
    run_parser.add_argument("--model", default="claude-opus-4-7", help="Claude model to use")
    run_parser.add_argument("--timeout", type=int, default=600, help="Per-task timeout in seconds")

    # --- report command ---
    report_parser = subparsers.add_parser("report", help="Generate comparison report from saved results")

    args = parser.parse_args()

    if args.command == "run":
        if not args.all_samples and not args.task_id:
            run_parser.error("Provide a task_id or use --all-samples")
        cmd_run(args)
    elif args.command == "report":
        cmd_report(args)


if __name__ == "__main__":
    main()
