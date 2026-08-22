"""Staged publication validation, atomic install, and conservative cleanup."""

from __future__ import annotations

import argparse
import posixpath
from collections.abc import Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from paperflow.atomic import atomic_write_text, install_staged_files
from paperflow.cli.sync_schedule import sync_schedule
from paperflow.config import ConfigBundle, load_config_bundle
from paperflow.generated_files import generated_cleanup_candidates, is_generated_file
from paperflow.llm.structured import PromptRenderer
from paperflow.models import (
    FigureStatus,
    FilterStatus,
    RunState,
    RunStats,
    SelectedPaper,
)
from paperflow.paper_store import load_run_state, load_selected_store
from paperflow.render.contracts import (
    DailyFeed,
    FeedIndex,
    TopicFeed,
    TopicsIndex,
    validate_topic_feed_contract,
    validate_topics_contract,
)
from paperflow.render.json_api import render_json_files
from paperflow.render.markdown import render_markdown_files
from paperflow.render.view_models import PublicProjection, build_public_projection
from paperflow.render.website import render_website_files
from paperflow.screening_ledger import ScreeningLedger
from paperflow.taxonomy import (
    TaxonomyConfig,
    load_taxonomy,
    taxonomy_hash,
    validate_assignments,
)


@dataclass(frozen=True)
class RepositoryValidationReport:
    selected_papers: int
    screening_events: int
    run_stats_files: int
    generated_files: int


def build_output_bundle(
    projection: PublicProjection,
    taxonomy: TaxonomyConfig,
    *,
    readme_latest_limit: int,
) -> dict[PurePosixPath, str]:
    markdown = render_markdown_files(
        projection, taxonomy, readme_latest_limit=readme_latest_limit
    )
    json_files = render_json_files(projection)
    website = render_website_files(projection, taxonomy)
    overlap = (set(markdown) & set(json_files)) | (
        set(markdown) & set(website)
    ) | (set(json_files) & set(website))
    if overlap:
        raise AssertionError(f"renderers produced overlapping paths: {overlap}")
    return {**markdown, **json_files, **website}


def write_output_staging(
    staging_root: Path, files: Mapping[PurePosixPath, str]
) -> None:
    for relative_path, content in files.items():
        atomic_write_text(staging_root / relative_path, content)


def validate_generated_artifacts(
    staging_root: Path,
    projection: PublicProjection,
    taxonomy: TaxonomyConfig,
    *,
    readme_latest_limit: int,
) -> None:
    """Validate exact bytes plus every JSON contract before live replacement."""
    expected = build_output_bundle(
        projection, taxonomy, readme_latest_limit=readme_latest_limit
    )
    for relative_path, expected_content in expected.items():
        path = staging_root / relative_path
        if not path.is_file():
            raise ValueError(f"generated artifact is missing: {relative_path}")
        if path.read_text(encoding="utf-8") != expected_content:
            raise ValueError(
                f"generated artifact differs from projection: {relative_path}"
            )

    index = FeedIndex.model_validate_json(
        (staging_root / "data/feed_index.json").read_text(encoding="utf-8")
    )
    topics = TopicsIndex.model_validate_json(
        (staging_root / "data/topics.json").read_text(encoding="utf-8")
    )
    validate_topics_contract(topics, taxonomy)
    for day in index.days:
        feed_path = staging_root / PurePosixPath(day.feed_url)
        feed = DailyFeed.model_validate_json(feed_path.read_text(encoding="utf-8"))
        if feed.date != day.date or feed.paper_count != day.paper_count:
            raise ValueError("feed-index day does not match referenced daily feed")
    for topic in topics.topics:
        topic_feed = TopicFeed.model_validate_json(
            (staging_root / PurePosixPath(topic.feed_url)).read_text(
                encoding="utf-8"
            )
        )
        validate_topic_feed_contract(topic_feed, taxonomy)
        if topic.paper_count != topic_feed.total_paper_count:
            raise ValueError("topic count does not match referenced topic feed")
        for subtopic in topic.subtopics:
            subtopic_feed = TopicFeed.model_validate_json(
                (staging_root / PurePosixPath(subtopic.feed_url)).read_text(
                    encoding="utf-8"
                )
            )
            validate_topic_feed_contract(subtopic_feed, taxonomy)
            if subtopic.paper_count != subtopic_feed.total_paper_count:
                raise ValueError(
                    "subtopic count does not match referenced subtopic feed"
                )
    validate_website_links(staging_root, expected)


