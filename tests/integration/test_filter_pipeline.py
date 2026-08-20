from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from paperflow.config import load_config_bundle
from paperflow.llm.filtering import FilterBatchEnvelope, filter_workset
from paperflow.llm.structured import PromptRenderer
from paperflow.models import CandidatePaper, FilterStatus, LLMCallResult
from paperflow.retry_queue import WorkItem, WorkReason
from paperflow.screening_ledger import ScreeningLedger
from paperflow.taxonomy import load_taxonomy

ROOT = Path(__file__).parents[2]


class FixtureFilterClient:
    def __init__(self, responses: list[list[dict[str, object]]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def structured_chat(
        self,
        *,
        task_name: str,
        messages: list[dict[str, str]],
        schema: type[FilterBatchEnvelope],
        model_chain: list[str],
        request_metadata: dict[str, str],
    ) -> LLMCallResult[FilterBatchEnvelope]:
        self.calls.append(
            {
                "task_name": task_name,
                "messages": messages,
                "model_chain": model_chain,
                "metadata": request_metadata,
            }
        )
        model_id = load_config_bundle(ROOT).models.models[model_chain[0]].model_id
        return LLMCallResult[FilterBatchEnvelope](
            parsed=schema.model_validate({"results": self.responses.pop(0)}),
            requested_model=model_id,
            actual_model=model_id,
            provider="DeterministicFixture",
            input_tokens=500,
            output_tokens=100,
            cost_usd=0.001,
            latency_ms=25,
            request_id=f"filter-fixture-{len(self.calls)}",
            attempt=1,
        )


def test_ten_paper_filter_pipeline_salvages_siblings_and_persists_all(
    tmp_path: Path,
) -> None:
    fixture = json.loads(
        (ROOT / "tests/fixtures/pipeline/filter_ten_papers.json").read_text()
    )
    items = [
        WorkItem(
            paper=CandidatePaper(
                arxiv_id=paper["arxiv_id"],
                source_arxiv_id=f"{paper['arxiv_id']}v1",
                title=paper["title"],
                abstract=paper["abstract"],
                authors=["Deterministic Fixture"],
                categories=["cs.AI"],
                arxiv_url=f"https://arxiv.org/abs/{paper['arxiv_id']}",
                pdf_url=f"https://arxiv.org/pdf/{paper['arxiv_id']}",
            ),
            reason=WorkReason.NEW_UNSEEN,
            next_attempt_number=1,
        )
        for paper in fixture["candidates"]
    ]
    client = FixtureFilterClient(
        [fixture["primary_results"], fixture["retry_results"]]
    )
    bundle = load_config_bundle(ROOT)
    ledger = ScreeningLedger(tmp_path / "screening_events")
    event_ids = iter(UUID(int=index) for index in range(1, 11))

    outcome = filter_workset(
        items,
        client=client,
        renderer=PromptRenderer(ROOT / "configs/prompts", bundle.prompts),
        taxonomy=load_taxonomy(ROOT / "configs/topics.yaml"),
        model_config=bundle.models,
        filtering_config=bundle.runtime.filtering,
        ledger=ledger,
        run_id="fixture-filter-run",
        observed_at=datetime(2026, 8, 20, 21, tzinfo=UTC),
        event_id_factory=lambda: next(event_ids),
    )

    counts = {
        status.value: sum(event.filter_status == status for event in outcome.events)
        for status in FilterStatus
    }
    assert counts == fixture["expected"]
    assert len(outcome.events) == 10
    assert list(ledger.iter_events()) == list(outcome.events)
    assert len({event.arxiv_id for event in outcome.events}) == 10
    assert len(client.calls) == 2
    retry_prompt = client.calls[1]["messages"][1]["content"]
    assert "2608.20010" in retry_prompt
    assert "2608.20001" not in retry_prompt
    assert outcome.events[0].filter_status == FilterStatus.KEPT
    assert outcome.events[-1].filter_status == FilterStatus.FAILED
    assert outcome.events[-1].requested_model == "z-ai/glm-4.7-flash"
