from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path, PurePosixPath

from paperflow.models import (
    FigureStatus,
    FilterStatus,
    SelectedPaper,
    SummaryStatus,
    TopicAssignment,
)
from paperflow.render.contracts import DailyFeed, FeedIndex, TopicFeed, TopicsIndex
from paperflow.render.json_api import render_json_files
from paperflow.render.view_models import build_public_projection
from paperflow.taxonomy import load_taxonomy

ROOT = Path(__file__).parents[3]
HASH = "9" * 64


def _selected(index: int) -> SelectedPaper:
    paper_id = f"2608.{70000 + index:05d}"
    seen = datetime.fromisoformat("2026-08-20T21:00:00-04:00")
    return SelectedPaper(
        arxiv_id=paper_id,
        source_arxiv_id=f"{paper_id}v1",
        title=f"JSON Paper {index}",
        abstract=f"Required full abstract {index}.",
        authors=["JSON Author"],
        categories=["cs.AI"],
        arxiv_url=f"https://arxiv.org/abs/{paper_id}",
        pdf_url=f"https://arxiv.org/pdf/{paper_id}",
        first_seen_at=seen,
        first_seen_date=seen.date(),
        filter_status=FilterStatus.KEPT,
        relevance=8,
        novelty=7,
        topic_assignments=[
            TopicAssignment(
                topic_id="world-models", subtopic_ids=["video-world-models"]
            )
        ],
        selection_reason="JSON fixture.",
        summary_status=SummaryStatus.FAILED,
        figure_status=FigureStatus.NOT_IMPLEMENTED,
        taxonomy_version=1,
        taxonomy_hash=HASH,
        filter_prompt_version="filter-v3",
        filter_prompt_hash=HASH,
        summary_prompt_version="summary-v2",
        summary_prompt_hash=HASH,
        filter_model="deepseek/deepseek-v4-flash-0731",
    )


def _projection(count: int, *, zero_day: bool = False):
    papers = {_selected(index).arxiv_id: _selected(index) for index in range(count)}
    return build_public_projection(
        papers,
        load_taxonomy(ROOT / "configs/topics.yaml"),
        generated_at=datetime.fromisoformat("2026-08-20T21:05:00-04:00"),
        timezone="America/New_York",
        base_url="https://example.test/PaperFlow/",
        successful_dates=[date(2026, 8, 19)] if zero_day else [],
    )


def test_json_renderer_emits_every_configured_feed_including_empty_views() -> None:
    files = render_json_files(_projection(0, zero_day=True))
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")
    expected_topic_feeds = len(taxonomy.topics) + sum(
        len(topic.subtopics) for topic in taxonomy.topics
    )

    assert PurePosixPath("data/feed_index.json") in files
    assert PurePosixPath("data/topics.json") in files
    assert PurePosixPath("data/daily_feeds/2026-08-19.json") in files
    assert len(files) == 2 + 1 + expected_topic_feeds
    empty = TopicFeed.model_validate_json(
        files[PurePosixPath("data/topic_feeds/efficient-ai/all.json")]
    )
    assert empty.total_paper_count == 0
    assert empty.days == []


def test_json_counts_membership_and_fallback_are_full_history() -> None:
    files = render_json_files(_projection(81, zero_day=True))
    index = FeedIndex.model_validate_json(
        files[PurePosixPath("data/feed_index.json")]
    )
    daily = DailyFeed.model_validate_json(
        files[PurePosixPath("data/daily_feeds/2026-08-20.json")]
    )
    world = TopicFeed.model_validate_json(
        files[PurePosixPath("data/topic_feeds/world-models/all.json")]
    )
    video = TopicFeed.model_validate_json(
        files[
            PurePosixPath(
                "data/topic_feeds/world-models/video-world-models.json"
            )
        ]
    )

    assert index.total_paper_count == 81
    assert daily.paper_count == world.total_paper_count == 81
    assert video.total_paper_count == 81
    assert all(paper.abstract for paper in daily.papers)
    assert all(paper.display_summary == paper.abstract for paper in daily.papers)


def test_topics_hierarchy_and_counts_come_from_full_projection() -> None:
    files = render_json_files(_projection(2))
    topics = TopicsIndex.model_validate_json(
        files[PurePosixPath("data/topics.json")]
    )
    world = next(topic for topic in topics.topics if topic.id == "world-models")
    video = next(
        subtopic
        for subtopic in world.subtopics
        if subtopic.id == "video-world-models"
    )

    assert topics.total_paper_count == 2
    assert world.paper_count == video.paper_count == 2
    assert [topic.id for topic in topics.topics] == list(
        load_taxonomy(ROOT / "configs/topics.yaml").ordered_topic_ids()
    )


def test_public_json_contains_no_private_fields() -> None:
    files = render_json_files(_projection(1))
    serialized = files[PurePosixPath("data/daily_feeds/2026-08-20.json")]

    for private in (
        "filter_prompt_hash",
        "summary_prompt_hash",
        "filter_model",
        "requested_model",
        "retry_exhausted",
    ):
        assert private not in serialized
    assert json.loads(serialized)["papers"][0]["abstract"]
