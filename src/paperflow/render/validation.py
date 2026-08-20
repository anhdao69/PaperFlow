"""Staged publication validation, atomic install, and conservative cleanup."""

from __future__ import annotations

import posixpath
from collections.abc import Iterable, Mapping
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

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
from paperflow.render.website import render_website_files
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
