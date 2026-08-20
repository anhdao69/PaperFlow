"""PaperFlow command entry point.

Pipeline behavior is added by later implementation phases.
"""

from __future__ import annotations

from paperflow.observability import create_run_id, structured_event


def main() -> int:
    """Start a no-op bootstrap run and return success."""
    run_id = create_run_id()
    structured_event("run_started", run_id=run_id, phase="bootstrap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
