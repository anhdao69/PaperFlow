from __future__ import annotations

import json
import shutil
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from threading import Lock
from zoneinfo import ZoneInfo

import pytest
import yaml
from pydantic import BaseModel

from paperflow.arxiv_client import ArxivSourceError
from paperflow.cli.rebuild_outputs import main as rebuild_outputs
from paperflow.cli.sync_schedule import sync_schedule
from paperflow.config import load_config_bundle
from paperflow.llm.filtering import FilterBatchEnvelope
from paperflow.llm.openrouter import OpenRouterSemanticError
from paperflow.models import (
    AnnounceType,
    CandidatePaper,
    LLMCallResult,
    RawArxivEntry,
    RunState,
    RunStats,
    SelectedPaperCollection,
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
    shutil.copytree(ROOT / "configs", project / "configs")
    data = project / "data"
    data.mkdir()
    (data / "papers.json").write_text(
        SelectedPaperCollection().model_dump_json(indent=2) + "\n"
    )
    (data / "state.json").write_text(RunState().model_dump_json(indent=2) + "\n")
    assert rebuild_outputs(["--root", str(project)]) == 0
    workflow = project / ".github/workflows/paperflow-daily.yml"
    workflow.parent.mkdir(parents=True)
    shutil.copy2(ROOT / ".github/workflows/paperflow-daily.yml", workflow)
    return project


class SequencedSource:
    def __init__(
        self, runs: list[list[RawArxivEntry] | ArxivSourceError]
    ) -> None:
        self.runs = runs

    def fetch_new(self, categories, *, timeout_seconds):
        del categories, timeout_seconds
        result = self.runs.pop(0)
        if isinstance(result, ArxivSourceError):
            raise result
        return result


class FailedSource:
    def fetch_new(self, categories, *, timeout_seconds):
        del categories, timeout_seconds
        raise ArxivSourceError("deterministic source failure")


class FixtureRefetch:
    def __init__(self, papers: dict[str, CandidatePaper] | None = None) -> None:
        self.papers = papers or {}

    def refetch(self, arxiv_id: str) -> CandidatePaper | None:
        return self.papers.get(arxiv_id)


class FixturePipelineLLM:
    def __init__(self, root: Path, filter_responses: list[list[dict]]) -> None:
        self.bundle = load_config_bundle(root)
        self.filter_responses = filter_responses
        self._lock = Lock()
        self.summary_calls = 0
        self.summary_counts: defaultdict[str, int] = defaultdict(int)

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
                self.summary_counts[request_metadata["arxiv_id"]] += 1
            paper_id = request_metadata["arxiv_id"]
            if paper_id == "2608.20003" and self.summary_counts[paper_id] <= 2:
                raise OpenRouterSemanticError("deterministic summary failure")
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


def test_five_date_core_soak_with_retry_fallback_and_failure_drill(
    tmp_path: Path,
) -> None:
    project = project_copy(tmp_path)
    runtime_path = project / "configs/runtime.yaml"
    runtime = yaml.safe_load(runtime_path.read_text())
    runtime["schedule"]["enabled"] = True
    runtime["figures"]["enabled"] = False
    runtime_path.write_text(yaml.safe_dump(runtime, sort_keys=False))
    assert sync_schedule(project, check=False) is False
    entries, fixture = raw_fixture()
    recovered = {
        "arxiv_id": "2608.20010",
        "keep": True,
        "relevance": 8,
        "novelty": 7,
        "assignments": [
            {
                "topic_id": "adaptation-and-memory",
                "subtopic_ids": ["embodied-memory"],
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
                            "subtopic_ids": ["robot-learning-and-manipulation"],
                        }
                    ],
                    "reason": "Explicit deterministic reclassification.",
                }
            ],
        ],
    )
    instants = iter(
        [
            datetime(2026, 8, 21, 1, tzinfo=UTC),
            datetime(2026, 8, 22, 1, tzinfo=UTC),
            datetime(2026, 8, 23, 1, tzinfo=UTC),
            datetime(2026, 8, 23, 2, tzinfo=UTC),
            datetime(2026, 8, 24, 1, tzinfo=UTC),
            datetime(2026, 8, 25, 1, tzinfo=UTC),
        ]
    )
    failed_id = "2608.20010"
    without_failed = [
        entry
        for entry in entries
        if not entry.source_arxiv_id.startswith(failed_id)
    ]
    refetched = CandidatePaper(
        arxiv_id=failed_id,
        source_arxiv_id=f"{failed_id}v1",
        title="Ambiguous Spatial Classifier",
        abstract=(
            "A spatial classifier is returned with an intentionally invalid "
            "taxonomy assignment."
        ),
        authors=["Pipeline Fixture"],
        categories=["cs.AI"],
        arxiv_url=f"https://arxiv.org/abs/{failed_id}",
        pdf_url=f"https://arxiv.org/pdf/{failed_id}",
    )
    dependencies = PipelineDependencies(
        source_client=SequencedSource(
            [
                entries,
                without_failed,
                ArxivSourceError("deterministic soak source failure"),
                without_failed,
                without_failed,
                without_failed,
            ]
        ),
        refetcher=FixtureRefetch({failed_id: refetched}),
        llm_client_factory=lambda: llm,
        now=lambda: next(instants),
        run_id_factory=lambda now: f"fixture-{now:%Y-%m-%dT%H}",
    )

    first = run_pipeline(project, dependencies, manual=False)
    second = run_pipeline(project, dependencies, manual=False)
    tracked = [
        project / "data/papers.json",
        project / "data/state.json",
        project / "data/feed_index.json",
        project / "site/index.html",
        project / "README.md",
    ]
    before_failure = {path: path.read_bytes() for path in tracked}
    with pytest.raises(ArxivSourceError):
        run_pipeline(project, dependencies, manual=False)
    assert {path: path.read_bytes() for path in tracked} == before_failure
    third = run_pipeline(project, dependencies, manual=False)
    fourth = run_pipeline(project, dependencies, manual=False)
    fifth = run_pipeline(project, dependencies, manual=False)

    assert first.stats is not None
    assert (first.stats.fetched, first.stats.deduplicated) == (12, 10)
    assert (first.stats.kept, first.stats.dropped, first.stats.filter_failed) == (
        3,
        6,
        1,
    )
    assert (first.stats.summary_generated, first.stats.summary_failed) == (2, 1)
    assert second.stats is not None
    assert second.stats.failed_backlog_added == 1
    assert second.stats.kept == 1
    assert (second.stats.summary_generated, second.stats.summary_failed) == (2, 0)
    assert third.stats is not None
    assert fourth.stats is not None
    assert fifth.stats is not None
    assert all(
        result.stats.figure_mode == "placeholder"
        for result in (first, second, third, fourth, fifth)
        if result.stats is not None
    )
    taxonomy = load_taxonomy(project / "configs/topics.yaml")
    selected = load_selected_store(project / "data/papers.json", taxonomy)
    assert len(selected.papers) == 4
    assert load_run_state(project / "data/state.json").last_successful_run_id == (
        "fixture-2026-08-25T01"
    )
    assert RunStats.model_validate_json(
        (project / "data/run_stats/2026-08-20.json").read_text()
    ).source_ok
    events = tuple(
        ScreeningLedger(project / "data/screening_events").iter_events()
    )
    assert len({event.arxiv_id for event in events}) == 10
    failed_history = [event for event in events if event.arxiv_id == failed_id]
    assert [event.filter_status.value for event in failed_history] == [
        "failed",
        "kept",
    ]
    report = validate_repository(project)
    assert report.run_stats_files == 5
    assert report.selected_papers == 4
    assert len(selected.papers) == len(set(selected.papers))


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
        refetcher=FixtureRefetch(),
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


