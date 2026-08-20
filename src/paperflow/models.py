"""Shared typed domain models."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

TaxonomyId = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]*$", min_length=1),
]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


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
