import json
from datetime import date
from pathlib import Path

import pytest

from paperflow.recovery import load_recovery_snapshot


def snapshot(path: Path, **changes) -> Path:
    payload = {
        "schema_version": 1,
        "publication_date": "2026-10-06",
        "announcement_date": "2026-10-07",
        "categories": ["cs.AI", "cs.CV"],
        "captured_at": "2026-10-09T18:00:00Z",
        "provenance": "dated arXiv listings and refetched metadata",
        "candidate_count": 1,
        "entries": [
            {
                "source_arxiv_id": "2610.01234v2",
                "title": "Navigation",
                "abstract": "Spatial memory for navigation.",
                "authors": ["A. Researcher"],
                "categories": ["cs.CV", "cs.AI"],
                "announce_type": "cross",
            }
        ],
    }
    payload.update(changes)
    path.write_text(json.dumps(payload))
    return path


def test_recovery_preserves_cross_listing_and_version(tmp_path: Path) -> None:
    entries = load_recovery_snapshot(
        snapshot(tmp_path / "snapshot.json"),
        publication_date=date(2026, 10, 6),
        categories=["cs.AI", "cs.CV"],
    )
    assert len(entries) == 1
    assert entries[0].source_arxiv_id == "2610.01234v2"
    assert entries[0].announce_type.value == "cross"


@pytest.mark.parametrize(
    "changes",
    [
        {"publication_date": "2026-10-07"},
        {"announcement_date": "2026-10-09"},
        {"categories": ["cs.AI"]},
        {"candidate_count": 2},
        {"schema_version": 99},
    ],
)
def test_recovery_rejects_wrong_date_coverage_or_schema(
    tmp_path: Path, changes
) -> None:
    with pytest.raises(ValueError):
        load_recovery_snapshot(
            snapshot(tmp_path / "snapshot.json", **changes),
            publication_date=date(2026, 10, 6),
            categories=["cs.AI", "cs.CV"],
        )
