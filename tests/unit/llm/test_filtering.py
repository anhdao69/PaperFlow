from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from uuid import UUID

import pytest
from pydantic import ValidationError

from paperflow.config import load_config_bundle
from paperflow.llm.filtering import FilterBatchEnvelope, filter_workset
from paperflow.llm.openrouter import OpenRouterSemanticError
from paperflow.llm.structured import PromptRenderer
from paperflow.models import (
    CandidatePaper,
    FilterResult,
    FilterStatus,
    LLMCallResult,
    TopicAssignment,
)
from paperflow.retry_queue import WorkItem, WorkReason
from paperflow.screening_ledger import ScreeningLedger
from paperflow.taxonomy import (
    DuplicateTopicAssignmentError,
    InvalidParentChildError,
    UnknownTopicError,
    load_taxonomy,
    validate_assignments,
)

ROOT = Path(__file__).parents[3]
NOW = datetime(2026, 8, 20, 21, tzinfo=UTC)


class FakeFilterClient:
    def __init__(
        self,
        responses: list[
            dict[str, object]
            | Exception
            | Callable[[list[dict[str, str]], list[str]], dict[str, object]]
        ],
    ) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []
        self._lock = Lock()

    def structured_chat(
        self,
        *,
        task_name: str,
        messages: list[dict[str, str]],
        schema: type[FilterBatchEnvelope],
        model_chain: list[str],
        request_metadata: dict[str, str],
    ) -> LLMCallResult[FilterBatchEnvelope]:
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
        if callable(response):
            response = response(messages, model_chain)
        parsed = schema.model_validate(response)
        model_id = load_config_bundle(ROOT).models.models[model_chain[0]].model_id
        return LLMCallResult[FilterBatchEnvelope](
            parsed=parsed,
            requested_model=model_id,
            actual_model=model_id,
            provider="FixtureProvider",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.00001,
            latency_ms=4,
            request_id=f"fixture-{len(self.calls)}",
            attempt=1,
        )


def _paper(number: int) -> CandidatePaper:
    arxiv_id = f"2608.{number:05d}"
    return CandidatePaper(
        arxiv_id=arxiv_id,
        source_arxiv_id=f"{arxiv_id}v1",
        title=f"Fixture Paper {number}",
        abstract=f"A deterministic abstract about spatial robot learning {number}.",
        authors=["Fixture Author"],
        categories=["cs.RO"],
        arxiv_url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
    )


def _item(number: int, *, attempt: int = 1) -> WorkItem:
    return WorkItem(_paper(number), WorkReason.NEW_UNSEEN, attempt)


def _result(
    paper_id: str,
    *,
    keep: bool = True,
    relevance: int = 9,
    novelty: int = 8,
    topic_id: str = "embodied-ai",
    subtopic_ids: list[str] | None = None,
) -> dict[str, object]:
    assignments: list[dict[str, object]] = []
    if keep:
        assignments = [
            {
                "topic_id": topic_id,
                "subtopic_ids": subtopic_ids
                if subtopic_ids is not None
                else ["robot-learning"],
            }
        ]
    return {
        "arxiv_id": paper_id,
        "keep": keep,
        "relevance": relevance,
        "novelty": novelty,
        "assignments": assignments,
        "reason": "Deterministic fixture decision.",
    }


def _run(
    tmp_path: Path,
    items: list[WorkItem],
    client: FakeFilterClient,
    *,
    batch_size: int = 10,
    concurrency: int = 1,
    semantic_retries: int = 1,
    persist: bool = True,
):
    bundle = load_config_bundle(ROOT)
    config = bundle.runtime.filtering.model_copy(
        update={
            "batch_size": batch_size,
            "concurrency": concurrency,
            "semantic_retry_count": semantic_retries,
        }
    )
    renderer = PromptRenderer(ROOT / "configs/prompts", bundle.prompts)
    ids = iter(UUID(int=index) for index in range(1, len(items) + 1))
    return filter_workset(
        items,
        client=client,
        renderer=renderer,
        taxonomy=load_taxonomy(ROOT / "configs/topics.yaml"),
        model_config=bundle.models,
        filtering_config=config,
        ledger=ScreeningLedger(tmp_path / "ledger") if persist else None,
        run_id="fixture-run",
        observed_at=NOW,
        event_id_factory=lambda: next(ids),
    )


