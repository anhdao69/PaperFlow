"""DST-safe schedule generation and application-level due gating."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from paperflow.config import RuntimeConfig, load_config_bundle
from paperflow.models import RunState
from paperflow.observability import structured_event
from paperflow.paper_store import load_run_state

# GitHub documents elevated scheduled-workflow load at the start of each hour.
# Poll shortly after the hour and keep four local retry windows. The union across
# daylight and standard time is five UTC triggers, while the application gate
# still permits only one successful publication per configured local date.
CRON_DELIVERY_OFFSET_MINUTES = 17
CRON_RETRY_WINDOWS = 4


@dataclass(frozen=True)
class ScheduleDecision:
    due: bool
    local_date: date
    scheduled_for: datetime
    reason: str


def cron_candidates(runtime: RuntimeConfig, *, year: int = 2026) -> tuple[str, ...]:
    """Return delayed-delivery-resistant UTC triggers for the local schedule."""
    timezone = ZoneInfo(runtime.timezone)
    current = date(year, 1, 1)
    end = date(year + 1, 1, 1)
    candidates: set[tuple[int, int]] = set()
    while current < end:
        local = datetime.combine(current, runtime.schedule.run_at_local, timezone)
        retry_windows = (
            CRON_RETRY_WINDOWS if runtime.schedule.same_day_catchup else 1
        )
        delivery_offset = (
            CRON_DELIVERY_OFFSET_MINUTES
            if runtime.schedule.same_day_catchup
            else 0
        )
        for retry_window in range(retry_windows):
            utc = (
                local
                + timedelta(
                    minutes=delivery_offset,
                    hours=retry_window,
                )
            ).astimezone(UTC)
            candidates.add((utc.minute, utc.hour))
        current += timedelta(days=1)
    return tuple(f"{minute} {hour} * * *" for minute, hour in sorted(candidates))


def evaluate_schedule(
    runtime: RuntimeConfig,
    state: RunState,
    *,
    now: datetime,
    manual: bool = False,
) -> ScheduleDecision:
    """Select the oldest missed publication date that is eligible to run."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("schedule evaluation requires a timezone-aware timestamp")
    timezone = ZoneInfo(runtime.timezone)
    local = now.astimezone(timezone)
    local_date = local.date()
    schedule = runtime.schedule
    if manual:
        return ScheduleDecision(True, local_date, local, "manual_bypass")
    if not schedule.enabled:
        return ScheduleDecision(False, local_date, local, "disabled")

    if state.last_successful_local_date is None:
        scheduled_for = datetime.combine(
            local_date,
            schedule.run_at_local,
            timezone,
        )
        if _day_name(local_date) not in schedule.run_days:
            return ScheduleDecision(
                False,
                local_date,
                scheduled_for,
                "day_not_allowed",
            )
        if local < scheduled_for:
            return ScheduleDecision(False, local_date, scheduled_for, "too_early")
        target_date = local_date
    else:
        latest_due_date = _latest_due_date(local, runtime)
        target_date = _next_allowed_date(
            state.last_successful_local_date,
            runtime,
        )
        if target_date > latest_due_date:
            scheduled_for = datetime.combine(
                latest_due_date,
                schedule.run_at_local,
                timezone,
            )
            return ScheduleDecision(
                False,
                latest_due_date,
                scheduled_for,
                "already_succeeded",
            )
        scheduled_for = datetime.combine(
            target_date,
            schedule.run_at_local,
            timezone,
        )

    if local > scheduled_for and not schedule.same_day_catchup:
        return ScheduleDecision(
            False,
            target_date,
            scheduled_for,
            "catchup_disabled",
        )
    return ScheduleDecision(True, target_date, scheduled_for, "due")


def _latest_due_date(local: datetime, runtime: RuntimeConfig) -> date:
    candidate = local.date()
    scheduled_today = datetime.combine(
        candidate,
        runtime.schedule.run_at_local,
        local.tzinfo,
    )
    if local < scheduled_today:
        candidate -= timedelta(days=1)
    while _day_name(candidate) not in runtime.schedule.run_days:
        candidate -= timedelta(days=1)
    return candidate


def _next_allowed_date(previous: date, runtime: RuntimeConfig) -> date:
    candidate = previous + timedelta(days=1)
    while _day_name(candidate) not in runtime.schedule.run_days:
        candidate += timedelta(days=1)
    return candidate


def _day_name(value: date) -> str:
    return value.strftime("%A").lower()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--manual", action="store_true")
    parser.add_argument("--now", help="ISO-8601 aware timestamp for controlled checks")
    parser.add_argument(
        "--github-output",
        type=Path,
        help="append the due decision to a GitHub Actions output file",
    )
    arguments = parser.parse_args(argv)
    bundle = load_config_bundle(arguments.root)
    state_path = arguments.root / "data" / "state.json"
    state = load_run_state(state_path) if state_path.exists() else RunState()
    now = datetime.fromisoformat(arguments.now) if arguments.now else datetime.now(UTC)
    decision = evaluate_schedule(
        bundle.runtime,
        state,
        now=now,
        manual=arguments.manual,
    )
    structured_event(
        "schedule_gate",
        due=decision.due,
        local_date=decision.local_date.isoformat(),
        scheduled_for=decision.scheduled_for.isoformat(),
        reason=decision.reason,
    )
    if arguments.github_output is not None:
        with arguments.github_output.open("a", encoding="utf-8") as output:
            output.write(f"due={str(decision.due).lower()}\n")
            output.write(f"local_date={decision.local_date.isoformat()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
