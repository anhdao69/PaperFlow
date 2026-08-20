from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from paperflow.config import FilteringConfig
from paperflow.models import (
    CandidatePaper,
    FilterStatus,
    ScreeningEvent,
    TopicAssignment,
)
from paperflow.retry_queue import (
    ExclusionReason,
    WorkReason,
    determine_workset,
    is_retry_eligible,
)

HASH = "e" * 64
NOW = datetime(2026, 8, 20, 21, tzinfo=UTC)


class FakeRefetcher:
    def __init__(self, papers: dict[str, CandidatePaper | None]) -> None:
        self.papers = papers
        self.calls: list[str] = []

    def refetch(self, arxiv_id: str) -> CandidatePaper | None:
        self.calls.append(arxiv_id)
        return self.papers.get(arxiv_id)


def _config(**changes: object) -> FilteringConfig:
    data: dict[str, object] = {
        "batch_size": 10,
        "concurrency": 3,
        "semantic_retry_count": 1,
        "transient_retry_count": 3,
        "failed_auto_retry_max_attempts": 5,
        "failed_retry_cooldown_hours": 12,
    }
    data.update(changes)
    return FilteringConfig.model_validate(data)


def _paper(arxiv_id: str) -> CandidatePaper:
    return CandidatePaper(
        arxiv_id=arxiv_id,
        source_arxiv_id=f"{arxiv_id}v1",
        title=f"Paper {arxiv_id}",
        abstract="A fixture abstract.",
        authors=["A. Author"],
        categories=["cs.AI"],
        arxiv_url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
    )


def _state(
    arxiv_id: str,
    status: FilterStatus,
    *,
    attempt: int = 1,
    observed_at: datetime | None = None,
    next_retry_at: datetime | None = None,
    exhausted: bool = False,
) -> ScreeningEvent:
    data: dict[str, object] = {
        "event_id": UUID(int=int(arxiv_id.split(".")[1])),
        "run_id": "fixture-run",
        "arxiv_id": arxiv_id,
        "observed_at": observed_at or NOW - timedelta(days=1),
        "abstract_hash": HASH,
        "filter_status": status,
        "attempt_number": attempt,
        "taxonomy_version": 1,
        "taxonomy_hash": HASH,
        "filter_prompt_version": "filter-v3",
        "filter_prompt_hash": HASH,
    }
    if status == FilterStatus.FAILED:
        data.update(
            error_type="semantic",
            error_message="Invalid output.",
            next_retry_at=next_retry_at,
            retry_exhausted=exhausted,
        )
    elif status == FilterStatus.KEPT:
        data.update(
            relevance=9,
            novelty=8,
            topic_assignments=[
                TopicAssignment(topic_id="world-models", subtopic_ids=[])
            ],
            reason="Relevant.",
        )
    else:
        data.update(relevance=2, novelty=3, reason="Not relevant.")
    return ScreeningEvent.model_validate(data)


def test_unseen_current_candidate_is_included() -> None:
    paper = _paper("2608.10001")
    plan = determine_workset(
        [paper], {}, now=NOW, retry_config=_config(), refetcher=FakeRefetcher({})
    )

    assert plan.items[0].reason == WorkReason.NEW_UNSEEN
    assert plan.items[0].next_attempt_number == 1


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (FilterStatus.KEPT, ExclusionReason.TERMINAL_KEPT),
        (FilterStatus.DROPPED, ExclusionReason.TERMINAL_DROPPED),
    ],
)
def test_terminal_current_candidates_are_excluded(
    status: FilterStatus, reason: ExclusionReason
) -> None:
    paper = _paper("2608.10001")
    plan = determine_workset(
        [paper],
        {paper.arxiv_id: _state(paper.arxiv_id, status)},
        now=NOW,
        retry_config=_config(),
        refetcher=FakeRefetcher({}),
    )

    assert not plan.items
    assert plan.exclusions[0].reason == reason


@pytest.mark.parametrize(
    ("offset", "eligible"),
    [
        (timedelta(microseconds=-1), False),
        (timedelta(), True),
        (timedelta(microseconds=1), True),
    ],
)
def test_cooldown_exact_boundary(offset: timedelta, eligible: bool) -> None:
    event = _state(
        "2608.10001",
        FilterStatus.FAILED,
        observed_at=NOW - timedelta(hours=12),
    )

    result, _ = is_retry_eligible(event, NOW + offset, _config())

    assert result is eligible


