from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from paperflow.atomic import install_staged_files
from paperflow.models import (
    FigureStatus,
    FilterStatus,
    SelectedPaper,
    SummaryStatus,
    TopicAssignment,
)
from paperflow.render.contracts import DailyFeed, FeedIndex, TopicFeed, TopicsIndex
from paperflow.render.validation import (
    build_output_bundle,
    publish_outputs,
    validate_generated_artifacts,
    write_output_staging,
)
from paperflow.render.view_models import build_public_projection
from paperflow.taxonomy import load_taxonomy

ROOT = Path(__file__).parents[2]
HASH = "8" * 64
ARXIV_LINK = re.compile(r"https://arxiv\.org/abs/(\d{4}\.\d{4,5})")


def _paper(index: int) -> SelectedPaper:
    paper_id = f"2608.{80000 + index:05d}"
    seen = datetime.fromisoformat("2026-08-20T21:00:00-04:00") + timedelta(
        seconds=index
    )
    assignments = [
        TopicAssignment(
            topic_id="world-models",
            subtopic_ids=[] if index == 0 else ["video-world-models"],
        )
    ]
    if index == 80:
        assignments.append(TopicAssignment(topic_id="embodied-ai"))
    generated = index != 40
    return SelectedPaper(
        arxiv_id=paper_id,
        source_arxiv_id=f"{paper_id}v1",
        title=f"Generated Output Paper {index}",
        abstract=f"Complete abstract fallback for generated fixture {index}.",
        authors=["Generated Fixture"],
        categories=["cs.AI"],
        arxiv_url=f"https://arxiv.org/abs/{paper_id}",
        pdf_url=f"https://arxiv.org/pdf/{paper_id}",
        first_seen_at=seen,
        first_seen_date=seen.date(),
        filter_status=FilterStatus.KEPT,
        relevance=9,
        novelty=8,
        topic_assignments=assignments,
        selection_reason="Full-history publication fixture.",
        summary_status=(
            SummaryStatus.GENERATED if generated else SummaryStatus.FAILED
        ),
        tldr=f"Generated TL;DR {index}." if generated else None,
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
def publication_fixture():
    papers = [_paper(index) for index in range(81)]
    selected = {paper.arxiv_id: paper for paper in papers}
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")
    projection = build_public_projection(
        selected,
        taxonomy,
        generated_at=datetime.fromisoformat("2026-08-20T21:05:00-04:00"),
        timezone="America/New_York",
        base_url="https://example.test/PaperFlow/",
        successful_dates=[date(2026, 8, 19)],
    )
    return selected, taxonomy, projection


def _markdown_ids(path: Path) -> list[str]:
    return ARXIV_LINK.findall(path.read_text(encoding="utf-8"))


def test_generated_outputs_are_complete_consistent_and_linked(
    tmp_path: Path, publication_fixture
) -> None:
    selected, taxonomy, projection = publication_fixture
    paths = publish_outputs(
        tmp_path,
        projection,
        taxonomy,
        readme_latest_limit=80,
    )
    validate_generated_artifacts(
        tmp_path,
        projection,
        taxonomy,
        readme_latest_limit=80,
    )

    readme_ids = _markdown_ids(tmp_path / "README.md")
    daily_ids = _markdown_ids(tmp_path / "daily/2026-08-20.md")
    world_ids = _markdown_ids(tmp_path / "topics/world-models/README.md")
    video_ids = _markdown_ids(
        tmp_path / "topics/world-models/video-world-models.md"
    )
    assert len(readme_ids) == 80
    assert "2608.80000" not in readme_ids
    assert "2608.80001" in readme_ids
    assert set(daily_ids) == set(selected)
    assert set(world_ids) == set(selected)
    assert len(video_ids) == 80
    assert "2608.80000" not in video_ids

    index = FeedIndex.model_validate_json(
        (tmp_path / "data/feed_index.json").read_text(encoding="utf-8")
    )
    daily = DailyFeed.model_validate_json(
        (tmp_path / "data/daily_feeds/2026-08-20.json").read_text(
            encoding="utf-8"
        )
    )
    zero = DailyFeed.model_validate_json(
        (tmp_path / "data/daily_feeds/2026-08-19.json").read_text(
            encoding="utf-8"
        )
    )
    topics = TopicsIndex.model_validate_json(
        (tmp_path / "data/topics.json").read_text(encoding="utf-8")
    )
    world = TopicFeed.model_validate_json(
        (tmp_path / "data/topic_feeds/world-models/all.json").read_text(
            encoding="utf-8"
        )
    )
    video = TopicFeed.model_validate_json(
        (
            tmp_path
            / "data/topic_feeds/world-models/video-world-models.json"
        ).read_text(encoding="utf-8")
    )
    assert index.total_paper_count == daily.paper_count == world.total_paper_count == 81
    assert zero.paper_count == 0
    assert video.total_paper_count == 80
    assert {paper.arxiv_id for paper in daily.papers} == set(selected)
    world_topic = next(
        topic for topic in topics.topics if topic.id == "world-models"
    )
    assert world_topic.paper_count == 81
    assert (
        tmp_path / "topics/efficient-ai/efficient-attention.md"
    ).is_file()
    for day in index.days:
        assert (tmp_path / day.feed_url).is_file()
    for topic in topics.topics:
        assert (tmp_path / topic.feed_url).is_file()
        for subtopic in topic.subtopics:
            assert (tmp_path / subtopic.feed_url).is_file()
    assert len(paths) > 50


def test_failed_staged_validation_cannot_change_live_outputs(
    tmp_path: Path, publication_fixture
) -> None:
    _, taxonomy, projection = publication_fixture
    live = tmp_path / "live"
    paths = publish_outputs(
        live,
        projection,
        taxonomy,
        readme_latest_limit=80,
    )
    before = {path: (live / path).read_bytes() for path in paths}
    staging = tmp_path / "invalid-staging"
    files = build_output_bundle(
        projection, taxonomy, readme_latest_limit=80
    )
    write_output_staging(staging, files)
    daily = staging / "data/daily_feeds/2026-08-20.json"
    daily.write_text(
        daily.read_text(encoding="utf-8").replace(
            '"paper_count": 81', '"paper_count": 80', 1
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="differs from projection"):
        install_staged_files(
            staging,
            live,
            paths,
            validate_staging=lambda root: validate_generated_artifacts(
                root,
                projection,
                taxonomy,
                readme_latest_limit=80,
            ),
        )

    assert {path: (live / path).read_bytes() for path in paths} == before
