from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from paperflow.llm.structured import (
    LLMCache,
    LLMCacheKey,
    PromptPaper,
    RenderedPrompt,
    summary_cache_key,
)
from paperflow.models import LLMCallResult, SummaryContent

HASH_A = "a" * 64
HASH_B = "b" * 64


def _paper(abstract: str = "A stable fixture abstract.") -> PromptPaper:
    return PromptPaper(
        arxiv_id="2608.30001",
        title="Fixture Summary Paper",
        abstract=abstract,
        categories=["cs.AI"],
    )


def _prompt(prompt_hash: str = HASH_A) -> RenderedPrompt:
    return RenderedPrompt(
        version="summary-v2",
        system="Summary system prompt.\n",
        user="TITLE: Fixture Summary Paper\nABSTRACT: A stable fixture abstract.\n",
        system_hash=prompt_hash,
    )


def _result() -> LLMCallResult[SummaryContent]:
    return LLMCallResult[SummaryContent](
        parsed=SummaryContent(
            tldr="A concise deterministic summary.",
            bullets=["Problem.", "Method.", "Contribution."],
        ),
        requested_model="openai/gpt-5.6-luna",
        actual_model="openai/gpt-5.6-luna",
        provider="FixtureProvider",
        input_tokens=20,
        output_tokens=10,
        cached_input_tokens=5,
        cost_usd=0.00002,
        latency_ms=12,
        request_id="fixture-summary",
        attempt=1,
    )


def test_cache_round_trip_preserves_typed_result_and_provenance(
    tmp_path: Path,
) -> None:
    cache = LLMCache(tmp_path)
    key = summary_cache_key(_paper(), _prompt(), "openai/gpt-5.6-luna")

    path = cache.store(key, _result())

    assert path.is_file()
    assert cache.load(key, SummaryContent) == _result()


def test_summary_cache_key_changes_for_abstract_prompt_or_model() -> None:
    base = summary_cache_key(_paper(), _prompt(), "openai/gpt-5.6-luna")
    keys = {
        summary_cache_key(_paper("Changed abstract."), _prompt(), base.model_id),
        summary_cache_key(_paper(), _prompt(HASH_B), base.model_id),
        summary_cache_key(_paper(), _prompt(), "mistralai/mistral-small-2603"),
    }

    assert all(key != base for key in keys)
    assert len({base.fingerprint(), *(key.fingerprint() for key in keys)}) == 4


def test_changed_key_is_a_miss_even_when_old_record_exists(tmp_path: Path) -> None:
    cache = LLMCache(tmp_path)
    old_key = summary_cache_key(_paper(), _prompt(), "openai/gpt-5.6-luna")
    changed = summary_cache_key(_paper(), _prompt(HASH_B), old_key.model_id)
    cache.store(old_key, _result())

    assert cache.load(changed, SummaryContent) is None


def test_tampered_stale_record_at_expected_path_is_rejected(tmp_path: Path) -> None:
    cache = LLMCache(tmp_path)
    key = summary_cache_key(_paper(), _prompt(), "openai/gpt-5.6-luna")
    path = cache.store(key, _result())
    payload = json.loads(path.read_text())
    payload["key"]["prompt_hash"] = HASH_B
    path.write_text(json.dumps(payload))

    assert cache.load(key, SummaryContent) is None


@pytest.mark.parametrize("content", ["not json", '{"schema_version":1}'])
def test_corrupt_or_incomplete_cache_is_a_miss(
    tmp_path: Path, content: str
) -> None:
    cache = LLMCache(tmp_path)
    key = summary_cache_key(_paper(), _prompt(), "openai/gpt-5.6-luna")
    path = cache._path(key)
    path.parent.mkdir(parents=True)
    path.write_text(content)

    assert cache.load(key, SummaryContent) is None


def test_missing_cache_is_a_miss(tmp_path: Path) -> None:
    key = summary_cache_key(_paper(), _prompt(), "openai/gpt-5.6-luna")

    assert LLMCache(tmp_path).load(key, SummaryContent) is None


def test_task_specific_cache_components_are_enforced() -> None:
    common = {
        "arxiv_id": "2608.30001",
        "abstract_hash": HASH_A,
        "prompt_hash": HASH_A,
        "model_id": "fixture/model",
    }

    with pytest.raises(ValidationError, match="taxonomy_hash"):
        LLMCacheKey(task="filter", **common)
    with pytest.raises(ValidationError, match="must not include"):
        LLMCacheKey(task="summary", taxonomy_hash=HASH_A, **common)


def test_legacy_arxiv_id_cannot_create_nested_cache_path(tmp_path: Path) -> None:
    key = LLMCacheKey(
        task="summary",
        arxiv_id="hep-th/9901001",
        abstract_hash=HASH_A,
        prompt_hash=HASH_A,
        model_id="fixture/model",
    )

    path = LLMCache(tmp_path)._path(key)

    assert path.parent == tmp_path / "llm_summary"
    assert "/" not in path.name
