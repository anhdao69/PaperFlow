"""Deterministic taxonomy rename and re-parent migration planning."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from paperflow.models import TopicAssignment
from paperflow.taxonomy import TaxonomyConfig, validate_assignments

AssignmentStore = Mapping[str, Sequence[TopicAssignment]]


@dataclass(frozen=True)
class SubtopicMove:
    subtopic_id: str
    old_parent_id: str
    new_parent_id: str


@dataclass(frozen=True)
class TaxonomyMigrationPlan:
    topic_renames: tuple[tuple[str, str], ...]
    subtopic_renames: tuple[tuple[str, str], ...]
    subtopic_moves: tuple[SubtopicMove, ...]

    @property
    def has_changes(self) -> bool:
        return bool(self.topic_renames or self.subtopic_renames or self.subtopic_moves)

    def render(self) -> str:
        """Render a stable human-readable dry-run diff."""
        lines = ["PaperFlow taxonomy migration plan"]
        if not self.has_changes:
            return "\n".join([*lines, "No identity or parent changes."])
        lines.extend(
            f"RENAME topic {old_id} -> {new_id}"
            for old_id, new_id in self.topic_renames
        )
        lines.extend(
            f"RENAME subtopic {old_id} -> {new_id}"
            for old_id, new_id in self.subtopic_renames
        )
        lines.extend(
            f"MOVE subtopic {move.subtopic_id}: "
            f"{move.old_parent_id} -> {move.new_parent_id}"
            for move in self.subtopic_moves
        )
        return "\n".join(lines)


def _previous_subtopic_parents(taxonomy: TaxonomyConfig) -> dict[str, str]:
    return {
        subtopic.id: topic.id
        for topic in taxonomy.topics
        for subtopic in topic.subtopics
    }


def _rename_maps(
    previous: TaxonomyConfig, current: TaxonomyConfig
) -> tuple[dict[str, str], dict[str, str]]:
    previous_topic_ids = {topic.id for topic in previous.topics}
    previous_subtopic_ids = {
        subtopic.id for topic in previous.topics for subtopic in topic.subtopics
    }
    topic_renames = {
        previous_id: topic.id
        for topic in current.topics
        for previous_id in topic.previous_ids
        if previous_id in previous_topic_ids
    }
    subtopic_renames = {
        previous_id: subtopic.id
        for topic in current.topics
        for subtopic in topic.subtopics
        for previous_id in subtopic.previous_ids
        if previous_id in previous_subtopic_ids
    }
    return topic_renames, subtopic_renames


def plan_taxonomy_migrations(
    previous: TaxonomyConfig,
    current: TaxonomyConfig,
    assignments_by_paper: AssignmentStore,
) -> TaxonomyMigrationPlan:
    """Compute and fully validate a rename-then-move plan without mutation."""
    topic_renames, subtopic_renames = _rename_maps(previous, current)
    old_parents = _previous_subtopic_parents(previous)
    moves: list[SubtopicMove] = []

    for destination in current.topics:
        for subtopic in destination.subtopics:
            previous_id_candidates = [
                identifier
                for identifier in [subtopic.id, *subtopic.previous_ids]
                if identifier in old_parents
            ]
            if len(previous_id_candidates) > 1:
                raise ValueError(
                    f"subtopic {subtopic.id!r} has ambiguous prior identities: "
                    f"{', '.join(sorted(previous_id_candidates))}"
                )
            previous_id = (
                previous_id_candidates[0] if previous_id_candidates else None
            )
            previous_parent = old_parents.get(previous_id) if previous_id else None
            moved_from = subtopic.moved_from.topic_id if subtopic.moved_from else None

            if previous_parent is None and moved_from is not None:
                message = (
                    f"subtopic {subtopic.id!r} declares a move but has no prior "
                    "identity"
                )
                raise ValueError(message)
            if previous_parent is None:
                continue

            expected_old_parent = moved_from or previous_parent
            if moved_from is not None and moved_from != previous_parent:
                raise ValueError(
                    f"subtopic {subtopic.id!r} moved_from {moved_from!r}, but its "
                    f"previous parent was {previous_parent!r}"
                )

            resolved_old_parent = topic_renames.get(
                expected_old_parent, expected_old_parent
            )
            if resolved_old_parent != destination.id:
                if moved_from is None:
                    raise ValueError(
                        f"subtopic {subtopic.id!r} changed parent without moved_from"
                    )
                moves.append(
                    SubtopicMove(
                        subtopic_id=subtopic.id,
                        old_parent_id=resolved_old_parent,
                        new_parent_id=destination.id,
                    )
                )

    plan = TaxonomyMigrationPlan(
        topic_renames=tuple(sorted(topic_renames.items())),
        subtopic_renames=tuple(sorted(subtopic_renames.items())),
        subtopic_moves=tuple(
            sorted(
                moves,
                key=lambda move: (
                    move.subtopic_id,
                    move.old_parent_id,
                    move.new_parent_id,
                ),
            )
        ),
    )
    apply_taxonomy_migrations(assignments_by_paper, current, plan)
    return plan


def apply_taxonomy_migrations(
    assignments_by_paper: AssignmentStore,
    current: TaxonomyConfig,
    plan: TaxonomyMigrationPlan,
) -> dict[str, list[TopicAssignment]]:
    """Return migrated copies; inputs remain unchanged on every failure path."""
    topic_renames = dict(plan.topic_renames)
    subtopic_renames = dict(plan.subtopic_renames)
    moves = {
        (move.old_parent_id, move.subtopic_id): move.new_parent_id
        for move in plan.subtopic_moves
    }
    migrated_store: dict[str, list[TopicAssignment]] = {}

    for paper_id in sorted(assignments_by_paper):
        source_assignments = assignments_by_paper[paper_id]
        assignments = [
            TopicAssignment(
                topic_id=topic_renames.get(assignment.topic_id, assignment.topic_id),
                subtopic_ids=[
                    subtopic_renames.get(subtopic_id, subtopic_id)
                    for subtopic_id in assignment.subtopic_ids
                ],
            )
            for assignment in source_assignments
        ]
        emptied_by_move: set[int] = set()

        for assignment in list(assignments):
            for subtopic_id in list(assignment.subtopic_ids):
                new_parent = moves.get((assignment.topic_id, subtopic_id))
                if new_parent is None:
                    continue
                assignment.subtopic_ids.remove(subtopic_id)
                if not assignment.subtopic_ids:
                    emptied_by_move.add(id(assignment))
                target = next(
                    (
                        candidate
                        for candidate in assignments
                        if candidate.topic_id == new_parent
                    ),
                    None,
                )
                if target is None:
                    target = TopicAssignment(topic_id=new_parent, subtopic_ids=[])
                    assignments.append(target)
                if subtopic_id not in target.subtopic_ids:
                    target.subtopic_ids.append(subtopic_id)

        assignments = [
            assignment
            for assignment in assignments
            if id(assignment) not in emptied_by_move
        ]
        assignments = _merge_duplicate_assignments(assignments)
        validate_assignments(current, assignments)
        migrated_store[paper_id] = assignments

    return migrated_store


def _merge_duplicate_assignments(
    assignments: Sequence[TopicAssignment],
) -> list[TopicAssignment]:
    merged: list[TopicAssignment] = []
    by_topic: dict[str, TopicAssignment] = {}
    for assignment in assignments:
        target = by_topic.get(assignment.topic_id)
        if target is None:
            target = TopicAssignment(
                topic_id=assignment.topic_id,
                subtopic_ids=list(assignment.subtopic_ids),
            )
            by_topic[assignment.topic_id] = target
            merged.append(target)
            continue
        for subtopic_id in assignment.subtopic_ids:
            if subtopic_id not in target.subtopic_ids:
                target.subtopic_ids.append(subtopic_id)
    return merged
