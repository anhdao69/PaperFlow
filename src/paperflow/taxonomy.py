"""Taxonomy loading, validation, lookup, hashing, and path safety."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from paperflow.atomic import atomic_write_text
from paperflow.config import load_yaml
from paperflow.models import DomainModel, TopicAssignment, TopicConfig

_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class TaxonomyAssignmentError(ValueError):
    """Base error for a structurally valid but unknown taxonomy assignment."""


class UnknownTopicError(TaxonomyAssignmentError):
    """Raised when an assignment names no active topic."""


class DuplicateTopicAssignmentError(TaxonomyAssignmentError):
    """Raised when one paper repeats a parent topic assignment."""


class DuplicateSubtopicError(TaxonomyAssignmentError):
    """Raised when one topic assignment repeats a child ID."""


class InvalidParentChildError(TaxonomyAssignmentError):
    """Raised when a subtopic is unknown or belongs to another topic."""


class TaxonomyConfig(DomainModel):
    """Validated two-level PaperFlow taxonomy in configured display order."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    taxonomy_version: int = Field(ge=1)
    topics: list[TopicConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_global_identity(self) -> TaxonomyConfig:
        active: dict[str, str] = {}
        historical: dict[str, str] = {}

        def register_active(identifier: str, owner: str) -> None:
            if identifier in active:
                raise ValueError(
                    f"active taxonomy ID {identifier!r} is reused by {owner} and "
                    f"{active[identifier]}"
                )
            active[identifier] = owner

        def register_historical(identifier: str, owner: str) -> None:
            if identifier in historical:
                raise ValueError(
                    f"previous ID {identifier!r} is ambiguous between {owner} and "
                    f"{historical[identifier]}"
                )
            historical[identifier] = owner

        for topic in self.topics:
            register_active(topic.id, f"topic {topic.id}")
            for previous_id in topic.previous_ids:
                register_historical(previous_id, f"topic {topic.id}")
            for subtopic in topic.subtopics:
                register_active(subtopic.id, f"subtopic {subtopic.id}")
                for previous_id in subtopic.previous_ids:
                    register_historical(previous_id, f"subtopic {subtopic.id}")

        collisions = set(active) & set(historical)
        if collisions:
            rendered = ", ".join(sorted(collisions))
            raise ValueError(
                f"active IDs cannot also be previous IDs (rename cycle): {rendered}"
            )

        valid_parent_ids = {
            identifier
            for topic in self.topics
            for identifier in [topic.id, *topic.previous_ids]
        }
        for topic in self.topics:
            for subtopic in topic.subtopics:
                moved_from = subtopic.moved_from
                if moved_from is None:
                    continue
                if moved_from.topic_id not in valid_parent_ids:
                    raise ValueError(
                        f"subtopic {subtopic.id!r} moved_from references unknown topic "
                        f"{moved_from.topic_id!r}"
                    )
                if moved_from.topic_id in {topic.id, *topic.previous_ids}:
                    raise ValueError(
                        f"subtopic {subtopic.id!r} cannot move from its active parent"
                    )
        return self

    def topic(self, topic_id: str) -> TopicConfig:
        for topic in self.topics:
            if topic.id == topic_id:
                return topic
        raise KeyError(f"unknown topic ID: {topic_id}")

    def subtopic_parent(self, subtopic_id: str) -> TopicConfig:
        for topic in self.topics:
            if any(subtopic.id == subtopic_id for subtopic in topic.subtopics):
                return topic
        raise KeyError(f"unknown subtopic ID: {subtopic_id}")

    def has_topic(self, topic_id: str) -> bool:
        return any(topic.id == topic_id for topic in self.topics)

    def is_child(self, topic_id: str, subtopic_id: str) -> bool:
        try:
            topic = self.topic(topic_id)
        except KeyError:
            return False
        return any(subtopic.id == subtopic_id for subtopic in topic.subtopics)

    def ordered_topic_ids(self) -> tuple[str, ...]:
        return tuple(topic.id for topic in self.topics)

    def ordered_subtopic_ids(self, topic_id: str) -> tuple[str, ...]:
        return tuple(subtopic.id for subtopic in self.topic(topic_id).subtopics)


def load_taxonomy(path: Path = Path("configs/topics.yaml")) -> TaxonomyConfig:
    """Load and validate one taxonomy YAML file."""
    return TaxonomyConfig.model_validate(load_yaml(path))


def load_taxonomy_snapshot(path: Path) -> TaxonomyConfig | None:
    """Load the last successfully published taxonomy, if one exists."""
    if not path.exists():
        return None
    return TaxonomyConfig.model_validate_json(path.read_text(encoding="utf-8"))


def save_taxonomy_snapshot(path: Path, taxonomy: TaxonomyConfig) -> None:
    """Atomically persist the taxonomy only after publication validation."""
    content = taxonomy.model_dump_json(indent=2) + "\n"
    atomic_write_text(
        path,
        content,
        validator=lambda staged: TaxonomyConfig.model_validate_json(
            staged.read_text(encoding="utf-8")
        ),
    )


def taxonomy_hash(taxonomy: TaxonomyConfig) -> str:
    """Return a deterministic semantic hash while preserving list order."""
    normalized = json.dumps(
        taxonomy.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(normalized).hexdigest()


def safe_taxonomy_path(*identifiers: str) -> PurePosixPath:
    """Build a safe relative path from already validated taxonomy identifiers."""
    if not identifiers or any(not _SAFE_ID.fullmatch(value) for value in identifiers):
        raise ValueError("taxonomy paths require one or more safe taxonomy IDs")
    return PurePosixPath(*identifiers)


def validate_assignments(
    taxonomy: TaxonomyConfig, assignments: Iterable[TopicAssignment]
) -> None:
    """Validate topic assignments against active taxonomy identity and parentage."""
    seen_topics: set[str] = set()
    for assignment in assignments:
        if assignment.topic_id in seen_topics:
            raise DuplicateTopicAssignmentError(
                f"duplicate topic assignment: {assignment.topic_id}"
            )
        seen_topics.add(assignment.topic_id)
        if not taxonomy.has_topic(assignment.topic_id):
            raise UnknownTopicError(
                f"unknown topic assignment: {assignment.topic_id}"
            )
        seen_subtopics: set[str] = set()
        for subtopic_id in assignment.subtopic_ids:
            if subtopic_id in seen_subtopics:
                raise DuplicateSubtopicError(
                    f"duplicate subtopic assignment: {subtopic_id}"
                )
            seen_subtopics.add(subtopic_id)
            if not taxonomy.is_child(assignment.topic_id, subtopic_id):
                raise InvalidParentChildError(
                    f"subtopic {subtopic_id!r} is not a child of "
                    f"{assignment.topic_id!r}"
                )
