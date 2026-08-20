from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from paperflow.models import FilterStatus, ScreeningEvent, TopicAssignment
from paperflow.screening_ledger import (
    ScreeningLedger,
    ScreeningLedgerError,
    reduce_latest_screening_state,
)

HASH = "a" * 64


def _event(
    *,
    event_id: str,
    status: FilterStatus = FilterStatus.KEPT,
    observed_at: datetime | None = None,
    attempt: int = 1,
) -> ScreeningEvent:
    common = {
        "event_id": UUID(event_id),
        "run_id": "20260820T210000000000Z-00000000000000000000000000000001",
        "arxiv_id": "2608.12345",
        "observed_at": observed_at or datetime(2026, 8, 20, 21, tzinfo=UTC),
        "abstract_hash": HASH,
        "filter_status": status,
        "attempt_number": attempt,
        "taxonomy_version": 1,
        "taxonomy_hash": HASH,
        "filter_prompt_version": "filter-v3",
        "filter_prompt_hash": HASH,
    }
    if status == FilterStatus.KEPT:
        common.update(
            relevance=9,
            novelty=8,
            topic_assignments=[
                TopicAssignment(topic_id="world-models", subtopic_ids=[])
            ],
            reason="Directly relevant.",
        )
    elif status == FilterStatus.DROPPED:
        common.update(relevance=2, novelty=4, reason="Outside configured scope.")
    else:
        common.update(
            error_type="semantic_validation",
            error_message="Invalid assignment returned.",
            next_retry_at=datetime(2026, 8, 21, 9, tzinfo=UTC),
        )
    return ScreeningEvent.model_validate(common)


@pytest.mark.parametrize("status", list(FilterStatus))
def test_each_screening_status_round_trips(status: FilterStatus) -> None:
    event = _event(event_id="00000000-0000-0000-0000-000000000001", status=status)

    assert ScreeningEvent.model_validate_json(event.model_dump_json()) == event


@pytest.mark.parametrize(
    "changes",
    [
        {"filter_status": "kept", "topic_assignments": []},
        {
            "filter_status": "dropped",
            "topic_assignments": [
                {"topic_id": "world-models", "subtopic_ids": []}
            ],
        },
        {"filter_status": "failed", "error_type": None, "error_message": None},
    ],
)
def test_status_invariants_reject_invalid_events(changes: dict[str, object]) -> None:
    data = _event(
        event_id="00000000-0000-0000-0000-000000000001"
    ).model_dump(mode="python")
    data.update(changes)
    with pytest.raises(ValidationError):
        ScreeningEvent.model_validate(data)


def test_monthly_append_reload_and_prior_failure_history(tmp_path: Path) -> None:
    ledger = ScreeningLedger(tmp_path)
    failed = _event(
        event_id="00000000-0000-0000-0000-000000000001",
        status=FilterStatus.FAILED,
        observed_at=datetime(2026, 8, 31, 23, tzinfo=UTC),
    )
    kept = _event(
        event_id="00000000-0000-0000-0000-000000000002",
        status=FilterStatus.KEPT,
        observed_at=datetime(2026, 9, 1, 1, tzinfo=UTC),
        attempt=2,
    )

    assert ledger.append(failed).name == "2026-08.jsonl"
    assert ledger.append(kept).name == "2026-09.jsonl"
    assert list(ledger.iter_events()) == [failed, kept]
    assert ledger.load_latest()["2608.12345"] == kept


def test_latest_reduction_has_deterministic_tie_policy() -> None:
    instant = datetime(2026, 8, 20, 21, tzinfo=UTC)
    low = _event(
        event_id="00000000-0000-0000-0000-000000000001",
        observed_at=instant,
    )
    high_attempt = _event(
        event_id="00000000-0000-0000-0000-000000000002",
        observed_at=instant,
        attempt=2,
    )
    later_uuid = _event(
        event_id="00000000-0000-0000-0000-000000000003",
        observed_at=instant,
        attempt=2,
    )

    for order in (
        [low, high_attempt, later_uuid],
        [later_uuid, low, high_attempt],
    ):
        assert reduce_latest_screening_state(order)["2608.12345"] == later_uuid


def test_corrupt_or_truncated_line_is_actionable(tmp_path: Path) -> None:
    path = tmp_path / "2026-08.jsonl"
    path.write_text('{"event_id":', encoding="utf-8")

    with pytest.raises(ScreeningLedgerError, match=r"2026-08\.jsonl:1"):
        list(ScreeningLedger(tmp_path).iter_events())


def test_naive_timestamps_are_rejected() -> None:
    data = _event(
        event_id="00000000-0000-0000-0000-000000000001"
    ).model_dump(mode="python")
    data["observed_at"] = datetime.now() - timedelta(days=1)

    with pytest.raises(ValidationError, match="timezone"):
        ScreeningEvent.model_validate(data)