def publish_outputs(
    destination_root: Path,
    projection: PublicProjection,
    taxonomy: TaxonomyConfig,
    *,
    readme_latest_limit: int,
) -> tuple[PurePosixPath, ...]:
    """Validate/install staged output, then remove marker-confirmed stale Markdown."""
    files = build_output_bundle(
        projection, taxonomy, readme_latest_limit=readme_latest_limit
    )
    paths = tuple(sorted(files, key=str))
    _require_safe_markdown_replacements(destination_root, paths)
    _require_safe_website_replacements(destination_root, paths)
    stale = (
        *plan_stale_markdown_cleanup(destination_root, paths),
        *plan_stale_website_cleanup(destination_root, paths),
    )
    stale_public_data = plan_stale_public_data_cleanup(destination_root, paths)
    destination_root.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        dir=destination_root.parent, prefix=".paperflow-output-"
    ) as temporary:
        staging_root = Path(temporary)
        write_output_staging(staging_root, files)
        validate_generated_artifacts(
            staging_root,
            projection,
            taxonomy,
            readme_latest_limit=readme_latest_limit,
        )
        install_staged_files(
            staging_root,
            destination_root,
            paths,
            validate_staging=lambda root: validate_generated_artifacts(
                root,
                projection,
                taxonomy,
                readme_latest_limit=readme_latest_limit,
            ),
        )
    remove_stale_generated_files(destination_root, stale)
    remove_stale_public_data_files(destination_root, stale_public_data)
    return paths


def plan_stale_markdown_cleanup(
    destination_root: Path, desired_paths: Iterable[PurePosixPath]
) -> tuple[Path, ...]:
    desired = {destination_root / path for path in desired_paths}
    candidates: list[Path] = []
    for relative_root in ("daily", "topics"):
        root = destination_root / relative_root
        if root.is_dir():
            candidates.extend(
                path for path in root.rglob("*.md") if path not in desired
            )
    return generated_cleanup_candidates(candidates)


def plan_stale_website_cleanup(
    destination_root: Path, desired_paths: Iterable[PurePosixPath]
) -> tuple[Path, ...]:
    desired = {destination_root / path for path in desired_paths}
    site_root = destination_root / "site"
    if not site_root.is_dir():
        return ()
    return generated_cleanup_candidates(
        path for path in site_root.rglob("*.html") if path not in desired
    )


def plan_stale_public_data_cleanup(
    destination_root: Path, desired_paths: Iterable[PurePosixPath]
) -> tuple[Path, ...]:
    """Find orphaned generated day/topic JSON under the public allowlist."""
    desired = {destination_root / path for path in desired_paths}
    candidates: list[Path] = []
    for relative_root in ("data/daily_feeds", "data/topic_feeds"):
        root = destination_root / relative_root
        if root.is_dir():
            candidates.extend(
                path
                for path in root.rglob("*.json")
                if path.is_file() and path not in desired
            )
    return tuple(sorted(candidates))


def remove_stale_generated_files(
    destination_root: Path, paths: Iterable[Path]
) -> None:
    root = destination_root.resolve()
    for path in paths:
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError(f"stale generated path escapes project root: {path}")
        if not is_generated_file(path):
            raise ValueError(f"refusing to remove unmarked file: {path}")
        path.unlink()


def remove_stale_public_data_files(
    destination_root: Path, paths: Iterable[Path]
) -> None:
    """Remove only orphaned JSON inside generated public-feed directories."""
    root = destination_root.resolve()
    allowed_roots = tuple(
        (root / relative).resolve()
        for relative in ("data/daily_feeds", "data/topic_feeds")
    )
    for path in paths:
        resolved = path.resolve()
        if path.suffix != ".json" or not any(
            resolved.is_relative_to(allowed) for allowed in allowed_roots
        ):
            raise ValueError(f"stale public-data path escapes allowlist: {path}")
        path.unlink()
    for allowed in allowed_roots:
        if not allowed.exists():
            continue
        for directory in sorted(
            (item for item in allowed.rglob("*") if item.is_dir()),
            key=lambda item: len(item.parts),
            reverse=True,
        ):
            with suppress(OSError):
                directory.rmdir()


