"""Main entry point for Idea Seed."""

import argparse
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

    print(f"\nStarting Idea Seed with seed: {seed}\n")
    print("Press Ctrl+C to interrupt...\n")

    orchestrator = Orchestrator(seed=seed, resume=args.resume)
    orchestrator.run()


if __name__ == "__main__":
    main()