def test_absent_eligible_failure_is_refetched_once() -> None:
    failed_id = "2608.10010"
    refetcher = FakeRefetcher({failed_id: _paper(failed_id)})

    plan = determine_workset(
        [],
        {failed_id: _state(failed_id, FilterStatus.FAILED)},
        now=NOW,
        retry_config=_config(),
        refetcher=refetcher,
    )

    assert [item.paper.arxiv_id for item in plan.items] == [failed_id]
    assert plan.items[0].reason == WorkReason.FAILED_BACKLOG
    assert plan.items[0].next_attempt_number == 2
    assert refetcher.calls == [failed_id]


def test_current_and_backlog_duplicate_is_processed_once_without_refetch() -> None:
    failed_id = "2608.10010"
    refetcher = FakeRefetcher({failed_id: _paper(failed_id)})

    plan = determine_workset(
        [_paper(failed_id)],
        {failed_id: _state(failed_id, FilterStatus.FAILED)},
        now=NOW,
        retry_config=_config(),
        refetcher=refetcher,
    )

    assert len(plan.items) == 1
    assert plan.items[0].reason == WorkReason.FAILED_CURRENT
    assert not refetcher.calls


def test_metadata_refetch_failure_retains_failed_exclusion() -> None:
    failed_id = "2608.10010"
    plan = determine_workset(
        [],
        {failed_id: _state(failed_id, FilterStatus.FAILED)},
        now=NOW,
        retry_config=_config(),
        refetcher=FakeRefetcher({failed_id: None}),
    )

    assert not plan.items
    assert plan.exclusions[0].reason == ExclusionReason.METADATA_REFETCH_FAILED


def test_duplicate_current_candidates_are_processed_once() -> None:
    paper = _paper("2608.10001")

    plan = determine_workset(
        [paper, paper],
        {},
        now=NOW,
        retry_config=_config(),
        refetcher=FakeRefetcher({}),
    )

    assert len(plan.items) == 1


@pytest.mark.parametrize("explicit_flag", [False, True])
def test_attempt_exhaustion_remains_failed_and_is_not_automatic(
    explicit_flag: bool,
) -> None:
    failed_id = "2608.10010"
    state = _state(
        failed_id,
        FilterStatus.FAILED,
        attempt=5,
        exhausted=explicit_flag,
    )
    plan = determine_workset(
        [],
        {failed_id: state},
        now=NOW,
        retry_config=_config(),
        refetcher=FakeRefetcher({failed_id: _paper(failed_id)}),
    )

    assert not plan.items
    assert state.filter_status == FilterStatus.FAILED
    assert plan.exclusions[0].reason == ExclusionReason.RETRY_EXHAUSTED


def test_manual_override_selects_exhausted_failure() -> None:
    failed_id = "2608.10010"
    plan = determine_workset(
        [],
        {
            failed_id: _state(
                failed_id, FilterStatus.FAILED, attempt=5, exhausted=True
            )
        },
        now=NOW,
        retry_config=_config(),
        refetcher=FakeRefetcher({failed_id: _paper(failed_id)}),
        manual_override_ids=[failed_id],
    )

    assert plan.items[0].reason == WorkReason.MANUAL_OVERRIDE
    assert plan.items[0].next_attempt_number == 6


def test_naive_now_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        determine_workset(
            [],
            {},
            now=datetime(2026, 8, 20, 21),
            retry_config=_config(),
            refetcher=FakeRefetcher({}),
        )


def test_dry_report_explains_every_decision() -> None:
    new = _paper("2608.10001")
    terminal = _paper("2608.10002")
    plan = determine_workset(
        [new, terminal],
        {terminal.arxiv_id: _state(terminal.arxiv_id, FilterStatus.DROPPED)},
        now=NOW,
        retry_config=_config(),
        refetcher=FakeRefetcher({}),
    )

    assert "INCLUDE 2608.10001 (new_unseen, attempt 1)" in plan.render()
    assert "EXCLUDE 2608.10002 (terminal_dropped)" in plan.render()