@pytest.mark.parametrize("field,value", [("relevance", 0), ("novelty", 11)])
def test_filter_result_rejects_score_outside_one_to_ten(
    field: str, value: int
) -> None:
    data = _result("2608.10001")
    data[field] = value

    with pytest.raises(ValidationError):
        FilterResult.model_validate(data)


def test_keep_requires_assignment_and_drop_requires_empty_assignment() -> None:
    keep = _result("2608.10001")
    keep["assignments"] = []
    drop = _result("2608.10002", keep=False)
    drop["assignments"] = [
        {"topic_id": "embodied-ai", "subtopic_ids": []}
    ]

    with pytest.raises(ValidationError, match="KEEP"):
        FilterResult.model_validate(keep)
    with pytest.raises(ValidationError, match="DROP"):
        FilterResult.model_validate(drop)


def test_duplicate_subtopics_are_rejected_deterministically() -> None:
    data = _result(
        "2608.10001",
        subtopic_ids=["robot-learning", "robot-learning"],
    )

    with pytest.raises(ValidationError, match="unique"):
        FilterResult.model_validate(data)


def test_taxonomy_rejects_unknown_wrong_parent_and_duplicate_topic() -> None:
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")

    with pytest.raises(UnknownTopicError):
        validate_assignments(taxonomy, [TopicAssignment(topic_id="unknown")])
    with pytest.raises(InvalidParentChildError):
        validate_assignments(
            taxonomy,
            [
                TopicAssignment(
                    topic_id="embodied-ai",
                    subtopic_ids=["spatial-memory"],
                )
            ],
        )
    with pytest.raises(DuplicateTopicAssignmentError):
        validate_assignments(
            taxonomy,
            [
                TopicAssignment(topic_id="embodied-ai"),
                TopicAssignment(topic_id="embodied-ai"),
            ],
        )


@pytest.mark.parametrize(
    "unsafe_results",
    [
        [_result("2608.10001")],
        [
            _result("2608.10001"),
            _result("2608.10002"),
            _result("2608.19999"),
        ],
        [_result("2608.10001"), _result("2608.10001")],
    ],
    ids=["missing", "extra", "duplicate"],
)
def test_unsafe_id_mapping_retries_full_batch_once(
    tmp_path: Path, unsafe_results: list[dict[str, object]]
) -> None:
    items = [_item(10001), _item(10002)]
    valid_retry = [_result(item.paper.arxiv_id, keep=False) for item in items]
    client = FakeFilterClient(
        [{"results": unsafe_results}, {"results": valid_retry}]
    )

    outcome = _run(tmp_path, items, client)

    assert [event.filter_status for event in outcome.events] == [
        FilterStatus.DROPPED,
        FilterStatus.DROPPED,
    ]
    assert len(client.calls) == 2
    assert all(
        item.paper.arxiv_id in client.calls[1]["messages"][1]["content"]
        for item in items
    )


def test_valid_subset_is_kept_and_only_invalid_sibling_retries(
    tmp_path: Path,
) -> None:
    first_id = "2608.10001"
    second_id = "2608.10002"
    client = FakeFilterClient(
        [
            {
                "results": [
                    _result(first_id),
                    _result(
                        second_id,
                        topic_id="embodied-ai",
                        subtopic_ids=["spatial-memory"],
                    ),
                ]
            },
            {"results": [_result(second_id, keep=False)]},
        ]
    )

    outcome = _run(tmp_path, [_item(10001), _item(10002)], client)

    assert [event.filter_status for event in outcome.events] == [
        FilterStatus.KEPT,
        FilterStatus.DROPPED,
    ]
    retry_prompt = client.calls[1]["messages"][1]["content"]
    assert first_id not in retry_prompt
    assert second_id in retry_prompt
    assert client.calls[0]["model_chain"] == ["deepseek_v4_flash"]
    assert client.calls[1]["model_chain"] == ["glm_4_7_flashx"]


