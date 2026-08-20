"""Validate PaperFlow runtime, model, and prompt-manifest configuration."""

from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import ValidationError

from paperflow.config import load_config_bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        bundle = load_config_bundle(args.root)
    except (ValueError, ValidationError) as error:
        print(f"Configuration invalid: {error}")
        return 1

    print("Configuration valid")
    print(f"Runtime hash: {bundle.runtime_hash}")
    print(f"Model hash: {bundle.model_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
