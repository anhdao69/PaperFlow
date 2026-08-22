"""Shared typed domain models."""

from __future__ import annotations

import re
from datetime import date, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

TaxonomyId = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]*$", min_length=1),
]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]

_CANONICAL_ARXIV_ID = re.compile(
    r"^(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})$"
)


class DomainModel(BaseModel):
    """Strict base model for canonical PaperFlow domain data."""

    model_config = ConfigDict(extra="forbid")


class MovedFrom(DomainModel):
    topic_id: TaxonomyId


class SubtopicConfig(DomainModel):
    id: TaxonomyId
    name: NonEmptyText
    short_name: NonEmptyText | None = None
    description: NonEmptyText
    include: list[NonEmptyText] = Field(default_factory=list)
    exclude: list[NonEmptyText] = Field(default_factory=list)
    previous_ids: list[TaxonomyId] = Field(default_factory=list)
    moved_from: MovedFrom | None = None

    @field_validator("include", "exclude", "previous_ids")
    @classmethod
    def require_unique_values(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("values must be unique")
        return value


class TopicConfig(DomainModel):
    id: TaxonomyId
    name: NonEmptyText
    icon: NonEmptyText = "square.grid.2x2.fill"
    short_name: NonEmptyText | None = None
    description: NonEmptyText
    subtopics: list[SubtopicConfig] = Field(default_factory=list)
    previous_ids: list[TaxonomyId] = Field(default_factory=list)

    @field_validator("previous_ids")
    @classmethod
    def require_unique_previous_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("previous_ids must be unique")
        return value


class TopicAssignment(DomainModel):
    topic_id: TaxonomyId
    subtopic_ids: list[TaxonomyId] = Field(default_factory=list)

    @field_validator("subtopic_ids")
    @classmethod
    def require_unique_subtopics(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("subtopic_ids must be unique")
        return value


class FilterResult(DomainModel):
    arxiv_id: str
    keep: bool
    relevance: int = Field(ge=1, le=10)
    novelty: int = Field(ge=1, le=10)
    assignments: list[TopicAssignment]
    reason: NonEmptyText

    @field_validator("arxiv_id")
    @classmethod
    def require_canonical_arxiv_id(cls, value: str) -> str:
        if not _CANONICAL_ARXIV_ID.fullmatch(value):
            raise ValueError("arxiv_id must be a canonical versionless arXiv ID")
        return value

    @model_validator(mode="after")
    def validate_decision(self) -> FilterResult:
        if self.keep and not self.assignments:
            raise ValueError("KEEP requires at least one topic assignment")
        if not self.keep and self.assignments:
            raise ValueError("DROP requires empty topic assignments")
        return self


class FilterBatchResponse(DomainModel):
    results: list[FilterResult]


class SummaryContent(DomainModel):
    tldr: NonEmptyText
    bullets: list[NonEmptyText] = Field(min_length=3, max_length=5)
    problem: NonEmptyText | None = None
    method: NonEmptyText | None = None
    contribution: NonEmptyText | None = None


class SummaryResult(SummaryContent):
    arxiv_id: str

    @field_validator("arxiv_id")
    @classmethod
    def require_canonical_arxiv_id(cls, value: str) -> str:
        if not _CANONICAL_ARXIV_ID.fullmatch(value):
            raise ValueError("arxiv_id must be a canonical versionless arXiv ID")
        return value


class FilterStatus(StrEnum):
    KEPT = "kept"
    DROPPED = "dropped"
    FAILED = "failed"


class SummaryStatus(StrEnum):
    PENDING = "pending"
    GENERATED = "generated"
    FAILED = "failed"


class FigureStatus(StrEnum):
    NOT_IMPLEMENTED = "not_implemented"
    READY = "ready"
    FAILED = "failed"


class FigureAsset(DomainModel):
    """One published scientific figure or table crop."""

    figure_id: NonEmptyText
    figure_number: str | None = None
    kind: Literal["figure", "table"]
    page: int = Field(ge=1)
    caption: str | None = None
    image_path: NonEmptyText
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    @field_validator("image_path")
    @classmethod
    def require_safe_publication_path(cls, value: str) -> str:
        parsed = urlsplit(value)
        candidate = PurePosixPath(value)
        if (
            candidate.is_absolute()
            or ".." in candidate.parts
            or "\\" in value
            or parsed.scheme
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or not candidate.parts
        ):
            raise ValueError("figure image_path must be publication-root relative")
        return value


class AnnounceType(StrEnum):
    NEW = "new"
    CROSS = "cross"
    REPLACE = "replace"


def validate_canonical_arxiv_id(value: str) -> str:
    if not _CANONICAL_ARXIV_ID.fullmatch(value):
        raise ValueError("arxiv_id must be a canonical versionless arXiv ID")
    return value


class RawArxivEntry(DomainModel):
    source_arxiv_id: NonEmptyText
    title: NonEmptyText
    abstract: NonEmptyText
    authors: list[NonEmptyText] = Field(min_length=1)
    categories: list[NonEmptyText] = Field(min_length=1)
    announce_type: AnnounceType


class CandidatePaper(DomainModel):
    arxiv_id: str
    source_arxiv_id: NonEmptyText
    title: NonEmptyText
    abstract: NonEmptyText
    authors: list[NonEmptyText] = Field(min_length=1)
    categories: list[NonEmptyText] = Field(min_length=1)
    arxiv_url: AnyHttpUrl
    pdf_url: AnyHttpUrl

    _validate_arxiv_id = field_validator("arxiv_id")(validate_canonical_arxiv_id)

    @field_validator("authors", "categories")
    @classmethod
    def require_unique_candidate_values(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("candidate list values must be unique")
        return value


class LLMCallResult[StructuredOutputT: BaseModel](DomainModel):
    parsed: StructuredOutputT
    requested_model: NonEmptyText
    actual_model: str | None = None
    provider: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    latency_ms: int = Field(ge=0)
    request_id: str | None = None
    attempt: int = Field(ge=1)


def require_aware_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a timezone offset")
    return value


class ScreeningEvent(DomainModel):
    event_id: UUID
    run_id: NonEmptyText
    arxiv_id: str
    observed_at: datetime
    abstract_hash: Sha256
    filter_status: FilterStatus
    attempt_number: int = Field(ge=1)
    relevance: int | None = Field(default=None, ge=1, le=10)
    novelty: int | None = Field(default=None, ge=1, le=10)
    topic_assignments: list[TopicAssignment] = Field(default_factory=list)
    reason: NonEmptyText | None = None
    taxonomy_version: int = Field(ge=1)
    taxonomy_hash: Sha256
    filter_prompt_version: NonEmptyText
    filter_prompt_hash: Sha256
    requested_model: str | None = None
    actual_model: str | None = None
    provider: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    next_retry_at: datetime | None = None
    retry_exhausted: bool = False

    _validate_arxiv_id = field_validator("arxiv_id")(validate_canonical_arxiv_id)
    _validate_observed_at = field_validator("observed_at")(require_aware_datetime)
    _validate_next_retry_at = field_validator("next_retry_at")(require_aware_datetime)

    @model_validator(mode="after")
    def validate_outcome(self) -> ScreeningEvent:
        if self.filter_status == FilterStatus.KEPT:
            if self.relevance is None or self.novelty is None:
                raise ValueError("KEPT requires relevance and novelty")
            if not self.topic_assignments:
                raise ValueError("KEPT requires at least one topic assignment")
            if self.reason is None:
                raise ValueError("KEPT requires a selection reason")
        elif self.filter_status == FilterStatus.DROPPED:
            if self.relevance is None or self.novelty is None:
                raise ValueError("DROPPED requires relevance and novelty")
            if self.topic_assignments:
                raise ValueError("DROPPED requires empty topic assignments")
            if self.reason is None:
                raise ValueError("DROPPED requires a reason")
        else:
            if self.topic_assignments:
                raise ValueError("FAILED requires empty topic assignments")
            if not self.error_type or not self.error_message:
                raise ValueError("FAILED requires error_type and error_message")

        if self.filter_status != FilterStatus.FAILED and (
            any(
                value is not None
                for value in (self.error_type, self.error_message, self.next_retry_at)
            )
            or self.retry_exhausted
        ):
            raise ValueError("only FAILED events may contain retry/error state")
        if self.retry_exhausted and self.next_retry_at is not None:
            raise ValueError("retry-exhausted events cannot have next_retry_at")
        return self


class SelectedPaper(DomainModel):
    arxiv_id: str
    source_arxiv_id: NonEmptyText
    title: NonEmptyText
    abstract: NonEmptyText
    authors: list[NonEmptyText] = Field(min_length=1)
    categories: list[NonEmptyText] = Field(min_length=1)
    arxiv_url: AnyHttpUrl
    pdf_url: AnyHttpUrl
    first_seen_at: datetime
    first_seen_date: date
    filter_status: Literal[FilterStatus.KEPT]
    relevance: int = Field(ge=1, le=10)
    novelty: int = Field(ge=1, le=10)
    topic_assignments: list[TopicAssignment] = Field(min_length=1)
    selection_reason: NonEmptyText
    summary_status: SummaryStatus
    tldr: NonEmptyText | None = None
    bullets: list[NonEmptyText] = Field(default_factory=list, max_length=5)
    problem: NonEmptyText | None = None
    method: NonEmptyText | None = None
    contribution: NonEmptyText | None = None
    hero_figure: str | None = None
    figures: list[FigureAsset] = Field(default_factory=list)
    figure_status: FigureStatus
    taxonomy_version: int = Field(ge=1)
    taxonomy_hash: Sha256
    filter_prompt_version: NonEmptyText
    filter_prompt_hash: Sha256
    summary_prompt_version: NonEmptyText
    summary_prompt_hash: Sha256
    filter_model: NonEmptyText
    summary_model: str | None = None

    _validate_arxiv_id = field_validator("arxiv_id")(validate_canonical_arxiv_id)
    _validate_first_seen_at = field_validator("first_seen_at")(require_aware_datetime)

    @field_validator("authors", "categories")
    @classmethod
    def require_unique_list_values(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("list values must be unique")
        return value

    @model_validator(mode="after")
    def validate_summary_and_figure_state(self) -> SelectedPaper:
        if self.first_seen_at.date() != self.first_seen_date:
            raise ValueError("first_seen_date must match first_seen_at")
        if self.summary_status == SummaryStatus.GENERATED:
            if self.tldr is None or not 3 <= len(self.bullets) <= 5:
                raise ValueError("generated summary requires a TL;DR and 3-5 bullets")
            if self.summary_model is None:
                raise ValueError("generated summary requires summary_model provenance")
        elif any(
            value is not None
            for value in (self.tldr, self.problem, self.method, self.contribution)
        ) or self.bullets:
            raise ValueError("pending/failed summary cannot contain generated content")
        if self.figure_status == FigureStatus.READY:
            if not self.hero_figure:
                raise ValueError("ready figure requires hero_figure")
        elif self.hero_figure is not None or self.figures:
            raise ValueError("non-ready figure must not contain figure assets")
        return self


class SelectedPaperCollection(DomainModel):
    schema_version: Literal[1] = 1
    papers: dict[str, SelectedPaper] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_keys(self) -> SelectedPaperCollection:
        for paper_id, paper in self.papers.items():
            if paper_id != paper.arxiv_id:
                raise ValueError(
                    f"selected-store key {paper_id!r} does not match paper arxiv_id"
                )
        return self


class RunState(DomainModel):
    schema_version: Literal[1] = 1
    last_successful_run_id: str | None = None
    last_successful_at: datetime | None = None
    last_successful_local_date: date | None = None
    taxonomy_hash: Sha256 | None = None
    runtime_config_hash: Sha256 | None = None
    model_config_hash: Sha256 | None = None

    _validate_success_at = field_validator("last_successful_at")(require_aware_datetime)

    @model_validator(mode="after")
    def validate_all_or_empty(self) -> RunState:
        values = (
            self.last_successful_run_id,
            self.last_successful_at,
            self.last_successful_local_date,
            self.taxonomy_hash,
            self.runtime_config_hash,
            self.model_config_hash,
        )
        if any(value is not None for value in values) and any(
            value is None for value in values
        ):
            raise ValueError("run success state must be entirely populated or empty")
        if (
            self.last_successful_at is not None
            and self.last_successful_local_date is not None
            and self.last_successful_at.date() != self.last_successful_local_date
        ):
            raise ValueError("successful local date must match successful timestamp")
        return self


class ModelUsageStats(DomainModel):
    calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    providers: dict[str, int] = Field(default_factory=dict)

    @field_validator("providers")
    @classmethod
    def validate_provider_counts(cls, value: dict[str, int]) -> dict[str, int]:
        if any(not provider.strip() or count < 1 for provider, count in value.items()):
            raise ValueError(
                "provider usage requires non-empty names and positive counts"
            )
        return value


class RunStats(DomainModel):
    """Persisted, public-safe operational counts for one local run date."""

    schema_version: Literal[1] = 1
    run_id: NonEmptyText
    date: date
    source_ok: bool
    fetched: int = Field(ge=0)
    deduplicated: int = Field(ge=0)
    terminal_skipped: int = Field(ge=0)
    failed_backlog_added: int = Field(ge=0)
    screened: int = Field(ge=0)
    kept: int = Field(ge=0)
    dropped: int = Field(ge=0)
    filter_failed: int = Field(ge=0)
    summary_generated: int = Field(ge=0)
    summary_failed: int = Field(ge=0)
    figure_mode: Literal["disabled", "placeholder", "extraction"]
    llm_input_tokens: int = Field(ge=0)
    llm_output_tokens: int = Field(ge=0)
    llm_cached_input_tokens: int = Field(ge=0)
    llm_cost_usd: float = Field(ge=0)
    model_breakdown: dict[str, ModelUsageStats] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_arithmetic(self) -> RunStats:
        if self.deduplicated > self.fetched:
            raise ValueError("deduplicated count cannot exceed fetched count")
        if self.screened != self.kept + self.dropped + self.filter_failed:
            raise ValueError("screened must equal kept + dropped + filter_failed")
        breakdown = tuple(self.model_breakdown.values())
        if self.llm_input_tokens != sum(item.input_tokens for item in breakdown):
            raise ValueError("LLM input-token total does not match model breakdown")
        if self.llm_output_tokens != sum(item.output_tokens for item in breakdown):
            raise ValueError("LLM output-token total does not match model breakdown")
        if self.llm_cached_input_tokens != sum(
            item.cached_input_tokens for item in breakdown
        ):
            raise ValueError("LLM cached-token total does not match model breakdown")
        if abs(self.llm_cost_usd - sum(item.cost_usd for item in breakdown)) > 1e-9:
            raise ValueError("LLM cost total does not match model breakdown")
        return self
