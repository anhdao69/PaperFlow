from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from paperflow.models import RunState
from paperflow.paper_store import load_run_state, save_run_state

HASH = "c" * 64


def _successful_state() -> RunState:
    return RunState(
        last_successful_run_id=(
            "20260820T210000000000Z-00000000000000000000000000000001"
        ),
        last_successful_at=datetime(2026, 8, 20, 21, tzinfo=UTC),
        last_successful_local_date="2026-08-20",
        taxonomy_hash=HASH,
        runtime_config_hash=HASH,
        model_config_hash=HASH,
    )


def test_empty_state_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = RunState()

    save_run_state(path, state, publication_validated=False)

    assert load_run_state(path) == state


def test_success_state_requires_publication_validation(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("previous", encoding="utf-8")

    with pytest.raises(ValueError, match="validated publication"):
        save_run_state(path, _successful_state(), publication_validated=False)

    assert path.read_text(encoding="utf-8") == "previous"


def test_validated_success_state_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = _successful_state()

    save_run_state(path, state, publication_validated=True)

    assert load_run_state(path) == state


def test_partial_or_date_inconsistent_success_state_is_rejected() -> None:
    with pytest.raises(ValidationError, match="entirely populated"):
        RunState(last_successful_run_id="run")
    data = _successful_state().model_dump(mode="python")
    data["last_successful_local_date"] = "2026-08-19"
    with pytest.raises(ValidationError, match="must match"):
        RunState.model_validate(data)