def _require_safe_markdown_replacements(
    destination_root: Path, paths: Iterable[PurePosixPath]
) -> None:
    for relative_path in paths:
        if relative_path.suffix != ".md":
            continue
        destination = destination_root / relative_path
        if destination.exists() and not is_generated_file(destination):
            raise ValueError(f"refusing to overwrite manual Markdown: {relative_path}")


def _require_safe_website_replacements(
    destination_root: Path, paths: Iterable[PurePosixPath]
) -> None:
    for relative_path in paths:
        if relative_path.parts[:1] != ("site",):
            continue
        destination = destination_root / relative_path
        if not destination.exists():
            continue
        if relative_path.suffix == ".html" and not is_generated_file(destination):
            raise ValueError(f"refusing to overwrite manual HTML: {relative_path}")
        if relative_path.suffix == ".css" and not destination.read_text(
            encoding="utf-8"
        ).startswith("/* AUTO-GENERATED BY PAPERFLOW."):
            raise ValueError(f"refusing to overwrite manual CSS: {relative_path}")


def validate_website_links(
    staging_root: Path, files: Mapping[PurePosixPath, str]
) -> None:
    """Require every internal target to exist and every HTML route to be reachable."""
    html_paths = {
        path
        for path in files
        if path.parts[:1] == ("site",) and path.suffix == ".html"
    }
    graph: dict[PurePosixPath, set[PurePosixPath]] = {
        path: set() for path in html_paths
    }
    for source in html_paths:
        parser = _LinkParser()
        parser.feed((staging_root / source).read_text(encoding="utf-8"))
        for href in parser.hrefs:
            parsed = urlsplit(href)
            if parsed.scheme or parsed.netloc or href.startswith("#"):
                continue
            normalized = PurePosixPath(
                posixpath.normpath(str(source.parent / parsed.path))
            )
            if str(normalized).startswith("../"):
                raise ValueError(f"website link escapes publication root: {href}")
            target = staging_root / normalized
            if not target.is_file():
                raise ValueError(f"broken internal website link: {source} -> {href}")
            if normalized in html_paths:
                graph[source].add(normalized)

    root = PurePosixPath("site/index.html")
    reachable = {root}
    frontier = [root]
    while frontier:
        source = frontier.pop()
        for target in graph[source] - reachable:
            reachable.add(target)
            frontier.append(target)
    if reachable != html_paths:
        missing = ", ".join(str(path) for path in sorted(html_paths - reachable))
        raise ValueError(f"website routes are not reachable from site root: {missing}")

class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag not in {"a", "link"}:
            return
        for key, value in attrs:
            if key == "href" and value:
                self.hrefs.append(value)


