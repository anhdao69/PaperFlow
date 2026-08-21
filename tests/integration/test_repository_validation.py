from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from paperflow.generated_files import GENERATED_FILE_MARKER
from paperflow.paper_store import load_selected_store
from paperflow.render.validation import validate_repository
from paperflow.taxonomy import load_taxonomy

ROOT = Path(__file__).parents[2]


def copy_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    for relative in ("configs", "data", "figures", "site", "topics"):
        shutil.copytree(ROOT / relative, project / relative)
    if (ROOT / "daily").exists():
        shutil.copytree(ROOT / "daily", project / "daily")
    shutil.copy2(ROOT / "README.md", project / "README.md")
    workflow = project / ".github/workflows/paperflow-daily.yml"
    workflow.parent.mkdir(parents=True)
    shutil.copy2(ROOT / ".github/workflows/paperflow-daily.yml", workflow)
    return project


def snapshot(project: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(project)): path.read_bytes()
        for path in sorted(project.rglob("*"))
        if path.is_file()
    }


def test_checked_in_repository_passes_full_validation() -> None:
    report = validate_repository(ROOT)
    taxonomy = load_taxonomy(ROOT / "configs/topics.yaml")
    selected = load_selected_store(ROOT / "data/papers.json", taxonomy)

    assert report.selected_papers == len(selected.papers)
    assert report.generated_files > 80


def test_validation_failure_changes_no_bytes(tmp_path: Path) -> None:
    project = copy_project(tmp_path)
    index = project / "data/feed_index.json"
    content = json.loads(index.read_text())
    content["day_count"] += 1
    index.write_text(json.dumps(content, indent=2, sort_keys=True) + "\n")
    before = snapshot(project)

    with pytest.raises(ValueError):
        validate_repository(project)

    assert snapshot(project) == before


def test_stale_marked_site_file_is_rejected(tmp_path: Path) -> None:
    project = copy_project(tmp_path)
    stale = project / "site/stale.html"
    stale.write_text(GENERATED_FILE_MARKER)

    with pytest.raises(ValueError, match="stale generated artifact"):
        validate_repository(project)


def test_ready_figure_asset_must_exist(tmp_path: Path) -> None:
    project = copy_project(tmp_path)
    papers_path = project / "data/papers.json"
    content = json.loads(papers_path.read_text())
    paper = next(iter(content["papers"].values()))
    paper["figure_status"] = "ready"
    paper["hero_figure"] = "figures/does-not-exist/hero.webp"
    papers_path.write_text(json.dumps(content, indent=2, sort_keys=True) + "\n")

    with pytest.raises(ValueError, match="ready figure asset is missing"):
        validate_repository(project)
