from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from paperflow.models import TopicAssignment
from paperflow.taxonomy import (
    TaxonomyConfig,
    load_taxonomy,
    safe_taxonomy_path,
    taxonomy_hash,
    validate_assignments,
)

ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests/fixtures/taxonomy"


def _seed_data() -> dict[str, object]:
    return yaml.safe_load((ROOT / "configs/topics.yaml").read_text(encoding="utf-8"))


def test_seed_taxonomy_loads_in_yaml_order() -> None:
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")

    assert taxonomy.ordered_topic_ids() == (
        "embodied-ai",
        "world-models",
        "multimodal-foundation-models",
        "spatial-intelligence",
        "3d-vision",
        "video-generation",
        "efficient-ai",
    )
    assert taxonomy.ordered_subtopic_ids("world-models") == (
        "latent-action-models",
        "world-action-models",
        "video-world-models",
    )
    assert taxonomy.subtopic_parent("spatial-memory").id == "spatial-intelligence"


@pytest.mark.parametrize("fixture", sorted(FIXTURES.glob("invalid_*.yaml")))
def test_invalid_taxonomy_fixtures_are_rejected(fixture: Path) -> None:
    with pytest.raises((ValueError, ValidationError)):
        load_taxonomy(fixture)


def test_previous_ids_are_globally_unambiguous() -> None:
    data = _seed_data()
    data["topics"][0]["previous_ids"] = ["old-topic"]
    data["topics"][1]["previous_ids"] = ["old-topic"]

    with pytest.raises(ValidationError, match="ambiguous"):
        TaxonomyConfig.model_validate(data)


def test_valid_move_can_reference_historical_parent_id() -> None:
    data = _seed_data()
    data["topics"][0]["previous_ids"] = ["old-embodied"]
    data["topics"][1]["subtopics"][0]["moved_from"] = {
        "topic_id": "old-embodied"
    }

    taxonomy = TaxonomyConfig.model_validate(data)

    assert taxonomy.topics[1].subtopics[0].moved_from is not None


def test_move_from_active_parent_is_rejected() -> None:
    data = _seed_data()
    data["topics"][0]["subtopics"][0]["moved_from"] = {
        "topic_id": "embodied-ai"
    }

    with pytest.raises(ValidationError, match="active parent"):
        TaxonomyConfig.model_validate(data)


def test_safe_paths_accept_ids_and_reject_traversal() -> None:
    assert str(safe_taxonomy_path("world-models", "video-world-models")) == (
        "world-models/video-world-models"
    )
    for unsafe in ("../topics", "/absolute", "has\\backslash", "has?query", ""):
        with pytest.raises(ValueError, match="safe taxonomy IDs"):
            safe_taxonomy_path(unsafe)


def test_assignment_validation_accepts_parent_only_and_valid_children() -> None:
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")

    validate_assignments(
        taxonomy,
        [
            TopicAssignment(topic_id="world-models", subtopic_ids=[]),
            TopicAssignment(
                topic_id="spatial-intelligence",
                subtopic_ids=["spatial-memory", "geometry-aware-models"],
            ),
        ],
    )


@pytest.mark.parametrize(
    "assignments",
    [
        [TopicAssignment(topic_id="missing", subtopic_ids=[])],
        [TopicAssignment(topic_id="world-models", subtopic_ids=["spatial-memory"])],
        [
            TopicAssignment(topic_id="world-models", subtopic_ids=[]),
            TopicAssignment(topic_id="world-models", subtopic_ids=[]),
        ],
    ],
)
def test_assignment_validation_rejects_invalid_semantics(
    assignments: list[TopicAssignment],
) -> None:
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")
    with pytest.raises(ValueError):
        validate_assignments(taxonomy, assignments)


def test_taxonomy_hash_is_deterministic_and_semantic() -> None:
    data = _seed_data()
    first = TaxonomyConfig.model_validate(data)
    same = TaxonomyConfig.model_validate(deepcopy(data))
    changed_data = deepcopy(data)
    changed_data["topics"][0]["description"] += " Expanded."
    changed = TaxonomyConfig.model_validate(changed_data)

    assert taxonomy_hash(first) == taxonomy_hash(same)
    assert taxonomy_hash(first) != taxonomy_hash(changed)
