from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from paperflow.models import (
    FigureStatus,
    FilterStatus,
    SelectedPaper,
    SummaryStatus,
    TopicAssignment,
)
from paperflow.render.contracts import (
    validate_topic_feed_contract,
    validate_topics_contract,
)
from paperflow.render.view_models import build_public_projection
from paperflow.taxonomy import load_taxonomy

ROOT = Path(__file__).parents[3]
HASH = "e" * 64


def _paper(
    paper_id: str,
    *,
    seen: datetime,
    assignments: list[TopicAssignment],
    summary_status: SummaryStatus = SummaryStatus.GENERATED,
) -> SelectedPaper:
    generated = summary_status == SummaryStatus.GENERATED
    return SelectedPaper(
        arxiv_id=paper_id,
        source_arxiv_id=f"{paper_id}v1",
        title=f"Projection Paper {paper_id}",
        abstract=f"Required abstract fallback for {paper_id}.",
        authors=["Projection Author"],
        categories=["cs.AI"],
        arxiv_url=f"https://arxiv.org/abs/{paper_id}",
        pdf_url=f"https://arxiv.org/pdf/{paper_id}",
        first_seen_at=seen,
        first_seen_date=seen.date(),
        filter_status=FilterStatus.KEPT,
        relevance=9,
        novelty=7,
        topic_assignments=assignments,
        selection_reason="Projected fixture membership.",
        summary_status=summary_status,
        tldr=f"Generated summary for {paper_id}." if generated else None,
        bullets=["Problem.", "Method.", "Contribution."] if generated else [],
        figure_status=FigureStatus.NOT_IMPLEMENTED,
        taxonomy_version=1,
        taxonomy_hash=HASH,
        filter_prompt_version="filter-v3",
        filter_prompt_hash=HASH,
        summary_prompt_version="summary-v2",
        summary_prompt_hash=HASH,
        filter_model="deepseek/deepseek-v4-flash-0731",
        summary_model="openai/gpt-5.6-luna" if generated else None,
    )


@pytest.fixture
def projection():
    offset = datetime.fromisoformat
    multi_topic = _paper(
        "2608.50001",
        seen=offset("2026-08-20T21:00:00-04:00"),
        assignments=[
            TopicAssignment(
                topic_id="world-models",
                subtopic_ids=["video-world-models"],
            ),
            TopicAssignment(topic_id="embodied-ai", subtopic_ids=[]),
        ],
    )
    same_time_higher_id = _paper(
        "2608.50002",
        seen=offset("2026-08-20T21:00:00-04:00"),
        assignments=[
            TopicAssignment(
                topic_id="spatial-intelligence",
                subtopic_ids=["spatial-memory"],
            )
        ],
        summary_status=SummaryStatus.FAILED,
    )
    older_parent_only = _paper(
        "2608.49999",
        seen=offset("2026-08-19T21:00:00-04:00"),
        assignments=[TopicAssignment(topic_id="world-models", subtopic_ids=[])],
    )
    papers = {
        paper.arxiv_id: paper
        for paper in [multi_topic, same_time_higher_id, older_parent_only]
    }
    return build_public_projection(
        papers,
        load_taxonomy(ROOT / "configs/topics.yaml"),
        generated_at=offset("2026-08-20T21:05:00-04:00"),
        timezone="America/New_York",
        base_url="https://example.test/PaperFlow/",
        successful_dates=[date(2026, 8, 18)],
    )


def test_global_membership_order_counts_and_zero_day(projection) -> None:
    assert [paper.arxiv_id for paper in projection.papers] == [
        "2608.50002",
        "2608.50001",
        "2608.49999",
    ]
    index = projection.feed_index()
    assert index.total_paper_count == 3
    assert index.day_count == 3
    assert [(day.date.isoformat(), day.paper_count) for day in index.days] == [
        ("2026-08-20", 2),
        ("2026-08-19", 1),
        ("2026-08-18", 0),
    ]
    assert projection.daily_feeds()[date(2026, 8, 18)].papers == []


def test_topics_mirror_config_order_and_unique_total(projection) -> None:
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")
    topics = projection.topics_index()

    validate_topics_contract(topics, taxonomy)
    assert [topic.id for topic in topics.topics] == list(
        taxonomy.ordered_topic_ids()
    )
    assert topics.total_paper_count == 3
    assert sum(topic.paper_count for topic in topics.topics) == 4
    assert topics.topics[-1].id == "efficient-ai"
    assert topics.topics[-1].paper_count == 0


def test_multi_topic_fanout_and_parent_only_membership(projection) -> None:
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")
    world = projection.topic_feed("world-models")
    video = projection.topic_feed("world-models", "video-world-models")
    embodied = projection.topic_feed("embodied-ai")

    validate_topic_feed_contract(world, taxonomy)
    validate_topic_feed_contract(video, taxonomy)
    validate_topic_feed_contract(embodied, taxonomy)
    assert {paper.arxiv_id for day in world.days for paper in day.papers} == {
        "2608.50001",
        "2608.49999",
    }
    assert [paper.arxiv_id for day in video.days for paper in day.papers] == [
        "2608.50001"
    ]
    assert [paper.arxiv_id for day in embodied.days for paper in day.papers] == [
        "2608.50001"
    ]


def test_assignments_are_normalized_to_taxonomy_order(projection) -> None:
    paper = next(item for item in projection.papers if item.arxiv_id == "2608.50001")

    assert [assignment.topic_id for assignment in paper.topic_assignments] == [
        "embodied-ai",
        "world-models",
    ]


def test_failed_summary_retains_required_abstract_fallback(projection) -> None:
    paper = next(item for item in projection.papers if item.arxiv_id == "2608.50002")

    assert paper.abstract
    assert paper.tldr is None
    assert paper.display_summary == paper.abstract


def test_every_feed_url_is_explicit_and_root_relative(projection) -> None:
    index = projection.feed_index()
    topics = projection.topics_index()

    assert index.days[0].feed_url == "data/daily_feeds/2026-08-20.json"
    assert topics.topics[0].feed_url == "data/topic_feeds/embodied-ai/all.json"
    assert topics.topics[0].subtopics[0].feed_url == (
        "data/topic_feeds/embodied-ai/vision-language-navigation.json"
    )


def test_unknown_topic_or_wrong_parent_feed_request_fails(projection) -> None:
    with pytest.raises(KeyError):
        projection.topic_feed("not-configured")
    with pytest.raises(KeyError):
        projection.topic_feed("world-models", "spatial-memory")


def test_projection_rejects_invalid_selected_mapping_key() -> None:
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")
    paper = _paper(
        "2608.50001",
        seen=datetime.fromisoformat("2026-08-20T21:00:00-04:00"),
        assignments=[TopicAssignment(topic_id="world-models")],
    )

    with pytest.raises(ValueError, match="mapping key"):
        build_public_projection(
            {"2608.99999": paper},
            taxonomy,
            generated_at=datetime.fromisoformat("2026-08-20T21:05:00-04:00"),
            timezone="America/New_York",
            base_url="https://example.test/PaperFlow/",
        )
