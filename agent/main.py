"""Main entry point for Idea Seed."""

import argparse
import logging
import os
import sys
from pathlib import Path

from agent.orchestrator import Orchestrator
from agent.plan_manager import PlanManager
from agent.plan import PlanStage, PlanStatus


def setup_logging() -> None:
    """Configure logging for idea-seed."""
    # Get the idea-seed logger
    logger = logging.getLogger("idea-seed")
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers
    if logger.handlers:
        return

    # Console handler - INFO level
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(name)s - %(message)s"))
    logger.addHandler(console)


def run_seed_mode_args() -> None:
    """Handle seed mode when first arg is the seed text itself."""

    parser = argparse.ArgumentParser(description="Idea Seed")
    parser.add_argument("seed", help="Seed idea")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--interactive", "-i", action="store_true")
    parser.add_argument("--provider", choices=["minimax", "aliyun", "bytedance"])
    parser.add_argument("--max-rounds", type=int)
    parser.add_argument("--mode", choices=["legacy", "plan"], default="legacy")

    args, _ = parser.parse_known_args()

    seed = args.seed
    if args.interactive:
        seed = input("Enter seed idea: ").strip()
        if not seed:
            print("Error: Seed idea cannot be empty")
            sys.exit(1)
    elif not args.resume and not seed:
        print("Error: Seed idea cannot be empty")
        sys.exit(1)

    setup_logging()
    if args.provider:
        os.environ["PROVIDER"] = args.provider

    print(f"\nStarting Idea Seed with seed: {seed}")
    if args.provider:
        print(f"Using provider: {args.provider}")
    if args.max_rounds:
        print(f"Max rounds: {args.max_rounds}")
    print(f"Mode: {args.mode}")
    print("\nPress Ctrl+C to interrupt...\n")

    orchestrator = Orchestrator(
        seed=seed,
        resume=args.resume,
        max_rounds=args.max_rounds,
        mode=args.mode,
    )
    orchestrator.run()


