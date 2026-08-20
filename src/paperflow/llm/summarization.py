"""Independent selected-paper summary generation and graceful degradation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from dataclasses import dataclass

from paperflow.config import ModelConfig, SummaryConfig
from paperflow.llm.filtering import StructuredChatClient
from paperflow.llm.openrouter import OpenRouterError, OpenRouterSemanticError
from paperflow.llm.structured import (
    LLMCache,
    PromptPaper,
    PromptRenderer,
    RenderedPrompt,
    summary_cache_key,
)
from paperflow.models import (
    CandidatePaper,
    FigureStatus,
    FilterStatus,
    LLMCallResult,
    ScreeningEvent,
    SelectedPaper,
    SummaryContent,
    SummaryResult,
    SummaryStatus,
)


@dataclass(frozen=True)
class SummaryPaperOutcome:
    arxiv_id: str
    status: SummaryStatus
    result: SummaryResult | None
    llm_result: LLMCallResult[SummaryContent] | None
    from_cache: bool
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class SummaryRunResult:
    papers: Mapping[str, SelectedPaper]
    outcomes: tuple[SummaryPaperOutcome, ...]


def build_selected_paper(
    candidate: CandidatePaper,
    event: ScreeningEvent,
    *,
    renderer: PromptRenderer,
) -> SelectedPaper:
    """Create a pending canonical record from one validated KEEP outcome."""
    if event.filter_status != FilterStatus.KEPT:
        raise ValueError("only KEEP events can create selected papers")
    if event.arxiv_id != candidate.arxiv_id:
        raise ValueError("candidate and screening event arXiv IDs must match")
    filter_model = event.actual_model or event.requested_model
    if filter_model is None:
        raise ValueError("KEEP event requires filter model provenance")
    prompt_paper = _prompt_paper(candidate)
    summary_prompt = renderer.render_summary(prompt_paper)
    return SelectedPaper(
        arxiv_id=candidate.arxiv_id,
        source_arxiv_id=candidate.source_arxiv_id,
        title=candidate.title,
        abstract=candidate.abstract,
        authors=candidate.authors,
        categories=candidate.categories,
        arxiv_url=candidate.arxiv_url,
        pdf_url=candidate.pdf_url,
        first_seen_at=event.observed_at,
        first_seen_date=event.observed_at.date(),
        filter_status=FilterStatus.KEPT,
        relevance=event.relevance,
        novelty=event.novelty,
        topic_assignments=event.topic_assignments,
        selection_reason=event.reason,
        summary_status=SummaryStatus.PENDING,
        figure_status=FigureStatus.NOT_IMPLEMENTED,
        taxonomy_version=event.taxonomy_version,
        taxonomy_hash=event.taxonomy_hash,
        filter_prompt_version=event.filter_prompt_version,
        filter_prompt_hash=event.filter_prompt_hash,
        summary_prompt_version=summary_prompt.version,
        summary_prompt_hash=summary_prompt.system_hash,
        filter_model=filter_model,
    )


def collect_summary_targets(
    papers: Mapping[str, SelectedPaper],
) -> tuple[SelectedPaper, ...]:
    """Select only pending or prior-failed KEEP records in stable store order."""
    return tuple(
        paper
        for paper in papers.values()
        if paper.filter_status == FilterStatus.KEPT
        and paper.summary_status in {SummaryStatus.PENDING, SummaryStatus.FAILED}
    )


def summarize_selected(
    papers: Mapping[str, SelectedPaper],
    *,
    client: StructuredChatClient,
    renderer: PromptRenderer,
    model_config: ModelConfig,
    summary_config: SummaryConfig,
    cache: LLMCache | None = None,
    run_id: str,
) -> SummaryRunResult:
    """Summarize targets concurrently without changing selected membership."""
    if not run_id.strip():
        raise ValueError("summary run_id cannot be empty")
    targets = collect_summary_targets(papers)
    if not targets:
        return SummaryRunResult(papers=dict(papers), outcomes=())
    task_chain = model_config.tasks.get("summary")
    if task_chain is None:
        raise ValueError("model configuration has no summary task")
    aliases = [task_chain.primary, *task_chain.fallbacks]
    indexed_outcomes: dict[int, SummaryPaperOutcome] = {}

    with ThreadPoolExecutor(max_workers=summary_config.concurrency) as executor:
        futures = {
            executor.submit(
                _summarize_one,
                paper,
                client=client,
                renderer=renderer,
                model_config=model_config,
                model_aliases=aliases,
                semantic_retry_count=summary_config.semantic_retry_count,
                cache=cache,
                run_id=run_id,
            ): index
            for index, paper in enumerate(targets)
        }
        for future in as_completed(futures):
            indexed_outcomes[futures[future]] = future.result()

    outcomes = tuple(indexed_outcomes[index] for index in range(len(targets)))
    updated = dict(papers)
    for outcome in outcomes:
        updated[outcome.arxiv_id] = _apply_outcome(
            updated[outcome.arxiv_id], outcome
        )
    if set(updated) != set(papers):
        raise AssertionError("summary processing changed selected-paper membership")
    return SummaryRunResult(papers=updated, outcomes=outcomes)


def summary_or_abstract(paper: SelectedPaper) -> str:
    """Return the generated display summary or the required abstract fallback."""
    if paper.summary_status == SummaryStatus.GENERATED:
        return paper.tldr
    return paper.abstract


def _summarize_one(
    paper: SelectedPaper,
    *,
    client: StructuredChatClient,
    renderer: PromptRenderer,
    model_config: ModelConfig,
    model_aliases: Sequence[str],
    semantic_retry_count: int,
    cache: LLMCache | None,
    run_id: str,
) -> SummaryPaperOutcome:
    prompt_paper = PromptPaper(
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        abstract=paper.abstract,
        categories=paper.categories,
    )
    prompt = renderer.render_summary(prompt_paper)

    if cache is not None:
        for alias in model_aliases:
            model_id = model_config.models[alias].model_id
            cached = cache.load(
                summary_cache_key(prompt_paper, prompt, model_id), SummaryContent
            )
            if cached is not None:
                return _success_outcome(paper.arxiv_id, cached, from_cache=True)

    alias = model_aliases[0]
    try:
        llm_result = _request_summary(
            paper,
            client=client,
            prompt=prompt,
            model_alias=alias,
            run_id=run_id,
        )
    except OpenRouterSemanticError as first_error:
        if semantic_retry_count <= 0 or len(model_aliases) <= 1:
            return _failure_outcome(paper.arxiv_id, first_error)
        alias = model_aliases[1]
        try:
            llm_result = _request_summary(
                paper,
                client=client,
                prompt=prompt,
                model_alias=alias,
                run_id=run_id,
            )
        except OpenRouterError as retry_error:
            return _failure_outcome(paper.arxiv_id, retry_error)
    except OpenRouterError as error:
        return _failure_outcome(paper.arxiv_id, error)

    if cache is not None:
        model_id = model_config.models[alias].model_id
        with suppress(OSError, ValueError):
            cache.store(summary_cache_key(prompt_paper, prompt, model_id), llm_result)
    return _success_outcome(paper.arxiv_id, llm_result, from_cache=False)


def _request_summary(
    paper: SelectedPaper,
    *,
    client: StructuredChatClient,
    prompt: RenderedPrompt,
    model_alias: str,
    run_id: str,
) -> LLMCallResult[SummaryContent]:
    return client.structured_chat(
        task_name="summary",
        messages=[
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user},
        ],
        schema=SummaryContent,
        model_chain=[model_alias],
        request_metadata={"run_id": run_id, "arxiv_id": paper.arxiv_id},
    )


def _success_outcome(
    arxiv_id: str,
    llm_result: LLMCallResult[SummaryContent],
    *,
    from_cache: bool,
) -> SummaryPaperOutcome:
    content = llm_result.parsed
    return SummaryPaperOutcome(
        arxiv_id=arxiv_id,
        status=SummaryStatus.GENERATED,
        result=SummaryResult(arxiv_id=arxiv_id, **content.model_dump()),
        llm_result=llm_result,
        from_cache=from_cache,
    )


def _failure_outcome(arxiv_id: str, error: OpenRouterError) -> SummaryPaperOutcome:
    return SummaryPaperOutcome(
        arxiv_id=arxiv_id,
        status=SummaryStatus.FAILED,
        result=None,
        llm_result=None,
        from_cache=False,
        error_type=type(error).__name__,
        error_message="summary generation failed; abstract fallback retained",
    )


def _apply_outcome(
    paper: SelectedPaper, outcome: SummaryPaperOutcome
) -> SelectedPaper:
    data = paper.model_dump(mode="python")
    if outcome.result is None:
        data.update(
            summary_status=SummaryStatus.FAILED,
            tldr=None,
            bullets=[],
            problem=None,
            method=None,
            contribution=None,
            summary_model=None,
        )
    else:
        result = outcome.result
        if outcome.llm_result is None:
            raise AssertionError("generated summary requires LLM provenance")
        data.update(
            summary_status=SummaryStatus.GENERATED,
            tldr=result.tldr,
            bullets=result.bullets,
            problem=result.problem,
            method=result.method,
            contribution=result.contribution,
            summary_model=(
                outcome.llm_result.actual_model
                or outcome.llm_result.requested_model
            ),
        )
    return SelectedPaper.model_validate(data)


def _prompt_paper(candidate: CandidatePaper) -> PromptPaper:
    return PromptPaper(
        arxiv_id=candidate.arxiv_id,
        title=candidate.title,
        abstract=candidate.abstract,
        categories=candidate.categories,
    )
