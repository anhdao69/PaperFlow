"""Deterministic Markdown rendering from the shared public projection."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from paperflow.generated_files import GENERATED_FILE_MARKER
from paperflow.render.contracts import PublicPaper
from paperflow.render.view_models import PublicProjection
from paperflow.taxonomy import TaxonomyConfig

PAPER_TABLE_HEADER = """\
| Date | Paper | Topics | TL;DR | Rel. | Nov. |
|---|---|---|---|---:|---:|
"""


def md_escape(value: str) -> str:
    """Escape text for a Markdown table cell or link label."""
    normalized = " ".join(value.split())
    return re.sub(r"([\\|\[\]])", r"\\\1", normalized)


def compact_abstract_fallback(abstract: str, *, limit: int = 240) -> str:
    normalized = " ".join(abstract.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def render_paper_row(paper: PublicPaper, taxonomy: TaxonomyConfig) -> str:
    title = md_escape(paper.title)
    labels = md_escape(_display_topic_labels(paper, taxonomy))
    summary = md_escape(
        paper.tldr or compact_abstract_fallback(paper.abstract)
    )
    return (
        f"| {paper.first_seen_at.date()} "
        f"| [{title}]({paper.arxiv_url}) "
        f"| {labels} "
        f"| {summary} "
        f"| {paper.relevance} "
        f"| {paper.novelty} |"
    )


def render_markdown_files(
    projection: PublicProjection,
    taxonomy: TaxonomyConfig,
    *,
    readme_latest_limit: int,
) -> dict[PurePosixPath, str]:
    """Render root, daily, and complete taxonomy Markdown trees."""
    if readme_latest_limit < 1:
        raise ValueError("README latest limit must be positive")
    files: dict[PurePosixPath, str] = {
        PurePosixPath("README.md"): _render_root(
            projection, taxonomy, readme_latest_limit
        )
    }
    for day in projection.days:
        files[PurePosixPath("daily", f"{day.date}.md")] = _render_daily(
            day.date.isoformat(), day.papers, taxonomy
        )
    for topic in projection.topics:
        files[PurePosixPath("topics", topic.id, "README.md")] = _render_view(
            title=topic.name,
            papers=tuple(paper for day in topic.days for paper in day.papers),
            taxonomy=taxonomy,
            count_label=f"{topic.paper_count} papers total",
        )
        for subtopic in topic.subtopics:
            files[
                PurePosixPath("topics", topic.id, f"{subtopic.id}.md")
            ] = _render_view(
                title=subtopic.name,
                papers=tuple(
                    paper for day in subtopic.days for paper in day.papers
                ),
                taxonomy=taxonomy,
                count_label=f"{subtopic.paper_count} papers total",
            )
    return files


def _render_root(
    projection: PublicProjection,
    taxonomy: TaxonomyConfig,
    limit: int,
) -> str:
    lines = [GENERATED_FILE_MARKER.rstrip(), "", "# PaperFlow", "", "## Topics", ""]
    for topic in taxonomy.topics:
        lines.append(f"- [{md_escape(topic.name)}](topics/{topic.id}/README.md)")
        lines.extend(
            f"  - [{md_escape(subtopic.name)}]"
            f"(topics/{topic.id}/{subtopic.id}.md)"
            for subtopic in topic.subtopics
        )
    visible = projection.papers[:limit]
    lines.extend(
        [
            "",
            "## Latest selected papers",
            "",
            f"Showing {len(visible)} of {len(projection.papers)} selected papers.",
            "",
        ]
    )
    lines.extend(_table_or_empty(visible, taxonomy))
    return "\n".join(lines).rstrip() + "\n"


def _render_daily(
    day: str, papers: tuple[PublicPaper, ...], taxonomy: TaxonomyConfig
) -> str:
    lines = [
        GENERATED_FILE_MARKER.rstrip(),
        "",
        f"# PaperFlow — {day}",
        "",
    ]
    if papers:
        lines.extend([f"**Papers kept: {len(papers)}**", ""])
        lines.extend(_table_or_empty(papers, taxonomy))
    else:
        lines.append("_No papers matched the configured research interests today._")
    return "\n".join(lines).rstrip() + "\n"


def _render_view(
    *,
    title: str,
    papers: tuple[PublicPaper, ...],
    taxonomy: TaxonomyConfig,
    count_label: str,
) -> str:
    lines = [
        GENERATED_FILE_MARKER.rstrip(),
        "",
        f"# {md_escape(title)}",
        "",
        f"**{count_label}**",
        "",
    ]
    lines.extend(_table_or_empty(papers, taxonomy))
    return "\n".join(lines).rstrip() + "\n"


def _table_or_empty(
    papers: tuple[PublicPaper, ...], taxonomy: TaxonomyConfig
) -> list[str]:
    if not papers:
        return ["_No matching papers yet._"]
    return [
        PAPER_TABLE_HEADER.rstrip(),
        *(render_paper_row(paper, taxonomy) for paper in papers),
    ]


def _display_topic_labels(paper: PublicPaper, taxonomy: TaxonomyConfig) -> str:
    labels: list[str] = []
    assignments = {
        assignment.topic_id: assignment for assignment in paper.topic_assignments
    }
    for topic in taxonomy.topics:
        assignment = assignments.get(topic.id)
        if assignment is None:
            continue
        selected_subtopics = set(assignment.subtopic_ids)
        children = [
            subtopic.name
            for subtopic in topic.subtopics
            if subtopic.id in selected_subtopics
        ]
        labels.append(
            f"{topic.name}: {', '.join(children)}" if children else topic.name
        )
    return "; ".join(labels)
