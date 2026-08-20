from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from paperflow.config import load_config_bundle
from paperflow.llm.openrouter import OpenRouterSemanticError
from paperflow.llm.structured import LLMCache, PromptRenderer
from paperflow.llm.summarization import summarize_selected, summary_or_abstract
from paperflow.models import (
    FigureStatus,
    FilterStatus,
    LLMCallResult,
    SelectedPaper,
    SummaryContent,
    SummaryStatus,
    TopicAssignment,
)
from paperflow.paper_store import load_selected_store, save_selected_store
from paperflow.taxonomy import load_taxonomy

ROOT = Path(__file__).parents[2]
HASH = "d" * 64
NOW = datetime(2026, 8, 20, 21, tzinfo=UTC)


class MixedFixtureSummaryClient:
    def __init__(self, behavior: dict[str, str]) -> None:
        self.behavior = behavior
        self.calls: list[tuple[str, str]] = []
        self.counts: defaultdict[str, int] = defaultdict(int)
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
        del task_name, messages
        paper_id = request_metadata["arxiv_id"]
        with self._lock:
            self.counts[paper_id] += 1
            self.calls.append((paper_id, model_chain[0]))
        if self.behavior[paper_id] == "semantic_failure":
            raise OpenRouterSemanticError("deterministic malformed summary")
        model_id = load_config_bundle(ROOT).models.models[model_chain[0]].model_id
        return LLMCallResult[SummaryContent](
            parsed=schema(
                tldr=f"Generated summary for {paper_id}.",
                bullets=["Problem.", "Method.", "Contribution."],
            ),
            requested_model=model_id,
            actual_model=model_id,
            provider="DeterministicFixture",
            input_tokens=40,
            output_tokens=20,
            cost_usd=0.00004,
            latency_ms=10,
            request_id=f"mixed-{paper_id}",
            attempt=1,
        )


def _selected(data: dict[str, str]) -> SelectedPaper:
    paper_id = data["arxiv_id"]
    return SelectedPaper(
        arxiv_id=paper_id,
        source_arxiv_id=f"{paper_id}v1",
        title=data["title"],
        abstract=data["abstract"],
        authors=["Deterministic Fixture"],
        categories=["cs.AI"],
        arxiv_url=f"https://arxiv.org/abs/{paper_id}",
        pdf_url=f"https://arxiv.org/pdf/{paper_id}",
        first_seen_at=NOW,
        first_seen_date=NOW.date(),
        filter_status=FilterStatus.KEPT,
        relevance=9,
        novelty=7,
        topic_assignments=[
            TopicAssignment(
                topic_id="embodied-ai", subtopic_ids=["robot-learning"]
            )
        ],
        selection_reason="Selected deterministic fixture.",
        summary_status=SummaryStatus(data["summary_status"]),
        figure_status=FigureStatus.NOT_IMPLEMENTED,
        taxonomy_version=1,
        taxonomy_hash=HASH,
        filter_prompt_version="filter-v3",
        filter_prompt_hash=HASH,
        summary_prompt_version="summary-v2",
        summary_prompt_hash=HASH,
        filter_model="deepseek/deepseek-v4-flash-0731",
    )


def test_mixed_summary_failures_preserve_all_selected_members_and_fallback(
    tmp_path: Path,
) -> None:
    fixture = json.loads(
        (ROOT / "tests/fixtures/pipeline/summary_mixed.json").read_text()
    )
    papers = {
        data["arxiv_id"]: _selected(data) for data in fixture["papers"]
    }
    behavior = {
        data["arxiv_id"]: data["behavior"] for data in fixture["papers"]
    }
    client = MixedFixtureSummaryClient(behavior)
    bundle = load_config_bundle(ROOT)

    run = summarize_selected(
        papers,
        client=client,
        renderer=PromptRenderer(ROOT / "configs/prompts", bundle.prompts),
        model_config=bundle.models,
        summary_config=bundle.runtime.summaries,
        cache=LLMCache(tmp_path / "cache"),
        run_id="mixed-summary-fixture",
    )
    path = tmp_path / "papers.json"
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")
    save_selected_store(path, dict(run.papers), taxonomy)
    reloaded = load_selected_store(path, taxonomy)

    counts = {
        status.value: sum(
            paper.summary_status == status for paper in reloaded.papers.values()
        )
        for status in (SummaryStatus.GENERATED, SummaryStatus.FAILED)
    }
    assert counts == {
        "generated": fixture["expected"]["generated"],
        "failed": fixture["expected"]["failed"],
    }
    assert len(reloaded.papers) == fixture["expected"]["membership"]
    assert set(reloaded.papers) == set(papers)
    failed = reloaded.papers["2608.31002"]
    assert failed.filter_status == FilterStatus.KEPT
    assert failed.topic_assignments == papers[failed.arxiv_id].topic_assignments
    assert summary_or_abstract(failed) == failed.abstract
    assert client.counts["2608.31002"] == 2
    assert client.counts["2608.31003"] == 1
    assert reloaded.papers["2608.31003"].summary_status == SummaryStatus.GENERATED
