"""Single deterministic projection used by all PaperFlow public renderers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from paperflow.models import SelectedPaper, TopicAssignment
from paperflow.render.contracts import (
    DailyFeed,
    FeedDay,
    FeedIndex,
    PublicPaper,
    PublicSubtopic,
    PublicTopic,
    TopicFeed,
    TopicFeedDay,
    TopicsIndex,
    validate_publication_base_url,
)
from paperflow.taxonomy import TaxonomyConfig, validate_assignments


@dataclass(frozen=True)
class DayProjection:
    date: date
    papers: tuple[PublicPaper, ...]


@dataclass(frozen=True)
class SubtopicProjection:
    id: str
    name: str
    days: tuple[DayProjection, ...]

    @property
    def paper_count(self) -> int:
        return sum(len(day.papers) for day in self.days)


@dataclass(frozen=True)
class TopicProjection:
    id: str
    name: str
    days: tuple[DayProjection, ...]
    subtopics: tuple[SubtopicProjection, ...]
    icon: str = "square.grid.2x2.fill"

    @property
    def paper_count(self) -> int:
        return sum(len(day.papers) for day in self.days)


@dataclass(frozen=True)
class PublicProjection:
    generated_at: datetime
    timezone: str
    base_url: str
    papers: tuple[PublicPaper, ...]
    days: tuple[DayProjection, ...]
    topics: tuple[TopicProjection, ...]
    taxonomy_version: int

    def feed_index(self) -> FeedIndex:
        return FeedIndex(
            generated_at=self.generated_at,
            timezone=self.timezone,
            total_paper_count=len(self.papers),
            day_count=len(self.days),
            days=[
                FeedDay(
                    date=day.date,
                    paper_count=len(day.papers),
                    feed_url=f"data/daily_feeds/{day.date.isoformat()}.json",
                )
                for day in self.days
            ],
        )

    def daily_feeds(self) -> Mapping[date, DailyFeed]:
        return {
            day.date: DailyFeed(
                date=day.date,
                paper_count=len(day.papers),
                papers=list(day.papers),
            )
            for day in self.days
        }

    def topics_index(self) -> TopicsIndex:
        return TopicsIndex(
            taxonomy_version=self.taxonomy_version,
            total_paper_count=len(self.papers),
            topics=[
                PublicTopic(
                    id=topic.id,
                    name=topic.name,
                    icon=topic.icon,
                    paper_count=topic.paper_count,
                    feed_url=f"data/topic_feeds/{topic.id}/all.json",
                    subtopics=[
                        PublicSubtopic(
                            id=subtopic.id,
                            name=subtopic.name,
                            paper_count=subtopic.paper_count,
                            feed_url=(
                                f"data/topic_feeds/{topic.id}/{subtopic.id}.json"
                            ),
                        )
                        for subtopic in topic.subtopics
                    ],
                )
                for topic in self.topics
            ],
        )

    def topic_feed(
        self, topic_id: str, subtopic_id: str | None = None
    ) -> TopicFeed:
        try:
            topic = next(item for item in self.topics if item.id == topic_id)
        except StopIteration as error:
            raise KeyError(f"unknown projected topic: {topic_id}") from error
        if subtopic_id is None:
            days = topic.days
        else:
            try:
                subtopic = next(
                    item for item in topic.subtopics if item.id == subtopic_id
                )
            except StopIteration as error:
                raise KeyError(
                    f"unknown projected subtopic {topic_id}/{subtopic_id}"
                ) from error
            days = subtopic.days
        return TopicFeed(
            topic_id=topic.id,
            subtopic_id=subtopic_id,
            total_paper_count=sum(len(day.papers) for day in days),
            days=[
                TopicFeedDay(
                    date=day.date,
                    paper_count=len(day.papers),
                    papers=list(day.papers),
                )
                for day in days
            ],
        )


def build_public_projection(
    selected: Mapping[str, SelectedPaper],
    taxonomy: TaxonomyConfig,
    *,
    generated_at: datetime,
    timezone: str,
    base_url: str,
    successful_dates: Iterable[date] = (),
) -> PublicProjection:
    """Project canonical KEEP records once for JSON, Markdown, web, and iOS."""
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("projection generated_at must be timezone-aware")
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"unknown IANA timezone: {timezone}") from error
    validate_publication_base_url(base_url)
    for key, paper in selected.items():
        if key != paper.arxiv_id:
            raise ValueError("selected mapping key must match canonical arXiv ID")
        validate_assignments(taxonomy, paper.topic_assignments)

    public_papers = tuple(
        sorted(
            (_public_paper(paper, taxonomy) for paper in selected.values()),
            key=lambda paper: (paper.first_seen_at, paper.arxiv_id),
            reverse=True,
        )
    )
    all_dates = set(successful_dates) | {
        paper.first_seen_at.date() for paper in public_papers
    }
    days = tuple(
        DayProjection(
            date=day,
            papers=tuple(
                paper for paper in public_papers if paper.first_seen_at.date() == day
            ),
        )
        for day in sorted(all_dates, reverse=True)
    )

    topics: list[TopicProjection] = []
    for configured_topic in taxonomy.topics:
        topic_papers = tuple(
            paper
            for paper in public_papers
            if any(
                assignment.topic_id == configured_topic.id
                for assignment in paper.topic_assignments
            )
        )
        subtopics = tuple(
            SubtopicProjection(
                id=configured_subtopic.id,
                name=configured_subtopic.name,
                days=_group_nonempty_days(
                    tuple(
                        paper
                        for paper in topic_papers
                        if _has_subtopic(
                            paper,
                            configured_topic.id,
                            configured_subtopic.id,
                        )
                    )
                ),
            )
            for configured_subtopic in configured_topic.subtopics
        )
        topics.append(
            TopicProjection(
                id=configured_topic.id,
                name=configured_topic.name,
                icon=configured_topic.icon,
                days=_group_nonempty_days(topic_papers),
                subtopics=subtopics,
            )
        )
    return PublicProjection(
        generated_at=generated_at,
        timezone=timezone,
        base_url=base_url,
        papers=public_papers,
        days=days,
        topics=tuple(topics),
        taxonomy_version=taxonomy.taxonomy_version,
    )


def _public_paper(paper: SelectedPaper, taxonomy: TaxonomyConfig) -> PublicPaper:
    assignments_by_topic = {
        assignment.topic_id: assignment for assignment in paper.topic_assignments
    }
    ordered_assignments = [
        TopicAssignment(
            topic_id=topic.id,
            subtopic_ids=[
                subtopic.id
                for subtopic in topic.subtopics
                if subtopic.id
                in set(assignments_by_topic[topic.id].subtopic_ids)
            ],
        )
        for topic in taxonomy.topics
        if topic.id in assignments_by_topic
    ]
    return PublicPaper(
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        authors=paper.authors,
        abstract=paper.abstract,
        arxiv_url=paper.arxiv_url,
        pdf_url=paper.pdf_url,
        first_seen_at=paper.first_seen_at,
        categories=paper.categories,
        relevance=paper.relevance,
        novelty=paper.novelty,
        topic_assignments=ordered_assignments,
        selection_reason=paper.selection_reason,
        tldr=paper.tldr,
        bullets=paper.bullets,
        summary_status=paper.summary_status,
        hero_figure=paper.hero_figure,
        figures=paper.figures,
        figure_status=paper.figure_status,
    )


def _group_nonempty_days(papers: tuple[PublicPaper, ...]) -> tuple[DayProjection, ...]:
    dates = sorted({paper.first_seen_at.date() for paper in papers}, reverse=True)
    return tuple(
        DayProjection(
            date=day,
            papers=tuple(
                paper for paper in papers if paper.first_seen_at.date() == day
            ),
        )
        for day in dates
    )


def _has_subtopic(paper: PublicPaper, topic_id: str, subtopic_id: str) -> bool:
    return any(
        assignment.topic_id == topic_id
        and subtopic_id in assignment.subtopic_ids
        for assignment in paper.topic_assignments
    )
