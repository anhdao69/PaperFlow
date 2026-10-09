from __future__ import annotations

import json
from pathlib import Path

import pytest

import paperflow.main as entrypoint
from paperflow.llm.openrouter import OpenRouterHTTPError

ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 422])
def test_run_failure_reports_http_status_without_provider_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], status: int
) -> None:
    def fail(*args, **kwargs):
        raise OpenRouterHTTPError(status, "private provider response and credential")

    monkeypatch.setattr(entrypoint, "run_pipeline", fail)

    assert entrypoint.main(["--root", str(ROOT)]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "event": "run_failed",
        "error_type": "OpenRouterHTTPError",
        "http_status": status,
    }


def test_other_run_failures_do_not_log_exception_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("private exception detail")

    monkeypatch.setattr(entrypoint, "run_pipeline", fail)

    assert entrypoint.main(["--root", str(ROOT)]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "event": "run_failed",
        "error_type": "RuntimeError",
    }
