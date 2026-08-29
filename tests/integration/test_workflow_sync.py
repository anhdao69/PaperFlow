from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from paperflow.cli.commit_generated import commit_generated_outputs
from paperflow.cli.sync_schedule import sync_schedule


def git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_enabled_checked_in_workflow_is_synced_and_gates_scheduled_runs() -> None:
    assert sync_schedule(Path("."), check=True) is False
    workflow = Path(".github/workflows/paperflow-daily.yml").read_text()
    assert "\n  schedule:\n" in workflow
    assert '    - cron: "17 1 * * *"' in workflow
    assert '    - cron: "17 5 * * *"' in workflow
    assert "workflow_dispatch:" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "ref: main" in workflow
    assert "python -m paperflow.schedule" in workflow
    assert "--github-output \"$GITHUB_OUTPUT\"" in workflow
    assert "if: steps.schedule.outputs.due == 'true'" in workflow
    assert "OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}" in workflow
    assert 'if [ "${{ github.event_name }}" = "workflow_dispatch" ]' in workflow
    assert "python -m paperflow.main --manual" in workflow
    assert "python -m paperflow.main\n" in workflow


def test_stale_schedule_is_detected_and_sync_is_deterministic(tmp_path: Path) -> None:
    shutil.copytree("configs", tmp_path / "configs")
    workflow = Path(".github/workflows/paperflow-daily.yml")
    target = tmp_path / workflow
    target.parent.mkdir(parents=True)
    shutil.copy2(workflow, target)
    runtime_path = tmp_path / "configs/runtime.yaml"
    runtime = yaml.safe_load(runtime_path.read_text())
    runtime["schedule"]["enabled"] = False
    runtime_path.write_text(yaml.safe_dump(runtime, sort_keys=False))

    with pytest.raises(ValueError, match=r"python -m paperflow\.cli\.sync_schedule"):
        sync_schedule(tmp_path, check=True)
    assert sync_schedule(tmp_path, check=False) is True
    synchronized = target.read_text()
    assert "Recurring schedule disabled" in synchronized
    assert "\n  schedule:\n" not in synchronized
    assert sync_schedule(tmp_path, check=True) is False


def test_generated_commit_allowlist_success_noop_and_failure_safety(
    tmp_path: Path,
) -> None:
    git(tmp_path, "init")
    git(tmp_path, "config", "user.name", "PaperFlow Test")
    git(tmp_path, "config", "user.email", "paperflow@example.invalid")
    (tmp_path / "README.md").write_text("initial\n")
    (tmp_path / "site").mkdir()
    (tmp_path / "site/index.html").write_text("initial\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src/manual.py").write_text("initial\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "initial")

    (tmp_path / "site/index.html").write_text("generated\n")
    (tmp_path / "src/manual.py").write_text("personal change\n")
    assert commit_generated_outputs(tmp_path, message="generated") is True
    assert git(tmp_path, "show", "--name-only", "--format=", "HEAD") == (
        "site/index.html"
    )
    assert "src/manual.py" in git(tmp_path, "status", "--short")
    assert commit_generated_outputs(tmp_path, message="noop") is False

    before = git(tmp_path, "rev-parse", "HEAD")
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run(["false"], cwd=tmp_path, check=True)
    assert git(tmp_path, "rev-parse", "HEAD") == before
    assert git(tmp_path, "diff", "--cached", "--name-only") == ""


def test_pages_workflow_stages_only_public_feed_allowlist() -> None:
    workflow = Path(".github/workflows/pages.yml").read_text()
    assert "workflow_run:" in workflow
    assert "PaperFlow Daily" in workflow
    assert "github.event.workflow_run.conclusion == 'success'" in workflow
    assert "data/feed_index.json" in workflow
    assert "data/topics.json" in workflow
    assert "data/topic_feeds" in workflow
    assert "data/state.json" not in workflow
    assert "data/screening_events" not in workflow
    assert "pages: write" in workflow
