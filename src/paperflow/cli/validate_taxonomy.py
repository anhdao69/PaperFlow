"""Validate the PaperFlow taxonomy and print its deterministic identity."""

from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import ValidationError

from paperflow.taxonomy import load_taxonomy, taxonomy_hash


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path", nargs="?", type=Path, default=Path("configs/topics.yaml")
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        taxonomy = load_taxonomy(args.path)
    except (ValueError, ValidationError) as error:
        print(f"Taxonomy invalid: {error}")
        return 1

    topic_count = len(taxonomy.topics)
    subtopic_count = sum(len(topic.subtopics) for topic in taxonomy.topics)
    print(
        f"Taxonomy valid: version {taxonomy.taxonomy_version}, "
        f"{topic_count} topics, {subtopic_count} subtopics"
    )
    print(f"Taxonomy hash: {taxonomy_hash(taxonomy)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
