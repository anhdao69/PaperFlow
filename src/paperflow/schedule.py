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


@dataclass(frozen=True)
class ScheduleDecision:
    due: bool
    local_date: date
    reason: str


def cron_candidates(runtime: RuntimeConfig, *, year: int = 2026) -> tuple[str, ...]:
    """Return every UTC cron needed for the configured local wall-clock time."""
    timezone = ZoneInfo(runtime.timezone)
    current = date(year, 1, 1)
    end = date(year + 1, 1, 1)
    candidates: set[tuple[int, int]] = set()
    while current < end:
        local = datetime.combine(current, runtime.schedule.run_at_local, timezone)
        utc = local.astimezone(UTC)
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
    """Decide whether a trigger may run without mutating state."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("schedule evaluation requires a timezone-aware timestamp")
    local = now.astimezone(ZoneInfo(runtime.timezone))
    local_date = local.date()
    schedule = runtime.schedule
    if manual:
        return ScheduleDecision(True, local_date, "manual_bypass")
    if not schedule.enabled:
        return ScheduleDecision(False, local_date, "disabled")
    if local.strftime("%A").lower() not in schedule.run_days:
        return ScheduleDecision(False, local_date, "day_not_allowed")
    if state.last_successful_local_date == local_date:
        return ScheduleDecision(False, local_date, "already_succeeded")

    local_minutes = local.hour * 60 + local.minute
    due_minutes = schedule.run_at_local.hour * 60 + schedule.run_at_local.minute
    if local_minutes < due_minutes:
        return ScheduleDecision(False, local_date, "too_early")
    if local_minutes > due_minutes and not schedule.same_day_catchup:
        return ScheduleDecision(False, local_date, "catchup_disabled")
    return ScheduleDecision(True, local_date, "due")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--manual", action="store_true")
    parser.add_argument("--now", help="ISO-8601 aware timestamp for controlled checks")
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
        reason=decision.reason,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
