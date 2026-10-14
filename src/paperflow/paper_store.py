"""Validated canonical selected-paper and run-state persistence."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from paperflow.atomic import atomic_write_bytes, atomic_write_text
from paperflow.models import RunState, SelectedPaper, SelectedPaperCollection
from paperflow.taxonomy import TaxonomyConfig, validate_assignments

COMPRESS_THRESHOLD_BYTES = 90 * 1024 * 1024


def selected_store_path(path: Path) -> Path:
    """Resolve the canonical store, preferring an installed compressed version."""
    compressed = path.with_suffix(path.suffix + ".gz")
    return compressed if compressed.exists() else path


def _read_selected_bytes(path: Path) -> bytes:
    actual = selected_store_path(path)
    content = actual.read_bytes()
    return gzip.decompress(content) if actual != path else content


def _stable_json(
    model: SelectedPaperCollection | RunState, *, compact: bool = False
) -> str:
    return (
        json.dumps(
            model.model_dump(mode="json", exclude_none=False),
            ensure_ascii=False,
            indent=None if compact else 2,
            separators=(",", ":") if compact else None,
            sort_keys=True,
        )
        + "\n"
    )


def validate_selected_collection(
    collection: SelectedPaperCollection, taxonomy: TaxonomyConfig
) -> None:
    for paper in collection.papers.values():
        validate_assignments(taxonomy, paper.topic_assignments)


def load_selected_store(
    path: Path, taxonomy: TaxonomyConfig
) -> SelectedPaperCollection:
    content = _read_selected_bytes(path)
    collection = SelectedPaperCollection.model_validate_json(content)
    validate_selected_collection(collection, taxonomy)
    return collection


def load_selected_store_unvalidated(path: Path) -> SelectedPaperCollection:
    """Load canonical records before a taxonomy migration is applied."""
    return SelectedPaperCollection.model_validate_json(_read_selected_bytes(path))


def save_selected_store(
    path: Path,
    papers: dict[str, SelectedPaper],
    taxonomy: TaxonomyConfig,
) -> SelectedPaperCollection:
    """Validate all paper/taxonomy invariants before replacing canonical bytes."""
    collection = SelectedPaperCollection(papers=papers)
    validate_selected_collection(collection, taxonomy)

    content = _stable_json(collection, compact=True).encode("utf-8")
    compressed_path = path.with_suffix(path.suffix + ".gz")
    compress = compressed_path.exists() or len(content) >= COMPRESS_THRESHOLD_BYTES

    def validate_staged(staged_path: Path) -> None:
        staged_bytes = staged_path.read_bytes()
        if compress:
            staged_bytes = gzip.decompress(staged_bytes)
        staged = SelectedPaperCollection.model_validate_json(staged_bytes)
        validate_selected_collection(staged, taxonomy)

    if compress:
        # Zero timestamp keeps identical records byte-for-byte deterministic.
        atomic_write_bytes(
            compressed_path, gzip.compress(content, mtime=0), validator=validate_staged
        )
        # Remove legacy bytes only after the validated gzip is atomically installed.
        path.unlink(missing_ok=True)
    else:
        atomic_write_bytes(path, content, validator=validate_staged)
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
