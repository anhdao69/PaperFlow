from __future__ import annotations

from datetime import date, datetime
from pathlib import Path, PurePosixPath

from paperflow.models import (
    FigureStatus,
    FilterStatus,
    SelectedPaper,
    SummaryStatus,
    TopicAssignment,
)
from paperflow.render.validation import validate_website_links
from paperflow.render.view_models import build_public_projection
from paperflow.render.website import render_website_files
from paperflow.taxonomy import load_taxonomy

ROOT = Path(__file__).parents[3]
HASH = "7" * 64


def _paper(
    index: int,
    *,
    title: str | None = None,
    summary_status: SummaryStatus = SummaryStatus.GENERATED,
    figure_status: FigureStatus = FigureStatus.NOT_IMPLEMENTED,
) -> SelectedPaper:
    paper_id = f"2608.{90000 + index:05d}"
    seen = datetime.fromisoformat(f"2026-08-20T21:00:{index:02d}-04:00")
    generated = summary_status == SummaryStatus.GENERATED
    return SelectedPaper(
        arxiv_id=paper_id,
        source_arxiv_id=f"{paper_id}v1",
        title=title or f"Website Paper {index}",
        abstract=f"Website abstract fallback {index}.",
        authors=["Website Author"],
        categories=["cs.AI"],
        arxiv_url=f"https://arxiv.org/abs/{paper_id}",
        pdf_url=f"https://arxiv.org/pdf/{paper_id}",
        first_seen_at=seen,
        first_seen_date=seen.date(),
        filter_status=FilterStatus.KEPT,
        relevance=9,
        novelty=8,
        topic_assignments=[
            TopicAssignment(
                topic_id="world-models", subtopic_ids=["video-world-models"]
            )
        ],
        selection_reason="Website fixture.",
        summary_status=summary_status,
        tldr=f"Website summary {index}." if generated else None,
        bullets=["Problem.", "Method.", "Contribution."] if generated else [],
        hero_figure=(
            f"figures/{paper_id}/hero.webp"
            if figure_status == FigureStatus.READY
            else None
        ),
        figure_status=figure_status,
        taxonomy_version=1,
        taxonomy_hash=HASH,
        filter_prompt_version="filter-v3",
        filter_prompt_hash=HASH,
        summary_prompt_version="summary-v2",
        summary_prompt_hash=HASH,
        filter_model="deepseek/deepseek-v4-flash-0731",
        summary_model="openai/gpt-5.6-luna" if generated else None,
    )


def _render():
    papers = [
        _paper(1, title="Escaped <script>alert(1)</script>"),
        _paper(
            2,
            summary_status=SummaryStatus.FAILED,
            figure_status=FigureStatus.FAILED,
        ),
        _paper(3, figure_status=FigureStatus.READY),
    ]
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")
    projection = build_public_projection(
        {paper.arxiv_id: paper for paper in papers},
        taxonomy,
        generated_at=datetime.fromisoformat("2026-08-20T21:05:00-04:00"),
        timezone="America/New_York",
        base_url="https://example.test/PaperFlow/",
        successful_dates=[date(2026, 8, 19)],
    )
    return render_website_files(projection, taxonomy), projection, taxonomy


def test_routes_derive_from_every_day_topic_and_subtopic() -> None:
    files, projection, taxonomy = _render()
    taxonomy_route_count = len(taxonomy.topics) + sum(
        len(topic.subtopics) for topic in taxonomy.topics
    )

    assert len(files) == 1 + len(projection.days) + taxonomy_route_count + 1
    assert PurePosixPath("site/index.html") in files
    assert PurePosixPath("site/days/2026-08-20.html") in files
    assert PurePosixPath("site/topics/world-models/index.html") in files
    assert PurePosixPath(
        "site/topics/world-models/video-world-models.html"
    ) in files
    assert PurePosixPath("site/assets/style.css") in files


def test_root_and_day_render_full_membership_and_exact_header() -> None:
    files, _, _ = _render()
    root = files[PurePosixPath("site/index.html")]
    day = files[PurePosixPath("site/days/2026-08-20.html")]

    assert root.count('data-arxiv-id="') == 3
    assert day.count('data-arxiv-id="') == 3
    assert "August 20, 2026" in root
    assert "3 papers" in root
    assert "2026-08-19" in root
    assert "No papers matched" in root


def test_html_is_escaped_and_summary_fallback_is_labeled() -> None:
    files, _, _ = _render()
    root = files[PurePosixPath("site/index.html")]

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in root
    assert "<script>alert(1)</script>" not in root
    assert "Website abstract fallback 2." in root
    assert 'class="summary fallback"' in root


def test_figure_states_use_stable_placeholder_or_ready_image() -> None:
    files, _, _ = _render()
    root = files[PurePosixPath("site/index.html")]

    assert "Figure preview coming later" in root
    assert "Figure unavailable" in root
    assert '<img src="../figures/2608.90003/hero.webp"' in root


def test_empty_topic_and_subtopic_pages_are_present() -> None:
    files, _, _ = _render()

    topic = files[PurePosixPath("site/topics/efficient-ai/index.html")]
    subtopic = files[
        PurePosixPath("site/topics/efficient-ai/efficient-attention.html")
    ]
    assert "0 papers total" in topic
    assert "No matching papers yet" in topic
    assert "No matching papers yet" in subtopic


def test_all_internal_links_exist_and_all_routes_are_reachable(
    tmp_path: Path,
) -> None:
    files, _, _ = _render()
    for relative_path, content in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    validate_website_links(tmp_path, files)


def test_website_has_no_readme_limit_dependency() -> None:
    source = (ROOT / "src/paperflow/render/website.py").read_text(encoding="utf-8")

    assert "readme_latest_limit" not in source
    assert "[:80]" not in source
