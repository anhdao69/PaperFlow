from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from uuid import UUID

import pytest
from pydantic import ValidationError

from paperflow.config import load_config_bundle
from paperflow.llm.openrouter import (
    OpenRouterSemanticError,
    OpenRouterTransportError,
)
from paperflow.llm.structured import LLMCache, PromptRenderer
from paperflow.llm.summarization import (
    build_selected_paper,
    collect_summary_targets,
    summarize_selected,
    summary_or_abstract,
)
from paperflow.models import (
    CandidatePaper,
    FigureStatus,
    FilterStatus,
    LLMCallResult,
    ScreeningEvent,
    SelectedPaper,
    SummaryContent,
    SummaryStatus,
    TopicAssignment,
)

ROOT = Path(__file__).parents[3]
HASH = "c" * 64
NOW = datetime(2026, 8, 20, 21, tzinfo=UTC)


class FakeSummaryClient:
    def __init__(self, responses: list[dict[str, object] | Exception]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []
        self._lock = Lock()

    def structured_chat(
        self,
        *,
        task_name: str,
        messages: list[dict[str, str]],
        schema: type[SummaryContent],
        model_chain: list[str],
        request_metadata: dict[str, str],
    ) -> LLMCallResult[SummaryContent]:
        with self._lock:
            response = self.responses.pop(0)
            self.calls.append(
                {
                    "task_name": task_name,
                    "messages": messages,
                    "model_chain": model_chain,
                    "metadata": request_metadata,
                }
            )
        if isinstance(response, Exception):
            raise response
        model_id = load_config_bundle(ROOT).models.models[model_chain[0]].model_id
        return LLMCallResult[SummaryContent](
            parsed=schema.model_validate(response),
            requested_model=model_id,
            actual_model=model_id,
            provider="FixtureProvider",
            input_tokens=30,
            output_tokens=15,
            cached_input_tokens=4,
            cost_usd=0.00003,
            latency_ms=8,
            request_id=f"summary-{len(self.calls)}",
            attempt=1,
        )


class FailingWriteCache(LLMCache):
    def store(self, key, result):
        del key, result
        raise OSError("fixture cache unavailable")


def _content(label: str = "fixture") -> dict[str, object]:
    return {
        "tldr": f"A concise {label} summary.",
        "bullets": ["Problem.", "Method.", "Contribution."],
        "problem": "A relevant problem.",
        "method": "A tested method.",
        "contribution": "A clear contribution.",
    }


def _paper(
    number: int,
    status: SummaryStatus = SummaryStatus.PENDING,
) -> SelectedPaper:
    arxiv_id = f"2608.{number:05d}"
    generated = status == SummaryStatus.GENERATED
    return SelectedPaper(
        arxiv_id=arxiv_id,
        source_arxiv_id=f"{arxiv_id}v1",
        title=f"Selected Fixture {number}",
        abstract=f"Original abstract fallback {number}.",
        authors=["Fixture Author"],
        categories=["cs.AI"],
        arxiv_url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
        first_seen_at=NOW,
        first_seen_date=NOW.date(),
        filter_status=FilterStatus.KEPT,
        relevance=9,
        novelty=8,
        topic_assignments=[
            TopicAssignment(
                topic_id="embodied-ai", subtopic_ids=["robot-learning"]
            )
        ],
        selection_reason="Directly relevant fixture.",
        summary_status=status,
        tldr="Existing generated summary." if generated else None,
        bullets=["One.", "Two.", "Three."] if generated else [],
        hero_figure=None,
        figure_status=FigureStatus.NOT_IMPLEMENTED,
        taxonomy_version=1,
        taxonomy_hash=HASH,
        filter_prompt_version="filter-v3",
        filter_prompt_hash=HASH,
        summary_prompt_version="summary-v2",
        summary_prompt_hash=HASH,
        filter_model="deepseek/deepseek-v4-flash-0731",
        summary_model="openai/gpt-5.6-luna" if generated else None,
    )


def _summarize(
    papers: dict[str, SelectedPaper],
    client: FakeSummaryClient,
    *,
    tmp_path: Path,
    cache: LLMCache | None = None,
    semantic_retries: int = 1,
    concurrency: int = 1,
):
    bundle = load_config_bundle(ROOT)
    config = bundle.runtime.summaries.model_copy(
        update={
            "semantic_retry_count": semantic_retries,
            "concurrency": concurrency,
        }
    )
    return summarize_selected(
        papers,
        client=client,
        renderer=PromptRenderer(ROOT / "configs/prompts", bundle.prompts),
        model_config=bundle.models,
        summary_config=config,
        cache=cache,
        run_id="fixture-summary-run",
    )


@pytest.mark.parametrize("bullet_count", [2, 6])
def test_summary_content_requires_three_to_five_bullets(
    bullet_count: int,
) -> None:
    data = _content()
    data["bullets"] = [f"Bullet {index}." for index in range(bullet_count)]

    with pytest.raises(ValidationError):
        SummaryContent.model_validate(data)


def test_summary_content_requires_nonempty_tldr() -> None:
    data = _content()
    data["tldr"] = "  "

    with pytest.raises(ValidationError):
        SummaryContent.model_validate(data)


def test_collect_targets_includes_pending_and_failed_but_not_generated() -> None:
    pending = _paper(30001)
    failed = _paper(30002, SummaryStatus.FAILED)
    generated = _paper(30003, SummaryStatus.GENERATED)

    targets = collect_summary_targets(
        {
            pending.arxiv_id: pending,
            failed.arxiv_id: failed,
            generated.arxiv_id: generated,
        }
    )

    assert targets == (pending, failed)


def test_success_generates_summary_and_captures_provenance(tmp_path: Path) -> None:
    paper = _paper(30001)

    run = _summarize(
        {paper.arxiv_id: paper},
        FakeSummaryClient([_content()]),
        tmp_path=tmp_path,
    )
    updated = run.papers[paper.arxiv_id]

    assert updated.summary_status == SummaryStatus.GENERATED
    assert updated.tldr == "A concise fixture summary."
    assert len(updated.bullets) == 3
    assert updated.summary_model == "openai/gpt-5.6-luna"
    assert run.outcomes[0].llm_result.cost_usd == 0.00003
    assert run.outcomes[0].llm_result.provider == "FixtureProvider"
    assert summary_or_abstract(updated) == updated.tldr


def test_semantic_failure_retries_once_on_next_model(tmp_path: Path) -> None:
    paper = _paper(30001)
    client = FakeSummaryClient(
        [OpenRouterSemanticError("bad schema"), _content("retry")]
    )

    run = _summarize(
        {paper.arxiv_id: paper}, client, tmp_path=tmp_path
    )

    assert run.papers[paper.arxiv_id].summary_status == SummaryStatus.GENERATED
    assert run.papers[paper.arxiv_id].summary_model == (
        "deepseek/deepseek-v4-flash-0731"
    )
    assert [call["model_chain"] for call in client.calls] == [
        ["gpt_5_6_luna"],
        ["deepseek_v4_flash"],
    ]


def test_second_semantic_failure_preserves_selected_paper_with_fallback(
    tmp_path: Path,
) -> None:
    paper = _paper(30001)
    client = FakeSummaryClient(
        [OpenRouterSemanticError("bad first"), OpenRouterSemanticError("bad second")]
    )

    run = _summarize(
        {paper.arxiv_id: paper}, client, tmp_path=tmp_path
    )
    failed = run.papers[paper.arxiv_id]

    assert set(run.papers) == {paper.arxiv_id}
    assert failed.filter_status == FilterStatus.KEPT
    assert failed.topic_assignments == paper.topic_assignments
    assert failed.relevance == paper.relevance
    assert failed.summary_status == SummaryStatus.FAILED
    assert failed.tldr is None
    assert failed.bullets == []
    assert summary_or_abstract(failed) == paper.abstract
    assert len(client.calls) == 2


def test_exhausted_transient_failure_degrades_without_semantic_retry(
    tmp_path: Path,
) -> None:
    paper = _paper(30001)
    client = FakeSummaryClient([OpenRouterTransportError("timeout")])

    run = _summarize(
        {paper.arxiv_id: paper}, client, tmp_path=tmp_path
    )

    assert run.papers[paper.arxiv_id].summary_status == SummaryStatus.FAILED
    assert len(client.calls) == 1
    assert run.outcomes[0].error_message == (
        "summary generation failed; abstract fallback retained"
    )


def test_prior_failed_summary_retries_successfully(tmp_path: Path) -> None:
    paper = _paper(30001, SummaryStatus.FAILED)

    run = _summarize(
        {paper.arxiv_id: paper},
        FakeSummaryClient([_content("later")]),
        tmp_path=tmp_path,
    )

    assert run.papers[paper.arxiv_id].summary_status == SummaryStatus.GENERATED
    assert run.papers[paper.arxiv_id].tldr == "A concise later summary."


def test_cache_hit_avoids_network_and_updates_paper(tmp_path: Path) -> None:
    cache = LLMCache(tmp_path / "cache")
    paper = _paper(30001)
    first_client = FakeSummaryClient([_content("cached")])
    first = _summarize(
        {paper.arxiv_id: paper},
        first_client,
        tmp_path=tmp_path,
        cache=cache,
    )
    assert first.papers[paper.arxiv_id].summary_status == SummaryStatus.GENERATED

    empty_client = FakeSummaryClient([])
    second = _summarize(
        {paper.arxiv_id: paper},
        empty_client,
        tmp_path=tmp_path,
        cache=cache,
    )

    assert second.papers[paper.arxiv_id].tldr == "A concise cached summary."
    assert second.outcomes[0].from_cache is True
    assert empty_client.calls == []


def test_cache_write_failure_does_not_change_correctness(tmp_path: Path) -> None:
    paper = _paper(30001)

    run = _summarize(
        {paper.arxiv_id: paper},
        FakeSummaryClient([_content()]),
        tmp_path=tmp_path,
        cache=FailingWriteCache(tmp_path / "unavailable"),
    )

    assert run.papers[paper.arxiv_id].summary_status == SummaryStatus.GENERATED


def test_generated_paper_is_not_resummarized(tmp_path: Path) -> None:
    paper = _paper(30001, SummaryStatus.GENERATED)
    client = FakeSummaryClient([])

    run = _summarize(
        {paper.arxiv_id: paper}, client, tmp_path=tmp_path
    )

    assert run.papers[paper.arxiv_id] == paper
    assert run.outcomes == ()
    assert client.calls == []


def test_build_selected_paper_from_keep_starts_pending() -> None:
    candidate = CandidatePaper(
        arxiv_id="2608.30001",
        source_arxiv_id="2608.30001v1",
        title="Newly Kept Paper",
        abstract="A robot learning abstract.",
        authors=["Fixture Author"],
        categories=["cs.RO"],
        arxiv_url="https://arxiv.org/abs/2608.30001",
        pdf_url="https://arxiv.org/pdf/2608.30001",
    )
    event = ScreeningEvent(
        event_id=UUID(int=1),
        run_id="fixture-run",
        arxiv_id=candidate.arxiv_id,
        observed_at=NOW,
        abstract_hash=HASH,
        filter_status=FilterStatus.KEPT,
        attempt_number=1,
        relevance=9,
        novelty=8,
        topic_assignments=[
            TopicAssignment(
                topic_id="embodied-ai", subtopic_ids=["robot-learning"]
            )
        ],
        reason="Directly relevant.",
        taxonomy_version=1,
        taxonomy_hash=HASH,
        filter_prompt_version="filter-v3",
        filter_prompt_hash=HASH,
        requested_model="deepseek/deepseek-v4-flash-0731",
        actual_model="deepseek/deepseek-v4-flash-0731",
        provider="FixtureProvider",
    )
    bundle = load_config_bundle(ROOT)

    selected = build_selected_paper(
        candidate,
        event,
        renderer=PromptRenderer(ROOT / "configs/prompts", bundle.prompts),
    )

    assert selected.summary_status == SummaryStatus.PENDING
    assert selected.filter_status == FilterStatus.KEPT
    assert selected.summary_prompt_version == "summary-v2"
    assert selected.tldr is None
    assert selected.bullets == []


def test_build_selected_rejects_drop_event() -> None:
    candidate = CandidatePaper(
        arxiv_id="2608.30001",
        source_arxiv_id="2608.30001v1",
        title="Dropped Paper",
        abstract="An unrelated abstract.",
        authors=["Fixture Author"],
        categories=["cs.AI"],
        arxiv_url="https://arxiv.org/abs/2608.30001",
        pdf_url="https://arxiv.org/pdf/2608.30001",
    )
    event = ScreeningEvent(
        event_id=UUID(int=1),
        run_id="fixture-run",
        arxiv_id=candidate.arxiv_id,
        observed_at=NOW,
        abstract_hash=HASH,
        filter_status=FilterStatus.DROPPED,
        attempt_number=1,
        relevance=1,
        novelty=2,
        reason="Outside scope.",
        taxonomy_version=1,
        taxonomy_hash=HASH,
        filter_prompt_version="filter-v3",
        filter_prompt_hash=HASH,
        requested_model="deepseek/deepseek-v4-flash-0731",
    )
    bundle = load_config_bundle(ROOT)

    with pytest.raises(ValueError, match="KEEP"):
        build_selected_paper(
            candidate,
            event,
            renderer=PromptRenderer(ROOT / "configs/prompts", bundle.prompts),
        )
