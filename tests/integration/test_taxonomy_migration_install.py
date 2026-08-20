from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

import pytest

from paperflow.atomic import install_staged_files
from paperflow.generated_files import (
    GENERATED_FILE_MARKER,
    generated_cleanup_candidates,
)
from paperflow.models import TopicAssignment
from paperflow.taxonomy import load_taxonomy
from paperflow.taxonomy_migrations import (
    apply_taxonomy_migrations,
    plan_taxonomy_migrations,
)


def test_migrate_validate_stage_and_install_with_failure_rollback(
    tmp_path: Path,
) -> None:
    root = Path(__file__).parents[2]
    fixtures = root / "tests/fixtures/taxonomy/migrations"
    previous = load_taxonomy(fixtures / "previous.yaml")
    current = load_taxonomy(fixtures / "current.yaml")
    store = {
        "paper-1": [
            TopicAssignment(topic_id="old-topic", subtopic_ids=["old-child"])
        ],
        "paper-2": [
            TopicAssignment(topic_id="destination", subtopic_ids=["existing-child"])
        ],
    }
    plan = plan_taxonomy_migrations(previous, current, store)
    migrated = apply_taxonomy_migrations(store, current, plan)

    staging = tmp_path / "staging"
    live = tmp_path / "live"
    staging.mkdir()
    live.mkdir()
    payload = {
        paper_id: [assignment.model_dump() for assignment in assignments]
        for paper_id, assignments in migrated.items()
    }
    (staging / "papers.json").write_text(
        json.dumps(payload, sort_keys=True), encoding="utf-8"
    )
    (staging / "topic.md").write_text(
        f"{GENERATED_FILE_MARKER}\nMigrated\n", encoding="utf-8"
    )
    (live / "papers.json").write_text("old papers", encoding="utf-8")
    (live / "topic.md").write_text(
        f"{GENERATED_FILE_MARKER}\nOld\n", encoding="utf-8"
    )
    original = {path.name: path.read_bytes() for path in live.iterdir()}

    def validate(staged_root: Path) -> None:
        loaded = json.loads((staged_root / "papers.json").read_text(encoding="utf-8"))
        assert loaded["paper-1"][0]["topic_id"] == "destination"

    def fail_before_install() -> None:
        raise RuntimeError("injected failure")

    relative_paths = [PurePosixPath("papers.json"), PurePosixPath("topic.md")]
    with pytest.raises(RuntimeError, match="injected failure"):
        install_staged_files(
            staging,
            live,
            relative_paths,
            validate_staging=validate,
            before_install=fail_before_install,
        )
    assert {path.name: path.read_bytes() for path in live.iterdir()} == original

    install_staged_files(
        staging, live, relative_paths, validate_staging=validate
    )
    assert json.loads((live / "papers.json").read_text())["paper-1"][0][
        "topic_id"
    ] == "destination"
    manual = live / "notes.md"
    manual.write_text("manual", encoding="utf-8")
    assert generated_cleanup_candidates([live / "topic.md", manual]) == (
        live / "topic.md",
    )
