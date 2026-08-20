"""Small structured-observability primitives shared by pipeline stages."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TextIO
from uuid import uuid4

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
    """Write one compact JSON event without inspecting process environment."""
    destination = stream or sys.stdout
    payload: Mapping[str, object] = {"event": event, **fields}
    destination.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    destination.write("\n")
