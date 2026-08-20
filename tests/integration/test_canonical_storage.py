from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from paperflow.models import FilterStatus, ScreeningEvent, TopicAssignment
from paperflow.paper_store import load_run_state, load_selected_store
from paperflow.screening_ledger import ScreeningLedger
from paperflow.taxonomy import load_taxonomy

HASH = "d" * 64


def test_checked_in_empty_canonical_files_validate() -> None:
    root = Path(__file__).parents[2]
    taxonomy = load_taxonomy(root / "configs/topics.yaml")

    assert not load_selected_store(root / "data/papers.json", taxonomy).papers
    assert load_run_state(root / "data/state.json").last_successful_run_id is None


def _event(
    event_id: str, status: FilterStatus, observed_at: datetime, attempt: int
) -> ScreeningEvent:
    data: dict[str, object] = {
        "event_id": UUID(event_id),
        "run_id": f"run-{attempt}",
        "arxiv_id": "2608.12345",
        "observed_at": observed_at,
        "abstract_hash": HASH,
        "filter_status": status,
        "attempt_number": attempt,
        "taxonomy_version": 1,
        "taxonomy_hash": HASH,
        "filter_prompt_version": "filter-v3",
        "filter_prompt_hash": HASH,
    }
    if status == FilterStatus.FAILED:
        data.update(error_type="transport", error_message="Temporary failure.")
    else:
        data.update(
            relevance=9,
            novelty=8,
            topic_assignments=[
                TopicAssignment(topic_id="world-models", subtopic_ids=[])
            ],
            reason="Relevant on retry.",
        )
    return ScreeningEvent.model_validate(data)


def test_ledger_keeps_failed_history_after_later_success(tmp_path: Path) -> None:
    ledger = ScreeningLedger(tmp_path / "screening_events")
    failed = _event(
        "00000000-0000-0000-0000-000000000001",
        FilterStatus.FAILED,
        datetime(2026, 8, 31, 23, tzinfo=UTC),
        1,
    )
    kept = _event(
        "00000000-0000-0000-0000-000000000002",
        FilterStatus.KEPT,
        datetime(2026, 9, 1, 1, tzinfo=UTC),
        2,
    )

    ledger.append(failed)
    ledger.append(kept)

    assert list(ledger.iter_events()) == [failed, kept]
    assert ledger.load_latest()["2608.12345"].filter_status == FilterStatus.KEPT
