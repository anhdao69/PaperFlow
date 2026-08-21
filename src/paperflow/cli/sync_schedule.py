"""Synchronize the generated GitHub Actions schedule block."""

from __future__ import annotations

import argparse
from pathlib import Path

from paperflow.config import RuntimeConfig, load_config_bundle
from paperflow.schedule import cron_candidates

BEGIN_MARKER = "  # BEGIN AUTO-GENERATED PAPERFLOW SCHEDULE"
END_MARKER = "  # END AUTO-GENERATED PAPERFLOW SCHEDULE"
WORKFLOW_PATH = Path(".github/workflows/paperflow-daily.yml")


def generated_block(runtime: RuntimeConfig) -> str:
    candidates = cron_candidates(runtime)
    lines = [BEGIN_MARKER]
    if runtime.schedule.enabled:
        lines.append("  schedule:")
        lines.extend(f'    - cron: "{candidate}"' for candidate in candidates)
    else:
        lines.append("  # Recurring schedule disabled in configs/runtime.yaml.")
        lines.extend(
            f'  # Inactive candidate: "{candidate}"' for candidate in candidates
        )
    lines.append(END_MARKER)
    return "\n".join(lines)


def synchronized_content(content: str, runtime: RuntimeConfig) -> str:
    begin = content.find(BEGIN_MARKER)
    end = content.find(END_MARKER)
    if begin < 0 or end < begin:
        raise ValueError("daily workflow is missing generated schedule markers")
    end += len(END_MARKER)
    return content[:begin] + generated_block(runtime) + content[end:]


def sync_schedule(root: Path, *, check: bool) -> bool:
    runtime = load_config_bundle(root).runtime
    path = root / WORKFLOW_PATH
    current = path.read_text(encoding="utf-8")
    expected = synchronized_content(current, runtime)
    if current == expected:
        return False
    if check:
        raise ValueError(
            "generated workflow schedule is stale; run "
            "python -m paperflow.cli.sync_schedule"
        )
    path.write_text(expected, encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        changed = sync_schedule(arguments.root, check=arguments.check)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print("Schedule synchronized." if changed else "Schedule already synchronized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
