"""Staged publication validation, atomic install, and conservative cleanup."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from paperflow.atomic import atomic_write_text, install_staged_files
from paperflow.generated_files import generated_cleanup_candidates, is_generated_file
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
from paperflow.render.view_models import PublicProjection
from paperflow.taxonomy import TaxonomyConfig


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
    overlap = set(markdown) & set(json_files)
    if overlap:
        raise AssertionError(f"renderers produced overlapping paths: {overlap}")
    return {**markdown, **json_files}


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
    stale = plan_stale_markdown_cleanup(destination_root, paths)
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


def _require_safe_markdown_replacements(
    destination_root: Path, paths: Iterable[PurePosixPath]
) -> None:
    for relative_path in paths:
        if relative_path.suffix != ".md":
            continue
        destination = destination_root / relative_path
        if destination.exists() and not is_generated_file(destination):
            raise ValueError(f"refusing to overwrite manual Markdown: {relative_path}")
