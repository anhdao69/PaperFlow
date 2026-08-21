"""Structured batch filtering with taxonomy validation and partial salvage."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ValidationError

from paperflow.config import FilteringConfig, ModelConfig
from paperflow.llm.openrouter import OpenRouterSemanticError
from paperflow.llm.structured import PromptPaper, PromptRenderer, RenderedPrompt
from paperflow.models import (
    DomainModel,
    FilterResult,
    FilterStatus,
    LLMCallResult,
    ScreeningEvent,
)
from paperflow.retry_queue import WorkItem
from paperflow.screening_ledger import ScreeningLedger
from paperflow.taxonomy import (
    TaxonomyAssignmentError,
    TaxonomyConfig,
    taxonomy_hash,
    validate_assignments,
)


class StructuredChatClient(Protocol):
    def structured_chat[OutputT: BaseModel](
        self,
        *,
        task_name: str,
        messages: list[dict[str, str]],
        schema: type[OutputT],
        model_chain: list[str],
        request_metadata: dict[str, str],
    ) -> LLMCallResult[OutputT]: ...


class FilterWireAssignment(DomainModel):
    """Assignment shape without semantic ID or duplicate constraints."""

    topic_id: str
    subtopic_ids: list[str] = Field(default_factory=list)


class FilterWireResult(DomainModel):
    """Member shape that preserves an ID while deferring decision validation."""

    arxiv_id: str
    keep: bool
    relevance: int
    novelty: int
    assignments: list[FilterWireAssignment]
    reason: str


class FilterBatchEnvelope(DomainModel):
    results: list[FilterWireResult]


@dataclass(frozen=True)
class FilterRunResult:
    events: tuple[ScreeningEvent, ...]
    llm_calls: tuple[LLMCallResult[FilterBatchEnvelope], ...] = ()

    @property
    def valid_kept(self) -> tuple[ScreeningEvent, ...]:
        return tuple(
            event for event in self.events if event.filter_status == FilterStatus.KEPT
        )

    def render_dry_run_report(self) -> str:
        """Render decisions and provenance without prompt or credential material."""
        lines = ["PaperFlow filter dry-run report"]
        for event in self.events:
            score = (
                f" relevance={event.relevance} novelty={event.novelty}"
                if event.relevance is not None and event.novelty is not None
                else ""
            )
            lines.append(
                f"{event.arxiv_id} {event.filter_status.value.upper()}{score} "
                f"taxonomy={event.taxonomy_hash} prompt={event.filter_prompt_hash} "
                f"requested={event.requested_model or '-'} "
                f"actual={event.actual_model or '-'} provider={event.provider or '-'}"
            )
        return "\n".join(lines)


@dataclass(frozen=True)
class _Decision:
    result: FilterResult | None
    llm_result: LLMCallResult[FilterBatchEnvelope] | None
    requested_model: str
    error_message: str | None = None


@dataclass(frozen=True)
class _ClassifiedResponse:
    valid: Mapping[str, FilterResult]
    invalid: Mapping[str, str]
    mapping_safe: bool


def filter_workset(
    work_items: Sequence[WorkItem],
    *,
    client: StructuredChatClient,
    renderer: PromptRenderer,
    taxonomy: TaxonomyConfig,
    model_config: ModelConfig,
    filtering_config: FilteringConfig,
    ledger: ScreeningLedger | None,
    run_id: str,
    observed_at: datetime,
    event_id_factory: Callable[[], UUID] = uuid4,
) -> FilterRunResult:
    """Filter every work item once and append one durable terminal-attempt event."""
    _require_aware(observed_at)
    if not run_id.strip():
        raise ValueError("filter run_id cannot be empty")
    paper_ids = [item.paper.arxiv_id for item in work_items]
    if len(paper_ids) != len(set(paper_ids)):
        raise ValueError("filter workset contains duplicate arXiv IDs")
    if not work_items:
        return FilterRunResult(events=())

    task_chain = model_config.tasks.get("filter")
    if task_chain is None:
        raise ValueError("model configuration has no filter task")
    aliases = [task_chain.primary, *task_chain.fallbacks]
    batches = [
        tuple(work_items[index : index + filtering_config.batch_size])
        for index in range(0, len(work_items), filtering_config.batch_size)
    ]
    decisions_by_batch: dict[int, tuple[_Decision, ...]] = {}

    with ThreadPoolExecutor(max_workers=filtering_config.concurrency) as executor:
        futures = {
            executor.submit(
                _filter_batch,
                batch,
                batch_index=index,
                client=client,
                renderer=renderer,
                taxonomy=taxonomy,
                model_config=model_config,
                model_aliases=aliases,
                semantic_retry_count=filtering_config.semantic_retry_count,
                run_id=run_id,
            ): index
            for index, batch in enumerate(batches)
        }
        for future in as_completed(futures):
            decisions_by_batch[futures[future]] = future.result()

    ordered_decisions = tuple(
        decision
        for index in range(len(batches))
        for decision in decisions_by_batch[index]
    )
    prompt = renderer.render_filter(
        taxonomy,
        [
            PromptPaper(
                arxiv_id=item.paper.arxiv_id,
                title=item.paper.title,
                abstract=item.paper.abstract,
                categories=item.paper.categories,
            )
            for item in work_items[:1]
        ],
    )
    taxonomy_digest = taxonomy_hash(taxonomy)
    events = tuple(
        _build_event(
            item,
            decision,
            run_id=run_id,
            observed_at=observed_at,
            taxonomy=taxonomy,
            taxonomy_digest=taxonomy_digest,
            prompt=prompt,
            filtering_config=filtering_config,
            event_id=event_id_factory(),
        )
        for item, decision in zip(work_items, ordered_decisions, strict=True)
    )
    if ledger is not None:
        ledger.append_many(events)
    calls: list[LLMCallResult[FilterBatchEnvelope]] = []
    seen_calls: set[int] = set()
    for decision in ordered_decisions:
        if decision.llm_result is None or id(decision.llm_result) in seen_calls:
            continue
        seen_calls.add(id(decision.llm_result))
        calls.append(decision.llm_result)
    return FilterRunResult(events=events, llm_calls=tuple(calls))


def _filter_batch(
    items: Sequence[WorkItem],
    *,
    batch_index: int,
    client: StructuredChatClient,
    renderer: PromptRenderer,
    taxonomy: TaxonomyConfig,
    model_config: ModelConfig,
    model_aliases: Sequence[str],
    semantic_retry_count: int,
    run_id: str,
) -> tuple[_Decision, ...]:
    expected = {item.paper.arxiv_id: item for item in items}
    accepted: dict[str, _Decision] = {}
    invalid_ids = set(expected)
    invalid_reasons = {
        paper_id: "filter response could not be validated" for paper_id in expected
    }
    last_llm: LLMCallResult[FilterBatchEnvelope] | None = None
    requested_alias = model_aliases[0]

    try:
        first = _request_filter_batch(
            items,
            batch_index=batch_index,
            client=client,
            renderer=renderer,
            taxonomy=taxonomy,
            model_alias=requested_alias,
            run_id=run_id,
        )
    except OpenRouterSemanticError:
        first = None
        invalid_reasons = {
            paper_id: "structured filter envelope was malformed"
            for paper_id in expected
        }
    else:
        last_llm = first
        classified = _classify_response(first.parsed, expected, taxonomy)
        if classified.mapping_safe:
            accepted.update(
                {
                    paper_id: _Decision(result, first, first.requested_model)
                    for paper_id, result in classified.valid.items()
                }
            )
            invalid_ids = set(classified.invalid)
            invalid_reasons = dict(classified.invalid)
        else:
            invalid_reasons = dict(classified.invalid)

    can_retry = (
        invalid_ids and semantic_retry_count > 0 and len(model_aliases) > 1
    )
    if can_retry:
        requested_alias = model_aliases[1]
        retry_items = tuple(
            item for item in items if item.paper.arxiv_id in invalid_ids
        )
        last_llm = None
        try:
            retry = _request_filter_batch(
                retry_items,
                batch_index=batch_index,
                client=client,
                renderer=renderer,
                taxonomy=taxonomy,
                model_alias=requested_alias,
                run_id=run_id,
            )
        except OpenRouterSemanticError:
            invalid_reasons = {
                paper_id: "structured filter envelope remained malformed after retry"
                for paper_id in invalid_ids
            }
        else:
            last_llm = retry
            retry_expected = {
                item.paper.arxiv_id: item for item in retry_items
            }
            classified = _classify_response(retry.parsed, retry_expected, taxonomy)
            if classified.mapping_safe:
                accepted.update(
                    {
                        paper_id: _Decision(result, retry, retry.requested_model)
                        for paper_id, result in classified.valid.items()
                    }
                )
                invalid_ids = set(classified.invalid)
                invalid_reasons = dict(classified.invalid)
            else:
                invalid_reasons = dict(classified.invalid)

    requested_model = model_config.models[requested_alias].model_id
    decisions: list[_Decision] = []
    for item in items:
        paper_id = item.paper.arxiv_id
        decision = accepted.get(paper_id)
        if decision is None:
            decisions.append(
                _Decision(
                    result=None,
                    llm_result=last_llm,
                    requested_model=requested_model,
                    error_message=invalid_reasons.get(
                        paper_id, "filter result remained invalid after retry"
                    ),
                )
            )
        else:
            decisions.append(decision)
    return tuple(decisions)


def _request_filter_batch(
    items: Sequence[WorkItem],
    *,
    batch_index: int,
    client: StructuredChatClient,
    renderer: PromptRenderer,
    taxonomy: TaxonomyConfig,
    model_alias: str,
    run_id: str,
) -> LLMCallResult[FilterBatchEnvelope]:
    prompt = renderer.render_filter(
        taxonomy,
        [
            PromptPaper(
                arxiv_id=item.paper.arxiv_id,
                title=item.paper.title,
                abstract=item.paper.abstract,
                categories=item.paper.categories,
            )
            for item in items
        ],
    )
    return client.structured_chat(
        task_name="filter",
        messages=[
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user},
        ],
        schema=FilterBatchEnvelope,
        model_chain=[model_alias],
        request_metadata={
            "run_id": run_id,
            "batch_index": str(batch_index),
            "paper_count": str(len(items)),
        },
    )


def _classify_response(
    envelope: FilterBatchEnvelope,
    expected: Mapping[str, WorkItem],
    taxonomy: TaxonomyConfig,
) -> _ClassifiedResponse:
    result_ids = [result.arxiv_id for result in envelope.results]
    expected_ids = set(expected)
    if len(result_ids) != len(set(result_ids)):
        message = "filter response contains duplicate result IDs"
        return _ClassifiedResponse({}, dict.fromkeys(expected_ids, message), False)
    if set(result_ids) != expected_ids:
        message = "filter result IDs do not exactly match requested IDs"
        return _ClassifiedResponse({}, dict.fromkeys(expected_ids, message), False)

    valid: dict[str, FilterResult] = {}
    invalid: dict[str, str] = {}
    for wire_result in envelope.results:
        try:
            result = FilterResult.model_validate(wire_result.model_dump())
        except ValidationError:
            invalid[wire_result.arxiv_id] = "filter result schema validation failed"
            continue
        try:
            validate_assignments(taxonomy, result.assignments)
        except TaxonomyAssignmentError as error:
            invalid[wire_result.arxiv_id] = str(error)
            continue
        valid[wire_result.arxiv_id] = result
    return _ClassifiedResponse(valid, invalid, True)


def _build_event(
    item: WorkItem,
    decision: _Decision,
    *,
    run_id: str,
    observed_at: datetime,
    taxonomy: TaxonomyConfig,
    taxonomy_digest: str,
    prompt: RenderedPrompt,
    filtering_config: FilteringConfig,
    event_id: UUID,
) -> ScreeningEvent:
    common: dict[str, object] = {
        "event_id": event_id,
        "run_id": run_id,
        "arxiv_id": item.paper.arxiv_id,
        "observed_at": observed_at,
        "abstract_hash": hashlib.sha256(item.paper.abstract.encode()).hexdigest(),
        "attempt_number": item.next_attempt_number,
        "taxonomy_version": taxonomy.taxonomy_version,
        "taxonomy_hash": taxonomy_digest,
        "filter_prompt_version": prompt.version,
        "filter_prompt_hash": prompt.system_hash,
        "requested_model": decision.requested_model,
    }
    if decision.llm_result is not None:
        common.update(
            actual_model=decision.llm_result.actual_model,
            provider=decision.llm_result.provider,
        )
    if decision.result is not None:
        result = decision.result
        common.update(
            filter_status=(FilterStatus.KEPT if result.keep else FilterStatus.DROPPED),
            relevance=result.relevance,
            novelty=result.novelty,
            topic_assignments=result.assignments,
            reason=result.reason,
        )
    else:
        exhausted = (
            item.next_attempt_number
            >= filtering_config.failed_auto_retry_max_attempts
        )
        common.update(
            filter_status=FilterStatus.FAILED,
            error_type="semantic_validation",
            error_message=decision.error_message
            or "filter result remained invalid after retry",
            retry_exhausted=exhausted,
            next_retry_at=(
                None
                if exhausted
                else observed_at
                + timedelta(hours=filtering_config.failed_retry_cooldown_hours)
            ),
        )
    return ScreeningEvent.model_validate(common)


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("filter observed_at must be timezone-aware")
