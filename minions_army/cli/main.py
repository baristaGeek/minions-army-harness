"""Main command line interface for Minions Army."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from minions_army.core.config.loader import load_config


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""
    parser = argparse.ArgumentParser(prog="minions")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("show-config", "validate-config"):
        command = subparsers.add_parser(name)
        command.add_argument("--config", default=None)

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run a CLI command."""
    args = build_parser().parse_args(argv)
    config = load_config(Path(args.config) if args.config else None)
    if args.command == "show-config":
        print(json.dumps(config.model_dump(), indent=2, sort_keys=True))
        return
    if args.command == "validate-config":
        print("Config is valid.")
        return
    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":  # pragma: no cover
    main()
