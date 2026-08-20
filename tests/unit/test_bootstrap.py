from __future__ import annotations

from datetime import UTC, datetime
from io import StringIO

import paperflow
from paperflow.observability import create_run_id, parse_run_id, structured_event


def test_package_imports() -> None:
    assert paperflow.__version__ == "0.1.0"


def test_run_ids_are_unique_and_parseable() -> None:
    instant = datetime(2026, 8, 20, 21, 0, tzinfo=UTC)
    first = create_run_id(instant)
    second = create_run_id(instant)

    assert first != second
    assert parse_run_id(first) == instant
    assert parse_run_id(second) == instant


def test_structured_event_is_single_line_json() -> None:
    output = StringIO()
    structured_event("run_started", stream=output, run_id="run-1")

    assert output.getvalue() == '{"event":"run_started","run_id":"run-1"}\n'
