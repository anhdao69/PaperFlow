"""Validate and explain an explicit manual paper reprocess override."""

from __future__ import annotations

import argparse
from pathlib import Path

from paperflow.main import main as pipeline_main
from paperflow.models import validate_canonical_arxiv_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--paper", required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report the override without running the later filtering pipeline",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        paper_id = validate_canonical_arxiv_id(args.paper)
    except ValueError as error:
        print(f"Reprocess request invalid: {error}")
        return 1

    if not args.dry_run:
        return pipeline_main(
            [
                "--root",
                str(args.root),
                "--manual",
                "--maintenance-only",
                "--paper",
                paper_id,
            ]
        )
    print(f"Manual dry-run reprocess override accepted for {paper_id}")
    print("Automatic retry exhaustion and cooldown will be bypassed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
