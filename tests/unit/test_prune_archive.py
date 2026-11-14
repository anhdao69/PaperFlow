from __future__ import annotations

import gzip
import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from test_paper_store import _paper

from paperflow.cli.prune_archive import prune_archive as prune
from paperflow.cli.rebuild_outputs import main as rebuild
from paperflow.models import FigureStatus, RunState
from paperflow.paper_store import load_selected_store, save_selected_store
from paperflow.taxonomy import load_taxonomy

ROOT = Path(__file__).parents[2]


def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    shutil.copytree(ROOT / "configs", root / "configs")
    (root / "data").mkdir()
    papers = {}
    for number, day in ((1, "2026-09-20"), (2, "2026-09-21")):
        paper = _paper(
            arxiv_id=f"2609.0000{number}",
            first_seen_date=day,
            first_seen_at=datetime.fromisoformat(day).replace(tzinfo=UTC),
            figure_status=FigureStatus.READY,
            hero_figure=f"figures/2609.0000{number}/hero.webp",
        )
        papers[paper.arxiv_id] = paper
        asset = root / paper.hero_figure
        asset.parent.mkdir(parents=True)
        asset.write_bytes(b"fixture-asset")
    save_selected_store(
        root / "data/papers.json", papers, load_taxonomy(root / "configs/topics.yaml")
    )
    (root / "data/state.json").write_text(RunState().model_dump_json())
    rebuild(["--root", str(root), "--successful-date", "2026-09-19"])
    # Deliberately preserve opaque audit/state bytes; pruning must not rewrite them.
    state = {
        "schema_version": 1,
        "last_successful_local_date": "2026-11-13",
        "last_successful_at": "2026-11-13T21:00:00-05:00",
        "last_successful_run_id": "retained-run",
        "taxonomy_hash": "b" * 64,
        "runtime_config_hash": "b" * 64,
        "model_config_hash": "b" * 64,
    }
    RunState.model_validate(state)
    (root / "data/state.json").write_text(json.dumps(state))
    ledger = root / "data/screening_events/2026-09.jsonl"
    ledger.parent.mkdir()
    ledger.write_text("preserve terminal decisions\n")
    stats = root / "data/run_stats"
    stats.mkdir()
    (stats / "2026-09-20.json").write_text("old stats")
    (stats / "2026-11-13.json").write_text("retained stats")
    return root


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()
    }


def test_dry_run_is_read_only_and_counts_old_assets(tmp_path: Path) -> None:
    root = project(tmp_path)
    before = snapshot(root)
    report = prune(root, before=date(2026, 9, 21))
    assert report.removed_papers == 1
    assert report.removed_days == 2  # Includes the successful zero-paper day.
    assert report.figure_files == 1
    assert report.figure_bytes == 13
    assert snapshot(root) == before


@pytest.mark.parametrize("compressed", [False, True])
def test_apply_removes_oldest_only_and_rebuilds_without_resurrection(
    tmp_path: Path,
    compressed: bool,
) -> None:
    root = project(tmp_path)
    if compressed:
        path = root / "data/papers.json"
        path.with_suffix(".json.gz").write_bytes(
            gzip.compress(path.read_bytes(), mtime=0)
        )
        path.unlink()
    original = snapshot(root)
    assert (root / "site/days/2026-09-20.html").exists()
    taxonomy = load_taxonomy(root / "configs/topics.yaml")
    kept = load_selected_store(root / "data/papers.json", taxonomy).papers["2609.00002"]
    report = prune(root, before=date(2026, 9, 21), apply=True, expected_papers=1)
    assert report.removed_papers == 1
    actual = load_selected_store(root / "data/papers.json", taxonomy)
    assert actual.papers == {"2609.00002": kept}
    assert not (root / "figures/2609.00001").exists()
    assert (root / "figures/2609.00002/hero.webp").read_bytes() == b"fixture-asset"
    assert not (root / "data/run_stats/2026-09-20.json").exists()
    for path in (
        "data/state.json",
        "data/screening_events/2026-09.jsonl",
        "data/run_stats/2026-11-13.json",
    ):
        assert (root / path).read_bytes() == original[path]
    rebuild(["--root", str(root)])
    index = json.loads((root / "data/feed_index.json").read_text())
    assert [day["date"] for day in index["days"]] == ["2026-11-13", "2026-09-21"]
    for path in (
        "daily/2026-09-20.md",
        "data/daily_feeds/2026-09-20.json",
        "site/days/2026-09-20.html",
    ):
        assert not (root / path).exists()
    assert prune(root, before=date(2026, 9, 21), apply=True).removed_papers == 0


@pytest.mark.parametrize(
    "before,expected", [(date(2026, 11, 14), None), (date(2026, 9, 21), 2)]
)
def test_wrong_cutoff_or_expected_count_changes_no_bytes(
    tmp_path: Path, before: date, expected: int | None
) -> None:
    root = project(tmp_path)
    original = snapshot(root)
    with pytest.raises(ValueError):
        prune(root, before=before, apply=True, expected_papers=expected)
    assert snapshot(root) == original


def test_retained_reference_to_old_directory_blocks_removal(tmp_path: Path) -> None:
    root = project(tmp_path)
    taxonomy = load_taxonomy(root / "configs/topics.yaml")
    selected = load_selected_store(root / "data/papers.json", taxonomy)
    selected.papers["2609.00002"].hero_figure = "figures/2609.00001/hero.webp"
    save_selected_store(root / "data/papers.json", selected.papers, taxonomy)
    original = snapshot(root)
    with pytest.raises(ValueError, match="retained"):
        prune(root, before=date(2026, 9, 21), apply=True)
    assert snapshot(root) == original


def test_symlink_in_old_assets_blocks_removal(tmp_path: Path) -> None:
    root = project(tmp_path)
    (root / "figures/2609.00001/link.webp").symlink_to(
        root / "figures/2609.00002/hero.webp"
    )
    original = snapshot(root)
    with pytest.raises(ValueError, match="symlink"):
        prune(root, before=date(2026, 9, 21), apply=True)
    assert snapshot(root) == original


def test_symlinked_stats_directory_cannot_delete_external_files(tmp_path: Path) -> None:
    root = project(tmp_path)
    stats = root / "data/run_stats"
    external = tmp_path / "external-stats"
    stats.rename(external)
    stats.symlink_to(external, target_is_directory=True)
    original = snapshot(root)
    external_before = snapshot(external)
    with pytest.raises(ValueError, match=r"symlink|unsafe"):
        prune(root, before=date(2026, 9, 21), apply=True)
    assert snapshot(root) == original
    assert snapshot(external) == external_before
