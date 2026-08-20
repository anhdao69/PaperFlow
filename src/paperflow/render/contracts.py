"""Strict V1 public JSON contracts shared by every producer and consumer."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Literal
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AnyHttpUrl,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from paperflow.models import (
    DomainModel,
    FigureStatus,
    NonEmptyText,
    SummaryStatus,
    TaxonomyId,
    TopicAssignment,
    require_aware_datetime,
    validate_canonical_arxiv_id,
)
from paperflow.taxonomy import TaxonomyConfig, validate_assignments

RelativePublicationPath = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]
_PATH_CHARACTERS = re.compile(r"^[A-Za-z0-9._~!$&'()*+,;=:@%/-]+$")
_INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")


def validate_relative_publication_path(value: str) -> str:
    parsed = urlsplit(value)
    if (
        value.startswith("/")
        or "\\" in value
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or any(segment in {"", ".", ".."} for segment in parsed.path.split("/"))
        or not _PATH_CHARACTERS.fullmatch(value)
        or _INVALID_PERCENT_ESCAPE.search(value)
    ):
        raise ValueError("URL must be a safe publication-root-relative path")
    return value


def validate_publication_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or not parsed.path.endswith("/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("publication base URL must be an HTTPS directory URL")
    return value


def resolve_publication_url(base_url: str, relative_path: str) -> str:
    """Resolve one validated relative URL against the publication root exactly once."""
    validate_publication_base_url(base_url)
    validate_relative_publication_path(relative_path)
    return urljoin(base_url, relative_path)


class PublicPaper(DomainModel):
    arxiv_id: str
    title: NonEmptyText
    authors: list[NonEmptyText] = Field(min_length=1)
    abstract: NonEmptyText
    arxiv_url: AnyHttpUrl
    pdf_url: AnyHttpUrl
    first_seen_at: datetime
    categories: list[NonEmptyText] = Field(min_length=1)
    relevance: int = Field(ge=1, le=10)
    novelty: int = Field(ge=1, le=10)
    topic_assignments: list[TopicAssignment] = Field(min_length=1)
    selection_reason: NonEmptyText
    tldr: NonEmptyText | None = None
    bullets: list[NonEmptyText] = Field(default_factory=list, max_length=5)
    summary_status: SummaryStatus
    hero_figure: RelativePublicationPath | None = None
    figure_status: FigureStatus

    _validate_arxiv_id = field_validator("arxiv_id")(validate_canonical_arxiv_id)
    _validate_first_seen_at = field_validator("first_seen_at")(
        require_aware_datetime
    )

    @field_validator("arxiv_url", "pdf_url")
    @classmethod
    def require_https_source_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.scheme != "https":
            raise ValueError("public source links must use HTTPS")
        return value

    @field_validator("authors", "categories")
    @classmethod
    def require_unique_public_lists(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("public paper list values must be unique")
        return value

    @field_validator("hero_figure")
    @classmethod
    def require_safe_hero_path(cls, value: str | None) -> str | None:
        return (
            validate_relative_publication_path(value)
            if value is not None
            else None
        )

    @model_validator(mode="after")
    def validate_summary_and_figure(self) -> PublicPaper:
        if self.summary_status == SummaryStatus.GENERATED:
            if self.tldr is None or not 3 <= len(self.bullets) <= 5:
                raise ValueError(
                    "generated public summary requires TL;DR and 3-5 bullets"
                )
        elif self.tldr is not None or self.bullets:
            raise ValueError("failed/pending public summary uses abstract fallback")
        if self.figure_status == FigureStatus.READY:
            if self.hero_figure is None:
                raise ValueError("ready public figure requires hero_figure")
        elif self.hero_figure is not None:
            raise ValueError("non-ready public figure must have hero_figure=null")
        return self

    @property
    def display_summary(self) -> str:
        return self.tldr if self.tldr is not None else self.abstract


class FeedDay(DomainModel):
    date: date
    paper_count: int = Field(ge=0)
    feed_url: RelativePublicationPath

    _validate_feed_url = field_validator("feed_url")(
        validate_relative_publication_path
    )


class FeedIndex(DomainModel):
    schema_version: Literal[1] = 1
    generated_at: datetime
    timezone: NonEmptyText
    total_paper_count: int = Field(ge=0)
    day_count: int = Field(ge=0)
    days: list[FeedDay]

    _validate_generated_at = field_validator("generated_at")(
        require_aware_datetime
    )

    @field_validator("timezone")
    @classmethod
    def require_iana_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"unknown IANA timezone: {value}") from error
        return value

    @model_validator(mode="after")
    def validate_counts_and_order(self) -> FeedIndex:
        if self.day_count != len(self.days):
            raise ValueError("day_count must equal days length")
        if self.total_paper_count != sum(day.paper_count for day in self.days):
            raise ValueError("total_paper_count must equal daily membership")
        dates = [day.date for day in self.days]
        if dates != sorted(set(dates), reverse=True):
            raise ValueError("feed-index days must be unique and newest first")
        return self


class DailyFeed(DomainModel):
    schema_version: Literal[1] = 1
    date: date
    paper_count: int = Field(ge=0)
    papers: list[PublicPaper]

    @model_validator(mode="after")
    def validate_membership(self) -> DailyFeed:
        if self.paper_count != len(self.papers):
            raise ValueError("paper_count must equal papers length")
        _validate_public_paper_order(self.papers)
        if any(paper.first_seen_at.date() != self.date for paper in self.papers):
            raise ValueError("daily-feed paper date must match feed date")
        return self


class PublicSubtopic(DomainModel):
    id: TaxonomyId
    name: NonEmptyText
    paper_count: int = Field(ge=0)
    feed_url: RelativePublicationPath

    _validate_feed_url = field_validator("feed_url")(
        validate_relative_publication_path
    )


class PublicTopic(DomainModel):
    id: TaxonomyId
    name: NonEmptyText
    paper_count: int = Field(ge=0)
    feed_url: RelativePublicationPath
    subtopics: list[PublicSubtopic]

    _validate_feed_url = field_validator("feed_url")(
        validate_relative_publication_path
    )

    @model_validator(mode="after")
    def validate_unique_subtopics(self) -> PublicTopic:
        identifiers = [subtopic.id for subtopic in self.subtopics]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("topic subtopic IDs must be unique")
        return self


class TopicsIndex(DomainModel):
    schema_version: Literal[1] = 1
    taxonomy_version: int = Field(ge=1)
    total_paper_count: int = Field(ge=0)
    topics: list[PublicTopic]

    @model_validator(mode="after")
    def validate_unique_topics(self) -> TopicsIndex:
        identifiers = [topic.id for topic in self.topics]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("topic IDs must be unique")
        return self


class TopicFeedDay(DomainModel):
    date: date
    paper_count: int = Field(ge=0)
    papers: list[PublicPaper]

    @model_validator(mode="after")
    def validate_membership(self) -> TopicFeedDay:
        if self.paper_count != len(self.papers):
            raise ValueError("topic day paper_count must equal papers length")
        _validate_public_paper_order(self.papers)
        if any(paper.first_seen_at.date() != self.date for paper in self.papers):
            raise ValueError("topic-feed paper date must match group date")
        return self


class TopicFeed(DomainModel):
    schema_version: Literal[1] = 1
    topic_id: TaxonomyId
    subtopic_id: TaxonomyId | None = None
    total_paper_count: int = Field(ge=0)
    days: list[TopicFeedDay]

    @model_validator(mode="after")
    def validate_counts_order_and_identity(self) -> TopicFeed:
        if self.total_paper_count != sum(day.paper_count for day in self.days):
            raise ValueError("topic total_paper_count must equal daily membership")
        dates = [day.date for day in self.days]
        if dates != sorted(set(dates), reverse=True):
            raise ValueError("topic-feed days must be unique and newest first")
        paper_ids = [paper.arxiv_id for day in self.days for paper in day.papers]
        if len(paper_ids) != len(set(paper_ids)):
            raise ValueError("topic feed cannot repeat a canonical paper")
        return self


def validate_topics_contract(
    contract: TopicsIndex, taxonomy: TaxonomyConfig
) -> None:
    """Require the public hierarchy to mirror configured taxonomy exactly."""
    expected_topics = [topic.id for topic in taxonomy.topics]
    actual_topics = [topic.id for topic in contract.topics]
    if actual_topics != expected_topics:
        raise ValueError("topics contract must mirror configured topic order")
    for public_topic, configured_topic in zip(
        contract.topics, taxonomy.topics, strict=True
    ):
        if public_topic.name != configured_topic.name:
            raise ValueError("topics contract names must match configured taxonomy")
        if public_topic.feed_url != (
            f"data/topic_feeds/{configured_topic.id}/all.json"
        ):
            raise ValueError("topic feed_url must be explicit and canonical")
        expected_subtopics = [item.id for item in configured_topic.subtopics]
        actual_subtopics = [item.id for item in public_topic.subtopics]
        if actual_subtopics != expected_subtopics:
            raise ValueError(
                "topics contract must mirror configured subtopic order"
            )
        if any(
            public.name != configured.name
            for public, configured in zip(
                public_topic.subtopics,
                configured_topic.subtopics,
                strict=True,
            )
        ):
            raise ValueError("subtopic names must match configured taxonomy")
        if any(
            public.feed_url
            != (
                f"data/topic_feeds/{configured_topic.id}/"
                f"{configured.id}.json"
            )
            for public, configured in zip(
                public_topic.subtopics,
                configured_topic.subtopics,
                strict=True,
            )
        ):
            raise ValueError("subtopic feed_url must be explicit and canonical")


def validate_topic_feed_contract(
    contract: TopicFeed, taxonomy: TaxonomyConfig
) -> None:
    """Validate feed identity, child relation, and every projected membership."""
    taxonomy.topic(contract.topic_id)
    if contract.subtopic_id is not None and not taxonomy.is_child(
        contract.topic_id, contract.subtopic_id
    ):
        raise ValueError("topic feed subtopic is not a child of topic_id")
    for day in contract.days:
        for paper in day.papers:
            validate_assignments(taxonomy, paper.topic_assignments)
            matching = next(
                (
                    assignment
                    for assignment in paper.topic_assignments
                    if assignment.topic_id == contract.topic_id
                ),
                None,
            )
            if matching is None:
                raise ValueError("topic feed contains a paper outside topic membership")
            if (
                contract.subtopic_id is not None
                and contract.subtopic_id not in matching.subtopic_ids
            ):
                raise ValueError(
                    "subtopic feed contains a paper outside subtopic membership"
                )


def _validate_public_paper_order(papers: list[PublicPaper]) -> None:
    identities = [paper.arxiv_id for paper in papers]
    if len(identities) != len(set(identities)):
        raise ValueError("public paper IDs must be unique within a collection")
    expected = sorted(
        papers,
        key=lambda paper: (paper.first_seen_at, paper.arxiv_id),
        reverse=True,
    )
    if papers != expected:
        raise ValueError("public papers must use stable newest-first ordering")
