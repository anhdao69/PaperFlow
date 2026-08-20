"""Append-only monthly screening event ledger."""

from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path

from pydantic import ValidationError

from paperflow.models import ScreeningEvent


class ScreeningLedgerError(ValueError):
    """Raised when durable screening history cannot be trusted."""


class ScreeningLedger:
    def __init__(self, root: Path) -> None:
        self.root = root

    def append(self, event: ScreeningEvent) -> Path:
        """Durably append one already-validated event to its observed month."""
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{event.observed_at:%Y-%m}.jsonl"
        encoded = event.model_dump_json(exclude_none=True) + "\n"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        return path

    def append_many(self, events: Iterable[ScreeningEvent]) -> tuple[Path, ...]:
        """Append a validated event batch with one write per monthly ledger."""
        grouped: dict[str, list[ScreeningEvent]] = defaultdict(list)
        for event in events:
            grouped[f"{event.observed_at:%Y-%m}.jsonl"].append(event)
        if not grouped:
            return ()
        self.root.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for filename in sorted(grouped):
            path = self.root / filename
            encoded = "".join(
                event.model_dump_json(exclude_none=True) + "\n"
                for event in grouped[filename]
            )
            with path.open("a", encoding="utf-8") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            paths.append(path)
        return tuple(paths)

    def iter_events(self) -> Iterator[ScreeningEvent]:
        for path in sorted(self.root.glob("????-??.jsonl")):
            try:
                with path.open(encoding="utf-8") as stream:
                    for line_number, line in enumerate(stream, start=1):
                        if not line.strip():
                            raise ScreeningLedgerError(
                                f"blank screening event at {path}:{line_number}"
                            )
                        try:
                            yield ScreeningEvent.model_validate_json(line)
                        except (ValidationError, ValueError) as error:
                            raise ScreeningLedgerError(
                                f"invalid screening event at {path}:{line_number}"
                            ) from error
            except OSError as error:
                message = f"unable to read screening ledger {path}"
                raise ScreeningLedgerError(message) from error

    def load_latest(self) -> dict[str, ScreeningEvent]:
        return reduce_latest_screening_state(self.iter_events())


def reduce_latest_screening_state(
    events: Iterable[ScreeningEvent],
) -> dict[str, ScreeningEvent]:
    """Reduce by timestamp, attempt number, then event UUID for stable ties."""
    latest: dict[str, ScreeningEvent] = {}
    for event in events:
        current = latest.get(event.arxiv_id)
        event_key = (event.observed_at, event.attempt_number, str(event.event_id))
        if current is None:
            latest[event.arxiv_id] = event
            continue
        current_key = (
            current.observed_at,
            current.attempt_number,
            str(current.event_id),
        )
        if event_key > current_key:
            latest[event.arxiv_id] = event
    return latest