def validate_repository(root: Path) -> RepositoryValidationReport:
    """Validate every persisted V1 domain without making network requests."""
    root = root.resolve()
    bundle = load_config_bundle(root)
    taxonomy = load_taxonomy(root / "configs/topics.yaml")
    renderer = PromptRenderer(root / "configs/prompts", bundle.prompts)
    renderer.validate_templates()
    if not renderer.render_taxonomy(taxonomy).strip():
        raise ValueError("rendered taxonomy prompt cannot be empty")
    sync_schedule(root, check=True)

    selected = load_selected_store(root / "data/papers.json", taxonomy)
    _validate_figure_assets(root, selected.papers.values())
    state = load_run_state(root / "data/state.json")
    ledger = ScreeningLedger(root / "data/screening_events")
    events = tuple(ledger.iter_events())
    latest = ledger.load_latest()
    if latest != ledger.load_latest():
        raise ValueError("screening latest-state reduction is not deterministic")
    for event in latest.values():
        if event.filter_status == FilterStatus.KEPT:
            validate_assignments(taxonomy, event.topic_assignments)

    index = FeedIndex.model_validate_json(
        (root / "data/feed_index.json").read_text(encoding="utf-8")
    )
    if index.timezone != bundle.runtime.timezone:
        raise ValueError("feed-index timezone does not match runtime config")
    projection = build_public_projection(
        selected.papers,
        taxonomy,
        generated_at=index.generated_at,
        timezone=bundle.runtime.timezone,
        base_url=str(bundle.runtime.publishing.base_url),
        successful_dates=(day.date for day in index.days),
    )
    expected = build_output_bundle(
        projection,
        taxonomy,
        readme_latest_limit=bundle.runtime.publishing.readme_latest_limit,
    )
    validate_generated_artifacts(
        root,
        projection,
        taxonomy,
        readme_latest_limit=bundle.runtime.publishing.readme_latest_limit,
    )
    stale = (
        *plan_stale_markdown_cleanup(root, expected),
        *plan_stale_website_cleanup(root, expected),
    )
    if stale:
        raise ValueError(f"stale generated artifact remains: {stale[0]}")
    stale_public_data = plan_stale_public_data_cleanup(root, expected)
    if stale_public_data:
        raise ValueError(f"stale public-data artifact remains: {stale_public_data[0]}")

    stats = _load_run_stats(root / "data/run_stats")
    if state.last_successful_local_date is not None:
        expected_stats = root / "data/run_stats" / (
            f"{state.last_successful_local_date.isoformat()}.json"
        )
        if not expected_stats.is_file():
            raise ValueError("successful run state has no matching run-stats file")
        successful_stats = RunStats.model_validate_json(
            expected_stats.read_text(encoding="utf-8")
        )
        if successful_stats.run_id != state.last_successful_run_id:
            raise ValueError("run state and run stats disagree on successful run ID")
        _validate_success_hashes(bundle, taxonomy, state)

    return RepositoryValidationReport(
        selected_papers=len(selected.papers),
        screening_events=len(events),
        run_stats_files=len(stats),
        generated_files=len(expected),
    )


def _validate_figure_assets(root: Path, papers: Iterable[SelectedPaper]) -> None:
    """Require every published ready-state figure reference to resolve locally."""
    for paper in papers:
        if paper.figure_status != FigureStatus.READY:
            continue
        referenced = [paper.hero_figure]
        referenced.extend(figure.image_path for figure in paper.figures)
        for relative_path in referenced:
            if relative_path is None:
                raise ValueError(
                    f"ready figure state has no hero image: {paper.arxiv_id}"
                )
            asset = (root / relative_path).resolve()
            if not asset.is_relative_to(root) or not asset.is_file():
                raise ValueError(
                    "ready figure asset is missing: "
                    f"{paper.arxiv_id} -> {relative_path}"
                )


def _load_run_stats(root: Path) -> tuple[RunStats, ...]:
    if not root.exists():
        return ()
    result: list[RunStats] = []
    for path in sorted(root.glob("*.json")):
        stats = RunStats.model_validate_json(path.read_text(encoding="utf-8"))
        if path.name != f"{stats.date.isoformat()}.json":
            raise ValueError(f"run-stats filename/date mismatch: {path.name}")
        result.append(stats)
    return tuple(result)


def _validate_success_hashes(
    bundle: ConfigBundle,
    taxonomy: TaxonomyConfig,
    state: RunState,
) -> None:
    if state.runtime_config_hash != bundle.runtime_hash:
        raise ValueError("successful state runtime hash is stale")
    if state.model_config_hash != bundle.model_hash:
        raise ValueError("successful state model hash is stale")
    if state.taxonomy_hash != taxonomy_hash(taxonomy):
        raise ValueError("successful state taxonomy hash is stale")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    arguments = parser.parse_args(argv)
    try:
        report = validate_repository(arguments.root)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(
        "PaperFlow repository valid: "
        f"{report.selected_papers} selected, "
        f"{report.screening_events} screening events, "
        f"{report.run_stats_files} run stats, "
        f"{report.generated_files} generated files"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
