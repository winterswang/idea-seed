"""Main entry point for Idea Seed."""

import argparse
import os
import sys

from agent.orchestrator import Orchestrator


def main() -> None:
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

    args = parser.parse_args()

    if args.interactive:
        seed = input("Enter seed idea: ").strip()
        if not seed:
            print("Error: Seed idea cannot be empty")
            sys.exit(1)
    elif args.seed:
        seed = args.seed
    else:
        parser.print_help()
        sys.exit(1)

    # Override provider if specified
    if args.provider:
        os.environ["PROVIDER"] = args.provider

    print(f"\nStarting Idea Seed with seed: {seed}\n")
    if args.provider:
        print(f"Using provider: {args.provider}")
    if args.max_rounds:
        print(f"Max rounds: {args.max_rounds}")
    print("\nPress Ctrl+C to interrupt...\n")

    orchestrator = Orchestrator(
        seed=seed, resume=args.resume, max_rounds=args.max_rounds
    )
    orchestrator.run()


if __name__ == "__main__":
    main()
