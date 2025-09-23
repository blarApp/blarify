"""Main CLI entry point for Blarify."""

import argparse
import sys
from typing import List, Optional

from blarify.cli.commands import create


def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for the Blarify CLI.

    Args:
        args: Optional list of arguments (for testing). If None, uses sys.argv.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(
        prog="blarify", description="Blarify - Transform your codebase into a graph structure for analysis"
    )

    # Add version flag
    parser.add_argument("--version", action="version", version="%(prog)s 1.3.0")

    # Add debug flag
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    # Create subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add create command
    create_parser = subparsers.add_parser("create", help="Build a graph from the current directory repository")
    create.add_arguments(create_parser)

    # Parse arguments
    parsed_args = parser.parse_args(args)

    # Configure logging based on debug flag
    if getattr(parsed_args, "debug", False):
        import logging

        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        print("Debug mode enabled")

    # Execute command
    if parsed_args.command == "create":
        return create.execute(parsed_args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
