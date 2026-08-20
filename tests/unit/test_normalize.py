from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from paperflow.models import AnnounceType, RawArxivEntry
from paperflow.normalize import normalize_and_deduplicate, normalize_arxiv_id

ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize(
    ("source_id", "canonical"),
    [
        ("2608.12345v1", "2608.12345"),
        ("2608.12345v27", "2608.12345"),
        ("2608.12345", "2608.12345"),
        ("arXiv:2608.12345v2", "2608.12345"),
        ("hep-th/9901001v3", "hep-th/9901001"),
    ],
)
def test_version_normalization(source_id: str, canonical: str) -> None:
    assert normalize_arxiv_id(source_id) == canonical


@pytest.mark.parametrize("invalid", ["", "2608.12", "2608.12345v", "../paper"])
def test_invalid_ids_are_rejected(invalid: str) -> None:
    with pytest.raises(ValueError, match="invalid arXiv ID"):
        normalize_arxiv_id(invalid)


def test_dedup_merges_categories_stably_and_preserves_scientific_text() -> None:
    entries = [
        RawArxivEntry(
            source_arxiv_id="2608.12345v1",
            title="A  $\\LaTeX$   Title",
            abstract="Energy is  $E = mc^2$\nwithout rewriting.",
            authors=["A. Author"],
            categories=["cs.RO", "cs.CV"],
            announce_type=AnnounceType.NEW,
        ),
        RawArxivEntry(
            source_arxiv_id="2608.12345v1",
            title="A $\\LaTeX$ Title",
            abstract="Energy is $E = mc^2$ without rewriting.",
            authors=["A. Author", "B. Author"],
            categories=["cs.CV", "cs.AI"],
            announce_type=AnnounceType.CROSS,
        ),
    ]

    candidates = normalize_and_deduplicate(entries)

    assert len(candidates) == 1
    assert candidates[0].categories == ["cs.RO", "cs.CV", "cs.AI"]
    assert candidates[0].authors == ["A. Author", "B. Author"]
    assert candidates[0].title == "A $\\LaTeX$ Title"
    assert candidates[0].abstract == "Energy is $E = mc^2$ without rewriting."


def test_replacement_is_excluded_from_normal_flow() -> None:
    replacement = RawArxivEntry(
        source_arxiv_id="2608.12345v2",
        title="Replacement",
        abstract="Updated abstract.",
        authors=["A. Author"],
        categories=["cs.AI"],
        announce_type=AnnounceType.REPLACE,
    )

    assert normalize_and_deduplicate([replacement]) == []


def test_twelve_entry_fixture_yields_ten_unique_candidates() -> None:
    payload = json.loads(
        (ROOT / "tests/fixtures/arxiv_daily_sample.json").read_text(encoding="utf-8")
    )
    entries = TypeAdapter(list[RawArxivEntry]).validate_python(payload)

    candidates = normalize_and_deduplicate(entries)

    assert len(entries) == 12
    assert [paper.arxiv_id for paper in candidates] == [
        f"2608.{number:05d}" for number in range(10001, 10011)
    ]
    assert candidates[0].categories == ["cs.RO", "cs.CV"]
    assert candidates[1].categories == ["cs.AI", "cs.LG"]
