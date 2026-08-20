"""FAILED-backlog eligibility and deterministic daily workset planning."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from paperflow.config import FilteringConfig
from paperflow.models import CandidatePaper, FilterStatus, ScreeningEvent


class WorkReason(StrEnum):
    NEW_UNSEEN = "new_unseen"
    FAILED_CURRENT = "failed_current"
    FAILED_BACKLOG = "failed_backlog"
    MANUAL_OVERRIDE = "manual_override"


class ExclusionReason(StrEnum):
    TERMINAL_KEPT = "terminal_kept"
    TERMINAL_DROPPED = "terminal_dropped"
    RETRY_COOLDOWN = "retry_cooldown"
    RETRY_EXHAUSTED = "retry_exhausted"
    METADATA_REFETCH_FAILED = "metadata_refetch_failed"
    MANUAL_METADATA_UNAVAILABLE = "manual_metadata_unavailable"


class MetadataRefetcher(Protocol):
    def refetch(self, arxiv_id: str) -> CandidatePaper | None: ...


@dataclass(frozen=True)
class WorkItem:
    paper: CandidatePaper
    reason: WorkReason
    next_attempt_number: int


@dataclass(frozen=True)
class WorksetExclusion:
    arxiv_id: str
    reason: ExclusionReason


@dataclass(frozen=True)
class WorksetPlan:
    items: tuple[WorkItem, ...]
    exclusions: tuple[WorksetExclusion, ...]

    def render(self) -> str:
        lines = ["PaperFlow workset"]
        lines.extend(
            f"INCLUDE {item.paper.arxiv_id} ({item.reason.value}, "
            f"attempt {item.next_attempt_number})"
            for item in self.items
        )
        lines.extend(
            f"EXCLUDE {item.arxiv_id} ({item.reason.value})"
            for item in self.exclusions
        )
        if len(lines) == 1:
            lines.append("No candidates.")
        return "\n".join(lines)


def is_retry_eligible(
    event: ScreeningEvent, now: datetime, config: FilteringConfig
) -> tuple[bool, ExclusionReason | None]:
    """Return retry eligibility at exact cooldown/exhaustion boundaries."""
    _require_aware(now)
    if event.filter_status != FilterStatus.FAILED:
        return False, (
            ExclusionReason.TERMINAL_KEPT
            if event.filter_status == FilterStatus.KEPT
            else ExclusionReason.TERMINAL_DROPPED
        )
    if (
        event.retry_exhausted
        or event.attempt_number >= config.failed_auto_retry_max_attempts
    ):
        return False, ExclusionReason.RETRY_EXHAUSTED
    eligible_at = event.next_retry_at or (
        event.observed_at
        + timedelta(hours=config.failed_retry_cooldown_hours)
    )
    if now < eligible_at:
        return False, ExclusionReason.RETRY_COOLDOWN
    return True, None


def determine_workset(
    today_candidates: Sequence[CandidatePaper],
    latest_screening_state: Mapping[str, ScreeningEvent],
    *,
    now: datetime,
    retry_config: FilteringConfig,
    refetcher: MetadataRefetcher,
    manual_override_ids: Sequence[str] = (),
) -> WorksetPlan:
    """Merge unseen current papers and eligible FAILED backlog exactly once."""
    _require_aware(now)
    work: dict[str, WorkItem] = {}
    exclusions: dict[str, WorksetExclusion] = {}
    current_by_id: dict[str, CandidatePaper] = {}
    current_order: list[CandidatePaper] = []
    for paper in today_candidates:
        if paper.arxiv_id not in current_by_id:
            current_by_id[paper.arxiv_id] = paper
            current_order.append(paper)
    manual_ids = set(manual_override_ids)

    for paper in current_order:
        state = latest_screening_state.get(paper.arxiv_id)
        if paper.arxiv_id in manual_ids:
            work[paper.arxiv_id] = WorkItem(
                paper=paper,
                reason=WorkReason.MANUAL_OVERRIDE,
                next_attempt_number=(state.attempt_number + 1 if state else 1),
            )
            continue
        if state is None:
            work[paper.arxiv_id] = WorkItem(
                paper=paper,
                reason=WorkReason.NEW_UNSEEN,
                next_attempt_number=1,
            )
            continue
        eligible, exclusion = is_retry_eligible(state, now, retry_config)
        if eligible:
            work[paper.arxiv_id] = WorkItem(
                paper=paper,
                reason=WorkReason.FAILED_CURRENT,
                next_attempt_number=state.attempt_number + 1,
            )
        elif exclusion is not None:
            exclusions[paper.arxiv_id] = WorksetExclusion(
                arxiv_id=paper.arxiv_id, reason=exclusion
            )

    for arxiv_id in sorted(latest_screening_state):
        if arxiv_id in work or arxiv_id in current_by_id:
            continue
        state = latest_screening_state[arxiv_id]
        if arxiv_id in manual_ids:
            paper = refetcher.refetch(arxiv_id)
            if paper is None:
                exclusions[arxiv_id] = WorksetExclusion(
                    arxiv_id=arxiv_id,
                    reason=ExclusionReason.MANUAL_METADATA_UNAVAILABLE,
                )
            else:
                work[arxiv_id] = WorkItem(
                    paper=paper,
                    reason=WorkReason.MANUAL_OVERRIDE,
                    next_attempt_number=state.attempt_number + 1,
                )
                exclusions.pop(arxiv_id, None)
            continue

        eligible, exclusion = is_retry_eligible(state, now, retry_config)
        if not eligible:
            if state.filter_status == FilterStatus.FAILED and exclusion is not None:
                exclusions[arxiv_id] = WorksetExclusion(arxiv_id, exclusion)
            continue
        paper = refetcher.refetch(arxiv_id)
        if paper is None:
            exclusions[arxiv_id] = WorksetExclusion(
                arxiv_id, ExclusionReason.METADATA_REFETCH_FAILED
            )
            continue
        work[arxiv_id] = WorkItem(
            paper=paper,
            reason=WorkReason.FAILED_BACKLOG,
            next_attempt_number=state.attempt_number + 1,
        )
        exclusions.pop(arxiv_id, None)

    unknown_manual_ids = manual_ids - set(latest_screening_state) - set(current_by_id)
    for arxiv_id in sorted(unknown_manual_ids):
        paper = refetcher.refetch(arxiv_id)
        if paper is None:
            exclusions[arxiv_id] = WorksetExclusion(
                arxiv_id, ExclusionReason.MANUAL_METADATA_UNAVAILABLE
            )
        else:
            work[arxiv_id] = WorkItem(paper, WorkReason.MANUAL_OVERRIDE, 1)

    ordered_items = tuple(
        [work[paper.arxiv_id] for paper in current_order if paper.arxiv_id in work]
        + [
            work[arxiv_id]
            for arxiv_id in sorted(work)
            if arxiv_id not in current_by_id
        ]
    )
    return WorksetPlan(
        items=ordered_items,
        exclusions=tuple(exclusions[key] for key in sorted(exclusions)),
    )


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("workset time must be timezone-aware")