def test_delayed_trigger_publishes_the_missed_date_not_delivery_date(
    tmp_path: Path,
) -> None:
    project = project_copy(tmp_path)
    runtime_path = project / "configs/runtime.yaml"
    runtime = yaml.safe_load(runtime_path.read_text())
    runtime["figures"]["enabled"] = False
    runtime_path.write_text(yaml.safe_dump(runtime, sort_keys=False))
    previous_date = date(2026, 8, 25)
    previous_state = RunState(
        last_successful_run_id="previous",
        last_successful_at=datetime(
            2026,
            8,
            25,
            21,
            tzinfo=ZoneInfo("America/New_York"),
        ),
        last_successful_local_date=previous_date,
        runtime_config_hash="a" * 64,
        model_config_hash="b" * 64,
        taxonomy_hash="c" * 64,
    )
    (project / "data/state.json").write_text(
        previous_state.model_dump_json(indent=2) + "\n"
    )
    dependencies = PipelineDependencies(
        source_client=SequencedSource([[]]),
        refetcher=FixtureRefetch(),
        llm_client_factory=lambda: pytest.fail("empty source must not call the LLM"),
        now=lambda: datetime(2026, 8, 27, 11, 6, tzinfo=UTC),
        run_id_factory=lambda now: "delayed-run",
    )

    result = run_pipeline(project, dependencies, manual=False)

    assert result.ran
    assert load_run_state(project / "data/state.json").last_successful_local_date == (
        date(2026, 8, 26)
    )
    assert (project / "data/daily_feeds/2026-08-26.json").exists()
    assert not (project / "data/daily_feeds/2026-08-27.json").exists()
    assert (project / "data/run_stats/2026-08-26.json").exists()
