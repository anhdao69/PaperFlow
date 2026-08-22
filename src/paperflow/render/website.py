"""Static full-history PaperFlow website renderer."""

from __future__ import annotations

import posixpath
from pathlib import Path, PurePosixPath

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from paperflow.render.contracts import PublicPaper, resolve_publication_url
from paperflow.render.view_models import (
    DayProjection,
    PublicProjection,
)
from paperflow.taxonomy import TaxonomyConfig

_TEMPLATE_ROOT = Path(__file__).parent / "templates/site"


def render_website_files(
    projection: PublicProjection, taxonomy: TaxonomyConfig
) -> dict[PurePosixPath, str]:
    """Render every full-history website route from the shared projection."""
    environment = Environment(
        loader=FileSystemLoader(_TEMPLATE_ROOT),
        undefined=StrictUndefined,
        autoescape=select_autoescape(enabled_extensions=("html", "j2")),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
        newline_sequence="\n",
    )
    template = environment.get_template("page.html.j2")
    files: dict[PurePosixPath, str] = {}

    root_path = PurePosixPath("site/index.html")
    files[root_path] = _render_page(
        template,
        source_path=root_path,
        projection=projection,
        taxonomy=taxonomy,
        heading="Research worth returning to",
        subtitle=(
            f"{len(projection.papers)} selected papers across "
            f"{len(projection.days)} successful feed days."
        ),
        days=projection.days,
        section_links=(),
    )

    for day in projection.days:
        day_path = PurePosixPath("site/days", f"{day.date}.html")
        files[day_path] = _render_page(
            template,
            source_path=day_path,
            projection=projection,
            taxonomy=taxonomy,
            heading=_date_label(day.date),
            subtitle=f"{len(day.papers)} {_paper_word(len(day.papers))} in this feed.",
            days=(day,),
            section_links=(),
        )

    for topic in projection.topics:
        topic_path = PurePosixPath("site/topics", topic.id, "index.html")
        section_links = tuple(
            {
                "name": subtopic.name,
                "count": subtopic.paper_count,
                "href": _relative_href(
                    topic_path,
                    PurePosixPath(
                        "site/topics", topic.id, f"{subtopic.id}.html"
                    ),
                ),
            }
            for subtopic in topic.subtopics
        )
        files[topic_path] = _render_page(
            template,
            source_path=topic_path,
            projection=projection,
            taxonomy=taxonomy,
            heading=topic.name,
            subtitle=f"{topic.paper_count} {_paper_word(topic.paper_count)} total.",
            days=topic.days,
            section_links=section_links,
        )
        for subtopic in topic.subtopics:
            subtopic_path = PurePosixPath(
                "site/topics", topic.id, f"{subtopic.id}.html"
            )
            files[subtopic_path] = _render_page(
                template,
                source_path=subtopic_path,
                projection=projection,
                taxonomy=taxonomy,
                heading=subtopic.name,
                subtitle=(
                    f"{subtopic.paper_count} "
                    f"{_paper_word(subtopic.paper_count)} total in {topic.name}."
                ),
                days=subtopic.days,
                section_links=(
                    {
                        "name": topic.name,
                        "count": topic.paper_count,
                        "href": _relative_href(subtopic_path, topic_path),
                    },
                ),
            )

    files[PurePosixPath("site/assets/style.css")] = (
        _TEMPLATE_ROOT / "style.css"
    ).read_text(encoding="utf-8")
    return files


def _render_page(
    template,
    *,
    source_path: PurePosixPath,
    projection: PublicProjection,
    taxonomy: TaxonomyConfig,
    heading: str,
    subtitle: str,
    days: tuple[DayProjection, ...],
    section_links: tuple[dict[str, object], ...],
) -> str:
    topic_links = tuple(
        {
            "name": topic.name,
            "href": _relative_href(
                source_path,
                PurePosixPath("site/topics", topic.id, "index.html"),
            ),
        }
        for topic in projection.topics
    )
    day_context = tuple(
        {
            "date": day.date.isoformat(),
            "label": _date_label(day.date),
            "paper_count": len(day.papers),
            "href": _relative_href(
                source_path,
                PurePosixPath("site/days", f"{day.date}.html"),
            ),
            "papers": tuple(
                _paper_context(paper, projection.base_url, taxonomy)
                for paper in day.papers
            ),
        }
        for day in days
    )
    return template.render(
        page_title=heading,
        heading=heading,
        subtitle=subtitle,
        home_href=_relative_href(source_path, PurePosixPath("site/index.html")),
        stylesheet_href=_relative_href(
            source_path, PurePosixPath("site/assets/style.css")
        ),
        topic_links=topic_links,
        section_links=section_links,
        days=day_context,
    )


def _paper_context(
    paper: PublicPaper,
    base_url: str,
    taxonomy: TaxonomyConfig,
) -> dict[str, object]:
    return {
        "paper": paper,
        "topic_labels": _topic_labels(paper, taxonomy),
        "uses_fallback": paper.tldr is None,
        "hero_src": (
            resolve_publication_url(base_url, paper.hero_figure)
            if paper.hero_figure is not None
            else None
        ),
        "figure_label": (
            "Figure unavailable"
            if paper.figure_status.value == "failed"
            else "Figure preview coming later"
        ),
    }


def _topic_labels(
    paper: PublicPaper, taxonomy: TaxonomyConfig
) -> tuple[str, ...]:
    assignments = {
        assignment.topic_id: assignment for assignment in paper.topic_assignments
    }
    labels: list[str] = []
    for topic in taxonomy.topics:
        assignment = assignments.get(topic.id)
        if assignment is None:
            continue
        labels.append(topic.name)
        assigned_subtopics = set(assignment.subtopic_ids)
        labels.extend(
            subtopic.name
            for subtopic in topic.subtopics
            if subtopic.id in assigned_subtopics
        )
    return tuple(labels)


def _relative_href(source: PurePosixPath, target: PurePosixPath) -> str:
    return posixpath.relpath(str(target), start=str(source.parent))


def _date_label(value) -> str:
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def _paper_word(count: int) -> str:
    return "paper" if count == 1 else "papers"
