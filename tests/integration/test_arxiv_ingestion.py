from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from paperflow.arxiv_client import save_raw_snapshot
from paperflow.models import RawArxivEntry
from paperflow.normalize import normalize_and_deduplicate


def test_canonical_fixture_ingests_to_cache_without_public_writes(
    tmp_path: Path,
) -> None:
    root = Path(__file__).parents[2]
    payload = json.loads(
        (root / "tests/fixtures/arxiv_daily_sample.json").read_text(encoding="utf-8")
    )
    entries = TypeAdapter(list[RawArxivEntry]).validate_python(payload)

    candidates = normalize_and_deduplicate(entries)
    snapshot = save_raw_snapshot(tmp_path / "cache", "fixture-run", entries)

    assert len(entries) == 12
    assert len(candidates) == 10
    assert snapshot.is_file()
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / "site").exists()
