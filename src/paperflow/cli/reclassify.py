"""Explicitly reclassify a deterministic historical paper subset."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import date
from pathlib import Path

from paperflow.main import main as pipeline_main
from paperflow.models import FilterStatus, ScreeningEvent, SelectedPaper
from paperflow.paper_store import load_selected_store
from paperflow.screening_ledger import ScreeningLedger
from paperflow.taxonomy import load_taxonomy


def select_reclassification_ids(
    selected: Mapping[str, SelectedPaper],
    latest: Mapping[str, ScreeningEvent],
    *,
    all_selected: bool,
    since: date | None,
    topic: str | None,
    screened_drops: bool,
) -> tuple[str, ...]:
    if screened_drops:
        identifiers = [
            event.arxiv_id
            for event in latest.values()
            if event.filter_status == FilterStatus.DROPPED
            and (since is None or event.observed_at.date() >= since)
        ]
    else:
        identifiers = [
            paper.arxiv_id
            for paper in selected.values()
            if (all_selected or since is not None or topic is not None)
            and (since is None or paper.first_seen_date >= since)
            and (
                topic is None
                or any(
                    assignment.topic_id == topic
                    for assignment in paper.topic_assignments
                )
            )
        ]
    return tuple(sorted(set(identifiers)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--all-selected", action="store_true")
    parser.add_argument("--since", type=date.fromisoformat)
    parser.add_argument("--topic")
    parser.add_argument("--screened-drops", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not any((args.all_selected, args.since, args.topic, args.screened_drops)):
        print("Reclassification requires an explicit historical selector.")
        return 1
    if args.screened_drops and (args.all_selected or args.topic):
        print("--screened-drops cannot be combined with selected-paper selectors.")
        return 1
    root = args.root.resolve()
    taxonomy = load_taxonomy(root / "configs/topics.yaml")
    if args.topic is not None and args.topic not in {
        topic.id for topic in taxonomy.topics
    }:
        print(f"Unknown active topic: {args.topic}")
        return 1
    selected = load_selected_store(root / "data/papers.json", taxonomy)
    latest = ScreeningLedger(root / "data/screening_events").load_latest()
    identifiers = select_reclassification_ids(
        selected.papers,
        latest,
        all_selected=args.all_selected,
        since=args.since,
        topic=args.topic,
        screened_drops=args.screened_drops,
    )
    print(f"Reclassification selection: {len(identifiers)} papers.")
    if args.dry_run or not identifiers:
        return 0
    command = ["--root", str(root), "--manual", "--maintenance-only"]
    for paper_id in identifiers:
        command.extend(["--paper", paper_id])
    return pipeline_main(command)


if __name__ == "__main__":
    raise SystemExit(main())
