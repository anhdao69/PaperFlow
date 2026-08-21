from __future__ import annotations

import json
from datetime import date
from io import StringIO

import pytest
from pydantic import ValidationError

from paperflow.models import LLMCallResult, RunStats, SummaryContent
from paperflow.observability import (
    aggregate_llm_usage,
    render_run_report,
    save_run_stats,
    structured_event,
)


def call(
    *,
    requested: str,
    actual: str | None,
    provider: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_tokens: int | None,
    cost: float | None,
) -> LLMCallResult[SummaryContent]:
    return LLMCallResult[SummaryContent](
        parsed=SummaryContent(tldr="Summary.", bullets=["A.", "B.", "C."]),
        requested_model=requested,
        actual_model=actual,
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_tokens,
        cost_usd=cost,
        latency_ms=1,
        attempt=1,
    )


def stats(**updates: object) -> RunStats:
    breakdown = aggregate_llm_usage(
        [
            call(
                requested="requested/model",
                actual="actual/model",
                provider="fixture",
                input_tokens=10,
                output_tokens=4,
                cached_tokens=2,
                cost=0.001,
            )
        ]
    )
    values: dict[str, object] = {
        "run_id": "fixture-run",
        "date": date(2026, 8, 20),
        "source_ok": True,
        "fetched": 12,
        "deduplicated": 10,
        "terminal_skipped": 0,
        "failed_backlog_added": 0,
        "screened": 10,
        "kept": 3,
        "dropped": 6,
        "filter_failed": 1,
        "summary_generated": 2,
        "summary_failed": 1,
        "figure_mode": "placeholder",
        "llm_input_tokens": 10,
        "llm_output_tokens": 4,
        "llm_cached_input_tokens": 2,
        "llm_cost_usd": 0.001,
        "model_breakdown": breakdown,
    }
    values.update(updates)
    return RunStats.model_validate(values)


def test_usage_uses_actual_model_and_aggregates_missing_values() -> None:
    result = aggregate_llm_usage(
        [
            call(
                requested="primary/model",
                actual="routed/model",
                provider="provider-a",
                input_tokens=10,
                output_tokens=5,
                cached_tokens=3,
                cost=0.01,
            ),
            call(
                requested="routed/model",
                actual=None,
                provider=None,
                input_tokens=None,
                output_tokens=None,
                cached_tokens=None,
                cost=None,
            ),
        ]
    )

    usage = result["routed/model"]
    assert usage.calls == 2
    assert usage.input_tokens == 10
    assert usage.output_tokens == 5
    assert usage.cached_input_tokens == 3
    assert usage.cost_usd == pytest.approx(0.01)
    assert usage.providers == {"provider-a": 1}


def test_run_stats_arithmetic_and_round_trip(tmp_path) -> None:
    value = stats()
    path = tmp_path / "2026-08-20.json"
    save_run_stats(path, value)
    assert RunStats.model_validate_json(path.read_text()) == value

    with pytest.raises(ValidationError, match="screened must equal"):
        stats(screened=9)
    with pytest.raises(ValidationError, match="cost total"):
        stats(llm_cost_usd=2.0)


def test_report_has_uncapped_keep_source_and_actual_model() -> None:
    report = render_run_report(stats())
    assert "Source: OK" in report
    assert "KEEP: 3" in report
    assert "KEEP cap: NONE" in report
    assert "Model actual/model" in report
    assert "$0.001000" in report


def test_structured_event_recursively_redacts_sensitive_fields() -> None:
    output = StringIO()
    structured_event(
        "run_failed",
        stream=output,
        authorization="Bearer visible-no-more",
        nested={"OPENROUTER_API_KEY": "hidden", "abstract": "too noisy"},
        safe="retained",
    )
    payload = json.loads(output.getvalue())
    assert payload == {
        "event": "run_failed",
        "authorization": "[REDACTED]",
        "nested": {
            "OPENROUTER_API_KEY": "[REDACTED]",
            "abstract": "[REDACTED]",
        },
        "safe": "retained",
    }
    assert "visible-no-more" not in output.getvalue()
    assert "too noisy" not in output.getvalue()
