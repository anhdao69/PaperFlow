from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from paperflow.models import FigureStatus, SummaryStatus, TopicAssignment
from paperflow.render.contracts import PublicPaper
from paperflow.render.markdown import (
    PAPER_TABLE_HEADER,
    md_escape,
    render_markdown_files,
    render_paper_row,
)
from paperflow.render.view_models import (
    DayProjection,
    PublicProjection,
    SubtopicProjection,
    TopicProjection,
)
from paperflow.taxonomy import load_taxonomy

ROOT = Path(__file__).parents[3]


def _public(index: int, *, summary: bool = True) -> PublicPaper:
    paper_id = f"2608.{60000 + index:05d}"
    return PublicPaper(
        arxiv_id=paper_id,
        title=f"Paper {index}",
        authors=["Fixture Author"],
        abstract=f"Abstract fallback {index}.",
        arxiv_url=f"https://arxiv.org/abs/{paper_id}",
        pdf_url=f"https://arxiv.org/pdf/{paper_id}",
        first_seen_at=datetime.fromisoformat("2026-08-20T21:00:00-04:00"),
        categories=["cs.AI"],
        relevance=9,
        novelty=8,
        topic_assignments=[TopicAssignment(topic_id="world-models")],
        selection_reason="Relevant fixture.",
        tldr=f"Summary {index}." if summary else None,
        bullets=["One.", "Two.", "Three."] if summary else [],
        summary_status=(
            SummaryStatus.GENERATED if summary else SummaryStatus.FAILED
        ),
        hero_figure=None,
        figure_status=FigureStatus.NOT_IMPLEMENTED,
    )


def _projection(count: int) -> PublicProjection:
    papers = tuple(reversed([_public(index) for index in range(count)]))
    return PublicProjection(
        generated_at=datetime.fromisoformat("2026-08-20T21:05:00-04:00"),
        timezone="America/New_York",
        base_url="https://example.test/PaperFlow/",
        papers=papers,
        days=(),
        topics=(),
        taxonomy_version=1,
    )


@pytest.mark.parametrize("count", [0, 1, 79, 80, 81, 500])
def test_only_root_readme_caps_at_eighty(count: int) -> None:
    rendered = render_markdown_files(
        _projection(count),
        load_taxonomy(ROOT / "configs/topics.yaml"),
        readme_latest_limit=80,
    )[Path("README.md")]

    assert rendered.count("| 2026-08-20 |") == min(count, 80)
    assert f"Showing {min(count, 80)} of {count} selected papers." in rendered


def test_markdown_escaping_handles_tables_links_and_newlines() -> None:
    assert md_escape("A | B\\C\n[D]") == r"A \| B\\C \[D\]"
    paper = _public(1).model_copy(
        update={"title": "A [paper] | result", "tldr": "Line 1\nLine | 2"}
    )

    row = render_paper_row(
        paper, load_taxonomy(ROOT / "configs/topics.yaml")
    )

    assert r"A \[paper\] \| result" in row
    assert r"Line 1 Line \| 2" in row


def test_zero_day_has_explicit_success_message() -> None:
    projection = _projection(0)
    projection = PublicProjection(
        **{
            **projection.__dict__,
            "days": (DayProjection(date(2026, 8, 20), ()),),
        }
    )

    daily = render_markdown_files(
        projection,
        load_taxonomy(ROOT / "configs/topics.yaml"),
        readme_latest_limit=80,
    )[Path("daily/2026-08-20.md")]

    assert "# PaperFlow — 2026-08-20" in daily
    assert "No papers matched" in daily
    assert PAPER_TABLE_HEADER not in daily


def test_empty_configured_topic_and_subtopic_are_generated() -> None:
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")
    topic = taxonomy.topics[-1]
    projection = PublicProjection(
        generated_at=datetime.fromisoformat("2026-08-20T21:05:00-04:00"),
        timezone="America/New_York",
        base_url="https://example.test/PaperFlow/",
        papers=(),
        days=(),
        topics=(
            TopicProjection(
                id=topic.id,
                name=topic.name,
                days=(),
                subtopics=tuple(
                    SubtopicProjection(item.id, item.name, ())
                    for item in topic.subtopics
                ),
            ),
        ),
        taxonomy_version=1,
    )

    files = render_markdown_files(
        projection, taxonomy, readme_latest_limit=80
    )

    topic_root = Path("topics") / topic.id
    subtopic_path = topic_root / f"{topic.subtopics[0].id}.md"
    assert topic_root / "README.md" in files
    assert subtopic_path in files
    assert "0 papers total" in files[topic_root / "README.md"]
    assert "No matching papers yet" in files[
        subtopic_path
    ]


def test_table_header_is_identical_in_root_daily_and_topic_views() -> None:
    paper = _public(1)
    day = DayProjection(paper.first_seen_at.date(), (paper,))
    topic = TopicProjection("world-models", "World Models", (day,), ())
    projection = PublicProjection(
        generated_at=paper.first_seen_at,
        timezone="America/New_York",
        base_url="https://example.test/PaperFlow/",
        papers=(paper,),
        days=(day,),
        topics=(topic,),
        taxonomy_version=1,
    )

    files = render_markdown_files(
        projection,
        load_taxonomy(ROOT / "configs/topics.yaml"),
        readme_latest_limit=80,
    )

    assert files[Path("README.md")].count(PAPER_TABLE_HEADER) == 1
    assert files[Path("daily/2026-08-20.md")].count(PAPER_TABLE_HEADER) == 1
    assert files[Path("topics/world-models/README.md")].count(
        PAPER_TABLE_HEADER
    ) == 1
