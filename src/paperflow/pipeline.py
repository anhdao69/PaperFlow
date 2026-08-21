"""End-to-end PaperFlow run orchestration with injectable network boundaries."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from paperflow.arxiv_client import ArxivSourceError, save_raw_snapshot
from paperflow.config import load_config_bundle
from paperflow.llm.filtering import (
    FilterRunResult,
    StructuredChatClient,
    filter_workset,
)
from paperflow.llm.structured import LLMCache, PromptRenderer
from paperflow.llm.summarization import (
    SummaryRunResult,
    build_selected_paper,
    collect_summary_targets,
    summarize_selected,
)
from paperflow.models import (
    CandidatePaper,
    FilterStatus,
    RawArxivEntry,
    RunState,
    RunStats,
    SelectedPaper,
    SummaryStatus,
)
from paperflow.normalize import normalize_and_deduplicate
from paperflow.observability import (
    aggregate_llm_usage,
    render_run_report,
    save_run_stats,
    structured_event,
)
from paperflow.paper_store import (
    load_run_state,
    load_selected_store,
    save_run_state,
    save_selected_store,
)
from paperflow.render.contracts import FeedIndex
from paperflow.render.validation import publish_outputs, validate_repository
from paperflow.render.view_models import build_public_projection
from paperflow.retry_queue import (
    ExclusionReason,
    MetadataRefetcher,
    WorkReason,
    determine_workset,
)
from paperflow.schedule import evaluate_schedule
from paperflow.screening_ledger import ScreeningLedger
from paperflow.taxonomy import load_taxonomy, taxonomy_hash


class DailySourceClient(Protocol):
    def fetch_new(
        self, categories: Sequence[str], *, timeout_seconds: float
    ) -> list[RawArxivEntry]: ...


@dataclass(frozen=True)
class PipelineDependencies:
    source_client: DailySourceClient
    refetcher: MetadataRefetcher
    llm_client_factory: Callable[[], StructuredChatClient]
    now: Callable[[], datetime] = lambda: datetime.now(UTC)
    run_id_factory: Callable[[datetime], str] = lambda now: now.isoformat()


@dataclass(frozen=True)
class PipelineRunResult:
    ran: bool
    run_id: str | None
    stats: RunStats | None
    reason: str


def run_pipeline(
    root: Path,
    dependencies: PipelineDependencies,
    *,
    manual: bool,
    manual_override_ids: Sequence[str] = (),
    maintenance_only: bool = False,
) -> PipelineRunResult:
    """Execute one validated run; callers commit only after this returns."""
    root = root.resolve()
    bundle = load_config_bundle(root)
    taxonomy = load_taxonomy(root / "configs/topics.yaml")
    renderer = PromptRenderer(root / "configs/prompts", bundle.prompts)
    renderer.validate_templates()
    state = load_run_state(root / "data/state.json")
    instant = dependencies.now()
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("pipeline clock must return a timezone-aware timestamp")
    local_now = instant.astimezone(ZoneInfo(bundle.runtime.timezone))
    decision = evaluate_schedule(bundle.runtime, state, now=instant, manual=manual)
    if not decision.due:
        structured_event("run_skipped", reason=decision.reason)
        return PipelineRunResult(False, None, None, decision.reason)

    run_id = dependencies.run_id_factory(instant)
    structured_event("run_started", run_id=run_id)
    structured_event("config_loaded", run_id=run_id)
    structured_event("taxonomy_validated", run_id=run_id)
    selected = load_selected_store(root / "data/papers.json", taxonomy)
    ledger = ScreeningLedger(root / "data/screening_events")
    latest = ledger.load_latest()

    try:
        entries = (
            []
            if maintenance_only
            else dependencies.source_client.fetch_new(
                bundle.runtime.source.categories,
                timeout_seconds=bundle.runtime.source.request_timeout_seconds,
            )
        )
    except ArxivSourceError:
        failed_stats = _empty_source_failure_stats(run_id, local_now, bundle.runtime)
        stats_path = _stats_path(root, local_now)
        if bundle.runtime.observability.persist_run_stats and not stats_path.exists():
            save_run_stats(stats_path, failed_stats)
        structured_event("run_failed", run_id=run_id, error_type="source_failure")
        print(render_run_report(failed_stats))
        raise
    structured_event("source_fetch_completed", run_id=run_id, fetched=len(entries))
    save_raw_snapshot(root / ".cache/paperflow", run_id, entries)
    candidates = normalize_and_deduplicate(entries)
    source_candidate_count = len(candidates)
    existing_candidate_ids = {paper.arxiv_id for paper in candidates}
    for paper_id in manual_override_ids:
        if paper_id in selected.papers and paper_id not in existing_candidate_ids:
            candidates.append(_candidate_from_selected(selected.papers[paper_id]))
            existing_candidate_ids.add(paper_id)
    structured_event(
        "dedup_completed", run_id=run_id, deduplicated=len(candidates)
    )
    workset = determine_workset(
        candidates,
        latest,
        now=local_now,
        retry_config=bundle.runtime.filtering,
        refetcher=dependencies.refetcher,
        manual_override_ids=manual_override_ids,
    )
    structured_event(
        "retry_backlog_built",
        run_id=run_id,
        work_items=len(workset.items),
        exclusions=len(workset.exclusions),
    )

    llm_client: StructuredChatClient | None = None

    def client() -> StructuredChatClient:
        nonlocal llm_client
        if llm_client is None:
            llm_client = dependencies.llm_client_factory()
        return llm_client

    if workset.items:
        structured_event(
            "filter_batch_started", run_id=run_id, papers=len(workset.items)
        )
        filtered = filter_workset(
            workset.items,
            client=client(),
            renderer=renderer,
            taxonomy=taxonomy,
            model_config=bundle.models,
            filtering_config=bundle.runtime.filtering,
            ledger=ledger,
            run_id=run_id,
            observed_at=local_now,
        )
        structured_event(
            "filter_batch_completed", run_id=run_id, papers=len(filtered.events)
        )
    else:
        filtered = FilterRunResult(events=())

    papers = _merge_filter_results(
        selected.papers,
        workset.items,
        filtered,
        renderer=renderer,
        manual_override_ids=set(manual_override_ids),
    )
    targets = collect_summary_targets(papers)
    if targets:
        structured_event("summary_started", run_id=run_id, papers=len(targets))
        summarized = summarize_selected(
            papers,
            client=client(),
            renderer=renderer,
            model_config=bundle.models,
            summary_config=bundle.runtime.summaries,
            cache=LLMCache(root / ".cache/paperflow"),
            run_id=run_id,
        )
        structured_event(
            "summary_completed", run_id=run_id, papers=len(summarized.outcomes)
        )
    else:
        summarized = SummaryRunResult(papers=papers, outcomes=())

    successful_dates = _successful_dates(root)
    successful_dates.add(local_now.date())
    projection = build_public_projection(
        summarized.papers,
        taxonomy,
        generated_at=local_now,
        timezone=bundle.runtime.timezone,
        base_url=str(bundle.runtime.publishing.base_url),
        successful_dates=successful_dates,
    )
    paths = publish_outputs(
        root,
        projection,
        taxonomy,
        readme_latest_limit=bundle.runtime.publishing.readme_latest_limit,
    )
    structured_event("render_completed", run_id=run_id, files=len(paths))
    save_selected_store(root / "data/papers.json", dict(summarized.papers), taxonomy)

    stats = _build_stats(
        run_id,
        local_now,
        bundle.runtime,
        entries=entries,
        source_candidate_count=source_candidate_count,
        workset=workset,
        filtered=filtered,
        summarized=summarized,
    )
    if bundle.runtime.observability.persist_run_stats:
        save_run_stats(_stats_path(root, local_now), stats)
    success_state = RunState(
        last_successful_run_id=run_id,
        last_successful_at=local_now,
        last_successful_local_date=local_now.date(),
        taxonomy_hash=taxonomy_hash(taxonomy),
        runtime_config_hash=bundle.runtime_hash,
        model_config_hash=bundle.model_hash,
    )
    save_run_state(
        root / "data/state.json", success_state, publication_validated=True
    )
    validate_repository(root)
    structured_event("validation_completed", run_id=run_id)
    structured_event("run_succeeded", run_id=run_id, cost_usd=stats.llm_cost_usd)
    print(render_run_report(stats))
    return PipelineRunResult(True, run_id, stats, "success")


def _merge_filter_results(
    existing: dict[str, SelectedPaper],
    work_items,
    filtered: FilterRunResult,
    *,
    renderer: PromptRenderer,
    manual_override_ids: set[str],
) -> dict[str, SelectedPaper]:
    papers = dict(existing)
    candidate_by_id: dict[str, CandidatePaper] = {
        item.paper.arxiv_id: item.paper for item in work_items
    }
    for event in filtered.events:
        prior = papers.get(event.arxiv_id)
        if event.filter_status == FilterStatus.KEPT:
            updated = build_selected_paper(
                candidate_by_id[event.arxiv_id], event, renderer=renderer
            )
            if prior is not None:
                updated = updated.model_copy(
                    update={
                        "first_seen_at": prior.first_seen_at,
                        "first_seen_date": prior.first_seen_date,
                    }
                )
            if (
                prior is not None
                and prior.abstract == updated.abstract
                and prior.summary_prompt_hash == updated.summary_prompt_hash
                and prior.summary_status == SummaryStatus.GENERATED
            ):
                updated = updated.model_copy(
                    update={
                        "summary_status": prior.summary_status,
                        "tldr": prior.tldr,
                        "bullets": prior.bullets,
                        "problem": prior.problem,
                        "method": prior.method,
                        "contribution": prior.contribution,
                        "summary_model": prior.summary_model,
                        "hero_figure": prior.hero_figure,
                        "figure_status": prior.figure_status,
                    }
                )
            papers[event.arxiv_id] = updated
        elif (
            event.filter_status == FilterStatus.DROPPED
            and event.arxiv_id in manual_override_ids
        ):
            papers.pop(event.arxiv_id, None)
    return papers


def _candidate_from_selected(paper: SelectedPaper) -> CandidatePaper:
    return CandidatePaper(
        arxiv_id=paper.arxiv_id,
        source_arxiv_id=paper.source_arxiv_id,
        title=paper.title,
        abstract=paper.abstract,
        authors=paper.authors,
        categories=paper.categories,
        arxiv_url=paper.arxiv_url,
        pdf_url=paper.pdf_url,
    )


def _build_stats(
    run_id,
    local_now,
    runtime,
    *,
    entries,
    source_candidate_count,
    workset,
    filtered,
    summarized,
) -> RunStats:
    calls = [*filtered.llm_calls]
    calls.extend(
        outcome.llm_result
        for outcome in summarized.outcomes
        if outcome.llm_result is not None and not outcome.from_cache
    )
    breakdown = aggregate_llm_usage(calls)
    events = filtered.events
    return RunStats(
        run_id=run_id,
        date=local_now.date(),
        source_ok=True,
        fetched=len(entries),
        deduplicated=source_candidate_count,
        terminal_skipped=sum(
            exclusion.reason
            in {ExclusionReason.TERMINAL_KEPT, ExclusionReason.TERMINAL_DROPPED}
            for exclusion in workset.exclusions
        ),
        failed_backlog_added=sum(
            item.reason == WorkReason.FAILED_BACKLOG for item in workset.items
        ),
        screened=len(events),
        kept=sum(event.filter_status == FilterStatus.KEPT for event in events),
        dropped=sum(event.filter_status == FilterStatus.DROPPED for event in events),
        filter_failed=sum(
            event.filter_status == FilterStatus.FAILED for event in events
        ),
        summary_generated=sum(
            outcome.status == SummaryStatus.GENERATED
            for outcome in summarized.outcomes
        ),
        summary_failed=sum(
            outcome.status == SummaryStatus.FAILED for outcome in summarized.outcomes
        ),
        figure_mode=(
            "extraction"
            if runtime.figures.enabled
            else "placeholder"
            if runtime.figures.iphone_placeholder
            else "disabled"
        ),
        llm_input_tokens=sum(item.input_tokens for item in breakdown.values()),
        llm_output_tokens=sum(item.output_tokens for item in breakdown.values()),
        llm_cached_input_tokens=sum(
            item.cached_input_tokens for item in breakdown.values()
        ),
        llm_cost_usd=sum(item.cost_usd for item in breakdown.values()),
        model_breakdown=breakdown,
    )


def _empty_source_failure_stats(run_id, local_now, runtime) -> RunStats:
    return RunStats(
        run_id=run_id,
        date=local_now.date(),
        source_ok=False,
        fetched=0,
        deduplicated=0,
        terminal_skipped=0,
        failed_backlog_added=0,
        screened=0,
        kept=0,
        dropped=0,
        filter_failed=0,
        summary_generated=0,
        summary_failed=0,
        figure_mode=(
            "placeholder" if runtime.figures.iphone_placeholder else "disabled"
        ),
        llm_input_tokens=0,
        llm_output_tokens=0,
        llm_cached_input_tokens=0,
        llm_cost_usd=0,
        model_breakdown={},
    )


def _successful_dates(root: Path) -> set:
    path = root / "data/feed_index.json"
    if not path.exists():
        return set()
    index = FeedIndex.model_validate_json(path.read_text(encoding="utf-8"))
    return {day.date for day in index.days}


def _stats_path(root: Path, local_now: datetime) -> Path:
    return root / "data/run_stats" / f"{local_now.date().isoformat()}.json"
