from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from paperflow.models import (
    FigureStatus,
    FilterStatus,
    SelectedPaper,
    SummaryStatus,
    TopicAssignment,
)
from paperflow.paper_store import load_selected_store, save_selected_store
from paperflow.taxonomy import load_taxonomy

HASH = "b" * 64
ROOT = Path(__file__).parents[2]


def _paper(**changes: object) -> SelectedPaper:
    data: dict[str, object] = {
        "arxiv_id": "2608.12345",
        "source_arxiv_id": "2608.12345v1",
        "title": "Geometry-Aware Navigation",
        "abstract": "We introduce a geometry-aware navigation method.",
        "authors": ["A. Researcher", "B. Scientist"],
        "categories": ["cs.RO", "cs.CV"],
        "arxiv_url": "https://arxiv.org/abs/2608.12345",
        "pdf_url": "https://arxiv.org/pdf/2608.12345",
        "first_seen_at": datetime(2026, 8, 20, 21, tzinfo=UTC),
        "first_seen_date": "2026-08-20",
        "filter_status": FilterStatus.KEPT,
        "relevance": 10,
        "novelty": 8,
        "topic_assignments": [
            TopicAssignment(
                topic_id="spatial-intelligence",
                subtopic_ids=["geometry-aware-models"],
            )
        ],
        "selection_reason": "Direct use of geometry for navigation.",
        "summary_status": SummaryStatus.GENERATED,
        "tldr": "A geometry-aware navigation method.",
        "bullets": ["Problem.", "Method.", "Contribution."],
        "hero_figure": None,
        "figure_status": FigureStatus.NOT_IMPLEMENTED,
        "taxonomy_version": 1,
        "taxonomy_hash": HASH,
        "filter_prompt_version": "filter-v3",
        "filter_prompt_hash": HASH,
        "summary_prompt_version": "summary-v2",
        "summary_prompt_hash": HASH,
        "filter_model": "deepseek/deepseek-v4-flash-0731",
        "summary_model": "openai/gpt-5.6-luna",
    }
    data.update(changes)
    return SelectedPaper.model_validate(data)


def test_selected_store_round_trip_preserves_every_field(tmp_path: Path) -> None:
    path = tmp_path / "papers.json"
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")
    paper = _paper()

    saved = save_selected_store(path, {paper.arxiv_id: paper}, taxonomy)
    loaded = load_selected_store(path, taxonomy)

    assert loaded == saved
    assert loaded.papers[paper.arxiv_id] == paper


@pytest.mark.parametrize(
    "changes",
    [
        {"filter_status": FilterStatus.DROPPED},
        {"topic_assignments": []},
        {"summary_status": SummaryStatus.GENERATED, "tldr": None},
        {"summary_status": SummaryStatus.GENERATED, "summary_model": None},
        {"summary_status": SummaryStatus.FAILED, "tldr": "Unexpected"},
        {"figure_status": FigureStatus.READY, "hero_figure": None},
        {
            "figure_status": FigureStatus.NOT_IMPLEMENTED,
            "hero_figure": "figures/2608.12345/hero.webp",
        },
    ],
)
def test_selected_paper_invariants(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _paper(**changes)


def test_wrong_parent_assignment_cannot_replace_valid_store(tmp_path: Path) -> None:
    path = tmp_path / "papers.json"
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")
    paper = _paper()
    save_selected_store(path, {paper.arxiv_id: paper}, taxonomy)
    original = path.read_bytes()
    invalid = _paper(
        topic_assignments=[
            TopicAssignment(
                topic_id="world-models", subtopic_ids=["geometry-aware-models"]
            )
        ]
    )

    with pytest.raises(ValueError, match="not a child"):
        save_selected_store(path, {invalid.arxiv_id: invalid}, taxonomy)

    assert path.read_bytes() == original


def test_selected_store_key_must_match_canonical_id(tmp_path: Path) -> None:
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")
    with pytest.raises(ValidationError, match="does not match"):
        save_selected_store(
            tmp_path / "papers.json", {"2608.99999": _paper()}, taxonomy
        )


def test_pending_and_failed_summary_fallback_states_are_valid() -> None:
    for status in (SummaryStatus.PENDING, SummaryStatus.FAILED):
        paper = _paper(
            summary_status=status,
            tldr=None,
            bullets=[],
            summary_model=None,
        )
        assert paper.abstract
