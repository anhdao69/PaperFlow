"""Explicit, offline archive pruning for a disposable maintenance checkout."""

from __future__ import annotations

import argparse
import shutil
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from paperflow.config import load_config_bundle
from paperflow.models import DomainModel
from paperflow.paper_store import (
    load_run_state,
    load_selected_store,
    save_selected_store,
)
from paperflow.render.contracts import FeedIndex
from paperflow.render.validation import (
    build_output_bundle,
    publish_outputs,
    validate_generated_artifacts,
    write_output_staging,
)
from paperflow.render.view_models import build_public_projection
from paperflow.taxonomy import load_taxonomy


class ArchivePruneReport(DomainModel):
    before: date
    removed_papers: int
    retained_papers: int
    removed_days: int
    figure_files: int
    figure_bytes: int
    removed_stats: int
    applied: bool


def prune_archive(
    root: Path,
    *,
    before: date,
    apply: bool = False,
    expected_papers: int | None = None,
) -> ArchivePruneReport:
    """Remove dates strictly before the cutoff; preserve state and screening history.

    The caller must serialize against publication and validate the entire checkout
    before committing. Failures must never be pushed; this is not a live-site editor.
    """
    root = root.resolve()
    bundle = load_config_bundle(root)
    taxonomy = load_taxonomy(root / "configs/topics.yaml")
    selected = load_selected_store(root / "data/papers.json", taxonomy)
    state = load_run_state(root / "data/state.json")
    if (
        state.last_successful_local_date is None
        or before > state.last_successful_local_date
    ):
        raise ValueError("cutoff must preserve the latest successful publication")
    index = FeedIndex.model_validate_json((root / "data/feed_index.json").read_bytes())
    removed = {
        key: paper
        for key, paper in selected.papers.items()
        if paper.first_seen_date < before
    }
    retained = {
        key: paper for key, paper in selected.papers.items() if key not in removed
    }
    if expected_papers is not None and len(removed) != expected_papers:
        raise ValueError("removed-paper count differs from the reviewed cleanup plan")
    directories = tuple(
        root / "figures" / key.replace("/", "_") for key in sorted(removed)
    )
    figure_files: list[Path] = []
    for directory in directories:
        if (root / "figures").is_symlink() or directory.is_symlink():
            raise ValueError("refusing symlink in figure deletion path")
        if not directory.resolve().is_relative_to(root / "figures"):
            raise ValueError("unsafe figure deletion path")
        if directory.exists() and not directory.is_dir():
            raise ValueError("figure deletion target must be a directory")
        for path in directory.rglob("*"):
            if path.is_symlink():
                raise ValueError("refusing symlink inside old figure directory")
            if path.is_file():
                figure_files.append(path)
    removed_roots = set(directories)
    for paper in retained.values():
        for relative in [
            paper.hero_figure,
            *(figure.image_path for figure in paper.figures),
        ]:
            if relative is None:
                continue
            asset = (root / relative).resolve()
            if removed_roots.intersection(asset.parents):
                raise ValueError("retained paper references an old figure directory")
            if not asset.is_relative_to(root) or not asset.is_file():
                raise ValueError("retained figure asset is missing or unsafe")
    stats_root = root / "data/run_stats"
    if (root / "data").is_symlink() or stats_root.is_symlink():
        raise ValueError("refusing symlink in run-statistics directory")
    if not stats_root.resolve().is_relative_to(root):
        raise ValueError("unsafe run-statistics directory")
    stats = tuple(
        path
        for path in stats_root.glob("*.json")
        if date.fromisoformat(path.stem) < before
    )
    if any(path.is_symlink() for path in stats):
        raise ValueError("refusing symlink in old run statistics")
    successful_dates = {day.date for day in index.days if day.date >= before}
    successful_dates.add(state.last_successful_local_date)
    projection = build_public_projection(
        retained,
        taxonomy,
        generated_at=index.generated_at,
        timezone=bundle.runtime.timezone,
        base_url=str(bundle.runtime.publishing.base_url),
        successful_dates=successful_dates,
    )
    limit = bundle.runtime.publishing.readme_latest_limit
    files = build_output_bundle(projection, taxonomy, readme_latest_limit=limit)
    with TemporaryDirectory(prefix="paperflow-prune-validation-") as temporary:
        staging = Path(temporary)
        write_output_staging(staging, files)
        validate_generated_artifacts(
            staging, projection, taxonomy, readme_latest_limit=limit
        )
    report = ArchivePruneReport(
        before=before,
        removed_papers=len(removed),
        retained_papers=len(retained),
        removed_days=sum(day.date < before for day in index.days),
        figure_files=len(figure_files),
        figure_bytes=sum(path.stat().st_size for path in figure_files),
        removed_stats=len(stats),
        applied=apply,
    )
    if apply:
        publish_outputs(root, projection, taxonomy, readme_latest_limit=limit)
        save_selected_store(root / "data/papers.json", retained, taxonomy)
        for directory in directories:
            if directory.exists():
                shutil.rmtree(directory)
        for path in stats:
            path.unlink()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--before", type=date.fromisoformat, required=True)
    parser.add_argument("--expected-papers", type=int)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="apply the reviewed deletion; default is dry run",
    )
    args = parser.parse_args(argv)
    report = prune_archive(
        args.root,
        before=args.before,
        apply=args.apply,
        expected_papers=args.expected_papers,
    )
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
