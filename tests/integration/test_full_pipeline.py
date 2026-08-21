from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

import pytest
from pydantic import BaseModel

from paperflow.arxiv_client import ArxivSourceError
from paperflow.config import load_config_bundle
from paperflow.llm.filtering import FilterBatchEnvelope
from paperflow.models import (
    AnnounceType,
    CandidatePaper,
    LLMCallResult,
    RawArxivEntry,
    RunStats,
    SummaryContent,
)
from paperflow.paper_store import load_run_state, load_selected_store
from paperflow.pipeline import PipelineDependencies, run_pipeline
from paperflow.render.validation import validate_repository
from paperflow.screening_ledger import ScreeningLedger
from paperflow.taxonomy import load_taxonomy

ROOT = Path(__file__).parents[2]


def project_copy(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    for relative in ("configs", "data", "site", "topics"):
        shutil.copytree(ROOT / relative, project / relative)
    shutil.copy2(ROOT / "README.md", project / "README.md")
    workflow = project / ".github/workflows/paperflow-daily.yml"
    workflow.parent.mkdir(parents=True)
    shutil.copy2(ROOT / ".github/workflows/paperflow-daily.yml", workflow)
    return project


class SequencedSource:
    def __init__(self, runs: list[list[RawArxivEntry]]) -> None:
        self.runs = runs

    def fetch_new(self, categories, *, timeout_seconds):
        del categories, timeout_seconds
        return self.runs.pop(0)


class FailedSource:
    def fetch_new(self, categories, *, timeout_seconds):
        del categories, timeout_seconds
        raise ArxivSourceError("deterministic source failure")


class NoRefetch:
    def refetch(self, arxiv_id: str) -> CandidatePaper | None:
        del arxiv_id
        return None


class FixturePipelineLLM:
    def __init__(self, root: Path, filter_responses: list[list[dict]]) -> None:
        self.bundle = load_config_bundle(root)
        self.filter_responses = filter_responses
        self._lock = Lock()
        self.summary_calls = 0

    def structured_chat(
        self,
        *,
        task_name: str,
        messages: list[dict[str, str]],
        schema: type[BaseModel],
        model_chain: list[str],
        request_metadata: dict[str, str],
    ) -> LLMCallResult:
        del messages, schema
        model_id = self.bundle.models.models[model_chain[0]].model_id
        if task_name == "filter":
            with self._lock:
                response = self.filter_responses.pop(0)
            parsed = FilterBatchEnvelope.model_validate({"results": response})
            input_tokens, output_tokens, cost = 500, 100, 0.001
        else:
            with self._lock:
                self.summary_calls += 1
            paper_id = request_metadata["arxiv_id"]
            parsed = SummaryContent(
                tldr=f"Summary for {paper_id}.",
                bullets=["Problem.", "Method.", "Contribution."],
            )
            input_tokens, output_tokens, cost = 40, 20, 0.00004
        return LLMCallResult(
            parsed=parsed,
            requested_model=model_id,
            actual_model=model_id,
            provider="DeterministicFixture",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=0,
            cost_usd=cost,
            latency_ms=1,
            request_id=f"{task_name}-{request_metadata}",
            attempt=1,
        )


def raw_fixture() -> tuple[list[RawArxivEntry], dict]:
    fixture = json.loads(
        (ROOT / "tests/fixtures/pipeline/filter_ten_papers.json").read_text()
    )
    entries = [
        RawArxivEntry(
            source_arxiv_id=f"{paper['arxiv_id']}v1",
            title=paper["title"],
            abstract=paper["abstract"],
            authors=["Pipeline Fixture"],
            categories=["cs.AI"],
            announce_type=AnnounceType.NEW,
        )
        for paper in fixture["candidates"]
    ]
    for paper in fixture["candidates"][:2]:
        entries.append(
            RawArxivEntry(
                source_arxiv_id=f"{paper['arxiv_id']}v1",
                title=paper["title"],
                abstract=paper["abstract"],
                authors=["Pipeline Fixture"],
                categories=["cs.CV"],
                announce_type=AnnounceType.CROSS,
            )
        )
    return entries, fixture


def test_two_full_runs_retry_failure_and_publish_valid_outputs(tmp_path: Path) -> None:
    project = project_copy(tmp_path)
    entries, fixture = raw_fixture()
    recovered = {
        "arxiv_id": "2608.20010",
        "keep": True,
        "relevance": 8,
        "novelty": 7,
        "assignments": [
            {
                "topic_id": "spatial-intelligence",
                "subtopic_ids": ["spatial-memory"],
            }
        ],
        "reason": "Recovered deterministic retry.",
    }
    llm = FixturePipelineLLM(
        project,
        [
            fixture["primary_results"],
            fixture["retry_results"],
            [recovered],
            [
                {
                    "arxiv_id": "2608.20001",
                    "keep": True,
                    "relevance": 9,
                    "novelty": 9,
                    "assignments": [
                        {
                            "topic_id": "embodied-ai",
                            "subtopic_ids": ["robot-learning"],
                        }
                    ],
                    "reason": "Explicit deterministic reclassification.",
                }
            ],
        ],
    )
    instants = iter(
        [
            datetime(2026, 8, 20, 23, tzinfo=UTC),
            datetime(2026, 8, 21, 23, tzinfo=UTC),
            datetime(2026, 8, 22, 23, tzinfo=UTC),
        ]
    )
    dependencies = PipelineDependencies(
        source_client=SequencedSource([entries, entries]),
        refetcher=NoRefetch(),
        llm_client_factory=lambda: llm,
        now=lambda: next(instants),
        run_id_factory=lambda now: f"fixture-{now.date().isoformat()}",
    )

    first = run_pipeline(project, dependencies, manual=True)
    second = run_pipeline(project, dependencies, manual=True)
    third = run_pipeline(
        project,
        dependencies,
        manual=True,
        manual_override_ids=["2608.20001"],
        maintenance_only=True,
    )

    assert first.stats is not None
    assert (first.stats.fetched, first.stats.deduplicated) == (12, 10)
    assert (first.stats.kept, first.stats.dropped, first.stats.filter_failed) == (
        3,
        6,
        1,
    )
    assert second.stats is not None
    assert second.stats.kept == 1
    assert third.stats is not None
    assert (third.stats.fetched, third.stats.deduplicated, third.stats.kept) == (
        0,
        0,
        1,
    )
    taxonomy = load_taxonomy(project / "configs/topics.yaml")
    selected = load_selected_store(project / "data/papers.json", taxonomy)
    assert len(selected.papers) == 4
    assert load_run_state(project / "data/state.json").last_successful_run_id == (
        "fixture-2026-08-22"
    )
    assert RunStats.model_validate_json(
        (project / "data/run_stats/2026-08-20.json").read_text()
    ).source_ok
    events = [
        event
        for event in ScreeningLedger(project / "data/screening_events").iter_events()
        if event.arxiv_id == "2608.20001"
    ]
    assert len(events) == 2
    assert events[0].topic_assignments != events[1].topic_assignments
    assert selected.papers["2608.20001"].first_seen_date.isoformat() == "2026-08-20"
    assert validate_repository(project).run_stats_files == 3


def test_source_failure_preserves_canonical_and_public_outputs(tmp_path: Path) -> None:
    project = project_copy(tmp_path)
    tracked = [
        project / "data/papers.json",
        project / "data/state.json",
        project / "data/feed_index.json",
        project / "site/index.html",
        project / "README.md",
    ]
    before = {path: path.read_bytes() for path in tracked}
    dependencies = PipelineDependencies(
        source_client=FailedSource(),
        refetcher=NoRefetch(),
        llm_client_factory=lambda: pytest.fail("LLM must not run on source failure"),
        now=lambda: datetime(2026, 8, 20, 23, tzinfo=UTC),
        run_id_factory=lambda now: "fixture-source-failure",
    )

    with pytest.raises(ArxivSourceError):
        run_pipeline(project, dependencies, manual=True)

    assert {path: path.read_bytes() for path in tracked} == before
    failed = RunStats.model_validate_json(
        (project / "data/run_stats/2026-08-20.json").read_text()
    )
    assert failed.source_ok is False
    assert failed.fetched == 0
