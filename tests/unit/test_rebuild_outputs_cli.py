from __future__ import annotations

import shutil
import socket
from pathlib import Path

from paperflow.cli.rebuild_outputs import main
from paperflow.render.contracts import DailyFeed, FeedIndex

ROOT = Path(__file__).parents[2]


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "configs", project / "configs")
    (project / "data").mkdir()
    shutil.copy2(ROOT / "data/papers.json", project / "data/papers.json")
    shutil.copy2(ROOT / "data/state.json", project / "data/state.json")
    return project


def _snapshot(project: Path) -> dict[str, bytes]:
    roots = [
        project / "README.md",
        project / "daily",
        project / "topics",
        project / "site",
        project / "data",
    ]
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(path for path in root.rglob("*") if path.is_file())
    return {
        str(path.relative_to(project)): path.read_bytes() for path in sorted(files)
    }


def test_rebuild_is_deterministic_and_uses_no_network(
    tmp_path: Path, monkeypatch
) -> None:
    project = _project(tmp_path)

    def fail_network(*args, **kwargs):
        del args, kwargs
        raise AssertionError("rebuild_outputs attempted network access")

    monkeypatch.setattr(socket, "create_connection", fail_network)

    assert main(["--root", str(project)]) == 0
    first = _snapshot(project)
    assert main(["--root", str(project)]) == 0
    second = _snapshot(project)

    assert first == second
    assert "README.md" in first
    assert "data/feed_index.json" in first
    assert "data/topics.json" in first
    assert "site/index.html" in first
    assert "site/assets/style.css" in first
    assert not any(path.startswith("daily/") for path in first)


def test_rebuild_generates_and_preserves_successful_zero_day(tmp_path: Path) -> None:
    project = _project(tmp_path)

    assert (
        main(
            [
                "--root",
                str(project),
                "--successful-date",
                "2026-08-20",
                "--generated-at",
                "2026-08-20T21:05:00-04:00",
            ]
        )
        == 0
    )
    index = FeedIndex.model_validate_json(
        (project / "data/feed_index.json").read_text(encoding="utf-8")
    )
    daily = DailyFeed.model_validate_json(
        (project / "data/daily_feeds/2026-08-20.json").read_text(
            encoding="utf-8"
        )
    )

    assert index.days[0].paper_count == 0
    assert daily.paper_count == 0
    assert "No papers matched" in (
        project / "daily/2026-08-20.md"
    ).read_text(encoding="utf-8")

    assert main(["--root", str(project)]) == 0
    rebuilt = FeedIndex.model_validate_json(
        (project / "data/feed_index.json").read_text(encoding="utf-8")
    )
    assert [day.date.isoformat() for day in rebuilt.days] == ["2026-08-20"]
