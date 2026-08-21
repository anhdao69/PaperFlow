from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from paperflow.cli.reclassify import main, select_reclassification_ids
from paperflow.models import (
    FigureStatus,
    FilterStatus,
    ScreeningEvent,
    SelectedPaper,
    SummaryStatus,
    TopicAssignment,
)

HASH = "a" * 64


def selected(paper_id: str, seen: date, topic: str) -> SelectedPaper:
    instant = datetime.combine(seen, datetime.min.time(), UTC)
    return SelectedPaper(
        arxiv_id=paper_id,
        source_arxiv_id=f"{paper_id}v1",
        title="Fixture paper",
        abstract="Fixture abstract.",
        authors=["Fixture Author"],
        categories=["cs.AI"],
        arxiv_url=f"https://arxiv.org/abs/{paper_id}",
        pdf_url=f"https://arxiv.org/pdf/{paper_id}",
        first_seen_at=instant,
        first_seen_date=seen,
        filter_status=FilterStatus.KEPT,
        relevance=8,
        novelty=7,
        topic_assignments=[TopicAssignment(topic_id=topic)],
        selection_reason="Fixture selection.",
        summary_status=SummaryStatus.FAILED,
        figure_status=FigureStatus.NOT_IMPLEMENTED,
        taxonomy_version=1,
        taxonomy_hash=HASH,
        filter_prompt_version="filter-v3",
        filter_prompt_hash=HASH,
        summary_prompt_version="summary-v2",
        summary_prompt_hash=HASH,
        filter_model="fixture/model",
    )


def dropped(paper_id: str, observed: datetime) -> ScreeningEvent:
    return ScreeningEvent(
        event_id=UUID(int=1),
        run_id="fixture",
        arxiv_id=paper_id,
        observed_at=observed,
        abstract_hash=HASH,
        filter_status=FilterStatus.DROPPED,
        attempt_number=1,
        relevance=2,
        novelty=3,
        reason="Fixture drop.",
        taxonomy_version=1,
        taxonomy_hash=HASH,
        filter_prompt_version="filter-v3",
        filter_prompt_hash=HASH,
    )


def test_selection_supports_since_topic_and_screened_drops() -> None:
    papers = {
        "2608.10001": selected(
            "2608.10001", date(2026, 8, 1), "world-models"
        ),
        "2608.10002": selected(
            "2608.10002", date(2026, 8, 20), "embodied-ai"
        ),
    }
    latest = {
        "2608.10003": dropped(
            "2608.10003", datetime(2026, 8, 21, tzinfo=UTC)
        )
    }

    assert select_reclassification_ids(
        papers,
        latest,
        all_selected=False,
        since=date(2026, 8, 15),
        topic=None,
        screened_drops=False,
    ) == ("2608.10002",)
    assert select_reclassification_ids(
        papers,
        latest,
        all_selected=False,
        since=None,
        topic="world-models",
        screened_drops=False,
    ) == ("2608.10001",)
    assert select_reclassification_ids(
        papers,
        latest,
        all_selected=False,
        since=date(2026, 8, 20),
        topic=None,
        screened_drops=True,
    ) == ("2608.10003",)


def test_cli_requires_explicit_selector_and_empty_dry_run_is_safe() -> None:
    assert main([]) == 1
    assert main(["--all-selected", "--dry-run"]) == 0