def main() -> None:
    # Pre-check: if first arg looks like seed text (not a subcommand), run seed mode
    import sys
    subcommands = {"review", "plans", "append"}
    if len(sys.argv) >= 2 and sys.argv[1] not in subcommands and not sys.argv[1].startswith("-"):
        run_seed_mode_args()
        return

    setup_logging()
    _logger = logging.getLogger("idea-seed")

    parser = argparse.ArgumentParser(
        description="Idea Seed - Iterative document building system"
    )
    parser.add_argument(
        "seed",
        nargs="?",
        help="Seed idea to develop",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from saved state",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Interactive mode",
    )
    parser.add_argument(
        "--provider",
        choices=["minimax", "aliyun", "bytedance"],
        default=None,
        help="API provider to use (overrides .env setting)",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=None,
        help="Maximum number of iteration rounds (default: 10)",
    )
    parser.add_argument(
        "--mode",
        choices=["legacy", "plan"],
        default="legacy",
        help="Execution mode: 'legacy' or 'plan'",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # review command
    review_parser = subparsers.add_parser("review", help="View or update plan status")
    review_parser.add_argument("plan_id", help="Plan ID")
    review_parser.add_argument("--stage", choices=["dev", "test", "release", "blocked"])
    review_parser.add_argument("--status", choices=["pending", "in_progress", "done", "blocked"])

    # plans command
    plans_parser = subparsers.add_parser("plans", help="List plans")
    plans_parser.add_argument("project", nargs="?", help="Project slug")

    # append command
    append_parser = subparsers.add_parser("append", help="Append new feature")
    append_parser.add_argument("idea", help="New feature idea")
    append_parser.add_argument("--project", "-p", required=True)

    args = parser.parse_args()

    # Handle subcommands
    if args.command == "review":
        handle_review(args)
        return
    elif args.command == "plans":
        handle_plans(args)
        return
    elif args.command == "append":
        handle_append(args)
        return

    # Resume or interactive mode
    seed = args.seed

    if args.interactive:
        seed = input("Enter seed idea: ").strip()
        if not seed:
            print("Error: Seed idea cannot be empty")
            sys.exit(1)
    elif not args.resume and not seed:
        parser.print_help()
        sys.exit(1)

    if args.provider:
        os.environ["PROVIDER"] = args.provider

    print(f"\nStarting Idea Seed with seed: {seed}\n")
    if args.provider:
        print(f"Using provider: {args.provider}")
    if args.max_rounds:
        print(f"Max rounds: {args.max_rounds}")
    print(f"Mode: {args.mode}")
    print("\nPress Ctrl+C to interrupt...\n")

    orchestrator = Orchestrator(
        seed=seed,
        resume=args.resume,
        max_rounds=args.max_rounds,
        mode=args.mode,
    )
    orchestrator.run()


if __name__ == "__main__":
    main()


# ============================================================================
# Command Handlers
# ============================================================================

def handle_review(args) -> None:
    """Handle 'review' command - view/update plan status."""
    from agent.config import WORKDIR

    project_slug = input("Project slug: ").strip() if not getattr(args, 'project', None) else args.project
    if not project_slug:
        print("Error: Project slug required")
        return

    project_dir = WORKDIR / "projects" / project_slug
    if not project_dir.exists():
        print(f"Error: Project '{project_slug}' not found")
        return

    state_dir = project_dir / ".state"
    pm = PlanManager(state_dir)

    try:
        plans = pm.load_plans()
    except FileNotFoundError:
        print(f"Error: No plans.json found for project '{project_slug}'")
        print("This project may not be using v2 plan management yet.")
        return

    plan = pm.get_plan(args.plan_id, plans)
    if not plan:
        print(f"Error: Plan '{args.plan_id}' not found in project '{project_slug}'")
        print("Available plans:")
        for p in plans:
            print(f"  - {p.plan_id}: {p.feature}")
        return

    # Display current status
    print(f"\n{'='*60}")
    print(f"Plan: {plan.plan_id}")
    print(f"Feature: {plan.feature}")
    print(f"Priority: {plan.priority.value}")
    print(f"Stage: {plan.stage.value}")
    print(f"Status: {plan.status.value}")
    print(f"Depends on: {plan.depends_on or 'none'}")
    print(f"Blocks: {plan.blocks or 'none'}")
    print(f"Summary: {plan.summary or '(none)'}")
    print(f"{'='*60}\n")

    if args.stage:
        try:
            new_stage = PlanStage(args.stage)
            pm.update_plan_stage(args.plan_id, new_stage)
            print(f"Updated stage to: {args.stage}")
        except ValueError:
            print(f"Error: Invalid stage '{args.stage}'")

    if args.status:
        try:
            new_status = PlanStatus(args.status)
            pm.update_plan_status(args.plan_id, new_status)
            print(f"Updated status to: {args.status}")
        except ValueError:
            print(f"Error: Invalid status '{args.status}'")


def handle_plans(args) -> None:
    """Handle 'plans' command - list plans for a project."""
    from agent.config import WORKDIR

    project_slug = args.project
    if not project_slug:
        project_slug = input("Project slug: ").strip()

    if not project_slug:
        # List all projects with plans
        projects_dir = WORKDIR / "projects"
        if not projects_dir.exists():
            print("No projects found")
            return

        print("\nProjects with plans:")
        for proj in projects_dir.iterdir():
            plans_file = proj / ".state" / "plans.json"
            if plans_file.exists():
                pm = PlanManager(proj / ".state")
                plans = pm.load_plans()
                print(f"  {proj.name}: {len(plans)} plans")
        return

    project_dir = WORKDIR / "projects" / project_slug
    if not project_dir.exists():
        print(f"Error: Project '{project_slug}' not found")
        return

    state_dir = project_dir / ".state"
    pm = PlanManager(state_dir)

    try:
        plans = pm.load_plans()
    except FileNotFoundError:
        print(f"No plans found for project '{project_slug}'")
        return

    if not plans:
        print(f"No plans in project '{project_slug}'")
        return

    # Table header
    print(f"\nPlans for '{project_slug}':")
    print(f"{'Plan ID':<12} {'Feature':<30} {'Priority':<8} {'Stage':<10} {'Status':<12}")
    print("-" * 80)

    for plan in plans:
        feature = plan.feature[:28] + ".." if len(plan.feature) > 30 else plan.feature
        print(f"{plan.plan_id:<12} {feature:<30} {plan.priority.value:<8} {plan.stage.value:<10} {plan.status.value:<12}")

    print()


def handle_append(args) -> None:
    """Handle 'append' command - append new feature to existing project."""
    from agent.config import WORKDIR

    project_slug = args.project if hasattr(args, 'project') and args.project else input("Project slug: ").strip()
    idea = args.idea if hasattr(args, 'idea') and args.idea else input("New feature idea: ").strip()

    if not project_slug or not idea:
        print("Error: Both project slug and idea are required")
        return

    project_dir = WORKDIR / "projects" / project_slug
    if not project_dir.exists():
        print(f"Error: Project '{project_slug}' not found")
        return

    state_dir = project_dir / ".state"
    pm = PlanManager(state_dir)

    try:
        plans = pm.load_plans()
    except FileNotFoundError:
        print(f"Error: Project '{project_slug}' doesn't have plans.json")
        print("This project may not be using v2 plan management yet.")
        return

    # Analyze how to append
    strategy, affected = pm.resolve_append(idea, plans)

    print(f"\nAnalyzing append for: {idea}")
    print(f"Strategy: {strategy}")
    if affected:
        print(f"Affected plans: {affected}")

    if strategy == "new":
        print("→ Will create new plan")
    elif strategy == "depends_on":
        print(f"→ Will create new plan depending on: {affected}")
    elif strategy == "supersedes":
        print(f"→ Will mark plan {affected} as superseded and create new plan")

    # Create new plan
    from agent.plan import Plan, Priority
    new_plan = Plan.create(idea, Priority.P1)
    if strategy == "depends_on":
        new_plan.depends_on.extend(affected)

    pm.add_plan(new_plan, plans)
    print(f"\nCreated: {new_plan.plan_id} - {new_plan.feature}")
    print(f"Depends on: {new_plan.depends_on or 'none'}")