def test_unmappable_envelope_retries_full_batch_once(tmp_path: Path) -> None:
    items = [_item(10001), _item(10002)]
    client = FakeFilterClient(
        [
            OpenRouterSemanticError("malformed fixture"),
            {
                "results": [
                    _result(item.paper.arxiv_id, keep=False) for item in items
                ]
            },
        ]
    )

    outcome = _run(tmp_path, items, client)

    assert all(
        event.filter_status == FilterStatus.DROPPED for event in outcome.events
    )
    assert len(client.calls) == 2


def test_second_semantic_failure_becomes_failed_never_drop(
    tmp_path: Path,
) -> None:
    item = _item(10001)
    invalid = _result(
        item.paper.arxiv_id,
        topic_id="embodied-ai",
        subtopic_ids=["spatial-memory"],
    )
    client = FakeFilterClient(
        [{"results": [invalid]}, {"results": [invalid]}]
    )

    outcome = _run(tmp_path, [item], client)
    event = outcome.events[0]

    assert event.filter_status == FilterStatus.FAILED
    assert event.error_type == "semantic_validation"
    assert event.next_retry_at == NOW + timedelta(hours=12)
    assert event.requested_model == "z-ai/glm-4.7-flash"
    assert len(client.calls) == 2
    assert list(ScreeningLedger(tmp_path / "ledger").iter_events()) == [event]


def test_retry_exhaustion_is_recorded_without_next_retry(tmp_path: Path) -> None:
    item = _item(10001, attempt=5)
    client = FakeFilterClient(
        [
            OpenRouterSemanticError("bad first"),
            OpenRouterSemanticError("bad second"),
        ]
    )

    event = _run(tmp_path, [item], client).events[0]

    assert event.filter_status == FilterStatus.FAILED
    assert event.retry_exhausted is True
    assert event.next_retry_at is None


def test_semantic_retry_can_be_disabled(tmp_path: Path) -> None:
    item = _item(10001)
    client = FakeFilterClient([OpenRouterSemanticError("bad")])

    event = _run(
        tmp_path, [item], client, semantic_retries=0
    ).events[0]

    assert event.filter_status == FilterStatus.FAILED
    assert len(client.calls) == 1


def test_batch_concurrency_preserves_workset_order(tmp_path: Path) -> None:
    items = [_item(number) for number in range(10001, 10006)]

    def respond(
        messages: list[dict[str, str]], model_chain: list[str]
    ) -> dict[str, object]:
        del model_chain
        user = messages[1]["content"]
        paper_id = next(
            item.paper.arxiv_id for item in items if item.paper.arxiv_id in user
        )
        return {"results": [_result(paper_id, keep=False)]}

    client = FakeFilterClient([respond] * len(items))

    outcome = _run(
        tmp_path,
        items,
        client,
        batch_size=1,
        concurrency=3,
    )

    assert [event.arxiv_id for event in outcome.events] == [
        item.paper.arxiv_id for item in items
    ]
    assert len(outcome.events) == len(items)


def test_dry_run_report_excludes_prompts_authors_and_secrets(tmp_path: Path) -> None:
    item = _item(10001)
    outcome = _run(
        tmp_path,
        [item],
        FakeFilterClient([{"results": [_result(item.paper.arxiv_id)]}]),
        persist=False,
    )

    report = outcome.render_dry_run_report()

    assert "KEPT" in report
    assert "taxonomy=" in report
    assert "prompt=" in report
    assert "FixtureProvider" in report
    assert item.paper.abstract not in report
    assert "Fixture Author" not in report
    assert "OPENROUTER" not in report


def test_empty_workset_makes_no_client_or_ledger_call(tmp_path: Path) -> None:
    client = FakeFilterClient([])

    outcome = _run(tmp_path, [], client)

    assert outcome.events == ()
    assert client.calls == []
    assert not (tmp_path / "ledger").exists()


def test_duplicate_workset_id_is_rejected_before_network(tmp_path: Path) -> None:
    item = _item(10001)
    client = FakeFilterClient([])

    with pytest.raises(ValueError, match="duplicate"):
        _run(tmp_path, [item, item], client)

    assert client.calls == []
