from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from paperflow.models import (
    FilterStatus,
    SelectedPaper,
)
from paperflow.render.contracts import (
    DailyFeed,
    FeedIndex,
    PublicPaper,
    TopicFeed,
    TopicsIndex,
    validate_topic_feed_contract,
    validate_topics_contract,
)
from paperflow.render.view_models import build_public_projection
from paperflow.taxonomy import load_taxonomy

ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests/fixtures/contracts/v1/valid"
HASH = "f" * 64


def _selected_from_public(path: Path) -> SelectedPaper:
    public = PublicPaper.model_validate_json(path.read_text(encoding="utf-8"))
    return SelectedPaper(
        **public.model_dump(mode="python"),
        source_arxiv_id=f"{public.arxiv_id}v1",
        first_seen_date=public.first_seen_at.date(),
        filter_status=FilterStatus.KEPT,
        taxonomy_version=1,
        taxonomy_hash=HASH,
        filter_prompt_version="filter-v3",
        filter_prompt_hash=HASH,
        summary_prompt_version="summary-v2",
        summary_prompt_hash=HASH,
        filter_model="deepseek/deepseek-v4-flash-0731",
        summary_model=(
            "openai/gpt-5.6-luna" if public.tldr is not None else None
        ),
    )


def test_projection_membership_and_counts_match_across_every_contract() -> None:
    generated = _selected_from_public(FIXTURES / "public_paper_generated.json")
    fallback = _selected_from_public(FIXTURES / "public_paper_fallback.json")
    selected = {
        generated.arxiv_id: generated,
        fallback.arxiv_id: fallback,
    }
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")
    projection = build_public_projection(
        selected,
        taxonomy,
        generated_at=generated.first_seen_at,
        timezone="America/New_York",
        base_url="https://example.test/PaperFlow/",
        successful_dates=[date(2026, 8, 19)],
    )

    feed_index = FeedIndex.model_validate_json(
        projection.feed_index().model_dump_json()
    )
    daily_feeds = {
        day: DailyFeed.model_validate_json(feed.model_dump_json())
        for day, feed in projection.daily_feeds().items()
    }
    topics = TopicsIndex.model_validate_json(
        projection.topics_index().model_dump_json()
    )
    world = TopicFeed.model_validate_json(
        projection.topic_feed("world-models").model_dump_json()
    )
    video = TopicFeed.model_validate_json(
        projection.topic_feed(
            "world-models", "video-world-models"
        ).model_dump_json()
    )
    memory = TopicFeed.model_validate_json(
        projection.topic_feed("adaptation-and-memory").model_dump_json()
    )

    validate_topics_contract(topics, taxonomy)
    for contract in (world, video, memory):
        validate_topic_feed_contract(contract, taxonomy)
    assert feed_index.total_paper_count == len(selected) == 2
    assert feed_index.total_paper_count == sum(
        feed.paper_count for feed in daily_feeds.values()
    )
    assert daily_feeds[date(2026, 8, 20)].paper_count == 2
    assert daily_feeds[date(2026, 8, 19)].paper_count == 0
    assert world.total_paper_count == video.total_paper_count == 1
    assert memory.total_paper_count == 1
    assert topics.total_paper_count == 2
    topics_by_id = {topic.id: topic for topic in topics.topics}
    assert topics_by_id["world-models"].paper_count == world.total_paper_count
    assert topics_by_id["adaptation-and-memory"].paper_count == (
        memory.total_paper_count
    )
    world_subtopics = {
        subtopic.id: subtopic for subtopic in topics_by_id["world-models"].subtopics
    }
    assert world_subtopics["video-world-models"].paper_count == (
        video.total_paper_count
    )
    assert all(
        paper.abstract
        for feed in daily_feeds.values()
        for paper in feed.papers
    )
    assert "filter_prompt_hash" not in json.dumps(
        daily_feeds[date(2026, 8, 20)].model_dump(mode="json")
    )
