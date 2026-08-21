"""Small structured-observability primitives shared by pipeline stages."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO
from uuid import uuid4

from paperflow.atomic import atomic_write_text
from paperflow.models import LLMCallResult, ModelUsageStats, RunStats

_RUN_ID_DATETIME_FORMAT = "%Y%m%dT%H%M%S%fZ"


def create_run_id(now: datetime | None = None) -> str:
    """Create a chronologically readable, collision-resistant run identifier."""
    instant = now or datetime.now(UTC)
    if instant.tzinfo is None:
        raise ValueError("run ID timestamps must be timezone-aware")
    utc_instant = instant.astimezone(UTC)
    return f"{utc_instant.strftime(_RUN_ID_DATETIME_FORMAT)}-{uuid4().hex}"


def parse_run_id(run_id: str) -> datetime:
    """Parse and validate a run ID, returning its UTC timestamp."""
    timestamp, separator, suffix = run_id.partition("-")
    if separator != "-" or len(suffix) != 32:
        raise ValueError("invalid PaperFlow run ID")
    try:
        int(suffix, 16)
        parsed = datetime.strptime(timestamp, _RUN_ID_DATETIME_FORMAT)
    except ValueError as error:
        raise ValueError("invalid PaperFlow run ID") from error
    return parsed.replace(tzinfo=UTC)


def structured_event(
    event: str,
    *,
    stream: TextIO | None = None,
    **fields: object,
) -> None:
    """Write one compact, recursively redacted JSON event."""
    if not event.strip():
        raise ValueError("structured event name cannot be empty")
    destination = stream or sys.stdout
    payload: Mapping[str, object] = {
        "event": event,
        **_redact_mapping(fields),
    }
    destination.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    destination.write("\n")


def aggregate_llm_usage(
    calls: Iterable[LLMCallResult],
) -> dict[str, ModelUsageStats]:
    """Aggregate actual model/provider usage without prompt or response content."""
    counters: dict[str, dict[str, object]] = {}
    for call in calls:
        model = call.actual_model or call.requested_model
        current = counters.setdefault(
            model,
            {
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_input_tokens": 0,
                "cost_usd": 0.0,
                "providers": defaultdict(int),
            },
        )
        current["calls"] = int(current["calls"]) + 1
        current["input_tokens"] = int(current["input_tokens"]) + (
            call.input_tokens or 0
        )
        current["output_tokens"] = int(current["output_tokens"]) + (
            call.output_tokens or 0
        )
        current["cached_input_tokens"] = int(
            current["cached_input_tokens"]
        ) + (call.cached_input_tokens or 0)
        current["cost_usd"] = float(current["cost_usd"]) + (call.cost_usd or 0)
        if call.provider:
            providers = current["providers"]
            assert isinstance(providers, defaultdict)
            providers[call.provider] += 1
    return {
        model: ModelUsageStats.model_validate(values)
        for model, values in sorted(counters.items())
    }


def save_run_stats(path: Path, stats: RunStats) -> None:
    encoded = json.dumps(
        stats.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    atomic_write_text(
        path,
        encoded,
        validator=lambda staged: RunStats.model_validate_json(
            staged.read_text(encoding="utf-8")
        ),
    )


def render_run_report(stats: RunStats) -> str:
    source = "OK" if stats.source_ok else "FAILED"
    lines = [
        f"PaperFlow run {stats.run_id}",
        f"Date: {stats.date.isoformat()}",
        f"Source: {source}",
        f"Fetched: {stats.fetched}",
        f"Deduplicated: {stats.deduplicated}",
        f"Screened: {stats.screened}",
        f"KEEP: {stats.kept}",
        "KEEP cap: NONE",
        f"DROP: {stats.dropped}",
        f"FAILED: {stats.filter_failed}",
        f"Summary generated: {stats.summary_generated}",
        f"Summary failed: {stats.summary_failed}",
        f"LLM cost: ${stats.llm_cost_usd:.6f}",
    ]
    for model, usage in stats.model_breakdown.items():
        lines.append(
            f"Model {model}: calls={usage.calls} input={usage.input_tokens} "
            f"output={usage.output_tokens} cost=${usage.cost_usd:.6f}"
        )
    return "\n".join(lines)


def _redact_mapping(fields: Mapping[str, object]) -> dict[str, object]:
    return {key: _redact_value(key, value) for key, value in fields.items()}


def _redact_value(key: str, value: object) -> object:
    normalized = key.lower().replace("-", "_")
    if normalized in {
        "authorization",
        "api_key",
        "openrouter_api_key",
        "token",
        "secret",
        "abstract",
        "raw_abstract",
    }:
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return _redact_mapping(value)
    if isinstance(value, (list, tuple)):
        return [_redact_value(key, item) for item in value]
    if isinstance(value, str) and value.lower().startswith("bearer "):
        return "[REDACTED]"
    return value
