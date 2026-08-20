from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from paperflow.generated_files import GENERATED_FILE_MARKER
from paperflow.render.validation import (
    build_output_bundle,
    plan_stale_markdown_cleanup,
    publish_outputs,
    remove_stale_generated_files,
    validate_generated_artifacts,
    write_output_staging,
)
from paperflow.render.view_models import build_public_projection
from paperflow.taxonomy import load_taxonomy

ROOT = Path(__file__).parents[3]


def _empty_projection(*, zero_day: bool = False):
    return build_public_projection(
        {},
        load_taxonomy(ROOT / "configs/topics.yaml"),
        generated_at=datetime.fromisoformat("2026-08-20T21:05:00-04:00"),
        timezone="America/New_York",
        base_url="https://example.test/PaperFlow/",
        successful_dates=[date(2026, 8, 20)] if zero_day else [],
    )


def test_publish_removes_only_marker_confirmed_stale_markdown(
    tmp_path: Path,
) -> None:
    stale = tmp_path / "topics/removed-topic/README.md"
    stale.parent.mkdir(parents=True)
    stale.write_text(f"{GENERATED_FILE_MARKER}\nOld generated page.\n")
    manual = tmp_path / "topics/personal-notes.md"
    manual.write_text("# Personal notes\n")

    publish_outputs(
        tmp_path,
        _empty_projection(),
        load_taxonomy(ROOT / "configs/topics.yaml"),
        readme_latest_limit=80,
    )

    assert not stale.exists()
    assert manual.read_text() == "# Personal notes\n"


def test_manual_markdown_at_planned_target_blocks_all_publication(
    tmp_path: Path,
) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# Handwritten project notes\n")

    with pytest.raises(ValueError, match="manual Markdown"):
        publish_outputs(
            tmp_path,
            _empty_projection(),
            load_taxonomy(ROOT / "configs/topics.yaml"),
            readme_latest_limit=80,
        )

    assert readme.read_text() == "# Handwritten project notes\n"
    assert not (tmp_path / "data/feed_index.json").exists()


def test_cleanup_plan_excludes_desired_and_unmarked_files(tmp_path: Path) -> None:
    desired = tmp_path / "topics/world-models/README.md"
    desired.parent.mkdir(parents=True)
    desired.write_text(GENERATED_FILE_MARKER)
    stale = tmp_path / "topics/old.md"
    stale.write_text(GENERATED_FILE_MARKER)
    manual = tmp_path / "daily/notes.md"
    manual.parent.mkdir(parents=True)
    manual.write_text("manual")

    planned = plan_stale_markdown_cleanup(
        tmp_path, [Path("topics/world-models/README.md")]
    )

    assert planned == (stale,)


def test_cleanup_refuses_marked_file_outside_destination(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text(GENERATED_FILE_MARKER)

    with pytest.raises(ValueError, match="escapes"):
        remove_stale_generated_files(root, [outside])

    assert outside.exists()


def test_staged_validation_error_leaves_live_outputs_byte_identical(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "live"
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")
    projection = _empty_projection(zero_day=True)
    paths = publish_outputs(
        destination,
        projection,
        taxonomy,
        readme_latest_limit=80,
    )
    before = {path: (destination / path).read_bytes() for path in paths}
    staging = tmp_path / "staging"
    files = build_output_bundle(
        projection, taxonomy, readme_latest_limit=80
    )
    write_output_staging(staging, files)
    feed_index = staging / "data/feed_index.json"
    feed_index.write_text(
        feed_index.read_text(encoding="utf-8").replace(
            '"day_count": 1', '"day_count": 9'
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="differs from projection"):
        validate_generated_artifacts(
            staging,
            projection,
            taxonomy,
            readme_latest_limit=80,
        )

    assert {path: (destination / path).read_bytes() for path in paths} == before
