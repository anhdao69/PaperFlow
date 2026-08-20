"""Rebuild public outputs deterministically from canonical local data only."""

from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
from pathlib import Path

from paperflow.config import load_config_bundle
from paperflow.models import RunState, SelectedPaperCollection
from paperflow.paper_store import load_run_state, load_selected_store
from paperflow.render.contracts import FeedIndex
from paperflow.render.validation import publish_outputs
from paperflow.render.view_models import build_public_projection
from paperflow.taxonomy import load_taxonomy

_EMPTY_GENERATED_AT = datetime(2000, 1, 1, tzinfo=UTC)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--generated-at", type=_aware_datetime)
    parser.add_argument(
        "--successful-date",
        action="append",
        type=date.fromisoformat,
        default=[],
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    bundle = load_config_bundle(root)
    taxonomy = load_taxonomy(root / "configs/topics.yaml")
    selected = load_selected_store(root / "data/papers.json", taxonomy)
    state = load_run_state(root / "data/state.json")
    generated_at = args.generated_at or _deterministic_generated_at(selected, state)
    successful_dates = set(args.successful_date)
    successful_dates.update(_existing_successful_dates(root))
    if state.last_successful_local_date is not None:
        successful_dates.add(state.last_successful_local_date)
    projection = build_public_projection(
        selected.papers,
        taxonomy,
        generated_at=generated_at,
        timezone=bundle.runtime.timezone,
        base_url=str(bundle.runtime.publishing.base_url),
        successful_dates=successful_dates,
    )
    paths = publish_outputs(
        root,
        projection,
        taxonomy,
        readme_latest_limit=bundle.runtime.publishing.readme_latest_limit,
    )
    print(f"Rebuilt {len(paths)} deterministic PaperFlow outputs.")
    return 0


def _deterministic_generated_at(
    selected: SelectedPaperCollection, state: RunState
) -> datetime:
    if state.last_successful_at is not None:
        return state.last_successful_at
    if selected.papers:
        return max(paper.first_seen_at for paper in selected.papers.values())
    return _EMPTY_GENERATED_AT


def _existing_successful_dates(root: Path) -> set[date]:
    path = root / "data/feed_index.json"
    if not path.exists():
        return set()
    index = FeedIndex.model_validate_json(path.read_text(encoding="utf-8"))
    return {day.date for day in index.days}


def _aware_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("generated-at must include a timezone offset")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
