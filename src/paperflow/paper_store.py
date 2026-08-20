"""Validated canonical selected-paper and run-state persistence."""

from __future__ import annotations

import json
from pathlib import Path

from paperflow.atomic import atomic_write_text
from paperflow.models import RunState, SelectedPaper, SelectedPaperCollection
from paperflow.taxonomy import TaxonomyConfig, validate_assignments


def _stable_json(model: SelectedPaperCollection | RunState) -> str:
    return json.dumps(
        model.model_dump(mode="json", exclude_none=False),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def validate_selected_collection(
    collection: SelectedPaperCollection, taxonomy: TaxonomyConfig
) -> None:
    for paper in collection.papers.values():
        validate_assignments(taxonomy, paper.topic_assignments)


def load_selected_store(
    path: Path, taxonomy: TaxonomyConfig
) -> SelectedPaperCollection:
    content = path.read_text(encoding="utf-8")
    collection = SelectedPaperCollection.model_validate_json(content)
    validate_selected_collection(collection, taxonomy)
    return collection


def save_selected_store(
    path: Path,
    papers: dict[str, SelectedPaper],
    taxonomy: TaxonomyConfig,
) -> SelectedPaperCollection:
    """Validate all paper/taxonomy invariants before replacing canonical bytes."""
    collection = SelectedPaperCollection(papers=papers)
    validate_selected_collection(collection, taxonomy)

    def validate_staged(staged_path: Path) -> None:
        staged = SelectedPaperCollection.model_validate_json(
            staged_path.read_text(encoding="utf-8")
        )
        validate_selected_collection(staged, taxonomy)

    atomic_write_text(path, _stable_json(collection), validator=validate_staged)
    return collection


def load_run_state(path: Path) -> RunState:
    return RunState.model_validate_json(path.read_text(encoding="utf-8"))


def save_run_state(
    path: Path, state: RunState, *, publication_validated: bool
) -> None:
    """Persist successful state only after the caller's publication gate passes."""
    if state.last_successful_run_id is not None and not publication_validated:
        raise ValueError("successful run state requires validated publication")
    atomic_write_text(
        path,
        _stable_json(state),
        validator=lambda staged: RunState.model_validate_json(
            staged.read_text(encoding="utf-8")
        ),
    )
