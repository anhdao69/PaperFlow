from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from paperflow.config import load_config_bundle
from paperflow.models import (
    CandidatePaper,
    FilterStatus,
    ScreeningEvent,
    TopicAssignment,
)
from paperflow.retry_queue import WorkReason, determine_workset
from paperflow.screening_ledger import ScreeningLedger

HASH = "f" * 64


class FixtureRefetcher:
    def __init__(self, paper: CandidatePaper) -> None:
        self.paper = paper
        self.calls = 0

    def refetch(self, arxiv_id: str) -> CandidatePaper | None:
        self.calls += 1
        return self.paper if arxiv_id == self.paper.arxiv_id else None


def _event(
    *, status: FilterStatus, attempt: int, observed_at: datetime
) -> ScreeningEvent:
    data: dict[str, object] = {
        "event_id": UUID(int=attempt),
        "run_id": f"run-{attempt}",
        "arxiv_id": "2608.10010",
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
        data.update(error_type="semantic", error_message="Malformed result.")
    else:
        data.update(
            relevance=9,
            novelty=8,
            topic_assignments=[
                TopicAssignment(topic_id="world-models", subtopic_ids=[])
            ],
            reason="Retry succeeded.",
        )
    return ScreeningEvent.model_validate(data)


def test_second_run_retries_failed_paper_absent_from_source_once(
    tmp_path: Path,
) -> None:
    root = Path(__file__).parents[2]
    fixture = json.loads(
        (root / "tests/fixtures/pipeline/retry_second_run.json").read_text()
    )
    refetched = CandidatePaper.model_validate(fixture["refetched_candidate"])
    first_run_at = datetime(2026, 8, 19, 21, tzinfo=UTC)
    second_run_at = first_run_at + timedelta(days=1)
    ledger = ScreeningLedger(tmp_path / "screening_events")
    failed = _event(
        status=FilterStatus.FAILED, attempt=1, observed_at=first_run_at
    )
    ledger.append(failed)
    refetcher = FixtureRefetcher(refetched)

    plan = determine_workset(
        [],
        ledger.load_latest(),
        now=second_run_at,
        retry_config=load_config_bundle(root).runtime.filtering,
        refetcher=refetcher,
    )

    assert fixture["omitted_failed_id"] not in fixture["current_source_ids"]
    assert len(plan.items) == 1
    assert plan.items[0].paper.arxiv_id == fixture["omitted_failed_id"]
    assert plan.items[0].reason == WorkReason.FAILED_BACKLOG
    assert refetcher.calls == 1

    succeeded = _event(
        status=FilterStatus.KEPT, attempt=2, observed_at=second_run_at
    )
    ledger.append(succeeded)
    assert list(ledger.iter_events()) == [failed, succeeded]
    assert ledger.load_latest()[succeeded.arxiv_id].filter_status == FilterStatus.KEPT
