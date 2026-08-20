from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from paperflow.render.contracts import (
    DailyFeed,
    FeedIndex,
    PublicPaper,
    TopicFeed,
    TopicsIndex,
    resolve_publication_url,
    validate_relative_publication_path,
    validate_topic_feed_contract,
)
from paperflow.taxonomy import load_taxonomy

ROOT = Path(__file__).parents[3]
FIXTURES = ROOT / "tests/fixtures/contracts/v1"


def _read(relative: str) -> str:
    return (FIXTURES / relative).read_text(encoding="utf-8")


def test_all_v1_valid_contract_goldens_decode() -> None:
    assert FeedIndex.model_validate_json(_read("valid/feed_index.json"))
    populated = DailyFeed.model_validate_json(_read("valid/daily_feed.json"))
    zero = DailyFeed.model_validate_json(_read("valid/zero_day.json"))
    assert TopicsIndex.model_validate_json(_read("valid/topics.json"))
    assert TopicFeed.model_validate_json(_read("valid/topic_feed_all.json"))
    subtopic = TopicFeed.model_validate_json(
        _read("valid/topic_feed_subtopic.json")
    )
    generated = PublicPaper.model_validate_json(
        _read("valid/public_paper_generated.json")
    )
    fallback = PublicPaper.model_validate_json(
        _read("valid/public_paper_fallback.json")
    )

    assert populated.paper_count == 2
    assert zero.paper_count == 0
    assert subtopic.subtopic_id == "video-world-models"
    assert generated.display_summary == generated.tldr
    assert fallback.display_summary == fallback.abstract


@pytest.mark.parametrize(
    "fixture,model",
    [
        ("invalid/count_mismatch.json", DailyFeed),
        ("invalid/unsafe_path.json", TopicsIndex),
        ("invalid/schema_version.json", DailyFeed),
    ],
)
def test_invalid_v1_goldens_are_rejected(fixture: str, model: type) -> None:
    with pytest.raises(ValidationError):
        model.model_validate_json(_read(fixture))


def test_wrong_parent_topic_feed_requires_taxonomy_validation() -> None:
    contract = TopicFeed.model_validate_json(
        _read("invalid/wrong_parent_topic_feed.json")
    )

    with pytest.raises(ValueError, match="not a child"):
        validate_topic_feed_contract(
            contract, load_taxonomy(ROOT / "configs/topics.yaml")
        )


def test_public_paper_allowlist_excludes_private_provenance_and_retry_fields() -> None:
    paper = PublicPaper.model_validate_json(
        _read("valid/public_paper_generated.json")
    )

    assert set(paper.model_dump()) == {
        "arxiv_id",
        "title",
        "authors",
        "abstract",
        "arxiv_url",
        "pdf_url",
        "first_seen_at",
        "categories",
        "relevance",
        "novelty",
        "topic_assignments",
        "selection_reason",
        "tldr",
        "bullets",
        "summary_status",
        "hero_figure",
        "figure_status",
    }
    serialized = paper.model_dump_json()
    for private in (
        "filter_prompt_hash",
        "summary_prompt_hash",
        "requested_model",
        "provider",
        "retry",
        "api_key",
    ):
        assert private not in serialized


@pytest.mark.parametrize(
    "path",
    [
        "/data/feed.json",
        "../data/feed.json",
        "data\\feed.json",
        "data/feed.json?token=x",
        "data/feed.json#fragment",
        "https://example.test/feed.json",
        "data//feed.json",
        "data/feed name.json",
        "data/feed%ZZ.json",
    ],
)
def test_unsafe_relative_publication_paths_are_rejected(path: str) -> None:
    with pytest.raises(ValueError):
        validate_relative_publication_path(path)


def test_relative_url_resolves_against_publication_root_exactly_once() -> None:
    assert resolve_publication_url(
        "https://example.test/PaperFlow/",
        "data/daily_feeds/2026-08-20.json",
    ) == "https://example.test/PaperFlow/data/daily_feeds/2026-08-20.json"


@pytest.mark.parametrize(
    "base_url",
    [
        "http://example.test/PaperFlow/",
        "https://example.test/PaperFlow",
        "https://example.test/PaperFlow/?token=x",
    ],
)
def test_invalid_publication_base_url_is_rejected(base_url: str) -> None:
    with pytest.raises(ValueError):
        resolve_publication_url(base_url, "data/feed_index.json")


def test_feed_index_rejects_unknown_timezone() -> None:
    payload = FeedIndex.model_validate_json(
        _read("valid/feed_index.json")
    ).model_dump(mode="python")
    payload["timezone"] = "Mars/Olympus"

    with pytest.raises(ValidationError, match="IANA"):
        FeedIndex.model_validate(payload)


def test_failed_summary_cannot_publish_generated_content() -> None:
    payload = PublicPaper.model_validate_json(
        _read("valid/public_paper_fallback.json")
    ).model_dump(mode="python")
    payload["tldr"] = "Stale summary."

    with pytest.raises(ValidationError, match="fallback"):
        PublicPaper.model_validate(payload)
