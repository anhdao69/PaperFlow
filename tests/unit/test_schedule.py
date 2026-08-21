from __future__ import annotations

from datetime import UTC, datetime

import pytest

from paperflow.config import RuntimeConfig, ScheduleConfig, load_config_bundle
from paperflow.models import RunState
from paperflow.schedule import cron_candidates, evaluate_schedule


def runtime(**schedule_updates: object) -> RuntimeConfig:
    base = load_config_bundle().runtime
    schedule = base.schedule.model_copy(
        update={"enabled": True, **schedule_updates}
    )
    return base.model_copy(update={"schedule": schedule})


def decision(
    now: datetime,
    *,
    state: RunState | None = None,
    manual: bool = False,
    schedule: ScheduleConfig | None = None,
):
    configured = runtime()
    if schedule is not None:
        configured = configured.model_copy(update={"schedule": schedule})
    return evaluate_schedule(
        configured,
        state or RunState(),
        now=now,
        manual=manual,
    )


def test_cron_candidates_cover_est_and_edt_deterministically() -> None:
    assert cron_candidates(runtime()) == ("0 1 * * *", "0 2 * * *")
    assert cron_candidates(runtime()) == cron_candidates(runtime())


@pytest.mark.parametrize(
    ("now", "expected_due"),
    [
        (datetime(2026, 7, 2, 1, tzinfo=UTC), True),
        (datetime(2026, 1, 2, 2, tzinfo=UTC), True),
        (datetime(2026, 1, 2, 1, tzinfo=UTC), False),
        (datetime(2026, 3, 9, 1, tzinfo=UTC), True),
        (datetime(2026, 11, 2, 2, tzinfo=UTC), True),
    ],
)
def test_gate_handles_dst_boundaries_and_wrong_candidate(
    now: datetime, expected_due: bool
) -> None:
    assert decision(now).due is expected_due


def test_disabled_disallowed_early_and_duplicate_reasons() -> None:
    base = runtime()
    disabled = base.schedule.model_copy(update={"enabled": False})
    assert decision(datetime(2026, 8, 21, 2, tzinfo=UTC), schedule=disabled).reason == (
        "disabled"
    )

    monday_only = base.schedule.model_copy(update={"run_days": ["monday"]})
    assert decision(
        datetime(2026, 8, 22, 2, tzinfo=UTC), schedule=monday_only
    ).reason == "day_not_allowed"
    assert decision(datetime(2026, 8, 21, 0, tzinfo=UTC)).reason == "too_early"

    state = RunState(
        last_successful_run_id="run",
        last_successful_at=datetime(2026, 8, 20, 23, tzinfo=UTC),
        last_successful_local_date="2026-08-20",
        runtime_config_hash="a" * 64,
        model_config_hash="b" * 64,
        taxonomy_hash="c" * 64,
    )
    assert decision(datetime(2026, 8, 21, 3, tzinfo=UTC), state=state).reason == (
        "already_succeeded"
    )


def test_same_day_catchup_and_manual_bypass() -> None:
    late = datetime(2026, 8, 22, 2, tzinfo=UTC)
    assert decision(late).reason == "due"
    base = runtime()
    no_catchup = base.schedule.model_copy(update={"same_day_catchup": False})
    assert decision(late, schedule=no_catchup).reason == "catchup_disabled"
    disabled = base.schedule.model_copy(update={"enabled": False})
    assert decision(late, schedule=disabled, manual=True).reason == "manual_bypass"


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        decision(datetime(2026, 8, 20, 21))
