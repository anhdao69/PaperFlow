from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from paperflow.models import FilterStatus, SelectedPaper
from paperflow.render.contracts import PublicPaper, TopicFeed
from paperflow.render.validation import publish_outputs
from paperflow.render.view_models import build_public_projection
from paperflow.taxonomy import load_taxonomy

ROOT = Path(__file__).parents[2]
PUBLIC_FIXTURES = ROOT / "tests/fixtures/contracts/v1/valid"
HASH = "6" * 64
MEMBERSHIP = re.compile(r'data-arxiv-id="([^"]+)"')


def _selected(fixture: str) -> SelectedPaper:
    public = PublicPaper.model_validate_json(
        (PUBLIC_FIXTURES / fixture).read_text(encoding="utf-8")
    )
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


def _html_ids(path: Path) -> set[str]:
    return set(MEMBERSHIP.findall(path.read_text(encoding="utf-8")))


def _feed_ids(path: Path) -> set[str]:
    feed = TopicFeed.model_validate_json(path.read_text(encoding="utf-8"))
    return {paper.arxiv_id for day in feed.days for paper in day.papers}


def test_website_memberships_and_counts_match_json_and_markdown(
    tmp_path: Path,
) -> None:
    generated = _selected("public_paper_generated.json")
    fallback = _selected("public_paper_fallback.json")
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
    publish_outputs(
        tmp_path,
        projection,
        taxonomy,
        readme_latest_limit=80,
    )

    root_ids = _html_ids(tmp_path / "site/index.html")
    day_ids = _html_ids(tmp_path / "site/days/2026-08-20.html")
    world_html = _html_ids(tmp_path / "site/topics/world-models/index.html")
    video_html = _html_ids(
        tmp_path / "site/topics/world-models/video-world-models.html"
    )
    spatial_html = _html_ids(
        tmp_path / "site/topics/spatial-intelligence/index.html"
    )
    world_json = _feed_ids(
        tmp_path / "data/topic_feeds/world-models/all.json"
    )
    video_json = _feed_ids(
        tmp_path / "data/topic_feeds/world-models/video-world-models.json"
    )
    spatial_json = _feed_ids(
        tmp_path / "data/topic_feeds/spatial-intelligence/all.json"
    )

    assert root_ids == day_ids == set(selected)
    assert world_html == world_json == {generated.arxiv_id}
    assert video_html == video_json == {generated.arxiv_id}
    assert spatial_html == spatial_json == {fallback.arxiv_id}
    assert set(
        re.findall(
            r"https://arxiv\.org/abs/(\d{4}\.\d{4,5})",
            (tmp_path / "topics/world-models/README.md").read_text(
                encoding="utf-8"
            ),
        )
    ) == world_html
    assert _html_ids(tmp_path / "site/topics/efficient-ai/index.html") == set()
    assert "August 20, 2026" in (
        tmp_path / "site/index.html"
    ).read_text(encoding="utf-8")
    assert "2 papers" in (
        tmp_path / "site/days/2026-08-20.html"
    ).read_text(encoding="utf-8")
