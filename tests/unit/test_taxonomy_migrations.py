from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from paperflow.models import TopicAssignment
from paperflow.taxonomy import TaxonomyConfig, load_taxonomy
from paperflow.taxonomy_migrations import (
    apply_taxonomy_migrations,
    plan_taxonomy_migrations,
)

ROOT = Path(__file__).parents[2]
MIGRATIONS = ROOT / "tests/fixtures/taxonomy/migrations"


def _fixture_taxonomies() -> tuple[TaxonomyConfig, TaxonomyConfig]:
    return (
        load_taxonomy(MIGRATIONS / "previous.yaml"),
        load_taxonomy(MIGRATIONS / "current.yaml"),
    )


def test_combined_rename_then_move_and_dry_run_are_deterministic() -> None:
    previous, current = _fixture_taxonomies()
    store = {
        "paper-1": [
            TopicAssignment(topic_id="old-topic", subtopic_ids=["old-child"])
        ]
    }

    plan = plan_taxonomy_migrations(previous, current, store)
    migrated = apply_taxonomy_migrations(store, current, plan)

    assert plan.render().splitlines() == [
        "PaperFlow taxonomy migration plan",
        "RENAME topic old-topic -> topic-new",
        "RENAME subtopic old-child -> child-new",
        "MOVE subtopic child-new: topic-new -> destination",
    ]
    assert migrated == {
        "paper-1": [
            TopicAssignment(topic_id="destination", subtopic_ids=["child-new"])
        ]
    }
    assert store["paper-1"][0].topic_id == "old-topic"
    assert store["paper-1"][0].subtopic_ids == ["old-child"]


def test_move_merges_existing_target_without_duplicates() -> None:
    previous, current = _fixture_taxonomies()
    store = {
        "paper-1": [
            TopicAssignment(topic_id="old-topic", subtopic_ids=["old-child"]),
            TopicAssignment(
                topic_id="destination",
                subtopic_ids=["existing-child", "child-new"],
            ),
        ]
    }

    plan = plan_taxonomy_migrations(previous, current, store)
    migrated = apply_taxonomy_migrations(store, current, plan)

    assert migrated["paper-1"] == [
        TopicAssignment(
            topic_id="destination",
            subtopic_ids=["existing-child", "child-new"],
        )
    ]


def test_topic_rename_preserves_parent_only_assignment() -> None:
    previous, current = _fixture_taxonomies()
    store = {
        "paper-1": [TopicAssignment(topic_id="old-topic", subtopic_ids=[])]
    }

    plan = plan_taxonomy_migrations(previous, current, store)
    migrated = apply_taxonomy_migrations(store, current, plan)

    assert migrated["paper-1"] == [
        TopicAssignment(topic_id="topic-new", subtopic_ids=[])
    ]


def test_subtopic_rename_without_move() -> None:
    previous = TaxonomyConfig.model_validate(
        {
            "schema_version": 1,
            "taxonomy_version": 1,
            "topics": [
                {
                    "id": "parent",
                    "name": "Parent",
                    "description": "Parent topic.",
                    "subtopics": [
                        {
                            "id": "old-child",
                            "name": "Old Child",
                            "description": "Original child.",
                        }
                    ],
                }
            ],
        }
    )
    current_data = previous.model_dump(mode="python")
    current_data["taxonomy_version"] = 2
    child = current_data["topics"][0]["subtopics"][0]
    child["id"] = "new-child"
    child["previous_ids"] = ["old-child"]
    current = TaxonomyConfig.model_validate(current_data)
    store = {
        "paper-1": [
            TopicAssignment(topic_id="parent", subtopic_ids=["old-child"])
        ]
    }

    plan = plan_taxonomy_migrations(previous, current, store)
    migrated = apply_taxonomy_migrations(store, current, plan)

    assert plan.subtopic_renames == (("old-child", "new-child"),)
    assert not plan.subtopic_moves
    assert migrated["paper-1"][0].subtopic_ids == ["new-child"]


def test_move_without_rename() -> None:
    previous = TaxonomyConfig.model_validate(
        {
            "schema_version": 1,
            "taxonomy_version": 1,
            "topics": [
                {
                    "id": "source",
                    "name": "Source",
                    "description": "Source topic.",
                    "subtopics": [
                        {
                            "id": "child",
                            "name": "Child",
                            "description": "Moving child.",
                        }
                    ],
                },
                {
                    "id": "destination",
                    "name": "Destination",
                    "description": "Destination topic.",
                },
            ],
        }
    )
    current_data = previous.model_dump(mode="python")
    current_data["taxonomy_version"] = 2
    child = current_data["topics"][0]["subtopics"].pop()
    child["moved_from"] = {"topic_id": "source"}
    current_data["topics"][1]["subtopics"].append(child)
    current = TaxonomyConfig.model_validate(current_data)
    store = {
        "paper-1": [TopicAssignment(topic_id="source", subtopic_ids=["child"])]
    }

    plan = plan_taxonomy_migrations(previous, current, store)
    migrated = apply_taxonomy_migrations(store, current, plan)

    assert not plan.topic_renames
    assert not plan.subtopic_renames
    assert migrated["paper-1"] == [
        TopicAssignment(topic_id="destination", subtopic_ids=["child"])
    ]


def test_display_name_only_change_has_no_identity_plan() -> None:
    previous, _ = _fixture_taxonomies()
    data = previous.model_dump(mode="python")
    data["topics"][0]["name"] = "A New Display Name"
    current = TaxonomyConfig.model_validate(data)

    plan = plan_taxonomy_migrations(previous, current, {})

    assert not plan.has_changes
    assert "No identity or parent changes" in plan.render()


def test_removed_in_use_id_blocks_without_mutating_input() -> None:
    previous, current = _fixture_taxonomies()
    store = {
        "paper-1": [
            TopicAssignment(topic_id="old-topic", subtopic_ids=[]),
            TopicAssignment(topic_id="destination", subtopic_ids=["removed-child"]),
        ]
    }
    original = deepcopy(store)

    with pytest.raises(ValueError, match="removed-child"):
        plan_taxonomy_migrations(previous, current, store)

    assert store == original


def test_parent_change_without_move_metadata_is_rejected() -> None:
    previous, current = _fixture_taxonomies()
    data = current.model_dump(mode="python")
    data["topics"][1]["subtopics"][1]["moved_from"] = None
    invalid_current = TaxonomyConfig.model_validate(data)

    with pytest.raises(ValueError, match="without moved_from"):
        plan_taxonomy_migrations(previous, invalid_current, {})


def test_incorrect_old_parent_conflict_is_rejected() -> None:
    _, current = _fixture_taxonomies()
    data = current.model_dump(mode="python")
    data["topics"][1]["subtopics"][1]["moved_from"] = {
        "topic_id": "destination"
    }

    with pytest.raises(ValidationError):
        TaxonomyConfig.model_validate(data)


def test_rename_cycle_is_rejected_by_taxonomy_validation() -> None:
    previous, _ = _fixture_taxonomies()
    data = previous.model_dump(mode="python")
    data["topics"][0]["previous_ids"] = ["destination"]

    with pytest.raises(ValidationError, match="rename cycle"):
        TaxonomyConfig.model_validate(data)
